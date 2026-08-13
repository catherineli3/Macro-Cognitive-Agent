"""Tests for EvidenceAggregator & ConfidenceCalculator (Sprint 6).

Covers:
    - EvidenceAggregator: classifying supporting/contradicting evidence
    - EvidenceAggregator: contribution weight calculation
    - EvidenceAggregator: edge cases (no signals, no evidence, neutral)
    - ConfidenceCalculator: multi-factor scoring
    - ConfidenceCalculator: edge cases (no evidence, all supporting, all contradicting)
"""

from datetime import UTC, datetime

import pytest

from src.hypothesis.aggregator import EvidenceAggregator
from src.hypothesis.confidence import ConfidenceCalculator
from src.schemas.hypothesis import HypothesisEvidence
from src.schemas.signal import (
    MacroSignalSchema,
    SignalDirection,
    SignalEvidence,
    SignalStrength,
)

# ── Helpers ───────────────────────────────────────────────────────────────


def make_signal(
    signal_id: str,
    indicator: str,
    direction: SignalDirection,
    strength: SignalStrength = SignalStrength.MODERATE,
    confidence: float = 0.70,
    dimension: str = "Liquidity",
    with_evidence: bool = True,
) -> MacroSignalSchema:
    """Factory for test signals."""
    now = datetime.now(UTC)
    evidence = []
    if with_evidence:
        evidence = [
            SignalEvidence(
                rule_id=f"r_{signal_id}",
                rule_description=f"{indicator} test rule",
                input_value=100.0,
                condition="value > 50",
                interpretation=f"{indicator} interpretation",
                evaluated_at=now,
            )
        ]
    return MacroSignalSchema(
        signal_id=signal_id,
        indicator=indicator,
        dimension=dimension,
        direction=direction,
        strength=strength,
        confidence=confidence,
        timestamp=now,
        evidence=evidence,
    )


# ── EvidenceAggregator Tests ──────────────────────────────────────────────


class TestEvidenceAggregator:
    @pytest.fixture
    def aggregator(self):
        return EvidenceAggregator()

    def test_all_supporting(self, aggregator):
        signals = [
            make_signal("s1", "DXY", SignalDirection.BEARISH),
            make_signal("s2", "US10Y", SignalDirection.BEARISH),
        ]
        supporting, contradicting = aggregator.aggregate(signals, SignalDirection.BEARISH)
        assert len(supporting) == 2
        assert len(contradicting) == 0

    def test_all_contradicting(self, aggregator):
        signals = [
            make_signal("s1", "DXY", SignalDirection.BULLISH),
        ]
        supporting, contradicting = aggregator.aggregate(signals, SignalDirection.BEARISH)
        assert len(supporting) == 0
        assert len(contradicting) == 1

    def test_mixed_evidence(self, aggregator):
        signals = [
            make_signal("s1", "DXY", SignalDirection.BEARISH),
            make_signal("s2", "HG=F", SignalDirection.BULLISH),
            make_signal("s3", "US10Y", SignalDirection.BEARISH),
        ]
        supporting, contradicting = aggregator.aggregate(signals, SignalDirection.BEARISH)
        assert len(supporting) == 2
        assert len(contradicting) == 1

    def test_neutral_signal_is_supporting(self, aggregator):
        """Neutral signals are treated as weak supporting evidence."""
        signals = [
            make_signal("s1", "DXY", SignalDirection.NEUTRAL),
        ]
        supporting, contradicting = aggregator.aggregate(signals, SignalDirection.BEARISH)
        assert len(supporting) == 1
        assert len(contradicting) == 0

    def test_empty_signals(self, aggregator):
        supporting, contradicting = aggregator.aggregate([], SignalDirection.BEARISH)
        assert supporting == []
        assert contradicting == []

    def test_contribution_from_strength_and_confidence(self, aggregator):
        """Contribution = strength_weight × signal.confidence."""
        signals = [
            make_signal(
                "s1",
                "DXY",
                SignalDirection.BEARISH,
                strength=SignalStrength.STRONG,
                confidence=0.80,
            ),
        ]
        supporting, _ = aggregator.aggregate(signals, SignalDirection.BEARISH)
        # strong weight = 0.80, confidence = 0.80 → contribution ≈ 0.64
        assert len(supporting) == 1
        assert supporting[0].contribution == pytest.approx(0.64, rel=0.01)

    def test_contribution_weak_signal(self, aggregator):
        signals = [
            make_signal(
                "s1", "DXY", SignalDirection.BEARISH, strength=SignalStrength.WEAK, confidence=0.50
            ),
        ]
        supporting, _ = aggregator.aggregate(signals, SignalDirection.BEARISH)
        # weak weight = 0.30, confidence = 0.50 → contribution ≈ 0.15
        assert supporting[0].contribution == pytest.approx(0.15, rel=0.01)

    def test_evidence_items_contain_indicator(self, aggregator):
        signals = [make_signal("s1", "DXY", SignalDirection.BEARISH)]
        supporting, _ = aggregator.aggregate(signals, SignalDirection.BEARISH)
        assert supporting[0].indicator == "DXY"

    def test_evidence_items_contain_signal_id(self, aggregator):
        signals = [make_signal("s1", "DXY", SignalDirection.BEARISH)]
        supporting, _ = aggregator.aggregate(signals, SignalDirection.BEARISH)
        assert supporting[0].signal_id == "s1"

    def test_alignment_label(self, aggregator):
        signals = [
            make_signal("s1", "DXY", SignalDirection.BEARISH),
            make_signal("s2", "HG=F", SignalDirection.BULLISH),
        ]
        supporting, contradicting = aggregator.aggregate(signals, SignalDirection.BEARISH)
        assert supporting[0].alignment == "supporting"
        assert contradicting[0].alignment == "contradicting"

    def test_signal_without_evidence_still_produces_item(self, aggregator):
        signals = [make_signal("s1", "DXY", SignalDirection.BEARISH, with_evidence=False)]
        supporting, contradicting = aggregator.aggregate(signals, SignalDirection.BEARISH)
        assert len(supporting) == 1
        assert "DXY" in supporting[0].observation

    def test_multi_evidence_signal(self, aggregator):
        """A signal with 2 evidence items produces 2 HypothesisEvidence items."""
        now = datetime.now(UTC)
        signal = MacroSignalSchema(
            signal_id="s1",
            indicator="DXY",
            dimension="Liquidity",
            direction=SignalDirection.BEARISH,
            strength=SignalStrength.STRONG,
            confidence=0.80,
            timestamp=now,
            evidence=[
                SignalEvidence(
                    rule_id="r1",
                    rule_description="Rule 1",
                    input_value=106.0,
                    condition="value > 105",
                    interpretation="Above 105",
                    evaluated_at=now,
                ),
                SignalEvidence(
                    rule_id="r2",
                    rule_description="Rule 2",
                    input_value=106.0,
                    condition="value > 100",
                    interpretation="Above 100",
                    evaluated_at=now,
                ),
            ],
        )
        supporting, _ = aggregator.aggregate([signal], SignalDirection.BEARISH)
        assert len(supporting) == 2


