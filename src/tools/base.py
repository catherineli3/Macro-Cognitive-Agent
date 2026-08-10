"""BaseTool — Abstract contract for all Tools in the Agent Tool Layer.

Sprint 5 design:
    A Tool is a pluggable capability unit that communicates with an external
    system. Every Tool must:

    1. Declare its capability string (for routing)
    2. Declare its name (for logging/audit)
    3. Execute asynchronously and return ToolResult

    Tools are STATELESS. They receive input, perform an external operation,
    translate the result into the Agent's canonical schema, and return a
    ToolResult. Tools must NEVER return raw vendor-specific data.

    Principle (Canonical Data Layer):
        Yahoo returns JSON. FRED returns XML. SEC returns HTML.
        NONE of these should reach the Agent.
        Every Tool is responsible for translating external data into
        the Agent's internal canonical schema before returning ToolResult.

    Future compatibility:
        Adding a new Tool (FRED, Bloomberg, Wind, etc.) should require
        ZERO changes to Planner, Executor, or Handler.
"""

from abc import ABC, abstractmethod

from src.schemas.tool import ToolResult


class BaseTool(ABC):
    """Contract for every Agent Tool.

    All tools implement this interface. ToolManager uses capability()
    for lookup and execute() for invocation. No Tool is ever instantiated
    or called directly by Handlers — all access goes through ToolManager.

    Usage:
        class MyTool(BaseTool):
            def tool_name(self) -> str:
                return "MyTool"

            def capability(self) -> str:
                return "vendor.my_source"

            async def execute(self, input_data: dict) -> ToolResult:
                # 1. Call external system
                # 2. Transform to canonical schema
                # 3. Return ToolResult
                ...
    """

    @abstractmethod
    def tool_name(self) -> str:
        """Unique human-readable tool name for logging/debugging.

        Examples: "YahooMacroTool", "FredTool", "BloombergTool".
        """
        ...

    @abstractmethod
    def capability(self) -> str:
        """Capability key for ToolManager lookup.

        Examples:
            "macro.yahoo"       — Yahoo Finance macro data
            "macro.fred"        — FRED economic data
            "macro.bloomberg"   — Bloomberg terminal data
            "macro.wind"        — Wind financial data
            "sec.filing"        — SEC EDGAR filings
            "news.google"       — Google News search
            "worldbank.data"    — World Bank indicators

        This is the same capability namespace used by Handlers.
        """
        ...

    @abstractmethod
    async def execute(self, input_data: dict) -> ToolResult:
        """Execute this tool against the given input.

        Args:
            input_data: Tool-specific parameters (e.g., {"symbol": "DXY",
                        "period": "1mo"}). Structure defined per-tool.

        Returns:
            ToolResult with canonical artifacts and execution metadata.
            Must NEVER raise business exceptions — failures are returned
            as ToolResult with status=FAILED.

        Implementation MUST:
            1. Call the external system
            2. Translate raw response → canonical schema (MacroDataSchema etc.)
            3. Return ToolResult (SUCCESS or FAILED)
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.tool_name()} capability={self.capability()}>"
