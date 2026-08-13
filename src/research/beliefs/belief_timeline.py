"""V7.2 Live Belief Evolution — Track how beliefs change over time.

Beliefs are not static. They evolve as new evidence arrives.

This module tracks:
    - Belief confidence over time (timeline)
    - What events caused belief shifts
    - Belief convergence/divergence patterns
    - When beliefs should be retired vs strengthened

Output: Belief Timeline chart data and narrative evolution stories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class BeliefTrend(str, Enum):
    STRENGTHENING = "strengthening"  # Confidence rising
    WEAKENING = "weakening"  # Confidence falling
    STABLE = "stable"  # No significant change
    VOLATILE = "volatile"  # Erratic confidence
    CONVERGING = "converging"  # Multiple beliefs aligning
    DIVERGING = "diverging"  # Beliefs pulling apart


@dataclass
class BeliefSnapshot:
    """A single point in a belief's evolution timeline."""

    timestamp: str = ""
    belief_id: str = ""
    belief_name: str = ""
    confidence: float = 0.5
    stage: str = ""  # hypothesis, evidence_gathering, etc.
    evidence_count: int = 0
    supporting_evidence: int = 0
    contradicting_evidence: int = 0

    # What caused this state
    trigger_event: str = ""
    trigger_description: str = ""

    # Narrative context
    dominant_narrative: str = ""
    narrative_alignment: float = 0.0  # How well does belief align with narrative?


