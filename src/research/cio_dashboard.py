"""V7.5 CIO Dashboard — Institutional-quality macro dashboard.

Not JSON. A real CIO dashboard that a portfolio manager would read:
    - Current Regime
    - Main Narrative
    - Top Beliefs
    - Prediction Confidence
    - Risk Monitor
    - Capital Flow
    - Regime Change Probability
    - Top Unknowns

This is the single-page view that synthesizes all research into
actionable intelligence for investment decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4


class RiskLevel(str, Enum):
    LOW = "low"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class RegimePhase(str, Enum):
    EXPANSION = "expansion"
    PEAK = "peak"
    CONTRACTION = "contraction"
    TROUGH = "trough"
    TRANSITION = "transition"


@dataclass
class CIODashboard:
    """Institutional CIO Dashboard — one-page macro intelligence."""

    dashboard_id: str = field(default_factory=lambda: uuid4().hex[:8])
    title: str = "CIO Macro Dashboard"
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # ── 1. Current Regime ────────────────────────────────────────────────
    regime: str = ""  # e.g., "Late Cycle — Cooling but Resilient"
    regime_phase: RegimePhase = RegimePhase.EXPANSION
    regime_confidence: float = 0.5
    regime_change_probability: float = 0.0  # Probability of regime change in 3 months

    # ── 2. Main Narrative ────────────────────────────────────────────────
    dominant_narrative: str = ""
    narrative_strength: float = 0.5

    # ── 3. Top Beliefs ───────────────────────────────────────────────────
    top_beliefs: list[dict] = field(default_factory=list)
    # [{name, confidence, direction, last_changed}]

    # ── 4. Prediction Confidence ─────────────────────────────────────────
    prediction_confidence: float = 0.5  # Aggregate confidence across predictions
    active_predictions: int = 0
    predictions_on_track: int = 0

    # ── 5. Risk Monitor ─────────────────────────────────────────────────
    risk_level: RiskLevel = RiskLevel.ELEVATED
    top_risks: list[dict] = field(default_factory=list)
    # [{risk, probability, severity, trend, last_update}]
    risk_score: float = 0.0  # 0–100 aggregate risk score

    # ── 6. Capital Flow ─────────────────────────────────────────────────
    capital_flows: dict = field(default_factory=dict)
    # {asset_class: {direction, magnitude, institutional_sentiment}}
    flow_regime: str = ""  # "risk-on", "risk-off", "rotation", "neutral"

    # ── 7. Key Unknowns ─────────────────────────────────────────────────
    top_unknowns: list[str] = field(default_factory=list)
    watch_items: list[dict] = field(default_factory=list)
    # [{item, deadline, importance, what_to_watch}]

    # ── 8. Positioning Summary ──────────────────────────────────────────
    positioning_bias: str = ""  # e.g., "Moderately defensive"
    conviction_level: str = ""  # "high", "medium", "low"

    # ── 9. Cross-Asset Snapshot ─────────────────────────────────────────
    asset_snapshot: dict = field(default_factory=dict)
    # {asset: {price, change_daily, change_weekly, signal}}

    # ── 10. Upcoming Catalysts ──────────────────────────────────────────
    upcoming_catalysts: list[dict] = field(default_factory=list)
    # [{event, date, importance, expected_impact}]

    # Meta
    last_updated: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def render(self) -> str:
        """Render the CIO Dashboard as a readable one-page report."""
        sections = [
            self._render_header(),
            self._render_regime(),
            self._render_narrative_beliefs(),
            self._render_prediction_confidence(),
            self._render_risk_monitor(),
            self._render_capital_flows(),
            self._render_positioning(),
            self._render_unknowns_and_watchlist(),
            self._render_upcoming_catalysts(),
            self._render_asset_snapshot(),
        ]
        return "\n\n".join(sections)

    def _render_header(self) -> str:
        return f"""# 🏦 CIO Macro Dashboard

