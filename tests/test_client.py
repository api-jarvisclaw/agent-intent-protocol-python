"""Tests for the AIP client, using httpx's built-in MockTransport.

Mocked responses mirror the wire contract served by the gateway
(new-api controller/aip/intent.go), so these tests double as a
contract check between the SDK and the backend.
"""

from __future__ import annotations

import json

import httpx
import pytest

from agent_intent_x402 import (
    AIPAPIError,
    AIPAuthError,
    AIPClient,
    AIPPaymentRequiredError,
    IntentType,
    OptimizeFor,
    ResolveResult,
)


def make_client(handler) -> AIPClient:
    """Build an AIPClient wired to a MockTransport handler."""
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport)
    return AIPClient(api_key="sk-test", http_client=http, endpoint="https://api.test")


# ── resolve ────────────────────────────────────────────────────────────
def test_resolve_returns_ranked_matches():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "matches": [
                    {
                        "provider_id": "openai",
                        "score": 0.95,
                        "estimated_price_usd": 0.002,
                        "pricing": {
                            "input_per_million": 2.5,
                            "output_per_million": 10.0,
                        },
                        "endpoint": "/v1/chat/completions",
                        "model": "gpt-4o",
                        "reason": "best score for cost",
                    },
                    {
                        "provider_id": "anthropic",
                        "score": 0.90,
                        "model": "claude-3-5-sonnet",
                    },
                ],
                "intent_type": "chat_completion",
                "total_available": 2,
            },
        )

    client = make_client(handler)
    result = client.resolve(
        IntentType.CHAT_COMPLETION,
        constraints={"max_price_usd": 0.01},
        preferences={"optimize_for": OptimizeFor.COST, "limit": 5},
    )

    assert isinstance(result, ResolveResult)
    assert result.intent_type == "chat_completion"
    assert result.total_available == 2
    assert len(result.matches) == 2
    assert result.best_match.provider_id == "openai"
    assert result.best_match.model == "gpt-4o"
    assert result.best_match.pricing.input_per_million == 2.5

    # request contract
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.test/v1/intent/resolve"
    assert captured["auth"] == "Bearer sk-test"
    assert captured["body"]["intent"] == "chat_completion"
    assert captured["body"]["constraints"] == {"max_price_usd": 0.01}
    assert captured["body"]["preferences"] == {"optimize_for": "cost", "limit": 5}


def test_resolve_best_match_none_when_empty():
    def handler(request):
        return httpx.Response(
            200, json={"matches": [], "intent_type": "utility", "total_available": 0}
        )

    result = make_client(handler).resolve("utility")
    assert result.matches == []
    assert result.best_match is None


# ── resolve_natural ──────────────────────────────────────────────────────
def test_resolve_natural_passes_query_and_session():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "clarify", "message": "which model?"})

    result = make_client(handler).resolve_natural(
        "I want to chat cheaply", session_id="s-1"
    )
    assert result["status"] == "clarify"
    assert captured["url"] == "https://api.test/v1/intent/resolve/natural"
    assert captured["body"] == {"query": "I want to chat cheaply", "session_id": "s-1"}


# ── discover ───────────────────────────────────────────────────────────
def test_discover_filters_by_intent_type():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["method"] = request.method
        return httpx.Response(
            200,
            json={
                "providers": [
                    {
                        "id": "openai",
                        "name": "OpenAI",
                        "intent_types": ["chat_completion"],
                        "features": ["function_calling"],
                    }
                ],
                "total": 1,
            },
        )

    providers = make_client(handler).discover(intent_type=IntentType.CHAT_COMPLETION)
    assert captured["method"] == "GET"
    assert "intent_type=chat_completion" in captured["url"]
    assert len(providers) == 1
    assert providers[0].id == "openai"
    assert providers[0].intent_types == ["chat_completion"]


# ── execute ────────────────────────────────────────────────────────────
def test_execute_sends_intent_and_payload():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "chatcmpl-1", "choices": []})

    payload = {"messages": [{"role": "user", "content": "hi"}]}
    result = make_client(handler).execute(IntentType.CHAT_COMPLETION, payload)
    assert result["id"] == "chatcmpl-1"
    assert captured["url"] == "https://api.test/v1/intent/execute"
    assert captured["body"]["intent"] == "chat_completion"
    assert captured["body"]["payload"] == payload


# ── list helpers ───────────────────────────────────────────────────────
def test_list_intent_types_unwraps_dict():
    def handler(request):
        return httpx.Response(
            200, json={"intent_types": ["chat_completion", "image_generation"]}
        )

    types = make_client(handler).list_intent_types()
    assert types == ["chat_completion", "image_generation"]


def test_list_providers_returns_typed():
    def handler(request):
        return httpx.Response(
            200, json={"providers": [{"id": "p1", "name": "Provider One"}], "total": 1}
        )

    providers = make_client(handler).list_providers()
    assert len(providers) == 1
    assert providers[0].name == "Provider One"


# ── error mapping ──────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "status,exc",
    [
        (401, AIPAuthError),
        (403, AIPAuthError),
        (402, AIPPaymentRequiredError),
        (500, AIPAPIError),
    ],
)
def test_error_status_maps_to_exception(status, exc):
    def handler(request):
        return httpx.Response(status, json={"error": "boom"})

    with pytest.raises(exc) as ei:
        make_client(handler).resolve("chat_completion")
    assert ei.value.status_code == status
