# agent-intent-x402

[![CI](https://github.com/api-jarvisclaw/agent-intent-x402/actions/workflows/ci.yml/badge.svg)](https://github.com/api-jarvisclaw/agent-intent-x402/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/agent-intent-x402.svg)](https://pypi.org/project/agent-intent-x402/)
[![Python](https://img.shields.io/pypi/pyversions/agent-intent-x402.svg)](https://pypi.org/project/agent-intent-x402/)
[![License: MIT](https://img.shields.io/badge/License-MIT-informational.svg)](LICENSE)
[![x402](https://img.shields.io/badge/protocol-x402-8A2BE2.svg)](https://x402.org)

Pay-per-request access to any service, for AI agents — over the open
[x402](https://x402.org) protocol.

Declare *what* you want, discover *who* provides it, and pay for the
request on-chain with a single signature. No accounts, no API keys, no
platform lock-in. Your agent carries a wallet; the service quotes a
price with HTTP `402 Payment Required`; the client signs and settles.
Because payment speaks the open x402 standard, the same client works
against any compliant gateway.

- **No accounts, no API keys** — a wallet is the only credential.
- **Single-signature payments** — sign an [EIP-3009](https://eips.ethereum.org/EIPS/eip-3009) authorization; the gateway settles on-chain, no gas from your side.
- **Vendor-neutral** — the same client works against any x402-compliant gateway; nothing here is tied to one platform.
- **Offline-verifiable receipts** — every settlement can return an [AIR/1](#offline-verifiable-receipts) receipt that anyone can verify without trusting the issuer.
- **Base and Solana** — `secp256k1`/EIP-191 for EVM chains, `ed25519` for Solana.

```bash
pip install agent-intent-x402
```

Jump straight to [runnable examples](examples/), or read on for the guided tour.

## Quick start

Give the client a wallet and it settles `402` challenges automatically —
sign the payment, retry the request, return the result.

```python
from agent_intent_x402 import AIPClient, Wallet, IntentType

wallet = Wallet(private_key="0x...")   # your agent's EVM key

with AIPClient(wallet=wallet, endpoint="https://api.example.com") as client:
    # Resolve an intent to the best-ranked provider. If the gateway
    # answers 402, the wallet pays and the call transparently retries.
    result = client.resolve(
        IntentType.CHAT_COMPLETION,
        constraints={"max_price_usd": 0.01},
        preferences={"optimize_for": "cost"},
    )
    best = result.best_match
    print(f"{best.provider_id} · {best.model} · score={best.score}")
```

The private key can also be supplied via the `AIP_WALLET_KEY`
environment variable, in which case `Wallet()` needs no arguments.

## How payment works

x402 turns HTTP `402 Payment Required` into a usable payment step:

1. The client makes a normal request.
2. If payment is due, the gateway replies `402` with the accepted terms
   (amount, asset, recipient, network) in the body.
3. The wallet signs an [EIP-3009](https://eips.ethereum.org/EIPS/eip-3009)
   `TransferWithAuthorization` for those exact terms — an EIP-712 typed
   signature, no gas, no on-chain transaction from your side.
4. The client retries with a `PAYMENT-SIGNATURE` header. The gateway
   verifies and settles on-chain, then serves the response.

Payments default to USDC on Base (`eip155:8453`); the network and asset
come from the gateway's `402` terms, so the wallet always signs exactly
what it is asked to pay.

## Resolve, then execute

`resolve` returns ranked matches so you can inspect price and score
before committing. `execute` resolves *and* runs the intent in one call,
proxying the provider response back:

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
- `AIPAuthError` — `401`/`403`, missing or invalid credentials.
- `AIPPaymentRequiredError` — `402`, payment required and no wallet was
  configured (or the payment was rejected).
- `AIPAPIError` — any other non-2xx response (`status_code`, `detail`, `body`).

`WalletError` is raised when a `402` challenge cannot be signed (missing
key, malformed terms).

## Offline-verifiable receipts

When a request settles, the gateway can return an **AIR/1** receipt — a
self-certifying record that a named provider fulfilled the request and it
was paid for on-chain. The point: anyone can verify it *without trusting
the party that issued it*. No callback to the issuer, no shared secret,
just the receipt bytes and public-key math.

```python
from agent_intent_x402 import verify_receipt

result = verify_receipt(receipt, intent=intent, result=response)
if result.valid:
    print("verified — signed by", result.signer)
```

Verification recomputes the intent and result hashes, checks the
signature against the signer's public key, and rejects any tampering.
Two signature suites are supported: `secp256k1`/EIP-191 for EVM chains
like Base (the same key type that signs x402 payments) and `ed25519`
for Solana. See [`examples/04_offline_receipt.py`](examples/04_offline_receipt.py)
for an end-to-end, network-free demo.

## Protocol

The intent wire format and endpoint contract are defined in the
[Agent Intent Protocol specification](https://github.com/api-jarvisclaw/agent-intent-protocol).
The payment layer follows the open [x402](https://x402.org) protocol.

## License

MIT
