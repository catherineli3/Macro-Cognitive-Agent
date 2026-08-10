"""DollarModel — assess USD direction and implications.

Inputs:   DXY (from MacroSnapshot feature_summary)
Outputs:  Dollar Strengthening / Weakening / Neutral with confidence

DXY is the single most important macro variable for global markets:
    - Strong USD → EM pressure, commodity headwind, tightening proxy
    - Weak USD → EM relief, commodity tailwind, easing proxy
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


class DollarModel(MentalModel):
    """Assess USD direction and global implications.

    Core thesis:
        - DXY is the world's most important price.
        - Rising DXY = global tightening (even without Fed action).
        - Falling DXY = global easing.
        - DXY extremes signal regime shifts.

    DXY impacts:
        - EM currencies and debt
        - Commodity prices (inverse)
        - US multinational earnings (inverse)
        - Global liquidity (inverse)
    """

    model_name = "DollarModel"
    domain = "Dollar"
    description = "USD strength and direction"

    _INDICATORS = ["DXY"]

    def evaluate(self, input: ModelInput) -> list[ResearchConclusion]:
        score, direction, dim_data = self._extract_dimension_score(input, "Dollar")

        supporting, contradicting = self._build_evidence(
            input, self._INDICATORS, self._interpret_dollar
        )

        # DXY level-based regime
        dxy = input.get_indicator("DXY")
        dxy_level = dxy.get("raw_value", 100) if dxy else 100
        level_signal = self._level_signal(dxy_level)

        if direction == "strengthening":
            conclusion_text = (
                f"Dollar Strengthening — DXY at {dxy_level:.1f}. "
                f"{level_signal}. USD strength acts as a global tightening force."
            )
        elif direction == "weakening":
            conclusion_text = (
                f"Dollar Weakening — DXY at {dxy_level:.1f}. "
                f"{level_signal}. USD weakness provides global easing tailwind."
            )
        else:
            conclusion_text = (
                f"Dollar Neutral — DXY at {dxy_level:.1f}. {level_signal}"
            )

        confidence = self._compute_confidence(
            score, len(supporting), len(contradicting), len(self._INDICATORS)
        )

        narrative_seeds = self._generate_narratives(direction, dxy_level, supporting)

        return [
            ResearchConclusion(
                model_name=self.model_name,
                domain=self.domain,
                conclusion=conclusion_text,
                confidence=round(confidence, 3),
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                assumptions=[
                    "DXY adequately proxies broad USD strength",
                    "DXY moves reflect actual capital flows and rate expectations",
                    "EM FX sensitivity to DXY follows historical patterns",
                ],
                narrative_seeds=narrative_seeds,
                raw_score=score,
                direction=direction,
            )
        ]

    @staticmethod
    def _interpret_dollar(name: str, value: float, features: list[dict]) -> dict:
        if value > 105:
            return {
                "text": f"DXY strong ({value:.1f}) — USD at multi-year highs, global tightening",
                "contradicts": True,
                "weight": 1.5,
            }
        elif value < 95:
            return {
                "text": f"DXY weak ({value:.1f}) — USD at lows, global easing proxy",
                "contradicts": False,
                "weight": 1.5,
            }
        elif value > 100:
            return {
                "text": f"DXY above 100 ({value:.1f}) — moderate dollar strength",
                "contradicts": False,
            }
        else:
            return {
                "text": f"DXY below 100 ({value:.1f}) — dollar neutral/weak",
                "contradicts": False,
            }

    @staticmethod
    def _level_signal(level: float) -> str:
        if level > 108:
            return "Extreme USD strength — historically precedes EM crisis events"
        elif level > 105:
            return "Dollar dominance regime — risk-off favored"
        elif level > 100:
            return "Moderate dollar — no extreme signal"
        elif level > 95:
            return "Dollar soft — supportive of risk assets"
        else:
            return "Dollar weak — maximum EM and commodity tailwind"

    @staticmethod
    def _generate_narratives(
        direction: str, level: float, supporting: list[EvidenceItem]
    ) -> list[str]:
        if direction == "strengthening":
            return [
                "Dollar strength → EM FX depreciation → capital outflow risk",
                "USD bid → commodity headwind (gold, copper, oil pressure)",
                "Strong dollar → US multinationals earnings headwind",
                "DXY above 105 → historical risk-off trigger zone",
            ]
        elif direction == "weakening":
            return [
                "Dollar weakness → EM relief rally → carry trade revival",
                "USD decline → commodity super-cycle tailwind",
                "Weak dollar → US exporter advantage → industrial rotation",
                "DXY breakdown → risk-on confirmation signal",
            ]
        else:
            return [
                "Dollar range-bound → wait for breakout direction",
                "DXY consolidation → risk-neutral positioning",
            ]
