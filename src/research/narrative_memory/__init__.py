"""Narrative Memory — Daily narrative persistence layer (V3.4).

Tracks how narratives evolve over time:
    - Daily narrative snapshots (what narrative dominated, confidence, stage)
    - Narrative transition events (when one narrative replaces another)
    - Narrative lifecycle tracking (forming → consensus → extreme → breaking)
    - Narrative memory retrieval (historical patterns, similarity search)

This is the "memory" that allows the agent to say:
    "Three weeks ago, the dominant narrative was X. It has since evolved to Y,
     with Z being the key catalyst for the transition."

Without memory, each day's analysis is independent. With memory, the agent
can track narrative evolution — essential for reflexivity detection.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Optional

from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Schema
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class NarrativeMemoryEntry:
    """A single day's narrative snapshot."""

    date: str = ""  # "YYYY-MM-DD"
    timestamp: str = ""

    # Dominant narrative
    dominant_narrative: str = ""
    narrative_confidence: float = 0.0
    narrative_stage: str = ""  # forming / consensus / extreme / breaking

    # Competing narratives
    competing_narratives: list[dict] = field(default_factory=list)

    # Context
    regime_label: str = ""
    key_events: list[str] = field(default_factory=list)
    key_data_points: dict = field(default_factory=dict)

    # Narrative metadata
    narrative_category: str = ""  # monetary / growth / inflation / risk / structural
    narrative_intensity: float = 0.0  # How strongly the narrative is driving markets
    narrative_entropy: float = 0.0  # Shannon entropy of competing narratives (0=consensus)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "timestamp": self.timestamp,
            "dominant_narrative": self.dominant_narrative,
            "narrative_confidence": self.narrative_confidence,
            "narrative_stage": self.narrative_stage,
            "competing_narratives": self.competing_narratives,
            "regime_label": self.regime_label,
            "key_events": self.key_events,
            "key_data_points": self.key_data_points,
            "narrative_category": self.narrative_category,
            "narrative_intensity": self.narrative_intensity,
            "narrative_entropy": self.narrative_entropy,
        }

    @classmethod
    def from_dict(cls, data: dict) -> NarrativeMemoryEntry:
        return cls(
            **{
                k: data.get(
                    k,
                    (
                        ""
                        if k
                        in (
                            "date",
                            "dominant_narrative",
                        )
                        else (
                            []
                            if k in ("competing_narratives", "key_events")
                            else (
                                {}
                                if k == "key_data_points"
                                else 0.0 if isinstance(getattr(cls, k, 0.0), float) else ""
                            )
                        )
                    ),
                )
                for k in cls.__dataclass_fields__
            }
        )


@dataclass
class NarrativeTransition:
    """Records when one dominant narrative replaces another."""

    transition_id: str = ""
    from_narrative: str = ""
    to_narrative: str = ""
    transition_date: str = ""
    catalyst: str = ""  # What triggered the transition
    speed: str = ""  # "gradual" / "sudden" / "shock"
    regime_change: bool = False  # Did regime change simultaneously?


# ═══════════════════════════════════════════════════════════════════════════
# Narrative Memory Engine
# ═══════════════════════════════════════════════════════════════════════════


