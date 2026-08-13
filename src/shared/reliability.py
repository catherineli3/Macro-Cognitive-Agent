"""Reliability utilities — timeout, retry wrappers, and execution safeguards.

RC-1: Provides async-safe timeout enforcement and retry orchestration.
All utilities are decorator/factory-style — zero business logic.
"""

from __future__ import annotations

import asyncio
import functools
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from src.shared.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# ── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_TIMEOUT_SECONDS: float = 30.0
DEFAULT_MAX_RETRIES: int = 1
DEFAULT_RETRY_DELAY: float = 1.0
DEFAULT_RETRY_BACKOFF: float = 2.0


# ── Timeout ─────────────────────────────────────────────────────────────────


class TaskTimeoutError(asyncio.TimeoutError):
    """Raised when a task exceeds its allotted execution time.

    Carries task context for observability.
    """

    def __init__(
        self,
        task_id: str = "",
        task_name: str = "",
        timeout_seconds: float = 0.0,
    ) -> None:
        msg = f"Task '{task_name}' ({task_id}) timed out after " f"{timeout_seconds:.1f}s"
        super().__init__(msg)
        self.task_id = task_id
        self.task_name = task_name
        self.timeout_seconds = timeout_seconds


async def execute_with_timeout(
    coro: Awaitable[T],
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    task_id: str = "",
    task_name: str = "",
) -> T:
    """Execute an awaitable with a hard timeout.

    Args:
        coro: The coroutine to execute.
        timeout_seconds: Maximum wall-clock seconds before raising.
        task_id: Task identifier for error context.
        task_name: Human-readable task name for error context.

    Returns:
        The coroutine's return value.

    Raises:
        TaskTimeoutError: If execution exceeds timeout_seconds.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except TimeoutError:
        elapsed = timeout_seconds
        logger.error(
            "task_timeout",
            extra={
                "task_id": task_id,
                "task_name": task_name,
                "timeout_s": timeout_seconds,
                "elapsed_s": elapsed,
            },
        )
        raise TaskTimeoutError(
            task_id=task_id,
            task_name=task_name,
            timeout_seconds=timeout_seconds,
        ) from None


# ── Retry Factory ───────────────────────────────────────────────────────────


def with_async_retry(
    max_attempts: int = DEFAULT_MAX_RETRIES + 1,
    base_delay: float = DEFAULT_RETRY_DELAY,
    backoff: float = DEFAULT_RETRY_BACKOFF,
    retryable_exceptions: tuple[type[Exception], ...] = (
        asyncio.TimeoutError,
        TaskTimeoutError,
        ConnectionError,
        TimeoutError,
        OSError,
    ),
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator: retry an async function with exponential backoff.

    Unlike the simpler `with_retry` in logging.py, this:
      - Is async-only (no sync path).
      - Distinguishes retryable vs fatal exceptions.
      - Emits structured retry log events.

    Args:
        max_attempts: Total attempts (1 = no retry).
        base_delay: Initial delay in seconds.
        backoff: Multiplier for each subsequent delay.
        retryable_exceptions: Exception types that trigger retry.
            All others are re-raised immediately.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        func_logger = get_logger(func.__module__)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exc: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    result = await func(*args, **kwargs)
                    if attempt > 1:
                        func_logger.info(
                            "retry_succeeded",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt,
                                "max_attempts": max_attempts,
                            },
                        )
                    return result
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        delay = base_delay * (backoff ** (attempt - 1))
                        func_logger.warning(
                            "task_retry",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt,
                                "max_attempts": max_attempts,
                                "delay_s": round(delay, 2),
                                "error": str(exc)[:200],
                                "error_type": type(exc).__name__,
                            },
                        )
                        await asyncio.sleep(delay)
                except Exception as exc:
                    # Non-retryable — fail fast
                    func_logger.error(
                        "task_fatal_error",
                        extra={
                            "function": func.__name__,
                            "error": str(exc)[:200],
                            "error_type": type(exc).__name__,
                        },
                    )
                    raise

            # Exhausted retries
            assert last_exc is not None  # for type checker
            raise last_exc

        return wrapper

    return decorator


# ── Execution Metrics ───────────────────────────────────────────────────────


class ExecutionMetrics:
    """Lightweight metrics collector for a single handler invocation.

    Aggregates timing, retry counts, and timeout events into a dict
    suitable for structured logging and performance analysis (RC-2).
    """

    __slots__ = (
        "task_id",
        "task_name",
        "capability",
        "start_time",
        "end_time",
        "attempts",
        "timed_out",
        "error_type",
        "error_message",
    )

    def __init__(
        self,
        task_id: str = "",
        task_name: str = "",
        capability: str = "",
    ) -> None:
        self.task_id = task_id
        self.task_name = task_name
        self.capability = capability
        self.start_time: float = time.perf_counter()
        self.end_time: float = 0.0
        self.attempts: int = 0
        self.timed_out: bool = False
        self.error_type: str | None = None
        self.error_message: str | None = None

    @property
    def elapsed_ms(self) -> float:
        end = self.end_time if self.end_time > 0 else time.perf_counter()
        return round((end - self.start_time) * 1000, 2)

    def record_success(self, attempts: int = 1) -> None:
        self.end_time = time.perf_counter()
        self.attempts = attempts

    def record_timeout(self, attempts: int = 1) -> None:
        self.end_time = time.perf_counter()
        self.attempts = attempts
        self.timed_out = True

    def record_error(self, exc: Exception, attempts: int = 1) -> None:
        self.end_time = time.perf_counter()
        self.attempts = attempts
        self.error_type = type(exc).__name__
        self.error_message = str(exc)[:500]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "capability": self.capability,
            "elapsed_ms": self.elapsed_ms,
            "attempts": self.attempts,
            "timed_out": self.timed_out,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }
