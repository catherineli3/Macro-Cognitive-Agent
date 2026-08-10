"""PolicyModel — assess monetary policy stance.

Inputs:   US2Y, US10Y (short and long-end yields as policy proxies)
Outputs:  Hawkish / Neutral / Dovish with confidence

2s10s spread is one of the best real-time policy indicators:
    - Inverted (2Y > 10Y) → hawkish / tightening
    - Steep (10Y >> 2Y) → dovish / easing expectations
    - Flat → neutral / transition
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


class PolicyModel(MentalModel):
    """Assess monetary policy stance from yield curve.

    Core thesis:
        - 2s10s inversion → restrictive policy → recession probability
        - 2s10s steepening → easing expectations → reflation
        - 2s10s flattening from steep → policy transition warning
    """

    model_name = "PolicyModel"
    domain = "Policy"
    description = "Monetary policy stance and rate expectations"

    _INDICATORS = ["US2Y", "US10Y"]

    def evaluate(self, input: ModelInput) -> list[ResearchConclusion]:
        score, direction, dim_data = self._extract_dimension_score(input, "Policy")

        supporting, contradicting = self._build_evidence(
            input, self._INDICATORS, self._interpret_policy
        )

        # Compute 2s10s spread
        us2y = input.get_indicator("US2Y")
        us10y = input.get_indicator("US10Y")
        spread, spread_signal = self._compute_spread(us2y, us10y)

        if direction == "hawkish":
            conclusion_text = (
                f"Hawkish Policy Stance — yields suggest restrictive monetary policy. "
                f"2s10s spread: {spread:.0f}bps. {spread_signal}"
            )
        elif direction == "dovish":
            conclusion_text = (
                f"Dovish Policy Stance — yields suggest accommodative expectations. "
                f"2s10s spread: {spread:.0f}bps. {spread_signal}"
            )
        else:
            conclusion_text = (
                f"Policy Neutral — yield curve in transition. "
                f"2s10s spread: {spread:.0f}bps. {spread_signal}"
            )

        confidence = self._compute_confidence(
            score, len(supporting), len(contradicting), len(self._INDICATORS)
        )
        # Boost confidence if spread is extreme
        if abs(spread) > 50:
            confidence = min(0.95, confidence + 0.1)

        narrative_seeds = self._generate_narratives(direction, spread, supporting)

        return [
            ResearchConclusion(
                model_name=self.model_name,
                domain=self.domain,
                conclusion=conclusion_text,
                confidence=round(confidence, 3),
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                assumptions=[
                    "Yield curve accurately reflects policy expectations",
                    "No yield curve control or QE distorting signals",
                    "US2Y and US10Y are timely from Yahoo Finance",
                ],
                narrative_seeds=narrative_seeds,
                raw_score=score,
                direction=direction,
            )
        ]

    @staticmethod
    def _interpret_policy(name: str, value: float, features: list[dict]) -> dict:
        if name == "US2Y":
            if value > 4.5:
                return {"text": f"US2Y elevated ({value:.2f}%) — hawkish short-end pricing", "contradicts": True}
            elif value < 3.5:
                return {"text": f"US2Y low ({value:.2f}%) — dovish / rate cut pricing", "contradicts": False}
            else:
                return {"text": f"US2Y moderate ({value:.2f}%)", "contradicts": False}
        if name == "US10Y":
            if value > 4.5:
                return {"text": f"US10Y elevated ({value:.2f}%) — term premium rising", "contradicts": True}
            elif value < 3.5:
                return {"text": f"US10Y low ({value:.2f}%) — recession / safety bid", "contradicts": False}
            else:
                return {"text": f"US10Y moderate ({value:.2f}%)", "contradicts": False}
        return {"text": f"{name}: {value:.2f}", "contradicts": False}

    @staticmethod
    def _compute_spread(
        us2y: dict | None, us10y: dict | None
    ) -> tuple[float, str]:
        """Compute 2s10s spread and signal."""
        if not us2y or not us10y:
            return 0.0, "Spread unavailable"

        s2 = us2y.get("raw_value", 0)
        s10 = us10y.get("raw_value", 0)
        if s2 <= 0 or s10 <= 0:
            return 0.0, "Invalid values"

        spread_bps = (s10 - s2) * 100

        if spread_bps < -20:
            return spread_bps, "Deeply inverted → recession signal"
        elif spread_bps < 0:
            return spread_bps, "Inverted → restrictive policy"
        elif spread_bps < 20:
            return spread_bps, "Flat → policy transition zone"
        elif spread_bps < 50:
            return spread_bps, "Mild steepening → normalization"
        else:
            return spread_bps, "Steep → easing expectations / reflation"

    @staticmethod
    def _generate_narratives(
        direction: str, spread: float, supporting: list[EvidenceItem]
    ) -> list[str]:
        if direction == "hawkish":
            return [
                "Hawkish repricing → curve flattening / inversion",
                "Rate trajectory uncertainty → vol-of-vol increase",
                "Higher-for-longer → growth vs value tension",
                "Inverted curve persistence → bank sector margin pressure",
            ]
        elif direction == "dovish":
            return [
                "Dovish pivot → duration bid → long bond rally",
                "Easing expectations → cyclical sector re-rating",
                "Rate cut cycle → financial conditions easing",
                "Steepening → reflation trade (financials, energy, materials)",
            ]
        else:
            return [
                "Policy in transition → watch FOMC guidance",
                "Curve flattening from steep → possible hawkish shift",
            ]
