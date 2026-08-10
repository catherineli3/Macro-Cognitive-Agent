"""Tests — Collector module (YahooCollector).

Covers:
    - YahooCollector creation
    - _raw_to_schema mapping
    - Health check interface
    - Source name property
"""

from datetime import datetime, timezone

import pytest

from src.collector.yahoo import YahooCollector
from src.domain.macro_indicator import Frequency, HypothesisDimension, MacroIndicator


@pytest.fixture
def collector() -> YahooCollector:
    return YahooCollector()


@pytest.fixture
def dxy_indicator() -> MacroIndicator:
    return MacroIndicator(
        symbol="DXY",
        name="US Dollar Index",
        category="Currency",
        frequency=Frequency.DAILY,
        unit="Index",
        source="Yahoo",
        hypothesis_dimension=HypothesisDimension.LIQUIDITY,
    )


class TestYahooCollector:
    """YahooCollector — interface compliance and mapping."""

    def test_source_name(self, collector: YahooCollector) -> None:
        assert collector.source_name == "Yahoo"

    def test_raw_to_schema_mapping(self, collector: YahooCollector, dxy_indicator: MacroIndicator) -> None:
        """Verify the internal mapping from raw dict to MacroDataSchema."""
        raw = {
            "date": datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc),
            "open": 104.0,
            "high": 105.0,
            "low": 103.5,
            "close": 104.5,
            "volume": 100000,
        }
        schema = collector._raw_to_schema(dxy_indicator, raw)

        assert schema.symbol == "DXY"
        assert schema.value == 104.5  # close price
        assert schema.source == "Yahoo"
        assert schema.currency == "USD"
        assert schema.unit == "Index"

    @pytest.mark.asyncio
    @pytest.mark.external_api  # Depends on Yahoo Finance — may be rate-limited
    async def test_collect_dxy(self, collector: YahooCollector, dxy_indicator: MacroIndicator) -> None:
        """Integration test: fetch DXY from Yahoo Finance.

        Note: Yahoo Finance API may rate-limit. If this test fails with
        YFRateLimitError, it's an infrastructure issue, not a code bug.
        """
        from src.shared.exceptions import CollectionError

        try:
            result = await collector.collect(dxy_indicator)
        except CollectionError as exc:
            if "Rate limited" in str(exc) or "Too Many Requests" in str(exc):
                pytest.skip("Yahoo Finance rate limited — skipping external API test")
            raise

        assert result.symbol == "DXY"
        assert isinstance(result.value, float)
        assert result.value > 0  # DXY is always positive
        assert result.source == "Yahoo"
        assert result.timestamp.tzinfo is not None

    @pytest.mark.asyncio
    async def test_health_check(self, collector: YahooCollector) -> None:
        """Health check should be able to reach Yahoo."""
        ok = await collector.health_check()
        # May fail if Yahoo is unreachable, but should not raise
        assert isinstance(ok, bool)

    @pytest.mark.asyncio
    async def test_collect_invalid_ticker(self, collector: YahooCollector) -> None:
        """Invalid ticker should raise CollectionError."""
        from src.shared.exceptions import CollectionError

        bad = MacroIndicator(
            symbol="ZZZZZZZZZZ_INVALID",
            name="Invalid",
            category="Test",
            frequency=Frequency.DAILY,
            source="Yahoo",
            hypothesis_dimension=HypothesisDimension.GROWTH,
        )
        with pytest.raises(CollectionError):
            await collector.collect(bad)
