"""Phase 2: ChangeDetector — Detect momentum, acceleration, divergence, regime change.

Detects 4 critical macro pair divergences:
    1. Stocks vs Credit      → SP500 direction vs HYG/LQD direction
    2. USD vs Gold           → DXY direction vs Gold direction
    3. Yields vs Equities    → TLT direction vs SP500 direction
    4. Copper vs Growth      → Copper direction vs Russell/GDP proxy

Also detects:
    - Momentum signals: which indicators trending strongly
    - Acceleration signals: which trends are strengthening/weakening
    - Regime change: has the macro regime shifted?

Reuses: FeatureEngine features (CHANGE_5D, TREND_20D, MOMENTUM, VOLATILITY)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.data_pipeline.feature_engine import FeatureDimension, FeatureSnapshot
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class MomentumSignal:
    """Single momentum signal for one indicator."""

    indicator: str
    trend: float  # 20-day trend magnitude
    change_5d: float
    momentum_20d: float
    volatility: float
    strength: str  # "strong_bullish", "bullish", "neutral", "bearish", "strong_bearish"
    score: float  # -1.0 to 1.0

    def to_dict(self) -> dict:
        return {
            "indicator": self.indicator,
            "trend": round(self.trend, 4),
            "change_5d": round(self.change_5d, 4),
            "momentum_20d": round(self.momentum_20d, 4),
            "volatility": round(self.volatility, 4),
            "strength": self.strength,
            "score": round(self.score, 2),
        }


@dataclass
class DivergenceSignal:
    """Detected divergence between a pair of indicators or asset classes."""

    pair: str  # "stocks_vs_credit", "usd_vs_gold", etc.
    asset_a: str
    asset_b: str
    direction_a: str
    direction_b: str
    is_diverging: bool
    divergence_type: str  # "bullish_divergence", "bearish_divergence", "convergent"
    significance: float  # 0-1
    interpretation: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pair": self.pair,
            "asset_a": self.asset_a,
            "asset_b": self.asset_b,
            "direction_a": self.direction_a,
            "direction_b": self.direction_b,
            "is_diverging": self.is_diverging,
            "divergence_type": self.divergence_type,
            "significance": round(self.significance, 2),
            "interpretation": self.interpretation,
            "evidence": self.evidence,
        }


@dataclass
class RegimeChangeSignal:
    """Detection of potential macro regime change."""

    has_shifted: bool
    previous_regime: str
    current_regime: str
    shift_magnitude: float  # 0-1, how significant the shift
    shift_drivers: list[str]  # Which indicators drove the shift
    confidence: float
    summary: str

    def to_dict(self) -> dict:
        return {
            "has_shifted": self.has_shifted,
            "previous_regime": self.previous_regime,
            "current_regime": self.current_regime,
            "shift_magnitude": round(self.shift_magnitude, 2),
            "shift_drivers": self.shift_drivers,
            "confidence": round(self.confidence, 2),
            "summary": self.summary,
        }


@dataclass
class ChangeSignals:
    """Complete change detection output."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    momentum_signals: list[MomentumSignal] = field(default_factory=list)
    divergence_signals: list[DivergenceSignal] = field(default_factory=list)
    regime_change: RegimeChangeSignal | None = None
    strongest_signals: list[str] = field(default_factory=list)  # Top-3 notable signals
    acceleration_signals: list[str] = field(default_factory=list)  # What's accelerating

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "momentum_signals": [m.to_dict() for m in self.momentum_signals],
            "divergence_signals": [d.to_dict() for d in self.divergence_signals],
            "regime_change": self.regime_change.to_dict() if self.regime_change else None,
            "strongest_signals": self.strongest_signals,
            "acceleration_signals": self.acceleration_signals,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ChangeDetector
# ═══════════════════════════════════════════════════════════════════════════════


