"""Domain module — Core business objects.

All domain models live here as Pydantic models. They define what things ARE
(identity, metadata, structure), not how data flows between modules.

Models (Sprint 1):
    MacroIndicator  — Indicator metadata with hypothesis_dimension
    MarketSource    — Data source definition and config

Models (Sprint 2):
    SignalDirection — Market-implied direction enum
    SignalStrength  — Signal severity level enum
    RuleType        — Rule engine capability catalog

Models (Sprint 3+):
    Hypothesis
    Evidence
    MacroState
    ReportSection

Models (Sprint 5):
    ToolResultStatus — Tool execution outcome enum

Models (Sprint 8):
    TransitionType   — Belief change classification
    BeliefStatus     — Memory-level belief state
"""

from src.domain.hypothesis import HypothesisStatus
from src.domain.macro_indicator import Frequency, HypothesisDimension, MacroIndicator
from src.domain.market_source import AuthType, MarketSource, SourceType
from src.domain.memory import BeliefStatus, TransitionType
from src.domain.narrative import ConfidenceLevel, ReportFormat, RiskLevel
from src.domain.planning import TaskType
from src.domain.reflection import FindingSeverity, ReflectionVerdict
from src.domain.signal import RuleType, SignalDirection, SignalStrength
from src.domain.tool import ToolResultStatus

__all__ = [
    # MacroIndicator
    "MacroIndicator",
    "HypothesisDimension",
    "Frequency",
    # MarketSource
    "MarketSource",
    "SourceType",
    "AuthType",
    # Signal
    "SignalDirection",
    "SignalStrength",
    "RuleType",
    # Planning
    "TaskType",
    # Tool
    "ToolResultStatus",
    # Hypothesis
    "HypothesisStatus",
    # Reflection (Sprint 7)
    "ReflectionVerdict",
    "FindingSeverity",
    # Memory (Sprint 8)
    "TransitionType",
    "BeliefStatus",
    # Narrative (MVP)
    "ReportFormat",
    "RiskLevel",
    "ConfidenceLevel",
]
