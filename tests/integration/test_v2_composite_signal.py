"""v2.0 Composite Signal Generator tests."""

import pytest

from src.schemas.signal import (
    CompositeSignal,
    CompositeSignalSnapshot,
    MacroSignalSchema,
    MacroTheme,
    SignalDirection,
    SignalEvidence,
    SignalSnapshot,
    SignalStrength,
)
from src.signal.composite_signal_generator import CompositeSignalGenerator


# ── Helpers ─────────────────────────────────────────────────────────────────


def signal(indicator, dimension, direction, confidence=0.8):
    return MacroSignalSchema(
        indicator=indicator,
        dimension=dimension,
        direction=SignalDirection(direction),
        strength=SignalStrength.STRONG if confidence > 0.7 else SignalStrength.MODERATE,
        confidence=confidence,
        evidence=[SignalEvidence(
            rule_id=f"r_{indicator}", rule_description=direction,
            input_value=1.0, condition=f"{indicator} {direction}",
            interpretation=f"{indicator}: {direction} signal",
        )],
    )


# ── CompositeSignalGenerator ───────────────────────────────────────────────


class TestCompositeSignalGenerator:
    def test_generates_composite_for_multiple_signals(self):
        gen = CompositeSignalGenerator()
        snap = SignalSnapshot(signals=[
            signal("DXY", "Liquidity", "bullish", 0.85),
            signal("US10Y", "Liquidity", "bullish", 0.80),
            signal("FEDFUNDS", "Liquidity", "bullish", 0.75),
        ])
        composites = gen.generate_composites(snap)
        assert len(composites) == 1
        c = composites[0]
        assert c.theme == "Liquidity Strengthening"
        assert c.combined_direction == SignalDirection.BULLISH
        assert c.agreement_ratio == 1.0  # unanimous
        assert c.signal_diversity == 1.0  # 3 unique indicators / 3 signals

    def test_mixed_signals_reduce_agreement(self):
        gen = CompositeSignalGenerator()
        snap = SignalSnapshot(signals=[
            signal("DXY", "Liquidity", "bullish", 0.80),
            signal("US10Y", "Liquidity", "bearish", 0.70),
        ])
        composites = gen.generate_composites(snap)
        assert len(composites) == 1
        c = composites[0]
        assert c.agreement_ratio == 0.5  # 1 bullish, 1 bearish
        assert c.combined_direction == SignalDirection.NEUTRAL  # tied → neutral

    def test_single_signal_no_composite(self):
        gen = CompositeSignalGenerator()
        snap = SignalSnapshot(signals=[
            signal("DXY", "Liquidity", "bullish", 0.80),
        ])
        composites = gen.generate_composites(snap)
        assert len(composites) == 0  # Need >= 2 signals

    def test_multiple_dimensions(self):
        gen = CompositeSignalGenerator()
        snap = SignalSnapshot(signals=[
            signal("DXY", "Liquidity", "bullish", 0.80),
            signal("US10Y", "Liquidity", "bullish", 0.75),
            signal("HYG", "Credit", "bearish", 0.85),
            signal("CDS", "Credit", "bearish", 0.70),
        ])
        composites = gen.generate_composites(snap)
        assert len(composites) == 2
        themes = {c.theme for c in composites}
        assert "Liquidity Strengthening" in themes or "Liquidity" in c.theme
        credit = [c for c in composites if "redit" in c.theme][0]
        assert "bearish" in credit.combined_direction.value or credit.combined_direction == SignalDirection.BEARISH

    def test_generates_macro_themes(self):
        gen = CompositeSignalGenerator()
        snap = SignalSnapshot(signals=[
            signal("DXY", "Liquidity", "bearish", 0.80),
            signal("US10Y", "Liquidity", "bearish", 0.75),
            signal("HYG", "Credit", "bullish", 0.85),
        ])
        composites = gen.generate_composites(snap)
        themes = gen.generate_themes(snap, composites)

        assert len(themes) > 0
        # Liquidity Easing should be active
        easing = [t for t in themes if "Easing" in t.name or "easing" in t.name.lower()]
        assert len(easing) >= 1

    def test_full_snapshot_generation(self):
        gen = CompositeSignalGenerator()
        snap = SignalSnapshot(signals=[
            signal("DXY", "Liquidity", "bullish", 0.85),
            signal("US10Y", "Liquidity", "bullish", 0.80),
            signal("HYG", "Credit", "bullish", 0.75),
            signal("PMI", "Growth", "bullish", 0.70),
        ])
        snapshot = gen.generate_snapshot(snap)
        assert isinstance(snapshot, CompositeSignalSnapshot)
        assert len(snapshot.composite_signals) >= 1
        assert len(snapshot.macro_themes) > 0
        assert snapshot.dominant_theme is not None

    def test_risk_off_detection(self):
        gen = CompositeSignalGenerator()
        snap = SignalSnapshot(signals=[
            signal("HYG", "Credit", "bearish", 0.85),
            signal("CDS", "Credit", "bearish", 0.80),
            signal("VIX", "Risk_Appetite", "bearish", 0.80),
        ])
        snapshot = gen.generate_snapshot(snap)
        risk_off = [t for t in snapshot.macro_themes if "Risk-Off" in t.name or "Risk Off" in t.name]
        assert len(risk_off) >= 1
        assert risk_off[0].activated

    def test_liquidity_tightening_detection(self):
        gen = CompositeSignalGenerator()
        snap = SignalSnapshot(signals=[
            signal("DXY", "Liquidity", "bullish", 0.90),
            signal("US10Y", "Liquidity", "bullish", 0.85),
            signal("HYG", "Credit", "bearish", 0.80),
        ])
        snapshot = gen.generate_snapshot(snap)
        tightening = [t for t in snapshot.macro_themes if "Tightening" in t.name]
        assert len(tightening) >= 1
        assert tightening[0].activated
        assert tightening[0].activation_score > 0.5

    def test_inactive_themes_present(self):
        gen = CompositeSignalGenerator()
        snap = SignalSnapshot(signals=[
            signal("DXY", "Liquidity", "bullish", 0.85),
            signal("US10Y", "Liquidity", "bullish", 0.80),
        ])
        snapshot = gen.generate_snapshot(snap)
        inactive = [t for t in snapshot.macro_themes if not t.activated]
        assert len(inactive) > 0
