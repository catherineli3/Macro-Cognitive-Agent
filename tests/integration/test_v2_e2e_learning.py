"""v2.0 End-to-End learning closed loop test.

Validates the full v2.0 cognitive loop:
    Signal → Hypothesis → Reflection → Memory →
    Outcome Tracking → Learning → Calibration → Narrative
"""

import tempfile
from pathlib import Path

import pytest
from datetime import datetime, timezone

from src.calibration.confidence_calibrator import ConfidenceCalibrator
from src.learning.learning_engine import LearningEngine
from src.narrative.engine import NarrativeEngine
from src.outcome.engine import OutcomeEngine, OutcomeTracker
from src.schemas.calibration import CalibratedConfidenceSet
from src.schemas.hypothesis import HypothesisEvidence, HypothesisSchema, HypothesisSet
from src.schemas.learning import LearningSummary
from src.schemas.memory import BeliefRecord
from src.schemas.narrative import MacroNarrative
from src.schemas.outcome import (
    OutcomeDirection, OutcomeRecord, OutcomeVerdict, PredictionOutcome,
)
from src.schemas.reflection import ReflectionReport, ReflectionSet, ReflectionVerdict
from src.schemas.signal import SignalDirection, SignalEvidence, SignalSnapshot, MacroSignalSchema, SignalStrength
from src.signal.composite_signal_generator import CompositeSignalGenerator
from src.domain.memory import BeliefStatus, TransitionType


# ── Fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    """Use temp directory to isolate test outcome data."""
    with tempfile.TemporaryDirectory() as tmp:
        tracker = OutcomeTracker(file_path=str(Path(tmp) / "outcomes.json"))
        yield OutcomeEngine(tracker=tracker)


# ── Helpers ─────────────────────────────────────────────────────────────────


def sig(indicator, dim, direction, confidence=0.8):
    return MacroSignalSchema(
        indicator=indicator, dimension=dim,
        direction=SignalDirection(direction),
        strength=SignalStrength.STRONG if confidence > 0.7 else SignalStrength.MODERATE,
        confidence=confidence,
        evidence=[SignalEvidence(
            rule_id=f"r_{indicator}", rule_description=direction,
            input_value=1.0, condition=f"{indicator} {direction}",
            interpretation=f"{indicator}: {direction} signal",
        )],
    )


def hyp(statement, dim, direction, confidence=0.7):
    return HypothesisSchema(
        statement=statement, dimension=dim,
        direction=SignalDirection(direction), confidence=confidence,
        supporting_evidence=[HypothesisEvidence(
            indicator=f"S{i}", signal_id=f"s_{i}",
            observation=f"Support {i}",
            interpretation=f"Evidence: {statement[:30]}",
            contribution=0.7, alignment="supporting",
        ) for i in range(2)],
        contradicting_evidence=[],
    )


