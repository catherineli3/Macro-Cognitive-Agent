"""v2.0 Outcome Engine tests — PredictionOutcome, OutcomeTracker, OutcomeEvaluator."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.domain.memory import BeliefStatus, TransitionType
from src.domain.signal import SignalDirection
from src.outcome.engine import OutcomeEngine, OutcomeEvaluator, OutcomeMetrics, OutcomeTracker
from src.schemas.memory import BeliefRecord
from src.schemas.outcome import (
    OutcomeDirection,
    OutcomeRecord,
    OutcomeVerdict,
    PredictionOutcome,
)

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def belief():
    return BeliefRecord(
        run_id="run_001",
        hypothesis_id="hyp_001",
        dimension="Liquidity",
        statement="DXY will strengthen as Fed maintains restrictive stance.",
        direction=SignalDirection.BULLISH,
        confidence=0.75,
        status=BeliefStatus.HELD,
        transition=TransitionType.NEW,
        supporting_count=3,
        contradicting_count=0,
        evidence_summary="Strong dollar signals.",
        review_summary="Review confirms.",
        timestamp=datetime(2026, 7, 1, tzinfo=UTC),
    )


@pytest.fixture
def tracker():
    with tempfile.TemporaryDirectory() as tmp:
        store_path = Path(tmp) / "outcomes.json"
        yield OutcomeTracker(file_path=str(store_path))


@pytest.fixture
def engine(tracker):
    return OutcomeEngine(tracker=tracker)


# ── PredictionOutcome ────────────────────────────────────────────────────────


class TestPredictionOutcome:
    def test_create_pending(self, belief):
        outcome = PredictionOutcome(
            hypothesis_id=belief.hypothesis_id,
            dimension=belief.dimension,
            predicted_statement=belief.statement,
            predicted_direction=belief.direction,
            predicted_confidence=belief.confidence,
        )
        assert outcome.verdict == OutcomeVerdict.PENDING
        assert not outcome.is_evaluated

    def test_create_evaluated(self):
        outcome = PredictionOutcome(
            hypothesis_id="h1",
            dimension="Liquidity",
            predicted_statement="Test",
            predicted_direction=SignalDirection.BULLISH,
            predicted_confidence=0.8,
            verdict=OutcomeVerdict.CORRECT,
            observed_direction=OutcomeDirection.UP,
        )
        assert outcome.is_evaluated
        assert outcome.is_correct
        assert not outcome.is_incorrect

    def test_partial_correct(self):
        outcome = PredictionOutcome(
            hypothesis_id="h1",
            dimension="Growth",
            predicted_statement="Test",
            predicted_direction=SignalDirection.NEUTRAL,
            predicted_confidence=0.5,
            verdict=OutcomeVerdict.PARTIALLY_CORRECT,
        )
        assert outcome.is_evaluated
        assert not outcome.is_correct
        assert not outcome.is_incorrect


# ── OutcomeEvaluator ─────────────────────────────────────────────────────────


class TestOutcomeEvaluator:
    def test_bullish_up_is_correct(self):
        outcome = PredictionOutcome(
            hypothesis_id="h1",
            dimension="Liquidity",
            predicted_statement="DXY up",
            predicted_direction=SignalDirection.BULLISH,
            predicted_confidence=0.8,
        )
        result = OutcomeEvaluator.evaluate(outcome, observed_direction=OutcomeDirection.UP)
        assert result.verdict == OutcomeVerdict.CORRECT

    def test_bearish_down_is_correct(self):
        outcome = PredictionOutcome(
            hypothesis_id="h1",
            dimension="Credit",
            predicted_statement="HYG down",
            predicted_direction=SignalDirection.BEARISH,
            predicted_confidence=0.7,
        )
        result = OutcomeEvaluator.evaluate(outcome, observed_direction=OutcomeDirection.DOWN)
        assert result.verdict == OutcomeVerdict.CORRECT

    def test_bullish_down_is_incorrect(self):
        outcome = PredictionOutcome(
            hypothesis_id="h1",
            dimension="Growth",
            predicted_statement="PMI up",
            predicted_direction=SignalDirection.BULLISH,
            predicted_confidence=0.6,
        )
        result = OutcomeEvaluator.evaluate(outcome, observed_direction=OutcomeDirection.DOWN)
        assert result.verdict == OutcomeVerdict.INCORRECT

    def test_bearish_up_is_incorrect(self):
        outcome = PredictionOutcome(
            hypothesis_id="h1",
            dimension="Inflation",
            predicted_statement="CPI down",
            predicted_direction=SignalDirection.BEARISH,
            predicted_confidence=0.9,
        )
        result = OutcomeEvaluator.evaluate(outcome, observed_direction=OutcomeDirection.UP)
        assert result.verdict == OutcomeVerdict.INCORRECT

    def test_neutral_flat_is_correct(self):
        outcome = PredictionOutcome(
            hypothesis_id="h1",
            dimension="Risk_Appetite",
            predicted_statement="VIX flat",
            predicted_direction=SignalDirection.NEUTRAL,
            predicted_confidence=0.5,
        )
        result = OutcomeEvaluator.evaluate(outcome, observed_direction=OutcomeDirection.FLAT)
        assert result.verdict == OutcomeVerdict.CORRECT

    def test_neutral_up_is_partial(self):
        outcome = PredictionOutcome(
            hypothesis_id="h1",
            dimension="Risk_Appetite",
            predicted_statement="Flat",
            predicted_direction=SignalDirection.NEUTRAL,
            predicted_confidence=0.5,
        )
        result = OutcomeEvaluator.evaluate(outcome, observed_direction=OutcomeDirection.UP)
        assert result.verdict == OutcomeVerdict.PARTIALLY_CORRECT

    def test_no_observation_stays_pending(self):
        outcome = PredictionOutcome(
            hypothesis_id="h1",
            dimension="Liquidity",
            predicted_statement="Test",
            predicted_direction=SignalDirection.BULLISH,
            predicted_confidence=0.7,
        )
        result = OutcomeEvaluator.evaluate(outcome, observed_direction=None)
        assert result.verdict == OutcomeVerdict.PENDING


# ── OutcomeMetrics ───────────────────────────────────────────────────────────


class TestOutcomeMetrics:
    def test_empty_summary(self):
        summary = OutcomeMetrics.compute_summary([])
        assert summary.total_predictions == 0
        assert summary.hit_rate == 0.0
        assert summary.brier_score == 0.0

    def test_perfect_accuracy(self):
        records = []
        for i in range(5):
            outcome = PredictionOutcome(
                hypothesis_id=f"h{i}",
                dimension="Liquidity",
                predicted_statement="Test",
                predicted_direction=SignalDirection.BULLISH,
                predicted_confidence=0.8,
                verdict=OutcomeVerdict.CORRECT,
                observed_direction=OutcomeDirection.UP,
                evaluated_at=datetime.now(UTC),
            )
            records.append(OutcomeRecord(run_id=f"r{i}", outcome=outcome))

        summary = OutcomeMetrics.compute_summary(records)
        assert summary.hit_rate == 1.0
        assert summary.correct_count == 5
        assert summary.incorrect_count == 0

    def test_mixed_accuracy(self):
        records = []
        for i in range(3):
            outcome = PredictionOutcome(
                hypothesis_id=f"h{i}",
                dimension="Growth",
                predicted_statement="Test",
                predicted_direction=SignalDirection.BULLISH,
                predicted_confidence=0.8,
                verdict=OutcomeVerdict.CORRECT if i < 2 else OutcomeVerdict.INCORRECT,
                observed_direction=OutcomeDirection.UP if i < 2 else OutcomeDirection.DOWN,
                evaluated_at=datetime.now(UTC),
            )
            records.append(OutcomeRecord(run_id=f"r{i}", outcome=outcome))

        summary = OutcomeMetrics.compute_summary(records)
        assert summary.hit_rate == pytest.approx(2 / 3, rel=0.1)
        assert summary.correct_count == 2
        assert summary.incorrect_count == 1

    def test_brier_score_perfect(self):
        outcome = PredictionOutcome(
            hypothesis_id="h1",
            dimension="Liquidity",
            predicted_statement="Test",
            predicted_direction=SignalDirection.BULLISH,
            predicted_confidence=1.0,
            verdict=OutcomeVerdict.CORRECT,
            observed_direction=OutcomeDirection.UP,
            evaluated_at=datetime.now(UTC),
        )
        record = OutcomeRecord(run_id="r1", outcome=outcome)
        summary = OutcomeMetrics.compute_summary([record])
        assert summary.brier_score == pytest.approx(0.0, abs=0.01)

    def test_per_dimension_accuracy(self):
        records = []
        for dim in ["Liquidity", "Credit", "Growth"]:
            for i in range(2):
                outcome = PredictionOutcome(
                    hypothesis_id=f"h_{dim}_{i}",
                    dimension=dim,
                    predicted_statement=f"{dim} test",
                    predicted_direction=SignalDirection.BULLISH,
                    predicted_confidence=0.8,
                    verdict=OutcomeVerdict.CORRECT,
                    observed_direction=OutcomeDirection.UP,
                    evaluated_at=datetime.now(UTC),
                )
                records.append(OutcomeRecord(run_id=f"r_{dim}_{i}", outcome=outcome))

        summary = OutcomeMetrics.compute_summary(records)
        for dim in ["liquidity", "credit", "growth"]:
            assert dim in summary.dimension_accuracy
            assert summary.dimension_accuracy[dim]["hit_rate"] == 1.0


# ── OutcomeTracker ───────────────────────────────────────────────────────────


class TestOutcomeTracker:
    def test_persist_and_load(self, tracker):
        outcome = PredictionOutcome(
            hypothesis_id="h1",
            dimension="Liquidity",
            predicted_statement="Test",
            predicted_direction=SignalDirection.BULLISH,
            predicted_confidence=0.8,
        )
        record = OutcomeRecord(run_id="r1", outcome=outcome)
        tracker.record(record)
        assert tracker.count() == 1

    def test_batch_record(self, tracker):
        records = []
        for i in range(5):
            outcome = PredictionOutcome(
                hypothesis_id=f"h{i}",
                dimension="Liquidity",
                predicted_statement=f"Test {i}",
                predicted_direction=SignalDirection.BULLISH,
                predicted_confidence=0.7,
            )
            records.append(OutcomeRecord(run_id=f"r{i}", outcome=outcome))
        tracker.record_batch(records)
        assert tracker.count() == 5

    def test_get_pending(self, tracker):
        outcome = PredictionOutcome(
            hypothesis_id="h1",
            dimension="Liquidity",
            predicted_statement="Test",
            predicted_direction=SignalDirection.BULLISH,
            predicted_confidence=0.7,
        )
        tracker.record(OutcomeRecord(run_id="r1", outcome=outcome))
        pending = tracker.get_pending()
        assert len(pending) == 1
        assert not pending[0].outcome.is_evaluated

    def test_get_evaluated(self, tracker):
        outcome1 = PredictionOutcome(
            hypothesis_id="h1",
            dimension="Liquidity",
            predicted_statement="Test",
            predicted_direction=SignalDirection.BULLISH,
            predicted_confidence=0.7,
            verdict=OutcomeVerdict.CORRECT,
            observed_direction=OutcomeDirection.UP,
            evaluated_at=datetime.now(UTC),
        )
        outcome2 = PredictionOutcome(
            hypothesis_id="h2",
            dimension="Credit",
            predicted_statement="Test",
            predicted_direction=SignalDirection.BEARISH,
            predicted_confidence=0.6,
        )
        tracker.record(OutcomeRecord(run_id="r1", outcome=outcome1))
        tracker.record(OutcomeRecord(run_id="r2", outcome=outcome2))
        evaluated = tracker.get_evaluated()
        assert len(evaluated) == 1

    def test_get_by_dimension(self, tracker):
        for dim in ["Liquidity", "Credit", "Liquidity"]:
            outcome = PredictionOutcome(
                hypothesis_id=f"h_{dim}",
                dimension=dim,
                predicted_statement=f"{dim} test",
                predicted_direction=SignalDirection.BULLISH,
                predicted_confidence=0.7,
            )
            tracker.record(OutcomeRecord(run_id="r1", outcome=outcome))
        liq = tracker.get_by_dimension("Liquidity")
        assert len(liq) == 2


# ── OutcomeEngine ────────────────────────────────────────────────────────────


class TestOutcomeEngine:
    def test_create_outcome_from_belief(self, engine, belief):
        outcome = engine.create_outcome(belief, "run_001")
        assert outcome.hypothesis_id == belief.hypothesis_id
        assert outcome.dimension == "Liquidity"
        assert outcome.predicted_confidence == 0.75
        assert outcome.verdict == OutcomeVerdict.PENDING

    def test_persist(self, engine, belief):
        outcome = engine.create_outcome(belief, "run_001")
        record = engine.persist(outcome, "run_001")
        assert record.run_id == "run_001"
        assert engine._tracker.count() == 1

    def test_evaluate(self, engine, belief):
        outcome = engine.create_outcome(belief, "run_001")
        result = engine.evaluate(outcome, observed_direction=OutcomeDirection.UP)
        assert result.verdict == OutcomeVerdict.CORRECT

    def test_summary(self, engine, belief):
        outcome = engine.create_outcome(belief, "run_001")
        engine.persist(outcome, "run_001")
        # Evaluate
        engine._tracker._records[0].outcome = engine.evaluate(
            engine._tracker._records[0].outcome,
            observed_direction=OutcomeDirection.UP,
        )
        summary = engine.summary()
        assert summary.total_predictions == 1
        assert summary.hit_rate == 1.0

    def test_evaluate_pending(self, engine):
        # Create 2 pending outcomes in different dimensions
        for dim, direction in [
            ("Liquidity", SignalDirection.BULLISH),
            ("Growth", SignalDirection.BEARISH),
        ]:
            belief = BeliefRecord(
                run_id="r1",
                hypothesis_id=f"h_{dim}",
                dimension=dim,
                statement=f"{dim} test",
                direction=direction,
                confidence=0.8,
                status=BeliefStatus.HELD,
                transition=TransitionType.NEW,
                supporting_count=2,
                contradicting_count=0,
                evidence_summary="Test",
                review_summary="Test",
                timestamp=datetime(2026, 7, 1, tzinfo=UTC),
            )
            outcome = engine.create_outcome(belief, "r1")
            engine.persist(outcome, "r1")

        # Evaluate with observed map
        observed = {"liquidity": OutcomeDirection.UP, "growth": OutcomeDirection.UP}
        updated = engine.evaluate_pending(observed)

        assert len(updated) == 2
        # Liquidity: bullish + UP = CORRECT
        liq = [r for r in updated if r.outcome.dimension == "Liquidity"][0]
        assert liq.outcome.verdict == OutcomeVerdict.CORRECT
        # Growth: bearish + UP = INCORRECT
        gr = [r for r in updated if r.outcome.dimension == "Growth"][0]
        assert gr.outcome.verdict == OutcomeVerdict.INCORRECT

    def test_empty_summary(self, engine):
        summary = engine.summary()
        assert summary.total_predictions == 0
        assert summary.hit_rate == 0.0
