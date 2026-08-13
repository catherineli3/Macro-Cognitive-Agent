"""V4 News Schemas — Data structures for news intelligence.

Design: Each news item becomes a ResearchEvent that can feed into
the Evidence Graph and influence beliefs/predictions/memos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class NewsSourceType(str, Enum):
    """Category of news source."""

    WIRE_SERVICE = "wire_service"  # Reuters, Bloomberg
    CENTRAL_BANK = "central_bank"  # FOMC, ECB, BOJ, PBOC
    CENTRAL_BANK_SPEECH = "cb_speech"  # Fed speeches, ECB pressers
    GOVERNMENT_AGENCY = "government"  # BLS, BEA, Treasury
    INTERNATIONAL_ORG = "international"  # IMF, BIS, OECD
    MARKET_DATA = "market_data"  # Economic data releases
    UNKNOWN = "unknown"


class EventCategory(str, Enum):
    """Type of economic/financial event."""

    MONETARY_POLICY = "monetary_policy"
    FISCAL_POLICY = "fiscal_policy"
    ECONOMIC_DATA = "economic_data"
    GEOPOLITICAL = "geopolitical"
    MARKET_EVENT = "market_event"
    CORPORATE_EVENT = "corporate_event"
    REGULATORY = "regulatory"
    SPEECH_COMMENTARY = "speech_commentary"
    OTHER = "other"


class ImpactDirection(str, Enum):
    """Direction of impact on risk assets / beliefs."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNCERTAIN = "uncertain"


class ImpactSeverity(str, Enum):
    """Severity of market/belief impact."""

    CRITICAL = "critical"  # Market-moving, belief-changing
    HIGH = "high"  # Significant for positioning
    MEDIUM = "medium"  # Notable, additive to picture
    LOW = "low"  # Background noise
    NEGLIGIBLE = "negligible"  # Ignorable


@dataclass
class NewsArticle:
    """Raw news article before processing."""

    article_id: str = ""
    headline: str = ""
    content: str = ""  # Full text or summary
    url: str = ""
    source: NewsSourceType = NewsSourceType.UNKNOWN
    source_name: str = ""  # e.g., "Reuters", "FOMC Statement"
    published_at: str = ""
    language: str = "en"

    # Metadata
    country: str = ""  # Primary country
    tickers: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    author: str = ""

    def to_dict(self) -> dict:
        return {
            "article_id": self.article_id,
            "headline": self.headline,
            "source": (
                self.source.value if isinstance(self.source, NewsSourceType) else str(self.source)
            ),
            "source_name": self.source_name,
            "published_at": self.published_at,
            "country": self.country,
            "topics": self.topics,
        }


@dataclass
class ResearchEvent:
    """Canonical research event — deduplicated, classified, impact-assessed.

    This is the core unit that feeds into the Evidence Graph.
    Every piece of news that matters for macro research becomes one of these.
    """

    event_id: str = ""
    title: str = ""  # Canonical event title
    description: str = ""  # 2-3 sentence summary
    category: EventCategory = EventCategory.OTHER

    # Source
    source_type: NewsSourceType = NewsSourceType.UNKNOWN
    sources: list[dict] = field(default_factory=list)  # All source articles merged into this event
    news_articles: list[NewsArticle] = field(default_factory=list)

    # Entities
    entities: list[str] = field(default_factory=list)  # Organizations, people, countries mentioned
    country: str = ""
    countries_affected: list[str] = field(default_factory=list)

    # Impact assessment
    market_impact: ImpactDirection = ImpactDirection.UNCERTAIN
    impact_severity: ImpactSeverity = ImpactSeverity.MEDIUM
    impact_confidence: float = 0.5  # How confident are we in the impact assessment?

    # Belief linkage
    belief_impact: dict = field(default_factory=dict)
    # {belief_id: {direction: "support"|"contradict", strength: float}}

    # Temporal
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_date: str = ""  # When the event actually occurred

    # Meta
    is_breaking: bool = False
    is_important: bool = False  # Does this matter for macro research?
    is_duplicate: bool = False  # Was this deduplicated from other articles?

    # Key numbers
    key_numbers: dict = field(default_factory=dict)
    # e.g., {"cpi_yoy": 3.2, "core_cpi_mom": 0.2}

    # Market expectation vs reality
    consensus_expectation: float | None = None
    actual_value: float | None = None
    surprise: float | None = None  # actual - expected

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "description": self.description,
            "category": (
                self.category.value
                if isinstance(self.category, EventCategory)
                else str(self.category)
            ),
            "source_type": (
                self.source_type.value
                if isinstance(self.source_type, NewsSourceType)
                else str(self.source_type)
            ),
            "entities": self.entities,
            "country": self.country,
            "countries_affected": self.countries_affected,
            "market_impact": (
                self.market_impact.value
                if isinstance(self.market_impact, ImpactDirection)
                else str(self.market_impact)
            ),
            "impact_severity": (
                self.impact_severity.value
                if isinstance(self.impact_severity, ImpactSeverity)
                else str(self.impact_severity)
            ),
            "impact_confidence": self.impact_confidence,
            "belief_impact": self.belief_impact,
            "timestamp": self.timestamp,
            "event_date": self.event_date,
            "is_important": self.is_important,
            "key_numbers": self.key_numbers,
            "surprise": self.surprise,
        }

    def is_evidence_for_belief(self, belief_id: str) -> tuple[bool, str]:
        """Check if this event provides evidence for/against a belief."""
        bi = self.belief_impact.get(belief_id, {})
        if not bi:
            return False, "neutral"
        return True, bi.get("direction", "neutral")


