"""Planning schemas — Data contracts for Planner Agent v1.

Sprint 3 defines the canonical Task and ExecutionPlan formats.
Every module that produces or consumes plans MUST use these schemas.

Key design decisions (per Architecture Review):
    - TaskType: generic Agent capabilities (RETRIEVE/PROCESS/ANALYZE/GENERATE/VALIDATE/DECIDE)
    - No TaskStatus: execution status belongs to Executor (future Sprint)
    - Plan is immutable: Planner creates, does not track execution
    - plan_explanation: human-readable justification for observability
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from src.domain.planning import TaskType


# ── Task ──────────────────────────────────────────────────────────────────


class Task(BaseModel):
    """A single unit of work within an ExecutionPlan.

    Task is an abstract work item — it describes WHAT to do, not HOW.
    The Executor (future Sprint) maps each task to concrete tool invocations.

    Attributes:
        id: Unique task identifier within the plan scope.
        name: Short human-readable label.
        description: What this task aims to accomplish.
        type: Generic Agent capability classification.
        priority: Execution priority (lower = higher priority).
        dependencies: IDs of tasks that must complete before this one.
        config: Extensible parameters for future Executor use (Sprint 3: empty).
    """

    id: str = Field(
        default_factory=lambda: uuid4().hex[:8],
        min_length=1,
        max_length=64,
        description="Unique task identifier within the plan",
    )
    name: str = Field(..., min_length=1, max_length=128, description="Short human-readable label")
    description: str = Field(
        default="",
        max_length=512,
        description="What this task aims to accomplish",
    )
    type: TaskType = Field(..., description="Generic Agent capability classification")
    priority: int = Field(default=1, ge=1, le=10, description="Execution priority (1 = highest)")
    dependencies: list[str] = Field(
        default_factory=list,
        description="Task IDs that must complete before this task",
    )
    config: dict = Field(
        default_factory=dict,
        description="Extensible parameters (reserved for Executor, Sprint 3: empty)",
    )


# ── ExecutionPlan ─────────────────────────────────────────────────────────


class ExecutionPlan(BaseModel):
    """A structured, immutable plan decomposed from a user goal.

    The Planner creates an ExecutionPlan. The Executor (future Sprint)
    reads it and orchestrates task execution. The plan itself never changes
    after creation — any revision creates a new plan.

    Attributes:
        plan_id: Unique plan identifier.
        goal: The original user goal string.
        tasks: Ordered list of abstract tasks.
        plan_explanation: Human-readable justification of the plan structure,
                          intended for observability, debugging, and audit.
        created_at: Plan creation timestamp.
        version: Schema version for forward compatibility.
    """

    plan_id: str = Field(
        default_factory=lambda: uuid4().hex[:12],
        description="Unique plan identifier",
    )
    goal: str = Field(..., min_length=1, max_length=1024, description="Original user goal")
    tasks: list[Task] = Field(
        default_factory=list,
        description="Ordered list of abstract tasks",
    )
    plan_explanation: str = Field(
        default="",
        max_length=2048,
        description="Human-readable justification of plan structure (observability/debugging)",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Plan creation timestamp (timezone-aware)",
    )
    version: str = Field(default="1.0", description="Schema version")

    @property
    def task_count(self) -> int:
        """Total number of tasks in the plan."""
        return len(self.tasks)

    @property
    def task_ids(self) -> set[str]:
        """Set of all task IDs for fast lookup."""
        return {t.id for t in self.tasks}

    def get_task(self, task_id: str) -> Optional["Task"]:
        """Retrieve a task by its ID."""
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def get_dependency_graph(self) -> dict[str, list[str]]:
        """Return adjacency list: task_id → list of dependency IDs."""
        return {t.id: list(t.dependencies) for t in self.tasks}

    def __repr__(self) -> str:
        return f"<ExecutionPlan {self.plan_id} goal='{self.goal[:40]}...' tasks={len(self.tasks)}>"
