"""v2.0 Learning Engine tests — BeliefUpdater, PatternMiner, LearningEngine."""

from datetime import UTC, datetime

import pytest

from src.domain.signal import SignalDirection
from src.learning.learning_engine import (
    BeliefUpdater,
    ConfidenceDecay,
    LearningEngine,
    PatternMiner,
)
from src.schemas.learning import LearningSummary
from src.schemas.outcome import (
    OutcomeDirection,
    OutcomeRecord,
    OutcomeSummary,
    OutcomeVerdict,
    PredictionOutcome,
)

# ── Fixtures ────────────────────────────────────────────────────────────────


def make_outcome(h_id, dim, direction, confidence, correct=True):
    return OutcomeRecord(
        run_id=f"run_{h_id}",
        outcome=PredictionOutcome(
            outcome_id=f"out_{h_id}",
            hypothesis_id=h_id,
            dimension=dim,
            predicted_statement=f"Test {h_id}",
            predicted_direction=direction,
            predicted_confidence=confidence,
            verdict=OutcomeVerdict.CORRECT if correct else OutcomeVerdict.INCORRECT,
            observed_direction=(
                OutcomeDirection.UP
                if direction == SignalDirection.BULLISH and correct
                else (
                    OutcomeDirection.DOWN
                    if direction == SignalDirection.BEARISH and correct
                    else (
                        OutcomeDirection.DOWN
                        if direction == SignalDirection.BULLISH and not correct
                        else OutcomeDirection.UP
                    )
                )
            ),
            evaluated_at=datetime.now(UTC),
        ),
    )


def make_outcome_summary(records, dim_accuracy=None):
    from src.outcome.engine import OutcomeMetrics

    return OutcomeMetrics.compute_summary(records)


# ── BeliefUpdater ───────────────────────────────────────────────────────────


class TestBeliefUpdater:
    def test_initialize_weights(self):
        updater = BeliefUpdater()
        weights = updater.initialize_weights()
        assert len(weights) == 5
        for w in weights:
            assert w.current_weight == 0.5
            assert w.initial_weight == 0.5

    def test_update_from_perfect_accuracy(self):
        updater = BeliefUpdater(learning_rate=0.3)
        weights = updater.initialize_weights()

        records = [
            make_outcome(f"h{i}", "Liquidity", SignalDirection.BULLISH, 0.8) for i in range(10)
        ]
        summary = make_outcome_summary(records)

        updated = updater.update_from_summary(weights, summary, records)
        liq = [w for w in updated if w.dimension == "liquidity"][0]
        assert liq.historical_accuracy == 1.0
        # Weight should move toward 1.0: 0.5 * (1-0.3) + 1.0 * 0.3 = 0.65
        assert liq.current_weight == pytest.approx(0.65, abs=0.01)
        assert liq.total_predictions == 10
        assert liq.correct_predictions == 10

    def test_update_from_poor_accuracy(self):
        updater = BeliefUpdater(learning_rate=0.3)
        weights = updater.initialize_weights()

        records = []
        for i in range(10):
            correct = i < 2  # only 2/10 correct
            records.append(
                make_outcome(f"h{i}", "Liquidity", SignalDirection.BULLISH, 0.8, correct=correct)
            )

        summary = make_outcome_summary(records)
        updated = updater.update_from_summary(weights, summary, records)
        liq = [w for w in updated if w.dimension == "liquidity"][0]
        assert liq.historical_accuracy == pytest.approx(0.2, abs=0.05)

    def test_streak_positive(self):
        updater = BeliefUpdater()
        weights = updater.initialize_weights()

        records = [
            make_outcome(f"h{i}", "Liquidity", SignalDirection.BULLISH, 0.8) for i in range(5)
        ]
        summary = make_outcome_summary(records)
        updated = updater.update_from_summary(weights, summary, records)
        liq = [w for w in updated if w.dimension == "liquidity"][0]
        assert liq.streak > 0

    def test_multiple_dimensions(self):
        updater = BeliefUpdater()
        weights = updater.initialize_weights()

        records = []
        for dim, count, accuracy in [("Liquidity", 5, 1.0), ("Growth", 5, 0.4)]:
            for i in range(count):
                correct = i < int(count * accuracy)
                records.append(
                    make_outcome(f"h_{dim}_{i}", dim, SignalDirection.BULLISH, 0.8, correct=correct)
                )

        summary = make_outcome_summary(records)
        updated = updater.update_from_summary(weights, summary, records)
        liq = [w for w in updated if w.dimension == "liquidity"][0]
        assert liq.historical_accuracy == 1.0
        gr = [w for w in updated if w.dimension == "growth"][0]
        assert gr.historical_accuracy == pytest.approx(0.4, abs=0.1)


# ── ConfidenceDecay ─────────────────────────────────────────────────────────


