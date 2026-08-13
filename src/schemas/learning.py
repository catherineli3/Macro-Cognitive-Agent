"""Learning schemas — Data contracts for the Learning Engine (v2.0).

Key design:
    - BeliefWeight assigns a learnable reliability score to each dimension.
    - LearningSummary captures what the Agent has learned from past outcomes.
    - ConfidenceDecay controls how recent outcomes are weighted vs older ones.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

# ── Belief Weight ────────────────────────────────────────────────────────────


class BeliefWeight(BaseModel):
    """A learnable reliability score for a single macro dimension.

    Updated by the Learning Engine after each outcome evaluation cycle.
    Higher weight → more influence on subsequent hypotheses.
    """

    dimension: str = Field(
        ...,
        min_length=1,
        max_length=40,
        description="Macro dimension name",
    )

    # ── Core weight ────────────────────────────────────────────────────
    current_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Current reliability weight (0-1)",
    )
    initial_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight at Agent initialization (before any learning)",
    )

    # ── Historical accuracy ────────────────────────────────────────────
    total_predictions: int = Field(default=0, ge=0)
    correct_predictions: int = Field(default=0, ge=0)
    historical_accuracy: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Rolling accuracy over all tracked outcomes",
    )
    recent_accuracy: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Accuracy over last N predictions (recency-weighted)",
    )

    # ── Trend ──────────────────────────────────────────────────────────
    accuracy_trend: str = Field(
        default="stable",
        description="improving | declining | stable",
    )
    streak: int = Field(
        default=0,
        description="Consecutive correct (+) or incorrect (-) predictions",
    )

    # ── Decay ──────────────────────────────────────────────────────────
    confidence_decay_rate: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Rate at which confidence decays per cycle without new evidence",
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @property
    def reliability(self) -> str:
        """Human-readable reliability tier."""
        if self.historical_accuracy >= 0.70:
            return "high"
        elif self.historical_accuracy >= 0.45:
            return "moderate"
        return "low"

    def __repr__(self) -> str:
        return (
            f"<BeliefWeight [{self.dimension}] weight={self.current_weight:.2f} "
            f"acc={self.historical_accuracy:.0%} streak={self.streak}>"
        )


# ── Learning Summary ─────────────────────────────────────────────────────────


class LearningSummary(BaseModel):
    """What the Agent has learned from all tracked outcomes.

    Aggregates:
        - Per-dimension belief weights
        - Global calibration metrics
        - Pattern observations
        - Confidence adjustment recommendations
    """

    # ── Weights ────────────────────────────────────────────────────────
    belief_weights: list[BeliefWeight] = Field(
        default_factory=list,
        description="Learnable reliability weights per dimension",
    )
    overall_calibration_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Global Brier-based calibration score",
    )

    # ── Accuracy ───────────────────────────────────────────────────────
    total_tracked_outcomes: int = Field(default=0, ge=0)
    global_hit_rate: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )
    brier_score: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
    )

    # ── Trends ─────────────────────────────────────────────────────────
    improvement_trend: str = Field(
        default="stable",
        description="Whether accuracy is improving, declining, or stable",
    )
    best_dimension: str = Field(default="", description="Most reliable dimension")
    worst_dimension: str = Field(default="", description="Least reliable dimension")

    # ── Patterns ───────────────────────────────────────────────────────
    learned_patterns: list[str] = Field(
        default_factory=list,
        description="Natural language descriptions of learned patterns",
    )

    # ── Recommendations ────────────────────────────────────────────────
    confidence_adjustments: dict[str, float] = Field(
        default_factory=dict,
        description="{dimension: suggested_confidence_adjustment}",
    )

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    def get_weight(self, dimension: str) -> float:
        """Get current weight for a dimension (default 0.5)."""
        for bw in self.belief_weights:
            if bw.dimension.lower() == dimension.lower():
                return bw.current_weight
        return 0.5

    def get_accuracy(self, dimension: str) -> float:
        """Get historical accuracy for a dimension (default 0.5)."""
        for bw in self.belief_weights:
            if bw.dimension.lower() == dimension.lower():
                return bw.historical_accuracy
        return 0.5

    def __repr__(self) -> str:
        return (
            f"<LearningSummary outcomes={self.total_tracked_outcomes} "
            f"hit_rate={self.global_hit_rate:.0%} "
            f"best={self.best_dimension} worst={self.worst_dimension}>"
        )
