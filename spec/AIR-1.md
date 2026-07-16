# AIR/1 — Agent Intent Receipt

The canonical specification is the IETF Internet-Draft:

**[`draft-air-agent-intent-receipt-00.md`](./draft-air-agent-intent-receipt-00.md)**

It is written in [kramdown-rfc](https://github.com/cabo/kramdown-rfc) source
form and compiles to the xml2rfc v3 XML/text that the IETF Datatracker accepts.

## Building the draft

```sh
gem install kramdown-rfc2629          # Ruby toolchain
pip install xml2rfc                    # renderer

kramdown-rfc draft-air-agent-intent-receipt-00.md > draft.xml
xml2rfc draft.xml --text --html        # -> draft.txt, draft.html
```

The `agent_intent_x402.receipt` module is the reference implementation of the
draft (canonicalization, hashing, the `secp256k1-eip191` and `ed25519` signer
suites, and verification).