@dataclass
class BeliefTimeline:
    """Complete evolution history of a single belief."""

    belief_id: str = ""
    belief_name: str = ""
    domain: str = ""

    snapshots: list[BeliefSnapshot] = field(default_factory=list)

    # Derived metrics
    trend: BeliefTrend = BeliefTrend.STABLE
    volatility: float = 0.0  # Std dev of confidence changes
    confidence_range: tuple[float, float] = (0.0, 0.0)  # (min, max)
    total_evidence_processed: int = 0

    # Key events
    peak_confidence: float | None = None
    trough_confidence: float | None = None
    peak_at: str = ""
    trough_at: str = ""

    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def add_snapshot(self, snapshot: BeliefSnapshot):
        self.snapshots.append(snapshot)
        self._recalculate()

    def _recalculate(self):
        if not self.snapshots:
            return

        confidences = [s.confidence for s in self.snapshots]
        self.confidence_range = (min(confidences), max(confidences))
        self.total_evidence_processed = sum(s.evidence_count for s in self.snapshots)

        # Volatility
        if len(confidences) > 1:
            mean = sum(confidences) / len(confidences)
            variance = sum((c - mean) ** 2 for c in confidences) / len(confidences)
            self.volatility = variance**0.5
        else:
            self.volatility = 0.0

        # Trend
        if len(confidences) >= 2:
            first_half = confidences[: len(confidences) // 2]
            second_half = confidences[len(confidences) // 2 :]
            delta = sum(second_half) / len(second_half) - sum(first_half) / len(first_half)

            if delta > 0.1:
                self.trend = BeliefTrend.STRENGTHENING
            elif delta < -0.1:
                self.trend = BeliefTrend.WEAKENING
            elif self.volatility > 0.15:
                self.trend = BeliefTrend.VOLATILE
            else:
                self.trend = BeliefTrend.STABLE

        # Peaks
        if confidences:
            self.peak_confidence = max(confidences)
            self.trough_confidence = min(confidences)
            max_idx = confidences.index(self.peak_confidence)
            min_idx = confidences.index(self.trough_confidence)
            self.peak_at = (
                self.snapshots[max_idx].timestamp if max_idx < len(self.snapshots) else ""
            )
            self.trough_at = (
                self.snapshots[min_idx].timestamp if min_idx < len(self.snapshots) else ""
            )

    def get_evolution_data(self) -> list[dict]:
        """Get data for charting belief evolution."""
        return [
            {
                "timestamp": s.timestamp[:10],  # Date only
                "confidence": round(s.confidence, 3),
                "stage": s.stage,
                "evidence_supporting": s.supporting_evidence,
                "evidence_contradicting": s.contradicting_evidence,
                "trigger": s.trigger_description[:60],
            }
            for s in self.snapshots
        ]

    def summary(self) -> str:
        return (
            f"Belief '{self.belief_name}': {self.trend.value} trend, "
            f"confidence {self.confidence_range[0]:.2f}→{self.confidence_range[1]:.2f}, "
            f"{len(self.snapshots)} snapshots, "
            f"volatility: {self.volatility:.3f}"
        )


class BeliefEvolutionTracker:
    """Track the evolution of all beliefs over time.

    Every time a belief's confidence changes, we record:
    - When it changed
    - What caused the change
    - The new evidence count
    - The narrative context

    This builds a complete belief timeline for retrospective analysis.
    """

    def __init__(self):
        self.timelines: dict[str, BeliefTimeline] = {}
        self._global_snapshots: list[dict] = []  # Cross-belief snapshot

    def record(
        self,
        belief_id: str,
        belief_name: str,
        confidence: float,
        stage: str = "",
        evidence_count: int = 0,
        supporting: int = 0,
        contradicting: int = 0,
        trigger_event: str = "",
        trigger_description: str = "",
        dominant_narrative: str = "",
        narrative_alignment: float = 0.0,
        domain: str = "",
    ) -> BeliefSnapshot:
        """Record a new belief snapshot."""

        # Get or create timeline
        if belief_id not in self.timelines:
            self.timelines[belief_id] = BeliefTimeline(
                belief_id=belief_id,
                belief_name=belief_name,
                domain=domain,
            )

        timeline = self.timelines[belief_id]
        timeline.belief_name = belief_name  # Update name if changed

        snapshot = BeliefSnapshot(
            timestamp=datetime.now(UTC).isoformat(),
            belief_id=belief_id,
            belief_name=belief_name,
            confidence=confidence,
            stage=stage,
            evidence_count=evidence_count,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            trigger_event=trigger_event,
            trigger_description=trigger_description,
            dominant_narrative=dominant_narrative,
            narrative_alignment=narrative_alignment,
        )

        timeline.add_snapshot(snapshot)

        # Global record
        self._global_snapshots.append(
            {
                "timestamp": snapshot.timestamp,
                "belief_id": belief_id,
                "confidence": confidence,
            }
        )

        return snapshot

    def record_batch(self, beliefs: list[dict]) -> list[BeliefSnapshot]:
        """Record multiple belief updates at once."""
        snapshots = []
        for b in beliefs:
            s = self.record(
                belief_id=b.get("id", ""),
                belief_name=b.get("name", ""),
                confidence=b.get("confidence", 0.5),
                stage=b.get("stage", ""),
                evidence_count=b.get("evidence_count", 0),
                supporting=b.get("supporting", 0),
                contradicting=b.get("contradicting", 0),
                trigger_event=b.get("trigger_event", ""),
                trigger_description=b.get("trigger_description", ""),
                dominant_narrative=b.get("narrative", ""),
                domain=b.get("domain", ""),
            )
            snapshots.append(s)
        return snapshots

    # ── Query APIs ────────────────────────────────────────────────────────

    def get_timeline(self, belief_id: str) -> BeliefTimeline | None:
        return self.timelines.get(belief_id)

    def get_all_timelines(self) -> dict[str, BeliefTimeline]:
        return dict(self.timelines)

    def get_evolution_data(self, belief_id: str) -> list[dict]:
        """Get chart-ready evolution data for a belief."""
        timeline = self.timelines.get(belief_id)
        if not timeline:
            return []
        return timeline.get_evolution_data()

    def get_current_snapshot(self) -> dict[str, BeliefSnapshot]:
        """Get the most recent snapshot for every belief."""
        current = {}
        for bid, timeline in self.timelines.items():
            if timeline.snapshots:
                current[bid] = timeline.snapshots[-1]
        return current

    def get_beliefs_by_trend(self, trend: BeliefTrend) -> list[BeliefTimeline]:
        """Get all beliefs with a specific trend."""
        return [t for t in self.timelines.values() if t.trend == trend]

    def get_most_volatile(self, limit: int = 5) -> list[BeliefTimeline]:
        """Get the most volatile beliefs."""
        sorted_timelines = sorted(self.timelines.values(), key=lambda t: t.volatility, reverse=True)
        return sorted_timelines[:limit]

    def get_strongest_beliefs(self, limit: int = 5) -> list[BeliefTimeline]:
        """Get beliefs with highest current confidence."""
        current = self.get_current_snapshot()
        sorted_beliefs = sorted(current.values(), key=lambda s: s.confidence, reverse=True)
        result = []
        for s in sorted_beliefs[:limit]:
            timeline = self.timelines.get(s.belief_id)
            if timeline:
                result.append(timeline)
        return result

    def get_weakening_beliefs(self) -> list[BeliefTimeline]:
        """Get beliefs that are currently weakening."""
        return self.get_beliefs_by_trend(BeliefTrend.WEAKENING)

    def get_convergence_analysis(self) -> dict:
        """Check if multiple beliefs are converging or diverging."""
        timelines = list(self.timelines.values())
        if len(timelines) < 2:
            return {"status": "insufficient_data"}

        # Check trend alignment
        trends = [t.trend for t in timelines]
        strengthening = sum(1 for tr in trends if tr == BeliefTrend.STRENGTHENING)
        weakening = sum(1 for tr in trends if tr == BeliefTrend.WEAKENING)
        stable = sum(1 for tr in trends if tr == BeliefTrend.STABLE)

        if strengthening > len(timelines) * 0.6:
            status = "converging_bullish"
        elif weakening > len(timelines) * 0.6:
            status = "converging_bearish"
        elif stable > len(timelines) * 0.6:
            status = "stable_consensus"
        else:
            status = "diverging"

        return {
            "status": status,
            "total_beliefs": len(timelines),
            "strengthening": strengthening,
            "weakening": weakening,
            "stable": stable,
            "avg_volatility": sum(t.volatility for t in timelines) / len(timelines),
        }

    def get_belief_impact_events(self, belief_id: str) -> list[dict]:
        """Get all events that impacted a specific belief."""
        timeline = self.timelines.get(belief_id)
        if not timeline:
            return []

        events = []
        for s in timeline.snapshots:
            if s.trigger_event or s.trigger_description:
                events.append(
                    {
                        "timestamp": s.timestamp,
                        "confidence": s.confidence,
                        "confidence_change": (
                            s.confidence - events[-1]["confidence"] if events else 0
                        ),
                        "trigger": s.trigger_description,
                    }
                )
        return sorted(events, key=lambda e: abs(e["confidence_change"]), reverse=True)

    # ── Reporting ─────────────────────────────────────────────────────────

    def get_evolution_report(self) -> str:
        """Generate a narrative report on belief evolution."""
        lines = ["# Belief Evolution Report", ""]

        for bid, timeline in self.timelines.items():
            lines.append(f"## {timeline.belief_name or bid}")
            lines.append(f"- **Trend**: {timeline.trend.value}")
            lines.append(
                f"- **Confidence Range**: {timeline.confidence_range[0]:.2f} → {timeline.confidence_range[1]:.2f}"
            )
            lines.append(f"- **Volatility**: {timeline.volatility:.3f}")
            lines.append(f"- **Evidence Processed**: {timeline.total_evidence_processed}")
            lines.append(f"- **Snapshots**: {len(timeline.snapshots)}")

            if timeline.peak_at:
                lines.append(
                    f"- **Peak**: {timeline.peak_confidence:.2f} at {timeline.peak_at[:10]}"
                )
            if timeline.trough_at:
                lines.append(
                    f"- **Trough**: {timeline.trough_confidence:.2f} at {timeline.trough_at[:10]}"
                )

            lines.append("")

        convergence = self.get_convergence_analysis()
        lines.append("## Cross-Belief Analysis")
        lines.append(f"- **Convergence Status**: {convergence.get('status', 'unknown')}")
        lines.append(f"- **Average Volatility**: {convergence.get('avg_volatility', 0):.3f}")
        lines.append("")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        return {
            "total_beliefs_tracked": len(self.timelines),
            "total_snapshots": len(self._global_snapshots),
            "avg_snapshots_per_belief": (len(self._global_snapshots) / max(len(self.timelines), 1)),
            "trends": {trend.value: len(self.get_beliefs_by_trend(trend)) for trend in BeliefTrend},
            "convergence": self.get_convergence_analysis(),
        }
