from __future__ import annotations

"""HypothesisHandler — Executor adapter for the Reasoning Engine.

Capability: "macro.hypothesis"
Reads:      context.artifacts["signals"] (list[MacroSignalSchema], from Signal Engine)
Produces:   context.artifacts["hypotheses"] (HypothesisSet)

Design:
    - Stateless: delegates all work to HypothesisEngine.
    - Reads signals from ExecutionContext (produced by a prior Signal task).
    - Produces HypothesisSet as a named artifact for downstream consumption
      by Reflection (Sprint 7), Report (future), and Memory (Sprint 8).
"""

from datetime import datetime, timezone

from src.domain.execution import TaskResultStatus
from src.hypothesis.engine import HypothesisEngine
from src.interfaces.task_handler import TaskHandlerInterface
from src.schemas.execution import TaskResult
from src.schemas.hypothesis import HypothesisSet
from src.schemas.planning import Task
from src.schemas.signal import MacroSignalSchema, SignalSnapshot
from src.shared.logging import get_logger

logger = get_logger(__name__)


class HypothesisHandler(TaskHandlerInterface):
    """Executes hypothesis generation via the Reasoning Engine.

    Capability: "macro.hypothesis"
    Consumes:   context.artifacts["signals"]
    Produces:   context.artifacts["hypotheses"]

    This handler bridges the Executor (Sprint 4) to the
    HypothesisEngine (Sprint 6). It follows the exact same
    stateless-handler pattern as SimpleGenerateHandler.
    """

    def __init__(self, engine: HypothesisEngine | None = None) -> None:
        """Initialize with an optional pre-configured HypothesisEngine.

        If no engine is provided, a default one is created.
        This enables dependency injection for testing.
        """
        self._engine = engine or HypothesisEngine()

    def supported_capability(self) -> str:
        return "macro.hypothesis"

    def handler_name(self) -> str:
        return "HypothesisHandler"

    async def execute(self, task: Task, context) -> TaskResult:
        """Execute hypothesis generation.

        Args:
            task: The task to execute.
            context: ExecutionContext containing upstream artifacts.

        Returns:
            TaskResult with HypothesisSet in artifacts["hypotheses"].
            Returns FAILED if signals are missing or reasoning fails.
        """
        started = datetime.now(timezone.utc)

        try:
            # Read signals from context (produced by a prior Signal Engine task)
            signals_raw = context.get_artifact("signals", [])

            # Validate and parse signals
            if not signals_raw:
                logger.warning("hypothesis_handler_no_signals — producing empty set")
                result_set = HypothesisSet()
            else:
                # signals_raw may be dicts (from JSON serialization) or
                # MacroSignalSchema objects. Re-hydrate if needed.
                signals = self._parse_signals(signals_raw)
                result_set = self._engine.reason(signals)

            completed = datetime.now(timezone.utc)

            return TaskResult(
                task_id=task.id,
                task_name=task.name,
                status=TaskResultStatus.SUCCESS,
                artifacts={"hypotheses": result_set},
                started_at=started,
                completed_at=completed,
            )

        except Exception as exc:
            completed = datetime.now(timezone.utc)
            logger.error(
                "hypothesis_handler_failed task=%s error=%s",
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
    def _parse_signals(
        raw: SignalSnapshot | list | dict,
    ) -> list[MacroSignalSchema]:
        """Parse signals from context artifacts into MacroSignalSchema objects.

        Handles SignalSnapshot, list[dict], list[MacroSignalSchema], and dict input.
        """
        # Case 1: SignalSnapshot — extract .signals
        if isinstance(raw, SignalSnapshot):
            return list(raw.signals) if raw.signals else []

        # Case 2: list of items
        if isinstance(raw, list):
            parsed: list[MacroSignalSchema] = []
            for item in raw:
                if isinstance(item, MacroSignalSchema):
                    parsed.append(item)
                elif isinstance(item, dict):
                    parsed.append(MacroSignalSchema(**item))
                else:
                    logger.warning(
                        "hypothesis_handler_unknown_signal_type type=%s",
                        type(item).__name__,
                    )
            return parsed

        # Case 3: single dict
        if isinstance(raw, dict):
            try:
                return [MacroSignalSchema(**raw)]
            except Exception:
                return []

        logger.warning("hypothesis_handler_unexpected_signal_format type=%s", type(raw).__name__)
        return []
