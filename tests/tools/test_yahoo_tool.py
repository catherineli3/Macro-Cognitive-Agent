"""Tests for YahooMacroTool — Canonical Data Layer translation.

Tests the full path: yfinance raw data → MacroDataSchema (canonical).

Unit tests mock the yfinance call. Integration tests (marked 'network')
test against live Yahoo Finance — skipped by default in offline environments.
"""

import socket
from unittest.mock import patch

import pandas as pd
import pytest

from src.domain.tool import ToolResultStatus
from src.schemas.macro_data import MacroDataSchema
from src.tools.yahoo_tool import YahooMacroTool

# ── Helpers ──────────────────────────────────────────────────────────────


def _has_internet() -> bool:
    """Cheap connectivity check — resolves a well-known host."""
    try:
        s = socket.create_connection(("8.8.8.8", 53), timeout=2)
        s.close()
        return True
    except OSError:
        return False


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_mock_df():
    """Create a realistic yfinance-style DataFrame with 5 trading days."""
    dates = pd.date_range("2026-07-08", periods=5, freq="B", tz="UTC")
    return pd.DataFrame(
        {
            "Open": [104.0, 104.5, 105.0, 104.8, 105.3],
            "High": [105.0, 105.5, 106.0, 105.5, 106.2],
            "Low": [103.5, 104.0, 104.5, 104.0, 104.8],
            "Close": [104.5, 105.0, 104.8, 105.3, 106.0],
            "Volume": [10000, 12000, 11000, 13000, 15000],
            "Dividends": [0, 0, 0, 0, 0],
            "Stock Splits": [0, 0, 0, 0, 0],
        },
        index=dates,
    )


# ── Unit Tests ──────────────────────────────────────────────────────────


class TestYahooMacroToolInterface:
    """YahooMacroTool implements BaseTool contract."""

    def test_tool_name(self):
        tool = YahooMacroTool()
        assert tool.tool_name() == "YahooMacroTool"

    def test_capability(self):
        tool = YahooMacroTool()
        assert tool.capability() == "macro.yahoo"

    def test_is_base_tool(self):
        from src.tools.base import BaseTool

        tool = YahooMacroTool()
        assert isinstance(tool, BaseTool)


class TestYahooMacroToolCanonicalTranslation:
    """The core function: raw OHLCV → MacroDataSchema (Canonical Data Layer)."""

    def test_translates_df_to_canonical(self):
        """Each DataFrame row → one MacroDataSchema with canonical fields."""
        tool = YahooMacroTool()
        df = _make_mock_df()
        records = tool._to_canonical("^VIX", df)

        assert len(records) == 5
        for r in records:
            assert isinstance(r, MacroDataSchema)
            assert r.symbol == "^VIX"
            assert r.source == "Yahoo"
            assert r.currency == "USD"
            assert r.unit == "Price"
            assert r.timestamp.tzinfo is not None  # timezone-aware
            assert r.quality.overall == 0.95

    def test_canonical_fields_correct(self):
        """Verify specific field values from translation."""
        tool = YahooMacroTool()
        df = _make_mock_df()
        records = tool._to_canonical("DXY", df)

        # First record: Close=104.5
        assert records[0].value == 104.5
        # Fifth record: Close=106.0
        assert records[4].value == 106.0

    def test_no_raw_dataframe_in_output(self):
        """Canonical Data Layer contract: raw pandas DataFrames never reach output."""
        tool = YahooMacroTool()
        df = _make_mock_df()
        records = tool._to_canonical("DXY", df)

        for r in records:
            # Should be MacroDataSchema, not DataFrame rows or dicts
            assert isinstance(r, MacroDataSchema)
            # Should NOT contain raw OHLCV columns as dict keys
            assert hasattr(r, "symbol")
            assert hasattr(r, "value")
            assert hasattr(r, "source")


class TestYahooMacroToolInputValidation:
    """Input validation — missing/bad parameters."""

    @pytest.mark.asyncio
    async def test_missing_symbol(self):
        tool = YahooMacroTool()
        result = await tool.execute({})
        assert result.is_failed is True
        assert result.status == ToolResultStatus.FAILED
        assert "symbol" in result.error.lower()

    @pytest.mark.asyncio
    async def test_empty_symbol(self):
        tool = YahooMacroTool()
        result = await tool.execute({"symbol": ""})
        assert result.is_failed is True
        assert "symbol" in result.error.lower()


