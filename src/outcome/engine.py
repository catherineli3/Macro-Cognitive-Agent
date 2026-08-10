"""Outcome Tracking Engine — v2.0 core module.

Tracks what actually happened vs what the Agent predicted.
Replaces hypothesis-only memory with verifiable prediction→outcome pairs.

Design (DDR-v2):
    - OutcomeTracker stores outcomes as JSON alongside beliefs.
    - OutcomeEvaluator compares predictions to realized indicator values.
    - OutcomeMetrics computes Brier Score, Hit Rate, Precision.
    - OutcomeEngine orchestrates the full tracking cycle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.schemas.memory import BeliefRecord
from src.schemas.outcome import (
    OutcomeDirection,
    OutcomeRecord,
    OutcomeSummary,
    OutcomeVerdict,
    PredictionOutcome,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)

_DIMENSION_WEIGHTS = ["liquidity", "credit", "growth", "risk_appetite", "inflation"]

# ── Outcome Evaluator ────────────────────────────────────────────────────────


class OutcomeEvaluator:
    """Evaluates a single prediction against observed data."""

    @staticmethod
    def evaluate(
        outcome: PredictionOutcome,
        observed_value: Optional[float] = None,
        observed_direction: Optional[OutcomeDirection] = None,
    ) -> PredictionOutcome:
        """Evaluate a pending outcome against observed data.

        If observed_direction is provided, compares against predicted direction.
        If only observed_value is provided, infers direction from value.

        Args:
            outcome: The pending PredictionOutcome to evaluate.
            observed_value: The realized indicator value (optional).
            observed_direction: The realized market direction (optional).

        Returns:
            The same outcome with verdict and rationale set.
        """
        if observed_direction is not None:
            outcome.observed_direction = observed_direction
        elif observed_value is not None:
            outcome.realized_value = observed_value
            outcome.observed_direction = OutcomeDirection.UNKNOWN

        outcome.evaluated_at = datetime.now(timezone.utc)

        if outcome.observed_direction is None or outcome.observed_direction == OutcomeDirection.UNKNOWN:
            outcome.verdict = OutcomeVerdict.PENDING
            outcome.verdict_rationale = "Insufficient observed data for evaluation."
            outcome.verdict_confidence = 0.1
            return outcome

        predicted = outcome.predicted_direction.value
        observed = outcome.observed_direction.value

        # Direction matching
        if predicted == "bullish" and observed == "up":
            outcome.verdict = OutcomeVerdict.CORRECT
            outcome.verdict_confidence = 0.85
            outcome.verdict_rationale = (
                f"Predicted bullish ({outcome.predicted_confidence:.0%}), "
                f"observed {observed} — directional match."
            )
        elif predicted == "bearish" and observed == "down":
            outcome.verdict = OutcomeVerdict.CORRECT
            outcome.verdict_confidence = 0.85
            outcome.verdict_rationale = (
                f"Predicted bearish ({outcome.predicted_confidence:.0%}), "
                f"observed {observed} — directional match."
            )
        elif predicted == "neutral":
            if observed == "flat":
                outcome.verdict = OutcomeVerdict.CORRECT
                outcome.verdict_confidence = 0.70
                outcome.verdict_rationale = "Predicted neutral, observed flat."
            else:
                outcome.verdict = OutcomeVerdict.PARTIALLY_CORRECT
                outcome.verdict_confidence = 0.50
                outcome.verdict_rationale = (
                    f"Predicted neutral but observed {observed} — "
                    f"no strong directional error."
                )
        elif observed == "flat":
            outcome.verdict = OutcomeVerdict.PARTIALLY_CORRECT
            outcome.verdict_confidence = 0.55
            outcome.verdict_rationale = (
                f"Predicted {predicted} but observed flat — "
                f"direction was not realized."
            )
        else:
            outcome.verdict = OutcomeVerdict.INCORRECT
            outcome.verdict_confidence = 0.85
            outcome.verdict_rationale = (
                f"Predicted {predicted} ({outcome.predicted_confidence:.0%}), "
                f"observed {observed} — directional miss."
            )

        return outcome


# ── Outcome Metrics ──────────────────────────────────────────────────────────


class OutcomeMetrics:
    """Compute aggregate metrics from outcome records."""

    @staticmethod
    def compute_summary(records: list[OutcomeRecord]) -> OutcomeSummary:
        """Compute OutcomeSummary from a list of outcome records.

        Args:
            records: All tracked outcome records.

        Returns:
            Aggregated OutcomeSummary with accuracy, Brier, precision.
        """
        outcomes = [r.outcome for r in records]
        evaluated = [o for o in outcomes if o.is_evaluated]
        pending = [o for o in outcomes if not o.is_evaluated]

        total = len(outcomes)
        pending_count = len(pending)
        correct = sum(1 for o in evaluated if o.is_correct)
        incorrect = sum(1 for o in evaluated if o.is_incorrect)
        partial = sum(1 for o in evaluated if o.verdict == OutcomeVerdict.PARTIALLY_CORRECT)

        evaluated_count = len(evaluated)
        hit_rate = correct / evaluated_count if evaluated_count > 0 else 0.0

        # Brier Score: (1/N) * Σ(p_i - o_i)^2
        # where p_i = predicted confidence, o_i = 1 if correct, 0 if incorrect
        brier = 0.0
        if evaluated_count > 0:
            squared_errors = 0.0
            for o in evaluated:
                actual = 1.0 if o.is_correct else 0.0
                if o.verdict == OutcomeVerdict.PARTIALLY_CORRECT:
                    actual = 0.5
                squared_errors += (o.predicted_confidence - actual) ** 2
            brier = squared_errors / evaluated_count

        # Per-dimension accuracy
        dim_accuracy: dict[str, dict] = {}
        for dim in _DIMENSION_WEIGHTS:
            dim_outcomes = [o for o in evaluated if o.dimension.lower() == dim]
            if dim_outcomes:
                dim_correct = sum(1 for o in dim_outcomes if o.is_correct)
                dim_total = len(dim_outcomes)
                dim_brier_sum = sum(
                    (o.predicted_confidence - (1.0 if o.is_correct else 0.0)) ** 2
                    for o in dim_outcomes
                )
                dim_accuracy[dim] = {
                    "correct": dim_correct,
                    "total": dim_total,
                    "hit_rate": round(dim_correct / dim_total, 3),
                    "brier": round(dim_brier_sum / dim_total, 4),
                }

        # Directional accuracy
        directional_total = 0
        directional_correct = 0
        for o in evaluated:
            if o.predicted_direction.value in ("bullish", "bearish"):
                directional_total += 1
                if o.is_correct:
                    directional_correct += 1

        directional_acc = directional_correct / directional_total if directional_total > 0 else 0.0

        # Average evaluation lag
        lags = [
            (o.evaluated_at - o.predicted_at).total_seconds() / 86400
            for o in evaluated
            if o.evaluated_at
        ]
        avg_lag = sum(lags) / len(lags) if lags else 0.0

        return OutcomeSummary(
            total_predictions=total,
            pending_predictions=pending_count,
            correct_count=correct,
            incorrect_count=incorrect,
            partially_correct_count=partial,
            hit_rate=round(hit_rate, 4),
            brier_score=round(brier, 4),
            precision=round(hit_rate, 4),  # Simple precision = hit rate for now
            directional_accuracy=round(directional_acc, 4),
            dimension_accuracy=dim_accuracy,
            average_evaluation_lag_days=round(avg_lag, 2),
        )


# ── Outcome Tracker ──────────────────────────────────────────────────────────


class OutcomeTracker:
    """Persistent store for outcome records.

    v2.0: Stores outcomes alongside belief memory for historical querying.
    """

    def __init__(self, file_path: Optional[str] = None) -> None:
        if file_path is None:
            base = Path(__file__).resolve().parent.parent.parent
            file_path = str(base / "data" / "memory" / "outcomes.json")
        self._file_path = Path(file_path)
        self._records: list[OutcomeRecord] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        if self._file_path.exists():
            import json

            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._records = [
                    OutcomeRecord(**r) for r in data.get("records", [])
                ]
            except Exception as e:
                logger.warning("Failed to load outcomes, starting fresh: %s", str(e))
                self._records = []
        self._loaded = True

    def _flush(self) -> None:
        import json
        import os
        import tempfile

        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(self._records),
            "records": [r.model_dump(mode="json") for r in self._records],
        }
        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix=".json", prefix="outcomes_", dir=str(self._file_path.parent),
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp_path, str(self._file_path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def record(self, record: OutcomeRecord) -> None:
        self._ensure_loaded()
        self._records.append(record)
        self._flush()
        logger.debug("outcome_recorded", extra={"record_id": record.record_id})

    def record_batch(self, records: list[OutcomeRecord]) -> None:
        if not records:
            return
        self._ensure_loaded()
        self._records.extend(records)
        self._flush()
        logger.info("outcome_batch_recorded", extra={"count": len(records)})

    def get_all(self) -> list[OutcomeRecord]:
        self._ensure_loaded()
        return list(self._records)

    def get_by_dimension(self, dimension: str) -> list[OutcomeRecord]:
        self._ensure_loaded()
        dim_lower = dimension.lower()
        return [r for r in self._records if r.outcome.dimension.lower() == dim_lower]

    def get_pending(self) -> list[OutcomeRecord]:
        self._ensure_loaded()
        return [r for r in self._records if not r.outcome.is_evaluated]

    def get_evaluated(self) -> list[OutcomeRecord]:
        self._ensure_loaded()
        return [r for r in self._records if r.outcome.is_evaluated]

    def summary(self) -> OutcomeSummary:
        self._ensure_loaded()
        return OutcomeMetrics.compute_summary(self._records)

    def count(self) -> int:
        self._ensure_loaded()
        return len(self._records)


# ── Outcome Engine ───────────────────────────────────────────────────────────


class OutcomeEngine:
    """Orchestrates the full outcome tracking cycle.

    Workflow:
        1. create_outcome() — create a PENDING outcome from a BeliefRecord.
        2. evaluate_outcome() — evaluate against observed data.
        3. summary() — compute aggregate metrics.
    """

    def __init__(self, tracker: Optional[OutcomeTracker] = None) -> None:
        self._tracker = tracker or OutcomeTracker()
        self._evaluator = OutcomeEvaluator()

    def create_outcome(
        self,
        belief: BeliefRecord,
        run_id: str,
        observation_window_days: int = 7,
    ) -> PredictionOutcome:
        """Create a PENDING prediction outcome from a belief record.

        Args:
            belief: The BeliefRecord containing the prediction.
            run_id: The pipeline run identifier.
            observation_window_days: Days to wait before evaluating.

        Returns:
            A new PredictionOutcome in PENDING state.
        """
        outcome = PredictionOutcome(
            hypothesis_id=belief.hypothesis_id,
            belief_id=belief.belief_id,
            dimension=belief.dimension,
            predicted_statement=belief.statement,
            predicted_direction=belief.direction,
            predicted_confidence=belief.confidence,
            observation_window_days=observation_window_days,
            verdict=OutcomeVerdict.PENDING,
            predicted_at=belief.timestamp,
        )
        return outcome

    def persist(self, outcome: PredictionOutcome, run_id: str) -> OutcomeRecord:
        """Persist a prediction outcome to the tracker."""
        record = OutcomeRecord(run_id=run_id, outcome=outcome)
        self._tracker.record(record)
        return record

    def evaluate(
        self,
        outcome: PredictionOutcome,
        observed_direction: Optional[OutcomeDirection] = None,
        observed_value: Optional[float] = None,
    ) -> PredictionOutcome:
        """Evaluate a pending outcome against observed direction."""
        result = self._evaluator.evaluate(
            outcome,
            observed_value=observed_value,
            observed_direction=observed_direction,
        )
        return result

    def evaluate_pending(
        self,
        observed_map: dict[str, OutcomeDirection],
    ) -> list[OutcomeRecord]:
        """Evaluate all pending outcomes against observed directions.

        Args:
            observed_map: {dimension: realized_direction} for evaluation.

        Returns:
            Updated outcome records.
        """
        pending = self._tracker.get_pending()
        updated: list[OutcomeRecord] = []
        for record in pending:
            obs_dir = observed_map.get(record.outcome.dimension.lower())
            if obs_dir is not None:
                evaluated = self._evaluator.evaluate(record.outcome, observed_direction=obs_dir)
                record.outcome = evaluated
                updated.append(record)

        if updated:
            # Re-persist all records
            self._tracker._flush()
            logger.info(
                "outcomes_evaluated",
                extra={"count": len(updated)},
            )

        return updated

    def summary(self) -> OutcomeSummary:
        """Compute current outcome summary."""
        return self._tracker.summary()

    def get_history(self, dimension: Optional[str] = None) -> list[OutcomeRecord]:
        """Get outcome history, optionally filtered by dimension."""
        if dimension:
            return self._tracker.get_by_dimension(dimension)
        return self._tracker.get_all()
