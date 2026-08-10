"""BeliefCalibration — recalibrate belief confidence from prediction track record.

The core insight:
    A belief with 80% confidence and 50% actual accuracy is OVERCONFIDENT.
    A belief with 60% confidence and 75% actual accuracy is UNDERCONFIDENT.

This engine:
    1. Computes accuracy for each belief's prediction history
    2. Detects over/under-confidence
    3. Produces calibrated confidence using empirical Bayes-like adjustment
    4. Recommends confidence adjustments

Formula:
    calibrated_confidence = (alpha + correct) / (alpha + beta + total)
    where alpha/beta are the belief's prior parameters.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from src.learning.schemas import (
    BeliefCalibrationResult,
    ScoredPrediction,
)


class BeliefCalibration:
    """Recalibrates belief confidence based on prediction track record."""

    def __init__(self, min_predictions_for_calibration: int = 3):
        self.min_predictions = min_predictions_for_calibration
        self._calibration_history: dict[str, list[dict]] = defaultdict(list)

    def calibrate_belief(
        self,
        belief: Any,
        scored_predictions: list[ScoredPrediction],
    ) -> BeliefCalibrationResult:
        """Calibrate a single belief.

        Args:
            belief: ResearchBelief object with prediction_history.
            scored_predictions: Scored predictions for this belief.

        Returns:
            BeliefCalibrationResult with original vs. calibrated confidence.
        """
        belief_id = getattr(belief, "belief_id", "") or getattr(belief, "id", "")
        title = getattr(belief, "title", "")
        domain_raw = getattr(belief, "domain", "")
        domain = domain_raw.value if hasattr(domain_raw, "value") else str(domain_raw)

        total = len(scored_predictions)
        correct = sum(1 for sp in scored_predictions if sp.outcome.was_correct)
        original_conf = float(getattr(belief, "confidence", 0.5) or 0.5)

        # Use evidence count as prior alpha/beta refinement
        evidence_count = int(getattr(belief, "evidence_count", 0) or 0)
        alpha_prior = max(0.5, evidence_count * 0.1)
        beta_prior = max(0.5, evidence_count * 0.05)

        if total < self.min_predictions:
            return BeliefCalibrationResult(
                belief_id=belief_id,
                belief_title=title,
                domain=domain,
                original_confidence=original_conf,
                original_alpha=alpha_prior,
                original_beta=beta_prior,
                total_predictions=total,
                correct_predictions=correct,
                raw_accuracy=correct / total if total > 0 else 0.5,
                calibrated_confidence=original_conf,
                calibrated_alpha=alpha_prior,
                calibrated_beta=beta_prior,
                calibration_bias=0.0,
                recommendation="insufficient_data",
            )

        # Empirical Bayes calibration
        alpha_post = alpha_prior + correct
        beta_post = beta_prior + (total - correct)
        calibrated_conf = alpha_post / (alpha_post + beta_post) if (alpha_post + beta_post) > 0 else 0.5

        # Smooth toward original to prevent over-fitting small samples
        weight_n = min(1.0, total / 10.0)  # Full weight at 10+ predictions
        final_conf = weight_n * calibrated_conf + (1.0 - weight_n) * original_conf

        # Calibration bias
        raw_accuracy = correct / total if total > 0 else 0.0
        bias = original_conf - raw_accuracy
        is_over = bias > 0.1
        is_under = bias < -0.1

        if is_over:
            recommendation = "decrease_confidence"
        elif is_under:
            recommendation = "increase_confidence"
        else:
            recommendation = "maintain"

        result = BeliefCalibrationResult(
            belief_id=belief_id,
            belief_title=title,
            domain=domain,
            original_confidence=round(original_conf, 3),
            original_alpha=alpha_prior,
            original_beta=beta_prior,
            total_predictions=total,
            correct_predictions=correct,
            raw_accuracy=round(raw_accuracy, 3),
            calibrated_confidence=round(final_conf, 3),
            calibrated_alpha=alpha_post,
            calibrated_beta=beta_post,
            calibration_bias=round(bias, 3),
            is_overconfident=is_over,
            is_underconfident=is_under,
            recommendation=recommendation,
        )

        self._calibration_history[belief_id].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "original": original_conf,
            "calibrated": final_conf,
            "bias": bias,
        })

        return result

    def calibrate_all(
        self,
        beliefs: list[Any],
        all_scored: list[ScoredPrediction],
    ) -> list[BeliefCalibrationResult]:
        """Calibrate all beliefs against their scored predictions."""
        # Group scored predictions by belief_id
        by_belief: dict[str, list[ScoredPrediction]] = defaultdict(list)
        for sp in all_scored:
            bid = sp.outcome.belief_id
            if bid:
                by_belief[bid].append(sp)

        results = []
        for belief in beliefs:
            bid = getattr(belief, "belief_id", "")
            scored = by_belief.get(bid, [])
            result = self.calibrate_belief(belief, scored)
            results.append(result)

        return results

    def get_calibration_summary(
        self, results: list[BeliefCalibrationResult]
    ) -> dict:
        """Summarize calibration results across all beliefs."""
        if not results:
            return {"total": 0, "overconfident": 0, "underconfident": 0, "calibrated": 0}

        calibrated = [r for r in results if r.total_predictions >= self.min_predictions]
        over = [r for r in calibrated if r.is_overconfident]
        under = [r for r in calibrated if r.is_underconfident]
        ok = [r for r in calibrated if not r.is_overconfident and not r.is_underconfident]

        avg_bias = sum(r.calibration_bias for r in calibrated) / len(calibrated) if calibrated else 0

        return {
            "total_beliefs": len(results),
            "calibratable_beliefs": len(calibrated),
            "overconfident": len(over),
            "underconfident": len(under),
            "well_calibrated": len(ok),
            "avg_calibration_bias": round(avg_bias, 3),
            "systemic_bias": (
                "overconfident" if avg_bias > 0.05
                else "underconfident" if avg_bias < -0.05
                else "well_calibrated"
            ),
        }
