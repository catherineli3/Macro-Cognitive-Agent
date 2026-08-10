"""YahooCollector — Yahoo Finance data collector.

Implements CollectorInterface via the yfinance library.
Single responsibility: API call → JSON parsing → MacroDataSchema.

Prohibited: DB writes, analysis, LLM calls, data transformation.
"""

import asyncio
import random
from datetime import datetime, timezone

import yfinance as yf

from src.domain.macro_indicator import MacroIndicator
from src.interfaces.collector import CollectorInterface
from src.schemas.macro_data import MacroDataSchema
from src.shared.exceptions import CollectionError
from src.shared.logging import get_logger

logger = get_logger(__name__)

# Rate-limit Yahoo Finance requests: max 2 concurrent, with staggered delays.
_YAHOO_SEM = asyncio.Semaphore(2)


class YahooCollector(CollectorInterface):
    """Fetch macro-economic data from Yahoo Finance via the yfinance library.

    Usage:
        collector = YahooCollector()
        indicator = MacroIndicator(symbol="DXY", ...)
        data: MacroDataSchema = await collector.collect(indicator)
    """

    source_name: str = "Yahoo"

    # ── Public API ─────────────────────────────────────────────────

    async def collect(self, indicator: MacroIndicator) -> MacroDataSchema:
        """Fetch the latest observation for an indicator from Yahoo Finance.

        Uses asyncio.to_thread() to keep the event loop free
        (yfinance is a synchronous library).

        Raises:
            CollectionError: If the ticker is invalid, data is missing,
                             or the Yahoo API returns an unexpected response.
        """
        async with _YAHOO_SEM:
            # Stagger requests by 0.5-1.5s to avoid triggering rate limits
            await asyncio.sleep(random.uniform(0.5, 1.5))

            logger.info(
                "yahoo_collect_start",
                symbol=indicator.symbol,
                hypothesis_dimension=indicator.hypothesis_dimension.value,
            )

            try:
                raw = await asyncio.to_thread(self._fetch_raw, indicator.symbol)
            except Exception as exc:
                raise CollectionError(
                    f"Failed to fetch {indicator.symbol} from Yahoo: {exc}",
                    details={"symbol": indicator.symbol, "error": str(exc)},
                ) from exc

        schema = self._raw_to_schema(indicator, raw)
        logger.info(
            "yahoo_collect_done",
            symbol=indicator.symbol,
            value=schema.value,
            timestamp=schema.timestamp.isoformat(),
        )
        return schema

    async def health_check(self) -> bool:
        """Verify Yahoo Finance is reachable by querying a known ticker."""
        try:
            await self.collect(
                MacroIndicator(
                    symbol="^GSPC",
                    name="S&P 500 (health check)",
                    category="Equity",
                    frequency="Daily",
                    unit="Index",
                    source="Yahoo",
                    hypothesis_dimension="Risk_Appetite",  # type: ignore[arg-type]
                )
            )
            return True
        except Exception:
            return False

    # ── Private helpers ────────────────────────────────────────────

    @staticmethod
    def _fetch_raw(symbol: str) -> dict:
        """Synchronous fetch from yfinance — runs in executor thread.

        Returns a dict with normalized keys: date, open, high, low, close, volume.
        """
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")

        if hist.empty:
            raise CollectionError(
                f"No data returned for ticker '{symbol}'",
                details={"symbol": symbol},
            )

        latest = hist.iloc[-1]
        return {
            "date": latest.name.to_pydatetime(),
            "open": float(latest["Open"]),
            "high": float(latest["High"]),
            "low": float(latest["Low"]),
            "close": float(latest["Close"]),
            "volume": int(latest["Volume"]),
        }

    @staticmethod
    def _raw_to_schema(indicator: MacroIndicator, raw: dict) -> MacroDataSchema:
        """Map raw yfinance response to canonical MacroDataSchema."""
        return MacroDataSchema(
            symbol=indicator.symbol,
            timestamp=raw["date"],
            value=raw["close"],
            currency=indicator.currency,
            unit=indicator.unit,
            source="Yahoo",
        )
