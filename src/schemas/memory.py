"""Memory schemas — Data contracts for the Belief Memory System.

Sprint 8 defines the canonical BeliefRecord format. Every belief persisted
by the Memory layer MUST use this schema.

Key design:
    - BeliefRecord is Self-Contained — it carries all information needed
      to understand a belief without accessing Hypothesis or Reflection.
    - BeliefStatus maps FROM ReflectionVerdict but lives in Memory domain.
      Memory NEVER imports ReflectionVerdict directly.
    - BeliefRecord stores METADATA only — no raw signal data, no tool outputs.
"""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from src.domain.memory import BeliefStatus, TransitionType
from src.domain.signal import SignalDirection


class BeliefRecord(BaseModel):
    """A single belief persisted in long-term memory.

    Each BeliefRecord captures the Agent's belief about a macro dimension
    at a specific point in time, AFTER reflection has reviewed it.
    """

    # ── Identity ──────────────────────────────────────────────────────

    belief_id: str = Field(
        default_factory=lambda: uuid4().hex[:12],
        min_length=1,
        max_length=64,
        description="Unique belief record identifier",
    )
    run_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="ExecutionPlan.plan_id that produced this belief",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this belief was recorded",
    )

    # ── Source Reference ──────────────────────────────────────────────

    hypothesis_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Source HypothesisSchema.hypothesis_id",
    )
    dimension: str = Field(
        ...,
        min_length=1,
        max_length=40,
        description="Macro dimension: Liquidity | Credit | Growth | Risk_Appetite | Inflation",
    )

    # ── Belief Content ────────────────────────────────────────────────

    statement: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="The belief statement — what the Agent believes",
    )
    direction: SignalDirection = Field(
        default=SignalDirection.NEUTRAL,
        description="Market-implied direction: bullish | bearish | neutral",
    )

    # ── Confidence ────────────────────────────────────────────────────

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Review-adjusted confidence (after Reflection)",
    )

    # ── Verdict ───────────────────────────────────────────────────────

    status: BeliefStatus = Field(
        default=BeliefStatus.IN_DOUBT,
        description="Memory-level belief status (NOT ReflectionVerdict)",
    )

    # ── Transition ────────────────────────────────────────────────────

    transition: TransitionType = Field(
        default=TransitionType.NEW,
        description="How this belief relates to the prior belief in this dimension",
    )

    # ── Evidence Summary ──────────────────────────────────────────────

    supporting_count: int = Field(
        default=0,
        ge=0,
        description="Number of supporting evidence items",
    )
    contradicting_count: int = Field(
        default=0,
        ge=0,
        description="Number of contradicting evidence items",
    )
    evidence_summary: str = Field(
        default="",
        max_length=512,
        description="One-sentence summary of the evidence picture",
    )
    review_summary: str = Field(
        default="",
        max_length=1024,
        description="Human-readable review summary from ReflectionReport",
    )

    # ── Metadata ──────────────────────────────────────────────────────

    metadata: dict = Field(
        default_factory=dict,
        description="Extensible metadata (e.g., generation_context)",
    )

    # ── Computed Properties ───────────────────────────────────────────

    @property
    def has_contradictions(self) -> bool:
        """Whether this belief had contradicting evidence."""
        return self.contradicting_count > 0

    @property
    def is_reversal(self) -> bool:
        """Whether this belief represents a direction reversal."""
        return self.transition == TransitionType.REVERSED

    @property
    def is_new_dimension(self) -> bool:
        """Whether this is the first belief for this dimension."""
        return self.transition == TransitionType.NEW

    def __repr__(self) -> str:
        d = self.direction.value
        brief = self.statement[:80]
        return (
            f"<BeliefRecord [{self.dimension}] {d} c={self.confidence:.2f} "
            f"{self.transition.value} '{brief}'>"
        )
