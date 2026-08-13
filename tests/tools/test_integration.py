"""Integration tests: ToolManager + YahooTool → canonical data flow.

Tests the full Tool Layer pipeline:
    1. ToolRegistry registers YahooMacroTool
    2. ToolManager executes "macro.yahoo"
    3. YahooMacroTool translates yfinance → MacroDataSchema
    4. ToolResult artifact is canonical (no raw data leakage)

Also tests ToolManager + Handler integration pattern.
"""

from unittest.mock import patch

import pandas as pd
import pytest

from src.domain.execution import TaskResultStatus
from src.domain.planning import TaskType
from src.schemas.execution import TaskResult
from src.schemas.macro_data import MacroDataSchema
from src.schemas.planning import Task
from src.tools.base import BaseTool
from src.tools.manager import ToolManager
from src.tools.registry import ToolRegistry
from src.tools.yahoo_tool import YahooMacroTool

# ── Helpers ──────────────────────────────────────────────────────────────


def _make_mock_df():
    dates = pd.date_range("2026-07-08", periods=3, freq="B", tz="UTC")
    return pd.DataFrame(
        {
            "Open": [104.0, 104.5, 105.0],
            "High": [105.0, 105.5, 106.0],
            "Low": [103.5, 104.0, 104.5],
            "Close": [104.5, 105.0, 105.3],
            "Volume": [10000, 12000, 11000],
            "Dividends": [0, 0, 0],
            "Stock Splits": [0, 0, 0],
        },
        index=dates,
    )


def _make_task(
    task_id: str = "t1",
    capability: str = "macro.yahoo",
    config_extra: dict | None = None,
) -> Task:
    config = {"capability": capability, **(config_extra or {})}
    return Task(
        id=task_id,
        name=task_id,
        description="Test task",
        type=TaskType.RETRIEVE,
        config=config,
    )


# ── Integration Tests ───────────────────────────────────────────────────


class TestFullToolPipeline:
    """End-to-end: Registry → Manager → Tool → Canonical Artifact."""

    @pytest.mark.asyncio
    async def test_full_pipeline_success(self):
        """Registry→Manager→YahooTool→MacroDataSchema (mocked)."""
        # Setup
        registry = ToolRegistry()
        registry.register(YahooMacroTool())
        manager = ToolManager(registry)

        # Execute via Manager (what a Handler would do)
        with patch.object(YahooMacroTool, "_fetch_history", return_value=_make_mock_df()):
            result = await manager.execute("macro.yahoo", {"symbol": "^VIX", "period": "1mo"})

        # Assertions
        assert result.is_success is True
        assert result.tool_name == "YahooMacroTool"
        assert "macro_data" in result.artifact
        records = result.artifact["macro_data"]
        assert len(records) == 3
        assert all(isinstance(r, MacroDataSchema) for r in records)

    @pytest.mark.asyncio
    async def test_full_pipeline_unknown_capability(self):
        """Unknown capability → FAILED ToolResult (graceful)."""
        registry = ToolRegistry()
        manager = ToolManager(registry)

        result = await manager.execute("macro.nonexistent", {})
        assert result.is_failed is True
        assert "No tool registered" in result.error

    @pytest.mark.asyncio
    async def test_full_pipeline_tool_exception(self):
        """Tool crash → Manager returns FAILED ToolResult."""
        registry = ToolRegistry()

        class BrokenTool(BaseTool):
            def tool_name(self):
                return "Broken"

            def capability(self):
                return "test.broken"

            async def execute(self, input_data):
                raise RuntimeError("Catastrophic failure")

        registry.register(BrokenTool())
        manager = ToolManager(registry)

        result = await manager.execute("test.broken", {})
        assert result.is_failed is True
        assert "RuntimeError" in result.error


