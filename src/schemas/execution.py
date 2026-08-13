"""Execution schemas — Data contracts for Agent Executor v1.

Sprint 4 defines TaskResult and ExecutionResult as the output contracts
for the Executor. These are complement to Sprint 3's ExecutionPlan.

Key design decisions:
    - TaskResult carries: execution metadata (status, timing) + business artifacts
    - ExecutionResult is the summary of a full plan execution
    - Artifacts are the primary business data carrier (Memory/Reflection/Report consume them)
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from src.domain.execution import ExecutionStatus, TaskResultStatus

# ── TaskResult ─────────────────────────────────────────────────────────────


class TaskResult(BaseModel):
    """Outcome of executing a single Task.

    Separates execution metadata (status, timing, error) from business
    data (artifacts). Artifacts are the primary data carrier consumed
    by downstream components (Memory, Reflection, Report).

    Attributes:
        task_id: Corresponding Task.id from ExecutionPlan.
        task_name: Redundant label for log readability.
        status: SUCCESS or FAILED.
        artifacts: Named business outputs (e.g., "macro_data", "signals").
                   Populated by the Handler, stored by the Executor in Context.
        error: Error message if status is FAILED.
        started_at: When handler execution began.
        completed_at: When handler returned.
        execution_time_ms: Wall-clock duration.
    """

    task_id: str = Field(..., description="Corresponding Task.id")
    task_name: str = Field(default="", description="Human-readable label")
    status: TaskResultStatus = Field(..., description="SUCCESS or FAILED")
    artifacts: dict[str, Any] = Field(
        default_factory=dict,
        description="Named business outputs produced by this task",
    )
    error: str | None = Field(
        default=None,
        description="Error message if status is FAILED",
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Execution start timestamp",
    )
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Execution end timestamp",
    )
    execution_time_ms: float = Field(
        default=0.0,
        ge=0,
        description="Wall-clock duration in milliseconds",
    )

    def model_post_init(self, __context) -> None:
        """Auto-compute execution_time_ms if both timestamps are set."""
        if self.execution_time_ms == 0.0:
            delta = self.completed_at - self.started_at
            self.execution_time_ms = round(delta.total_seconds() * 1000, 2)

    @property
    def is_success(self) -> bool:
        """Convenience check for success."""
        return self.status == TaskResultStatus.SUCCESS


# ── ExecutionResult ────────────────────────────────────────────────────────


class ExecutionResult(BaseModel):
    """Summary of executing an entire ExecutionPlan.

    Attributes:
        plan_id: The plan that was executed.
        goal: Original user goal (redundant for log readability).
        status: COMPLETED / PARTIALLY_COMPLETED / FAILED.
        task_results: Per-task results, keyed by task_id.
        artifacts: Aggregated artifacts from all completed tasks.
                   This is the primary data interface for Memory/Reflection/Report.
        execution_order: Task IDs in actual execution order.
        total_time_ms: Total wall-clock duration.
        started_at: When execution began.
        completed_at: When execution ended.
    """

    plan_id: str = Field(..., description="The plan that was executed")
    goal: str = Field(default="", description="Original user goal")
    status: ExecutionStatus = Field(..., description="Overall outcome")
    task_results: dict[str, TaskResult] = Field(
        default_factory=dict,
        description="Per-task results keyed by task_id",
    )
    artifacts: dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregated artifacts from all tasks (primary data interface)",
    )
    execution_order: list[str] = Field(
        default_factory=list,
        description="Task IDs in actual execution order",
    )
    total_time_ms: float = Field(default=0.0, ge=0, description="Total wall-clock duration")
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Execution start timestamp",
    )
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Execution end timestamp",
    )

    @property
    def success_count(self) -> int:
        """Number of successfully completed tasks."""
        return sum(1 for r in self.task_results.values() if r.is_success)

    @property
    def failure_count(self) -> int:
        """Number of failed tasks."""
        return len(self.task_results) - self.success_count

    @property
    def has_failures(self) -> bool:
        """Whether any task failed."""
        return self.failure_count > 0

    def get_artifact(self, name: str) -> Any:
        """Retrieve a named artifact from the aggregated set."""
        return self.artifacts.get(name)

    def __repr__(self) -> str:
        return (
            f"<ExecutionResult plan={self.plan_id} "
            f"status={self.status.value} "
            f"tasks={self.success_count}/{len(self.task_results)} "
            f"artifacts={list(self.artifacts.keys())}>"
        )
