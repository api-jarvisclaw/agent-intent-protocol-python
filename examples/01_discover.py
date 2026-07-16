"""Discover providers — no auth, no wallet, no payment.

The discovery endpoint is public: it lists which providers can serve a given
intent type. This is the cheapest way to sanity-check connectivity and see
what the gateway offers before you spend anything.

    python examples/01_discover.py

Point it at any AIP-compatible gateway with AIP_ENDPOINT:

    AIP_ENDPOINT=https://your-gateway.example python examples/01_discover.py
"""

import os

from agent_intent_x402 import AIPClient


def main() -> None:
    endpoint = os.getenv("AIP_ENDPOINT")
    client = AIPClient(endpoint=endpoint) if endpoint else AIPClient()

    with client:
        providers = client.discover(intent_type="chat.completion")
        print(f"{len(providers)} provider(s) can serve 'chat.completion':\n")
        for p in providers:
            print(f"  - {p}")


if __name__ == "__main__":
    main()