**{self.dashboard_id}** | {self.date} | Updated: {self.last_updated[:19]}

---
"""

    def _render_regime(self) -> str:
        return f"""## 1. Current Macro Regime

**Regime**: {self.regime or 'Analyzing...'}
**Phase**: {self.regime_phase.value}
**Confidence**: {self.regime_confidence:.0%}
**Regime Change Probability (3M)**: {self.regime_change_probability:.0%}

> *A regime change is {'likely' if self.regime_change_probability > 0.5 else 'unlikely'} in the next 3 months.*
"""

    def _render_narrative_beliefs(self) -> str:
        lines = [
            "## 2. Narrative & Beliefs",
            "",
            "### Dominant Narrative",
            f"**{self.dominant_narrative or 'No dominant narrative identified.'}**",
            f"*Narrative Strength: {self.narrative_strength:.0%}*",
            "",
            "### Top Beliefs",
            "",
        ]

        if self.top_beliefs:
            for i, b in enumerate(self.top_beliefs[:5]):
                name = b.get("name", f"Belief {i+1}")
                confidence = b.get("confidence", 0.5)
                direction = b.get("direction", "neutral")
                lines.append(f"{i+1}. **{name}** — {confidence:.0%} confidence ({direction})")
        else:
            lines.append("*No active beliefs tracked.*")

        return "\n".join(lines)

    def _render_prediction_confidence(self) -> str:
        lines = [
            "## 3. Prediction Dashboard",
            "",
            f"**Aggregate Confidence**: {self.prediction_confidence:.0%}",
            f"**Active Predictions**: {self.active_predictions}",
            f"**On Track**: {self.predictions_on_track}/{self.active_predictions}",
            f"**Hit Rate**: {(self.predictions_on_track / max(self.active_predictions, 1)):.0%}",
            "",
        ]
        return "\n".join(lines)

    def _render_risk_monitor(self) -> str:
        risk_color = {
            RiskLevel.LOW: "🟢",
            RiskLevel.ELEVATED: "🟡",
            RiskLevel.HIGH: "🟠",
            RiskLevel.CRITICAL: "🔴",
        }

        lines = [
            "## 4. Risk Monitor",
            "",
            f"### Overall Risk Level: {risk_color.get(self.risk_level, '⚪')} **{self.risk_level.value.upper()}**",
            f"**Risk Score**: {self.risk_score:.0f}/100",
            "",
            "### Top Risks",
            "",
        ]

        if self.top_risks:
            lines.append("| Risk | Probability | Severity | Trend |")
            lines.append("|------|-------------|----------|-------|")
            for r in self.top_risks[:6]:
                risk = r.get("risk", "")
                prob = r.get("probability", 0)
                severity = r.get("severity", "medium")
                trend = r.get("trend", "—")
                lines.append(f"| {risk} | {prob:.0%} | {severity} | {trend} |")
        else:
            lines.append("*Risk assessment pending.*")

        return "\n".join(lines)

    def _render_capital_flows(self) -> str:
        lines = [
            "## 5. Capital Flow Monitor",
            "",
            f"**Flow Regime**: {self.flow_regime or 'No data'}",
            "",
        ]

        if self.capital_flows:
            lines.append("| Asset Class | Direction | Magnitude | Sentiment |")
            lines.append("|-------------|-----------|-----------|-----------|")
            for asset, flow in list(self.capital_flows.items())[:6]:
                if isinstance(flow, dict):
                    lines.append(
                        f"| {asset} | {flow.get('direction', '—')} | "
                        f"{flow.get('magnitude', '—')} | "
                        f"{flow.get('institutional_sentiment', '—')} |"
                    )
        else:
            lines.append("*Flow data pending.*")

        return "\n".join(lines)

    def _render_positioning(self) -> str:
        return f"""## 6. Portfolio Positioning

**Positioning Bias**: {self.positioning_bias or 'Neutral'}
**Conviction Level**: {self.conviction_level or 'Low'}

