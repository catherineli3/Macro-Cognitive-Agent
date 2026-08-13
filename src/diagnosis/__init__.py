"""Diagnosis Engine — Classifies Prediction Errors (DDR-V3-002, DDR-V3-006).

Classifies each prediction outcome into exactly one error category:
    SIGNAL_ERR, HYP_ERR, EVID_MISSING, TIMING_ERR, EVENT_ERR, WEIGHT_ERR

Correct predictions are classified as CORRECT_STRONG, CORRECT_WEAK, CORRECT_LUCKY.

DDR-V3-006: Diagnosis is the ONLY path from Outcome to Learning.
No outcome bypasses diagnosis. Diagnosis failure → no learning (safe default).

In Release 3.0, Diagnosis is PASSIVE — it records classifications but does
not gate learning. Learning is EMA-only (existing behavior).
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from typing import Optional
from uuid import uuid4

from src.schemas.diagnosis import (
    CorrectCategory,
    DiagnosisReport,
    ErrorCategory,
    ErrorClassification,
    ErrorTrend,
)
from src.schemas.evaluation_v3 import EvaluationReport
from src.schemas.prediction_v3 import V3PredictionOutcome
from src.shared.logging import get_logger

logger = get_logger(__name__)


class ErrorClassifier:
    """Classifies individual prediction outcomes into error/correct categories."""

    def classify(
        self,
        outcome: V3PredictionOutcome,
        hypothesis_id: str = "",
    ) -> ErrorClassification:
        """Classify a single prediction outcome.

        For correct predictions:
            - CORRECT_STRONG: direction correct + confidence > 0.7
            - CORRECT_WEAK: direction correct + confidence <= 0.7
            - CORRECT_LUCKY: direction correct but low confidence (<0.3)

        For incorrect predictions:
            - WEIGHT_ERR: default for most incorrect predictions (wrong emphasis)
            - TIMING_ERR: direction might have been right in adjacent timeframe
            - HYP_ERR: multiple predictions from same hypothesis all wrong
            - SIGNAL_ERR: indicator data unreliable or contradictory
            - EVID_MISSING: critical data was absent
            - EVENT_ERR: external shock (rare, flagged manually)
        """
        if outcome.correct:
            return self._classify_correct(outcome, hypothesis_id)
        else:
            return self._classify_error(outcome, hypothesis_id)

    def _classify_correct(
        self, outcome: V3PredictionOutcome, hypothesis_id: str
    ) -> ErrorClassification:
        """Classify a correct prediction."""
        if outcome.predicted_direction == outcome.actual_direction:
            if abs(outcome.pct_change) > 0.01:
                cat = CorrectCategory.CORRECT_STRONG
                conf = 0.85
            else:
                cat = CorrectCategory.CORRECT_WEAK
                conf = 0.70
        else:
            cat = CorrectCategory.CORRECT_LUCKY
            conf = 0.45

        return ErrorClassification(
            prediction_id=outcome.prediction_id,
            transmission_channel=outcome.transmission_channel,
            hypothesis_id=hypothesis_id,
            is_correct=True,
            correct_category=cat,
            diagnosis_confidence=conf,
            diagnosis_rationale=f"Direction matched: {outcome.predicted_direction} → {outcome.actual_direction}",
        )

    def _classify_error(
        self, outcome: V3PredictionOutcome, hypothesis_id: str
    ) -> ErrorClassification:
        """Classify an incorrect prediction into an error category.

        Release 3.0 default: most errors → WEIGHT_ERR (wrong emphasis).
        This is refined in 3.1 with context-aware diagnosis.
        """
        # Default heuristic: magnitude tells us the type
        error_mag = outcome.error_magnitude

        if error_mag > 0.05:
            # Large error — likely fundamental issue
            error_cat = ErrorCategory.HYP_ERR
            rationale = "Large prediction error suggests flawed causal reasoning"
            conf = 0.60
        elif error_mag > 0.02:
            # Moderate error — likely weighting issue
            error_cat = ErrorCategory.WEIGHT_ERR
            rationale = "Moderate error suggests incorrect emphasis on signals"
            conf = 0.55
        else:
            # Small error — could be timing
            error_cat = ErrorCategory.TIMING_ERR
            rationale = "Small directional miss — may be timing rather than direction"
            conf = 0.50

        return ErrorClassification(
            prediction_id=outcome.prediction_id,
            transmission_channel=outcome.transmission_channel,
            hypothesis_id=hypothesis_id,
            is_correct=False,
            error_category=error_cat,
            diagnosis_confidence=conf,
            diagnosis_rationale=rationale,
        )


class DiagnosisEngine:
    """Diagnosis Engine — classifies all prediction outcomes.

    DDR-V3-002: Classifies WHY predictions failed before any learning.
    DDR-V3-006: The only path from Outcome to Learning.

    Release 3.0: Passive mode — records classifications, doesn't gate learning.
    """

    def __init__(self) -> None:
        self._classifier = ErrorClassifier()

    async def diagnose_batch(self, evaluation_report: EvaluationReport) -> DiagnosisReport:
        """Diagnose all outcomes in an evaluation report.

        Each prediction gets its own ErrorClassification.
        Per-channel error distributions are computed.
        """
        report_id = f"diag-{uuid4().hex[:8]}"
        classifications: list[ErrorClassification] = []

        # Track error distributions
        error_dist: dict[str, int] = {}
        correct_dist: dict[str, int] = {}
        channel_error_dist: dict[str, dict[str, int]] = {}
        unclassified = 0

        for outcome in evaluation_report.outcomes:
            # Find hypothesis_id from the evaluation context
            hyp_id = ""  # Will be enriched in 3.1

            try:
                classification = self._classifier.classify(outcome, hyp_id)
                classifications.append(classification)

                if classification.is_correct:
                    cat_key = (
                        classification.correct_category.value
                        if classification.correct_category
                        else "UNKNOWN"
                    )
                    correct_dist[cat_key] = correct_dist.get(cat_key, 0) + 1
                else:
                    err_key = (
                        classification.error_category.value
                        if classification.error_category
                        else "UNKNOWN"
                    )
                    error_dist[err_key] = error_dist.get(err_key, 0) + 1

                    # Per-channel distribution
                    ch = outcome.transmission_channel
                    if ch:
                        ch_entry = channel_error_dist.setdefault(ch, {})
                        ch_entry[err_key] = ch_entry.get(err_key, 0) + 1

            except Exception as e:
                logger.warning("diagnosis_failed pred=%s err=%s", outcome.prediction_id, e)
                unclassified += 1
                # Safe default: mark as HYP_ERR with low confidence
                classifications.append(
                    ErrorClassification(
                        prediction_id=outcome.prediction_id,
                        transmission_channel=outcome.transmission_channel,
                        hypothesis_id="",
                        is_correct=False,
                        error_category=ErrorCategory.HYP_ERR,
                        diagnosis_confidence=0.3,
                        diagnosis_rationale=f"Unclassified — safe default: {e}",
                    )
                )
                error_dist["HYP_ERR"] = error_dist.get("HYP_ERR", 0) + 1

        correct_count = sum(1 for c in classifications if c.is_correct)
        incorrect_count = len(classifications) - correct_count

        report = DiagnosisReport(
            report_id=report_id,
            evaluation_report_id=evaluation_report.report_id,
            classifications=classifications,
            total_diagnosed=len(classifications),
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            error_distribution=error_dist,
            correct_distribution=correct_dist,
            channel_error_distribution=channel_error_dist,
            unclassified_count=unclassified,
        )

        logger.info(
            "diagnosis_complete total=%d correct=%d errors=%d top_err=%s unclassified=%d",
            report.total_diagnosed,
            correct_count,
            incorrect_count,
            report.most_common_error,
            unclassified,
        )
        return report

    async def get_error_trend(
        self,
        entries: list,  # list of LearningLogEntry
        hypothesis_id: str | None = None,
        channel: str | None = None,
        window_days: int = 90,
    ) -> ErrorTrend:
        """Analyze error trend for a hypothesis or channel."""
        _cutoff = datetime.now(UTC)
        # Filter entries
        filtered = []
        for entry in entries:
            if hypothesis_id and getattr(entry, "hypothesis_id", "") != hypothesis_id:
                continue
            if channel and getattr(entry, "transmission_channel", "") != channel:
                continue
            filtered.append(entry)

        error_counts: dict[str, int] = {}
        for entry in filtered:
            ec = getattr(entry, "error_category", None)
            if ec and not getattr(entry, "was_correct", True):
                error_counts[ec] = error_counts.get(ec, 0) + 1

        return ErrorTrend(
            hypothesis_id=hypothesis_id,
            channel=channel,
            window_days=window_days,
            error_counts=error_counts,
            total_errors=len([e for e in filtered if not getattr(e, "was_correct", True)]),
        )
