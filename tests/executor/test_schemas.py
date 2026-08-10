"""Tests for Execution Schemas: TaskResult and ExecutionResult."""
import pytest
from datetime import datetime, timezone

from src.domain.execution import ExecutionStatus, TaskResultStatus
from src.schemas.execution import ExecutionResult, TaskResult


class TestTaskResult:
    """TaskResult schema tests."""

    def test_minimal_creation(self):
        tr = TaskResult(task_id="t1", status=TaskResultStatus.SUCCESS)
        assert tr.task_id == "t1"
        assert tr.status == TaskResultStatus.SUCCESS
        assert tr.task_name == ""
        assert tr.artifacts == {}
        assert tr.error is None
        assert tr.is_success is True

    def test_full_creation(self):
        started = datetime.now(timezone.utc)
        completed = datetime.now(timezone.utc)
        tr = TaskResult(
            task_id="t_collect",
            task_name="Collect Data",
            status=TaskResultStatus.SUCCESS,
            artifacts={"raw_data": {"records": [1, 2, 3]}},
            error=None,
            started_at=started,
            completed_at=completed,
        )
        assert tr.task_id == "t_collect"
        assert tr.task_name == "Collect Data"
        assert tr.status == TaskResultStatus.SUCCESS
        assert tr.artifacts["raw_data"] == {"records": [1, 2, 3]}
        assert tr.error is None

    def test_failed_result(self):
        tr = TaskResult(
            task_id="t_fail",
            status=TaskResultStatus.FAILED,
            error="Connection timeout",
        )
        assert tr.status == TaskResultStatus.FAILED
        assert tr.is_success is False
        assert tr.error == "Connection timeout"
        assert tr.artifacts == {}

    def test_multi_artifact(self):
        tr = TaskResult(
            task_id="t_multi",
            status=TaskResultStatus.SUCCESS,
            artifacts={"signals": [], "metadata": {"updated": True}},
        )
        assert len(tr.artifacts) == 2
        assert "signals" in tr.artifacts
        assert "metadata" in tr.artifacts

    def test_execution_time_auto_computed(self):
        started = datetime(2026, 7, 14, 10, 0, 0, tzinfo=timezone.utc)
        completed = datetime(2026, 7, 14, 10, 0, 1, tzinfo=timezone.utc)
        tr = TaskResult(
            task_id="t1",
            status=TaskResultStatus.SUCCESS,
            started_at=started,
            completed_at=completed,
        )
        assert tr.execution_time_ms == 1000.0

    def test_default_status_fails_validation(self):
        with pytest.raises(Exception):
            TaskResult(task_id="t1")  # missing required 'status'


class TestExecutionResult:
    """ExecutionResult schema tests."""

    def test_minimal_creation(self):
        er = ExecutionResult(plan_id="p1", status=ExecutionStatus.COMPLETED)
        assert er.plan_id == "p1"
        assert er.status == ExecutionStatus.COMPLETED
        assert er.success_count == 0
        assert er.failure_count == 0
        assert er.has_failures is False

    def test_with_successful_tasks(self):
        started = datetime.now(timezone.utc)
        tr1 = TaskResult(task_id="t1", task_name="A", status=TaskResultStatus.SUCCESS, started_at=started)
        tr2 = TaskResult(task_id="t2", task_name="B", status=TaskResultStatus.SUCCESS, started_at=started)
        er = ExecutionResult(
            plan_id="p1",
            status=ExecutionStatus.COMPLETED,
            task_results={"t1": tr1, "t2": tr2},
            execution_order=["t1", "t2"],
        )
        assert er.success_count == 2
        assert er.failure_count == 0
        assert er.has_failures is False

    def test_with_mixed_results(self):
        started = datetime.now(timezone.utc)
        tr1 = TaskResult(task_id="t1", task_name="A", status=TaskResultStatus.SUCCESS, started_at=started)
        tr2 = TaskResult(task_id="t2", task_name="B", status=TaskResultStatus.FAILED, error="fail", started_at=started)
        er = ExecutionResult(
            plan_id="p1",
            goal="Test",
            status=ExecutionStatus.PARTIALLY_COMPLETED,
            task_results={"t1": tr1, "t2": tr2},
            execution_order=["t1", "t2"],
        )
        assert er.success_count == 1
        assert er.failure_count == 1
        assert er.has_failures is True
        assert er.goal == "Test"

    def test_artifacts_access(self):
        er = ExecutionResult(
            plan_id="p1",
            status=ExecutionStatus.COMPLETED,
            artifacts={"macro_data": {"DXY": 105}, "signals": ["neutral"]},
        )
        assert er.get_artifact("macro_data") == {"DXY": 105}
        assert er.get_artifact("signals") == ["neutral"]
        assert er.get_artifact("nonexistent") is None
