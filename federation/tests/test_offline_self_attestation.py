"""End-to-end offline self-attestation test: all three legs, on real chain data.

AIR/1's promise is "you don't have to trust the issuer, verify it yourself".
That claim has three legs, and this test walks all three against a *real*
transaction on Base mainnet, using an independent verifier that shares no code
with the issuer:

    leg 1  recompute  -- independently recompute intent_hash / result_hash
                         from the intent and result, byte-for-byte.
    leg 2  verify     -- verify the issuer's signature over the canonical
                         receipt with a separate signature implementation.
    leg 3  settle     -- ask the blockchain directly whether the settlement
                         tx_hash exists, succeeded, and actually moved the
                         claimed amount of the claimed asset to pay_to.

If any leg fails, or if an attacker tampers with any field, verification must
fail. The test also runs the negative cases to prove the checks have teeth.

The on-chain leg needs public JSON-RPC access to Base. If the network is
unavailable the settlement leg is skipped (with a clear reason) but the
signature/hash legs still run, so the test never silently passes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make both packages importable: issuer (repo root) and the independent
# federation verifier (federation/). They deliberately share no code.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FEDERATION = Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT), str(_FEDERATION)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Issuer side (the code under audit).
from agent_intent_x402.receipt import (  # noqa: E402
    EvmSigner,
    build_receipt,
    sign_receipt,
)

# Independent side (a second implementation).
from air_federation_verifier import (  # noqa: E402
    sha256_hex,
    verify_receipt,
    verify_settlement,
)

# --- Real, immutable Base mainnet transaction used as ground truth ----------
# A USDC (6 decimals) ERC-20 Transfer confirmed on Base mainnet. These values
# are fixed on-chain history and cannot change.
REAL_TX = "0x58f15a29c7b9002c4b6335796ce3d520e066a0804d85bbae87a23306d24aaf90"
REAL_PAY_TO = "0x09ad820aac5779683b481c4674208a4e1b024afa"
REAL_AMOUNT = "114586"  # smallest unit (0.114586 USDC)
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
BASE_NETWORK = "eip155:8453"

# Public Base RPC endpoints (no account, no vendor lock-in). The verifier
# tries them in order; any one that answers is enough.
BASE_RPC_CANDIDATES = (
    "https://base.drpc.org",
    "https://1rpc.io/base",
    "https://gateway.tenderly.co/public/base",
)

INTENT = {
    "action": "search",
    "query": "cheapest flight SFO->NRT",
    "constraints": {"max_price_usd": 900, "nonstop": True},
}
RESULT = {"provider": "acme-search", "answers": [{"price_usd": 812}]}


def _settlement():
    return {
        "tx_hash": REAL_TX,
        "network": BASE_NETWORK,
        "amount": REAL_AMOUNT,
        "asset": USDC_BASE,
        "pay_to": REAL_PAY_TO,
    }


def _reachable_endpoint():
    """Return the first Base RPC that answers eth_blockNumber, else None."""
    import json
    import urllib.request

    ua = "Mozilla/5.0 (compatible; air-federation-verifier/0.1)"
    for url in BASE_RPC_CANDIDATES:
        try:
            payload = json.dumps(
                {"jsonrpc": "2.0", "id": 1,
                 "method": "eth_blockNumber", "params": []}
            ).encode()
            req = urllib.request.Request(
                url, data=payload,
                headers={"content-type": "application/json", "user-agent": ua},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                body = json.loads(resp.read().decode())
            if isinstance(body.get("result"), str):
                return url
        except Exception:
            continue
    return None


@pytest.fixture(scope="module")
def signed_receipt():
    """A receipt built and signed by the issuer implementation."""
    signer = EvmSigner.generate()
    unsigned = build_receipt(
        intent=INTENT,
        result=RESULT,
        provider_used="acme-search",
        settlement=_settlement(),
        issuer="issuer.example",
    )
    return sign_receipt(unsigned, signer)


# --- Leg 1: independent hash recomputation ---------------------------------

def test_leg1_independent_hash_recompute(signed_receipt):
    """The verifier recomputes intent/result hashes from scratch and they
    match what the issuer put in the receipt."""
    assert sha256_hex(INTENT) == signed_receipt["intent_hash"]
    assert sha256_hex(RESULT) == signed_receipt["result_hash"]


def test_leg1_tampered_result_detected(signed_receipt):
    """If the result is altered, the recomputed hash no longer matches."""
    tampered = {"provider": "acme-search", "answers": [{"price_usd": 1}]}
    assert sha256_hex(tampered) != signed_receipt["result_hash"]


# --- Leg 2: independent signature verification -----------------------------

def test_leg2_signature_verifies(signed_receipt):
    report = verify_receipt(signed_receipt)
    assert report.valid, report.errors


def test_leg2_tampered_field_breaks_signature(signed_receipt):
    forged = dict(signed_receipt)
    forged["intent_hash"] = "0" * 64
    report = verify_receipt(forged)
    assert not report.valid


# --- Leg 3: on-chain settlement confirmation (real Base tx) -----------------

def test_leg3_settlement_confirmed_on_chain(signed_receipt):
    endpoint = _reachable_endpoint()
    if endpoint is None:
        pytest.skip("no public Base RPC reachable from this environment")

    report = verify_settlement(signed_receipt["settlement"], endpoint=endpoint)
    assert report.checked, report.detail
    assert report.confirmed is True, report.detail
    assert report.matched is True, report.detail
    # the exact real transfer must be among the decoded transfers
    assert any(
        t["to"].lower() == REAL_PAY_TO.lower()
        and str(t["value"]) == REAL_AMOUNT
        and t["asset"].lower() == USDC_BASE.lower()
        for t in report.transfers
    ), report.transfers


def test_leg3_wrong_amount_rejected():
    endpoint = _reachable_endpoint()
    if endpoint is None:
        pytest.skip("no public Base RPC reachable from this environment")

    bad = _settlement()
    bad["amount"] = "999999999"
    report = verify_settlement(bad, endpoint=endpoint)
    assert report.confirmed is True  # tx itself is real and succeeded
    assert report.matched is False   # but no transfer of that amount exists


def test_leg3_wrong_pay_to_rejected():
    endpoint = _reachable_endpoint()
    if endpoint is None:
        pytest.skip("no public Base RPC reachable from this environment")

    bad = _settlement()
    bad["pay_to"] = "0x" + "11" * 20
    report = verify_settlement(bad, endpoint=endpoint)
    assert report.matched is False


def test_leg3_nonexistent_tx_rejected():
    endpoint = _reachable_endpoint()
    if endpoint is None:
        pytest.skip("no public Base RPC reachable from this environment")

    bad = _settlement()
    bad["tx_hash"] = "0x" + "de" * 32
    report = verify_settlement(bad, endpoint=endpoint)
    assert report.confirmed is not True


# --- All three legs in one pass (the full "trust nobody" chain) ------------

def test_all_three_legs_end_to_end(signed_receipt):
    """The complete offline self-attestation: recompute, verify, settle."""
    # leg 1
    assert sha256_hex(INTENT) == signed_receipt["intent_hash"]
    assert sha256_hex(RESULT) == signed_receipt["result_hash"]
    # leg 2
    assert verify_receipt(signed_receipt).valid
    # leg 3
    endpoint = _reachable_endpoint()
    if endpoint is None:
        pytest.skip("no public Base RPC reachable from this environment")
    settle = verify_settlement(signed_receipt["settlement"], endpoint=endpoint)
    assert settle.confirmed is True and settle.matched is True, settle.detail
