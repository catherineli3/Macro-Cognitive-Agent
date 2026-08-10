"""FeatureEngine — transform raw observations into trading features.

The Agent should see Features, not Raw Prices.

Examples:
    DXY  → level, 5d_change, 20d_trend, momentum, volatility, z-score
    US10Y → trend, slope, real_rate_proxy, breakout
    VIX  → regime: panic / normal / complacency
    Copper → growth_strength
    Gold   → safe_haven_demand

Each indicator maps to a pre-defined set of features via FeatureDimension.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from src.data_pipeline.normalizer import MacroObservation
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Feature Dimension Enum ──────────────────────────────────────────────────

class FeatureDimension(Enum):
    """Pre-defined feature types extracted from raw observations."""

    LEVEL = "level"
    CHANGE_1D = "change_1d"
    CHANGE_5D = "change_5d"
    TREND_20D = "trend_20d"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    Z_SCORE = "z_score"
    REGIME = "regime"


# ── Data Classes ────────────────────────────────────────────────────────────


@dataclass
class FeaturePoint:
    """A single extracted feature value."""

    symbol: str
    dimension: FeatureDimension
    value: float
    label: str = ""  # Human-readable label (e.g., "tightening", "expansion")
    confidence: float = 1.0


@dataclass
class IndicatorFeatures:
    """All features for a single indicator."""

    symbol: str
    name: str
    macro_dimension: str
    features: list[FeaturePoint] = field(default_factory=list)
    raw_value: float = 0.0
    timestamp: Optional[datetime] = None

    def get(self, dimension: FeatureDimension) -> Optional[FeaturePoint]:
        for f in self.features:
            if f.dimension == dimension:
                return f
        return None


@dataclass
class FeatureSnapshot:
    """Complete feature extraction result for a collection cycle."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    indicators: dict[str, IndicatorFeatures] = field(default_factory=dict)
    dimension_summaries: dict[str, dict] = field(default_factory=dict)

    def get_indicator(self, name: str) -> Optional[IndicatorFeatures]:
        return self.indicators.get(name.upper())


# ── FeatureEngine ───────────────────────────────────────────────────────────