def ref(h, verdict="confirmed", updated_conf=0.8):
    return ReflectionReport(
        hypothesis_id=h.hypothesis_id, statement=h.statement,
        original_confidence=h.confidence, updated_confidence=updated_conf,
        verdict=ReflectionVerdict(verdict), findings=[],
        evidence_sufficiency="medium", evidence_consistency="consistent",
        review_summary=f"Review of {h.hypothesis_id}",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Full Closed Loop Test
# ═══════════════════════════════════════════════════════════════════════════════


class TestV2ClosedLoop:
    """Complete S→H→R→M→O→L→C→N loop."""

    def test_full_loop_single_cycle(self, engine):
        """Step-by-step: Signal → Narrative with all v2.0 engines."""
        # Step 1: Signal
        snapshot = SignalSnapshot(signals=[
            sig("DXY", "Liquidity", "bullish", 0.85),
            sig("US10Y", "Liquidity", "bullish", 0.80),
            sig("HYG", "Credit", "bearish", 0.75),
        ])

        # Step 2: Hypothesis
        hypotheses = HypothesisSet(
            hypotheses=[
                hyp("Dollar strengthens as liquidity tightens.", "Liquidity", "bearish", 0.82),
                hyp("Credit markets show stress signals.", "Credit", "bearish", 0.78),
            ],
            dimensions_covered=["Liquidity", "Credit"],
        )

        # Step 3: Reflection
        reflections = ReflectionSet(reports=[
            ref(hypotheses.hypotheses[0], "confirmed", 0.85),
            ref(hypotheses.hypotheses[1], "confirmed", 0.82),
        ])

        # Step 4: Memory
        beliefs = [
            BeliefRecord(
                run_id="cycle_1", hypothesis_id=hypotheses.hypotheses[0].hypothesis_id,
                dimension="Liquidity", statement=hypotheses.hypotheses[0].statement,
                direction=SignalDirection.BEARISH, confidence=0.85,
                status=BeliefStatus.HELD, transition=TransitionType.NEW,
                supporting_count=3, contradicting_count=0,
                evidence_summary="Strong liquidity tightening.",
                review_summary="Confirmed.",
                timestamp=datetime.now(timezone.utc),
            ),
            BeliefRecord(
                run_id="cycle_1", hypothesis_id=hypotheses.hypotheses[1].hypothesis_id,
                dimension="Credit", statement=hypotheses.hypotheses[1].statement,
                direction=SignalDirection.BEARISH, confidence=0.82,
                status=BeliefStatus.HELD, transition=TransitionType.NEW,
                supporting_count=3, contradicting_count=0,
                evidence_summary="Credit stress signals.",
                review_summary="Confirmed.",
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        # Step 5: Outcome Tracking — create pending outcomes
        for b in beliefs:
            outcome = engine.create_outcome(b, "cycle_1")
            engine.persist(outcome, "cycle_1")
        outcomes = engine._tracker.get_all()
        assert len(outcomes) == 2

        # Step 6: Learning — update weights
        learning = LearningEngine()
        learning.learn(
            outcome_summary=engine.summary(),
            outcome_records=outcomes,
        )

        # Step 7: Calibration
        calibrator = ConfidenceCalibrator(learning_engine=learning)
        calibrated = calibrator.calibrate_set(hypotheses, reflections, "cycle_1")

        # Step 8: Composite Signals
        composite_gen = CompositeSignalGenerator()
        composite_snap = composite_gen.generate_snapshot(snapshot)

        # Step 9: Narrative
        narrative_engine = NarrativeEngine()
        narrative = narrative_engine.narrate(
            signals=snapshot,
            hypotheses=hypotheses,
            reflections=reflections,
            belief_records=beliefs,
            learning_summary=learning.learn(
                outcome_summary=engine.summary(),
                outcome_records=outcomes,
            ),
            calibrated_confidence=calibrated,
            outcome_summary=engine.summary(),
        )

        # Assertions
        assert isinstance(narrative, MacroNarrative)
        assert len(narrative.summary) > 0
        assert len(narrative.macro_story) > 0
        assert narrative.confidence_score > 0

        # v2.0 additions
        assert "learning_summary" in narrative.metadata
        assert "calibrated_confidence" in narrative.metadata
        assert len(composite_snap.composite_signals) >= 1
        assert len(composite_snap.macro_themes) > 0

    def test_multi_cycle_learning(self, engine):
        """3 cycles of prediction → evaluation → learning update."""
        learning = LearningEngine()

        dimensions = ["Liquidity", "Credit", "Growth"]

        for cycle in range(1, 4):
            # Generate predictions per cycle
            for dim in dimensions:
                direction = SignalDirection.BULLISH if cycle % 2 == 1 else SignalDirection.BEARISH
                belief = BeliefRecord(
                    run_id=f"cycle_{cycle}", hypothesis_id=f"h_{dim}_{cycle}",
                    dimension=dim, statement=f"Cycle {cycle}: {dim} {direction.value}",
                    direction=direction, confidence=0.7 + cycle * 0.05,
                    status=BeliefStatus.HELD, transition=TransitionType.NEW,
                    supporting_count=3, contradicting_count=0,
                    evidence_summary=f"Cycle {cycle} evidence.",
                    review_summary=f"Cycle {cycle} review.",
                    timestamp=datetime(2026, 7, cycle, tzinfo=timezone.utc),
                )
                outcome = engine.create_outcome(belief, f"cycle_{cycle}")
                engine.persist(outcome, f"cycle_{cycle}")

            # Evaluate prev cycle's predictions
            if cycle > 1:
                prev_outcomes = [
                    r for r in engine._tracker.get_all()
                    if r.run_id == f"cycle_{cycle - 1}"
                ]
                for record in prev_outcomes:
                    # Simulate: Liquidity correct, Growth incorrect, Credit mixed
                    if record.outcome.dimension.lower() == "liquidity":
                        obs_dir = OutcomeDirection.UP if record.outcome.predicted_direction == SignalDirection.BULLISH else OutcomeDirection.DOWN
                        correct = True
                    elif record.outcome.dimension.lower() == "credit":
                        obs_dir = OutcomeDirection.FLAT
                        correct = False  # partial
                    else:
                        obs_dir = OutcomeDirection.DOWN if record.outcome.predicted_direction == SignalDirection.BULLISH else OutcomeDirection.UP
                        correct = False

                    evaluated = engine.evaluate(
                        record.outcome,
                        observed_direction=obs_dir,
                    )
                    record.outcome = evaluated

                # Learn from evaluated data
                summary = engine.summary()
                all_records = engine._tracker.get_all()
                result = learning.learn(summary, all_records)
                assert isinstance(result, LearningSummary)

        # After 3 cycles:
        summary = engine.summary()
        assert summary.total_predictions == 9  # 3 cycles * 3 dims

        # Liquidity should have better accuracy (always correct)
        best = learning.get_accuracy("liquidity")
        worst = learning.get_accuracy("growth")
        assert best > worst

    def test_calibration_updates_over_cycles(self, engine):
        """Confidence calibration adjusts as historical accuracy changes."""
        learning = LearningEngine()

        # Cycle 1: High confidence, no history
        calibrator = ConfidenceCalibrator(learning_engine=learning)
        h = hyp("Liquidity tightening continues.", "Liquidity", "bearish", 0.85)
        cal1 = calibrator.calibrate_hypothesis(h, 0.85)
        assert cal1.calibrated_confidence < 0.85  # No history → discounted

        # Feed 10 perfect outcomes to build trust
        for i in range(10):
            belief = BeliefRecord(
                run_id=f"trust_{i}", hypothesis_id=f"ht_{i}",
                dimension="Liquidity", statement="Historical test",
                direction=SignalDirection.BEARISH, confidence=0.8,
                status=BeliefStatus.HELD, transition=TransitionType.NEW,
                supporting_count=3, contradicting_count=0,
                evidence_summary="Historical.", review_summary="Historical.",
                timestamp=datetime.now(timezone.utc),
            )
            outcome = engine.create_outcome(belief, f"trust_{i}")
            engine.persist(outcome, f"trust_{i}")
            evaluated = engine.evaluate(engine._tracker.get_all()[-1].outcome, observed_direction=OutcomeDirection.DOWN)
            engine._tracker._records[-1].outcome = evaluated

        # Learn from perfect history
        all_records = engine._tracker.get_all()
        summary = engine.summary()
        learning.learn(summary, all_records)

        # Cycle 2: Same hypothesis, better calibrated confidence
        cal2 = calibrator.calibrate_hypothesis(h, 0.85)
        assert cal2.calibrated_confidence > cal1.calibrated_confidence
        # Should be close to raw now (strong track record)
        assert cal2.calibration_delta < cal1.calibration_delta or cal2.calibration_delta <= 0

    def test_narrative_includes_learning_sections(self, engine):
        """Narrative engine generates v2.0 learning sections."""
        # Setup full pipeline
        signals = SignalSnapshot(signals=[
            sig("DXY", "Liquidity", "bullish", 0.85),
            sig("US10Y", "Liquidity", "bullish", 0.80),
        ])
        hyps = HypothesisSet(
            hypotheses=[hyp("Dollar dominance continues.", "Liquidity", "bearish", 0.80)],
            dimensions_covered=["Liquidity"],
        )
        refs = ReflectionSet(reports=[ref(hyps.hypotheses[0], "confirmed", 0.85)])

        # Outcome + Learning
        learning = LearningEngine()
        for i in range(5):
            belief_rec = BeliefRecord(
                run_id=f"narr_{i}", hypothesis_id=f"hn_{i}",
                dimension="Liquidity", statement="Historical liquidity test",
                direction=SignalDirection.BULLISH, confidence=0.75,
                status=BeliefStatus.HELD, transition=TransitionType.NEW,
                supporting_count=2, contradicting_count=1,
                evidence_summary=f"Evidence {i}", review_summary=f"Review {i}",
                timestamp=datetime.now(timezone.utc),
            )
            outcome = engine.create_outcome(belief_rec, f"narr_{i}")
            engine.persist(outcome, f"narr_{i}")
            engine._tracker._records[-1].outcome = engine.evaluate(
                engine._tracker._records[-1].outcome,
                observed_direction=OutcomeDirection.UP,
            )

        all_records = engine._tracker.get_all()
        outcome_s = engine.summary()
        ls = learning.learn(outcome_s, all_records)

        calibrator = ConfidenceCalibrator(learning_engine=learning)
        cal = calibrator.calibrate_set(hyps, refs, "narr_test")

        # Generate narrative
        narrative_engine = NarrativeEngine()
        narrative = narrative_engine.narrate(
            signals=signals, hypotheses=hyps, reflections=refs,
            learning_summary=ls,
            calibrated_confidence=cal,
            outcome_summary=outcome_s,
        )

        # Verify v2.0 sections are in metadata
        assert narrative.metadata.get("learning_summary") is not None
        assert narrative.metadata.get("calibrated_confidence") is not None
        assert narrative.metadata.get("outcome_summary") is not None
        assert narrative.confidence_score > 0
