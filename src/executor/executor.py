"""AgentExecutor — Executes an ExecutionPlan via registered TaskHandlers.

Sprint 4 design (Minimal Agent Architecture):
    AgentExecutor is the single entry point for plan execution. It keeps
    Scheduler, Dispatcher, and Registry as internal PRIVATE methods,
    NOT as independent modules or classes. This avoids premature abstraction.

    Execution loop:
        1. Validate plan structure (reuse PlanValidator from Sprint 3)
        2. Check all capabilities have registered handlers
        3. Initialize ExecutionContext
        4. Loop: get ready tasks → execute each → record result + artifacts
        5. Build ExecutionResult

    AgentExecutor contains ZERO business logic and ZERO domain knowledge.
    It only orchestrates: plan → handler → context → result.

RC-1 (Reliability):
    - Per-task timeout via asyncio.wait_for (configurable via task.config["timeout_seconds"]).
    - Retry on transient failures (configurable via task.config["max_retries"]).
    - Graceful degradation: non-critical task failures do not block downstream.
    - Every handler exception is isolated — single handler crash never kills the pipeline.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from src.domain.execution import TaskResultStatus
from src.executor.context import ExecutionContext
from src.interfaces.task_handler import TaskHandlerInterface
from src.planning.validator import PlanValidator
from src.schemas.execution import ExecutionResult, TaskResult
from src.schemas.planning import ExecutionPlan, Task
from src.shared.exceptions import ExecutionError, PlanValidationError
from src.shared.logging import get_logger
from src.shared.reliability import (
    TaskTimeoutError,
    execute_with_timeout,
)

logger = get_logger(__name__)

# ── Default Reliability Configuration ──────────────────────────────────────

_DEFAULT_TIMEOUT_SECONDS: float = 30.0
_DEFAULT_MAX_RETRIES: int = 1  # 1 = no retry (single attempt)
_DEFAULT_RETRY_DELAY: float = 1.0
_DEFAULT_RETRY_BACKOFF: float = 2.0
_DEFAULT_CRITICAL: bool = True

# Retryable exception types
_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    asyncio.TimeoutError,
    TaskTimeoutError,
    ConnectionError,
    TimeoutError,
    OSError,
)


class AgentExecutor:
    """Executes an ExecutionPlan by dispatching each Task to the correct handler.

    The Executor is stateless — all runtime state lives in ExecutionContext,
    which is created fresh for each execute() call.

    Usage:
        executor = AgentExecutor()
        executor.register(MyRetrieveHandler())
        executor.register(MyAnalyzeHandler())
        result = await executor.execute(plan)
    """

    def __init__(self) -> None:
        # Internal handler registry: capability_string → handler
        self._handlers: dict[str, TaskHandlerInterface] = {}

    # ── Handler Registration ───────────────────────────────────────────────

    def register(self, handler: TaskHandlerInterface) -> "AgentExecutor":
        """Register a handler for its supported capability.

        Returns self for fluent chaining:
            executor.register(h1).register(h2).register(h3)

        Raises:
            ExecutionError: If a handler is already registered for this capability.
        """
        capability = handler.supported_capability()
        if capability in self._handlers:
            existing = self._handlers[capability]
            raise ExecutionError(
                f"Handler already registered for capability '{capability}': "
                f"{existing.handler_name()} (tried to register {handler.handler_name()})",
                details={"capability": capability},
            )
        self._handlers[capability] = handler
        logger.debug(
            "Handler registered",
            extra={"capability": capability, "handler": handler.handler_name()},
        )
        return self

    @property
    def registered_capabilities(self) -> set[str]:
        """Set of all registered capability strings."""
        return set(self._handlers.keys())

    # ── Main Entry Point ───────────────────────────────────────────────────

    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        """Execute an ExecutionPlan and return results.

        Args:
            plan: A validated ExecutionPlan from the Planner.

        Returns:
            ExecutionResult with per-task outcomes and aggregated artifacts.

        Raises:
            PlanValidationError: If plan structure is invalid.
            ExecutionError: If a task has no registered handler.
        """
        # Step 0: Validate
        self._validate(plan)

        # Step 1: Init context
        context = ExecutionContext(plan_id=plan.plan_id)
        logger.info(
            "Starting plan execution",
            extra={"plan_id": plan.plan_id, "task_count": plan.task_count, "goal": plan.goal[:80]},
        )

        # Step 2: Execution loop
        while True:
            ready = self._get_ready_tasks(plan, context)
            if not ready:
                break  # All done or deadlocked (blocked by failures)

            for task in ready:
                result = await self._execute_one(task, context)
                context.record_result(result)
                context.record_artifacts(result.artifacts)

        # Step 3: Build result
        result = context.to_execution_result(plan)
        logger.info(
            "Plan execution finished",
            extra={
                "plan_id": plan.plan_id,
                "status": result.status.value,
                "succeeded": result.success_count,
                "failed": result.failure_count,
                "total_ms": result.total_time_ms,
            },
        )
        return result

    # ── Private: Validation ────────────────────────────────────────────────

    def _validate(self, plan: ExecutionPlan) -> None:
        """Pre-execution validation: plan structure + handler coverage."""
        # Reuse Sprint 3's PlanValidator for structural checks
        PlanValidator.validate(plan)

        # Check every required capability has a handler
        missing: list[str] = []
        for task in plan.tasks:
            capability = task.config.get("capability", "")
            if not capability:
                missing.append(f"task '{task.id}' has no 'capability' in config")
            elif capability not in self._handlers:
                missing.append(
                    f"task '{task.id}' requires capability '{capability}' "
                    f"— no handler registered"
                )

        if missing:
            raise ExecutionError(
                f"Handler coverage check failed: {'; '.join(missing)}",
                details={
                    "plan_id": plan.plan_id,
                    "missing": missing,
                    "registered": list(self._handlers.keys()),
                },
            )

    # ── Private: Scheduler (dependency resolution) ─────────────────────────

    def _get_ready_tasks(
        self, plan: ExecutionPlan, context: ExecutionContext
    ) -> list[Task]:
        """Return tasks whose all dependencies have completed (or soft-failed).

        Rules:
          1. Skip already-completed tasks.
          2. A task is ready when ALL its *critical* dependencies succeeded,
             AND all *non-critical* dependencies completed (regardless of outcome).
          3. A failed *critical* dependency blocks downstream tasks (strict mode).
          4. A failed *non-critical* dependency allows downstream to proceed
             (graceful degradation).

        This is a PRIVATE method — not a standalone Scheduler module.
        """
        ready: list[Task] = []
        for task in plan.tasks:
            if context.is_completed(task.id):
                continue
            if self._all_deps_resolved(task, plan, context):
                ready.append(task)
        return ready

    def _all_deps_resolved(
        self, task: Task, plan: ExecutionPlan, context: ExecutionContext
    ) -> bool:
        """Check whether all dependencies are resolved for a task.

        Critical deps must succeed; non-critical deps just need to complete.
        A task with no dependencies is always considered resolved.
        """
        if not task.dependencies:
            return True

        for dep_id in task.dependencies:
            dep_task = plan.get_task(dep_id)
            dep_critical = self._is_critical(dep_task)

            if dep_critical:
                # Critical dependency: must succeed
                if not context.is_successful(dep_id):
                    return False
            else:
                # Non-critical dependency: just needs to be done
                if not context.is_completed(dep_id):
                    return False

        return True

    @staticmethod
    def _is_critical(task: Optional[Task]) -> bool:
        """Determine if a task is critical (failure blocks downstream)."""
        if task is None:
            return True  # Unknown tasks are treated as critical
        return task.config.get("critical", _DEFAULT_CRITICAL)

    @staticmethod
    def _get_timeout(task: Task) -> float:
        """Read timeout from task config, falling back to default."""
        return float(task.config.get("timeout_seconds", _DEFAULT_TIMEOUT_SECONDS))

    @staticmethod
    def _get_max_retries(task: Task) -> int:
        """Read max retries from task config, falling back to default."""
        return int(task.config.get("max_retries", _DEFAULT_MAX_RETRIES))

    # ── Private: Dispatcher (handler lookup) ───────────────────────────────

    def _get_handler(self, task: Task) -> TaskHandlerInterface:
        """Resolve a Task to its handler via capability routing.

        Looks up task.config["capability"] in the internal handler map.
        This is a PRIVATE method — not a standalone Dispatcher module.

        Raises:
            ExecutionError: If capability is missing from task config
                            or no handler is registered for it.
        """
        capability: Optional[str] = task.config.get("capability")
        if not capability:
            raise ExecutionError(
                f"Task '{task.id}' has no 'capability' in config",
                details={"task_id": task.id, "task_name": task.name},
            )

        handler = self._handlers.get(capability)
        if handler is None:
            raise ExecutionError(
                f"No handler registered for capability '{capability}' "
                f"(task '{task.id}')",
                details={
                    "task_id": task.id,
                    "capability": capability,
                    "registered": list(self._handlers.keys()),
                },
            )

        return handler

    # ── Private: Single Task Execution ─────────────────────────────────────

    async def _execute_one(self, task: Task, context: ExecutionContext) -> TaskResult:
        """Execute a single task via its handler with timeout and retry.

        Wraps handler execution with:
          - Timeout enforcement (per task.config["timeout_seconds"]).
          - Retry on transient failures (per task.config["max_retries"]).
          - Exception isolation: any handler crash → FAILED/TIMED_OUT TaskResult.
          - Graceful degradation: non-critical failures → SKIPPED TaskResult.

        A handler exception is caught and converted to a FAILED TaskResult
        — it does NOT crash the Executor or the Pipeline.
        """
        started_at = datetime.now(timezone.utc)
        capability = task.config.get("capability", "unknown")
        logger.debug(
            "Executing task",
            extra={
                "task_id": task.id,
                "task_name": task.name,
                "capability": capability,
                "critical": self._is_critical(task),
            },
        )

        timeout_s = self._get_timeout(task)
        max_retries = self._get_max_retries(task)

        handler = self._get_handler(task)
        last_error: Optional[str] = None
        attempts = 0

        for attempt in range(1, max_retries + 1):
            attempts = attempt
            try:
                # Execute handler with timeout enforcement
                result = await execute_with_timeout(
                    handler.execute(task, context),
                    timeout_seconds=timeout_s,
                    task_id=task.id,
                    task_name=task.name,
                )
                break  # Success — exit retry loop
            except TaskTimeoutError:
                completed_at = datetime.now(timezone.utc)
                delta_ms = round((completed_at - started_at).total_seconds() * 1000, 2)
                logger.error(
                    "Task timed out",
                    extra={
                        "task_id": task.id,
                        "task_name": task.name,
                        "timeout_s": timeout_s,
                        "attempt": f"{attempt}/{max_retries}",
                    },
                )
                if attempt >= max_retries:
                    return self._build_task_result(
                        task=task,
                        status=TaskResultStatus.TIMED_OUT
                        if self._is_critical(task)
                        else TaskResultStatus.SKIPPED,
                        started_at=started_at,
                        error=f"Timed out after {timeout_s:.1f}s ({attempt} attempt(s))",
                        execution_time_ms=delta_ms,
                    )
                await asyncio.sleep(
                    _DEFAULT_RETRY_DELAY * (_DEFAULT_RETRY_BACKOFF ** (attempt - 1))
                )
            except _RETRYABLE_EXCEPTIONS as exc:
                last_error = str(exc)
                if attempt < max_retries:
                    delay = _DEFAULT_RETRY_DELAY * (_DEFAULT_RETRY_BACKOFF ** (attempt - 1))
                    logger.warning(
                        "Task retry",
                        extra={
                            "task_id": task.id,
                            "attempt": f"{attempt}/{max_retries}",
                            "delay_s": round(delay, 2),
                            "error": str(exc)[:200],
                        },
                    )
                    await asyncio.sleep(delay)
                # If last attempt, fall through to the except block below
                if attempt >= max_retries:
                    continue  # Will hit the outer except
            except Exception as exc:
                # Non-retryable exception — fail immediately
                completed_at = datetime.now(timezone.utc)
                delta_ms = round((completed_at - started_at).total_seconds() * 1000, 2)
                logger.error(
                    "Task execution failed with non-retryable exception",
                    extra={"task_id": task.id, "error": str(exc), "error_type": type(exc).__name__},
                )
                return self._build_task_result(
                    task=task,
                    status=TaskResultStatus.FAILED
                    if self._is_critical(task)
                    else TaskResultStatus.SKIPPED,
                    started_at=started_at,
                    error=str(exc),
                    execution_time_ms=delta_ms,
                )
        else:
            # Retry loop exhausted without success
            completed_at = datetime.now(timezone.utc)
            delta_ms = round((completed_at - started_at).total_seconds() * 1000, 2)
            logger.error(
                "Task failed after all retries",
                extra={
                    "task_id": task.id,
                    "attempts": attempts,
                    "error": last_error,
                },
            )
            return self._build_task_result(
                task=task,
                status=TaskResultStatus.FAILED
                if self._is_critical(task)
                else TaskResultStatus.SKIPPED,
                started_at=started_at,
                error=f"Failed after {attempts} attempt(s): {last_error}",
                execution_time_ms=delta_ms,
            )

        # Success path — result was set in the try block
        # Ensure timing is set if handler didn't populate it
        if result.started_at == result.completed_at or result.execution_time_ms == 0.0:
            completed_at = datetime.now(timezone.utc)
            result.completed_at = completed_at
            delta = completed_at - result.started_at
            result.execution_time_ms = round(delta.total_seconds() * 1000, 2)

        logger.debug(
            "Task executed",
            extra={
                "task_id": task.id,
                "status": result.status.value,
                "artifacts": list(result.artifacts.keys()),
                "ms": result.execution_time_ms,
                "attempts": attempts,
            },
        )
        return result

    @staticmethod
    def _build_task_result(
        task: Task,
        status: TaskResultStatus,
        started_at: datetime,
        error: str = "",
        execution_time_ms: float = 0.0,
        artifacts: Optional[dict] = None,
    ) -> TaskResult:
        """Build a TaskResult for non-success outcomes (timeout, failure, skipped)."""
        completed_at = datetime.now(timezone.utc)
        if execution_time_ms == 0.0:
            execution_time_ms = round(
                (completed_at - started_at).total_seconds() * 1000, 2
            )
        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=status,
            artifacts=artifacts or {},
            error=error if error else None,
            started_at=started_at,
            completed_at=completed_at,
            execution_time_ms=execution_time_ms,
        )

    def __repr__(self) -> str:
        return f"<AgentExecutor capabilities={list(self._handlers.keys())}>"
