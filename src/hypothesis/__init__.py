"""Hypothesis module — Reasoning Engine (Sprint 6).

Transforms structured macro signals into explanatory hypotheses.
This is the Agent's first cognitive capability beyond pure execution.

Conceptual model:
    Observations → Signals → REASONING → Hypotheses

Modules:
    engine.py       — HypothesisEngine.reason(), the sole entry point
    generator.py    — HypothesisGenerator, template-based explanation generation
    aggregator.py   — EvidenceAggregator, first-class evidence classification
    confidence.py   — ConfidenceCalculator, multi-factor belief scoring

Design principles:
    - Hypothesis = explanation, NOT signal aggregation.
    - Evidence = first-class objects, NOT signal_id references.
    - Confidence = belief, NOT agreement percentage.
    - Assumptions enable Reflection (Sprint 7).
    - No LLM, no memory, no reflection (MVP).
"""

from src.hypothesis.aggregator import EvidenceAggregator
from src.hypothesis.confidence import ConfidenceCalculator
from src.hypothesis.engine import HypothesisEngine
from src.hypothesis.generator import HypothesisGenerator

__all__ = [
    "HypothesisEngine",
    "HypothesisGenerator",
    "EvidenceAggregator",
    "ConfidenceCalculator",
]
