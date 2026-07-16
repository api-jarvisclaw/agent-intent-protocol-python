"""Asynchronous Agent Intent client with built-in x402 payment.

This is the ``asyncio`` mirror of :class:`agent_intent_x402.client.AIPClient`.
It exposes the same protocol methods with identical semantics — declare an
intent, discover a provider, and settle on-chain over the open
`x402 <https://x402.org>`_ protocol — but every network call is awaitable.

When the client is given a :class:`~agent_intent_x402.wallet.Wallet`, any
HTTP 402 challenge is answered automatically: the wallet signs the payment
and the request is retried once with a ``PAYMENT-SIGNATURE`` header.

Example::

    import asyncio
    from agent_intent_x402 import AsyncAIPClient, IntentType, Wallet

    async def main():
        async with AsyncAIPClient(wallet=Wallet(private_key="0x...")) as client:
            result = await client.resolve(
                IntentType.CHAT_COMPLETION,
                constraints={"max_price_usd": 0.01},
            )
            print(result.best_match.provider_id)

    asyncio.run(main())
"""

from __future__ import annotations

import os
from typing import Any, Optional, Union

import httpx

from .client import (
    DEFAULT_ENDPOINT,
    _coerce_constraints,
    _coerce_preferences,
    _extract_providers,
    _ConstraintsArg,
    _PreferencesArg,
    __version__,
)
from .errors import (
    AIPAPIError,
    AIPAuthError,
    AIPConnectionError,
    AIPPaymentRequiredError,
)
from .models import (
    IntentType,
    Provider,
    ResolveResult,
)
from .wallet import Wallet


