"""V5.3 Reasoning Checker — Verify logical coherence and reasoning consistency.

Checks:
    1. Observations → Evidence → Hypothesis chain integrity
    2. No contradictory statements
    3. Reasoning flows logically (not just assertion stacking)
    4. Evidence actually supports stated conclusions
"""

from __future__ import annotations

import re

from src.research.qa.schemas import DimensionScore, MemoGrade


class ReasoningChecker:
    """Verify reasoning consistency in research output."""

    # Contradiction pair patterns
    CONTRADICTION_PAIRS = [
        (r"\b(?:hawkish|tightening|hiking)\b", r"\b(?:dovish|easing|cutting)\b"),
        (r"\b(?:bullish|positive|constructive)\b", r"\b(?:bearish|negative|cautious)\b"),
        (
            r"\b(?:strong\s+(?:growth|economy|demand))\b",
            r"\b(?:weak\s+(?:growth|economy|demand))\b",
        ),
        (r"\b(?:high\s+inflation)\b", r"\b(?:low\s+inflation|deflation)\b"),
        (r"\b(?:tight\s+labor)\b", r"\b(?:weak\s+labor|slack)\b"),
        (r"\b(?:rising\s+(?:yields?|rates?))\b", r"\b(?:falling\s+(?:yields?|rates?))\b"),
    ]

    LOGICAL_CONNECTORS = [
        r"\btherefore\b",
        r"\bthus\b",
        r"\bhence\b",
        r"\baccordingly\b",
        r"\bconsequently\b",
        r"\bas\s+a\s+result\b",
        r"\bthis\s+(?:implies|suggests|indicates|means|points\s+to)\b",
        r"\bbecause\b",
        r"\bsince\b",
        r"\bdue\s+to\b",
        r"\bgiven\s+that\b",
        r"\b(?:if|when)\s+.+\bthen\b",
    ]

    REASONING_MARKERS = [
        r"\bobservation\b",
        r"\bhypothesis\b",
        r"\bevidence\b",
        r"\bconclusion\b",
        r"\bimplies\b",
        r"\btherefore\b",
    ]

    def __init__(self):
        pass

    def verify(self, text: str) -> DimensionScore:
        """Verify reasoning consistency.

        Args:
            text: Research memo text

        Returns:
            DimensionScore for reasoning consistency
        """
        score = DimensionScore(
            dimension="reasoning_consistency",
            score=100.0,
            weight=0.20,
        )

        if not text.strip():
            score.score = 0.0
            return score

        text_lower = text.lower()
        deductions = 0

        # 1. Check for reasoning structure markers
        reasoning_markers = sum(1 for p in self.REASONING_MARKERS if re.search(p, text_lower))
        if reasoning_markers < 3:
            deductions += 20
            score.findings.append(
                "Weak reasoning structure — missing observation, evidence, "
                "hypothesis, or conclusion markers"
            )
        elif reasoning_markers < 5:
            deductions += 10
            score.findings.append("Moderate reasoning structure — some steps missing")

        # 2. Check for logical connectors
        logical_count = sum(len(re.findall(p, text_lower)) for p in self.LOGICAL_CONNECTORS)
        if logical_count < 5:
            deductions += 15
            score.findings.append("Few logical connectors — reasoning may be assertion-based")

        # 3. Check for contradictions
        contradictions = self._find_contradictions(text_lower)
        if contradictions:
            deductions += min(len(contradictions) * 15, 40)
            score.findings.append(
                f"Possible contradictions detected: {', '.join(contradictions[:3])}"
            )

        # 4. Check argument structure
        paragraphs = [p for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) < 4:
            deductions += 15
            score.findings.append("Too few paragraphs for coherent reasoning structure")

        # 5. Check for unqualified jumps
        jump_markers = re.findall(
            r"\b(?:therefore|thus|hence)\s+.*?[.!?]",
            text_lower,
        )
        if len(jump_markers) > 5:
            deductions += 10
            score.findings.append("Many 'therefore/thus/hence' jumps — check each logical leap")

        score.score = max(100 - deductions, 0)
        score.grade = self._to_grade(score.score)

        if score.score < 80:
            score.recommendations.append(
                "Structure arguments as: Observation → Evidence → Hypothesis → Conclusion"
            )
            score.recommendations.append("Ensure each 'therefore' has explicit preceding evidence")

        return score

    def _find_contradictions(self, text: str) -> list[str]:
        """Find pairs of contradictory statements."""
        found = []
        for pos_pattern, neg_pattern in self.CONTRADICTION_PAIRS:
            has_pos = bool(re.search(pos_pattern, text))
            has_neg = bool(re.search(neg_pattern, text))
            if has_pos and has_neg:
                # Check context — are they in different contexts?
                # If both are author's statements, it's a contradiction
                found.append(
                    f"{re.search(pos_pattern, text).group(0)} vs "
                    f"{re.search(neg_pattern, text).group(0)}"
                )
        return found[:3]

    def _to_grade(self, score: float) -> MemoGrade:
        if score >= 90:
            return MemoGrade.A
        elif score >= 80:
            return MemoGrade.B
        elif score >= 65:
            return MemoGrade.C
        return MemoGrade.D
