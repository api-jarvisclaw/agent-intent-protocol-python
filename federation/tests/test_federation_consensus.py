"""Multi-node federation consensus: independent nodes, independent data sources.

Legs 1 and 2 (recompute hashes, verify signature) are pure functions of the
receipt bytes, so any honest node reaches the same answer. Leg 3 is different:
it asks *the chain* whether the payment happened, and a skeptic can rightly
ask "what if the one RPC provider you queried lied to you?"

The federation answer is: don't query one. Run several independent nodes, each
pinned to a *different* RPC operator with no shared infrastructure, and require
them to agree. This module actually does that. It spins up N in-process nodes,
each hard-pinned to a distinct public Base RPC (dRPC, 1RPC, MeowRPC -- three
unaffiliated operators), and asserts:

  * every reachable node reaches the SAME verdict on a genuine receipt, and
  * every reachable node reaches the SAME verdict rejecting a forged one.

If two operators who share no code and no infrastructure independently confirm
the same on-chain fact, trusting the receipt issuer is no longer required.

The tests skip (rather than fail) when fewer than two providers are reachable,
because network reachability is an environment property, not a code defect.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "agent_intent_x402" / "..")
)

from agent_intent_x402.receipt import (  # noqa: E402
    EvmSigner,
    build_receipt,
    sign_receipt,
)
from air_federation_verifier import (  # noqa: E402
    sha256_hex,
    verify_receipt,
    verify_settlement,
)

# --- Ground truth: a real, immutable USDC Transfer on Base mainnet ----------
REAL_TX = "0x58f15a29c7b9002c4b6335796ce3d520e066a0804d85bbae87a23306d24aaf90"
REAL_PAY_TO = "0x09ad820aac5779683b481c4674208a4e1b024afa"
REAL_AMOUNT = "114586"  # smallest unit (0.114586 USDC)
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
BASE_NETWORK = "eip155:8453"

INTENT = {
    "action": "search",
    "query": "cheapest flight SFO->NRT",
    "constraints": {"max_price_usd": 900, "nonstop": True},
}
RESULT = {"provider": "acme-search", "answers": [{"price_usd": 812}]}

# Three UNAFFILIATED public Base RPC operators. A node is pinned to exactly one
# of these; consensus across them means no single operator can forge a verdict.
FEDERATION_RPCS = {
    "drpc": "https://base.drpc.org",
    "1rpc": "https://1rpc.io/base",
    "meowrpc": "https://base.meowrpc.com",
}

_UA = "Mozilla/5.0 (compatible; air-federation-verifier/0.1)"


def _settlement() -> dict:
    return {
        "tx_hash": REAL_TX,
        "network": BASE_NETWORK,
        "amount": REAL_AMOUNT,
        "asset": USDC_BASE,
        "pay_to": REAL_PAY_TO,
    }


def _is_reachable(url: str) -> bool:
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}
    ).encode()
    try:
        req = urllib.request.Request(
            url, data=payload,
            headers={"content-type": "application/json", "user-agent": _UA},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = json.loads(resp.read().decode())
        return isinstance(body.get("result"), str)
    except Exception:
        return False


@dataclass
class NodeVerdict:
    """One federation node's full, independent verdict on a receipt."""

    node: str
    endpoint: str
    hashes_ok: bool
    signature_ok: bool
    settlement_confirmed: Optional[bool]
    settlement_matched: Optional[bool]

    @property
    def verdict(self) -> bool:
        """A node accepts a receipt only if every leg it checked passed."""
        return (
            self.hashes_ok
            and self.signature_ok
            and self.settlement_confirmed is True
            and self.settlement_matched is True
        )


def _run_node(name: str, endpoint: str, receipt: dict) -> NodeVerdict:
    """A single federation node: runs all three legs against ONE pinned RPC."""
    hashes_ok = (
        sha256_hex(INTENT) == receipt.get("intent_hash")
        and sha256_hex(RESULT) == receipt.get("result_hash")
    )
    signature_ok = verify_receipt(receipt).valid
    settle = verify_settlement(receipt["settlement"], endpoint=endpoint)
    return NodeVerdict(
        node=name,
        endpoint=endpoint,
        hashes_ok=hashes_ok,
        signature_ok=signature_ok,
        settlement_confirmed=settle.confirmed,
        settlement_matched=settle.matched,
    )


@pytest.fixture(scope="module")
def reachable_nodes() -> dict:
    """The subset of federation RPCs actually reachable right now."""
    live = {n: url for n, url in FEDERATION_RPCS.items() if _is_reachable(url)}
    if len(live) < 2:
        pytest.skip(
            "federation consensus needs >=2 independent RPCs reachable; "
            f"only {sorted(live)} responded"
        )
    return live


@pytest.fixture(scope="module")
def signed_receipt() -> dict:
    signer = EvmSigner.generate()
    unsigned = build_receipt(
        intent=INTENT,
        result=RESULT,
        provider_used="acme-search",
        settlement=_settlement(),
        issuer="issuer.example",
    )
    return sign_receipt(unsigned, signer)


def test_independent_nodes_agree_receipt_is_valid(reachable_nodes, signed_receipt):
    """Every independent node, on its own RPC operator, accepts the receipt."""
    verdicts = [
        _run_node(name, url, signed_receipt)
        for name, url in reachable_nodes.items()
    ]
    # All nodes must reach the same boolean verdict...
    assert len({v.verdict for v in verdicts}) == 1, [
        (v.node, v.verdict) for v in verdicts
    ]
    # ...and that shared verdict must be ACCEPT.
    assert all(v.verdict for v in verdicts), [
        (v.node, v.settlement_confirmed, v.settlement_matched) for v in verdicts
    ]
    # Sanity: the consensus really did span >=2 distinct operators.
    assert len({v.endpoint for v in verdicts}) >= 2


def test_independent_nodes_agree_forged_receipt_is_invalid(
    reachable_nodes, signed_receipt
):
    """A tampered receipt is rejected by every node, unanimously.

    The signature no longer covers the mutated field, so leg 2 fails on every
    node regardless of which RPC operator it trusts for leg 3.
    """
    forged = dict(signed_receipt)
    forged["result_hash"] = "0" * 64
    verdicts = [
        _run_node(name, url, forged)
        for name, url in reachable_nodes.items()
    ]
    assert len({v.verdict for v in verdicts}) == 1, [
        (v.node, v.verdict) for v in verdicts
    ]
    assert not any(v.verdict for v in verdicts)


def test_independent_nodes_agree_wrong_amount_is_invalid(reachable_nodes):
    """A receipt claiming a payment amount that never happened on-chain is
    rejected by every node: the tx is real, but no transfer of that amount
    exists, so settlement_matched is False everywhere."""
    signer = EvmSigner.generate()
    bad_settlement = _settlement()
    bad_settlement["amount"] = "999999999"
    unsigned = build_receipt(
        intent=INTENT,
        result=RESULT,
        provider_used="acme-search",
        settlement=bad_settlement,
        issuer="issuer.example",
    )
    receipt = sign_receipt(unsigned, signer)

    verdicts = [
        _run_node(name, url, receipt)
        for name, url in reachable_nodes.items()
    ]
    # Signature and hashes are fine (the issuer really signed this lie), but
    # every node's on-chain check independently refuses to match the amount.
    assert all(v.signature_ok for v in verdicts)
    assert all(v.settlement_matched is False for v in verdicts), [
        (v.node, v.settlement_matched) for v in verdicts
    ]
    assert len({v.verdict for v in verdicts}) == 1
    assert not any(v.verdict for v in verdicts)
