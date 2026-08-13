"""(Unit) LLMClient retry logic: verify LLMRetryableError triggers retry."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.llm.client import LLMClient, LLMError, LLMRetryableError


class TestRetryOnTransientErrors:
    """LLMRetryableError (timeout / network / 429) triggers retry;
    non-retryable errors raise immediately."""

    def test_retry_on_first_retryable_then_success(self) -> None:
        """First call raises LLMRetryableError, second succeeds.
        Verifies retry mechanism actually fires — the key bug was that
        _request caught LLMError and re-raised immediately.
        """
        client = LLMClient(api_key="test-key")
        retries_spent: list[int] = []

        def side_effect(method, url, body, extract_key):
            retries_spent.append(1)
            if len(retries_spent) == 1:
                raise LLMRetryableError("simulated transient")
            return '{"ok": true}'

        with patch.object(client, "_do_request", side_effect=side_effect):
            result = client.chat([{"role": "user", "content": "hi"}])

        assert len(retries_spent) == 2
        assert result == '{"ok": true}'

    def test_no_retry_on_auth_error(self) -> None:
        """Non-retryable LLMError (e.g. auth) raises immediately, 1 call only."""
        client = LLMClient(api_key="test-key")
        call_count = 0

        def side_effect(method, url, body, extract_key):
            nonlocal call_count
            call_count += 1
            raise LLMError("invalid auth")

        with patch.object(client, "_do_request", side_effect=side_effect):
            with pytest.raises(LLMError, match="invalid auth"):
                client.chat([{"role": "user", "content": "hi"}])

        assert call_count == 1

    def test_raises_after_max_retries_exceeded(self) -> None:
        """max_retries=1 → 2 attempts total, then raise LLMError."""
        client = LLMClient(api_key="test-key")
        call_count = 0

        def side_effect(method, url, body, extract_key):
            nonlocal call_count
            call_count += 1
            raise LLMRetryableError("always transient")

        with patch.object(client, "_do_request", side_effect=side_effect):
            with pytest.raises(LLMError, match="after 2 attempts"):
                client.chat([{"role": "user", "content": "hi"}])

        assert call_count == 2


def test_retryable_error_is_llm_error_subclass() -> None:
    """LLMRetryableError IS-A LLMError for existing except LLMError handlers."""
    exc = LLMRetryableError("transient")
    assert isinstance(exc, LLMError)
    assert isinstance(exc, LLMRetryableError)
