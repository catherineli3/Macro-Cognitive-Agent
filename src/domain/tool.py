"""Tool domain concepts — ToolResult status enum.

Sprint 5 defines Tool-level status types. These are domain-agnostic:
    ToolResultStatus: per-Tool-call outcome (SUCCESS / FAILED)

Design principle:
    Even Tool failures should return ToolResult (with FAILED status)
    rather than raising business exceptions. This keeps the execution
    flow predictable and the error handling centralized in ToolManager.
"""

from enum import Enum


class ToolResultStatus(str, Enum):
    """Outcome of a single Tool execution.

    Every Tool.execute() returns a ToolResult with one of these statuses.
    Exceptions are caught by ToolManager and converted to FAILED status
    — Tools should NOT leak raw exceptions to callers.
    """

    SUCCESS = "success"
    FAILED = "failed"
