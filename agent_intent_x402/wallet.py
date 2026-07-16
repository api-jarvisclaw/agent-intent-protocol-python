"""x402 wallet — sign HTTP 402 payment challenges with an EVM private key.

This is the core of ``agent-intent-x402``: it lets an agent pay for a
request over the open `x402 <https://x402.org>`_ protocol without any
platform-specific glue. Given a 402 challenge, the wallet builds and
signs an EIP-712 ``TransferWithAuthorization`` (EIP-3009) message and
returns the ``PAYMENT-SIGNATURE`` header value the server expects.

The signing is vendor-neutral: it targets the standard USDC
``TransferWithAuthorization`` typed-data used across the x402 ecosystem,
so the same wallet works against any compliant x402 gateway, not just one
platform.

    from agent_intent_x402 import Wallet

    wallet = Wallet(private_key="0x...")
    header = wallet.sign_challenge(challenge)  # PAYMENT-SIGNATURE value
"""

from __future__ import annotations

import base64
import json
import secrets
import time
from typing import Any, Optional

# Default asset: USDC on Base (eip155:8453). Used only when a 402 challenge
# omits the asset address. The EIP-712 domain name/version below match the
# canonical USDC TransferWithAuthorization contract.
DEFAULT_NETWORK = "eip155:8453"
DEFAULT_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_DOMAIN_NAME = "USD Coin"
USDC_DOMAIN_VERSION = "2"

# The x402 protocol version this wallet speaks.
X402_VERSION = 2


class WalletError(Exception):
    """Raised when a 402 challenge cannot be parsed or signed."""


def _import_eth_account() -> Any:
    try:
        from eth_account import Account  # noqa: WPS433 (local import by design)
    except ImportError as exc:  # pragma: no cover - exercised via message only
        raise WalletError(
            "x402 payment requires the 'eth-account' package. "
            "Install it with: pip install 'agent-intent-x402[wallet]'"
        ) from exc
    return Account


class Wallet:
    """An EVM wallet that signs x402 payment challenges.

    Args:
        private_key: Hex private key (with or without the ``0x`` prefix).

    The wallet never sends funds itself. It produces a signed
    authorization that the gateway settles on-chain, so a single signature
    authorizes exactly the amount named in the challenge and nothing more.
    """

    def __init__(self, private_key: str) -> None:
        account_cls = _import_eth_account()
        key = private_key if private_key.startswith("0x") else f"0x{private_key}"
        self._account = account_cls.from_key(key)
        self.address: str = self._account.address

    # ── public API ─────────────────────────────────────────────────────
    def sign_challenge(self, challenge: Any) -> str:
        """Sign a 402 challenge and return the ``PAYMENT-SIGNATURE`` value.

        Args:
            challenge: The parsed JSON body of the 402 response. The first
                entry of ``accepts`` is used as the payment terms.

        Returns:
            A base64-encoded x402 v2 payload suitable for the
            ``PAYMENT-SIGNATURE`` request header.
        """
        terms = self._select_terms(challenge)
        return self._sign_terms(terms)

    # ── internals ──────────────────────────────────────────────────────
    @staticmethod
    def _select_terms(challenge: Any) -> dict[str, Any]:
        if not isinstance(challenge, dict):
            raise WalletError("402 challenge body is not a JSON object")
        accepts = challenge.get("accepts")
        if not isinstance(accepts, list) or not accepts:
            raise WalletError("402 challenge has no 'accepts' payment terms")
        terms = accepts[0]
        if not isinstance(terms, dict):
            raise WalletError("402 payment terms are malformed")
        if not terms.get("payTo"):
            raise WalletError("402 payment terms missing 'payTo'")
        if terms.get("amount") in (None, ""):
            raise WalletError("402 payment terms missing 'amount'")
        return terms

    def _sign_terms(self, terms: dict[str, Any]) -> str:
        network = terms.get("network") or DEFAULT_NETWORK
        asset = terms.get("asset") or DEFAULT_USDC
        pay_to = terms["payTo"]
        amount = str(terms["amount"])
        max_timeout = int(terms.get("maxTimeoutSeconds", 60))
        extra = terms.get("extra")

        chain_id = _chain_id_from_network(network)
        now = int(time.time())
        valid_after = 0
        valid_before = now + max_timeout
        nonce = "0x" + secrets.token_hex(32)

        signature = self._sign_transfer_authorization(
            chain_id=chain_id,
            verifying_contract=asset,
            from_addr=self.address,
            to_addr=pay_to,
            value=amount,
            valid_after=valid_after,
            valid_before=valid_before,
            nonce_hex=nonce,
        )

        payload = {
            "x402Version": X402_VERSION,
            "accepted": {
                "scheme": terms.get("scheme", "exact"),
                "network": network,
                "amount": amount,
                "asset": asset,
                "payTo": pay_to,
                "maxTimeoutSeconds": max_timeout,
                "extra": extra if extra is not None else {},
            },
            "payload": {
                "signature": signature,
                "authorization": {
                    "from": self.address,
                    "to": pay_to,
                    "value": amount,
                    "validAfter": str(valid_after),
                    "validBefore": str(valid_before),
                    "nonce": nonce,
                },
            },
            "extensions": {},
        }
        payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return base64.b64encode(payload_json).decode("ascii")

    def _sign_transfer_authorization(
        self,
        *,
        chain_id: int,
        verifying_contract: str,
        from_addr: str,
        to_addr: str,
        value: str,
        valid_after: int,
        valid_before: int,
        nonce_hex: str,
    ) -> str:
        account_cls = _import_eth_account()
        from eth_account.messages import encode_typed_data

        full_message = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "TransferWithAuthorization": [
                    {"name": "from", "type": "address"},
                    {"name": "to", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "validAfter", "type": "uint256"},
                    {"name": "validBefore", "type": "uint256"},
                    {"name": "nonce", "type": "bytes32"},
                ],
            },
            "primaryType": "TransferWithAuthorization",
            "domain": {
                "name": USDC_DOMAIN_NAME,
                "version": USDC_DOMAIN_VERSION,
                "chainId": chain_id,
                "verifyingContract": verifying_contract,
            },
            "message": {
                "from": from_addr,
                "to": to_addr,
                "value": int(value),
                "validAfter": valid_after,
                "validBefore": valid_before,
                "nonce": bytes.fromhex(nonce_hex[2:]),
            },
        }
        signable = encode_typed_data(full_message=full_message)
        signed = account_cls.sign_message(signable, private_key=self._account.key)
        # eth-account already yields v in {27, 28}; do not add 27 again.
        return "0x" + signed.signature.hex()


def _chain_id_from_network(network: str) -> int:
    """Extract the numeric chain id from an ``eip155:<id>`` network string."""
    if network.startswith("eip155:"):
        tail = network.split(":", 1)[1]
        try:
            return int(tail)
        except ValueError:
            pass
    return 8453  # default to Base
