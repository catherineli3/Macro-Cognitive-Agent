"""MacroStateVector — multi-dimensional macro state scoring.

Produces a 9-dimension state vector that captures the "macro weather."
Each dimension is scored 0-1 with supporting indicators and confidence.

Dimensions:
    Liquidity  — Fed policy, USD strength, financial conditions
    Credit     — HY spreads, IG performance, credit expansion/contraction
    Inflation  — CPI/PCE proxies, commodities, wage pressures
    Growth     — PMI proxies, copper, employment, retail
    Risk       — VIX, equity momentum, safe-haven demand
    Dollar     — DXY trend, rate differentials, capital flows
    Policy     — Rate expectations, QT/QE, fiscal stance
    AI_Capex   — Semiconductor, hyperscaler capex, AI investment cycle
    Employment — Jobless claims, payrolls, labor market tightness

This is the primary input to Mental Models and Hypothesis Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from src.data_pipeline.feature_engine import FeatureSnapshot, IndicatorFeatures
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Dimension Enum ──────────────────────────────────────────────────────────


class StateVectorDimension(Enum):
    """The 9 macro dimensions scored by the state vector."""

    LIQUIDITY = "Liquidity"
    CREDIT = "Credit"
    INFLATION = "Inflation"
    GROWTH = "Growth"
    RISK = "Risk_Appetite"
    DOLLAR = "Dollar"
    POLICY = "Policy"
    AI_CAPEX = "AI_Capex"
    EMPLOYMENT = "Employment"


# ── Data Classes ────────────────────────────────────────────────────────────


@dataclass
class DimensionScore:
    """Score for a single macro dimension."""

    dimension: StateVectorDimension
    score: float  # 0.0 - 1.0 (higher = more "risk-on" or expansionary)
    confidence: float  # 0.0 - 1.0
    direction: str  # tightening/easing, expansion/contraction, etc.
    drivers: list[str] = field(default_factory=list)  # Key indicators driving this score
    supporting_indicators: list[str] = field(default_factory=list)
    narrative_seeds: list[str] = field(default_factory=list)
    raw_values: dict[str, float] = field(default_factory=dict)


@dataclass
class MacroStateVector:
    """Complete multi-dimensional macro state assessment."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    dimensions: dict[StateVectorDimension, DimensionScore] = field(default_factory=dict)
    # Overall summary
    aggregate_score: float = 0.0  # Weighted average across dimensions
    dominant_theme: str = ""
    risk_regime: str = "normal"  # normal / cautious / risk_off / risk_on
    summary: str = ""

    def get(self, dim: StateVectorDimension) -> DimensionScore | None:
        return self.dimensions.get(dim)

    def is_tightening(self) -> bool:
        liq = self.get(StateVectorDimension.LIQUIDITY)
        return liq is not None and liq.direction == "tightening"

    def is_risk_off(self) -> bool:
        risk = self.get(StateVectorDimension.RISK)
        return risk is not None and risk.direction in ("risk_off", "caution")


# ── StateVectorBuilder ──────────────────────────────────────────────────────


