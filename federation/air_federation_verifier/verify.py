"""Independent AIR/1 receipt verifier — the trust-nobody path.

This verifier is a *second implementation* of the AIR/1 verification
procedure, written against the specification and deliberately sharing no code
with the issuer's ``agent_intent_x402`` package. A federation node runs this
to answer one question for itself:

    "Given only a receipt (and optionally the original intent/result), is this
    a genuine, unmodified statement signed by the party it names, covering the
    hashes it claims?"

The verifier re-derives everything from public data:

* recompute ``intent_hash`` / ``result_hash`` from the originals (if given)
  using an independent canonicalizer (:mod:`.canonical`);
* recompute the signable byte string and check the signature with the
  public-key math for the receipt's ``algorithm`` (secp256k1+EIP-191 for
  ``secp256k1-eip191``; Ed25519 for ``ed25519``);
* it never needs the issuer's private key, the facilitator, or any of our
  servers.

On-chain settlement (``tx_hash``) is checked separately by :mod:`.chain`,
because the blockchain, not the issuer, is authoritative on payment.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Optional

from .canonical import sha256_hex, signable_bytes

# Algorithm identifiers, transcribed from the IANA registry section of the
# draft. The ``algorithm`` member of the signature selects the verifier.
ALG_EVM = "secp256k1-eip191"
ALG_SOLANA = "ed25519"


@dataclass
class VerificationReport:
    """Outcome of an independent verification pass.

    ``valid`` is the AND of every check that was actually performed. A hash
    check that was skipped (because the original was not supplied) does not
    make a receipt invalid, but it is reported as ``None`` so a caller can
    tell "verified" from "not checked".
    """

    valid: bool
    algorithm: Optional[str]
    signer: Optional[str]
    key_id: Optional[str]
    signature_valid: Optional[bool]
    intent_hash_valid: Optional[bool]
    result_hash_valid: Optional[bool]
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "algorithm": self.algorithm,
            "signer": self.signer,
            "key_id": self.key_id,
            "signature_valid": self.signature_valid,
            "intent_hash_valid": self.intent_hash_valid,
            "result_hash_valid": self.result_hash_valid,
            "errors": list(self.errors),
        }


# --------------------------------------------------------------------------
# Base58 (Bitcoin alphabet) — needed to decode Solana public keys. Written
# here independently rather than imported from the issuer package.
# --------------------------------------------------------------------------
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58decode(text: str) -> bytes:
    num = 0
    for char in text:
        num = num * 58 + _B58_ALPHABET.index(char)
    body = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    pad = len(text) - len(text.lstrip("1"))
    return b"\x00" * pad + body


# --------------------------------------------------------------------------
# Per-suite signature verification. Each returns True only on a valid match.
# --------------------------------------------------------------------------
def _verify_evm(message: bytes, signature_b64: str, signer: str) -> bool:
    """secp256k1 + EIP-191: recover the address from the signature over the
    EIP-191 personal-message wrapping of ``message`` and compare to ``signer``.
    """
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct

        recovered = Account.recover_message(
            encode_defunct(primitive=message),
            signature=base64.b64decode(signature_b64),
        )
        return recovered.lower() == signer.lower()
    except Exception:
        return False


def _verify_ed25519(message: bytes, signature_b64: str, signer: str) -> bool:
    """Ed25519: verify ``message`` against the base58 public key ``signer``."""
    try:
        from nacl.signing import VerifyKey

        VerifyKey(_b58decode(signer)).verify(
            message, base64.b64decode(signature_b64)
        )
        return True
    except Exception:
        return False


_VERIFIERS = {
    ALG_EVM: _verify_evm,
    ALG_SOLANA: _verify_ed25519,
}


def supported_algorithms() -> list[str]:
    return sorted(_VERIFIERS)


# --------------------------------------------------------------------------
# The verification procedure itself.
# --------------------------------------------------------------------------
def verify_receipt(
    receipt: dict[str, Any],
    *,
    original_intent: Optional[dict[str, Any]] = None,
    original_result: Any = None,
) -> VerificationReport:
    """Independently verify an AIR/1 receipt.

    Args:
        receipt: The signed receipt object as received (parsed JSON).
        original_intent: If supplied, ``intent_hash`` is recomputed from it
            and compared. Omit to skip that check.
        original_result: If supplied (and not ``None``), ``result_hash`` is
            recomputed from it and compared. Omit to skip that check.

    Returns:
        A :class:`VerificationReport`. ``valid`` is True only if the signature
        verified and no performed hash check failed.
    """
    errors: list[str] = []

    signature = receipt.get("signature")
    if not isinstance(signature, dict):
        return VerificationReport(
            valid=False,
            algorithm=None,
            signer=None,
            key_id=None,
            signature_valid=False,
            intent_hash_valid=None,
            result_hash_valid=None,
            errors=["receipt has no signature block"],
        )

    algorithm = signature.get("algorithm")
    signer = signature.get("signer")
    key_id = signature.get("key_id")
    value = signature.get("value")

    signature_valid: Optional[bool] = None
    verifier = _VERIFIERS.get(algorithm)
    if verifier is None:
        signature_valid = False
        errors.append(f"unsupported algorithm: {algorithm!r}")
    elif not isinstance(value, str) or not isinstance(signer, str):
        signature_valid = False
        errors.append("signature is missing a value or signer")
    else:
        message = signable_bytes(receipt)
        signature_valid = verifier(message, value, signer)
        if not signature_valid:
            errors.append("signature did not verify against signer")

    intent_hash_valid: Optional[bool] = None
    if original_intent is not None:
        recomputed = sha256_hex(original_intent)
        intent_hash_valid = recomputed == receipt.get("intent_hash")
        if not intent_hash_valid:
            errors.append(
                "intent_hash mismatch: receipt="
                f"{receipt.get('intent_hash')!r} recomputed={recomputed!r}"
            )

    result_hash_valid: Optional[bool] = None
    if original_result is not None:
        recomputed = sha256_hex(original_result)
        result_hash_valid = recomputed == receipt.get("result_hash")
        if not result_hash_valid:
            errors.append(
                "result_hash mismatch: receipt="
                f"{receipt.get('result_hash')!r} recomputed={recomputed!r}"
            )

    valid = (
        signature_valid is True
        and intent_hash_valid is not False
        and result_hash_valid is not False
    )

    return VerificationReport(
        valid=valid,
        algorithm=algorithm,
        signer=signer,
        key_id=key_id,
        signature_valid=signature_valid,
        intent_hash_valid=intent_hash_valid,
        result_hash_valid=result_hash_valid,
        errors=errors,
    )
