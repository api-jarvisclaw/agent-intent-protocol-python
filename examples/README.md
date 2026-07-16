# Examples

Runnable examples, ordered from "no setup" to "spends real money".

| File | Needs | What it shows |
|------|-------|---------------|
| [`01_discover.py`](01_discover.py) | nothing | List providers for an intent — public endpoint, no auth |
| [`02_resolve.py`](02_resolve.py) | API key | Rank providers by your constraints and preferences |
| [`03_execute_with_wallet.py`](03_execute_with_wallet.py) | funded test wallet | The full x402 loop: 402 → sign → retry → result |
| [`04_offline_receipt.py`](04_offline_receipt.py) | nothing | Issue and **offline-verify** an AIR/1 settlement receipt |

## Running them

From the repository root:

```bash
pip install -e .
python examples/01_discover.py
python examples/04_offline_receipt.py   # fully offline, no network
```

`01` and `04` run with zero configuration. `02` and `03` talk to a live
gateway, so they read credentials from the environment:

```bash
export AIP_ENDPOINT=https://your-gateway.example   # optional, defaults to the hosted gateway
export AIP_API_KEY=sk-...                           # for 02_resolve.py
export AIP_WALLET_KEY=0x...                          # for 03_execute_with_wallet.py
```

> `03_execute_with_wallet.py` spends real USDC. Use a throwaway wallet with a
> small balance, never your main key.
