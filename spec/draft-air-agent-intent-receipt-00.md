---
title: "AIR/1: Offline-Verifiable Agent Intent Receipts over x402"
abbrev: "Agent Intent Receipt"
category: std
docname: draft-air-agent-intent-receipt-00
submissiontype: IETF
number:
date:
consensus: true
v: 3
area: "Applications and Real-Time"
keyword:
 - agent
 - receipt
 - x402
 - payment
 - offline verification
venue:
  group: ""
  type: ""
  mail: ""
  arch: ""
  github: "api-jarvisclaw/agent-intent-x402"
  latest: "https://github.com/api-jarvisclaw/agent-intent-x402/tree/main/spec"

author:
 -
    fullname: "AIR Editors"
    organization: "Independent"
    email: "spec@example.org"

normative:
  RFC2119:
  RFC8174:
  RFC4648:
  RFC8259:
  RFC6234:
  SHS:
    title: "Secure Hash Standard (SHS)"
    author:
      - org: "National Institute of Standards and Technology"
    date: 2015-08
    seriesinfo:
      FIPS: "180-4"

informative:
  RFC8785:
  RFC7515:
  x402:
    title: "x402: An HTTP-native payment protocol"
    target: "https://x402.org"
    author:
      - org: "x402"
    date: 2025
  EIP-191:
    title: "EIP-191: Signed Data Standard"
    target: "https://eips.ethereum.org/EIPS/eip-191"
    author:
      - name: "M. Swende"
      - name: "N. Johnson"
    date: 2016
  EIP-712:
    title: "EIP-712: Typed structured data hashing and signing"
    target: "https://eips.ethereum.org/EIPS/eip-712"
    author:
      - name: "R. Belchior"
      - name: "L. Logvinov"
    date: 2017
  EIP-3009:
    title: "EIP-3009: Transfer With Authorization"
    target: "https://eips.ethereum.org/EIPS/eip-3009"
    author:
      - name: "P. Gao"
      - name: "D. Mohsen"
    date: 2020
  RFC8032:
  SEC2:
    title: "SEC 2: Recommended Elliptic Curve Domain Parameters"
    author:
      - org: "Standards for Efficient Cryptography Group"
    date: 2010

--- abstract

An Agent Intent Receipt (AIR) is a self-certifying record that an HTTP request
was fulfilled by a named provider and paid for on-chain over the x402 payment
protocol. A receipt can be verified offline, by any party, without trusting
the party that issued it and without access to the issuer's systems. This
document defines the AIR/1 object model, its canonical JSON serialization, its
extensible signature-suite framework, the verification procedure, and the
associated IANA registry. Two initial signature suites are defined, one for
secp256k1/EVM signers and one for Ed25519/Solana signers.

--- middle

# Introduction

The x402 protocol {{x402}} lets a client pay for a single HTTP request on-chain
with no account and no API key: the server answers an unpaid request with HTTP
402 (Payment Required), the client returns a payment authorization, and the
server serves the result once settlement is arranged. After settlement the
client holds a result, but nothing that independently proves *what was
requested*, *who fulfilled it*, and *that payment occurred*.

This document defines the Agent Intent Receipt, version 1 (AIR/1): a compact,
signed JSON object that binds those three facts together so a third party (an
auditor, a marketplace, or a dispute resolver) can check them after the fact,
offline, with no access to the issuer.

AIR/1 is transport- and platform-neutral. It does not depend on any particular
gateway, facilitator, or chain beyond the abstractions defined here.

## Requirements Language

{::boilerplate bcp14-tagged}

## Terminology

Payer:
: The party that authorizes and funds the on-chain payment for a request.

Facilitator:
: The party that submits the payment on-chain and produces a settlement
  transaction. In x402 this is typically a third-party settlement service.

Issuer:
: The provider or gateway that fulfills the request and signs the receipt. The
  issuer's cryptographic identity is carried in the signature block
  ({{signature}}).

