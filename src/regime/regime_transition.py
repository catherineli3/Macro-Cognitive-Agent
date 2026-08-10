"""RegimeTransitionDetector — estimates regime transition probabilities.

Uses a transition matrix with lead indicators to estimate:
    - Probability of transitioning to each possible next regime
    - Stability of current regime
    - Expected timing of change
    - Lead indicators to monitor

The transition matrix is parameterized by the current regime and
lead indicator readings (yield curve, credit spreads, VIX, etc.).
"""

from __future__ import annotations
from typing import Optional
from src.regime.schemas import RegimeTransitionModel, MacroRegime


# Base transition matrix: P(next_regime | current_regime)
# Values are unnormalized — normalized on the fly.
BASE_TRANSITION_MATRIX = {
    "expansion": {
        "expansion": 5.0, "late_cycle": 2.0, "inflation_shock": 1.0,
        "policy_tightening": 0.5, "liquidity_stress": 0.2, "credit_event": 0.1,
        "recovery": 0.2, "stable_growth": 2.0,
    },
    "late_cycle": {
        "expansion": 1.0, "late_cycle": 3.0, "inflation_shock": 3.0,
        "policy_tightening": 2.0, "liquidity_stress": 1.0, "credit_event": 1.0,
        "recovery": 0.5, "stable_growth": 1.0,
    },
    "inflation_shock": {
        "expansion": 0.5, "late_cycle": 1.0, "inflation_shock": 3.0,
        "policy_tightening": 3.0, "liquidity_stress": 2.0, "credit_event": 1.5,
        "recovery": 1.0, "stable_growth": 0.5,
    },
    "policy_tightening": {
        "expansion": 0.5, "late_cycle": 1.0, "inflation_shock": 1.0,
        "policy_tightening": 2.0, "liquidity_stress": 3.0, "credit_event": 2.0,
        "recovery": 1.5, "stable_growth": 0.5,
    },
    "liquidity_stress": {
        "expansion": 0.2, "late_cycle": 0.5, "inflation_shock": 0.5,
        "policy_tightening": 1.0, "liquidity_stress": 2.0, "credit_event": 4.0,
        "recovery": 2.0, "stable_growth": 0.3,
    },
    "credit_event": {
        "expansion": 0.1, "late_cycle": 0.1, "inflation_shock": 0.2,
        "policy_tightening": 0.3, "liquidity_stress": 1.0, "credit_event": 1.0,
        "recovery": 5.0, "stable_growth": 0.2,
    },
    "recovery": {
        "expansion": 3.0, "late_cycle": 1.0, "inflation_shock": 0.5,
        "policy_tightening": 0.3, "liquidity_stress": 0.2, "credit_event": 0.1,
        "recovery": 2.0, "stable_growth": 3.0,
    },
    "stable_growth": {
        "expansion": 2.0, "late_cycle": 1.5, "inflation_shock": 1.0,
        "policy_tightening": 1.0, "liquidity_stress": 0.5, "credit_event": 0.2,
        "recovery": 0.5, "stable_growth": 3.0,
    },
}


