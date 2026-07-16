# AIR/1 Federation Verifier

An **independent, runnable reference implementation** of the AIR/1 receipt
verification procedure defined in
[`draft-air-agent-intent-receipt-00`](../spec/draft-air-agent-intent-receipt-00.txt).

The point of this package is to demonstrate the core promise of AIR/1:

> **You do not have to trust the issuer.** Anyone can verify a receipt with
> their own independent code and, for settlement, with the blockchain itself.

## Why a second implementation?

The issuer signs receipts with `agent_intent_x402`. This verifier is a
*separate* codebase that shares **no code** with the issuer. It re-derives the
canonical signable bytes straight from the specification. If a receipt signed
by the issuer verifies against bytes produced here, then two independent
implementations agree on the protocol — which is exactly what an open standard
needs.

This is what a "federation node" runs: it never calls the issuer, it just
checks the math.

## What it verifies

1. **Signature** — recomputes the canonical JSON (RFC 8785-style) of the
   receipt with `signature.value` removed, then checks the signature against
   the claimed `signer`, routed by the `algorithm` field:
   - `secp256k1-eip191` (Base / EVM) — recovers the signer address from an
     EIP-191 `personal_sign` signature.
   - `ed25519` (Solana) — verifies against the base58 public key.
2. **Intent / result hashes** — if you supply the original intent and/or
   result, it recomputes `intent_hash` / `result_hash` and checks they match.
3. **On-chain settlement** *(optional)* — queries a public JSON-RPC endpoint to
   confirm the `settlement.tx_hash` actually exists on-chain. The chain, not
   the issuer, is authoritative on whether payment happened.

## Install

```bash
cd federation
pip install -e .
```

Runtime dependencies: `eth-account` (EVM recovery), `PyNaCl` (ed25519). Both
are widely used, actively maintained libraries.

## CLI

```bash
# Offline signature + hash verification
python -m air_federation_verifier receipt.json \
    --intent intent.json --result result.json

# Also confirm settlement on-chain
python -m air_federation_verifier receipt.json --check-chain
```

Exit code is `0` when the receipt is valid, `1` otherwise, and the full report
is printed as JSON.

### Example

```bash
python -m air_federation_verifier examples/receipt.evm.json \
    --intent examples/intent.json --result examples/result.json
```

```json
{
  "signature": {
    "valid": true,
    "algorithm": "secp256k1-eip191",
    "signer": "0x6425dcaBe4dBB9b8fFb8923620103D59C5985e72",
    "signature_valid": true,
    "intent_hash_valid": true,
    "result_hash_valid": true,
    "errors": []
  },
  "ok": true
}
```

Tamper with any field and verification fails:

```json
{ "signature": { "valid": false,
    "errors": ["signature did not verify against signer"] }, "ok": false }
```

## Library

```python
from air_federation_verifier import verify_receipt, verify_settlement
import json

receipt = json.load(open("receipt.json"))
report = verify_receipt(receipt, intent=my_intent, result=my_result)
assert report.valid

# Optional: ask the chain directly
settlement = verify_settlement(receipt["settlement"])
print(settlement.confirmed)
```

## Tests

The test suite proves cross-implementation agreement: receipts are **signed by
the issuer** (`agent_intent_x402`) and **verified here**, across both signature
suites, plus tampering-detection cases.

```bash
pip install -e . pytest
pytest tests/ -v
```

## Not tied to any platform

This verifier depends only on the public AIR/1 format. It has no knowledge of,
and no dependency on, any specific gateway, service, or vendor. Any issuer that
follows the spec produces receipts this tool can verify.
