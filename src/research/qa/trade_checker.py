"""V5.3 Trade Checker — Evaluate trade actionability.

A trade must be:
    1. Actionable (can actually be executed)
    2. Specific (clear instrument, direction, sizing)
    3. Risk-managed (stop loss, position size)
    4. Consistent with the macro narrative
"""

from __future__ import annotations

import re
from typing import Optional

from src.research.qa.schemas import DimensionScore, MemoGrade


class TradeChecker:
    """Evaluate whether trade recommendations are actionable."""

    TRADE_ACTION_SIGNALS = [
        r'\b(?:long|short|buy|sell|overweight|underweight)\b',
        r'\b(?:initiate|enter|establish|add\s+to|reduce|exit)\b',
        r'\b(?:position|trade|allocation|exposure)\b',
    ]

    INSTRUMENT_PATTERNS = [
        r'\b(?:S&P\s*500|SPX|Nasdaq|NDX|UST|Bund|JGB|EUR/USD|USD/JPY)\b',
        r'\b(?:equit(?:y|ies)|bond|treasury|currency|commodity)\b',
        r'\b(?:future|option|swap|etf|index|spread)\b',
    ]

    RISK_MANAGEMENT_SIGNALS = [
        r'\b(?:stop[\s-]?(?:loss|out)|position\s+size|risk\s+per|sizing)\b',
        r'\b(?:drawdown|max\s+loss|risk\s+budget)\b',
    ]

    HORIZON_SIGNALS = [
        r'\b(?:short[\s-]?term|medium[\s-]?term|long[\s-]?term)\b',
        r'\b(?:tactical|strategic)\b',
        r'\b(?:days?|weeks?|months?|quarters?)\s+(?:horizon|view|outlook)\b',
    ]

    CONVICTION_SIGNALS = [
        r'\b(?:high\s+conviction|strong\s+view|core\s+position)\b',
        r'\b(?:moderate\s+conviction|tactical\s+trade)\b',
        r'\b(?:low\s+conviction|pilot\s+position|small\s+size)\b',
    ]

    VAGUE_LANGUAGE = [
        r'\b(?:interesting|maybe|perhaps|possibly|could\s+consider)\b',
        r'\b(?:worth\s+watching|keep\s+an\s+eye\s+on|monitor)\b',
        r'\b(?:might\s+be|seems?\s+like|appears?\s+to\s+be)\b',
    ]

    def __init__(self):
        pass

    def verify(self, text: str) -> DimensionScore:
        """Evaluate trade actionability.

        Args:
            text: Research memo text (especially trade section)

        Returns:
            DimensionScore for trade actionability
        """
        score = DimensionScore(
            dimension="trade_actionability",
            score=100.0,
            weight=0.05,
        )

        if not text.strip():
            score.score = 0.0
            score.findings.append("No trade section present")
            return score

        text_lower = text.lower()
        deductions = 0

        # 1. Check for trade direction signals
        action_count = sum(
            len(re.findall(p, text_lower))
            for p in self.TRADE_ACTION_SIGNALS
        )
        if action_count < 2:
            deductions += 30
            score.findings.append(
                "No clear trade direction — missing long/short/overweight signals"
            )

        # 2. Check for specific instruments
        instrument_count = sum(
            len(re.findall(p, text_lower))
            for p in self.INSTRUMENT_PATTERNS
        )
        if instrument_count < 2:
            deductions += 25
            score.findings.append(
                "No specific instruments mentioned — trades must be expressed"
            )

        # 3. Check risk management
        risk_count = sum(
            len(re.findall(p, text_lower))
            for p in self.RISK_MANAGEMENT_SIGNALS
        )
        if risk_count == 0:
            deductions += 20
            score.findings.append(
                "No risk management mentioned — missing stop loss, sizing"
            )

        # 4. Check time horizon
        horizon_count = sum(
            len(re.findall(p, text_lower))
            for p in self.HORIZON_SIGNALS
        )
        if horizon_count == 0:
            deductions += 10
            score.findings.append(
                "No time horizon specified for trades"
            )

        # 5. Check conviction level
        conviction_count = sum(
            len(re.findall(p, text_lower))
            for p in self.CONVICTION_SIGNALS
        )
        if conviction_count == 0:
            deductions += 5
            score.findings.append(
                "No conviction level stated — needed for position sizing"
            )

        # 6. Check for vague language
        vague_count = sum(
            len(re.findall(p, text_lower))
            for p in self.VAGUE_LANGUAGE
        )
        if vague_count > 3:
            deductions += min((vague_count - 3) * 3, 20)
            score.findings.append(
                f"Vague language in trade section ({vague_count} instances) — "
                "be specific and actionable"
            )

        score.score = max(100 - deductions, 0)
        score.grade = self._to_grade(score.score)

        if score.score < 80:
            score.recommendations.append(
                "Specify: instrument, direction, entry level, stop, target"
            )
            score.recommendations.append(
                "Add position sizing and conviction level"
            )
            score.recommendations.append(
                "State explicit trade horizon"
            )

        return score

    def _to_grade(self, score: float) -> MemoGrade:
        if score >= 90:
            return MemoGrade.A
        elif score >= 80:
            return MemoGrade.B
        elif score >= 65:
            return MemoGrade.C
        return MemoGrade.D
