"""V5.3 Source Verifier — Verify that claims have traceable sources.

Every claim should be traceable to either:
    - A specific data source (BLS, BEA, Fed, etc.)
    - A specific news article
    - A specific document reference
"""

from __future__ import annotations

import re

from src.research.qa.schemas import DimensionScore, MemoGrade


class SourceVerifier:
    """Verify source traceability of research claims."""

    KNOWN_SOURCES = {
        "BLS": ["bls", "bureau of labor statistics", "labor department"],
        "BEA": ["bea", "bureau of economic analysis"],
        "FED": ["federal reserve", "fed", "fomc", "board of governors"],
        "ECB": ["ecb", "european central bank"],
        "BOJ": ["boj", "bank of japan"],
        "PBOC": ["pboc", "people's bank of china"],
        "BOE": ["boe", "bank of england"],
        "IMF": ["imf", "international monetary fund"],
        "BIS": ["bis", "bank for international settlements"],
        "OECD": ["oecd"],
        "WORLD_BANK": ["world bank"],
        "BLOOMBERG": ["bloomberg"],
        "REUTERS": ["reuters"],
        "CENSUS": ["census bureau", "census"],
        "TREASURY": ["treasury", "ust", "us treasury"],
        "CME": ["cme", "fed funds futures", "fedwatch"],
    }

    CITATION_PATTERNS = [
        r"\[(\d+(?:,\s*\d+)*)\]",  # [1], [1,2,3]
        r"\(([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*(\d{4})\)",  # (Author, 2024)
        r"\(([A-Z]+),\s*(\d{4})\)",  # (BLS, 2024)
    ]

    def __init__(self):
        pass

    def verify(self, text: str) -> DimensionScore:
        """Verify source traceability.

        Args:
            text: Research memo text

        Returns:
            DimensionScore for source traceability
        """
        score = DimensionScore(
            dimension="source_traceability",
            score=100.0,
            weight=0.05,
        )

        if not text.strip():
            score.score = 0.0
            return score

        # 1. Count explicit source mentions
        source_mentions = 0
        found_sources = set()
        text_lower = text.lower()

        for source_name, patterns in self.KNOWN_SOURCES.items():
            for pattern in patterns:
                if pattern in text_lower:
                    source_mentions += 1
                    found_sources.add(source_name)
                    break

        # 2. Count citation patterns
        citations = []
        for pattern in self.CITATION_PATTERNS:
            matches = re.findall(pattern, text)
            citations.extend(matches)

        # 3. Score
        deductions = 0

        # Source diversity
        if len(found_sources) < 3:
            deductions += 30
            score.findings.append(
                f"Only {len(found_sources)} sources referenced — "
                "professional research requires multiple source types"
            )
        elif len(found_sources) < 5:
            deductions += 15
            score.findings.append(f"Moderate source diversity: {len(found_sources)} sources")

        # Explicit citations
        if len(citations) < 2:
            deductions += 25
            score.findings.append("Few formal citations — data claims need explicit referencing")
        elif len(citations) < 5:
            deductions += 10
            score.findings.append(f"Limited formal citations: {len(citations)} found")

        # Coverage: key source types
        key_types = ["FED", "BLS", "BEA", "IMF", "BIS"]
        missing = [s for s in key_types if s not in found_sources]
        if len(missing) > 3:
            deductions += 20
            score.findings.append(f"Missing key source types: {', '.join(missing[:3])}")

        score.score = max(100 - deductions, 0)
        score.grade = self._to_grade(score.score)

        if source_mentions > 0:
            score.details = f"Sources found: {', '.join(sorted(found_sources))}"

        if score.score < 80:
            score.recommendations.append("Add explicit data source citations (BLS, BEA, Fed, etc.)")
            score.recommendations.append("Include formal citation brackets [1], [2] for key claims")

        return score

    def _to_grade(self, score: float) -> MemoGrade:
        if score >= 90:
            return MemoGrade.A
        elif score >= 80:
            return MemoGrade.B
        elif score >= 65:
            return MemoGrade.C
        return MemoGrade.D
