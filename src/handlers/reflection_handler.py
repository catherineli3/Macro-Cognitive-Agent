from __future__ import annotations

"""ReflectionHandler — Executor adapter for the Belief Review Engine.

Capability: "macro.reflection"
Reads:      context.artifacts["hypotheses"] (HypothesisSet, from Sprint 6)
Produces:   context.artifacts["reflections"] (ReflectionSet)

Design:
    - Stateless: delegates all work to ReflectionEngine.
    - Reads hypotheses from ExecutionContext (produced by HypothesisHandler).
    - Produces ReflectionSet as a named artifact for downstream consumption
      by Memory (Sprint 8) and Report (future).
    - Never mutates Hypothesis objects.
"""

from datetime import datetime, timezone

from src.critic.engine import ReflectionEngine
from src.domain.execution import TaskResultStatus
from src.interfaces.task_handler import TaskHandlerInterface
from src.schemas.execution import TaskResult
from src.schemas.hypothesis import HypothesisSet
from src.schemas.planning import Task
from src.schemas.reflection import ReflectionSet
from src.shared.logging import get_logger

logger = get_logger(__name__)


class ReflectionHandler(TaskHandlerInterface):
    """Executes belief review via the Reflection Engine.

    Capability: "macro.reflection"
    Consumes:   context.artifacts["hypotheses"]
    Produces:   context.artifacts["reflections"]

    This handler bridges the Executor (Sprint 4) to the
    ReflectionEngine (Sprint 7). It follows the exact same
    stateless-handler pattern as HypothesisHandler.
    """

    def __init__(self, engine: ReflectionEngine | None = None) -> None:
        """Initialize with an optional pre-configured ReflectionEngine.

        If no engine is provided, a default one is created.
        This enables dependency injection for testing.
        """
        self._engine = engine or ReflectionEngine()

    def supported_capability(self) -> str:
        return "macro.reflection"

    def handler_name(self) -> str:
        return "ReflectionHandler"

    async def execute(self, task: Task, context) -> TaskResult:
        """Execute belief review.

        Args:
            task: The task to execute.
            context: ExecutionContext containing upstream artifacts.

        Returns:
            TaskResult with ReflectionSet in artifacts["reflections"].
            Returns FAILED if hypotheses are missing or review fails.
        """
        started = datetime.now(timezone.utc)

        try:
            # Read hypotheses from context (produced by HypothesisHandler)
            hypotheses_raw = context.get_artifact("hypotheses", None)

            if hypotheses_raw is None:
                logger.warning(
                    "reflection_handler_no_hypotheses — producing empty set"
                )
                result_set = ReflectionSet(
                    summary="No hypotheses available for review."
                )
            else:
                # Re-hydrate if needed
                hypothesis_set = self._parse_hypotheses(hypotheses_raw)
                result_set = self._engine.review(hypothesis_set)

            completed = datetime.now(timezone.utc)

            return TaskResult(
                task_id=task.id,
                task_name=task.name,
                status=TaskResultStatus.SUCCESS,
                artifacts={"reflections": result_set},
                started_at=started,
                completed_at=completed,
            )

        except Exception as exc:
            completed = datetime.now(timezone.utc)
            logger.error(
                "reflection_handler_failed task=%s error=%s",
                task.name,
                str(exc),
            )
            return TaskResult(
                task_id=task.id,
                task_name=task.name,
                status=TaskResultStatus.FAILED,
                error=str(exc),
                artifacts={},
                started_at=started,
                completed_at=completed,
            )

    # ── Private ─────────────────────────────────────────────────────────

    @staticmethod
    def _parse_hypotheses(raw) -> HypothesisSet:
        """Parse hypotheses from context artifacts into HypothesisSet.

        Handles both dict (JSON-deserialized) and HypothesisSet input.
        """
        if isinstance(raw, HypothesisSet):
            return raw
        if isinstance(raw, dict):
            return HypothesisSet(**raw)
        logger.warning(
            "reflection_handler_unknown_type type=%s",
            type(raw).__name__,
        )
        return HypothesisSet()