class StateVectorBuilder:
    """Builds MacroStateVector from FeatureSnapshot.

    Each dimension is scored by aggregating its constituent indicators'
    features into a single directional score.

    Scoring logic is deliberately transparent and rules-based.
    Future iterations (M3+) will replace with model-driven scores.

    Usage:
        builder = StateVectorBuilder()
        state_vector = builder.build(feature_snapshot)
    """

    # ── Dimension Scoring Logic ─────────────────────────────────────────────
    # Each dimension specifies:
    #   indicators: which indicators feed into this dimension
    #   scoring: how to compute the 0-1 score (rules-based for M1)

    _DIMENSION_CONFIG: dict[StateVectorDimension, dict] = {
        StateVectorDimension.LIQUIDITY: {
            "indicators": ["DXY", "US10Y", "US2Y"],
            "high_score_bias": "easing",  # Higher score = easier liquidity
            "description": "Monetary/financial liquidity conditions",
        },
        StateVectorDimension.CREDIT: {
            "indicators": ["HYG", "LQD"],
            "high_score_bias": "expansion",
            "description": "Credit market health and spreads",
        },
        StateVectorDimension.INFLATION: {
            "indicators": ["Gold", "Oil"],
            "high_score_bias": "rising",
            "description": "Inflation pressures (commodities proxy)",
        },
        StateVectorDimension.GROWTH: {
            "indicators": ["Copper", "SP500", "Russell"],
            "high_score_bias": "expansion",
            "description": "Economic growth momentum",
        },
        StateVectorDimension.RISK: {
            "indicators": ["VIX", "SP500", "Nasdaq"],
            "high_score_bias": "risk_on",
            "description": "Market risk appetite",
        },
        StateVectorDimension.DOLLAR: {
            "indicators": ["DXY"],
            "high_score_bias": "strengthening",
            "description": "USD strength and direction",
        },
        StateVectorDimension.POLICY: {
            "indicators": ["US2Y", "US10Y"],
            "high_score_bias": "dovish",
            "description": "Monetary policy stance",
        },
        StateVectorDimension.AI_CAPEX: {
            "indicators": ["NVDA", "Semiconductor", "ASML", "TSMC"],
            "high_score_bias": "expansion",
            "description": "AI investment cycle health",
        },
        StateVectorDimension.EMPLOYMENT: {
            "indicators": ["SP500", "Russell"],  # Proxy until BLS data is connected
            "high_score_bias": "expansion",
            "description": "Labor market conditions (equity proxy)",
        },
    }

    def __init__(self) -> None:
        pass

    # ── Public API ──────────────────────────────────────────────────────────

    def build(self, features: FeatureSnapshot) -> MacroStateVector:
        """Build complete state vector from extracted features."""
        sv = MacroStateVector()

        for dim, config in self._DIMENSION_CONFIG.items():
            score = self._score_dimension(dim, config, features)
            sv.dimensions[dim] = score

        # Aggregate
        valid_scores = [s.score for s in sv.dimensions.values() if s.confidence > 0.3]
        sv.aggregate_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0.5

        # Dominant theme
        sv.dominant_theme = self._identify_dominant_theme(sv)

        # Risk regime
        sv.risk_regime = self._classify_risk_regime(sv)

        # Summary string
        sv.summary = self._build_summary(sv)

        logger.info(
            "state_vector_done | score=%.2f | theme=%s | regime=%s",
            sv.aggregate_score,
            sv.dominant_theme,
            sv.risk_regime,
        )
        return sv

    # ── Dimension Scoring ───────────────────────────────────────────────────

    def _score_dimension(
        self,
        dim: StateVectorDimension,
        config: dict,
        features: FeatureSnapshot,
    ) -> DimensionScore:
        """Score a single dimension from its constituent indicators."""
        indicator_names = config["indicators"]
        bias = config["high_score_bias"]

        scores: list[float] = []
        confidences: list[float] = []
        drivers: list[str] = []
        raw_values: dict[str, float] = {}

        for name in indicator_names:
            ind = features.get_indicator(name)
            if ind is None:
                continue

            raw_values[name] = ind.raw_value
            dim_score = self._indicator_to_dimension_score(ind, bias)
            if dim_score is not None:
                scores.append(dim_score)
                confidences.append(0.8)  # Default confidence for M1
                drivers.append(name)

        # Aggregate
        avg_score = sum(scores) / len(scores) if scores else 0.5
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.3

        direction = self._score_to_direction(avg_score, bias)

        return DimensionScore(
            dimension=dim,
            score=round(avg_score, 3),
            confidence=round(avg_conf, 3),
            direction=direction,
            drivers=drivers,
            supporting_indicators=indicator_names,
            raw_values=raw_values,
            narrative_seeds=self._generate_narrative_seeds(dim, avg_score, direction, drivers),
        )

    @staticmethod
    def _indicator_to_dimension_score(
        ind: IndicatorFeatures,
        bias: str,
    ) -> float | None:
        """Map an indicator's features to a 0-1 dimension score."""
        from src.data_pipeline.feature_engine import FeatureDimension

        trend = ind.get(FeatureDimension.TREND_20D)
        momentum = ind.get(FeatureDimension.MOMENTUM)
        regime = ind.get(FeatureDimension.REGIME)

        # Base score from trend
        base_score = 0.5
        if trend:
            # Map trend magnitude to score range
            trend_v = max(-0.1, min(0.1, trend.value))
            base_score = 0.5 + trend_v * 5.0
            base_score = max(0.0, min(1.0, base_score))

        # Momentum adjustment
        if momentum:
            mom = max(-0.05, min(0.05, momentum.value))
            base_score += mom * 2.0

        # Volatility adjustment
        volatility = ind.get(FeatureDimension.VOLATILITY)
        if volatility and volatility.value > 0.03:
            base_score -= 0.05  # Penalty for high vol

        # Regime adjustment (VIX, Gold)
        if regime:
            base_score = 0.5 * base_score + 0.5 * regime.value

        # Apply bias inversion if needed
        # Some dimensions want high score = tightening, others = easing
        if bias in ("tightening", "strengthening", "rising"):
            # For these, raw upward movement = higher score
            pass
        elif bias in ("hawkish", "risk_off", "contraction"):
            base_score = 1.0 - base_score

        return max(0.0, min(1.0, base_score))

    @staticmethod
    def _score_to_direction(score: float, bias: str) -> str:
        """Convert score to human-readable direction."""
        if score > 0.65:
            if bias == "tightening":
                return "tightening"
            elif bias == "strengthening":
                return "strengthening"
            elif bias == "rising":
                return "rising"
            elif bias == "hawkish":
                return "hawkish"
            elif bias == "dovish":
                return "dovish"
            elif bias == "risk_on":
                return "risk_on"
            else:
                return "expansion"
        elif score < 0.35:
            if bias == "tightening":
                return "easing"
            elif bias == "strengthening":
                return "weakening"
            elif bias == "rising":
                return "cooling"
            elif bias == "hawkish":
                return "dovish"
            elif bias == "dovish":
                return "hawkish"
            elif bias == "risk_on":
                return "risk_off"
            else:
                return "contraction"
        else:
            return "neutral"

    # ── Theme & Regime Detection ────────────────────────────────────────────

    def _identify_dominant_theme(self, sv: MacroStateVector) -> str:
        """Identify the dominant macro theme from extreme dimension scores."""
        themes: list[tuple[str, float]] = []

        for dim, score in sv.dimensions.items():
            if abs(score.score - 0.5) > 0.2:
                direction = score.direction
                themes.append((f"{dim.value}_{direction}", abs(score.score - 0.5)))

        themes.sort(key=lambda x: x[1], reverse=True)

        if not themes:
            return "mixed_signals"

        # Single dominant theme
        if len(themes) == 1 or themes[0][1] > themes[1][1] * 1.5:
            return themes[0][0]

        # Competing themes
        return f"{themes[0][0]}_vs_{themes[1][0]}"

    def _classify_risk_regime(self, sv: MacroStateVector) -> str:
        """Classify overall risk regime."""
        risk = sv.get(StateVectorDimension.RISK)
        liquidity = sv.get(StateVectorDimension.LIQUIDITY)
        credit = sv.get(StateVectorDimension.CREDIT)

        risk_val = risk.score if risk else 0.5
        liq_val = liquidity.score if liquidity else 0.5
        cr_val = credit.score if credit else 0.5

        composite = risk_val * 0.4 + liq_val * 0.3 + cr_val * 0.3

        if composite > 0.7:
            return "risk_on"
        elif composite < 0.3:
            return "risk_off"
        elif composite < 0.45:
            return "cautious"
        else:
            return "normal"

    def _build_summary(self, sv: MacroStateVector) -> str:
        """Build human-readable summary string."""
        parts = []
        for dim in StateVectorDimension:
            score = sv.get(dim)
            if score and score.confidence > 0.3:
                parts.append(
                    f"{dim.value}: {score.direction} "
                    f"(score={score.score:.2f}, conf={score.confidence:.2f})"
                )
        return " | ".join(parts)

    # ── Narrative Seeds ─────────────────────────────────────────────────────

    @staticmethod
    def _generate_narrative_seeds(
        dim: StateVectorDimension,
        score: float,
        direction: str,
        drivers: list[str],
    ) -> list[str]:
        """Generate possible narrative directions for M3 Narrative Engine."""
        seeds: list[str] = []

        if dim == StateVectorDimension.LIQUIDITY:
            if direction == "tightening":
                seeds = [
                    "Higher real yields → long duration pressure",
                    "Tight financial conditions → growth stock compression",
                    "USD strength feedback loop",
                ]
            elif direction == "easing":
                seeds = [
                    "Liquidity tailwind → risk asset bid",
                    "Lower real yields → duration relief",
                    "EM carry trade revival",
                ]

        elif dim == StateVectorDimension.CREDIT:
            if direction == "contraction":
                seeds = [
                    "Credit stress → equity risk premium repricing",
                    "HY underperformance → small cap pressure",
                ]
            elif direction == "expansion":
                seeds = [
                    "Credit expansion → equity multiple support",
                    "Low default risk → cyclical outperformance",
                ]

        elif dim == StateVectorDimension.INFLATION:
            if direction == "rising":
                seeds = [
                    "Inflation persistence → Fed hawkish risk",
                    "Commodity bid → resource sector rotation",
                ]
            elif direction == "cooling":
                seeds = [
                    "Inflation normalization → rate cut expectations",
                    "Real wage recovery → consumer discretionary upside",
                ]

        elif dim == StateVectorDimension.GROWTH:
            if direction == "expansion":
                seeds = [
                    "Growth acceleration → cyclical leadership",
                    "Earnings momentum → multiple expansion",
                ]
            elif direction == "contraction":
                seeds = [
                    "Growth scare → defensive rotation",
                    "Recession probability repricing",
                ]

        elif dim == StateVectorDimension.RISK:
            if direction == "risk_off":
                seeds = [
                    "Risk aversion → quality factor outperformance",
                    "Volatility regime shift → position reduction",
                ]
            elif direction == "risk_on":
                seeds = [
                    "Risk appetite recovery → beta chase",
                    "Low vol regime → carry strategies",
                ]

        elif dim == StateVectorDimension.DOLLAR:
            if direction == "strengthening":
                seeds = [
                    "Dollar strength → EM FX pressure",
                    "USD bid → commodity headwind",
                ]
            elif direction == "weakening":
                seeds = [
                    "Dollar weakness → EM relief rally",
                    "USD decline → commodity tailwind",
                ]

        elif dim == StateVectorDimension.POLICY:
            if direction == "hawkish":
                seeds = [
                    "Hawkish repricing → curve flattening",
                    "Rate trajectory uncertainty",
                ]
            elif direction == "dovish":
                seeds = [
                    "Dovish pivot → duration bid",
                    "Easing expectations → cyclical re-rating",
                ]

        elif dim == StateVectorDimension.AI_CAPEX:
            if direction == "expansion":
                seeds = [
                    "AI investment acceleration → semis leadership",
                    "Capex cycle intact → infrastructure build-out",
                ]
            elif direction == "contraction":
                seeds = [
                    "AI capex fatigue → semis correction risk",
                    "Hyperscaler spending slowdown → tech re-rating",
                ]

        return seeds