# ── ConfidenceCalculator Tests ────────────────────────────────────────────


class TestConfidenceCalculator:
    @pytest.fixture
    def calculator(self):
        return ConfidenceCalculator()

    def test_all_supporting_high_confidence(self, calculator):
        supporting = [
            HypothesisEvidence(
                indicator="DXY",
                signal_id="s1",
                observation="DXY at 106",
                interpretation="Test",
                contribution=0.64,
                alignment="supporting",
            ),
            HypothesisEvidence(
                indicator="US10Y",
                signal_id="s2",
                observation="US10Y at 5.2",
                interpretation="Test",
                contribution=0.68,
                alignment="supporting",
            ),
        ]
        confidence = calculator.calculate(supporting, [])
        # agreement=1.0, strength≈0.66, coverage=1.0
        # → 0.35*1.0 + 0.35*0.66 + 0.30*1.0 ≈ 0.88
        assert confidence > 0.80
        assert confidence <= 1.0

    def test_mixed_evidence_moderate_confidence(self, calculator):
        supporting = [
            HypothesisEvidence(
                indicator="DXY",
                signal_id="s1",
                observation="DXY at 106",
                interpretation="Test",
                contribution=0.64,
                alignment="supporting",
            ),
        ]
        contradicting = [
            HypothesisEvidence(
                indicator="HG=F",
                signal_id="s2",
                observation="Copper at 4.8",
                interpretation="Test",
                contribution=0.385,
                alignment="contradicting",
            ),
        ]
        confidence = calculator.calculate(supporting, contradicting)
        # agreement=0.5, strength=0.64, coverage=1.0
        # → 0.35*0.5 + 0.35*0.64 + 0.30*1.0 ≈ 0.699
        assert 0.50 < confidence < 0.80

    def test_all_contradicting_low_confidence(self, calculator):
        contradicting = [
            HypothesisEvidence(
                indicator="DXY",
                signal_id="s1",
                observation="DXY at 106",
                interpretation="Test",
                contribution=0.64,
                alignment="contradicting",
            ),
        ]
        confidence = calculator.calculate([], contradicting)
        # agreement=0.0, strength=0.10 (default), coverage=1.0
        # → 0.35*0.0 + 0.35*0.10 + 0.30*1.0 ≈ 0.335
        assert confidence < 0.40

    def test_no_evidence_minimal_confidence(self, calculator):
        confidence = calculator.calculate([], [])
        assert confidence == 0.10

    def test_confidence_in_range(self, calculator):
        """Confidence is always in 0-1 range."""
        import random

        for _ in range(20):
            n_supporting = random.randint(0, 5)
            n_contradicting = random.randint(0, 5)
            supporting = [
                HypothesisEvidence(
                    indicator="T",
                    signal_id=f"s{i}",
                    observation="X",
                    interpretation="Y",
                    contribution=random.uniform(0.1, 1.0),
                    alignment="supporting",
                )
                for i in range(n_supporting)
            ]
            contradicting = [
                HypothesisEvidence(
                    indicator="T",
                    signal_id=f"c{i}",
                    observation="X",
                    interpretation="Y",
                    contribution=random.uniform(0.1, 1.0),
                    alignment="contradicting",
                )
                for i in range(n_contradicting)
            ]
            c = calculator.calculate(supporting, contradicting)
            assert 0.0 <= c <= 1.0, f"Confidence {c} out of range"

    def test_agreement_score_weights(self, calculator):
        """Verify the agreement factor contributes correctly."""
        supporting = [
            HypothesisEvidence(
                indicator="A",
                signal_id="s1",
                observation="X",
                interpretation="Y",
                contribution=0.5,
                alignment="supporting",
            )
        ] * 3
        contradicting = [
            HypothesisEvidence(
                indicator="B",
                signal_id="s2",
                observation="X",
                interpretation="Y",
                contribution=0.5,
                alignment="contradicting",
            )
        ]
        confidence = calculator.calculate(supporting, contradicting)
        # agreement = 3/4 = 0.75
        assert 0.55 < confidence < 0.90
