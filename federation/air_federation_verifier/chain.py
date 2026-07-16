"""Independent on-chain settlement verification for AIR/1 receipts.

Signature verification (:mod:`.verify`) proves *who said what*. It does not
prove the payment happened. For that, a federation node asks the blockchain
directly, because the chain, not the issuer, is authoritative on settlement.

Given a receipt's ``settlement`` block the module queries a public JSON-RPC
endpoint and confirms the transaction. It uses only standard node RPC methods,
so any third party pointing at any node (their own, or a public one) reaches
the same answer without trusting the issuer.

Two families are supported, matching the two signature suites:

* EVM chains (Base, etc.) via ``eth_getTransactionReceipt``. The transaction
  must have succeeded (``status == 0x1``) and, when the settlement names an
  ``asset``/``amount``/``pay_to``, the receipt logs must contain a matching
  ERC-20 ``Transfer`` event. Matching the event, not just the status, is what
  turns "a transaction exists" into "the stated payment happened".
* Solana via ``getSignatureStatuses``; success is a confirmed/finalized
  status with no ``err``.

Network access is required and is the caller's choice of endpoint. The
functions never contact the issuer.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

# Public RPC endpoints used when the caller does not supply one. These are
# well-known community endpoints; a federation node is expected to point at
# an endpoint it trusts (ideally its own node).
DEFAULT_RPC = {
    "base": "https://base.drpc.org",
    "base-sepolia": "https://sepolia.base.org",
    "solana": "https://api.mainnet-beta.solana.com",
    "solana-devnet": "https://api.devnet.solana.com",
}

# CAIP-2 network identifiers mapped to the internal chain key used above.
_CAIP2_TO_CHAIN = {
    "eip155:8453": "base",
    "eip155:84532": "base-sepolia",
    "eip155:1": "ethereum",
    "eip155:10": "optimism",
    "eip155:42161": "arbitrum",
    "solana:mainnet": "solana",
    "solana:devnet": "solana-devnet",
    # CAIP-2 genesis-hash form for Solana mainnet.
    "solana:5eykt4usfv8p8njdtrepy1vzqkqzkvdp": "solana",
}

# Which suite family a chain key belongs to.
_EVM_CHAINS = {"base", "base-sepolia", "ethereum", "optimism", "arbitrum"}
_SOLANA_CHAINS = {"solana", "solana-devnet", "solana-testnet"}

# keccak256("Transfer(address,address,uint256)")
_TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)


@dataclass
class SettlementReport:
    """Result of an on-chain settlement lookup.

    ``checked`` distinguishes "we could not even ask the chain" (unknown
    network, missing tx hash, RPC unreachable) from "we asked and got an
    answer". ``confirmed`` is the answer, and is ``None`` when not checked.
    ``matched`` reports whether the on-chain transfer matched the settlement's
    stated ``amount``/``asset``/``pay_to``; it is ``None`` when the settlement
    did not state enough to check a transfer (status-only confirmation).
    """

    checked: bool
    confirmed: Optional[bool]
    chain: Optional[str]
    tx_hash: Optional[str]
    detail: str
    matched: Optional[bool] = None
    transfers: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "checked": self.checked,
            "confirmed": self.confirmed,
            "matched": self.matched,
            "chain": self.chain,
            "tx_hash": self.tx_hash,
            "detail": self.detail,
            "transfers": self.transfers,
        }


def _rpc_call(endpoint: str, method: str, params: list[Any],
              timeout: float = 15.0) -> Any:
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    ).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "content-type": "application/json",
            # Some public gateways 403 requests without a browser-like UA.
            "User-Agent": "air-federation-verifier/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if "error" in body and body["error"]:
        raise RuntimeError(f"RPC error: {body['error']}")
    return body.get("result")


def _resolve_chain(settlement: dict[str, Any]) -> Optional[str]:
    """Map the settlement's network id to an internal chain key.

    Prefers the spec ``network`` field (CAIP-2, e.g. ``eip155:8453``) and
    falls back to a legacy ``chain`` field.
    """
    network = settlement.get("network")
    if network:
        key = str(network).lower()
        if key in _CAIP2_TO_CHAIN:
            return _CAIP2_TO_CHAIN[key]
        # Bare families like "solana" also accepted.
        if key in _EVM_CHAINS or key in _SOLANA_CHAINS:
            return key
        return None
    chain = settlement.get("chain")
    return str(chain).lower() if chain else None


def _resolve_endpoint(chain: str, endpoint: Optional[str]) -> Optional[str]:
    if endpoint:
        return endpoint
    return DEFAULT_RPC.get(chain)


def _norm_addr(addr: Optional[str]) -> Optional[str]:
    return addr.lower() if addr else None


def verify_settlement(
    settlement: dict[str, Any],
    *,
    endpoint: Optional[str] = None,
    timeout: float = 15.0,
) -> SettlementReport:
    """Check a receipt's settlement against the chain.

    For EVM chains, confirms the transaction succeeded and, when the
    settlement names ``amount``/``asset``/``pay_to``, that a matching ERC-20
    ``Transfer`` event is present in the transaction's logs. For Solana,
    confirms the signature reached a confirmed/finalized status.

    Args:
        settlement: The receipt's ``settlement`` block. Must carry a network
            id (``network`` CAIP-2, or legacy ``chain``) and ``tx_hash``.
        endpoint: JSON-RPC URL to use. Defaults to a public endpoint for the
            named chain. Pass your own node for a fully self-sovereign check.
        timeout: Per-request timeout in seconds.

    Returns:
        A :class:`SettlementReport`.
    """
    tx_hash = settlement.get("tx_hash")
    chain = _resolve_chain(settlement)

    if not tx_hash:
        return SettlementReport(
            checked=False, confirmed=None, chain=chain, tx_hash=tx_hash,
            detail="settlement is missing tx_hash",
        )
    if chain is None:
        return SettlementReport(
            checked=False, confirmed=None, chain=chain, tx_hash=tx_hash,
            detail="settlement has no known network/chain identifier",
        )

    url = _resolve_endpoint(chain, endpoint)
    if url is None:
        return SettlementReport(
            checked=False, confirmed=None, chain=chain, tx_hash=tx_hash,
            detail=f"no RPC endpoint known for chain {chain!r}; pass endpoint=",
        )

    try:
        if chain in _EVM_CHAINS:
            return _verify_evm_tx(url, chain, tx_hash, settlement, timeout)
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


def _decode_transfers(logs: list[dict[str, Any]],
                      asset: Optional[str]) -> list[dict[str, Any]]:
    """Decode ERC-20 Transfer events from receipt logs.

    If ``asset`` is given, only transfers emitted by that token contract are
    returned. Each transfer is ``{asset, from, to, value}`` with ``value`` an
    integer in the token's smallest unit.
    """
    want = _norm_addr(asset)
    out: list[dict[str, Any]] = []
    for lg in logs or []:
        topics = lg.get("topics") or []
        if not topics or topics[0].lower() != _TRANSFER_TOPIC:
            continue
        if len(topics) < 3:  # indexed from + to
            continue
        token = _norm_addr(lg.get("address"))
        if want is not None and token != want:
            continue
        out.append({
            "asset": token,
            "from": "0x" + topics[1][-40:],
            "to": "0x" + topics[2][-40:],
            "value": int(lg.get("data", "0x0"), 16),
        })
    return out


def _verify_evm_tx(url: str, chain: str, tx_hash: str,
                   settlement: dict[str, Any],
                   timeout: float) -> SettlementReport:
    receipt = _rpc_call(url, "eth_getTransactionReceipt", [tx_hash], timeout)
    if receipt is None:
        return SettlementReport(
            checked=True, confirmed=False, chain=chain, tx_hash=tx_hash,
            detail="transaction not found or not yet mined",
        )
    status = receipt.get("status")
    confirmed = str(status).lower() in ("0x1", "1")
    if not confirmed:
        return SettlementReport(
            checked=True, confirmed=False, chain=chain, tx_hash=tx_hash,
            detail=f"transaction reverted (status={status})",
        )

    asset = settlement.get("asset")
    pay_to = _norm_addr(settlement.get("pay_to"))
    amount_str = settlement.get("amount")

    transfers = _decode_transfers(receipt.get("logs", []), asset)

    # Status-only confirmation when the settlement does not state a transfer
    # to check. The transaction succeeded; there is nothing more to match.
    if not (asset and pay_to and amount_str is not None):
        return SettlementReport(
            checked=True, confirmed=True, chain=chain, tx_hash=tx_hash,
            detail="transaction succeeded; settlement did not state "
                   "asset/pay_to/amount to match a transfer",
            matched=None, transfers=transfers,
        )

    try:
        want_amount = int(str(amount_str))
    except ValueError:
        return SettlementReport(
            checked=True, confirmed=True, chain=chain, tx_hash=tx_hash,
            detail=f"settlement amount {amount_str!r} is not an integer "
                   "smallest-unit string",
            matched=False, transfers=transfers,
        )

    matched = any(
        t["to"].lower() == pay_to and t["value"] == want_amount
        for t in transfers
    )
    if matched:
        detail = (
            f"transaction succeeded and an ERC-20 Transfer of {want_amount} "
            f"(smallest unit) of {_norm_addr(asset)} to {pay_to} is present"
        )
    else:
        detail = (
            f"transaction succeeded but no ERC-20 Transfer of {want_amount} "
            f"(smallest unit) of {_norm_addr(asset)} to {pay_to} was found "
            f"among {len(transfers)} matching-asset transfer(s)"
        )
    return SettlementReport(
        checked=True, confirmed=True, chain=chain, tx_hash=tx_hash,
        detail=detail, matched=matched, transfers=transfers,
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