class ChangeDetector:
    """Detect macro momentum, acceleration, divergence, and regime changes.

    Reuses: FeatureEngine features — no extra API calls needed.
    """

    # ── 4 Key Macro Pairs for Divergence Detection ────────────────────────────
    DIVERGENCE_PAIRS = [
        {
            "pair": "stocks_vs_credit",
            "asset_a": "SP500",
            "asset_b": "HYG",
            "label_a": "Equities",
            "label_b": "Credit",
            "bullish_description": "Equities leading credit higher — risk appetite broadening",
            "bearish_description": "Equities up but credit lagging — equity rally not confirmed by credit markets",
            "credit_leading_equity": "Credit leading equities — bond market more forward-looking",
        },
        {
            "pair": "usd_vs_gold",
            "asset_a": "DXY",
            "asset_b": "Gold",
            "label_a": "USD",
            "label_b": "Gold",
            "bullish_description": "Gold rising despite USD strength — safe-haven demand fears",
            "bearish_description": "Gold weakness with USD — real yield pressure",
            "convergence": "Gold rising, USD falling — classic dollar debasement trade",
        },
        {
            "pair": "yields_vs_equities",
            "asset_a": "US10Y",  # TLT (inverse of yield)
            "asset_b": "SP500",
            "label_a": "Treasuries",
            "label_b": "Equities",
            "bullish_description": "Bonds and stocks both bid — 'everything rally' liquidity regime",
            "bearish_description": "Bonds and stocks both offered — liquidity drain or stagflation fear",
            "stocks_up_bonds_down": "Stocks up, bonds down — risk-on rotation out of safe havens",
        },
        {
            "pair": "copper_vs_growth",
            "asset_a": "Copper",
            "asset_b": "Russell",  # Small caps = growth proxy
            "label_a": "Copper",
            "label_b": "Small Caps",
            "bullish_description": "Copper and small caps rising together — cyclical growth confirmation",
            "bearish_description": "Copper rising but small caps weak — growth skepticism",
            "copper_leading": "Copper (Dr. Copper) leading equities — industrial demand signal",
        },
    ]

    # Momentum thresholds
    STRONG_BULLISH = 0.05
    BULLISH = 0.015
    NEUTRAL = -0.015
    BEARISH = -0.05

    def __init__(self) -> None:
        self._previous_regime: str | None = None

    def set_previous_regime(self, regime: str) -> None:
        """Set previous regime for regime-change detection."""
        self._previous_regime = regime

    def detect(
        self,
        features: FeatureSnapshot,
        current_regime: str = "normal",
    ) -> ChangeSignals:
        """Run full change detection on feature snapshot.

        Args:
            features: FeatureSnapshot with all indicator features
            current_regime: Current risk regime classification
        """
        cs = ChangeSignals()

        # Step 1: Individual momentum signals
        cs.momentum_signals = self._detect_momentum(features)

        # Step 2: Pair divergence
        cs.divergence_signals = self._detect_divergences(features)

        # Step 3: Regime change
        cs.regime_change = self._detect_regime_change(features, current_regime)

        # Step 4: Acceleration signals
        cs.acceleration_signals = self._detect_acceleration(features)

        # Step 5: Strongest signals summary
        cs.strongest_signals = self._identify_strongest(cs)

        logger.info(
            "change_detector_done | momentum=%d divergence=%d regime_change=%s",
            len(cs.momentum_signals),
            sum(1 for d in cs.divergence_signals if d.is_diverging),
            cs.regime_change.has_shifted if cs.regime_change else "none",
        )
        return cs

    # ── Momentum Detection ───────────────────────────────────────────────────

    def _detect_momentum(self, features: FeatureSnapshot) -> list[MomentumSignal]:
        """Detect momentum for every indicator with sufficient data."""
        signals = []

        for name, ind in features.indicators.items():
            trend = ind.get(FeatureDimension.TREND_20D)
            change = ind.get(FeatureDimension.CHANGE_5D)
            momentum = ind.get(FeatureDimension.MOMENTUM)
            vol = ind.get(FeatureDimension.VOLATILITY)

            t_val = trend.value if trend else 0.0
            c_val = change.value if change else 0.0
            m_val = momentum.value if momentum else 0.0
            v_val = vol.value if vol else 0.0

            strength = self._classify_strength(t_val)

            signals.append(
                MomentumSignal(
                    indicator=name,
                    trend=t_val,
                    change_5d=c_val,
                    momentum_20d=m_val,
                    volatility=v_val,
                    strength=strength,
                    score=max(-1.0, min(1.0, t_val * 20)),
                )
            )

        # Sort by absolute score
        signals.sort(key=lambda s: abs(s.score), reverse=True)
        return signals

    @staticmethod
    def _classify_strength(trend: float) -> str:
        if trend > 0.05:
            return "strong_bullish"
        elif trend > 0.015:
            return "bullish"
        elif trend < -0.05:
            return "strong_bearish"
        elif trend < -0.015:
            return "bearish"
        else:
            return "neutral"

    # ── Divergence Detection ─────────────────────────────────────────────────

    def _detect_divergences(self, features: FeatureSnapshot) -> list[DivergenceSignal]:
        """Detect divergences for all 4 key macro pairs."""
        divergences = []

        for pair_config in self.DIVERGENCE_PAIRS:
            div = self._detect_single_divergence(features, pair_config)
            divergences.append(div)

        return divergences

    def _detect_single_divergence(
        self, features: FeatureSnapshot, config: dict
    ) -> DivergenceSignal:
        """Detect divergence for a single pair configuration."""
        a_name = config["asset_a"]
        b_name = config["asset_b"]

        trend_a = self._get_trend(features, a_name)
        trend_b = self._get_trend(features, b_name)

        # Determine individual directions
        dir_a = self._trend_to_direction(trend_a)
        dir_b = self._trend_to_direction(trend_b)

        # Detect divergence
        is_diverging = (
            trend_a is not None
            and trend_b is not None
            and trend_a * trend_b < 0  # Opposite signs
            and abs(trend_a) > 0.01
            and abs(trend_b) > 0.01
        )

        # Classify divergence type
        div_type = "convergent"
        interpretation = ""
        evidence = []

        if is_diverging:
            if trend_a > 0 and trend_b < 0:
                # A rising, B falling
                div_type = "bearish_divergence"  # Risk: A's strength not confirmed by B
            elif trend_a < 0 and trend_b > 0:
                div_type = "bullish_divergence"  # Opportunity: B leading A higher

            interpretation = self._interpret_divergence(config, div_type, dir_a, dir_b)
            evidence = [
                f"{config['label_a']} trend: {dir_a} ({trend_a:+.2%})",
                f"{config['label_b']} trend: {dir_b} ({trend_b:+.2%})",
            ]
        else:
            interpretation = self._interpret_convergence(config, dir_a, dir_b)
            evidence = [
                (
                    f"{config['label_a']}: {dir_a} ({trend_a:+.2%})"
                    if trend_a
                    else f"{config['label_a']}: no data"
                ),
                (
                    f"{config['label_b']}: {dir_b} ({trend_b:+.2%})"
                    if trend_b
                    else f"{config['label_b']}: no data"
                ),
            ]

        significance = self._compute_significance(trend_a, trend_b, is_diverging)

        return DivergenceSignal(
            pair=config["pair"],
            asset_a=config["label_a"],
            asset_b=config["label_b"],
            direction_a=dir_a,
            direction_b=dir_b,
            is_diverging=is_diverging,
            divergence_type=div_type,
            significance=significance,
            interpretation=interpretation,
            evidence=evidence,
        )

    def _interpret_divergence(self, config: dict, div_type: str, dir_a: str, dir_b: str) -> str:
        """Interpret what a divergence means for this pair."""
        pair_key = config["pair"]

        if pair_key == "stocks_vs_credit":
            if div_type == "bearish_divergence":
                return config.get(
                    "bearish_description",
                    "Equities up but credit lagging — equity rally not confirmed by credit",
                )
            return config.get(
                "credit_leading_equity",
                "Credit leading equities — bond market signal",
            )

        elif pair_key == "usd_vs_gold":
            if div_type == "bearish_divergence":
                return "USD strengthening but gold also rising — possible safe-haven fear bid beneath the surface"
            return "Gold rising with USD weakening — classic dollar debasement / inflation hedge signal"

        elif pair_key == "yields_vs_equities":
            # TLT up = yields down; TLT down = yields up
            if dir_a == "up" and dir_b == "up":
                return "Treasuries and equities both bid — 'everything rally' liquidity regime"
            elif dir_a == "down" and dir_b == "down":
                return "Treasuries and equities both selling off — possible liquidity drain"
            elif dir_a == "down" and dir_b == "up":
                return "Bonds selling (yields up) but stocks up — growth optimism outweighing rate fears"
            return "Bonds bid (yields down) but stocks soft — defensive rotation, growth concerns"

        elif pair_key == "copper_vs_growth":
            if div_type == "bearish_divergence":
                return "Copper weak despite risk-on equity — industrial demand skepticism, growth divergence"
            return "Copper leading small caps higher — Dr. Copper confirms cyclical expansion"

        return f"{config['label_a']} {dir_a}, {config['label_b']} {dir_b}"

    def _interpret_convergence(self, config: dict, dir_a: str, dir_b: str) -> str:
        """Interpret convergent movement for a pair."""
        pair_key = config["pair"]

        if pair_key == "stocks_vs_credit":
            if dir_a == "up" and dir_b == "up":
                return "Equities and credit both rising — broad risk appetite, confirmed rally"
            elif dir_a == "down" and dir_b == "down":
                return "Equities and credit both weakening — broad risk-off"
            return "Mixed signals in equity-credit relationship"

        elif pair_key == "usd_vs_gold":
            if dir_a == "up" and dir_b == "up":
                return "USD and gold both rising — unusual, possible geopolitical hedging"
            elif dir_a == "down" and dir_b == "down":
                return "USD and gold both softening — risk appetite dominant, no haven demand"
            return "No clear USD-Gold signal"

        elif pair_key == "yields_vs_equities":
            if dir_a == "up" and dir_b == "up":
                return "Treasuries and equities both bid — accommodative financial conditions"
            return "Treasuries and equities moving in normal relationship"

        elif pair_key == "copper_vs_growth":
            if dir_a == "up" and dir_b == "up":
                return "Copper and small caps rising together — cyclical growth confirmed"
            elif dir_a == "down" and dir_b == "down":
                return "Copper and small caps both weak — cyclical slowdown signal"
            return "No clear copper-growth signal"

        return "Convergent movement — no divergence detected"

    @staticmethod
    def _compute_significance(
        trend_a: float | None,
        trend_b: float | None,
        is_diverging: bool,
    ) -> float:
        """Compute 0-1 significance score for the divergence."""
        if trend_a is None or trend_b is None:
            return 0.0

        mag = (abs(trend_a) + abs(trend_b)) / 2
        sig = min(1.0, mag * 10)

        if is_diverging:
            sig += 0.2  # Bonus for actual divergence

        return min(1.0, sig)

    # ── Regime Change Detection ──────────────────────────────────────────────

    def _detect_regime_change(
        self,
        features: FeatureSnapshot,
        current_regime: str,
    ) -> RegimeChangeSignal:
        """Detect if macro regime has shifted."""
        has_shifted = False
        shift_drivers = []
        shift_magnitude = 0.0

        if self._previous_regime and self._previous_regime != current_regime:
            has_shifted = True
            shift_drivers = self._identify_shift_drivers(features)
            shift_magnitude = 0.5  # Base magnitude for detected shift

        # Also check for nascent regime change via feature extremes
        extreme_count = 0
        for _, ind in features.indicators.items():
            change = ind.get(FeatureDimension.CHANGE_5D)
            trend = ind.get(FeatureDimension.TREND_20D)
            if change and trend and abs(change.value) > 0.03:
                extreme_count += 1

        if extreme_count >= 4 and not has_shifted:
            has_shifted = True
            shift_magnitude = min(1.0, extreme_count / 10)
            shift_drivers.append(f"{extreme_count} indicators with extreme 5-day moves")

        confidence = min(1.0, shift_magnitude + (len(shift_drivers) * 0.1))

        summary = (
            f"Regime {'shifted from ' + self._previous_regime + ' to ' + current_regime if has_shifted else 'stable at ' + current_regime}. "
            f"{len(shift_drivers)} drivers identified."
        )

        return RegimeChangeSignal(
            has_shifted=has_shifted,
            previous_regime=self._previous_regime or "unknown",
            current_regime=current_regime,
            shift_magnitude=shift_magnitude,
            shift_drivers=shift_drivers,
            confidence=confidence,
            summary=summary,
        )

    def _identify_shift_drivers(self, features: FeatureSnapshot) -> list[str]:
        """Identify which indicators drove the regime shift."""
        drivers = []
        for name, ind in features.indicators.items():
            change = ind.get(FeatureDimension.CHANGE_5D)
            if change and abs(change.value) > 0.02:
                direction = "up" if change.value > 0 else "down"
                drivers.append(f"{name} {direction} {change.value:+.2%}")
        return drivers[:5]  # Top 5

    # ── Acceleration Detection ───────────────────────────────────────────────

    def _detect_acceleration(self, features: FeatureSnapshot) -> list[str]:
        """Detect which trends are accelerating (momentum > trend)."""
        signals = []

        for name, ind in features.indicators.items():
            trend = ind.get(FeatureDimension.TREND_20D)
            momentum = ind.get(FeatureDimension.MOMENTUM)

            if trend is None or momentum is None:
                continue

            t_val = trend.value
            m_val = momentum.value

            if abs(m_val) > abs(t_val) * 1.5 and abs(m_val) > 0.01:
                direction = "加速上行" if m_val > 0 else "加速下行"
                signals.append(f"{name}: {direction} (trend={t_val:+.2%}, momentum={m_val:+.2%})")

        return signals

    # ── Summary ──────────────────────────────────────────────────────────────

    def _identify_strongest(self, cs: ChangeSignals) -> list[str]:
        """Identify top-3 most notable signals across all categories."""
        notable = []

        # Strong momentum
        for m in cs.momentum_signals[:4]:
            if abs(m.score) > 0.3:
                notable.append(f"{m.indicator}: {m.strength} (score={m.score:+.1f})")

        # Divergences
        for d in cs.divergence_signals:
            if d.is_diverging and d.significance > 0.3:
                notable.append(f"DIVERGENCE {d.asset_a} vs {d.asset_b}: {d.interpretation[:80]}")

        # Acceleration
        for a in cs.acceleration_signals[:3]:
            notable.append(a)

        return notable[:3]

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _get_trend(features: FeatureSnapshot, name: str) -> float | None:
        """Get 20-day trend value for indicator."""
        ind = features.get_indicator(name)
        if ind is None:
            return None
        fv = ind.get(FeatureDimension.TREND_20D)
        return fv.value if fv else None

    @staticmethod
    def _trend_to_direction(trend: float | None) -> str:
        """Convert trend value to direction label."""
        if trend is None:
            return "unknown"
        if trend > 0.005:
            return "up"
        elif trend < -0.005:
            return "down"
        else:
            return "flat"
