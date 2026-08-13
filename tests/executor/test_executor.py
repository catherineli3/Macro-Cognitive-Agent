"""Tests for ExecutionContext and AgentExecutor."""

import pytest

from src.domain.execution import ExecutionStatus, TaskResultStatus
from src.domain.planning import TaskType
from src.executor.context import ExecutionContext
from src.executor.executor import AgentExecutor
from src.handlers import (
    SimpleAnalyzeHandler,
    SimpleGenerateHandler,
    SimpleProcessHandler,
    SimpleRetrieveHandler,
    SimpleValidateHandler,
)
from src.schemas.execution import TaskResult
from src.schemas.planning import ExecutionPlan, Task
from src.shared.exceptions import ExecutionError

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_task(
    task_id: str,
    name: str = "",
    task_type: TaskType = TaskType.RETRIEVE,
    deps: list | None = None,
    capability: str = "simple.retrieve",
) -> Task:
    return Task(
        id=task_id,
        name=name or task_id,
        description=f"Task {task_id}",
        type=task_type,
        dependencies=deps or [],
        config={"capability": capability},
    )


def _make_plan(*tasks: Task, goal: str = "test") -> ExecutionPlan:
    return ExecutionPlan(goal=goal, tasks=list(tasks))


def _make_result(task_id: str, success: bool = True) -> TaskResult:
    return TaskResult(
        task_id=task_id,
        task_name=task_id,
        status=TaskResultStatus.SUCCESS if success else TaskResultStatus.FAILED,
        error=None if success else "failed",
    )


# ── ExecutionContext Tests ──────────────────────────────────────────────────


class TestExecutionContext:
    """ExecutionContext lifecycle and artifact management."""

    def test_initial_state_empty(self):
        ctx = ExecutionContext(plan_id="p1")
        assert ctx._plan_id == "p1"
        assert ctx.artifacts == {}
        assert ctx.get_artifact("any") is None
        assert ctx.is_completed("any") is False

    def test_record_and_retrieve_result(self):
        ctx = ExecutionContext(plan_id="p1")
        tr = _make_result("t1")
        ctx.record_result(tr)
        assert ctx.is_completed("t1") is True
        assert ctx.is_successful("t1") is True
        assert ctx.get_result("t1") == tr

    def test_failed_task_not_successful(self):
        ctx = ExecutionContext(plan_id="p1")
        tr = _make_result("t1", success=False)
        ctx.record_result(tr)
        assert ctx.is_completed("t1") is True
        assert ctx.is_successful("t1") is False

    def test_record_artifacts_merge(self):
        ctx = ExecutionContext(plan_id="p1")
        ctx.record_artifacts({"raw_data": {"x": 1}})
        ctx.record_artifacts({"signals": [1, 2, 3]})
        assert ctx.get_artifact("raw_data") == {"x": 1}
        assert ctx.get_artifact("signals") == [1, 2, 3]

    def test_artifacts_readonly_copy(self):
        ctx = ExecutionContext(plan_id="p1")
        ctx.record_artifacts({"key": "value"})
        snap = ctx.artifacts
        snap["new"] = "should not persist"
        assert ctx.get_artifact("new") is None

    def test_all_deps_satisfied_empty(self):
        ctx = ExecutionContext(plan_id="p1")
        task = _make_task("t1", deps=[])
        assert ctx.all_deps_satisfied(task) is True

    def test_all_deps_satisfied_success(self):
        ctx = ExecutionContext(plan_id="p1")
        ctx.record_result(_make_result("dep1"))
        ctx.record_result(_make_result("dep2"))
        task = _make_task("t1", deps=["dep1", "dep2"])
        assert ctx.all_deps_satisfied(task) is True

    def test_deps_not_satisfied_when_failed(self):
        ctx = ExecutionContext(plan_id="p1")
        ctx.record_result(_make_result("dep1", success=False))
        task = _make_task("t1", deps=["dep1"])
        assert ctx.all_deps_satisfied(task) is False

    def test_deps_not_satisfied_when_missing(self):
        ctx = ExecutionContext(plan_id="p1")
        task = _make_task("t1", deps=["missing_dep"])
        assert ctx.all_deps_satisfied(task) is False

    def test_to_execution_result_empty_plan(self):
        ctx = ExecutionContext(plan_id="p1")
        plan = _make_plan()
        result = ctx.to_execution_result(plan)
        assert result.plan_id == plan.plan_id
        assert result.status == ExecutionStatus.COMPLETED  # 0/0 tasks = complete
        assert result.success_count == 0

    def test_to_execution_result_all_success(self):
        ctx = ExecutionContext(plan_id="p1")
        task = _make_task("t1")
        plan = _make_plan(task)
        ctx.record_result(_make_result("t1", success=True))
        ctx.record_artifacts({"out": "ok"})
        result = ctx.to_execution_result(plan)
        assert result.status == ExecutionStatus.COMPLETED
        assert result.success_count == 1
        assert result.failure_count == 0
        assert result.artifacts == {"out": "ok"}
        assert result.execution_order == ["t1"]

    def test_to_execution_result_partial(self):
        ctx = ExecutionContext(plan_id="p1")
        t1 = _make_task("t1")
        t2 = _make_task("t2", deps=["t1"])
        plan = _make_plan(t1, t2)
        ctx.record_result(_make_result("t1", success=True))
        ctx.record_result(_make_result("t2", success=False))
        ctx.record_artifacts({"data": [1]})
        result = ctx.to_execution_result(plan)
        assert result.status == ExecutionStatus.PARTIALLY_COMPLETED
        assert result.success_count == 1
        assert result.failure_count == 1