class TestManagerHandlerIntegration:
    """Handler ← ToolManager integration pattern.

    This is the EXACT pattern that real Handlers follow:
        Handler.execute()
          → tool_manager.execute(capability, input)
          → ToolResult
          → extract artifact
          → return TaskResult
    """

    @pytest.mark.asyncio
    async def test_handler_uses_manager_for_yahoo(self):
        """Simulate a real RetrieveHandler that calls ToolManager for Yahoo data."""
        registry = ToolRegistry()
        registry.register(YahooMacroTool())
        manager = ToolManager(registry)

        task = _make_task("retrieve_dxy", capability="macro.yahoo")

        # Simulate what a real handler would do:
        async def handler_execute(task: Task) -> TaskResult:
            symbol = task.config.get("symbol", "DXY")
            period = task.config.get("period", "1mo")

            tool_result = await manager.execute(
                "macro.yahoo",
                {"symbol": symbol, "period": period},
            )

            if tool_result.is_failed:
                return TaskResult(
                    task_id=task.id,
                    task_name=task.name,
                    status=TaskResultStatus.FAILED,
                    error=tool_result.error,
                )

            return TaskResult(
                task_id=task.id,
                task_name=task.name,
                status=TaskResultStatus.SUCCESS,
                artifacts=tool_result.artifact,  # Direct mapping!
            )

        with patch.object(YahooMacroTool, "_fetch_history", return_value=_make_mock_df()):
            task_result = await handler_execute(task)

        assert task_result.is_success is True
        assert "macro_data" in task_result.artifacts
        macro_data = task_result.artifacts["macro_data"]
        assert len(macro_data) == 3
        assert all(isinstance(r, MacroDataSchema) for r in macro_data)

    @pytest.mark.asyncio
    async def test_handler_maps_tool_failure_to_task_failure(self):
        """When ToolManager returns FAILED, handler propagates as FAILED TaskResult."""
        registry = ToolRegistry()
        manager = ToolManager(registry)  # Empty — no tools registered

        task = _make_task("bad_task", capability="macro.nonexistent")

        tool_result = await manager.execute("macro.nonexistent", {})

        task_result = TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=TaskResultStatus.FAILED,
            error=tool_result.error,
        )

        assert task_result.is_success is False
        assert "No tool registered" in task_result.error


class TestCanonicalDataLayerBoundary:
    """The Canonical Data Layer is the enterprise-grade separation.

    Tests that:
        - No raw vendor data (DataFrame, dict) leaks into artifact
        - All external data is translated to MacroDataSchema
        - The Agent never depends on vendor-specific formats
    """

    @pytest.mark.asyncio
    async def test_no_dataframe_in_artifact(self):
        """Artifact must never contain raw pandas objects."""
        tool = YahooMacroTool()

        with patch.object(tool, "_fetch_history", return_value=_make_mock_df()):
            result = await tool.execute({"symbol": "DXY"})

        assert result.is_success is True
        records = result.artifact["macro_data"]
        # Every record must be MacroDataSchema — not DataFrame, not dict
        for record in records:
            assert isinstance(record, MacroDataSchema)
            assert not isinstance(record, pd.DataFrame)
            assert record.source == "Yahoo"  # Canonical source label

    @pytest.mark.asyncio
    async def test_canonical_schema_fields_preserved(self):
        """All canonical fields are populated correctly after translation."""
        tool = YahooMacroTool()

        with patch.object(tool, "_fetch_history", return_value=_make_mock_df()):
            result = await tool.execute({"symbol": "^VIX"})

        records = result.artifact["macro_data"]
        for r in records:
            assert r.symbol == "^VIX"
            assert r.source == "Yahoo"
            assert r.currency == "USD"
            assert r.unit == "Price"
            assert isinstance(r.value, float)
            assert r.timestamp.tzinfo is not None
            assert 0.0 <= r.quality.overall <= 1.0

    @pytest.mark.asyncio
    async def test_agent_sees_only_macrodata(self):
        """The rest of the Agent (Planner/Executor/Handler) only sees MacroDataSchema.

        This is the fundamental invariant of the Canonical Data Layer.
        If Yahoo is replaced with Bloomberg, the Agent code does not change.
        """
        tool = YahooMacroTool()

        with patch.object(tool, "_fetch_history", return_value=_make_mock_df()):
            result = await tool.execute({"symbol": "USDJPY"})

        # Simulate what the Agent sees:
        for record in result.artifact["macro_data"]:
            # Agent only accesses canonical fields — never "Adj Close" or volume
            assert record.symbol is not None
            assert record.value is not None
            assert record.timestamp is not None
            assert record.source == "Yahoo"
            # These are the only fields Agent code should depend on
