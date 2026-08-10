"""Tests for Sprint 3 planning schemas and domain models."""

from datetime import timezone

import pytest
from pydantic import ValidationError

from src.domain.planning import TaskType
from src.schemas.planning import ExecutionPlan, Task


class TestTaskType:
    """TaskType: generic Agent capability enum."""

    def test_all_values_present(self) -> None:
        assert TaskType.RETRIEVE.value == "retrieve"
        assert TaskType.PROCESS.value == "process"
        assert TaskType.ANALYZE.value == "analyze"
        assert TaskType.GENERATE.value == "generate"
        assert TaskType.VALIDATE.value == "validate"
        assert TaskType.DECIDE.value == "decide"

    def test_no_macro_specific_types(self) -> None:
        """TaskType must NOT contain domain-specific values."""
        values = {t.value for t in TaskType}
        assert "data_collection" not in values
        assert "signal_generation" not in values
        assert "hypothesis_generation" not in values

    def test_string_coercion(self) -> None:
        """Task type accepts string values via constructor."""
        t = Task(id="t1", name="Test", type="retrieve")
        assert t.type == TaskType.RETRIEVE


class TestTaskModel:
    """Task: abstract work item within a plan."""

    def test_minimal_creation(self) -> None:
        t = Task(id="t1", name="Test Task", type=TaskType.ANALYZE)
        assert t.id == "t1"
        assert t.name == "Test Task"
        assert t.type == TaskType.ANALYZE
        assert t.priority == 1
        assert t.dependencies == []
        assert t.description == ""
        assert t.config == {}

    def test_full_creation(self) -> None:
        t = Task(
            id="task_collect",
            name="Collect Data",
            description="Fetch data from external sources",
            type=TaskType.RETRIEVE,
            priority=3,
            dependencies=["task_setup"],
            config={"timeout": 30},
        )
        assert t.priority == 3
        assert t.dependencies == ["task_setup"]
        assert t.config == {"timeout": 30}

    def test_auto_id_generation(self) -> None:
        t = Task(name="Auto ID", type=TaskType.PROCESS)
        assert t.id is not None
        assert len(t.id) == 8

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            Task(id="t1", type=TaskType.ANALYZE)  # type: ignore[call-arg]

    def test_type_required(self) -> None:
        with pytest.raises(ValidationError):
            Task(id="t1", name="Test")  # type: ignore[call-arg]

    def test_priority_range(self) -> None:
        with pytest.raises(ValidationError):
            Task(id="t1", name="Bad", type=TaskType.ANALYZE, priority=0)
        with pytest.raises(ValidationError):
            Task(id="t1", name="Bad", type=TaskType.ANALYZE, priority=11)

    def test_name_max_length(self) -> None:
        with pytest.raises(ValidationError):
            Task(id="t1", name="X" * 129, type=TaskType.ANALYZE)

    def test_empty_dependencies_default(self) -> None:
        t = Task(id="t1", name="Solo", type=TaskType.GENERATE)
        assert t.dependencies == []

    def test_task_repr(self) -> None:
        t = Task(id="abc", name="Do Something", type=TaskType.RETRIEVE)
        r = repr(t)
        assert "abc" in r


class TestExecutionPlan:
    """ExecutionPlan: immutable structured plan."""

    def test_empty_plan(self) -> None:
        plan = ExecutionPlan(goal="Do nothing")
        assert plan.goal == "Do nothing"
        assert plan.tasks == []
        assert plan.task_count == 0
        assert plan.version == "1.0"

    def test_plan_with_tasks(self) -> None:
        tasks = [
            Task(id="t1", name="First", type=TaskType.RETRIEVE),
            Task(id="t2", name="Second", type=TaskType.ANALYZE, dependencies=["t1"]),
        ]
        plan = ExecutionPlan(goal="Test goal", tasks=tasks, plan_explanation="Two-step analysis")
        assert plan.task_count == 2
        assert plan.task_ids == {"t1", "t2"}
        assert plan.plan_explanation == "Two-step analysis"

    def test_plan_explanation_defaults_to_empty(self) -> None:
        plan = ExecutionPlan(goal="Simple")
        assert plan.plan_explanation == ""

    def test_get_task_existing(self) -> None:
        t1 = Task(id="t1", name="First", type=TaskType.RETRIEVE)
        plan = ExecutionPlan(goal="G", tasks=[t1])
        found = plan.get_task("t1")
        assert found is not None
        assert found.id == "t1"

    def test_get_task_missing(self) -> None:
        plan = ExecutionPlan(goal="G", tasks=[])
        assert plan.get_task("nonexistent") is None

    def test_dependency_graph(self) -> None:
        tasks = [
            Task(id="a", name="A", type=TaskType.RETRIEVE, dependencies=[]),
            Task(id="b", name="B", type=TaskType.PROCESS, dependencies=["a"]),
            Task(id="c", name="C", type=TaskType.ANALYZE, dependencies=["a", "b"]),
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        graph = plan.get_dependency_graph()
        assert graph["a"] == []
        assert graph["b"] == ["a"]
        assert graph["c"] == ["a", "b"]

    def test_created_at_is_utc(self) -> None:
        plan = ExecutionPlan(goal="Test")
        assert plan.created_at.tzinfo == timezone.utc

    def test_plan_repr(self) -> None:
        plan = ExecutionPlan(goal="Analyze risk")
        r = repr(plan)
        assert "Analyze risk" in r
        assert plan.plan_id in r

    def test_plan_id_unique(self) -> None:
        p1 = ExecutionPlan(goal="A")
        p2 = ExecutionPlan(goal="B")
        assert p1.plan_id != p2.plan_id

    def test_plan_has_no_status_field(self) -> None:
        """ExecutionPlan must NOT have a status field (belongs to Executor)."""
        plan = ExecutionPlan(goal="Test")
        assert not hasattr(plan, "status")
