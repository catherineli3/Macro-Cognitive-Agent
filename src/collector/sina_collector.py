"""Sina Finance collector — Primary market data source for the macro pipeline.

Replaces Yahoo Finance as the market data collector.
Sina Finance API is freely accessible without API key and works from China.
"""

from __future__ import annotations

from datetime import UTC, datetime

import requests

from src.domain.macro_indicator import MacroIndicator
from src.interfaces.collector import CollectorInterface
from src.schemas.macro_data import MacroDataSchema, QualityFactor, QualityScore
from src.shared.exceptions import CollectionError
from src.shared.logging import get_logger

logger = get_logger(__name__)

# Sina code mapping: indicator_symbol -> sina_code
SINA_CODE_MAP: dict[str, str] = {
    "SPY": "gb_spy",  # S&P 500 ETF
    "QQQ": "gb_qqq",  # Nasdaq-100 ETF
    "IWM": "gb_iwm",  # Russell 2000 ETF
    "GLD": "gb_gld",  # Gold ETF → proxy for GC=F
    "USO": "gb_uso",  # WTI Oil ETF → proxy for CL=F
    "HYG": "gb_hyg",  # High Yield Bond ETF → proxy for HYG
    "LQD": "gb_lqd",  # Investment Grade Bond ETF → proxy for LQD
    "TLT": "gb_tlt",  # 20+ Year Treasury ETF → proxy for US10Y
    "SHY": "gb_shy",  # 1-3 Year Treasury ETF → proxy for US2Y
    "VIXY": "gb_vixy",  # VIX Short-Term Futures → proxy for ^VIX
    "NVDA": "gb_nvda",  # NVIDIA
    "SMH": "gb_smh",  # Semiconductor ETF → proxy for SOXX/SOXL
    "ASML": "gb_asml",  # ASML
    "TSM": "gb_tsm",  # TSMC
    "COPX": "gb_copx",  # Copper Miners ETF → proxy for HG=F
    "BND": "gb_bnd",  # Total Bond Market ETF
    "UUP": "gb_uup",  # Invesco DB USD Bullish Fund → proxy for DXY
}


def _fetch_sina_quote(sina_code: str) -> dict | None:
    """Fetch a single quote from Sina Finance. Returns dict or None."""
    try:
        r = requests.get(
            f"https://hq.sinajs.cn/list={sina_code}",
            headers={"Referer": "https://finance.sina.com.cn"},
            timeout=10,
        )
        text = r.text.strip()
        if not text or '=""' in text:
            return None

        # Parse: var hq_str_CODE="name,price,change%,time,..."
        inner = text.split('"')[1]
        parts = inner.split(",")

        if len(parts) < 4 or float(parts[1]) == 0:
            return None

        return {
            "name": parts[0],
            "price": float(parts[1]),
            "change_pct": float(parts[2]) if parts[2] else 0.0,
            "time": parts[3],
            "volume": float(parts[7]) if len(parts) > 7 and parts[7] else 0,
        }
    except Exception as exc:
        logger.warning("sina_fetch_failed | code=%s error=%s", sina_code, exc)
        return None


class SinaCollector(CollectorInterface):
    """Fetch market data from Sina Finance (free, no API key, works from China).

    Used as primary replacement for Yahoo Finance which is rate-limited
    in the user's network environment.

    Usage:
        collector = SinaCollector()
        indicator = MacroIndicator(symbol="SPY", ...)
        data = await collector.collect(indicator)
    """

    source_name: str = "Sina"

    async def collect(self, indicator: MacroIndicator) -> MacroDataSchema:
        """Fetch a market indicator from Sina Finance."""
        sina_code = SINA_CODE_MAP.get(indicator.symbol)
        if not sina_code:
            raise CollectionError(
                f"No Sina code mapping for {indicator.symbol}",
                details={"symbol": indicator.symbol},
            )

        logger.info(
            "sina_collect",
            symbol=indicator.symbol,
            sina_code=sina_code,
        )

        quote = _fetch_sina_quote(sina_code)
        if quote is None:
            raise CollectionError(
                f"Sina returned no data for {indicator.symbol}",
                details={"symbol": indicator.symbol, "sina_code": sina_code},
            )

        return MacroDataSchema(
            symbol=indicator.symbol,
            value=quote["price"],
            source="Sina",
            timestamp=datetime.now(UTC),
            quality=QualityScore(
                overall=0.90,
                factors={
                    QualityFactor.COMPLETENESS: 0.95,
                    QualityFactor.TIMELINESS: 0.95,
                    QualityFactor.CONSISTENCY: 0.85,
                    QualityFactor.OUTLIER: 0.80,
                    QualityFactor.DUPLICATE: 0.90,
                },
                flags=[
                    "sina_realtime",
                    f"code={sina_code}",
                    f"change_pct={quote['change_pct']:.2f}%",
                ],
            ),
            currency="USD",
            unit=indicator.unit,
        )

    async def health_check(self) -> bool:
        """Check Sina Finance API availability."""
        try:
            quote = _fetch_sina_quote("gb_spy")
            return quote is not None and quote["price"] > 0
        except Exception:
            return False

    @staticmethod
    def collect_sync(indicator: MacroIndicator) -> MacroDataSchema:
        """Synchronous version for use in sync pipeline flows."""
        sina_code = SINA_CODE_MAP.get(indicator.symbol)
        if not sina_code:
            raise CollectionError(
                f"No Sina code mapping for {indicator.symbol}",
                details={"symbol": indicator.symbol},
            )

        quote = _fetch_sina_quote(sina_code)
        if quote is None:
            raise CollectionError(
                f"Sina returned no data for {indicator.symbol}",
                details={"symbol": indicator.symbol, "sina_code": sina_code},
            )

        return MacroDataSchema(
            symbol=indicator.symbol,
            value=quote["price"],
            source="Sina",
            timestamp=datetime.now(UTC),
            quality=QualityScore(
                overall=0.90,
                factors={
                    QualityFactor.COMPLETENESS: 0.95,
                    QualityFactor.TIMELINESS: 0.95,
                    QualityFactor.CONSISTENCY: 0.85,
                    QualityFactor.OUTLIER: 0.80,
                    QualityFactor.DUPLICATE: 0.90,
                },
                flags=[
                    "sina_realtime",
                    f"code={sina_code}",
                    f"change_pct={quote['change_pct']:.2f}%",
                ],
            ),
            currency="USD",
            unit=indicator.unit,
        )
