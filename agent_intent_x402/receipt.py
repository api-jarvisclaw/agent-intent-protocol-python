"""Offline-verifiable settlement receipts — the AIR/1 format.

An **AIR/1** (Agent Intent Receipt) is a self-certifying record that a
request was fulfilled by a named provider and paid for on-chain. Anyone can
verify a receipt *without trusting the party that issued it*:

1. Recompute ``intent_hash`` from the original intent.
2. Recompute ``result_hash`` from the returned result.
3. Verify the issuer's signature over the canonical receipt bytes.
4. Check ``settlement.tx_hash`` on-chain to confirm the payment.

Three independent parties back three independent facts:

* The **x402 facilitator** (e.g. Coinbase's) settles the payment on-chain
  and produces ``tx_hash``. It holds its own key; the receipt never needs it.
* Cryptographic **hashes** bind the intent and result to the receipt.
* The **issuer** — the resolver/gateway that fulfilled the request — signs
  the whole receipt with its own key, identified by ``signature.signer``.

The format is chain-agnostic. The signature suite is selected by
``signature.algorithm`` so the same receipt body works across chains:

===================  ==========  =====================================
algorithm            chain       signer identity
===================  ==========  =====================================
``secp256k1-eip191`` Base / EVM  0x Ethereum address
``ed25519``          Solana      base58-encoded public key
===================  ==========  =====================================

Signing covers the canonical JSON of the *entire* receipt (minus the
signature value), not a delimiter-joined string, so it is safe against
field-injection and forward-compatible as new fields are added.

The canonical serialization rules are distilled from the AIP-1 canonical
serialization spec: recursive key sorting, no insignificant whitespace,
UTF-8 output, and integer-valued floats normalized to integers, so that
independent implementations produce byte-identical signable payloads.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

RECEIPT_VERSION = "AIR/1"

ALG_EVM = "secp256k1-eip191"
ALG_SOLANA = "ed25519"


# --------------------------------------------------------------------------
# Canonical serialization (distilled from the AIP-1 canonical spec)
# --------------------------------------------------------------------------
def _normalize(obj: Any) -> Any:
    """Recursively normalize a value for canonical serialization.

    Integer-valued floats collapse to ints (``500.0`` -> ``500``) so that
    JSON produced by different languages hashes identically.
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return int(obj) if obj.is_integer() else obj
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    return obj


