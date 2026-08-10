"""InstitutionalPosition — CFTC COT + 13F-style positioning analysis.

Tracks positioning for major macro assets:
    - Currencies (DXY, EUR, JPY, GBP)
    - Rates (10Y, 2Y, SOFR)
    - Equities (S&P, Nasdaq)
    - Commodities (Gold, Oil, Copper)

Key signals:
    - Extreme positioning (crowded trades) → contrarian signal
    - Positioning changes (who is adding/reducing)
    - Speculator vs. commercial divergence
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from src.capital_flow.schemas import FlowSignal, PositionSnapshot


# Asset universe for positioning tracking
POSITION_UNIVERSE = {
    "usd_index": {"asset": "DXY", "class": "currencies", "region": "US"},
    "eur_usd": {"asset": "EUR/USD", "class": "currencies", "region": "Europe"},
    "jpy_usd": {"asset": "JPY/USD", "class": "currencies", "region": "Japan"},
    "10y_treasury": {"asset": "10Y Futures", "class": "rates", "region": "US"},
    "2y_treasury": {"asset": "2Y Futures", "class": "rates", "region": "US"},
    "sp500": {"asset": "S&P 500", "class": "equities", "region": "US"},
    "nasdaq": {"asset": "Nasdaq 100", "class": "equities", "region": "US"},
    "gold": {"asset": "Gold", "class": "commodities", "region": "Global"},
    "crude_oil": {"asset": "WTI Crude", "class": "commodities", "region": "Global"},
    "copper": {"asset": "Copper", "class": "commodities", "region": "Global"},
    "vix": {"asset": "VIX Futures", "class": "volatility", "region": "US"},
}

CROWDED_THRESHOLD = 80  # Percentile above which = crowded
CONTRARIAN_THRESHOLD = 20  # Percentile below which = extreme bearish


class InstitutionalPosition:
    """Analyzes institutional positioning."""

    def __init__(self):
        self._position_history: dict[str, list[PositionSnapshot]] = {}

    def analyze_positions(
        self,
        position_data: Optional[dict] = None,
        date: Optional[str] = None,
    ) -> list[PositionSnapshot]:
        """Analyze positioning across the universe.

        Args:
            position_data: Optional {asset: {net_position, long, short, oi, ...}}.
                           If None, generates synthetic for dev/test.
            date: Analysis date.

        Returns:
            List of PositionSnapshot objects.
        """
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        snapshots = []
        for asset_key, info in POSITION_UNIVERSE.items():
            if position_data and asset_key in position_data:
                snap = self._analyze_from_data(
                    asset_key, info, position_data[asset_key], date
                )
            else:
                snap = self._generate_synthetic(asset_key, info, date)
            snapshots.append(snap)

        return snapshots

    def _analyze_from_data(
        self,
        key: str,
        info: dict,
        data: dict,
        date: str,
    ) -> PositionSnapshot:
        net = data.get("net_position", 0)
        long_val = data.get("long_contracts", 0)
        short_val = data.get("short_contracts", 0)
        oi = data.get("open_interest", 1)

        pct_of_oi = net / oi * 100 if oi > 0 else 0
        # Estimate percentile from data
        percentile = data.get("positioning_percentile", 50.0)
        is_extreme = percentile > 90 or percentile < 10
        is_crowded = percentile > CROWDED_THRESHOLD

        return PositionSnapshot(
            date=date,
            asset=info["asset"],
            asset_class=info["class"],
            long_contracts=long_val,
            short_contracts=short_val,
            net_position=net,
            net_pct_of_oi=round(pct_of_oi, 2),
            weekly_change=data.get("weekly_change", 0),
            monthly_change=data.get("monthly_change", 0),
            positioning_percentile=percentile,
            is_extreme=is_extreme,
            is_crowded=is_crowded,
            description=self._describe_snapshot(info["asset"], net, percentile),
        )

    def _generate_synthetic(
        self, key: str, info: dict, date: str
    ) -> PositionSnapshot:
        """Deterministic synthetic for development."""
        seed = sum(ord(c) for c in f"{key}{date}")
        r = (seed % 100) / 100.0

        net = (r - 0.45) * 200000
        percentile = r * 100
        is_extreme = percentile > 90 or percentile < 10
        is_crowded = percentile > CROWDED_THRESHOLD

        return PositionSnapshot(
            date=date,
            asset=info["asset"],
            asset_class=info["class"],
            long_contracts=100000 + int(r * 100000),
            short_contracts=100000 - int(r * 100000),
            net_position=net,
            net_pct_of_oi=round((r - 0.45) * 40, 2),
            weekly_change=(r - 0.5) * 15000,
            monthly_change=(r - 0.48) * 30000,
            positioning_percentile=round(percentile, 1),
            is_extreme=is_extreme,
            is_crowded=is_crowded,
            description=self._describe_snapshot(info["asset"], net, percentile),
        )

    def _describe_snapshot(
        self, asset: str, net: float, percentile: float
    ) -> str:
        direction = "long" if net > 0 else "short"
        if percentile > 90:
            severity = "extreme " + direction
        elif percentile > 75:
            severity = "heavy " + direction
        elif percentile > 60:
            severity = direction + "-biased"
        elif percentile < 10:
            severity = "extreme " + ("short" if net < 0 else "long")
        elif percentile < 25:
            severity = "light " + direction
        else:
            severity = "neutral"
        return f"{asset}: {severity} positioning ({percentile:.0f}th pct)"

    def to_flow_signals(
        self, snapshots: list[PositionSnapshot]
    ) -> list[FlowSignal]:
        """Convert positioning to flow signals."""
        signals = []
        for snap in snapshots:
            direction = (
                "inflow" if snap.weekly_change > 0
                else "outflow" if snap.weekly_change < 0
                else "neutral"
            )
            magnitude = max(-1.0, min(1.0, snap.net_pct_of_oi / 40.0))

            signals.append(FlowSignal(
                asset_class=snap.asset_class,
                region=POSITION_UNIVERSE.get(snap.asset.lower().replace(" ", "_"), {}).get("region", "Global"),
                direction=direction,
                magnitude=round(magnitude, 3),
                weekly_flow_bn=snap.net_position / 100,
                percentile=snap.positioning_percentile,
                description=snap.description,
                source="CFTC",
            ))
        return signals

    def detect_crowded_trades(
        self, snapshots: list[PositionSnapshot]
    ) -> list[dict]:
        """Identify excessively crowded trades — contrarian signals."""
        crowded = []
        for snap in snapshots:
            if snap.is_crowded:
                crowded.append({
                    "asset": snap.asset,
                    "direction": "long" if snap.net_position > 0 else "short",
                    "percentile": snap.positioning_percentile,
                    "signal": "contrarian",  # Extreme positioning = contrarian
                    "risk": "unwinding" if snap.weekly_change < 0 else "continuing",
                })
        return sorted(crowded, key=lambda x: x["percentile"], reverse=True)

    def detect_extreme_positions(
        self, snapshots: list[PositionSnapshot]
    ) -> list[dict]:
        """Identify extreme positioning — potential inflection points."""
        extreme = []
        for snap in snapshots:
            if snap.is_extreme:
                direction = "long" if snap.net_position > 0 else "short"
                extreme.append({
                    "asset": snap.asset,
                    "direction": direction,
                    "percentile": snap.positioning_percentile,
                    "if_mean_reverts": (
                        "buy" if snap.positioning_percentile < 10
                        else "sell" if snap.positioning_percentile > 90
                        else "hold"
                    ),
                })
        return extreme
