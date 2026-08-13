"""Calibration Engine — V3 standalone calibration wrapper.

Wraps ConfidenceCalibrator and adds:
    - Calibration curve building from historical outcome data
    - Platt scaling / isotonic regression parameter management
    - Time-decayed dimensional accuracy tracking
    - Calibration health diagnostics
    - Curve parameter persistence and evolution

Design:
    CalibrationEngine is a higher-level orchestrator that consumes outcome
    history and produces calibrated confidences. It wraps the existing
    ConfidenceCalibrator for single-hypothesis calibration and adds:
        1. build_calibration_curve() — learning a reliability diagram
        2. get_calibration_health() — diagnosing over/under-confidence
        3. evolve_curves() — time-weighted recalibration

    This is the V3 Milestone F (Release 3.2) component.
"""

from __future__ import annotations

from collections import defaultdict

from src.calibration.confidence_calibrator import ConfidenceCalibrator
from src.learning.learning_engine import LearningEngine
from src.schemas.calibration import CalibratedConfidenceSet, ConfidenceCalibration
from src.schemas.hypothesis import HypothesisSchema, HypothesisSet
from src.schemas.outcome import PredictionOutcome
from src.schemas.reflection import ReflectionSet
from src.shared.logging import get_logger

logger = get_logger(__name__)

# ── Calibration Bucket Constants ──────────────────────────────────────────────

# Buckets for reliability diagram: bin predicted confidence into ranges
_RELIABILITY_BUCKETS = [
    (0.0, 0.20),  # Bucket 1: 0-20%
    (0.20, 0.40),  # Bucket 2: 20-40%
    (0.40, 0.60),  # Bucket 3: 40-60%
    (0.60, 0.80),  # Bucket 4: 60-80%
    (0.80, 1.00),  # Bucket 5: 80-100%
]

# Ideal calibration: predicted confidence ≈ observed accuracy in each bin
# Perfect calibration means the line y=x on the reliability diagram.

# ── Calibration Engine ────────────────────────────────────────────────────────


