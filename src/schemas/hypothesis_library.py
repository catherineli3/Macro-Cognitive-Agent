"""V3 Hypothesis Library Schemas — Scored, Searchable Knowledge Base (DDR-V3-010).

Key design:
    - Every hypothesis gets a composite HypothesisScore from 5 sub-scores
    - The Library is the system's long-term intellectual asset
    - High-score hypotheses drive predictions; deprecated ones are avoided
    - KPI-1 (Hypothesis Accuracy) derived from Library scores
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

# ── Hypothesis Score ─────────────────────────────────────────────────────────


class HypothesisScore(BaseModel):
    """Composite score for a hypothesis, aggregating 5 dimensions.

    DDR-V3-010: The HypothesisScore defines how "good" a hypothesis is.
    Weights:
        Prediction Accuracy: 0.30
        Evidence Quality:    0.25
        Calibration:         0.20
        Consistency:         0.15
        Learning History:    0.10
    """

    hypothesis_id: str = Field(..., min_length=1, max_length=64)
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    # ── Composite score (0 ~ 1) ──────────────────────────────────────────
    total_score: float = Field(default=0.5, ge=0.0, le=1.0)

    # ── Sub-score 1: Prediction Accuracy (weight: 0.30) ──────────────────
    prediction_accuracy: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Directional accuracy of this hypothesis's predictions",
    )
    accuracy_trend: str = Field(
        default="stable",
        description="'improving' | 'stable' | 'declining'",
    )
    predictions_evaluated: int = Field(default=0, ge=0)

    # ── Sub-score 2: Evidence Quality (weight: 0.25) ─────────────────────
    evidence_quality: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Average strength + recency of supporting evidence",
    )
    evidence_count: int = Field(default=0, ge=0)
    evidence_freshness_days: float = Field(
        default=30.0,
        ge=0.0,
        description="Average age of evidence in days",
    )

    # ── Sub-score 3: Calibration (weight: 0.20) ──────────────────────────
    calibration_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="1.0 - ECE for this hypothesis",
    )
    ece: float = Field(default=0.25, ge=0.0, le=1.0)

    # ── Sub-score 4: Consistency (weight: 0.15) ──────────────────────────
    consistency_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="1.0 - std_dev of accuracy across cycles",
    )
    accuracy_variance: float = Field(default=0.0, ge=0.0, le=1.0)
    cycle_count: int = Field(default=0, ge=0)

    # ── Sub-score 5: Learning History (weight: 0.10) ─────────────────────
    learning_history_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Has accuracy improved over time?",
    )
    accuracy_trajectory_slope: float = Field(
        default=0.0,
        description="Positive = improving",
    )
    version_count: int = Field(default=1, ge=1)

    @property
    def tier(self) -> str:
        """Human-readable quality tier."""
        if self.total_score >= 0.70:
            return "high"
        elif self.total_score >= 0.50:
            return "medium"
        return "low"

    def __repr__(self) -> str:
        return (
            f"<HypothesisScore [{self.tier}] total={self.total_score:.2f} "
            f"acc={self.prediction_accuracy:.0%} cal={self.calibration_score:.2f} "
            f"cycles={self.cycle_count}>"
        )


# ── Hypothesis Library Entry ─────────────────────────────────────────────────


class HypothesisLibraryEntry(BaseModel):
    """A hypothesis registered in the Hypothesis Library with its current score.

    DDR-V3-010: The Library IS the Agent's intelligence.
    """

    hypothesis_id: str = Field(..., min_length=1, max_length=64)
    dimension: str = Field(..., min_length=1, max_length=40)
    statement: str = Field(default="", max_length=1024)
    direction: str = Field(default="neutral")

    # ── Current score ────────────────────────────────────────────────────
    current_score: HypothesisScore = Field(...)

    # ── Score history (for trajectory analysis) ──────────────────────────
    score_history: list[HypothesisScore] = Field(
        default_factory=list,
        description="All historical scores, newest last",
    )

    # ── Lifecycle ────────────────────────────────────────────────────────
    registered_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    status: str = Field(default="active")  # 'active' | 'deprecated' | 'archived'

    # ── Associated beliefs ───────────────────────────────────────────────
    belief_ids: list[str] = Field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def score_trajectory_slope(self) -> float:
        """Whether scores are improving over time."""
        scores = [s.total_score for s in self.score_history]
        if len(scores) < 2:
            return 0.0
        n = len(scores)
        x_mean = sum(range(n)) / n
        y_mean = sum(scores) / n
        num = sum((i - x_mean) * (s - y_mean) for i, s in enumerate(scores))
        den = sum((i - x_mean) ** 2 for i in range(n))
        return num / den if den != 0 else 0.0

    def __repr__(self) -> str:
        return (
            f"<HypothesisLibraryEntry [{self.dimension}] {self.status} "
            f"score={self.current_score.total_score:.2f} "
            f"history={len(self.score_history)}>"
        )
