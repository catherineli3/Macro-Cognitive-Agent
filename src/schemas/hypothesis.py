"""Hypothesis schemas — Data contracts for Reasoning Engine output.

Sprint 6 defines the canonical Hypothesis format. Every reasoning output
in the system MUST use these schemas. No dicts, no bare lists, no raw strings.

Key design:
    - HypothesisEvidence is a FIRST-CLASS object — not a signal_id reference.
      Reflection (Sprint 7) consumes Evidence directly without re-querying signals.
    - Assumptions are explicit. Without them, the Agent cannot challenge
      its own reasoning.
    - Direction reuses SignalDirection (semantic alignment across layers).
"""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from src.domain.hypothesis import HypothesisStatus
from src.schemas.signal import SignalDirection

# ── Evidence ──────────────────────────────────────────────────────────────


class HypothesisEvidence(BaseModel):
    """A single piece of evidence supporting or contradicting a Hypothesis.

    Evidence is self-contained — it carries the full provenance needed
    for Reflection to critically evaluate the hypothesis without
    re-querying the original signals.

    Attributes:
        indicator:      The macro indicator that generated this evidence.
        signal_id:      Reference to the source MacroSignal (for traceability).
        observation:    What the signal observed (e.g., "DXY at 106.5").
        interpretation: Financial meaning in plain language.
        contribution:   How strongly this evidence supports/contradicts (0-1).
        alignment:      "supporting" if evidence aligns with the hypothesis,
                        "contradicting" if it challenges it.
    """

    indicator: str = Field(..., min_length=1, max_length=20)
    signal_id: str = Field(..., description="Source signal ID for traceability")
    observation: str = Field(..., description="What was observed, e.g. 'DXY at 106.5'")
    interpretation: str = Field(..., description="Financial meaning in plain language")
    contribution: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Evidence strength (0-1)",
    )
    alignment: str = Field(
        default="supporting",
        description="supporting | contradicting",
    )


# ── Hypothesis Schema ─────────────────────────────────────────────────────


class HypothesisSchema(BaseModel):
    """A single structured hypothesis — the Agent's explanation of reality.

    A Hypothesis is NOT a signal aggregation. It is a reasoned explanation
    that organizes observations into a coherent thesis. Each Hypothesis
    represents ONE explanation, backed by evidence and grounded in
    explicit assumptions.

    Attributes:
        hypothesis_id:           Unique identifier.
        statement:               The human-readable explanation.
                                 e.g. "Global liquidity conditions are tightening
                                 as dollar strength and rising rates constrain
                                 capital flows."
        dimension:               Primary HypothesisDimension (metadata, not the
                                 primary grouping). One of: Liquidity, Credit,
                                 Growth, Risk_Appetite, Inflation.
        direction:               bullish | bearish | neutral.
        status:                  Lifecycle status (default ACTIVE).
        confidence:              How strongly the Agent believes this explanation
                                 (0.0-1.0). Measures BELIEF, not signal agreement.
        supporting_evidence:     Evidence that supports this hypothesis.
        contradicting_evidence:  Evidence that challenges this hypothesis.
                                 Reflection (Sprint 7) consumes this directly.
        assumptions:             Explicit assumptions underlying the reasoning.
                                 Without these, the Agent cannot challenge its
                                 own conclusions.
        generated_at:            When the hypothesis was produced.
        metadata:                Extensible (generation_context, model_version, etc.).
    """

    hypothesis_id: str = Field(
        default_factory=lambda: uuid4().hex[:12],
        description="Unique hypothesis identifier",
    )
    statement: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="The explanation — what the Agent believes is happening",
    )
    dimension: str = Field(
        ...,
        description="Primary macro dimension (metadata, not grouping key)",
    )
    direction: SignalDirection = Field(
        default=SignalDirection.NEUTRAL,
        description="Market-implied direction of this hypothesis",
    )
    status: HypothesisStatus = Field(
        default=HypothesisStatus.ACTIVE,
        description="Lifecycle status",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Agent's belief in this explanation (0-1). NOT signal agreement %",
    )
    supporting_evidence: list[HypothesisEvidence] = Field(
        default_factory=list,
        description="Evidence that supports this hypothesis",
    )
    contradicting_evidence: list[HypothesisEvidence] = Field(
        default_factory=list,
        description="Evidence that challenges this hypothesis",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions the hypothesis rests on",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Hypothesis generation timestamp",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Extensible metadata",
    )

    @property
    def evidence_count(self) -> int:
        """Total evidence items (supporting + contradicting)."""
        return len(self.supporting_evidence) + len(self.contradicting_evidence)

    @property
    def has_contradictions(self) -> bool:
        """Whether this hypothesis has contradicting evidence."""
        return len(self.contradicting_evidence) > 0

    @property
    def supporting_ratio(self) -> float:
        """Proportion of evidence that supports the hypothesis (0-1)."""
        total = self.evidence_count
        if total == 0:
            return 0.0
        return len(self.supporting_evidence) / total

    def __repr__(self) -> str:
        d = self.direction.value
        c = self.confidence
        s_count = len(self.supporting_evidence)
        x_count = len(self.contradicting_evidence)
        return f"<Hypothesis [{self.dimension}] {d} c={c:.2f} " f"evidence=+{s_count}/-{x_count}>"


# ── Hypothesis Set ────────────────────────────────────────────────────────


class HypothesisSet(BaseModel):
    """A collection of hypotheses produced by a single reasoning cycle.

    The HypothesisSet is the output of HypothesisEngine.reason().
    It contains all generated hypotheses across all covered dimensions,
    enabling the Planner and Executor to reason about the complete
    macro picture.

    Attributes:
        generated_at:       When the set was produced.
        hypotheses:         All generated hypotheses.
        dimensions_covered: Which macro dimensions have at least one hypothesis.
        summary:            One-sentence overview of the macro picture.
    """

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    hypotheses: list[HypothesisSchema] = Field(default_factory=list)
    dimensions_covered: list[str] = Field(default_factory=list)
    summary: str = Field(default="", description="One-sentence macro overview")

    @property
    def count(self) -> int:
        """Total number of hypotheses."""
        return len(self.hypotheses)

    def get_by_dimension(self, dimension: str) -> list[HypothesisSchema]:
        """Retrieve all hypotheses for a specific dimension."""
        return [h for h in self.hypotheses if h.dimension == dimension]

    def get_highest_confidence(self) -> HypothesisSchema | None:
        """Return the hypothesis with the highest confidence."""
        if not self.hypotheses:
            return None
        return max(self.hypotheses, key=lambda h: h.confidence)

    def __repr__(self) -> str:
        dims = ", ".join(self.dimensions_covered) if self.dimensions_covered else "none"
        return f"<HypothesisSet hypotheses={len(self.hypotheses)} " f"dimensions=[{dims}]>"
