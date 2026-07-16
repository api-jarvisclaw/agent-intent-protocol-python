"""Execute an intent and pay for it with a wallet — the full x402 loop.

Give the client a `Wallet` and it answers HTTP 402 payment challenges
automatically: when the gateway replies "402 Payment Required", the wallet
signs the x402 terms and the request is retried once. A single signature
authorizes exactly the amount named in the challenge and nothing more — the
wallet never sends funds itself, the gateway settles on-chain.

    AIP_WALLET_KEY=0x<private-key> python examples/03_execute_with_wallet.py

SAFETY: this spends real USDC on a live gateway. Use a funded test wallet with
a small balance, never your main key. The private key is read from the
environment and never hard-coded.
"""

import os
import sys

from agent_intent_x402 import AIPClient, Wallet


def main() -> None:
    key = os.getenv("AIP_WALLET_KEY")
    if not key:
        sys.exit(
            "Set AIP_WALLET_KEY to a funded test wallet's private key first.\n"
            "This example spends real USDC, so use a throwaway key."
        )

    endpoint = os.getenv("AIP_ENDPOINT")
    wallet = Wallet(key)
    print("paying from wallet:", wallet.address)

    kwargs = {"wallet": wallet}
    if endpoint:
        kwargs["endpoint"] = endpoint

    with AIPClient(**kwargs) as client:
        # The 402 challenge (if any) is signed and retried transparently.
        response = client.execute(
            "chat.completion",
            payload={"messages": [{"role": "user", "content": "Say hi in one word."}]},
        )
        print("\nprovider response:")
        print(response)


if __name__ == "__main__":
    main()
