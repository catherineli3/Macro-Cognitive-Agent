"""LiquidityModel — assess monetary and financial liquidity conditions.

Inputs:   DXY, US10Y, US2Y (from MacroSnapshot state_vector)
Outputs:  Liquidity Tightening / Neutral / Easing with confidence

PTJ first principle: "Liquidity drives risk assets."
This model is the highest-priority mental model.
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


class LiquidityModel(MentalModel):
    """Assess financial liquidity conditions.

    Core thesis:
        - Rising DXY + rising US10Y + inverted 2s10s = tightening
        - Falling DXY + falling US10Y + steepening = easing
        - Mixed signals = neutral with lower confidence
    """

    model_name = "LiquidityModel"
    domain = "Liquidity"
    description = "Monetary and financial liquidity conditions"

    # Indicators monitored
    _INDICATORS = ["DXY", "US10Y", "US2Y"]

    def evaluate(self, input: ModelInput) -> list[ResearchConclusion]:
        score, direction, dim_data = self._extract_dimension_score(input, "Liquidity")

        # Build evidence
        supporting, contradicting = self._build_evidence(
            input, self._INDICATORS, self._interpret_liquidity
        )

        # Determine conclusion
        if direction == "tightening":
            conclusion_text = (
                "Liquidity Tightening — financial conditions are restrictive. "
                "Risk assets face headwinds from reduced monetary accommodation."
            )
        elif direction == "easing":
            conclusion_text = (
                "Liquidity Easing — financial conditions are accommodative. "
                "Risk assets benefit from increased liquidity availability."
            )
        else:
            conclusion_text = (
                "Liquidity Neutral — financial conditions are balanced. "
                "No clear liquidity signal for risk assets."
            )

        # Confidence
        confidence = self._compute_confidence(
            score, len(supporting), len(contradicting), len(self._INDICATORS)
        )

        # Narrative seeds
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
                    "DXY, US10Y, US2Y adequately proxy Fed/Treasury liquidity",
                    "Market prices reflect actual monetary conditions",
                    "Yahoo Finance data is timely and accurate",
                ],
                narrative_seeds=narrative_seeds,
                raw_score=score,
                direction=direction,
            )
        ]

    # ── Interpretation ──────────────────────────────────────────────────

    @staticmethod
    def _interpret_liquidity(
        name: str, value: float, features: list[dict]
    ) -> dict:
        """Interpret a single liquidity indicator."""
        interpretations = {
            "DXY": {
                "high": (105, "USD strength → global liquidity drain", True),
                "low": (95, "USD weakness → global liquidity expansion", False),
                "mid": (100, "USD neutral", False),
            },
            "US10Y": {
                "high": (4.5, "High long-end yields → tight financial conditions", True),
                "low": (3.5, "Low long-end yields → loose conditions", False),
                "mid": (4.0, "Yields moderate", False),
            },
            "US2Y": {
                "high": (4.5, "High short-end → Fed hawkish stance", True),
                "low": (3.5, "Low short-end → Fed dovish stance", False),
                "mid": (4.0, "Short-end moderate", False),
            },
        }

        info = interpretations.get(name, {})
        if not info:
            return {"text": f"{name}: {value:.2f}", "contradicts": False}

        high_threshold, high_text, high_contradicts = info["high"]
        low_threshold, low_text, low_contradicts = info["low"]
        mid_threshold, mid_text, mid_contradicts = info["mid"]

        if value > high_threshold:
            return {"text": high_text, "contradicts": high_contradicts, "weight": 1.2}
        elif value < low_threshold:
            return {"text": low_text, "contradicts": low_contradicts, "weight": 1.0}
        else:
            return {"text": mid_text, "contradicts": mid_contradicts, "weight": 0.8}

    @staticmethod
    def _generate_narratives(
        direction: str, supporting: list[EvidenceItem]
    ) -> list[str]:
        """Generate possible narrative directions."""
        if direction == "tightening":
            return [
                "Higher real yields → long duration pressure",
                "Tight financial conditions → growth stock compression",
                "USD strength feedback loop → EM capital outflows",
                "Fed higher-for-longer → rate-sensitive sector weakness",
            ]
        elif direction == "easing":
            return [
                "Liquidity tailwind → risk asset bid",
                "Lower real yields → duration relief rally",
                "EM carry trade revival on USD weakness",
                "Easing cycle → cyclical/value rotation",
            ]
        else:
            return [
                "Mixed liquidity signals → wait-and-see mode",
                "Liquidity transition period → sector rotation",
            ]
