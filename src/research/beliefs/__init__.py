"""M4 — Belief Engine.

Converts Narrative Intelligence into structured, verifiable Research Beliefs
using Beta-Bayesian inference with 7-stage lifecycle management.

Architecture:
    Narratives (M3)
         ↓
    TemplateMatcher → Belief Templates
         ↓
    BeliefUpdateEngine → Beta-Bayesian initialization
         ↓
    ResearchBelief[] → With evidence, track record, lifecycle
         ↓
    BeliefGraph → SUPPORTS / COMPETES / CONTRADICTS / EXPLAINS
         ↓
    BeliefLifecycleManager → 7-stage progression
         ↓
    BeliefStore → Persistent storage
"""

from src.research.beliefs.schemas import (
    BeliefDomain,
    BeliefRelationType,
    BeliefStage,
    EvidenceItem,
    EvidenceSource,
    Prediction,
    ResearchBelief,
)
from src.research.beliefs.belief_engine import BeliefEngine
from src.research.beliefs.belief_graph import BeliefGraph, BeliefRelation
from src.research.beliefs.belief_lifecycle import BeliefLifecycleManager
from src.research.beliefs.belief_store import BeliefStore
from src.research.beliefs.belief_update_engine import BeliefUpdateEngine
from src.research.beliefs.evidence_weight import (
    EVIDENCE_BASE_WEIGHTS,
    classify_evidence,
    compute_evidence_weight,
)
from src.research.beliefs.template_matcher import BeliefTemplate, TemplateMatcher

__all__ = [
    "BeliefDomain",
    "BeliefEngine",
    "BeliefGraph",
    "BeliefLifecycleManager",
    "BeliefRelation",
    "BeliefRelationType",
    "BeliefStage",
    "BeliefStore",
    "BeliefTemplate",
    "BeliefUpdateEngine",
    "EVIDENCE_BASE_WEIGHTS",
    "EvidenceItem",
    "EvidenceSource",
    "Prediction",
    "ResearchBelief",
    "TemplateMatcher",
    "classify_evidence",
    "compute_evidence_weight",
]
