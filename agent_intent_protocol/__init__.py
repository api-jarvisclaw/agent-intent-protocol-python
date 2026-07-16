"""Agent Intent Protocol — Python SDK.

Declare an intent, let the protocol route it to the optimal provider.

    from agent_intent_protocol import AIPClient, IntentType

    with AIPClient(api_key="sk-...") as client:
        result = client.resolve(IntentType.CHAT_COMPLETION)
        print(result.best_match.provider_id)
"""

from .client import DEFAULT_ENDPOINT, AIPClient
from .errors import (
    AIPAPIError,
    AIPAuthError,
    AIPConnectionError,
    AIPError,
    AIPPaymentRequiredError,
)
from .models import (
    Constraints,
    IntentType,
    Match,
    OptimizeFor,
    Preferences,
    Pricing,
    Provider,
    ResolveResult,
)

__version__ = "0.1.0"

__all__ = [
    "AIPClient",
    "DEFAULT_ENDPOINT",
    "AIPError",
    "AIPAPIError",
    "AIPAuthError",
    "AIPConnectionError",
    "AIPPaymentRequiredError",
    "IntentType",
    "OptimizeFor",
    "Constraints",
    "Preferences",
    "Pricing",
    "Match",
    "ResolveResult",
    "Provider",
]
