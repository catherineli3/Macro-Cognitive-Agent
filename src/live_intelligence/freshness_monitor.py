"""V6.1 Freshness Monitor — Track data freshness and staleness.

Every event has a freshness_score that decays over time.
Critical data (CPI, NFP, FOMC) decays faster as the next release approaches.
Background data (IMF reports) decays slowly.

The monitor tells the agent:
- What data is fresh enough to use?
- What data needs updating?
- When will current data become stale?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from src.live_intelligence.schemas import EventImportance, NormalizedEvent


@dataclass
class FreshnessReport:
    """Report on data freshness across all sources."""

    total_events: int = 0
    fresh_count: int = 0
    stale_count: int = 0
    expiring_count: int = 0

    # By source
    source_freshness: dict[str, float] = field(default_factory=dict)

    # Specific stale items
    stale_items: list[dict] = field(default_factory=list)
    expiring_items: list[dict] = field(default_factory=list)

    # Overall
    overall_freshness: float = 0.0  # 0–1

    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def is_healthy(self) -> bool:
        return self.overall_freshness >= 0.5

    def summary(self) -> str:
        return (
            f"Freshness: {self.overall_freshness:.1%} — "
            f"{self.fresh_count} fresh, {self.stale_count} stale, "
            f"{self.expiring_count} expiring"
        )


class FreshnessMonitor:
    """Monitor information freshness across all event sources.

    Each event type has a different decay curve:
    - Economic data: fast decay (next month's release replaces this month's)
    - FOMC decisions: very fast decay (next meeting replaces current stance)
    - IMF reports: slow decay (relevant for months)
    - Market pricing: continuous (always fresh, no decay)
    """

    # Default TTL (time-to-live) in hours per importance level
    DEFAULT_TTL_HOURS = {
        EventImportance.CRITICAL: 4,  # Must be very fresh
        EventImportance.HIGH: 12,
        EventImportance.MEDIUM: 48,
        EventImportance.LOW: 168,  # A week
        EventImportance.NEGLIGIBLE: 720,  # A month
    }

    # Category-specific overrides (hours)
    CATEGORY_TTL_OVERRIDE = {
        "monetary_policy": 6,  # Policy can change fast
        "economic_data": 24,  # Data is stale by next cycle
        "fiscal_policy": 72,
        "market_event": 4,  # Market events are ephemeral
        "speech_commentary": 12,
        "geopolitical": 24,
        "corporate_event": 48,
        "regulatory": 168,
    }

    def __init__(
        self,
        stale_threshold: float = 0.3,
        expiring_threshold: float = 0.5,
        max_events_tracked: int = 10000,
    ):

        self.stale_threshold = stale_threshold
        self.expiring_threshold = expiring_threshold
        self.max_events = max_events_tracked

        # Event freshness tracking
        self._events: dict[str, NormalizedEvent] = {}
        self._freshness_scores: dict[str, float] = {}
        self._ingestion_times: dict[str, str] = {}

        # Stats
        self.total_checked = 0
        self.total_stale = 0

    def register(self, event: NormalizedEvent):
        """Register a new event for freshness tracking."""
        self._events[event.event_id] = event
        self._freshness_scores[event.event_id] = 1.0
        self._ingestion_times[event.event_id] = event.ingested_at

        # Update event's freshness
        event.freshness_score = 1.0
        event.is_fresh = True

        # Prune old events
        if len(self._events) > self.max_events:
            self._prune()

    def register_batch(self, events: list[NormalizedEvent]):
        """Register multiple events."""
        for event in events:
            self.register(event)

    def check_freshness(self, event_id: str, reference_time: datetime | None = None) -> float:
        """Check current freshness score for an event (0–1)."""
        if event_id not in self._events:
            return 0.0

        event = self._events[event_id]
        now = reference_time or datetime.now(UTC)

        try:
            ingested = datetime.fromisoformat(event.ingested_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            ingested = now

        # Get TTL for this event
        ttl_hours = self._get_ttl(event)

        # Linear decay
        hours_elapsed = (now - ingested).total_seconds() / 3600
        freshness = max(0.0, 1.0 - hours_elapsed / ttl_hours)

        # Update cache
        self._freshness_scores[event_id] = freshness
        event.freshness_score = freshness
        event.is_fresh = freshness >= self.stale_threshold

        self.total_checked += 1
        if freshness < self.stale_threshold:
            self.total_stale += 1

        return freshness

    def check_all(self) -> FreshnessReport:
        """Check freshness for all tracked events and generate report."""
        report = FreshnessReport(total_events=len(self._events))
        source_scores: dict[str, list[float]] = {}

        for event_id, event in self._events.items():
            score = self.check_freshness(event_id)

            if score < self.stale_threshold:
                report.stale_count += 1
                report.stale_items.append(
                    {
                        "event_id": event_id,
                        "title": event.title,
                        "category": event.category,
                        "freshness": round(score, 3),
                        "ingested": event.ingested_at,
                    }
                )
            elif score < self.expiring_threshold:
                report.expiring_count += 1
                report.expiring_items.append(
                    {
                        "event_id": event_id,
                        "title": event.title,
                        "category": event.category,
                        "freshness": round(score, 3),
                        "ingested": event.ingested_at,
                        "ttl_hours": self._get_ttl(event),
                    }
                )
            else:
                report.fresh_count += 1

            # Track by source
            for src in event.sources:
                src_key = src.value if hasattr(src, "value") else str(src)
                if src_key not in source_scores:
                    source_scores[src_key] = []
                source_scores[src_key].append(score)

        # Per-source average freshness
        for src, scores in source_scores.items():
            report.source_freshness[src] = sum(scores) / len(scores) if scores else 0.0

        # Overall
        if self._events:
            all_scores = list(self._freshness_scores.values())
            report.overall_freshness = sum(all_scores) / len(all_scores)

        return report

    def get_stale_events(self) -> list[NormalizedEvent]:
        """Get list of events that are currently stale."""
        stale = []
        for event_id, event in self._events.items():
            score = self._freshness_scores.get(event_id, 1.0)
            if score < self.stale_threshold:
                stale.append(event)
        return stale

    def get_expiring_events(self, within_hours: int = 6) -> list[NormalizedEvent]:
        """Get events that will become stale within N hours."""
        expiring = []
        now = datetime.now(UTC)

        for event_id, event in self._events.items():
            ttl = self._get_ttl(event)
            _score = self._freshness_scores.get(event_id, 1.0)

            # Estimate when it becomes stale
            try:
                ingested = datetime.fromisoformat(event.ingested_at.replace("Z", "+00:00"))
                stale_at = ingested + timedelta(hours=ttl * (1 - self.stale_threshold))
                hours_until_stale = (stale_at - now).total_seconds() / 3600

                if 0 < hours_until_stale <= within_hours:
                    expiring.append(event)
            except (ValueError, TypeError):
                pass

        return expiring

    def remove_stale(self) -> int:
        """Remove stale events from tracking. Returns count removed."""
        stale_ids = [
            eid for eid, score in self._freshness_scores.items() if score < self.stale_threshold
        ]
        for eid in stale_ids:
            self._events.pop(eid, None)
            self._freshness_scores.pop(eid, None)
            self._ingestion_times.pop(eid, None)
        return len(stale_ids)

    # ── Internal ──────────────────────────────────────────────────────────

    def _get_ttl(self, event: NormalizedEvent) -> float:
        """Get TTL in hours for an event."""
        # Category override first
        if event.category in self.CATEGORY_TTL_OVERRIDE:
            return self.CATEGORY_TTL_OVERRIDE[event.category]

        # Then importance-based
        return self.DEFAULT_TTL_HOURS.get(event.importance, 48)

    def _prune(self):
        """Remove lowest-freshness events to stay under max."""
        if len(self._events) <= self.max_events:
            return

        # Sort by freshness, remove worst
        sorted_events = sorted(self._freshness_scores.items(), key=lambda x: x[1])
        to_remove = len(self._events) - self.max_events

        for event_id, _ in sorted_events[:to_remove]:
            self._events.pop(event_id, None)
            self._freshness_scores.pop(event_id, None)
            self._ingestion_times.pop(event_id, None)

    def get_stats(self) -> dict:
        return {
            "tracked_events": len(self._events),
            "total_checked": self.total_checked,
            "total_stale": self.total_stale,
            "stale_rate": self.total_stale / max(self.total_checked, 1),
            "avg_freshness": (
                sum(self._freshness_scores.values()) / max(len(self._freshness_scores), 1)
            ),
        }

    def reset(self):
        self._events.clear()
        self._freshness_scores.clear()
        self._ingestion_times.clear()
        self.total_checked = 0
        self.total_stale = 0
