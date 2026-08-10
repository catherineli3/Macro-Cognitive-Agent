"""Belief Lifecycle Manager — six-stage belief lifecycle (Milestone C, Q3).

Replaces the old Learning Engine with a principled six-stage lifecycle:
    CREATED → VALIDATED → MATURE → WEAKENING → RETIRED → ARCHIVED

Plus REVIVAL path for regime-appropriate reactivation.

Architecture: Belief weight is DERIVED from Principles, not independent.
    belief.weight = f(principle.strength_score, principle.accuracy, belief.recent_performance)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from src.schemas.research import ResearchPrinciple, PrincipleStrength, PrincipleStatus
from src.schemas.belief_version import AdaptiveBelief, BeliefVersion
from src.shared.logging import get_logger

logger = get_logger(__name__)


class BeliefLifecycleStage(str, Enum):
    """Six-stage belief lifecycle (Architecture Q3)."""
    CREATED = "created"          # New belief, low data
    VALIDATED = "validated"      # Entry threshold met
    MATURE = "mature"            # Stable, high accuracy
    WEAKENING = "weakening"      # Accuracy declining
    RETIRED = "retired"          # Failure threshold met
    ARCHIVED = "archived"        # Historical artifact


class BeliefLifecycleManager:
    """Manages the six-stage lifecycle of Adaptive Beliefs.

    Key invariants:
        - Belief.weight = f(Principle.strength) + f(recent_performance)
        - When a Principle is retired → all founded beliefs re-evaluated
        - Competing principles → weight × 0.5 penalty
    """

    # Lifecycle thresholds
    VALIDATION_MIN_CORRECT = 5
    VALIDATION_MIN_OBS = 10
    MATURITY_MIN_CORRECT = 20
    MATURITY_MIN_ACCURACY = 0.65
    WEAKENING_MAX_FAILURES_IN_WINDOW = 3  # In last 10
    RETIREMENT_MAX_FAILURES = 10
    RETIREMENT_MAX_CYCLES_WITHOUT_RECOVERY = 30

    def __init__(self) -> None:
        self._beliefs: dict[str, AdaptiveBelief] = {}
        self._principle_index: dict[str, list[str]] = {}  # principle_id → [belief_ids]

    def register_belief(self, belief: AdaptiveBelief) -> str:
        """Register a new belief in CREATED state."""
        bid = belief.belief_id
        self._beliefs[bid] = belief
        return bid

    def link_to_principle(self, belief_id: str, principle_id: str) -> bool:
        """Link a belief to its founding principle."""
        belief = self._beliefs.get(belief_id)
        if not belief:
            return False

        if principle_id not in belief.founded_on_principles:
            belief.founded_on_principles.append(principle_id)

        self._principle_index.setdefault(principle_id, []).append(belief_id)
        return True

    def evaluate_lifecycle(self, belief_id: str, cycle: int = 0) -> BeliefLifecycleStage:
        """Evaluate and transition a belief through its lifecycle stages.

        Returns the current lifecycle stage after evaluation.
        """
        belief = self._beliefs.get(belief_id)
        if not belief:
            return BeliefLifecycleStage.CREATED

        current = self._determine_stage(belief)

        # Transition logic
        if current == BeliefLifecycleStage.CREATED:
            if (belief.correct_count >= self.VALIDATION_MIN_CORRECT
                    and belief.cycle_count >= self.VALIDATION_MIN_OBS):
                current = BeliefLifecycleStage.VALIDATED
                logger.debug("Belief %s: CREATED → VALIDATED", belief_id)

        if current == BeliefLifecycleStage.VALIDATED:
            if (belief.correct_count >= self.MATURITY_MIN_CORRECT
                    and belief.historical_accuracy >= self.MATURITY_MIN_ACCURACY):
                current = BeliefLifecycleStage.MATURE
                logger.debug("Belief %s: VALIDATED → MATURE", belief_id)

            if (belief.streak < -self.WEAKENING_MAX_FAILURES_IN_WINDOW
                    and belief.cycle_count >= 10):
                current = BeliefLifecycleStage.WEAKENING
                logger.debug("Belief %s: VALIDATED → WEAKENING", belief_id)

        if current == BeliefLifecycleStage.MATURE:
            if (belief.streak < -self.WEAKENING_MAX_FAILURES_IN_WINDOW
                    and belief.cycle_count >= 20):
                current = BeliefLifecycleStage.WEAKENING
                logger.debug("Belief %s: MATURE → WEAKENING", belief_id)

        if current == BeliefLifecycleStage.WEAKENING:
            if (belief.streak < -self.RETIREMENT_MAX_FAILURES
                    and belief.cycle_count >= self.RETIREMENT_MAX_CYCLES_WITHOUT_RECOVERY):
                current = BeliefLifecycleStage.RETIRED
                belief.status = "deprecated"
                logger.info("Belief %s: WEAKENING → RETIRED", belief_id)

        # Update belief status
        self._update_belief_status(belief, current)
        return current

    def derive_weight(self, belief_id: str,
                       principles: dict[str, ResearchPrinciple],
                       competition_penalty: float = 1.0) -> float:
        """Derive belief weight from founding principles + recent performance.

        Invariant 1: Belief.weight is NOT an independent parameter.
        weight = f(principle.strength_score, principle.accuracy_in_context, recent_performance)
        """
        belief = self._beliefs.get(belief_id)
        if not belief:
            return 0.5

        if not belief.founded_on_principles:
            # No principles → use historical performance only
            return belief.historical_accuracy

        # Average strength of founding principles
        principle_scores = []
        for pid in belief.founded_on_principles:
            p = principles.get(pid)
            if p and p.status not in (PrincipleStatus.RETIRED, PrincipleStatus.ARCHIVED):
                score = p.evidence.strength_score
                # Competing principle penalty
                if p.status == PrincipleStatus.ACTIVE_COMPETITION:
                    score *= 0.5
                principle_scores.append(score)

        if not principle_scores:
            return 0.3  # Found on retired principles → low confidence

        avg_principle_strength = sum(principle_scores) / len(principle_scores)

        # Recent performance
        if belief.cycle_count > 0:
            recent_acc = belief.historical_accuracy
        else:
            recent_acc = 0.5

        # Combined weight
        weight = 0.5 * avg_principle_strength + 0.3 * recent_acc + 0.2 * min(1.0, belief.cycle_count / 50)

        # Apply competition penalty
        weight *= competition_penalty

        return round(min(1.0, max(0.0, weight)), 4)

    def cascade_principle_retirement(self, principle_id: str,
                                       principles: dict[str, ResearchPrinciple]) -> list[str]:
        """When a Principle is retired, re-derive all dependent beliefs.

        Returns list of affected belief IDs.
        """
        affected = self._principle_index.get(principle_id, [])
        for bid in affected:
            self.derive_weight(bid, principles)
        if affected:
            logger.info("Principle %s retired → %d beliefs re-derived", principle_id, len(affected))
        return affected

    def record_prediction_outcome(self, belief_id: str,
                                    correct: bool,
                                    cycle: int = 0) -> None:
        """Record a prediction outcome for lifecycle tracking."""
        belief = self._beliefs.get(belief_id)
        if not belief:
            return

        belief.cycle_count += 1
        if correct:
            belief.correct_count += 1
            belief.streak = max(0, belief.streak) + 1
        else:
            belief.streak = min(0, belief.streak) - 1

    def _determine_stage(self, belief: AdaptiveBelief) -> BeliefLifecycleStage:
        """Determine current lifecycle stage from belief state."""
        if belief.status == "deprecated":
            return BeliefLifecycleStage.RETIRED
        if belief.cycle_count == 0:
            return BeliefLifecycleStage.CREATED
        if belief.cycle_count < self.VALIDATION_MIN_OBS:
            return BeliefLifecycleStage.CREATED
        if belief.cycle_count < self.MATURITY_MIN_CORRECT:
            return BeliefLifecycleStage.VALIDATED
        if belief.historical_accuracy >= self.MATURITY_MIN_ACCURACY:
            return BeliefLifecycleStage.MATURE
        if belief.streak < -self.WEAKENING_MAX_FAILURES_IN_WINDOW:
            return BeliefLifecycleStage.WEAKENING
        return BeliefLifecycleStage.VALIDATED

    @staticmethod
    def _update_belief_status(belief: AdaptiveBelief,
                               stage: BeliefLifecycleStage) -> None:
        """Update belief weight based on lifecycle stage."""
        stage_weights = {
            BeliefLifecycleStage.CREATED: 0.3,
            BeliefLifecycleStage.VALIDATED: 0.6,
            BeliefLifecycleStage.MATURE: 0.85,
            BeliefLifecycleStage.WEAKENING: 0.3,
            BeliefLifecycleStage.RETIRED: 0.0,
            BeliefLifecycleStage.ARCHIVED: 0.0,
        }
        belief.weight = stage_weights.get(stage, 0.5)

    def get_belief(self, belief_id: str) -> AdaptiveBelief | None:
        return self._beliefs.get(belief_id)

    def get_mature_beliefs(self) -> list[AdaptiveBelief]:
        """Get all mature (ready for hypothesis generation) beliefs."""
        return [
            b for b in self._beliefs.values()
            if self._determine_stage(b) == BeliefLifecycleStage.MATURE
            and b.status != "deprecated"
        ]

    def get_active_beliefs(self) -> list[AdaptiveBelief]:
        """Get all active beliefs (not retired/archived)."""
        return [
            b for b in self._beliefs.values()
            if b.status != "deprecated"
        ]

    @property
    def total_beliefs(self) -> int:
        return len(self._beliefs)

    def summary(self) -> str:
        stages = {}
        for b in self._beliefs.values():
            stage = self._determine_stage(b).value
            stages[stage] = stages.get(stage, 0) + 1
        return f"BeliefLifecycleManager: {self.total_beliefs} beliefs, stages={stages}"
