"""Tests for Sprint 2 schema and domain models."""

from datetime import UTC, datetime

import pytest

from src.domain.signal import RuleType
from src.schemas.signal import (
    MacroSignalSchema,
    SignalDirection,
    SignalEvidence,
    SignalSnapshot,
    SignalStrength,
)


class TestSignalEvidence:
    """SignalEvidence model validation."""

    def test_create_evidence(self) -> None:
        ev = SignalEvidence(
            rule_id="test_rule",
            rule_description="A test rule",
            input_value=105.0,
            condition="value gt 100",
            interpretation="Financial Conditions Tightening",
        )
        assert ev.rule_id == "test_rule"
        assert ev.interpretation == "Financial Conditions Tightening"
        assert ev.input_value == 105.0

    def test_evidence_missing_interpretation_fails(self) -> None:
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            SignalEvidence(
                rule_id="test",
                rule_description="desc",
                input_value=1.0,
                condition="x > 0",
                # interpretation is required — omitted
            )


class TestMacroSignalSchema:
    """MacroSignalSchema model validation."""

    def test_create_minimal_signal(self) -> None:
        sig = MacroSignalSchema(
            indicator="DXY",
            dimension="Liquidity",
            direction=SignalDirection.BEARISH,
            strength=SignalStrength.STRONG,
            confidence=0.9,
        )
        assert sig.indicator == "DXY"
        assert sig.dimension == "Liquidity"
        assert len(sig.evidence) == 0

    def test_create_full_signal(self) -> None:
        ev = SignalEvidence(
            rule_id="dxy_strong",
            rule_description="DXY above 105",
            input_value=106.0,
            condition="value gt 105",
            interpretation="Strong dollar — tightening conditions",
        )
        sig = MacroSignalSchema(
            indicator="DXY",
            dimension="Liquidity",
            direction=SignalDirection.BEARISH,
            strength=SignalStrength.MODERATE,
            confidence=0.75,
            evidence=[ev],
            data_timestamp=datetime(2026, 7, 13, tzinfo=UTC),
        )
        assert len(sig.evidence) == 1
        assert sig.evidence[0].interpretation == "Strong dollar — tightening conditions"

    def test_add_evidence(self) -> None:
        sig = MacroSignalSchema(
            indicator="DXY",
            dimension="Liquidity",
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.WEAK,
            confidence=0.3,
        )
        assert len(sig.evidence) == 0
        sig.add_evidence(
            SignalEvidence(
                rule_id="r1",
                rule_description="rule 1",
                input_value=100.0,
                condition="x eq 100",
                interpretation="Neutral conditions",
            )
        )
        assert len(sig.evidence) == 1

    def test_signal_id_defaults(self) -> None:
        sig = MacroSignalSchema(
            indicator="DXY",
            dimension="Liquidity",
            direction=SignalDirection.NEUTRAL,
            strength=SignalStrength.WEAK,
            confidence=0.3,
        )
        assert sig.signal_id
        assert len(sig.signal_id) > 0

    def test_confidence_bounds(self) -> None:
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            MacroSignalSchema(
                indicator="DXY",
                dimension="Liquidity",
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.WEAK,
                confidence=1.5,  # > 1.0
            )

        with pytest.raises(pydantic.ValidationError):
            MacroSignalSchema(
                indicator="DXY",
                dimension="Liquidity",
                direction=SignalDirection.NEUTRAL,
                strength=SignalStrength.WEAK,
                confidence=-0.1,  # < 0.0
            )


class TestSignalSnapshot:
    """SignalSnapshot model."""

    def test_empty_snapshot(self) -> None:
        snap = SignalSnapshot()
        assert snap.count == 0
        assert snap.dimensions_covered == []
        assert snap.summary == ""

    def test_snapshot_with_signals(self) -> None:
        sig1 = MacroSignalSchema(
            indicator="DXY",
            dimension="Liquidity",
            direction=SignalDirection.BEARISH,
            strength=SignalStrength.MODERATE,
            confidence=0.7,
        )
        sig2 = MacroSignalSchema(
            indicator="VIX",
            dimension="Risk_Appetite",
            direction=SignalDirection.BEARISH,
            strength=SignalStrength.STRONG,
            confidence=0.9,
        )
        snap = SignalSnapshot(signals=[sig1, sig2])
        assert snap.count == 2
        assert "Liquidity" in snap.dimensions_covered
        assert "Risk_Appetite" in snap.dimensions_covered


class TestRuleType:
    """RuleType enum covers all planned rule types."""

    def test_threshold_exists(self) -> None:
        assert RuleType.THRESHOLD.value == "threshold"

    def test_future_types_exist(self) -> None:
        """Verify reserved rule types are defined (not yet implemented)."""
        assert RuleType.TREND.value == "trend"
        assert RuleType.MOMENTUM.value == "momentum"
        assert RuleType.SPREAD.value == "spread"
        assert RuleType.CORRELATION.value == "correlation"
        assert RuleType.REGIME.value == "regime"
