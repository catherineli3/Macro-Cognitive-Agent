"""KPI Metrics Engine — 4-KPI Computation & Regression Gate (DDR-V3-004).

Computes the 4 V3 KPIs on rolling windows (30d, 90d, all-time):
    1. Hypothesis Accuracy   (from Hypothesis Library)
    2. Prediction Error      (Directional Accuracy, MAE, RMSE)
    3. Confidence Calibration (ECE, Brier Score)
    4. Learning Speed        (Error Recurrence Rate, Time-to-Correction)

Regression check blocks deployment if any KPI degrades > threshold.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.schemas.kpi import (
    FourKPIReport,
    KPI1_HypothesisAccuracy,
    KPI2_PredictionError,
    KPI3_ConfidenceCalibration,
    KPI4_LearningSpeed,
    RegressionCheck,
    WindowPeriod,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


class KPIMetricsEngine:
    """Computes and tracks V3's 4-KPI Dashboard.

    DDR-V3-004: All KPIs equally weighted, tracked on rolling windows.
    """

    def __init__(self) -> None:
        self._baseline: Optional[FourKPIReport] = None

    async def compute_kpi1(
        self,
        library_avg_score: float,
        top3_accuracy: float = 0.5,
        deprecation_rate: float = 0.0,
        score_trajectory_slope: float = 0.0,
        active_hypotheses: int = 0,
        total_hypotheses: int = 0,
    ) -> KPI1_HypothesisAccuracy:
        """Compute KPI-1: Hypothesis Library quality."""
        return KPI1_HypothesisAccuracy(
            library_avg_score=round(library_avg_score, 4),
            top3_accuracy=round(top3_accuracy, 4),
            deprecation_rate=round(deprecation_rate, 4),
            score_trajectory_slope=round(score_trajectory_slope, 6),
            active_hypotheses=active_hypotheses,
            total_hypotheses=total_hypotheses,
        )

    async def compute_kpi2(
        self,
        directional_accuracy: float,
        mae: float,
        rmse: float,
        total_predictions: int = 0,
        correct_predictions: int = 0,
        primary_accuracy: float = 0.5,
        secondary_accuracy: float = 0.5,
    ) -> KPI2_PredictionError:
        """Compute KPI-2: Prediction error metrics."""
        return KPI2_PredictionError(
            directional_accuracy=round(directional_accuracy, 4),
            mae=round(mae, 6),
            rmse=round(rmse, 6),
            total_predictions=total_predictions,
            correct_predictions=correct_predictions,
            primary_accuracy=round(primary_accuracy, 4),
            secondary_accuracy=round(secondary_accuracy, 4),
        )

    async def compute_kpi3(
        self,
        ece: float,
        brier_score: float,
        calibration_curve_points: int = 0,
        overconfidence_ratio: float = 0.5,
    ) -> KPI3_ConfidenceCalibration:
        """Compute KPI-3: Confidence calibration."""
        return KPI3_ConfidenceCalibration(
            ece=round(ece, 4),
            brier_score=round(brier_score, 4),
            calibration_curve_points=calibration_curve_points,
            overconfidence_ratio=round(overconfidence_ratio, 4),
        )

    async def compute_kpi4(
        self,
        error_recurrence_rate: float = 0.5,
        time_to_correction_days: float = 30.0,
        pattern_fix_rate: float = 0.0,
        total_errors_classified: int = 0,
        unique_error_patterns: int = 0,
        patterns_fixed: int = 0,
    ) -> KPI4_LearningSpeed:
        """Compute KPI-4: Learning speed."""
        is_significant = total_errors_classified >= 200
        return KPI4_LearningSpeed(
            error_recurrence_rate=round(error_recurrence_rate, 4),
            time_to_correction_days=round(time_to_correction_days, 2),
            pattern_fix_rate=round(pattern_fix_rate, 4),
            total_errors_classified=total_errors_classified,
            unique_error_patterns=unique_error_patterns,
            patterns_fixed=patterns_fixed,
            is_significant=is_significant,
        )

    async def compute_full_report(
        self,
        window: WindowPeriod,
        kpi1: KPI1_HypothesisAccuracy,
        kpi2: KPI2_PredictionError,
        kpi3: KPI3_ConfidenceCalibration,
        kpi4: KPI4_LearningSpeed,
    ) -> FourKPIReport:
        """Assemble a complete 4-KPI report."""
        return FourKPIReport(
            report_id=f"kpi-{uuid4().hex[:8]}",
            window=window,
            kpi1_hypothesis_accuracy=kpi1,
            kpi2_prediction_error=kpi2,
            kpi3_calibration=kpi3,
            kpi4_learning_speed=kpi4,
        )

    async def set_baseline(self, report: FourKPIReport) -> None:
        """Establish baseline KPI values (Release 3.0 initialization)."""
        self._baseline = report
        logger.info(
            "kpi_baseline_set overall=%.3f kpi1=%.3f kpi2=%.3f kpi3=%.3f kpi4=%.3f",
            report.overall_score,
            report.kpi1_hypothesis_accuracy.composite_score,
            report.kpi2_prediction_error.composite_score,
            report.kpi3_calibration.composite_score,
            report.kpi4_learning_speed.composite_score,
        )

    async def check_regression(
        self, current: FourKPIReport, threshold: float = 0.05
    ) -> RegressionCheck:
        """Check if any KPI has regressed beyond threshold vs baseline."""
        if self._baseline is None:
            logger.warning("regression_check_no_baseline")
            return RegressionCheck(
                previous_report=current,
                current_report=current,
                degradation_threshold=threshold,
            )

        check = RegressionCheck(
            previous_report=self._baseline,
            current_report=current,
            degradation_threshold=threshold,
        )

        prev = self._baseline
        curr = current

        check.kpi1_degraded = (
            prev.kpi1_hypothesis_accuracy.composite_score -
            curr.kpi1_hypothesis_accuracy.composite_score
        ) > threshold

        check.kpi2_degraded = (
            prev.kpi2_prediction_error.composite_score -
            curr.kpi2_prediction_error.composite_score
        ) > threshold

        check.kpi3_degraded = (
            prev.kpi3_calibration.composite_score -
            curr.kpi3_calibration.composite_score
        ) > threshold

        check.kpi4_degraded = (
            prev.kpi4_learning_speed.composite_score -
            curr.kpi4_learning_speed.composite_score
        ) > threshold

        if check.any_degraded:
            logger.warning("regression_detected degraded_kpis=%s", check.degraded_kpis())
        else:
            logger.info("regression_check_passed")

        return check
