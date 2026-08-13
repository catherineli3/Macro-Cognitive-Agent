"""InflationModel — assess inflation pressures and trajectory.

Inputs:   Gold, Oil (commodity proxies for inflation)
Outputs:  Inflation Rising / Peak / Cooling with confidence

Commodity prices lead CPI by 3-6 months. Gold captures inflation expectations,
Oil captures cost-push inflation pressure.
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


class InflationModel(MentalModel):
    """Assess inflation pressures via commodity proxies.

    Core thesis:
        - Gold rising + Oil rising → reflation / inflation acceleration
        - Gold falling + Oil falling → disinflation / cooling
        - Gold up + Oil down → stagflation concern (cost-push absent, expectations up)
        - Gold down + Oil up → supply shock (transitory)

    Note: M1 uses Gold/Oil as proxies. M3+ will add CPI/PCE/Wage data.
    """

    model_name = "InflationModel"
    domain = "Inflation"
    description = "Inflation pressures and trajectory (commodity proxies)"

    _INDICATORS = ["Gold", "Oil"]

    def evaluate(self, input: ModelInput) -> list[ResearchConclusion]:
        score, direction, dim_data = self._extract_dimension_score(input, "Inflation")

        supporting, contradicting = self._build_evidence(
            input, self._INDICATORS, self._interpret_inflation
        )

        # Detect Gold-Oil divergence
        gold = input.get_indicator("GOLD")
        oil = input.get_indicator("OIL")
        divergence = self._check_divergence(gold, oil)

        if divergence:
            direction = "divergent"
            conclusion_text = (
                f"Inflation Signals Divergent — {divergence}. "
                "Commodity proxies are sending mixed inflation messages. "
                "This increases uncertainty around the inflation trajectory."
            )
        elif direction == "rising":
            conclusion_text = (
                "Inflation Rising — commodity prices indicate building inflationary pressure. "
                "Gold and Oil strength suggest both expectations and cost-push are active."
            )
        elif direction == "cooling":
            conclusion_text = (
                "Inflation Cooling — commodity prices suggest easing inflation. "
                "Disinflationary trend supports Fed policy normalization."
            )
        else:
            conclusion_text = "Inflation Stable — no clear directional signal from commodities."

        confidence = self._compute_confidence(
            score, len(supporting), len(contradicting), len(self._INDICATORS)
        )
        if divergence:
            confidence *= 0.7  # Divergence reduces confidence

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
                    "Gold and Oil adequately proxy inflation pressures",
                    "Commodity prices lead CPI by 3-6 months",
                    "Current commodity moves are not purely speculation-driven",
                    "No major supply disruption distorting Oil signal",
                ],
                narrative_seeds=narrative_seeds,
                raw_score=score,
                direction=direction,
            )
        ]

    @staticmethod
    def _interpret_inflation(name: str, value: float, features: list[dict]) -> dict:
        if name == "GOLD":
            if value > 2000:
                return {
                    "text": f"Gold elevated (${value:.0f}) — inflation fear / safe-haven bid",
                    "contradicts": False,
                }
            elif value < 1800:
                return {
                    "text": f"Gold subdued (${value:.0f}) — inflation expectations anchored",
                    "contradicts": False,
                }
            else:
                return {"text": f"Gold moderate (${value:.0f})", "contradicts": False}
        if name == "OIL":
            if value > 85:
                return {
                    "text": f"Oil elevated (${value:.1f}) — cost-push inflation pressure",
                    "contradicts": False,
                }
            elif value < 65:
                return {
                    "text": f"Oil low (${value:.1f}) — disinflationary tailwind",
                    "contradicts": True,
                }
            else:
                return {"text": f"Oil moderate (${value:.1f})", "contradicts": False}
        return {"text": f"{name}: {value:.2f}", "contradicts": False}

    @staticmethod
    def _check_divergence(gold: dict | None, oil: dict | None) -> str | None:
        """Check if Gold and Oil are sending divergent signals."""
        if not gold or not oil:
            return None

        gv = gold.get("raw_value", 0)
        ov = oil.get("raw_value", 0)

        gold_high = gv > 2000
        oil_high = ov > 80
        gold_low = gv < 1800
        oil_low = ov < 65

        if gold_high and oil_low:
            return "Gold strength + Oil weakness: stagflation concern or safe-haven demand"
        if gold_low and oil_high:
            return "Gold weakness + Oil strength: supply shock, potentially transitory"
        return None

    @staticmethod
    def _generate_narratives(direction: str, supporting: list[EvidenceItem]) -> list[str]:
        if direction == "rising":
            return [
                "Inflation persistence → Fed hawkish risk → rate-sensitive selloff",
                "Commodity bid → energy/materials sector rotation",
                "Real asset preference → gold miner upside",
            ]
        elif direction == "cooling":
            return [
                "Inflation normalization → rate cut expectations → duration bid",
                "Real wage recovery → consumer discretionary upside",
                "Disinflation trend → growth stock re-rating",
            ]
        elif direction == "divergent":
            return [
                "Mixed commodity signals → inflation uncertainty premium",
                "Possible stagflation scenario → defensive positioning",
            ]
        else:
            return ["Inflation in transition — wait for clearer commodity signal"]
