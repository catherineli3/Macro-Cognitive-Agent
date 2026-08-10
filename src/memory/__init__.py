"""Memory module — Belief Memory System.

Sprint 8 introduces the Belief Memory System, which persists
reviewed beliefs across execution cycles.

Responsibilities:
    - BeliefRecordBuilder: Transform HypothesisSet + ReflectionSet → BeliefRecords.
    - BeliefMemoryStore: Persist and query historical beliefs (JSON-file backed).
    - Transition detection: Auto-compute NEW/STABLE/REINFORCED/WEAKENED/REVERSED.

Key design (per Architecture Review):
    - Memory is INDEPENDENT from Reflection. It uses BeliefStatus, not ReflectionVerdict.
    - Memory is WRITTEN AFTER Reflection (see MemoryHandler).
    - Memory is READ BEFORE the NEXT reasoning cycle (future Sprint).
    - Memory stores BELIEFS, not raw data, signals, or tool outputs.

Dependencies: domain, schemas, shared
"""

from .builder import BeliefRecordBuilder
from .store import BeliefMemoryStore
from src.schemas.memory import BeliefRecord

__all__ = [
    "BeliefMemoryStore",
    "BeliefRecordBuilder",
    "BeliefRecord",
]
