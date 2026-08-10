from __future__ import annotations

"""ToolManager — Single entry point for all Tool access.

Sprint 5 design:
    ToolManager is the ONLY component that Handlers interact with for
    external capabilities. It enforces:

    1. Handlers NEVER instantiate or import tools directly.
    2. ALL tool access goes through ToolManager.
    3. ALL tool exceptions are caught and converted to ToolResult.
    4. No raw vendor data leaks past this layer.

    Architecture:
        Handler
          ↓
        ToolManager     ← Single entry point
          ↓
        ToolRegistry    ← Capability lookup
          ↓
        YahooTool       ← Actual execution
          ↓
        ToolResult      ← Canonical output

    ToolManager responsibilities:
        - Find Tool by capability
        - Execute Tool
        - Return ToolResult
        - Convert Tool exceptions into ToolResult (FAILED)
        - Logging

    No scheduling. No planning. No business logic.
"""

import time

from src.schemas.tool import ToolResult
from src.domain.tool import ToolResultStatus
from src.shared.logging import get_logger
from src.tools.base import BaseTool
from src.tools.registry import ToolRegistry

logger = get_logger(__name__)


class ToolManager:
    """Orchestrates tool access for the Agent.

    Handlers interact ONLY with ToolManager. They never:
      - Import tool classes directly
      - Instantiate tools
      - Handle raw tool exceptions

    Usage:
        registry = ToolRegistry()
        registry.register(YahooMacroTool())
        mgr = ToolManager(registry)

        result = await mgr.execute("macro.yahoo", {"symbol": "DXY"})
        if result.is_success:
            data = result.artifact["macro_data"]
    """

    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize with a pre-configured ToolRegistry.

        Args:
            registry: Registry containing all available tools.
        """
        self._registry = registry

    # ── Main Entry Point ─────────────────────────────────────────────────────

    async def execute(self, capability: str, input_data: dict) -> ToolResult:
        """Execute a tool by capability.

        This is the single entry point for all tool access. Handlers call
        this method with a capability string and input parameters.

        Args:
            capability: Tool capability key (e.g., "macro.yahoo").
            input_data: Tool-specific parameters (e.g., {"symbol": "DXY",
                        "period": "1mo"}).

        Returns:
            ToolResult wrapping canonical artifacts or failure information.
            NEVER raises — all errors are returned as ToolResult(FAILED).
        """
        start = time.perf_counter()

        # Step 1: Find tool
        tool = self._resolve_tool(capability)
        if tool is None:
            return self._not_found_result(capability, start)

        # Step 2: Execute
        logger.info(
            "tool_execute_start tool=%s capability=%s input_keys=%s",
            tool.tool_name(),
            capability,
            list(input_data.keys()),
        )
        try:
            result = await tool.execute(input_data)
        except Exception as exc:
            result = self._exception_result(tool, exc, start)

        # Step 3: Normalize timing
        self._fill_latency(result, start)

        logger.info(
            "tool_execute_done tool=%s capability=%s status=%s latency_ms=%.1f artifacts=%s",
            result.tool_name,
            capability,
            result.status.value,
            result.latency_ms,
            list(result.artifact.keys()),
        )
        return result

    # ── Capability Queries ───────────────────────────────────────────────────

    def has_capability(self, capability: str) -> bool:
        """Check if a tool is available for the given capability."""
        return self._registry.has(capability)

    def list_capabilities(self) -> set[str]:
        """Return all registered capability strings."""
        return self._registry.capabilities

    # ── Private ──────────────────────────────────────────────────────────────

    def _resolve_tool(self, capability: str) -> BaseTool | None:
        """Look up a tool by capability. Returns None if not found."""
        try:
            return self._registry.get(capability)
        except KeyError:
            return None

    def _not_found_result(self, capability: str, start: float) -> ToolResult:
        """Build a FAILED ToolResult for an unknown capability."""
        latency = (time.perf_counter() - start) * 1000
        available = list(self._registry.capabilities)
        logger.warning(
            "tool_not_found capability=%s available=%s",
            capability,
            available,
        )
        return ToolResult(
            status=ToolResultStatus.FAILED,
            tool_name="unknown",
            artifact={},
            latency_ms=round(latency, 2),
            error=(f"No tool registered for capability '{capability}'. "
                   f"Available: {available}"),
        )

    def _exception_result(
        self, tool: BaseTool, exc: Exception, start: float
    ) -> ToolResult:
        """Build a FAILED ToolResult from a tool exception."""
        latency = (time.perf_counter() - start) * 1000
        logger.error(
            "tool_exception tool=%s capability=%s error=%s",
            tool.tool_name(),
            tool.capability(),
            exc,
        )
        return ToolResult(
            status=ToolResultStatus.FAILED,
            tool_name=tool.tool_name(),
            artifact={},
            latency_ms=round(latency, 2),
            error=f"{type(exc).__name__}: {exc}",
        )

    def _fill_latency(self, result: ToolResult, start: float) -> None:
        """Ensure ToolResult has accurate latency if not set by the tool."""
        if result.latency_ms == 0.0:
            result.latency_ms = round((time.perf_counter() - start) * 1000, 2)

    def __repr__(self) -> str:
        return f"<ToolManager capabilities={list(self._registry.capabilities)}>"
