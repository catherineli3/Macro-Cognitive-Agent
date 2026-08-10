"""Tests for ToolManager — single entry point for Handlers."""
import pytest

from src.tools.base import BaseTool
from src.tools.registry import ToolRegistry
from src.tools.manager import ToolManager
from src.schemas.tool import ToolResult
from src.domain.tool import ToolResultStatus


# ── Test Tools ─────────────────────────────────────────────────────────────


class _SuccessTool(BaseTool):
    def tool_name(self) -> str:
        return "SuccessTool"

    def capability(self) -> str:
        return "test.success"

    async def execute(self, input_data: dict) -> ToolResult:
        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            tool_name=self.tool_name(),
            artifact={"result": input_data},
            latency_ms=42.0,
        )


class _FailingTool(BaseTool):
    def tool_name(self) -> str:
        return "FailingTool"

    def capability(self) -> str:
        return "test.failing"

    async def execute(self, input_data: dict) -> ToolResult:
        return ToolResult(
            status=ToolResultStatus.FAILED,
            tool_name=self.tool_name(),
            error="Intended failure",
            latency_ms=10.0,
        )


class _CrashingTool(BaseTool):
    def tool_name(self) -> str:
        return "CrashingTool"

    def capability(self) -> str:
        return "test.crashing"

    async def execute(self, input_data: dict) -> ToolResult:
        raise RuntimeError("Boom!")


class _NoLatencyTool(BaseTool):
    """Tool that doesn't set latency_ms — Manager should fill it."""

    def tool_name(self) -> str:
        return "NoLatencyTool"

    def capability(self) -> str:
        return "test.nolatency"

    async def execute(self, input_data: dict) -> ToolResult:
        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            tool_name=self.tool_name(),
            artifact={"data": "ok"},
        )


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def empty_manager() -> ToolManager:
    registry = ToolRegistry()
    return ToolManager(registry)


@pytest.fixture
def populated_manager() -> ToolManager:
    registry = ToolRegistry()
    registry.register(_SuccessTool())
    registry.register(_FailingTool())
    registry.register(_CrashingTool())
    registry.register(_NoLatencyTool())
    return ToolManager(registry)


# ── Tests ─────────────────────────────────────────────────────────────────


class TestToolManagerCapabilityQueries:
    """ToolManager: capability checks."""

    def test_empty_manager_no_capabilities(self, empty_manager):
        assert empty_manager.has_capability("any") is False
        assert empty_manager.list_capabilities() == set()

    def test_populated_manager_capabilities(self, populated_manager):
        assert populated_manager.has_capability("test.success") is True
        assert populated_manager.has_capability("nonexistent") is False
        caps = populated_manager.list_capabilities()
        assert "test.success" in caps
        assert "test.failing" in caps
        assert "test.crashing" in caps


class TestToolManagerExecution:
    """ToolManager: execute() path — success, failure, exceptions."""

    @pytest.mark.asyncio
    async def test_successful_execution(self, populated_manager):
        result = await populated_manager.execute(
            "test.success", {"symbol": "DXY"}
        )
        assert result.is_success is True
        assert result.status == ToolResultStatus.SUCCESS
        assert result.tool_name == "SuccessTool"
        assert result.artifact == {"result": {"symbol": "DXY"}}
        assert result.latency_ms >= 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_tool_returned_failure(self, populated_manager):
        """Manager passes through ToolResult.FAILED from the tool."""
        result = await populated_manager.execute("test.failing", {})
        assert result.is_success is False
        assert result.status == ToolResultStatus.FAILED
        assert result.tool_name == "FailingTool"
        assert result.error == "Intended failure"
        assert result.artifact == {}

    @pytest.mark.asyncio
    async def test_crashing_tool_caught(self, populated_manager):
        """Tool exception → Manager returns FAILED ToolResult (no crash)."""
        result = await populated_manager.execute("test.crashing", {})
        assert result.is_success is False
        assert result.status == ToolResultStatus.FAILED
        assert result.tool_name == "CrashingTool"
        assert "RuntimeError" in result.error
        assert "Boom" in result.error
        assert result.artifact == {}

    @pytest.mark.asyncio
    async def test_unknown_capability(self, empty_manager):
        """Calling unknown capability returns FAILED ToolResult."""
        result = await empty_manager.execute("macro.nonexistent", {})
        assert result.is_success is False
        assert result.status == ToolResultStatus.FAILED
        assert "No tool registered" in result.error
        assert result.artifact == {}

    @pytest.mark.asyncio
    async def test_latency_auto_filled(self, populated_manager):
        """If tool doesn't set latency_ms, Manager fills it."""
        result = await populated_manager.execute("test.nolatency", {})
        assert result.is_success is True
        assert result.latency_ms > 0  # Manager computed it
        assert result.artifact == {"data": "ok"}

    @pytest.mark.asyncio
    async def test_result_has_completed_at(self, populated_manager):
        """Every ToolResult has a completed_at timestamp."""
        result = await populated_manager.execute("test.success", {})
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_manager_never_raises(self, populated_manager):
        """ToolManager.execute() must never raise — all errors become ToolResult."""
        # Unknown capability
        r1 = await populated_manager.execute("bad", {})
        assert r1.is_failed is True

        # Crashing tool
        r2 = await populated_manager.execute("test.crashing", {})
        assert r2.is_failed is True

        # Normal failure
        r3 = await populated_manager.execute("test.failing", {})
        assert r3.is_failed is True

        # Success
        r4 = await populated_manager.execute("test.success", {"k": "v"})
        assert r4.is_success is True

        # All were ToolResult objects — no exceptions leaked
        for r in [r1, r2, r3, r4]:
            assert isinstance(r, ToolResult)


class TestToolManagerHandlerBoundary:
    """ToolManager is the ONLY component Handlers should interact with."""

    @pytest.mark.asyncio
    async def test_handler_uses_manager_not_tool_directly(self, populated_manager):
        """Simulate a Handler calling Manager.execute() — no direct tool access."""
        capability = "test.success"
        input_data = {"symbol": "^VIX", "period": "1mo"}

        # This is what a Handler does:
        result = await populated_manager.execute(capability, input_data)
        assert result.is_success is True
        assert result.artifact == {"result": input_data}
