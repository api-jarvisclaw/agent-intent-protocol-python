"""Exceptions raised by the Agent Intent Protocol client."""

from __future__ import annotations

from typing import Any, Optional


class AIPError(Exception):
    """Base class for all AIP client errors."""


class AIPConnectionError(AIPError):
    """Raised when the request never reached the server (network/timeout)."""


class AIPAPIError(AIPError):
    """Raised when the server returns a non-2xx response.

    Attributes:
        status_code: HTTP status code returned by the server.
        detail: Server-provided error detail, when available.
        body: Raw parsed response body, when available.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        detail: Optional[str] = None,
        body: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail
        self.body = body


class AIPAuthError(AIPAPIError):
    """Raised on 401/403 — missing or invalid API key."""


class AIPPaymentRequiredError(AIPAPIError):
    """Raised on 402 — x402 payment required to complete the request."""
