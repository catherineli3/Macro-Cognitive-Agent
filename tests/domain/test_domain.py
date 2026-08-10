"""Tests — Domain models (MacroIndicator, MarketSource)."""

import pytest

from src.domain.macro_indicator import Frequency, HypothesisDimension, MacroIndicator
from src.domain.market_source import AuthType, MarketSource, SourceType


class TestHypothesisDimension:
    """All macro dimensions should be defined and immutable."""

    def test_all_dimensions_exist(self) -> None:
        assert HypothesisDimension.LIQUIDITY.value == "Liquidity"
        assert HypothesisDimension.CREDIT.value == "Credit"
        assert HypothesisDimension.GROWTH.value == "Growth"
        assert HypothesisDimension.RISK_APPETITE.value == "Risk_Appetite"
        assert HypothesisDimension.INFLATION.value == "Inflation"

    def test_dimension_is_hashable(self) -> None:
        """Enums should be usable as dict keys."""
        mapping = {HypothesisDimension.LIQUIDITY: ["DXY", "US10Y"]}
        assert mapping[HypothesisDimension.LIQUIDITY] == ["DXY", "US10Y"]


class TestMacroIndicator:
    """MacroIndicator — immutable metadata for a macro indicator."""

    @pytest.fixture
    def dxy(self) -> MacroIndicator:
        return MacroIndicator(
            symbol="DXY",
            name="US Dollar Index",
            category="Currency",
            frequency=Frequency.DAILY,
            unit="Index",
            source="Yahoo",
            hypothesis_dimension=HypothesisDimension.LIQUIDITY,
        )

    def test_create_indicator(self, dxy: MacroIndicator) -> None:
        assert dxy.symbol == "DXY"
        assert dxy.hypothesis_dimension == HypothesisDimension.LIQUIDITY

    def test_defaults(self) -> None:
        ind = MacroIndicator(
            symbol="TEST",
            name="Test",
            category="Test",
            frequency=Frequency.DAILY,
            source="Yahoo",
            hypothesis_dimension=HypothesisDimension.GROWTH,
        )
        assert ind.unit == "Index"
        assert ind.currency == "USD"
        assert ind.enabled is True

    def test_is_frozen(self, dxy: MacroIndicator) -> None:
        """Indicators are immutable at runtime."""
        with pytest.raises(Exception):  # pydantic ValidationError or FrozenInstanceError
            dxy.symbol = "NEW"  # type: ignore[misc]

    def test_repr(self, dxy: MacroIndicator) -> None:
        rep = repr(dxy)
        assert "DXY" in rep
        assert "Liquidity" in rep

    def test_all_frequency_values(self) -> None:
        assert Frequency.DAILY.value == "Daily"
        assert Frequency.WEEKLY.value == "Weekly"
        assert Frequency.MONTHLY.value == "Monthly"
        assert Frequency.QUARTERLY.value == "Quarterly"

    def test_description_optional(self) -> None:
        ind = MacroIndicator(
            symbol="VIX",
            name="Volatility Index",
            category="Volatility",
            frequency=Frequency.DAILY,
            source="Yahoo",
            hypothesis_dimension=HypothesisDimension.RISK_APPETITE,
            description="CBOE Volatility Index",
        )
        assert ind.description == "CBOE Volatility Index"

    def test_disabled_indicator(self) -> None:
        ind = MacroIndicator(
            symbol="OLD",
            name="Deprecated",
            category="Test",
            frequency=Frequency.DAILY,
            source="Yahoo",
            hypothesis_dimension=HypothesisDimension.GROWTH,
            enabled=False,
        )
        assert ind.enabled is False


class TestMarketSource:
    """MarketSource — immutable data source definition."""

    def test_create_yahoo_source(self) -> None:
        src = MarketSource(
            name="Yahoo",
            source_type=SourceType.LIBRARY,
            library_name="yfinance",
            enabled=True,
        )
        assert src.name == "Yahoo"
        assert src.source_type == SourceType.LIBRARY
        assert src.enabled is True

    def test_default_auth(self) -> None:
        src = MarketSource(
            name="TestSource",
            source_type=SourceType.REST_API,
            base_url="https://api.example.com",
        )
        assert src.auth_type == AuthType.NONE
        assert src.rate_limit_rpm == 60

    def test_is_frozen(self) -> None:
        src = MarketSource(
            name="FRED",
            source_type=SourceType.REST_API,
            base_url="https://api.example.com",
        )
        with pytest.raises(Exception):
            src.name = "NEW_NAME"  # type: ignore[misc]

    def test_repr(self) -> None:
        src = MarketSource(
            name="Bloomberg",
            source_type=SourceType.SDK,
            enabled=False,
        )
        rep = repr(src)
        assert "Bloomberg" in rep
        assert "disabled" in rep
