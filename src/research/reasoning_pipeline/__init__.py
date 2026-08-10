"""V5.2 Reasoning Pipeline — Strict 10-stage reasoning process.

Every stage produces a typed output object.
LLM cannot skip steps or jump directly to the final memo.

Pipeline:
    Observation → Evidence → Pattern → Historical Analogy →
    Hypothesis → Counter → Prediction → Trade → Risk → Synthesis

No templates. All prompts derived from real research corpus (V5.1).
"""

from src.research.reasoning_pipeline.schemas import (
    ObservationOutput,
    EvidenceOutput,
    PatternOutput,
    AnalogyOutput,
    HypothesisOutput,
    CounterOutput,
    PredictionOutput,
    TradeOutput,
    RiskOutput,
    PipelineState,
    StageResult,
    StageStatus,
)

from src.research.reasoning_pipeline.observation_stage import ObservationStage
from src.research.reasoning_pipeline.evidence_stage import EvidenceStage
from src.research.reasoning_pipeline.pattern_stage import PatternStage
from src.research.reasoning_pipeline.analogy_stage import AnalogyStage
from src.research.reasoning_pipeline.hypothesis_stage import HypothesisStage
from src.research.reasoning_pipeline.counter_stage import CounterStage
from src.research.reasoning_pipeline.prediction_stage import PredictionStage
from src.research.reasoning_pipeline.trade_stage import TradeStage
from src.research.reasoning_pipeline.risk_stage import RiskStage
from src.research.reasoning_pipeline.pipeline import ReasoningPipeline

__all__ = [
    # Schemas
    "ObservationOutput",
    "EvidenceOutput",
    "PatternOutput",
    "AnalogyOutput",
    "HypothesisOutput",
    "CounterOutput",
    "PredictionOutput",
    "TradeOutput",
    "RiskOutput",
    "PipelineState",
    "StageResult",
    "StageStatus",
    # Stages
    "ObservationStage",
    "EvidenceStage",
    "PatternStage",
    "AnalogyStage",
    "HypothesisStage",
    "CounterStage",
    "PredictionStage",
    "TradeStage",
    "RiskStage",
    # Pipeline
    "ReasoningPipeline",
]
