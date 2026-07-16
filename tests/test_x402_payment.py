"""End-to-end x402 payment flow tests.

These exercise the full pay-per-request loop against a mocked gateway:

    1. The client sends a request.
    2. The gateway answers ``402 Payment Required`` with an ``accepts`` list.
    3. The wallet signs the challenge into a ``PAYMENT-SIGNATURE`` header.
    4. The client retries once and the gateway answers ``200``.

Both the synchronous :class:`AIPClient` and the asynchronous
:class:`AsyncAIPClient` are covered, so the two clients are held to the same
wire contract. The wallet uses a throwaway EVM key generated per test — no
funds move because the gateway is mocked.
"""

from __future__ import annotations

import json

import httpx
import pytest

from agent_intent_x402 import AIPClient, AsyncAIPClient, Wallet

# A deterministic throwaway key. Never used on any real network.
TEST_PRIVATE_KEY = "0x" + "11" * 32


def _challenge_body() -> dict:
    """A minimal, spec-shaped 402 challenge the wallet can sign."""
    return {
        "x402Version": 2,
        "error": "payment required",
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:8453",
                "amount": "2000",
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "payTo": "0x000000000000000000000000000000000000dEaD",
                "maxTimeoutSeconds": 60,
            }
        ],
    }


def _result_body() -> dict:
    """A successful execute result carrying a settlement block."""
    return {
        "id": "chatcmpl-xyz",
        "choices": [{"message": {"role": "assistant", "content": "hi"}}],
        "settlement": {
            "tx_hash": "0xabc123",
            "network": "eip155:8453",
            "amount": "2000",
            "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "facilitator": "https://x402.org/facilitator",
        },
    }


# ── synchronous client ──────────────────────────────────────────────────
def test_sync_402_challenge_is_signed_and_retried():
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(
            {
                "url": str(request.url),
                "payment": request.headers.get("PAYMENT-SIGNATURE"),
            }
        )
        # First hit: demand payment. Retry: succeed.
        if len(calls) == 1:
            return httpx.Response(402, json=_challenge_body())
        return httpx.Response(200, json=_result_body())

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport)
    client = AIPClient(
        api_key="sk-test",
        http_client=http,
        endpoint="https://api.test",
        wallet=Wallet(private_key=TEST_PRIVATE_KEY),
    )

    result = client.execute("chat_completion", {"messages": []})

    # The gateway was hit exactly twice: challenge, then paid retry.
    assert len(calls) == 2
    # First request carried no payment header.
    assert calls[0]["payment"] is None
    # Retry carried a non-empty PAYMENT-SIGNATURE.
    assert calls[1]["payment"]
    # The paid response body came back intact, settlement included.
    assert result["id"] == "chatcmpl-xyz"
    assert result["settlement"]["tx_hash"] == "0xabc123"


def test_sync_402_without_wallet_raises():
    """No wallet means no auto-payment — the 402 surfaces as an error."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json=_challenge_body())

    from agent_intent_x402 import AIPPaymentRequiredError

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport)
    client = AIPClient(api_key="sk-test", http_client=http, endpoint="https://api.test")

    with pytest.raises(AIPPaymentRequiredError):
        client.execute("chat_completion", {"messages": []})


# ── asynchronous client ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_async_402_challenge_is_signed_and_retried():
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(
            {
                "url": str(request.url),
                "payment": request.headers.get("PAYMENT-SIGNATURE"),
                "body": json.loads(request.content) if request.content else None,
            }
        )
        if len(calls) == 1:
            return httpx.Response(402, json=_challenge_body())
        return httpx.Response(200, json=_result_body())

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    client = AsyncAIPClient(
        api_key="sk-test",
        http_client=http,
        endpoint="https://api.test",
        wallet=Wallet(private_key=TEST_PRIVATE_KEY),
    )

    result = await client.execute("chat_completion", {"messages": []})

    assert len(calls) == 2
    assert calls[0]["payment"] is None
    assert calls[1]["payment"]
    # Both attempts carried the same intent payload.
    assert calls[0]["body"]["intent"] == "chat_completion"
    assert calls[1]["body"]["intent"] == "chat_completion"
    assert result["settlement"]["facilitator"] == "https://x402.org/facilitator"

    await client.aclose()


@pytest.mark.asyncio
async def test_async_402_without_wallet_raises():
    from agent_intent_x402 import AIPPaymentRequiredError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json=_challenge_body())

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    client = AsyncAIPClient(
        api_key="sk-test", http_client=http, endpoint="https://api.test"
    )

    with pytest.raises(AIPPaymentRequiredError):
        await client.execute("chat_completion", {"messages": []})

    await client.aclose()
