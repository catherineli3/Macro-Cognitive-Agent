"""V5.3 QA Schemas — Scoring models for research quality evaluation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MemoGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class QAVerdict(str, Enum):
    PASS = "pass"  # Score >= 80
    CONDITIONAL = "conditional"  # 70-79, can publish with warnings
    REJECT = "reject"  # < 70, must regenerate


@dataclass
class DimensionScore:
    """Score for a single quality dimension."""

    dimension: str
    score: float  # 0-100
    weight: float  # Relative weight in total
    grade: MemoGrade = MemoGrade.C
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    details: str = ""


@dataclass
class ResearchScoreCard:
    """Complete quality scorecard for a research memo or pipeline output."""

    scorecard_id: str = field(default_factory=lambda: f"qa_{uuid.uuid4().hex[:8]}")
    evaluated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    memo_id: str = ""

    # Dimension scores
    evidence_coverage: DimensionScore = field(
        default_factory=lambda: DimensionScore(
            dimension="evidence_coverage",
            score=0.0,
            weight=0.20,
        )
    )
    reasoning_consistency: DimensionScore = field(
        default_factory=lambda: DimensionScore(
            dimension="reasoning_consistency",
            score=0.0,
            weight=0.20,
        )
    )
    causal_completeness: DimensionScore = field(
        default_factory=lambda: DimensionScore(
            dimension="causal_completeness",
            score=0.0,
            weight=0.15,
        )
    )
    counter_quality: DimensionScore = field(
        default_factory=lambda: DimensionScore(
            dimension="counter_quality",
            score=0.0,
            weight=0.15,
        )
    )
    prediction_testability: DimensionScore = field(
        default_factory=lambda: DimensionScore(
            dimension="prediction_testability",
            score=0.0,
            weight=0.10,
        )
    )
    trade_actionability: DimensionScore = field(
        default_factory=lambda: DimensionScore(
            dimension="trade_actionability",
            score=0.0,
            weight=0.05,
        )
    )
    hallucination_risk: DimensionScore = field(
        default_factory=lambda: DimensionScore(
            dimension="hallucination_risk",
            score=0.0,
            weight=0.10,
        )
    )
    source_traceability: DimensionScore = field(
        default_factory=lambda: DimensionScore(
            dimension="source_traceability",
            score=0.0,
            weight=0.05,
        )
    )

    # Aggregate
    total_score: float = 0.0
    grade: MemoGrade = MemoGrade.D
    verdict: QAVerdict = QAVerdict.REJECT

    # Summary
    overall_assessment: str = ""
    critical_issues: list[str] = field(default_factory=list)
    improvement_actions: list[str] = field(default_factory=list)

    @property
    def dimensions(self) -> list[DimensionScore]:
        """All dimension scores in order."""
        return [
            self.evidence_coverage,
            self.reasoning_consistency,
            self.causal_completeness,
            self.counter_quality,
            self.prediction_testability,
            self.trade_actionability,
            self.hallucination_risk,
            self.source_traceability,
        ]

    def compute_total(self):
        """Compute weighted total score and assign grade/verdict."""
        total = sum(d.score * d.weight for d in self.dimensions)
        self.total_score = round(total, 1)

        # Assign grade
        if self.total_score >= 93:
            self.grade = MemoGrade.A_PLUS
        elif self.total_score >= 85:
            self.grade = MemoGrade.A
        elif self.total_score >= 75:
            self.grade = MemoGrade.B
        elif self.total_score >= 65:
            self.grade = MemoGrade.C
        elif self.total_score >= 55:
            self.grade = MemoGrade.D
        else:
            self.grade = MemoGrade.F

        # Assign verdict
        if self.total_score >= 80:
            self.verdict = QAVerdict.PASS
        elif self.total_score >= 70:
            self.verdict = QAVerdict.CONDITIONAL
        else:
            self.verdict = QAVerdict.REJECT

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "scorecard_id": self.scorecard_id,
            "evaluated_at": self.evaluated_at,
            "memo_id": self.memo_id,
            "total_score": self.total_score,
            "grade": self.grade.value,
            "verdict": self.verdict.value,
            "dimensions": [
                {
                    "name": d.dimension,
                    "score": d.score,
                    "weight": d.weight,
                    "grade": d.grade.value,
                    "findings": d.findings[:3],
                    "recommendations": d.recommendations[:3],
                }
                for d in self.dimensions
            ],
            "overall_assessment": self.overall_assessment,
            "critical_issues": self.critical_issues,
            "improvement_actions": self.improvement_actions,
        }

    def summary(self) -> str:
        """Human-readable summary."""
        status = {
            QAVerdict.PASS: "[APPROVED]",
            QAVerdict.CONDITIONAL: "[CONDITIONAL - Requires Review]",
            QAVerdict.REJECT: "[REJECTED - Must Regenerate]",
        }
        return (
            f"ResearchScoreCard: {self.total_score:.1f}/100 "
            f"({self.grade.value}) {status[self.verdict]}"
        )
