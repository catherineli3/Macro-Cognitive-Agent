"""V3 Prediction Schemas — Multi-Prediction Model (DDR-V3-009).

Key design:
    - One Hypothesis → N Predictions (primary/secondary/tertiary tiers)
    - Each Prediction targets a specific transmission_channel
    - Every Prediction traces back to its source_hypothesis_id (DDR-V3-001)
    - PredictionBatch groups predictions by hypothesis and channel
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.schemas.signal import SignalDirection


# ── Prediction Tier ──────────────────────────────────────────────────────────


class PredictionTier(str, Enum):
    """Priority tier of a prediction within a hypothesis's prediction set."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"


class PredictionStatus(str, Enum):
    """Lifecycle status of a prediction."""
    PENDING = "pending"
    EVALUATED = "evaluated"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# ── Transmission Channel ─────────────────────────────────────────────────────


class TransmissionChannel(BaseModel):
    """The causal mechanism linking a hypothesis to a specific asset prediction.

    Example:
        dimension="liquidity", asset="equity" → channel_id="liquidity→equity"
    """
    dimension: str = Field(..., min_length=1, max_length=40)
    asset_class: str = Field(..., min_length=1, max_length=40)
    channel_id: str = ""  # Auto-computed: "{dimension}→{asset_class}"

    def model_post_init(self, __context) -> None:
        if not self.channel_id:
            self.channel_id = f"{self.dimension}→{self.asset_class}"


# ── Prediction (V3 Multi-Prediction) ─────────────────────────────────────────


class Prediction(BaseModel):
    """A single falsifiable prediction derived from a hypothesis.

    DDR-V3-001: Every prediction must trace to a source hypothesis.
    DDR-V3-009: One hypothesis generates multiple predictions across channels.
    """

    prediction_id: str = Field(default="", description="Unique prediction identifier")
    run_id: str = Field(..., min_length=1, max_length=64)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # ── WHAT we predict ──────────────────────────────────────────────────
    dimension: str = Field(..., min_length=1, max_length=40)
    indicator: str = Field(..., min_length=1, max_length=40)
    direction: str = Field(..., description="bullish | bearish | flat")

    # Multi-Prediction (DDR-V3-009)
    prediction_tier: PredictionTier = Field(default=PredictionTier.PRIMARY)
    transmission_channel: str = Field(
        ..., min_length=1, max_length=80,
        description="e.g. 'liquidity→equity', 'liquidity→fx'",
    )

    target_range: Optional[tuple[float, float]] = Field(default=None)
    horizon: str = Field(default="5d", description="e.g. 1d, 3d, 5d, 10d, 21d")
    evaluate_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # ── WHY — all non-nullable (DDR-V3-001) ──────────────────────────────
    source_hypothesis_id: str = Field(..., min_length=1, max_length=64)
    source_evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    rationale: str = Field(default="", max_length=1024)

    # ── LIFECYCLE ────────────────────────────────────────────────────────
    status: PredictionStatus = Field(default=PredictionStatus.PENDING)

    @property
    def asset_class(self) -> str:
        """Extract asset class from transmission_channel."""
        for sep in ("→", "->"):
            if sep in self.transmission_channel:
                return self.transmission_channel.split(sep)[1].strip()
        return self.transmission_channel

    @property
    def channel_dimension(self) -> str:
        """Extract dimension from transmission_channel."""
        for sep in ("→", "->"):
            if sep in self.transmission_channel:
                return self.transmission_channel.split(sep)[0].strip()
        return ""

    @property
    def is_primary(self) -> bool:
        return self.prediction_tier == PredictionTier.PRIMARY

    def __repr__(self) -> str:
        return (
            f"<Prediction [{self.prediction_tier.value}] {self.direction} "
            f"{self.indicator} channel={self.transmission_channel} "
            f"c={self.confidence:.0%}>"
        )


# ── Prediction Batch ─────────────────────────────────────────────────────────


class PredictionBatch(BaseModel):
    """A collection of predictions from a single pipeline run.

    DDR-V3-009: Grouped by hypothesis_id and transmission_channel for
    per-channel evaluation and learning.
    """

    batch_id: str = Field(default="", description="Unique batch identifier")
    run_id: str = Field(..., min_length=1, max_length=64)
    predictions: list[Prediction] = Field(default_factory=list)
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # ── Grouped views (DDR-V3-009) ───────────────────────────────────────
    @property
    def by_hypothesis(self) -> dict[str, list[Prediction]]:
        """Group predictions by source hypothesis ID."""
        result: dict[str, list[Prediction]] = {}
        for p in self.predictions:
            result.setdefault(p.source_hypothesis_id, []).append(p)
        return result

    @property
    def by_channel(self) -> dict[str, list[Prediction]]:
        """Group predictions by transmission channel."""
        result: dict[str, list[Prediction]] = {}
        for p in self.predictions:
            result.setdefault(p.transmission_channel, []).append(p)
        return result

    @property
    def by_tier(self) -> dict[str, list[Prediction]]:
        """Group predictions by tier."""
        result: dict[str, list[Prediction]] = {}
        for p in self.predictions:
            result.setdefault(p.prediction_tier.value, []).append(p)
        return result

    @property
    def hypothesis_count(self) -> int:
        return len(self.by_hypothesis)

    @property
    def channel_count(self) -> int:
        return len(self.by_channel)

    @property
    def total_predictions(self) -> int:
        return len(self.predictions)

    def get_primary(self) -> list[Prediction]:
        return [p for p in self.predictions if p.is_primary]

    def __repr__(self) -> str:
        return (
            f"<PredictionBatch preds={len(self.predictions)} "
            f"hypotheses={self.hypothesis_count} channels={self.channel_count}>"
        )


# ── Prediction-Outcome Mapping ───────────────────────────────────────────────


class V3PredictionOutcome(BaseModel):
    """Outcome for a single V3 prediction (per-prediction, per-channel)."""

    prediction_id: str
    correct: bool
    predicted_direction: str
    actual_direction: str
    pct_change: float
    error_magnitude: float
    actual_value: float
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    transmission_channel: str = ""

    @property
    def is_correct(self) -> bool:
        return self.correct

    def __repr__(self) -> str:
        status = "✓" if self.correct else "✗"
        return (
            f"<V3PredictionOutcome {status} "
            f"pred={self.predicted_direction} actual={self.actual_direction} "
            f"Δ={self.pct_change:+.2%} channel={self.transmission_channel}>"
        )
