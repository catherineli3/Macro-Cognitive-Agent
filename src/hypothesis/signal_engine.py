"""Signal Engine — Detect anomalous macro signals and aggregate into themes.

Milestone A: Raw macro snapshot → structured signal report.
Identifies what's "unusual" today, which drives hypothesis generation.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional

from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Data Types ───────────────────────────────────────────────────────────────


@dataclass
class AnomalousSignal:
    """A single anomalous signal detected in the macro snapshot."""
    indicator: str
    value: float
    z_score: float                 # Deviation from historical mean
    direction: str                 # "bullish" / "bearish" / "neutral"
    strength: float                # 0~1, normalized anomaly strength
    interpretation: str = ""       # Human-readable interpretation


@dataclass
class SignalTheme:
    """A macro theme aggregated from multiple signals."""
    name: str                      # e.g. "tightening_liquidity"
    label: str                     # Human-readable, e.g. "Liquidity Tightening"
    direction: str                 # Overall direction
    strength: float                # 0~1
    supporting_signals: list[str] = field(default_factory=list)
    narrative: str = ""            # One-sentence description


@dataclass
class SignalReport:
    """Complete signal analysis output."""
    regime: str = "unknown"                           # easing / tightening / neutral
    anomalies: list[AnomalousSignal] = field(default_factory=list)
    themes: list[SignalTheme] = field(default_factory=list)
    regime_shift_detected: bool = False
    summary: str = ""


# ── Config ───────────────────────────────────────────────────────────────────


# Historical mean and std for key indicators (approximate, for z-score computation)
# These would normally come from a real data store; here we use reasonable defaults
# that can be overridden by the simulation/real data feed.
_REFERENCE_STATS: dict[str, dict[str, float]] = {
    # Rate indicators
    "US10Y": {"mean": 3.50, "std": 0.80},
    "US02Y": {"mean": 3.80, "std": 0.90},
    "TIPS": {"mean": 1.50, "std": 0.50},
    # Equity
    "SPX": {"mean": 5000, "std": 600},
    "NASDAQ": {"mean": 17000, "std": 2500},
    # FX
    "DXY": {"mean": 104, "std": 5},
    "USD": {"mean": 104, "std": 5},
    # Volatility
    "VIX": {"mean": 18, "std": 6},
    # Credit
    "HYG": {"mean": 77, "std": 3},
    # Commodities
    "Gold": {"mean": 2100, "std": 150},
    # Fed
    "FED_FUNDS": {"mean": 4.50, "std": 1.00},
}

# Theme detection rules
_THEME_RULES: list[dict] = [
    {
        "name": "liquidity_tightening",
        "label": "Liquidity Tightening",
        "direction": "bearish",
        "required_signals": ["DXY", "US02Y"],
        "condition": lambda sigs: (
            _get_dir(sigs, "DXY") == "bullish" and _get_dir(sigs, "US02Y") == "bullish"
        ),
        "narrative": "Liquidity conditions are tightening — rising dollar and short-term rates constrain capital flows.",
    },
    {
        "name": "liquidity_easing",
        "label": "Liquidity Easing",
        "direction": "bullish",
        "required_signals": ["DXY", "US02Y"],
        "condition": lambda sigs: (
            _get_dir(sigs, "DXY") == "bearish" and _get_dir(sigs, "US02Y") == "bearish"
        ),
        "narrative": "Liquidity conditions are easing — weakening dollar and falling short-term rates support risk appetite.",
    },
    {
        "name": "credit_stress",
        "label": "Credit Stress",
        "direction": "bearish",
        "required_signals": ["HYG", "VIX"],
        "condition": lambda sigs: (
            _get_dir(sigs, "HYG") == "bearish" and _get_dir(sigs, "VIX") == "bullish"
        ),
        "narrative": "Credit markets are showing stress — widening spreads and elevated volatility signal risk aversion.",
    },
    {
        "name": "risk_on",
        "label": "Risk-On Environment",
        "direction": "bullish",
        "required_signals": ["SPX", "VIX"],
        "condition": lambda sigs: (
            _get_dir(sigs, "SPX") == "bullish" and _get_dir(sigs, "VIX") == "bearish"
        ),
        "narrative": "Risk appetite is strong — equities rising with low volatility supports a risk-on environment.",
    },
    {
        "name": "inflation_pressure",
        "label": "Inflation Pressure",
        "direction": "bearish",
        "required_signals": ["TIPS", "US10Y", "Gold"],
        "condition": lambda sigs: (
            _get_dir(sigs, "TIPS") == "bearish" and
            _get_dir(sigs, "US10Y") == "bullish" and
            _get_dir(sigs, "Gold") == "bullish"
        ),
        "narrative": "Inflation pressures are building — declining TIPS, rising long yields, and strong gold demand signal inflation concerns.",
    },
    {
        "name": "growth_slowing",
        "label": "Growth Deceleration",
        "direction": "bearish",
        "required_signals": ["SPX", "US10Y"],
        "condition": lambda sigs: (
            _get_dir(sigs, "SPX") == "bearish" and _get_dir(sigs, "US10Y") == "bearish"
        ),
        "narrative": "Growth is decelerating — falling equities and declining long yields suggest economic slowdown.",
    },
    {
        "name": "growth_accelerating",
        "label": "Growth Acceleration",
        "direction": "bullish",
        "required_signals": ["SPX", "US10Y"],
        "condition": lambda sigs: (
            _get_dir(sigs, "SPX") == "bullish" and _get_dir(sigs, "US10Y") == "bullish"
        ),
        "narrative": "Growth is accelerating — rising equities and climbing long yields reflect strong economic momentum.",
    },
    {
        "name": "dollar_weakness",
        "label": "Dollar Weakness Regime",
        "direction": "bullish",
        "required_signals": ["DXY", "Gold"],
        "condition": lambda sigs: (
            _get_dir(sigs, "DXY") == "bearish" and _get_dir(sigs, "Gold") == "bullish"
        ),
        "narrative": "Dollar weakness is a dominant theme — declining DXY and rising gold support EM and commodity exposure.",
    },
]


def _get_dir(sigs: dict[str, AnomalousSignal], indicator: str) -> str:
    s = sigs.get(indicator)
    return s.direction if s else "neutral"


# ── Engine ───────────────────────────────────────────────────────────────────


class SignalEngine:
    """Detects anomalous signals and aggregates them into macro themes.

    This is the entry point for Milestone A: it answers "What's unusual today?"
    """

    def __init__(self, reference_stats: Optional[dict] = None) -> None:
        self._stats = reference_stats or _REFERENCE_STATS
        self._anomaly_threshold = 1.0  # z-score threshold for anomaly detection

    def process(self, indicators: dict[str, float], regime: str = "unknown") -> SignalReport:
        """Process a macro snapshot and return a structured signal report.

        Args:
            indicators: {indicator_name: current_value}
            regime: Known regime, e.g. "easing", "tightening", "neutral"

        Returns:
            SignalReport with anomalies and aggregated themes.
        """
        # Step 1: Detect anomalous signals
        anomalies = self._detect_anomalies(indicators)

        # Step 2: Aggregate into themes
        themes = self._aggregate_themes(anomalies)

        # Step 3: Determine regime if not provided
        if regime == "unknown":
            regime = self._infer_regime(themes)

        # Step 4: Regime shift detection (compare with stored previous regime)
        regime_shift = False  # Simplified for Milestone A

        # Step 5: Build summary
        summary = self._build_summary(themes, regime)

        return SignalReport(
            regime=regime,
            anomalies=anomalies,
            themes=themes,
            regime_shift_detected=regime_shift,
            summary=summary,
        )

    def _detect_anomalies(self, indicators: dict[str, float]) -> list[AnomalousSignal]:
        """Detect anomalous signal values via z-score."""
        anomalies: list[AnomalousSignal] = []
        for name, value in indicators.items():
            stats = self._stats.get(name, {"mean": value, "std": abs(value) * 0.05})
            mean = stats["mean"]
            std = stats["std"]
            if std == 0:
                continue

            z = (value - mean) / std
            if abs(z) < self._anomaly_threshold:
                continue  # Not anomalous enough

            # Determine direction and strength
            # For rates/VIX/DXY: higher = bearish (tightening), lower = bullish (easing)
            # For equities/gold/HYG: higher = bullish, lower = bearish
            flip_direction = name in ("US10Y", "US02Y", "DXY", "USD", "VIX", "FED_FUNDS")
            if z > 0:
                direction = "bearish" if flip_direction else "bullish"
            else:
                direction = "bullish" if flip_direction else "bearish"

            strength = min(1.0, abs(z) / 3.0)  # Scale z=3 → strength=1.0

            interpretation = self._interpret_signal(name, value, z, direction)

            anomalies.append(AnomalousSignal(
                indicator=name, value=value, z_score=round(z, 2),
                direction=direction, strength=round(strength, 3),
                interpretation=interpretation,
            ))

        # Sort by absolute z_score descending
        anomalies.sort(key=lambda s: abs(s.z_score), reverse=True)
        return anomalies

    def _interpret_signal(self, name: str, value: float, z: float, direction: str) -> str:
        """Generate a human-readable interpretation of a signal."""
        z_desc = "significantly" if abs(z) > 2.0 else "moderately"
        if z > 0:
            return f"{name} at {value:.1f} — {z_desc} above historical mean, {direction} signal"
        else:
            return f"{name} at {value:.1f} — {z_desc} below historical mean, {direction} signal"

    def _aggregate_themes(self, anomalies: list[AnomalousSignal]) -> list[SignalTheme]:
        """Aggregate individual signals into macro themes."""
        sig_dict = {s.indicator: s for s in anomalies}
        themes: list[SignalTheme] = []

        for rule in _THEME_RULES:
            required = rule["required_signals"]
            # Check if we have at least one of the required signals as anomalous
            has_required = any(r in sig_dict for r in required)
            if not has_required:
                continue

            if rule["condition"](sig_dict):
                supporting = [r for r in required if r in sig_dict]
                avg_strength = statistics.mean(sig_dict[r].strength for r in supporting) if supporting else 0.3

                themes.append(SignalTheme(
                    name=rule["name"],
                    label=rule["label"],
                    direction=rule["direction"],
                    strength=round(avg_strength, 3),
                    supporting_signals=supporting,
                    narrative=rule["narrative"],
                ))

        themes.sort(key=lambda t: t.strength, reverse=True)
        return themes

    def _infer_regime(self, themes: list[SignalTheme]) -> str:
        """Infer the macro regime from detected themes."""
        if not themes:
            return "neutral"

        bullish_count = sum(1 for t in themes if t.direction == "bullish")
        bearish_count = sum(1 for t in themes if t.direction == "bearish")

        if bearish_count > bullish_count:
            return "tightening"
        elif bullish_count > bearish_count:
            return "easing"
        return "neutral"

    def _build_summary(self, themes: list[SignalTheme], regime: str) -> str:
        """Build a one-paragraph summary."""
        if not themes:
            return "No dominant macro themes detected. Indicators are within normal ranges."

        top_themes = themes[:3]
        theme_labels = [t.label for t in top_themes]
        return (
            f"Regime: {regime}. "
            f"Dominant themes: {', '.join(theme_labels)}. "
            f"{top_themes[0].narrative}"
        )

    @property
    def anomaly_threshold(self) -> float:
        return self._anomaly_threshold

    def set_threshold(self, threshold: float) -> None:
        self._anomaly_threshold = threshold
