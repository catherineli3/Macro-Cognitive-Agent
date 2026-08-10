"""AICapexModel — assess AI investment cycle health.

Inputs:   NVDA, Semiconductor (SMH), ASML, TSMC
Outputs:  AI Investment Expansion / Stable / Contraction with confidence

This is the user's special thesis: the AI capex cycle is a separate
macro force that can diverge from the broader business cycle.

Key chain: NVDA → TSMC → ASML → SMH → Cloud Capex → AI buildout
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


class AICapexModel(MentalModel):
    """Assess AI investment cycle health.

    Core thesis:
        - All 4 semis up → AI capex cycle intact → tech leadership
        - NVDA up but others mixed → narrow AI leadership (concentration risk)
        - Multiple semis down → AI capex fatigue → tech re-rating risk
        - ASML orders are the leading indicator (3-6 month lead)

    This model is unique: it detects a sectoral cycle that can run
    independently of the broader macro cycle.
    """

    model_name = "AICapexModel"
    domain = "AI_Capex"
    description = "AI investment cycle health (semiconductor chain)"

    _INDICATORS = ["NVDA", "Semiconductor", "ASML", "TSMC"]

    def evaluate(self, input: ModelInput) -> list[ResearchConclusion]:
        score, direction, dim_data = self._extract_dimension_score(input, "AI_Capex")

        supporting, contradicting = self._build_evidence(
            input, self._INDICATORS, self._interpret_ai
        )

        # Check for AI chain health
        chain_health = self._assess_chain_health(input)

        if direction == "expansion":
            conclusion_text = (
                "AI Investment Expansion — the semiconductor chain indicates "
                "sustained AI capex growth. All key nodes (NVDA, TSMC, ASML) "
                f"are signaling strength. {chain_health}"
            )
        elif direction == "contraction":
            conclusion_text = (
                "AI Capex Contraction Warning — semiconductor signals suggest "
                "AI investment cycle is slowing. This could precede a broader "
                f"tech sector re-rating. {chain_health}"
            )
        else:
            conclusion_text = (
                "AI Capex Stable — mixed signals from the semiconductor chain. "
                f"{chain_health}"
            )

        # Concentration risk check
        concentration_note = self._check_concentration(input)
        if concentration_note:
            conclusion_text += f" {concentration_note}"

        confidence = self._compute_confidence(
            score, len(supporting), len(contradicting), len(self._INDICATORS)
        )
        # Lower confidence with fewer data points (M1 has limited AI data)
        confidence = min(confidence, 0.75)

        narrative_seeds = self._generate_narratives(direction, chain_health)

        return [
            ResearchConclusion(
                model_name=self.model_name,
                domain=self.domain,
                conclusion=conclusion_text,
                confidence=round(confidence, 3),
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                assumptions=[
                    "NVDA, SMH, ASML, TSMC prices reflect actual AI capex trends",
                    "Semiconductor chain is leading indicator for AI investment",
                    "Hyperscaler capex follows semiconductor order patterns",
                    "M1 uses price data only — earnings/capex data to be added in M3+",
                ],
                narrative_seeds=narrative_seeds,
                raw_score=score,
                direction=direction,
            )
        ]

    @staticmethod
    def _interpret_ai(name: str, value: float, features: list[dict]) -> dict:
        interpretations = {
            "NVDA": {
                "strong": (800, "NVDA strong — AI GPU demand robust"),
                "weak": (400, "NVDA weak — AI chip demand slowing"),
                "mid": (600, "NVDA moderate"),
            },
            "ASML": {
                "strong": (900, "ASML strong — lithography orders healthy (leading)"),
                "weak": (500, "ASML weak — equipment orders slowing (warning)"),
                "mid": (700, "ASML moderate"),
            },
            "TSMC": {
                "strong": (150, "TSMC strong — advanced node demand solid"),
                "weak": (80, "TSMC weak — foundry utilization falling"),
                "mid": (120, "TSMC moderate"),
            },
            "SEMICONDUCTOR": {
                "strong": (250, "SMH strong — broad semiconductor rally"),
                "weak": (150, "SMH weak — sector-wide pressure"),
                "mid": (200, "SMH moderate"),
            },
        }

        info = interpretations.get(name.upper(), {})
        if not info:
            return {"text": f"{name}: {value:.2f}", "contradicts": False}

        strong_thresh, strong_text = info["strong"]
        weak_thresh, weak_text = info["weak"]
        mid_text = info["mid"]

        if value > strong_thresh:
            return {"text": strong_text, "contradicts": False, "weight": 1.2}
        elif value < weak_thresh:
            return {"text": weak_text, "contradicts": True, "weight": 1.2}
        else:
            return {"text": mid_text, "contradicts": False}

    def _assess_chain_health(self, input: ModelInput) -> str:
        """Assess the semiconductor chain from equipment to chips."""
        nodes = ["ASML", "TSMC", "NVDA", "SEMICONDUCTOR"]
        strengths = []

        for node in nodes:
            ind = input.get_indicator(node)
            if ind:
                raw = ind.get("raw_value", 0)
                strs = {
                    "ASML": (900, 500),
                    "TSMC": (150, 80),
                    "NVDA": (800, 400),
                    "SEMICONDUCTOR": (250, 150),
                }
                high, low = strs.get(node, (1, 0))
                if raw > high:
                    strengths.append("strong")
                elif raw < low:
                    strengths.append("weak")
                else:
                    strengths.append("moderate")

        strong_count = strengths.count("strong")
        weak_count = strengths.count("weak")

        if weak_count >= 3:
            return "Chain-wide weakness — AI capex cycle at risk."
        elif weak_count >= 2:
            return "Significant chain stress — monitor ASML orders closely."
        elif strong_count >= 3:
            return "Chain-wide strength — AI buildout accelerating."
        elif strong_count >= 2:
            return "Moderate chain strength — AI cycle intact."
        else:
            return "Mixed chain signals — neutral stance."

    @staticmethod
    def _check_concentration(input: ModelInput) -> str | None:
        """Check if only NVDA is strong (concentration risk)."""
        nvda = input.get_indicator("NVDA")
        smh = input.get_indicator("Semiconductor")

        if nvda and smh:
            nv = nvda.get("raw_value", 0)
            sv = smh.get("raw_value", 0)

            nvda_strong = nv > 800
            smh_weak = sv < 200

            if nvda_strong and smh_weak:
                return "Warning: NVDA strength but SMH weakness → narrow AI leadership (concentration risk)."

        return None

    @staticmethod
    def _generate_narratives(
        direction: str, chain_health: str
    ) -> list[str]:
        if direction == "expansion":
            return [
                "AI investment acceleration → semis leadership continues",
                "Capex cycle intact → infrastructure build-out (data centers, energy)",
                "AI productivity narrative → broad tech multiple support",
                "Hyperscaler spending → cloud/edge AI deployment wave",
            ]
        elif direction == "contraction":
            return [
                "AI capex fatigue → semis correction risk",
                "Hyperscaler spending slowdown → tech re-rating",
                "AI bubble concerns → growth-to-value rotation",
                "ASML order slowdown → equipment cycle peak warning",
            ]
        else:
            return [
                "AI cycle at potential inflection → watch ASML earnings",
                "Semiconductor consolidation → digestion phase",
            ]
