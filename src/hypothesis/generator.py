"""HypothesisGenerator — Transform signals into explanatory hypotheses.

Sprint 6 MVP: template-based, deterministic, rule-driven.
Generates structured HYPOTHESES (explanations), NOT signal aggregations.

Design (per Architecture Review):
    - Signal = observation ("what is happening").
    - Hypothesis = explanation ("why and what it means").
    - Dimension is metadata — hypotheses reason across dimensions.
    - Each hypothesis carries explicit assumptions.
    - Competing hypotheses are generated when signals are mixed.

Algorithm (MVP):
    1. Classify each signal as bearish, bullish, or neutral.
    2. Identify the DOMINANT NARRATIVE from cross-signal patterns.
    3. Generate an explanation statement via templates.
    4. Select assumptions from the narrative template.
    5. If signals are mixed, produce competing hypotheses (one bearish-leaning,
       one bullish-leaning).
"""

from src.schemas.hypothesis import HypothesisSchema
from src.schemas.signal import MacroSignalSchema, SignalDirection
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Narrative Templates ──────────────────────────────────────────────────

# Each narrative maps a signal pattern to an explanation + assumptions.
_NARRATIVES: dict[str, dict] = {
    "tightening": {
        "label": "Financial Conditions Tightening",
        "statement": (
            "Global financial conditions are tightening — "
            "{key_signals} collectively indicate a restrictive "
            "monetary and credit environment that constrains "
            "capital flows and risk-taking."
        ),
        "assumptions": [
            "Dollar strength reflects tighter global liquidity conditions, "
            "not isolated US economic outperformance",
            "Rising bond yields are driven by monetary restriction "
            "rather than growth-driven demand for capital",
            "Credit spread widening is a response to tightening conditions "
            "rather than idiosyncratic credit events",
        ],
        "direction": SignalDirection.BEARISH,
        "trigger": "bearish_majority",
    },
    "easing": {
        "label": "Monetary Conditions Easing",
        "statement": (
            "Monetary conditions are easing — "
            "{key_signals} suggest an accommodative "
            "environment supportive of risk assets and capital deployment."
        ),
        "assumptions": [
            "Dollar weakness represents genuine liquidity expansion "
            "rather than currency-specific dynamics",
            "Lower yields reflect accommodative policy stance " "rather than growth fears",
            "Credit market strength is sustainable and not a " "late-cycle compression",
        ],
        "direction": SignalDirection.BULLISH,
        "trigger": "bullish_majority",
    },
    "risk_off": {
        "label": "Risk Aversion Rising",
        "statement": (
            "Market risk appetite is contracting — "
            "{key_signals} indicate a flight-to-safety "
            "environment where investors are reducing exposure "
            "to risk assets."
        ),
        "assumptions": [
            "VIX elevation reflects genuine market fear, " "not transient volatility event",
            "Safe-haven demand (Gold) is driven by risk concerns " "rather than inflation hedging",
            "Credit stress is risk-driven rather than " "fundamental credit deterioration",
        ],
        "direction": SignalDirection.BEARISH,
        "trigger": "bearish_majority",
    },
    "risk_on": {
        "label": "Risk Appetite Expanding",
        "statement": (
            "Risk appetite is expanding across markets — "
            "{key_signals} reflect a constructive "
            "environment where capital is flowing into growth "
            "and risk-sensitive assets."
        ),
        "assumptions": [
            "Low volatility reflects genuine stability " "rather than complacency",
            "Industrial demand (Copper) strength represents "
            "real economic expansion, not speculative positioning",
            "Credit spread compression is sustainable and " "reflects fundamental health",
        ],
        "direction": SignalDirection.BULLISH,
        "trigger": "bullish_majority",
    },
    "divergence": {
        "label": "Cross-Market Divergence",
        "statement": (
            "Macro signals are diverging across dimensions — "
            "{bearish_side} while {bullish_side}, "
            "suggesting a transitional environment where "
            "traditional correlations are breaking down."
        ),
        "assumptions": [
            "Cross-asset divergence reflects a genuine regime transition "
            "rather than temporary noise",
            "Traditional macro relationships (DXY-EM, Rates-Equities) "
            "may not hold linearly in the current environment",
        ],
        "direction": SignalDirection.NEUTRAL,
        "trigger": "mixed",
    },
}


