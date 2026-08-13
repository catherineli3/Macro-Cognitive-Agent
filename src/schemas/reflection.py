"""Sprint 7 — Reflection schemas.

Reflection is a belief review: HypothesisSet → ReflectionSet.
Outputs are standalone reports; original Hypothesis objects are never mutated.
"""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from src.domain.reflection import FindingSeverity, ReflectionVerdict

# ── Reflection Finding ──────────────────────────────────────────────────────


class ReflectionFinding(BaseModel):
    """A single finding discovered during belief review.

    Types:
        evidence_insufficient  — Too few evidence items to be confident.
        conflicting_evidence   — Supporting and contradicting evidence both present.
        evidence_quality_low   — Evidence contributions are weak on average.
        single_source_risk     — All supporting evidence comes from one indicator.
    """

    type: str = Field(
        ...,
        min_length=1,
        max_length=40,
        description="Finding category",
    )
    severity: FindingSeverity = Field(
        default=FindingSeverity.MAJOR,
        description="Impact level on belief",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Human-readable description of the finding",
    )


# ── Reflection Report ───────────────────────────────────────────────────────


class ReflectionReport(BaseModel):
    """Belief review result for a single hypothesis.

    Answers three questions:
    1. Is the evidence sufficient?
    2. Is the evidence internally consistent?
    3. Should we still believe this hypothesis?
    """

    hypothesis_id: str = Field(
        default_factory=lambda: uuid4().hex[:12],
        min_length=1,
        max_length=64,
    )
    statement: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="The hypothesis statement being reviewed",
    )
    original_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Agent's confidence before review",
    )
    updated_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Agent's confidence after belief review",
    )
    verdict: ReflectionVerdict = Field(
        default=ReflectionVerdict.UNCERTAIN,
        description="Should we still believe this?",
    )
    findings: list[ReflectionFinding] = Field(
        default_factory=list,
        description="All issues discovered during review",
    )
    evidence_sufficiency: str = Field(
        default="medium",
        pattern=r"^(high|medium|low)$",
        description="Do we have enough evidence? (high | medium | low)",
    )
    evidence_consistency: str = Field(
        default="consistent",
        pattern=r"^(consistent|mixed|conflicting)$",
        description="Is the evidence internally consistent?",
    )
    review_summary: str = Field(
        default="",
        min_length=0,
        max_length=1024,
        description="One-sentence summary of the belief review",
    )
    reviewed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the review was performed",
    )

    # ── Computed helpers ─────────────────────────────────────────────────

    @property
    def confidence_delta(self) -> float:
        """How much did confidence change?"""
        return self.updated_confidence - self.original_confidence

    @property
    def has_critical_findings(self) -> bool:
        return any(f.severity == FindingSeverity.CRITICAL for f in self.findings)

    @property
    def finding_count(self) -> int:
        return len(self.findings)


# ── Reflection Set ──────────────────────────────────────────────────────────


class ReflectionSet(BaseModel):
    """Complete belief review output for a set of hypotheses."""

    reviewed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    reports: list[ReflectionReport] = Field(
        default_factory=list,
        description="One report per hypothesis reviewed",
    )
    summary: str = Field(
        default="",
        description="Overall review summary",
    )

    # ── Convenience ──────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return len(self.reports)

    @property
    def confirmed(self) -> list[ReflectionReport]:
        return [r for r in self.reports if r.verdict == ReflectionVerdict.CONFIRMED]

    @property
    def refuted(self) -> list[ReflectionReport]:
        return [r for r in self.reports if r.verdict == ReflectionVerdict.REFUTED]

    @property
    def uncertain(self) -> list[ReflectionReport]:
        return [r for r in self.reports if r.verdict == ReflectionVerdict.UNCERTAIN]

    def get_by_hypothesis_id(self, hypothesis_id: str) -> ReflectionReport | None:
        for r in self.reports:
            if r.hypothesis_id == hypothesis_id:
                return r
        return None
