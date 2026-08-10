"""Signal module — Signal Engine (Sprint 2).

Converts trusted macro data into structured macro signals.
Answers: "What is happening?" — NOT "Why?" or "What will happen?"

Modules:
    rule_engine.py  — Configurable rule evaluation (Sprint 2: Threshold only)
    generator.py    — SignalGenerator: (indicator, current, history) → MacroSignalSchema
"""

from src.signal.generator import ThresholdSignalGenerator
from src.signal.rule_engine import RuleEngine, RuleEvaluation

__all__ = [
    "ThresholdSignalGenerator",
    "RuleEngine",
    "RuleEvaluation",
]
