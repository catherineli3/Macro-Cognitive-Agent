"""V11 Macro Summary Engine — Macro Research Intelligence Summary.

Replaces the old build_dynamic_summaries() with a 5-layer intelligence engine:
    Phase 1: MacroStateLayer   — 5-dim macro state from indicators
    Phase 2: ChangeDetector    — momentum / acceleration / divergence / regime change
    Phase 3: NarrativeGenerator — dominant narrative + evidence + uncertainty
    Phase 4: CIOBrief          — 7-section CIO-level macro brief
    Phase 5: SummaryEvaluator  — 5-dim quality scoring (target > 85)

All phases reuse existing infrastructure:
    - StateVectorBuilder  (Phase 1)
    - FeatureEngine       (Phase 2)
    - EvidenceSynthesizer (Phase 3-4)
    - NarrativeAnalyzer   (Phase 3)
    - MarketChallenge     (Phase 4)
    - ReasoningPipeline   (Phase 4)

Design principle: deterministic rules-based with zero LLM dependency.
"""

from src.summary_engine.change_detector import (
    ChangeDetector,
    ChangeSignals,
    DivergenceSignal,
    MomentumSignal,
    RegimeChangeSignal,
)
from src.summary_engine.cio_brief import CIOBrief, CIOBriefGenerator
from src.summary_engine.macro_state_layer import MacroState, MacroStateLayer, StateAssessment
from src.summary_engine.narrative_generator import (
    MacroNarrative,
    NarrativeGenerator,
)
from src.summary_engine.summary_evaluator import SummaryEvaluator, SummaryQuality

__all__ = [
    # Phase 1
    "MacroStateLayer",
    "MacroState",
    "StateAssessment",
    # Phase 2
    "ChangeDetector",
    "ChangeSignals",
    "MomentumSignal",
    "DivergenceSignal",
    "RegimeChangeSignal",
    # Phase 3
    "NarrativeGenerator",
    "MacroNarrative",
    # Phase 4
    "CIOBrief",
    "CIOBriefGenerator",
    # Phase 5
    "SummaryEvaluator",
    "SummaryQuality",
]
