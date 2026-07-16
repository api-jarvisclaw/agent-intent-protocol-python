"""CLI for the independent AIR/1 federation verifier.

Usage::

    python -m air_federation_verifier RECEIPT.json \
        [--intent INTENT.json] [--result RESULT.json] \
        [--check-chain] [--endpoint URL]

Reads a signed receipt, verifies the signature offline (recomputing the
signable bytes with an independent canonicalizer), optionally recomputes
``intent_hash`` / ``result_hash`` from the originals, and optionally confirms
the settlement transaction on-chain. Exit code 0 iff everything checked
passed; 1 otherwise. Prints a JSON report to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .chain import verify_settlement
from .verify import verify_receipt


def _load(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="air_federation_verifier",
        description="Independently verify an AIR/1 receipt (trust nobody).",
    )
    parser.add_argument("receipt", help="path to the signed receipt JSON")
    parser.add_argument("--intent", help="path to the original intent JSON")
    parser.add_argument("--result", help="path to the original result JSON")
    parser.add_argument(
        "--check-chain",
        action="store_true",
        help="also confirm the settlement tx on-chain via public RPC",
    )
    parser.add_argument(
        "--endpoint",
        help="JSON-RPC endpoint for the chain check (default: public node)",
    )
    args = parser.parse_args(argv)

    receipt = _load(args.receipt)
    original_intent = _load(args.intent) if args.intent else None
    original_result = _load(args.result) if args.result else None

    report = verify_receipt(
        receipt,
        original_intent=original_intent,
        original_result=original_result,
    )
    out: dict[str, Any] = {"signature": report.as_dict()}
    ok = report.valid

    if args.check_chain:
        settlement = receipt.get("settlement") or {}
        chain_report = verify_settlement(settlement, endpoint=args.endpoint)
        out["settlement"] = chain_report.as_dict()
        # A chain check only lowers the verdict if it actually ran and failed.
        # Both a failed/absent transaction (confirmed is False) and a
        # transaction that does not match the stated amount/asset/pay_to
        # (matched is False) invalidate the receipt.
        if chain_report.checked and chain_report.confirmed is False:
            ok = False
        if chain_report.checked and chain_report.matched is False:
            ok = False

    out["ok"] = ok
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
