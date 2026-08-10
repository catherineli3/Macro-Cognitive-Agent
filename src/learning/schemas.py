"""V3.5 Learning Engine Schemas — data structures for the feedback loop.

The learning cycle:
    Prediction → Outcome → Scoring → Calibration → Weight Update
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class PredictionOutcome:
    """Resolved outcome of a prediction — market reality vs. prediction."""

    prediction_id: str = ""
    belief_id: str = ""
    belief_title: str = ""

    # Original prediction
    statement: str = ""
    asset: str = ""
    predicted_direction: str = ""  # "up" / "down" / "flat"
    predicted_value: float = 0.0
    confidence: float = 0.5
    time_horizon_days: int = 30

    # Actual outcome
    actual_direction: str = ""
    actual_value: float = 0.0
    actual_change_pct: float = 0.0

    # Resolution
    was_correct: bool = False
    resolved_at: str = ""
    days_to_resolution: int = 0

    def to_dict(self) -> dict:
        return {
            "prediction_id": self.prediction_id,
            "belief_id": self.belief_id,
            "belief_title": self.belief_title,
            "statement": self.statement,
            "asset": self.asset,
            "predicted_direction": self.predicted_direction,
            "predicted_value": self.predicted_value,
            "confidence": self.confidence,
            "time_horizon_days": self.time_horizon_days,
            "actual_direction": self.actual_direction,
            "actual_value": self.actual_value,
            "actual_change_pct": self.actual_change_pct,
            "was_correct": self.was_correct,
            "resolved_at": self.resolved_at,
            "days_to_resolution": self.days_to_resolution,
        }


@dataclass
class PredictionScore:
    """Nuanced scoring of a single prediction — beyond correct/wrong."""

    prediction_id: str = ""
    outcome: PredictionOutcome = None

    # Core scores (0-1, higher = better)
    direction_score: float = 0.0   # Was direction right?
    magnitude_score: float = 0.0   # Was magnitude close?
    brier_score: float = 0.0       # (confidence - outcome)^2, lower is better
    calibration_score: float = 0.0  # Brier decomposed: calibration component
    resolution_score: float = 0.0   # Brier decomposed: resolution component
    composite_score: float = 0.0    # Weighted combination

    # Classification
    grade: str = ""  # "A+" / "A" / "B" / "C" / "D" / "F"

    def __post_init__(self):
        if self.outcome is None:
            self.outcome = PredictionOutcome()

    def to_dict(self) -> dict:
        return {
            "prediction_id": self.prediction_id,
            "direction_score": self.direction_score,
            "magnitude_score": self.magnitude_score,
            "brier_score": self.brier_score,
            "calibration_score": self.calibration_score,
            "resolution_score": self.resolution_score,
            "composite_score": self.composite_score,
            "grade": self.grade,
        }


@dataclass
class ScoredPrediction:
    """A fully resolved and scored prediction, linking outcome to score."""

    outcome: PredictionOutcome = field(default_factory=PredictionOutcome)
    score: PredictionScore = field(default_factory=PredictionScore)


@dataclass
class BeliefCalibrationResult:
    """Result of recalibrating a belief based on its prediction track record."""

    belief_id: str = ""
    belief_title: str = ""
    domain: str = ""

    # Before calibration
    original_confidence: float = 0.5
    original_alpha: float = 1.0
    original_beta: float = 1.0

    # Track record summary
    total_predictions: int = 0
    correct_predictions: int = 0
    raw_accuracy: float = 0.0      # simple: correct/total

    # Calibrated values
    calibrated_confidence: float = 0.5
    calibrated_alpha: float = 1.0
    calibrated_beta: float = 1.0

    # Calibration assessment
    calibration_bias: float = 0.0   # positive = overconfident
    is_overconfident: bool = False
    is_underconfident: bool = False
    recommendation: str = ""        # "maintain" / "increase_confidence" / "decrease_confidence"

    def to_dict(self) -> dict:
        return {
            "belief_id": self.belief_id,
            "belief_title": self.belief_title,
            "domain": self.domain,
            "original_confidence": self.original_confidence,
            "calibrated_confidence": self.calibrated_confidence,
            "raw_accuracy": self.raw_accuracy,
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "calibration_bias": self.calibration_bias,
            "is_overconfident": self.is_overconfident,
            "is_underconfident": self.is_underconfident,
            "recommendation": self.recommendation,
        }


@dataclass
class ModelPerformance:
    """Performance metrics for a single mental model."""

    model_name: str = ""
    domain: str = ""

    # Prediction history
    total_predictions: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.0

    # Calibration
    avg_confidence: float = 0.0
    calibration_error: float = 0.0  # |accuracy - avg_confidence|
    is_calibrated: bool = False

    # Recent trend
    recent_accuracy: float = 0.0    # Last 10 predictions
    momentum: float = 0.0           # Recent vs overall (-1 to 1)

    # Derived from beliefs
    belief_count: int = 0
    active_beliefs: int = 0

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "domain": self.domain,
            "accuracy": self.accuracy,
            "total_predictions": self.total_predictions,
            "calibration_error": self.calibration_error,
            "is_calibrated": self.is_calibrated,
            "recent_accuracy": self.recent_accuracy,
            "momentum": self.momentum,
            "active_beliefs": self.active_beliefs,
        }


@dataclass
class ModelWeightRecommendation:
    """Recommended weight adjustment for a model."""

    model_name: str = ""
    current_weight: float = 1.0
    recommended_weight: float = 1.0
    adjustment: float = 0.0          # new_weight - current_weight
    reason: str = ""


@dataclass
class LearningReport:
    """Complete learning cycle report."""

    report_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    date: str = ""

    # Resolution summary
    predictions_resolved: int = 0
    predictions_pending: int = 0
    overall_accuracy: float = 0.0
    overall_brier_score: float = 0.0

    # Calibration results
    beliefs_calibrated: int = 0
    overconfident_beliefs: int = 0
    underconfident_beliefs: int = 0

    # Model performance
    model_performances: list[ModelPerformance] = field(default_factory=list)
    weight_recommendations: list[ModelWeightRecommendation] = field(default_factory=list)

    # Top findings
    best_domain: str = ""
    worst_domain: str = ""
    key_insights: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)

    # Scored predictions
    scored_predictions: list[ScoredPrediction] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "date": self.date,
            "predictions_resolved": self.predictions_resolved,
            "predictions_pending": self.predictions_pending,
            "overall_accuracy": self.overall_accuracy,
            "overall_brier_score": self.overall_brier_score,
            "beliefs_calibrated": self.beliefs_calibrated,
            "overconfident_beliefs": self.overconfident_beliefs,
            "underconfident_beliefs": self.underconfident_beliefs,
            "model_performances": [mp.to_dict() for mp in self.model_performances],
            "weight_recommendations": [wr.__dict__ for wr in self.weight_recommendations],
            "best_domain": self.best_domain,
            "worst_domain": self.worst_domain,
            "key_insights": self.key_insights,
            "action_items": self.action_items,
        }
