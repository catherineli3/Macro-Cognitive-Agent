"""Phase 4: CIOBrief — CIO-Level Macro Brief.

7-section structured macro assessment:
    1. Current Regime       — What regime are we in right now?
    2. What Changed         — What's different from prior assessment?
    3. Market Narrative     — What story is the market telling?
    4. Evidence Supporting  — Data that backs the narrative
    5. Evidence Contradicting — Data that challenges it
    6. Investment Implication — What does this mean for portfolios?
    7. Risks To Monitor     — What could break the thesis?

Reuses: EvidenceSynthesizer (theme clustering) + MarketChallenge (risk assessment patterns).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.summary_engine.macro_state_layer import MacroState
from src.summary_engine.change_detector import ChangeSignals, DivergenceSignal
from src.summary_engine.narrative_generator import MacroNarrative
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CIOBrief:
    """7-section CIO-level macro brief."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    date_str: str = ""

    # Section 1: Current Regime
    current_regime: str = ""
    regime_description: str = ""
    regime_indicators: list[str] = field(default_factory=list)

    # Section 2: What Changed
    what_changed: list[str] = field(default_factory=list)
    key_changes: list[str] = field(default_factory=list)

    # Section 3: Market Narrative
    market_narrative: str = ""
    narrative_theme: str = ""

    # Section 4: Evidence Supporting
    evidence_supporting: list[str] = field(default_factory=list)

    # Section 5: Evidence Contradicting
    evidence_contradicting: list[str] = field(default_factory=list)

    # Section 6: Investment Implication
    investment_implication: str = ""
    asset_views: dict[str, str] = field(default_factory=dict)  # asset_class → view

    # Section 7: Risks To Monitor
    risks_to_monitor: list[str] = field(default_factory=list)
    tail_risks: list[str] = field(default_factory=list)
    key_levels: dict[str, str] = field(default_factory=dict)  # indicator → level to watch

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "date_str": self.date_str,
            "current_regime": {
                "name": self.current_regime,
                "description": self.regime_description,
                "indicators": self.regime_indicators,
            },
            "what_changed": {
                "summary": self.what_changed,
                "key_changes": self.key_changes,
            },
            "market_narrative": {
                "story": self.market_narrative,
                "theme": self.narrative_theme,
            },
            "evidence_supporting": self.evidence_supporting,
            "evidence_contradicting": self.evidence_contradicting,
            "investment_implication": {
                "summary": self.investment_implication,
                "asset_views": self.asset_views,
            },
            "risks_to_monitor": {
                "primary": self.risks_to_monitor,
                "tail": self.tail_risks,
                "key_levels": self.key_levels,
            },
        }

    def to_display_lines(self, width: int = 80) -> list[str]:
        """Convert to formatted display lines for terminal output."""
        lines = []
        bar = "─" * width

        # Header
        lines.append(f"📋 CIO MACRO BRIEF — {self.date_str}")
        lines.append(bar)

        # Section 1
        lines.append("")
        lines.append("1. CURRENT REGIME")
        lines.append(f"   Regime: {self.current_regime.upper()}")
        lines.append(f"   {self.regime_description}")
        for ind in self.regime_indicators:
            lines.append(f"   • {ind}")

        # Section 2
        lines.append("")
        lines.append("2. WHAT CHANGED")
        if self.what_changed:
            for change in self.what_changed:
                lines.append(f"   • {change}")
        else:
            lines.append("   No significant changes detected")

        # Section 3
        lines.append("")
        lines.append("3. MARKET NARRATIVE")
        lines.append(f"   Theme: {self.narrative_theme}")
        lines.append(f"   {self.market_narrative}")

        # Section 4
        lines.append("")
        lines.append("4. EVIDENCE SUPPORTING")
        for i, ev in enumerate(self.evidence_supporting, 1):
            lines.append(f"   {i}. {ev}")

        # Section 5
        lines.append("")
        lines.append("5. EVIDENCE CONTRADICTING")
        if self.evidence_contradicting:
            for i, ev in enumerate(self.evidence_contradicting, 1):
                lines.append(f"   {i}. {ev}")
        else:
            lines.append("   No contradicting evidence — high conviction environment")

        # Section 6
        lines.append("")
        lines.append("6. INVESTMENT IMPLICATION")
        lines.append(f"   {self.investment_implication}")
        for asset, view in self.asset_views.items():
            lines.append(f"   • {asset}: {view}")

        # Section 7
        lines.append("")
        lines.append("7. RISKS TO MONITOR")
        for i, risk in enumerate(self.risks_to_monitor, 1):
            lines.append(f"   {i}. {risk}")
        if self.tail_risks:
            lines.append("")
            lines.append("   Tail Risks:")
            for tr in self.tail_risks:
                lines.append(f"   ⚠ {tr}")

        lines.append("")
        lines.append(bar)
        return lines


