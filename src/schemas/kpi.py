"""V3 KPI Schemas — Four-Component KPI System (DDR-V3-004).

Key design:
    - 4 equally-weighted KPIs on rolling 30d/90d/all-time windows
    - KPI-1: Hypothesis Accuracy (source: Hypothesis Library average score)
    - KPI-2: Prediction Error (Directional Accuracy, MAE, RMSE)
    - KPI-3: Confidence Calibration (ECE, Brier Score)
    - KPI-4: Learning Speed (Error Recurrence Rate, Time-to-Correction)
    - Regression gate blocks any deployment that degrades any KPI > threshold
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

# ── Rolling Window ───────────────────────────────────────────────────────────


class WindowPeriod(str, Enum):
    D30 = "30d"
    D90 = "90d"
    ALL_TIME = "all_time"


# ── Individual KPI Metrics ───────────────────────────────────────────────────


class KPI1_HypothesisAccuracy(BaseModel):
    """KPI-1: Hypothesis Library quality (DDR-V3-010).

    Source: Hypothesis Library average scores.
    """

    library_avg_score: float = Field(default=0.5, ge=0.0, le=1.0)
    top3_accuracy: float = Field(default=0.5, ge=0.0, le=1.0)
    deprecation_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    score_trajectory_slope: float = Field(default=0.0)
    active_hypotheses: int = Field(default=0, ge=0)
    total_hypotheses: int = Field(default=0, ge=0)

    @property
    def composite_score(self) -> float:
        """Weighted composite of sub-metrics."""
        return (
            0.40 * self.library_avg_score
            + 0.30 * self.top3_accuracy
            + 0.20 * (1.0 - self.deprecation_rate)
            + 0.10 * max(0.0, min(1.0, 0.5 + self.score_trajectory_slope * 10))
        )


class KPI2_PredictionError(BaseModel):
    """KPI-2: Prediction accuracy metrics."""

    directional_accuracy: float = Field(default=0.5, ge=0.0, le=1.0)
    mae: float = Field(default=0.0, ge=0.0)
    rmse: float = Field(default=0.0, ge=0.0)
    total_predictions: int = Field(default=0, ge=0)
    correct_predictions: int = Field(default=0, ge=0)
    primary_accuracy: float = Field(default=0.5, ge=0.0, le=1.0)
    secondary_accuracy: float = Field(default=0.5, ge=0.0, le=1.0)

    @property
    def composite_score(self) -> float:
        """Higher is better (normalized)."""
        return (
            0.50 * self.directional_accuracy
            + 0.30 * max(0.0, 1.0 - min(self.mae, 1.0))
            + 0.20 * max(0.0, 1.0 - min(self.rmse, 1.0))
        )


class KPI3_ConfidenceCalibration(BaseModel):
    """KPI-3: Confidence calibration quality."""

    ece: float = Field(default=0.25, ge=0.0, le=1.0, description="Expected Calibration Error")
    brier_score: float = Field(default=0.25, ge=0.0, le=1.0)
    calibration_curve_points: int = Field(default=0, ge=0)
    overconfidence_ratio: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Ratio of predictions where confidence > accuracy",
    )

    @property
    def composite_score(self) -> float:
        """Higher is better: 1.0 - average calibration error."""
        return 1.0 - (0.50 * self.ece + 0.50 * self.brier_score)


class KPI4_LearningSpeed(BaseModel):
    """KPI-4: How fast does the system learn from errors?

    DDR-V3-004: This validates the entire closed loop.
    Requires ≥200 LearningLog entries to compute meaningfully.
    """

    error_recurrence_rate: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Fraction of errors that are repeats of prior errors",
    )
    time_to_correction_days: float = Field(
        default=30.0,
        ge=0.0,
        description="Average days from first error to pattern fix",
    )
    pattern_fix_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of detected patterns that have been addressed",
    )
    total_errors_classified: int = Field(default=0, ge=0)
    unique_error_patterns: int = Field(default=0, ge=0)
    patterns_fixed: int = Field(default=0, ge=0)
    is_significant: bool = Field(
        default=False,
        description="Whether >=200 entries exist for meaningful computation",
    )

    @property
    def composite_score(self) -> float:
        """Higher is better."""
        if not self.is_significant:
            return 0.5  # Neutral until meaningful
        return (
            0.40 * (1.0 - self.error_recurrence_rate)
            + 0.30 * max(0.0, 1.0 - self.time_to_correction_days / 90.0)
            + 0.30 * self.pattern_fix_rate
        )


# ── Four-KPI Report ──────────────────────────────────────────────────────────


class FourKPIReport(BaseModel):
    """Complete 4-KPI dashboard for a specific time window.

    DDR-V3-004: Four equally-weighted KPIs.
    """

    report_id: str = Field(default="")
    window: WindowPeriod = Field(default=WindowPeriod.D30)
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    # ── Individual KPIs ──────────────────────────────────────────────────
    kpi1_hypothesis_accuracy: KPI1_HypothesisAccuracy = Field(
        default_factory=KPI1_HypothesisAccuracy,
    )
    kpi2_prediction_error: KPI2_PredictionError = Field(
        default_factory=KPI2_PredictionError,
    )
    kpi3_calibration: KPI3_ConfidenceCalibration = Field(
        default_factory=KPI3_ConfidenceCalibration,
    )
    kpi4_learning_speed: KPI4_LearningSpeed = Field(
        default_factory=KPI4_LearningSpeed,
    )

    @property
    def overall_score(self) -> float:
        """Equal-weighted average of all 4 KPI composite scores."""
        return (
            0.25 * self.kpi1_hypothesis_accuracy.composite_score
            + 0.25 * self.kpi2_prediction_error.composite_score
            + 0.25 * self.kpi3_calibration.composite_score
            + 0.25 * self.kpi4_learning_speed.composite_score
        )

    def summary(self) -> dict[str, float]:
        """Key metrics as a flat dict."""
        return {
            "overall": round(self.overall_score, 3),
            "hypothesis_accuracy": round(self.kpi1_hypothesis_accuracy.composite_score, 3),
            "prediction_error": round(self.kpi2_prediction_error.composite_score, 3),
            "calibration": round(self.kpi3_calibration.composite_score, 3),
            "learning_speed": round(self.kpi4_learning_speed.composite_score, 3),
        }

    def __repr__(self) -> str:
        return (
            f"<FourKPIReport [{self.window.value}] "
            f"overall={self.overall_score:.3f} "
            f"kpi1={self.kpi1_hypothesis_accuracy.composite_score:.2f} "
            f"kpi2={self.kpi2_prediction_error.composite_score:.2f} "
            f"kpi3={self.kpi3_calibration.composite_score:.2f} "
            f"kpi4={self.kpi4_learning_speed.composite_score:.2f}>"
        )


# ── Regression Check ─────────────────────────────────────────────────────────


class RegressionCheck(BaseModel):
    """Regression gate: blocks deployment if any KPI degrades > threshold."""

    previous_report: FourKPIReport = Field(...)
    current_report: FourKPIReport = Field(...)
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    # ── Thresholds ───────────────────────────────────────────────────────
    degradation_threshold: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Max allowed KPI degradation (5%)",
    )

    # ── Results ──────────────────────────────────────────────────────────
    kpi1_degraded: bool = Field(default=False)
    kpi2_degraded: bool = Field(default=False)
    kpi3_degraded: bool = Field(default=False)
    kpi4_degraded: bool = Field(default=False)

    @property
    def any_degraded(self) -> bool:
        """Whether any KPI degraded beyond threshold."""
        return any(
            [
                self.kpi1_degraded,
                self.kpi2_degraded,
                self.kpi3_degraded,
                self.kpi4_degraded,
            ]
        )

    @property
    def pass_gate(self) -> bool:
        """Whether the regression gate is passed."""
        return not self.any_degraded

    def degraded_kpis(self) -> list[str]:
        """List of KPI names that degraded."""
        degraded = []
        if self.kpi1_degraded:
            degraded.append("KPI-1 Hypothesis Accuracy")
        if self.kpi2_degraded:
            degraded.append("KPI-2 Prediction Error")
        if self.kpi3_degraded:
            degraded.append("KPI-3 Calibration")
        if self.kpi4_degraded:
            degraded.append("KPI-4 Learning Speed")
        return degraded

    def __repr__(self) -> str:
        status = "PASS" if self.pass_gate else "BLOCKED"
        return f"<RegressionCheck {status} degraded={self.degraded_kpis()}>"
