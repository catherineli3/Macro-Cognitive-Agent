"""ModelWeightOptimizer — adjusts model weights based on predictive performance.

The agent uses multiple mental models (Liquidity, Credit, Growth, etc.).
Each model generates predictions. Over time, some models prove more accurate.

This engine:
    1. Computes per-model performance from scored predictions
    2. Detects performance trends (improving/worsening)
    3. Recommends weight adjustments
    4. Applies Bayesian weight updating

Weight updates use a soft-Bayesian approach:
    w_new = w_old * (1 + learning_rate * (accuracy - baseline))
    Normalized to maintain sum=1.
"""

from __future__ import annotations

from typing import Any

from src.learning.schemas import (
    ModelPerformance,
    ModelWeightRecommendation,
    ScoredPrediction,
    PredictionOutcome,
)


class ModelWeightOptimizer:
    """Adjusts mental model weights based on predictive accuracy."""

    def __init__(
        self,
        learning_rate: float = 0.1,
        min_weight: float = 0.05,
        max_samples_decay: float = 0.95,
    ):
        self.learning_rate = learning_rate
        self.min_weight = min_weight
        self.max_samples_decay = max_samples_decay
        self._performance_history: dict[str, list[dict]] = {}

    def assess_model_performance(
        self,
        model_name: str,
        domain: str,
        scored: list[ScoredPrediction],
        beliefs: list[Any] = None,
    ) -> ModelPerformance:
        """Compute performance metrics for a single model.

        Args:
            model_name: Name of the mental model (e.g., "LiquidityModel")
            domain: Domain (e.g., "liquidity")
            scored: Scored predictions attributed to this model
            beliefs: Associated beliefs (for active count)

        Returns:
            ModelPerformance with all metrics.
        """
        total = len(scored)
        correct = sum(1 for sp in scored if sp.outcome.was_correct)
        accuracy = correct / total if total > 0 else 0.0

        avg_conf = (
            sum(sp.outcome.confidence for sp in scored) / total if total > 0 else 0.0
        )
        cal_error = abs(accuracy - avg_conf) if total > 0 else 0.0

        # Recent accuracy (last 10)
        recent = [s for s in scored if s.outcome.resolved_at]
        recent = sorted(recent, key=lambda s: s.outcome.resolved_at, reverse=True)[:10]
        recent_n = len(recent)
        recent_acc = (
            sum(1 for sp in recent if sp.outcome.was_correct) / recent_n
            if recent_n > 0 else 0.0
        )

        # Momentum: is performance improving?
        momentum = recent_acc - accuracy if total > 0 else 0.0

        belief_count = len(beliefs) if beliefs else 0
        active_beliefs = sum(
            1 for b in (beliefs or []) if getattr(b, "status", "active") == "active"
        )

        perf = ModelPerformance(
            model_name=model_name,
            domain=domain,
            total_predictions=total,
            correct_predictions=correct,
            accuracy=round(accuracy, 3),
            avg_confidence=round(avg_conf, 3),
            calibration_error=round(cal_error, 3),
            is_calibrated=cal_error < 0.1,
            recent_accuracy=round(recent_acc, 3),
            momentum=round(momentum, 3),
            belief_count=belief_count,
            active_beliefs=active_beliefs,
        )

        self._performance_history.setdefault(model_name, []).append(perf.to_dict())
        return perf

    def recommend_weights(
        self,
        performances: list[ModelPerformance],
        current_weights: dict[str, float] = None,
    ) -> list[ModelWeightRecommendation]:
        """Generate weight adjustment recommendations.

        Higher accuracy → higher weight, but with bounds.
        """
        if not performances:
            return []

        current_weights = current_weights or {}
        n = len(performances)

        # Base weights: proportional to accuracy * (1 + momentum_bonus)
        raw_weights = {}
        for perf in performances:
            # Decay weight if too few predictions (insufficient sample)
            sample_bonus = 1.0 - self.max_samples_decay ** perf.total_predictions
            # Momentum bonus: slightly reward improving models
            momentum_bonus = max(0.0, perf.momentum) * 0.5
            # Calibration penalty: penalize poorly calibrated models
            cal_penalty = max(0.0, perf.calibration_error - 0.15)
            raw_weights[perf.model_name] = (
                perf.accuracy * sample_bonus
                + momentum_bonus
                - cal_penalty
            )

        # Normalize to sum to 1
        total_raw = sum(raw_weights.values()) or 1.0
        recommendations = []

        for perf in performances:
            current = current_weights.get(perf.model_name, 1.0 / n)
            raw = raw_weights[perf.model_name]
            target = raw / total_raw

            # Blend: weighted average toward target
            recommended = current * (1 - self.learning_rate) + target * self.learning_rate

            # Floor
            recommended = max(self.min_weight, recommended)

            # Build reason
            reasons = []
            if perf.accuracy < 0.45:
                reasons.append(f"accuracy low ({perf.accuracy:.0%})")
            if perf.accuracy > 0.65:
                reasons.append(f"accuracy high ({perf.accuracy:.0%})")
            if perf.momentum > 0.1:
                reasons.append("improving trend")
            if perf.momentum < -0.1:
                reasons.append("worsening trend")
            if perf.calibration_error > 0.15:
                reasons.append(f"poorly calibrated (error={perf.calibration_error:.2f})")
            if perf.total_predictions < 5:
                reasons.append("insufficient sample")
            reason_str = "; ".join(reasons) if reasons else "maintain"

            recommendations.append(ModelWeightRecommendation(
                model_name=perf.model_name,
                current_weight=round(current, 3),
                recommended_weight=round(recommended, 3),
                adjustment=round(recommended - current, 3),
                reason=reason_str,
            ))

        # Re-normalize recommendations
        total_rec = sum(r.recommended_weight for r in recommendations) or 1.0
        for r in recommendations:
            r.recommended_weight = round(r.recommended_weight / total_rec, 3)

        return recommendations

    def apply_weight_updates(
        self,
        recommendations: list[ModelWeightRecommendation],
        target_weights: dict[str, float],
    ) -> dict[str, float]:
        """Apply recommended weight updates to a weight dictionary."""
        updated = dict(target_weights)
        for rec in recommendations:
            updated[rec.model_name] = rec.recommended_weight
        # Re-normalize
        total = sum(updated.values()) or 1.0
        return {k: v / total for k, v in updated.items()}

    def get_model_rankings(
        self, performances: list[ModelPerformance]
    ) -> list[dict]:
        """Rank models by accuracy and reliability."""
        ranked = sorted(
            performances,
            key=lambda p: (p.accuracy * 0.6 + (1 - p.calibration_error) * 0.4),
            reverse=True,
        )
        return [
            {
                "rank": i + 1,
                "model": p.model_name,
                "accuracy": p.accuracy,
                "cal_error": p.calibration_error,
                "trend": f"{'up' if p.momentum > 0.05 else 'down' if p.momentum < -0.05 else 'stable'}",
                "predictions": p.total_predictions,
            }
            for i, p in enumerate(ranked)
        ]