> *Positioning reflects the synthesis of all macro signals, beliefs, and risk assessments.*
"""

    def _render_unknowns_and_watchlist(self) -> str:
        lines = ["## 7. Key Unknowns & Watchlist", "", "### Top Unknowns"]

        if self.top_unknowns:
            for i, u in enumerate(self.top_unknowns[:5]):
                lines.append(f"{i+1}. {u}")
        else:
            lines.append("*No key unknowns tracked.*")

        lines.extend(["", "### Watch Items", ""])
        if self.watch_items:
            lines.append("| Item | Deadline | Importance | What to Watch |")
            lines.append("|------|----------|------------|---------------|")
            for w in self.watch_items[:5]:
                item = w.get("item", "")
                deadline = w.get("deadline", "")
                importance = w.get("importance", "")
                watch = w.get("what_to_watch", "")
                lines.append(f"| {item} | {deadline} | {importance} | {watch} |")
        else:
            lines.append("*Watchlist pending.*")

        return "\n".join(lines)

    def _render_upcoming_catalysts(self) -> str:
        lines = ["## 8. Upcoming Catalysts", ""]

        if self.upcoming_catalysts:
            lines.append("| Event | Date | Importance | Expected Impact |")
            lines.append("|-------|------|------------|-----------------|")
            for c in self.upcoming_catalysts[:5]:
                event = c.get("event", "")
                date = c.get("date", "")
                importance = c.get("importance", "")
                impact = c.get("expected_impact", "")
                lines.append(f"| {event} | {date} | {importance} | {impact} |")
        else:
            lines.append("*No upcoming catalysts tracked.*")

        return "\n".join(lines)

    def _render_asset_snapshot(self) -> str:
        lines = ["## 9. Cross-Asset Snapshot", ""]

        if self.asset_snapshot:
            lines.append("| Asset | Price | Daily Δ | Weekly Δ | Signal |")
            lines.append("|-------|-------|---------|----------|--------|")
            for asset, data in list(self.asset_snapshot.items())[:8]:
                if isinstance(data, dict):
                    price = data.get("price", "—")
                    daily = data.get("change_daily", "—")
                    weekly = data.get("change_weekly", "—")
                    signal = data.get("signal", "—")
                    lines.append(f"| {asset} | {price} | {daily} | {weekly} | {signal} |")
        else:
            lines.append("*Asset snapshot pending.*")

        lines.extend(
            [
                "",
                "---",
                "*Dashboard generated by Macro Research Agent v7.5. For internal use only.*",
            ]
        )

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "dashboard_id": self.dashboard_id,
            "date": self.date,
            "regime": self.regime,
            "regime_phase": self.regime_phase.value,
            "regime_change_probability": self.regime_change_probability,
            "dominant_narrative": self.dominant_narrative,
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "prediction_confidence": self.prediction_confidence,
            "flow_regime": self.flow_regime,
            "positioning_bias": self.positioning_bias,
            "top_unknowns": self.top_unknowns,
            "upcoming_catalysts_count": len(self.upcoming_catalysts),
        }


class CIODashboardBuilder:
    """Build CIO Dashboards programmatically."""

    def __init__(self):
        self._dash = CIODashboard()

    def regime(
        self, regime: str, phase: RegimePhase, confidence: float = 0.5, change_prob: float = 0.0
    ) -> CIODashboardBuilder:
        self._dash.regime = regime
        self._dash.regime_phase = phase
        self._dash.regime_confidence = confidence
        self._dash.regime_change_probability = change_prob
        return self

    def narrative(self, narrative: str, strength: float = 0.5) -> CIODashboardBuilder:
        self._dash.dominant_narrative = narrative
        self._dash.narrative_strength = strength
        return self

    def add_belief(
        self, name: str, confidence: float = 0.5, direction: str = "neutral", last_changed: str = ""
    ) -> CIODashboardBuilder:
        self._dash.top_beliefs.append(
            {
                "name": name,
                "confidence": confidence,
                "direction": direction,
                "last_changed": last_changed,
            }
        )
        return self

    def prediction_confidence(
        self, confidence: float = 0.5, active: int = 0, on_track: int = 0
    ) -> CIODashboardBuilder:
        self._dash.prediction_confidence = confidence
        self._dash.active_predictions = active
        self._dash.predictions_on_track = on_track
        return self

    def risk_level(self, level: RiskLevel, score: float = 0.0) -> CIODashboardBuilder:
        self._dash.risk_level = level
        self._dash.risk_score = score
        return self

    def add_risk(
        self, risk: str, probability: float = 0.1, severity: str = "medium", trend: str = "—"
    ) -> CIODashboardBuilder:
        self._dash.top_risks.append(
            {
                "risk": risk,
                "probability": probability,
                "severity": severity,
                "trend": trend,
            }
        )
        return self

    def capital_flows(self, flows: dict, regime: str = "") -> CIODashboardBuilder:
        self._dash.capital_flows = flows
        self._dash.flow_regime = regime
        return self

    def positioning(self, bias: str = "Neutral", conviction: str = "Low") -> CIODashboardBuilder:
        self._dash.positioning_bias = bias
        self._dash.conviction_level = conviction
        return self

    def add_unknown(self, unknown: str) -> CIODashboardBuilder:
        self._dash.top_unknowns.append(unknown)
        return self

    def add_watch_item(
        self, item: str, deadline: str = "", importance: str = "", watch: str = ""
    ) -> CIODashboardBuilder:
        self._dash.watch_items.append(
            {
                "item": item,
                "deadline": deadline,
                "importance": importance,
                "what_to_watch": watch,
            }
        )
        return self

    def add_catalyst(
        self, event: str, date: str = "", importance: str = "", impact: str = ""
    ) -> CIODashboardBuilder:
        self._dash.upcoming_catalysts.append(
            {
                "event": event,
                "date": date,
                "importance": importance,
                "expected_impact": impact,
            }
        )
        return self

    def asset_snapshot(self, snapshot: dict) -> CIODashboardBuilder:
        self._dash.asset_snapshot = snapshot
        return self

    def build(self) -> CIODashboard:
        return self._dash

    @staticmethod
    def from_research_data(
        topic: str,
        regime: str,
        beliefs: list[dict],
        narratives: list[str],
        predictions: list[dict],
        risks: list[dict],
        flows: dict = None,
    ) -> CIODashboard:
        """Quick-build a CIO dashboard from research pipeline outputs."""
        builder = CIODashboardBuilder()

        builder.regime(regime, RegimePhase.EXPANSION, confidence=0.6)

        if narratives:
            builder.narrative(
                narratives[0] if isinstance(narratives[0], str) else str(narratives[0])
            )

        for b in beliefs[:5]:
            if isinstance(b, dict):
                builder.add_belief(name=b.get("name", ""), confidence=b.get("confidence", 0.5))

        builder.prediction_confidence(
            confidence=sum(p.get("probability", 0) for p in predictions) / max(len(predictions), 1),
            active=len(predictions),
        )

        if risks:
            risk_probs = [r.get("probability", 0) for r in risks if isinstance(r, dict)]
            avg_risk = sum(risk_probs) / max(len(risk_probs), 1) * 100
            level = (
                RiskLevel.LOW
                if avg_risk < 20
                else RiskLevel.ELEVATED if avg_risk < 50 else RiskLevel.HIGH
            )
            builder.risk_level(level, score=avg_risk)

            for r in risks[:5]:
                if isinstance(r, dict):
                    builder.add_risk(r.get("risk", ""), r.get("probability", 0.1))

        if flows:
            builder.capital_flows(flows)

        builder.add_unknown("Will inflation prove sticky above target?")
        builder.add_unknown("When does the cutting cycle begin?")
        builder.add_unknown("Is AI capex a bubble or a structural shift?")

        return builder.build()
