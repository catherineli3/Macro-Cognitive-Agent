"""HistoricalSimilarity — match current regime to historical periods.

Finds the closest historical analogs using multi-dimensional similarity scoring:
    - Growth profile similarity
    - Inflation profile similarity
    - Policy stance similarity
    - Credit cycle similarity
    - Dollar regime similarity
    - Volatility regime similarity

Historical database covers major macro regimes since 1970s.
"""

from __future__ import annotations
from typing import Optional
from src.regime.schemas import HistoricalAnalog, MacroRegime


# Database of historical macro regime periods
HISTORICAL_PERIODS = [
    {
        "period": "1973-1975", "name": "Oil Shock / Stagflation",
        "growth": "decelerating", "inflation": "stagflation",
        "monetary": "tightening", "credit": "contraction",
        "dollar": "weak", "volatility": "high_vol",
        "resolution": "Deep recession, then recovery. Fed ultimately cut rates.",
        "duration": 24, "drawdown": 48,
        "lessons": [
            "Supply shocks + tight policy = worst case for risk assets",
            "Gold and commodities outperform in stagflation",
            "Policy pivot takes longer than expected in inflation regimes",
        ],
    },
    {
        "period": "1998-2000", "name": "Tech Bubble / Late Cycle",
        "growth": "accelerating", "inflation": "disinflation",
        "monetary": "tightening", "credit": "expansion",
        "dollar": "strong", "volatility": "low_vol",
        "resolution": "Bubble burst, recession, aggressive easing cycle",
        "duration": 30, "drawdown": 49,
        "lessons": [
            "Low inflation + strong dollar mask late-cycle risks",
            "Productivity boom can extend cycles longer than expected",
            "When credit starts tightening, equity follows with 6-month lag",
        ],
    },
    {
        "period": "2006-2007", "name": "Housing Bubble Peak / Pre-GFC",
        "growth": "decelerating", "inflation": "reflation",
        "monetary": "tightening", "credit": "peak",
        "dollar": "weak", "volatility": "low_vol",
        "resolution": "Global financial crisis, systemic credit collapse",
        "duration": 18, "drawdown": 57,
        "lessons": [
            "Credit cycle is the cycle — when credit peaks, everything changes",
            "Low VIX does not mean low risk — it means unrecognized risk",
            "Housing as transmission mechanism: credit → housing → banking → global",
        ],
    },
    {
        "period": "2008-2009", "name": "GFC / Credit Event",
        "growth": "decelerating", "inflation": "deflation",
        "monetary": "easing", "credit": "contraction",
        "dollar": "strong", "volatility": "crisis",
        "resolution": "Unprecedented policy response, slow recovery",
        "duration": 18, "drawdown": 57,
        "lessons": [
            "In credit events, correlations go to 1 — everything sells off",
            "Dollar funding stress is the real crisis transmission mechanism",
            "Policy response matters most in the recovery phase, not the crisis",
        ],
    },
    {
        "period": "2010-2015", "name": "QE Era / Recovery",
        "growth": "stable", "inflation": "disinflation",
        "monetary": "easing", "credit": "expansion",
        "dollar": "weak", "volatility": "normal",
        "resolution": "Gradual normalization, then tightening cycle began",
        "duration": 60, "drawdown": 20,
        "lessons": [
            "QE can support assets without generating inflation (for a long time)",
            "Zero rates create reach-for-yield behavior across all assets",
            "Exit from unconventional policy is extremely difficult",
        ],
    },
    {
        "period": "2018 Q4", "name": "Tightening Tantrum",
        "growth": "decelerating", "inflation": "reflation",
        "monetary": "tightening", "credit": "peak",
        "dollar": "strong", "volatility": "high_vol",
        "resolution": "Fed pivot, rapid recovery into 2019",
        "duration": 4, "drawdown": 20,
        "lessons": [
            "Markets force Fed pivots faster than expected",
            "Strong dollar + tight policy = EM crisis risk",
            "Short but sharp corrections are buying opportunities if Fed pivots",
        ],
    },
    {
        "period": "2020", "name": "COVID Crisis",
        "growth": "decelerating", "inflation": "deflation",
        "monetary": "easing", "credit": "contraction",
        "dollar": "strong", "volatility": "crisis",
        "resolution": "Massive fiscal + monetary response, V-shaped recovery",
        "duration": 3, "drawdown": 34,
        "lessons": [
            "When fiscal and monetary policy coordinate, recovery can be V-shaped",
            "Exogenous shocks resolve differently than endogenous financial crises",
            "Massive liquidity injections find their way into risk assets",
        ],
    },
    {
        "period": "2021-2022", "name": "Inflation Shock / Tightening",
        "growth": "decelerating", "inflation": "stagflation",
        "monetary": "tightening", "credit": "contraction",
        "dollar": "strong", "volatility": "high_vol",
        "resolution": "Ongoing — bond/equity correlation turned positive",
        "duration": 18, "drawdown": 25,
        "lessons": [
            "When inflation is the problem, bonds and equities sell off together",
            "60/40 portfolio diversification fails in inflation regimes",
            "Dollar strength is a global tightening mechanism",
        ],
    },
    {
        "period": "2023-2024", "name": "AI Boom / Disinflation",
        "growth": "accelerating", "inflation": "disinflation",
        "monetary": "neutral", "credit": "expansion",
        "dollar": "stable", "volatility": "low_vol",
        "resolution": "Ongoing — AI capex cycle + soft landing narrative",
        "duration": 18, "drawdown": 10,
        "lessons": [
            "Technology-driven productivity gains can coexist with disinflation",
            "Concentrated market leadership creates hidden fragility",
            "Soft landing is historically rare — be skeptical",
        ],
    },
]


