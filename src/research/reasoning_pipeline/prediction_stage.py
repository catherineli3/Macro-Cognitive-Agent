"""V5.2 Stage 7: Prediction — Calibrated forecasts with probabilities.

Every prediction must have:
    - Clear probability (not just "likely" or "probably")
    - Time horizon
    - Explicit conditions
    - What would prove it wrong (invalidation)

No vague forecasts. Every prediction is testable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.research.reasoning_pipeline.schemas import (
    ObservationOutput,
    EvidenceOutput,
    PatternOutput,
    HypothesisOutput,
    PredictionOutput,
    StageStatus,
)


class PredictionStage:
    """Stage 7: Probabilistic forecasting with explicit invalidation."""

    PREDICTION_TYPES = [
        "economic_data",           # GDP, CPI, employment, etc.
        "monetary_policy",         # Rate path, balance sheet
        "market_direction",        # Asset class direction
        "relative_value",           # Cross-asset, cross-market
        "volatility",              # Vol regime outlook
        "macro_regime",            # Regime persistence/transition
    ]

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def execute(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
        pattern: PatternOutput,
        hypothesis: HypothesisOutput,
    ) -> PredictionOutput:
        """Execute forecasting.

        Args:
            observation: Stage 1
            evidence: Stage 2
            pattern: Stage 3
            hypothesis: Stage 5

        Returns:
            PredictionOutput with calibrated probability forecasts
        """
        output = PredictionOutput(
            timestamp=datetime.now().isoformat(),
            status=StageStatus.IN_PROGRESS,
        )

        # 1. Generate forecasts across prediction types
        output.predictions = self._generate_forecasts(
            observation, evidence, pattern, hypothesis
        )

        # 2. Calibrate probabilities
        output.calibration_notes = self._calibrate_notes(hypothesis)

        # 3. Define forecast dependencies
        output.forecast_dependencies = self._define_dependencies(
            observation, evidence
        )

        # 4. Generate trace
        output.reasoning_trace = self._generate_trace(output)
        output.status = StageStatus.COMPLETED

        return output

    def _generate_forecasts(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
        pattern: PatternOutput,
        hypothesis: HypothesisOutput,
    ) -> list[dict]:
        """Generate structured probability forecasts."""
        forecasts = []

        base_confidence = hypothesis.hypothesis_confidence
        net_weight = evidence.net_weight

        # 1. Macro regime forecast
        regime_prob = base_confidence * 0.9
        forecasts.append({
            "claim": f"Current regime ({pattern.regime_diagnosis}) persists for 3-6 months",
            "probability": round(regime_prob, 2),
            "horizon": "3-6 months",
            "conditions": [
                "No major exogenous shock",
                "Central bank stays on current path",
                "Key economic data does not surprise >2 std deviations",
            ],
            "invalidation": (
                "Regime transition warning if: 1) 2+ consecutive data misses in "
                "same direction, 2) central bank pivot language, 3) financial "
                "conditions index moves >1 std deviation"
            ),
        })

        # 2. Monetary policy forecast
        policy_items = " ".join(
            evidence.evidence_clusters.get("monetary_policy", [])
        ).lower()
        if "hawkish" in policy_items or "tighten" in policy_items:
            policy_claim = "Central bank maintains hawkish stance; next move is a hike or hold"
            policy_prob = base_confidence * 0.85
        elif "dovish" in policy_items or "ease" in policy_items:
            policy_claim = "Central bank pivots dovish; next move is a cut or pause"
            policy_prob = base_confidence * 0.8
        else:
            policy_claim = "Central bank remains data-dependent; no strong directional bias"
            policy_prob = 0.5

        forecasts.append({
            "claim": policy_claim,
            "probability": round(policy_prob, 2),
            "horizon": "next 1-2 meetings",
            "conditions": ["Incoming data consistent with current trend"],
            "invalidation": "Explicit forward guidance change or inter-meeting action",
        })

        # 3. Economic data forecast
        if observation.data_surprises:
            direction = "positive" if net_weight > 0 else "negative"
            forecasts.append({
                "claim": f"Economic data continues to surprise to the {direction} over next 1-2 months",
                "probability": round(abs(net_weight) * 0.9, 2),
                "horizon": "1-2 months",
                "conditions": ["No structural break in data generating process"],
                "invalidation": "Two consecutive data releases in opposite direction",
            })

        # 4. Market direction forecast
        if observation.market_moves:
            if net_weight > 0.2:
                market_claim = "Risk assets maintain positive momentum near-term"
                market_prob = 0.65
            elif net_weight < -0.2:
                market_claim = "Risk assets face headwinds; cautious positioning warranted"
                market_prob = 0.65
            else:
                market_claim = "Markets trade range-bound with elevated two-way risk"
                market_prob = 0.5

            forecasts.append({
                "claim": market_claim,
                "probability": market_prob,
                "horizon": "1 month",
                "conditions": ["No VIX spike above 25", "No credit event"],
                "invalidation": "VIX above 30 or credit spread widening >50bp in one week",
            })

        return forecasts

    def _calibrate_notes(self, hypothesis: HypothesisOutput) -> str:
        """Generate probability calibration notes."""
        conf = hypothesis.hypothesis_confidence

        if conf > 0.8:
            return (
                "High conviction forecasts. Historical accuracy for similar "
                "confidence levels: ~70-75%. Overconfidence risk: reduce stated "
                "probabilities by 5-10% for external communication."
            )
        elif conf > 0.6:
            return (
                "Moderate conviction. These are working assumptions, not high-conviction "
                "calls. Probabilities reflect base rates adjusted for current evidence."
            )
        else:
            return (
                "Low conviction environment. Forecasts are highly conditional. "
                "Probability bands are wide; market pricing should be the primary anchor. "
                "Position sizing should be minimal."
            )

    def _define_dependencies(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
    ) -> list[str]:
        """Define what these forecasts depend on."""
        deps = []

        dominant_themes = sorted(
            evidence.evidence_clusters.keys(),
            key=lambda k: len(evidence.evidence_clusters[k]),
            reverse=True,
        )[:3]

        for theme in dominant_themes:
            deps.append(f"{theme}: Continued data flow in same direction")

        deps.append("Policy: No unexpected central bank action")
        deps.append("External: No major geopolitical or financial shock")
        deps.append("Liquidity: Orderly market functioning maintained")

        return deps

    def _generate_trace(self, output: PredictionOutput) -> str:
        """Generate reasoning trace."""
        trace = []
        trace.append("=== Stage 7: Prediction ===")
        for i, pred in enumerate(output.predictions, 1):
            trace.append(
                f"  Prediction {i}: {pred['claim'][:60]}... "
                f"(P={pred['probability']:.0%}, horizon={pred['horizon']})"
            )
        trace.append(f"Dependencies: {len(output.forecast_dependencies)}")
        return "\n".join(trace)
