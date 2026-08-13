"""Temporary Event Layer — separates transient from permanent knowledge (Milestone C, Q2).

Not all observations should become principles. Single events, geopolitical
shocks, policy regime changes, and one-time market structure events belong
in the Temporary Event Layer — they provide context but never become
permanent Research Principles.

Architecture (Q2): The boundary between Temporary and Permanent knowledge
is enforced at the schema level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

from src.schemas.transmission_v3_1 import ResearchFinding
from src.shared.logging import get_logger

logger = get_logger(__name__)


class EventCategory(str, Enum):
    """Categories of temporary/singular events."""

    PERSON_SPECIFIC = "person_specific"  # E.g., Powell speech, Trump tweet
    GEOPOLITICAL = "geopolitical"  # E.g., Russia-Ukraine, trade war
    POLICY_REGIME = "policy_regime"  # E.g., Fed regime change
    MARKET_STRUCTURE = "market_structure"  # E.g., circuit breaker, liquidity crisis
    ELECTION = "election"  # Election-specific effects
    SINGLE_OBSERVATION = "single_observation"  # Isolated, not yet pattern
    EXOGENOUS_SHOCK = "exogenous_shock"  # Natural disaster, pandemic


@dataclass
class TemporaryEvent:
    """A transient, non-generalizable macro event.

    Stored separately from permanent principles. Provides context
    for understanding anomalous observations without polluting
    the principle layer.
    """

    event_id: str = ""
    category: EventCategory = EventCategory.SINGLE_OBSERVATION
    name: str = ""
    description: str = ""
    context_key: str = ""
    finding_ids: list[str] = field(default_factory=list)
    regime_snapshot: dict = field(default_factory=dict)

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None  # Auto-expire after some time
    archived: bool = False
    archived_at: datetime | None = None

    def is_active(self) -> bool:
        if self.archived:
            return False
        if self.expires_at and datetime.now(UTC) > self.expires_at:
            return False
        return True

    def __repr__(self) -> str:
        return f"<TemporaryEvent [{self.category.value}] {self.name[:40]}>"


class TemporaryEventLayer:
    """Manages transient, non-generalizable macro events.

    Architecture Q2: Defines what the agent can NEVER encode as permanent knowledge.
    Events in this layer provide context but do not become Principles.

    Excluded categories:
        - Person-specific events (non-recurring)
        - Geopolitical singularities (no recurring pattern)
        - Policy regime changes (one-time structural shifts)
        - Market structure events (tail events)
        - Election/political events (idiosyncratic)
        - Single-cycle observations (statistically insignificant)
    """

    DEFAULT_TTL_DAYS = 365  # Events auto-expire after 1 year

    def __init__(self) -> None:
        self._events: dict[str, TemporaryEvent] = {}
        self._archived: dict[str, TemporaryEvent] = {}

    def register_event(
        self,
        name: str,
        description: str,
        category: EventCategory,
        finding_ids: list[str] | None = None,
        context_key: str = "",
        ttl_days: int | None = None,
    ) -> TemporaryEvent:
        """Register a new temporary event."""
        event_id = f"te-{len(self._events) + len(self._archived) + 1:04d}"
        ttl = ttl_days or self.DEFAULT_TTL_DAYS

        event = TemporaryEvent(
            event_id=event_id,
            category=category,
            name=name,
            description=description,
            context_key=context_key,
            finding_ids=finding_ids or [],
            expires_at=datetime.now(UTC) + timedelta(days=ttl),
        )
        self._events[event_id] = event
        logger.info("Registered temporary event: %s [%s]", name, category.value)
        return event

    def register_from_finding(
        self, finding: ResearchFinding, category: EventCategory
    ) -> TemporaryEvent | None:
        """Register a temporary event from a single research finding."""
        if self._is_potentially_permanent(finding):
            return None  # Let it flow to Principle admission

        return self.register_event(
            name=finding.title or f"Event from {finding.finding_id}",
            description=finding.description or "",
            category=category,
            finding_ids=[finding.finding_id],
            context_key=finding.context_key,
        )

    def _is_potentially_permanent(self, finding: ResearchFinding) -> bool:
        """Check if a finding could be a permanent pattern.

        Returns False for findings that should go to Temporary Layer.
        """
        # Single observations with low confidence → temporary
        if finding.confidence and finding.confidence.value == "preliminary":
            evidence = finding.evidence or {}
            if evidence.get("observations", 0) < 5:
                return False

        # Isolated events without structural pattern → temporary
        if finding.category in ("regime_similarity",):
            # These are reference data, not causal patterns
            return False

        return True

    def get_active_events(self) -> list[TemporaryEvent]:
        """Get all active (non-expired, non-archived) events."""
        now = datetime.now(UTC)
        return [
            e
            for e in self._events.values()
            if not e.archived and (e.expires_at is None or now <= e.expires_at)
        ]

    def get_by_category(self, category: EventCategory) -> list[TemporaryEvent]:
        return [e for e in self._events.values() if e.category == category]

    def get_context(self, context_key: str) -> list[TemporaryEvent]:
        """Get all events relevant to a specific context."""
        return [e for e in self.get_active_events() if e.context_key == context_key]

    def archive_expired(self) -> int:
        """Archive all expired events. Returns count of archived events."""
        now = datetime.now(UTC)
        to_archive = []
        for eid, event in self._events.items():
            if event.expires_at and now > event.expires_at:
                to_archive.append(eid)

        for eid in to_archive:
            event = self._events.pop(eid)
            event.archived = True
            event.archived_at = now
            self._archived[eid] = event

        if to_archive:
            logger.info("Archived %d expired temporary events", len(to_archive))
        return len(to_archive)

    def get_finding_context(self, finding_id: str) -> list[TemporaryEvent]:
        """Get temporary context for a specific finding."""
        return [e for e in self._events.values() if finding_id in (e.finding_ids or [])]

    @property
    def active_count(self) -> int:
        return len(self.get_active_events())

    @property
    def total_events(self) -> int:
        return len(self._events) + len(self._archived)

    def summary(self) -> str:
        categories = {}
        for e in self._events.values():
            categories[e.category.value] = categories.get(e.category.value, 0) + 1
        return (
            f"TemporaryEventLayer: {self.active_count} active events "
            f"(categories: {categories}), {len(self._archived)} archived"
        )