Verifier:
: Any party that checks a receipt. A verifier needs only public information.

Receipt:
: An AIR/1 object as defined in {{receipt-object}}.

# Trust Model {#trust-model}

AIR/1 is trust-minimizing: three independent parties back three independent
facts, and no single party can forge the whole receipt.

| Fact | Backed by | How a verifier checks it |
| Payment happened | Facilitator, on-chain | Look up `settlement.tx_hash` on the named chain |
| Intent and result are untampered | SHA-256 hashes | Recompute `intent_hash` / `result_hash` ({{canonical}}) |
| This receipt was issued by X | Issuer's signature | Verify `signature.value` against `signature.signer` ({{verification}}) |

The facilitator holds its own settlement key and lands the payment on-chain;
the receipt never needs that key. The issuer signs the whole receipt with its
own key, identified by `signature.signer`. The facilitator and the issuer are
distinct roles and are generally distinct entities.

The payment authorization signed by the payer (for example, an EIP-3009
{{EIP-3009}} `transferWithAuthorization` over EIP-712 {{EIP-712}}) is a
separate signature, by a separate key, over a separate payload, and is out of
scope for this document. AIR/1 attests to fulfillment, not to the payment
authorization. Implementations MUST NOT reuse the payer's payment-authorization
signature as the receipt signature.

# Receipt Object {#receipt-object}

An unsigned receipt is a JSON object {{RFC8259}} with the following members.

| Field | Type | Required | Description |
| `version` | string | yes | Format version. MUST be `"AIR/1"`. |
| `issued_at` | string | yes | ISO 8601 UTC instant, `YYYY-MM-DDTHH:MM:SSZ`. |
| `provider_used` | string | yes | Identifier of the provider that fulfilled the intent. |
| `intent_hash` | string | yes | Lowercase SHA-256 hex digest of the canonical intent ({{canonical}}). |
| `result_hash` | string | yes | Lowercase SHA-256 hex digest of the canonical result ({{canonical}}). |
| `settlement` | object | yes | On-chain settlement facts ({{settlement-object}}). |
| `issuer` | string | no | Human-readable name of the issuing service. The cryptographic identity is `signature.signer`. |
| `signature` | object | after signing | Issuer signature block ({{signature}}). |

Implementations MAY include additional top-level members. A verifier MUST
preserve unknown members verbatim; unknown members are covered by the signature
({{signature}}).

## The settlement Object {#settlement-object}

`settlement` records what happened on-chain. Its members are informational for
verification; the authoritative source is the chain itself.

| Field | Type | Required | Description |
| `tx_hash` | string | yes | Settlement transaction hash. To be confirmed on-chain. |
| `network` | string | yes | Chain identifier, e.g. `eip155:8453` (Base) or `solana:mainnet`. |
| `amount` | string | yes | Amount settled, in the asset's smallest unit, as a decimal string. |
| `asset` | string | yes | Asset contract address or mint. |
| `facilitator` | string | no | Facilitator that settled the payment. |
| `timestamp` | string | no | ISO 8601 settlement time. |

# Canonical Serialization {#canonical}

Signatures and hashes are computed over a canonical JSON encoding so that
independent implementations, in any language, produce byte-identical output.
The canonical form of a value is produced by the following rules, applied
recursively. These rules are compatible with JCS {{RFC8785}} for the value
subset used by this specification.

1. Object member names are sorted in ascending order by Unicode code point.
2. No insignificant whitespace is emitted. The value separator is U+002C (`,`)
   and the name/value separator is U+003A (`:`).
3. Output is UTF-8. Characters outside the ASCII range are emitted literally
   and MUST NOT be `\u`-escaped, except where JSON string escaping is required
   by {{RFC8259}}.
4. A number whose value is an integer (for example `500.0`) is emitted as that
   integer (`500`). Non-integer numbers are emitted unchanged. Boolean values
   are never treated as numbers.

