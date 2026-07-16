# AIR/1 — Agent Intent Receipt

**Status:** Draft
**Version:** AIR/1
**Updated:** 2026-07-16

## Abstract

An Agent Intent Receipt (AIR) is a self-certifying record that a request was
fulfilled by a named provider and paid for on-chain over the
[x402](https://x402.org) protocol. A receipt can be verified **offline**, by
anyone, **without trusting the party that issued it**. This document defines
the AIR/1 wire format, its canonical serialization, its signature suites, and
the verification procedure.

## 1. Motivation

x402 lets an agent pay for a single HTTP request on-chain with no accounts and
no API keys. After payment settles, the caller holds a result — but nothing
that independently proves *what they asked for*, *who fulfilled it*, and *that
payment happened*. AIR/1 fills that gap with a compact, signed record that
binds those three facts together so they can be checked after the fact by a
third party (an auditor, a marketplace, a dispute resolver) with no access to
the issuer's systems.

## 2. Trust model

Three independent parties back three independent facts. No single party can
forge the whole receipt.

| Fact | Backed by | How to verify |
|------|-----------|---------------|
| Payment happened | x402 **facilitator** (e.g. Coinbase's), on-chain | Look up `settlement.tx_hash` on the named chain |
| Intent & result are untampered | Cryptographic **hashes** | Recompute `intent_hash` / `result_hash` |
| This receipt was issued by X | The **issuer's** signature | Verify `signature.value` against `signature.signer` |

The x402 facilitator settles the payment and produces `tx_hash`. It holds its
own settlement key; **the receipt never needs that key**. The issuer — the
resolver or gateway that fulfilled the request — signs the whole receipt with
its **own** key, identified by `signature.signer`. The facilitator and the
issuer are distinct roles and are generally distinct entities.

This is why the model is trust-minimizing: the payment leg is attested on a
public chain, the fulfillment leg is attested by the issuer's signature, and
the two are decoupled. An issuer cannot fabricate a settlement that does not
exist on-chain, and the facilitator never sees or signs the receipt.

## 3. Receipt object

An unsigned receipt is a JSON object with the following members.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | yes | Format version. MUST be `"AIR/1"`. |
| `issued_at` | string | yes | ISO-8601 UTC instant, `YYYY-MM-DDTHH:MM:SSZ`. |
| `provider_used` | string | yes | Identifier of the provider that fulfilled the intent. |
| `intent_hash` | string | yes | SHA-256 hex digest of the canonical intent (§4). |
| `result_hash` | string | yes | SHA-256 hex digest of the canonical result (§4). |
| `settlement` | object | yes | On-chain settlement facts (§3.1). |
| `issuer` | string | no | Human-readable name of the issuing service. The cryptographic identity is `signature.signer`. |
| `signature` | object | after signing | Issuer signature block (§5). |

Implementations MAY include additional top-level members. Unknown members
MUST be preserved verbatim and are covered by the signature (§5).

### 3.1 `settlement` object

`settlement` records what happened on-chain. Its members are informational for
verification purposes; the authoritative source is the chain itself. Typical
members:

| Field | Type | Description |
|-------|------|-------------|
| `tx_hash` | string | Settlement transaction hash. Verify this on-chain. |
| `network` | string | Chain identifier, e.g. `eip155:8453` (Base) or `solana:mainnet`. |
| `amount` | string | Amount settled, in the asset's smallest unit. |
| `asset` | string | Asset contract address or mint. |
| `facilitator` | string | x402 facilitator that settled the payment. |
| `timestamp` | string | Optional ISO-8601 settlement time. |

## 4. Canonical serialization

Signatures and hashes are computed over a **canonical** JSON encoding so that
independent implementations, in any language, produce byte-identical bytes.

The canonical form of a value is produced by these rules, applied recursively:

1. **Object keys are sorted** in ascending Unicode code-point order.
2. **No insignificant whitespace.** The item separator is `,` and the
   key/value separator is `:`.
3. **UTF-8 output.** Non-ASCII characters are emitted literally, not `\u`-escaped.
4. **Integer-valued floats normalize to integers.** A number equal to an
   integer (e.g. `500.0`) is emitted as that integer (`500`). Non-integer
   numbers are unchanged. Booleans are never treated as numbers.

`intent_hash` and `result_hash` are the lowercase SHA-256 hex digests of the
canonical bytes of the intent object and the result value respectively.

```
intent_hash  = SHA256( canonical(intent) )    # hex
result_hash  = SHA256( canonical(result) )    # hex
```

## 5. Signature

The `signature` object binds the issuer to the entire receipt.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `algorithm` | string | yes | Signature suite (§6). |
| `signer` | string | yes | Issuer's public identity (address or public key). |
| `key_id` | string | no | Optional key identifier (e.g. a DID or key fragment). |
| `value` | string | yes | The signature over the signable bytes (§5.1). |

### 5.1 Signable bytes

The signature covers the canonical JSON of the **entire receipt**, including
the `signature` block **with its `value` member omitted**. That is:

1. Take the full receipt with its `signature` object attached.
2. Remove `signature.value`, leaving `algorithm`, `signer`, and `key_id`.
3. Canonicalize the result (§4). Those bytes are the signable payload.

Signing the whole object — rather than a delimiter-joined string of selected
fields — makes the format safe against field-injection attacks and
forward-compatible: any field added later is automatically covered, and
`algorithm`, `signer`, and `key_id` are all bound by the signature.

## 6. Signature suites

The suite is selected by `signature.algorithm`. A verifier picks the matching
algorithm; it needs only public-key math, so verification is fully offline and
requires no private keys.

| `algorithm` | Chain | `signer` identity | Signature encoding |
|-------------|-------|-------------------|--------------------|
| `secp256k1-eip191` | Base / EVM | `0x` Ethereum address | `0x`-prefixed hex of the 65-byte `[r‖s‖v]` signature |
| `ed25519` | Solana | base58-encoded 32-byte public key | base64 of the 64-byte signature |

### 6.1 `secp256k1-eip191`

The signable bytes (§5.1) are signed as an Ethereum
[EIP-191](https://eips.ethereum.org/EIPS/eip-191) personal message
(`personal_sign`): the signer prepends `"\x19Ethereum Signed Message:\n" +
len(message)` and signs the Keccak-256 of that. `signer` is the recovered
Ethereum address; verification recovers the address from the signature and
compares it case-insensitively to `signer`.

This reuses the exact key and signing primitive an EVM wallet already has, so
no new key material is introduced for receipts.

### 6.2 `ed25519`

The signable bytes are signed directly with an Ed25519 secret key. `signer` is
the base58 encoding of the 32-byte public key; `value` is the base64 of the
64-byte detached signature. This is the native signature scheme on Solana.

## 7. Verification

Given a receipt, a verifier:

1. Checks `version == "AIR/1"`.
2. Selects the verifier for `signature.algorithm`. An unknown algorithm, or a
   missing `value` or `signer`, makes the signature invalid.
3. Reconstructs the signable bytes (§5.1) and verifies `signature.value`
   against `signature.signer`.
4. If the original intent is available, recomputes `intent_hash` and compares.
5. If the original result is available, recomputes `result_hash` and compares.
6. Optionally pins the issuer by requiring `signature.signer` to equal an
   expected value (case-insensitively).

A receipt is **valid** when the signature verifies, the version is `AIR/1`,
the signer matches any pin, and no supplied hash mismatches. Hash checks that
the caller does not supply are skipped, not failed.

**Out of scope:** confirming the payment itself. The verifier leaves the caller
to look up `settlement.tx_hash` on-chain and confirm the amount, asset, and
recipient. AIR/1 attests that the issuer *claims* a given settlement; the chain
is the authority on whether it happened.

## 8. Example

A signed EVM receipt (whitespace added for readability; the signed bytes use
the canonical form of §4):

```json
{
  "version": "AIR/1",
  "issued_at": "2026-07-16T09:30:00Z",
  "provider_used": "gpt-4o-mini@example-provider",
  "intent_hash": "b5d4045c3f466fa91fe2cc6abe79232a1a57cdf104f7a26e716e0a1e2789df78",
  "result_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "settlement": {
    "tx_hash": "0xabc123...",
    "network": "eip155:8453",
    "amount": "2000",
    "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "facilitator": "https://x402.org/facilitator"
  },
  "issuer": "example-gateway",
  "signature": {
    "algorithm": "secp256k1-eip191",
    "signer": "0x84fA83f3627c7C7e8d...",
    "value": "0x1c9a...ab"
  }
}
```

## 9. Reference implementation

The `agent_intent_x402.receipt` module implements this specification:
`canonicalize`, `hash_object`, `build_receipt`, `sign_receipt`,
`verify_receipt`, and the `EvmSigner` / `SolanaSigner` suites. It is the
normative reference where this prose is ambiguous.

## 10. Security considerations

- **Sign the whole object.** Never sign a subset of fields or a delimiter-joined
  string; that invites field-injection and cross-field ambiguity. §5.1 signs
  the canonical whole.
- **The receipt is not proof of payment.** It is proof that the issuer *asserts*
  a settlement. Always confirm `settlement.tx_hash` on-chain for value-bearing
  decisions.
- **Pin the issuer** when you know who should have signed. An unpinned valid
  signature only says *some* holder of *some* key signed the receipt.
- **Canonicalization is load-bearing.** Two encoders that disagree on number
  normalization or key ordering will disagree on hashes and signatures. Follow
  §4 exactly.
