# Contributing

Thanks for taking the time to contribute. This project is a client for an
open protocol, so contributions that improve interoperability, clarity, and
correctness are especially welcome.

## Ground rules

- **Stay vendor-neutral.** This is an open x402 client. Nothing should hard-code
  a specific gateway, platform, or provider. Endpoints belong in configuration,
  not in the library.
- **Keep the wire format stable.** Changes to the intent wire format or the
  AIR/1 receipt format must track the
  [Agent Intent Protocol specification](https://github.com/api-jarvisclaw/agent-intent-protocol).
  If the spec needs to change, raise that first.
- **Payments are real money.** Anything touching signing or the x402 payment
  loop needs tests and careful review. A wrong byte can mean a wrong payment.

## Development setup

```bash
git clone https://github.com/api-jarvisclaw/agent-intent-x402
cd agent-intent-x402
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

The `dev` extra pulls in pytest, pytest-httpx, pytest-asyncio, ruff, and
pynacl (for the Solana ed25519 path).

## Before you open a PR

Run the same checks CI runs:

```bash
ruff check .
ruff format --check .
pytest
```

- Add or update tests for any behavior change. HTTP is mocked with
  `pytest-httpx`, so tests need no network and no real funds.
- Keep public API changes documented in the README and noted in
  `CHANGELOG.md` under an `Unreleased` heading.
- Small, focused PRs get reviewed faster than large ones.

## Commit and PR style

- Write clear commit messages in the imperative mood ("add receipt verifier",
  not "added").
- In the PR description, say what changed, why, and how you tested it.
- Link any related issue.

## Reporting bugs and requesting features

Use the issue templates. For anything security-sensitive (signing, payment
handling, key management), do **not** open a public issue — see
[SECURITY.md](SECURITY.md).
