"""Critic module — Belief Review Engine (Sprint 7).

Reflection decides: "Should we still believe this hypothesis?"

Architecture:
    ReflectionEngine.review(hypothesis_set)
        ├── HypothesisReviewer   → findings, sufficiency, consistency, verdict
        └── BeliefScorer          → updated confidence

CRITICAL CONSTRAINT:
- Read only: may read HypothesisSchema objects
- Output only: ReflectionReport[] (standalone, never mutates Hypothesis)
- MUST NOT write to Hypothesis store
- MUST NOT access external data or signals

Dependencies: schemas, domain
"""

from src.critic.engine import ReflectionEngine
from src.critic.reviewer import HypothesisReviewer
from src.critic.scorer import BeliefScorer

__all__ = [
    "ReflectionEngine",
    "HypothesisReviewer",
    "BeliefScorer",
]
