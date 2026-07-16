"""Long-running AIR/1 federation node (HTTP).

Wraps the independent ``air_federation_verifier`` in a dependency-free HTTP
service so any third party can POST a receipt and get a verdict back without
trusting or contacting the issuer. Each node is meant to run pinned to a
*different* RPC operator (see ``AIR_NODE_RPC``); running two nodes on two
independent operators and comparing verdicts is what turns "one implementation
can verify" into "trust nobody" evidence.

Environment:
    AIR_NODE_NAME  Human-readable node id echoed in every response.
    AIR_NODE_RPC   JSON-RPC endpoint this node uses for the on-chain leg.
                   When unset, the verifier falls back to its built-in public
                   default for the receipt's chain.
    AIR_NODE_PORT  TCP port to listen on (default 8080).

Endpoints:
    GET  /health   -> {"status": "ok", "node": ..., "rpc": ...}
    POST /verify   -> body: {"receipt": {...},
                             "intent": {...}?, "result": {...}?,
                             "check_chain": bool?}
                      returns the signature verdict, and (when check_chain and
                      a settlement is present) the on-chain settlement verdict.

Uses only the Python standard library; no web framework, no vendor SDK.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from air_federation_verifier import (
    __version__ as verifier_version,
    verify_receipt,
    verify_settlement,
)

NODE_NAME = os.environ.get("AIR_NODE_NAME", "air-node")
NODE_RPC = os.environ.get("AIR_NODE_RPC") or None
NODE_PORT = int(os.environ.get("AIR_NODE_PORT", "8080"))


def _verdict(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Run the verification and build the response body.

    Returns (http_status, body). The receipt is considered ``ok`` only when the
    offline signature/hash checks pass and, if a chain check ran, it neither
    failed to confirm nor mismatched the stated transfer.
    """
    receipt = payload.get("receipt")
    if not isinstance(receipt, dict):
        return 400, {"error": "body must contain a 'receipt' object"}

    report = verify_receipt(
        receipt,
        original_intent=payload.get("intent"),
        original_result=payload.get("result"),
    )
    body: dict[str, Any] = {
        "node": NODE_NAME,
        "rpc": NODE_RPC or "(built-in public default)",
        "verifier_version": verifier_version,
        "signature": report.as_dict(),
    }
    ok = report.valid

    if payload.get("check_chain"):
        settlement = receipt.get("settlement") or {}
        chain_report = verify_settlement(settlement, endpoint=NODE_RPC)
        body["settlement"] = chain_report.as_dict()
        if chain_report.checked and chain_report.confirmed is False:
            ok = False
        if chain_report.checked and chain_report.matched is False:
            ok = False

    body["ok"] = ok
    return 200, body


class Handler(BaseHTTPRequestHandler):
    server_version = f"air-federation-node/{verifier_version}"

    def _send(self, status: int, body: dict[str, Any]) -> None:
        raw = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        if self.path.rstrip("/") == "/health":
            self._send(200, {
                "status": "ok",
                "node": NODE_NAME,
                "rpc": NODE_RPC or "(built-in public default)",
                "verifier_version": verifier_version,
            })
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
        if self.path.rstrip("/") != "/verify":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send(400, {"error": "invalid JSON body"})
            return
        if not isinstance(payload, dict):
            self._send(400, {"error": "body must be a JSON object"})
            return
        status, body = _verdict(payload)
        self._send(status, body)

    def log_message(self, fmt: str, *args: Any) -> None:
        # Compact one-line access log to stdout.
        print(f"[{NODE_NAME}] {self.address_string()} {fmt % args}", flush=True)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", NODE_PORT), Handler)
    print(
        f"[{NODE_NAME}] AIR/1 federation node listening on :{NODE_PORT} "
        f"(rpc={NODE_RPC or 'built-in default'})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
