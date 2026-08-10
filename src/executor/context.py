"""ExecutionContext — Shared runtime state for a single plan execution.

Design (Sprint 4):
    ExecutionContext is the ONLY data-sharing mechanism during plan execution.
    
    Artifacts are the primary data carrier:
      - Each Handler produces named artifacts in TaskResult.artifacts.
      - The Executor merges them into context.artifacts.
      - Future components (Memory, Reflection, Report) consume context.artifacts directly.
    
    Task results are tracked separately for execution observability (status, timing, errors).
    
    The Executor OWNS the context. Handlers can only READ (they receive it as a parameter).
    Artifact mutation happens EXCLUSIVELY through executor-controlled methods.

    This is NOT long-term Memory — it lives for one plan execution.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from src.domain.execution import ExecutionStatus
from src.schemas.execution import ExecutionResult, TaskResult
from src.schemas.planning import ExecutionPlan, Task


class ExecutionContext:
    """Mutable runtime state shared across Task executions within a single plan run.

    Usage:
        ctx = ExecutionContext(plan_id="abc123")
        # Executor calls after each handler completes:
        ctx.record_result(task_result)           # Track execution metadata
        ctx.record_artifacts(task_result.artifacts)  # Store business data
        # Scheduler queries:
        ready = ctx.is_successful("task_1")       # Check if dep satisfied
    """

    def __init__(self, plan_id: str) -> None:
        self._plan_id: str = plan_id
        self._started_at: datetime = datetime.now(timezone.utc)

        # Execution tracking (for observability)
        self._task_results: dict[str, TaskResult] = {}

        # Business data (the primary data interface)
        self._artifacts: dict[str, Any] = {}

    # ── Artifact Operations (primary data carrier) ─────────────────────────

    @property
    def artifacts(self) -> dict[str, Any]:
        """Read-only view of all artifacts accumulated so far.

        Handlers use this to access outputs from previous tasks.
        """
        return dict(self._artifacts)  # Return a copy to enforce read-only

    def get_artifact(self, name: str, default: Any = None) -> Any:
        """Read a single named artifact produced by a previous task.

        Args:
            name: Artifact key (e.g., "raw_data", "signals", "hypothesis").
            default: Value to return if artifact not found.

        Returns:
            The artifact value, or default if not present.
        """
        return self._artifacts.get(name, default)

    def record_artifacts(self, artifacts: dict[str, Any]) -> None:
        """Merge artifacts into context. Called ONLY by Executor.

        Args:
            artifacts: Named artifacts produced by a handler.
                       Keys are merged into context._artifacts.
        """
        self._artifacts.update(artifacts)

    # ── Task Result Operations (execution tracking) ────────────────────────

    def record_result(self, task_result: TaskResult) -> None:
        """Record a task's execution result. Called ONLY by Executor.

        Args:
            task_result: Completed task result with status and timing.
        """
        self._task_results[task_result.task_id] = task_result

    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """Get the execution result for a specific task."""
        return self._task_results.get(task_id)

    # ── Dependency Resolution Helpers ──────────────────────────────────────

    def is_completed(self, task_id: str) -> bool:
        """Check if a task has been executed (regardless of success/failure).

        Used by Scheduler to skip already-executed tasks.
        """
        return task_id in self._task_results

    def is_successful(self, task_id: str) -> bool:
        """Check if a task completed SUCCESSFULLY.

        Used by Scheduler to determine if dependent tasks can proceed.
        In strict mode, a failed dependency blocks downstream tasks.
        """
        result = self._task_results.get(task_id)
        return result is not None and result.is_success

    def all_deps_satisfied(self, task: Task) -> bool:
        """Check if all dependencies of a given task have completed successfully.

        A task with no dependencies is always considered satisfied.
        """
        if not task.dependencies:
            return True
        return all(self.is_successful(dep) for dep in task.dependencies)

    # ── Serialization ──────────────────────────────────────────────────────

    def to_execution_result(self, plan: "ExecutionPlan") -> ExecutionResult:
        """Serialize the runtime context into an immutable ExecutionResult.

        Computes the overall status based on task outcomes:
          - All success → COMPLETED
          - Some failure → PARTIALLY_COMPLETED
          - No tasks executed → FAILED (shouldn't happen in practice)

        Args:
            plan: The original ExecutionPlan for goal/plan_id reference.

        Returns:
            Immutable ExecutionResult suitable for return or storage.
        """
        completed_at = datetime.now(timezone.utc)
        total_ms = round((completed_at - self._started_at).total_seconds() * 1000, 2)

        # Build execution order from results (preserve first-seen order)
        execution_order = list(self._task_results.keys())

        # Determine overall status
        total = len(plan.tasks)
        succeeded = sum(1 for r in self._task_results.values() if r.is_success)
        failed = total - succeeded if total > 0 else sum(
            1 for r in self._task_results.values() if not r.is_success
        )

        if succeeded == total:
            status = ExecutionStatus.COMPLETED
        elif succeeded > 0:
            status = ExecutionStatus.PARTIALLY_COMPLETED
        else:
            status = ExecutionStatus.FAILED

        return ExecutionResult(
            plan_id=plan.plan_id,
            goal=plan.goal,
            status=status,
            task_results=dict(self._task_results),
            artifacts=dict(self._artifacts),
            execution_order=execution_order,
            total_time_ms=total_ms,
            started_at=self._started_at,
            completed_at=completed_at,
        )

    def __repr__(self) -> str:
        completed = len(self._task_results)
        return (
            f"<ExecutionContext plan={self._plan_id} "
            f"completed={completed} "
            f"artifacts={list(self._artifacts.keys())}>"
        )
