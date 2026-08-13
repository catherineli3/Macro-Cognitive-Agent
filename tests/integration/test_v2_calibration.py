"""v2.0 Confidence Calibration tests."""

from src.calibration.confidence_calibrator import ConfidenceCalibrator
from src.domain.signal import SignalDirection
from src.learning.learning_engine import LearningEngine
from src.schemas.hypothesis import HypothesisEvidence, HypothesisSchema, HypothesisSet
from src.schemas.outcome import (
    OutcomeDirection,
    OutcomeRecord,
    OutcomeVerdict,
    PredictionOutcome,
)
from src.schemas.reflection import ReflectionReport, ReflectionSet, ReflectionVerdict

# ── Fixtures ────────────────────────────────────────────────────────────────


def make_hypothesis(h_id, dim, direction, confidence, sup=3, con=0):
    sup_ev = [
        HypothesisEvidence(
            indicator=f"S{i}",
            signal_id=f"s_{i}",
            observation=f"Support {i}",
            interpretation=f"Evidence for {dim}",
            contribution=0.7,
            alignment="supporting",
        )
        for i in range(sup)
    ]
    con_ev = [
        HypothesisEvidence(
            indicator=f"C{i}",
            signal_id=f"c_{i}",
            observation=f"Contradict {i}",
            interpretation="Evidence against",
            contribution=0.3,
            alignment="contradicting",
        )
        for i in range(con)
    ]
    return HypothesisSchema(
        hypothesis_id=h_id,
        statement=f"{dim}: {direction.value} trend.",
        dimension=dim,
        direction=direction,
        confidence=confidence,
        supporting_evidence=sup_ev,
        contradicting_evidence=con_ev,
    )


def make_reflection(hyp, verdict="confirmed", updated_conf=None):
    return ReflectionReport(
        hypothesis_id=hyp.hypothesis_id,
        statement=hyp.statement,
        original_confidence=hyp.confidence,
        updated_confidence=updated_conf or hyp.confidence,
        verdict=ReflectionVerdict(verdict),
        findings=[],
        evidence_sufficiency="medium",
        evidence_consistency="consistent",
        review_summary=f"Review of {hyp.hypothesis_id}",
    )


# ── ConfidenceCalibrator ───────────────────────────────────────────────────


class TestConfidenceCalibrator:
    def test_no_history_no_adjustment(self):
        calibrator = ConfidenceCalibrator()
        hyp = make_hypothesis("h1", "Liquidity", SignalDirection.BULLISH, 0.82)
        cal = calibrator.calibrate_hypothesis(hyp, 0.82)
        # Without learning engine, defaults to 0.5 historical accuracy
        # calibrated = 0.82*0.50 + 0.5*0.30 + 0.5*0.20 = 0.41+0.15+0.10 = 0.66
        assert cal.calibrated_confidence < 0.82
        assert cal.calibration_delta > 0  # downward adjustment

    def test_high_accuracy_no_adjustment(self):
        engine = LearningEngine()
        # Pre-train engine with perfect Liquidity accuracy
        records = []
        for i in range(20):
            records.append(
                OutcomeRecord(
                    run_id=f"r{i}",
                    outcome=PredictionOutcome(
                        hypothesis_id=f"h{i}",
                        dimension="Liquidity",
                        predicted_statement="Test",
                        predicted_direction=SignalDirection.BULLISH,
                        predicted_confidence=0.8,
                        verdict=OutcomeVerdict.CORRECT,
                        observed_direction=OutcomeDirection.UP,
                    ),
                )
            )
        from src.outcome.engine import OutcomeMetrics

        summary = OutcomeMetrics.compute_summary(records)
        engine.learn(summary, records)

        calibrator = ConfidenceCalibrator(learning_engine=engine)
        hyp = make_hypothesis("h_new", "Liquidity", SignalDirection.BULLISH, 0.82)
        cal = calibrator.calibrate_hypothesis(hyp, 0.82)
        # With perfect history, calibrated should be close to raw
        assert cal.calibrated_confidence >= 0.70

    def test_poor_accuracy_downward_adjustment(self):
        engine = LearningEngine()
        # Pre-train with poor Growth accuracy
        records = []
        for i in range(20):
            correct = i < 5  # only 5/20 correct
            records.append(
                OutcomeRecord(
                    run_id=f"r{i}",
                    outcome=PredictionOutcome(
                        hypothesis_id=f"h{i}",
                        dimension="Growth",
                        predicted_statement="Test",
                        predicted_direction=SignalDirection.BULLISH,
                        predicted_confidence=0.8,
                        verdict=OutcomeVerdict.CORRECT if correct else OutcomeVerdict.INCORRECT,
                        observed_direction=(
                            OutcomeDirection.UP if correct else OutcomeDirection.DOWN
                        ),
                    ),
                )
            )
        from src.outcome.engine import OutcomeMetrics

        summary = OutcomeMetrics.compute_summary(records)
        engine.learn(summary, records)

        calibrator = ConfidenceCalibrator(learning_engine=engine)
        hyp = make_hypothesis("h_new", "Growth", SignalDirection.BULLISH, 0.82)
        cal = calibrator.calibrate_hypothesis(hyp, 0.82)
        # Poor history → significant downward adjustment
        assert cal.calibrated_confidence < 0.65
        assert cal.calibration_delta > 0.1

    def test_never_exceeds_raw(self):
        calibrator = ConfidenceCalibrator()
        hyp = make_hypothesis("h1", "Liquidity", SignalDirection.BULLISH, 0.50)
        cal = calibrator.calibrate_hypothesis(hyp, 0.50)
        assert cal.calibrated_confidence <= 0.50

    def test_calibrate_set(self):
        engine = LearningEngine()
        records = [
            OutcomeRecord(
                run_id=f"r{i}",
                outcome=PredictionOutcome(
                    hypothesis_id=f"h{i}",
                    dimension="Liquidity",
                    predicted_statement="Test",
                    predicted_direction=SignalDirection.BULLISH,
                    predicted_confidence=0.8,
                    verdict=OutcomeVerdict.CORRECT,
                    observed_direction=OutcomeDirection.UP,
                ),
            )
            for i in range(10)
        ]
        from src.outcome.engine import OutcomeMetrics

        summary = OutcomeMetrics.compute_summary(records)
        engine.learn(summary, records)

        calibrator = ConfidenceCalibrator(learning_engine=engine)
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis("ha", "Liquidity", SignalDirection.BULLISH, 0.80),
                make_hypothesis("hb", "Credit", SignalDirection.BEARISH, 0.70),
                make_hypothesis("hc", "Growth", SignalDirection.NEUTRAL, 0.60),
            ],
            dimensions_covered=["Liquidity", "Credit", "Growth"],
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "confirmed", 0.85),
                make_reflection(hyps.hypotheses[1], "confirmed", 0.75),
                make_reflection(hyps.hypotheses[2], "uncertain", 0.55),
            ]
        )

        result = calibrator.calibrate_set(hyps, refs, "run_test")
        assert len(result.calibrations) == 3
        assert result.global_calibration_factor > 0

    def test_rationale_generated(self):
        calibrator = ConfidenceCalibrator()
        hyp = make_hypothesis("h1", "Liquidity", SignalDirection.BULLISH, 0.82)
        cal = calibrator.calibrate_hypothesis(hyp, 0.82)
        assert len(cal.calibration_rationale) > 0
        assert cal.calibration_method in ("weighted_blend", "none")
