"""V3.1 Hypothesis Evolution Schemas — Candidate Hypothesis with Arguments.

Milestone A: Hypothesis Evolution.
Key design:
    - Each candidate hypothesis carries its full argument (claims + evidence + transmission)
    - Competition results track why a hypothesis was eliminated and when it can be revived
    - The schema bridges "hypothesis as data" to "hypothesis as argument"
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ── Evidence Claim ───────────────────────────────────────────────────────────


class EvidenceClaim(BaseModel):
    """A single piece of evidence bound to a hypothesis.

    Unlike V3.0 HypothesisEvidence (which is just observation), EvidenceClaim
    explicitly states WHY this evidence supports the hypothesis.
    """

    claim_id: str = Field(default_factory=lambda: f"evc-{uuid4().hex[:8]}")
    indicator: str = Field(..., description="e.g. US10Y, VIX, DXY")
    current_value: float = Field(default=0.0)
    direction: str = Field(default="neutral")  # bullish / bearish / neutral
    z_score: float = Field(default=0.0, description="Deviation from historical mean")
    claim: str = Field(
        default="",
        description="Why this evidence supports the hypothesis, e.g. '2Y yield declining signals dovish Fed stance'",
    )
    strength: float = Field(default=0.5, ge=0.0, le=1.0, description="How strongly this evidence supports")


# ── Transmission Segment ─────────────────────────────────────────────────────


class TransmissionSegment(BaseModel):
    """A single segment in a transmission chain.

    Example: credit[easing] → risk_appetite[rising] with reliability 0.78.
    """

    source: str = Field(..., description="Source concept, e.g. 'credit'")
    target: str = Field(..., description="Target concept, e.g. 'risk_appetite'")
    direction: str = Field(default="+", description="+ (positive) / - (negative) correlation")
    description: str = Field(default="", description="Human-readable description")
    reliability: float = Field(default=0.5, ge=0.0, le=1.0)
    conditions: list[str] = Field(
        default_factory=list,
        description="Conditions for this segment to hold, e.g. 'VIX < 25'",
    )

    @property
    def segment_id(self) -> str:
        return f"{self.source}→{self.target}"


# ── Candidate Hypothesis ─────────────────────────────────────────────────────


class CandidateHypothesis(BaseModel):
    """A candidate hypothesis generated from macro signals.

    Each candidate carries:
        - A thesis (claim about what's happening)
        - Supporting evidence (specific indicators + why they matter)
        - A transmission chain (how cause flows to effect)
        - Competing hypotheses it contradicts (populated during competition)

    This is the core data type of Milestone A.
    """

    candidate_id: str = Field(default_factory=lambda: f"cand-{uuid4().hex[:8]}")
    dimension: str = Field(..., description="Primary macro dimension")
    direction: str = Field(..., description="bullish / bearish / neutral")

    # The thesis
    thesis: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="One-sentence thesis: what the hypothesis claims",
    )
    narrative: str = Field(
        default="",
        max_length=1024,
        description="Extended narrative explaining the reasoning",
    )

    # Evidence
    evidence: list[EvidenceClaim] = Field(
        default_factory=list,
        description="Evidence claims that support this hypothesis",
    )

    # Transmission chain
    transmission_chain: list[TransmissionSegment] = Field(
        default_factory=list,
        description="Causal chain from macro driver to market impact",
    )

    # Meta
    source_template: str = Field(
        default="",
        description="Which template generated this candidate",
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    generation_context: dict = Field(default_factory=dict)

    # Computed during competition
    competition_score: float = Field(default=0.5, ge=0.0, le=1.0)

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    @property
    def chain_length(self) -> int:
        return len(self.transmission_chain)

    @property
    def avg_evidence_strength(self) -> float:
        if not self.evidence:
            return 0.0
        return sum(e.strength for e in self.evidence) / len(self.evidence)

    @property
    def avg_chain_reliability(self) -> float:
        if not self.transmission_chain:
            return 0.5
        return sum(s.reliability for s in self.transmission_chain) / len(self.transmission_chain)

    def predicts_indicator_direction(self, indicator: str) -> Optional[str]:
        """Return the direction this hypothesis predicts for a given indicator, or None."""
        for s in self.transmission_chain:
            if s.target == indicator:
                if s.direction == "+":
                    return self.direction
                else:
                    return "bearish" if self.direction == "bullish" else "bullish"
        return None

    def __repr__(self) -> str:
        return (
            f"<CandidateHypothesis [{self.dimension}] {self.direction} "
            f"ev={self.evidence_count} seg={self.chain_length} "
            f"score={self.competition_score:.2f}>"
        )


# ── Competition Types ────────────────────────────────────────────────────────


class EliminationReason(str, Enum):
    """Why a hypothesis was eliminated during competition."""
    DIRECT_CONTRADICTION = "direct_contradiction"       # Predicts opposite direction for same indicator
    WEAKER_EVIDENCE = "weaker_evidence"                  # Same direction but weaker evidence
    BROKEN_TRANSMISSION = "broken_transmission"          # Transmission chain less reliable
    DIMENSION_OVERLAP = "dimension_overlap"             # Duplicate in same dimension, lower score
    LOW_CONFIDENCE = "low_confidence"                    # Below minimum confidence threshold


class ContradictionType(str, Enum):
    """Type of contradiction between two hypotheses."""
    DIRECTION = "direction"          # Predict opposite directions for same indicator
    MECHANISM = "mechanism"          # Incompatible causal mechanisms
    TRANSMISSION = "transmission"    # Rely on contradictory transmission segments


# ── Competition Round ────────────────────────────────────────────────────────


class Contradiction(BaseModel):
    """A detected contradiction between two hypotheses."""
    hypothesis_a: str
    hypothesis_b: str
    contradiction_type: ContradictionType
    indicator: str = Field(default="", description="Indicator on which they disagree, if directional")
    description: str = Field(default="", description="Human-readable explanation of the contradiction")
    severity: float = Field(default=0.5, ge=0.0, le=1.0, description="How severe is this contradiction")


class EliminatedHypothesis(BaseModel):
    """Record of a hypothesis eliminated during competition."""
    candidate_id: str
    eliminated_by: str = Field(default="", description="Candidate ID of the hypothesis that eliminated this")
    reason: EliminationReason
    contradiction: Optional[Contradiction] = Field(default=None)
    detail: str = Field(default="", description="Detailed explanation of why")
    revival_condition: str = Field(
        default="",
        description="Under what condition should this hypothesis be reconsidered",
    )
    eliminated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CompetitionRound(BaseModel):
    """Result of one round of hypothesis competition."""
    round_id: str = Field(default_factory=lambda: f"comp-{uuid4().hex[:6]}")
    candidates_before: int = 0
    candidates_after: int = 0
    contradictions_found: list[Contradiction] = Field(default_factory=list)
    eliminated: list[EliminatedHypothesis] = Field(default_factory=list)
    survivors: list[str] = Field(default_factory=list)
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Selected Hypothesis ──────────────────────────────────────────────────────


class SelectedHypothesis(BaseModel):
    """A hypothesis that survived competition and was selected for the final Top-N."""

    candidate_id: str
    rank: int = 0
    dimension: str = ""
    direction: str = ""
    thesis: str = ""
    evidence_summary: list[str] = Field(default_factory=list)
    transmission_summary: str = Field(default="")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # Why selected
    competition_result: str = Field(
        default="",
        description="How it performed in competition (survived_direct_contradiction / unmatched / etc.)",
    )
    historical_backing: str = Field(
        default="",
        description="What historical precedent supports this hypothesis",
    )

    # For quality tracking
    similarity_to_gold: float = Field(default=0.0, ge=0.0, le=1.0)


class HypothesisEvolutionResult(BaseModel):
    """Complete output of the Hypothesis Evolution pipeline (Milestone A)."""

    run_id: str = Field(default_factory=lambda: f"evol-{uuid4().hex[:8]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Input
    regime: str = ""
    snapshot_summary: str = ""

    # Pipeline stats
    signals_detected: int = 0
    themes_identified: int = 0
    candidates_generated: int = 0
    historical_matches: int = 0

    # Competition
    competition_round: Optional[CompetitionRound] = None

    # Final output
    selected_hypotheses: list[SelectedHypothesis] = Field(default_factory=list)

    @property
    def top5_thesis(self) -> list[str]:
        return [h.thesis for h in self.selected_hypotheses[:5]]
