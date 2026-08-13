"""ConfidenceOptimizer — Calibrate confidence estimates based on outcomes.

Quality: Overconfident predictions destroy research credibility.
Underconfident predictions are useless for decision-making.

This module tracks the calibration curve: when we say 70% confidence,
do we really get it right 70% of the time?

Output: Calibration adjustments that flow into:
    - HypothesisBuilder confidence estimation
    - MemoWriter confidence reporting
    - Belief system weight updates
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class CalibrationBucket:
    """Track predictions in a confidence bucket (e.g., 70-80%)."""

    bucket_low: float = 0.0
    bucket_high: float = 0.0
    total_predictions: int = 0
    correct_predictions: int = 0
    observed_accuracy: float = 0.0
    expected_accuracy: float = 0.0  # Midpoint of bucket
    is_calibrated: bool = True
    adjustment: float = 0.0  # How much to adjust (positive = underconfident)


@dataclass
class CalibrationReport:
    """Complete confidence calibration report."""

    report_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    total_predictions: int = 0
    buckets: list[CalibrationBucket] = field(default_factory=list)

    # Overall metrics
    expected_calibration_error: float = 0.0  # ECE
    max_calibration_error: float = 0.0
    overconfidence_bias: bool = False  # True if systematically overconfident
    average_calibration_bias: float = 0.0  # Positive = overconfident

    # Recommendations
    global_adjustment: float = 0.0  # Global confidence shift
    per_bucket_adjustments: dict = field(default_factory=dict)
    # {bucket_label: adjustment}

    recommendations: list[str] = field(default_factory=list)


class ConfidenceOptimizer:
    """Track and optimize confidence calibration.

    The goal: p(confidence) ≈ actual_accuracy.

    When we say "80% confidence", we should be right ~80% of the time.
    """

    # Bucket definitions
    BUCKETS = [
        (0.0, 0.1),
        (0.1, 0.2),
        (0.2, 0.3),
        (0.3, 0.4),
        (0.4, 0.5),
        (0.5, 0.6),
        (0.6, 0.7),
        (0.7, 0.8),
        (0.8, 0.9),
        (0.9, 1.0),
    ]

    def __init__(self):
        self.prediction_history: list[dict] = []
        # [{confidence, was_correct, domain, ...}]

    def record(self, confidence: float, was_correct: bool, domain: str = ""):
        """Record a single prediction outcome for calibration tracking."""
        self.prediction_history.append(
            {
                "confidence": confidence,
                "was_correct": was_correct,
                "domain": domain,
                "recorded_at": datetime.now(UTC).isoformat(),
            }
        )

    def record_batch(self, predictions_outcomes: list[dict]):
        """Record multiple prediction outcomes.

        Args:
            predictions_outcomes: [{confidence, was_correct}, ...]
        """
        for po in predictions_outcomes:
            self.record(
                confidence=float(po.get("confidence", 0.5)),
                was_correct=bool(po.get("was_correct", False)),
                domain=po.get("domain", ""),
            )

    def calibrate(self) -> CalibrationReport:
        """Produce calibration analysis and adjustment recommendations.

        Returns:
            CalibrationReport with ECE, bucket-level analysis, adjustments
        """
        if not self.prediction_history:
            return CalibrationReport(
                report_id=f"CR_{str(uuid.uuid4())[:8]}",
                recommendations=["No prediction history — cannot calibrate"],
            )

        report = CalibrationReport(
            report_id=f"CR_{str(uuid.uuid4())[:8]}",
            total_predictions=len(self.prediction_history),
        )

        # 1. Bucket predictions
        bucket_data = defaultdict(list)
        for pred in self.prediction_history:
            conf = pred["confidence"]
            for low, high in self.BUCKETS:
                if low <= conf < high:
                    bucket_data[(low, high)].append(pred)
                    break

        # 2. Compute per-bucket calibration
        total_ece = 0.0
        total_weight = 0.0
        max_error = 0.0
        overconfident_buckets = 0

        for (low, high), preds in bucket_data.items():
            total = len(preds)
            correct = sum(1 for p in preds if p["was_correct"])
            observed = correct / total if total > 0 else 0.0
            expected = (low + high) / 2

            error = expected - observed
            is_cal = abs(error) < 0.15

            bucket = CalibrationBucket(
                bucket_low=low,
                bucket_high=high,
                total_predictions=total,
                correct_predictions=correct,
                observed_accuracy=round(observed, 2),
                expected_accuracy=round(expected, 2),
                is_calibrated=is_cal,
                adjustment=round(error, 2),
            )
            report.buckets.append(bucket)

            # ECE contribution
            total_ece += total * abs(error)
            total_weight += total
            max_error = max(max_error, abs(error))

            if error > 0 and total > 0:
                overconfident_buckets += 1

        report.expected_calibration_error = (
            round(total_ece / total_weight, 3) if total_weight > 0 else 0.0
        )
        report.max_calibration_error = round(max_error, 3)

        # 3. Aggregate bias
        all_errors = []
        for pred in self.prediction_history:
            all_errors.append(pred["confidence"] - (1.0 if pred["was_correct"] else 0.0))
        report.average_calibration_bias = (
            round(sum(all_errors) / len(all_errors), 3) if all_errors else 0.0
        )
        report.overconfidence_bias = report.average_calibration_bias > 0.1

        # 4. Per-bucket adjustments
        for bucket in report.buckets:
            label = f"{bucket.bucket_low:.0%}-{bucket.bucket_high:.0%}"
            if not bucket.is_calibrated:
                report.per_bucket_adjustments[label] = bucket.adjustment

        # 5. Global adjustment
        report.global_adjustment = round(-report.average_calibration_bias * 0.5, 2)

        # 6. Recommendations
        report.recommendations = self._build_recommendations(report)

        return report

    def adjust_confidence(self, raw_confidence: float) -> float:
        """Apply calibration adjustment to a raw confidence estimate.

        Args:
            raw_confidence: The raw confidence from the reasoning pipeline

        Returns:
            Calibrated confidence with adjustment applied
        """
        if len(self.prediction_history) < 10:
            return raw_confidence  # Not enough data to calibrate

        # Find applicable bucket adjustment
        for low, high in self.BUCKETS:
            if low <= raw_confidence < high:
                bucket_preds = [p for p in self.prediction_history if low <= p["confidence"] < high]
                if len(bucket_preds) >= 5:
                    correct = sum(1 for p in bucket_preds if p["was_correct"])
                    observed = correct / len(bucket_preds)
                    expected = (low + high) / 2
                    adjustment = expected - observed
                    calibrated = raw_confidence - adjustment * 0.5  # Half-step adjustment
                    return round(max(0.05, min(0.95, calibrated)), 2)
                break

        return raw_confidence

    def get_calibration_curve(self) -> dict[float, float]:
        """Get the calibration curve: expected_accuracy → observed_accuracy."""
        curve = {}
        for low, high in self.BUCKETS:
            bucket_preds = [p for p in self.prediction_history if low <= p["confidence"] < high]
            if bucket_preds:
                expected = (low + high) / 2
                observed = sum(1 for p in bucket_preds if p["was_correct"]) / len(bucket_preds)
                curve[round(expected, 2)] = round(observed, 2)
        return curve

    def reset(self):
        """Clear prediction history."""
        self.prediction_history = []

    # ── Internal ──

    def _build_recommendations(self, report: CalibrationReport) -> list[str]:
        """Build calibration recommendations."""
        recs = []

        if report.overconfidence_bias:
            recs.append(
                f"Systematically overconfident (bias: {report.average_calibration_bias:+.3f}). "
                "Reduce all confidence estimates by {abs(report.global_adjustment):.0%} "
                "until recalibrated."
            )

        if report.expected_calibration_error > 0.1:
            recs.append(
                f"ECE ({report.expected_calibration_error:.3f}) is elevated. "
                "Review confidence estimation methodology."
            )

        # Bucket-specific
        for bucket in report.buckets:
            if not bucket.is_calibrated and bucket.total_predictions >= 3:
                label = f"{bucket.bucket_low:.0%}-{bucket.bucket_high:.0%}"
                if bucket.adjustment > 0:
                    recs.append(
                        f"In {label} bucket: overconfident by {bucket.adjustment:.0%} "
                        f"({bucket.correct_predictions}/{bucket.total_predictions} correct vs "
                        f"{bucket.expected_accuracy:.0%} expected)"
                    )
                else:
                    recs.append(
                        f"In {label} bucket: underconfident by {abs(bucket.adjustment):.0%} "
                        f"({bucket.correct_predictions}/{bucket.total_predictions} correct)"
                    )

        if not report.overconfidence_bias and report.expected_calibration_error < 0.05:
            recs.append("Confidence calibration is well-tuned. No adjustment needed.")

        return recs
