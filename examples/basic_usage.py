"""Basic usage of the Agent Intent Protocol Python client.

Set your key first::

    export JARVISCLAW_API_KEY=sk-...

then run::

    python examples/basic_usage.py
"""

from agent_intent_protocol import AIPClient, IntentType, OptimizeFor


def main() -> None:
    # Reads JARVISCLAW_API_KEY from the environment; targets api.jarvisclaw.ai.
    with AIPClient() as client:
        # 1. Discover which intents the gateway understands (no auth needed).
        print("Intent types:", client.list_intent_types())

        # 2. Resolve an intent to the best-ranked provider.
        result = client.resolve(
            IntentType.CHAT_COMPLETION,
            constraints={"max_price_usd": 0.01},
            preferences={"optimize_for": OptimizeFor.COST},
        )
        best = result.best_match
        if best is not None:
            print(f"Best: {best.provider_id} · {best.model} · score={best.score}")
        print(f"{result.total_available} provider(s) available for {result.intent_type}")

        # 3. Browse the ranked matches yourself.
        for match in result.matches:
            print(f"  - {match.provider_id}: ${match.estimated_price_usd}")


if __name__ == "__main__":
    main()
