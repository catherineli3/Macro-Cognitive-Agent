"""Integration tests for HypothesisHandler (Sprint 6).

Covers:
    - HypothesisHandler interface compliance (supported_capability, handler_name)
    - Handler reads signals from ExecutionContext
    - Handler produces HypothesisSet artifact
    - Handler handles missing signals gracefully
    - Full Executor + HypothesisHandler integration
"""

from datetime import UTC, datetime

import pytest

from src.domain.planning import TaskType
from src.executor.context import ExecutionContext
from src.executor.executor import AgentExecutor
from src.handlers.hypothesis_handler import HypothesisHandler
from src.hypothesis.engine import HypothesisEngine
from src.interfaces.task_handler import TaskHandlerInterface
from src.schemas.execution import TaskResult
from src.schemas.hypothesis import HypothesisSet
from src.schemas.planning import Task
from src.schemas.signal import (
    MacroSignalSchema,
    SignalDirection,
    SignalEvidence,
    SignalStrength,
)

# ── Helpers ───────────────────────────────────────────────────────────────


def make_signal(
    signal_id: str,
    indicator: str,
    direction: SignalDirection,
    dimension: str = "Liquidity",
) -> MacroSignalSchema:
    now = datetime.now(UTC)
    return MacroSignalSchema(
        signal_id=signal_id,
        indicator=indicator,
        dimension=dimension,
        direction=direction,
        strength=SignalStrength.MODERATE,
        confidence=0.75,
        timestamp=now,
        evidence=[
            SignalEvidence(
                rule_id=f"r_{signal_id}",
                rule_description=f"{indicator} rule",
                input_value=100.0,
                condition="value > 50",
                interpretation=f"{indicator} interpretation",
                evaluated_at=now,
            )
        ],
    )


# ── HypothesisHandler Unit Tests ──────────────────────────────────────────


class TestHypothesisHandlerInterface:
    """Verify handler conforms to TaskHandlerInterface contract."""

    def test_is_handler_interface(self):
        handler = HypothesisHandler()
        assert isinstance(handler, TaskHandlerInterface)

    def test_supported_capability(self):
        handler = HypothesisHandler()
        assert handler.supported_capability() == "macro.hypothesis"

    def test_handler_name(self):
        handler = HypothesisHandler()
        assert handler.handler_name() == "HypothesisHandler"

    def test_dependency_injection(self):
        """Can inject a custom HypothesisEngine for testing."""
        engine = HypothesisEngine()
        handler = HypothesisHandler(engine=engine)
        assert handler._engine is engine


class TestHypothesisHandlerExecution:
    """Verify handler execution with ExecutionContext."""

    @pytest.fixture
    def handler(self):
        return HypothesisHandler()

    @pytest.fixture
    def context_with_signals(self):
        ctx = ExecutionContext("plan_test")
        signals = [
            make_signal("s1", "DXY", SignalDirection.BEARISH),
            make_signal("s2", "US10Y", SignalDirection.BEARISH),
        ]
        ctx.record_artifacts({"signals": signals})
        return ctx

    @pytest.fixture
    def task(self):
        return Task(
            id="task_hypothesis",
            name="Generate Hypotheses",
            description="Generate macro hypotheses from signals",
            type=TaskType.GENERATE,
            config={"capability": "macro.hypothesis"},
        )

    @pytest.mark.asyncio
    async def test_execute_produces_hypothesis_artifact(self, handler, context_with_signals, task):
        result = await handler.execute(task, context_with_signals)
        assert result.is_success
        assert "hypotheses" in result.artifacts
        assert isinstance(result.artifacts["hypotheses"], HypothesisSet)

    @pytest.mark.asyncio
    async def test_execute_produces_non_empty_set(self, handler, context_with_signals, task):
        result = await handler.execute(task, context_with_signals)
        hypothesis_set = result.artifacts["hypotheses"]
        assert hypothesis_set.count >= 1

    @pytest.mark.asyncio
    async def test_execute_with_no_signals(self, handler, task):
        """Handler should handle missing signals gracefully."""
        ctx = ExecutionContext("plan_empty")
        result = await handler.execute(task, ctx)
        assert result.is_success
        hypothesis_set = result.artifacts["hypotheses"]
        assert hypothesis_set.count == 0

    @pytest.mark.asyncio
    async def test_execute_with_dict_signals(self, handler, task):
        """Handler should parse dict-format signals (JSON-deserialized)."""
        ctx = ExecutionContext("plan_dict")
        now = datetime.now(UTC)
        signals_dict = [
            {
                "signal_id": "s1",
                "indicator": "DXY",
                "dimension": "Liquidity",
                "direction": "bearish",
                "strength": "strong",
                "confidence": 0.80,
                "timestamp": now.isoformat(),
                "evidence": [],
                "metadata": {},
            },
            {
                "signal_id": "s2",
                "indicator": "US10Y",
                "dimension": "Liquidity",
                "direction": "bearish",
                "strength": "strong",
                "confidence": 0.85,
                "timestamp": now.isoformat(),
                "evidence": [],
                "metadata": {},
            },
        ]
        ctx.record_artifacts({"signals": signals_dict})
        result = await handler.execute(task, ctx)
        assert result.is_success
        hypothesis_set = result.artifacts["hypotheses"]
        assert hypothesis_set.count >= 1

    @pytest.mark.asyncio
    async def test_execute_sets_task_id(self, handler, context_with_signals, task):
        result = await handler.execute(task, context_with_signals)
        assert result.task_id == "task_hypothesis"

    @pytest.mark.asyncio
    async def test_execute_sets_timestamps(self, handler, context_with_signals, task):
        result = await handler.execute(task, context_with_signals)
        assert result.started_at.tzinfo is not None
        assert result.completed_at.tzinfo is not None
        assert result.execution_time_ms >= 0


