"""Outcome Evaluation Engine — Per-Prediction, Per-Channel Evaluation.

Compares V3 predictions against actual market data at individual prediction
granularity. Hypothesis-level accuracy is a derived aggregate.
Per-channel breakdowns enable precise diagnosis (DDR-V3-009).
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt
from typing import Optional
from uuid import uuid4

from src.schemas.evaluation_v3 import EvaluationReport
from src.schemas.prediction_v3 import (
    Prediction,
    PredictionBatch,
    PredictionStatus,
    V3PredictionOutcome,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


class PerChannelComparator:
    """Compares individual predictions against actual data."""

    @staticmethod
    def compare(
        prediction: Prediction,
        actual_value: float,
        prev_value: float,
    ) -> V3PredictionOutcome:
        """Compare a single prediction against actual market data.

        Returns a V3PredictionOutcome with per-prediction evaluation.
        """
        if prev_value == 0.0:
            return V3PredictionOutcome(
                prediction_id=prediction.prediction_id,
                correct=False,
                predicted_direction=prediction.direction,
                actual_direction="unknown",
                pct_change=0.0,
                error_magnitude=float('inf'),
                actual_value=actual_value,
                transmission_channel=prediction.transmission_channel,
                evaluated_at=datetime.now(timezone.utc),
            )

        pct_change = (actual_value - prev_value) / abs(prev_value)

        # Determine actual direction
        if pct_change > 0.001:
            actual_dir = "bullish"
        elif pct_change < -0.001:
            actual_dir = "bearish"
        else:
            actual_dir = "flat"

        # Check correctness
        pred_dir = prediction.direction.lower()
        if pred_dir == actual_dir:
            correct = True
        elif pred_dir == "flat" and abs(pct_change) <= 0.005:
            correct = True
        elif actual_dir == "flat" and pred_dir == "bullish" and pct_change > -0.001:
            correct = True
        elif actual_dir == "flat" and pred_dir == "bearish" and pct_change < 0.001:
            correct = True
        else:
            correct = False

        error_magnitude = 0.0 if correct else abs(pct_change)

        return V3PredictionOutcome(
            prediction_id=prediction.prediction_id,
            correct=correct,
            predicted_direction=pred_dir,
            actual_direction=actual_dir,
            pct_change=round(pct_change, 6),
            error_magnitude=round(error_magnitude, 6),
            actual_value=round(actual_value, 4),
            transmission_channel=prediction.transmission_channel,
            evaluated_at=datetime.now(timezone.utc),
        )


class OutcomeEvaluationEngine:
    """Evaluates prediction batches against actual market data.

    DDR-V3-009: Per-prediction, per-channel evaluation.
    Produces EvaluationReport with dimensional and channel breakdowns.
    """

    def __init__(self) -> None:
        self._comparator = PerChannelComparator()

    async def evaluate_batch(
        self,
        batch: PredictionBatch,
        actual_data: dict[str, tuple[float, float]],
        # actual_data: {indicator: (current_value, previous_value)}
    ) -> EvaluationReport:
        """Evaluate all predictions in a batch against actual data.

        Args:
            batch: The prediction batch to evaluate.
            actual_data: {indicator_name: (current_value, previous_value)}

        Returns:
            EvaluationReport with per-prediction, per-channel breakdowns.
        """
        report_id = f"eval-{uuid4().hex[:8]}"
        outcomes: list[V3PredictionOutcome] = []

        # Dimension, channel, horizon, hypothesis accumulators
        dim_correct: dict[str, int] = {}
        dim_total: dict[str, int] = {}
        channel_correct: dict[str, int] = {}
        channel_total: dict[str, int] = {}
        horizon_correct: dict[str, int] = {}
        horizon_total: dict[str, int] = {}
        hyp_correct: dict[str, int] = {}
        hyp_total: dict[str, int] = {}
        tier_correct: dict[str, int] = {}
        tier_total: dict[str, int] = {}

        squared_errors: list[float] = []
        brier_terms: list[float] = []

        for pred in batch.predictions:
            indicator_data = actual_data.get(pred.indicator)
            if indicator_data is None:
                # Indicator not in actual_data — skip or mark unknown
                outcome = V3PredictionOutcome(
                    prediction_id=pred.prediction_id,
                    correct=False,
                    predicted_direction=pred.direction,
                    actual_direction="unknown",
                    pct_change=0.0,
                    error_magnitude=0.0,
                    actual_value=0.0,
                    transmission_channel=pred.transmission_channel,
                    evaluated_at=datetime.now(timezone.utc),
                )
            else:
                current_val, prev_val = indicator_data
                outcome = self._comparator.compare(pred, current_val, prev_val)

            outcomes.append(outcome)
            pred.status = PredictionStatus.EVALUATED

            # Accumulate per-dimension
            dim = pred.dimension
            dim_total[dim] = dim_total.get(dim, 0) + 1
            if outcome.correct:
                dim_correct[dim] = dim_correct.get(dim, 0) + 1

            # Accumulate per-channel
            ch = pred.transmission_channel
            channel_total[ch] = channel_total.get(ch, 0) + 1
            if outcome.correct:
                channel_correct[ch] = channel_correct.get(ch, 0) + 1

            # Accumulate per-horizon
            hz = pred.horizon
            horizon_total[hz] = horizon_total.get(hz, 0) + 1
            if outcome.correct:
                horizon_correct[hz] = horizon_correct.get(hz, 0) + 1

            # Accumulate per-hypothesis
            hid = pred.source_hypothesis_id
            hyp_total[hid] = hyp_total.get(hid, 0) + 1
            if outcome.correct:
                hyp_correct[hid] = hyp_correct.get(hid, 0) + 1

            # Accumulate per-tier
            tier = pred.prediction_tier.value
            tier_total[tier] = tier_total.get(tier, 0) + 1
            if outcome.correct:
                tier_correct[tier] = tier_correct.get(tier, 0) + 1

            # MAE, RMSE components
            squared_errors.append(outcome.error_magnitude ** 2)

            # Brier score: (confidence - outcome)^2
            outcome_val = 1.0 if outcome.correct else 0.0
            brier_terms.append((pred.confidence - outcome_val) ** 2)

        total = len(outcomes)
        total_correct = sum(1 for o in outcomes if o.correct)
        total_incorrect = total - total_correct

        # ── Compute summary metrics ──────────────────────────────────
        directional_accuracy = total_correct / total if total > 0 else 0.0
        mae = sum(abs(o.error_magnitude) for o in outcomes) / total if total > 0 else 0.0
        rmse = sqrt(sum(squared_errors) / total) if total > 0 else 0.0
        brier = sum(brier_terms) / total if total > 0 else 0.0

        # ── Build accuracy breakdowns ────────────────────────────────
        accuracy_by_dimension = {
            d: dim_correct.get(d, 0) / dim_total[d]
            for d in dim_total
        }
        accuracy_by_channel = {
            c: channel_correct.get(c, 0) / channel_total[c]
            for c in channel_total
        }
        accuracy_by_horizon = {
            h: horizon_correct.get(h, 0) / horizon_total[h]
            for h in horizon_total
        }
        accuracy_by_hypothesis = {
            h: hyp_correct.get(h, 0) / hyp_total[h]
            for h in hyp_total
        }
        accuracy_by_tier = {
            t: tier_correct.get(t, 0) / tier_total[t]
            for t in tier_total
        }

        logger.info(
            "evaluation_complete batch=%s total=%d correct=%d da=%.1f%% channels=%d",
            batch.batch_id, total, total_correct, directional_accuracy * 100, len(accuracy_by_channel),
        )

        return EvaluationReport(
            report_id=report_id,
            batch_id=batch.batch_id,
            outcomes=outcomes,
            directional_accuracy=round(directional_accuracy, 4),
            mean_absolute_error=round(mae, 6),
            rmse=round(rmse, 6),
            brier_score=round(brier, 4),
            accuracy_by_dimension={k: round(v, 4) for k, v in accuracy_by_dimension.items()},
            accuracy_by_horizon={k: round(v, 4) for k, v in accuracy_by_horizon.items()},
            accuracy_by_hypothesis={k: round(v, 4) for k, v in accuracy_by_hypothesis.items()},
            accuracy_by_channel={k: round(v, 4) for k, v in accuracy_by_channel.items()},
            accuracy_by_tier={k: round(v, 4) for k, v in accuracy_by_tier.items()},
            total_outcomes=total,
            total_correct=total_correct,
            total_incorrect=total_incorrect,
        )
