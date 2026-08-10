"""Calibration schemas — Data contracts for Confidence Calibration (v2.0).

Key design:
    - ConfidenceCalibration combines Reflection confidence with historical accuracy.
    - Generates a calibrated confidence that reflects BOTH current evidence quality
      AND the Agent's track record on similar predictions.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


# ── Confidence Calibration ───────────────────────────────────────────────────


class ConfidenceCalibration(BaseModel):
    """A calibrated confidence for a single hypothesis.

    Combines:
        1. Reflection-based confidence (current evidence quality)
        2. Historical accuracy on this dimension
        3. Prediction stability (how consistent is this call?)

    The calibrated confidence NEVER exceeds the reflection confidence
    but can be significantly LOWER if historical accuracy is poor.
    """

    hypothesis_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="The hypothesis being calibrated",
    )
    dimension: str = Field(
        ...,
        description="Macro dimension for historical lookup",
    )

    # ── Input confidences ──────────────────────────────────────────────
    raw_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence from Reflection (uncalibrated)",
    )
    historical_accuracy: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Historical hit rate on this dimension",
    )
    dimension_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Learned reliability weight for this dimension",
    )

    # ── Calibrated output ──────────────────────────────────────────────
    calibrated_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Final calibrated confidence",
    )
    calibration_delta: float = Field(
        default=0.0,
        description="raw_confidence - calibrated_confidence (how much we adjusted)",
    )

    # ── Explanation ────────────────────────────────────────────────────
    calibration_rationale: str = Field(
        default="",
        max_length=512,
        description="Why the confidence was adjusted (or not)",
    )
    calibration_method: str = Field(
        default="weighted_blend",
        description="Method used: weighted_blend | brier_scaled | none",
    )

    # ── Metadata ───────────────────────────────────────────────────────
    total_outcomes_tracked: int = Field(default=0, ge=0)
    calibrated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @property
    def was_adjusted(self) -> bool:
        """Whether any calibration adjustment was applied."""
        return abs(self.calibration_delta) > 0.01

    @property
    def adjustment_direction(self) -> str:
        """Direction of the calibration adjustment."""
        if self.calibration_delta > 0.01:
            return "downward"
        elif self.calibration_delta < -0.01:
            return "upward"
        return "none"

    def __repr__(self) -> str:
        return (
            f"<ConfidenceCalibration [{self.dimension}] "
            f"raw={self.raw_confidence:.0%} "
            f"→ calibrated={self.calibrated_confidence:.0%} "
            f"(Δ={self.calibration_delta:+.0%})>"
        )


class CalibratedConfidenceSet(BaseModel):
    """A set of calibrated confidences for all hypotheses in a run."""

    run_id: str = Field(..., description="Pipeline run identifier")
    calibrations: list[ConfidenceCalibration] = Field(default_factory=list)
    global_calibration_factor: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Global multiplier based on overall Agent accuracy",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @property
    def average_raw(self) -> float:
        if not self.calibrations:
            return 0.5
        return sum(c.raw_confidence for c in self.calibrations) / len(self.calibrations)

    @property
    def average_calibrated(self) -> float:
        if not self.calibrations:
            return 0.5
        return sum(c.calibrated_confidence for c in self.calibrations) / len(self.calibrations)

    def __repr__(self) -> str:
        return (
            f"<CalibratedConfidenceSet run={self.run_id[:8]} "
            f"avg_raw={self.average_raw:.0%} "
            f"avg_cal={self.average_calibrated:.0%}>"
        )
