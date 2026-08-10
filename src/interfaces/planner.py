"""PlannerInterface — Abstract contract for plan creation.

Design:
    Planner is a PURE planning component. It receives a user goal string
    and returns a structured ExecutionPlan. It does NOT execute tasks,
    call tools, use LLM, or access any external system.

    The separation is strict:
        Planner → ExecutionPlan → Executor (future) → Tools → Reasoning → Output

    Sprint 3 Implementation:
        RuleBasedPlanner — keyword-driven, deterministic, no LLM.

    Future Implementations:
        LLMPlanner — LLM-driven task decomposition (preserves same interface).
"""

from abc import ABC, abstractmethod

from src.schemas.planning import ExecutionPlan


class PlannerInterface(ABC):
    """Abstract contract for goal-to-plan decomposition.

    All Planner implementations MUST conform to this interface.
    The interface is intentionally narrow: one method, one output type.
    """

    @abstractmethod
    async def create_plan(self, goal: str) -> ExecutionPlan:
        """Decompose a user goal into a structured execution plan.

        Args:
            goal: Natural language description of the user's objective.

        Returns:
            A validated, immutable ExecutionPlan with ordered tasks
            and resolved dependencies.

        Raises:
            PlanCreationError: If the goal cannot be decomposed into
                               a valid plan (e.g., unrecognized domain,
                               contradictory requirements).
        """
        ...

    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name of this planner (for logging & audit)."""
        ...
