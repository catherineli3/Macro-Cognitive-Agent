"""ETFFlow — ETF fund flow analysis.

Tracks money flowing into/out of major ETF categories:
    - US Equities (SPY, QQQ, IWM)
    - International Equities (EFA, EEM)
    - Fixed Income (AGG, TLT, HYG, LQD)
    - Commodities (GLD, USO, DBC)
    - Sectors (XLF, XLK, XLE, XLV)
    - Cash/Money Market (BIL, SHV)

Generates FlowSignal objects used by CrossAssetFlow and CapitalRotation.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.capital_flow.schemas import ETFDay, ETFSummary, FlowSignal

# ETF universe organized by category
ETF_UNIVERSE = {
    "equities_us_large": {"tickers": ["SPY", "IVV", "VOO"], "label": "US Large Cap"},
    "equities_us_tech": {"tickers": ["QQQ", "XLK", "VGT"], "label": "US Tech"},
    "equities_us_small": {"tickers": ["IWM", "IJR"], "label": "US Small Cap"},
    "equities_intl_dev": {"tickers": ["EFA", "IEFA", "VEA"], "label": "Intl Developed"},
    "equities_em": {"tickers": ["EEM", "IEMG", "VWO"], "label": "Emerging Markets"},
    "bonds_treasury": {"tickers": ["TLT", "IEF", "SHY", "GOVT"], "label": "Treasury"},
    "bonds_corp": {"tickers": ["LQD", "IGIB"], "label": "Investment Grade"},
    "bonds_hy": {"tickers": ["HYG", "JNK"], "label": "High Yield"},
    "bonds_agg": {"tickers": ["AGG", "BND"], "label": "Aggregate Bond"},
    "gold": {"tickers": ["GLD", "IAU"], "label": "Gold"},
    "commodities": {"tickers": ["DBC", "USO", "GSG"], "label": "Commodities"},
    "cash": {"tickers": ["BIL", "SHV", "MINT"], "label": "Cash/Short-Term"},
}

CATEGORY_LABELS = {k: v["label"] for k, v in ETF_UNIVERSE.items()}
ALL_TICKERS = [t for v in ETF_UNIVERSE.values() for t in v["tickers"]]


class ETFFlow:
    """Analyzes ETF fund flows."""

    def __init__(self):
        self._flow_history: dict[str, list[ETFDay]] = {}

    def analyze_flows(
        self,
        flow_data: dict[str, list[dict]] | None = None,
        market_data: dict | None = None,
        date: str | None = None,
    ) -> list[ETFSummary]:
        """Analyze ETF flows by category.

        Args:
            flow_data: Optional {ticker: [{date, flow_mm, aum_bn, ...}, ...]}.
                       If None, generates simulated signals for dev/test.
            market_data: Optional market context.
            date: Analysis date (defaults to today).

        Returns:
            List of ETFSummary by category.
        """
        if date is None:
            date = datetime.now(UTC).strftime("%Y-%m-%d")

        summaries = []
        for cat_key, cat_info in ETF_UNIVERSE.items():
            cat_tickers = cat_info["tickers"]

            if flow_data:
                summary = self._analyze_from_data(cat_key, cat_tickers, flow_data, date)
            else:
                summary = self._generate_synthetic(cat_key, cat_tickers, date)

            summaries.append(summary)

        return summaries

    def _analyze_from_data(
        self,
        cat_key: str,
        tickers: list[str],
        flow_data: dict,
        date: str,
    ) -> ETFSummary:
        """Analyze from actual flow data."""
        days = []
        weekly_total = 0.0
        monthly_total = 0.0
        ytd_total = 0.0

        for ticker in tickers:
            ticker_data = flow_data.get(ticker, [])
            for record in ticker_data:
                day = ETFDay(
                    date=record.get("date", ""),
                    ticker=ticker,
                    name=record.get("name", ""),
                    category=cat_key,
                    flow_mm=record.get("flow_mm", 0),
                    aum_bn=record.get("aum_bn", 0),
                    flow_pct=record.get("flow_pct", 0),
                    price_change_pct=record.get("price_change_pct", 0),
                )
                days.append(day)
                weekly_total += record.get("flow_mm", 0)
                monthly_total += record.get("flow_mm", 0)
                ytd_total += record.get("flow_mm", 0)

        # Calculate momentum
        if len(days) >= 10:
            recent = sum(d.flow_mm for d in days[-5:])
            prior = sum(d.flow_mm for d in days[-10:-5])
            momentum = (recent - prior) / (abs(prior) + 1) * 0.5 if prior != 0 else 0
        else:
            momentum = 0

        return ETFSummary(
            category=cat_key,
            weekly_flow_bn=weekly_total / 1000,
            monthly_flow_bn=monthly_total / 1000,
            ytd_flow_bn=ytd_total / 1000,
            aum_bn=sum((getattr(d, "aum_bn", 0) or 0) for d in days),
            flow_momentum=momentum,
            days=days,
            description=self._describe(cat_key, weekly_total),
        )

    def _generate_synthetic(self, cat_key: str, tickers: list[str], date: str) -> ETFSummary:
        """Generate synthetic flow signals for development/testing."""
        # Deterministic by category + date
        seed = sum(ord(c) for c in f"{cat_key}{date}")
        r = (seed % 100) / 100.0

        w = (r - 0.4) * 15  # Weekly flow in billions, -6 to +9 range
        m = w * 3.5 + (r - 0.5) * 5
        ytd = m * 6

        momentum = (r - 0.5) * 0.8

        days = [
            ETFDay(
                date=date,
                ticker=tickers[0],
                name=cat_key,
                category=cat_key,
                flow_mm=w * 1000,
                flow_pct=w * 0.3,
            )
        ]

        return ETFSummary(
            category=cat_key,
            weekly_flow_bn=round(w, 2),
            monthly_flow_bn=round(m, 2),
            ytd_flow_bn=round(ytd, 2),
            aum_bn=20 + r * 100,
            flow_momentum=round(momentum, 2),
            days=days,
            description=self._describe(cat_key, w * 1000),
        )

    def _describe(self, cat_key: str, weekly_flow_mm: float) -> str:
        label = CATEGORY_LABELS.get(cat_key, cat_key)
        if weekly_flow_mm > 2000:
            return f"{label}: massive inflows"
        elif weekly_flow_mm > 500:
            return f"{label}: strong inflows"
        elif weekly_flow_mm > 0:
            return f"{label}: moderate inflows"
        elif weekly_flow_mm > -500:
            return f"{label}: mild outflows"
        elif weekly_flow_mm > -2000:
            return f"{label}: significant outflows"
        else:
            return f"{label}: massive outflows"

    def to_flow_signals(self, summaries: list[ETFSummary]) -> list[FlowSignal]:
        """Convert ETF summaries to generic flow signals."""
        signals = []
        for s in summaries:
            direction = (
                "inflow"
                if s.weekly_flow_bn > 0.3
                else "outflow" if s.weekly_flow_bn < -0.3 else "neutral"
            )
            magnitude = max(-1.0, min(1.0, s.weekly_flow_bn / 20.0))

            # Map category to asset_class and region
            asset_class, region = self._map_category(s.category)

            signals.append(
                FlowSignal(
                    asset_class=asset_class,
                    region=region,
                    direction=direction,
                    magnitude=round(magnitude, 3),
                    weekly_flow_bn=s.weekly_flow_bn,
                    monthly_flow_bn=s.monthly_flow_bn,
                    ytd_flow_bn=s.ytd_flow_bn,
                    percentile=50 + magnitude * 40,
                    description=s.description,
                    source="ETF",
                )
            )
        return signals

    def _map_category(self, cat: str) -> tuple:
        """Map ETF category to (asset_class, region)."""
        mappings = {
            "equities_us_large": ("equities", "US"),
            "equities_us_tech": ("equities", "US"),
            "equities_us_small": ("equities", "US"),
            "equities_intl_dev": ("equities", "Developed"),
            "equities_em": ("equities", "EM"),
            "bonds_treasury": ("bonds", "US"),
            "bonds_corp": ("bonds", "US"),
            "bonds_hy": ("bonds", "US"),
            "bonds_agg": ("bonds", "US"),
            "gold": ("gold", "Global"),
            "commodities": ("commodities", "Global"),
            "cash": ("cash", "Global"),
        }
        return mappings.get(cat, ("other", "Global"))

    def get_etf_summary(self, summaries: list[ETFSummary]) -> dict:
        """Generate a human-readable ETF flow summary."""
        inflows = [s for s in summaries if s.weekly_flow_bn > 0]
        outflows = [s for s in summaries if s.weekly_flow_bn < 0]

        total_inflow = sum(s.weekly_flow_bn for s in inflows)
        total_outflow = sum(abs(s.weekly_flow_bn) for s in outflows)
        net = total_inflow - total_outflow

        return {
            "total_inflow_bn": round(total_inflow, 2),
            "total_outflow_bn": round(total_outflow, 2),
            "net_flow_bn": round(net, 2),
            "top_inflow": (
                sorted(inflows, key=lambda s: s.weekly_flow_bn, reverse=True)[:3] if inflows else []
            ),
            "top_outflow": (
                sorted(outflows, key=lambda s: s.weekly_flow_bn)[:3] if outflows else []
            ),
            "regime": ("risk_on" if net > 5 else "risk_off" if net < -5 else "neutral"),
        }
