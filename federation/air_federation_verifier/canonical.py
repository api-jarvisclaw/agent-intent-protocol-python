"""Independent re-implementation of AIR/1 canonical JSON serialization.

This module is written *from the specification*
(draft-air-agent-intent-receipt-00, "Canonical Serialization") and shares no
code with the issuer's ``agent_intent_x402.receipt`` module. If a receipt
signed by the issuer verifies against bytes produced here, then two
independent implementations agree on the signable payload byte-for-byte,
which is the whole point of an offline-verifiable, federated receipt.

Canonicalization rules (from the draft):

1. Object member names are sorted lexicographically by Unicode code point,
   recursively, at every level.
2. No insignificant whitespace: members and elements are separated by a
   single ``,`` and object names from values by a single ``:``.
3. Output is UTF-8; non-ASCII characters are emitted literally, not escaped.
4. A number whose value is integral is emitted without a fractional part so
   that receipts remain stable across languages lacking a distinct integer
   type.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _normalize(value: Any) -> Any:
    """Apply rule 4 (integral floats collapse to ints), recursively.

    ``bool`` is checked before ``int``/``float`` because ``bool`` is a
    subclass of ``int`` in Python and must stay ``true``/``false``.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {key: _normalize(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def canonicalize(obj: Any) -> bytes:
    """Return the canonical UTF-8 byte string for ``obj``.

    ``json.dumps`` with ``sort_keys=True`` gives recursive lexicographic
    ordering (rule 1), compact ``separators`` give no insignificant
    whitespace (rule 2), ``ensure_ascii=False`` gives literal UTF-8
    (rule 3), and ``_normalize`` gives integral-float collapsing (rule 4).
    """
    return json.dumps(
        _normalize(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_hex(obj: Any) -> str:
    """Lowercase SHA-256 hex digest of an object's canonical bytes."""
    return hashlib.sha256(canonicalize(obj)).hexdigest()


def signable_bytes(receipt: dict[str, Any]) -> bytes:
    """Canonical bytes the issuer signs: the full receipt with the signature
    block present but ``signature.value`` removed.

    Reconstructed independently from the draft ("Signing Procedure"): the
    signature covers ``algorithm``, ``signer`` and any ``key_id`` but not the
    signature ``value`` itself.
    """
    to_sign = dict(receipt)
    sig = dict(to_sign.get("signature") or {})
    sig.pop("value", None)
    to_sign["signature"] = sig
    return canonicalize(to_sign)