# ═══════════════════════════════════════════════════════════════════════════════
# CIOBriefGenerator
# ═══════════════════════════════════════════════════════════════════════════════


# ── Regime Descriptions ──────────────────────────────────────────────────────
REGIME_DESCRIPTIONS = {
    "risk_on": "Risk appetite elevated — equities bid, volatility suppressed, credit spreads tight. Markets pricing benign macro outcome.",
    "risk_off": "Risk aversion dominant — safe-haven demand elevated, volatility spiking, credit stress building. Markets pricing adverse scenario.",
    "cautious": "Guarded optimism — moderate risk-taking with hedging demand. Markets in wait-and-see mode.",
    "normal": "Balanced macro environment — no extreme positioning. Markets pricing baseline expectations.",
}

# ── Asset View Templates ─────────────────────────────────────────────────────
ASSET_VIEW_TEMPLATES = {
    "reflation": {
        "equities": "Cyclical overweight — financials, energy, materials",
        "fixed_income": "Short duration — rising rate risk",
        "commodities": "Overweight — inflation hedge",
        "gold": "Neutral — real yield headwind",
        "usd": "Strong — rate differential support",
    },
    "soft_landing": {
        "equities": "Quality tilt — balanced growth/value",
        "fixed_income": "Duration neutral — barbell strategy",
        "commodities": "Underweight — demand moderation",
        "gold": "Modest overweight — insurance",
        "usd": "Weakening — easing expectations",
    },
    "hard_landing": {
        "equities": "Defensive underweight — utilities, staples, healthcare",
        "fixed_income": "Long duration — recession pricing",
        "commodities": "Underweight — demand destruction",
        "gold": "Overweight — safe haven",
        "usd": "Mixed — flight to quality vs rate cuts",
    },
    "dovish_pivot": {
        "equities": "Rate-sensitive overweight — homebuilders, REITs, growth",
        "fixed_income": "Long duration — rate cut beneficiary",
        "commodities": "Neutral — mixed signals",
        "gold": "Overweight — lower real rates",
        "usd": "Bearish — rate differential compression",
    },
    "liquidity_rally": {
        "equities": "High beta overweight — growth, tech, EM",
        "fixed_income": "Credit overweight — carry strategies",
        "commodities": "Modest overweight — reflation trade",
        "gold": "Underweight — risk-on",
        "usd": "Bearish — global liquidity expansion",
    },
    "risk_rout": {
        "equities": "Significant underweight — raise cash",
        "fixed_income": "Sovereign only — credit underweight",
        "commodities": "Underweight except gold",
        "gold": "Overweight — ultimate safe haven",
        "usd": "Bullish — flight to safety",
    },
    "stagflation": {
        "equities": "Defensive overweight — commodities producers",
        "fixed_income": "TIPS overweight — inflation protection",
        "commodities": "Overweight — real assets",
        "gold": "Overweight — stagflation hedge",
        "usd": "Mixed — inflation vs growth drag",
    },
    "mixed_signals": {
        "equities": "Market neutral — wait for clarity",
        "fixed_income": "Duration neutral — barbell",
        "commodities": "Diversification position only",
        "gold": "Strategic allocation",
        "usd": "Neutral — range-bound expectation",
    },
}

# ── Investment Implication Summaries ─────────────────────────────────────────
INVESTMENT_SUMMARIES = {
    "reflation": "Position for rising nominal growth. Overweight cyclical equities and commodities. Underweight long-duration fixed income. Expect value to outperform growth, small caps to outperform large.",
    "soft_landing": "Balanced risk positioning with a quality bias. Duration exposure adds diversification value. Favor companies with pricing power and strong balance sheets. Gradual risk addition on dips.",
    "hard_landing": "Capital preservation priority. Overweight defensives and safe havens. Long duration as recession hedge. Raise cash levels. Avoid cyclicals and high-beta exposure.",
    "dovish_pivot": "Front-run easing cycle. Overweight duration and rate-sensitive sectors. Gold benefits from lower real rates. USD to weaken — favor international and EM exposure.",
    "liquidity_rally": "Ride the liquidity wave. Overweight growth, high-beta, and EM. Credit and carry strategies outperform. Risk: liquidity can reverse quickly — maintain hedges.",
    "risk_rout": "Defense first. Reduce gross exposure. Overweight cash, gold, and sovereign bonds. Prepare buy list for capitulation. Do not fade the sell-off prematurely.",
    "stagflation": "Difficult environment for traditional 60/40. Overweight real assets — commodities, TIPS, gold. Defensive equity positioning. Avoid long duration — inflation erodes real returns.",
    "mixed_signals": "Capital preservation with selective deployment. Maintain strategic allocations. Focus on bottom-up alpha generation. Prepare for regime resolution in either direction.",
}


