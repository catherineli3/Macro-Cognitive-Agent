"""V3 Release 3.0 Smoke Test."""

import asyncio

from src.belief_versioning import BeliefVersionManager
from src.diagnosis import DiagnosisEngine
from src.evaluation import OutcomeEvaluationEngine
from src.hypothesis_library import HypothesisLibrary
from src.learning_log import LearningLogRepository
from src.learning_unit import LearningUnitValidator
from src.metrics import KPIMetricsEngine
from src.prediction import MultiPredictionEngine
from src.schemas.hypothesis import HypothesisSchema, HypothesisSet
from src.schemas.learning_unit import LearningUnit
from src.schemas.signal import SignalDirection


async def main():
    print("=== V3 Smoke Test ===")

    # 1. Hypothesis Library
    lib = HypothesisLibrary(storage_dir="data/v3_test/hypothesis_library")
    hid = await lib.register("h-test", "liquidity", "Liquidity tightening", "bearish")
    entry = await lib.get(hid)
    assert entry is not None
    print(f"1. Library: registered {hid}")

    # 2. Belief Versioning
    bvm = BeliefVersionManager(storage_dir="data/v3_test/belief_versions")
    belief = await bvm.create_belief("liquidity", "liquidity->equity", 0.85, 0.9)
    assert belief.current_version == 1
    assert len(belief.version_history) == 1
    print(f"2. Belief: v{belief.current_version} w={belief.weight}")

    # 3. Learning Unit validation
    validator = LearningUnitValidator()
    lu = LearningUnit(belief_id=belief.belief_id, weight_delta=-0.04)
    ok, violations = validator.validate(lu, current_weight=0.85)
    assert ok, str(violations)
    print(f"3. LearningUnit: valid={ok}")

    # 4. Prediction Engine
    eng = MultiPredictionEngine()
    h = HypothesisSchema(
        statement="Liquidity tightening",
        dimension="liquidity",
        direction=SignalDirection.BEARISH,
    )
    hs = HypothesisSet(hypotheses=[h])
    batch = await eng.generate_predictions(hs, "test-run")
    assert batch.total_predictions == 3
    print(f"4. Predictions: {batch.total_predictions} preds, {batch.channel_count} channels")
    for p in batch.predictions:
        print(
            f"   {p.prediction_tier.value}: {p.indicator} {p.direction} ({p.transmission_channel})"
        )

    # 5. Evaluation
    ev = OutcomeEvaluationEngine()
    actual = {
        "NASDAQ": (18000.0, 18500.0),  # ↓ bearish correct
        "USD": (106.5, 105.5),  # ↑ bullish (wrong direction)
        "Gold": (2350.0, 2310.0),  # ↑ bullish (wrong direction)
    }
    report = await ev.evaluate_batch(batch, actual)
    print(
        f"5. Evaluation: da={report.directional_accuracy:.1%}, ch_acc={report.accuracy_by_channel}"
    )

    # 6. Diagnosis
    diag = DiagnosisEngine()
    dr = await diag.diagnose_batch(report)
    print(
        f"6. Diagnosis: {dr.total_diagnosed} classified, {dr.correct_count} correct, {dr.incorrect_count} errors"
    )
    print(f"   Error dist: {dr.error_distribution}")

    # 7. Learning Log
    log = LearningLogRepository(storage_dir="data/v3_test/learning_log")
    from src.schemas.learning_log import LearningLogEntry

    entries = []
    for outcome, classification in zip(report.outcomes, dr.classifications):
        pred = next(
            (p for p in batch.predictions if p.prediction_id == outcome.prediction_id), None
        )
        if pred:
            entry = LearningLogEntry(
                run_id="test-run",
                prediction_id=pred.prediction_id,
                hypothesis_id=pred.source_hypothesis_id,
                dimension=pred.dimension,
                transmission_channel=pred.transmission_channel,
                prediction_tier=pred.prediction_tier.value,
                predicted_direction=pred.direction,
                predicted_confidence=pred.confidence,
                horizon=pred.horizon,
                was_correct=outcome.correct,
                actual_direction=outcome.actual_direction,
                error_magnitude=outcome.error_magnitude,
                error_category=(
                    classification.error_category.value if classification.error_category else None
                ),
            )
            entries.append(entry)
    await log.append_batch(entries)
    print(f"7. LearningLog: {await log.count()} entries")

    # 8. Belief Versioning update
    lu2 = LearningUnit(belief_id=belief.belief_id, weight_delta=-0.02)
    updated = await bvm.create_version(belief, lu2, "diag-test", "Test update")
    assert updated.current_version == 2
    assert len(updated.version_history) == 2
    print(
        f"8. Belief Updated: v{updated.current_version} w={updated.weight} ({len(updated.version_history)} versions)"
    )

    # 9. Hypothesis Library score update
    score = await lib.update_score("h-test", batch.predictions)
    print(f"9. Library Score: total={score.total_score:.2f}" if score else "9. Library Score: N/A")

    # 10. KPI
    kpi = KPIMetricsEngine()
    kpi1 = await kpi.compute_kpi1(library_avg_score=0.65, active_hypotheses=1)
    kpi2 = await kpi.compute_kpi2(
        report.directional_accuracy,
        report.mean_absolute_error,
        report.rmse,
        report.total_outcomes,
        report.total_correct,
    )
    kpi3 = await kpi.compute_kpi3(0.15, report.brier_score)
    kpi4 = await kpi.compute_kpi4(total_errors_classified=3)
    from src.schemas.kpi import FourKPIReport, WindowPeriod

    kpi_report = FourKPIReport(
        window=WindowPeriod.D30,
        kpi1_hypothesis_accuracy=kpi1,
        kpi2_prediction_error=kpi2,
        kpi3_calibration=kpi3,
        kpi4_learning_speed=kpi4,
    )
    print(f"10. KPI: overall={kpi_report.overall_score:.3f}")

    print()
    print("=== ALL V3 SMOKE TESTS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
