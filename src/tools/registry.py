"""ToolRegistry — Capability → Tool mapping with zero business logic.

Sprint 5 design:
    ToolRegistry is a pure lookup table. It maps capability strings to
    concrete BaseTool instances.

    No business logic. No execution logic. No scheduling.
    Only registration and lookup.

    This is deliberately minimal. A future Sprint could add:
        - Lazy tool instantiation
        - Tool health checks
        - Capability versioning
        - Dynamic tool discovery

    But Sprint 5 keeps it to the bare minimum that satisfies YAGNI.
"""

from src.tools.base import BaseTool


class ToolRegistry:
    """Maps capability strings to Tool instances.

    Usage:
        registry = ToolRegistry()
        registry.register(YahooMacroTool())
        tool = registry.get("macro.yahoo")
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    # ── Registration ─────────────────────────────────────────────────────────

    def register(self, tool: BaseTool) -> "ToolRegistry":
        """Register a tool instance.

        Args:
            tool: A concrete BaseTool implementation.

        Returns:
            Self for fluent chaining.

        Raises:
            ValueError: If a tool is already registered for this capability.
        """
        capability = tool.capability()
        if capability in self._tools:
            existing = self._tools[capability].tool_name()
            raise ValueError(
                f"Tool already registered for capability '{capability}': "
                f"{existing} (tried to register {tool.tool_name()})"
            )
        self._tools[capability] = tool
        return self

    # ── Lookup ───────────────────────────────────────────────────────────────

    def get(self, capability: str) -> BaseTool:
        """Retrieve a tool by capability string.

        Args:
            capability: Tool capability key (e.g., "macro.yahoo").

        Returns:
            The registered BaseTool instance.

        Raises:
            KeyError: If no tool is registered for this capability.
        """
        if capability not in self._tools:
            raise KeyError(
                f"No tool registered for capability '{capability}'. "
                f"Registered: {list(self._tools.keys())}"
            )
        return self._tools[capability]

    def has(self, capability: str) -> bool:
        """Check if a tool is registered for a given capability."""
        return capability in self._tools

    @property
    def capabilities(self) -> set[str]:
        """Set of all registered capability strings."""
        return set(self._tools.keys())

    @property
    def tool_count(self) -> int:
        """Number of registered tools."""
        return len(self._tools)

    def __len__(self) -> int:
        return self.tool_count

    def __contains__(self, capability: str) -> bool:
        return self.has(capability)

    def __repr__(self) -> str:
        return f"<ToolRegistry tools={list(self._tools.keys())}>"
