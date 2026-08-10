"""Research Cycle — Autonomous Research Cycle (Milestone D).

Package that connects the existing V3 A+B+C capabilities into a complete,
self-driving daily research loop.

Architecture (Milestone D):
    Market Data → Framework Selection → Thesis Generation →
    Hypothesis Competition (A) → Transmission Reasoning (B) →
    Prediction → Outcome → Diagnosis → Postmortem →
    Evolution (C) → Memory Storage → Next Cycle

Core components:
    ResearchCycleEngine  — Main orchestrator (D1)
    FrameworkSelector    — Maps regime to active frameworks (D3)
    ThesisGenerator      — Upgrades hypotheses into theses (D4)
    ResearchMemory       — Persistent cycle history (D5)
    OutcomeTracker       — Tracks prediction outcomes (D6.1)
    Postmortem           — Post-cycle root cause analysis (D6.2)
"""

from src.research_cycle.cycle_engine import ResearchCycleEngine, CycleResult
from src.research_cycle.framework_selector import FrameworkSelector, FrameworkSelection
from src.research_cycle.thesis_generator import ThesisGenerator
from src.research_cycle.research_memory import (
    ResearchMemory,
    ResearchMemoryEntry,
    PostmortemReport,
)
from src.research_cycle.outcome_tracker import OutcomeTracker, PendingThesis
from src.research_cycle.postmortem import Postmortem

__all__ = [
    # Engine
    "ResearchCycleEngine",
    "CycleResult",
    # D3: Framework Activation
    "FrameworkSelector",
    "FrameworkSelection",
    # D4: Thesis Generation
    "ThesisGenerator",
    # D5: Research Memory
    "ResearchMemory",
    "ResearchMemoryEntry",
    "PostmortemReport",
    # D6: Outcome & Postmortem
    "OutcomeTracker",
    "PendingThesis",
    "Postmortem",
]
