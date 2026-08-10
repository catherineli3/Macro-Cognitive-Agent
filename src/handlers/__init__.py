"""Handlers package — Pluggable TaskHandler implementations.

Sprint 4: Simple mock handlers for testing and demo.
Sprint 6: HypothesisHandler for Reasoning Engine integration.
Sprint 7: ReflectionHandler for Belief Review Engine integration.
MVP: SignalHandler (macro.signal) + NarrativeHandler (macro.narrative).
"""

from .hypothesis_handler import HypothesisHandler
from .memory_handler import MemoryHandler
from .narrative_handler import NarrativeHandler
from .reflection_handler import ReflectionHandler
from .signal_handler import SignalHandler
from .simple import (
    SimpleAnalyzeHandler,
    SimpleGenerateHandler,
    SimpleProcessHandler,
    SimpleRetrieveHandler,
    SimpleValidateHandler,
)

__all__ = [
    "SimpleRetrieveHandler",
    "SimpleProcessHandler",
    "SimpleAnalyzeHandler",
    "SimpleGenerateHandler",
    "SimpleValidateHandler",
    "HypothesisHandler",
    "ReflectionHandler",
    "MemoryHandler",
    "SignalHandler",
    "NarrativeHandler",
]
