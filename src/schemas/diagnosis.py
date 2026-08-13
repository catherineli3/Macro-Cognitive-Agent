"""V3 Diagnosis Schemas — Error Taxonomy & Per-Prediction Diagnosis (DDR-V3-002, DDR-V3-005).

Key design:
    - 6 mandatory error categories (DDR-V3-002)
    - Per-prediction diagnosis (DDR-V3-009: per-channel context)
    - Correct predictions also classified (CORRECT_STRONG, CORRECT_WEAK, CORRECT_LUCKY)
    - DiagnosisReport is the ONLY input to Learning Engine (DDR-V3-006)
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

# ── Error Category ───────────────────────────────────────────────────────────


class ErrorCategory(str, Enum):
    """Six error categories — frozen by DDR-V3-002.

    Learning implications are category-specific:
        SIGNAL_ERR     → Improve signal quality
        HYP_ERR        → Revise hypothesis / narrow conditions
        EVID_MISSING   → Add data source
        TIMING_ERR     → Adjust horizon
        EVENT_ERR      → No weight change (non-learnable)
        WEIGHT_ERR     → Adjust dimension weights
    """

    SIGNAL_ERR = "SIGNAL_ERR"
    HYP_ERR = "HYP_ERR"
    EVID_MISSING = "EVID_MISSING"
    TIMING_ERR = "TIMING_ERR"
    EVENT_ERR = "EVENT_ERR"
    WEIGHT_ERR = "WEIGHT_ERR"


class CorrectCategory(str, Enum):
    """Categories for correct predictions."""

    CORRECT_STRONG = "CORRECT_STRONG"  # Direction + magnitude both correct
    CORRECT_WEAK = "CORRECT_WEAK"  # Direction correct, magnitude off
    CORRECT_LUCKY = "CORRECT_LUCKY"  # Direction correct but rationale suspect


# ── Error Classification ─────────────────────────────────────────────────────


class ErrorClassification(BaseModel):
    """Per-prediction error diagnosis.

    DDR-V3-005: Every error classified into exactly one category.
    Wrong predictions get an ErrorCategory; correct predictions get a CorrectCategory.
    """

    prediction_id: str = Field(..., min_length=1, max_length=64)
    transmission_channel: str = Field(
        default="", max_length=80, description="Channel context for diagnosis"
    )
    hypothesis_id: str = Field(default="", max_length=64)

    # ── Classification ───────────────────────────────────────────────────
    is_correct: bool = Field(default=False)
    error_category: ErrorCategory | None = Field(default=None)
    correct_category: CorrectCategory | None = Field(default=None)

    # ── Diagnosis Quality ────────────────────────────────────────────────
    diagnosis_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How confident we are in this diagnosis",
    )
    diagnosis_rationale: str = Field(default="", max_length=1024)

    # ── Metadata ─────────────────────────────────────────────────────────
    classified_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    evidence_for_diagnosis: list[str] = Field(
        default_factory=list,
        description="IDs of evidence items used to classify this error",
    )

    @property
    def is_learnable(self) -> bool:
        """Whether this error should trigger learning (EVENT_ERR is not)."""
        if self.is_correct:
            return True
        return self.error_category != ErrorCategory.EVENT_ERR

    @property
    def learning_weight(self) -> float:
        """Diagnosis-category-specific weight delta multiplier (DDR-V3-003)."""
        if self.is_correct:
            return 0.0
        weights = {
            ErrorCategory.HYP_ERR: 2.0,  # Strongest penalty
            ErrorCategory.WEIGHT_ERR: 1.5,
            ErrorCategory.SIGNAL_ERR: 1.0,
            ErrorCategory.EVID_MISSING: 1.0,
            ErrorCategory.TIMING_ERR: 0.5,  # Minor penalty
            ErrorCategory.EVENT_ERR: 0.0,  # No penalty (non-learnable)
        }
        return weights.get(self.error_category, 1.0)  # type: ignore[arg-type]

    def __repr__(self) -> str:
        if self.is_correct:
            cat = self.correct_category.value if self.correct_category else "UNKNOWN"
            return f"<ErrorClassification ✓ {cat} pred={self.prediction_id[:8]}>"
        cat = self.error_category.value if self.error_category else "UNKNOWN"
        return f"<ErrorClassification ✗ {cat} pred={self.prediction_id[:8]}>"


# ── Diagnosis Report ─────────────────────────────────────────────────────────


class DiagnosisReport(BaseModel):
    """Aggregated diagnosis for an evaluation batch.

    DDR-V3-006: This is the ONLY input to Learning Engine.
    No outcome bypasses diagnosis.
    """

    report_id: str = Field(default="", description="Unique diagnosis report ID")
    evaluation_report_id: str = Field(..., min_length=1, max_length=64)
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    # ── Per-prediction diagnoses ─────────────────────────────────────────
    classifications: list[ErrorClassification] = Field(default_factory=list)

    # ── Summary ──────────────────────────────────────────────────────────
    total_diagnosed: int = Field(default=0, ge=0)
    correct_count: int = Field(default=0, ge=0)
    incorrect_count: int = Field(default=0, ge=0)

    # ── Error distribution ───────────────────────────────────────────────
    error_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="{ErrorCategory: count}",
    )
    correct_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="{CorrectCategory: count}",
    )

    # ── Per-channel error summary ────────────────────────────────────────
    channel_error_distribution: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="{channel: {ErrorCategory: count}}",
    )

    # ── Unclassified ─────────────────────────────────────────────────────
    unclassified_count: int = Field(
        default=0,
        ge=0,
        description="Predictions that could not be classified (safe default)",
    )

    @property
    def most_common_error(self) -> str | None:
        """The most frequent error category in this batch."""
        if not self.error_distribution:
            return None
        return max(self.error_distribution, key=self.error_distribution.get)  # type: ignore[arg-type]

    @property
    def learnable_count(self) -> int:
        """Number of predictions that should trigger learning."""
        return sum(1 for c in self.classifications if c.is_learnable)

    def get_channel_errors(self, channel: str) -> dict[str, int]:
        """Get error distribution for a specific channel."""
        return self.channel_error_distribution.get(channel, {})

    def __repr__(self) -> str:
        return (
            f"<DiagnosisReport total={self.total_diagnosed} "
            f"correct={self.correct_count} errors={self.incorrect_count} "
            f"top_err={self.most_common_error}>"
        )


# ── Error Trend ──────────────────────────────────────────────────────────────


class ErrorTrend(BaseModel):
    """Historical error pattern for a hypothesis or channel over a time window."""

    hypothesis_id: str | None = None
    channel: str | None = None
    window_days: int = Field(default=90, ge=1)
    error_counts: dict[str, int] = Field(default_factory=dict)
    trend_direction: str = Field(default="stable")  # improving | declining | stable
    total_errors: int = Field(default=0, ge=0)

    @property
    def primary_error_type(self) -> str | None:
        if not self.error_counts:
            return None
        return max(self.error_counts, key=self.error_counts.get)  # type: ignore[arg-type]