class CalibrationEngine:
    """V3 Calibration Engine — learns calibration curves from outcome history.

    Responsibilities:
        1. Build reliability diagrams from historical outcomes
        2. Calibrate hypothesis sets (delegates to ConfidenceCalibrator by default)
        3. Compute calibration metrics (ECE, MCE, overconfidence index)
        4. Evolve calibration parameters as more data arrives
        5. Diagnose calibration health and suggest adjustments

    Example:
        engine = CalibrationEngine(learning_engine=le)
        engine.build_calibration_curve(outcomes)
        health = engine.get_calibration_health()
        print(f"Expected Calibration Error: {health['ece']:.3f}")
    """

    def __init__(
        self,
        learning_engine: LearningEngine | None = None,
        calibrator: ConfidenceCalibrator | None = None,
    ) -> None:
        self._learning = learning_engine
        self._calibrator = calibrator or ConfidenceCalibrator(learning_engine)

        # Calibration curve data: bucket_key → {predicted_mean, observed_accuracy, count}
        self._curve: dict[str, dict] = {}

        # Time-weighted dimensional accuracy: dimension → accuracy_float
        self._dim_accuracy: dict[str, float] = {}

        # Overall calibration metrics
        self._ece: float = 0.0  # Expected Calibration Error
        self._mce: float = 0.0  # Maximum Calibration Error
        self._overconfidence_index: float = 0.0  # >0 = overconfident, <0 = underconfident

        # History of calibration snapshots
        self._history: list[dict] = []

    # ── Core Calibration (delegation) ──────────────────────────────────────

    def calibrate_hypothesis(
        self,
        hypothesis: HypothesisSchema,
        reflection_confidence: float,
    ) -> ConfidenceCalibration:
        """Calibrate a single hypothesis (delegates to ConfidenceCalibrator)."""
        return self._calibrator.calibrate_hypothesis(hypothesis, reflection_confidence)

    def calibrate_set(
        self,
        hypotheses: HypothesisSet,
        reflections: ReflectionSet,
        run_id: str = "unknown",
    ) -> CalibratedConfidenceSet:
        """Calibrate all hypotheses in a set."""
        return self._calibrator.calibrate_set(hypotheses, reflections, run_id)

    # ── Reliability Diagram — Calibration Curve Building ───────────────────

    def build_calibration_curve(
        self,
        outcomes: list[PredictionOutcome],
    ) -> dict[str, dict]:
        """Build a reliability diagram from historical prediction outcomes.

        Groups predictions into confidence buckets and computes observed
        accuracy within each bucket. This is the core calibration curve
        that determines whether the model is well-calibrated.

        A well-calibrated model has predicted_confidence ≈ observed_accuracy
        in every bucket (the y=x line).

        Args:
            outcomes: All evaluated PredictionOutcome records.

        Returns:
            Dict with bucket summaries, ECE, and calibration curve data.
            Keys: 'buckets', 'ece', 'mce', 'overconfidence_index', 'ideal_line'.
        """
        evaluated = [o for o in outcomes if o.verdict is not None and o.verdict.value != "pending"]
        if not evaluated:
            return self._empty_curve()

        # Bucket outcomes by predicted confidence
        buckets: dict[int, list[PredictionOutcome]] = defaultdict(list)

        for outcome in evaluated:
            conf = outcome.predicted_confidence
            for idx, (low, high) in enumerate(_RELIABILITY_BUCKETS):
                if conf > low and conf <= high:
                    buckets[idx].append(outcome)
                    break
            else:
                # Edge case: confidence == 0 or > 1.0
                if conf <= 0:
                    buckets[0].append(outcome)
                else:
                    buckets[4].append(outcome)

        # Compute accuracy per bucket
        curve_data: dict[str, dict] = {}
        bucket_summaries = []
        total_weighted_error = 0.0
        max_error = 0.0
        total_count = len(evaluated)

        for idx, (low, high) in enumerate(_RELIABILITY_BUCKETS):
            bucket_outcomes = buckets.get(idx, [])
            count = len(bucket_outcomes)
            bin_center = (low + high) / 2

            if count > 0:
                correct = sum(1 for o in bucket_outcomes if o.is_correct)
                observed_accuracy = correct / count
                predicted_mean = sum(o.predicted_confidence for o in bucket_outcomes) / count
            else:
                observed_accuracy = 0.0
                predicted_mean = bin_center

            error = abs(predicted_mean - observed_accuracy)
            total_weighted_error += error * count
            max_error = max(max_error, error)

            bucket_key = f"bucket_{idx}_[{low:.0f}-{high:.0f}]"
            curve_data[bucket_key] = {
                "range": f"{low:.0%}-{high:.0%}",
                "predicted_mean": round(predicted_mean, 4),
                "observed_accuracy": round(observed_accuracy, 4),
                "count": count,
                "calibration_error": round(error, 4),
                "status": self._bucket_status(predicted_mean, observed_accuracy, count),
            }
            bucket_summaries.append(curve_data[bucket_key])

        # ECE = weighted average of calibration errors
        self._ece = round(total_weighted_error / total_count, 4) if total_count > 0 else 0.0
        self._mce = round(max_error, 4)

        # Overconfidence index: sum of (predicted_mean - observed_accuracy) * count / total
        # Positive = overconfident, Negative = underconfident
        overconfidence_sum = 0.0
        for b in bucket_summaries:
            if b["count"] > 0:
                overconfidence_sum += (b["predicted_mean"] - b["observed_accuracy"]) * b["count"]
        self._overconfidence_index = (
            round(overconfidence_sum / total_count, 4) if total_count > 0 else 0.0
        )

        # Update per-dimension accuracy
        self._update_dim_accuracy(evaluated)

        # Snapshot history
        self._history.append(
            {
                "ece": self._ece,
                "mce": self._mce,
                "overconfidence_index": self._overconfidence_index,
                "total_outcomes": total_count,
                "bucket_count": len(bucket_summaries),
                "bucket_summaries": bucket_summaries,
            }
        )

        self._curve = curve_data

        logger.info(
            "calibration_curve_built",
            extra={
                "ece": self._ece,
                "mce": self._mce,
                "overconfidence": self._overconfidence_index,
                "total_outcomes": total_count,
            },
        )

        return {
            "buckets": curve_data,
            "ece": self._ece,
            "mce": self._mce,
            "overconfidence_index": self._overconfidence_index,
            "total_outcomes": total_count,
            "ideal_line": "y=x (perfect calibration)",
        }

    # ── Calibration Health ─────────────────────────────────────────────────

    def get_calibration_health(self) -> dict:
        """Diagnose the current calibration health.

        Returns a dict with metrics and a health assessment.

        Returns:
            Dict with keys: ece, mce, overconfidence_index, health_status,
            severity, recommendations.
        """
        # Determine health status
        if self._ece < 0.05:
            health_status = "excellent"
            severity = "none"
        elif self._ece < 0.10:
            health_status = "good"
            severity = "low"
        elif self._ece < 0.15:
            health_status = "fair"
            severity = "medium"
        elif self._ece < 0.25:
            health_status = "poor"
            severity = "high"
        else:
            health_status = "critical"
            severity = "critical"

        # Generate recommendations
        recommendations = self._generate_recommendations(health_status)

        # Per-dimension breakdown
        dim_breakdown = self._build_dim_breakdown()

        return {
            "ece": self._ece,
            "mce": self._mce,
            "overconfidence_index": self._overconfidence_index,
            "health_status": health_status,
            "severity": severity,
            "ideal_ece_target": "< 0.05",
            "curve_buckets": len(self._curve),
            "dim_accuracy": self._dim_accuracy,
            "dim_breakdown": dim_breakdown,
            "recommendations": recommendations,
            "history_size": len(self._history),
        }

    def get_curve(self) -> dict[str, dict]:
        """Return the current calibration curve data."""
        return self._curve

    # ── Evolution ──────────────────────────────────────────────────────────

    def evolve_curves(
        self,
        new_outcomes: list[PredictionOutcome],
        alpha: float = 0.3,
    ) -> dict:
        """Evolve calibration curves with new outcome data.

        Uses exponential moving average with weight alpha for new data.
        This allows curves to adapt while being robust to noise.

        Args:
            new_outcomes: New outcome records to incorporate.
            alpha: Weight for new data (0-1, default 0.3 = 30% new, 70% old).

        Returns:
            Updated calibration health dict.
        """
        # Build curve from new outcomes only
        new_curve = self._build_curve_from_outcomes(new_outcomes)

        if not self._curve:
            # First curve: just use the new data
            self.build_calibration_curve(new_outcomes)
        else:
            # Merge with EMA
            for bucket_key, new_data in new_curve.items():
                if bucket_key in self._curve:
                    old_data = self._curve[bucket_key]
                    old_count = old_data["count"]
                    new_count = new_data["count"]
                    total = old_count + new_count

                    if total > 0:
                        new_weight = (new_count / total) * alpha + (1 - alpha) * 0.5
                        old_weight = 1 - new_weight

                        # EMA update of accuracies
                        merged_acc = (
                            old_data["observed_accuracy"] * old_weight
                            + new_data["observed_accuracy"] * new_weight
                        )
                        merged_pred_mean = (
                            old_data["predicted_mean"] * old_weight
                            + new_data["predicted_mean"] * new_weight
                        )
                        error = abs(merged_pred_mean - merged_acc)

                        self._curve[bucket_key] = {
                            "range": old_data["range"],
                            "predicted_mean": round(merged_pred_mean, 4),
                            "observed_accuracy": round(merged_acc, 4),
                            "count": total,
                            "calibration_error": round(error, 4),
                            "status": self._bucket_status(merged_pred_mean, merged_acc, total),
                        }

            # Recompute aggregate metrics
            self._recompute_aggregates()

        return self.get_calibration_health()

    # ── Scaling ────────────────────────────────────────────────────────────

    def platt_scale(
        self,
        raw_confidence: float,
        dimension: str | None = None,
    ) -> float:
        """Apply Platt scaling to adjust a raw confidence.

        Platt scaling learns A * logit(conf) + B parameters from outcome data.
        This is a simplified version that uses calibration curve data.

        Args:
            raw_confidence: Uncalibrated confidence (0-1).
            dimension: Optional dimension for dim-specific scaling.

        Returns:
            Platt-scaled confidence (0-1).
        """
        if not self._curve:
            return raw_confidence

        # Find which bucket this confidence falls into
        bucket_data = None
        for key, data in self._curve.items():
            range_str = data["range"]
            low_str, high_str = range_str.split("-")
            low = float(low_str.strip("%")) / 100
            high = float(high_str.strip("%")) / 100

            if low < raw_confidence <= high:
                bucket_data = data
                break

        if bucket_data is None:
            return raw_confidence

        # Adjust: if bucket is overconfident, reduce; if underconfident, boost
        bias = bucket_data["predicted_mean"] - bucket_data["observed_accuracy"]
        scaled = raw_confidence - bias * 0.5  # damped correction

        return round(max(0.01, min(0.99, scaled)), 4)

    # ── Private Helpers ────────────────────────────────────────────────────

    def _build_curve_from_outcomes(
        self,
        outcomes: list[PredictionOutcome],
    ) -> dict[str, dict]:
        """Build a temporary curve from outcomes without updating engine state."""
        # Save current state
        saved_curve = self._curve
        saved_ece = self._ece
        saved_mce = self._mce
        saved_oi = self._overconfidence_index

        # Build from new outcomes
        _result = self.build_calibration_curve(outcomes)

        # Restore previous state (caller handles merging)
        # Actually, build_calibration_curve updates state — let's save the new curve and restore
        new_curve = self._curve
        self._curve = saved_curve
        self._ece = saved_ece
        self._mce = saved_mce
        self._overconfidence_index = saved_oi

        return new_curve

    def _recompute_aggregates(self) -> None:
        """Recompute ECE, MCE, and overconfidence index from current curve."""
        total_weighted_error = 0.0
        max_error = 0.0
        total_count = 0
        overconfidence_sum = 0.0

        for data in self._curve.values():
            count = data["count"]
            error = data["calibration_error"]
            total_weighted_error += error * count
            max_error = max(max_error, error)
            total_count += count
            if count > 0:
                overconfidence_sum += (data["predicted_mean"] - data["observed_accuracy"]) * count

        if total_count > 0:
            self._ece = round(total_weighted_error / total_count, 4)
            self._overconfidence_index = round(overconfidence_sum / total_count, 4)
        self._mce = round(max_error, 4)

    def _update_dim_accuracy(self, outcomes: list[PredictionOutcome]) -> None:
        """Update per-dimension accuracy from outcomes."""
        dim_counts: dict[str, int] = defaultdict(int)
        dim_correct: dict[str, int] = defaultdict(int)

        for outcome in outcomes:
            if outcome.dimension:
                dim_counts[outcome.dimension] += 1
                if outcome.is_correct:
                    dim_correct[outcome.dimension] += 1

        for dim, total in dim_counts.items():
            self._dim_accuracy[dim] = round(dim_correct[dim] / total, 4) if total > 0 else 0.5

    def _build_dim_breakdown(self) -> dict[str, dict]:
        """Build per-dimension calibration status."""
        breakdown = {}
        for dim, acc in self._dim_accuracy.items():
            if acc >= 0.65:
                status = "well_calibrated"
            elif acc >= 0.50:
                status = "moderate"
            elif acc >= 0.35:
                status = "needs_adjustment"
            else:
                status = "poor"
            breakdown[dim] = {
                "accuracy": acc,
                "status": status,
            }
        return breakdown

    @staticmethod
    def _bucket_status(
        predicted_mean: float,
        observed_accuracy: float,
        count: int,
    ) -> str:
        """Classify a calibration bucket's status."""
        if count == 0:
            return "empty"
        error = predicted_mean - observed_accuracy
        if abs(error) < 0.05:
            return "well_calibrated"
        elif error > 0.10:
            return "overconfident"
        elif error < -0.10:
            return "underconfident"
        elif error > 0.05:
            return "slightly_overconfident"
        else:
            return "slightly_underconfident"

    @staticmethod
    def _empty_curve() -> dict:
        """Return an empty calibration curve structure."""
        empty_buckets = {}
        for idx, (low, high) in enumerate(_RELIABILITY_BUCKETS):
            bucket_key = f"bucket_{idx}_[{low:.0f}-{high:.0f}]"
            empty_buckets[bucket_key] = {
                "range": f"{low:.0%}-{high:.0%}",
                "predicted_mean": 0.0,
                "observed_accuracy": 0.0,
                "count": 0,
                "calibration_error": 0.0,
                "status": "empty",
            }
        return {
            "buckets": empty_buckets,
            "ece": 0.0,
            "mce": 0.0,
            "overconfidence_index": 0.0,
            "total_outcomes": 0,
            "ideal_line": "y=x (perfect calibration)",
        }

    def _generate_recommendations(self, health_status: str) -> list[str]:
        """Generate actionable recommendations based on calibration health."""
        recs: list[str] = []

        if health_status in ("excellent", "good"):
            recs.append(
                "Calibration is healthy. Continue collecting outcomes " "to maintain the curve."
            )
            return recs

        if self._overconfidence_index > 0.05:
            recs.append(
                f"Agent is overconfident (index={self._overconfidence_index:.3f}). "
                f"Apply downward confidence adjustment of approximately "
                f"{self._overconfidence_index:.0%} across all dimensions."
            )

        if self._overconfidence_index < -0.05:
            recs.append(
                f"Agent is underconfident (index={self._overconfidence_index:.3f}). "
                f"Historical accuracy exceeds predicted confidence — "
                f"confidence can be modestly increased."
            )

        if health_status in ("poor", "critical"):
            recs.append(
                f"ECE is {self._ece:.3f} — above the acceptable threshold. "
                f"Consider: (1) reducing prediction frequency, "
                f"(2) increasing evidence requirements, or "
                f"(3) restricting predictions to well-calibrated dimensions."
            )

            # Identify problematic dimensions
            for dim, acc in self._dim_accuracy.items():
                if acc < 0.40:
                    recs.append(
                        f"Dimension '{dim}' has very low accuracy ({acc:.0%}). "
                        f"Consider freezing predictions on this dimension."
                    )

        return recs

    def set_learning_engine(self, engine: LearningEngine) -> None:
        """Inject a learning engine for historical accuracy data."""
        self._learning = engine
        self._calibrator.set_learning_engine(engine)

    @property
    def ece(self) -> float:
        """Expected Calibration Error."""
        return self._ece

    @property
    def mce(self) -> float:
        """Maximum Calibration Error."""
        return self._mce

    @property
    def is_calibrated(self) -> bool:
        """Whether the engine has built at least one calibration curve."""
        return len(self._history) > 0 and self._ece < 0.15
