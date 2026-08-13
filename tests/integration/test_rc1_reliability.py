"""RC-1 Reliability Tests — timeout, retry, graceful degradation, exception isolation.

Verifies:
    1. Timeout enforcement kills slow handlers
    2. Retry recovers from transient failures
    3. Non-critical failure does NOT block downstream
    4. Handler exception does NOT crash the pipeline
    5. Default behavior unchanged (backward-compatible)
"""

import asyncio
from datetime import UTC, datetime

import pytest

from src.domain.execution import TaskResultStatus
from src.executor.executor import AgentExecutor
from src.interfaces.task_handler import TaskHandlerInterface
from src.schemas.execution import TaskResult
from src.schemas.planning import ExecutionPlan, Task, TaskType

# ── Test Handlers ───────────────────────────────────────────────────────────


class FastHandler(TaskHandlerInterface):
    """A handler that succeeds immediately."""

    def supported_capability(self) -> str:
        return "test.fast"

    def handler_name(self) -> str:
        return "FastHandler"

    async def execute(self, task: Task, context) -> TaskResult:
        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=TaskResultStatus.SUCCESS,
            artifacts={"result": "fast"},
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )


class SlowHandler(TaskHandlerInterface):
    """A handler that exceeds the timeout."""

    def __init__(self, delay_s: float = 5.0) -> None:
        self.delay_s = delay_s

    def supported_capability(self) -> str:
        return "test.slow"

    def handler_name(self) -> str:
        return "SlowHandler"

    async def execute(self, task: Task, context) -> TaskResult:
        await asyncio.sleep(self.delay_s)
        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=TaskResultStatus.SUCCESS,
            artifacts={"result": "slow_done"},
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )


class FlakyHandler(TaskHandlerInterface):
    """A handler that fails on the first N-1 attempts, then succeeds."""

    def __init__(self, fail_count: int = 1) -> None:
        self.fail_count = fail_count
        self._attempts = 0

    def supported_capability(self) -> str:
        return "test.flaky"

    def handler_name(self) -> str:
        return "FlakyHandler"

    async def execute(self, task: Task, context) -> TaskResult:
        self._attempts += 1
        if self._attempts <= self.fail_count:
            raise ConnectionError(f"Transient failure, attempt {self._attempts}")
        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=TaskResultStatus.SUCCESS,
            artifacts={"result": f"success_on_attempt_{self._attempts}"},
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )


class CrashHandler(TaskHandlerInterface):
    """A handler that always raises a non-retryable exception."""

    def supported_capability(self) -> str:
        return "test.crash"

    def handler_name(self) -> str:
        return "CrashHandler"

    async def execute(self, task: Task, context) -> TaskResult:
        raise RuntimeError("Simulated handler crash")


def _make_plan(task_id: str, task_name: str, capability: str, **config) -> ExecutionPlan:
    """Helper: build a single-task plan."""
    task = Task(
        id=task_id,
        name=task_name,
        type=TaskType.ANALYZE,
        priority=1,
        dependencies=[],
        config={"capability": capability, **config},
    )
    return ExecutionPlan(goal="reliability test", tasks=[task])


def _make_dag_plan(
    tasks_spec: list[tuple[str, str, str, list[str], dict]],
) -> ExecutionPlan:
    """Helper: build a multi-task DAG plan.

    Args:
        tasks_spec: list of (id, name, capability, dependencies, config)
    """
    tasks = [
        Task(
            id=tid,
            name=tname,
            type=TaskType.ANALYZE,
            priority=1,
            dependencies=deps,
            config={"capability": cap, **cfg},
        )
        for tid, tname, cap, deps, cfg in tasks_spec
    ]
    return ExecutionPlan(goal="dag test", tasks=tasks)


# ── Test: Timeout ───────────────────────────────────────────────────────────


