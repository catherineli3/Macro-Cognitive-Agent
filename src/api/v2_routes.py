"""v2.0 API Routes — Continuous Learning endpoints.

GET /v2/beliefs        — Current agent beliefs and weights
GET /v2/learning       — Learning summary and patterns
GET /v2/outcomes       — Outcome history and metrics
GET /v2/accuracy       — Prediction accuracy per dimension
GET /v2/confidence     — Calibrated confidence data
POST /v2/relearn       — Trigger a learning cycle
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from src.learning.learning_engine import LearningEngine
from src.outcome.engine import OutcomeEngine
from src.pipeline import MacroResearchPipeline
from src.shared.logging import get_logger

router = APIRouter(prefix="/v2", tags=["v2.0 Continuous Learning"])

logger = get_logger(__name__)

# ── Lazy-initialized engines (singleton per process) ─────────────────────────

_pipeline: MacroResearchPipeline | None = None
_outcome_engine: OutcomeEngine | None = None
_learning_engine: LearningEngine | None = None


def _get_pipeline() -> MacroResearchPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = MacroResearchPipeline()
    return _pipeline


def _get_outcome_engine() -> OutcomeEngine:
    global _outcome_engine
    if _outcome_engine is None:
        p = _get_pipeline()
        p._ensure_v2_engines()
        _outcome_engine = p._outcome_engine
    return _outcome_engine


def _get_learning_engine() -> LearningEngine:
    global _learning_engine
    if _learning_engine is None:
        p = _get_pipeline()
        p._ensure_v2_engines()
        _learning_engine = p._learning_engine
    return _learning_engine


# ═══════════════════════════════════════════════════════════════════════════════
# Beliefs
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/beliefs")
async def get_beliefs() -> dict:
    """Get current Agent belief weights across all dimensions.

    Returns per-dimension: weight, accuracy, trend, streak, total predictions.
    """
    try:
        engine = _get_learning_engine()
        weights = engine.get_weights()

        beliefs_data = [
            {
                "dimension": bw.dimension,
                "weight": bw.current_weight,
                "accuracy": bw.historical_accuracy,
                "recent_accuracy": bw.recent_accuracy,
                "trend": bw.accuracy_trend,
                "streak": bw.streak,
                "total_predictions": bw.total_predictions,
                "correct_predictions": bw.correct_predictions,
                "reliability": bw.reliability,
                "last_updated": bw.last_updated.isoformat(),
            }
            for bw in weights
        ]

        return {
            "status": "ok",
            "count": len(beliefs_data),
            "beliefs": beliefs_data,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# Learning
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/learning")
async def get_learning() -> dict:
    """Get the current learning summary: patterns, weights, calibration.

    Automatically runs a learning cycle using the latest outcome data.
    """
    try:
        outcome = _get_outcome_engine()
        engine = _get_learning_engine()

        summary = outcome.summary()
        all_records = outcome.get_history()

        if summary.total_predictions > 0:
            learning = engine.learn(
                outcome_summary=summary,
                outcome_records=all_records,
            )
        else:
            learning = engine.learn(outcome_summary=summary, outcome_records=[])

        return {
            "status": "ok",
            "learning": {
                "total_outcomes": learning.total_tracked_outcomes,
                "global_hit_rate": learning.global_hit_rate,
                "brier_score": learning.brier_score,
                "calibration_score": learning.overall_calibration_score,
                "improvement_trend": learning.improvement_trend,
                "best_dimension": learning.best_dimension,
                "worst_dimension": learning.worst_dimension,
                "learned_patterns": learning.learned_patterns,
                "confidence_adjustments": learning.confidence_adjustments,
                "belief_weights": [
                    {
                        "dimension": bw.dimension,
                        "weight": bw.current_weight,
                        "accuracy": bw.historical_accuracy,
                        "trend": bw.accuracy_trend,
                    }
                    for bw in learning.belief_weights
                ],
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# Outcomes
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/outcomes")
async def get_outcomes(dimension: str | None = None, limit: int = 20) -> dict:
    """Get prediction outcome history.

    Query parameters:
        dimension: Filter by macro dimension (optional).
        limit: Max number of records to return (default 20).
    """
    try:
        outcome = _get_outcome_engine()
        records = outcome.get_history(dimension=dimension)
        summary = outcome.summary()

        # Paginate
        recent = records[-limit:] if len(records) > limit else records

        return {
            "status": "ok",
            "total": len(records),
            "returned": len(recent),
            "summary": {
                "hit_rate": summary.hit_rate,
                "brier_score": summary.brier_score,
                "total_evaluated": summary.evaluated_count,
                "pending": summary.pending_predictions,
                "per_dimension": summary.dimension_accuracy,
            },
            "outcomes": [
                {
                    "outcome_id": r.outcome.outcome_id,
                    "dimension": r.outcome.dimension,
                    "predicted_direction": r.outcome.predicted_direction.value,
                    "predicted_confidence": r.outcome.predicted_confidence,
                    "observed_direction": (
                        r.outcome.observed_direction.value
                        if r.outcome.observed_direction
                        else "pending"
                    ),
                    "verdict": r.outcome.verdict.value,
                    "predicted_at": r.outcome.predicted_at.isoformat(),
                    "evaluated_at": (
                        r.outcome.evaluated_at.isoformat() if r.outcome.evaluated_at else None
                    ),
                    "rationale": r.outcome.verdict_rationale,
                }
                for r in recent
            ],
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# Accuracy
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/accuracy")
async def get_accuracy() -> dict:
    """Get prediction accuracy metrics — hit rate, Brier score, per-dimension."""
    try:
        outcome = _get_outcome_engine()
        summary = outcome.summary()

        return {
            "status": "ok",
            "accuracy": {
                "hit_rate": summary.hit_rate,
                "brier_score": summary.brier_score,
                "precision": summary.precision,
                "directional_accuracy": summary.directional_accuracy,
                "correct": summary.correct_count,
                "incorrect": summary.incorrect_count,
                "partially_correct": summary.partially_correct_count,
                "pending": summary.pending_predictions,
                "total": summary.total_predictions,
                "evaluation_lag_days": summary.average_evaluation_lag_days,
                "per_dimension": summary.dimension_accuracy,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# Confidence Calibration
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/confidence")
async def get_confidence() -> dict:
    """Get calibrated confidence data for the current cycle."""
    try:
        engine = _get_learning_engine()
        weights = engine.get_weights()

        return {
            "status": "ok",
            "dimensions": [
                {
                    "dimension": bw.dimension,
                    "current_weight": bw.current_weight,
                    "initial_weight": bw.initial_weight,
                    "accuracy": bw.historical_accuracy,
                    "recent_accuracy": bw.recent_accuracy,
                    "reliability": bw.reliability,
                    "streak": bw.streak,
                    "decay_rate": bw.confidence_decay_rate,
                    "last_updated": bw.last_updated.isoformat(),
                }
                for bw in weights
            ],
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# Re-learn (manual trigger)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/relearn")
async def trigger_relearn() -> dict:
    """Manually trigger a learning cycle using all available outcome data.

    This forces the Agent to:
        1. Re-evaluate pending outcomes.
        2. Recompute belief weights.
        3. Re-mine patterns.
        4. Update dimension reliability scores.
    """
    try:
        outcome = _get_outcome_engine()
        engine = _get_learning_engine()

        summary = outcome.summary()
        all_records = outcome.get_history()

        learning = engine.learn(
            outcome_summary=summary,
            outcome_records=all_records,
        )

        logger.info(
            "manual_relearn_triggered",
            extra={
                "outcomes": learning.total_tracked_outcomes,
                "hit_rate": learning.global_hit_rate,
            },
        )

        return {
            "status": "ok",
            "message": f"Learning cycle completed. Processed {learning.total_tracked_outcomes} outcomes.",
            "result": {
                "global_hit_rate": learning.global_hit_rate,
                "brier_score": learning.brier_score,
                "best_dimension": learning.best_dimension,
                "worst_dimension": learning.worst_dimension,
                "patterns_found": len(learning.learned_patterns),
                "improvement_trend": learning.improvement_trend,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