class RegimeTransitionDetector:
    """Estimates probability of regime transitions."""

    def __init__(self):
        self._transition_matrix = BASE_TRANSITION_MATRIX
        self._lead_indicator_history: dict[str, list[float]] = {}

    def estimate_transition(
        self,
        current_regime: MacroRegime,
        market_data: Optional[dict] = None,
        regime_history: Optional[list[dict]] = None,
    ) -> RegimeTransitionModel:
        """Estimate transition probabilities from current regime.

        Args:
            current_regime: Current MacroRegime classification.
            market_data: Current market indicators.
            regime_history: Optional recent regime history.

        Returns:
            RegimeTransitionModel with transition probabilities.
        """
        base = self._transition_matrix.get(
            current_regime.regime_label,
            self._transition_matrix["stable_growth"],
        )

        # Apply lead indicator adjustments
        adjusted = self._apply_indicators(base, market_data)

        # Normalize
        total = sum(adjusted.values()) or 1.0
        probs = {k: round(v / total, 3) for k, v in adjusted.items()}

        # Stability score: probability of staying in current regime
        stability = probs.get(current_regime.regime_label, 0.3)

        # Expected timing
        timing = self._estimate_timing(stability, market_data)

        # Lead indicators to watch
        lead_indicators = self._identify_lead_indicators(
            current_regime.regime_label, market_data
        )

        # Transition drivers
        drivers = self._identify_drivers(current_regime, market_data)

        return RegimeTransitionModel(
            current_regime=current_regime.regime_label,
            transition_drivers=drivers,
            target_probabilities=probs,
            stability_score=round(stability, 3),
            expected_change_timing=timing,
            lead_indicators=lead_indicators,
        )

    def _apply_indicators(
        self, base: dict[str, float], market: Optional[dict]
    ) -> dict[str, float]:
        """Modify transition probabilities based on lead indicators."""
        if not market:
            return dict(base)
        adjusted = dict(base)

        # Yield curve inversion → recession risk
        if market.get("yield_curve", 0.5) < -0.3:
            adjusted["credit_event"] = adjusted.get("credit_event", 0) * 2.5
            adjusted["recovery"] = adjusted.get("recovery", 0) * 2.0

        # High VIX → tail risk
        if market.get("vix", 18) > 30:
            adjusted["credit_event"] = adjusted.get("credit_event", 0) * 2.0
            adjusted["liquidity_stress"] = adjusted.get("liquidity_stress", 0) * 1.5

        # Credit spreads widening → stress
        if market.get("hy_spread", 350) > 550:
            adjusted["credit_event"] = adjusted.get("credit_event", 0) * 1.8

        # Dollar extreme → EM stress
        if abs(market.get("dxy_trend", 0)) > 6:
            adjusted["liquidity_stress"] = adjusted.get("liquidity_stress", 0) * 1.5

        return adjusted

    def _estimate_timing(
        self, stability: float, market: Optional[dict]
    ) -> str:
        if stability < 0.3:
            return "imminent (1-4 weeks)"
        if stability < 0.5:
            return "3-6 months"
        if stability < 0.7:
            return "6-12 months"
        return "no change expected (>12 months)"

    def _identify_lead_indicators(
        self, regime_label: str, market: Optional[dict]
    ) -> list[str]:
        """Identify which indicators to watch for this regime."""
        indicators_by_regime = {
            "expansion": ["Yield curve", "Inflation breakevens", "Capacity utilization", "Credit growth"],
            "late_cycle": ["Yield curve", "HY spreads", "Consumer confidence", "Housing starts"],
            "inflation_shock": ["CPI mom", "Wage growth", "Breakevens", "Commodity prices"],
            "policy_tightening": ["Swap spreads", "HY OAS", "Loan officer survey", "Repo rates"],
            "liquidity_stress": ["FRA-OIS spread", "Cross-currency basis", "SOFR-IORB", "TED spread"],
            "credit_event": ["CDX IG/HY", "OAS widening rate", "Funding stress", "CP issuance"],
            "recovery": ["PMI new orders", "Jobless claims", "Credit impulse", "Housing permits"],
            "stable_growth": ["Real rates", "Earnings growth", "Productivity", "Fiscal impulse"],
        }
        return indicators_by_regime.get(regime_label, ["VIX", "Yield curve", "HY spreads"])

    def _identify_drivers(
        self, regime: MacroRegime, market: Optional[dict]
    ) -> list[dict]:
        """Identify the key drivers pushing toward transition."""
        drivers = []
        if regime.monetary_stance == "tightening":
            drivers.append({"driver": "monetary_policy", "direction": "tightening", "impact": 0.7})
        if regime.credit_cycle in ("contraction", "peak"):
            drivers.append({"driver": "credit_conditions", "direction": "tightening", "impact": 0.6})
        if regime.dollar_regime == "strong":
            drivers.append({"driver": "dollar_strength", "direction": "tightening_global", "impact": 0.5})
        if regime.volatility_regime in ("high_vol", "crisis"):
            drivers.append({"driver": "volatility", "direction": "destabilizing", "impact": 0.8})
        if not drivers:
            drivers.append({"driver": "momentum", "direction": "steady_state", "impact": 0.3})
        return drivers
