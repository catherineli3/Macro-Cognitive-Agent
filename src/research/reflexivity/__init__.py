"""Reflexivity Engine — V3.4 Soros-style reflexivity analysis.

Core insight: Markets don't just reflect fundamentals — they change them.

The Reflexivity Engine detects feedback loops where:
    Narrative → Capital Flows → Price Action → Narrative Reinforcement
    (participant bias)    (self-fulfilling)    (confirmation)

Three components:
    MarketBeliefModel — Tracks the formation and evolution of market beliefs
    CapitalFlowTracker — Tracks capital flows as narrative evidence
    ReflexivityCycleDetector — Detects boom-bust self-reinforcing cycles
"""

from src.research.reflexivity.schemas import (
    MarketBelief,
    CapitalFlowSnapshot,
    ReflexivityCycle,
    ReflexivityReport,
)
from src.research.reflexivity.market_belief_model import (
    MarketBeliefModel,
)
from src.research.reflexivity.capital_flow_tracker import (
    CapitalFlowTracker,
)
from src.research.reflexivity.reflexivity_cycle_detector import (
    ReflexivityCycleDetector,
)

__all__ = [
    # Schemas
    "MarketBelief",
    "CapitalFlowSnapshot",
    "ReflexivityCycle",
    "ReflexivityReport",
    # Engines
    "MarketBeliefModel",
    "CapitalFlowTracker",
    "ReflexivityCycleDetector",
]
