"""Tests for Simple Task Handlers: capability routing, artifact production."""

import pytest

from src.domain.execution import TaskResultStatus
from src.domain.planning import TaskType
from src.executor.context import ExecutionContext
from src.handlers import (
    SimpleAnalyzeHandler,
    SimpleGenerateHandler,
    SimpleProcessHandler,
    SimpleRetrieveHandler,
    SimpleValidateHandler,
)
from src.interfaces.task_handler import TaskHandlerInterface
from src.schemas.planning import Task


def _make_task(task_id: str, name: str = "", capability: str = "simple.retrieve") -> Task:
    return Task(
        id=task_id,
        name=name or task_id,
        description="Test task",
        type=TaskType.RETRIEVE,
        config={"capability": capability},
    )


class TestSimpleRetrieveHandler:

    def test_capability(self):
        h = SimpleRetrieveHandler()
        assert h.supported_capability() == "simple.retrieve"
        assert h.handler_name() == "SimpleRetrieveHandler"

    def test_implements_interface(self):
        h = SimpleRetrieveHandler()
        assert isinstance(h, TaskHandlerInterface)

    @pytest.mark.asyncio
    async def test_produces_raw_data_artifact(self):
        h = SimpleRetrieveHandler()
        ctx = ExecutionContext(plan_id="p1")
        task = _make_task("t1", "Fetch Data")
        result = await h.execute(task, ctx)
        assert result.status == TaskResultStatus.SUCCESS
        assert result.is_success
        assert "raw_data" in result.artifacts
        assert result.artifacts["raw_data"]["source"] == "mock"
        assert len(result.artifacts["raw_data"]["records"]) == 2

    @pytest.mark.asyncio
    async def test_result_has_timing(self):
        h = SimpleRetrieveHandler()
        ctx = ExecutionContext(plan_id="p1")
        task = _make_task("t1")
        result = await h.execute(task, ctx)
        assert result.started_at <= result.completed_at


class TestSimpleProcessHandler:

    def test_capability(self):
        h = SimpleProcessHandler()
        assert h.supported_capability() == "simple.process"

    @pytest.mark.asyncio
    async def test_reads_upstream_context(self):
        h = SimpleProcessHandler()
        ctx = ExecutionContext(plan_id="p1")
        # Simulate upstream: retrieve handler produced raw_data
        ctx.record_artifacts({"raw_data": {"records": [1, 2, 3, 4, 5]}})
        task = _make_task("t2", capability="simple.process")
        result = await h.execute(task, ctx)
        assert result.status == TaskResultStatus.SUCCESS
        assert "processed_data" in result.artifacts
        assert result.artifacts["processed_data"]["input_records_count"] == 5

    @pytest.mark.asyncio
    async def test_handles_missing_upstream_artifact(self):
        h = SimpleProcessHandler()
        ctx = ExecutionContext(plan_id="p1")
        # No raw_data in context
        task = _make_task("t2", capability="simple.process")
        result = await h.execute(task, ctx)
        assert result.status == TaskResultStatus.SUCCESS
        assert result.artifacts["processed_data"]["input_records_count"] == 0


class TestSimpleAnalyzeHandler:

    def test_capability(self):
        h = SimpleAnalyzeHandler()
        assert h.supported_capability() == "simple.analyze"

    @pytest.mark.asyncio
    async def test_reads_multiple_upstream_artifacts(self):
        h = SimpleAnalyzeHandler()
        ctx = ExecutionContext(plan_id="p1")
        ctx.record_artifacts({"raw_data": {"records": [1, 2]}})
        ctx.record_artifacts({"processed_data": {"output": {"quality": 0.99}}})
        task = _make_task("t3", capability="simple.analyze")
        result = await h.execute(task, ctx)
        assert result.status == TaskResultStatus.SUCCESS
        assert "analysis" in result.artifacts
        assert len(result.artifacts["analysis"]["findings"]) == 2
        assert result.artifacts["analysis"]["confidence"] == 0.75

    @pytest.mark.asyncio
    async def test_handles_missing_upstream(self):
        h = SimpleAnalyzeHandler()
        ctx = ExecutionContext(plan_id="p1")
        task = _make_task("t3", capability="simple.analyze")
        result = await h.execute(task, ctx)
        assert result.status == TaskResultStatus.SUCCESS


class TestSimpleGenerateHandler:

    def test_capability(self):
        h = SimpleGenerateHandler()
        assert h.supported_capability() == "simple.generate"

    @pytest.mark.asyncio
    async def test_builds_on_analysis(self):
        h = SimpleGenerateHandler()
        ctx = ExecutionContext(plan_id="p1")
        ctx.record_artifacts({"analysis": {"findings": ["Finding A"], "confidence": 0.8}})
        task = _make_task("t4", capability="simple.generate")
        result = await h.execute(task, ctx)
        assert result.status == TaskResultStatus.SUCCESS
        assert "output" in result.artifacts
        assert result.artifacts["output"]["confidence"] == 0.8
        assert result.artifacts["output"]["based_on_findings"] == ["Finding A"]


class TestSimpleValidateHandler:

    def test_capability(self):
        h = SimpleValidateHandler()
        assert h.supported_capability() == "simple.validate"

    @pytest.mark.asyncio
    async def test_sees_all_artifacts(self):
        h = SimpleValidateHandler()
        ctx = ExecutionContext(plan_id="p1")
        ctx.record_artifacts({"raw_data": {}, "analysis": {}, "output": {}})
        task = _make_task("t5", capability="simple.validate")
        result = await h.execute(task, ctx)
        assert result.status == TaskResultStatus.SUCCESS
        assert "validation" in result.artifacts
        assert result.artifacts["validation"]["valid"] is True
        assert len(result.artifacts["validation"]["artifacts_available"]) == 3


class TestHandlerStatelessness:
    """Handlers should be stateless — multiple calls with same input → same output."""

    @pytest.mark.asyncio
    async def test_retrieve_is_stateless(self):
        h = SimpleRetrieveHandler()
        ctx = ExecutionContext(plan_id="p1")
        task = _make_task("t1")
        r1 = await h.execute(task, ctx)
        r2 = await h.execute(task, ctx)
        assert r1.artifacts == r2.artifacts
        assert r1.status == r2.status

    @pytest.mark.asyncio
    async def test_process_is_idempotent(self):
        h = SimpleProcessHandler()
        ctx = ExecutionContext(plan_id="p1")
        ctx.record_artifacts({"raw_data": {"records": [1]}})
        task = _make_task("t1", capability="simple.process")
        r1 = await h.execute(task, ctx)
        r2 = await h.execute(task, ctx)
        assert (
            r1.artifacts["processed_data"]["input_records_count"]
            == r2.artifacts["processed_data"]["input_records_count"]
        )
