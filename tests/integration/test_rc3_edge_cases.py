"""RC-3 Edge Case Tests — boundary conditions, invalid inputs, recovery scenarios.

Covers:
    - Empty inputs (empty signals, empty hypotheses, empty reflections)
    - Boundary values (confidence=0, confidence=1, -1 signals)
    - Invalid inputs (malformed JSON, wrong types, None artifacts)
    - Recovery scenarios (corrupted memory file, partial context)
    - Duplicate data (duplicate signals, duplicate task IDs)
    - Large datasets (100+ records)
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, PropertyMock

import pytest

from src.domain.execution import TaskResultStatus
from src.executor.context import ExecutionContext
from src.executor.executor import AgentExecutor
from src.memory.store import BeliefMemoryStore
from src.narrative.engine import NarrativeEngine
from src.schemas.hypothesis import HypothesisEvidence, HypothesisSchema, HypothesisSet
from src.schemas.memory import BeliefRecord
from src.schemas.narrative import MacroNarrative
from src.schemas.reflection import ReflectionReport, ReflectionSet
from src.schemas.signal import MacroSignalSchema, SignalDirection, SignalEvidence, SignalSnapshot


# ── Helpers ─────────────────────────────────────────────────────────────────


def make_signal(indicator: str, direction: str, dimension: str, confidence: float = 0.7):
    from src.schemas.signal import SignalStrength
    return MacroSignalSchema(
        indicator=indicator,
        dimension=dimension,
        direction=SignalDirection(direction),
        strength=SignalStrength("strong") if confidence > 0.7 else SignalStrength("moderate"),
        confidence=confidence,
        evidence=[SignalEvidence(
            rule_id=f"rule_{indicator.lower()}",
            rule_description="Test rule",
            input_value=1.0,
            condition="Test condition",
            interpretation="Test interpretation",
        )],
    )


def make_hypothesis(statement: str, dimension: str, direction: str = "neutral", confidence: float = 0.6):
    return HypothesisSchema(
        statement=statement,
        dimension=dimension,
        direction=SignalDirection(direction),
        confidence=confidence,
        supporting_evidence=[],
        contradicting_evidence=[],
    )


def make_reflection(hyp: HypothesisSchema, verdict: str = "confirmed", confidence: float = 0.7):
    return ReflectionReport(
        hypothesis_id=hyp.hypothesis_id,
        statement=hyp.statement,
        original_confidence=hyp.confidence,
        updated_confidence=confidence,
        verdict=verdict,
        findings=[],
        evidence_sufficiency="medium",
        evidence_consistency="consistent",
        review_summary=f"Review: {hyp.statement[:60]}",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Empty Input
# ═══════════════════════════════════════════════════════════════════════════════


class TestEmptyInput:
    """Empty inputs to all cognitive modules."""

    def test_empty_signals_produces_valid_narrative(self):
        """Empty SignalSnapshot → valid MacroNarrative (no crash)."""
        engine = NarrativeEngine()
        n = engine.narrate(
            signals=SignalSnapshot(signals=[]),
            hypotheses=HypothesisSet(hypotheses=[]),
            reflections=ReflectionSet(reports=[]),
        )
        assert isinstance(n, MacroNarrative)
        assert isinstance(n.summary, str)
        assert len(n.summary) > 0

    def test_empty_hypothesis_produces_valid_narrative(self):
        """Signals present but no hypotheses → valid narrative."""
        engine = NarrativeEngine()
        n = engine.narrate(
            signals=SignalSnapshot(signals=[
                make_signal("DXY", "bullish", "Liquidity", 0.8),
            ]),
            hypotheses=HypothesisSet(hypotheses=[]),
            reflections=ReflectionSet(reports=[]),
        )
        assert isinstance(n, MacroNarrative)

    def test_null_reflection_produces_valid_narrative(self):
        """No reflections → valid narrative (defensive)."""
        engine = NarrativeEngine()
        hyp = make_hypothesis("Test.", "Liquidity", "bearish", 0.7)
        n = engine.narrate(
            signals=SignalSnapshot(signals=[
                make_signal("DXY", "bullish", "Liquidity", 0.8),
            ]),
            hypotheses=HypothesisSet(hypotheses=[hyp], dimensions_covered=["Liquidity"]),
            reflections=ReflectionSet(reports=[]),
        )
        assert isinstance(n, MacroNarrative)

    def test_empty_string_goal_pipeline(self):
        """Empty goal string is caught gracefully."""
        from src.planning.planner import RuleBasedPlanner
        import asyncio
        from src.shared.exceptions import PlanCreationError

        planner = RuleBasedPlanner()
        with pytest.raises(PlanCreationError, match="empty"):
            asyncio.run(planner.create_plan(""))


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary Values
# ═══════════════════════════════════════════════════════════════════════════════


class TestBoundaryValues:
    """Boundary value tests for confidence, probability, counts."""

    def test_confidence_zero(self):
        """Confidence = 0 should not crash."""
        engine = NarrativeEngine()
        hyp = make_hypothesis("Zero confidence.", "Liquidity", "bearish", 0.0)
        n = engine.narrate(
            signals=SignalSnapshot(signals=[
                make_signal("DXY", "neutral", "Liquidity", 0.0),
            ]),
            hypotheses=HypothesisSet(hypotheses=[hyp], dimensions_covered=["Liquidity"]),
            reflections=ReflectionSet(reports=[
                make_reflection(hyp, "uncertain", 0.0),
            ]),
        )
        assert 0.0 <= n.confidence_score <= 1.0

    def test_confidence_one(self):
        """Confidence = 1.0 should not crash."""
        engine = NarrativeEngine()
        hyp = make_hypothesis("Max confidence.", "Growth", "bullish", 1.0)
        n = engine.narrate(
            signals=SignalSnapshot(signals=[
                make_signal("PMI", "bullish", "Growth", 1.0),
            ]),
            hypotheses=HypothesisSet(hypotheses=[hyp], dimensions_covered=["Growth"]),
            reflections=ReflectionSet(reports=[
                make_reflection(hyp, "confirmed", 1.0),
            ]),
        )
        assert n.confidence_score <= 1.0

    def test_many_signals(self):
        """100 signals should not cause memory or perf issues."""
        engine = NarrativeEngine()
        signals = SignalSnapshot(signals=[
            make_signal(f"IND{i}", "bullish", "Liquidity", 0.7)
            for i in range(100)
        ])
        n = engine.narrate(
            signals=signals,
            hypotheses=HypothesisSet(hypotheses=[
                make_hypothesis("Many signals.", "Liquidity", "bullish", 0.7),
            ], dimensions_covered=["Liquidity"]),
            reflections=ReflectionSet(reports=[]),
        )
        assert isinstance(n, MacroNarrative)


# ═══════════════════════════════════════════════════════════════════════════════
# Invalid Input / Recovery
# ═══════════════════════════════════════════════════════════════════════════════


class TestInvalidInputRecovery:
    """Invalid or corrupt inputs are handled gracefully."""

    def test_corrupted_memory_file_recovery(self):
        """Corrupted JSON in memory file → empty store (no crash)."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "corrupt.json")
            # Write garbage
            with open(path, "w") as f:
                f.write("{this is not valid json[[[}}}")

            store = BeliefMemoryStore(file_path=path)
            # Should not crash on load
            assert store.belief_count == 0

    def test_empty_memory_file(self):
        """Empty file → empty store (no crash)."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "empty.json")
            with open(path, "w") as f:
                f.write("{}")

            store = BeliefMemoryStore(file_path=path)
            assert store.belief_count == 0

    def test_null_artifacts_in_context(self):
        """Execution context with None artifacts."""
        ctx = ExecutionContext(plan_id="test")
        assert ctx.get_artifact("nonexistent") is None
        assert ctx.get_artifact("nonexistent", "default") == "default"

    def test_unknown_capability_is_handled(self):
        """Plan with unknown capability is caught at validation time."""
        from src.schemas.planning import Task, ExecutionPlan, TaskType

        task = Task(
            id="t1", name="Unknown", type=TaskType.ANALYZE,
            config={"capability": "nonexistent.capability"},
        )
        plan = ExecutionPlan(goal="test", tasks=[task])

        from src.shared.exceptions import ExecutionError
        executor = AgentExecutor()
        with pytest.raises(ExecutionError, match="no handler"):
            import asyncio
            asyncio.run(executor.execute(plan))

    def test_duplicate_task_ids_in_plan(self):
        """Duplicate task IDs should be caught by validation."""
        from src.schemas.planning import Task, ExecutionPlan, TaskType
        from src.planning.validator import PlanValidator

        t1 = Task(id="dup_id", name="Task A", type=TaskType.ANALYZE, config={"capability": "test"})
        t2 = Task(id="dup_id", name="Task B", type=TaskType.ANALYZE, config={"capability": "test"})
        plan = ExecutionPlan(goal="test", tasks=[t1, t2])

        from src.shared.exceptions import PlanValidationError
        with pytest.raises(PlanValidationError, match="Duplicate"):
            PlanValidator.validate(plan)


# ═══════════════════════════════════════════════════════════════════════════════
# Duplicate Signals / Circular Dependency
# ═══════════════════════════════════════════════════════════════════════════════


class TestDuplicateData:
    """Duplicate data handling."""

    def test_duplicate_signals(self):
        """Duplicate signals (same indicator) → handled correctly."""
        engine = NarrativeEngine()
        signals = SignalSnapshot(signals=[
            make_signal("DXY", "bullish", "Liquidity", 0.8),
            make_signal("DXY", "bearish", "Liquidity", 0.3),  # duplicate indicator
        ])
        n = engine.narrate(
            signals=signals,
            hypotheses=HypothesisSet(hypotheses=[
                make_hypothesis("Dupe test.", "Liquidity", "neutral", 0.5),
            ], dimensions_covered=["Liquidity"]),
            reflections=ReflectionSet(reports=[]),
        )
        assert isinstance(n, MacroNarrative)


class TestCircularDependency:
    """Circular dependency detection."""

    def test_circular_dependency_detected(self):
        """Task depending on itself → validation fails."""
        from src.schemas.planning import Task, ExecutionPlan, TaskType
        from src.planning.validator import PlanValidator

        t1 = Task(
            id="t_circular", name="Self-dep",
            type=TaskType.ANALYZE,
            dependencies=["t_circular"],
            config={"capability": "test"},
        )
        plan = ExecutionPlan(goal="test", tasks=[t1])

        from src.shared.exceptions import PlanValidationError
        with pytest.raises(PlanValidationError):
            PlanValidator.validate(plan)


# ═══════════════════════════════════════════════════════════════════════════════
# Memory Recovery
# ═══════════════════════════════════════════════════════════════════════════════


class TestMemoryRecovery:
    """Memory store recovery from edge states."""

    def test_memory_with_growing_file(self):
        """Store handles growing record counts correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "beliefs.json")
            store = BeliefMemoryStore(file_path=path)

            # Add 50 records
            records = []
            for i in range(50):
                hyp = make_hypothesis(f"Record {i}", "Liquidity", "bearish", 0.7)
                rec = BeliefRecord(
                    run_id=f"run_{i}",
                    hypothesis_id=hyp.hypothesis_id,
                    dimension="Liquidity",
                    statement=f"Record {i}",
                    direction=SignalDirection("bearish"),
                    confidence=0.7,
                )
                records.append(rec)

            store.record_batch(records)
            assert store.belief_count == 50

    def test_last_belief_nonexistent_dimension(self):
        """Querying a dimension with no records returns None."""
        store = BeliefMemoryStore(file_path=":test_nonexistent:")
        store._loaded = True
        store._records = []
        assert store.last_belief("NonexistentDim") is None

    def test_has_reversal_single_record(self):
        """Single record → no reversal."""
        store = BeliefMemoryStore(file_path=":test_single_rev:")
        hyp = make_hypothesis("Single", "Liquidity", "bearish", 0.7)
        rec = BeliefRecord(
            run_id="run1", hypothesis_id=hyp.hypothesis_id,
            dimension="Liquidity", statement="Single",
            direction=SignalDirection("bearish"), confidence=0.7,
        )
        store._loaded = True
        store._records = [rec]
        assert not store.has_reversal("Liquidity")
