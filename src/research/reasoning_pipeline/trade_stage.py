"""V5.2 Stage 8: Trade — Express macro views as actionable trade ideas.

This is where macro research becomes investment decisions.

Rules:
    1. Every trade must directly follow from the preceding stages.
    2. No "interesting idea" — must be actionable with clear parameters.
    3. Include what to avoid, not just what to do.
    4. Distinguish high-conviction from tactical trades.
"""

from __future__ import annotations

from datetime import datetime

from src.research.reasoning_pipeline.schemas import (
    EvidenceOutput,
    HypothesisOutput,
    ObservationOutput,
    PatternOutput,
    PredictionOutput,
    StageStatus,
    TradeOutput,
)


class TradeStage:
    """Stage 8: Translate macro views into actionable trades."""

    # Instrument universe organized by view type
    INSTRUMENT_MAP: dict[str, list[str]] = {
        "hawkish_fed": ["Short 2Y UST futures", "Long USD vs EM FX", "Short Gold"],
        "dovish_fed": ["Long 2Y UST futures", "Short USD", "Long Gold"],
        "reflation": ["Long Equities", "Short duration", "Long Commodities", "Long TIPS"],
        "stagflation": ["Long Gold", "Long Oil", "Short Equities", "Long TIPS"],
        "risk_on": ["Long SPX", "Short VIX", "Long EM", "Short USD"],
        "risk_off": ["Long UST", "Long VIX", "Long USD", "Long JPY"],
        "growth_strong": ["Long Cyclicals vs Defensives", "Long Small Caps", "Short duration"],
        "growth_weak": ["Long Defensives", "Long Duration", "Short Cyclicals"],
        "inflation_high": ["Long TIPS breakevens", "Long Commodities", "Short duration"],
        "inflation_low": ["Long Nominal Bonds", "Short TIPS breakevens"],
        "dollar_strong": ["Short EM", "Short Gold", "Short Commodities"],
        "dollar_weak": ["Long EM", "Long Gold", "Long EUR"],
        "credit_stress": ["Short HY vs IG", "Long CDX protection", "Long Volatility"],
    }

    POSITION_SIZING = {
        "high_conviction": "2-3% risk per idea",
        "moderate_conviction": "1-2% risk per idea",
        "low_conviction": "0.5-1% risk per idea",
    }

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def execute(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
        pattern: PatternOutput,
        hypothesis: HypothesisOutput,
        prediction: PredictionOutput,
    ) -> TradeOutput:
        """Execute trade generation.

        Args:
            observation: Stage 1
            evidence: Stage 2
            pattern: Stage 3
            hypothesis: Stage 5
            prediction: Stage 7

        Returns:
            TradeOutput with actionable trade expressions
        """
        output = TradeOutput(
            timestamp=datetime.now().isoformat(),
            status=StageStatus.IN_PROGRESS,
        )

        # 1. Identify which views to express
        trade_views = self._identify_views(pattern, evidence)

        # 2. Map views to specific instruments
        output.trades = self._map_to_trades(trade_views, hypothesis, prediction)

        # 3. Portfolio positioning overview
        output.portfolio_positioning = self._portfolio_overview(pattern, hypothesis, evidence)

        # 4. Trades to avoid
        output.trades_to_avoid = self._trades_to_avoid(pattern, evidence)

        # 5. Execution notes
        output.execution_notes = self._execution_notes(hypothesis)

        # 6. Generate trace
        output.reasoning_trace = self._generate_trace(output)
        output.status = StageStatus.COMPLETED

        return output

    def _identify_views(
        self,
        pattern: PatternOutput,
        evidence: EvidenceOutput,
    ) -> list[str]:
        """Identify trade views implied by the macro analysis."""
        views = []

        patterns_text = " ".join(pattern.patterns).lower()
        clusters = evidence.evidence_clusters

        # Monetary policy views
        policy_text = " ".join(clusters.get("monetary_policy", [])).lower()
        if "hawkish" in policy_text or "tighten" in policy_text:
            views.append("hawkish_fed")
        elif "dovish" in policy_text or "ease" in policy_text:
            views.append("dovish_fed")

        # Growth views
        if "goldilocks" in patterns_text or "disinflationary boom" in patterns_text:
            views.append("growth_strong")
        elif "stagflation" in patterns_text:
            views.append("growth_weak")

        # Inflation views
        inflation_text = " ".join(clusters.get("inflation", [])).lower()
        if "high" in inflation_text or "surge" in inflation_text or "hot" in inflation_text:
            views.append("inflation_high")
        elif "low" in inflation_text or "cooling" in inflation_text:
            views.append("inflation_low")

        # Risk views
        sentiment_text = " ".join(clusters.get("sentiment", [])).lower()
        if "risk on" in patterns_text or "bullish" in sentiment_text:
            views.append("risk_on")
        elif "risk off" in patterns_text or "bearish" in sentiment_text:
            views.append("risk_off")

        # Credit views
        credit_text = " ".join(clusters.get("credit_markets", [])).lower()
        if "widen" in credit_text or "stress" in credit_text:
            views.append("credit_stress")

        return views[:4]  # Top 4 views

    def _map_to_trades(
        self,
        views: list[str],
        hypothesis: HypothesisOutput,
        prediction: PredictionOutput,
    ) -> list[dict]:
        """Map macro views to specific trade expressions."""
        trades = []
        conviction = hypothesis.hypothesis_confidence

        size_category = (
            "high_conviction"
            if conviction > 0.75
            else "moderate_conviction" if conviction > 0.5 else "low_conviction"
        )

        for view in views:
            instruments = self.INSTRUMENT_MAP.get(view, [])
            for instrument in instruments[:2]:  # Top 2 instruments per view
                # Determine direction
                if "Long" in instrument:
                    direction = "long"
                elif "Short" in instrument:
                    direction = "short"
                else:
                    direction = "neutral"

                trades.append(
                    {
                        "description": f"{instrument} — expresses {view} view",
                        "direction": direction,
                        "instrument": instrument.replace("Long ", "").replace("Short ", ""),
                        "size_hint": self.POSITION_SIZING[size_category],
                        "entry": "Current market",
                        "stop": self._suggest_stop(direction, conviction),
                        "target": "TBD based on market evolution",
                        "conviction": round(conviction, 2),
                        "horizon": (
                            prediction.predictions[0]["horizon"]
                            if prediction.predictions
                            else "1-3 months"
                        ),
                    }
                )

        return trades

    def _portfolio_overview(
        self,
        pattern: PatternOutput,
        hypothesis: HypothesisOutput,
        evidence: EvidenceOutput,
    ) -> str:
        """Generate portfolio-level positioning overview."""
        net = evidence.net_weight
        conf = hypothesis.hypothesis_confidence

        if net > 0.3:
            bias = "modestly risk-on"
        elif net < -0.3:
            bias = "modestly risk-off"
        else:
            bias = "neutral / range-bound"

        if conf > 0.7:
            sizing = "full position sizes"
        elif conf > 0.5:
            sizing = "moderate position sizes"
        else:
            sizing = "reduced position sizes, emphasis on convexity"

        return (
            f"Portfolio stance: {bias} with {sizing}. "
            f"Regime: {pattern.regime_diagnosis}. "
            f"Key risk: overconfidence in consensus trade."
        )

    def _trades_to_avoid(
        self,
        pattern: PatternOutput,
        evidence: EvidenceOutput,
    ) -> list[str]:
        """Identify trades to avoid given current macro picture."""
        avoid = []
        patterns_text = " ".join(pattern.patterns).lower()

        if "risk-on" in patterns_text:
            avoid.extend(
                [
                    "Short volatility (crowded, asymmetry wrong)",
                    "Long duration (against momentum)",
                ]
            )
        elif "risk-off" in patterns_text:
            avoid.extend(
                [
                    "Long high-beta equities (catching falling knife)",
                    "Short USD in risk-off (carry trade unwind risk)",
                ]
            )

        if evidence.evidence_gaps:
            avoid.append("High-conviction bets on themes with significant evidence gaps")

        return avoid

    def _suggest_stop(self, direction: str, conviction: float) -> str:
        """Suggest stop-loss level based on conviction and direction."""
        if conviction > 0.7:
            return "2 ATR / -3% from entry"
        elif conviction > 0.5:
            return "1.5 ATR / -2% from entry"
        return "1 ATR / -1.5% from entry"

    def _execution_notes(self, hypothesis: HypothesisOutput) -> str:
        """Generate execution notes."""
        if hypothesis.hypothesis_confidence > 0.7:
            return (
                "Execute with conviction. Scale in over 2-3 days. "
                "Use limit orders near VWAP. No urgency for full size."
            )
        else:
            return (
                "Scale in slowly. Start with 1/3 position. "
                "Add only if thesis confirms. Tight stops. "
                "Emphasis on risk management over return maximization."
            )

    def _generate_trace(self, output: TradeOutput) -> str:
        """Generate reasoning trace."""
        trace = []
        trace.append("=== Stage 8: Trade ===")
        trace.append(f"Trade ideas: {len(output.trades)}")
        for t in output.trades:
            trace.append(
                f"  {t['description'][:60]}... ({t['direction']}, conv={t['conviction']:.0%})"
            )
        trace.append(f"Trades to avoid: {len(output.trades_to_avoid)}")
        return "\n".join(trace)
