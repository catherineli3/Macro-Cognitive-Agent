"""V3 Learning Log Schemas — Append-Only Error & Learning Record (DDR-V3-005).

Key design:
    - Append-only, immutable store of (prediction → outcome → diagnosis → learning action)
    - Minimum 200 entries before PatternLearner activates
    - Queryable by hypothesis, error category, dimension, channel
    - This is the Agent's accumulated experience
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from src.schemas.diagnosis import ErrorCategory
from src.schemas.learning_unit import LearningActionType

# ── Learning Log Entry ───────────────────────────────────────────────────────


class LearningLogEntry(BaseModel):
    """A single entry in the append-only Learning Log.

    DDR-V3-005: Every prediction → outcome → diagnosis → learning action
    chain is persisted as a LearningLogEntry. This is the raw data for
    PatternLearner to identify systematic weaknesses.
    """

    entry_id: str = Field(default="", description="Unique entry identifier")
    run_id: str = Field(..., min_length=1, max_length=64)

    # ── Prediction ───────────────────────────────────────────────────────
    prediction_id: str = Field(..., min_length=1, max_length=64)
    hypothesis_id: str = Field(..., min_length=1, max_length=64)
    dimension: str = Field(..., min_length=1, max_length=40)
    transmission_channel: str = Field(default="", max_length=80)
    prediction_tier: str = Field(default="primary")
    predicted_direction: str = Field(default="neutral")
    predicted_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    horizon: str = Field(default="5d")

    # ── Outcome ──────────────────────────────────────────────────────────
    was_correct: bool = Field(default=False)
    actual_direction: str = Field(default="unknown")
    error_magnitude: float = Field(default=0.0, ge=0.0)

    # ── Diagnosis ────────────────────────────────────────────────────────
    error_category: str | None = Field(
        default=None,
        description=f"One of: {[e.value for e in ErrorCategory]}",
    )
    diagnosis_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    diagnosis_rationale: str = Field(default="", max_length=1024)

    # ── Learning Action ──────────────────────────────────────────────────
    learning_action: str | None = Field(
        default=None,
        description=f"One of: {[a.value for a in LearningActionType]}",
    )
    learning_unit_changes: list[str] = Field(
        default_factory=list,
        description="Which of the 5 LU attributes were modified",
    )
    belief_id: str | None = Field(default=None, max_length=64)
    belief_version_created: int | None = Field(default=None, ge=1)

    # ── Metadata ─────────────────────────────────────────────────────────
    predicted_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    logged_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @property
    def days_to_evaluation(self) -> float:
        """How long between prediction and evaluation."""
        delta = self.evaluated_at - self.predicted_at
        return delta.total_seconds() / 86400.0

    @property
    def is_learnable_error(self) -> bool:
        """Whether this error triggers learning (excludes EVENT_ERR)."""
        return self.error_category is not None and self.error_category != "EVENT_ERR"

    def __repr__(self) -> str:
        status = "✓" if self.was_correct else "✗"
        return (
            f"<LearningLogEntry {status} [{self.dimension}] "
            f"err={self.error_category} action={self.learning_action} "
            f"channel={self.transmission_channel}>"
        )
