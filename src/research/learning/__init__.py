"""V5.4 Continuous Learning — Learn from reasoning errors, not just predictions.

Don't just decrement confidence when a prediction fails.
Diagnose WHY:
    - Evidence wrong?
    - Narrative wrong?
    - Regime judgment wrong?
    - Counter not considered?
    - Time window wrong?

True learning is about improving reasoning, not adjusting weights.
"""

from src.research.learning.schemas import (
    LearningEvent,
    FailureDiagnosis,
    ImprovementAction,
    LearningLog,
    RootCauseCategory,
)

from src.research.learning.reasoning_feedback_v5 import ReasoningFeedbackV5
from src.research.learning.narrative_feedback import NarrativeFeedback
from src.research.learning.trade_feedback import TradeFeedback
from src.research.learning.root_cause_analyzer import RootCauseAnalyzer
from src.research.learning.learning_orchestrator import LearningOrchestrator

__all__ = [
    # Schemas
    "LearningEvent",
    "FailureDiagnosis",
    "ImprovementAction",
    "LearningLog",
    "RootCauseCategory",
    # Engines
    "ReasoningFeedbackV5",
    "NarrativeFeedback",
    "TradeFeedback",
    "RootCauseAnalyzer",
    "LearningOrchestrator",
]
