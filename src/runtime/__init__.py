"""Runtime Infrastructure — Live Research Agent (Milestone E).

This package contains the infrastructure that makes the V3 agent "live":
    - Daily Runner:     Executes one full research cycle per day
    - Prediction Registry: SQLite-backed prediction tracking
    - Outcome Scheduler:   Automated evaluation of expired predictions
    - Report Generator:    Daily markdown research notes
    - Paper Trader:        Historical replay for growth validation

These modules add ZERO new knowledge capabilities. They are pure
runtime infrastructure: scheduling, persistence, and output formatting.

The cognitive architecture was frozen at Milestone D.
"""

from src.runtime.daily_runner import DailyRunner, RunReport
from src.runtime.outcome_scheduler import (
    EvaluationResult,
    OutcomeScheduler,
    SchedulerReport,
)
from src.runtime.paper_trader import (
    PaperTrader,
    ReplayDay,
    ReplayResult,
    ReplayStats,
)
from src.runtime.prediction_registry import (
    PredictionRecord,
    PredictionRegistry,
)
from src.runtime.report_generator import ReportGenerator

__all__ = [
    "DailyRunner",
    "RunReport",
    "PredictionRegistry",
    "PredictionRecord",
    "OutcomeScheduler",
    "EvaluationResult",
    "SchedulerReport",
    "ReportGenerator",
    "PaperTrader",
    "ReplayDay",
    "ReplayResult",
    "ReplayStats",
]
