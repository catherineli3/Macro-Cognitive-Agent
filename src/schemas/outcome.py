"""Outcome schemas — Data contracts for the Outcome Tracking Engine (v2.0).

Key design:
    - OutcomeRecord stores the ground truth: what actually happened vs the prediction.
    - PredictionOutcome evaluates a single hypothesis against the realized outcome.
    - OutcomeSummary aggregates metrics across all tracked predictions.

Each hypothesis becomes a PredictionOutcome after a configurable observation window.
The Learning Engine consumes OutcomeSummary to adjust belief weights and calibrate confidence.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from src.domain.signal import SignalDirection


# ── Outcome Verdict ──────────────────────────────────────────────────────────


class OutcomeVerdict(str, Enum):
    """Whether a prediction was correct, incorrect, or indeterminate."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIALLY_CORRECT = "partially_correct"
    PENDING = "pending"  # Not yet evaluated


class OutcomeDirection(str, Enum):
    """Realized market direction for the observed indicator."""

    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    UNKNOWN = "unknown"


# ── Prediction Outcome ───────────────────────────────────────────────────────


class PredictionOutcome(BaseModel):
    """A single hypothesis-to-outcome evaluation.

    Connects:
        hypothesis_id → what was predicted
        indicator → what was observed
        verdict → was the prediction correct?
    """

    outcome_id: str = Field(
        default_factory=lambda: uuid4().hex[:12],
        description="Unique outcome record identifier",
    )
    hypothesis_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Source HypothesisSchema.hypothesis_id",
    )
    belief_id: str = Field(
        default="",
        max_length=64,
        description="Related BeliefRecord.belief_id (if persisted)",
    )
    dimension: str = Field(
        ...,
        min_length=1,
        max_length=40,
        description="Macro dimension: Liquidity | Credit | Growth | Risk_Appetite | Inflation",
    )

    # ── Prediction ─────────────────────────────────────────────────────
    predicted_statement: str = Field(
        ...,
        max_length=512,
        description="What the Agent predicted",
    )
    predicted_direction: SignalDirection = Field(
        default=SignalDirection.NEUTRAL,
        description="Predicted direction",
    )
    predicted_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence at time of prediction",
    )

    # ── Realized Outcome ───────────────────────────────────────────────
    observed_direction: Optional[OutcomeDirection] = Field(
        default=None,
        description="What actually happened (None = pending)",
    )
    realized_value: Optional[float] = Field(
        default=None,
        description="Realized indicator value (e.g., DXY = 106.5)",
    )
    observation_window_days: int = Field(
        default=7,
        ge=1,
        description="Days waited before evaluating outcome",
    )
    observation_end: Optional[datetime] = Field(
        default=None,
        description="When the observation window closed",
    )

    # ── Verdict ────────────────────────────────────────────────────────
    verdict: OutcomeVerdict = Field(
        default=OutcomeVerdict.PENDING,
        description="Outcome evaluation result",
    )
    verdict_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the verdict (e.g., noisy data → lower)",
    )
    verdict_rationale: str = Field(
        default="",
        max_length=512,
        description="Why the verdict was reached",
    )

    # ── Timing ─────────────────────────────────────────────────────────
    predicted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    evaluated_at: Optional[datetime] = Field(
        default=None,
    )

    @property
    def is_evaluated(self) -> bool:
        """Whether this outcome has been evaluated."""
        return self.verdict != OutcomeVerdict.PENDING

    @property
    def is_correct(self) -> bool:
        """Whether the prediction was correct."""
        return self.verdict == OutcomeVerdict.CORRECT

    @property
    def is_incorrect(self) -> bool:
        """Whether the prediction was incorrect."""
        return self.verdict == OutcomeVerdict.INCORRECT

    def __repr__(self) -> str:
        return (
            f"<PredictionOutcome [{self.dimension}] {self.verdict.value} "
            f"pred={self.predicted_confidence:.0%} />"
        )


# ── Outcome Record ───────────────────────────────────────────────────────────


class OutcomeRecord(BaseModel):
    """A self-contained record of a prediction-to-outcome evaluation.

    Wraps PredictionOutcome into a storable record that the Learning Engine
    can query historically.
    """

    record_id: str = Field(
        default_factory=lambda: uuid4().hex[:12],
    )
    run_id: str = Field(
        ...,
        min_length=1,
        description="The pipeline run that produced this prediction",
    )
    outcome: PredictionOutcome = Field(...)
    recorded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    metadata: dict = Field(default_factory=dict)


# ── Outcome Summary ──────────────────────────────────────────────────────────


class OutcomeSummary(BaseModel):
    """Aggregated outcome metrics across all tracked predictions.

    This is the primary input to the Learning Engine.
    """

    # ── Identifiers ────────────────────────────────────────────────────
    total_predictions: int = Field(
        default=0,
        ge=0,
        description="Total number of evaluated predictions",
    )
    pending_predictions: int = Field(
        default=0,
        ge=0,
        description="Predictions not yet evaluated",
    )

    # ── Accuracy ───────────────────────────────────────────────────────
    correct_count: int = Field(default=0, ge=0)
    incorrect_count: int = Field(default=0, ge=0)
    partially_correct_count: int = Field(default=0, ge=0)

    hit_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Simple accuracy: correct / total",
    )
    brier_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Brier Score — lower is better (0 = perfect calibration)",
    )

    # ── Per-Dimension Breakdown ────────────────────────────────────────
    dimension_accuracy: dict[str, dict] = Field(
        default_factory=dict,
        description="Per-dimension: {dim: {correct, total, hit_rate, brier}}",
    )

    # ── Directional ────────────────────────────────────────────────────
    precision: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Precision of directional calls",
    )
    directional_accuracy: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of correct directional predictions",
    )

    # ── Time ───────────────────────────────────────────────────────────
    average_evaluation_lag_days: float = Field(
        default=0.0,
        description="Average days between prediction and evaluation",
    )
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @property
    def evaluated_count(self) -> int:
        return self.total_predictions - self.pending_predictions

    def to_accuracy(self) -> float:
        """Convenience: overall hit rate as a float."""
        return self.hit_rate

    def __repr__(self) -> str:
        return (
            f"<OutcomeSummary total={self.total_predictions} "
            f"hit_rate={self.hit_rate:.0%} brier={self.brier_score:.3f}>"
        )
