"""V6.5 Research Journal — Persistent research logs.

Every day, the agent automatically saves:
    - Thinking Log: What did we think about?
    - Decision Log: What decisions did we make and why?
    - Evidence Log: What new evidence did we incorporate?
    - Prediction Log: What did we predict?
    - Reflection Log: What did we learn?

This creates a complete audit trail of the agent's research process.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4


class LogType(str, Enum):
    THINKING = "thinking"
    DECISION = "decision"
    EVIDENCE = "evidence"
    PREDICTION = "prediction"
    REFLECTION = "reflection"


@dataclass
class JournalEntry:
    """A single entry in any research journal."""

    entry_id: str = field(default_factory=lambda: uuid4().hex[:8])
    log_type: LogType = LogType.THINKING
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Content
    title: str = ""
    content: str = ""
    tags: list[str] = field(default_factory=list)

    # Context
    session_id: str = ""
    topic: str = ""

    # For decision log
    decision: str = ""
    rationale: str = ""
    alternatives_considered: list[str] = field(default_factory=list)

    # For evidence log
    evidence_items: list[dict] = field(default_factory=list)
    source: str = ""
    impact_on_beliefs: dict = field(default_factory=dict)

    # For prediction log
    prediction: str = ""
    probability: float | None = None
    time_horizon: str = ""
    invalidation_condition: str = ""

    # For reflection log
    reflection: str = ""
    lessons_learned: list[str] = field(default_factory=list)
    mistakes_identified: list[str] = field(default_factory=list)
    improvements_needed: list[str] = field(default_factory=list)

    # Meta
    importance: str = "medium"  # critical, high, medium, low
    is_milestone: bool = False

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "log_type": self.log_type.value,
            "date": self.date,
            "timestamp": self.timestamp,
            "title": self.title,
            "importance": self.importance,
            "is_milestone": self.is_milestone,
            "content_length": len(self.content),
        }


class ResearchJournal:
    """Complete research journal system with 5 log types.

    The journal is the agent's memory of its own thinking process.
    It's not just a log — it's the research record that enables learning.
    """

    def __init__(self):
        self.entries: dict[str, JournalEntry] = {}

        # Indices for fast lookup
        self._by_date: dict[str, list[str]] = {}
        self._by_type: dict[LogType, list[str]] = {}
        self._by_topic: dict[str, list[str]] = {}
        self._by_session: dict[str, list[str]] = {}

        # Stats
        self._entry_counts: dict[LogType, int] = {lt: 0 for lt in LogType}

    # ── Log Writers ──────────────────────────────────────────────────────

    def log_thinking(
        self,
        title: str,
        content: str,
        topic: str = "",
        session_id: str = "",
        tags: list[str] | None = None,
    ) -> JournalEntry:
        """Log a thinking process entry."""
        entry = JournalEntry(
            log_type=LogType.THINKING,
            title=title,
            content=content,
            topic=topic,
            session_id=session_id,
            tags=tags or [],
        )
        self._store(entry)
        return entry

    def log_decision(
        self,
        decision: str,
        rationale: str,
        alternatives: list[str] | None = None,
        topic: str = "",
        session_id: str = "",
        importance: str = "medium",
    ) -> JournalEntry:
        """Log a research decision with rationale."""
        entry = JournalEntry(
            log_type=LogType.DECISION,
            title=f"Decision: {decision[:80]}",
            content=f"## Decision\n{decision}\n\n## Rationale\n{rationale}",
            decision=decision,
            rationale=rationale,
            alternatives_considered=alternatives or [],
            topic=topic,
            session_id=session_id,
            importance=importance,
            is_milestone=importance == "critical",
        )
        self._store(entry)
        return entry

    def log_evidence(
        self,
        title: str,
        evidence_items: list[dict],
        source: str = "",
        impact: dict | None = None,
        topic: str = "",
        session_id: str = "",
    ) -> JournalEntry:
        """Log new evidence incorporated into research."""
        content_parts = [f"## New Evidence: {title}", f"Source: {source}"]
        for i, item in enumerate(evidence_items):
            content_parts.append(f"### Evidence {i+1}")
            content_parts.append(str(item))

        entry = JournalEntry(
            log_type=LogType.EVIDENCE,
            title=title,
            content="\n".join(content_parts),
            evidence_items=evidence_items,
            source=source,
            impact_on_beliefs=impact or {},
            topic=topic,
            session_id=session_id,
        )
        self._store(entry)
        return entry

    def log_prediction(
        self,
        prediction: str,
        probability: float = 0.5,
        time_horizon: str = "",
        invalidation: str = "",
        topic: str = "",
        session_id: str = "",
    ) -> JournalEntry:
        """Log a prediction for future calibration."""
        content = (
            f"## Prediction\n{prediction}\n\n"
            f"## Probability: {probability:.0%}\n\n"
            f"## Time Horizon: {time_horizon}\n\n"
            f"## Invalidation Condition\n{invalidation}"
        )

        entry = JournalEntry(
            log_type=LogType.PREDICTION,
            title=f"Prediction: {prediction[:80]}",
            content=content,
            prediction=prediction,
            probability=probability,
            time_horizon=time_horizon,
            invalidation_condition=invalidation,
            topic=topic,
            session_id=session_id,
        )
        self._store(entry)
        return entry

    def log_reflection(
        self,
        title: str,
        reflection: str,
        lessons: list[str] | None = None,
        mistakes: list[str] | None = None,
        improvements: list[str] | None = None,
        topic: str = "",
        session_id: str = "",
    ) -> JournalEntry:
        """Log a reflection on research process or outcomes."""
        entry = JournalEntry(
            log_type=LogType.REFLECTION,
            title=title,
            content=reflection,
            reflection=reflection,
            lessons_learned=lessons or [],
            mistakes_identified=mistakes or [],
            improvements_needed=improvements or [],
            topic=topic,
            session_id=session_id,
        )
        self._store(entry)
        return entry

    # ── Read APIs ────────────────────────────────────────────────────────

    def get_entries_by_date(self, date: str) -> list[JournalEntry]:
        """Get all journal entries for a specific date."""
        ids = self._by_date.get(date, [])
        return [self.entries[eid] for eid in ids if eid in self.entries]

    def get_entries_by_type(self, log_type: LogType) -> list[JournalEntry]:
        """Get all entries of a specific type."""
        ids = self._by_type.get(log_type, [])
        return [self.entries[eid] for eid in ids if eid in self.entries]

    def get_entries_by_topic(self, topic: str) -> list[JournalEntry]:
        """Get all entries for a topic."""
        ids = self._by_topic.get(topic, [])
        return [self.entries[eid] for eid in ids if eid in self.entries]

    def get_session_journal(self, session_id: str) -> list[JournalEntry]:
        """Get all entries for a research session."""
        ids = self._by_session.get(session_id, [])
        return [self.entries[eid] for eid in ids if eid in self.entries]

    def get_today_entries(self) -> list[JournalEntry]:
        """Get today's journal entries."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.get_entries_by_date(today)

    def get_predictions(self, limit: int = 50) -> list[JournalEntry]:
        """Get recent predictions for calibration."""
        preds = self.get_entries_by_type(LogType.PREDICTION)
        return sorted(preds, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_decisions(self, limit: int = 50) -> list[JournalEntry]:
        """Get recent decisions."""
        decs = self.get_entries_by_type(LogType.DECISION)
        return sorted(decs, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_reflections(self, limit: int = 50) -> list[JournalEntry]:
        """Get recent reflections."""
        refs = self.get_entries_by_type(LogType.REFLECTION)
        return sorted(refs, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_milestones(self) -> list[JournalEntry]:
        """Get all milestone entries."""
        return [e for e in self.entries.values() if e.is_milestone]

    # ── Journal Summary ──────────────────────────────────────────────────

    def get_daily_summary(self, date: str | None = None) -> dict:
        """Get a structured summary of a day's research."""
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        entries = self.get_entries_by_date(target_date)

        by_type: dict[str, list] = {}
        for e in entries:
            key = e.log_type.value
            if key not in by_type:
                by_type[key] = []
            by_type[key].append(
                {
                    "title": e.title,
                    "importance": e.importance,
                    "is_milestone": e.is_milestone,
                }
            )

        return {
            "date": target_date,
            "total_entries": len(entries),
            "by_type": {k: len(v) for k, v in by_type.items()},
            "highlights": by_type,
            "milestones": [e.title for e in entries if e.is_milestone],
            "topics_covered": list(set(e.topic for e in entries if e.topic)),
        }

    def get_weekly_summary(self) -> dict:
        """Get summary for the past 7 days."""
        from datetime import timedelta

        today = datetime.now()
        summaries = {}
        for i in range(7):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            entries = self.get_entries_by_date(date)
            summaries[date] = len(entries)

        return {
            "period": f"{(today - timedelta(days=6)).strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}",
            "total_entries": sum(summaries.values()),
            "daily_breakdown": summaries,
            "total_predictions": sum(
                len([e for e in self.get_entries_by_date(d) if e.log_type == LogType.PREDICTION])
                for d in summaries
            ),
            "total_decisions": sum(
                len([e for e in self.get_entries_by_date(d) if e.log_type == LogType.DECISION])
                for d in summaries
            ),
        }

    # ── Stats ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "total_entries": len(self.entries),
            "by_type": dict(self._entry_counts),
            "total_dates": len(self._by_date),
            "total_topics": len(self._by_topic),
            "total_sessions": len(self._by_session),
            # Content stats
            "total_predictions": self._entry_counts.get(LogType.PREDICTION, 0),
            "total_decisions": self._entry_counts.get(LogType.DECISION, 0),
            "total_reflections": self._entry_counts.get(LogType.REFLECTION, 0),
            "milestone_count": sum(1 for e in self.entries.values() if e.is_milestone),
        }

    def search(self, query: str) -> list[JournalEntry]:
        """Simple search across all journal entries."""
        q = query.lower()
        results = []
        for entry in self.entries.values():
            if (
                q in entry.title.lower()
                or q in entry.content.lower()
                or q in " ".join(entry.tags).lower()
            ):
                results.append(entry)
        return sorted(results, key=lambda e: e.timestamp, reverse=True)[:50]

    # ── Internal ─────────────────────────────────────────────────────────

    def _store(self, entry: JournalEntry):
        """Store entry and update all indices."""
        self.entries[entry.entry_id] = entry

        # Date index
        if entry.date not in self._by_date:
            self._by_date[entry.date] = []
        self._by_date[entry.date].append(entry.entry_id)

        # Type index
        if entry.log_type not in self._by_type:
            self._by_type[entry.log_type] = []
        self._by_type[entry.log_type].append(entry.entry_id)

        # Topic index
        if entry.topic:
            if entry.topic not in self._by_topic:
                self._by_topic[entry.topic] = []
            self._by_topic[entry.topic].append(entry.entry_id)

        # Session index
        if entry.session_id:
            if entry.session_id not in self._by_session:
                self._by_session[entry.session_id] = []
            self._by_session[entry.session_id].append(entry.entry_id)

        # Counts
        self._entry_counts[entry.log_type] = self._entry_counts.get(entry.log_type, 0) + 1
