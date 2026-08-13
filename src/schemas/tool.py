"""Tool schemas — Data contracts for Tool Layer (Sprint 5).

ToolResult is the unified output contract for every Tool in the system.
It separates execution metadata (status, timing, tool_name) from the
canonical business data (artifact).

Design principle (Canonical Data Layer):
    Tool outputs MUST be Artifacts, NOT raw API responses.
    Every Tool is responsible for translating external data into the
    Agent's internal canonical schema (MacroDataSchema, etc.) before
    returning. The rest of the Agent (Planner, Executor, Handler) must
    NEVER depend on vendor-specific response formats.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from src.domain.tool import ToolResultStatus


class ToolResult(BaseModel):
    """Unified output of a single Tool invocation.

    Every Tool, regardless of data source or implementation, returns
    exactly one ToolResult. Even failures are expressed as ToolResult
    with status=FAILED — raw exceptions never leak past ToolManager.

    Attributes:
        status: SUCCESS or FAILED.
        tool_name: Which tool produced this result (for logging/audit).
        artifact: Named canonical data artifacts (e.g., {"macro_data": [...]}).
                  Uses the same pattern as TaskResult.artifacts for seamless
                  integration with ExecutionContext.
        latency_ms: Wall-clock execution time.
        error: Error message if status is FAILED.
        completed_at: When the tool finished execution.
    """

    status: ToolResultStatus = Field(..., description="SUCCESS or FAILED")
    tool_name: str = Field(..., min_length=1, description="Tool that produced this result")
    artifact: dict[str, Any] = Field(
        default_factory=dict,
        description="Named canonical data artifacts",
    )
    latency_ms: float = Field(default=0.0, ge=0, description="Wall-clock execution time in ms")
    error: str | None = Field(
        default=None,
        description="Error message if status is FAILED",
    )
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Completion timestamp",
    )

    @property
    def is_success(self) -> bool:
        """Convenience check for success."""
        return self.status == ToolResultStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        """Convenience check for failure."""
        return self.status == ToolResultStatus.FAILED

    def __repr__(self) -> str:
        return (
            f"<ToolResult tool={self.tool_name} status={self.status.value} "
            f"artifacts={list(self.artifact.keys())} latency={self.latency_ms:.1f}ms>"
        )
