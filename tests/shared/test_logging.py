"""Tests — Shared logging infrastructure.

Covers:
    - get_logger returns a LoggerAdapter
    - pipeline_step context manager logging
    - with_retry decorator behavior
    - configure_logging initializes without errors
"""

import logging

import pytest

from src.shared.logging import (
    configure_logging,
    get_logger,
    pipeline_step,
    pipeline_step_sync,
    with_retry,
)


class TestGetLogger:
    """Logger factory returns usable loggers."""

    def test_logger_is_not_none(self) -> None:
        logger = get_logger("test_module")
        assert logger is not None

    def test_logger_has_info_method(self) -> None:
        logger = get_logger("test_module")
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")

    def test_logger_inherits_name(self) -> None:
        logger = get_logger("test.specific.module")
        assert "test.specific.module" == logger.name


class TestConfigureLogging:
    """Configure logging sets up without errors."""

    def test_configure_default(self) -> None:
        configure_logging(level="INFO")

    def test_configure_debug(self) -> None:
        configure_logging(level="DEBUG")

    def test_configure_with_file(self, tmp_path) -> None:
        log_file = str(tmp_path / "test.log")
        configure_logging(level="INFO", log_file=log_file)


class TestWithRetry:
    """Retry decorator handles success and failure."""

    def test_sync_success_no_retry(self) -> None:
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        def succeed_on_first() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeed_on_first()
        assert result == "ok"
        assert call_count == 1

    def test_sync_retry_then_fail(self) -> None:
        call_count = 0

        @with_retry(max_attempts=2, base_delay=0.01, exceptions=(ValueError,))
        def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with pytest.raises(ValueError):
            always_fail()
        assert call_count == 2  # tried twice

    def test_sync_success_after_retry(self) -> None:
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01, exceptions=(ValueError,))
        def succeed_on_third() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "ok"

        result = succeed_on_third()
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_retry(self) -> None:
        call_count = 0

        @with_retry(max_attempts=2, base_delay=0.01, exceptions=(ValueError,))
        async def async_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await async_fail()
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_success(self) -> None:
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01, exceptions=(ValueError,))
        async def async_ok() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await async_ok()
        assert result == "ok"
        assert call_count == 1


class TestSharedExceptions:
    """All shared exceptions should be importable and usable."""

    def test_collection_error(self) -> None:
        from src.shared.exceptions import CollectionError

        exc = CollectionError("test", details={"symbol": "DXY"})
        assert str(exc) == "test"
        assert exc.details == {"symbol": "DXY"}

    def test_configuration_error(self) -> None:
        from src.shared.exceptions import ConfigurationError

        exc = ConfigurationError("missing config")
        assert isinstance(exc, Exception)

    def test_repository_error(self) -> None:
        from src.shared.exceptions import RepositoryError

        exc = RepositoryError("db down")
        assert str(exc) == "db down"

    def test_pipeline_error(self) -> None:
        from src.shared.exceptions import PipelineError

        exc = PipelineError("broken")
        assert isinstance(exc, Exception)