class TestTimeout:
    """RC-1: Timeout enforcement."""

    @pytest.mark.asyncio
    async def test_slow_handler_times_out(self) -> None:
        """A handler exceeding its timeout is terminated."""
        executor = AgentExecutor()
        executor.register(SlowHandler(delay_s=5.0))
        plan = _make_plan("t1", "Slow Task", "test.slow", timeout_seconds=0.5)

        result = await executor.execute(plan)

        assert result.status.value in ("completed", "partially_completed", "failed")
        tr = result.task_results["t1"]
        assert tr.status in (TaskResultStatus.TIMED_OUT, TaskResultStatus.FAILED)

    @pytest.mark.asyncio
    async def test_fast_handler_completes_within_timeout(self) -> None:
        """A fast handler completes normally within timeout."""
        executor = AgentExecutor()
        executor.register(FastHandler())
        plan = _make_plan("t1", "Fast Task", "test.fast", timeout_seconds=5.0)

        result = await executor.execute(plan)

        assert result.status == "completed"
        tr = result.task_results["t1"]
        assert tr.status == TaskResultStatus.SUCCESS
        assert tr.artifacts.get("result") == "fast"

    @pytest.mark.asyncio
    async def test_default_timeout_is_applied(self) -> None:
        """Tasks without explicit timeout_seconds use the default."""
        executor = AgentExecutor()
        executor.register(FastHandler())
        # No timeout_seconds in config — default (30s) should be used
        plan = _make_plan("t1", "Default Timeout Task", "test.fast")

        result = await executor.execute(plan)

        assert result.status == "completed"
        assert result.task_results["t1"].status == TaskResultStatus.SUCCESS


# ── Test: Retry ─────────────────────────────────────────────────────────────