`intent_hash` and `result_hash` are the lowercase SHA-256 {{SHS}} {{RFC6234}}
hex digests of the canonical bytes of the intent object and the result value,
respectively:

~~~
intent_hash = LOWER-HEX( SHA-256( canonical(intent) ) )
result_hash = LOWER-HEX( SHA-256( canonical(result) ) )
~~~

# Signature {#signature}

The `signature` object binds the issuer to the entire receipt.

| Field | Type | Required | Description |
| `algorithm` | string | yes | Signature suite ({{suites}}). |
| `signer` | string | yes | Issuer public identity (address or public key). |
| `key_id` | string | no | Optional key identifier (for example a DID or key fragment). |
| `value` | string | yes | Signature over the signable bytes ({{signable}}). |

## Signable Bytes {#signable}

The signature covers the canonical JSON of the entire receipt, including the
`signature` object with its `value` member omitted. A signer:

1. Takes the full receipt with its `signature` object attached.
2. Removes `signature.value`, leaving `algorithm`, `signer`, and, if present,
   `key_id`.
3. Canonicalizes the result ({{canonical}}). Those bytes are the signable
   payload.

Signing the whole object, rather than a delimiter-joined string of selected
fields, makes the format resistant to field-injection and cross-field ambiguity
and is forward-compatible: any field added later is automatically covered, and
`algorithm`, `signer`, and `key_id` are all bound by the signature.

# Signature Suites {#suites}

The suite is selected by `signature.algorithm`. A verifier selects the matching
suite; verification needs only public-key material and is fully offline. A
verifier that does not recognize `signature.algorithm` MUST treat the signature
as invalid (fail closed).

| `algorithm` | Curve / scheme | `signer` identity | Signature encoding |
| `secp256k1-eip191` | secp256k1 ECDSA {{SEC2}}, EIP-191 envelope | `0x` Ethereum address | `0x`-prefixed hex of the 65-byte `r \|\| s \|\| v` signature |
| `ed25519` | Ed25519 EdDSA {{RFC8032}} | base58 of the 32-byte public key | base64 {{RFC4648}} of the 64-byte signature |

## secp256k1-eip191 {#suite-eip191}

The signable bytes ({{signable}}) are signed as an EIP-191 {{EIP-191}} personal
message: the signer prepends the string
`"\x19Ethereum Signed Message:\n" || len(message)` and signs the Keccak-256
digest of that concatenation using secp256k1 ECDSA {{SEC2}}. The leading `0x19`
byte provides domain separation so the signed bytes cannot also be a valid
Ethereum transaction. `signer` is the Ethereum address. A verifier recovers the
address from the signature and compares it to `signer` case-insensitively.

This suite reuses the key and signing primitive an EVM wallet already has, so
no new key material is introduced for receipts.

## ed25519 {#suite-ed25519}

The signable bytes are signed directly with an Ed25519 {{RFC8032}} secret key,
with no additional envelope. `signer` is the base58 encoding of the 32-byte
public key; `value` is the base64 {{RFC4648}} of the 64-byte detached
signature. This is the native signature scheme on Solana.

# Verification {#verification}

Given a receipt, a verifier:

1. Checks that `version` equals `"AIR/1"`.
2. Selects the suite for `signature.algorithm`. An unrecognized algorithm, or a
   missing `value` or `signer`, makes the signature invalid.
3. Reconstructs the signable bytes ({{signable}}) and verifies `signature.value`
   against `signature.signer` using the selected suite.
4. If the original intent is available, recomputes `intent_hash` and compares.
5. If the original result is available, recomputes `result_hash` and compares.
6. Optionally pins the issuer by requiring `signature.signer` to equal an
   expected value (case-insensitively for EVM addresses).

A receipt is valid when the signature verifies, the version is `"AIR/1"`, the
signer matches any configured pin, and no supplied hash mismatches. Hash checks
that the caller does not supply are skipped, not failed.

