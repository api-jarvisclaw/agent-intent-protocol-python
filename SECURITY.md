# Security Policy

This library signs payment authorizations and settlement receipts with private
keys. Security reports are taken seriously.

## Reporting a vulnerability

**Do not open a public issue for security problems.**

Report privately through GitHub's
[private vulnerability reporting](https://github.com/api-jarvisclaw/agent-intent-x402/security/advisories/new),
or email the maintainers at **dev@jarvisclaw.ai**.

Please include:

- A description of the issue and its impact.
- Steps to reproduce, or a proof of concept.
- Affected version(s).

We aim to acknowledge reports within 3 business days and to provide a fix or
mitigation timeline after triage. Please give us a reasonable window to release
a fix before any public disclosure.

## Supported versions

Security fixes target the latest released version on PyPI. Older versions are
not patched retroactively; upgrade to the latest release.

## Handling keys and payments

A few things worth knowing when you use this library:

- **The wallet only signs; it never sends funds.** A `402` challenge produces an
  [EIP-3009](https://eips.ethereum.org/EIPS/eip-3009) `TransferWithAuthorization`
  signature for the exact terms quoted (amount, asset, recipient, network). The
  gateway settles that authorization on-chain.
- **A signature authorizes exactly what the challenge asks.** The wallet signs
  the terms in the `402` body and nothing more. Inspect a gateway you don't
  trust before pointing a funded wallet at it.
- **Never commit private keys.** Supply keys via environment variables
  (`AIP_WALLET_KEY`) or a secrets manager, never in source or config committed
  to a repo.
- **Use throwaway wallets for testing.** The runnable examples that spend funds
  are designed for a low-balance test wallet, not your main key.
- **Receipts are verifiable, not confidential.** An AIR/1 receipt is meant to be
  shared and independently verified. Do not put secrets in receipt `extra`
  fields — treat everything in a receipt as public.
