"""V5.2 Stage 3: Pattern — Identify macro patterns and regime signals.

The difference between novice and expert researchers:
    Novices see data points.
    Experts see patterns.

This stage identifies:
    - Which macro regime are we in?
    - Are there regime transition signals?
    - What patterns are absent (equally important)?
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.research.reasoning_pipeline.schemas import (
    ObservationOutput,
    EvidenceOutput,
    PatternOutput,
    StageStatus,
)


class PatternStage:
    """Stage 3: Pattern recognition and regime diagnosis."""

    MACRO_REGIMES = [
        "goldilocks",           # Strong growth, low inflation
        "reflation",            # Rising growth, rising inflation
        "stagflation",          # Weak growth, high inflation
        "deflation_bust",       # Weak growth, falling prices
        "overheating",          # Very strong growth, high inflation
        "secular_stagnation",   # Persistently weak growth, low inflation
        "disinflationary_boom", # Strong growth, falling inflation
        "liquidity_trap",       # Low rates, low growth, low inflation
        "credit_expansion",     # Rising credit, rising asset prices
        "credit_contraction",   # Falling credit, falling asset prices
        "dollar_squeeze",       # Strong dollar, EM stress
        "risk_on",              # Broad risk appetite
        "risk_off",             # Broad risk aversion
    ]

    REGIME_SIGNALS: dict[str, list[str]] = {
        "goldilocks": ["above-trend growth + below-target inflation", "PMI > 52 + CPI < 3%"],
        "reflation": ["rising breakevens", "commodity rally", "yield curve steepening"],
        "stagflation": ["rising CPI + falling PMI", "yield curve inversion", "consumer confidence weak"],
        "overheating": ["CPI > 4%", "wage growth > 5%", "capacity utilization > 80%"],
        "secular_stagnation": ["secular low yields", "persistent output gap", "demographic headwinds"],
        "disinflationary_boom": ["technology-driven productivity", "supply-side expansion"],
        "credit_expansion": ["narrowing spreads", "rising loan growth", "easy lending standards"],
        "credit_contraction": ["widening spreads", "falling loan growth", "tightening lending standards"],
        "risk_on": ["VIX < 15", "EM flows positive", "credit spreads tight"],
        "risk_off": ["VIX > 25", "EM outflows", "credit spreads wide"],
    }

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def execute(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
        regime_data: dict | None = None,
    ) -> PatternOutput:
        """Execute pattern recognition.

        Args:
            observation: Stage 1 output
            evidence: Stage 2 output
            regime_data: Existing regime analysis from V4 regime engine

        Returns:
            PatternOutput with identified patterns and regime
        """
        output = PatternOutput(
            timestamp=datetime.now().isoformat(),
            status=StageStatus.IN_PROGRESS,
        )

        # 1. Identify patterns from evidence clusters
        output.patterns = self._identify_patterns(evidence)

        # 2. Diagnose current regime
        output.regime_diagnosis = self._diagnose_regime(observation, evidence, regime_data)

        # 3. Check for regime transition signals
        output.regime_transition_signals = self._check_transition(observation, evidence)

        # 4. Identify absent patterns
        output.absent_patterns = self._identify_absent(output.patterns)

        # 5. Calibrate confidence
        output.pattern_confidence = self._calibrate_confidence(output, evidence)

        # 6. Generate trace
        output.reasoning_trace = self._generate_trace(output)
        output.status = StageStatus.COMPLETED

        return output

    # ── Pattern Identification ──────────────────────────────────────

    def _identify_patterns(self, evidence: EvidenceOutput) -> list[str]:
        """Identify patterns from evidence clusters."""
        patterns = []

        clusters = evidence.evidence_clusters

        # Growth + Inflation combinations
        growth_evidence = clusters.get("growth", [])
        inflation_evidence = clusters.get("inflation", [])

        growth_strong = any(
            kw in " ".join(growth_evidence).lower()
            for kw in ["strong", "above", "beat", "expansion", "growth"]
        )
        growth_weak = any(
            kw in " ".join(growth_evidence).lower()
            for kw in ["weak", "below", "contraction", "recession", "slowdown"]
        )
        inflation_high = any(
            kw in " ".join(inflation_evidence).lower()
            for kw in ["high", "above", "surge", "hot", "elevated"]
        )
        inflation_low = any(
            kw in " ".join(inflation_evidence).lower()
            for kw in ["low", "below", "deflation", "moderate", "cooling"]
        )

        if growth_strong and inflation_low:
            patterns.append("goldilocks / disinflationary boom")
        elif growth_strong and inflation_high:
            patterns.append("overheating / reflation")
        elif growth_weak and inflation_high:
            patterns.append("stagflation risk")
        elif growth_weak and inflation_low:
            patterns.append("disinflationary slowdown / potential recession")

        # Credit conditions
        credit_evidence = clusters.get("credit_markets", []) + clusters.get("financial_conditions", [])
        credit_tight = any(
            kw in " ".join(credit_evidence).lower()
            for kw in ["tight", "wider", "stress", "contraction"]
        )
        credit_easy = any(
            kw in " ".join(credit_evidence).lower()
            for kw in ["easy", "narrow", "accommodative", "expansion"]
        )

        if credit_tight:
            patterns.append("credit contraction / tightening financial conditions")
        elif credit_easy:
            patterns.append("credit expansion / loose financial conditions")

        # Risk appetite
        sentiment_evidence = clusters.get("sentiment", [])
        risk_on = any(
            kw in " ".join(sentiment_evidence).lower()
            for kw in ["bullish", "risk on", "appetite", "low vol"]
        )
        risk_off = any(
            kw in " ".join(sentiment_evidence).lower()
            for kw in ["bearish", "risk off", "aversion", "fear", "high vol"]
        )

        if risk_on:
            patterns.append("risk-on sentiment")
        elif risk_off:
            patterns.append("risk-off sentiment")

        # Monetary policy direction
        policy_evidence = clusters.get("monetary_policy", [])
        hawkish = any(
            kw in " ".join(policy_evidence).lower()
            for kw in ["hawkish", "tightening", "hike", "hawk"]
        )
        dovish = any(
            kw in " ".join(policy_evidence).lower()
            for kw in ["dovish", "easing", "cut", "dove", "pivot"]
        )

        if hawkish:
            patterns.append("hawkish monetary policy stance")
        elif dovish:
            patterns.append("dovish monetary policy stance")

        return patterns

    def _diagnose_regime(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
        regime_data: dict | None,
    ) -> str:
        """Diagnose the current macro regime."""
        # If existing regime data available, use it
        if regime_data and "current_regime" in regime_data:
            return str(regime_data["current_regime"])

        # Otherwise, construct from evidence
        net_weight = evidence.net_weight
        patterns = self._identify_patterns(evidence)

        if patterns:
            dominant = patterns[0]
            direction = "supporting" if net_weight > 0 else "challenging"
            return f"{dominant} regime ({direction} evidence, net weight: {net_weight:+.2f})"

        return "regime unclear — insufficient evidence"

    def _check_transition(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
    ) -> list[str]:
        """Check for regime transition signals."""
        signals = []

        # Divergence between data types
        clusters = evidence.evidence_clusters

        # Growth vs labor divergence
        growth_items = clusters.get("growth", [])
        labor_items = clusters.get("labor_market", [])
        if growth_items and labor_items:
            growth_weak = any(
                kw in " ".join(growth_items).lower()
                for kw in ["weak", "slow", "below"]
            )
            labor_strong = any(
                kw in " ".join(labor_items).lower()
                for kw in ["strong", "tight", "low unemployment"]
            )
            if growth_weak and labor_strong:
                signals.append("Growth-labor divergence: weak growth + tight labor → potential stagflation transition")

        # Yield curve signal
        market_moves = " ".join(observation.market_moves).lower()
        if "yield curve" in market_moves or "2s10s" in market_moves:
            if "invert" in market_moves or "flatten" in market_moves:
                signals.append("Yield curve flattening/inversion → recession signal")
            elif "steepen" in market_moves or "dis-invert" in market_moves:
                signals.append("Yield curve steepening/dis-inversion → recovery or inflation signal")

        # Credit stress signals
        credit_items = clusters.get("credit_markets", [])
        if any("widen" in item.lower() for item in credit_items):
            signals.append("Credit spreads widening → tightening financial conditions → potential regime shift")

        return signals

    def _identify_absent(self, found_patterns: list[str]) -> list[str]:
        """Identify important patterns that are NOT present."""
        absent = []
        all_regime_keywords = [
            "goldilocks", "reflation", "stagflation", "overheating",
            "recession", "credit crisis", "currency crisis",
            "disinflation", "deflation", "boom",
        ]

        found_text = " ".join(found_patterns).lower()
        for kw in all_regime_keywords:
            if kw not in found_text:
                absent.append(f"No evidence of {kw} scenario")

        return absent[:5]

    def _calibrate_confidence(
        self,
        output: PatternOutput,
        evidence: EvidenceOutput,
    ) -> float:
        """Calibrate pattern confidence based on evidence strength."""
        if not output.patterns:
            return 0.0

        # More patterns = lower confidence per pattern
        # Stronger evidence = higher confidence
        num_patterns = len(output.patterns)
        base_confidence = 0.7

        # Adjust for number of patterns (too many = less confident in any one)
        if num_patterns > 5:
            base_confidence -= 0.2
        elif num_patterns > 3:
            base_confidence -= 0.1

        # Adjust for evidence net weight
        abs_weight = abs(evidence.net_weight)
        base_confidence += abs_weight * 0.3

        return min(max(base_confidence, 0.1), 0.95)

    def _generate_trace(self, output: PatternOutput) -> str:
        """Generate reasoning trace."""
        trace = []
        trace.append("=== Stage 3: Pattern Recognition ===")
        trace.append(f"Patterns identified: {output.patterns}")
        trace.append(f"Regime: {output.regime_diagnosis}")
        trace.append(f"Transition signals: {output.regime_transition_signals}")
        trace.append(f"Confidence: {output.pattern_confidence:.2f}")
        return "\n".join(trace)
