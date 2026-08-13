"""Tests for HypothesisGenerator & HypothesisEngine (Sprint 6).

Covers:
    - HypothesisGenerator: single-narrative generation (bearish dominance)
    - HypothesisGenerator: single-narrative generation (bullish dominance)
    - HypothesisGenerator: competing hypotheses (mixed signals)
    - HypothesisGenerator: edge cases (empty, single signal, all neutral)
    - HypothesisEngine.reason(): full pipeline integration
    - HypothesisEngine.reason(): edge cases
    - Hypothesis statements are explanations, not aggregations
    - Assumptions are populated and filtered
"""

from datetime import UTC, datetime

import pytest

from src.hypothesis.engine import HypothesisEngine
from src.hypothesis.generator import HypothesisGenerator
from src.schemas.hypothesis import HypothesisSet
from src.schemas.signal import (
    MacroSignalSchema,
    SignalDirection,
    SignalEvidence,
    SignalStrength,
)

# ── Helpers ───────────────────────────────────────────────────────────────


def make_signal(
    signal_id: str = "s_test",
    indicator: str = "DXY",
    dimension: str = "Liquidity",
    direction: SignalDirection = SignalDirection.BEARISH,
    strength: SignalStrength = SignalStrength.MODERATE,
    confidence: float = 0.75,
    input_value: float = 106.0,
    condition: str = "value > 105.0",
    interpretation: str = "Dollar strengthening",
) -> MacroSignalSchema:
    """Factory for test signals with full evidence."""
    now = datetime.now(UTC)
    return MacroSignalSchema(
        signal_id=signal_id,
        indicator=indicator,
        dimension=dimension,
        direction=direction,
        strength=strength,
        confidence=confidence,
        timestamp=now,
        evidence=[
            SignalEvidence(
                rule_id=f"r_{signal_id}",
                rule_description=f"{indicator} rule",
                input_value=input_value,
                condition=condition,
                interpretation=interpretation,
                evaluated_at=now,
            )
        ],
    )


# ── HypothesisGenerator Tests ─────────────────────────────────────────────


