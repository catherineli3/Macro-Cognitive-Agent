"""Phase 3: NarrativeGenerator — Dominant Narrative from State + Change Signals.

Takes MacroState + ChangeSignals and produces a structured MacroNarrative:
    - dominant_narrative: the primary macro story
    - supporting_evidence: data backing the narrative
    - contradicting_evidence: data going against it
    - key_uncertainty: what market participants should watch

Reuses: EvidenceSynthesizer (theme clustering) + NarrativeAnalyzer (narrative ranking).
Pure deterministic rules — no LLM required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.shared.logging import get_logger
from src.summary_engine.change_detector import ChangeSignals
from src.summary_engine.macro_state_layer import MacroState

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class MacroNarrative:
    """Structured macro narrative from state + change analysis.

    This is the output of Phase 3, consumed by Phase 4 (CIOBrief).
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Core narrative
    dominant_narrative: str = ""  # One-line macro story
    narrative_theme: str = ""  # "reflation", "stagflation", "goldilocks", etc.
    narrative_strength: float = 0.0  # 0-1 how strong the narrative conviction

    # Evidence
    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)
    evidence_balance: float = 0.5  # 0 = heavily against, 1 = heavily for

    # Uncertainty
    key_uncertainty: str = ""
    uncertainty_level: str = "moderate"  # "low", "moderate", "high", "extreme"

    # Landscape assessment
    is_consensus_narrative: bool = False
    narrative_competition: list[str] = field(default_factory=list)  # Competing narratives
    narrative_tension: str = ""  # Description of narrative conflict

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "dominant_narrative": self.dominant_narrative,
            "narrative_theme": self.narrative_theme,
            "narrative_strength": round(self.narrative_strength, 2),
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "evidence_balance": round(self.evidence_balance, 2),
            "key_uncertainty": self.key_uncertainty,
            "uncertainty_level": self.uncertainty_level,
            "is_consensus_narrative": self.is_consensus_narrative,
            "narrative_competition": self.narrative_competition,
            "narrative_tension": self.narrative_tension,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# NarrativeGenerator
# ═══════════════════════════════════════════════════════════════════════════════

# ── Narrative Themes (Macro Regime Taxonomies) ──────────────────────────────
NARRATIVE_THEMES = {
    "reflation": {
        "conditions": ["growth expanding", "inflation rising", "risk risk_on"],
        "story": "Growth accelerating with rising inflation expectations — cyclical assets outperform",
        "uncertainty": "Is inflation sticky or transitory? Will the Fed overtighten?",
        "competing": "soft_landing",
        "assets": "cyclicals, commodities, value over growth",
    },
    "soft_landing": {
        "conditions": ["growth moderating", "inflation cooling", "liquidity easing"],
        "story": "Fed navigates inflation down without recession — Goldilocks scenario",
        "uncertainty": "Can the Fed stick the landing? Is growth slowing too much?",
        "competing": "hard_landing",
        "assets": "balanced portfolio, quality factor, duration exposure",
    },
    "hard_landing": {
        "conditions": ["growth contracting", "inflation cooling", "credit contracting"],
        "story": "Growth deterioration accelerating — recession risk rising rapidly",
        "uncertainty": "How deep will the recession be? Can policy respond in time?",
        "competing": "soft_landing",
        "assets": "defensives, long duration, safe havens, shorts",
    },
    "stagflation": {
        "conditions": ["growth contracting", "inflation rising", "risk risk_off"],
        "story": "Stagflationary environment — growth falling but inflation sticky",
        "uncertainty": "Is the inflation supply-side or demand-driven? Will growth stabilize?",
        "competing": "reflation",
        "assets": "commodities, gold, TIPS, defensive equities",
    },
    "liquidity_rally": {
        "conditions": ["liquidity easing", "risk risk_on", "credit expanding"],
        "story": "Abundant liquidity driving risk assets higher — financial conditions easing",
        "uncertainty": "Is this a liquidity mirage? Will fundamentals catch up?",
        "competing": "reflation",
        "assets": "growth stocks, high beta, EM, crypto proxies",
    },
    "risk_rout": {
        "conditions": ["risk risk_off", "credit contracting", "liquidity tightening"],
        "story": "Broad risk-off environment — capital seeking safety, volatility elevated",
        "uncertainty": "Is this a temporary correction or the start of a bear market?",
        "competing": "hard_landing",
        "assets": "long vol, cash, safe havens, short risk assets",
    },
    "dovish_pivot": {
        "conditions": ["inflation cooling", "liquidity easing", "growth moderating"],
        "story": "Fed signals policy easing — pivot narrative driving duration bid",
        "uncertainty": "Will the Fed pivot fast enough? Is inflation truly under control?",
        "competing": "hawkish_surprise",
        "assets": "duration long, gold, rate-sensitive sectors, homebuilders",
    },
    "mixed_signals": {
        "conditions": [],
        "story": "Conflicting macro signals — no clear directional conviction",
        "uncertainty": "Which signal will resolve first? Are we at an inflection point?",
        "competing": "",
        "assets": "neutral positioning, wait for clarity, optionality strategies",
    },
}


