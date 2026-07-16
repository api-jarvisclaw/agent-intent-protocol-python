"""Data models for the Agent Intent Protocol.

All models mirror the wire format served by the AIP gateway
(default platform: https://api.jarvisclaw.ai). Field names match the
JSON contract exactly so responses deserialize without translation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class IntentType(str, Enum):
    """Intent types supported by the protocol.

    An intent describes *what* an agent wants to accomplish, decoupled
    from *which* provider or model fulfils it.
    """

    CHAT_COMPLETION = "chat_completion"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    TEXT_TO_SPEECH = "text_to_speech"
    WEB_SEARCH = "web_search"
    KNOWLEDGE_SEARCH = "knowledge_search"
    PROMPT_OPTIMIZATION = "prompt_optimization"
    DOCUMENT_PROCESSING = "document_processing"
    UTILITY = "utility"
    CODE_EXECUTION = "code_execution"
    DATA_ANALYSIS = "data_analysis"
    TRANSLATION = "translation"
    CODE_GENERATION = "code_generation"

    def __str__(self) -> str:  # allow seamless use as a plain string
        return self.value


class OptimizeFor(str, Enum):
    """Soft optimization strategy used when ranking matched providers."""

    COST = "cost"
    QUALITY = "quality"
    LATENCY = "latency"

    def __str__(self) -> str:
        return self.value


@dataclass
class Constraints:
    """Hard requirements a provider MUST satisfy to be considered a match.

    Any field left as ``None`` (or an empty list) is omitted from the
    request and imposes no constraint.
    """

    max_price_usd: Optional[float] = None
    max_latency_ms: Optional[int] = None
    features: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.max_price_usd is not None:
            out["max_price_usd"] = self.max_price_usd
        if self.max_latency_ms is not None:
            out["max_latency_ms"] = self.max_latency_ms
        if self.features:
            out["features"] = list(self.features)
        return out


@dataclass
class Preferences:
    """Soft directives that steer ranking without excluding providers."""

    optimize_for: Optional[OptimizeFor | str] = None
    limit: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.optimize_for is not None:
            out["optimize_for"] = str(self.optimize_for)
        if self.limit is not None:
            out["limit"] = self.limit
        return out


@dataclass
class Pricing:
    """Price breakdown for a provider offering."""

    input_per_million: Optional[float] = None
    output_per_million: Optional[float] = None
    per_call: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> Optional["Pricing"]:
        if not data:
            return None
        return cls(
            input_per_million=data.get("input_per_million"),
            output_per_million=data.get("output_per_million"),
            per_call=data.get("per_call"),
        )


@dataclass
class Match:
    """A single provider matched to an intent, with score and pricing.

    Unknown fields returned by the server are preserved in ``raw`` so the
    SDK never silently drops data as the protocol evolves.
    """

    provider_id: str
    score: float = 0.0
    estimated_price_usd: Optional[float] = None
    pricing: Optional[Pricing] = None
    endpoint: Optional[str] = None
    model: Optional[str] = None
    reason: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Match":
        return cls(
            provider_id=data.get("provider_id", ""),
            score=data.get("score", 0.0),
            estimated_price_usd=data.get("estimated_price_usd"),
            pricing=Pricing.from_dict(data.get("pricing")),
            endpoint=data.get("endpoint"),
            model=data.get("model"),
            reason=data.get("reason"),
            raw=data,
        )


@dataclass
class ResolveResult:
    """Result of resolving an intent to ranked provider matches.

    Mirrors the gateway response ``{matches, intent_type, total_available}``.
    """

    matches: list[Match] = field(default_factory=list)
    intent_type: Optional[str] = None
    total_available: Optional[int] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def best_match(self) -> Optional[Match]:
        """The top-ranked match, or ``None`` when nothing matched.

        The gateway returns matches pre-sorted by score, so this is simply
        the first element — exposed as a property for ergonomic access.
        """
        return self.matches[0] if self.matches else None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResolveResult":
        return cls(
            matches=[Match.from_dict(m) for m in data.get("matches", [])],
            intent_type=data.get("intent_type"),
            total_available=data.get("total_available"),
            raw=data,
        )


@dataclass
class Provider:
    """A provider entry from the discovery / listing endpoints."""

    id: str
    name: Optional[str] = None
    intent_types: list[str] = field(default_factory=list)
    pricing: Optional[Pricing] = None
    features: list[str] = field(default_factory=list)
    endpoint: Optional[str] = None
    source: Optional[str] = None
    resource_id: Optional[str] = None
    server_id: Optional[str] = None
    description: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Provider":
        return cls(
            id=data.get("id", ""),
            name=data.get("name"),
            intent_types=data.get("intent_types", []),
            pricing=Pricing.from_dict(data.get("pricing")),
            features=data.get("features", []),
            endpoint=data.get("endpoint"),
            source=data.get("source"),
            resource_id=data.get("resource_id"),
            server_id=data.get("server_id"),
            description=data.get("description"),
            raw=data,
        )
