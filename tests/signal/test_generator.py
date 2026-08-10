"""Tests for ThresholdSignalGenerator — generation, evidence, edge cases."""

import pytest

from src.domain.macro_indicator import MacroIndicator
from src.schemas.macro_data import MacroDataSchema
from src.schemas.signal import MacroSignalSchema, SignalDirection, SignalStrength
from src.signal.generator import ThresholdSignalGenerator
from src.signal.rule_engine import RuleEngine


@pytest.fixture
def generator() -> ThresholdSignalGenerator:
    return ThresholdSignalGenerator(RuleEngine())


class TestSignalGeneration:
    """Core signal generation logic."""

    @pytest.mark.asyncio
    async def test_generates_bearish_for_strong_dollar(
        self,
        generator: ThresholdSignalGenerator,
        dxy_indicator: MacroIndicator,
        sample_dxy_data_high: MacroDataSchema,
        sample_history: list[MacroDataSchema],
    ) -> None:
        signal = await generator.generate(dxy_indicator, sample_dxy_data_high, sample_history)
        assert signal.indicator == "DXY"
        assert signal.dimension == "Liquidity"
        assert signal.direction == SignalDirection.BEARISH
        assert signal.confidence >= 0.5
        assert len(signal.evidence) >= 1
        assert any("dxy_strong_dollar" in e.rule_id for e in signal.evidence)

    @pytest.mark.asyncio
    async def test_generates_bullish_for_weak_dollar(
        self,
        generator: ThresholdSignalGenerator,
        dxy_indicator: MacroIndicator,
        sample_dxy_data_low: MacroDataSchema,
    ) -> None:
        signal = await generator.generate(dxy_indicator, sample_dxy_data_low, [])
        assert signal.indicator == "DXY"
        assert signal.direction == SignalDirection.BULLISH
        assert any("dxy_weak_dollar" in e.rule_id for e in signal.evidence)

    @pytest.mark.asyncio
    async def test_no_rules_triggered_returns_neutral(
        self,
        generator: ThresholdSignalGenerator,
        dxy_indicator: MacroIndicator,
        sample_dxy_data_mid: MacroDataSchema,
    ) -> None:
        """DXY=102 triggers neither rule → NEUTRAL/weak."""
        signal = await generator.generate(dxy_indicator, sample_dxy_data_mid, [])
        assert signal.direction == SignalDirection.NEUTRAL
        assert signal.strength == SignalStrength.WEAK
        assert len(signal.evidence) == 0

    @pytest.mark.asyncio
    async def test_signal_carries_data_timestamp(
        self,
        generator: ThresholdSignalGenerator,
        dxy_indicator: MacroIndicator,
        sample_dxy_data_high: MacroDataSchema,
    ) -> None:
        signal = await generator.generate(dxy_indicator, sample_dxy_data_high, [])
        assert signal.data_timestamp is not None
        assert signal.data_timestamp == sample_dxy_data_high.timestamp

    @pytest.mark.asyncio
    async def test_evidence_contains_interpretation(
        self,
        generator: ThresholdSignalGenerator,
        dxy_indicator: MacroIndicator,
        sample_dxy_data_high: MacroDataSchema,
    ) -> None:
        signal = await generator.generate(dxy_indicator, sample_dxy_data_high, [])
        for ev in signal.evidence:
            assert ev.interpretation, f"Missing interpretation for {ev.rule_id}"
            assert len(ev.interpretation) > 10  # meaningful text

    @pytest.mark.asyncio
    async def test_signal_id_is_unique(
        self,
        generator: ThresholdSignalGenerator,
        dxy_indicator: MacroIndicator,
        sample_dxy_data_high: MacroDataSchema,
    ) -> None:
        s1 = await generator.generate(dxy_indicator, sample_dxy_data_high, [])
        s2 = await generator.generate(dxy_indicator, sample_dxy_data_high, [])
        assert s1.signal_id != s2.signal_id

    @pytest.mark.asyncio
    async def test_source_name(self, generator: ThresholdSignalGenerator) -> None:
        assert generator.source_name() == "ThresholdSignalGenerator"


class TestSignalEdgeCases:
    """Edge case handling."""

    @pytest.mark.asyncio
    async def test_empty_history_still_generates(
        self,
        generator: ThresholdSignalGenerator,
        dxy_indicator: MacroIndicator,
        sample_dxy_data_high: MacroDataSchema,
    ) -> None:
        """Empty history should not block signal generation."""
        signal = await generator.generate(dxy_indicator, sample_dxy_data_high, [])
        assert signal.indicator == "DXY"
        assert len(signal.evidence) >= 1

    @pytest.mark.asyncio
    async def test_indicator_without_rules_returns_neutral(self, generator: ThresholdSignalGenerator) -> None:
        """Indicator with no rules → NEUTRAL/weak, no evidence."""
        from src.domain.macro_indicator import Frequency, HypothesisDimension
        from datetime import datetime, timezone

        indicator = MacroIndicator(
            symbol="NO_RULES",
            name="No Rules Indicator",
            category="Test",
            frequency=Frequency.DAILY,
            unit="Index",
            source="Test",
            hypothesis_dimension=HypothesisDimension.GROWTH,
        )
        data = MacroDataSchema(
            symbol="NO_RULES",
            timestamp=datetime(2026, 7, 13, tzinfo=timezone.utc),
            value=100.0,
            source="Test",
        )
        signal = await generator.generate(indicator, data, [])
        assert signal.direction == SignalDirection.NEUTRAL
        assert len(signal.evidence) == 0

    @pytest.mark.asyncio
    async def test_vix_generation(
        self,
        generator: ThresholdSignalGenerator,
        vix_indicator: MacroIndicator,
        sample_vix_data_high: MacroDataSchema,
    ) -> None:
        signal = await generator.generate(vix_indicator, sample_vix_data_high, [])
        assert signal.indicator == "^VIX"
        assert signal.dimension == "Risk_Appetite"
        assert signal.direction == SignalDirection.BEARISH
        assert any("vix_elevated" in e.rule_id for e in signal.evidence)
