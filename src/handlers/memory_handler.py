"""MemoryHandler — Executor adapter for the Belief Memory System.

Capability: "macro.memory"
Reads:      context.artifacts["hypotheses"] (HypothesisSet)
            context.artifacts["reflections"] (ReflectionSet)
Produces:   context.artifacts["memory_records"] (list[BeliefRecord])
Side-effect: Persists BeliefRecords to BeliefMemoryStore.

Design:
    - Stateless handler: delegates transformation to BeliefRecordBuilder,
      persistence to BeliefMemoryStore.
    - Runs AFTER "macro.reflection" (dependency constraint in Task pipeline).
    - Does NOT provide historical data to the current execution.
    - Memory records produced as artifact for downstream reporting.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.domain.execution import TaskResultStatus
from src.interfaces.task_handler import TaskHandlerInterface
from src.memory.builder import BeliefRecordBuilder
from src.memory.store import BeliefMemoryStore
from src.schemas.execution import TaskResult
from src.schemas.hypothesis import HypothesisSet
from src.schemas.memory import BeliefRecord
from src.schemas.planning import Task
from src.schemas.reflection import ReflectionSet
from src.shared.logging import get_logger

logger = get_logger(__name__)


class MemoryHandler(TaskHandlerInterface):
    """Writes reviewed beliefs to long-term memory.

    Capability: "macro.memory"
    Consumes:   context.artifacts["hypotheses"] + context.artifacts["reflections"]
    Produces:   context.artifacts["memory_records"]

    This handler is a PURE WRITER — it persists the current cycle's
    beliefs for future retrieval. It does not inject historical data
    into the current execution.
    """

    def __init__(
        self,
        store: BeliefMemoryStore | None = None,
        builder: BeliefRecordBuilder | None = None,
    ) -> None:
        """Initialize the handler.

        Args:
            store: BeliefMemoryStore instance. If None, creates a default one
                   writing to data/memory/beliefs.json.
            builder: BeliefRecordBuilder instance. If None, creates default.
        """
        self._store = store or BeliefMemoryStore()
        self._builder = builder or BeliefRecordBuilder()

    # ── TaskHandlerInterface Implementation ──────────────────────────────

    def supported_capability(self) -> str:
        return "macro.memory"

    def handler_name(self) -> str:
        return "MemoryHandler"

    async def execute(self, task: Task, context) -> TaskResult:
        """Persist reviewed beliefs to long-term memory.

        Args:
            task: The task to execute.
            context: ExecutionContext containing upstream artifacts.

        Returns:
            TaskResult with list[BeliefRecord] in artifacts["memory_records"].
            Returns FAILED if required artifacts are missing or persistence fails.
        """
        started = datetime.now(UTC)

        try:
            # Read required upstream artifacts
            hypotheses_raw = context.get_artifact("hypotheses", None)
            reflections_raw = context.get_artifact("reflections", None)

            if hypotheses_raw is None:
                logger.warning("memory_handler_no_hypotheses — nothing to record")
                return self._success(task, started, [])

            # Parse artifacts
            hypothesis_set = self._parse_hypotheses(hypotheses_raw)
            reflection_set = self._parse_reflections(reflections_raw)

            if hypothesis_set.count == 0:
                logger.info("memory_handler_empty_hypotheses — nothing to record")
                return self._success(task, started, [])

            # Build BeliefRecords via the builder
            records = self._builder.build(
                hypotheses=hypothesis_set,
                reflections=reflection_set,
                run_id=context._plan_id if hasattr(context, "_plan_id") else "unknown",
            )

            # Persist to store
            self._store.record_batch(records)

            logger.info(
                "memory_handler_completed",
                extra={
                    "belief_count": len(records),
                    "total_stored": self._store.belief_count,
                },
            )

            return self._success(task, started, records)

        except Exception as exc:
            completed = datetime.now(UTC)
            logger.error(
                "memory_handler_failed task=%s error=%s",
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

    # ── Private Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _success(
        task: Task,
        started: datetime,
        records: list[BeliefRecord],
    ) -> TaskResult:
        """Build a successful TaskResult with memory records."""
        completed = datetime.now(UTC)
        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=TaskResultStatus.SUCCESS,
            artifacts={"memory_records": records},
            started_at=started,
            completed_at=completed,
        )

    @staticmethod
    def _parse_hypotheses(raw) -> HypothesisSet:
        """Parse hypotheses from context artifacts.

        Handles both dict (JSON-deserialized) and HypothesisSet input.
        """
        if isinstance(raw, HypothesisSet):
            return raw
        if isinstance(raw, dict):
            return HypothesisSet(**raw)
        logger.warning(
            "memory_handler_unknown_hypothesis_type type=%s",
            type(raw).__name__,
        )
        return HypothesisSet()

    @staticmethod
    def _parse_reflections(raw) -> ReflectionSet:
        """Parse reflections from context artifacts.

        Handles None (not yet reviewed), dict, and ReflectionSet.
        """
        if raw is None:
            return ReflectionSet()
        if isinstance(raw, ReflectionSet):
            return raw
        if isinstance(raw, dict):
            return ReflectionSet(**raw)
        logger.warning(
            "memory_handler_unknown_reflection_type type=%s",
            type(raw).__name__,
        )
        return ReflectionSet()
