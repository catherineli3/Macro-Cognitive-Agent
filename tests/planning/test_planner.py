"""Tests for RuleBasedPlanner — goal-to-plan decomposition."""

import pytest

from src.domain.planning import TaskType
from src.planning.planner import RuleBasedPlanner
from src.shared.exceptions import PlanCreationError


@pytest.fixture
def planner() -> RuleBasedPlanner:
    """Default RuleBasedPlanner instance."""
    return RuleBasedPlanner()


class TestBasicPlanning:
    """Core: goal → plan decomposition."""

    @pytest.mark.asyncio
    async def test_liquidity_goal(self, planner: RuleBasedPlanner) -> None:
        plan = await planner.create_plan("Analyze global liquidity conditions")
        assert plan.goal == "Analyze global liquidity conditions"
        assert plan.task_count > 0
        assert plan.plan_explanation != ""
        assert plan.version == "1.0"

    @pytest.mark.asyncio
    async def test_macro_goal(self, planner: RuleBasedPlanner) -> None:
        plan = await planner.create_plan("Assess current economic environment")
        assert plan.task_count > 0
        types = {t.type for t in plan.tasks}
        assert len(types) >= 2  # At least retrieve + analyze

    @pytest.mark.asyncio
    async def test_risk_goal(self, planner: RuleBasedPlanner) -> None:
        plan = await planner.create_plan("Evaluate systemic risk")
        assert plan.task_count > 0

    @pytest.mark.asyncio
    async def test_report_goal(self, planner: RuleBasedPlanner) -> None:
        plan = await planner.create_plan("Write a market briefing")
        assert plan.task_count > 0
        types = {t.type for t in plan.tasks}
        assert TaskType.VALIDATE in types  # Report plans include validation


class TestTaskTypeCorrectness:
    """All generated tasks use generic Agent capability types only."""

    @pytest.mark.asyncio
    async def test_no_macro_specific_task_types(self, planner: RuleBasedPlanner) -> None:
        plan = await planner.create_plan("Analyze the macro environment and liquidity")
        for t in plan.tasks:
            assert t.type in {
                TaskType.RETRIEVE,
                TaskType.PROCESS,
                TaskType.ANALYZE,
                TaskType.GENERATE,
                TaskType.VALIDATE,
                TaskType.DECIDE,
            }

    @pytest.mark.asyncio
    async def test_tasks_are_abstract_no_specific_symbols(self, planner: RuleBasedPlanner) -> None:
        """Task names/descriptions must NOT mention specific indicators."""
        plan = await planner.create_plan("Analyze macro liquidity")
        for t in plan.tasks:
            name_lower = t.name.lower()
            desc_lower = t.description.lower()
            # Must not contain specific macro symbols
            assert "dxy" not in name_lower
            assert "us10y" not in name_lower
            assert "yahoo" not in name_lower
            assert "dxy" not in desc_lower
            assert "us10y" not in desc_lower


class TestDefaultFallback:
    """Unrecognized goals fall back to default rule."""

    @pytest.mark.asyncio
    async def test_unrecognized_goal_uses_default(self, planner: RuleBasedPlanner) -> None:
        plan = await planner.create_plan("Tell me something completely random")
        assert plan.task_count == 3
        # Default template: RETRIEVE → ANALYZE → GENERATE
        types = [t.type for t in plan.tasks]
        assert TaskType.RETRIEVE in types
        assert TaskType.ANALYZE in types
        assert TaskType.GENERATE in types

    @pytest.mark.asyncio
    async def test_default_plan_still_valid(self, planner: RuleBasedPlanner) -> None:
        plan = await planner.create_plan("xyz123 unknown request")
        assert plan.plan_explanation != ""
        assert plan.task_count > 0


class TestMultiRuleMerging:
    """Multiple matching rules merge tasks (union, dedup by ID)."""

    @pytest.mark.asyncio
    async def test_multi_match_merges(self, planner: RuleBasedPlanner) -> None:
        """Goal matching macro + liquidity + risk should merge all tasks."""
        plan = await planner.create_plan(
            "Analyze macro environment, liquidity conditions, and risk exposure"
        )
        # Should have tasks from all 3 rules
        task_ids = {t.id for t in plan.tasks}
        assert "collect_market_data" in task_ids  # macro
        assert "retrieve_liquidity_data" in task_ids  # liquidity
        assert "retrieve_risk_data" in task_ids  # risk

    @pytest.mark.asyncio
    async def test_dedup_common_tasks(self, planner: RuleBasedPlanner) -> None:
        """Tasks with same ID from different rules are deduplicated."""
        plan_1 = await planner.create_plan("macro environment")
        plan_2 = await planner.create_plan("macro environment and liquidity")
        # plan_2 should have more tasks (liquidity adds new ones)
        assert plan_2.task_count > plan_1.task_count
        # But macro tasks should not be duplicated
        macro_ids = {t.id for t in plan_1.tasks}
        plan2_ids = {t.id for t in plan_2.tasks}
        assert macro_ids.issubset(plan2_ids)


class TestEdgeCases:
    """Error handling and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_goal_raises(self) -> None:
        p = RuleBasedPlanner()
        with pytest.raises(PlanCreationError, match="empty"):
            await p.create_plan("")

    @pytest.mark.asyncio
    async def test_whitespace_only_goal_raises(self) -> None:
        p = RuleBasedPlanner()
        with pytest.raises(PlanCreationError, match="empty"):
            await p.create_plan("   ")

    @pytest.mark.asyncio
    async def test_plan_explanation_present(self, planner: RuleBasedPlanner) -> None:
        plan = await planner.create_plan("Analyze risk")
        explanation = plan.plan_explanation
        assert "Plan generated from" in explanation
        assert "rule template" in explanation
        assert "RETRIEVE" in explanation or "retrieve" in explanation.lower()

    @pytest.mark.asyncio
    async def test_source_name(self, planner: RuleBasedPlanner) -> None:
        name = planner.source_name()
        assert "RuleBasedPlanner" in name
        assert "planning_rules.yaml" in name

    @pytest.mark.asyncio
    async def test_all_dependencies_valid(self, planner: RuleBasedPlanner) -> None:
        """Every generated plan must have valid dependencies."""
        plan = await planner.create_plan("Analyze macro environment and report")
        valid_ids = plan.task_ids
        for t in plan.tasks:
            for dep in t.dependencies:
                assert dep in valid_ids, f"Task {t.id} depends on missing {dep}"

    @pytest.mark.asyncio
    async def test_no_circular_deps_in_generated_plan(self, planner: RuleBasedPlanner) -> None:
        """Planner must never generate a plan with circular dependencies."""
        # Test multiple goals to ensure robustness
        goals = [
            "Analyze macro environment",
            "liquidity analysis",
            "risk assessment",
            "Write a report on financial conditions",
            "Analyze macro liquidity and risk for report",
        ]
        for goal in goals:
            plan = await planner.create_plan(goal)
            # If circular, validator in create_plan would raise
            assert plan.plan_id is not None
