"""Phase 1: MacroStateLayer — 5-dimension macro state from raw indicators.

Takes the indicators dict (raw values from pipeline + Sina patch) and produces
a structured MacroState with 5 independent sub-assessments:

    inflation_state  — Is inflation cooling, stable, or accelerating?
    growth_state     — Is growth moderating, accelerating, or contracting?
    liquidity_state  — Are financial conditions easing, neutral, or tightening?
    credit_state     — Is credit expanding, stable, or contracting?
    risk_state       — Is risk appetite risk-on, neutral, or risk-off?

Each sub-state includes:
    - level (categorical)
    - direction (trending direction)
    - momentum (is the direction accelerating or decelerating)
    - confidence (0-1)
    - key_indicators (which indicators drive this assessment)
    - narrative_seeds (possible narrative threads)

Reuses: StateVectorBuilder.dimensions for directional scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from src.data_pipeline.feature_engine import FeatureSnapshot, IndicatorFeatures, FeatureDimension
from src.data_pipeline.state_vector import (
    MacroStateVector,
    StateVectorBuilder,
    StateVectorDimension,
    DimensionScore,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════════


class MacroCondition(Enum):
    """Categorical macro condition levels."""
    LOW = "low"
    MODERATE = "moderate"
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    TIGHT = "tight"
    LOOSE = "loose"
    EXPANDING = "expanding"
    CONTRACTING = "contracting"
    STABLE = "stable"
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"


class MomentumState(Enum):
    """Whether a condition is accelerating, decelerating, or stable."""
    ACCELERATING = "accelerating"
    DECELERATING = "decelerating"
    STABLE = "stable"
    REVERSING = "reversing"


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class StateAssessment:
    """Assessment of a single macro state dimension."""

    name: str  # "inflation", "growth", "liquidity", "credit", "risk"
    level: str  # categorical: "cooling", "moderating", "easing", etc.
    direction: str  # trending direction
    momentum: str  # "accelerating", "decelerating", "stable", "reversing"
    confidence: float  # 0.0 - 1.0
    score: float  # 0.0 - 1.0 numerical score
    key_indicators: list[str] = field(default_factory=list)
    indicator_values: dict[str, float] = field(default_factory=dict)
    driver_changes: list[str] = field(default_factory=list)
    narrative_seeds: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "direction": self.direction,
            "momentum": self.momentum,
            "confidence": self.confidence,
            "score": self.score,
            "key_indicators": self.key_indicators,
            "indicator_values": self.indicator_values,
            "driver_changes": self.driver_changes,
            "narrative_seeds": self.narrative_seeds,
        }


@dataclass
class MacroState:
    """Complete 5-dimension macro state snapshot."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    inflation_state: Optional[StateAssessment] = None
    growth_state: Optional[StateAssessment] = None
    liquidity_state: Optional[StateAssessment] = None
    credit_state: Optional[StateAssessment] = None
    risk_state: Optional[StateAssessment] = None

    overall_risk_regime: str = "normal"
    aggregate_score: float = 0.5

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "inflation_state": self.inflation_state.to_dict() if self.inflation_state else None,
            "growth_state": self.growth_state.to_dict() if self.growth_state else None,
            "liquidity_state": self.liquidity_state.to_dict() if self.liquidity_state else None,
            "credit_state": self.credit_state.to_dict() if self.credit_state else None,
            "risk_state": self.risk_state.to_dict() if self.risk_state else None,
            "overall_risk_regime": self.overall_risk_regime,
            "aggregate_score": self.aggregate_score,
        }

    def all_momentum_directions(self) -> list[tuple[str, str, str]]:
        """Return [(name, direction, momentum), ...] for all states."""
        result = []
        for name, attr in [
            ("inflation", self.inflation_state),
            ("growth", self.growth_state),
            ("liquidity", self.liquidity_state),
            ("credit", self.credit_state),
            ("risk", self.risk_state),
        ]:
            if attr:
                result.append((name, attr.direction, attr.momentum))
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# MacroStateLayer
# ═══════════════════════════════════════════════════════════════════════════════


