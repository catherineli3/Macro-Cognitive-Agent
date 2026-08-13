"""V5.3 Causal Checker — Verify causal reasoning quality.

Professional macro research requires causal chains, not correlations.
This checker evaluates:
    1. Is there a causal mechanism explained, not just correlation?
    2. Are confounding variables acknowledged?
    3. Is the direction of causality correct?
    4. Are feedback loops considered?
"""

from __future__ import annotations

import re

from src.research.qa.schemas import DimensionScore, MemoGrade


class CausalChecker:
    """Verify causal completeness in research output."""

    CAUSAL_MECHANISM_PATTERNS = [
        r"\b(?:mechanism|channel|transmission|pass[\s-]?through)\b",
        r"\b(?:drives?|causes?|leads?\s+to|results?\s+in)\b",
        r"\b(?:because|since|due\s+to|as\s+a\s+consequence)\b",
        r"\b(?:transmits?\s+(?:through|via)|propagates?\s+(?:through|via))\b",
    ]

    CORRELATION_ONLY_PATTERNS = [
        r"\b(?:correlated|associated|linked|connected|related)\s+(?:with|to)\b",
        r"\b(?:tends?\s+to|often|typically|usually)\s+(?:move|go|be)\b",
    ]

    CONFOUNDING_PATTERNS = [
        r"\b(?:confounding|third\s+factor|spurious|common\s+cause)\b",
        r"\b(?:alternative\s+explanation|not\s+causal|coincidence)\b",
    ]

    FEEDBACK_PATTERNS = [
        r"\b(?:feedback|self[\s-]?reinforcing|virtuous\s+cycle|vicious\s+cycle)\b",
        r"\b(?:second[\s-]?order\s+effect|feedback\s+loop|reflexive)\b",
    ]

    def __init__(self):
        pass

    def verify(self, text: str) -> DimensionScore:
        """Verify causal completeness.

        Args:
            text: Research memo text

        Returns:
            DimensionScore for causal completeness
        """
        score = DimensionScore(
            dimension="causal_completeness",
            score=100.0,
            weight=0.15,
        )

        if not text.strip():
            score.score = 0.0
            return score

        text_lower = text.lower()
        deductions = 0

        # 1. Check causal mechanism explanations
        mechanism_count = sum(
            len(re.findall(p, text_lower)) for p in self.CAUSAL_MECHANISM_PATTERNS
        )
        if mechanism_count < 3:
            deductions += 30
            score.findings.append("No clear causal mechanism explained — only correlations stated")
        elif mechanism_count < 6:
            deductions += 15
            score.findings.append(
                f"Weak causal explanation — only {mechanism_count} mechanism references"
            )

        # 2. Check correlation-only language (warning sign)
        correlation_count = sum(
            len(re.findall(p, text_lower)) for p in self.CORRELATION_ONLY_PATTERNS
        )
        if correlation_count > mechanism_count:
            deductions += 20
            score.findings.append(
                f"More correlation language ({correlation_count}) than causal "
                f"language ({mechanism_count}) — research reads as descriptive"
            )

        # 3. Check for confounding acknowledgment
        confound_count = sum(len(re.findall(p, text_lower)) for p in self.CONFOUNDING_PATTERNS)
        if confound_count == 0 and mechanism_count > 5:
            deductions += 10
            score.findings.append("No acknowledgment of potential confounding factors")

        # 4. Check for feedback loop consideration
        feedback_count = sum(len(re.findall(p, text_lower)) for p in self.FEEDBACK_PATTERNS)
        if feedback_count == 0:
            deductions += 10
            score.findings.append("No consideration of second-order effects or feedback loops")

        # 5. Check direction of causality
        reverse_causality = re.findall(
            r"\b(?:reverse\s+caus|endogeneity|simultaneity)\b",
            text_lower,
        )
        if not reverse_causality and mechanism_count > 3:
            deductions += 5
            score.findings.append("No discussion of causality direction")

        # 6. Chain length check — does reasoning have multiple causal steps?
        sentences = re.split(r"[.!?]+", text)
        causal_sentences = [
            s
            for s in sentences
            if any(re.search(p, s.lower()) for p in self.CAUSAL_MECHANISM_PATTERNS)
        ]
        if len(causal_sentences) < 3:
            deductions += 10
            score.findings.append(
                "Causal chain too short — professional research requires "
                "multi-step causal reasoning"
            )

        score.score = max(100 - deductions, 0)
        score.grade = self._to_grade(score.score)

        if score.score < 80:
            score.recommendations.append(
                "Replace correlation language with explicit causal mechanisms"
            )
            score.recommendations.append("Explain the transmission channel: What → How → Why")
            score.recommendations.append("Consider second-order effects and feedback loops")

        return score

    def _to_grade(self, score: float) -> MemoGrade:
        if score >= 90:
            return MemoGrade.A
        elif score >= 80:
            return MemoGrade.B
        elif score >= 65:
            return MemoGrade.C
        return MemoGrade.D
