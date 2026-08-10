"""Interfaces module — Abstract contracts for all modules.

Every business module MUST have a corresponding Protocol/ABC defined here.
Dependency Injection: modules depend on these interfaces, NOT on concrete implementations.

Sprint 1 Interfaces:
    CollectorInterface         — External data fetching
    ValidatorInterface         — Data validation (shared capability)
    NormalizerInterface        — Canonicalization only
    RepositoryInterface        — Data persistence (swappable backend)

Sprint 2 Interfaces:
    SignalGeneratorInterface   — Signal generation (pure function)
    SignalRepositoryInterface  — Signal persistence (separate from data repo)

Sprint 3 Interfaces:
    PlannerInterface            — Goal-to-plan decomposition

Sprint 4 Interfaces:
    TaskHandlerInterface        — Executable task capability (capability routing)

Sprint 4+ Interfaces (planned):
    AnalyzerProtocol
    HypothesisProtocol
    CriticProtocol
    ReportProtocol
    MemoryProtocol
"""

from src.interfaces.collector import CollectorInterface
from src.interfaces.normalizer import NormalizerInterface
from src.interfaces.planner import PlannerInterface
from src.interfaces.repository import RepositoryInterface
from src.interfaces.signal_generator import SignalGeneratorInterface
from src.interfaces.signal_repository import SignalRepositoryInterface
from src.interfaces.task_handler import TaskHandlerInterface
from src.interfaces.validator import ValidationError, ValidatorInterface

__all__ = [
    "CollectorInterface",
    "ValidatorInterface",
    "ValidationError",
    "NormalizerInterface",
    "RepositoryInterface",
    "SignalGeneratorInterface",
    "SignalRepositoryInterface",
    "PlannerInterface",
    "TaskHandlerInterface",
]
