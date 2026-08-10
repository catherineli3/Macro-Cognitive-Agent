"""PredictionScorer — nuanced scoring beyond "correct/wrong" binary.

Four dimensions of scoring:
    1. Direction Score: Did we get the direction right?
    2. Magnitude Score: How close was our magnitude estimate?
    3. Brier Score: (confidence - outcome)^2, lower is better
    4. Calibration Decomposition: Brier = uncertainty + calibration + resolution

Plus composite score + letter grade (A+ through F).
"""

from __future__ import annotations

import math
from typing import Any

from src.learning.schemas import (
    PredictionOutcome,
    PredictionScore,
    ScoredPrediction,
)

GRADE_THRESHOLDS = [
    (0.90, "A+"), (0.80, "A"), (0.65, "B"),
    (0.50, "C"), (0.35, "D"), (0.00, "F"),
]


class PredictionScorer:
    """Scores individual predictions across multiple dimensions."""

    def score_prediction(self, outcome: PredictionOutcome) -> PredictionScore:
        direction = self._score_direction(outcome)
        magnitude = self._score_magnitude(outcome)
        brier = self._score_brier(outcome)
        calibration, resolution = self._decompose_brier(outcome)
        composite = self._compute_composite(direction, magnitude, brier, calibration)
        grade = self._assign_grade(composite)

        return PredictionScore(
            prediction_id=outcome.prediction_id,
            outcome=outcome,
            direction_score=direction,
            magnitude_score=magnitude,
            brier_score=brier,
            calibration_score=calibration,
            resolution_score=resolution,
            composite_score=composite,
            grade=grade,
        )

    def score_batch(self, outcomes: list) -> list[ScoredPrediction]:
        return [
            ScoredPrediction(outcome=o, score=self.score_prediction(o))
            for o in outcomes
        ]

    def _score_direction(self, o: PredictionOutcome) -> float:
        if o.was_correct:
            return 1.0
        pred, actual = o.predicted_direction.lower(), o.actual_direction.lower()
        if pred == actual:
            return 1.0
        if pred == "flat" and abs(o.actual_change_pct) < 2.0:
            return 0.7
        if abs(o.actual_change_pct) > 3.0 and pred != "flat" and actual != "flat":
            return 0.3
        return 0.0

    def _score_magnitude(self, o: PredictionOutcome) -> float:
        if o.predicted_value == 0 or o.actual_value == 0:
            return 0.3
        if o.actual_change_pct == 0:
            return 0.5
        error_pct = abs(abs(o.actual_change_pct) - abs(o.predicted_direction == o.actual_direction and o.predicted_value or 0))
        if o.predicted_value > 0 and abs(o.predicted_value) > 0:
            error_pct = abs(o.actual_change_pct - o.predicted_value)
        else:
            error_pct = abs(o.actual_change_pct)
        score = max(0.0, 1.0 - error_pct / 20.0)
        return round(score, 4)

    def _score_brier(self, o: PredictionOutcome) -> float:
        outcome_binary = 1.0 if o.was_correct else 0.0
        return (o.confidence - outcome_binary) ** 2

    def _decompose_brier(self, o: PredictionOutcome) -> tuple:
        """Decompose Brier score into calibration error and resolution."""
        outcome_binary = 1.0 if o.was_correct else 0.0
        # calibration: (confidence_bin_pct - avg_outcome_in_bin)^2
        # For single prediction: calibration is the squared difference
        calibration = (o.confidence - outcome_binary) ** 2
        # resolution: how well predictions separate outcomes
        base_rate = 0.5
        resolution = (outcome_binary - base_rate) ** 2
        return calibration, resolution

    def _compute_composite(
        self, direction: float, magnitude: float, brier: float, calibration: float
    ) -> float:
        brier_normalized = max(0.0, 1.0 - brier * 4.0)
        calibration_normalized = max(0.0, 1.0 - calibration * 4.0)
        composite = (
            0.35 * direction
            + 0.15 * magnitude
            + 0.25 * brier_normalized
            + 0.25 * calibration_normalized
        )
        return round(composite, 4)

    def _assign_grade(self, composite: float) -> str:
        for threshold, grade in GRADE_THRESHOLDS:
            if composite >= threshold:
                return grade
        return "F"

    def compute_batch_metrics(
        self, scored: list[ScoredPrediction]
    ) -> dict:
        """Aggregate metrics across a batch of scored predictions."""
        if not scored:
            return {"n": 0, "accuracy": 0, "avg_brier": 0, "avg_composite": 0, "grade_distribution": {}}

        n = len(scored)
        accuracy = sum(1 for s in scored if s.outcome.was_correct) / n
        avg_brier = sum(s.score.brier_score for s in scored) / n
        avg_composite = sum(s.score.composite_score for s in scored) / n
        avg_direction = sum(s.score.direction_score for s in scored) / n
        avg_magnitude = sum(s.score.magnitude_score for s in scored) / n

        grade_dist = {}
        for s in scored:
            g = s.score.grade
            grade_dist[g] = grade_dist.get(g, 0) + 1

        return {
            "n": n,
            "accuracy": round(accuracy, 3),
            "avg_brier": round(avg_brier, 3),
            "avg_composite": round(avg_composite, 3),
            "avg_direction": round(avg_direction, 3),
            "avg_magnitude": round(avg_magnitude, 3),
            "grade_distribution": grade_dist,
        }
