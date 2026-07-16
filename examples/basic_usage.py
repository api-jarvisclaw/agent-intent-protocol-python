"""Pay-per-request AI access with agent-intent-x402.

Your agent carries a wallet. The gateway quotes a price via HTTP 402.
The SDK signs and settles on-chain automatically — no accounts, no
API keys, no platform lock-in.

Run::

    export WALLET_PRIVATE_KEY=0xdead...   # Base-chain funded wallet
    python examples/basic_usage.py
"""

from agent_intent_x402 import AIPClient, IntentType, OptimizeFor, Wallet


def main() -> None:
    # Create a wallet from an env-var private key (never hard-code!)
    wallet = Wallet.from_env()

    # The client auto-pays any 402 challenge using this wallet.
    with AIPClient(wallet=wallet) as client:
        # 1. Discover available intent types (free, no payment needed).
        print("Intent types:", client.list_intent_types())

        # 2. Resolve: find the best provider for a chat completion.
        result = client.resolve(
            IntentType.CHAT_COMPLETION,
            constraints={"max_price_usd": 0.01},
            preferences={"optimize_for": OptimizeFor.COST},
        )
        best = result.best_match
        if best:
            print(f"Best: {best.provider_id} · {best.model} · score={best.score}")
        print(f"{result.total_available} provider(s) for {result.intent_type}")

        # 3. Execute: resolve AND run the intent in one call.
        #    If the gateway returns 402, the wallet signs automatically.
        response = client.execute(
            IntentType.CHAT_COMPLETION,
            payload={"messages": [{"role": "user", "content": "Hello from x402!"}]},
            preferences={"optimize_for": OptimizeFor.QUALITY},
        )
        print("Response:", response)


if __name__ == "__main__":
    main()