class MacroStateLayer:
    """Build 5-dim macro state from indicators + feature snapshot.

    Reuses Existing Components:
        - StateVectorBuilder → dimension scoring
        - FeatureEngine → trend/momentum features

    Usage:
        layer = MacroStateLayer()
        state = layer.build(indicators_dict, feature_snapshot, state_vector)
    """

    # ── Inflation thresholds ─────────────────────────────────────────────
    INFLATION_LEVELS = {
        "low": (0.0, 1.5, "cooling"),
        "moderate": (1.5, 2.5, "benign"),
        "normal": (2.5, 3.5, "sticky"),
        "elevated": (3.5, 5.0, "elevated"),
        "high": (5.0, float("inf"), "runaway"),
    }

    # ── Growth thresholds ────────────────────────────────────────────────
    GROWTH_LEVELS = {
        "low": (-float("inf"), 1.0, "contracting"),
        "moderate": (1.0, 2.0, "slow"),
        "normal": (2.0, 3.0, "moderate"),
        "elevated": (3.0, 5.0, "strong"),
        "high": (5.0, float("inf"), "overheating"),
    }

    def __init__(self) -> None:
        self._sv_builder = StateVectorBuilder()

    def build(
        self,
        indicators: dict[str, dict],
        features: FeatureSnapshot,
        state_vector: MacroStateVector,
    ) -> MacroState:
        """Build complete 5-dim macro state.

        Args:
            indicators: Raw indicators dict {name: {raw_value, ...}}
            features: FeatureSnapshot from FeatureEngine
            state_vector: MacroStateVector from StateVectorBuilder
        """
        ms = MacroState()

        ms.inflation_state = self._assess_inflation(indicators, features, state_vector)
        ms.growth_state = self._assess_growth(indicators, features, state_vector)
        ms.liquidity_state = self._assess_liquidity(indicators, features, state_vector)
        ms.credit_state = self._assess_credit(indicators, features, state_vector)
        ms.risk_state = self._assess_risk(indicators, features, state_vector)

        ms.overall_risk_regime = state_vector.risk_regime
        ms.aggregate_score = self._compute_aggregate(ms, state_vector)

        logger.info(
            "macro_state_layer_done | "
            "inflation=%s growth=%s liquidity=%s credit=%s risk=%s | "
            "regime=%s score=%.2f",
            ms.inflation_state.direction if ms.inflation_state else "?",
            ms.growth_state.direction if ms.growth_state else "?",
            ms.liquidity_state.direction if ms.liquidity_state else "?",
            ms.credit_state.direction if ms.credit_state else "?",
            ms.risk_state.direction if ms.risk_state else "?",
            ms.overall_risk_regime,
            ms.aggregate_score,
        )
        return ms

    # ── Individual State Assessments ─────────────────────────────────────────

    def _assess_inflation(
        self,
        indicators: dict,
        features: FeatureSnapshot,
        sv: MacroStateVector,
    ) -> StateAssessment:
        """Assess inflation state from CPI + Gold + Oil + VIX."""
        cpi_val = self._safe_indicator_value(indicators, "CPI", "CPI_YoY")
        gold_trend = self._get_trend(features, "Gold")
        oil_trend = self._get_trend(features, "Oil")
        sv_dim = sv.get(StateVectorDimension.INFLATION)

        # Determine level from CPI
        level = "normal"
        for lvl, (lo, hi, label) in self.INFLATION_LEVELS.items():
            if lo <= cpi_val < hi:
                level = label
                break

        # Score from state vector
        score = sv_dim.score if sv_dim else 0.5

        # Direction
        if score > 0.65:
            direction = "rising"
        elif score < 0.35:
            direction = "cooling"
        else:
            direction = "stable"

        # Momentum from Gold + Oil trends
        momentum = self._infer_momentum([gold_trend, oil_trend])

        key_indicators = ["CPI_YoY", "Gold", "Oil"]
        indicator_values = {}
        if cpi_val > 0:
            indicator_values["CPI_YoY"] = cpi_val
        gld = self._safe_indicator_value(indicators, "Gold")
        if gld > 0:
            indicator_values["Gold"] = gld
        wti = self._safe_indicator_value(indicators, "WTI")
        if wti > 0:
            indicator_values["WTI"] = wti

        narrative_seeds = [
            f"Inflation {direction} — CPI at {cpi_val:.1f}%",
            f"Commodity signal: Gold {'rising' if gold_trend and gold_trend > 0 else 'flat'}",
        ]

        return StateAssessment(
            name="inflation",
            level=level,
            direction=direction,
            momentum=momentum,
            confidence=sv_dim.confidence if sv_dim else 0.6,
            score=score,
            key_indicators=key_indicators,
            indicator_values=indicator_values,
            driver_changes=self._detect_driver_changes(
                features, ["Gold", "Oil"], lookback=1
            ),
            narrative_seeds=narrative_seeds,
        )

    def _assess_growth(
        self,
        indicators: dict,
        features: FeatureSnapshot,
        sv: MacroStateVector,
    ) -> StateAssessment:
        """Assess growth state from Copper + SP500 + Russell + GDP."""
        gdp_val = self._safe_indicator_value(indicators, "GDP", "GDP_YoY")
        copper_trend = self._get_trend(features, "Copper")
        spx_trend = self._get_trend(features, "SP500")
        russell_trend = self._get_trend(features, "Russell")
        sv_dim = sv.get(StateVectorDimension.GROWTH)

        level = "moderating"
        score = sv_dim.score if sv_dim else 0.5

        if score > 0.65:
            direction = "expanding"
            level = "strong"
        elif score < 0.35:
            direction = "contracting"
            level = "slow"
        else:
            direction = "moderating"
            level = "moderate"

        momentum = self._infer_momentum([copper_trend, spx_trend, russell_trend])

        key_indicators = ["Copper", "SP500", "Russell", "GDP"]
        indicator_values = {
            "SP500": self._safe_indicator_value(indicators, "SPX"),
            "Copper": self._safe_indicator_value(indicators, "Copper"),
            "Russell": self._safe_indicator_value(indicators, "Russell"),
        }
        if gdp_val > 0:
            indicator_values["GDP"] = gdp_val

        narrative_seeds = [
            f"Growth {direction} — composite score {score:.2f}",
            f"Dr. Copper {'positive' if copper_trend and copper_trend > 0 else 'negative'} signal",
        ]

        return StateAssessment(
            name="growth",
            level=level,
            direction=direction,
            momentum=momentum,
            confidence=sv_dim.confidence if sv_dim else 0.6,
            score=score,
            key_indicators=key_indicators,
            indicator_values=indicator_values,
            driver_changes=self._detect_driver_changes(
                features, ["Copper", "SP500", "Russell"], lookback=1
            ),
            narrative_seeds=narrative_seeds,
        )

    def _assess_liquidity(
        self,
        indicators: dict,
        features: FeatureSnapshot,
        sv: MacroStateVector,
    ) -> StateAssessment:
        """Assess liquidity from DXY + US10Y + US2Y (TLT + SHY)."""
        dxy_trend = self._get_trend(features, "DXY")
        tlt_trend = self._get_trend(features, "US10Y")  # TLT = long duration proxy
        sv_dim = sv.get(StateVectorDimension.LIQUIDITY)

        score = sv_dim.score if sv_dim else 0.5

        if score > 0.65:
            direction = "easing"
            level = "loose"
        elif score < 0.35:
            direction = "tightening"
            level = "tight"
        else:
            direction = "neutral"
            level = "normal"

        momentum = self._infer_momentum([dxy_trend, tlt_trend])

        key_indicators = ["DXY", "TLT", "SHY"]
        indicator_values = {
            "DXY": self._safe_indicator_value(indicators, "DXY"),
            "TLT": self._safe_indicator_value(indicators, "US10Y"),
            "SHY": self._safe_indicator_value(indicators, "US2Y"),
        }

        narrative_seeds = [
            f"Financial conditions {direction}",
            f"DXY {'strengthening' if dxy_trend and dxy_trend > 0 else 'weakening'}",
        ]

        return StateAssessment(
            name="liquidity",
            level=level,
            direction=direction,
            momentum=momentum,
            confidence=sv_dim.confidence if sv_dim else 0.6,
            score=score,
            key_indicators=key_indicators,
            indicator_values=indicator_values,
            driver_changes=self._detect_driver_changes(
                features, ["DXY", "US10Y", "US2Y"], lookback=1
            ),
            narrative_seeds=narrative_seeds,
        )

    def _assess_credit(
        self,
        indicators: dict,
        features: FeatureSnapshot,
        sv: MacroStateVector,
    ) -> StateAssessment:
        """Assess credit from HYG + LQD + BND."""
        hyg_trend = self._get_trend(features, "HYG")
        lqd_trend = self._get_trend(features, "LQD")
        bnd_trend = self._get_trend(features, "Bond_Market")
        sv_dim = sv.get(StateVectorDimension.CREDIT)

        score = sv_dim.score if sv_dim else 0.5

        if score > 0.65:
            direction = "expanding"
            level = "healthy"
        elif score < 0.35:
            direction = "contracting"
            level = "stressed"
        else:
            direction = "stable"
            level = "normal"

        momentum = self._infer_momentum([hyg_trend, lqd_trend, bnd_trend])

        key_indicators = ["HYG", "LQD", "BND"]
        indicator_values = {
            "HYG": self._safe_indicator_value(indicators, "HYG"),
            "LQD": self._safe_indicator_value(indicators, "LQD"),
        }

        narrative_seeds = [
            f"Credit conditions {direction}",
            f"HYG {'bid' if hyg_trend and hyg_trend > 0 else 'offer'} signal",
        ]

        return StateAssessment(
            name="credit",
            level=level,
            direction=direction,
            momentum=momentum,
            confidence=sv_dim.confidence if sv_dim else 0.6,
            score=score,
            key_indicators=key_indicators,
            indicator_values=indicator_values,
            driver_changes=self._detect_driver_changes(
                features, ["HYG", "LQD"], lookback=1
            ),
            narrative_seeds=narrative_seeds,
        )

    def _assess_risk(
        self,
        indicators: dict,
        features: FeatureSnapshot,
        sv: MacroStateVector,
    ) -> StateAssessment:
        """Assess risk appetite from VIX + SP500 + Nasdaq."""
        vix_trend = self._get_trend(features, "VIX")
        spx_trend = self._get_trend(features, "SP500")
        nasdaq_trend = self._get_trend(features, "Nasdaq")
        sv_dim = sv.get(StateVectorDimension.RISK)

        score = sv_dim.score if sv_dim else 0.5

        if score > 0.65:
            direction = "risk_on"
            level = "appetite"
        elif score < 0.35:
            direction = "risk_off"
            level = "aversion"
        else:
            direction = "neutral"
            level = "balanced"

        momentum = self._infer_momentum([spx_trend, nasdaq_trend, -vix_trend if vix_trend else 0])

        key_indicators = ["VIX", "SP500", "Nasdaq"]
        indicator_values = {
            "VIX": self._safe_indicator_value(indicators, "VIX"),
            "SP500": self._safe_indicator_value(indicators, "SPX"),
            "Nasdaq": self._safe_indicator_value(indicators, "Nasdaq"),
        }

        narrative_seeds = [
            f"Risk {direction} — composite {score:.2f}",
            f"VIX {'elevated' if vix_trend and vix_trend > 0.03 else 'suppressed'}",
        ]

        return StateAssessment(
            name="risk",
            level=level,
            direction=direction,
            momentum=momentum,
            confidence=sv_dim.confidence if sv_dim else 0.6,
            score=score,
            key_indicators=key_indicators,
            indicator_values=indicator_values,
            driver_changes=self._detect_driver_changes(
                features, ["VIX", "SP500", "Nasdaq"], lookback=1
            ),
            narrative_seeds=narrative_seeds,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_indicator_value(indicators: dict, *keys: str) -> float:
        """Safely retrieve raw_value from indicators dict."""
        for key in keys:
            val = indicators.get(key, {}).get("raw_value")
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue
        return 0.0

    @staticmethod
    def _get_trend(features: FeatureSnapshot, indicator_name: str) -> Optional[float]:
        """Get TREND_20D feature value for an indicator."""
        ind = features.get_indicator(indicator_name)
        if ind is None:
            return None
        fv = ind.get(FeatureDimension.TREND_20D)
        return fv.value if fv else None

    @staticmethod
    def _infer_momentum(trends: list[Optional[float]]) -> str:
        """Infer momentum state from multiple trend values."""
        valid = [t for t in trends if t is not None]
        if not valid:
            return "stable"

        avg = sum(valid) / len(valid)

        if avg > 0.03:
            return "accelerating"
        elif avg < -0.03:
            return "decelerating"
        else:
            return "stable"

    def _detect_driver_changes(
        self,
        features: FeatureSnapshot,
        indicator_names: list[str],
        lookback: int = 1,
    ) -> list[str]:
        """Detect which indicators changed direction recently."""
        changes = []
        for name in indicator_names:
            ind = features.get_indicator(name)
            if ind is None:
                continue
            change = ind.get(FeatureDimension.CHANGE_5D)
            trend = ind.get(FeatureDimension.TREND_20D)
            if change and trend and change.value * trend.value < 0:
                # Short-term change opposes trend → possible reversal
                changes.append(f"{name}: short-term reversal signal")
        return changes

    def _compute_aggregate(
        self, ms: MacroState, sv: MacroStateVector
    ) -> float:
        """Compute weighted aggregate from all dimension scores."""
        scores = []
        weights = []

        for attr, weight in [
            (ms.inflation_state, 0.20),
            (ms.growth_state, 0.25),
            (ms.liquidity_state, 0.20),
            (ms.credit_state, 0.15),
            (ms.risk_state, 0.20),
        ]:
            if attr and attr.confidence > 0.3:
                scores.append(attr.score)
                weights.append(weight)

        if not scores:
            return sv.aggregate_score

        total_w = sum(weights)
        if total_w == 0:
            return 0.5

        return sum(s * w for s, w in zip(scores, weights)) / total_w
