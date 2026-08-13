"""V6.1 Live Intelligence Schemas — Data structures for real-time information intake.

Raw Event → SourceRouter → NormalizedEvent → DuplicateDetector →
FreshnessMonitor → IngestionPipeline → Evidence Graph
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

# ── Source Taxonomy ────────────────────────────────────────────────────────────


class SourceType(str, Enum):
    """All information sources the agent monitors."""

    # Wire services
    REUTERS = "reuters"
    BLOOMBERG = "bloomberg"
    # Central banks
    FED_SPEECH = "fed_speech"
    FOMC_MINUTES = "fomc_minutes"
    FOMC_STATEMENT = "fomc_statement"
    ECB_SPEECH = "ecb_speech"
    ECB_MINUTES = "ecb_minutes"
    BOJ_SPEECH = "boj_speech"
    BOJ_MINUTES = "boj_minutes"
    PBOC = "pboc"
    # Government agencies
    TREASURY = "treasury"
    BLS = "bls"  # Bureau of Labor Statistics
    BEA = "bea"  # Bureau of Economic Analysis
    SEC_FILING = "sec_filing"
    # Market data
    ETF_FLOW = "etf_flow"
    CME_FEDWATCH = "cme_fedwatch"
    INSTITUTIONAL_13F = "institutional_13f"
    # International
    IMF = "imf"
    BIS = "bis"
    WORLD_BANK = "world_bank"
    OECD = "oecd"
    # Alternative
    SOCIAL_SENTIMENT = "social_sentiment"
    SATELLITE = "satellite"
    UNKNOWN = "unknown"


class EventImportance(str, Enum):
    """Calibrated importance for macro research."""

    CRITICAL = "critical"  # Regime-changing (e.g., Fed pivot, NFP shock, war)
    HIGH = "high"  # Significant for positioning
    MEDIUM = "medium"  # Adds to the picture
    LOW = "low"  # Background noise
    NEGLIGIBLE = "negligible"  # Not worth researcher time


class IngestionStatus(str, Enum):
    """Status of a single ingestion attempt."""

    SUCCESS = "success"
    FAILED = "failed"
    DUPLICATE = "duplicate"
    STALE = "stale"
    SKIPPED = "skipped"


# ── Core Data Structures ───────────────────────────────────────────────────────


@dataclass
class RawEvent:
    """Raw event as it arrives from a source, before normalization.

    This is source-specific — each source has its own format.
    The SourceRouter's job is to convert this into a NormalizedEvent.
    """

    raw_id: str = field(default_factory=lambda: uuid4().hex[:12])
    source: SourceType = SourceType.UNKNOWN
    source_name: str = ""  # e.g., "Reuters Terminal", "Fed Website"

    # Raw content
    headline: str = ""
    content: str = ""  # Full text or summary
    url: str = ""
    raw_data: dict = field(default_factory=dict)  # Source-specific payload

    # Metadata
    received_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    published_at: str = ""  # When the source published it
    language: str = "en"
    country: str = ""

    # Routing hints
    asset_class: str = ""  # fx, equity, fixed_income, commodity
    tickers: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)

    # Quality
    source_reliability: float = 0.5  # 0–1: how reliable is this source?
    is_breaking: bool = False
    priority: int = 0  # Higher = process first

    def to_dict(self) -> dict:
        return {
            "raw_id": self.raw_id,
            "source": (
                self.source.value if isinstance(self.source, SourceType) else str(self.source)
            ),
            "source_name": self.source_name,
            "headline": self.headline,
            "url": self.url,
            "received_at": self.received_at,
            "published_at": self.published_at,
            "country": self.country,
            "asset_class": self.asset_class,
            "topics": self.topics,
            "is_breaking": self.is_breaking,
            "priority": self.priority,
        }


@dataclass
class NormalizedEvent:
    """Canonical event — all sources converge here.

    After SourceRouter normalizes a RawEvent, it becomes a NormalizedEvent.
    This is the single format that feeds the downstream pipeline.
    """

    event_id: str = field(default_factory=lambda: uuid4().hex[:12])

    # Link to raw
    raw_ids: list[str] = field(default_factory=list)  # Can merge multiple raws
    sources: list[SourceType] = field(default_factory=list)

    # Canonical content
    title: str = ""
    summary: str = ""  # 2–3 sentences
    full_text: str = ""

    # Classification
    category: str = ""  # monetary_policy, economic_data, etc.
    importance: EventImportance = EventImportance.MEDIUM
    confidence: float = 0.5  # How confident in classification?

    # Entities
    countries: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)  # People, orgs
    asset_classes: list[str] = field(default_factory=list)

    # Impact assessment
    impact_direction: str = "neutral"  # bullish, bearish, neutral
    impact_magnitude: float = 0.0  # -1 to +1
    affected_beliefs: list[str] = field(default_factory=list)

    # Key numbers extracted
    key_numbers: dict = field(default_factory=dict)
    surprise: float | None = None  # vs consensus

    # Temporal
    occurred_at: str = ""
    ingested_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Pipeline tracking
    is_duplicate: bool = False
    is_fresh: bool = True
    freshness_score: float = 1.0  # 0–1: decays over time
    has_evidence: bool = False  # Has been fed to evidence graph

    # Why this matters (V6.2 — filled by EventReasoner)
    importance_rationale: str = ""
    narrative_link: str = ""
    belief_link: str = ""
    unknowns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "summary": self.summary,
            "category": self.category,
            "importance": (
                self.importance.value
                if isinstance(self.importance, EventImportance)
                else str(self.importance)
            ),
            "countries": self.countries,
            "impact_direction": self.impact_direction,
            "impact_magnitude": self.impact_magnitude,
            "key_numbers": self.key_numbers,
            "surprise": self.surprise,
            "occurred_at": self.occurred_at,
            "ingested_at": self.ingested_at,
            "is_duplicate": self.is_duplicate,
            "freshness_score": self.freshness_score,
        }

    @property
    def is_critical(self) -> bool:
        return self.importance == EventImportance.CRITICAL

    @property
    def needs_immediate_attention(self) -> bool:
        return self.importance in (EventImportance.CRITICAL, EventImportance.HIGH)


@dataclass
class IngestionResult:
    """Result of a single ingestion pipeline run."""

    pipeline_id: str = field(default_factory=lambda: uuid4().hex[:8])
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str = ""

    # Counts
    raw_events_ingested: int = 0
    normalized_events: int = 0
    duplicates_detected: int = 0
    stale_events_dropped: int = 0
    events_to_evidence_graph: int = 0

    # Events
    events: list[NormalizedEvent] = field(default_factory=list)
    critical_events: list[NormalizedEvent] = field(default_factory=list)

    # Status
    status: IngestionStatus = IngestionStatus.SUCCESS
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Timing
    duration_ms: float = 0.0

    @property
    def has_critical(self) -> bool:
        return len(self.critical_events) > 0

    def summary(self) -> str:
        return (
            f"Ingestion: {self.raw_events_ingested} raw → "
            f"{self.normalized_events} normalized, "
            f"{self.duplicates_detected} dupes, "
            f"{self.stale_events_dropped} stale, "
            f"{self.events_to_evidence_graph} → evidence graph "
            f"({self.duration_ms:.0f}ms)"
        )


@dataclass
class PipelineStatus:
    """Overall pipeline health and metrics."""

    is_running: bool = False
    is_healthy: bool = True
    last_run: str = ""
    last_success: str = ""

    total_events_processed: int = 0
    events_last_24h: int = 0
    critical_events_last_24h: int = 0

    sources_active: int = 0
    sources_error: int = 0
    source_statuses: dict = field(default_factory=dict)

    avg_latency_ms: float = 0.0
    error_rate: float = 0.0

    uptime_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "is_running": self.is_running,
            "is_healthy": self.is_healthy,
            "last_run": self.last_run,
            "total_events_processed": self.total_events_processed,
            "events_last_24h": self.events_last_24h,
            "critical_events_last_24h": self.critical_events_last_24h,
            "sources_active": self.sources_active,
            "sources_error": self.sources_error,
            "error_rate": self.error_rate,
        }
