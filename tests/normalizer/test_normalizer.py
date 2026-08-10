"""Tests — Normalizer module (DataNormalizer).

Covers canonicalization:
    - Symbol uppercase
    - String trimming
    - Source normalization
    - Value preservation (never altered)
"""

from datetime import datetime, timezone

import pytest

from src.normalizer.normalizer import DataNormalizer
from src.schemas.macro_data import MacroDataSchema


@pytest.fixture
def normalizer() -> DataNormalizer:
    return DataNormalizer()


@pytest.fixture
def sample_data() -> MacroDataSchema:
    return MacroDataSchema(
        symbol=" dxy ",
        timestamp=datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc),
        value=104.5,
        currency=" usd ",
        unit=" Index ",
        source=" yahoo ",
    )


class TestNormalizer:
    """DataNormalizer — mechanical canonicalization only."""

    def test_symbol_uppercased(self, normalizer: DataNormalizer, sample_data: MacroDataSchema) -> None:
        result = normalizer.normalize(sample_data)
        assert result.symbol == "DXY"

    def test_symbol_stripped(self, normalizer: DataNormalizer) -> None:
        data = MacroDataSchema(
            symbol="  US10Y  ",
            timestamp=datetime(2026, 7, 13, tzinfo=timezone.utc),
            value=4.25,
            source="Yahoo",
        )
        result = normalizer.normalize(data)
        assert result.symbol == "US10Y"

    def test_currency_stripped_and_uppered(self, normalizer: DataNormalizer, sample_data: MacroDataSchema) -> None:
        result = normalizer.normalize(sample_data)
        assert result.currency == "USD"

    def test_unit_stripped(self, normalizer: DataNormalizer, sample_data: MacroDataSchema) -> None:
        result = normalizer.normalize(sample_data)
        assert result.unit == "Index"

    def test_source_titlecased(self, normalizer: DataNormalizer, sample_data: MacroDataSchema) -> None:
        result = normalizer.normalize(sample_data)
        assert result.source == "Yahoo"

    def test_value_preserved(self, normalizer: DataNormalizer, sample_data: MacroDataSchema) -> None:
        """CRITICAL: Normalizer must never alter the numeric value."""
        result = normalizer.normalize(sample_data)
        assert result.value == 104.5

    def test_timestamp_preserved(self, normalizer: DataNormalizer, sample_data: MacroDataSchema) -> None:
        result = normalizer.normalize(sample_data)
        assert result.timestamp == sample_data.timestamp

    def test_quality_preserved(self, normalizer: DataNormalizer, sample_data: MacroDataSchema) -> None:
        result = normalizer.normalize(sample_data)
        assert result.quality.overall == sample_data.quality.overall

    def test_idempotent(self, normalizer: DataNormalizer, sample_data: MacroDataSchema) -> None:
        """Normalization should be idempotent — applying twice gives same result."""
        first = normalizer.normalize(sample_data)
        second = normalizer.normalize(first)
        assert first.symbol == second.symbol
        assert first.value == second.value

    def test_source_with_hyphen(self, normalizer: DataNormalizer) -> None:
        data = MacroDataSchema(
            symbol="HYG",
            timestamp=datetime(2026, 7, 13, tzinfo=timezone.utc),
            value=75.0,
            source="yahoo-finance",
        )
        result = normalizer.normalize(data)
        assert result.source == "Yahoo-Finance"

    def test_negative_value_preserved(self, normalizer: DataNormalizer) -> None:
        """Negative values may pass validation for some indicators;
        Normalizer should never alter them."""
        data = MacroDataSchema(
            symbol="US2Y",
            timestamp=datetime(2026, 7, 13, tzinfo=timezone.utc),
            value=-0.05,
            source="Yahoo",
        )
        result = normalizer.normalize(data)
        assert result.value == -0.05