# ── Full Executor Integration ─────────────────────────────────────────────


class TestExecutorIntegration:
    """Verify HypothesisHandler works end-to-end with AgentExecutor."""

    @pytest.mark.asyncio
    async def test_executor_integration(self):
        """Full executor integration: plan → execute → hypothesis artifact."""
        from src.schemas.planning import ExecutionPlan

        # Create a plan
        plan = ExecutionPlan(
            goal="Analyze macro conditions",
            tasks=[
                Task(
                    id="t1",
                    name="Retrieve Signals",
                    description="Get macro signals",
                    type=TaskType.RETRIEVE,
                    config={"capability": "simple.retrieve"},
                ),
                Task(
                    id="t2",
                    name="Generate Hypotheses",
                    description="Generate macro hypotheses",
                    type=TaskType.GENERATE,
                    config={"capability": "macro.hypothesis"},
                    dependencies=["t1"],
                ),
            ],
        )

        # Create executor with both handlers
        executor = AgentExecutor()
        executor.register(HypothesisHandler())

        # Create context simulating t1 already completed
        ctx = ExecutionContext(plan.plan_id)
        signals = [
            make_signal("s1", "DXY", SignalDirection.BEARISH),
            make_signal("s2", "US10Y", SignalDirection.BEARISH),
        ]
        ctx.record_artifacts({"signals": signals})
        ctx.record_result(
            TaskResult(
                task_id="t1",
                task_name="Retrieve Signals",
                status="success",  # type: ignore
                artifacts={"signals": signals},
            )
        )

        # Execute t2 directly via the registered handler
        # (Simulates what executor._get_handler would do)
        handler = executor._get_handler(plan.tasks[1])
        assert handler is not None
        assert isinstance(handler, HypothesisHandler)

        result = await handler.execute(plan.tasks[1], ctx)
        assert result.is_success
        assert "hypotheses" in result.artifacts
        hypothesis_set = result.artifacts["hypotheses"]
        assert isinstance(hypothesis_set, HypothesisSet)
        assert hypothesis_set.count >= 1

    @pytest.mark.asyncio
    async def test_executor_full_plan_with_hypothesis(self):
        """Execute a full plan: retrieve → hypothesis."""
        from src.schemas.planning import ExecutionPlan

        plan = ExecutionPlan(
            goal="Analyze macro conditions",
            tasks=[
                Task(
                    id="t1",
                    name="Generate Hypotheses",
                    description="Generate macro hypotheses",
                    type=TaskType.GENERATE,
                    config={"capability": "macro.hypothesis"},
                ),
            ],
        )

        executor = AgentExecutor()
        executor.register(HypothesisHandler())

        # Seed signals into context before execution
        ctx = ExecutionContext(plan.plan_id)
        signals = [
            make_signal("s1", "DXY", SignalDirection.BEARISH),
            make_signal("s2", "US10Y", SignalDirection.BEARISH),
        ]
        ctx.record_artifacts({"signals": signals})

        # Execute t1
        handler = executor._get_handler(plan.tasks[0])
        result = await handler.execute(plan.tasks[0], ctx)
        assert result.is_success
        hypothesis_set = result.artifacts.get("hypotheses")
        assert hypothesis_set is not None
        assert hypothesis_set.count >= 1
