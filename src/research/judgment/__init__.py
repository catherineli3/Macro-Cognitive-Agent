"""Research Judgment Layer (V3.2).

Transforms the Agent from "reading the world" to "explaining the world"
by producing structured research conclusions with:

- Current belief (I believe X)
- Reasoning chain (because evidence A/B/C)
- Confidence assessment
- Falsification conditions (what would change my mind)

This is what separates a Macro Analyst from a Senior Macro Researcher.
"""

from src.research.judgment.research_judgment import (
    JudgmentOutput,
    ResearchJudgment,
    ResearchJudgmentEngine,
)

__all__ = [
    "ResearchJudgment",
    "JudgmentOutput",
    "ResearchJudgmentEngine",
]
