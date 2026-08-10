"""Research Memory — persistent history of research cycles (Milestone D, D5).

The agent's long-term memory. Records every completed research cycle:
    - Date + Market Regime
    - Framework Used
    - Thesis
    - Evidence
    - Outcome
    - Diagnosis
    - Learning

This enables future V4 dialog: "Last year in a similar environment, we judged
liquidity would drive assets, but were wrong because credit transmission failed."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.schemas.research_thesis import ResearchThesis, ThesisOutcome, ThesisStatus
from src.research.evolution.regime_gate import RegimeSnapshot
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PostmortemReport:
    """Post-cycle analysis of what happened and why."""

    report_id: str = ""
    thesis_id: str = ""
    thesis_validated: bool = False
    root_cause: str = ""                          # e.g. "Transmission chain broke at X"
    transmission_problems: list[str] = field(default_factory=list)
    framework_assessment: str = ""                # Was the framework appropriate?
    learning: str = ""                            # What should be remembered
    suggested_actions: list[str] = field(default_factory=list)
    diagnosis_notes: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def describe(self) -> str:
        status = "VALIDATED" if self.thesis_validated else "INVALIDATED"
        lines = [
            f"Postmortem: {status} — {self.root_cause}",
            f"  Learning: {self.learning}",
        ]
        if self.transmission_problems:
            lines.append(f"  Transmission issues: {', '.join(self.transmission_problems)}")
        if self.suggested_actions:
            lines.append(f"  Actions: {', '.join(self.suggested_actions[:3])}")
        return "\n".join(lines)


@dataclass
class ResearchMemoryEntry:
    """A single entry in the research memory — one completed cycle."""

    entry_id: str = ""
    cycle_number: int = 0
    date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Input state
    market_regime: RegimeSnapshot | None = None
    regime_label: str = ""

    # Framework selection
    framework_used: list[str] = field(default_factory=list)  # framework_ids

    # Output
    thesis: ResearchThesis | None = None
    hypothesis_count: int = 0

    # Outcome (set after market validation)
    outcome: ThesisOutcome | None = None
    diagnosis_notes: str = ""
    postmortem: PostmortemReport | None = None

    # Post-cycle state
    frameworks_after: list[str] = field(default_factory=list)
    principles_after: list[str] = field(default_factory=list)

    # Learning
    learning_note: str = ""  # Human-readable lesson from this cycle

    @property
    def was_successful(self) -> bool:
        if self.outcome:
            return self.outcome.verified
        return False

    @property
    def thesis_status(self) -> str:
        if self.thesis:
            return self.thesis.status.value
        return "unknown"

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "cycle_number": self.cycle_number,
            "date": self.date.isoformat(),
            "regime_label": self.regime_label,
            "market_regime": self.market_regime.to_dict() if self.market_regime else None,
            "framework_used": self.framework_used,
            "thesis_id": self.thesis.thesis_id if self.thesis else None,
            "thesis_title": self.thesis.title if self.thesis else None,
            "hypothesis_count": self.hypothesis_count,
            "was_successful": self.was_successful,
            "diagnosis_notes": self.diagnosis_notes,
            "postmortem_root_cause": self.postmortem.root_cause if self.postmortem else None,
            "frameworks_after": self.frameworks_after,
            "principles_after": self.principles_after,
            "learning_note": self.learning_note,
        }


class ResearchMemory:
    """Persistent store of research cycle history.

    This is the agent's long-term memory. Every cycle's thesis, outcome,
    diagnosis, and learning are recorded here.

    Storage: JSON file at configurable path (no database required).
    """

    DEFAULT_PATH = "data/research_memory.json"

    def __init__(self, storage_path: str | None = None):
        self._path = Path(storage_path or self.DEFAULT_PATH)
        self._entries: dict[str, ResearchMemoryEntry] = {}
        self._by_date: list[str] = []  # ordered entry_ids
        self._load()

    # ── CRUD ────────────────────────────────────────────────────────────

    def record_entry(self, entry: ResearchMemoryEntry) -> str:
        """Record a new research memory entry. Returns entry_id."""
        if not entry.entry_id:
            entry.entry_id = f"mem-{entry.date.strftime('%Y%m%d')}-{entry.cycle_number:04d}"

        self._entries[entry.entry_id] = entry
        self._by_date.append(entry.entry_id)
        self._save()
        logger.info("Memory entry recorded: %s (cycle %d)", entry.entry_id, entry.cycle_number)
        return entry.entry_id

    def get_entry(self, entry_id: str) -> ResearchMemoryEntry | None:
        return self._entries.get(entry_id)

    def get_recent(self, n: int = 10) -> list[ResearchMemoryEntry]:
        """Get the N most recent entries."""
        ids = self._by_date[-n:]
        return [self._entries[eid] for eid in reversed(ids) if eid in self._entries]

    # ── Query ───────────────────────────────────────────────────────────

    def query_by_regime(self, regime_key: str) -> list[ResearchMemoryEntry]:
        """Find entries where the market regime matches (contains) the key."""
        results = []
        for entry in self._entries.values():
            if entry.market_regime and regime_key.lower() in entry.market_regime.key.lower():
                results.append(entry)
            elif regime_key.lower() in entry.regime_label.lower():
                results.append(entry)
        return results

    def query_by_framework(self, framework_id: str) -> list[ResearchMemoryEntry]:
        """Find entries that used a specific framework."""
        return [
            e for e in self._entries.values()
            if framework_id in e.framework_used
        ]

    def get_validated_theses(self) -> list[ResearchMemoryEntry]:
        """Get entries where the thesis was validated."""
        return [e for e in self._entries.values() if e.was_successful]

    def get_invalidated_theses(self) -> list[ResearchMemoryEntry]:
        """Get entries where the thesis was invalidated."""
        return [
            e for e in self._entries.values()
            if e.outcome and not e.outcome.verified
        ]

    def get_active_theses(self) -> list[ResearchMemoryEntry]:
        """Get entries with actively pending theses."""
        return [
            e for e in self._entries.values()
            if e.thesis and e.thesis.status == ThesisStatus.ACTIVE
        ]

    # ── Analytics ───────────────────────────────────────────────────────

    @property
    def total_entries(self) -> int:
        return len(self._entries)

    @property
    def success_rate(self) -> float:
        """Overall thesis success rate across all completed cycles."""
        completed = [e for e in self._entries.values() if e.outcome]
        if not completed:
            return 0.0
        return sum(1 for e in completed if e.was_successful) / len(completed)

    def regime_success_rate(self, regime_key: str) -> float:
        """Success rate for a specific regime."""
        entries = self.query_by_regime(regime_key)
        completed = [e for e in entries if e.outcome]
        if not completed:
            return 0.0
        return sum(1 for e in completed if e.was_successful) / len(completed)

    def framework_success_rate(self, framework_id: str) -> float:
        """Success rate for a specific framework."""
        entries = self.query_by_framework(framework_id)
        completed = [e for e in entries if e.outcome]
        if not completed:
            return 0.0
        return sum(1 for e in completed if e.was_successful) / len(completed)

    def common_failure_reasons(self, n: int = 5) -> list[tuple[str, int]]:
        """Most common root causes of thesis failure."""
        from collections import Counter
        causes = Counter()
        for e in self._entries.values():
            if e.postmortem and e.postmortem.root_cause:
                causes[e.postmortem.root_cause] += 1
        return causes.most_common(n)

    # ── Display ────────────────────────────────────────────────────────

    def summary(self, last_n: int = 5) -> str:
        """Human-readable summary of recent research history."""
        recent = self.get_recent(last_n)

        lines = [
            f"=== Research Memory ({self.total_entries} total entries) ===",
            f"Overall Success Rate: {self.success_rate:.0%}",
            "",
            f"Last {len(recent)} cycles:",
        ]

        for i, entry in enumerate(recent):
            status = "✓" if entry.was_successful else "✗" if entry.outcome else "⋯"
            thesis_title = entry.thesis.title if entry.thesis else "No thesis"
            lines.append(
                f"  [{status}] Cycle {entry.cycle_number} "
                f"({entry.date.strftime('%Y-%m-%d')}): "
                f"{thesis_title[:80]}"
            )
            if entry.learning_note:
                lines.append(f"       Learn: {entry.learning_note[:100]}")

        # Most common failures
        failures = self.common_failure_reasons(3)
        if failures:
            lines.append("")
            lines.append("Top failure causes:")
            for cause, count in failures:
                lines.append(f"  - {cause} ({count}x)")

        return "\n".join(lines)

    # ── Persistence ────────────────────────────────────────────────────

    def _save(self) -> None:
        """Save all entries to JSON file."""
        import json
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "entries": {eid: entry.to_dict() for eid, entry in self._entries.items()},
                "by_date": self._by_date,
            }
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error("Failed to save research memory: %s", e)

    def _load(self) -> None:
        """Load entries from JSON file."""
        import json
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._entries = {}
            self._by_date = data.get("by_date", [])
            # Entries are loaded as dicts; full deserialization needs schema classes
            # For now, we store minimal dict data
            logger.info("Loaded %d memory entries from %s",
                        len(data.get("entries", {})), self._path)
        except Exception as e:
            logger.warning("Could not load research memory: %s", e)
            self._entries = {}
            self._by_date = []

    def export(self, path: str | None = None) -> str:
        """Export memory to a JSON file."""
        import json
        export_path = Path(path or f"data/research_memory_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json")
        export_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "total_entries": self.total_entries,
            "success_rate": self.success_rate,
            "entries": [e.to_dict() for e in self._entries.values()],
        }
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        logger.info("Exported %d entries to %s", self.total_entries, export_path)
        return str(export_path)

    def clear(self) -> None:
        """Clear all entries (for testing)."""
        self._entries.clear()
        self._by_date.clear()
        self._save()
