"""V5.3 Research QA — Automatic quality assessment for every research memo.

8-dimension scoring:
    Evidence Coverage, Reasoning Consistency, Causal Completeness,
    Counter Quality, Prediction Testability, Trade Actionability,
    Hallucination Risk, Source Traceability.

Each memo receives a ResearchScoreCard with letter grade.
Score < 80 → rejected, must regenerate.
"""

from src.research.qa.schemas import (
    ResearchScoreCard,
    DimensionScore,
    MemoGrade,
    QAVerdict,
)

from src.research.qa.memo_grader import MemoGrader
from src.research.qa.hallucination_checker import HallucinationChecker
from src.research.qa.source_verifier import SourceVerifier
from src.research.qa.reasoning_checker import ReasoningChecker
from src.research.qa.causal_checker import CausalChecker
from src.research.qa.trade_checker import TradeChecker
from src.research.qa.report_card import ReportCard

__all__ = [
    # Schemas
    "ResearchScoreCard",
    "DimensionScore",
    "MemoGrade",
    "QAVerdict",
    # Checkers
    "MemoGrader",
    "HallucinationChecker",
    "SourceVerifier",
    "ReasoningChecker",
    "CausalChecker",
    "TradeChecker",
    "ReportCard",
]
