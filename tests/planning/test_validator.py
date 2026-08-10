"""Tests for PlanValidator — structural validation of ExecutionPlan."""

import pytest

from src.domain.planning import TaskType
from src.schemas.planning import ExecutionPlan, Task
from src.planning.validator import PlanValidator
from src.shared.exceptions import PlanValidationError


class TestUniqueIds:
    """Validate: every task has a unique ID."""

    def test_unique_ids_pass(self) -> None:
        tasks = [
            Task(id="a", name="A", type=TaskType.RETRIEVE),
            Task(id="b", name="B", type=TaskType.PROCESS),
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        result = PlanValidator.validate(plan)
        assert result is plan  # Returns same plan on success

    def test_duplicate_ids_raises(self) -> None:
        tasks = [
            Task(id="dup", name="First", type=TaskType.RETRIEVE),
            Task(id="dup", name="Second", type=TaskType.PROCESS),
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        with pytest.raises(PlanValidationError, match="Duplicate"):
            PlanValidator.validate(plan)

    def test_no_tasks_raises(self) -> None:
        plan = ExecutionPlan(goal="Empty")
        with pytest.raises(PlanValidationError, match="no tasks"):
            PlanValidator.validate(plan)


class TestDependencyReferences:
    """Validate: all dependencies reference existing task IDs."""

    def test_valid_dependencies(self) -> None:
        tasks = [
            Task(id="a", name="A", type=TaskType.RETRIEVE),
            Task(id="b", name="B", type=TaskType.PROCESS, dependencies=["a"]),
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        PlanValidator.validate(plan)  # Should not raise

    def test_orphan_dependency_raises(self) -> None:
        tasks = [
            Task(id="a", name="A", type=TaskType.RETRIEVE, dependencies=["nonexistent"]),
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        with pytest.raises(PlanValidationError, match="non-existent"):
            PlanValidator.validate(plan)

    def test_multiple_orphans(self) -> None:
        tasks = [
            Task(id="a", name="A", type=TaskType.RETRIEVE),
            Task(id="b", name="B", type=TaskType.PROCESS, dependencies=["a", "ghost1", "ghost2"]),
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        with pytest.raises(PlanValidationError, match="non-existent"):
            PlanValidator.validate(plan)

    def test_self_dependency_is_valid_but_cyclic(self) -> None:
        """Self-dependency passes reference check but triggers cycle detection."""
        tasks = [
            Task(id="a", name="A", type=TaskType.RETRIEVE, dependencies=["a"]),
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        with pytest.raises(PlanValidationError, match="Circular"):
            PlanValidator.validate(plan)


class TestCircularDependency:
    """Validate: no circular dependency cycles."""

    def test_no_cycle_linear(self) -> None:
        tasks = [
            Task(id="a", name="A", type=TaskType.RETRIEVE),
            Task(id="b", name="B", type=TaskType.PROCESS, dependencies=["a"]),
            Task(id="c", name="C", type=TaskType.ANALYZE, dependencies=["b"]),
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        PlanValidator.validate(plan)  # Should not raise

    def test_diamond_dependency_no_cycle(self) -> None:
        """Diamond pattern: a→b, a→c, b→d, c→d — no cycle."""
        tasks = [
            Task(id="a", name="A", type=TaskType.RETRIEVE),
            Task(id="b", name="B", type=TaskType.PROCESS, dependencies=["a"]),
            Task(id="c", name="C", type=TaskType.PROCESS, dependencies=["a"]),
            Task(id="d", name="D", type=TaskType.ANALYZE, dependencies=["b", "c"]),
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        PlanValidator.validate(plan)

    def test_simple_cycle_detected(self) -> None:
        """a → b, b → a = cycle."""
        tasks = [
            Task(id="a", name="A", type=TaskType.RETRIEVE, dependencies=["b"]),
            Task(id="b", name="B", type=TaskType.PROCESS, dependencies=["a"]),
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        with pytest.raises(PlanValidationError, match="Circular"):
            PlanValidator.validate(plan)

    def test_three_node_cycle(self) -> None:
        """a → b, b → c, c → a = cycle."""
        tasks = [
            Task(id="a", name="A", type=TaskType.RETRIEVE, dependencies=["c"]),
            Task(id="b", name="B", type=TaskType.PROCESS, dependencies=["a"]),
            Task(id="c", name="C", type=TaskType.ANALYZE, dependencies=["b"]),
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        with pytest.raises(PlanValidationError, match="Circular"):
            PlanValidator.validate(plan)

    def test_long_chain_no_cycle(self) -> None:
        """5-node linear chain — no cycle."""
        tasks = [
            Task(id=f"t{i}", name=f"T{i}", type=TaskType.PROCESS,
                 dependencies=[f"t{i-1}"] if i > 0 else [])
            for i in range(5)
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        PlanValidator.validate(plan)


class TestTopologicalOrder:
    """Validate: correct topological sort output."""

    def test_linear_order(self) -> None:
        tasks = [
            Task(id="a", name="A", type=TaskType.RETRIEVE),
            Task(id="b", name="B", type=TaskType.PROCESS, dependencies=["a"]),
            Task(id="c", name="C", type=TaskType.ANALYZE, dependencies=["b"]),
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        PlanValidator.validate(plan)
        order = PlanValidator.topological_order(plan)
        assert order == ["a", "b", "c"]

    def test_independent_tasks_can_be_parallel(self) -> None:
        """Tasks with no interdependencies appear in any order."""
        tasks = [
            Task(id="a", name="A", type=TaskType.RETRIEVE),
            Task(id="b", name="B", type=TaskType.RETRIEVE),
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        order = PlanValidator.topological_order(plan)
        assert set(order) == {"a", "b"}
        assert len(order) == 2

    def test_dependency_precedes_dependent(self) -> None:
        """For any pair where b depends on a, a must appear before b."""
        tasks = [
            Task(id="z", name="Z", type=TaskType.RETRIEVE),
            Task(id="y", name="Y", type=TaskType.PROCESS, dependencies=["z"]),
            Task(id="x", name="X", type=TaskType.ANALYZE, dependencies=["y"]),
        ]
        plan = ExecutionPlan(goal="Test", tasks=tasks)
        order = PlanValidator.topological_order(plan)
        assert order.index("z") < order.index("y")
        assert order.index("y") < order.index("x")
