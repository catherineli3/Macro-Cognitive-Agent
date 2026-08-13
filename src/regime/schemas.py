"""Regime Engine schemas — regime classification and historical analogy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class MacroRegime:
    """Classification of the current macroeconomic regime."""

    regime_id: str = ""
    regime_label: str = ""
    confidence: float = 0.5
    growth_phase: str = ""
    inflation_regime: str = ""
    monetary_stance: str = ""
    credit_cycle: str = ""
    dollar_regime: str = ""
    volatility_regime: str = ""
    transition_probability: float = 0.0
    transition_direction: str = ""
    early_warning_signals: list[str] = field(default_factory=list)
    historical_period_label: str = ""

    def to_dict(self) -> dict:
        return {
            "regime_label": self.regime_label,
            "confidence": self.confidence,
            "growth_phase": self.growth_phase,
            "inflation_regime": self.inflation_regime,
            "monetary_stance": self.monetary_stance,
            "credit_cycle": self.credit_cycle,
            "dollar_regime": self.dollar_regime,
            "volatility_regime": self.volatility_regime,
            "transition_probability": self.transition_probability,
            "transition_direction": self.transition_direction,
            "historical_period_label": self.historical_period_label,
        }


@dataclass
class HistoricalAnalog:
    """A historical period that resembles the current regime."""

    period_label: str = ""
    period_name: str = ""
    similarity_score: float = 0.0
    growth_profile: str = ""
    inflation_profile: str = ""
    policy_response: str = ""
    market_outcome: str = ""
    resolution: str = ""
    duration_months: int = 0
    max_drawdown_pct: float = 0.0
    key_lessons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "period_label": self.period_label,
            "period_name": self.period_name,
            "similarity_score": self.similarity_score,
            "growth_profile": self.growth_profile,
            "inflation_profile": self.inflation_profile,
            "policy_response": self.policy_response,
            "market_outcome": self.market_outcome,
            "resolution": self.resolution,
            "duration_months": self.duration_months,
        }


@dataclass
class RegimeTransitionModel:
    """Models the probability of regime transition."""

    current_regime: str = ""
    transition_drivers: list[dict] = field(default_factory=list)
    target_probabilities: dict[str, float] = field(default_factory=dict)
    stability_score: float = 0.5
    expected_change_timing: str = ""
    lead_indicators: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "current_regime": self.current_regime,
            "target_probabilities": self.target_probabilities,
            "stability_score": self.stability_score,
            "expected_change_timing": self.expected_change_timing,
            "lead_indicators": self.lead_indicators,
        }


@dataclass
class RegimeReport:
    """Complete regime analysis report."""

    report_id: str = ""
    date: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    current_regime: MacroRegime = field(default_factory=MacroRegime)
    transition_model: RegimeTransitionModel = field(default_factory=RegimeTransitionModel)
    historical_analogs: list[HistoricalAnalog] = field(default_factory=list)
    top_analog: HistoricalAnalog | None = None
    reflexivity_state: str = ""
    capital_flow_context: str = ""
    where_in_cycle: str = ""
    key_implications: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "date": self.date,
            "current_regime": self.current_regime.to_dict(),
            "transition_model": self.transition_model.to_dict(),
            "top_analog": self.top_analog.to_dict() if self.top_analog else None,
            "where_in_cycle": self.where_in_cycle,
            "key_implications": self.key_implications,
        }
