from __future__ import annotations

"""YahooMacroTool — Retrieve macro market data from Yahoo Finance.

Sprint 5 design:
    YahooMacroTool is the reference implementation of the Tool Layer.
    It demonstrates:

    1. Async external API access (via yfinance in a thread executor)
    2. Raw response → canonical schema translation (Canonical Data Layer)
    3. Graceful error handling (FAILED ToolResult, no exceptions leaked)

    The tool:
      - Retrieves historical OHLCV data for a given symbol
      - Translates each data point into MacroDataSchema (Sprint 1 canonical format)
      - Returns ToolResult with named "macro_data" artifact

    Input:
        {
            "symbol": "^VIX",       # Yahoo Finance ticker (required)
            "period": "1mo",        # Data period (optional, default "1mo")
            "interval": "1d",       # Bar interval (optional, default "1d")
        }

    Output (ToolResult.artifact):
        {
            "macro_data": [MacroDataSchema, ...]   # One per trading day
        }

    Out of scope:
        - Signal generation
        - Hypothesis generation
        - Database operations
        - Multi-symbol batching
"""

import asyncio
import time
from datetime import datetime, timezone

import pandas as pd

from src.domain.tool import ToolResultStatus
from src.schemas.macro_data import MacroDataSchema, QualityScore
from src.schemas.tool import ToolResult
from src.shared.logging import get_logger
from src.tools.base import BaseTool

logger = get_logger(__name__)

# Default lookback period and interval
DEFAULT_PERIOD = "1mo"
DEFAULT_INTERVAL = "1d"


class YahooMacroTool(BaseTool):
    """Retrieve macro market data from Yahoo Finance as canonical MacroDataSchema.

    This is a Tool. It:
      - Talks to Yahoo Finance (external system)
      - Translates raw OHLCV → MacroDataSchema (canonical format)
      - Returns ToolResult — never raw DataFrames or dicts

    The rest of the Agent never knows that Yahoo Finance was involved.
    It only sees the standardized MacroDataSchema objects that land in
    ExecutionContext.artifacts["macro_data"].
    """

    def tool_name(self) -> str:
        return "YahooMacroTool"

    def capability(self) -> str:
        return "macro.yahoo"

    async def execute(self, input_data: dict) -> ToolResult:
        """Fetch market data from Yahoo Finance and return canonical artifacts.

        Args:
            input_data: {"symbol": str, "period"?: str, "interval"?: str}

        Returns:
            ToolResult with artifact={"macro_data": [MacroDataSchema, ...]}
            or FAILED if the external call fails.
        """
        start_time = time.perf_counter()

        # ── Validate input ───────────────────────────────────────────────
        symbol = input_data.get("symbol", "")
        if not symbol:
            return self._fail(start_time, "Missing required parameter: 'symbol'")

        period = input_data.get("period", DEFAULT_PERIOD)
        interval = input_data.get("interval", DEFAULT_INTERVAL)

        logger.debug(
            "yahoo_fetch_start symbol=%s period=%s interval=%s",
            symbol, period, interval,
        )

        # ── Fetch raw data ───────────────────────────────────────────────
        try:
            raw_df = await self._fetch_history(symbol, period, interval)
        except Exception as exc:
            return self._fail(
                start_time,
                f"Yahoo Finance fetch failed for symbol='{symbol}': {type(exc).__name__}: {exc}",
            )

        if raw_df is None or raw_df.empty:
            return self._fail(
                start_time,
                f"No data returned from Yahoo Finance for symbol='{symbol}' "
                f"(period={period}, interval={interval}). Check the symbol is valid.",
            )

        # ── Translate: raw DataFrame → canonical MacroDataSchema ─────────
        # This is the Canonical Data Layer: the Agent never sees the DataFrame.
        macro_data = self._to_canonical(symbol, raw_df)
        latency = (time.perf_counter() - start_time) * 1000

        logger.info(
            "yahoo_fetch_done symbol=%s records=%d latency_ms=%.1f",
            symbol, len(macro_data), latency,
        )

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            tool_name=self.tool_name(),
            artifact={"macro_data": macro_data},
            latency_ms=round(latency, 2),
        )

    # ── Private: External Access ─────────────────────────────────────────

    async def _fetch_history(
        self, symbol: str, period: str, interval: str
    ) -> "pd.DataFrame | None":
        """Fetch OHLCV history from Yahoo Finance via yfinance.

        Runs the synchronous yfinance call in a thread executor to avoid
        blocking the async event loop.

        Args:
            symbol: Yahoo Finance ticker (e.g., "^VIX", "DX-Y.NYB").
            period: Data lookback (e.g., "1mo", "3mo", "1y").
            interval: Bar size (e.g., "1d", "1wk", "1h").

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume.
            Returns None if an error occurs.
        """
        try:
            loop = asyncio.get_running_loop()
            df = await loop.run_in_executor(
                None,
                _yfinance_download,
                symbol, period, interval,
            )
            return df
        except Exception:
            raise

    # ── Private: Canonical Translation ───────────────────────────────────

    def _to_canonical(
        self, symbol: str, df: "pd.DataFrame"
    ) -> list[MacroDataSchema]:
        """Translate raw yfinance DataFrame rows into MacroDataSchema objects.

        Each row (trading day) becomes one MacroDataSchema with:
          - value = closing price (primary observation)
          - metadata stored in the schema as accessible fields

        The canonical schema enforces:
          - Timezone-aware timestamps (UTC)
          - Standardized source label ("Yahoo")
          - Quality scoring (default acceptable)
        """
        records: list[MacroDataSchema] = []

        for timestamp_idx, row in df.iterrows():
            # Ensure timezone-aware timestamp
            ts = timestamp_idx
            if hasattr(ts, "tzinfo") and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            elif not hasattr(ts, "tzinfo"):
                ts = pd.Timestamp(ts).tz_localize(timezone.utc)

            # Map OHLCV fields for the canonical record
            close_val = float(row["Close"]) if "Close" in row else float(row["Adj Close"])
            volume_val = int(row["Volume"]) if "Volume" in row and not pd.isna(row["Volume"]) else 0

            record = MacroDataSchema(
                symbol=symbol,
                timestamp=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
                value=close_val,
                currency="USD",
                unit="Price",
                source="Yahoo",
                quality=QualityScore(overall=0.95),
            )
            records.append(record)

        return records

    # ── Private: Error Result ────────────────────────────────────────────

    def _fail(self, start_time: float, error_msg: str) -> ToolResult:
        """Build a FAILED ToolResult with latency."""
        latency = (time.perf_counter() - start_time) * 1000
        logger.warning("yahoo_tool_failed error=%s", error_msg)
        return ToolResult(
            status=ToolResultStatus.FAILED,
            tool_name=self.tool_name(),
            artifact={},
            latency_ms=round(latency, 2),
            error=error_msg,
        )


# ── Module-level helper (avoid lambda in executor) ───────────────────────


def _yfinance_download(symbol: str, period: str, interval: str) -> "pd.DataFrame":
    """Synchronous yfinance download — designed for run_in_executor.

    Separated as a module-level function because lambdas and local
    functions cannot be safely pickled for ProcessPoolExecutor.
    """
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    return df
