"""Resolve an intent to ranked providers.

`resolve` declares *what* you want plus your constraints and preferences, and
gets back a ranked list of providers that can serve it. This endpoint needs
authentication (an API key or, on x402 gateways, a wallet).

    AIP_API_KEY=sk-... python examples/02_resolve.py

Constraints are hard requirements; preferences are soft ranking hints. Both
accept plain dicts, so you never have to import a config class to get started.
"""

import os

from agent_intent_x402 import AIPClient


def main() -> None:
    api_key = os.getenv("AIP_API_KEY")
    endpoint = os.getenv("AIP_ENDPOINT")

    kwargs = {}
    if endpoint:
        kwargs["endpoint"] = endpoint

    with AIPClient(api_key=api_key, **kwargs) as client:
        result = client.resolve(
            "chat.completion",
            constraints={"max_price_usd": 0.01, "features": ["function_calling"]},
            preferences={"optimize_for": "cost", "limit": 5},
        )
        best = result.best_match
        print("best match:", best)
        print("\nfull ranked list:")
        for match in result.matches:
            print("  -", match)


if __name__ == "__main__":
    main()
