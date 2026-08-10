"""WorldBank API collector — Free macroeconomic indicators (no API key required).

World Bank Data API: https://api.worldbank.org/v2/
Rate limit: None documented, but be respectful (~5 req/sec).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import requests

from src.domain.macro_indicator import MacroIndicator
from src.interfaces.collector import CollectorInterface
from src.schemas.macro_data import MacroDataSchema, QualityFactor, QualityScore
from src.shared.exceptions import CollectionError
from src.shared.logging import get_logger

logger = get_logger(__name__)

# WorldBank indicator codes for US macro data
# (Latest available value is typically prior year)
WB_INDICATOR_MAP: Dict[str, str] = {
    "GDP":           "NY.GDP.MKTP.CD",      # GDP (current US$)
    "GDP_CAP":       "NY.GDP.PCAP.CD",      # GDP per capita
    "CPI":           "FP.CPI.TOTL.ZG",      # Inflation, consumer prices (annual %)
    "UNEMPLOYMENT":  "SL.UEM.TOTL.ZS",      # Unemployment, total (% of labor force)
    "TRADE_BALANCE": "NE.RSB.GNFS.ZS",      # Trade (% of GDP)
    "GFCF":          "NE.GDI.FTOT.ZS",      # Gross fixed capital formation (% GDP)
    "INDUSTRY":      "NV.IND.TOTL.ZS",      # Industry value added (% GDP)
    "EXPORTS":       "NE.EXP.GNFS.ZS",      # Exports (% GDP)
}

BASE_URL = "https://api.worldbank.org/v2"


def fetch_wb_indicator(indicator_code: str, per_page: int = 3) -> float:
    """Fetch the latest value for a WorldBank indicator for the US.

    Args:
        indicator_code: WorldBank indicator code (e.g., "NY.GDP.MKTP.CD")
        per_page: Number of records to fetch (default 3, to get latest)

    Returns:
        The latest non-null value, or raises CollectionError.
    """
    url = (
        f"{BASE_URL}/country/US/indicator/{indicator_code}"
        f"?format=json&per_page={per_page}"
    )
    resp = requests.get(url, timeout=30)
    if resp.status_code != 200:
        raise CollectionError(
            f"WorldBank API returned {resp.status_code}",
            details={"url": url, "status": resp.status_code},
        )

    data = resp.json()
    if not data or len(data) < 2 or data[1] is None:
        raise CollectionError(
            f"No data for indicator {indicator_code}",
            details={"code": indicator_code},
        )

    # Find the most recent non-null value
    records = data[1]
    for record in records:
        if record and record.get("value") is not None:
            return float(record["value"])

    raise CollectionError(
        f"All values null for {indicator_code}",
        details={"code": indicator_code},
    )


class WorldBankCollector(CollectorInterface):
    """Fetch macroeconomic data from the World Bank Data API.

    Usage:
        collector = WorldBankCollector()
        indicator = MacroIndicator(symbol="GDP", ...)
        data = await collector.collect(indicator)
    """

    source_name: str = "WorldBank"

    async def collect(self, indicator: MacroIndicator) -> MacroDataSchema:
        """Fetch a macro indicator from WorldBank."""
        wb_code = WB_INDICATOR_MAP.get(indicator.symbol, indicator.symbol)
        logger.info(
            "worldbank_collect", symbol=indicator.symbol, wb_code=wb_code,
        )

        try:
            value = fetch_wb_indicator(wb_code)
            return MacroDataSchema(
                symbol=indicator.symbol,
                value=value,
                source="WorldBank",
                timestamp=datetime.now(timezone.utc),
                quality=QualityScore(
                    overall=0.85,
                    factors={
                        QualityFactor.COMPLETENESS: 0.85,
                        QualityFactor.TIMELINESS: 0.7,
                        QualityFactor.CONSISTENCY: 0.9,
                        QualityFactor.OUTLIER: 0.8,
                        QualityFactor.DUPLICATE: 0.9,
                    },
                    flags=["annual_data", f"wb_code={wb_code}"],
                ),
                currency="USD",
                unit=indicator.unit,
            )
        except CollectionError:
            raise
        except Exception as exc:
            raise CollectionError(
                f"WorldBank collect failed for {indicator.symbol}: {exc}",
                details={"symbol": indicator.symbol, "error": str(exc)},
            ) from exc

    async def health_check(self) -> bool:
        """Check WorldBank API availability."""
        try:
            resp = requests.get(
                f"{BASE_URL}/country/US/indicator/NY.GDP.MKTP.CD?format=json&per_page=1",
                timeout=15,
            )
            return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def collect_sync(indicator: MacroIndicator) -> MacroDataSchema:
        """Synchronous version for use in sync pipeline flows."""
        wb_code = WB_INDICATOR_MAP.get(indicator.symbol, indicator.symbol)
        logger.info(
            "worldbank_collect_sync", symbol=indicator.symbol, wb_code=wb_code,
        )

        try:
            value = fetch_wb_indicator(wb_code)
            return MacroDataSchema(
                symbol=indicator.symbol,
                value=value,
                source="WorldBank",
                timestamp=datetime.now(timezone.utc),
                quality=QualityScore(
                    overall=0.85,
                    factors={
                        QualityFactor.COMPLETENESS: 0.85,
                        QualityFactor.TIMELINESS: 0.7,
                        QualityFactor.CONSISTENCY: 0.9,
                        QualityFactor.OUTLIER: 0.8,
                        QualityFactor.DUPLICATE: 0.9,
                    },
                    flags=["annual_data", f"wb_code={wb_code}"],
                ),
                currency="USD",
                unit=indicator.unit,
            )
        except CollectionError:
            raise
        except Exception as exc:
            raise CollectionError(
                f"WorldBank collect failed for {indicator.symbol}: {exc}",
                details={"symbol": indicator.symbol, "error": str(exc)},
            ) from exc
