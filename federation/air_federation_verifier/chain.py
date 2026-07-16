"""Independent on-chain settlement verification for AIR/1 receipts.

Signature verification (:mod:`.verify`) proves *who said what*. It does not
prove the payment happened. For that, a federation node asks the blockchain
directly, because the chain, not the issuer, is authoritative on settlement.

Given a receipt's ``settlement`` block (``chain``, ``tx_hash``), this module
queries a public JSON-RPC endpoint and reports whether the transaction exists
and succeeded. It uses only the standard node RPC, so any third party
pointing at any node (their own, or a public one) reaches the same answer.

Two families are supported, matching the two signature suites:

* EVM chains (Base, etc.) via ``eth_getTransactionReceipt``; success is
  ``status == 0x1``.
* Solana via ``getSignatureStatuses``; success is a confirmed/finalized
  status with no ``err``.

Network access is required and is the caller's choice of endpoint. The
functions never contact the issuer.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

# Public RPC endpoints used when the caller does not supply one. These are
# well-known community endpoints; a federation node is expected to point at
# an endpoint it trusts (ideally its own node).
DEFAULT_RPC = {
    "base": "https://mainnet.base.org",
    "base-sepolia": "https://sepolia.base.org",
    "solana": "https://api.mainnet-beta.solana.com",
    "solana-devnet": "https://api.devnet.solana.com",
}

# Which suite family a chain id belongs to.
_EVM_CHAINS = {"base", "base-sepolia", "ethereum", "optimism", "arbitrum"}
_SOLANA_CHAINS = {"solana", "solana-devnet", "solana-testnet"}


@dataclass
class SettlementReport:
    """Result of an on-chain settlement lookup."""

    checked: bool          # did we actually query a chain?
    confirmed: Optional[bool]  # True/False if checked; None if not
    chain: Optional[str]
    tx_hash: Optional[str]
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "checked": self.checked,
            "confirmed": self.confirmed,
            "chain": self.chain,
            "tx_hash": self.tx_hash,
            "detail": self.detail,
        }


def _rpc_call(endpoint: str, method: str, params: list[Any],
              timeout: float = 15.0) -> Any:
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    ).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if "error" in body and body["error"]:
        raise RuntimeError(f"RPC error: {body['error']}")
    return body.get("result")


def _resolve_endpoint(chain: str, endpoint: Optional[str]) -> Optional[str]:
    if endpoint:
        return endpoint
    return DEFAULT_RPC.get(chain)


def verify_settlement(
    settlement: dict[str, Any],
    *,
    endpoint: Optional[str] = None,
    timeout: float = 15.0,
) -> SettlementReport:
    """Check that a receipt's settlement transaction exists and succeeded.

    Args:
        settlement: The receipt's ``settlement`` block. Must carry ``chain``
            and ``tx_hash``.
        endpoint: JSON-RPC URL to use. Defaults to a public endpoint for the
            named chain. Pass your own node for a fully self-sovereign check.
        timeout: Per-request timeout in seconds.

    Returns:
        A :class:`SettlementReport`. ``checked`` is False when we could not
        even attempt the lookup (unknown chain, missing tx hash), which is a
        distinct state from a lookup that ran and returned "not confirmed".
    """
    chain = settlement.get("chain")
    tx_hash = settlement.get("tx_hash")

    if not chain or not tx_hash:
        return SettlementReport(
            checked=False, confirmed=None, chain=chain, tx_hash=tx_hash,
            detail="settlement is missing chain or tx_hash",
        )

    url = _resolve_endpoint(chain, endpoint)
    if url is None:
        return SettlementReport(
            checked=False, confirmed=None, chain=chain, tx_hash=tx_hash,
            detail=f"no RPC endpoint known for chain {chain!r}; pass endpoint=",
        )

    try:
        if chain in _EVM_CHAINS:
            return _verify_evm_tx(url, chain, tx_hash, timeout)
        if chain in _SOLANA_CHAINS:
            return _verify_solana_tx(url, chain, tx_hash, timeout)
        return SettlementReport(
            checked=False, confirmed=None, chain=chain, tx_hash=tx_hash,
            detail=f"unknown chain family for {chain!r}",
        )
    except Exception as exc:  # network / RPC failure is "not checked"
        return SettlementReport(
            checked=False, confirmed=None, chain=chain, tx_hash=tx_hash,
            detail=f"RPC lookup failed: {exc}",
        )


def _verify_evm_tx(url: str, chain: str, tx_hash: str,
                   timeout: float) -> SettlementReport:
    receipt = _rpc_call(url, "eth_getTransactionReceipt", [tx_hash], timeout)
    if receipt is None:
        return SettlementReport(
            checked=True, confirmed=False, chain=chain, tx_hash=tx_hash,
            detail="transaction not found or not yet mined",
        )
    status = receipt.get("status")
    confirmed = str(status).lower() in ("0x1", "1")
    return SettlementReport(
        checked=True, confirmed=confirmed, chain=chain, tx_hash=tx_hash,
        detail=f"eth_getTransactionReceipt status={status}",
    )


def _verify_solana_tx(url: str, chain: str, tx_hash: str,
                      timeout: float) -> SettlementReport:
    result = _rpc_call(
        url,
        "getSignatureStatuses",
        [[tx_hash], {"searchTransactionHistory": True}],
        timeout,
    )
    value = (result or {}).get("value") or [None]
    status = value[0]
    if status is None:
        return SettlementReport(
            checked=True, confirmed=False, chain=chain, tx_hash=tx_hash,
            detail="signature not found on chain",
        )
    confirmed = status.get("err") is None and status.get(
        "confirmationStatus"
    ) in ("confirmed", "finalized")
    return SettlementReport(
        checked=True, confirmed=confirmed, chain=chain, tx_hash=tx_hash,
        detail=f"getSignatureStatuses status={status}",
    )