class FeatureEngine:
    """Extracts trading-relevant features from normalized observations.

    Maintains a rolling window of historical values per indicator to compute
    time-series features (changes, trends, momentum, volatility, z-scores).

    Usage:
        engine = FeatureEngine()
        snapshot = engine.extract_features(observations)
        # snapshot.indicators["DXY"].get(FeatureDimension.TREND_20D)
    """

    # Feature specifications per indicator type
    _FEATURE_SPEC: dict[str, list[FeatureDimension]] = {
        # Price/index indicators
        "DXY": [FeatureDimension.LEVEL, FeatureDimension.CHANGE_5D,
                 FeatureDimension.TREND_20D, FeatureDimension.MOMENTUM,
                 FeatureDimension.VOLATILITY, FeatureDimension.Z_SCORE],
        "SP500": [FeatureDimension.LEVEL, FeatureDimension.CHANGE_5D,
                   FeatureDimension.TREND_20D, FeatureDimension.MOMENTUM,
                   FeatureDimension.VOLATILITY],
        "Nasdaq": [FeatureDimension.LEVEL, FeatureDimension.CHANGE_5D,
                    FeatureDimension.TREND_20D, FeatureDimension.MOMENTUM],
        "Russell": [FeatureDimension.LEVEL, FeatureDimension.CHANGE_5D,
                     FeatureDimension.TREND_20D],
        # Yield indicators
        "US10Y": [FeatureDimension.LEVEL, FeatureDimension.CHANGE_5D,
                   FeatureDimension.TREND_20D, FeatureDimension.MOMENTUM],
        "US2Y": [FeatureDimension.LEVEL, FeatureDimension.CHANGE_5D,
                  FeatureDimension.TREND_20D],
        # Volatility
        "VIX": [FeatureDimension.LEVEL, FeatureDimension.CHANGE_5D,
                 FeatureDimension.REGIME],
        # Commodities
        "Gold": [FeatureDimension.LEVEL, FeatureDimension.CHANGE_5D,
                  FeatureDimension.TREND_20D],
        "Copper": [FeatureDimension.LEVEL, FeatureDimension.CHANGE_5D,
                    FeatureDimension.TREND_20D],
        "Oil": [FeatureDimension.LEVEL, FeatureDimension.CHANGE_5D,
                 FeatureDimension.VOLATILITY],
        # Credit
        "HYG": [FeatureDimension.LEVEL, FeatureDimension.CHANGE_5D,
                 FeatureDimension.TREND_20D],
        "LQD": [FeatureDimension.LEVEL, FeatureDimension.CHANGE_5D,
                 FeatureDimension.TREND_20D],
        # AI Cycle
        "NVDA": [FeatureDimension.LEVEL, FeatureDimension.MOMENTUM,
                  FeatureDimension.VOLATILITY],
        "Semiconductor": [FeatureDimension.LEVEL, FeatureDimension.TREND_20D],
        "ASML": [FeatureDimension.LEVEL, FeatureDimension.MOMENTUM],
        "TSMC": [FeatureDimension.LEVEL, FeatureDimension.TREND_20D],
    }

    # Regime-specific thresholds
    _VIX_REGIMES = {
        "complacency": (0, 15),
        "normal": (15, 25),
        "elevated": (25, 35),
        "panic": (35, float("inf")),
    }

    _GOLD_REGIMES = {
        "safe_haven_demand": (2000, float("inf")),
        "normal": (1500, 2000),
        "weak_demand": (0, 1500),
    }

    def __init__(self, history_window: int = 30) -> None:
        self._history: dict[str, list[float]] = defaultdict(list)
        self._timestamps: dict[str, list[datetime]] = defaultdict(list)
        self._history_window = history_window

    # ── Public API ──────────────────────────────────────────────────────────

    def extract_features(
        self,
        observations: list[MacroObservation],
    ) -> FeatureSnapshot:
        """Extract all features from a batch of observations."""
        snapshot = FeatureSnapshot()

        # Update history
        for obs in observations:
            if not obs.is_degraded and obs.value != 0:
                key = obs.name.upper()
                self._history[key].append(obs.value)
                self._timestamps[key].append(obs.timestamp)
                # Trim to window
                if len(self._history[key]) > self._history_window:
                    self._history[key] = self._history[key][-self._history_window:]
                    self._timestamps[key] = self._timestamps[key][-self._history_window:]

        # Extract features per indicator
        for obs in observations:
            key = obs.name.upper()
            spec = self._FEATURE_SPEC.get(key, [FeatureDimension.LEVEL])

            indicator_f = IndicatorFeatures(
                symbol=obs.symbol,
                name=obs.name,
                macro_dimension=obs.dimension,
                raw_value=obs.value,
                timestamp=obs.timestamp,
            )

            for dim in spec:
                fp = self._compute_feature(key, obs, dim)
                if fp:
                    indicator_f.features.append(fp)

            snapshot.indicators[key] = indicator_f

        # Compute dimension summaries
        self._compute_dimension_summaries(snapshot)

        logger.info(
            "feature_engine_done | indicators=%d features=%d",
            len(snapshot.indicators),
            sum(len(ind.features) for ind in snapshot.indicators.values()),
        )
        return snapshot

    # ── Internal ────────────────────────────────────────────────────────────

    def _compute_feature(
        self,
        key: str,
        obs: MacroObservation,
        dim: FeatureDimension,
    ) -> Optional[FeaturePoint]:
        """Compute a single feature for a given indicator."""
        hist = self._history.get(key, [])

        try:
            if dim == FeatureDimension.LEVEL:
                return FeaturePoint(
                    symbol=key, dimension=dim, value=obs.value,
                    label="current_level", confidence=obs.quality_score,
                )

            elif dim == FeatureDimension.CHANGE_5D and len(hist) >= 5:
                prev = hist[-6] if len(hist) >= 6 else hist[0]
                if prev != 0:
                    pct = (obs.value - prev) / abs(prev)
                    direction = "up" if pct > 0 else "down"
                    return FeaturePoint(
                        symbol=key, dimension=dim, value=pct,
                        label=f"5d_{direction}", confidence=obs.quality_score,
                    )

            elif dim == FeatureDimension.TREND_20D and len(hist) >= 10:
                prev = hist[-min(20, len(hist))]
                if prev != 0 and len(hist) >= 10:
                    pct = (obs.value - prev) / abs(prev)
                    regime = "uptrend" if pct > 0.02 else ("downtrend" if pct < -0.02 else "neutral")
                    return FeaturePoint(
                        symbol=key, dimension=dim, value=pct,
                        label=f"20d_{regime}", confidence=obs.quality_score,
                    )

            elif dim == FeatureDimension.MOMENTUM and len(hist) >= 10:
                # Simple momentum: short MA / long MA - 1
                short = sum(hist[-5:]) / min(5, len(hist[-5:]))
                long = sum(hist[-min(10, len(hist)):]) / min(10, len(hist))
                if long != 0:
                    mom = (short / long) - 1
                    regime = "accelerating" if mom > 0.01 else ("decelerating" if mom < -0.01 else "stable")
                    return FeaturePoint(
                        symbol=key, dimension=dim, value=mom,
                        label=f"momentum_{regime}", confidence=obs.quality_score,
                    )

            elif dim == FeatureDimension.VOLATILITY and len(hist) >= 10:
                recent = hist[-10:]
                mean_v = sum(recent) / len(recent)
                if mean_v != 0:
                    vol = (sum((v - mean_v) ** 2 for v in recent) / len(recent)) ** 0.5 / abs(mean_v)
                    regime = "high" if vol > 0.03 else ("low" if vol < 0.01 else "normal")
                    return FeaturePoint(
                        symbol=key, dimension=dim, value=vol,
                        label=f"volatility_{regime}", confidence=obs.quality_score,
                    )

            elif dim == FeatureDimension.Z_SCORE and len(hist) >= 20:
                all_vals = hist[-20:]
                mean_v = sum(all_vals) / len(all_vals)
                std_v = (sum((v - mean_v) ** 2 for v in all_vals) / len(all_vals)) ** 0.5
                if std_v > 0:
                    z = (obs.value - mean_v) / std_v
                    regime = "extreme_high" if z > 2 else ("extreme_low" if z < -2 else "normal")
                    return FeaturePoint(
                        symbol=key, dimension=dim, value=round(z, 2),
                        label=f"zscore_{regime}", confidence=obs.quality_score,
                    )

            elif dim == FeatureDimension.REGIME:
                return self._compute_regime(key, obs)

        except Exception as exc:
            logger.debug("feature_compute_error | %s %s: %s", key, dim.value, exc)

        return None

    def _compute_regime(self, key: str, obs: MacroObservation) -> Optional[FeaturePoint]:
        """Compute regime classification for special indicators."""
        if key == "VIX":
            for regime, (lo, hi) in self._VIX_REGIMES.items():
                if lo <= obs.value < hi:
                    return FeaturePoint(
                        symbol=key, dimension=FeatureDimension.REGIME,
                        value={"complacency": 0.1, "normal": 0.5, "elevated": 0.75, "panic": 0.95}.get(regime, 0.5),
                        label=regime, confidence=obs.quality_score,
                    )

        if key == "GOLD" or key == "GOLD":
            for regime, (lo, hi) in self._GOLD_REGIMES.items():
                if lo <= obs.value < hi:
                    return FeaturePoint(
                        symbol=key, dimension=FeatureDimension.REGIME,
                        value={"safe_haven_demand": 0.8, "normal": 0.5, "weak_demand": 0.2}.get(regime, 0.5),
                        label=regime, confidence=obs.quality_score,
                    )

        return None

    def _compute_dimension_summaries(self, snapshot: FeatureSnapshot) -> None:
        """Compute aggregate summaries per macro dimension."""
        dim_indicators: dict[str, list[IndicatorFeatures]] = defaultdict(list)
        for ind in snapshot.indicators.values():
            dim_indicators[ind.macro_dimension].append(ind)

        for dim, indicators in dim_indicators.items():
            trends = []
            for ind in indicators:
                trend_f = ind.get(FeatureDimension.TREND_20D)
                if trend_f:
                    trends.append(trend_f.value)

            snapshot.dimension_summaries[dim] = {
                "indicator_count": len(indicators),
                "avg_trend": sum(trends) / len(trends) if trends else 0.0,
                "indicators": [ind.name for ind in indicators],
            }
