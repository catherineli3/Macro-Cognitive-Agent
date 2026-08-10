"""MarketExpectationExtractor — Compare data vs expectations.

Quality: "Did CPI beat expectations?" is more important than "CPI is 2.8%".
Professional researchers always compare reality to expectations because
markets price the delta, not the level.

This module:
    1. Extracts consensus vs actual from data releases
    2. Computes surprise magnitude (std dev if available)
    3. Infers implication for macro narrative
    4. Tags if surprise is statistically significant
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from src.news.schemas import ResearchEvent, MarketExpectation, ImpactDirection


class MarketExpectationExtractor:
    """Extract and evaluate market expectations vs actual data.

    Core question: "Was this a surprise — and how big?"
    """

    # Common indicators and their typical behavior
    INDICATOR_PROFILES = {
        "cpi_yoy": {"name": "CPI YoY", "typical_range": (-0.5, 0.5), "std_dev": 0.15,
                    "bullish_surprise": "negative"},
        "core_cpi_yoy": {"name": "Core CPI YoY", "typical_range": (-0.3, 0.3), "std_dev": 0.12,
                         "bullish_surprise": "negative"},
        "cpi_mom": {"name": "CPI MoM", "typical_range": (-0.2, 0.2), "std_dev": 0.10,
                    "bullish_surprise": "negative"},
        "ppi_yoy": {"name": "PPI YoY", "typical_range": (-0.5, 0.5), "std_dev": 0.30,
                    "bullish_surprise": "negative"},
        "nfp": {"name": "Non-Farm Payrolls", "typical_range": (-100e3, 100e3), "std_dev": 80e3,
                "bullish_surprise": "positive"},
        "unemployment_rate": {"name": "Unemployment Rate", "typical_range": (-0.2, 0.2),
                               "std_dev": 0.1, "bullish_surprise": "negative"},
        "gdp_qoq": {"name": "GDP QoQ", "typical_range": (-1.0, 1.0), "std_dev": 0.5,
                    "bullish_surprise": "positive"},
        "retail_sales_mom": {"name": "Retail Sales MoM", "typical_range": (-1.0, 1.0),
                              "std_dev": 0.5, "bullish_surprise": "positive"},
        "ism_manufacturing": {"name": "ISM Manufacturing PMI", "typical_range": (-3.0, 3.0),
                               "std_dev": 1.5, "bullish_surprise": "positive"},
        "ism_services": {"name": "ISM Services PMI", "typical_range": (-2.0, 2.0),
                          "std_dev": 1.2, "bullish_surprise": "positive"},
    }

    def __init__(self):
        pass

    def extract(self, event: ResearchEvent) -> Optional[MarketExpectation]:
        """Extract market expectation analysis from a data release event.

        Returns None if the event doesn't have enough data for comparison.
        """
        if not event.consensus_expectation or event.actual_value is None:
            return None

        # Identify the indicator
        indicator = self._identify_indicator(event)

        # Compute surprise
        surprise = event.actual_value - event.consensus_expectation
        profile = self.INDICATOR_PROFILES.get(indicator, {})

        # Estimate surprise std
        std_dev = profile.get("std_dev")
        surprise_std = surprise / std_dev if std_dev and std_dev > 0 else None

        # Is it significant?
        is_significant = abs(surprise_std) > 1.0 if surprise_std else abs(surprise) > 0.0

        # Direction
        bullish_dir = profile.get("bullish_surprise", "positive")
        if surprise > 0:
            direction = ImpactDirection.BULLISH if bullish_dir == "positive" else ImpactDirection.BEARISH
        elif surprise < 0:
            direction = ImpactDirection.BEARISH if bullish_dir == "positive" else ImpactDirection.BULLISH
        else:
            direction = ImpactDirection.NEUTRAL

        # Implication
        implication = self._build_implication(indicator, surprise, is_significant, direction)

        # Market reaction context
        market_reaction = self._infer_reaction(indicator, surprise, is_significant)

        return MarketExpectation(
            expectation_id=f"EXP_{str(uuid.uuid4())[:8]}",
            event_id=event.event_id,
            indicator=indicator,
            consensus_forecast=event.consensus_expectation,
            prior_value=event.key_numbers.get("prior"),
            actual_value=event.actual_value,
            surprise=round(surprise, 4),
            surprise_std=round(surprise_std, 2) if surprise_std else None,
            is_significant_surprise=is_significant,
            surprise_direction=direction,
            market_reaction=market_reaction,
            implication=implication,
        )

    def extract_batch(self, events: list[ResearchEvent]) -> list[MarketExpectation]:
        """Extract expectations from a batch of events."""
        expectations = []
        for event in events:
            exp = self.extract(event)
            if exp:
                expectations.append(exp)
        return expectations

    def aggregate_surprises(self, expectations: list[MarketExpectation]) -> dict:
        """Aggregate surprises across multiple indicators.

        Returns a macro surprise index-like summary.
        """
        if not expectations:
            return {"summary": "No expectation data available"}

        bullish_count = 0
        bearish_count = 0
        significant_count = 0
        total_surprise = 0.0

        for exp in expectations:
            if exp.surprise_direction == ImpactDirection.BULLISH:
                bullish_count += 1
            elif exp.surprise_direction == ImpactDirection.BEARISH:
                bearish_count += 1
            if exp.is_significant_surprise:
                significant_count += 1
            total_surprise += exp.surprise or 0

        # Net surprise direction
        if bullish_count > bearish_count * 1.5:
            net_direction = "Data generally beating expectations (bullish bias)"
        elif bearish_count > bullish_count * 1.5:
            net_direction = "Data generally missing expectations (bearish bias)"
        else:
            net_direction = "Data mixed vs expectations"

        return {
            "summary": net_direction,
            "total_releases": len(expectations),
            "beating_expectations": bullish_count,
            "missing_expectations": bearish_count,
            "significant_surprises": significant_count,
            "surprise_index": round(total_surprise / max(len(expectations), 1), 4),
        }

    # ── Helpers ──

    def _identify_indicator(self, event: ResearchEvent) -> str:
        """Identify which economic indicator this event represents."""
        text = (event.title + " " + event.description).lower()

        indicator_map = [
            (["cpi", "consumer price"], "cpi_yoy"),
            (["core cpi"], "core_cpi_yoy"),
            (["ppi", "producer price"], "ppi_yoy"),
            (["nfp", "non-farm", "payroll", "employment", "jobs report"], "nfp"),
            (["unemployment rate", "jobless rate"], "unemployment_rate"),
            (["gdp", "gross domestic product"], "gdp_qoq"),
            (["retail sales"], "retail_sales_mom"),
            (["ism manufacturing", "manufacturing pmi"], "ism_manufacturing"),
            (["ism services", "services pmi", "non-manufacturing"], "ism_services"),
        ]

        for keywords, indicator_id in indicator_map:
            if any(k in text for k in keywords):
                return indicator_id

        # Extract from key_numbers
        for key in event.key_numbers:
            if key.lower() in self.INDICATOR_PROFILES:
                return key.lower()

        return "unknown"

    def _build_implication(
        self, indicator: str, surprise: float, is_significant: bool,
        direction: ImpactDirection
    ) -> str:
        """Build a 1-2 sentence implication statement."""
        profile = self.INDICATOR_PROFILES.get(indicator, {})
        indicator_name = profile.get("name", indicator)

        if not is_significant:
            return (f"{indicator_name} came in roughly in line with expectations "
                    f"(surprise: {surprise:.2f}). No material information content "
                    f"for this release.")

        severity = ""
        if abs(surprise) > 0:
            # Estimate severity
            if profile.get("std_dev"):
                ratio = abs(surprise) / profile["std_dev"]
                if ratio > 2:
                    severity = "substantially "
                elif ratio > 1.5:
                    severity = "notably "

        return (
            f"{indicator_name} {severity}"
            f"{'beat' if direction == ImpactDirection.BULLISH else 'missed'} "
            f"expectations (actual: {surprise + (event.consensus_expectation or 0):.2%} "
            f"vs consensus 0.00% in normalized space). "
            f"This {'supports' if direction == ImpactDirection.BULLISH else 'challenges'} "
            f"the prevailing macro narrative."
        )

    @staticmethod
    def _infer_reaction(indicator: str, surprise: float, is_significant: bool) -> str:
        """Infer typical market reaction to this indicator surprise."""
        if not is_significant:
            return "Minimal market reaction expected (in-line data)"

        typical_reactions = {
            "cpi_yoy": "Bonds rally, USD weaker on downside surprise / Bonds sell, USD stronger on upside",
            "core_cpi_yoy": "Similar to CPI — core more important for policy",
            "nfp": "Stocks love moderate beats (150-250k), fear extreme beats (>300k, wage inflation)",
            "gdp_qoq": "Growth surprise → equities positive, bonds negative (rates higher)",
            "ism_manufacturing": "Above 50 beat → cyclical rotation positive",
        }

        return typical_reactions.get(indicator, "Typical risk-on/risk-off reaction based on surprise direction")
