"""Tool Layer — Agent capability to external systems (Sprint 5).

Architecture:
    Handler  →  ToolManager  →  ToolRegistry  →  BaseTool  →  External System
                                    ↓
                              ToolResult (canonical artifacts)

Key principles:
    - Every Tool implements BaseTool (async execute → ToolResult)
    - ToolRegistry maps capability string → Tool instance
    - ToolManager is the ONLY entry point Handlers interact with
    - No Handler directly imports or instantiates a Tool
    - All external data is translated to canonical schema before return
    - Tool failures return ToolResult(FAILED), never raw exceptions

Canonical Data Layer:
    Yahoo returns JSON. FRED returns XML. SEC returns HTML.
    NONE of these reaches the Agent.
    Every Tool translates vendor-specific data → MacroDataSchema before return.
"""

from src.tools.base import BaseTool
from src.tools.manager import ToolManager
from src.tools.registry import ToolRegistry
from src.tools.yahoo_tool import YahooMacroTool

__all__ = [
    "BaseTool",
    "ToolRegistry",
    "ToolManager",
    "YahooMacroTool",
]
