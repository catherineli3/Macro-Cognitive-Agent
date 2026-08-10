"""GrowthModel — assess economic growth momentum.

Inputs:   Copper, SP500, Russell (from MacroSnapshot feature_summary)
Outputs:  Expansion / Slowdown / Recession with confidence

Copper = "Dr. Copper" — the metal with a PhD in economics.
SP500 + Russell = equity market growth proxies (large cap + small cap).
"""

from __future__ import annotations

from src.research.models.mental_model import (
    EvidenceItem,
    MentalModel,
    ModelInput,
    ResearchConclusion,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


class GrowthModel(MentalModel):
    """Assess economic growth trajectory.

    Core thesis:
        - Copper up + SP500 up + Russell up → synchronized expansion
        - Copper down + SP500 divergence → growth scare (small cap first)
        - Copper down + SP500 down → recessionary signal

    Dr. Copper principle:
        Copper leads industrial production by 3-6 months.
        It is the single best real-time growth indicator.
    """

    model_name = "GrowthModel"
    domain = "Growth"
    description = "Economic growth momentum and cycle phase"

    _INDICATORS = ["Copper", "SP500", "Russell"]

    def evaluate(self, input: ModelInput) -> list[ResearchConclusion]:
        score, direction, dim_data = self._extract_dimension_score(input, "Growth")

        supporting, contradicting = self._build_evidence(
            input, self._INDICATORS, self._interpret_growth
        )

        # Check for small-cap divergence
        sp500 = input.get_indicator("SP500")
        russell = input.get_indicator("RUSSELL")
        divergence_note = self._check_large_small_divergence(sp500, russell)

        if direction == "expansion":
            conclusion_text = (
                "Growth Expansion — economic momentum is positive. "
                "Copper strength + equity rally suggest synchronized global growth."
            )
        elif direction == "contraction":
            conclusion_text = (
                "Growth Contraction — economic momentum is weakening. "
                "Declining copper and equity weakness suggest growth slowdown risk. "
                "This may be early recession signal."
            )
        else:
            conclusion_text = (
                "Growth Stable — economic momentum is balanced. "
                "Mixed signals across growth indicators."
            )

        if divergence_note:
            conclusion_text += f" Note: {divergence_note}"

        confidence = self._compute_confidence(
            score, len(supporting), len(contradicting), len(self._INDICATORS)
        )

        narrative_seeds = self._generate_narratives(direction, supporting)

        return [
            ResearchConclusion(
                model_name=self.model_name,
                domain=self.domain,
                conclusion=conclusion_text,
                confidence=round(confidence, 3),
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                assumptions=[
                    "Copper adequately proxies industrial demand and global growth",
                    "SP500 and Russell capture broad equity market growth expectations",
                    "Equity markets are not distorted by extreme monetary policy",
                ],
                narrative_seeds=narrative_seeds,
                raw_score=score,
                direction=direction,
            )
        ]

    @staticmethod
    def _interpret_growth(name: str, value: float, features: list[dict]) -> dict:
        if name == "COPPER":
            if value > 4.5:
                return {"text": f"Copper strong (${value:.2f}) — industrial demand robust", "contradicts": False, "weight": 1.5}
            elif value < 3.5:
                return {"text": f"Copper weak (${value:.2f}) — industrial slowdown signal", "contradicts": True, "weight": 1.5}
            else:
                return {"text": f"Copper moderate (${value:.2f})", "contradicts": False, "weight": 1.2}
        if name == "SP500":
            if value < 3800:
                return {"text": f"SP500 low — growth fear priced in", "contradicts": True}
            elif value > 4500:
                return {"text": f"SP500 elevated — growth optimism", "contradicts": False}
            else:
                return {"text": f"SP500 range (${value:.0f})", "contradicts": False}
        if name == "RUSSELL":
            if value < 180:
                return {"text": f"Russell weak — domestic growth concern (small cap leading)", "contradicts": True, "weight": 1.3}
            elif value > 220:
                return {"text": f"Russell strong — domestic expansion", "contradicts": False}
            else:
                return {"text": f"Russell range (${value:.0f})", "contradicts": False}
        return {"text": f"{name}: {value:.2f}", "contradicts": False}

    @staticmethod
    def _check_large_small_divergence(
        sp500: dict | None, russell: dict | None
    ) -> str | None:
        """Check for large-cap vs small-cap divergence."""
        if not sp500 or not russell:
            return None

        # Simple check: is one showing different trend?
        sp_features = sp500.get("features", [])
        ru_features = russell.get("features", [])

        sp_trend = next((f for f in sp_features if f.get("dimension") == "trend_20d"), None)
        ru_trend = next((f for f in ru_features if f.get("dimension") == "trend_20d"), None)

        if sp_trend and ru_trend:
            sp_up = "uptrend" in sp_trend.get("label", "")
            ru_up = "uptrend" in ru_trend.get("label", "")
            if sp_up and not ru_up:
                return "SP500 up but Russell down → narrow market, growth not broad-based"
            if not sp_up and ru_up:
                return "Russell up but SP500 down → domestic rotation signal"

        return None

    @staticmethod
    def _generate_narratives(
        direction: str, supporting: list[EvidenceItem]
    ) -> list[str]:
        if direction == "expansion":
            return [
                "Growth acceleration → cyclical/value sector leadership",
                "Earnings momentum → multiple expansion support",
                "Global synchronized growth → commodities super-cycle",
                "Small cap catch-up → broadening market rally",
            ]
        elif direction == "contraction":
            return [
                "Growth scare → defensive rotation (utilities, staples)",
                "Recession probability repricing → bond bid",
                "Copper breakdown → industrial sector underperformance",
                "Small cap weakness → domestic demand concern",
            ]
        else:
            return [
                "Growth at inflection point → wait for copper confirmation",
                "Equity-commodity divergence → possible regime shift",
            ]
