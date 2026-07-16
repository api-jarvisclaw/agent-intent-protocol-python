"""air_federation_verifier — an independent AIR/1 receipt verifier.

A reference "federation node": a second, independent implementation of the
AIR/1 verification procedure. It lets any third party confirm a receipt
without trusting (or even contacting) the issuer:

* :func:`verify_receipt` — recompute hashes and check the signature offline.
* :func:`verify_settlement` — confirm the payment on-chain via public RPC.
* :func:`canonicalize` / :func:`sha256_hex` — the independent canonicalizer.

It shares no code with the issuer's ``agent_intent_x402`` package.
"""

from .canonical import canonicalize, sha256_hex, signable_bytes
from .chain import SettlementReport, verify_settlement
from .verify import (
    ALG_EVM,
    ALG_SOLANA,
    VerificationReport,
    supported_algorithms,
    verify_receipt,
)

__all__ = [
    "canonicalize",
    "sha256_hex",
    "signable_bytes",
    "verify_receipt",
    "VerificationReport",
    "supported_algorithms",
    "ALG_EVM",
    "ALG_SOLANA",
    "verify_settlement",
    "SettlementReport",
]

__version__ = "0.1.0"
