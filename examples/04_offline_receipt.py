"""Offline-verifiable settlement receipts (AIR/1).

An **AIR/1 receipt** is a self-certifying record that a request was fulfilled
and paid for on-chain. The point: anyone can verify it *without trusting the
party that issued it*. No callback to the issuer, no shared secret — just the
receipt bytes and public-key math.

This example issues a receipt with a freshly generated EVM (Base) key, then
verifies it offline, and finally shows that tampering with any field is
detected. Run it with no network and no API key:

    python examples/04_offline_receipt.py

Swap ``EvmSigner`` for ``SolanaSigner`` to issue the ed25519 (Solana) suite —
the receipt body is identical, only ``signature.algorithm`` changes.
"""

from agent_intent_x402 import (
    EvmSigner,
    build_receipt,
    sign_receipt,
    verify_receipt,
)


def main() -> None:
    # The original intent and the result that was returned to the caller.
    intent = {
        "type": "chat.completion",
        "input": {"messages": [{"role": "user", "content": "Hello"}]},
        "constraints": {"max_price_usd": 0.01},
    }
    result = {"output": "Hi there!", "model": "some-provider/model-x"}

    # On-chain settlement facts. In a real flow tx_hash comes from the x402
    # facilitator (e.g. Coinbase's) that settled the payment.
    settlement = {
        "tx_hash": "0xabc123...",
        "amount": "0.004",
        "currency": "USDC",
        "chain": "base",
        "facilitator": "coinbase",
    }

    # The issuer holds its own key. Here we generate one for the demo.
    issuer_signer = EvmSigner.generate()

    # 1) Build + sign the receipt.
    unsigned = build_receipt(
        intent=intent,
        result=result,
        provider_used="some-provider/model-x",
        settlement=settlement,
        issuer="demo-gateway",
    )
    receipt = sign_receipt(unsigned, issuer_signer)
    print("issued receipt signed by:", receipt["signature"]["signer"])
    print("algorithm:", receipt["signature"]["algorithm"])

    # 2) A third party verifies it offline. Passing the original intent/result
    #    also re-checks the bound hashes; expected_signer pins the issuer.
    outcome = verify_receipt(
        receipt,
        intent=intent,
        result=result,
        expected_signer=issuer_signer.signer,
    )
    print("\nverification.valid:", outcome.valid)
    assert outcome.valid, outcome.errors

    # 3) Tamper with the result — the bound result_hash no longer matches, and
    #    even if an attacker also rewrote result_hash, the signature would fail.
    tampered = dict(receipt)
    tampered_settlement = dict(settlement)
    tampered_settlement["amount"] = "0.000"  # pretend it was cheaper
    tampered["settlement"] = tampered_settlement
    bad = verify_receipt(tampered, intent=intent, result=result)
    print("tampered receipt valid:", bad.valid)
    print("errors:", bad.errors)
    assert not bad.valid

    print("\nOK — receipt verifies offline and tampering is rejected.")


if __name__ == "__main__":
    main()
