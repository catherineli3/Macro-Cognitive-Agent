"""Composite Signal Generator — v2.0 cross-indicator reasoning.

Combines individual macro signals into composite signals and macro themes.

Logic:
    - Signals in the same dimension with aligned direction → CompositeSignal
    - Cross-dimension signal patterns → MacroTheme
    - E.g., DXY↑ + US10Y↑ + HYG↓ → "Liquidity Tightening"

Design (DDR-v2):
    - Deterministic rule-based combination (no LLM in v2.0).
    - Each composite explains WHY the combination matters.
    - MacroThemes identify the dominant regime.
"""

from __future__ import annotations

from src.schemas.signal import (
    CompositeSignal,
    CompositeSignalSnapshot,
    MacroSignalSchema,
    MacroTheme,
    SignalDirection,
    SignalSnapshot,
    SignalStrength,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)

# ── Macro Theme Definitions ──────────────────────────────────────────────────

_THEME_DEFINITIONS: list[dict] = [
    {
        "name": "Liquidity Tightening",
        "conditions": {
            "liquidity": "bullish",  # DXY↑, US10Y↑ → tightening
            "credit": "bearish",  # HYG↓
        },
        "confidence_boost": 0.85,
        "summary": "Dollar strength and rising rates are tightening global liquidity. "
        "Credit markets are showing stress — risk assets face headwinds.",
        "implications": "Defensive positioning. Reduce EM exposure. Watch funding markets.",
    },
    {
        "name": "Liquidity Easing",
        "conditions": {
            "liquidity": "bearish",  # DXY↓, US10Y↓ → easing
            "credit": "bullish",  # HYG↑
        },
        "confidence_boost": 0.85,
        "summary": "Dollar weakness and falling rates are easing financial conditions. "
        "Credit markets supportive — risk assets benefit.",
        "implications": "Risk-on positioning. Consider adding to EM and credit exposure.",
    },
    {
        "name": "Credit Stress",
        "conditions": {
            "credit": "bearish",
        },
        "confidence_boost": 0.75,
        "summary": "Credit markets are signaling stress. High yield spreads widening, "
        "HYG under pressure. Watch for contagion to equities.",
        "implications": "Reduce credit exposure. Monitor HYG flows and CDS spreads.",
    },
    {
        "name": "Growth Recovery",
        "conditions": {
            "growth": "bullish",
        },
        "confidence_boost": 0.75,
        "summary": "Growth indicators are improving. PMI, ISM, and industrial production "
        "show expansion — cyclical assets benefit.",
        "implications": "Overweight cyclicals. Watch for confirmation in employment data.",
    },
    {
        "name": "Growth Slowdown",
        "conditions": {
            "growth": "bearish",
        },
        "confidence_boost": 0.80,
        "summary": "Growth momentum is decelerating. Leading indicators point to "
        "weakening activity — defensive positioning warranted.",
        "implications": "Defensive rotation. Monitor initial claims and consumer confidence.",
    },
    {
        "name": "Inflation Resurgence",
        "conditions": {
            "inflation": "bullish",
        },
        "confidence_boost": 0.80,
        "summary": "Inflation metrics are re-accelerating. This challenges the "
        "disinflation narrative and may delay rate cuts.",
        "implications": "Hedge inflation risk. Watch CPI MoM, PCE, and breakevens.",
    },
    {
        "name": "Risk-On",
        "conditions": {
            "credit": "bullish",
            "growth": "bullish",
        },
        "confidence_boost": 0.80,
        "summary": "Credit and growth signals are both supportive. Risk appetite "
        "is broadening — favorable environment for equities.",
        "implications": "Full risk-on positioning. Add beta exposure.",
    },
    {
        "name": "Risk-Off",
        "conditions": {
            "credit": "bearish",
            "risk_appetite": "bearish",
        },
        "confidence_boost": 0.85,
        "summary": "Risk aversion is dominant. Credit stress and volatility spikes "
        "signal a flight to safety.",
        "implications": "Move to cash and safe havens. Watch VIX and gold.",
    },
]


# ── Generator ────────────────────────────────────────────────────────────────


