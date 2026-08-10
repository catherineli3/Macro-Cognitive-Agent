from __future__ import annotations

"""NarrativeHandler — Executor adapter for Narrative Engine.

Capability: "macro.narrative"
Reads:
    - context.artifacts["signals"]          → SignalSnapshot
    - context.artifacts["hypotheses"]       → HypothesisSet
    - context.artifacts["reflections"]      → ReflectionSet
    - context.artifacts["memory_records"]   → list[BeliefRecord] (optional)
Produces:
    - context.artifacts["narrative"]        → MacroNarrative
"""

from datetime import datetime, timezone

from src.domain.execution import TaskResultStatus
from src.interfaces.task_handler import TaskHandlerInterface
from src.narrative.engine import NarrativeEngine
from src.schemas.execution import TaskResult
from src.schemas.hypothesis import HypothesisSet
from src.schemas.memory import BeliefRecord
from src.schemas.narrative import MacroNarrative
from src.schemas.planning import Task
from src.schemas.reflection import ReflectionSet
from src.schemas.signal import SignalSnapshot
from src.shared.logging import get_logger

logger = get_logger(__name__)


class NarrativeHandler(TaskHandlerInterface):
    """Synthesizes the full cognitive chain into a structured MacroNarrative.

    Capability: "macro.narrative"
    Consumes:   signals, hypotheses, reflections, memory_records
    Produces:   narrative (MacroNarrative)

    This is the final step of the cognitive pipeline — all upstream
    artifacts are synthesized into a structured research narrative.
    The output is a MacroNarrative Schema, NOT raw Markdown.
    """

    def __init__(self, engine: NarrativeEngine | None = None) -> None:
        """Initialize with an optional pre-configured NarrativeEngine.

        If no engine is provided, a default one is created.
        This enables dependency injection for testing.
        """
        self._engine = engine or NarrativeEngine()

    def supported_capability(self) -> str:
        return "macro.narrative"

    def handler_name(self) -> str:
        return "NarrativeHandler"

    async def execute(self, task: Task, context) -> TaskResult:
        """Execute narrative synthesis.

        Args:
            task: The task to execute.
            context: ExecutionContext containing upstream artifacts.

        Returns:
            TaskResult with MacroNarrative in artifacts["narrative"].
            Always returns SUCCESS — even with partial data, the engine
            produces a best-effort narrative.
        """
        started = datetime.now(timezone.utc)

        try:
            # Read all upstream artifacts
            signals = self._parse_signals(context.get_artifact("signals", None))
            hypotheses = self._parse_hypotheses(context.get_artifact("hypotheses", None))
            reflections = self._parse_reflections(context.get_artifact("reflections", None))
            memory_records = self._parse_memory(context.get_artifact("memory_records", None))

            # Synthesize narrative
            narrative = self._engine.narrate(
                signals=signals,
                hypotheses=hypotheses,
                reflections=reflections,
                belief_records=memory_records,
            )

            completed = datetime.now(timezone.utc)

            logger.info(
                "narrative_handler_completed",
                extra={
                    "confidence": narrative.confidence,
                    "risk_count": len(narrative.risks),
                    "belief_changes": len(narrative.belief_changes),
                },
            )

            return TaskResult(
                task_id=task.id,
                task_name=task.name,
                status=TaskResultStatus.SUCCESS,
                artifacts={"narrative": narrative},
                started_at=started,
                completed_at=completed,
            )

        except Exception as exc:
            completed = datetime.now(timezone.utc)
            logger.error(
                "narrative_handler_failed task=%s error=%s",
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

    # ── Private Parsers ─────────────────────────────────────────────────

    @staticmethod
    def _parse_signals(raw) -> SignalSnapshot | None:
        """Parse signals from context artifacts."""
        if raw is None:
            return None
        if isinstance(raw, SignalSnapshot):
            return raw
        if isinstance(raw, dict):
            try:
                return SignalSnapshot(**raw)
            except Exception:
                logger.warning("narrative_handler_parse_signals_failed")
                return None
        return None

    @staticmethod
    def _parse_hypotheses(raw) -> HypothesisSet | None:
        """Parse hypotheses from context artifacts."""
        if raw is None:
            return None
        if isinstance(raw, HypothesisSet):
            return raw
        if isinstance(raw, dict):
            try:
                return HypothesisSet(**raw)
            except Exception:
                logger.warning("narrative_handler_parse_hypotheses_failed")
                return None
        return None

    @staticmethod
    def _parse_reflections(raw) -> ReflectionSet | None:
        """Parse reflections from context artifacts."""
        if raw is None:
            return None
        if isinstance(raw, ReflectionSet):
            return raw
        if isinstance(raw, dict):
            try:
                return ReflectionSet(**raw)
            except Exception:
                logger.warning("narrative_handler_parse_reflections_failed")
                return None
        return None

    @staticmethod
    def _parse_memory(raw) -> list[BeliefRecord] | None:
        """Parse memory records from context artifacts."""
        if raw is None:
            return None
        if isinstance(raw, list):
            records: list[BeliefRecord] = []
            for item in raw:
                if isinstance(item, BeliefRecord):
                    records.append(item)
                elif isinstance(item, dict):
                    try:
                        records.append(BeliefRecord(**item))
                    except Exception:
                        pass
            return records if records else None
        return None
