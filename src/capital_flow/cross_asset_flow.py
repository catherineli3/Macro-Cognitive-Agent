"""CrossAssetFlow — cross-asset flow detection with rotation signals."""

from __future__ import annotations

from datetime import UTC, datetime

from src.capital_flow.etf_flow import ETFFlow
from src.capital_flow.institutional_position import InstitutionalPosition
from src.capital_flow.schemas import (
    CrossAssetFlowReport,
    ETFSummary,
    FlowSignal,
)


class CrossAssetFlow:
    """Integrates ETF flow + institutional positioning into a unified flow picture."""

    def __init__(self):
        self.etf = ETFFlow()
        self.positioning = InstitutionalPosition()

    def analyze(
        self,
        flow_data: dict | None = None,
        position_data: dict | None = None,
        date: str | None = None,
    ) -> CrossAssetFlowReport:
        if date is None:
            date = datetime.now(UTC).strftime("%Y-%m-%d")

        etf_summaries = self.etf.analyze_flows(flow_data, date=date)
        etf_signals = self.etf.to_flow_signals(etf_summaries)
        snapshots = self.positioning.analyze_positions(position_data, date=date)
        pos_signals = self.positioning.to_flow_signals(snapshots)
        all_signals = etf_signals + pos_signals
        rotations = self._detect_rotations(etf_summaries)
        sentiment, conviction = self._assess_sentiment(all_signals)
        narrative = self._generate_narrative(etf_summaries, snapshots, sentiment)

        return CrossAssetFlowReport(
            report_id=f"caf_{date}",
            date=date,
            signals=all_signals,
            rotations=rotations,
            narrative=narrative,
            risk_sentiment=sentiment,
            conviction=round(conviction, 2),
        )

    def _detect_rotations(self, summaries: list[ETFSummary]) -> list[dict]:
        rotations = []
        if not summaries:
            return rotations

        tech = self._find_summary(summaries, "equities_us_tech")
        value = self._find_summary(summaries, "equities_us_large")
        if tech and value:
            if tech.weekly_flow_bn < -0.5 and value.weekly_flow_bn > 0.5:
                rotations.append(
                    {
                        "type": "growth_to_value",
                        "from": "Tech/Growth",
                        "to": "Value/Cyclicals",
                        "strength": min(abs(tech.weekly_flow_bn), value.weekly_flow_bn) / 5.0,
                        "signal": "de-risking from high-beta tech to value",
                    }
                )
            elif value.weekly_flow_bn < -0.5 and tech.weekly_flow_bn > 0.5:
                rotations.append(
                    {
                        "type": "value_to_growth",
                        "from": "Value/Cyclicals",
                        "to": "Tech/Growth",
                        "strength": min(value.weekly_flow_bn, tech.weekly_flow_bn) / 5.0,
                        "signal": "risk-on rotation into high-beta tech",
                    }
                )

        # Risk-on/off rotation: equities vs. bonds
        eq = self._find_summary(summaries, "equities_us_large")
        bond = self._find_summary(summaries, "bonds_agg") or self._find_summary(
            summaries, "bonds_treasury"
        )
        if eq and bond:
            if eq.weekly_flow_bn > 1 and bond.weekly_flow_bn < 0:
                rotations.append(
                    {
                        "type": "bonds_to_equities",
                        "from": "Fixed Income",
                        "to": "Equities",
                        "strength": max(0, eq.weekly_flow_bn) / 10.0,
                        "signal": "risk-on rotation out of bonds",
                    }
                )
            elif bond.weekly_flow_bn > 1 and eq.weekly_flow_bn < 0:
                rotations.append(
                    {
                        "type": "equities_to_bonds",
                        "from": "Equities",
                        "to": "Fixed Income",
                        "strength": max(0, bond.weekly_flow_bn) / 10.0,
                        "signal": "risk-off rotation into safety",
                    }
                )

        # Gold rotation signal
        gold = self._find_summary(summaries, "gold")
        if gold and abs(gold.weekly_flow_bn) > 1:
            rotations.append(
                {
                    "type": "gold_flow",
                    "from": "other",
                    "to": "Gold",
                    "direction": "inflow" if gold.weekly_flow_bn > 0 else "outflow",
                    "strength": abs(gold.weekly_flow_bn) / 5.0,
                    "signal": (
                        "safe-haven demand" if gold.weekly_flow_bn > 0 else "reduced haven demand"
                    ),
                }
            )

        # EM outflows
        em = self._find_summary(summaries, "equities_em")
        if em and em.weekly_flow_bn < -1:
            rotations.append(
                {
                    "type": "em_outflow",
                    "from": "Emerging Markets",
                    "to": "Developed/Cash",
                    "strength": abs(em.weekly_flow_bn) / 5.0,
                    "signal": "EM risk reduction — dollar funding stress indicator",
                }
            )

        return rotations

    def _assess_sentiment(self, signals: list[FlowSignal]) -> tuple:
        if not signals:
            return "neutral", 0.3

        risk_on_assets = {"equities", "commodities"}
        risk_off_assets = {"bonds", "gold", "cash", "volatility"}

        risk_on_score = sum(
            s.magnitude
            for s in signals
            if s.asset_class in risk_on_assets and s.direction == "inflow"
        )
        risk_off_score = sum(
            s.magnitude
            for s in signals
            if s.asset_class in risk_off_assets and s.direction == "inflow"
        )

        net = risk_on_score - risk_off_score
        confidence = abs(net) / max(1.0, len(signals) * 0.5)

        if net > 0.3:
            return "risk_on", min(0.95, confidence)
        elif net < -0.3:
            return "risk_off", min(0.95, confidence)
        return "neutral", confidence

    def _generate_narrative(
        self,
        summaries: list[ETFSummary],
        snapshots: list,
        sentiment: str,
    ) -> str:
        parts = []
        inflows = sorted(
            [s for s in summaries if s.weekly_flow_bn > 0],
            key=lambda s: s.weekly_flow_bn,
            reverse=True,
        )
        outflows = sorted(
            [s for s in summaries if s.weekly_flow_bn < 0],
            key=lambda s: s.weekly_flow_bn,
        )

        if inflows:
            top_flow = inflows[0]
            parts.append(f"Money flowing into {top_flow.category}")
            if len(inflows) > 1:
                parts.append(f"and {inflows[1].category}")

        if outflows:
            top_out = outflows[0]
            parts.append(f"flowing out of {top_out.category}")

        if not parts:
            parts.append("Flows are balanced/neutral")

        parts.append(f"[{sentiment} regime]")
        return " | ".join(parts)

    def _find_summary(self, summaries: list[ETFSummary], cat: str) -> ETFSummary | None:
        for s in summaries:
            if s.category == cat:
                return s
        return None
