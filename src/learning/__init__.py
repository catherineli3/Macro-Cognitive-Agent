"""V3.5 Learning & Calibration Engine — closes the feedback loop.

Core capabilities:
    - OutcomeCollector: Auto-resolve past predictions against market data
    - PredictionScorer: Nuanced scoring (Brier, calibration, direction, magnitude)
    - BeliefCalibration: Recalibrate belief confidence from track record
    - ModelWeightOptimizer: Adjust model weights based on predictive performance

This transforms the agent from "one-shot analysis" to "learning from mistakes".
"""

from src.learning.schemas import (
    PredictionOutcome,
    PredictionScore,
    ScoredPrediction,
    BeliefCalibrationResult,
    ModelPerformance,
    ModelWeightRecommendation,
    LearningReport,
)

from src.learning.outcome_collector import OutcomeCollector
from src.learning.prediction_scorer import PredictionScorer
from src.learning.belief_calibration import BeliefCalibration
from src.learning.model_weight_optimizer import ModelWeightOptimizer

__all__ = [
    # Schemas
    "PredictionOutcome",
    "PredictionScore",
    "ScoredPrediction",
    "BeliefCalibrationResult",
    "ModelPerformance",
    "ModelWeightRecommendation",
    "LearningReport",
    # Engines
    "OutcomeCollector",
    "PredictionScorer",
    "BeliefCalibration",
    "ModelWeightOptimizer",
]