# ── AgentExecutor Tests ─────────────────────────────────────────────────────


class TestAgentExecutor:
    """AgentExecutor: registration, validation, execution loop."""

    def test_register_and_capabilities(self):
        executor = AgentExecutor()
        executor.register(SimpleRetrieveHandler())
        assert executor.registered_capabilities == {"simple.retrieve"}

    def test_fluent_registration(self):
        executor = (
            AgentExecutor()
            .register(SimpleRetrieveHandler())
            .register(SimpleProcessHandler())
            .register(SimpleAnalyzeHandler())
            .register(SimpleGenerateHandler())
            .register(SimpleValidateHandler())
        )
        assert len(executor.registered_capabilities) == 5

    def test_duplicate_handler_raises(self):
        executor = AgentExecutor()
        executor.register(SimpleRetrieveHandler())
        with pytest.raises(ExecutionError, match="already registered"):
            executor.register(SimpleRetrieveHandler())

    @pytest.mark.asyncio
    async def test_execute_empty_plan(self):
        executor = AgentExecutor()
        plan = _make_plan()
        from src.shared.exceptions import PlanValidationError

        with pytest.raises(PlanValidationError):
            await executor.execute(plan)

    @pytest.mark.asyncio
    async def test_execute_single_task(self):
        executor = AgentExecutor()
        executor.register(SimpleRetrieveHandler())
        task = _make_task("t1", "Retrieve", capability="simple.retrieve")
        plan = _make_plan(task)
        result = await executor.execute(plan)
        assert result.status == ExecutionStatus.COMPLETED
        assert result.success_count == 1
        assert "raw_data" in result.artifacts

    @pytest.mark.asyncio
    async def test_execute_full_pipeline(self):
        executor = (
            AgentExecutor()
            .register(SimpleRetrieveHandler())
            .register(SimpleProcessHandler())
            .register(SimpleAnalyzeHandler())
            .register(SimpleGenerateHandler())
        )
        t1 = _make_task("retrieve", "Get Data", TaskType.RETRIEVE, capability="simple.retrieve")
        t2 = _make_task(
            "process",
            "Clean Data",
            TaskType.PROCESS,
            deps=["retrieve"],
            capability="simple.process",
        )
        t3 = _make_task(
            "analyze", "Analyze", TaskType.ANALYZE, deps=["process"], capability="simple.analyze"
        )
        t4 = _make_task(
            "generate",
            "Generate",
            TaskType.GENERATE,
            deps=["analyze"],
            capability="simple.generate",
        )
        plan = _make_plan(t1, t2, t3, t4)

        result = await executor.execute(plan)
        assert result.status == ExecutionStatus.COMPLETED
        assert result.success_count == 4
        assert "raw_data" in result.artifacts
        assert "processed_data" in result.artifacts
        assert "analysis" in result.artifacts
        assert "output" in result.artifacts

    @pytest.mark.asyncio
    async def test_execution_order_respects_deps(self):
        executor = (
            AgentExecutor().register(SimpleRetrieveHandler()).register(SimpleProcessHandler())
        )
        t1 = _make_task("t1", capability="simple.retrieve")
        t2 = _make_task("t2", deps=["t1"], capability="simple.process")
        t3 = _make_task("t3", capability="simple.retrieve")
        plan = _make_plan(t1, t2, t3)

        result = await executor.execute(plan)
        order = result.execution_order
        assert order.index("t1") < order.index("t2")
        assert order.index("t3") < order.index("t2")

    @pytest.mark.asyncio
    async def test_failed_task_blocks_downstream(self):
        """Strict mode: t1 fails, t2 (depends on t1) never executes. Status=FAILED."""
        executor = AgentExecutor()

        class FailingHandler(SimpleRetrieveHandler):
            def supported_capability(self) -> str:
                return "simple.failing"

            async def execute(self, task, context):
                return TaskResult(
                    task_id=task.id,
                    status=TaskResultStatus.FAILED,
                    error="Simulated failure",
                )

        executor.register(FailingHandler())
        executor.register(SimpleProcessHandler())

        t1 = _make_task("t1", capability="simple.failing")
        t2 = _make_task("t2", deps=["t1"], capability="simple.process")
        plan = _make_plan(t1, t2)

        result = await executor.execute(plan)
        assert result.status == ExecutionStatus.FAILED
        assert result.success_count == 0
        assert result.failure_count == 1
        assert "t2" not in result.task_results  # blocked, never executed

    @pytest.mark.asyncio
    async def test_no_handler_raises(self):
        executor = AgentExecutor()
        task = _make_task("t1", capability="nonexistent.cap")
        plan = _make_plan(task)
        with pytest.raises(ExecutionError, match="no handler registered"):
            await executor.execute(plan)

    @pytest.mark.asyncio
    async def test_handler_exception_converted_to_failure(self):
        """Handler crashes -> Executor catches -> FAILED TaskResult."""
        crash_handler_returned_task = False

        class CrashingHandler(SimpleRetrieveHandler):
            def supported_capability(self) -> str:
                return "simple.crash"

            async def execute(self, task, context):
                nonlocal crash_handler_returned_task
                crash_handler_returned_task = True
                raise RuntimeError("Boom!")

        executor = AgentExecutor()
        executor.register(CrashingHandler())

        t1 = _make_task("t1", capability="simple.crash")
        plan = _make_plan(t1)
        result = await executor.execute(plan)
        assert result.status == ExecutionStatus.FAILED
        assert result.failure_count == 1
        assert crash_handler_returned_task is True
