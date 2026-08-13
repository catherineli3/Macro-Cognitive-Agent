"""Renderer — Presentation layer for MacroNarrative.

Beta: Separate rendering from cognitive pipeline per DDR-010.
All renderers consume MacroNarrative schema, never raw pipeline artifacts.

Supported formats:
    markdown — Full 12-section research report
    json     — Machine-readable structured output
    plaintext — Human-readable without formatting

Future: HTML, PDF
"""

from .json_renderer import JsonRenderer
from .markdown import MarkdownRenderer

__all__ = [
    "MarkdownRenderer",
    "JsonRenderer",
]
