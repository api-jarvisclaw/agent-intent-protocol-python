"""agent-intent-x402 — pay-per-request access for AI agents over x402.

Declare *what* you want, discover *who* provides it, and pay for the
request on-chain with a single signature — no accounts, no API keys, no
platform lock-in. Payment speaks the open `x402 <https://x402.org>`_
protocol, so the same client works against any compliant gateway.

    from agent_intent_x402 import AIPClient, IntentType, Wallet

    # A wallet lets the client answer HTTP 402 challenges automatically.
    wallet = Wallet(private_key="0x...")
    with AIPClient(wallet=wallet) as client:
        result = client.resolve(IntentType.CHAT_COMPLETION)
        print(result.best_match.provider_id)
"""

from .client import DEFAULT_ENDPOINT, AIPClient
from .client_async import AsyncAIPClient
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
from .receipt import (
    ALG_EVM,
    ALG_SOLANA,
    RECEIPT_VERSION,
    EvmSigner,
    SolanaSigner,
    VerificationResult,
    build_receipt,
    canonicalize,
    hash_object,
    sign_receipt,
    supported_algorithms,
    verify_receipt,
)
from .wallet import Wallet, WalletError

__version__ = "0.3.0"

__all__ = [
    "AIPClient",
    "AsyncAIPClient",
    "DEFAULT_ENDPOINT",
    "Wallet",
    "WalletError",
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
    # AIR/1 signed settlement receipts
    "RECEIPT_VERSION",
    "ALG_EVM",
    "ALG_SOLANA",
    "EvmSigner",
    "SolanaSigner",
    "VerificationResult",
    "build_receipt",
    "sign_receipt",
    "verify_receipt",
    "canonicalize",
    "hash_object",
    "supported_algorithms",
]