class NarrativeMemory:
    """Persistent narrative memory with daily snapshots and transition tracking.

    Usage:
        memory = NarrativeMemory(storage_dir="./data/narrative_memory")
        memory.record_daily_snapshot(narratives, regime, events)
        history = memory.get_history(days=30)
        transitions = memory.get_transitions()
        similar = memory.find_similar_narratives("hard landing", top_n=5)
    """

    def __init__(self, storage_dir: str = "./data/narrative_memory"):
        self.storage_dir = storage_dir
        self._entries: dict[str, NarrativeMemoryEntry] = {}  # date → entry
        self._transitions: list[NarrativeTransition] = []
        self._ensure_storage()

    def _ensure_storage(self):
        """Create storage directory and load existing data."""
        os.makedirs(self.storage_dir, exist_ok=True)
        self._load()

    def _entries_path(self) -> str:
        return os.path.join(self.storage_dir, "narrative_entries.json")

    def _transitions_path(self) -> str:
        return os.path.join(self.storage_dir, "narrative_transitions.json")

    def _load(self):
        """Load existing memory from disk."""
        try:
            if os.path.exists(self._entries_path()):
                with open(self._entries_path(), encoding="utf-8") as f:
                    data = json.load(f)
                    self._entries = {k: NarrativeMemoryEntry.from_dict(v) for k, v in data.items()}
                logger.info("Loaded %d narrative memory entries", len(self._entries))
        except Exception as e:
            logger.warning("Failed to load narrative entries: %s", e)

        try:
            if os.path.exists(self._transitions_path()):
                with open(self._transitions_path(), encoding="utf-8") as f:
                    data = json.load(f)
                    self._transitions = [NarrativeTransition(**t) for t in data]
                logger.info("Loaded %d narrative transitions", len(self._transitions))
        except Exception as e:
            logger.warning("Failed to load transitions: %s", e)

    def _save(self):
        """Persist memory to disk."""
        try:
            with open(self._entries_path(), "w", encoding="utf-8") as f:
                json.dump(
                    {k: v.to_dict() for k, v in self._entries.items()},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as e:
            logger.error("Failed to save narrative entries: %s", e)

        try:
            with open(self._transitions_path(), "w", encoding="utf-8") as f:
                json.dump(
                    [t.__dict__ for t in self._transitions],
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as e:
            logger.error("Failed to save transitions: %s", e)

    # ── Public API ────────────────────────────────────────────────────

    def record_daily_snapshot(
        self,
        dominant_narrative: str,
        narrative_confidence: float = 0.5,
        narrative_stage: str = "",
        competing_narratives: list[dict] = None,
        regime_label: str = "",
        key_events: list[str] = None,
        key_data_points: dict = None,
        narrative_category: str = "",
    ) -> NarrativeMemoryEntry:
        """Record a daily narrative snapshot.

        Also detects narrative transitions if the dominant narrative changed.
        """
        now = datetime.now(UTC)
        date_str = now.strftime("%Y-%m-%d")

        # Compute narrative entropy (how much disagreement among competing narratives)
        competing = competing_narratives or []
        entropy = self._compute_entropy(competing)

        # Narrative intensity: confidence × how directional the narrative is
        intensity = narrative_confidence * (1.0 - entropy) if competing else narrative_confidence

        entry = NarrativeMemoryEntry(
            date=date_str,
            timestamp=now.isoformat(),
            dominant_narrative=dominant_narrative,
            narrative_confidence=narrative_confidence,
            narrative_stage=narrative_stage,
            competing_narratives=competing,
            regime_label=regime_label,
            key_events=key_events or [],
            key_data_points=key_data_points or {},
            narrative_category=narrative_category,
            narrative_intensity=intensity,
            narrative_entropy=entropy,
        )

        # Detect transition
        prev_entry = self._get_previous_entry(date_str)
        if prev_entry and prev_entry.dominant_narrative != dominant_narrative:
            self._record_transition(
                from_narrative=prev_entry.dominant_narrative,
                to_narrative=dominant_narrative,
                transition_date=date_str,
                regime_change=prev_entry.regime_label != regime_label,
                prev_entry=prev_entry,
            )

        # Store
        self._entries[date_str] = entry
        self._save()

        logger.info(
            "Recorded narrative snapshot: %s → %s (conf: %.2f, entropy: %.2f)",
            date_str,
            dominant_narrative[:50],
            narrative_confidence,
            entropy,
        )
        return entry

    def get_history(self, days: int = 30) -> list[NarrativeMemoryEntry]:
        """Get narrative history for the last N days."""
        sorted_entries = sorted(self._entries.values(), key=lambda e: e.date, reverse=True)
        return sorted_entries[:days]

    def get_today(self) -> NarrativeMemoryEntry | None:
        """Get today's narrative snapshot if recorded."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        return self._entries.get(today)

    def get_transitions(self, days: int = 90) -> list[NarrativeTransition]:
        """Get narrative transitions in the last N days."""
        cutoff = (
            datetime.now(UTC).strftime("%Y-%m-%d")
            if days >= 365
            else datetime.now(UTC).strftime("%Y-%m-%d")
        )
        return [t for t in self._transitions if t.transition_date >= cutoff]

    def find_similar_narratives(self, query: str, top_n: int = 5) -> list[NarrativeMemoryEntry]:
        """Find historical periods with similar narratives (simple keyword match)."""
        query_lower = query.lower()
        scored = []
        for entry in self._entries.values():
            # Score by keyword overlap
            text = (
                entry.dominant_narrative
                + " "
                + " ".join(n.get("title", "") for n in entry.competing_narratives)
            ).lower()
            score = sum(1 for word in query_lower.split() if word in text)
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_n]]

    def get_narrative_lifecycle(self, narrative_title: str) -> list[dict]:
        """Trace the lifecycle of a specific narrative over time.

        Returns a timeline of how the narrative evolved.
        """
        timeline = []
        for entry in sorted(self._entries.values(), key=lambda e: e.date):
            # Check if this narrative appears as dominant or competing
            if narrative_title.lower() in entry.dominant_narrative.lower():
                timeline.append(
                    {
                        "date": entry.date,
                        "role": "dominant",
                        "confidence": entry.narrative_confidence,
                        "stage": entry.narrative_stage,
                    }
                )
            else:
                for cn in entry.competing_narratives:
                    if narrative_title.lower() in cn.get("title", "").lower():
                        timeline.append(
                            {
                                "date": entry.date,
                                "role": "competing",
                                "probability": cn.get("probability", 0),
                            }
                        )
        return timeline

    def get_narrative_evolution_summary(self, days: int = 14) -> str:
        """Text summary of narrative evolution over recent days."""
        history = self.get_history(days)
        if not history:
            return "无叙事历史数据"

        parts = []
        for entry in history:
            trend = (
                "↑"
                if entry.narrative_confidence > 0.6
                else ("↓" if entry.narrative_confidence < 0.4 else "→")
            )
            parts.append(
                f"{entry.date}: [{entry.narrative_stage or '?'}] {entry.dominant_narrative[:60]} "
                f"(conf:{entry.narrative_confidence:.2f}) {trend}"
            )

        return "\n".join(parts)

    def detect_narrative_momentum(self, days: int = 7) -> dict:
        """Detect whether a narrative is gaining or losing momentum."""
        history = self.get_history(days)
        if len(history) < 3:
            return {"trend": "insufficient_data", "momentum": 0.0}

        # Check confidence trend
        confidences = [e.narrative_confidence for e in history[:days]]
        recent_avg = sum(confidences[:3]) / max(len(confidences[:3]), 1)
        earlier_avg = sum(confidences[3:]) / max(len(confidences[3:]), 1)

        momentum = recent_avg - earlier_avg

        if momentum > 0.1:
            trend = "strengthening"
        elif momentum < -0.1:
            trend = "weakening"
        else:
            trend = "stable"

        # Check if entropy is decreasing (narrowing consensus)
        entropies = [e.narrative_entropy for e in history[:days] if e.narrative_entropy > 0]
        entropy_trend = (
            "narrowing"
            if entropies and len(entropies) >= 3 and entropies[-1] < entropies[0] * 0.8
            else "stable"
        )

        return {
            "trend": trend,
            "momentum": round(momentum, 3),
            "entropy_trend": entropy_trend,
            "current_confidence": confidences[0] if confidences else 0.0,
            "narrative": history[0].dominant_narrative if history else "",
        }

    # ── Internal helpers ──────────────────────────────────────────────

    def _get_previous_entry(self, current_date: str) -> NarrativeMemoryEntry | None:
        """Get the most recent entry before the given date."""
        prev = None
        for date_str, entry in sorted(self._entries.items()):
            if date_str >= current_date:
                break
            prev = entry
        return prev

    def _record_transition(
        self,
        from_narrative: str,
        to_narrative: str,
        transition_date: str,
        regime_change: bool = False,
        prev_entry: NarrativeMemoryEntry | None = None,
    ):
        """Record a narrative transition."""
        catalyst = ""
        if prev_entry and prev_entry.key_events:
            catalyst = f"Key events: {', '.join(prev_entry.key_events[:3])}"

        speed = "sudden" if regime_change else "gradual"

        transition = NarrativeTransition(
            transition_id=f"trans-{transition_date}-{len(self._transitions)}",
            from_narrative=from_narrative,
            to_narrative=to_narrative,
            transition_date=transition_date,
            catalyst=catalyst,
            speed=speed,
            regime_change=regime_change,
        )

        self._transitions.append(transition)
        logger.info(
            "Narrative transition: [%s] → [%s] on %s (regime_change=%s)",
            from_narrative[:40],
            to_narrative[:40],
            transition_date,
            regime_change,
        )

    @staticmethod
    def _compute_entropy(competing_narratives: list[dict]) -> float:
        """Compute Shannon entropy of competing narrative probabilities."""
        if not competing_narratives:
            return 0.0

        import math

        probs = [n.get("probability", n.get("confidence", 0.1)) for n in competing_narratives]
        # Normalize
        total = sum(probs) or 1.0
        norm_probs = [p / total for p in probs]

        entropy = -sum(p * math.log(max(p, 1e-10)) for p in norm_probs)

        # Normalize to 0-1 by dividing by max entropy (log N)
        max_entropy = math.log(max(len(norm_probs), 1))
        return entropy / max_entropy if max_entropy > 0 else 0.0