class CompositeSignalGenerator:
    """Generates composite signals and macro themes from individual signals.

    v2.0: Replaces single-indicator reasoning with cross-indicator synthesis.
    """

    def __init__(self) -> None:
        pass

    def generate_composites(
        self,
        snapshot: SignalSnapshot,
    ) -> list[CompositeSignal]:
        """Generate composite signals from a signal snapshot.

        Groups signals by dimension and creates composites when multiple
        indicators in the same dimension agree on direction.

        Args:
            snapshot: All current individual signals.

        Returns:
            List of composite signals.
        """
        composites: list[CompositeSignal] = []

        # Group signals by dimension
        by_dimension: dict[str, list[MacroSignalSchema]] = {}
        for sig in snapshot.signals:
            dim_key = sig.dimension.lower()
            if dim_key not in by_dimension:
                by_dimension[dim_key] = []
            by_dimension[dim_key].append(sig)

        # Generate composite per dimension with >= 2 signals
        for dim, signals in by_dimension.items():
            if len(signals) < 2:
                continue

            bullish_count = sum(1 for s in signals if s.direction == SignalDirection.BULLISH)
            bearish_count = sum(1 for s in signals if s.direction == SignalDirection.BEARISH)

            # Calculate agreement
            total = len(signals)
            majority_count = max(bullish_count, bearish_count)
            agreement = majority_count / total if total > 0 else 0.0

            # Determine combined direction
            if bullish_count > bearish_count:
                combined_dir = SignalDirection.BULLISH
            elif bearish_count > bullish_count:
                combined_dir = SignalDirection.BEARISH
            else:
                combined_dir = SignalDirection.NEUTRAL

            # Combined confidence: average of constituent confidences
            combined_conf = sum(s.confidence for s in signals) / total

            # Signal diversity: how many unique indicators contribute
            unique_indicators = len(set(s.indicator for s in signals))
            diversity = unique_indicators / total if total > 0 else 0.0

            # Contradiction note
            contradiction = ""
            if bullish_count > 0 and bearish_count > 0:
                contradiction = (
                    f"Mixed signals: {bullish_count} bullish vs {bearish_count} bearish "
                    f"in {dim} dimension."
                )

            # Theme name
            theme = f"{dim.title()} " + (
                "Strengthening"
                if combined_dir == SignalDirection.BULLISH
                else "Weakening" if combined_dir == SignalDirection.BEARISH else "Mixed"
            )

            # Description
            indicators_list = sorted(set(s.indicator for s in signals))
            desc = (
                f"{', '.join(indicators_list[:5])} collectively indicate "
                f"{'supportive' if combined_dir == SignalDirection.BULLISH else 'restrictive' if combined_dir == SignalDirection.BEARISH else 'mixed'} "
                f"conditions in the {dim} dimension "
                f"(agreement: {agreement:.0%}, confidence: {combined_conf:.0%})."
            )

            composite = CompositeSignal(
                theme=theme,
                description=desc,
                source_signals=[s.signal_id for s in signals],
                indicators=indicators_list,
                dimensions=[dim],
                combined_direction=combined_dir,
                combined_strength=(
                    SignalStrength.STRONG if agreement >= 0.75 else SignalStrength.MODERATE
                ),
                combined_confidence=round(combined_conf, 4),
                agreement_ratio=round(agreement, 4),
                signal_diversity=round(diversity, 4),
                contradiction_note=contradiction,
            )
            composites.append(composite)

        return composites

    def generate_themes(
        self,
        snapshot: SignalSnapshot,
        composites: list[CompositeSignal] | None = None,
    ) -> list[MacroTheme]:
        """Generate macro themes from individual and composite signals.

        Themes represent the high-level macro regime the Agent believes
        is currently active.

        Args:
            snapshot: Current individual signals.
            composites: Optional pre-computed composite signals.

        Returns:
            List of macro themes with activation scores.
        """
        if composites is None:
            composites = self.generate_composites(snapshot)

        themes: list[MacroTheme] = []

        for template in _THEME_DEFINITIONS:
            conditions: dict[str, str] = template["conditions"]
            matching = True
            match_signals: list[str] = []
            all_indicators: list[str] = []

            for dim, expected_dir in conditions.items():
                # Check individual signals
                dim_signals = [s for s in snapshot.signals if s.dimension.lower() == dim]
                if dim_signals:
                    all_indicators.extend(s.indicator for s in dim_signals)
                    directions = [s.direction.value for s in dim_signals]
                    if expected_dir not in directions:
                        matching = False
                        break
                    match_signals.extend(
                        s.signal_id for s in dim_signals if s.direction.value == expected_dir
                    )

                # Also check composites
                dim_composites = [c for c in composites if dim in [d.lower() for d in c.dimensions]]
                for c in dim_composites:
                    if c.combined_direction.value == expected_dir:
                        match_signals.append(c.composite_id)
                    else:
                        matching = False

            if matching:
                # Activation score based on confidence and agreement
                avg_conf = 0.5
                if match_signals:
                    dim_confs = [
                        s.confidence for s in snapshot.signals if s.signal_id in match_signals
                    ]
                    if dim_confs:
                        avg_conf = sum(dim_confs) / len(dim_confs)

                activation = min(avg_conf * template["confidence_boost"], 1.0)
                themes.append(
                    MacroTheme(
                        name=template["name"],
                        activated=True,
                        activation_score=round(activation, 4),
                        supporting_composites=list(set(match_signals)),
                        underlying_indicators=list(set(all_indicators)),
                        summary=template["summary"],
                        implications=template["implications"],
                        confidence=round(activation, 4),
                    )
                )
            else:
                # Inactive theme
                themes.append(
                    MacroTheme(
                        name=template["name"],
                        activated=False,
                        activation_score=0.0,
                        supporting_composites=[],
                        underlying_indicators=[],
                        summary=template["summary"],
                        implications=template["implications"],
                        confidence=0.0,
                    )
                )

        # Determine dominant theme
        active = [t for t in themes if t.activated]
        _dominant = max(active, key=lambda t: t.activation_score).name if active else None

        return themes

    def generate_snapshot(
        self,
        individual_signals: SignalSnapshot,
    ) -> CompositeSignalSnapshot:
        """Generate a full composite signal snapshot.

        Args:
            individual_signals: Current individual signal snapshot.

        Returns:
            CompositeSignalSnapshot with composites and themes.
        """
        composites = self.generate_composites(individual_signals)
        themes = self.generate_themes(individual_signals, composites)

        dominant = None
        active = [t for t in themes if t.activated]
        if active:
            dominant = max(active, key=lambda t: t.activation_score).name

        return CompositeSignalSnapshot(
            composite_signals=composites,
            macro_themes=themes,
            dominant_theme=dominant,
        )
