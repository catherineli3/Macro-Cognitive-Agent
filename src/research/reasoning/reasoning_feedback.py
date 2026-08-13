"""ReasoningFeedback — Learn from prediction outcomes.

Quality: Every resolved prediction should improve the reasoning process.
When a prediction is right or wrong, we need to understand WHY and
feed that back into the system.

This module:
    1. Compares predictions with outcomes
    2. Diagnoses reasoning errors (was it causal logic? data quality? timing?)
    3. Produces actionable feedback for each module in the pipeline
    4. Feeds into PromptOptimizer and ConfidenceOptimizer
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class FeedbackEntry:
    """A single feedback signal from a resolved prediction."""

    feedback_id: str = ""
    prediction_id: str = ""
    hypothesis_id: str = ""

    # What happened
    prediction: dict = field(default_factory=dict)  # {statement, direction, confidence, ...}
    outcome: dict = field(default_factory=dict)  # {actual_direction, magnitude, ...}
    was_correct: bool = False
    prediction_error: float = 0.0  # How wrong? (0 = perfect)

    # Diagnosis
    error_source: str = (
        ""  # "causal_logic", "timing", "data_quality", "confidence_calibration", "external_shock"
    )
    root_cause: str = ""  # Human-readable explanation of what went wrong
    what_would_have_made_it_right: str = ""

    # Lessons
    lessons: list[str] = field(default_factory=list)
    confidence_adjustment: float = 0.0  # -0.2 to +0.2 adjustment to future confidence
    belief_weight_adjustment: float = 0.0  # -0.2 to +0.2 adjustment to belief weight

    # Timestamp
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class FeedbackReport:
    """Aggregated feedback across multiple resolved predictions."""

    report_id: str = ""
    period_start: str = ""
    period_end: str = ""

    entries: list[FeedbackEntry] = field(default_factory=list)
    total_predictions: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.0

    # Error analysis
    error_by_source: dict = field(default_factory=dict)
    # {"causal_logic": 3, "timing": 5, ...}

    # Improvement actions
    recommended_actions: list[str] = field(default_factory=list)

    # Calibration
    average_confidence_bias: float = 0.0  # positive = overconfident, negative = underconfident
    calibration_score: float = 0.0  # Brier score or similar

    def was_improvement(self) -> bool:
        """Did accuracy improve vs prior period?"""
        return True  # Placeholder — would compare to historical baseline


class ReasoningFeedback:
    """Learn from prediction outcomes and provide actionable feedback.

    Input: Predictions + real-world outcomes
    Output: FeedbackEntry objects tracking what went right/wrong

    The feedback flows into:
        - ConfidenceOptimizer: adjust confidence calibration
        - PromptOptimizer: improve reasoning prompts
        - Belief system: adjust belief weights
    """

    def __init__(self):
        self.feedback_history: list[FeedbackEntry] = []

    def process_outcome(
        self,
        prediction: dict,
        outcome: dict,
        hypothesis: Any | None = None,
    ) -> FeedbackEntry:
        """Process a single prediction outcome.

        Args:
            prediction: {statement, direction, confidence, asset, timeframe}
            outcome: {actual_direction, actual_magnitude, resolved_at}
            hypothesis: Optional Hypothesis object for causal diagnosis

        Returns:
            FeedbackEntry with diagnosis and lessons
        """
        pred_dir = prediction.get("direction", "")
        actual_dir = outcome.get("actual_direction", "")
        confidence = float(prediction.get("confidence", 0.5))

        was_correct = pred_dir == actual_dir

        # Compute prediction error
        if was_correct:
            error = 1.0 - confidence  # Underconfidence if right with low confidence
        else:
            error = confidence  # Overconfidence if wrong with high confidence

        # Diagnose error source
        error_source, root_cause = self._diagnose_error(
            prediction, outcome, was_correct, hypothesis
        )

        # What would have made it right?
        what_right = self._what_would_fix(prediction, outcome, error_source)

        # Lessons
        lessons = self._extract_lessons(was_correct, error_source, confidence)

        # Confidence adjustment
        if was_correct and confidence < 0.6:
            conf_adj = +0.05  # Underconfident and right → increase
        elif was_correct and confidence > 0.8:
            conf_adj = 0.0  # Rightfully confident → no change
        elif not was_correct and confidence > 0.7:
            conf_adj = -0.1  # Overconfident and wrong → decrease
        elif not was_correct:
            conf_adj = -0.05
        else:
            conf_adj = 0.0

        # Belief weight adjustment
        if was_correct:
            belief_adj = +0.05
        else:
            belief_adj = -0.05

        entry = FeedbackEntry(
            feedback_id=f"FB_{str(uuid.uuid4())[:8]}",
            prediction_id=prediction.get("prediction_id", prediction.get("hypothesis_id", "")),
            hypothesis_id=prediction.get("hypothesis_id", ""),
            prediction=prediction,
            outcome=outcome,
            was_correct=was_correct,
            prediction_error=round(error, 2),
            error_source=error_source,
            root_cause=root_cause,
            what_would_have_made_it_right=what_right,
            lessons=lessons,
            confidence_adjustment=round(conf_adj, 2),
            belief_weight_adjustment=round(belief_adj, 2),
        )

        self.feedback_history.append(entry)
        return entry

    def process_batch(
        self,
        predictions: list[dict],
        outcomes: list[dict],
    ) -> FeedbackReport:
        """Process a batch of predictions against outcomes."""
        entries = []
        for pred, out in zip(predictions, outcomes):
            entry = self.process_outcome(pred, out)
            entries.append(entry)

        return self._build_report(entries)

    def get_feedback_for_belief(self, belief_id: str) -> list[FeedbackEntry]:
        """Get feedback history for a specific belief."""
        return [e for e in self.feedback_history if e.prediction.get("belief_id") == belief_id]

    # ── Diagnosis ──

    def _diagnose_error(
        self, prediction: dict, outcome: dict, was_correct: bool, hypothesis: Any | None
    ) -> tuple[str, str]:
        """Diagnose WHY a prediction was wrong.

        Returns: (error_source, root_cause)
        """
        if was_correct:
            return "none", "Prediction was directionally correct"

        confidence = float(prediction.get("confidence", 0.5))

        # High confidence wrong → likely causal logic error
        if confidence > 0.7:
            return "causal_logic", (
                "High-confidence prediction was wrong, suggesting a fundamental "
                "error in the causal chain. The assumed mechanism may be incorrect "
                "or a structural factor was overlooked."
            )

        # Medium confidence wrong → could be timing or data quality
        if outcome.get("external_shock", ""):
            return "external_shock", (
                "External event not captured in the evidence set overwhelmed "
                "the fundamental signal. Need better risk/narrative monitoring."
            )

        # Check if the data suggested the opposite direction
        contrarian = prediction.get("evidence_weight", 0)
        if abs(contrarian) < 0.3:
            return "data_quality", (
                "Evidence was too weak to support a directional call. "
                "Should have flagged this as 'insufficient evidence' rather than "
                "making a low-conviction prediction."
            )

        # Default to confidence calibration
        return "confidence_calibration", (
            "Prediction direction was wrong. May be due to timing — "
            "the causal mechanism may be correct but the market is not yet pricing it."
        )

    def _what_would_fix(self, prediction: dict, outcome: dict, error_source: str) -> str:
        """What would have made this prediction correct?"""
        fixes = {
            "causal_logic": "Explicitly state and test the key assumption that broke. "
            "Add counter-argument with higher weight.",
            "timing": "Mark prediction timeframe more explicitly. Use regime transition "
            "signals to time entries better.",
            "data_quality": "Increase evidence quality threshold before making prediction. "
            "Require minimum 3 confirming data points.",
            "confidence_calibration": "Reduce confidence on similar patterns by 0.1-0.15. "
            "Use Brier score tracking for calibration.",
            "external_shock": "Add geopolitical/event-risk overlay to all predictions. "
            "Hedge tail risks if event probabilities are elevated.",
            "none": "Prediction was correct — maintain current approach.",
        }
        return fixes.get(error_source, "Review the full reasoning chain.")

    def _extract_lessons(
        self, was_correct: bool, error_source: str, confidence: float
    ) -> list[str]:
        """Extract actionable lessons."""
        lessons = []

        if was_correct:
            if confidence < 0.5:
                lessons.append("Increase confidence on well-supported hypotheses")
            else:
                lessons.append("Reasoning approach validated — reinforce this pattern")
        else:
            lessons.append(
                f"Error type: {error_source} — review this class of errors systematically"
            )
            if confidence > 0.7:
                lessons.append(
                    "Overconfidence detected — calibrate confidence downward on similar patterns"
                )
            if error_source == "causal_logic":
                lessons.append("Causal chain needs explicit testing before deployment")

        return lessons

    def _build_report(self, entries: list[FeedbackEntry]) -> FeedbackReport:
        """Build a feedback report from entries."""
        total = len(entries)
        correct = sum(1 for e in entries if e.was_correct)
        accuracy = correct / total if total > 0 else 0.0

        # Error by source
        error_sources = {}
        for e in entries:
            if not e.was_correct:
                error_sources[e.error_source] = error_sources.get(e.error_source, 0) + 1

        # Average confidence bias
        conf_biases = []
        for e in entries:
            conf = float(e.prediction.get("confidence", 0.5))
            if e.was_correct:
                conf_biases.append(conf - 0.5)  # Overconfident if positive bias
            else:
                conf_biases.append(-conf)  # Wrong with high confidence = negative

        avg_bias = sum(conf_biases) / len(conf_biases) if conf_biases else 0.0

        # Recommended actions
        actions = []
        if error_sources.get("causal_logic", 0) > 0:
            actions.append("Review causal chain logic for hypotheses with errors")
        if error_sources.get("confidence_calibration", 0) > 0:
            actions.append("Run confidence calibration adjustment")
        if error_sources.get("data_quality", 0) > 0:
            actions.append("Increase evidence quality thresholds before prediction")
        if accuracy < 0.5:
            actions.append("Accuracy below 50% — review overall reasoning framework")

        # Calibration score (simplified Brier)
        brier = sum(e.prediction_error**2 for e in entries) / total if total > 0 else 0.0

        return FeedbackReport(
            report_id=f"FBR_{str(uuid.uuid4())[:8]}",
            entries=entries,
            total_predictions=total,
            correct_predictions=correct,
            accuracy=round(accuracy, 2),
            error_by_source=error_sources,
            recommended_actions=actions,
            average_confidence_bias=round(avg_bias, 2),
            calibration_score=round(1 - brier, 2),
        )
