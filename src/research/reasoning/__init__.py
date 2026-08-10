""""V10 Reasoning Engine — Professional macro research reasoning.

Core principle: Deterministic reasoning before LLM synthesis.
LLM is ONLY called at Step 7 (synthesis) and Step 9 (rewrite) — all other steps are pure computation.

V10 Sprint 1:   Multi-pass Reasoning Engine (8 steps)
V10 Sprint 2:   Dynamic Prompt Routing (domain-specific prompts)
V10 Sprint 3:   Research Memo Self-Review (review → critic → rewrite → score loop)
V10 Sprint 4:   Continuous Learning Loop (diagnose → belief → prompt → reasoning update)
V10 Sprint 4.5: Research Intelligence Upgrade (narrative routing → market challenge → reasoning evolution)

Modules:
    ReasoningPipeline — V10 Multi-pass Reasoning Engine (10 steps)
    NarrativePromptRouter — Narrative-driven prompt generation (Sprint 4.5 Task 1)
    MarketChallenge — Trading value assessment (Sprint 4.5 Task 2)
    ReasoningEvolution — Reasoning template library & evolution (Sprint 4.5 Task 3)
    PromptRouter — Domain-specific prompt selection (Sprint 2)
    MemoReviewer / MemoCritic / MemoSelfReviewPipeline — Self-review (Sprint 3)
    ContinuousLearningLoop — Root cause diagnosis + belief/prompt/reasoning update (Sprint 4)
    MacroReasoner — Legacy orchestrator (backward compatible)

The output is a Research Memo that reads like:
    Bridgewater Daily Observations x PTJ Market Letter
"""

from src.research.reasoning.schemas import (
    ResearchMemo,
    EvidenceCluster,
    EvidenceAssessment,
    Hypothesis,
    CounterArgument,
    ReasoningChain,
    MemoSection,
)
from src.research.reasoning.macro_reasoner import MacroReasoner
from src.research.reasoning.reasoning_pipeline import ReasoningPipeline, PipelineResult, StepResult
from src.research.reasoning.evidence_synthesizer import EvidenceSynthesizer
from src.research.reasoning.hypothesis_builder import HypothesisBuilder
from src.research.reasoning.counter_argument_generator import CounterArgumentGenerator
from src.research.reasoning.memo_writer import MemoWriter
from src.research.reasoning.reasoning_feedback import ReasoningFeedback, FeedbackEntry, FeedbackReport
from src.research.reasoning.prompt_optimizer import PromptOptimizer, PromptOptimizationReport
from src.research.reasoning.confidence_optimizer import ConfidenceOptimizer, CalibrationReport
from src.research.reasoning.research_quality_evaluator import ResearchQualityEvaluator, QualityReport
from src.research.reasoning.review_queue import ReviewQueue, ReviewableItem, ReviewSession, ReviewStatus, ReviewableType

# V10 Sprint 2-4 modules
from src.research.reasoning.prompt_router import PromptRouter, RoutedPrompt, DOMAIN_RULES
from src.research.reasoning.memo_reviewer import (
    MemoReviewer, MemoCritic, MemoSelfReviewPipeline,
    ReviewResult, ReviewDimensionScore, SelfReviewResult, RevisionRecord,
    HallucinationDetector, review_memo,
)
from src.research.reasoning.continuous_learning import (
    ContinuousLearningLoop, RootCauseDiagnostician, BeliefUpdater,
    PromptUpdater, ReasoningUpdater, PredictionRecord, OutcomeRecord,
    RootCauseDiagnosis, BeliefUpdate, BeliefDiff, PromptUpdate, PromptDiff,
    ReasoningUpdate, ReasoningDiff, LearningReport,
)

# V10 Sprint 4.5: Research Intelligence Upgrade
from src.research.reasoning.narrative_prompt_router import (
    NarrativePromptRouter, NarrativeRoutedPrompt, NarrativeAnalyzer,
    DominantNarrative, NarrativeProfile,
)
from src.research.reasoning.market_challenge import (
    MarketChallenge, MarketChallengeResult,
    ConsensusCheck, CrowdedCheck, PositioningCheck,
    CatalystCheck, ReactionCheck, market_challenge,
)
from src.research.reasoning.reasoning_evolution import (
    ReasoningEvolution, ReasoningLibrary, ReasoningCase,
    CaseRetriever, RetrievalResult, ReasoningTemplate,
    ReasoningTemplateEvolver, ReasoningEvolutionEngine, EvolutionReport,
)

__all__ = [
    # Schemas
    "ResearchMemo",
    "EvidenceCluster",
    "EvidenceAssessment",
    "Hypothesis",
    "CounterArgument",
    "ReasoningChain",
    "MemoSection",
    # R1: Reasoning Engines
    "MacroReasoner",
    "EvidenceSynthesizer",
    "HypothesisBuilder",
    "CounterArgumentGenerator",
    "MemoWriter",
    # V10 Sprint 1-4
    "ReasoningPipeline",
    "PipelineResult",
    "StepResult",
    "PromptRouter",
    "RoutedPrompt",
    "DOMAIN_RULES",
    "MemoReviewer",
    "MemoCritic",
    "MemoSelfReviewPipeline",
    "ReviewResult",
    "ReviewDimensionScore",
    "SelfReviewResult",
    "RevisionRecord",
    "HallucinationDetector",
    "review_memo",
    "ContinuousLearningLoop",
    "RootCauseDiagnostician",
    "BeliefUpdater",
    "PromptUpdater",
    "ReasoningUpdater",
    "PredictionRecord",
    "OutcomeRecord",
    "RootCauseDiagnosis",
    "BeliefUpdate",
    "BeliefDiff",
    "PromptUpdate",
    "PromptDiff",
    "ReasoningUpdate",
    "ReasoningDiff",
    "LearningReport",
    # R5: Calibration
    "ReasoningFeedback",
    "FeedbackEntry",
    "FeedbackReport",
    "PromptOptimizer",
    "PromptOptimizationReport",
    "ConfidenceOptimizer",
    "CalibrationReport",
    # R6: Quality
    "ResearchQualityEvaluator",
    "QualityReport",
    # R7: Review
    "ReviewQueue",
    "ReviewableItem",
    "ReviewSession",
    "ReviewStatus",
    "ReviewableType",
    # Sprint 4.5 Task 1: Narrative-driven Prompt Routing
    "NarrativePromptRouter",
    "NarrativeRoutedPrompt",
    "NarrativeAnalyzer",
    "DominantNarrative",
    "NarrativeProfile",
    # Sprint 4.5 Task 2: Market Challenge
    "MarketChallenge",
    "MarketChallengeResult",
    "ConsensusCheck",
    "CrowdedCheck",
    "PositioningCheck",
    "CatalystCheck",
    "ReactionCheck",
    "market_challenge",
    # Sprint 4.5 Task 3: Reasoning Evolution
    "ReasoningEvolution",
    "ReasoningLibrary",
    "ReasoningCase",
    "CaseRetriever",
    "RetrievalResult",
    "ReasoningTemplate",
    "ReasoningTemplateEvolver",
    "ReasoningEvolutionEngine",
    "EvolutionReport",
]
