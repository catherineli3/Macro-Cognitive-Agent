"""TaskHandlerInterface — Abstract contract for executable task capabilities.

Design (Sprint 4):
    A TaskHandler is a pluggable unit of work identified by a capability string
    (e.g., "macro.yahoo", "macro.signal", "simple.retrieve").

    Capability routing separates the task category (TaskType: RETRIEVE/PROCESS/ANALYZE)
    from the concrete implementation (capability: "macro.yahoo" vs "macro.bloomberg").
    This avoids a single RETRIEVE handler ballooning with if/elif chains.

    Handlers are STATELESS. They read context, produce artifacts, and return
    a TaskResult. The Executor owns state mutation (writing artifacts into context).
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from src.schemas.execution import TaskResult
from src.schemas.planning import Task

if TYPE_CHECKING:
    from src.executor.context import ExecutionContext


class TaskHandlerInterface(ABC):
    """Contract for an executable task capability.

    Implementations must be:
      - Stateless: no mutable internal state across calls.
      - Idempotent: same task + same context → same result.
      - Pure I/O: reads from ExecutionContext (read-only), returns TaskResult.

    The Executor:
      1. Reads task.config["capability"] to find the handler.
      2. Calls handler.execute(task, context).
      3. Merges result.artifacts into ExecutionContext.
      4. Stores result for execution tracking.
    """

    @abstractmethod
    def supported_capability(self) -> str:
        """Capability key for routing.

        Examples:
            "macro.yahoo"        — Retrieve data from Yahoo Finance
            "macro.signal"       — Generate macro signals
            "macro.hypothesis"   — Generate macro hypothesis
            "simple.retrieve"    — Mock retrieve for testing
            "simple.analyze"     — Mock analysis for testing
        """
        ...

    @abstractmethod
    async def execute(self, task: "Task", context: "ExecutionContext") -> TaskResult:
        """Execute this task against the given context.

        Args:
            task: The task to execute (contains id, name, config, dependencies).
            context: Read-only runtime state (artifacts from previous tasks).

        Returns:
            TaskResult with status, artifacts, and execution metadata.
            The Executor is responsible for merging artifacts into context.
        """
        ...

    @abstractmethod
    def handler_name(self) -> str:
        """Unique human-readable handler name for logging/debugging."""
        ...
