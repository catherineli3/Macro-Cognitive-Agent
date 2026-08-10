"""BeliefLifecycle — 7-stage belief lifecycle management (upgraded from legacy 6-stage).

1. HYPOTHESIS          → Initial idea requiring investigation
2. EVIDENCE_GATHERING   → Actively collecting supporting/contradicting evidence
3. CONFIRMATION         → Evidence predominantly supports the belief
4. CHALLENGE            → Evidence predominantly contradicts the belief
5. CONSOLIDATION        → High confidence, prediction track record established
6. EROSION              → Confidence declining, track record deteriorating
7. RETIRED              → Belief is no longer active

Transitions are rule-based, driven by evidence state and track record.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.research.beliefs.schemas import BeliefStage, ResearchBelief
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Stage transition rules ──────────────────────────────────────────────────

def _min_evidence(stage: BeliefStage) -> int:
    return {
        BeliefStage.HYPOTHESIS: 0,
        BeliefStage.EVIDENCE_GATHERING: 1,
        BeliefStage.CONFIRMATION: 3,
        BeliefStage.CHALLENGE: 3,
        BeliefStage.CONSOLIDATION: 5,
        BeliefStage.EROSION: 5,
        BeliefStage.RETIRED: 0,
    }[stage]


def _min_confidence(stage: BeliefStage) -> float:
    return {
        BeliefStage.HYPOTHESIS: 0.0,
        BeliefStage.EVIDENCE_GATHERING: 0.3,
        BeliefStage.CONFIRMATION: 0.60,
        BeliefStage.CHALLENGE: 0.0,
        BeliefStage.CONSOLIDATION: 0.75,
        BeliefStage.EROSION: 0.0,
        BeliefStage.RETIRED: 0.0,
    }[stage]


class BeliefLifecycleManager:
    """Manages the 7-stage lifecycle of beliefs with rule-based transitions.

    Usage:
        mgr = BeliefLifecycleManager()
        mgr.evaluate(belief)  # Auto-determine and advance stage
    """

    def __init__(self) -> None:
        self._transition_log: list[dict] = []

    def evaluate(self, belief: ResearchBelief) -> Optional[BeliefStage]:
        """Evaluate a belief's current state and determine next stage.

        Returns:
            New stage if a transition is warranted, None otherwise.
        """
        n_supporting = sum(
            1 for e in belief.evidence if e.direction == "supporting"
        )
        n_contradicting = sum(
            1 for e in belief.evidence if e.direction == "contradicting"
        )
        total_evidence = n_supporting + n_contradicting
        track = belief.track_record_summary()
        accuracy = track.get("accuracy", 0.0)
        total_predictions = track.get("total", 0)

        new_stage: Optional[BeliefStage] = None
        reason = ""

        current = belief.stage

        # ── Retirement conditions ───────────────────────────────────────
        if not belief.is_active:
            return None

        # If accuracy is very poor with enough predictions, retire
        if total_predictions >= 5 and accuracy < 0.3:
            new_stage = BeliefStage.RETIRED
            reason = f"Poor track record: {accuracy:.0%} accuracy over {total_predictions} predictions"

        # If no evidence for 60+ days and in early stages
        elif belief.last_evidence_at:
            delta = (datetime.now(timezone.utc) - belief.last_evidence_at).days
            if delta > 60 and current in {BeliefStage.HYPOTHESIS, BeliefStage.EVIDENCE_GATHERING}:
                new_stage = BeliefStage.RETIRED
                reason = f"Inactive for {delta} days with insufficient evidence"

        # ── Stage progression ───────────────────────────────────────────

        # HYPOTHESIS → EVIDENCE_GATHERING
        elif current == BeliefStage.HYPOTHESIS and total_evidence >= 1:
            new_stage = BeliefStage.EVIDENCE_GATHERING
            reason = "First evidence received"

        # EVIDENCE_GATHERING → CONFIRMATION or CHALLENGE
        elif current == BeliefStage.EVIDENCE_GATHERING and total_evidence >= 3:
            ratio = n_supporting / total_evidence if total_evidence > 0 else 0
            if ratio >= 0.6:
                new_stage = BeliefStage.CONFIRMATION
                reason = f"Strong support ratio: {ratio:.0%} ({n_supporting}/{total_evidence})"
            elif ratio <= 0.4:
                new_stage = BeliefStage.CHALLENGE
                reason = f"Weak support ratio: {ratio:.0%} ({n_supporting}/{total_evidence})"

        # CONFIRMATION → CONSOLIDATION or CHALLENGE
        elif current == BeliefStage.CONFIRMATION:
            ratio = n_supporting / total_evidence if total_evidence > 0 else 0
            if belief.confidence >= 0.75 and total_predictions >= 3 and accuracy >= 0.6:
                new_stage = BeliefStage.CONSOLIDATION
                reason = f"High confidence ({belief.confidence:.2f}) + acceptable accuracy ({accuracy:.0%})"
            elif ratio <= 0.35:
                new_stage = BeliefStage.CHALLENGE
                reason = f"Support ratio declining: {ratio:.0%}"

        # CHALLENGE → EROSION or back to CONFIRMATION
        elif current == BeliefStage.CHALLENGE:
            ratio = n_supporting / total_evidence if total_evidence > 0 else 0
            if belief.confidence < 0.35:
                new_stage = BeliefStage.EROSION
                reason = f"Confidence critically low: {belief.confidence:.2f}"
            elif ratio >= 0.6:
                new_stage = BeliefStage.CONFIRMATION
                reason = f"Evidence turned supportive: {ratio:.0%}"

        # CONSOLIDATION → EROSION or stay
        elif current == BeliefStage.CONSOLIDATION:
            if belief.confidence < 0.55:
                new_stage = BeliefStage.EROSION
                reason = f"Confidence dropped below consolidation threshold: {belief.confidence:.2f}"
            elif total_predictions >= 5 and accuracy < 0.5:
                new_stage = BeliefStage.EROSION
                reason = f"Track record deteriorating: {accuracy:.0%}"

        # EROSION → RETIRED or back to CHALLENGE
        elif current == BeliefStage.EROSION:
            if belief.confidence < 0.2:
                new_stage = BeliefStage.RETIRED
                reason = f"Confidence floor reached: {belief.confidence:.2f}"
            elif n_supporting > n_contradicting * 2:
                new_stage = BeliefStage.CHALLENGE
                reason = "New supporting evidence emerging"

        # Apply transition
        if new_stage and new_stage != current:
            belief.advance_stage(new_stage, reason)
            self._transition_log.append({
                "belief_id": belief.id[:8],
                "title": belief.title,
                "from": current.value,
                "to": new_stage.value,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(
                "belief_lifecycle | %s: %s → %s (%s)",
                belief.id[:8], current.value, new_stage.value, reason,
            )

        return new_stage

    def get_active_count_by_stage(
        self, beliefs: list[ResearchBelief]
    ) -> dict[BeliefStage, int]:
        """Count active beliefs per stage."""
        counts = {stage: 0 for stage in BeliefStage}
        for b in beliefs:
            if b.is_active:
                counts[b.stage] += 1
        return counts

    def get_stage_summary(self, beliefs: list[ResearchBelief]) -> dict:
        """Get a summary of belief stages."""
        counts = self.get_active_count_by_stage(beliefs)
        total = sum(counts.values())
        return {
            "total_active": total,
            "by_stage": {s.value: c for s, c in counts.items() if c > 0},
            "retired": sum(1 for b in beliefs if not b.is_active),
            "transition_count": len(self._transition_log),
        }
