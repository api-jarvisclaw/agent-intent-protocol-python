# Agent Intent Protocol — Python SDK

Declare *what* you want. Let the protocol find *who* does it best.

The Agent Intent Protocol (AIP) decouples an agent's **intent**
(`chat_completion`, `image_generation`, `web_search`, ...) from the
provider and model that fulfil it. Instead of hard-wiring your code to a
single vendor's API, you declare an intent and the protocol routes it to
the optimal provider — ranked by cost, quality, or latency.

This package is the official Python client. It speaks the AIP wire
protocol served by any compliant gateway; by default it targets the
[JarvisClaw](https://api.jarvisclaw.ai) platform.

```bash
pip install agent-intent-protocol
```

## Quick start

```python
from agent_intent_protocol import AIPClient, IntentType, OptimizeFor

with AIPClient(api_key="sk-...") as client:
    # Resolve an intent to the best-ranked provider.
    result = client.resolve(
        IntentType.CHAT_COMPLETION,
        constraints={"max_price_usd": 0.01},
        preferences={"optimize_for": OptimizeFor.COST},
    )
    best = result.best_match
    print(f"{best.provider_id} · {best.model} · score={best.score}")
```

The API key can also be supplied via the `JARVISCLAW_API_KEY`
environment variable, in which case `AIPClient()` needs no arguments.

## Resolve, then execute

`resolve` returns ranked matches so you can inspect price and score
before committing. `execute` resolves *and* runs the intent against the
selected provider in one call, proxying the provider response back:

```python
response = client.execute(
    IntentType.CHAT_COMPLETION,
    payload={"messages": [{"role": "user", "content": "Hello"}]},
    preferences={"optimize_for": "quality"},
)
```

## Natural-language intents

Let the gateway interpret a free-form request. It may resolve directly
or reply with a clarifying question for a multi-turn exchange:

```python
reply = client.resolve_natural("I need to transcribe an audio file cheaply")
if reply.get("status") == "clarify":
    print(reply["message"])   # follow-up question
else:
    print(reply["matches"])   # resolved providers
```

## Discovery

```python
# Every intent type the gateway understands.
client.list_intent_types()

# Providers available for a given intent.
client.discover(intent_type=IntentType.IMAGE_GENERATION)

# The full provider catalogue.
client.list_providers()
```

## Intent types

`chat_completion`, `image_generation`, `video_generation`,
`text_to_speech`, `web_search`, `knowledge_search`,
`prompt_optimization`, `document_processing`, `utility`,
`code_execution`, `data_analysis`, `translation`, `code_generation`.

## Errors

All exceptions derive from `AIPError`:

- `AIPConnectionError` — the request never reached the gateway.
- `AIPAuthError` — `401`/`403`, missing or invalid API key.
- `AIPPaymentRequiredError` — `402`, x402 payment required.
- `AIPAPIError` — any other non-2xx response (`status_code`, `detail`, `body`).

## Protocol

The wire format and endpoint contract are defined in the
[Agent Intent Protocol specification](https://github.com/api-jarvisclaw/agent-intent-protocol).
A Go client is available at
[agent-intent-protocol-go](https://github.com/api-jarvisclaw/agent-intent-protocol-go).

## License

MIT
