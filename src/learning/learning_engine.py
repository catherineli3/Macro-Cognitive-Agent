"""Learning Engine — v2.0 core module.

Enables the Agent to learn from past prediction outcomes.
Updates belief weights, confidence decay rates, and discovers patterns.

Design (DDR-v2):
    - LearningEngine consumes OutcomeSummary to adjust BeliefWeights.
    - BeliefUpdater applies historical accuracy to dimension weights.
    - ConfidenceDecay controls recency weighting.
    - PatternMiner discovers recurring macro patterns from outcome data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.schemas.learning import BeliefWeight, LearningSummary
from src.schemas.outcome import OutcomeSummary
from src.shared.logging import get_logger

logger = get_logger(__name__)

_RECENCY_WINDOW: int = 10  # Last N outcomes for recent accuracy
_LEARNING_RATE: float = 0.1  # How aggressively weights update
_DEFAULT_DIMENSIONS = ["liquidity", "credit", "growth", "risk_appetite", "inflation"]


# ── Belief Updater ───────────────────────────────────────────────────────────


class BeliefUpdater:
    """Updates BeliefWeight based on historical outcome accuracy."""

    def __init__(self, learning_rate: float = _LEARNING_RATE) -> None:
        self._lr = learning_rate

    def update_from_summary(
        self,
        weights: list[BeliefWeight],
        outcome_summary: OutcomeSummary,
        recent_outcomes: Optional[list] = None,
    ) -> list[BeliefWeight]:
        """Update belief weights using outcome data.

        Formula:
            new_weight = old_weight * (1 - lr) + accuracy * lr

        Args:
            weights: Current belief weights.
            outcome_summary: Aggregated outcome metrics.
            recent_outcomes: Optional recent outcomes for recency bias.

        Returns:
            Updated belief weights.
        """
        dim_acc = outcome_summary.dimension_accuracy

        for bw in weights:
            dim_key = bw.dimension.lower()
            dim_data = dim_acc.get(dim_key)

            if dim_data and dim_data["total"] > 0:
                accuracy = dim_data["hit_rate"]

                # Update weight toward historical accuracy
                new_weight = bw.current_weight * (1 - self._lr) + accuracy * self._lr
                bw.current_weight = round(max(0.0, min(1.0, new_weight)), 4)

                # Update accuracy stats
                bw.total_predictions = dim_data["total"]
                bw.correct_predictions = dim_data["correct"]
                bw.historical_accuracy = accuracy

                # Recent accuracy (use last N)
                if recent_outcomes:
                    dim_recent = [
                        r.outcome
                        for r in recent_outcomes[-_RECENCY_WINDOW:]
                        if r.outcome.dimension.lower() == dim_key
                    ]
                    if dim_recent:
                        recent_correct = sum(1 for o in dim_recent if o.is_correct)
                        bw.recent_accuracy = round(recent_correct / len(dim_recent), 4)

                # Accuracy trend
                bw.accuracy_trend = self._compute_trend(bw)

                # Streak tracking
                bw.streak = self._compute_streak(bw, recent_outcomes, dim_key)

                bw.last_updated = datetime.now(timezone.utc)

        return weights

    @staticmethod
    def _compute_trend(bw: BeliefWeight) -> str:
        """Determine if accuracy is improving, declining, or stable."""
        if bw.recent_accuracy > bw.historical_accuracy + 0.05:
            return "improving"
        elif bw.recent_accuracy < bw.historical_accuracy - 0.05:
            return "declining"
        return "stable"

    @staticmethod
    def _compute_streak(
        bw: BeliefWeight,
        recent_outcomes: Optional[list],
        dim_key: str,
    ) -> int:
        """Compute consecutive streak of correct/incorrect predictions."""
        if not recent_outcomes:
            return 0

        streak = 0
        for record in reversed(recent_outcomes):
            if record.outcome.dimension.lower() != dim_key:
                continue
            if record.outcome.is_correct:
                if streak >= 0:
                    streak += 1
                else:
                    break
            elif record.outcome.is_incorrect:
                if streak <= 0:
                    streak -= 1
                else:
                    break
        return streak

    def initialize_weights(self, dimensions: Optional[list[str]] = None) -> list[BeliefWeight]:
        """Initialize belief weights for all dimensions (neutral start)."""
        dims = dimensions or _DEFAULT_DIMENSIONS
        return [BeliefWeight(dimension=d, current_weight=0.5, initial_weight=0.5) for d in dims]


# ── Confidence Decay ─────────────────────────────────────────────────────────


class ConfidenceDecay:
    """Manages time-based confidence decay.

    Older outcomes get less weight in learning.
    Confidence decays when no new evidence arrives.
    """

    def __init__(self, base_decay_rate: float = 0.05) -> None:
        self._base_decay_rate = base_decay_rate

    def apply_decay(
        self,
        weights: list[BeliefWeight],
        days_since_last_update: Optional[float] = None,
    ) -> list[BeliefWeight]:
        """Apply time decay to belief weights.

        Formula:
            decay_applied = base_rate * days_since_last / 7

        Only applied when no new evidence has arrived.

        Args:
            weights: Current belief weights.
            days_since_last_update: Days since last update (None = no decay).

        Returns:
            Weights with decay applied.
        """
        if days_since_last_update is None or days_since_last_update <= 0:
            return weights

        for bw in weights:
            days_factor = min(days_since_last_update / 7.0, 5.0)  # Cap at 5 weeks
            decay = self._base_decay_rate * days_factor
            bw.current_weight = round(max(0.1, bw.current_weight - decay), 4)

        return weights

    def get_recency_weights(self, outcomes: list, decay_per_week: float = 0.1) -> list[float]:
        """Compute recency weights for a list of outcomes.

        Newer outcomes get weight 1.0; older ones decay exponentially.
        """
        if not outcomes:
            return []

        now = datetime.now(timezone.utc)
        weights: list[float] = []
        for record in outcomes:
            age_days = (now - record.outcome.predicted_at).total_seconds() / 86400
            age_weeks = age_days / 7.0
            w = max(0.05, 1.0 - decay_per_week * age_weeks)
            weights.append(round(w, 4))
        return weights


# ── Pattern Miner ────────────────────────────────────────────────────────────


class PatternMiner:
    """Discover recurring patterns from outcome data.

    Patterns help the Agent understand which signal combinations
    have historically been reliable.
    """

    @staticmethod
    def discover(records: list, outcome_summary: OutcomeSummary) -> list[str]:
        """Discover learned patterns from outcome data.

        Args:
            records: All outcome records.
            outcome_summary: Aggregated metrics.

        Returns:
            Natural language pattern descriptions.
        """
        patterns: list[str] = []
        dim_acc = outcome_summary.dimension_accuracy

        # Pattern 1: Best-performing dimension
        best_dim = None
        best_hit = 0.0
        worst_dim = None
        worst_hit = 1.0
        for dim, data in dim_acc.items():
            if data["total"] >= 3 and data["hit_rate"] > best_hit:
                best_hit = data["hit_rate"]
                best_dim = dim
            if data["total"] >= 3 and data["hit_rate"] < worst_hit:
                worst_hit = data["hit_rate"]
                worst_dim = dim

        if best_dim and best_hit > 0.6:
            patterns.append(
                f"{best_dim.title()} signals have been the most reliable "
                f"predictors ({best_hit:.0%} accuracy over {dim_acc[best_dim]['total']} calls)."
            )
        if worst_dim and worst_hit < 0.45:
            patterns.append(
                f"{worst_dim.title()} signals have been less reliable "
                f"({worst_hit:.0%} accuracy over {dim_acc[worst_dim]['total']} calls) — "
                f"consider requiring stronger confirmation."
            )

        # Pattern 2: Directional bias
        evaluated = [r.outcome for r in records if r.outcome.is_evaluated]
        bullish = [o for o in evaluated if o.predicted_direction.value == "bullish"]
        bearish = [o for o in evaluated if o.predicted_direction.value == "bearish"]
        if bullish:
            bull_hit = sum(1 for o in bullish if o.is_correct) / len(bullish)
            if bull_hit > 0.65:
                patterns.append(f"Bullish calls have been accurate ({bull_hit:.0%} on {len(bullish)} predictions).")
        if bearish:
            bear_hit = sum(1 for o in bearish if o.is_correct) / len(bearish)
            if bear_hit > 0.65:
                patterns.append(f"Bearish calls have been accurate ({bear_hit:.0%} on {len(bearish)} predictions).")

        # Pattern 3: Confidence calibration observation
        high_conf = [o for o in evaluated if o.predicted_confidence >= 0.75]
        low_conf = [o for o in evaluated if o.predicted_confidence <= 0.45]
        if high_conf:
            high_hit = sum(1 for o in high_conf if o.is_correct) / len(high_conf)
            if high_hit < 0.55:
                patterns.append(
                    f"High-confidence predictions (≥75%) have been unreliable "
                    f"({high_hit:.0%} accuracy) — Agent may be overconfident."
                )
            elif high_hit > 0.75:
                patterns.append(
                    f"High-confidence predictions are well-calibrated "
                    f"({high_hit:.0%} accuracy on {len(high_conf)} calls)."
                )
        if low_conf:
            low_hit = sum(1 for o in low_conf if o.is_correct) / len(low_conf)
            if low_hit < 0.35:
                patterns.append(
                    f"Low-confidence predictions are appropriately cautious "
                    f"({low_hit:.0%} accuracy) — uncertainty is warranted."
                )

        # Pattern 4: Global calibration
        if outcome_summary.total_predictions >= 5:
            if outcome_summary.hit_rate >= 0.65:
                patterns.append(
                    f"Overall prediction accuracy is good "
                    f"({outcome_summary.hit_rate:.0%} across "
                    f"{outcome_summary.total_predictions} predictions)."
                )
            elif outcome_summary.hit_rate < 0.45:
                patterns.append(
                    f"Overall prediction accuracy is below threshold "
                    f"({outcome_summary.hit_rate:.0%}) — "
                    f"consider reducing confidence in all dimensions."
                )

        return patterns


# ── Learning Engine ──────────────────────────────────────────────────────────


class LearningEngine:
    """Orchestrates the full learning cycle.

    Workflow (per cycle):
        1. Load outcome summary from OutcomeEngine.
        2. Update belief weights via BeliefUpdater.
        3. Apply confidence decay for idle dimensions.
        4. Mine patterns from outcome data.
        5. Generate LearningSummary.
    """

    def __init__(
        self,
        updater: Optional[BeliefUpdater] = None,
        decay: Optional[ConfidenceDecay] = None,
        miner: Optional[PatternMiner] = None,
    ) -> None:
        self._updater = updater or BeliefUpdater()
        self._decay = decay or ConfidenceDecay()
        self._miner = miner or PatternMiner()
        self._weights: list[BeliefWeight] = []
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self._weights = self._updater.initialize_weights()
            self._initialized = True

    def learn(
        self,
        outcome_summary: OutcomeSummary,
        outcome_records: Optional[list] = None,
        days_since_last: Optional[float] = None,
    ) -> LearningSummary:
        """Execute a learning cycle.

        Args:
            outcome_summary: Aggregated outcome metrics.
            outcome_records: All outcome records for pattern mining.
            days_since_last: Days since last update (for decay).

        Returns:
            LearningSummary with updated weights and patterns.
        """
        self._ensure_initialized()

        # 1. Apply decay if no recent updates
        if days_since_last:
            self._weights = self._decay.apply_decay(self._weights, days_since_last)

        # 2. Update weights from outcomes
        self._weights = self._updater.update_from_summary(
            self._weights, outcome_summary, outcome_records,
        )

        # 3. Mine patterns
        patterns = self._miner.discover(
            outcome_records or [],
            outcome_summary,
        )

        # 4. Determine best/worst dimensions
        best_dim = ""
        worst_dim = ""
        best_acc = 0.0
        worst_acc = 1.0
        for bw in self._weights:
            if bw.total_predictions >= 2:
                if bw.historical_accuracy > best_acc:
                    best_acc = bw.historical_accuracy
                    best_dim = bw.dimension
                if bw.historical_accuracy < worst_acc:
                    worst_acc = bw.historical_accuracy
                    worst_dim = bw.dimension

        # 5. Confidence adjustments
        adjustments: dict[str, float] = {}
        for bw in self._weights:
            if bw.total_predictions >= 3:
                delta = bw.historical_accuracy - bw.current_weight
                if abs(delta) > 0.05:
                    adjustments[bw.dimension] = round(delta, 3)

        # 6. Improvement trend
        if outcome_summary.total_predictions >= 5:
            improving_count = sum(
                1 for bw in self._weights if bw.accuracy_trend == "improving"
            )
            declining_count = sum(
                1 for bw in self._weights if bw.accuracy_trend == "declining"
            )
            if improving_count > declining_count:
                trend = "improving"
            elif declining_count > improving_count:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        logger.info(
            "learning_cycle_completed",
            extra={
                "outcomes": outcome_summary.total_predictions,
                "hit_rate": outcome_summary.hit_rate,
                "best_dim": best_dim,
                "best_acc": best_acc,
            },
        )

        return LearningSummary(
            belief_weights=self._weights,
            total_tracked_outcomes=outcome_summary.total_predictions,
            global_hit_rate=outcome_summary.hit_rate,
            brier_score=outcome_summary.brier_score,
            overall_calibration_score=round(1.0 - outcome_summary.brier_score, 4),
            improvement_trend=trend,
            best_dimension=best_dim,
            worst_dimension=worst_dim,
            learned_patterns=patterns,
            confidence_adjustments=adjustments,
        )

    def get_weights(self) -> list[BeliefWeight]:
        """Get current belief weights."""
        self._ensure_initialized()
        return list(self._weights)

    def get_weight(self, dimension: str) -> float:
        """Get weight for a specific dimension (default 0.5)."""
        self._ensure_initialized()
        for bw in self._weights:
            if bw.dimension.lower() == dimension.lower():
                return bw.current_weight
        return 0.5

    def get_accuracy(self, dimension: str) -> float:
        """Get historical accuracy for a dimension (default 0.5)."""
        self._ensure_initialized()
        for bw in self._weights:
            if bw.dimension.lower() == dimension.lower():
                return bw.historical_accuracy
        return 0.5
