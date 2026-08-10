"""(Unit) LLMClient retry logic: verify LLMRetryableError triggers retry."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.llm.client import LLMClient, LLMError, LLMRetryableError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_response(content: str, status: int = 200) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


# ---------------------------------------------------------------------------
# Test: retry happens on transient errors
# ---------------------------------------------------------------------------


class TestRetryOnTransientErrors:
    """LLMRetryableError (timeout / network / 429) should trigger retry."""

    def test_retry_on_first_timeout_then_success(self) -> None:
        """First call raises LLMRetryableError(timeout), second succeeds.

        Verifies that the retry mechanism actually fires — the key bug
        was that _request caught LLMError and re-raised immediately
        without ever entering the retry path.
        """
        client = LLMClient(api_key="test-key")

        retries_spent: list[int] = []

        def side_effect(*args, **kwargs):
            nonlocal retries_spent
            retries_spent.append(1)
            if len(retries_spent) == 1:
                import httpx
                raise httpx.TimeoutException("timed out")
            return _fake_response('{"ok": true}')

        with patch("httpx.request", side_effect=side_effect):
            result = client.chat([{"role": "user", "content": "hi"}])

        # Retry happened: 2 calls total (first fail, second success)
        assert len(retries_spent) == 2
        assert result == '{"ok": true}'

    def test_retry_on_first_network_error_then_success(self) -> None:
        """First call raises LLMRetryableError(network), second succeeds."""
        client = LLMClient(api_key="test-key")

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                import httpx
                raise httpx.RequestError("connection reset")
            return _fake_response("hello")

        with patch("httpx.request", side_effect=side_effect):
            result = client.chat([{"role": "user", "content": "hi"}])

        assert call_count == 2
        assert result == "hello"

    def test_retry_on_http_429_then_success(self) -> None:
        """First call returns HTTP 429, second succeeds."""
        client = LLMClient(api_key="test-key")

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _fake_response("rate limited", status=429)
            return _fake_response("ok after retry")

        with patch("httpx.request", side_effect=side_effect):
            result = client.chat([{"role": "user", "content": "hi"}])

        assert call_count == 2
        assert result == "ok after retry"

    def test_no_retry_on_auth_error(self) -> None:
        """Authentication failures (401/403) are NOT retryable."""
        client = LLMClient(api_key="test-key")

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return _fake_response("unauthorized", status=401)

        with patch("httpx.request", side_effect=side_effect):
            with pytest.raises(LLMError):
                client.chat([{"role": "user", "content": "hi"}])

        # Auth errors are non-retryable: only 1 call
        assert call_count == 1

    def test_raises_after_max_retries_exceeded(self) -> None:
        """After max_retries+1 transient failures, raise LLMError."""
        client = LLMClient(api_key="test-key")  # max_retries=1
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            import httpx
            raise httpx.TimeoutException("always times out")

        with patch("httpx.request", side_effect=side_effect):
            with pytest.raises(LLMError, match="after 2 attempts"):
                client.chat([{"role": "user", "content": "hi"}])

        # max_retries=1 -> 2 attempts (initial + 1 retry)
        assert call_count == 2


# ---------------------------------------------------------------------------
# Test: LLMRetryableError is a subclass of LLMError (backward compat)
# ---------------------------------------------------------------------------


def test_retryable_error_is_llm_error_subclass() -> None:
    """LLMRetryableError IS-A LLMError for existing except LLMError handlers."""
    exc = LLMRetryableError("transient")
    assert isinstance(exc, LLMError)
    assert isinstance(exc, LLMRetryableError)
