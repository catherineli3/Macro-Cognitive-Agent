"""Schema module — Inter-module data exchange contracts.

All cross-module communication MUST use Schema objects defined here.

Rule:
    dict, JSON, and DataFrame MUST NOT cross module boundaries.
    Each module input/output MUST have a corresponding Schema.

V2 Schema Chain (DDR-010):
    MacroDataSchema → SignalSnapshot → HypothesisSet → ReflectionSet → BeliefRecord[] → MacroNarrative

V3 Schema Chain (DDR-V3 v2.2):
    HypothesisLibrary → PredictionBatch (1:N) → V3PredictionOutcome → ErrorClassification
    → DiagnosisReport → LearningUnit → AdaptiveBelief → BeliefVersion
    → LearningLogEntry → FourKPIReport
"""

from src.schemas.belief_version import AdaptiveBelief, BeliefVersion
from src.schemas.diagnosis import (
    CorrectCategory,
    DiagnosisReport,
    ErrorCategory,
    ErrorClassification,
    ErrorTrend,
)
from src.schemas.evaluation_v3 import EvaluationReport
from src.schemas.hypothesis import HypothesisEvidence, HypothesisSchema, HypothesisSet
from src.schemas.hypothesis_library import HypothesisLibraryEntry, HypothesisScore
from src.schemas.kpi import (
    FourKPIReport,
    KPI1_HypothesisAccuracy,
    KPI2_PredictionError,
    KPI3_ConfidenceCalibration,
    KPI4_LearningSpeed,
    RegressionCheck,
    WindowPeriod,
)
from src.schemas.learning_log import LearningLogEntry
from src.schemas.learning_unit import (
    EvidenceChange,
    LearningAction,
    LearningActionType,
    LearningUnit,
    PreconditionChange,
)
from src.schemas.macro_data import MacroDataSchema, QualityFactor, QualityScore

# ── V3: Autonomous Research Cycle (Milestone D) ──────────────────────
from src.schemas.macro_snapshot import MacroSnapshot, MarketSnapshot
from src.schemas.memory import BeliefRecord
from src.schemas.narrative import (
    BeliefChangeNote,
    ConfidenceExplanation,
    DimensionNarrative,
    MacroNarrative,
    RiskItem,
    ScenarioProbability,
)
from src.schemas.planning import ExecutionPlan, Task

# ── V3 schemas ──────────────────────────────────────────────────────────
from src.schemas.prediction_v3 import (
    Prediction,
    PredictionBatch,
    PredictionStatus,
    PredictionTier,
    TransmissionChannel,
    V3PredictionOutcome,
)
from src.schemas.reflection import ReflectionFinding, ReflectionReport, ReflectionSet

# ── V3: Research Evolution (Milestone C) ─────────────────────────────
from src.schemas.research import (
    CompetingPrinciple,
    ConflictRecord,
    ConflictResolution,
    FindingLifecycle,
    FindingTTLStatus,
    FrameworkExplainability,
    FrameworkSet,
    FrameworkStatus,
    PrincipleEvidence,
    PrincipleStatus,
    PrincipleStrength,
    ResearchFramework,
    ResearchPrinciple,
    SynthesisStrategy,
)
from src.schemas.research_thesis import (
    ResearchThesis,
    ThesisOutcome,
    ThesisStatus,
)
from src.schemas.signal import (
    MacroSignalSchema,
    SignalDirection,
    SignalEvidence,
    SignalSnapshot,
    SignalStrength,
)
from src.schemas.tool import ToolResult

__all__ = [
    # Data Pipeline
    "MacroDataSchema",
    "QualityFactor",
    "QualityScore",
    # Signal Engine
    "MacroSignalSchema",
    "SignalDirection",
    "SignalStrength",
    "SignalEvidence",
    "SignalSnapshot",
    # Planning
    "Task",
    "ExecutionPlan",
    # Tool Layer
    "ToolResult",
    # Hypothesis (Sprint 6)
    "HypothesisEvidence",
    "HypothesisSchema",
    "HypothesisSet",
    # Reflection (Sprint 7)
    "ReflectionFinding",
    "ReflectionReport",
    "ReflectionSet",
    # Memory (Sprint 8)
    "BeliefRecord",
    # Narrative (MVP)
    "MacroNarrative",
    "DimensionNarrative",
    "BeliefChangeNote",
    "RiskItem",
    "ScenarioProbability",
    "ConfidenceExplanation",
    # ── V3: Prediction & Evaluation ─────────────────────────────────
    "Prediction",
    "PredictionBatch",
    "PredictionStatus",
    "PredictionTier",
    "TransmissionChannel",
    "V3PredictionOutcome",
    "EvaluationReport",
    # ── V3: Diagnosis ───────────────────────────────────────────────
    "CorrectCategory",
    "DiagnosisReport",
    "ErrorCategory",
    "ErrorClassification",
    "ErrorTrend",
    # ── V3: Learning Unit ───────────────────────────────────────────
    "EvidenceChange",
    "LearningAction",
    "LearningActionType",
    "LearningUnit",
    "PreconditionChange",
    # ── V3: Belief Versioning ───────────────────────────────────────
    "AdaptiveBelief",
    "BeliefVersion",
    # ── V3: Hypothesis Library ──────────────────────────────────────
    "HypothesisLibraryEntry",
    "HypothesisScore",
    # ── V3: Learning Log ────────────────────────────────────────────
    "LearningLogEntry",
    # ── V3: KPI ─────────────────────────────────────────────────────
    "FourKPIReport",
    "KPI1_HypothesisAccuracy",
    "KPI2_PredictionError",
    "KPI3_ConfidenceCalibration",
    "KPI4_LearningSpeed",
    "RegressionCheck",
    "WindowPeriod",
    # ── V3: Research Evolution (Milestone C) ─────────────────────────
    "CompetingPrinciple",
    "ConflictRecord",
    "ConflictResolution",
    "FindingLifecycle",
    "FindingTTLStatus",
    "FrameworkExplainability",
    "FrameworkSet",
    "FrameworkStatus",
    "PrincipleEvidence",
    "PrincipleStatus",
    "PrincipleStrength",
    "ResearchFramework",
    "ResearchPrinciple",
    "SynthesisStrategy",
    # ── V3: Autonomous Research Cycle (Milestone D) ────────────────────
    "MacroSnapshot",
    "MarketSnapshot",
    "ResearchThesis",
    "ThesisOutcome",
    "ThesisStatus",
]