def canonicalize(obj: Any) -> bytes:
    """Serialize ``obj`` to canonical, byte-identical JSON.

    Keys are sorted recursively, whitespace is stripped, output is UTF-8,
    and integer-valued floats are normalized to integers.
    """
    return json.dumps(
        _normalize(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def hash_object(obj: Any) -> str:
    """Return the SHA-256 hex digest of an object's canonical bytes."""
    return hashlib.sha256(canonicalize(obj)).hexdigest()


# --------------------------------------------------------------------------
# base58 (inline, so the Solana suite needs only PyNaCl)
# --------------------------------------------------------------------------
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out = ""
    while n > 0:
        n, rem = divmod(n, 58)
        out = _B58_ALPHABET[rem] + out
    pad = len(data) - len(data.lstrip(b"\x00"))
    return "1" * pad + out


def _b58decode(text: str) -> bytes:
    n = 0
    for char in text:
        n = n * 58 + _B58_ALPHABET.index(char)
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(text) - len(text.lstrip("1"))
    return b"\x00" * pad + body


# --------------------------------------------------------------------------
# Signature suites — one signer + one verifier per algorithm
# --------------------------------------------------------------------------
class EvmSigner:
    """secp256k1 + EIP-191 signer. Signer identity is an Ethereum address.

    This is the suite used on Base and any EVM chain, and it reuses the same
    key type that signs x402 EIP-3009 payment authorizations.
    """

    algorithm = ALG_EVM

    def __init__(self, private_key: str) -> None:
        from eth_account import Account

        self._account = Account.from_key(private_key)
        self.signer = self._account.address

    @classmethod
    def generate(cls) -> "EvmSigner":
        from eth_account import Account

        return cls(Account.create().key.hex())

    def sign(self, message: bytes) -> str:
        from eth_account import Account
        from eth_account.messages import encode_defunct

        signed = Account.sign_message(
            encode_defunct(primitive=message), self._account.key
        )
        return base64.b64encode(signed.signature).decode("ascii")


class SolanaSigner:
    """Ed25519 signer. Signer identity is a base58-encoded public key."""

    algorithm = ALG_SOLANA

    def __init__(self, signing_key: "Any") -> None:
        from nacl.signing import SigningKey

        if not isinstance(signing_key, SigningKey):
            signing_key = SigningKey(bytes(signing_key))
        self._signing_key = signing_key
        self.signer = _b58encode(bytes(signing_key.verify_key))

    @classmethod
    def generate(cls) -> "SolanaSigner":
        from nacl.signing import SigningKey

        return cls(SigningKey.generate())

    def sign(self, message: bytes) -> str:
        signed = self._signing_key.sign(message)
        return base64.b64encode(signed.signature).decode("ascii")


def _verify_evm(message: bytes, signature_b64: str, signer: str) -> bool:
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct

        signature = base64.b64decode(signature_b64)
        recovered = Account.recover_message(
            encode_defunct(primitive=message), signature=signature
        )
        return recovered.lower() == signer.lower()
    except Exception:
        return False


def _verify_solana(message: bytes, signature_b64: str, signer: str) -> bool:
    try:
        from nacl.signing import VerifyKey

        verify_key = VerifyKey(_b58decode(signer))
        verify_key.verify(message, base64.b64decode(signature_b64))
        return True
    except Exception:
        return False


# algorithm -> verifier. Verifying needs no private-key libraries beyond
# the public-key math, so anyone can verify offline.
_VERIFIERS = {
    ALG_EVM: _verify_evm,
    ALG_SOLANA: _verify_solana,
}


def supported_algorithms() -> list[str]:
    """Return the signature algorithms this implementation can verify."""
    return sorted(_VERIFIERS)


# --------------------------------------------------------------------------
# Receipt build / sign / verify
# --------------------------------------------------------------------------
def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_receipt(
    *,
    intent: dict[str, Any],
    result: Any,
    provider_used: str,
    settlement: dict[str, Any],
    issuer: Optional[str] = None,
    issued_at: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build an unsigned AIR/1 receipt.

    Args:
        intent: The original intent object that was resolved.
        result: The result returned to the caller.
        provider_used: Identifier of the provider that fulfilled the intent.
        settlement: On-chain settlement facts (``tx_hash``, ``amount``,
            ``currency``, ``chain``, ``facilitator``, ``timestamp``).
        issuer: Optional human-readable identifier of the issuing service.
            The cryptographic identity is ``signature.signer`` after signing.
        issued_at: ISO-8601 UTC timestamp; defaults to now.
        extra: Optional extra fields to include verbatim in the receipt.

    Returns:
        A receipt dict without a ``signature`` block. Pass it to
        :func:`sign_receipt` to produce a verifiable receipt.
    """
    receipt: dict[str, Any] = {
        "version": RECEIPT_VERSION,
        "issued_at": issued_at or _utcnow_iso(),
        "provider_used": provider_used,
        "intent_hash": hash_object(intent),
        "result_hash": hash_object(result),
        "settlement": settlement,
    }
    if issuer is not None:
        receipt["issuer"] = issuer
    if extra:
        receipt.update(extra)
    return receipt


def _signable(receipt: dict[str, Any]) -> bytes:
    """Canonical bytes signed by the issuer: the receipt with the signature
    block present but its ``value`` omitted, so algorithm/signer/key_id are
    all covered by the signature.
    """
    to_sign = dict(receipt)
    sig = dict(to_sign.get("signature") or {})
    sig.pop("value", None)
    to_sign["signature"] = sig
    return canonicalize(to_sign)


def sign_receipt(
    receipt: dict[str, Any],
    signer: Any,
    *,
    key_id: Optional[str] = None,
) -> dict[str, Any]:
    """Sign a receipt with an issuer signer, returning a signed copy.

    Args:
        receipt: An unsigned receipt from :func:`build_receipt`.
        signer: An :class:`EvmSigner`, :class:`SolanaSigner`, or any object
            exposing ``algorithm``, ``signer``, and ``sign(bytes) -> str``.
        key_id: Optional key identifier (e.g. a DID or key fragment) that is
            included in and covered by the signature.
    """
    signed = dict(receipt)
    signature: dict[str, Any] = {
        "algorithm": signer.algorithm,
        "signer": signer.signer,
    }
    if key_id is not None:
        signature["key_id"] = key_id
    signed["signature"] = signature
    signature["value"] = signer.sign(_signable(signed))
    return signed


@dataclass
class VerificationResult:
    """Outcome of verifying a receipt.

    ``valid`` is the overall verdict. It requires a good signature, a
    supported version, no signer mismatch, and — when the caller supplies the
    original intent/result — matching hashes. On-chain ``tx_hash`` checking is
    the caller's responsibility and is deliberately out of scope here.
    """

    valid: bool
    signature_valid: bool
    algorithm: Optional[str] = None
    intent_hash_valid: Optional[bool] = None
    result_hash_valid: Optional[bool] = None
    signer: Optional[str] = None
    key_id: Optional[str] = None
    errors: list[str] = field(default_factory=list)


def verify_receipt(
    receipt: dict[str, Any],
    *,
    intent: Optional[dict[str, Any]] = None,
    result: Any = None,
    expected_signer: Optional[str] = None,
) -> VerificationResult:
    """Verify a signed AIR/1 receipt offline.

    Args:
        receipt: A signed receipt.
        intent: If given, ``intent_hash`` is recomputed and compared.
        result: If given, ``result_hash`` is recomputed and compared.
        expected_signer: If given, the signature's ``signer`` must match
            (case-insensitively), pinning the receipt to a known issuer.

    Returns:
        A :class:`VerificationResult`. The caller should additionally verify
        ``settlement.tx_hash`` on-chain to confirm the payment itself.
    """
    errors: list[str] = []
    signature = receipt.get("signature") or {}
    algorithm = signature.get("algorithm")
    signer = signature.get("signer")
    value = signature.get("value")
    key_id = signature.get("key_id")

    version = receipt.get("version")
    if version != RECEIPT_VERSION:
        errors.append(f"unsupported version: {version!r}")

    verifier = _VERIFIERS.get(algorithm)
    if verifier is None:
        errors.append(f"unsupported algorithm: {algorithm!r}")
        signature_valid = False
    elif not value or not signer:
        errors.append("missing signature value or signer")
        signature_valid = False
    else:
        signature_valid = verifier(_signable(receipt), value, signer)
        if not signature_valid:
            errors.append("signature verification failed")

    intent_hash_valid: Optional[bool] = None
    if intent is not None:
        intent_hash_valid = receipt.get("intent_hash") == hash_object(intent)
        if not intent_hash_valid:
            errors.append("intent_hash mismatch")

    result_hash_valid: Optional[bool] = None
    if result is not None:
        result_hash_valid = receipt.get("result_hash") == hash_object(result)
        if not result_hash_valid:
            errors.append("result_hash mismatch")

    signer_ok = True
    if expected_signer is not None:
        signer_ok = signer is not None and signer.lower() == expected_signer.lower()
        if not signer_ok:
            errors.append("signer does not match expected_signer")

    valid = (
        signature_valid
        and signer_ok
        and version == RECEIPT_VERSION
        and intent_hash_valid is not False
        and result_hash_valid is not False
    )

    return VerificationResult(
        valid=valid,
        signature_valid=signature_valid,
        algorithm=algorithm,
        intent_hash_valid=intent_hash_valid,
        result_hash_valid=result_hash_valid,
        signer=signer,
        key_id=key_id,
        errors=errors,
    )