@dataclass
class PolicySignal:
    """Extracted policy signal from central bank communication.

    Goals:
    - Is the CB hawkish, dovish, or neutral?
    - Is the stance changing?
    - What data is the CB watching?
    - What is the reaction function?
    """

    signal_id: str = ""
    central_bank: str = ""  # Fed, ECB, BOJ, PBOC, BOE, etc.
    event_id: str = ""  # Link to source ResearchEvent

    # Stance
    current_stance: str = ""  # hawkish, dovish, neutral, data-dependent
    stance_change: str = ""  # tightening, easing, unchanged, pivoting
    stance_confidence: float = 0.5

    # Forward guidance
    forward_guidance: str = ""
    rate_path_signal: str = ""  # higher, lower, steady, uncertain

    # Key phrases
    key_phrases: list[str] = field(default_factory=list)
    # e.g., ["restrictive for some time", "data dependent", "patient"]

    # Data dependency
    watched_indicators: list[str] = field(default_factory=list)
    # What the CB said they're watching

    # Market interpretation
    hawkish_dovish_score: float = 0.0  # -1 (very dovish) to +1 (very hawkish)
    market_reaction: str = ""  # How markets initially reacted

    # Source
    source_text: str = ""  # Key excerpt from the communication
    source_url: str = ""

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "central_bank": self.central_bank,
            "current_stance": self.current_stance,
            "stance_change": self.stance_change,
            "forward_guidance": self.forward_guidance,
            "rate_path_signal": self.rate_path_signal,
            "key_phrases": self.key_phrases,
            "hawkish_dovish_score": self.hawkish_dovish_score,
            "market_reaction": self.market_reaction,
        }


@dataclass
class MarketExpectation:
    """Market-implied vs actual data comparison.

    Key question: "Did the data beat, miss, or match expectations?"
    This determines whether a data release is market-moving.
    """

    expectation_id: str = ""
    event_id: str = ""  # Link to ResearchEvent

    # What was expected
    indicator: str = ""  # e.g., "CPI YoY", "NFP", "GDP QoQ"
    consensus_forecast: float | None = None
    prior_value: float | None = None
    forecast_range_low: float | None = None
    forecast_range_high: float | None = None

    # What actually happened
    actual_value: float | None = None
    revision: float | None = None  # Revision to prior

    # Surprise
    surprise: float | None = None  # actual - consensus
    surprise_std: float | None = None  # Surprise in standard deviations
    is_significant_surprise: bool = False  # > 1 standard deviation?

    # Impact
    surprise_direction: ImpactDirection = ImpactDirection.NEUTRAL
    market_reaction: str = ""  # Initial market response

    # Implication
    implication: str = ""  # What this means in 1-2 sentences

    def to_dict(self) -> dict:
        return {
            "expectation_id": self.expectation_id,
            "indicator": self.indicator,
            "consensus_forecast": self.consensus_forecast,
            "actual_value": self.actual_value,
            "surprise": self.surprise,
            "surprise_std": self.surprise_std,
            "is_significant_surprise": self.is_significant_surprise,
            "surprise_direction": (
                self.surprise_direction.value
                if isinstance(self.surprise_direction, ImpactDirection)
                else str(self.surprise_direction)
            ),
            "implication": self.implication,
        }