class CIOBriefGenerator:
    """Generate CIO-level macro brief from research intelligence outputs.

    Reuses:
        - EvidenceSynthesizer theme patterns
        - MarketChallenge risk assessment patterns
    """

    def __init__(self) -> None:
        pass

    def generate(
        self,
        date_str: str,
        macro_state: MacroState,
        change_signals: ChangeSignals,
        narrative: MacroNarrative,
        indicators: dict,
    ) -> CIOBrief:
        """Generate complete CIO brief.

        Args:
            date_str: Date string for display
            macro_state: Phase 1 output
            change_signals: Phase 2 output
            narrative: Phase 3 output
            indicators: Raw indicators dict for key levels
        """
        brief = CIOBrief()
        brief.date_str = date_str

        # Section 1: Current Regime
        self._build_regime_section(brief, macro_state, change_signals)

        # Section 2: What Changed
        self._build_changes_section(brief, change_signals, macro_state)

        # Section 3: Market Narrative
        self._build_narrative_section(brief, narrative)

        # Section 4: Evidence Supporting
        brief.evidence_supporting = narrative.supporting_evidence

        # Section 5: Evidence Contradicting
        brief.evidence_contradicting = narrative.contradicting_evidence

        # Section 6: Investment Implication
        self._build_investment_section(brief, narrative, macro_state)

        # Section 7: Risks To Monitor
        self._build_risks_section(brief, narrative, change_signals, macro_state, indicators)

        logger.info("cio_brief_done | regime=%s theme=%s", brief.current_regime, brief.narrative_theme)
        return brief

    # ── Section Builders ─────────────────────────────────────────────────────

    def _build_regime_section(
        self,
        brief: CIOBrief,
        macro_state: MacroState,
        change_signals: ChangeSignals,
    ) -> None:
        """Section 1: Current Regime."""
        regime = macro_state.overall_risk_regime
        brief.current_regime = regime
        brief.regime_description = REGIME_DESCRIPTIONS.get(
            regime, "Balanced macro environment."
        )

        # Build regime indicator summary
        indicators = []
        for name, state in [
            ("Growth", macro_state.growth_state),
            ("Inflation", macro_state.inflation_state),
            ("Liquidity", macro_state.liquidity_state),
            ("Credit", macro_state.credit_state),
            ("Risk Appetite", macro_state.risk_state),
        ]:
            if state:
                indicators.append(
                    f"{name}: {state.direction} ({state.level}), momentum {state.momentum}"
                )

        # Add significant divergences
        for d in change_signals.divergence_signals:
            if d.is_diverging and d.significance > 0.3:
                indicators.append(
                    f"⚠ Divergence: {d.asset_a} vs {d.asset_b}"
                )

        brief.regime_indicators = indicators

    def _build_changes_section(
        self,
        brief: CIOBrief,
        change_signals: ChangeSignals,
        macro_state: MacroState,
    ) -> None:
        """Section 2: What Changed."""
        changes = []

        # Regime change
        if change_signals.regime_change and change_signals.regime_change.has_shifted:
            changes.append(
                f"Regime shifted: {change_signals.regime_change.previous_regime} → "
                f"{change_signals.regime_change.current_regime}"
            )

        # Strong momentum signals
        for m in change_signals.momentum_signals[:5]:
            if abs(m.score) > 0.4:
                direction = "up" if m.score > 0 else "down"
                changes.append(f"{m.indicator}: strong move {direction} ({m.strength})")

        # Acceleration
        for acc in change_signals.acceleration_signals[:3]:
            changes.append(f"Acceleration: {acc}")

        # Divergences
        for d in change_signals.divergence_signals:
            if d.is_diverging:
                changes.append(f"New divergence: {d.asset_a} vs {d.asset_b}")

        brief.what_changed = changes
        brief.key_changes = change_signals.strongest_signals

    def _build_narrative_section(
        self,
        brief: CIOBrief,
        narrative: MacroNarrative,
    ) -> None:
        """Section 3: Market Narrative."""
        brief.narrative_theme = narrative.narrative_theme
        brief.market_narrative = narrative.dominant_narrative

    def _build_investment_section(
        self,
        brief: CIOBrief,
        narrative: MacroNarrative,
        macro_state: MacroState,
    ) -> None:
        """Section 6: Investment Implication."""
        theme = narrative.narrative_theme

        brief.investment_implication = INVESTMENT_SUMMARIES.get(
            theme, INVESTMENT_SUMMARIES["mixed_signals"]
        )

        brief.asset_views = ASSET_VIEW_TEMPLATES.get(
            theme, ASSET_VIEW_TEMPLATES["mixed_signals"]
        )

        # Add risk-based overlay
        if macro_state.overall_risk_regime == "risk_off":
            brief.asset_views["cash"] = "Overweight — capital preservation"
        elif macro_state.overall_risk_regime == "risk_on":
            brief.asset_views["cash"] = "Underweight — deploy into risk assets"

    def _build_risks_section(
        self,
        brief: CIOBrief,
        narrative: MacroNarrative,
        change_signals: ChangeSignals,
        macro_state: MacroState,
        indicators: dict,
    ) -> None:
        """Section 7: Risks To Monitor."""
        risks = []

        # Uncertainty as primary risk
        risks.append(f"Key uncertainty: {narrative.key_uncertainty}")

        # Divergence risks
        for d in change_signals.divergence_signals:
            if d.is_diverging and d.significance > 0.3:
                risks.append(
                    f"Divergence risk: {d.asset_a}-{d.asset_b} disconnect — if {d.asset_b} "
                    f"catches {'down' if d.direction_b == 'down' else 'up'} to {d.asset_a}, "
                    f"expect {self._divergence_resolution_impact(d)}"
                )

        # Regime shift risk
        if change_signals.regime_change and change_signals.regime_change.has_shifted:
            risks.append("Regime in transition — previous correlations may break down")

        # Momentum reversal risk
        strongest = [m for m in change_signals.momentum_signals if abs(m.score) > 0.5]
        if strongest:
            assets = ", ".join(m.indicator for m in strongest[:3])
            risks.append(f"Positioning risk: {assets} extended — mean reversion risk elevated")

        # Tail risks
        tail = []
        if macro_state.inflation_state and macro_state.inflation_state.direction == "rising":
            tail.append("Inflation re-acceleration forces hawkish Fed pivot")
        if macro_state.growth_state and macro_state.growth_state.direction == "contracting":
            tail.append("Growth scare morphs into full recession")
        if macro_state.credit_state and macro_state.credit_state.direction == "contracting":
            tail.append("Credit event triggers systemic de-risking")
        if macro_state.liquidity_state and macro_state.liquidity_state.direction == "tightening":
            tail.append("Liquidity crisis — funding market stress")

        if not tail:
            tail = [
                "Geopolitical shock (tariffs, conflict escalation)",
                "Unexpected Fed hawkishness",
                "Tech sector concentration unwind",
            ]

        brief.risks_to_monitor = risks
        brief.tail_risks = tail

        # Key levels
        brief.key_levels = {
            "SPX": self._fmt_level(indicators, "SPX"),
            "VIX": self._fmt_level(indicators, "VIX"),
            "DXY": self._fmt_level(indicators, "DXY"),
            "Gold": self._fmt_level(indicators, "Gold"),
            "WTI": self._fmt_level(indicators, "WTI"),
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _divergence_resolution_impact(d: DivergenceSignal) -> str:
        """Describe the impact if a divergence resolves."""
        if d.pair == "stocks_vs_credit":
            return "broad equity repricing"
        elif d.pair == "usd_vs_gold":
            return "FX and commodity volatility"
        elif d.pair == "yields_vs_equities":
            return "duration-equity correlation shift"
        elif d.pair == "copper_vs_growth":
            return "cyclical sector rotation"
        return "cross-asset volatility"

    @staticmethod
    def _fmt_level(indicators: dict, name: str) -> str:
        """Format indicator value as key level."""
        val = indicators.get(name, {}).get("raw_value")
        if val is None:
            return "N/A"
        if isinstance(val, float):
            if val >= 1000:
                return f"{val:,.0f}"
            return f"{val:.1f}"
        return str(val)
