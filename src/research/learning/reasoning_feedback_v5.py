"""V5.4 Reasoning Feedback — Learn from reasoning errors.

Previous V4 feedback only adjusted prediction confidence.
V5.4 asks WHY the prediction failed, not just THAT it failed.

Diagnoses:
    - Was the evidence misinterpreted?
    - Was the causal narrative wrong?
    - Was the macro regime misidentified?
    - Was a critical counterargument ignored?
    - Was the time horizon wrong?
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.research.learning.schemas import (
    LearningEvent,
    FailureDiagnosis,
    RootCauseCategory,
)


class ReasoningFeedbackV5:
    """Analyze prediction/trade failures to diagnose root causes.

    This is NOT just "prediction was wrong, reduce confidence."
    This analyzes the REASONING that led to the wrong conclusion.
    """

    DIAGNOSIS_FLOW = {
        RootCauseCategory.EVIDENCE_WRONG: [
            "Did the underlying data change after our prediction?",
            "Did we misinterpret the data at the time?",
            "Was the data itself revised later?",
        ],
        RootCauseCategory.NARRATIVE_WRONG: [
            "Was the causal mechanism we identified actually operative?",
            "Did a different mechanism dominate?",
            "Was our underlying theory flawed?",
        ],
        RootCauseCategory.REGIME_WRONG: [
            "Were we in a different macro regime than we thought?",
            "Did the regime change during our forecast horizon?",
            "Were regime transition signals missed or misinterpreted?",
        ],
        RootCauseCategory.COUNTER_MISSED: [
            "Which counterargument materialized?",
            "Was this counter considered and dismissed, or completely missed?",
            "Why was the counter's probability underestimated?",
        ],
        RootCauseCategory.TIME_WINDOW_WRONG: [
            "Was the direction correct but timing off?",
            "Were our catalysts/triggers correctly identified but delayed?",
            "Was the horizon reasonable given historical precedents?",
        ],
    }

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def analyze(
        self,
        event: LearningEvent,
        context: dict | None = None,
    ) -> FailureDiagnosis:
        """Analyze a learning event to diagnose root causes.

        Args:
            event: The learning event (prediction outcome)
            context: Additional context (market data, macro data at time)

        Returns:
            FailureDiagnosis with root cause analysis
        """
        context = context or {}
        diagnosis = FailureDiagnosis(
            learning_event_id=event.event_id,
        )

        # Skip if prediction was correct
        if event.was_correct:
            diagnosis.primary_cause = RootCauseCategory.UNKNOWN
            diagnosis.diagnosis_narrative = (
                "Prediction was correct. No failure to diagnose."
            )
            diagnosis.confidence_in_diagnosis = 1.0
            return diagnosis

        # For each potential root cause, score likelihood
        cause_scores = {}

        # 1. Evidence check
        evidence_score = self._assess_evidence_error(event, context)
        cause_scores[RootCauseCategory.EVIDENCE_WRONG] = evidence_score
        if evidence_score > 0.5:
            diagnosis.why_evidence_wrong = (
                f"Evidence may have been misinterpreted (score: {evidence_score:.2f}). "
                "The data at the time did not support the conclusion drawn."
            )

        # 2. Narrative check
        narrative_score = self._assess_narrative_error(event, context)
        cause_scores[RootCauseCategory.NARRATIVE_WRONG] = narrative_score
        if narrative_score > 0.5:
            diagnosis.why_narrative_wrong = (
                f"The causal narrative was likely incorrect (score: {narrative_score:.2f}). "
                "A different mechanism was operating than the one identified."
            )

        # 3. Regime check
        regime_score = self._assess_regime_error(event, context)
        cause_scores[RootCauseCategory.REGIME_WRONG] = regime_score
        if regime_score > 0.5:
            diagnosis.why_regime_wrong = (
                f"Macro regime was misdiagnosed (score: {regime_score:.2f}). "
                "The actual regime was different from the assumed one."
            )

        # 4. Counter check
        counter_score = self._assess_counter_missed(event, context)
        cause_scores[RootCauseCategory.COUNTER_MISSED] = counter_score
        if counter_score > 0.5:
            diagnosis.why_counter_missed = (
                f"A counterargument materialized that was not adequately considered "
                f"(score: {counter_score:.2f})."
            )

        # 5. Time window check
        time_score = self._assess_time_error(event, context)
        cause_scores[RootCauseCategory.TIME_WINDOW_WRONG] = time_score
        if time_score > 0.5:
            diagnosis.why_time_wrong = (
                f"The time horizon was likely incorrect (score: {time_score:.2f}). "
                f"{'Directionally correct but timing off' if event.was_directionally_correct else 'Timing was a contributing factor'}."
            )

        # Determine primary cause (highest score)
        if cause_scores:
            diagnosis.primary_cause = max(cause_scores, key=cause_scores.get)
            diagnosis.confidence_in_diagnosis = cause_scores[diagnosis.primary_cause]

        # Collect all significant causes (>0.4)
        diagnosis.root_causes = [
            cause for cause, score in cause_scores.items()
            if score > 0.4
        ]

        # Missed signals
        diagnosis.missed_signals = self._identify_missed_signals(event, context)

        # Build narrative
        diagnosis.diagnosis_narrative = self._build_narrative(diagnosis)

        return diagnosis

    def _assess_evidence_error(
        self,
        event: LearningEvent,
        context: dict,
    ) -> float:
        """Assess likelihood that evidence was misinterpreted."""
        score = 0.3  # Base

        if context.get("data_revisions"):
            score += 0.2  # Data was revised, making original interpretation wrong

        if context.get("conflicting_data_ignored"):
            score += 0.3  # Evidence that was available but ignored

        if context.get("data_quality_issues"):
            score += 0.1

        return min(score, 0.95)

    def _assess_narrative_error(
        self,
        event: LearningEvent,
        context: dict,
    ) -> float:
        """Assess likelihood that the causal narrative was wrong."""
        score = 0.25

        if context.get("alternative_mechanism_materialized"):
            score += 0.35

        if context.get("causal_chain_broken"):
            score += 0.2

        return min(score, 0.95)

    def _assess_regime_error(
        self,
        event: LearningEvent,
        context: dict,
    ) -> float:
        """Assess likelihood that the macro regime was misdiagnosed."""
        score = 0.2

        if context.get("regime_change_during_period"):
            score += 0.3

        if context.get("transition_signals_missed"):
            score += 0.25

        return min(score, 0.95)

    def _assess_counter_missed(
        self,
        event: LearningEvent,
        context: dict,
    ) -> float:
        """Assess likelihood that a counter was missed."""
        score = 0.2

        if context.get("counter_materialized"):
            score += 0.4

        if context.get("counter_probability_underestimated"):
            score += 0.2

        if event.original_probability > 0.8:
            score += 0.1  # Very high confidence → likely missed a counter

        return min(score, 0.95)

    def _assess_time_error(
        self,
        event: LearningEvent,
        context: dict,
    ) -> float:
        """Assess likelihood that timing was wrong."""
        score = 0.15

        if event.was_directionally_correct:
            score += 0.4  # Direction right but timing off

        if context.get("catalyst_delayed"):
            score += 0.2

        return min(score, 0.95)

    def _identify_missed_signals(
        self,
        event: LearningEvent,
        context: dict,
    ) -> list[str]:
        """Identify signals that were present but missed."""
        signals = []

        if context.get("early_warning_data"):
            signals.append(f"Early warning data: {context['early_warning_data']}")

        if context.get("market_pricing_divergence"):
            signals.append(f"Market divergence signal: {context['market_pricing_divergence']}")

        if context.get("leading_indicator_signal"):
            signals.append(f"Leading indicator signal: {context['leading_indicator_signal']}")

        if context.get("sentiment_shift"):
            signals.append(f"Sentiment shift: {context['sentiment_shift']}")

        return signals

    def _build_narrative(self, diagnosis: FailureDiagnosis) -> str:
        """Build human-readable diagnosis narrative."""
        if diagnosis.primary_cause == RootCauseCategory.UNKNOWN:
            return "Unable to determine root cause with sufficient confidence."

        cause_narratives = {
            RootCauseCategory.EVIDENCE_WRONG: (
                "The evidence underlying this prediction was misinterpreted or "
                "relied on data that was subsequently revised. Recommendation: "
                "strengthen data quality checks and consider broader evidence sets."
            ),
            RootCauseCategory.NARRATIVE_WRONG: (
                "The causal narrative was incorrect — a different mechanism drove "
                "the outcome than what was hypothesized. Recommendation: review "
                "the theoretical framework and consider alternative transmission channels."
            ),
            RootCauseCategory.REGIME_WRONG: (
                "The macro regime was misdiagnosed, leading to a forecast that was "
                "appropriate for the wrong environment. Recommendation: strengthen "
                "regime identification with multiple independent signals."
            ),
            RootCauseCategory.COUNTER_MISSED: (
                "A counterargument that was either dismissed or not considered "
                "materialized as the actual outcome. Recommendation: ensure every "
                "hypothesis has at least 3 structured counterarguments with explicit probabilities."
            ),
            RootCauseCategory.TIME_WINDOW_WRONG: (
                "The directional view may have been correct but the time horizon "
                "was wrong — the catalyst was delayed or the adjustment took longer "
                "than expected. Recommendation: widen forecast windows and clarify "
                "catalyst triggers."
            ),
            RootCauseCategory.EXOGENOUS_SHOCK: (
                "An exogenous, unforeseeable event drove the outcome. This is not "
                "a reasoning failure. Recommendation: note the event for tail risk calibration."
            ),
        }

        return cause_narratives.get(
            diagnosis.primary_cause,
            "Root cause could not be definitively determined."
        )
