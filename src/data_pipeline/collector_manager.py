"""CollectorManager — unified multi-source data collection.

Manages all data source collectors behind a single interface.
Current sources: Yahoo Finance, FRED, World Bank.
Extensible: add IMF, ECB, BLS, Treasury without changing main pipeline.

Interface:
    manager = CollectorManager()
    data = await manager.collect()  # → list[MacroDataSchema]
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from src.collector.sina_collector import SinaCollector
from src.collector.worldbank import WorldBankCollector, WB_INDICATOR_MAP
from src.collector.yahoo import YahooCollector
from src.domain.macro_indicator import Frequency, HypothesisDimension, MacroIndicator
from src.schemas.macro_data import MacroDataSchema, QualityFactor, QualityScore
from src.shared.logging import get_logger

logger = get_logger(__name__)

# ── Indicator Registry ──────────────────────────────────────────────────────
# Maps indicator symbols to their MacroIndicator definitions.

_INDICATOR_REGISTRY: list[MacroIndicator] = [
    # ── Dollar / Liquidity ───────────────────────────────────────────────
    MacroIndicator(
        symbol="UUP", name="DXY", category="Currency",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.LIQUIDITY,
        description="Invesco DB USD Bullish ETF (proxy for US Dollar Index)",
    ),
    MacroIndicator(
        symbol="TLT", name="US10Y", category="Rates",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.LIQUIDITY,
        description="iShares 20+ Year Treasury ETF (proxy for US 10-Year Yield)",
    ),
    MacroIndicator(
        symbol="SHY", name="US2Y", category="Rates",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.LIQUIDITY,
        description="iShares 1-3 Year Treasury ETF (proxy for US 2-Year Yield)",
    ),
    # ── Credit ───────────────────────────────────────────────────────────
    MacroIndicator(
        symbol="HYG", name="HYG", category="Credit",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.CREDIT,
        description="iShares iBoxx High Yield Corporate Bond ETF",
    ),
    MacroIndicator(
        symbol="LQD", name="LQD", category="Credit",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.CREDIT,
        description="iShares iBoxx Investment Grade Corporate Bond ETF",
    ),
    # ── Risk / Volatility ────────────────────────────────────────────────
    MacroIndicator(
        symbol="VIXY", name="VIX", category="Volatility",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.RISK_APPETITE,
        description="VIX Short-Term Futures ETF (proxy for CBOE VIX)",
    ),
    # ── Commodities ──────────────────────────────────────────────────────
    MacroIndicator(
        symbol="GLD", name="Gold", category="Commodities",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.INFLATION,
        description="SPDR Gold Trust ETF (proxy for Gold Futures)",
    ),
    MacroIndicator(
        symbol="COPX", name="Copper", category="Commodities",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.GROWTH,
        description="Global X Copper Miners ETF (proxy for Copper Futures)",
    ),
    MacroIndicator(
        symbol="USO", name="Oil", category="Commodities",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.INFLATION,
        description="United States Oil Fund ETF (proxy for WTI Crude)",
    ),
    # ── Equity ───────────────────────────────────────────────────────────
    MacroIndicator(
        symbol="SPY", name="SP500", category="Equity",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.RISK_APPETITE,
        description="SPDR S&P 500 ETF",
    ),
    MacroIndicator(
        symbol="QQQ", name="Nasdaq", category="Equity",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.RISK_APPETITE,
        description="Invesco QQQ Trust (Nasdaq-100)",
    ),
    MacroIndicator(
        symbol="IWM", name="Russell", category="Equity",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.GROWTH,
        description="iShares Russell 2000 ETF (Small Cap)",
    ),
    # ── AI Cycle ─────────────────────────────────────────────────────────
    MacroIndicator(
        symbol="NVDA", name="NVDA", category="Equity",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.AI_CAPEX,
        description="NVIDIA — AI GPU leader",
    ),
    MacroIndicator(
        symbol="SMH", name="Semiconductor", category="Equity",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.AI_CAPEX,
        description="VanEck Semiconductor ETF",
    ),
    MacroIndicator(
        symbol="ASML", name="ASML", category="Equity",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.AI_CAPEX,
        description="ASML — Lithography equipment leader",
    ),
    MacroIndicator(
        symbol="TSM", name="TSMC", category="Equity",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.AI_CAPEX,
        description="Taiwan Semiconductor — Advanced foundry",
    ),
    # ── Bond Market ──────────────────────────────────────────────────────
    MacroIndicator(
        symbol="BND", name="Bond_Market", category="Fixed_Income",
        frequency=Frequency.DAILY, unit="Price", source="Sina",
        hypothesis_dimension=HypothesisDimension.CREDIT,
        description="Vanguard Total Bond Market ETF",
    ),
    # ── WorldBank Macro Indicators (free, no API key) ────────────────────
    MacroIndicator(
        symbol="GDP", name="GDP_USD", category="Macro",
        frequency=Frequency.ANNUAL, unit="USD", source="WorldBank",
        hypothesis_dimension=HypothesisDimension.GROWTH,
        description="US GDP (current USD) — World Bank",
    ),
    MacroIndicator(
        symbol="CPI", name="CPI_YoY", category="Macro",
        frequency=Frequency.ANNUAL, unit="Percent", source="WorldBank",
        hypothesis_dimension=HypothesisDimension.INFLATION,
        description="US Inflation, consumer prices (annual %) — World Bank",
    ),
    MacroIndicator(
        symbol="UNEMPLOYMENT", name="Unemployment_Rate", category="Macro",
        frequency=Frequency.ANNUAL, unit="Percent", source="WorldBank",
        hypothesis_dimension=HypothesisDimension.EMPLOYMENT,
        description="US Unemployment, total (% of labor force) — World Bank",
    ),
    MacroIndicator(
        symbol="TRADE_BALANCE", name="Trade_Balance", category="Macro",
        frequency=Frequency.ANNUAL, unit="Percent", source="WorldBank",
        hypothesis_dimension=HypothesisDimension.GROWTH,
        description="US Trade (% of GDP) — World Bank",
    ),
]


class CollectorManager:
    """Unified data collection across all source adapters.

    Responsibilities:
        1. Route each indicator to the correct collector.
        2. Handle per-source failures gracefully (log, continue).
        3. Attach quality metadata to every data point.
        4. Return a unified list[MacroDataSchema].

    Usage:
        manager = CollectorManager()
        data = await manager.collect()           # All indicators
        data = await manager.collect(for_dimension="Liquidity")
    """

    def __init__(self, sina_collector: Optional[SinaCollector] = None,
                 yahoo_collector: Optional[YahooCollector] = None,
                 worldbank_collector: Optional[WorldBankCollector] = None) -> None:
        self._sina = sina_collector or SinaCollector()
        self._yahoo = yahoo_collector or YahooCollector()
        self._worldbank = worldbank_collector or WorldBankCollector()
        self._source_stats: dict[str, int] = {"success": 0, "failed": 0}

    # ── Public API ──────────────────────────────────────────────────────────

    async def collect_async(
        self,
        for_dimension: Optional[str] = None,
        indicators: Optional[list[str]] = None,
    ) -> list[MacroDataSchema]:
        """Collect all registered indicators asynchronously.

        Args:
            for_dimension: Optional filter by HypothesisDimension name.
            indicators: Optional explicit list of indicator names to collect.

        Returns:
            List of MacroDataSchema objects with attached quality metadata.
        """
        registry = self._filter_registry(for_dimension, indicators)
        logger.info(
            "collector_manager_collect | total_indicators=%d dimension=%s",
            len(registry),
            for_dimension or "all",
        )

        # Collect all indicators concurrently
        tasks = [self._collect_single(indicator) for indicator in registry]
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[MacroDataSchema] = []
        failed: list[str] = []

        for indicator, result in zip(registry, results_raw):
            if isinstance(result, Exception):
                logger.warning(
                    "collector_manager_failed | indicator=%s source=%s error=%s",
                    indicator.name, indicator.source, result,
                )
                failed.append(indicator.name)
                self._source_stats["failed"] += 1
                results.append(self._degraded_placeholder(indicator, str(result)))
            elif result is not None:
                results.append(result)
                self._source_stats["success"] += 1
            else:
                failed.append(indicator.name)
                self._source_stats["failed"] += 1
                results.append(self._degraded_placeholder(indicator, "no_data"))

        if failed:
            logger.warning(
                "collector_manager_partial_failure | failed=%d/%d indicators=%s",
                len(failed), len(registry), failed,
            )

        logger.info(
            "collector_manager_done | collected=%d failed=%d",
            len(results), len(failed),
        )
        return results

    def collect(
        self,
        for_dimension: Optional[str] = None,
        indicators: Optional[list[str]] = None,
    ) -> list[MacroDataSchema]:
        """Synchronous sequential collection with rate-limit delays.

        Avoids asyncio event-loop issues on Windows by running requests
        one at a time with 1-2s pauses between Yahoo calls.
        """
        import time
        import random

        registry = self._filter_registry(for_dimension, indicators)
        logger.info(
            "collector_manager_collect | total_indicators=%d dimension=%s",
            len(registry),
            for_dimension or "all",
        )

        results: list[MacroDataSchema] = []
        failed: list[str] = []
        yahoo_count = 0

        for indicator in registry:
            if indicator.source == "Yahoo":
                yahoo_count += 1
                # Stagger Yahoo requests: delay 3-6s between each to avoid rate limiting
                if yahoo_count > 1:
                    time.sleep(random.uniform(3.0, 6.0))
            elif indicator.source == "Sina":
                # Small stagger between Sina requests to be polite
                time.sleep(random.uniform(0.3, 0.8))

            try:
                if indicator.source == "Yahoo":
                    # Call yfinance synchronously (it's already sync)
                    raw = self._yahoo._fetch_raw(indicator.symbol)
                    schema = self._yahoo._raw_to_schema(indicator, raw)
                    results.append(schema)
                    self._source_stats["success"] += 1
                    logger.info(
                        "yahoo_collect_done | symbol=%s value=%.2f",
                        indicator.symbol, schema.value,
                    )
                elif indicator.source == "Sina":
                    schema = SinaCollector.collect_sync(indicator)
                    results.append(schema)
                    self._source_stats["success"] += 1
                    logger.info(
                        "sina_collect_done | symbol=%s value=%.2f",
                        indicator.symbol, schema.value,
                    )
                elif indicator.source == "WorldBank":
                    time.sleep(random.uniform(0.5, 1.0))
                    schema = WorldBankCollector.collect_sync(indicator)
                    results.append(schema)
                    self._source_stats["success"] += 1
                    logger.info(
                        "worldbank_collect_done | symbol=%s value=%.2f",
                        indicator.symbol, schema.value,
                    )
                else:
                    logger.warning(
                        "collector_not_implemented | source=%s indicator=%s",
                        indicator.source, indicator.name,
                    )
                    failed.append(indicator.name)
                    self._source_stats["failed"] += 1
                    results.append(self._degraded_placeholder(indicator, "not_implemented"))
            except Exception as exc:
                logger.warning(
                    "collector_manager_failed | indicator=%s source=%s error=%s",
                    indicator.name, indicator.source, str(exc)[:120],
                )
                failed.append(indicator.name)
                self._source_stats["failed"] += 1
                results.append(self._degraded_placeholder(indicator, str(exc)[:120]))

        if failed:
            logger.warning(
                "collector_manager_partial_failure | failed=%d/%d indicators=%s",
                len(failed), len(registry), failed,
            )

        logger.info(
            "collector_manager_done | collected=%d failed=%d",
            len(results) - len(failed), len(failed),
        )
        return results

    def get_stats(self) -> dict:
        """Return collection statistics for the current session."""
        return dict(self._source_stats)

    def registered_indicators(self) -> list[str]:
        """Return all registered indicator names."""
        return [ind.name for ind in _INDICATOR_REGISTRY]

    def dimensions_covered(self) -> list[str]:
        """Return all macro dimensions with at least one registered indicator."""
        return sorted(set(ind.hypothesis_dimension.value for ind in _INDICATOR_REGISTRY))

    # ── Internal ────────────────────────────────────────────────────────────

    def _filter_registry(
        self,
        for_dimension: Optional[str],
        indicators: Optional[list[str]],
    ) -> list[MacroIndicator]:
        """Apply dimension and indicator filters to the registry."""
        registry = list(_INDICATOR_REGISTRY)
        if for_dimension:
            registry = [
                ind for ind in registry
                if ind.hypothesis_dimension.value.lower() == for_dimension.lower()
            ]
        if indicators:
            names = [n.upper() for n in indicators]
            registry = [ind for ind in registry if ind.name.upper() in names]
        return registry

    async def _collect_single(self, indicator: MacroIndicator) -> Optional[MacroDataSchema]:
        """Collect a single indicator from its designated source."""
        source = indicator.source

        if source == "Sina":
            return await self._sina.collect(indicator)
        if source == "Yahoo":
            return await self._yahoo.collect(indicator)
        if source == "WorldBank":
            return await self._worldbank.collect(indicator)

        logger.warning(
            "collector_not_implemented | source=%s indicator=%s",
            source, indicator.name,
        )
        return None

    def _degraded_placeholder(
        self, indicator: MacroIndicator, error: str
    ) -> MacroDataSchema:
        """Create a degraded-quality placeholder when collection fails."""
        return MacroDataSchema(
            symbol=indicator.name,
            timestamp=datetime.now(timezone.utc),
            value=0.0,  # Placeholder value — marked as low quality
            source=indicator.source,
            quality=QualityScore(
                overall=0.1,
                factors={
                    QualityFactor.COMPLETENESS: 0.1,
                    QualityFactor.TIMELINESS: 0.1,
                    QualityFactor.CONSISTENCY: 0.1,
                    QualityFactor.OUTLIER: 0.5,
                    QualityFactor.DUPLICATE: 0.5,
                },
                flags=[f"collection_failed: {error[:80]}", f"dimension={indicator.hypothesis_dimension}"],
            ),
        )
