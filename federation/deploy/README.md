# AIR/1 Federation Node Deployment

A minimal, dependency-free way to run the independent `air_federation_verifier`
as a long-running HTTP service, and to stand up **two nodes on two different RPC
operators** so a receipt can be checked by parties who trust neither the issuer
nor each other.

## What's here

| File | Purpose |
| --- | --- |
| `server.py` | Stdlib-only HTTP wrapper. `GET /health`, `POST /verify`. No web framework, no vendor SDK. |
| `Dockerfile` | Builds the verifier package + the HTTP wrapper into one image. |
| `docker-compose.yml` | Two nodes, each pinned to a **different** Base RPC operator. |

## Why two operators

The offline legs (recompute intent/result hash, verify signature) need no
network at all. The on-chain leg (`check_chain: true`) confirms the settlement
`tx_hash` against a JSON-RPC endpoint. If both nodes talked to the *same* RPC
provider, a compromised or lying provider could fool both at once. Pinning each
node to an independent operator (`AIR_NODE_RPC`) and comparing verdicts is what
makes the result "trust nobody" evidence rather than "trust one vendor."

## Run with Docker

```bash
# from the federation/ directory (build context is the package root)
docker compose -f deploy/docker-compose.yml up --build

curl -s localhost:8081/health
curl -s localhost:8082/health

# verify a receipt against both nodes
curl -s -X POST localhost:8081/verify \
  -H 'content-type: application/json' \
  -d @- <<'JSON'
{"receipt": { ... }, "intent": { ... }, "result": { ... }, "check_chain": true}
JSON
```

Agreement across `:8081` and `:8082` is your two-operator consensus.

## Run without Docker

```bash
pip install .            # installs air_federation_verifier
AIR_NODE_NAME=node-a AIR_NODE_RPC=https://base.drpc.org           AIR_NODE_PORT=8081 python deploy/server.py &
AIR_NODE_NAME=node-b AIR_NODE_RPC=https://base-rpc.publicnode.com AIR_NODE_PORT=8082 python deploy/server.py &
```

## Configuration

| Env var | Default | Meaning |
| --- | --- | --- |
| `AIR_NODE_NAME` | `air-node` | Node id echoed in every response. |
| `AIR_NODE_RPC` | built-in public default | JSON-RPC endpoint for the on-chain leg. |
| `AIR_NODE_PORT` | `8080` | TCP listen port. |

## `POST /verify` contract

Request body:

```json
{
  "receipt":  { "...": "the AIR/1 receipt to verify" },
  "intent":   { "...": "optional original intent, enables intent_hash check" },
  "result":   { "...": "optional original result, enables result_hash check" },
  "check_chain": false
}
```

Response body:

```json
{
  "node": "node-a",
  "rpc": "https://base.drpc.org",
  "verifier_version": "0.1.0",
  "signature": {
    "valid": true,
    "algorithm": "secp256k1-eip191",
    "signer": "0x...",
    "signature_valid": true,
    "intent_hash_valid": true,
    "result_hash_valid": true,
    "errors": []
  },
  "ok": true
}
```

When `check_chain` is `true` and the receipt carries a `settlement`, the
response also includes a `settlement` block with the on-chain confirmation.

## Security notes

- The node exposes **no authentication** by design: it is a read-only public
  verifier that reveals nothing an observer could not recompute themselves. Do
  not add write endpoints or state to it. If you deploy it on the public
  internet, put it behind a rate limiter.
- The node never contacts the issuer and holds no keys. It only recomputes
  hashes, checks a signature, and optionally reads a public chain.