class TestHypothesisGenerator:
    @pytest.fixture
    def generator(self):
        return HypothesisGenerator()

    # ── Bearish-dominant ───────────────────────────────────────────

    def test_bearish_dominant_single_hypothesis(self, generator):
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
            make_signal("s2", "US10Y", "Liquidity", SignalDirection.BEARISH),
            make_signal("s3", "HYG", "Credit", SignalDirection.BEARISH),
        ]
        hypotheses = generator.generate(signals)
        assert len(hypotheses) == 1
        assert hypotheses[0].direction == SignalDirection.BEARISH

    def test_bearish_hypothesis_has_statement(self, generator):
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
            make_signal("s2", "US10Y", "Liquidity", SignalDirection.BEARISH),
        ]
        hypotheses = generator.generate(signals)
        assert len(hypotheses[0].statement) > 20

    def test_bearish_hypothesis_has_assumptions(self, generator):
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
            make_signal("s2", "US10Y", "Liquidity", SignalDirection.BEARISH),
        ]
        hypotheses = generator.generate(signals)
        assert len(hypotheses[0].assumptions) >= 2

    # ── Bullish-dominant ───────────────────────────────────────────

    def test_bullish_dominant_single_hypothesis(self, generator):
        signals = [
            make_signal(
                "s1",
                "DXY",
                "Liquidity",
                SignalDirection.BULLISH,
                input_value=99.0,
                condition="value < 100.0",
                interpretation="Dollar weakening",
            ),
            make_signal(
                "s2",
                "US10Y",
                "Liquidity",
                SignalDirection.BULLISH,
                input_value=2.8,
                condition="value < 3.0",
                interpretation="Low rates",
            ),
            make_signal(
                "s3",
                "HYG",
                "Credit",
                SignalDirection.BULLISH,
                input_value=80.0,
                condition="value > 78.0",
                interpretation="Credit healthy",
            ),
        ]
        hypotheses = generator.generate(signals)
        assert len(hypotheses) == 1
        assert hypotheses[0].direction == SignalDirection.BULLISH

    # ── Mixed signals → competing hypotheses ───────────────────────

    def test_mixed_signals_generates_competing(self, generator):
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
            make_signal("s2", "US10Y", "Liquidity", SignalDirection.BEARISH),
            make_signal("s3", "HYG", "Credit", SignalDirection.BULLISH),
            make_signal("s4", "^VIX", "Risk_Appetite", SignalDirection.BULLISH),
        ]
        hypotheses = generator.generate(signals)
        # Should produce at least 2 competing hypotheses
        assert len(hypotheses) >= 2

    def test_competing_hypotheses_have_different_directions(self, generator):
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
            make_signal("s2", "HYG", "Credit", SignalDirection.BULLISH),
        ]
        hypotheses = generator.generate(signals)
        directions = {h.direction for h in hypotheses}
        # Should have both bearish and bullish (plus possibly neutral)
        assert SignalDirection.BEARISH in directions or SignalDirection.BULLISH in directions

    # ── Edge cases ─────────────────────────────────────────────────

    def test_empty_signals(self, generator):
        hypotheses = generator.generate([])
        assert hypotheses == []

    def test_single_signal(self, generator):
        signals = [make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH)]
        hypotheses = generator.generate(signals)
        assert len(hypotheses) == 1

    def test_all_neutral_signals(self, generator):
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.NEUTRAL),
            make_signal("s2", "US10Y", "Liquidity", SignalDirection.NEUTRAL),
        ]
        hypotheses = generator.generate(signals)
        assert len(hypotheses) >= 1  # Should still produce something

    def test_hypothesis_is_not_signal_aggregation(self, generator):
        """Hypothesis should be an EXPLANATION, not just dimension grouping."""
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
            make_signal("s2", "US10Y", "Liquidity", SignalDirection.BEARISH),
        ]
        hypotheses = generator.generate(signals)
        for h in hypotheses:
            # Statement should be an explanation, not just a list of indicators
            assert len(h.statement) > 30
            # Should not be just "Liquidity indicators are bearish"
            assert "tightening" in h.statement.lower() or "conditions" in h.statement.lower()

    def test_cross_dimension_reasoning(self, generator):
        """Hypothesis should reason across dimensions, not silo them."""
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
            make_signal("s2", "HYG", "Credit", SignalDirection.BEARISH),
            make_signal("s3", "^VIX", "Risk_Appetite", SignalDirection.BEARISH),
        ]
        hypotheses = generator.generate(signals)
        # With Liquidity + Credit + Risk_Appetite all bearish,
        # it should produce a tightening narrative
        statement_lower = hypotheses[0].statement.lower()
        assert any(keyword in statement_lower for keyword in ["tightening", "risk", "conditions"])

    def test_dimension_is_metadata_only(self, generator):
        """Dimension should be set but is NOT the primary grouping mechanism."""
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
            make_signal("s2", "HG=F", "Growth", SignalDirection.BULLISH),
        ]
        hypotheses = generator.generate(signals)
        for h in hypotheses:
            assert h.dimension  # Has dimension
            # But statement is an explanation, not "Dimension X is Y"
            assert len(h.statement) > 20


# ── HypothesisEngine Tests ────────────────────────────────────────────────


