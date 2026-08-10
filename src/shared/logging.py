from __future__ import annotations

"""Shared logging infrastructure — zero external dependencies.

Meets Sprint 1 AC: Request / Response / Retry / Error / Latency logging.
Uses standard library logging with structured key=value formatting.
"""

import functools
import inspect
import logging
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Callable, Iterator


def get_logger(name: str) -> logging.Logger:
    """Return a standard Python logger for the given module name.

    Usage:
        logger = get_logger(__name__)
        logger.info("collector_fetch | symbol=%s latency_ms=%.2f", "DXY", 245)
    """
    return logging.getLogger(name)


# ── Pipeline step timing context managers ──────────────────────────────


@asynccontextmanager
async def pipeline_step(
    logger: logging.Logger, step_name: str, **context: str
) -> AsyncIterator[None]:
    """Async context manager: log start / done-with-latency / error for a step.

    Usage:
        async with pipeline_step(logger, "yahoo_collect", symbol="DXY"):
            data = await collector.collect(indicator)
    """
    start = time.perf_counter()
    ctx_str = " ".join(f"{k}={v}" for k, v in context.items())
    logger.info("%s_start %s", step_name, ctx_str)
    try:
        yield
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("%s_done latency_ms=%.2f %s", step_name, elapsed_ms, ctx_str)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.error("%s_failed latency_ms=%.2f %s", step_name, elapsed_ms, ctx_str)
        raise


@contextmanager
def pipeline_step_sync(
    logger: logging.Logger, step_name: str, **context: str
) -> Iterator[None]:
    """Sync version of pipeline_step."""
    start = time.perf_counter()
    ctx_str = " ".join(f"{k}={v}" for k, v in context.items())
    logger.info("%s_start %s", step_name, ctx_str)
    try:
        yield
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("%s_done latency_ms=%.2f %s", step_name, elapsed_ms, ctx_str)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.error("%s_failed latency_ms=%.2f %s", step_name, elapsed_ms, ctx_str)
        raise


# ── Retry decorator (with logging) ────────────────────────────────────


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """Decorator that retries a function on failure with exponential backoff.

    Logs each retry attempt including attempt number and delay.
    """

    import asyncio as _asyncio

    def decorator(func: Callable) -> Callable:
        logger = get_logger(func.__module__)

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: Exception | None = None
                for attempt in range(1, max_attempts + 1):
                    try:
                        return await func(*args, **kwargs)  # type: ignore[misc]
                    except exceptions as exc:
                        last_exc = exc
                        if attempt < max_attempts:
                            delay = base_delay * (backoff ** (attempt - 1))
                            logger.warning(
                                "%s_retry attempt=%d/%d delay_s=%.1f error=%s",
                                func.__name__,
                                attempt,
                                max_attempts,
                                delay,
                                exc,
                            )
                            await _asyncio.sleep(delay)
                raise last_exc  # type: ignore[misc]

            return async_wrapper

        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: Exception | None = None
                for attempt in range(1, max_attempts + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as exc:
                        last_exc = exc
                        if attempt < max_attempts:
                            delay = base_delay * (backoff ** (attempt - 1))
                            logger.warning(
                                "%s_retry attempt=%d/%d delay_s=%.1f error=%s",
                                func.__name__,
                                attempt,
                                max_attempts,
                                delay,
                                exc,
                            )
                            time.sleep(delay)
                raise last_exc  # type: ignore[misc]

            return sync_wrapper

    return decorator


# ── Configuration ─────────────────────────────────────────────────────


def configure_logging(level: str = "INFO", log_file: str | None = None) -> None:
    """Initialize logging with structured format.

    Call once at application startup.

    Args:
        level: Minimum log level.
        log_file: Optional file path for log output.
    """
    fmt = "%(asctime)s [%(levelname)-8s] %(name)s | %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file:
        from logging.handlers import RotatingFileHandler

        handlers.append(
            RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
        )

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )
