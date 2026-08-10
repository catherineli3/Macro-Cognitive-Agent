"""Narrative Engine — Synthesize cognitive chain output into MacroNarrative.

MVP output: MacroNarrative Schema (structured, NOT Markdown).
CLI/API/Dashboard each consume MacroNarrative and render their own format.

Dependencies: schemas, domain, shared
"""

from .engine import NarrativeEngine

__all__ = [
    "NarrativeEngine",
]
