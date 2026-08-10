"""PlanValidator — Structural validation for ExecutionPlan.

Validates:
    1. Every task has a unique ID
    2. All dependencies reference existing task IDs
    3. No circular dependency cycles
    4. Plan is topologically sortable (execution order exists)

Algorithm: Kahn's algorithm for topological sort + cycle detection.
"""

from collections import deque

from src.schemas.planning import ExecutionPlan
from src.shared.exceptions import PlanValidationError
from src.shared.logging import get_logger

logger = get_logger(__name__)


class PlanValidator:
    """Validates the structural integrity of an ExecutionPlan.

    This is a pure function — no state, no side effects. It takes a plan,
    checks all structural constraints, and returns the plan if valid or
    raises PlanValidationError with specific diagnostic information.
    """

    @staticmethod
    def validate(plan: ExecutionPlan) -> ExecutionPlan:
        """Validate plan structure.

        Checks (in order):
            1. Unique task IDs
            2. Dependency references exist
            3. No circular dependencies (via topological sort)

        Args:
            plan: The ExecutionPlan to validate.

        Returns:
            The same plan (for chaining) if valid.

        Raises:
            PlanValidationError: If any structural constraint is violated.
        """
        if not plan.tasks:
            raise PlanValidationError(
                "Plan has no tasks",
                details={"plan_id": plan.plan_id, "goal": plan.goal},
            )

        PlanValidator._check_unique_ids(plan)
        PlanValidator._check_dependency_references(plan)
        PlanValidator._check_no_cycles(plan)

        logger.debug(
            "Plan validated successfully",
            extra={
                "plan_id": plan.plan_id,
                "task_count": plan.task_count,
                "goal": plan.goal[:50],
            },
        )
        return plan

    @staticmethod
    def _check_unique_ids(plan: ExecutionPlan) -> None:
        """Verify all task IDs are unique within the plan."""
        seen: set[str] = set()
        duplicates: list[str] = []

        for task in plan.tasks:
            if task.id in seen:
                duplicates.append(task.id)
            seen.add(task.id)

        if duplicates:
            raise PlanValidationError(
                f"Duplicate task IDs found: {duplicates}",
                details={"plan_id": plan.plan_id, "duplicates": duplicates},
            )

    @staticmethod
    def _check_dependency_references(plan: ExecutionPlan) -> None:
        """Verify all dependency references point to existing tasks."""
        valid_ids = plan.task_ids

        for task in plan.tasks:
            orphans = [dep for dep in task.dependencies if dep not in valid_ids]
            if orphans:
                raise PlanValidationError(
                    f"Task '{task.id}' depends on non-existent task(s): {orphans}",
                    details={
                        "plan_id": plan.plan_id,
                        "task_id": task.id,
                        "orphan_dependencies": orphans,
                    },
                )

    @staticmethod
    def _check_no_cycles(plan: ExecutionPlan) -> None:
        """Detect circular dependencies using Kahn's topological sort.

        Builds an in-degree map and adjacency list, then processes nodes
        with zero in-degree. If fewer nodes are processed than total,
        there is at least one cycle.

        Returns:
            Sorted task IDs in topological order (for potential use by Executor).

        Raises:
            PlanValidationError: If a cycle is detected.
        """
        task_ids = [t.id for t in plan.tasks]

        # Build in-degree map and adjacency list
        in_degree: dict[str, int] = {tid: 0 for tid in task_ids}
        adj: dict[str, list[str]] = {tid: [] for tid in task_ids}

        for task in plan.tasks:
            for dep in task.dependencies:
                adj[dep].append(task.id)  # dep → task (dep must complete first)
                in_degree[task.id] += 1

        # Kahn's algorithm: process nodes with zero in-degree
        queue: deque[str] = deque(tid for tid, deg in in_degree.items() if deg == 0)
        sorted_order: list[str] = []

        while queue:
            node = queue.popleft()
            sorted_order.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_order) != len(task_ids):
            # There's a cycle — identify the nodes still in the cycle
            cycle_nodes = [tid for tid, deg in in_degree.items() if deg > 0]
            raise PlanValidationError(
                f"Circular dependency detected among tasks: {cycle_nodes}",
                details={
                    "plan_id": plan.plan_id,
                    "cycle_nodes": cycle_nodes,
                    "sorted_count": len(sorted_order),
                    "total_tasks": len(task_ids),
                },
            )

        logger.debug(
            "Topological sort successful",
            extra={"plan_id": plan.plan_id, "order": sorted_order},
        )

    @staticmethod
    def topological_order(plan: ExecutionPlan) -> list[str]:
        """Return task IDs in topological execution order.

        This is a read-only operation — it does NOT modify the plan.
        Useful for the Executor to know the correct execution sequence.

        Args:
            plan: A validated ExecutionPlan.

        Returns:
            Task IDs in dependency-respecting execution order.
        """
        task_ids = {t.id for t in plan.tasks}
        in_degree: dict[str, int] = {tid: 0 for tid in task_ids}
        adj: dict[str, list[str]] = {tid: [] for tid in task_ids}

        for task in plan.tasks:
            for dep in task.dependencies:
                adj[dep].append(task.id)
                in_degree[task.id] += 1

        queue: deque[str] = deque(tid for tid, deg in in_degree.items() if deg == 0)
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for nb in adj[node]:
                in_degree[nb] -= 1
                if in_degree[nb] == 0:
                    queue.append(nb)

        return order
