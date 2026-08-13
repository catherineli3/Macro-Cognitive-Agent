"""V3 Evaluation Schemas — Per-Prediction, Per-Channel Outcome Evaluation.

Key design (DDR-V3-009):
    - Each prediction evaluated independently
    - Hypothesis-level accuracy is a derived aggregate
    - Per-channel breakdowns for precise diagnosis
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from src.schemas.prediction_v3 import V3PredictionOutcome

# ── V3 Evaluation Report ─────────────────────────────────────────────────────


class EvaluationReport(BaseModel):
    """Aggregated outcome evaluation for a prediction batch.

    DDR-V3-004: Feeds into KPI-2 (Prediction Error).
    DDR-V3-009: Per-channel breakdowns for transmission-level insight.
    """

    report_id: str = Field(default="", description="Unique report identifier")
    batch_id: str = Field(..., min_length=1, max_length=64)
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    # ── Per-prediction outcomes ──────────────────────────────────────────
    outcomes: list[V3PredictionOutcome] = Field(default_factory=list)

    # ── Aggregate accuracy ───────────────────────────────────────────────
    directional_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    mean_absolute_error: float = Field(default=0.0, ge=0.0)
    rmse: float = Field(default=0.0, ge=0.0)
    brier_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # ── Breakdown: Per-Dimension ─────────────────────────────────────────
    accuracy_by_dimension: dict[str, float] = Field(default_factory=dict)

    # ── Breakdown: Per-Horizon ───────────────────────────────────────────
    accuracy_by_horizon: dict[str, float] = Field(default_factory=dict)

    # ── Breakdown: Per-Hypothesis ────────────────────────────────────────
    accuracy_by_hypothesis: dict[str, float] = Field(default_factory=dict)

    # ── Breakdown: Per-Channel (DDR-V3-009) ──────────────────────────────
    accuracy_by_channel: dict[str, float] = Field(default_factory=dict)

    # ── Breakdown: Per-Tier ──────────────────────────────────────────────
    accuracy_by_tier: dict[str, float] = Field(default_factory=dict)

    # ── Confidence Calibration ───────────────────────────────────────────
    accuracy_by_confidence_bucket: dict[str, float] = Field(default_factory=dict)

    # ── Metadata ─────────────────────────────────────────────────────────
    total_outcomes: int = Field(default=0, ge=0)
    total_correct: int = Field(default=0, ge=0)
    total_incorrect: int = Field(default=0, ge=0)

    @property
    def hit_rate(self) -> float:
        """Simple accuracy: correct / total."""
        if self.total_outcomes == 0:
            return 0.0
        return self.total_correct / self.total_outcomes

    def get_channel_accuracy(self, channel: str) -> float:
        """Get accuracy for a specific transmission channel."""
        return self.accuracy_by_channel.get(channel, 0.0)

    def get_hypothesis_accuracy(self, hypothesis_id: str) -> float:
        """Get accuracy for a specific hypothesis."""
        return self.accuracy_by_hypothesis.get(hypothesis_id, 0.0)

    def worst_channel(self) -> tuple[str, float] | None:
        """Return the channel with lowest accuracy."""
        if not self.accuracy_by_channel:
            return None
        worst = min(self.accuracy_by_channel.items(), key=lambda x: x[1])
        return worst

    def best_channel(self) -> tuple[str, float] | None:
        """Return the channel with highest accuracy."""
        if not self.accuracy_by_channel:
            return None
        best = max(self.accuracy_by_channel.items(), key=lambda x: x[1])
        return best

    def __repr__(self) -> str:
        return (
            f"<EvaluationReport total={self.total_outcomes} "
            f"da={self.directional_accuracy:.0%} mae={self.mean_absolute_error:.3f} "
            f"channels={len(self.accuracy_by_channel)}>"
        )
