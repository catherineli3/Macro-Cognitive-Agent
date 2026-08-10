"""Kimi API client — OpenAI-compatible interface with timeout, retry, error handling.

Environment variables:
  KIMI_BASE_URL  — default https://api.moonshot.cn/v1
  KIMI_API_KEY   — required for LLM features
  KIMI_MODEL     — default moonshot-v1-8k

All errors are wrapped in LLMError; callers handle degradation.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx


class LLMError(Exception):
    """Unified exception for all LLM-related failures (network, auth, schema, etc.)."""


class LLMRetryableError(LLMError):
    """Transient failures that warrant a retry: timeout, network hiccup, HTTP 429."""


class LLMClient:
    """Minimal Kimi API wrapper with 10s timeout + 1 automatic retry."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("KIMI_API_KEY", "")
        self.model = model or os.getenv("KIMI_MODEL", "moonshot-v1-8k")
        self._timeout = 10.0
        self._max_retries = 1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.3) -> str:
        """Send chat completion request; returns content string or raises LLMError."""
        if not self.api_key:
            raise LLMError("KIMI_API_KEY is not set — LLM features unavailable")

        return self._request(
            "POST",
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            },
            extract_key="choices.0.message.content",
        )

    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """chat() + parse JSON response. Raises LLMError on parse failure."""
        raw = self.chat(messages, temperature=temperature)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM returned invalid JSON: {exc}") from exc

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        url: str,
        json: dict[str, Any] | None = None,
        extract_key: str | None = None,
    ) -> str:
        """Execute HTTP request with retry logic."""
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                return self._do_request(method, url, json, extract_key)
            except LLMRetryableError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise LLMError(
                    f"LLM request failed after {self._max_retries + 1} attempts"
                ) from exc
            except LLMError:
                raise  # non-retryable: auth, schema, etc.

    def _do_request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None = None,
        extract_key: str | None = None,
    ) -> str:
        """Single HTTP request. Extracts nested value via dotted extract_key."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = httpx.request(
                method=method,
                url=url,
                json=body,
                headers=headers,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMRetryableError(f"LLM request timed out after {self._timeout}s") from exc
        except httpx.RequestError as exc:
            raise LLMRetryableError(f"LLM network error: {exc}") from exc

        if response.status_code != 200:
            self._raise_status(response)

        data = response.json()
        return self._extract(data, extract_key)

    @staticmethod
    def _raise_status(response: httpx.Response) -> None:
        """Map HTTP status to LLMError."""
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        status = response.status_code
        if status == 401 or status == 403:
            raise LLMError(f"LLM authentication failed (HTTP {status}): {detail}")
        if status == 429:
            raise LLMRetryableError(f"LLM rate limited (HTTP 429): {detail}")
        raise LLMError(f"LLM API error (HTTP {status}): {detail}")

    @staticmethod
    def _extract(data: dict[str, Any], path: str | None) -> str:
        """Navigate dotted path (e.g. 'choices.0.message.content') in JSON dict."""
        if not path:
            return str(data)
        current: Any = data
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (IndexError, ValueError):
                    raise LLMError(f"LLM response missing expected key '{path}'")
            if current is None:
                raise LLMError(f"LLM response missing expected key '{path}'")
        return str(current)
