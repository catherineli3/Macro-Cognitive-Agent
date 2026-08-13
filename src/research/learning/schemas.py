"""V5.4 Learning Schemas — Models for continuous improvement of reasoning."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RootCauseCategory(str, Enum):
    """Why did a prediction or trade fail?"""

    EVIDENCE_WRONG = "evidence_wrong"  # Data was misinterpreted
    NARRATIVE_WRONG = "narrative_wrong"  # Story was wrong
    REGIME_WRONG = "regime_wrong"  # Macro regime misdiagnosed
    COUNTER_MISSED = "counter_missed"  # Ignored counter that materialized
    TIME_WINDOW_WRONG = "time_window_wrong"  # Right direction, wrong timeframe
    MODEL_ERROR = "model_error"  # Framework limitation
    EXOGENOUS_SHOCK = "exogenous_shock"  # Unpredictable event
    EXECUTION_ERROR = "execution_error"  # Right view, bad trade expression
    CONVICTION_ERROR = "conviction_error"  # Right direction, wrong sizing
    UNKNOWN = "unknown"  # Cannot determine


@dataclass
class LearningEvent:
    """A single learning event from a resolved prediction or trade."""

    event_id: str = field(default_factory=lambda: f"learn_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # What was predicted/decided
    prediction_id: str = ""
    trade_id: str = ""
    original_claim: str = ""
    original_probability: float = 0.0
    original_conviction: float = 0.0
    time_horizon: str = ""

    # What actually happened
    actual_outcome: str = ""
    outcome_timestamp: str = ""

    # Was it correct?
    was_correct: bool = False
    was_directionally_correct: bool = False


@dataclass
class FailureDiagnosis:
    """Root cause analysis of why something failed."""

    diagnosis_id: str = field(default_factory=lambda: f"diag_{uuid.uuid4().hex[:8]}")
    learning_event_id: str = ""

    # Root cause(s) — can be multiple
    root_causes: list[RootCauseCategory] = field(default_factory=list)
    primary_cause: RootCauseCategory = RootCauseCategory.UNKNOWN
    confidence_in_diagnosis: float = 0.0

    # Diagnostic reasoning
    why_evidence_wrong: str = ""
    why_narrative_wrong: str = ""
    why_regime_wrong: str = ""
    why_counter_missed: str = ""
    why_time_wrong: str = ""

    # What should have been different
    correct_narrative: str = ""
    correct_prediction: str = ""
    missed_signals: list[str] = field(default_factory=list)

    # Diagnosis narrative (human-readable)
    diagnosis_narrative: str = ""


@dataclass
class ImprovementAction:
    """Concrete action to improve future reasoning."""

    action_id: str = field(default_factory=lambda: f"act_{uuid.uuid4().hex[:8]}")
    diagnosis_id: str = ""

    # What to improve
    target: str = ""  # "prompt", "belief_weight", "narrative", "trade_rule"

    # The action
    action_type: str = ""  # "modify_prompt", "adjust_weight", "add_rule"
    description: str = ""
    before_value: str = ""
    after_value: str = ""

    # Expected impact
    expected_improvement: str = ""
    applied: bool = False
    applied_at: str = ""

    # Verification
    verified: bool = False
    verification_result: str = ""


@dataclass
class LearningLog:
    """Cumulative learning log tracking all improvements."""

    log_id: str = field(default_factory=lambda: f"log_{uuid.uuid4().hex[:8]}")
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    events: list[LearningEvent] = field(default_factory=list)
    diagnoses: list[FailureDiagnosis] = field(default_factory=list)
    actions: list[ImprovementAction] = field(default_factory=list)

    # Statistics
    total_predictions: int = 0
    correct_predictions: int = 0
    total_trades: int = 0
    profitable_trades: int = 0

    # Improvement metrics
    baseline_accuracy: float = 0.0  # Accuracy before learning
    current_accuracy: float = 0.0  # Accuracy after learning
    accuracy_trend: list[float] = field(default_factory=list)

    # Root cause distribution
    root_cause_distribution: dict[str, int] = field(default_factory=dict)

    def accuracy_rate(self) -> float:
        if self.total_predictions == 0:
            return 0.0
        return self.correct_predictions / self.total_predictions

    def improvement_delta(self) -> float:
        return self.current_accuracy - self.baseline_accuracy

    def summary(self) -> str:
        return (
            f"LearningLog: {self.total_predictions} predictions, "
            f"{self.accuracy_rate():.1%} accuracy "
            f"(+{self.improvement_delta():.1%} improvement), "
            f"{len(self.actions)} actions applied"
        )