class AsyncAIPClient:
    """Asynchronous client with built-in x402 payment.

    Mirrors :class:`~agent_intent_x402.client.AIPClient` method-for-method;
    every protocol call is a coroutine. See the sync client for full
    argument documentation.

    Args:
        api_key: Optional bearer token for gateways that still use API-key
            auth. Falls back to the ``JARVISCLAW_API_KEY`` environment
            variable. Not required when paying with a wallet.
        wallet: A :class:`~agent_intent_x402.wallet.Wallet`. When set, HTTP
            402 responses are answered automatically by signing the payment
            and retrying with a ``PAYMENT-SIGNATURE`` header.
        endpoint: Base URL of the gateway. Defaults to a hosted service;
            override to target any compliant x402 deployment.
        timeout: Request timeout in seconds.
        http_client: Optional preconfigured ``httpx.AsyncClient``.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        wallet: Optional[Wallet] = None,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 30.0,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("JARVISCLAW_API_KEY")
        self.wallet = wallet
        self.endpoint = endpoint.rstrip("/")
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout)

    # ── context manager ────────────────────────────────────────────────
    async def __aenter__(self) -> "AsyncAIPClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client (only if this client owns it)."""
        if self._owns_client:
            await self._http.aclose()

    # ── internal request helper ────────────────────────────────────────
    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"agent-intent-x402/{__version__}",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.endpoint}{path}"
        try:
            resp = await self._http.request(
                method, url, json=json, params=params, headers=self._headers()
            )
        except httpx.RequestError as exc:
            raise AIPConnectionError(f"request to {url} failed: {exc}") from exc

        # x402: answer a payment challenge by signing it and retrying once.
        if resp.status_code == 402 and self.wallet is not None:
            resp = await self._pay_and_retry(
                resp, method, url, json=json, params=params
            )

        if resp.status_code >= 400:
            self._raise_for_status(resp)

        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError as exc:
            raise AIPAPIError(
                f"invalid JSON in response from {url}",
                status_code=resp.status_code,
                body=resp.text,
            ) from exc

    async def _pay_and_retry(
        self,
        resp: httpx.Response,
        method: str,
        url: str,
        *,
        json: Optional[dict[str, Any]],
        params: Optional[dict[str, Any]],
    ) -> httpx.Response:
        """Sign the 402 challenge and retry the request once.

        Returns the retried response, or the original 402 response if the
        challenge body could not be parsed (so normal error handling runs).
        """
        try:
            challenge = resp.json()
        except ValueError:
            return resp

        signature = self.wallet.sign_challenge(challenge)
        headers = self._headers()
        headers["PAYMENT-SIGNATURE"] = signature
        try:
            return await self._http.request(
                method, url, json=json, params=params, headers=headers
            )
        except httpx.RequestError as exc:
            raise AIPConnectionError(f"request to {url} failed: {exc}") from exc

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        detail: Optional[str] = None
        body: Any = None
        try:
            body = resp.json()
            if isinstance(body, dict):
                detail = body.get("detail") or body.get("error") or body.get("message")
        except ValueError:
            body = resp.text
            detail = resp.text or None

        message = f"AIP server returned {resp.status_code}"
        if detail:
            message = f"{message}: {detail}"

        code = resp.status_code
        if code in (401, 403):
            raise AIPAuthError(message, status_code=code, detail=detail, body=body)
        if code == 402:
            raise AIPPaymentRequiredError(
                message, status_code=code, detail=detail, body=body
            )
        raise AIPAPIError(message, status_code=code, detail=detail, body=body)

    # ── protocol methods ───────────────────────────────────────────────
    async def resolve(
        self,
        intent: Union[IntentType, str],
        *,
        constraints: _ConstraintsArg = None,
        preferences: _PreferencesArg = None,
    ) -> ResolveResult:
        """Resolve an intent to ranked provider matches.

        Endpoint: ``POST /v1/intent/resolve`` (requires authentication).
        """
        body: dict[str, Any] = {"intent": str(intent)}
        c = _coerce_constraints(constraints)
        if c:
            body["constraints"] = c
        p = _coerce_preferences(preferences)
        if p:
            body["preferences"] = p
        data = await self._request("POST", "/v1/intent/resolve", json=body)
        return ResolveResult.from_dict(data or {})

    async def resolve_natural(
        self,
        query: str,
        *,
        session_id: Optional[str] = None,
        constraints: _ConstraintsArg = None,
    ) -> dict[str, Any]:
        """Resolve a natural-language query to providers or a clarification.

        Endpoint: ``POST /v1/intent/resolve/natural`` (requires authentication).
        """
        body: dict[str, Any] = {"query": query}
        if session_id is not None:
            body["session_id"] = session_id
        c = _coerce_constraints(constraints)
        if c:
            body["constraints"] = c
        return await self._request("POST", "/v1/intent/resolve/natural", json=body) or {}

    async def discover(
        self,
        *,
        intent_type: Union[IntentType, str, None] = None,
    ) -> list[Provider]:
        """Discover providers, optionally filtered by intent type.

        Endpoint: ``GET /v1/intent/discover`` (no authentication required).
        """
        params: dict[str, Any] = {}
        if intent_type is not None:
            params["intent_type"] = str(intent_type)
        data = await self._request("GET", "/v1/intent/discover", params=params or None)
        return _extract_providers(data)

    async def execute(
        self,
        intent: Union[IntentType, str],
        payload: dict[str, Any],
        *,
        constraints: _ConstraintsArg = None,
        preferences: _PreferencesArg = None,
    ) -> Any:
        """Resolve an intent and execute it against the selected provider.

        Endpoint: ``POST /v1/intent/execute`` (requires authentication).
        """
        body: dict[str, Any] = {"intent": str(intent), "payload": payload}
        c = _coerce_constraints(constraints)
        if c:
            body["constraints"] = c
        p = _coerce_preferences(preferences)
        if p:
            body["preferences"] = p
        return await self._request("POST", "/v1/intent/execute", json=body)

    async def list_intent_types(self) -> list[str]:
        """List the intent types the gateway supports.

        Endpoint: ``GET /v1/intent/types`` (no authentication required).
        """
        data = await self._request("GET", "/v1/intent/types")
        if isinstance(data, dict):
            return data.get("intent_types", [])
        return data or []

    async def list_providers(self) -> list[Provider]:
        """List all registered providers.

        Endpoint: ``GET /v1/providers`` (no authentication required).
        """
        data = await self._request("GET", "/v1/providers")
        return _extract_providers(data)
