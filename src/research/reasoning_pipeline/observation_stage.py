"""V5.2 Stage 1: Observation — What do we observe in macro data and markets?

Extracts the raw observations that form the foundation of all subsequent
reasoning. Cannot skip: every pipeline must start here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.research.reasoning_pipeline.schemas import (
    ObservationOutput,
    StageStatus,
)


class ObservationStage:
    """Stage 1: Systematic observation of macro data, markets, and news.

    This is NOT a data collection step (that's done before).
    This is the cognitive act of observing — identifying what stands out,
    what's surprising, and what the raw picture looks like.

    Professional researchers don't start with a narrative.
    They start by looking at the data and asking:
        "What do I see? What's different from yesterday? What's surprising?"
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def execute(
        self,
        macro_data: dict | None = None,
        market_data: dict | None = None,
        news_items: list[str] | None = None,
        previous_observations: dict | None = None,
    ) -> ObservationOutput:
        """Execute the observation stage.

        Args:
            macro_data: Latest macro data (GDP, CPI, employment, etc.)
            market_data: Market data (equities, bonds, FX, commodities)
            news_items: Curated news headlines/summaries
            previous_observations: Yesterday's observations for diff

        Returns:
            ObservationOutput with structured observations
        """
        output = ObservationOutput(
            timestamp=datetime.now().isoformat(),
            status=StageStatus.IN_PROGRESS,
        )

        macro_data = macro_data or {}
        market_data = market_data or {}
        news_items = news_items or []

        # 1. Extract macro observations
        output.observations = self._observe_macro(macro_data)
        output.data_surprises = self._identify_surprises(
            macro_data, previous_observations
        )

        # 2. Extract market observations
        output.market_moves = self._observe_markets(market_data)

        # 3. Note significant news
        output.significant_news = self._filter_significant_news(news_items)

        # 4. Synthesize snapshot
        output.macro_snapshot = self._synthesize_snapshot(output)

        # 5. Track sources
        output.sources = self._collect_sources(macro_data, market_data, news_items)

        # 6. Generate reasoning trace
        output.reasoning_trace = self._generate_trace(output)
        output.status = StageStatus.COMPLETED

        return output

    # ── Observation Methods ─────────────────────────────────────────

    def _observe_macro(self, data: dict) -> list[str]:
        """Observe macro data points and convert to observations."""
        observations = []

        # Growth
        if "gdp" in data:
            observations.append(f"GDP: {data['gdp']}")
        if "gdp_growth" in data:
            observations.append(f"GDP Growth: {data['gdp_growth']}")
        if "pmi" in data:
            observations.append(f"PMI: {data['pmi']}")

        # Inflation
        if "cpi" in data:
            observations.append(f"CPI: {data['cpi']}")
        if "core_cpi" in data:
            observations.append(f"Core CPI: {data['core_cpi']}")
        if "pce" in data:
            observations.append(f"PCE: {data['pce']}")

        # Labor
        if "unemployment" in data:
            observations.append(f"Unemployment: {data['unemployment']}")
        if "nonfarm_payrolls" in data:
            observations.append(f"Nonfarm Payrolls: {data['nonfarm_payrolls']}")

        # Policy
        if "fed_rate" in data:
            observations.append(f"Fed Funds Rate: {data['fed_rate']}")
        if "ecb_rate" in data:
            observations.append(f"ECB Rate: {data['ecb_rate']}")

        # Add raw data observations
        for key, value in data.items():
            if key not in {"gdp", "gdp_growth", "pmi", "cpi", "core_cpi",
                           "pce", "unemployment", "nonfarm_payrolls",
                           "fed_rate", "ecb_rate"}:
                observations.append(f"{key}: {value}")

        return observations

    def _identify_surprises(
        self,
        current: dict,
        previous: dict | None,
    ) -> list[str]:
        """Identify data surprises relative to expectations or previous data."""
        surprises = []

        if not previous:
            return surprises

        for key in set(current.keys()) & set(previous.keys()):
            try:
                curr_val = float(str(current[key]).replace('%', ''))
                prev_val = float(str(previous[key]).replace('%', ''))
                if prev_val != 0:
                    change_pct = (curr_val - prev_val) / abs(prev_val) * 100
                    if abs(change_pct) > 1.0:
                        direction = "above" if change_pct > 0 else "below"
                        surprises.append(
                            f"{key}: {curr_val} ({direction} previous {prev_val}, "
                            f"{abs(change_pct):.1f}% change)"
                        )
            except (ValueError, TypeError):
                # Non-numeric value, compare as strings
                if str(current[key]) != str(previous[key]):
                    surprises.append(
                        f"{key}: changed from {previous[key]} to {current[key]}"
                    )

        return surprises

    def _observe_markets(self, data: dict) -> list[str]:
        """Observe market data and identify notable moves."""
        moves = []

        # Equities
        if "sp500" in data:
            moves.append(f"S&P 500: {data['sp500']}")
        if "nasdaq" in data:
            moves.append(f"Nasdaq: {data['nasdaq']}")

        # Bonds
        if "us10y" in data:
            moves.append(f"US 10Y Yield: {data['us10y']}")
        if "us2y" in data:
            moves.append(f"US 2Y Yield: {data['us2y']}")

        # FX
        if "dxy" in data:
            moves.append(f"DXY: {data['dxy']}")
        if "eurusd" in data:
            moves.append(f"EUR/USD: {data['eurusd']}")

        # Volatility
        if "vix" in data:
            moves.append(f"VIX: {data['vix']}")

        # Commodities
        if "gold" in data:
            moves.append(f"Gold: {data['gold']}")
        if "oil" in data:
            moves.append(f"Crude Oil: {data['oil']}")

        # Add any other market data
        for key, value in data.items():
            if key not in {"sp500", "nasdaq", "us10y", "us2y",
                           "dxy", "eurusd", "vix", "gold", "oil"}:
                moves.append(f"{key}: {value}")

        return moves

    def _filter_significant_news(self, items: list[str]) -> list[str]:
        """Filter for genuinely significant news."""
        significance_keywords = [
            "fomc", "fed", "rate hike", "rate cut", "ecb", "boj",
            "recession", "crisis", "inflation surprise", "jobs report",
            "gdp", "cpi", "pce", "employment", "geopolitical",
            "sanctions", "trade war", "default", "bailout",
            "intervention", "emergency meeting", "extraordinary",
        ]

        significant = []
        for item in items:
            item_lower = item.lower()
            if any(kw in item_lower for kw in significance_keywords):
                significant.append(item)

        return significant[:10]  # Top 10 most significant

    def _synthesize_snapshot(self, output: ObservationOutput) -> str:
        """Synthesize a 2-3 sentence macro snapshot from observations."""
        parts = []

        if output.data_surprises:
            parts.append(f"Key surprises: {'; '.join(output.data_surprises[:3])}")
        else:
            parts.append("No major data surprises.")

        if output.market_moves:
            parts.append(f"Markets: {'; '.join(output.market_moves[:5])}")
        else:
            parts.append("Markets: No notable moves.")

        if output.significant_news:
            parts.append(f"Top news: {'; '.join(output.significant_news[:3])}")

        return ". ".join(parts)

    def _collect_sources(
        self,
        macro: dict,
        market: dict,
        news: list[str],
    ) -> list[str]:
        """Collect data sources for traceability."""
        sources = []
        if macro:
            sources.append("macro_data")
        if market:
            sources.append("market_data")
        if news:
            sources.append(f"news_feed ({len(news)} items)")
        return sources

    def _generate_trace(self, output: ObservationOutput) -> str:
        """Generate reasoning trace for this stage."""
        trace = []
        trace.append("=== Stage 1: Observation ===")
        trace.append(f"Identified {len(output.observations)} macro observations")
        trace.append(f"Found {len(output.data_surprises)} data surprises")
        trace.append(f"Noted {len(output.market_moves)} market moves")
        trace.append(f"Filtered {len(output.significant_news)} significant news items")
        trace.append(f"Snapshot: {output.macro_snapshot}")
        return "\n".join(trace)
