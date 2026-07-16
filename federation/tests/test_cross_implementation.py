"""Cross-implementation federation tests.

The whole claim of AIR/1 is "you don't have to trust the issuer — verify it
yourself with your own code". These tests prove that literally:

* a receipt is *signed* by the issuer's implementation
  (``agent_intent_x402.receipt``), and
* *verified* by the independent federation verifier
  (``air_federation_verifier``),

which shares no code with the issuer. If the two implementations agree on the
canonical bytes and the signature math, verification succeeds. If an attacker
tampers with any field, verification fails.

Both signature suites (secp256k1-eip191 for EVM/Base, ed25519 for Solana) are
exercised. On-chain settlement lookup is a separate, network-dependent check
and is tested for structure without hitting a live RPC.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make both packages importable: the issuer package (repo root) and the
# independent verifier (federation/).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FEDERATION = Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT), str(_FEDERATION)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Issuer side (the code under audit).
from agent_intent_x402.receipt import (  # noqa: E402
    build_receipt,
    sign_receipt,
)

# Independent side (a second implementation, deliberately separate).
from air_federation_verifier import (  # noqa: E402
    canonicalize,
    sha256_hex,
    verify_receipt,
    verify_settlement,
)


INTENT = {
    "action": "search",
    "query": "cheapest flight SFO->NRT",
    "constraints": {"max_price_usd": 900, "nonstop": True},
}
RESULT = {"provider": "acme-search", "answers": [{"price_usd": 812}]}
SETTLEMENT = {
    "tx_hash": "0xabc123",
    "amount": "0.05",
    "currency": "USDC",
    "chain": "base",
    "facilitator": "facilitator.example",
    "timestamp": "2026-07-16T00:00:00Z",
}


def _make_signed(signer):
    receipt = build_receipt(
        intent=INTENT,
        result=RESULT,
        provider_used="acme-search",
        settlement=SETTLEMENT,
        issuer="issuer.example",
    )
    return sign_receipt(receipt, signer)


# --------------------------------------------------------------------------
# The two canonicalizers must agree byte-for-byte, or nothing else holds.
# --------------------------------------------------------------------------
def test_canonicalization_matches_issuer():
    from agent_intent_x402.receipt import canonicalize as issuer_canon
    from agent_intent_x402.receipt import hash_object as issuer_hash

    sample = {"b": 1, "a": [3, 2, {"z": True, "y": 2.0}], "c": "münchen"}
    assert canonicalize(sample) == issuer_canon(sample)
    assert sha256_hex(sample) == issuer_hash(sample)


# --------------------------------------------------------------------------
# EVM suite: sign with issuer, verify independently.
# --------------------------------------------------------------------------
def test_evm_receipt_verifies_independently():
    pytest.importorskip("eth_account")
    from agent_intent_x402.receipt import EvmSigner

    signer = EvmSigner.generate()
    receipt = _make_signed(signer)

    report = verify_receipt(
        receipt, original_intent=INTENT, original_result=RESULT
    )
    assert report.valid is True
    assert report.signature_valid is True
    assert report.intent_hash_valid is True
    assert report.result_hash_valid is True
    assert report.algorithm == "secp256k1-eip191"
    assert report.signer == signer.signer


# --------------------------------------------------------------------------
# Solana suite: sign with issuer, verify independently.
# --------------------------------------------------------------------------
def test_solana_receipt_verifies_independently():
    pytest.importorskip("nacl")
    from agent_intent_x402.receipt import SolanaSigner

    signer = SolanaSigner.generate()
    receipt = _make_signed(signer)

    report = verify_receipt(
        receipt, original_intent=INTENT, original_result=RESULT
    )
    assert report.valid is True
    assert report.signature_valid is True
    assert report.algorithm == "ed25519"
    assert report.signer == signer.signer


# --------------------------------------------------------------------------
# Tampering must be caught by the independent verifier.
# --------------------------------------------------------------------------
def test_tampered_result_hash_fails():
    pytest.importorskip("eth_account")
    from agent_intent_x402.receipt import EvmSigner

    receipt = _make_signed(EvmSigner.generate())
    receipt["result_hash"] = "0" * 64  # attacker rewrites the result hash

    report = verify_receipt(receipt)
    assert report.valid is False
    assert report.signature_valid is False


def test_tampered_body_fails():
    pytest.importorskip("eth_account")
    from agent_intent_x402.receipt import EvmSigner

    receipt = _make_signed(EvmSigner.generate())
    receipt["settlement"]["amount"] = "999.00"  # inflate the amount

    report = verify_receipt(receipt)
    assert report.valid is False
    assert report.signature_valid is False


def test_intent_hash_mismatch_detected():
    pytest.importorskip("eth_account")
    from agent_intent_x402.receipt import EvmSigner

    receipt = _make_signed(EvmSigner.generate())
    wrong_intent = dict(INTENT, query="something else entirely")

    report = verify_receipt(receipt, original_intent=wrong_intent)
    # signature still valid (body untouched) but the recomputed hash differs
    assert report.signature_valid is True
    assert report.intent_hash_valid is False
    assert report.valid is False


def test_wrong_signer_rejected():
    pytest.importorskip("eth_account")
    from agent_intent_x402.receipt import EvmSigner

    receipt = _make_signed(EvmSigner.generate())
    receipt["signature"]["signer"] = EvmSigner.generate().signer  # swap key

    report = verify_receipt(receipt)
    assert report.valid is False
    assert report.signature_valid is False


# --------------------------------------------------------------------------
# Settlement lookup structure (no live network).
# --------------------------------------------------------------------------
def test_settlement_missing_fields_not_checked():
    report = verify_settlement({})
    assert report.checked is False
    assert report.confirmed is None


def test_settlement_unknown_chain_not_checked():
    report = verify_settlement({"chain": "dogecoin", "tx_hash": "abc"})
    assert report.checked is False
    assert report.confirmed is None
