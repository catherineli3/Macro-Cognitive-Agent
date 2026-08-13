"""Tests for ToolResult schema and ToolResultStatus enum."""

import pytest

from src.domain.tool import ToolResultStatus
from src.schemas.tool import ToolResult


class TestToolResultStatus:
    """ToolResultStatus enum behavior."""

    def test_success_value(self):
        assert ToolResultStatus.SUCCESS.value == "success"
        assert ToolResultStatus.SUCCESS == "success"

    def test_failed_value(self):
        assert ToolResultStatus.FAILED.value == "failed"
        assert ToolResultStatus.FAILED == "failed"

    def test_distinct_values(self):
        assert ToolResultStatus.SUCCESS != ToolResultStatus.FAILED


class TestToolResult:
    """ToolResult schema: creation, properties, edge cases."""

    def test_minimal_success(self):
        result = ToolResult(status=ToolResultStatus.SUCCESS, tool_name="test_tool")
        assert result.status == ToolResultStatus.SUCCESS
        assert result.tool_name == "test_tool"
        assert result.artifact == {}
        assert result.error is None
        assert result.latency_ms == 0.0
        assert result.is_success is True
        assert result.is_failed is False

    def test_minimal_failed(self):
        result = ToolResult(
            status=ToolResultStatus.FAILED,
            tool_name="test_tool",
            error="Something went wrong",
        )
        assert result.status == ToolResultStatus.FAILED
        assert result.is_success is False
        assert result.is_failed is True
        assert result.error == "Something went wrong"

    def test_with_artifact(self):
        result = ToolResult(
            status=ToolResultStatus.SUCCESS,
            tool_name="macro.yahoo",
            artifact={"macro_data": [{"symbol": "DXY", "value": 105.3}]},
            latency_ms=245.0,
        )
        assert result.artifact == {"macro_data": [{"symbol": "DXY", "value": 105.3}]}
        assert result.latency_ms == 245.0
        assert result.is_success is True

    def test_multi_key_artifact(self):
        """ToolResult can carry multiple named artifacts (same pattern as TaskResult)."""
        result = ToolResult(
            status=ToolResultStatus.SUCCESS,
            tool_name="test",
            artifact={
                "macro_data": [{"a": 1}],
                "metadata": {"source": "Yahoo", "records": 20},
            },
        )
        assert len(result.artifact) == 2
        assert result.artifact["macro_data"] == [{"a": 1}]
        assert result.artifact["metadata"]["records"] == 20

    def test_latency_non_negative(self):
        """Latency must be >= 0."""
        result = ToolResult(status=ToolResultStatus.SUCCESS, tool_name="t", latency_ms=0.0)
        assert result.latency_ms == 0.0

    def test_completed_at_auto_set(self):
        """completed_at is auto-populated on creation."""
        result = ToolResult(status=ToolResultStatus.SUCCESS, tool_name="t")
        assert result.completed_at is not None

    def test_default_status_rejected(self):
        """ToolResult requires explicit status."""
        with pytest.raises(Exception):
            ToolResult(tool_name="t")

    def test_tool_name_min_length(self):
        """tool_name must be non-empty."""
        with pytest.raises(Exception):
            ToolResult(status=ToolResultStatus.SUCCESS, tool_name="")

    def test_failed_without_error_is_valid(self):
        """FAILED without an error string is technically valid (edge case)."""
        result = ToolResult(status=ToolResultStatus.FAILED, tool_name="t")
        assert result.is_failed is True
        assert result.error is None

    def test_repr(self):
        result = ToolResult(
            status=ToolResultStatus.SUCCESS,
            tool_name="YahooMacroTool",
            artifact={"macro_data": [1, 2]},
            latency_ms=123.4,
        )
        r = repr(result)
        assert "YahooMacroTool" in r
        assert "success" in r
        assert "macro_data" in r
        assert "123.4" in r
