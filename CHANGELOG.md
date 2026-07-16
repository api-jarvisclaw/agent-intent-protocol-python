# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Runnable `examples/` covering discovery, resolve, wallet-paid execution, and
  offline receipt verification.
- Project scaffolding: `CONTRIBUTING.md`, `SECURITY.md`, this changelog, and
  GitHub issue/PR templates.
- README badges, a feature overview, and an offline-verifiable receipts section.

## [0.3.0]

### Added
- AIR/1 offline-verifiable settlement receipts: `build_receipt`,
  `sign_receipt`, `verify_receipt`, plus `canonicalize` and `hash_object`.
- Dual signature suites: `EvmSigner` (`secp256k1`/EIP-191) for Base and other
  EVM chains, and `SolanaSigner` (`ed25519`) for Solana.
- `AsyncAIPClient` for async workflows.

## [0.2.0]

### Added
- Wallet-based x402 payments: the client answers `402` challenges by signing an
  EIP-3009 authorization and retrying transparently.
- Intent resolution and execution over the Agent Intent Protocol:
  `resolve`, `resolve_natural`, `execute`, `discover`, `list_intent_types`,
  and `list_providers`.

## [0.1.0]

### Added
- Initial release of the `agent-intent-x402` client.

[Unreleased]: https://github.com/api-jarvisclaw/agent-intent-x402/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/api-jarvisclaw/agent-intent-x402/releases/tag/v0.3.0
[0.2.0]: https://github.com/api-jarvisclaw/agent-intent-x402/releases/tag/v0.2.0
[0.1.0]: https://github.com/api-jarvisclaw/agent-intent-x402/releases/tag/v0.1.0