Confirming the payment itself is out of scope for receipt verification. A
verifier that requires proof of payment MUST look up `settlement.tx_hash` on the
named chain and confirm the amount, asset, and recipient. AIR/1 attests that the
issuer *asserts* a given settlement; the chain is authoritative on whether it
happened.

# Example

A signed EVM receipt (whitespace added for readability; the signed bytes use the
canonical form of {{canonical}}):

~~~json
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
~~~

# IANA Considerations {#iana}

This document requests that IANA create a new registry as described below.

## AIR Signature Suites Registry

IANA is requested to create the "AIR Signature Suites" registry. The registry
governs the values of the `algorithm` member of the AIR/1 signature object
({{signature}}).

The registration policy is Specification Required ({{!RFC8126}}). Each entry
contains:

Algorithm:
: The string value used in `signature.algorithm`. Values MUST match the ABNF
  `1*( %x21-7E )` (printable US-ASCII, no spaces) and are compared as exact,
  case-sensitive byte strings.

Description:
: A short human-readable description.

Signer Identity Encoding:
: How `signature.signer` is encoded for this suite.

Signature Encoding:
: How `signature.value` is encoded for this suite.

Reference:
: A stable reference to the defining specification.

The initial contents of the registry are:

| Algorithm | Description | Signer Identity Encoding | Signature Encoding | Reference |
| `secp256k1-eip191` | secp256k1 ECDSA with EIP-191 personal-message envelope | `0x` Ethereum address | `0x` hex, 65 bytes `r\|\|s\|\|v` | RFC-THIS, {{suite-eip191}} |
| `ed25519` | Ed25519 EdDSA, no envelope | base58 32-byte public key | base64 64-byte signature | RFC-THIS, {{suite-ed25519}} |

# Security Considerations {#security}

Sign the whole object. An implementation MUST NOT sign a subset of fields or a
delimiter-joined string; doing so invites field-injection and cross-field
ambiguity. {{signable}} signs the canonical whole, which is the only supported
mode.

The receipt is not proof of payment. A valid signature proves only that the
issuer *asserts* a settlement. For value-bearing decisions a verifier MUST
confirm `settlement.tx_hash` on-chain, as described in {{verification}}.

Pin the issuer. An unpinned valid signature says only that *some* holder of
*some* key signed the receipt. A verifier that knows who should have signed MUST
pin `signature.signer` to the expected identity.

Canonicalization is load-bearing. Two encoders that disagree on number
normalization, member ordering, or string escaping will disagree on hashes and
signatures. Implementations MUST follow {{canonical}} exactly. The number
normalization in {{canonical}} assumes intent and result payloads carry no
numbers that require more precision than an integer-valued float can represent;
producers SHOULD encode high-precision or large-magnitude quantities as strings.

Key separation. The issuer's receipt-signing key SHOULD be distinct in role
from any payment key. Even where the same curve is used (for example secp256k1
on EVM), the payment authorization and the receipt use different envelopes and
different payloads and MUST NOT be conflated ({{trust-model}}).

Replay and freshness. AIR/1 does not itself prevent a receipt from being
presented more than once. `issued_at` and the on-chain uniqueness of
`settlement.tx_hash` give a verifier the means to detect duplicates;
applications that require single-use semantics MUST enforce them out of band.

Algorithm agility and downgrade. Because the suite is named in the receipt, a
verifier MUST fail closed on unrecognized suites and MUST NOT silently accept a
weaker suite than a policy requires.

--- back

# Reference Implementation

The `agent_intent_x402.receipt` module of the agent-intent-x402 project
implements this specification: `canonicalize`, `hash_object`, `build_receipt`,
`sign_receipt`, `verify_receipt`, and the `secp256k1-eip191` and `ed25519`
signer/verifier suites. It is provided for interoperability testing and is not
normative.

# Acknowledgments
{:numbered="false"}

This work distills the offline-verifiable-receipt idea explored by earlier
agent-intent projects into a platform-neutral, x402-native form.
