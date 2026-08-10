"""Tests for ReflectionHandler — Executor integration."""

from typing import Optional

import pytest

from src.domain.execution import TaskResultStatus
from src.domain.signal import SignalDirection
from src.schemas.hypothesis import HypothesisEvidence, HypothesisSchema, HypothesisSet
from src.schemas.planning import Task
from src.schemas.reflection import ReflectionSet
from src.handlers.reflection_handler import ReflectionHandler
from src.interfaces.task_handler import TaskHandlerInterface


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_hypothesis(
    hypothesis_id: str = "h1",
    statement: str = "Test",
    supporting_count: int = 2,
    contradicting_count: int = 0,
    confidence: float = 0.8,
) -> HypothesisSchema:
    return HypothesisSchema(
        hypothesis_id=hypothesis_id,
        statement=statement,
        dimension="Liquidity",
        direction=SignalDirection.BEARISH,
        confidence=confidence,
        supporting_evidence=[
            HypothesisEvidence(
                indicator=f"IND{i}",
                signal_id=f"s{i}",
                observation=f"IND{i}=100",
                interpretation=f"IND{i} interpretation",
                contribution=0.8,
            )
            for i in range(supporting_count)
        ],
        contradicting_evidence=[
            HypothesisEvidence(
                indicator=f"CON{i}",
                signal_id=f"sc{i}",
                observation=f"CON{i}=100",
                interpretation=f"CON{i} interpretation",
                contribution=0.7,
            )
            for i in range(contradicting_count)
        ],
        assumptions=["Test assumption"],
    )


class MockContext:
    """Minimal mock of ExecutionContext for handler testing."""

    def __init__(self, artifacts: Optional[dict] = None):
        self._artifacts = artifacts or {}

    def get_artifact(self, key: str, default=None):
        return self._artifacts.get(key, default)


# ── Interface Compliance ────────────────────────────────────────────────────


class TestInterfaceCompliance:
    def test_implements_interface(self):
        handler = ReflectionHandler()
        assert isinstance(handler, TaskHandlerInterface)

    def test_capability_string(self):
        handler = ReflectionHandler()
        assert handler.supported_capability() == "macro.reflection"

    def test_handler_name(self):
        handler = ReflectionHandler()
        assert handler.handler_name() == "ReflectionHandler"


# ── Execute — Happy Path ────────────────────────────────────────────────────


class TestExecuteHappyPath:
    @pytest.mark.asyncio
    async def test_execute_with_hypothesis_set(self):
        handler = ReflectionHandler()
        h = _make_hypothesis(supporting_count=4)
        hs = HypothesisSet(hypotheses=[h])
        ctx = MockContext({"hypotheses": hs})

        task = Task.model_construct(
            id="t1",
            name="Review Hypotheses",
            description="Review belief",
            type="VALIDATE",  # type: ignore
        )
        result = await handler.execute(task, ctx)
        assert result.status == TaskResultStatus.SUCCESS  # type: ignore
        assert "reflections" in result.artifacts
        assert isinstance(result.artifacts["reflections"], ReflectionSet)
        rs = result.artifacts["reflections"]
        assert rs.count == 1

    @pytest.mark.asyncio
    async def test_execute_with_dict_input(self):
        """Handler should re-hydrate dict input into HypothesisSet."""
        handler = ReflectionHandler()
        h = _make_hypothesis(supporting_count=4)
        hs_dict = HypothesisSet(hypotheses=[h]).model_dump()
        ctx = MockContext({"hypotheses": hs_dict})

        task = Task.model_construct(
            id="t1",
            name="Review",
            description="Test",
            type="VALIDATE",  # type: ignore
        )
        result = await handler.execute(task, ctx)
        assert result.status == TaskResultStatus.SUCCESS  # type: ignore
        assert "reflections" in result.artifacts

    @pytest.mark.asyncio
    async def test_execute_with_multiple_hypotheses(self):
        handler = ReflectionHandler()
        h1 = _make_hypothesis("h1", "Statement A", supporting_count=4)
        h2 = _make_hypothesis("h2", "Statement B", supporting_count=1, contradicting_count=2)
        hs = HypothesisSet(hypotheses=[h1, h2])
        ctx = MockContext({"hypotheses": hs})

        task = Task.model_construct(
            id="t1",
            name="Review All",
            description="Test",
            type="VALIDATE",  # type: ignore
        )
        result = await handler.execute(task, ctx)
        assert result.status == TaskResultStatus.SUCCESS  # type: ignore
        rs = result.artifacts["reflections"]
        assert rs.count == 2

    @pytest.mark.asyncio
    async def test_execute_with_dependency_injection(self):
        """Handler should accept a pre-configured engine."""
        from src.critic.engine import ReflectionEngine

        engine = ReflectionEngine()
        handler = ReflectionHandler(engine=engine)
        h = _make_hypothesis(supporting_count=4)
        hs = HypothesisSet(hypotheses=[h])
        ctx = MockContext({"hypotheses": hs})

        task = Task.model_construct(
            id="t1", name="Review", description="Test", type="VALIDATE"  # type: ignore
        )
        result = await handler.execute(task, ctx)
        assert result.status == TaskResultStatus.SUCCESS  # type: ignore


# ── Execute — Edge Cases ────────────────────────────────────────────────────


class TestExecuteEdgeCases:
    @pytest.mark.asyncio
    async def test_execute_no_hypotheses(self):
        """When no hypotheses in context, produce empty ReflectionSet."""
        handler = ReflectionHandler()
        ctx = MockContext({})  # no "hypotheses" key

        task = Task.model_construct(
            id="t1",
            name="Review",
            description="Test",
            type="VALIDATE",  # type: ignore
        )
        result = await handler.execute(task, ctx)
        assert result.status == TaskResultStatus.SUCCESS  # type: ignore
        rs = result.artifacts["reflections"]
        assert rs.count == 0
        assert "No hypotheses" in rs.summary

    @pytest.mark.asyncio
    async def test_execute_unknown_type_produces_empty_set(self):
        """Unknown object type → empty HypothesisSet → empty ReflectionSet."""
        handler = ReflectionHandler()
        ctx = MockContext({"hypotheses": "not-a-hypothesis-set"})

        task = Task.model_construct(
            id="t1",
            name="Review",
            description="Test",
            type="VALIDATE",  # type: ignore
        )
        result = await handler.execute(task, ctx)
        # Should handle gracefully — produces empty set
        assert result.status == TaskResultStatus.SUCCESS  # type: ignore
        rs = result.artifacts["reflections"]
        assert rs.count == 0
