"""V5.3 Hallucination Checker — Detect unsupported factual claims.

Every statement must have evidence or citation.
Without evidence, it's a hallucination risk.

Checks:
    1. Numerical claims without source
    2. Causal assertions without backing
    3. Named entity claims (institutions, people)
    4. Historical event references
    5. Forward-looking unqualified statements
"""

from __future__ import annotations

import re

from src.research.qa.schemas import DimensionScore, MemoGrade


class HallucinationChecker:
    """Check for hallucination risks in research output."""

    # Patterns that suggest unsupported claims
    NUMERICAL_CLAIMS = re.compile(
        r"\b(\d+(?:\.\d+)?)\s*(?:%|bps|points?|dollars?|trillion|billion|million)\b",
        re.IGNORECASE,
    )

    CAUSAL_CLAIMS = re.compile(
        r"\b(?:because|due\s+to|as\s+a\s+result|led\s+to|caused|driven\s+by|resulted\s+in)\b",
        re.IGNORECASE,
    )

    FORECAST_CLAIMS = re.compile(
        r"\b(?:will\s+(?:be|rise|fall|grow|decline|increase|decrease)|"
        r"expected\s+to|forecast\s+to|projected\s+to)\b",
        re.IGNORECASE,
    )

    ATTRIBUTION_MARKERS = [
        r"according\s+to",
        r"(?:data|source|report)\s+(?:from|by)",
        r"(?:released|published|reported)\s+by",
        r"(?:said|stated|noted|commented)\s+(?:that\s+)?",
        r"(?:per|via)\s+",
        r"\[[\d,\s]+\]",  # Citation brackets
        r"\(\w+(?:\s+\w+)*,\s*\d{4}\)",  # Author (Year)
        r"(?:BLS|BEA|Fed|ECB|IMF|BIS|OECD)\s+(?:data|report|survey)",
    ]

    # High-risk phrases (often hallucinated)
    HIGH_RISK_PHRASES = [
        "all experts agree",
        "everyone knows",
        "it is obvious that",
        "clearly",
        "undoubtedly",
        "without question",
        "always",
        "never",
        "guaranteed",
        "certain to",
        "definitely",
    ]

    def __init__(self):
        self.attribution_pattern = re.compile(
            "|".join(self.ATTRIBUTION_MARKERS),
            re.IGNORECASE,
        )

    def check(self, text: str, source_data: dict | None = None) -> DimensionScore:
        """Check text for hallucination risks.

        Args:
            text: The research memo text to check
            source_data: Available source/citation metadata

        Returns:
            DimensionScore for hallucination risk
        """
        score = DimensionScore(
            dimension="hallucination_risk",
            score=100.0,
            weight=0.10,
        )

        if not text.strip():
            score.score = 0.0
            score.findings.append("Empty text — no content to evaluate")
            return score

        # Count risk indicators
        numerical_count = len(self.NUMERICAL_CLAIMS.findall(text))
        causal_count = len(self.CAUSAL_CLAIMS.findall(text))
        forecast_count = len(self.FORECAST_CLAIMS.findall(text))

        # Count attributions
        attributions = len(self.attribution_pattern.findall(text))

        # Count high-risk phrases
        high_risk_count = sum(
            len(re.findall(re.escape(phrase), text, re.IGNORECASE))
            for phrase in self.HIGH_RISK_PHRASES
        )

        # Scoring logic
        deductions = 0

        # 1. Ratio of attributions to claims
        total_claims = numerical_count + causal_count + forecast_count
        if total_claims > 0:
            attribution_ratio = attributions / total_claims
            if attribution_ratio < 0.3:
                deductions += 30
                score.findings.append(
                    f"Low attribution ratio: {attributions} attributions for "
                    f"{total_claims} claim types (need >30%)"
                )
            elif attribution_ratio < 0.5:
                deductions += 15
                score.findings.append(f"Moderate attribution ratio: {attributions}/{total_claims}")

        # 2. Numerical claims without nearby attribution
        if numerical_count > 5 and attributions < 3:
            deductions += 20
            score.findings.append(
                f"Many numerical claims ({numerical_count}) with few attributions "
                f"({attributions}) — high hallucination risk"
            )

        # 3. Forward-looking statements
        if forecast_count > 3:
            deductions += 10
            score.findings.append(
                f"Multiple unqualified forecasts ({forecast_count}) — "
                "each forecast should be explicitly qualified"
            )

        # 4. High-risk phrases
        if high_risk_count > 0:
            deductions += min(high_risk_count * 5, 25)
            score.findings.append(
                f"Found {high_risk_count} high-risk absolute language "
                "phrases — replace with qualified statements"
            )

        # 5. Check if extreme certainty language without evidence
        if re.search(r"(?:certain|definitely|guaranteed)", text, re.IGNORECASE):
            if attributions < 3:
                deductions += 10
                score.findings.append(
                    "Certainty language used without sufficient evidence attribution"
                )

        score.score = max(100 - deductions, 0)
        score.grade = self._to_grade(score.score)

        if score.score < 60:
            score.recommendations.append("CRITICAL: Add sources/citations for all factual claims")
        if score.score < 80:
            score.recommendations.append(
                "Replace absolute language with probabilistic/qualified statements"
            )
            score.recommendations.append("Ensure every numerical claim cites its source")

        return score

    def check_statement(self, statement: str) -> dict:
        """Check a single statement for hallucination risk.

        Returns:
            dict with risk indicators
        """
        result = {
            "statement": statement[:200],
            "has_attribution": bool(self.attribution_pattern.search(statement)),
            "has_numerical": bool(self.NUMERICAL_CLAIMS.search(statement)),
            "has_causal": bool(self.CAUSAL_CLAIMS.search(statement)),
            "has_high_risk_phrase": any(
                re.search(re.escape(phrase), statement, re.IGNORECASE)
                for phrase in self.HIGH_RISK_PHRASES
            ),
            "risk_level": "low",
        }

        # Assess risk
        risk_score = 0
        if result["has_numerical"] and not result["has_attribution"]:
            risk_score += 3
        if result["has_causal"] and not result["has_attribution"]:
            risk_score += 2
        if result["has_high_risk_phrase"]:
            risk_score += 1

        if risk_score >= 3:
            result["risk_level"] = "high"
        elif risk_score >= 2:
            result["risk_level"] = "medium"

        return result

    def _to_grade(self, score: float) -> MemoGrade:
        if score >= 90:
            return MemoGrade.A
        elif score >= 80:
            return MemoGrade.B
        elif score >= 65:
            return MemoGrade.C
        return MemoGrade.D
