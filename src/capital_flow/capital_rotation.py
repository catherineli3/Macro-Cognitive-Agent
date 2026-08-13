"""CapitalRotation — rotation regime identification.

Detects capital rotation regimes using ETF flow + positioning signals:
    - Risk-on rotation: Cash → Equities, Bonds → Equities
    - Risk-off rotation: Equities → Cash, Equities → Bonds
    - Sector rotation: Tech ←→ Value, Cyclical ←→ Defensive
    - Regional rotation: DM ←→ EM, US ←→ International
    - Safe haven: Any → Gold/Treasuries

Also integrates with reflexivity: detects Narrative → Capital → Price loops.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.capital_flow.cross_asset_flow import CrossAssetFlow
from src.capital_flow.schemas import (
    CapitalFlowRegime,
    CapitalFlowReport,
    CrossAssetFlowReport,
)


class CapitalRotation:
    """Identifies capital rotation regimes from cross-asset flow data."""

    def __init__(self):
        self.cross_asset = CrossAssetFlow()
        self._regime_history: list[CapitalFlowRegime] = []

    def detect_regime(
        self,
        flow_data: dict | None = None,
        position_data: dict | None = None,
        date: str | None = None,
        reflexivity_data: dict | None = None,
    ) -> CapitalFlowReport:
        """Full capital flow regime detection.

        Returns:
            CapitalFlowReport with regime, cross-asset, rotation signals.
        """
        if date is None:
            date = datetime.now(UTC).strftime("%Y-%m-%d")

        cross = self.cross_asset.analyze(flow_data, position_data, date)
        regime = self._classify_regime(cross, date)
        rotation_signals = self._derive_rotation_signals(cross, regime)

        # Integration with reflexivity
        reflex_warn, reflex_detail = False, ""
        if reflexivity_data:
            cycles = reflexivity_data.get("active_cycles", [])
            reflex_warn = len(cycles) > 0
            if reflex_warn:
                labels = [c.get("label", "") for c in cycles[:2]]
                reflex_detail = f"Active reflexivity cycles detected: {'; '.join(labels)}. Flow data may be self-reinforcing."

        # Key insights
        summary = self._summarize_regime(regime, cross, rotation_signals)
        actionable = self._actionable_insight(regime, cross)

        report = CapitalFlowReport(
            report_id=f"cfr_{date}",
            date=date,
            regime=regime,
            cross_asset=cross,
            rotation_signals=rotation_signals,
            reflexivity_warning=reflex_warn,
            reflexivity_detail=reflex_detail,
            summary=summary,
            actionable_insight=actionable,
        )

        self._regime_history.append(regime)
        return report

    def _classify_regime(self, cross: CrossAssetFlowReport, date: str) -> CapitalFlowRegime:
        sentiment = cross.risk_sentiment
        signals = cross.signals
        rotations = cross.rotations

        inflow_assets = []
        outflow_assets = []
        total_in = 0.0
        total_out = 0.0

        for s in signals:
            label = f"{s.asset_class}:{s.region}"
            if s.direction == "inflow":
                inflow_assets.append(label)
                total_in += s.weekly_flow_bn
            elif s.direction == "outflow":
                outflow_assets.append(label)
                total_out += abs(s.weekly_flow_bn)

        net = total_in - total_out

        # Classify regime
        rot_types = [r.get("type", "") for r in rotations]
        has_rotation = len(rotations) > 0

        if sentiment == "risk_on" and not has_rotation:
            label = "risk_on_inflow"
            interpretation = "Broad risk appetite: capital flowing into risk assets"
        elif sentiment == "risk_off" and not has_rotation:
            label = "risk_off_outflow"
            interpretation = "Broad risk aversion: capital flowing into safe havens"
        elif has_rotation:
            if any("bonds_to_equities" in t for t in rot_types):
                label = "rotation_risk_on"
                interpretation = "Rotation from safety to risk: early-cycle signal"
            elif any("equities_to_bonds" in t for t in rot_types):
                label = "rotation_risk_off"
                interpretation = "Rotation from risk to safety: late-cycle signal"
            elif any("growth_to_value" in t for t in rot_types):
                label = "rotation_sector_growth_to_value"
                interpretation = "Growth → Value rotation: rate sensitivity, cycle maturity"
            else:
                label = "rotation_active"
                interpretation = "Active sector/asset rotation underway"
        else:
            label = "balanced"
            interpretation = "Balanced flows, no dominant directional signal"

        # Prior regime
        prior = self._regime_history[-1].regime_label if self._regime_history else ""
        change_days = 0  # Could be computed from timestamps

        return CapitalFlowRegime(
            regime_label=label,
            confidence=max(0.3, min(0.9, cross.conviction)),
            inflow_assets=list(set(inflow_assets))[:5],
            outflow_assets=list(set(outflow_assets))[:5],
            total_weekly_inflow_bn=round(total_in, 2),
            total_weekly_outflow_bn=round(total_out, 2),
            net_flow_bn=round(net, 2),
            interpretation=interpretation,
            signal_strength=abs(net) / max(10.0, abs(total_in) + abs(total_out)),
            prior_regime=prior,
            regime_change_days=change_days,
        )

    def _derive_rotation_signals(
        self, cross: CrossAssetFlowReport, regime: CapitalFlowRegime
    ) -> list[dict]:
        return [
            {
                "signal_type": rot.get("type", "unknown"),
                "description": rot.get("signal", ""),
                "strength": rot.get("strength", 0),
                "from": rot.get("from", ""),
                "to": rot.get("to", ""),
            }
            for rot in cross.rotations
        ]

    def _summarize_regime(
        self,
        regime: CapitalFlowRegime,
        cross: CrossAssetFlowReport,
        rotation_signals: list,
    ) -> str:
        base = f"Capital flow regime: {regime.regime_label}"
        details = f"{regime.interpretation}. "
        if regime.inflow_assets and regime.outflow_assets:
            details += (
                f"Money entering: {', '.join(regime.inflow_assets[:3])}. "
                f"Money leaving: {', '.join(regime.outflow_assets[:3])}."
            )
        if rotation_signals:
            details += f" {len(rotation_signals)} rotation signal(s) active."
        return base + ": " + details

    def _actionable_insight(self, regime: CapitalFlowRegime, cross: CrossAssetFlowReport) -> str:
        if regime.regime_label == "risk_on_inflow":
            return "Risk appetite is broad — watch for overcrowding signals in momentum assets"
        elif regime.regime_label == "risk_off_outflow":
            return "Risk reduction underway — monitor credit spreads for acceleration signals"
        elif "rotation" in regime.regime_label:
            return "Active rotation detected — reduce trend-following, increase mean-reversion exposure"
        return "Balanced flows — wait for directional signal before repositioning"

    def get_regime_timeline(self) -> list[dict]:
        """Get historical regime timeline."""
        return [
            {
                "regime": r.regime_label,
                "confidence": r.confidence,
                "net_flow_bn": r.net_flow_bn,
            }
            for r in self._regime_history[-20:]  # Last 20 observations
        ]