class TestYahooMacroToolExecution:
    """End-to-end execute() with mocked yfinance."""

    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        """Mocked yfinance → SUCCESS ToolResult with canonical data."""
        tool = YahooMacroTool()
        df = _make_mock_df()

        async def mock_fetch(symbol, period, interval):
            return df

        with patch.object(tool, "_fetch_history", side_effect=mock_fetch):
            result = await tool.execute({"symbol": "^VIX", "period": "1mo"})

        assert result.is_success is True
        assert result.status == ToolResultStatus.SUCCESS
        assert result.tool_name == "YahooMacroTool"
        assert "macro_data" in result.artifact
        assert len(result.artifact["macro_data"]) == 5
        assert result.latency_ms > 0

        # Verify canonical translation
        records = result.artifact["macro_data"]
        assert all(isinstance(r, MacroDataSchema) for r in records)

    @pytest.mark.asyncio
    async def test_empty_dataframe(self):
        """Empty response → FAILED ToolResult."""
        tool = YahooMacroTool()

        async def mock_fetch(symbol, period, interval):
            return pd.DataFrame()

        with patch.object(tool, "_fetch_history", side_effect=mock_fetch):
            result = await tool.execute({"symbol": "INVALID_SYMBOL"})

        assert result.is_failed is True
        assert "No data" in result.error

    @pytest.mark.asyncio
    async def test_network_error(self):
        """Network/API error → FAILED ToolResult (no exception leaked)."""
        tool = YahooMacroTool()

        async def mock_fetch(symbol, period, interval):
            raise ConnectionError("Network unreachable")

        with patch.object(tool, "_fetch_history", side_effect=mock_fetch):
            result = await tool.execute({"symbol": "^VIX"})

        assert result.is_failed is True
        assert result.status == ToolResultStatus.FAILED
        assert "ConnectionError" in result.error
        assert result.artifact == {}

    @pytest.mark.asyncio
    async def test_none_dataframe(self):
        """None response → FAILED ToolResult."""
        tool = YahooMacroTool()

        async def mock_fetch(symbol, period, interval):
            return None

        with patch.object(tool, "_fetch_history", side_effect=mock_fetch):
            result = await tool.execute({"symbol": "^VIX"})

        assert result.is_failed is True

    @pytest.mark.asyncio
    async def test_default_params(self):
        """Uses default period/interval when not provided."""
        tool = YahooMacroTool()
        df = _make_mock_df()
        called_params = {}

        async def mock_fetch(symbol, period, interval):
            called_params["symbol"] = symbol
            called_params["period"] = period
            called_params["interval"] = interval
            return df

        with patch.object(tool, "_fetch_history", side_effect=mock_fetch):
            await tool.execute({"symbol": "DXY"})

        assert called_params["symbol"] == "DXY"
        assert called_params["period"] == "1mo"
        assert called_params["interval"] == "1d"

    @pytest.mark.asyncio
    async def test_custom_params(self):
        """Custom period/interval are passed through."""
        tool = YahooMacroTool()
        df = _make_mock_df()
        called_params = {}

        async def mock_fetch(symbol, period, interval):
            called_params["period"] = period
            called_params["interval"] = interval
            return df

        with patch.object(tool, "_fetch_history", side_effect=mock_fetch):
            await tool.execute({"symbol": "DXY", "period": "6mo", "interval": "1wk"})

        assert called_params["period"] == "6mo"
        assert called_params["interval"] == "1wk"


# ── Integration Tests (Live API) ────────────────────────────────────────


@pytest.mark.external_api
class TestYahooMacroToolIntegration:
    """Live Yahoo Finance access — requires internet."""

    @pytest.mark.asyncio
    @pytest.mark.skipif("not _has_internet()", reason="No internet — skipping live Yahoo API test")
    async def test_live_fetch_returns_canonical_data(self):
        """Live fetch → ToolResult with MacroDataSchema artifacts."""
        tool = YahooMacroTool()
        result = await tool.execute({"symbol": "^VIX", "period": "5d", "interval": "1d"})

        assert result.is_success is True
        assert result.tool_name == "YahooMacroTool"
        assert result.latency_ms > 0
        assert "macro_data" in result.artifact

        records = result.artifact["macro_data"]
        assert len(records) > 0
        for r in records:
            assert isinstance(r, MacroDataSchema)
            assert r.symbol == "^VIX"
            assert r.source == "Yahoo"
            assert r.timestamp.tzinfo is not None

    @pytest.mark.asyncio
    @pytest.mark.skipif("not _has_internet()", reason="No internet — skipping live Yahoo API test")
    async def test_live_invalid_symbol(self):
        """Invalid symbol → FAILED with helpful error."""
        tool = YahooMacroTool()
        result = await tool.execute({"symbol": "XX_INVALID_XX", "period": "5d"})

        assert result.is_failed is True
        assert "No data" in result.error or "Failed" in result.error
