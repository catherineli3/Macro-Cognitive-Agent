"""Reflexivity Schemas — Data structures for reflexivity analysis.

Key concepts (from Soros):
    - MarketBelief: A collective belief held by market participants
    - ReflexivityCycle: Narrative → Capital → Price → Narrative loop
    - CapitalFlowSnapshot: Capital movement signals at a point in time
    - ReflexivityReport: Full reflexivity analysis output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class MarketBelief:
    """A collective market belief — the "participant bias" in Soros framework.

    Market beliefs drive behavior, and behavior (via prices) reinforces or
    challenges the belief — this is the core reflexivity mechanism.
    """

    belief_id: str = ""
    title: str = ""  # e.g., "Fed will cut rates in Q3"
    description: str = ""

    # Belief properties
    category: str = ""  # "monetary" / "growth" / "inflation" / "risk" / "structural"
    strength: float = 0.0  # 0-1: how strongly held
    consensus_level: float = 0.0  # 0-1: how widely shared
    evidence_support: float = 0.0  # -1 to 1: evidence alignment

    # Reflexivity properties
    is_self_reinforcing: bool = False
    reinforcement_mechanism: str = ""  # How price action reinforces this belief
    vulnerability_to_disconfirmation: float = 0.0  # 0-1: how fragile

    # Timing
    first_observed: str = ""  # ISO timestamp
    last_updated: str = ""
    stage: str = ""  # "forming" / "consensus" / "extreme" / "challenged" / "broken"

    # Risk
    crowding_risk: float = 0.0  # 0-1: how crowded the trade is
    reversal_magnitude_estimate: str = ""  # "small" / "moderate" / "severe" / "catastrophic"

    def to_dict(self) -> dict:
        return {
            "belief_id": self.belief_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "strength": self.strength,
            "consensus_level": self.consensus_level,
            "evidence_support": self.evidence_support,
            "is_self_reinforcing": self.is_self_reinforcing,
            "reinforcement_mechanism": self.reinforcement_mechanism,
            "vulnerability": self.vulnerability_to_disconfirmation,
            "first_observed": self.first_observed,
            "last_updated": self.last_updated,
            "stage": self.stage,
            "crowding_risk": self.crowding_risk,
            "reversal_magnitude": self.reversal_magnitude_estimate,
        }


@dataclass
class CapitalFlowSnapshot:
    """Capital flow data for one point in time.

    Tracks money movement across asset classes, sectors, and regions —
    the capital leg of the Narrative → Capital → Price triangle.
    """

    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Equity flows
    equity_flow_direction: str = ""  # "inflow" / "outflow" / "neutral"
    equity_flow_magnitude: str = ""  # "strong" / "moderate" / "weak"
    sector_rotation: list[dict] = field(default_factory=list)
    # e.g., [{"from": "tech", "to": "energy", "strength": 0.7}]

    # Fixed income flows
    bond_flow_direction: str = ""
    duration_positioning: str = ""  # "long" / "neutral" / "short"
    credit_flow_direction: str = ""

    # Currency flows
    usd_flow_direction: str = ""
    em_fx_flow_direction: str = ""

    # Commodity flows
    gold_flow_direction: str = ""
    oil_flow_signal: str = ""

    # Aggregate
    risk_appetite_flow: str = ""  # "risk-on" / "risk-off" / "neutral"
    flow_momentum: float = 0.0  # -1 to 1: accelerating / decelerating

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "equity": {
                "direction": self.equity_flow_direction,
                "magnitude": self.equity_flow_magnitude,
                "sector_rotation": self.sector_rotation,
            },
            "fixed_income": {
                "direction": self.bond_flow_direction,
                "duration": self.duration_positioning,
                "credit": self.credit_flow_direction,
            },
            "currency": {
                "usd": self.usd_flow_direction,
                "em_fx": self.em_fx_flow_direction,
            },
            "commodity": {
                "gold": self.gold_flow_direction,
                "oil": self.oil_flow_signal,
            },
            "aggregate": {
                "risk_appetite": self.risk_appetite_flow,
                "flow_momentum": self.flow_momentum,
            },
        }


@dataclass
class ReflexivityCycle:
    """A detected reflexivity cycle — the core Soros concept.

    The cycle:
        1. Narrative forms (participant bias)
        2. Capital flows follow (self-fulfilling)
        3. Price moves in direction of narrative (confirmation)
        4. Narrative strengthens (reinforcement)
        5. Cycle continues until "moment of truth" (disconfirmation)

    This is the boom-bust sequence.
    """

    cycle_id: str = ""
    title: str = ""
    description: str = ""

    # The three nodes of the cycle
    narrative_driver: str = ""  # What story drives this cycle
    capital_flow_direction: str = ""  # Where money is flowing
    price_feedback: str = ""  # How prices confirm the narrative

    # Cycle state
    stage: str = ""  # "forming" / "accelerating" / "extreme" / "cracking" / "reversing"
    self_reinforcement_score: float = 0.0  # 0-1: how self-reinforcing
    cycle_maturity: float = 0.0  # 0-1: how far along the cycle
    estimated_duration: str = ""  # "weeks" / "months" / "quarters"

    # Breaking point analysis
    break_trigger_candidates: list[dict] = field(default_factory=list)
    # e.g., [{"trigger": "CPI > 4%", "impact": "narrative reversal", "probability": 0.3}]
    vulnerability_score: float = 0.0  # 0-1: cycle fragility

    # Historical analogs
    historical_analogs: list[str] = field(default_factory=list)
    # e.g., ["1999 dot-com boom", "2006 housing bubble"]

    # Asset impact
    favored_assets: list[str] = field(default_factory=list)
    unfavored_assets: list[str] = field(default_factory=list)
    reversal_candidates: list[str] = field(default_factory=list)

    # Meta
    detected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "title": self.title,
            "description": self.description,
            "narrative_driver": self.narrative_driver,
            "capital_flow_direction": self.capital_flow_direction,
            "price_feedback": self.price_feedback,
            "stage": self.stage,
            "self_reinforcement_score": self.self_reinforcement_score,
            "cycle_maturity": self.cycle_maturity,
            "estimated_duration": self.estimated_duration,
            "break_triggers": self.break_trigger_candidates,
            "vulnerability_score": self.vulnerability_score,
            "historical_analogs": self.historical_analogs,
            "favored_assets": self.favored_assets,
            "unfavored_assets": self.unfavored_assets,
            "reversal_candidates": self.reversal_candidates,
            "detected_at": self.detected_at,
            "confidence": self.confidence,
        }


@dataclass
class ReflexivityReport:
    """Complete reflexivity analysis output."""

    report_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Active beliefs
    active_beliefs: list[MarketBelief] = field(default_factory=list)

    # Latest capital flow
    capital_flows: CapitalFlowSnapshot | None = None

    # Detected cycles
    detected_cycles: list[ReflexivityCycle] = field(default_factory=list)

    # Summary
    reflexivity_score: float = 0.0  # Overall reflexivity intensity (0-1)
    most_dangerous_cycle: ReflexivityCycle | None = None
    key_warning_signals: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "reflexivity_score": self.reflexivity_score,
            "active_beliefs_count": len(self.active_beliefs),
            "detected_cycles_count": len(self.detected_cycles),
            "cycles": [c.to_dict() for c in self.detected_cycles],
            "most_dangerous_cycle": (
                self.most_dangerous_cycle.to_dict() if self.most_dangerous_cycle else None
            ),
            "key_warnings": self.key_warning_signals,
            "capital_flows": self.capital_flows.to_dict() if self.capital_flows else None,
            "summary": self.summary,
        }
