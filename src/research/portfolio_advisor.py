"""V8.2 Portfolio Recommendation — Research-driven positioning guidance.

Not buy/sell recommendations. Research recommendations.

Based on:
    Belief → Regime → Capital Flow → Narrative → Prediction

Output:
    Recommended Position: Increase / Decrease / Neutral / Avoid
    With full reasoning chain and risk considerations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4


class PositionAction(str, Enum):
    INCREASE = "increase"  # Add to position
    DECREASE = "decrease"  # Reduce position
    MAINTAIN = "maintain"  # Hold current
    INITIATE = "initiate"  # New position
    EXIT = "exit"  # Close position
    AVOID = "avoid"  # Do not enter
    HEDGE = "hedge"  # Add protection


class ConvictionLevel(str, Enum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


@dataclass
class AssetRecommendation:
    """Research recommendation for a single asset or asset class."""

    rec_id: str = field(default_factory=lambda: uuid4().hex[:8])
    asset: str = ""  # e.g., "US Equities (SPX)", "10Y UST"
    asset_class: str = ""

    # Recommendation
    action: PositionAction = PositionAction.MAINTAIN
    conviction: ConvictionLevel = ConvictionLevel.MEDIUM

    # Reasoning chain
    belief_driver: str = ""  # Which belief drives this?
    regime_alignment: str = ""  # How does this fit the regime?
    narrative_support: str = ""  # Which narrative supports?
    flow_signal: str = ""  # What are flows saying?
    prediction_link: str = ""  # Which prediction?

    # Risk
    key_risks: list[str] = field(default_factory=list)
    invalidation_condition: str = ""
    sizing_guidance: str = ""  # e.g., "1-2% of portfolio"

    # Meta
    last_updated: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    horizon: str = "3-6 months"

    def to_dict(self) -> dict:
        return {
            "asset": self.asset,
            "action": self.action.value,
            "conviction": self.conviction.value,
            "belief_driver": self.belief_driver,
            "regime_alignment": self.regime_alignment,
            "invalidation": self.invalidation_condition,
        }


@dataclass
class PortfolioRecommendation:
    """Complete portfolio-level research recommendation."""

    portfolio_id: str = field(default_factory=lambda: uuid4().hex[:8])
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Overview
    overall_stance: str = ""  # e.g., "Moderately constructive, selective"
    risk_budget: str = ""  # e.g., "75% of risk budget deployed"

    # Macro context
    regime: str = ""
    regime_confidence: float = 0.5
    dominant_narrative: str = ""

    # Recommendations
    recommendations: list[AssetRecommendation] = field(default_factory=list)

    # Summary matrix
    action_summary: dict[str, int] = field(default_factory=dict)
    conviction_distribution: dict[str, int] = field(default_factory=dict)

    # Key themes
    overweight_themes: list[str] = field(default_factory=list)
    underweight_themes: list[str] = field(default_factory=list)
    avoid_themes: list[str] = field(default_factory=list)

    # Risk management
    portfolio_risks: list[dict] = field(default_factory=list)
    correlation_warning: str = ""
    stress_scenario: str = ""

    # Monitoring
    watch_triggers: list[str] = field(default_factory=list)

    def render(self) -> str:
        """Render portfolio recommendation as a research note."""
        lines = [
            "# Portfolio Recommendation",
            f"**Date**: {self.date} | **ID**: {self.portfolio_id}",
            "",
            "---",
            "",
            "## Overall Stance",
            self.overall_stance,
            f"**Risk Budget**: {self.risk_budget}",
            "",
            "## Macro Context",
            f"**Regime**: {self.regime} (confidence: {self.regime_confidence:.0%})",
            f"**Dominant Narrative**: {self.dominant_narrative}",
            "",
            "## Recommendations",
            "",
            "| Asset | Action | Conviction | Invalidation |",
            "|-------|--------|------------|--------------|",
        ]

        for rec in self.recommendations:
            action_icon = {
                PositionAction.INCREASE: "🟢 Increase",
                PositionAction.INITIATE: "🟢 Initiate",
                PositionAction.MAINTAIN: "⚪ Maintain",
                PositionAction.DECREASE: "🟠 Decrease",
                PositionAction.EXIT: "🔴 Exit",
                PositionAction.AVOID: "⛔ Avoid",
                PositionAction.HEDGE: "🛡️ Hedge",
            }.get(rec.action, "—")

            lines.append(
                f"| {rec.asset} | {action_icon} | {rec.conviction.value} | "
                f"{rec.invalidation_condition[:60]} |"
            )

        lines.extend(
            [
                "",
                "## Key Themes",
                "",
                "### Overweight",
            ]
        )
        for t in self.overweight_themes:
            lines.append(f"- {t}")

        lines.extend(["", "### Underweight / Avoid"])
        for t in self.underweight_themes + self.avoid_themes:
            lines.append(f"- {t}")

        lines.extend(
            [
                "",
                "## Risk Management",
                f"**Correlation Warning**: {self.correlation_warning or 'No warning'}",
                f"**Stress Scenario**: {self.stress_scenario or 'None specified'}",
                "",
                "## Monitoring Triggers",
            ]
        )
        for t in self.watch_triggers:
            lines.append(f"- [ ] {t}")

        lines.extend(
            [
                "",
                "---",
                "*Research recommendation. Not investment advice. All positions carry risk.*",
            ]
        )

        return "\n".join(lines)


class PortfolioAdvisor:
    """Generate research-driven portfolio recommendations.

    Maps the full research stack into actionable positioning guidance:
    Belief → Regime → Capital Flow → Narrative → Prediction → Recommendation
    """

    # Regime-to-positioning mapping
    REGIME_POSITIONING = {
        "expansion": {
            "equity": PositionAction.INCREASE,
            "fixed_income": PositionAction.DECREASE,
            "commodity": PositionAction.INCREASE,
            "cash": PositionAction.DECREASE,
        },
        "peak": {
            "equity": PositionAction.MAINTAIN,
            "fixed_income": PositionAction.INCREASE,
            "commodity": PositionAction.MAINTAIN,
            "cash": PositionAction.MAINTAIN,
        },
        "contraction": {
            "equity": PositionAction.DECREASE,
            "fixed_income": PositionAction.INCREASE,
            "commodity": PositionAction.DECREASE,
            "cash": PositionAction.INCREASE,
        },
        "trough": {
            "equity": PositionAction.INCREASE,
            "fixed_income": PositionAction.DECREASE,
            "commodity": PositionAction.INCREASE,
            "cash": PositionAction.DECREASE,
        },
    }

    def __init__(self):
        self._history: list[PortfolioRecommendation] = []

    def recommend(
        self,
        regime: str = "",
        regime_confidence: float = 0.5,
        beliefs: list[dict] | None = None,
        narratives: list[str] | None = None,
        capital_flows: dict | None = None,
        predictions: list[dict] | None = None,
        risks: list[dict] | None = None,
        current_positions: dict | None = None,
    ) -> PortfolioRecommendation:
        """Generate a complete portfolio recommendation."""

        rec = PortfolioRecommendation(
            regime=regime,
            regime_confidence=regime_confidence,
            dominant_narrative=narratives[0] if narratives else "",
        )

        # Generate individual asset recommendations
        assets = self._get_asset_universe()

        for asset_info in assets:
            asset_rec = self._recommend_asset(
                asset_info,
                regime,
                beliefs,
                narratives,
                capital_flows,
                predictions,
                risks,
                current_positions,
            )
            rec.recommendations.append(asset_rec)

        # Compute summaries
        rec.action_summary = self._summarize_actions(rec.recommendations)
        rec.conviction_distribution = self._summarize_convictions(rec.recommendations)

        # Overall stance
        rec.overall_stance = self._determine_overall_stance(rec.action_summary, rec.regime)
        rec.risk_budget = self._recommend_risk_budget(rec.overall_stance)

        # Themes
        rec.overweight_themes = self._identify_themes(rec.recommendations, "increase")
        rec.underweight_themes = self._identify_themes(rec.recommendations, "decrease")
        rec.avoid_themes = self._identify_themes(rec.recommendations, "avoid")

        # Risk
        if risks:
            rec.portfolio_risks = risks[:5]
        rec.stress_scenario = self._generate_stress_scenario(risks)
        rec.watch_triggers = self._generate_watch_triggers(rec.recommendations)

        self._history.append(rec)
        return rec

    def get_latest(self) -> PortfolioRecommendation | None:
        if self._history:
            return self._history[-1]
        return None

    def get_history(self) -> list[PortfolioRecommendation]:
        return list(self._history)

    def get_stats(self) -> dict:
        if not self._history:
            return {"total_recommendations": 0}

        latest = self._history[-1]
        return {
            "total_recommendations": len(self._history),
            "latest_stance": latest.overall_stance,
            "latest_actions": latest.action_summary,
            "avg_recommendations": (
                sum(len(r.recommendations) for r in self._history) / len(self._history)
            ),
        }

    # ── Internal ─────────────────────────────────────────────────────────

    def _get_asset_universe(self) -> list[dict]:
        return [
            {"asset": "US Equities (SPX)", "asset_class": "equity"},
            {"asset": "US Tech (NDX)", "asset_class": "equity"},
            {"asset": "European Equities (SX5E)", "asset_class": "equity"},
            {"asset": "Japanese Equities (NKY)", "asset_class": "equity"},
            {"asset": "Chinese Equities (CSI300)", "asset_class": "equity"},
            {"asset": "US 2Y Treasuries", "asset_class": "fixed_income"},
            {"asset": "US 10Y Treasuries", "asset_class": "fixed_income"},
            {"asset": "US IG Credit", "asset_class": "fixed_income"},
            {"asset": "US HY Credit", "asset_class": "fixed_income"},
            {"asset": "USD (DXY)", "asset_class": "fx"},
            {"asset": "Gold", "asset_class": "commodity"},
            {"asset": "Crude Oil (WTI)", "asset_class": "commodity"},
            {"asset": "Cash / T-bills", "asset_class": "cash"},
        ]

    def _recommend_asset(
        self,
        asset_info: dict,
        regime: str,
        beliefs: list[dict] | None,
        narratives: list[str] | None,
        flows: dict | None,
        predictions: list[dict] | None,
        risks: list[dict] | None,
        positions: dict | None,
    ) -> AssetRecommendation:
        """Recommend action for a single asset."""

        asset_class = asset_info["asset_class"]
        asset_name = asset_info["asset"]

        # Regime-based default
        regime_map = self.REGIME_POSITIONING.get(regime.lower().split()[0], {})
        default_action = regime_map.get(asset_class, PositionAction.MAINTAIN)

        # Adjust based on beliefs
        conviction = ConvictionLevel.MEDIUM
        belief_driver = ""

        if beliefs:
            for b in beliefs:
                if isinstance(b, dict) and asset_class in str(b.get("name", "")).lower():
                    belief_conf = b.get("confidence", 0.5)
                    if belief_conf > 0.7:
                        conviction = ConvictionLevel.HIGH
                    belief_driver = b.get("name", "")
                    break

        # Flow adjustment
        flow_signal = ""
        if flows and asset_class in flows:
            flow_info = flows[asset_class]
            flow_signal = (
                str(flow_info)
                if not isinstance(flow_info, dict)
                else flow_info.get("direction", "")
            )

        # Prediction link
        prediction_link = ""
        if predictions:
            for p in predictions:
                if isinstance(p, dict) and asset_class in str(p.get("prediction", "")).lower():
                    prediction_link = p.get("prediction", "")
                    break

        # Generate recommendation
        rec = AssetRecommendation(
            asset=asset_name,
            asset_class=asset_class,
            action=default_action,
            conviction=conviction,
            belief_driver=belief_driver,
            regime_alignment=f"Aligned with {regime} regime positioning.",
            narrative_support=narratives[0] if narratives else "",
            flow_signal=flow_signal,
            prediction_link=prediction_link,
            invalidation_condition=f"{regime} regime proves transitory or data deteriorates significantly.",
            sizing_guidance=self._sizing_guidance(default_action, conviction),
        )

        # Risk mapping
        if risks:
            rec.key_risks = [r.get("risk", str(r)) for r in risks[:3] if isinstance(r, dict)]

        return rec

    def _summarize_actions(self, recs: list[AssetRecommendation]) -> dict[str, int]:
        summary = {}
        for r in recs:
            key = r.action.value
            summary[key] = summary.get(key, 0) + 1
        return summary

    def _summarize_convictions(self, recs: list[AssetRecommendation]) -> dict[str, int]:
        summary = {}
        for r in recs:
            key = r.conviction.value
            summary[key] = summary.get(key, 0) + 1
        return summary

    def _determine_overall_stance(self, actions: dict[str, int], regime: str) -> str:
        increase = actions.get("increase", 0) + actions.get("initiate", 0)
        decrease = actions.get("decrease", 0) + actions.get("exit", 0) + actions.get("avoid", 0)
        maintain = actions.get("maintain", 0)

        if increase > decrease + 2:
            return f"Constructive — favoring risk assets in {regime} regime"
        elif decrease > increase + 2:
            return f"Defensive — reducing risk in {regime} regime"
        elif maintain > increase + decrease:
            return "Neutral — maintaining current positioning, selective adjustments"
        else:
            return "Balanced — modest tilts, watching for regime confirmation"

    def _recommend_risk_budget(self, stance: str) -> str:
        if "Constructive" in stance:
            return "80-90% of risk budget deployed"
        elif "Defensive" in stance:
            return "40-60% of risk budget deployed"
        else:
            return "60-75% of risk budget deployed"

    def _identify_themes(self, recs: list[AssetRecommendation], action_type: str) -> list[str]:
        themes = []
        for r in recs:
            if action_type == "increase" and r.action == PositionAction.INCREASE:
                themes.append(f"{r.asset} — driven by {r.belief_driver or r.regime_alignment[:60]}")
            elif action_type == "decrease" and r.action in (
                PositionAction.DECREASE,
                PositionAction.EXIT,
            ):
                themes.append(f"{r.asset} — reduced exposure")
            elif action_type == "avoid" and r.action == PositionAction.AVOID:
                themes.append(f"{r.asset} — unfavorable risk/reward")
        return themes[:6]

    def _sizing_guidance(self, action: PositionAction, conviction: ConvictionLevel) -> str:
        if action in (PositionAction.INCREASE, PositionAction.INITIATE):
            if conviction in (ConvictionLevel.HIGH, ConvictionLevel.VERY_HIGH):
                return "2-3% position size"
            return "1-2% position size"
        elif action == PositionAction.MAINTAIN:
            return "Maintain current allocation"
        elif action == PositionAction.DECREASE:
            return "Reduce to 0.5-1% or hedging position"
        elif action == PositionAction.AVOID:
            return "No allocation recommended"
        return "Size conservatively"

    def _generate_stress_scenario(self, risks: list[dict] | None) -> str:
        if not risks:
            return "Multi-standard-deviation tail event across correlated risk assets."

        top_risks = [r.get("risk", "") for r in risks[:3] if isinstance(r, dict)]
        if top_risks:
            return f"Simultaneous realization of: {' + '.join(top_risks)}"
        return "Severe risk-off event with correlation breakdown."

    def _generate_watch_triggers(self, recs: list[AssetRecommendation]) -> list[str]:
        triggers = set()
        for r in recs[:8]:
            if r.invalidation_condition:
                triggers.add(r.invalidation_condition[:100])

        if not triggers:
            triggers = {
                "Significant deterioration in macro data",
                "Central bank policy surprise",
                "Correlation breakdown across asset classes",
                "Liquidity event in key markets",
            }

        return list(triggers)[:6]
