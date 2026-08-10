"""CreditModel — assess credit market health and cycle phase.

Inputs:   HYG, LQD (from MacroSnapshot feature_summary)
Outputs:  Credit Expansion / Stable / Contraction with confidence

PTJ emphasis: "Credit leads equity."
Credit stress always precedes equity weakness.
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


class CreditModel(MentalModel):
    """Assess credit market conditions.

    Core thesis:
        - HYG falling + LQD weakening → credit stress → equity risk
        - HYG rising + LQD stable → credit expansion → equity support
        - HYG-LQD divergence → sector rotation signal
    """

    model_name = "CreditModel"
    domain = "Credit"
    description = "Credit market health and cycle phase"

    _INDICATORS = ["HYG", "LQD"]

    def evaluate(self, input: ModelInput) -> list[ResearchConclusion]:
        score, direction, dim_data = self._extract_dimension_score(input, "Credit")

        supporting, contradicting = self._build_evidence(
            input, self._INDICATORS, self._interpret_credit
        )

        if direction == "contraction":
            conclusion_text = (
                "Credit Contraction — credit markets are signaling stress. "
                "High-yield weakness suggests rising default risk perception. "
                "This typically leads equity market repricing."
            )
        elif direction == "expansion":
            conclusion_text = (
                "Credit Expansion — credit markets are healthy. "
                "Tight spreads and HYG strength support risk-taking. "
                "Credit tailwind supports equity valuations."
            )
        else:
            conclusion_text = (
                "Credit Stable — credit markets are balanced. "
                "No clear stress or expansion signal."
            )

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
                    "HYG and LQD adequately proxy US credit markets",
                    "Credit spreads move before equity prices",
                    "No structural market distortions affecting HYG/LQD pricing",
                ],
                narrative_seeds=narrative_seeds,
                raw_score=score,
                direction=direction,
            )
        ]

    @staticmethod
    def _interpret_credit(name: str, value: float, features: list[dict]) -> dict:
        if name == "HYG":
            if value < 72:
                return {"text": f"HYG weak ({value:.1f}) — high-yield stress signal", "contradicts": True}
            elif value > 78:
                return {"text": f"HYG strong ({value:.1f}) — credit appetite healthy", "contradicts": False}
            else:
                return {"text": f"HYG range-bound ({value:.1f})", "contradicts": False}
        if name == "LQD":
            if value < 105:
                return {"text": f"LQD weak ({value:.1f}) — IG spreads widening", "contradicts": True}
            elif value > 115:
                return {"text": f"LQD strong ({value:.1f}) — IG demand solid", "contradicts": False}
            else:
                return {"text": f"LQD stable ({value:.1f})", "contradicts": False}
        return {"text": f"{name}: {value:.2f}", "contradicts": False}

    @staticmethod
    def _generate_narratives(
        direction: str, supporting: list[EvidenceItem]
    ) -> list[str]:
        if direction == "contraction":
            return [
                "Credit stress → equity risk premium repricing",
                "HY underperformance → small cap / value underperformance",
                "Default cycle fears → financial sector pressure",
                "Flight to quality → IG outperformance vs HY",
            ]
        elif direction == "expansion":
            return [
                "Credit expansion → equity multiple support",
                "Low default risk → cyclical sector outperformance",
                "Credit tailwind → M&A and buyback activity",
            ]
        else:
            return [
                "Credit market in wait-and-see mode",
                "HYG-LQD spread stability → no sector rotation signal",
            ]