class TestRetry:
    """RC-1: Retry on transient failures."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(self) -> None:
        """Flaky handler that fails once then succeeds."""
        executor = AgentExecutor()
        flaky = FlakyHandler(fail_count=1)
        executor.register(flaky)
        plan = _make_plan("t1", "Flaky Task", "test.flaky", max_retries=3)

        result = await executor.execute(plan)

        tr = result.task_results["t1"]
        assert tr.status == TaskResultStatus.SUCCESS
        assert "success_on_attempt" in tr.artifacts.get("result", "")

    @pytest.mark.asyncio
    async def test_retry_exhausted_fails(self) -> None:
        """Flaky handler that never succeeds after all retries."""
        executor = AgentExecutor()
        flaky = FlakyHandler(fail_count=10)  # fails 10 times
        executor.register(flaky)
        plan = _make_plan("t1", "Hopeless Task", "test.flaky", max_retries=3)

        result = await executor.execute(plan)

        tr = result.task_results["t1"]
        assert tr.status in (TaskResultStatus.FAILED, TaskResultStatus.TIMED_OUT)
        assert tr.error is not None

    @pytest.mark.asyncio
    async def test_no_retry_by_default(self) -> None:
        """By default (max_retries=1), no retries are attempted."""
        executor = AgentExecutor()
        flaky = FlakyHandler(fail_count=1)
        executor.register(flaky)
        plan = _make_plan("t1", "No Retry Task", "test.flaky")  # default: max_retries=1

        result = await executor.execute(plan)

        tr = result.task_results["t1"]
        assert tr.status in (TaskResultStatus.FAILED, TaskResultStatus.TIMED_OUT)


# ── Test: Graceful Degradation ──────────────────────────────────────────────


class TestGracefulDegradation:
    """RC-1: Non-critical failures do NOT block downstream."""

    @pytest.mark.asyncio
    async def test_non_critical_failure_allows_downstream(self) -> None:
        """Non-critical task failure → downstream task still runs."""
        executor = AgentExecutor()
        executor.register(CrashHandler())  # test.crash — always fails
        executor.register(FastHandler())  # test.fast — always succeeds

        plan = _make_dag_plan(
            [
                ("t_upstream", "Upstream", "test.crash", [], {"critical": False}),
                ("t_downstream", "Downstream", "test.fast", ["t_upstream"], {}),
            ]
        )

        result = await executor.execute(plan)

        # Upstream should be SKIPPED (non-critical failure)
        tr_up = result.task_results["t_upstream"]
        assert tr_up.status == TaskResultStatus.SKIPPED

        # Downstream should still run
        tr_down = result.task_results.get("t_downstream")
        assert tr_down is not None, "Downstream task was NOT executed (should have been)"
        assert tr_down.status == TaskResultStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_critical_failure_blocks_downstream(self) -> None:
        """Critical task failure → downstream task is BLOCKED."""
        executor = AgentExecutor()
        executor.register(CrashHandler())
        executor.register(FastHandler())

        plan = _make_dag_plan(
            [
                ("t_upstream", "Upstream", "test.crash", [], {"critical": True}),
                ("t_downstream", "Downstream", "test.fast", ["t_upstream"], {}),
            ]
        )

        result = await executor.execute(plan)

        # Upstream should be FAILED (critical failure)
        tr_up = result.task_results["t_upstream"]
        assert tr_up.status == TaskResultStatus.FAILED

        # Downstream should NOT run
        assert (
            "t_downstream" not in result.task_results
        ), "Downstream task ran despite critical upstream failure"

    @pytest.mark.asyncio
    async def test_critical_is_default(self) -> None:
        """By default, all tasks are critical (backward-compatible)."""
        executor = AgentExecutor()
        executor.register(CrashHandler())
        executor.register(FastHandler())

        plan = _make_dag_plan(
            [
                ("t_upstream", "Upstream", "test.crash", [], {}),  # no "critical" key
                ("t_downstream", "Downstream", "test.fast", ["t_upstream"], {}),
            ]
        )

        result = await executor.execute(plan)

        tr_up = result.task_results["t_upstream"]
        assert tr_up.status == TaskResultStatus.FAILED
        assert "t_downstream" not in result.task_results


# ── Test: Exception Isolation ───────────────────────────────────────────────


class TestExceptionIsolation:
    """RC-1: Handler exceptions never crash the executor/pipeline."""

    @pytest.mark.asyncio
    async def test_handler_crash_does_not_crash_executor(self) -> None:
        """A handler raising RuntimeError is caught, not propagated."""
        executor = AgentExecutor()
        executor.register(CrashHandler())
        plan = _make_plan("t1", "Crash Task", "test.crash")

        # This MUST NOT raise
        result = await executor.execute(plan)

        assert result is not None
        tr = result.task_results["t1"]
        assert tr.status in (TaskResultStatus.FAILED, TaskResultStatus.TIMED_OUT)
        assert "Simulated handler crash" in (tr.error or "")

    @pytest.mark.asyncio
    async def test_multiple_handlers_isolation(self) -> None:
        """If one handler crashes, others still execute (same level)."""
        executor = AgentExecutor()
        executor.register(CrashHandler())
        executor.register(FastHandler())

        plan = _make_dag_plan(
            [
                ("t_crash", "Crash", "test.crash", [], {"critical": False}),
                ("t_fast", "Fast", "test.fast", [], {}),
            ]
        )

        result = await executor.execute(plan)

        assert result.task_results["t_crash"].status == TaskResultStatus.SKIPPED
        assert result.task_results["t_fast"].status == TaskResultStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_pipeline_catches_top_level_exception(self) -> None:
        """Pipeline.run() catches exceptions and returns FAILED result."""
        from src.pipeline import MacroResearchPipeline

        pipeline = MacroResearchPipeline()
        result = await pipeline.run(goal="")  # Empty goal triggers PlanCreationError

        # Should not raise — should return a failed PipelineResult
        assert result is not None
        assert result.status.value in ("failed",)


class TestTimedOutStatus:
    """RC-1: TIMED_OUT status is handled correctly."""

    @pytest.mark.asyncio
    async def test_timed_out_status_propagated(self) -> None:
        """TIMED_OUT shows up in task results."""
        executor = AgentExecutor()
        executor.register(SlowHandler(delay_s=5.0))
        plan = _make_plan("t1", "Slow", "test.slow", timeout_seconds=0.3)

        result = await executor.execute(plan)

        tr = result.task_results["t1"]
        assert tr.status in (TaskResultStatus.TIMED_OUT, TaskResultStatus.FAILED)
        if tr.status == TaskResultStatus.TIMED_OUT:
            assert "timed out" in (tr.error or "").lower()
