"""Tests for ToolRegistry — capability → Tool mapping."""
import pytest

from src.tools.base import BaseTool
from src.tools.registry import ToolRegistry
from src.schemas.tool import ToolResult
from src.domain.tool import ToolResultStatus


class _MockTool(BaseTool):
    """Minimal tool implementation for testing."""
    def tool_name(self) -> str:
        return self._name

    def capability(self) -> str:
        return self._cap

    async def execute(self, input_data: dict) -> ToolResult:
        return ToolResult(status=ToolResultStatus.SUCCESS, tool_name=self._name)

    def __init__(self, name: str, cap: str):
        self._name = name
        self._cap = cap


class TestToolRegistry:
    """ToolRegistry: registration, lookup, error cases."""

    def test_initial_empty(self):
        registry = ToolRegistry()
        assert registry.tool_count == 0
        assert registry.capabilities == set()
        assert len(registry) == 0

    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = _MockTool("ToolA", "macro.test_a")
        registry.register(tool)
        assert registry.tool_count == 1
        assert registry.has("macro.test_a") is True
        assert "macro.test_a" in registry
        assert registry.get("macro.test_a") is tool

    def test_register_multiple(self):
        registry = ToolRegistry()
        t1 = _MockTool("A", "macro.a")
        t2 = _MockTool("B", "macro.b")
        registry.register(t1).register(t2)
        assert registry.tool_count == 2
        assert registry.capabilities == {"macro.a", "macro.b"}

    def test_fluent_registration(self):
        registry = ToolRegistry()
        registry.register(_MockTool("A", "a")).register(_MockTool("B", "b")).register(
            _MockTool("C", "c")
        )
        assert len(registry) == 3

    def test_duplicate_capability_raises(self):
        registry = ToolRegistry()
        registry.register(_MockTool("A", "macro.x"))
        with pytest.raises(ValueError, match="already registered"):
            registry.register(_MockTool("B", "macro.x"))

    def test_get_unknown_capability_raises(self):
        registry = ToolRegistry()
        with pytest.raises(KeyError, match="macro.unknown"):
            registry.get("macro.unknown")

    def test_has_unknown_capability(self):
        registry = ToolRegistry()
        assert registry.has("nonexistent") is False
        assert ("nonexistent" in registry) is False

    def test_no_business_logic(self):
        """ToolRegistry is pure lookup — no execution or transformation."""
        registry = ToolRegistry()
        registry.register(_MockTool("Tool", "macro.test"))
        # get() returns the raw tool, not a wrapper
        tool = registry.get("macro.test")
        assert isinstance(tool, BaseTool)
        assert tool.capability() == "macro.test"

    def test_repr(self):
        registry = ToolRegistry()
        registry.register(_MockTool("Yahoo", "macro.yahoo"))
        r = repr(registry)
        assert "macro.yahoo" in r
