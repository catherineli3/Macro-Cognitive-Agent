"""LLM Client — Abstraction layer for multiple LLM providers.

Supports multiple backends (OpenAI-compatible, Anthropic, local models)
with a unified interface. The ResearchReasoningAgent uses this for all
LLM calls, enabling provider-agnostic operation.

Design:
    - LLMResponse: Normalized response format
    - LLMClient: Provider abstraction with auto-detection
    - Supports OpenAI, Anthropic, Google, and local (Ollama/vLLM) backends
    - Automatic JSON extraction from LLM responses
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Callable

from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Response type
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class LLMResponse:
    """Normalized LLM response across all providers."""

    content: str = ""
    parsed_json: Optional[dict] = None
    model: str = ""
    provider: str = ""
    elapsed_ms: float = 0.0
    tokens_used: int = 0
    finish_reason: str = ""  # "stop", "length", "error"
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and self.finish_reason in ("stop", "")


# ═══════════════════════════════════════════════════════════════════════════
# JSON extraction utilities
# ═══════════════════════════════════════════════════════════════════════════


def extract_json_from_text(text: str) -> Optional[dict]:
    """Extract JSON object from LLM text output.

    Handles:
        - Pure JSON
        - JSON inside ```json ... ``` blocks
        - JSON inside ``` ... ``` blocks
        - JSON with trailing commas or comments
    """
    if not text:
        return None

    # Try pure JSON first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from ```json blocks
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try extracting from { ... } blocks (greedy, takes the outermost)
    brace_count = 0
    start_idx = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif ch == "}":
            brace_count -= 1
            if brace_count == 0 and start_idx >= 0:
                candidate = text[start_idx : i + 1]
                try:
                    # Clean common issues
                    cleaned = re.sub(r",\s*}", "}", candidate)
                    cleaned = re.sub(r",\s*]", "]", cleaned)
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass

    return None


# ═══════════════════════════════════════════════════════════════════════════
# Provider registry
# ═══════════════════════════════════════════════════════════════════════════


class LLMClient:
    """Unified LLM client supporting multiple providers.

    Usage:
        client = LLMClient(model="gpt-4o")  # Auto-detects provider
        # or
        client = LLMClient(provider="openai", model="gpt-4o", api_key="...")

        response = client.chat(
            messages=[{"role": "system", "content": "..."},
                      {"role": "user", "content": "..."}],
            temperature=0.3,
        )

        if response.success:
            print(response.content)
            print(response.parsed_json)  # Auto-extracted
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        provider: str = "",
        api_key: str = "",
        base_url: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        timeout: int = 120,
    ):
        """Initialize LLM client.

        Args:
            model: Model name (e.g. "gpt-4o", "claude-3-opus", "deepseek-v3")
            provider: "openai" / "anthropic" / "deepseek" / "local". Auto-detect if empty.
            api_key: Provider API key. Reads from env var if empty.
            base_url: Custom API base URL for self-hosted/proxy.
            temperature: Default temperature for generation.
            max_tokens: Max output tokens.
            timeout: Request timeout in seconds.
        """
        self.model = model
        self.provider = provider or self._detect_provider(model)
        self.api_key = api_key or self._get_api_key(self.provider)
        self.base_url = base_url or self._get_base_url(self.provider)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

        self._client: Any = None
        self._initialized = False

    # ── Provider detection ───────────────────────────────────────────

    @staticmethod
    def _detect_provider(model: str) -> str:
        """Auto-detect provider from model name."""
        model_lower = model.lower()
        if any(x in model_lower for x in ["gpt", "o1", "o3", "o4"]):
            return "openai"
        if any(x in model_lower for x in ["claude"]):
            return "anthropic"
        if any(x in model_lower for x in ["gemini"]):
            return "google"
        if any(x in model_lower for x in ["deepseek"]):
            return "deepseek"
        if any(x in model_lower for x in ["glm", "chatglm"]):
            return "zhipu"
        if any(x in model_lower for x in ["qwen"]):
            return "qwen"
        if any(x in model_lower for x in ["moonshot"]):
            return "moonshot"
        # Default: OpenAI-compatible (works for most local models)
        return "openai"

    @staticmethod
    def _get_api_key(provider: str) -> str:
        """Get API key from environment."""
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
            "qwen": "QWEN_API_KEY",
            "moonshot": "MOONSHOT_API_KEY",
            "local": "LOCAL_LLM_API_KEY",
        }
        return os.environ.get(env_map.get(provider, ""), "")

    @staticmethod
    def _get_base_url(provider: str) -> str:
        """Get base URL for provider."""
        url_map = {
            "openai": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "deepseek": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "zhipu": os.environ.get("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
            "moonshot": os.environ.get("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1"),
            "local": os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1"),
        }
        return url_map.get(provider, os.environ.get("LLM_BASE_URL", ""))

    # ── Initialization ────────────────────────────────────────────────

    def _ensure_client(self) -> None:
        """Lazily initialize the provider-specific client."""
        if self._initialized:
            return

        try:
            if self.provider in ("openai", "deepseek", "zhipu", "qwen", "moonshot", "local"):
                self._init_openai_compatible()
            elif self.provider == "anthropic":
                self._init_anthropic()
            elif self.provider == "google":
                self._init_google()
            else:
                # Fallback to OpenAI-compatible
                self._init_openai_compatible()

            self._initialized = True
        except ImportError as e:
            logger.warning(
                "LLM provider '%s' not available: %s. Will use mock responses.",
                self.provider, e,
            )
            self._initialized = True  # Don't keep trying

    def _init_openai_compatible(self) -> None:
        """Initialize OpenAI-compatible client (works for OpenAI, DeepSeek, etc.)."""
        try:
            from openai import OpenAI

            kwargs = {}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.base_url:
                kwargs["base_url"] = self.base_url

            self._client = OpenAI(**kwargs)
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

    def _init_anthropic(self) -> None:
        """Initialize Anthropic client."""
        try:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

    def _init_google(self) -> None:
        """Initialize Google Gemini client."""
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._client = genai
        except ImportError:
            raise ImportError(
                "google-generativeai package not installed. Run: pip install google-generativeai"
            )

    # ── Public API ────────────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        parse_json: bool = True,
    ) -> LLMResponse:
        """Send a chat completion request.

        Args:
            messages: Standard [{"role": "...", "content": "..."}] format.
            temperature: Override default temperature.
            max_tokens: Override default max_tokens.
            parse_json: Automatically extract JSON from response.

        Returns:
            LLMResponse with content and optional parsed JSON.
        """
        t0 = time.time()

        try:
            self._ensure_client()

            if self._client is None:
                return LLMResponse(
                    error="LLM client not available. Check API key and package installation.",
                    finish_reason="error",
                )

            temp = temperature if temperature is not None else self.temperature
            mt = max_tokens if max_tokens is not None else self.max_tokens

            if self.provider == "anthropic":
                return self._chat_anthropic(messages, temp, mt, t0, parse_json)
            elif self.provider == "google":
                return self._chat_google(messages, temp, mt, t0, parse_json)
            else:
                return self._chat_openai_compatible(messages, temp, mt, t0, parse_json)

        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            logger.error("LLM call failed: %s (%.0fms)", e, elapsed)
            return LLMResponse(
                error=str(e),
                finish_reason="error",
                elapsed_ms=elapsed,
                model=self.model,
                provider=self.provider,
            )

    def _chat_openai_compatible(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        t0: float,
        parse_json: bool,
    ) -> LLMResponse:
        """Call OpenAI-compatible API."""
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=self.timeout,
        )

        elapsed = (time.time() - t0) * 1000
        choice = response.choices[0]
        content = choice.message.content or ""

        parsed = extract_json_from_text(content) if parse_json else None

        return LLMResponse(
            content=content,
            parsed_json=parsed,
            model=self.model,
            provider=self.provider,
            elapsed_ms=elapsed,
            tokens_used=response.usage.total_tokens if response.usage else 0,
            finish_reason=choice.finish_reason or "stop",
        )

    def _chat_anthropic(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        t0: float,
        parse_json: bool,
    ) -> LLMResponse:
        """Call Anthropic API."""
        # Convert to Anthropic format
        system_msg = ""
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                user_messages.append(m)

        response = self._client.messages.create(
            model=self.model,
            system=system_msg,
            messages=user_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        elapsed = (time.time() - t0) * 1000
        content = response.content[0].text if response.content else ""

        parsed = extract_json_from_text(content) if parse_json else None

        return LLMResponse(
            content=content,
            parsed_json=parsed,
            model=self.model,
            provider=self.provider,
            elapsed_ms=elapsed,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            finish_reason=response.stop_reason or "stop",
        )

    def _chat_google(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        t0: float,
        parse_json: bool,
    ) -> LLMResponse:
        """Call Google Gemini API."""
        model = self._client.GenerativeModel(self.model)

        # Convert to Google format
        contents = []
        for m in messages:
            contents.append({"role": "user" if m["role"] != "assistant" else "model",
                             "parts": [m["content"]]})

        response = model.generate_content(
            contents,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )

        elapsed = (time.time() - t0) * 1000
        content = response.text or ""

        parsed = extract_json_from_text(content) if parse_json else None

        return LLMResponse(
            content=content,
            parsed_json=parsed,
            model=self.model,
            provider=self.provider,
            elapsed_ms=elapsed,
            finish_reason="stop",
        )

    # ── Convenience methods ───────────────────────────────────────────

    def research_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """Convenience: System + User chat with default research settings."""
        return self.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            parse_json=True,
        )

    def health_check(self) -> dict:
        """Check if the LLM client is operational."""
        try:
            self._ensure_client()
            return {
                "status": "ok" if self._client else "unavailable",
                "provider": self.provider,
                "model": self.model,
                "has_api_key": bool(self.api_key),
                "base_url": self.base_url,
            }
        except Exception as e:
            return {
                "status": "error",
                "provider": self.provider,
                "model": self.model,
                "error": str(e),
            }