class HistoricalSimilarity:
    """Finds historical periods most similar to the current regime."""

    def __init__(self):
        self._periods = HISTORICAL_PERIODS

    def find_analogs(
        self,
        current_regime: MacroRegime,
        top_n: int = 5,
    ) -> list[HistoricalAnalog]:
        """Find top-N historical analogs sorted by similarity.

        Returns:
            Sorted list of HistoricalAnalog (most similar first).
        """
        analogs = []
        for period in self._periods:
            score = self._similarity_score(current_regime, period)
            analogs.append(self._to_analog(period, score))

        analogs.sort(key=lambda a: a.similarity_score, reverse=True)
        return analogs[:top_n]

    def find_best_analog(
        self, current_regime: MacroRegime
    ) -> HistoricalAnalog:
        """Return the single best historical analog."""
        analogs = self.find_analogs(current_regime, top_n=1)
        return analogs[0] if analogs else HistoricalAnalog()

    def _similarity_score(
        self, regime: MacroRegime, period: dict
    ) -> float:
        """Compute multi-dimensional similarity score (0-1)."""
        scores = []

        # Growth (weight: 0.20)
        if regime.growth_phase == period["growth"]:
            scores.append(1.0)
        else:
            # Partial match
            g1, g2 = regime.growth_phase, period["growth"]
            if (g1, g2) in [("accelerating", "stable"), ("decelerating", "stable"),
                             ("stable", "accelerating"), ("stable", "decelerating")]:
                scores.append(0.5)
            else:
                scores.append(0.1)

        # Inflation (weight: 0.25 — most important dimension)
        if regime.inflation_regime == period["inflation"]:
            scores.append(1.0)
        elif (regime.inflation_regime, period["inflation"]) in [
            ("reflation", "stagflation"), ("disinflation", "deflation")
        ]:
            scores.append(0.6)
        else:
            scores.append(0.2)

        # Monetary policy (weight: 0.20)
        if regime.monetary_stance == period["monetary"]:
            scores.append(1.0)
        elif (regime.monetary_stance, period["monetary"]) in [
            ("neutral", "easing"), ("neutral", "tightening")
        ]:
            scores.append(0.6)
        else:
            scores.append(0.1)

        # Credit cycle (weight: 0.15)
        if regime.credit_cycle == period["credit"]:
            scores.append(1.0)
        elif (regime.credit_cycle, period["credit"]) in [
            ("peak", "contraction"), ("expansion", "peak")
        ]:
            scores.append(0.5)
        else:
            scores.append(0.2)

        # Dollar (weight: 0.10)
        if regime.dollar_regime == period["dollar"]:
            scores.append(1.0)
        elif (regime.dollar_regime, period["dollar"]) in [
            ("strong", "stable"), ("weak", "stable")
        ]:
            scores.append(0.6)
        else:
            scores.append(0.2)

        # Volatility (weight: 0.10)
        if regime.volatility_regime == period["volatility"]:
            scores.append(1.0)
        elif (regime.volatility_regime, period["volatility"]) in [
            ("high_vol", "crisis"), ("normal", "low_vol"), ("normal", "high_vol")
        ]:
            scores.append(0.5)
        else:
            scores.append(0.1)

        # Weighted sum
        weights = [0.20, 0.25, 0.20, 0.15, 0.10, 0.10]
        weighted = sum(s * w for s, w in zip(scores, weights))
        return round(weighted, 3)

    def _to_analog(self, period: dict, score: float) -> HistoricalAnalog:
        return HistoricalAnalog(
            period_label=period["period"],
            period_name=period["name"],
            similarity_score=score,
            growth_profile=period["growth"],
            inflation_profile=period["inflation"],
            policy_response=period["monetary"],
            market_outcome=f"{period['duration']}mo, max DD: {period['drawdown']}%",
            resolution=period["resolution"],
            duration_months=period["duration"],
            max_drawdown_pct=period["drawdown"],
            key_lessons=period["lessons"],
        )

    def generate_cycle_narrative(
        self, regime: MacroRegime, top_analog: HistoricalAnalog
    ) -> str:
        """Generate a Dalio-style 'where are we in the cycle' narrative."""
        if top_analog.similarity_score > 0.7:
            confidence = "strongly resembles"
        elif top_analog.similarity_score > 0.5:
            confidence = "partially resembles"
        else:
            confidence = "has some similarities with"

        parts = [
            f"Current regime ({regime.regime_label}) {confidence} {top_analog.period_name} ({top_analog.period_label}).",
            f"Key parallel: growth {regime.growth_phase} + inflation {regime.inflation_regime}.",
        ]

        if top_analog.key_lessons:
            parts.append(f"Lesson from that period: {top_analog.key_lessons[0]}")

        return " ".join(parts)

    def get_all_periods(self) -> list[dict]:
        """Return all historical periods for reference."""
        return self._periods