class HypothesisGenerator:
    """Generates explanatory hypotheses from macro signals.

    Responsibilities:
        - Analyze signal patterns to identify narratives.
        - Generate 1+ candidate hypotheses with explanation statements.
        - Produce explicit assumptions for each hypothesis.
        - Handle competing hypotheses when signals are mixed.

    Non-responsibilities:
        - Does NOT aggregate evidence (EvidenceAggregator).
        - Does NOT compute confidence (ConfidenceCalculator).
        - Does NOT access external systems.
        - Does NOT use LLM (MVP: template-based).
    """

    _DOMINANCE_THRESHOLD: float = 0.60

    def generate(self, signals: list[MacroSignalSchema]) -> list[HypothesisSchema]:
        """Generate hypotheses from a batch of macro signals.

        Args:
            signals: All current macro signals (any dimension).

        Returns:
            List of HypothesisSchema (1-2 in MVP). Empty if no signals.
        """
        if not signals:
            logger.debug("no_signals → empty_hypotheses")
            return []

        bearish = [s for s in signals if s.direction == SignalDirection.BEARISH]
        bullish = [s for s in signals if s.direction == SignalDirection.BULLISH]
        neutral = [s for s in signals if s.direction == SignalDirection.NEUTRAL]

        total = len(signals)
        bearish_ratio = len(bearish) / total if total > 0 else 0
        bullish_ratio = len(bullish) / total if total > 0 else 0

        logger.info(
            "generating_hypotheses total=%d bearish=%d bullish=%d neutral=%d "
            "bearish_ratio=%.2f bullish_ratio=%.2f",
            total,
            len(bearish),
            len(bullish),
            len(neutral),
            bearish_ratio,
            bullish_ratio,
        )

        hypotheses: list[HypothesisSchema] = []

        if bearish_ratio >= self._DOMINANCE_THRESHOLD:
            # Single bearish narrative
            narrative = self._select_narrative("bearish_majority", signals)
            hypotheses.append(
                self._build_hypothesis(
                    all_signals=signals,
                    bearish=bearish,
                    bullish=bullish,
                    narrative=narrative,
                )
            )
        elif bullish_ratio >= self._DOMINANCE_THRESHOLD:
            # Single bullish narrative
            narrative = self._select_narrative("bullish_majority", signals)
            hypotheses.append(
                self._build_hypothesis(
                    all_signals=signals,
                    bearish=bearish,
                    bullish=bullish,
                    narrative=narrative,
                )
            )
        else:
            # Mixed signals → generate competing hypotheses
            bearish_narrative = self._select_narrative("bearish_majority", signals)
            bullish_narrative = self._select_narrative("bullish_majority", signals)

            # Bearish-leaning hypothesis
            hypotheses.append(
                self._build_hypothesis(
                    all_signals=signals,
                    bearish=bearish,
                    bullish=bullish,
                    narrative=bearish_narrative,
                )
            )
            # Bullish-leaning hypothesis
            hypotheses.append(
                self._build_hypothesis(
                    all_signals=signals,
                    bearish=bearish,
                    bullish=bullish,
                    narrative=bullish_narrative,
                )
            )

            # If divergence narrative exists, add a third neutral hypothesis
            div_narrative = _NARRATIVES.get("divergence", {})
            if div_narrative:
                hypotheses.append(
                    self._build_hypothesis(
                        all_signals=signals,
                        bearish=bearish,
                        bullish=bullish,
                        narrative=div_narrative,
                    )
                )

        return hypotheses

    # ── Private: Hypothesis Construction ──────────────────────────────

    def _build_hypothesis(
        self,
        all_signals: list[MacroSignalSchema],
        bearish: list[MacroSignalSchema],
        bullish: list[MacroSignalSchema],
        narrative: dict,
    ) -> HypothesisSchema:
        """Construct a HypothesisSchema from a narrative template and signals."""

        # Format the key_signals placeholder from top signals
        key_signals_str = self._format_key_signals(all_signals)

        # Format the statement
        statement = narrative["statement"].format(
            key_signals=key_signals_str,
            bearish_side=self._format_side(bearish, "bearish"),
            bullish_side=self._format_side(bullish, "bullish"),
        )

        # Select assumptions
        assumptions = list(narrative.get("assumptions", []))

        # Determine primary dimension from majority
        dimensions = set(s.dimension for s in all_signals)
        primary_dimension = self._primary_dimension(all_signals)

        # Select 2-3 relevant assumptions based on actual dimensions present
        filtered_assumptions = self._filter_assumptions(assumptions, dimensions)

        return HypothesisSchema(
            statement=statement,
            dimension=primary_dimension,
            direction=narrative["direction"],
            assumptions=filtered_assumptions,
        )

    # ── Private: Narrative Selection ──────────────────────────────────

    def _select_narrative(self, trigger: str, signals: list[MacroSignalSchema]) -> dict:
        """Select the best narrative for a given trigger pattern.

        Priority order:
            1. Tightening/easing (if Liquidity + Credit signals present)
            2. Risk_on/risk_off (if Risk_Appetite signals present)
            3. Growth narratives (if Growth signals present)
            4. Fallback to generic
        """
        dimensions = {s.dimension for s in signals}

        has_liquidity = "Liquidity" in dimensions
        has_credit = "Credit" in dimensions
        has_risk = "Risk_Appetite" in dimensions
        has_growth = "Growth" in dimensions

        if trigger == "bearish_majority":
            if has_liquidity and has_credit:
                return _NARRATIVES["tightening"]
            if has_risk:
                return _NARRATIVES["risk_off"]
            return _NARRATIVES.get("tightening", _NARRATIVES["divergence"])

        if trigger == "bullish_majority":
            if has_liquidity:
                return _NARRATIVES["easing"]
            if has_risk or has_growth:
                return _NARRATIVES["risk_on"]
            return _NARRATIVES.get("easing", _NARRATIVES["divergence"])

        return _NARRATIVES.get("divergence", _NARRATIVES["tightening"])

    # ── Private: Formatting Helpers ───────────────────────────────────

    @staticmethod
    def _format_key_signals(signals: list[MacroSignalSchema]) -> str:
        """Create a human-readable summary of key signals.

        Example: "DXY rising, US10Y elevated, HYG under stress"
        """
        if not signals:
            return "no significant signals"

        parts: list[str] = []
        for s in signals[:5]:  # Top 5 for readability
            d = s.direction.value
            if d == "bearish":
                verb_map = {
                    "DXY": "rising",
                    "US10Y": "elevated",
                    "US2Y": "elevated",
                    "HYG": "under stress",
                    "^VIX": "elevated",
                    "GC=F": "surging",
                    "HG=F": "falling",
                }
                verb = verb_map.get(s.indicator, "deteriorating")
            elif d == "bullish":
                verb_map = {
                    "DXY": "weakening",
                    "US10Y": "declining",
                    "US2Y": "declining",
                    "HYG": "strengthening",
                    "^VIX": "subdued",
                    "GC=F": "declining",
                    "HG=F": "rising",
                }
                verb = verb_map.get(s.indicator, "improving")
            else:
                verb = "stable"
            parts.append(f"{s.indicator} {verb}")

        return ", ".join(parts)

    @staticmethod
    def _format_side(signals: list[MacroSignalSchema], label: str) -> str:
        """Format one side of a divergence statement.

        Example: "Liquidity indicators (DXY, US10Y) are tightening"
        """
        if not signals:
            return f"no {label} signals present"

        dimensions = sorted(set(s.dimension for s in signals))
        indicators = [s.indicator for s in signals[:4]]
        indicator_str = ", ".join(indicators)
        dim_str = ", ".join(dimensions)

        if label == "bearish":
            return f"{dim_str} indicators ({indicator_str}) show stress or contraction"
        return f"{dim_str} indicators ({indicator_str}) show strength or expansion"

    @staticmethod
    def _primary_dimension(signals: list[MacroSignalSchema]) -> str:
        """Determine the primary dimension from signal distribution.

        Returns the most frequently occurring dimension.
        """
        if not signals:
            return "Macro"
        from collections import Counter

        counter = Counter(s.dimension for s in signals)
        return counter.most_common(1)[0][0]

    @staticmethod
    def _filter_assumptions(assumptions: list[str], dimensions: set[str]) -> list[str]:
        """Filter assumptions to only those relevant to the present dimensions.

        Removes assumptions about dimensions with no signals.
        """
        relevant: list[str] = []
        for a in assumptions:
            lower = a.lower()
            # Check which dimensions this assumption references
            refs_dollar = any(w in lower for w in ["dollar", "dxy", "currency"])
            refs_rates = any(w in lower for w in ["yield", "rate", "bond"])
            refs_credit = any(w in lower for w in ["credit", "spread", "hyg"])
            refs_risk = any(w in lower for w in ["vix", "volatility", "fear", "safe-haven"])
            refs_growth = any(w in lower for w in ["growth", "industrial", "copper", "demand"])

            keep = False
            if refs_dollar and "Liquidity" in dimensions:
                keep = True
            if refs_rates and "Liquidity" in dimensions:
                keep = True
            if refs_credit and "Credit" in dimensions:
                keep = True
            if refs_risk and "Risk_Appetite" in dimensions:
                keep = True
            if refs_growth and "Growth" in dimensions:
                keep = True
            if not (refs_dollar or refs_rates or refs_credit or refs_risk or refs_growth):
                keep = True  # Generic assumption, always include

            if keep:
                relevant.append(a)

        # Ensure at least 2 assumptions remain
        if len(relevant) < 2:
            return assumptions[:2]

        return relevant
