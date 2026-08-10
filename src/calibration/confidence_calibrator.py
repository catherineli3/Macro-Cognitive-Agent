"""Confidence Calibrator — v2.0 core module.

Calibrates hypothesis confidence by combining:
    1. Reflection confidence (current evidence quality)
    2. Historical accuracy (how often was this dimension right?)
    3. Dimension weight (learned reliability)

Outputs a calibrated confidence that reflects BOTH current evidence
AND the Agent's historical track record.
"""

from __future__ import annotations

from typing import Optional

from src.learning.learning_engine import LearningEngine
from src.schemas.calibration import CalibratedConfidenceSet, ConfidenceCalibration
from src.schemas.hypothesis import HypothesisSchema, HypothesisSet
from src.schemas.reflection import ReflectionSet
from src.shared.logging import get_logger

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
_ACCURACY_WEIGHT: float = 0.30  # How much historical accuracy matters
_EVIDENCE_WEIGHT: float = 0.50  # How much current evidence matters
_DIM_WEIGHT_FACTOR: float = 0.20  # How much learned dimension weight matters


class ConfidenceCalibrator:
    """Calibrates raw (Reflection) confidence against historical accuracy.

    Design:
        calibrated = raw * evidence_weight
                   + historical_accuracy * accuracy_weight
                   + dimension_weight * dim_weight_factor

        The calibrated confidence never exceeds raw reflection confidence,
        but can be SIGNIFICANTLY lower when historical accuracy is poor.

    Example:
        Raw (reflection) = 0.82
        Historical accuracy = 0.40 (only 40% correct on this dimension)
        Dimension weight = 0.55

        calibrated = 0.82*0.50 + 0.40*0.30 + 0.55*0.20 = 0.41 + 0.12 + 0.11 = 0.64
        → downward adjustment of -0.18
    """

    def __init__(self, learning_engine: Optional[LearningEngine] = None) -> None:
        self._learning = learning_engine

    def set_learning_engine(self, engine: LearningEngine) -> None:
        """Inject learning engine for historical accuracy data."""
        self._learning = engine

    def calibrate_hypothesis(
        self,
        hypothesis: HypothesisSchema,
        reflection_confidence: float,
    ) -> ConfidenceCalibration:
        """Calibrate a single hypothesis's confidence.

        Args:
            hypothesis: The hypothesis being calibrated.
            reflection_confidence: The raw confidence from Reflection.

        Returns:
            ConfidenceCalibration with calibrated confidence.
        """
        dim = hypothesis.dimension

        # Get historical accuracy from learning engine
        historical_acc = 0.5
        dim_weight = 0.5
        total_tracked = 0

        if self._learning:
            historical_acc = self._learning.get_accuracy(dim)
            dim_weight = self._learning.get_weight(dim)

            # Get total tracked from weights
            for bw in self._learning.get_weights():
                if bw.dimension.lower() == dim.lower():
                    total_tracked = bw.total_predictions
                    break

        # Calibrated confidence formula
        calibrated = (
            reflection_confidence * _EVIDENCE_WEIGHT
            + historical_acc * _ACCURACY_WEIGHT
            + dim_weight * _DIM_WEIGHT_FACTOR
        )

        # Never exceed raw confidence (optimism cap)
        calibrated = min(reflection_confidence, calibrated)
        calibrated = round(max(0.05, min(1.0, calibrated)), 4)
        delta = round(reflection_confidence - calibrated, 4)

        # Build rationale
        rationale = self._build_rationale(
            reflection_confidence, historical_acc, dim_weight, calibrated, delta, dim,
        )

        return ConfidenceCalibration(
            hypothesis_id=hypothesis.hypothesis_id,
            dimension=dim,
            raw_confidence=reflection_confidence,
            historical_accuracy=round(historical_acc, 4),
            dimension_weight=round(dim_weight, 4),
            calibrated_confidence=calibrated,
            calibration_delta=delta,
            calibration_rationale=rationale,
            calibration_method="weighted_blend" if abs(delta) > 0.01 else "none",
            total_outcomes_tracked=total_tracked,
        )

    def calibrate_set(
        self,
        hypotheses: HypothesisSet,
        reflections: ReflectionSet,
        run_id: str = "unknown",
    ) -> CalibratedConfidenceSet:
        """Calibrate all hypotheses in a set.

        Args:
            hypotheses: All generated hypotheses.
            reflections: Reflection outputs with raw confidences.
            run_id: Pipeline run identifier.

        Returns:
            CalibratedConfidenceSet with all calibrations.
        """
        calibrations: list[ConfidenceCalibration] = []

        for hyp in hypotheses.hypotheses:
            # Find matching reflection report
            ref_conf = hyp.confidence  # Default: use hypothesis confidence
            for report in reflections.reports:
                if report.hypothesis_id == hyp.hypothesis_id:
                    ref_conf = report.updated_confidence
                    break

            cal = self.calibrate_hypothesis(hyp, ref_conf)
            calibrations.append(cal)

        # Global calibration factor: average calibrated / average raw
        if calibrations:
            avg_raw = sum(c.raw_confidence for c in calibrations) / len(calibrations)
            avg_cal = sum(c.calibrated_confidence for c in calibrations) / len(calibrations)
            global_factor = round(avg_cal / avg_raw, 4) if avg_raw > 0 else 1.0
        else:
            global_factor = 1.0

        logger.info(
            "calibration_completed",
            extra={
                "count": len(calibrations),
                "global_factor": global_factor,
            },
        )

        return CalibratedConfidenceSet(
            run_id=run_id,
            calibrations=calibrations,
            global_calibration_factor=global_factor,
        )

    @staticmethod
    def _build_rationale(
        raw: float,
        historical: float,
        weight: float,
        calibrated: float,
        delta: float,
        dimension: str,
    ) -> str:
        """Build a human-readable rationale for the calibration."""
        parts: list[str] = []

        if abs(delta) < 0.02:
            return (
                f"Reflection confidence ({raw:.0%}) aligns with historical accuracy "
                f"on {dimension} ({historical:.0%} over tracked outcomes). "
                f"No significant adjustment required."
            )

        if delta > 0.05:
            parts.append(
                f"Confidence adjusted DOWN from {raw:.0%} to {calibrated:.0%} "
                f"(Δ={delta:+.0%}). "
            )
            if historical < 0.45:
                parts.append(
                    f"Historical accuracy on {dimension} is only {historical:.0%} "
                    f"— the Agent has been wrong more often than right on this dimension. "
                )
            if weight < 0.4:
                parts.append(
                    f"The learned reliability weight for {dimension} is low ({weight:.0%}), "
                    f"indicating persistent prediction challenges. "
                )
            parts.append("Raw reflection confidence has been tempered by the track record.")
        elif delta < -0.02:
            parts.append(
                f"Confidence adjusted UP from {raw:.0%} to {calibrated:.0%} "
                f"(Δ={delta:+.0%}). "
            )
            if historical > 0.65:
                parts.append(
                    f"Historical accuracy on {dimension} is {historical:.0%} "
                    f"— the Agent has a solid track record here. "
                )
            parts.append("Historical performance supports stronger conviction than reflection alone suggests.")
        else:
            parts.append(
                f"Confidence slightly adjusted from {raw:.0%} to {calibrated:.0%} "
                f"(Δ={delta:+.0%}). Reflection and history are broadly aligned."
            )

        return "".join(parts)