class TestConfidenceDecay:
    def test_no_decay_for_zero_days(self):
        decay = ConfidenceDecay()
        weights = BeliefUpdater().initialize_weights()
        result = decay.apply_decay(weights, days_since_last_update=0)
        for i, w in enumerate(result):
            assert w.current_weight == weights[i].current_weight

    def test_decay_after_weeks(self):
        decay = ConfidenceDecay(base_decay_rate=0.1)
        weights = BeliefUpdater().initialize_weights()
        result = decay.apply_decay(weights, days_since_last_update=14)
        for w in result:
            assert w.current_weight < 0.5

    def test_decay_floor(self):
        decay = ConfidenceDecay(base_decay_rate=0.5)
        weights = BeliefUpdater().initialize_weights()
        # Very long time
        result = decay.apply_decay(weights, days_since_last_update=365)
        for w in result:
            assert w.current_weight >= 0.1  # floor

    def test_recency_weights(self):
        decay = ConfidenceDecay()
        records = [
            make_outcome(f"h{i}", "Liquidity", SignalDirection.BULLISH, 0.8) for i in range(5)
        ]
        rw = decay.get_recency_weights(records)
        assert len(rw) == 5
        # All very recent (today's test) — should all be near 1.0
        for w in rw:
            assert w >= 0.9


# ── PatternMiner ────────────────────────────────────────────────────────────


class TestPatternMiner:
    def test_discovers_best_dimension(self):
        records = []
        for i in range(10):
            records.append(make_outcome(f"liq{i}", "Liquidity", SignalDirection.BULLISH, 0.8))
        for i in range(5):
            records.append(
                make_outcome(f"gr{i}", "Growth", SignalDirection.BULLISH, 0.8, correct=(i < 2))
            )

        summary = make_outcome_summary(records)
        patterns = PatternMiner.discover(records, summary)
        assert any("Liquidity" in p for p in patterns)
        assert any("liquidity" in p.lower() for p in patterns)

    def test_discovers_overconfidence(self):
        records = []
        for i in range(10):
            correct = i < 4  # only 4/10 correct
            records.append(
                make_outcome(f"h{i}", "Liquidity", SignalDirection.BULLISH, 0.85, correct=correct)
            )

        summary = make_outcome_summary(records)
        patterns = PatternMiner.discover(records, summary)
        assert any("overconfident" in p.lower() for p in patterns) or any(
            "unreliable" in p.lower() for p in patterns
        )

    def test_discovers_bullish_accuracy(self):
        records = [
            make_outcome(f"h{i}", "Liquidity", SignalDirection.BULLISH, 0.7) for i in range(8)
        ]
        summary = make_outcome_summary(records)
        patterns = PatternMiner.discover(records, summary)
        assert any("Bullish" in p or "bullish" in p for p in patterns)


# ── LearningEngine ───────────────────────────────────────────────────────────


class TestLearningEngine:
    def test_learn_from_empty(self):
        engine = LearningEngine()
        summary = OutcomeSummary()
        result = engine.learn(summary, [])
        assert isinstance(result, LearningSummary)
        assert result.total_tracked_outcomes == 0

    def test_learn_from_data(self):
        engine = LearningEngine()
        records = [
            make_outcome(f"h{i}", "Liquidity", SignalDirection.BULLISH, 0.8, correct=(i < 8))
            for i in range(10)
        ]
        records += [
            make_outcome(f"g{i}", "Growth", SignalDirection.BEARISH, 0.7, correct=(i < 3))
            for i in range(5)
        ]
        summary = make_outcome_summary(records)
        result = engine.learn(summary, records)

        assert result.total_tracked_outcomes == 15
        assert result.global_hit_rate > 0
        assert len(result.belief_weights) == 5
        assert len(result.learned_patterns) > 0

    def test_get_weight_default(self):
        engine = LearningEngine()
        assert engine.get_weight("liquidity") == 0.5
        assert engine.get_weight("unknown") == 0.5

    def test_get_weight_after_learning(self):
        engine = LearningEngine()
        records = [
            make_outcome(f"h{i}", "Liquidity", SignalDirection.BULLISH, 0.8) for i in range(10)
        ]
        summary = make_outcome_summary(records)
        engine.learn(summary, records)
        assert engine.get_weight("liquidity") > 0.5

    def test_get_accuracy(self):
        engine = LearningEngine()
        assert engine.get_accuracy("liquidity") == 0.5

        records = [
            make_outcome(f"h{i}", "Growth", SignalDirection.BULLISH, 0.8, correct=(i < 8))
            for i in range(10)
        ]
        summary = make_outcome_summary(records)
        engine.learn(summary, records)
        assert engine.get_accuracy("growth") == pytest.approx(0.8, abs=0.05)