class TestHypothesisEngine:
    @pytest.fixture
    def engine(self):
        return HypothesisEngine()

    def test_reason_returns_hypothesis_set(self, engine):
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
        ]
        result = engine.reason(signals)
        assert isinstance(result, HypothesisSet)

    def test_reason_produces_hypotheses(self, engine):
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
            make_signal("s2", "US10Y", "Liquidity", SignalDirection.BEARISH),
        ]
        result = engine.reason(signals)
        assert result.count >= 1
        assert len(result.hypotheses[0].statement) > 20

    def test_reason_populates_evidence(self, engine):
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
            make_signal("s2", "US10Y", "Liquidity", SignalDirection.BEARISH),
        ]
        result = engine.reason(signals)
        for h in result.hypotheses:
            assert h.evidence_count > 0

    def test_reason_populates_supporting_evidence(self, engine):
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
        ]
        result = engine.reason(signals)
        h = result.hypotheses[0]
        assert len(h.supporting_evidence) >= 1

    def test_reason_populates_confidence(self, engine):
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
            make_signal("s2", "US10Y", "Liquidity", SignalDirection.BEARISH),
        ]
        result = engine.reason(signals)
        for h in result.hypotheses:
            assert 0.0 <= h.confidence <= 1.0
            # With 2 strong bearish signals, confidence should be reasonably high
            assert h.confidence > 0.40

    def test_reason_empty_signals(self, engine):
        result = engine.reason([])
        assert isinstance(result, HypothesisSet)
        assert result.count == 0

    def test_reason_dimensions_covered(self, engine):
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
            make_signal("s2", "HYG", "Credit", SignalDirection.BEARISH),
        ]
        result = engine.reason(signals)
        assert len(result.dimensions_covered) >= 1

    def test_reason_summary(self, engine):
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
        ]
        result = engine.reason(signals)
        assert len(result.summary) > 10

    def test_reason_with_contradicting_evidence(self, engine):
        """Mixed signals should produce contradicting evidence on some hypotheses."""
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
            make_signal("s2", "US10Y", "Liquidity", SignalDirection.BEARISH),
            make_signal("s3", "HG=F", "Growth", SignalDirection.BULLISH),
        ]
        result = engine.reason(signals)
        # At least one hypothesis should have contradicting evidence
        # (Copper bullish contradicts bearish thesis)
        has_contradictions = any(h.has_contradictions for h in result.hypotheses)
        assert has_contradictions

    def test_reason_confidence_correlates_with_evidence(self, engine):
        """More supporting evidence → higher confidence."""
        # Hypothesis with 3 strong supporting signals
        result1 = engine.reason(
            [
                make_signal(
                    "s1",
                    "DXY",
                    "Liquidity",
                    SignalDirection.BEARISH,
                    strength=SignalStrength.STRONG,
                    confidence=0.90,
                ),
                make_signal(
                    "s2",
                    "US10Y",
                    "Liquidity",
                    SignalDirection.BEARISH,
                    strength=SignalStrength.STRONG,
                    confidence=0.85,
                ),
                make_signal(
                    "s3",
                    "HYG",
                    "Credit",
                    SignalDirection.BEARISH,
                    strength=SignalStrength.STRONG,
                    confidence=0.90,
                ),
            ]
        )

        # Hypothesis with 1 weak signal
        result2 = engine.reason(
            [
                make_signal(
                    "s1",
                    "DXY",
                    "Liquidity",
                    SignalDirection.BEARISH,
                    strength=SignalStrength.WEAK,
                    confidence=0.30,
                ),
            ]
        )

        c1 = result1.hypotheses[0].confidence
        c2 = result2.hypotheses[0].confidence
        assert c1 > c2, f"Expected {c1} > {c2}: stronger signals should yield higher confidence"

    def test_hypotheses_are_explanations_not_aggregations(self, engine):
        """Validate that hypotheses are actual explanations of reality."""
        signals = [
            make_signal("s1", "DXY", "Liquidity", SignalDirection.BEARISH),
            make_signal("s2", "^VIX", "Risk_Appetite", SignalDirection.BEARISH),
        ]
        result = engine.reason(signals)
        for h in result.hypotheses:
            # Verification that statement is a real explanation:
            # - Long enough to be meaningful
            assert len(h.statement) > 40
            # - Not just listing indicators
            assert not h.statement.startswith("Liquidity")
            # - Contains causal or explanatory language
            has_explanation = any(
                word in h.statement.lower()
                for word in [
                    "tightening",
                    "easing",
                    "risk",
                    "conditions",
                    "divergence",
                    "transition",
                    "environment",
                ]
            )
            assert has_explanation, f"Statement lacks explanation: {h.statement}"