class NarrativeGenerator:
    """Generate structured macro narrative from state and change signals.

    Reuses:
        - EvidenceSynthesizer theme clustering patterns
        - NarrativeAnalyzer narrative ranking logic
    """

    def __init__(self) -> None:
        self._themes = NARRATIVE_THEMES

    def generate(
        self,
        macro_state: MacroState,
        change_signals: ChangeSignals,
    ) -> MacroNarrative:
        """Generate complete macro narrative.

        Args:
            macro_state: 5-dim MacroState from Phase 1
            change_signals: ChangeSignals from Phase 2
        """
        narrative = MacroNarrative()

        # Step 1: Identify narrative theme
        theme = self._match_narrative_theme(macro_state, change_signals)
        narrative.narrative_theme = theme

        # Step 2: Build dominant narrative statement
        narrative.dominant_narrative = self._build_dominant_narrative(
            theme, macro_state, change_signals
        )

        # Step 3: Gather supporting evidence
        narrative.supporting_evidence = self._gather_supporting_evidence(
            theme, macro_state, change_signals
        )

        # Step 4: Gather contradicting evidence
        narrative.contradicting_evidence = self._gather_contradicting_evidence(
            macro_state, change_signals
        )

        # Step 5: Assess evidence balance
        narrative.evidence_balance = self._compute_evidence_balance(narrative)

        # Step 6: Identify key uncertainty
        narrative.key_uncertainty = self._identify_key_uncertainty(
            theme, macro_state, change_signals
        )

        # Step 7: Uncertainty level
        narrative.uncertainty_level = self._assess_uncertainty(macro_state, change_signals)

        # Step 8: Narrative strength
        narrative.narrative_strength = self._compute_narrative_strength(narrative, macro_state)

        # Step 9: Consensus check
        narrative.is_consensus_narrative = self._check_consensus(theme, macro_state, change_signals)

        # Step 10: Competing narratives
        narrative.narrative_competition = self._identify_competing_narratives(theme, macro_state)

        # Step 11: Narrative tension
        narrative.narrative_tension = self._describe_tension(narrative, macro_state)

        logger.info(
            "narrative_generator_done | theme=%s strength=%.2f balance=%.2f uncertainty=%s",
            narrative.narrative_theme,
            narrative.narrative_strength,
            narrative.evidence_balance,
            narrative.uncertainty_level,
        )
        return narrative

    # ── Theme Matching ───────────────────────────────────────────────────────

    def _match_narrative_theme(
        self,
        macro_state: MacroState,
        change_signals: ChangeSignals,
    ) -> str:
        """Match current state to a narrative theme."""
        conditions = self._derive_conditions(macro_state, change_signals)

        best_theme = "mixed_signals"
        best_score = 0

        for theme_name, theme_config in self._themes.items():
            if not theme_config["conditions"]:
                continue

            matches = 0
            for cond in theme_config["conditions"]:
                if cond in conditions:
                    matches += 1

            score = matches / len(theme_config["conditions"])
            if score > best_score:
                best_score = score
                best_theme = theme_name

        # Require at least 50% match
        if best_score < 0.5:
            return "mixed_signals"

        return best_theme

    def _derive_conditions(
        self,
        macro_state: MacroState,
        change_signals: ChangeSignals,
    ) -> list[str]:
        """Derive conditions list from current state."""
        conds = []

        # Growth condition
        gs = macro_state.growth_state
        if gs:
            if gs.direction in ("expanding", "accelerating"):
                conds.append("growth expanding")
            elif gs.direction in ("contracting", "decelerating"):
                conds.append("growth contracting")
            elif gs.direction == "moderating":
                conds.append("growth moderating")

        # Inflation condition
        inf = macro_state.inflation_state
        if inf:
            if inf.direction in ("rising", "accelerating"):
                conds.append("inflation rising")
            elif inf.direction in ("cooling", "decelerating"):
                conds.append("inflation cooling")

        # Liquidity condition
        liq = macro_state.liquidity_state
        if liq:
            if liq.direction == "easing":
                conds.append("liquidity easing")
            elif liq.direction == "tightening":
                conds.append("liquidity tightening")

        # Credit condition
        cr = macro_state.credit_state
        if cr:
            if cr.direction == "expanding":
                conds.append("credit expanding")
            elif cr.direction == "contracting":
                conds.append("credit contracting")

        # Risk condition
        risk = macro_state.risk_state
        if risk:
            if risk.direction == "risk_on":
                conds.append("risk risk_on")
            elif risk.direction == "risk_off":
                conds.append("risk risk_off")

        return conds

    # ── Narrative Construction ───────────────────────────────────────────────

    def _build_dominant_narrative(
        self,
        theme: str,
        macro_state: MacroState,
        change_signals: ChangeSignals,
    ) -> str:
        """Build one-line dominant narrative from theme + current data."""
        theme_config = self._themes.get(theme, self._themes["mixed_signals"])
        base = theme_config["story"]

        # Add data-driven specificity
        specifics = []

        if macro_state.growth_state:
            specifics.append(f"growth {macro_state.growth_state.direction}")
        if macro_state.inflation_state:
            specifics.append(f"inflation {macro_state.inflation_state.direction}")
        if macro_state.liquidity_state and macro_state.liquidity_state.direction != "neutral":
            specifics.append(f"liquidity {macro_state.liquidity_state.direction}")

        # Include divergence signals
        divergences = [d for d in change_signals.divergence_signals if d.is_diverging]
        if divergences:
            specifics.append(f"{len(divergences)} key divergence(s) detected")

        if specifics:
            return f"{base}. Current: {', '.join(specifics)}."
        return base

    # ── Evidence Gathering ───────────────────────────────────────────────────

    def _gather_supporting_evidence(
        self,
        theme: str,
        macro_state: MacroState,
        change_signals: ChangeSignals,
    ) -> list[str]:
        """Gather evidence that supports the dominant narrative."""
        evidence = []

        # State-aligned evidence
        for name, state in [
            ("Growth", macro_state.growth_state),
            ("Inflation", macro_state.inflation_state),
            ("Liquidity", macro_state.liquidity_state),
            ("Credit", macro_state.credit_state),
            ("Risk", macro_state.risk_state),
        ]:
            if state and state.confidence > 0.4:
                for driver in state.key_indicators[:2]:
                    if driver in state.indicator_values:
                        val = state.indicator_values[driver]
                        evidence.append(f"{name}: {state.direction} — {driver} @ {self._fmt(val)}")

        # Strongest momentum signals
        for m in change_signals.momentum_signals[:3]:
            if abs(m.score) > 0.2:
                evidence.append(f"Momentum: {m.indicator} {m.strength} (score {m.score:+.1f})")

        # Convergence confirmations
        for d in change_signals.divergence_signals:
            if not d.is_diverging and d.significance > 0.2:
                evidence.append(f"Convergence: {d.asset_a} & {d.asset_b} — {d.interpretation}")

        return evidence

    def _gather_contradicting_evidence(
        self,
        macro_state: MacroState,
        change_signals: ChangeSignals,
    ) -> list[str]:
        """Gather evidence that contradicts or challenges the narrative."""
        evidence = []

        # Divergences are inherently contradicting signals
        for d in change_signals.divergence_signals:
            if d.is_diverging:
                evidence.append(
                    f"Divergence: {d.asset_a} ({d.direction_a}) vs {d.asset_b} ({d.direction_b}) — {d.interpretation}"
                )

        # States with low confidence
        for name, state in [
            ("Growth", macro_state.growth_state),
            ("Inflation", macro_state.inflation_state),
            ("Liquidity", macro_state.liquidity_state),
        ]:
            if state and state.confidence < 0.5:
                evidence.append(f"Low-confidence read on {name} (conf={state.confidence:.0%})")

        # Regime change signals
        if change_signals.regime_change and change_signals.regime_change.has_shifted:
            evidence.append(f"Regime shift: {change_signals.regime_change.summary}")

        return evidence

    # ── Uncertainty Assessment ───────────────────────────────────────────────

    def _identify_key_uncertainty(
        self,
        theme: str,
        macro_state: MacroState,
        change_signals: ChangeSignals,
    ) -> str:
        """Identify the single most important uncertainty."""
        theme_config = self._themes.get(theme, self._themes["mixed_signals"])
        base_uncertainty = theme_config["uncertainty"]

        # Check if a divergence creates specific uncertainty
        divergences = [d for d in change_signals.divergence_signals if d.is_diverging]
        if divergences:
            top_div = sorted(divergences, key=lambda d: d.significance, reverse=True)[0]
            return f"{base_uncertainty} Key cross-current: {top_div.asset_a} vs {top_div.asset_b} divergence needs resolution."

        # Check for regime change uncertainty
        if change_signals.regime_change and change_signals.regime_change.has_shifted:
            return f"{base_uncertainty} Regime in transition — previous drivers may not apply."

        return base_uncertainty

    def _assess_uncertainty(
        self,
        macro_state: MacroState,
        change_signals: ChangeSignals,
    ) -> str:
        """Assess uncertainty level."""
        factors = 0

        # Low-confidence states
        low_conf_states = sum(
            1
            for s in [
                macro_state.growth_state,
                macro_state.inflation_state,
                macro_state.liquidity_state,
                macro_state.credit_state,
                macro_state.risk_state,
            ]
            if s and s.confidence < 0.5
        )
        factors += low_conf_states

        # Divergences
        div_count = sum(1 for d in change_signals.divergence_signals if d.is_diverging)
        factors += div_count * 2

        # Regime change
        if change_signals.regime_change and change_signals.regime_change.has_shifted:
            factors += 3

        # Acceleration signals add uncertainty
        factors += len(change_signals.acceleration_signals) // 2

        if factors >= 6:
            return "extreme"
        elif factors >= 4:
            return "high"
        elif factors >= 2:
            return "moderate"
        else:
            return "low"

    # ── Narrative Quality ────────────────────────────────────────────────────

    def _compute_narrative_strength(
        self,
        narrative: MacroNarrative,
        macro_state: MacroState,
    ) -> float:
        """Compute 0-1 narrative strength score."""
        strength = 0.5

        # Evidence balance
        if narrative.evidence_balance > 0.7:
            strength += 0.2
        elif narrative.evidence_balance < 0.3:
            strength -= 0.2

        # State confidence
        confidences = [
            s.confidence
            for s in [
                macro_state.growth_state,
                macro_state.inflation_state,
                macro_state.liquidity_state,
                macro_state.credit_state,
                macro_state.risk_state,
            ]
            if s
        ]
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            strength = strength * 0.5 + avg_conf * 0.5

        # Supporting evidence count
        if len(narrative.supporting_evidence) >= 4:
            strength = min(1.0, strength + 0.1)

        return max(0.0, min(1.0, strength))

    def _compute_evidence_balance(self, narrative: MacroNarrative) -> float:
        """Compute evidence balance: 0 = all against, 1 = all for."""
        s_count = len(narrative.supporting_evidence)
        c_count = len(narrative.contradicting_evidence)

        if s_count + c_count == 0:
            return 0.5

        # Supporting evidence weighted slightly higher
        return (s_count * 1.2) / (s_count * 1.2 + c_count)

    def _check_consensus(
        self,
        theme: str,
        macro_state: MacroState,
        change_signals: ChangeSignals,
    ) -> bool:
        """Check if this narrative is likely consensus in the market."""
        # Consensus themes tend to be well-supported with few divergences
        div_count = sum(1 for d in change_signals.divergence_signals if d.is_diverging)

        if div_count >= 2:
            return False  # Too many conflicts → not consensus

        # Check alignment
        directions = [
            s.direction
            for s in [
                macro_state.growth_state,
                macro_state.inflation_state,
                macro_state.liquidity_state,
            ]
            if s
        ]

        # If all directions are same type (all "positive" or all "negative"), more consensus-like
        positive = sum(1 for d in directions if d in ("expanding", "cooling", "easing", "risk_on"))
        negative = sum(
            1 for d in directions if d in ("contracting", "rising", "tightening", "risk_off")
        )

        max_align = max(positive, negative)
        return max_align >= len(directions) * 0.75

    def _identify_competing_narratives(
        self,
        theme: str,
        macro_state: MacroState,
    ) -> list[str]:
        """Identify competing narrative themes."""
        theme_config = self._themes.get(theme, {})
        competing_key = theme_config.get("competing", "")

        if not competing_key or competing_key not in self._themes:
            # Find closest competing theme by condition overlap
            conditions = self._derive_conditions(macro_state, ChangeSignals())
            alternatives = []

            for t_name, t_config in self._themes.items():
                if t_name == theme or t_name == "mixed_signals":
                    continue
                if not t_config.get("conditions"):
                    continue
                matches = sum(1 for c in t_config["conditions"] if c in conditions)
                if matches > 0:
                    alternatives.append((t_name, matches))

            alternatives.sort(key=lambda x: x[1], reverse=True)
            return [a[0] for a in alternatives[:2]]

        comp_config = self._themes[competing_key]
        return [f"{competing_key}: {comp_config['story']}"]

    def _describe_tension(
        self,
        narrative: MacroNarrative,
        macro_state: MacroState,
    ) -> str:
        """Describe the narrative tension / conflict."""
        s_count = len(narrative.supporting_evidence)
        c_count = len(narrative.contradicting_evidence)

        if c_count == 0:
            return "Clear directional signal with no contradicting evidence — high conviction environment"
        elif c_count >= s_count:
            return "Narrative under serious challenge — contradictory evidence matches or exceeds supporting data"
        elif c_count >= s_count * 0.5:
            return "Narrative has moderate opposition — watch contradicting signals for potential regime shift"
        else:
            return "Minor counter-signals — narrative remains dominant but not undisputed"

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt(val: float) -> str:
        """Format a value for display."""
        if abs(val) >= 1e12:
            return f"${val/1e12:.1f}T"
        if abs(val) >= 1000:
            return f"{val:,.0f}"
        if abs(val) >= 100:
            return f"{val:.1f}"
        return f"{val:.2f}"
