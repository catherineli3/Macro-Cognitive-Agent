"""Execution domain concepts — result status enums.

Sprint 4 defines Execution-level status types. These are domain-agnostic:
    TaskResultStatus: per-task outcome (SUCCESS / FAILED)
    ExecutionStatus: whole-plan outcome (COMPLETED / PARTIALLY_COMPLETED / FAILED)
"""

from enum import Enum


class TaskResultStatus(str, Enum):
    """Outcome of a single Task execution."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"  # Graceful degradation: non-critical upstream failure


class ExecutionStatus(str, Enum):
    """Outcome of executing an entire ExecutionPlan."""

    COMPLETED = "completed"  # All tasks succeeded
    PARTIALLY_COMPLETED = "partially_completed"  # Some tasks failed (strict: downstream blocked)
    FAILED = "failed"  # Fatal error (validation, no handler, etc.)
