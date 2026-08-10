"""LLM integration layer — Kimi API wrapper + narrative engine.

Design:
  - Deterministic engines handle computation & judgment.
  - LLM layer handles expression & historical association.
  - LLM failure auto-degrades to template-based engine, pipeline never crashes.
"""

from src.llm.client import LLMClient, LLMError
from src.llm.narrative import LLMNarrativeEngine, LLMNarrativeResult

__all__ = [
    "LLMClient",
    "LLMError",
    "LLMNarrativeEngine",
    "LLMNarrativeResult",
]
