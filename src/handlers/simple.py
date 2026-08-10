"""Simple Task Handlers — Mock implementations for testing and demo.

Each handler implements TaskHandlerInterface using a specific capability string.
These handlers:
  - Are STATELESS (no internal mutable state)
  - Read from ExecutionContext (read-only)
  - Return TaskResult with named artifacts
  - Contain ZERO business logic (mock output only)

Capability keys follow "simple.<action>":
    simple.retrieve   → SimpleRetrieveHandler  (artifact: "raw_data")
    simple.process    → SimpleProcessHandler   (artifact: "processed_data")
    simple.analyze    → SimpleAnalyzeHandler   (artifact: "analysis")
    simple.generate   → SimpleGenerateHandler  (artifact: "output")
    simple.validate   → SimpleValidateHandler  (artifact: "validation")
"""

from datetime import datetime, timezone

from src.domain.execution import TaskResultStatus
from src.interfaces.task_handler import TaskHandlerInterface
from src.schemas.execution import TaskResult
from src.schemas.planning import Task


class SimpleRetrieveHandler(TaskHandlerInterface):
    """Mock handler for data retrieval tasks.

    Capability: "simple.retrieve"
    Produces artifact: "raw_data"
    """

    def supported_capability(self) -> str:
        return "simple.retrieve"

    def handler_name(self) -> str:
        return "SimpleRetrieveHandler"

    async def execute(self, task: Task, context) -> TaskResult:
        started = datetime.now(timezone.utc)
        completed = datetime.now(timezone.utc)

        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=TaskResultStatus.SUCCESS,
            artifacts={
                "raw_data": {
                    "source": "mock",
                    "task": task.name,
                    "records": [
                        {"timestamp": "2026-07-14", "value": 105.3, "indicator": "DXY"},
                        {"timestamp": "2026-07-14", "value": 4.25, "indicator": "US10Y"},
                    ],
                }
            },
            started_at=started,
            completed_at=completed,
        )


class SimpleProcessHandler(TaskHandlerInterface):
    """Mock handler for data processing tasks.

    Capability: "simple.process"
    Produces artifact: "processed_data"
    Reads artifact: "raw_data" (from upstream retrieve)
    """

    def supported_capability(self) -> str:
        return "simple.process"

    def handler_name(self) -> str:
        return "SimpleProcessHandler"

    async def execute(self, task: Task, context) -> TaskResult:
        started = datetime.now(timezone.utc)
        completed = datetime.now(timezone.utc)

        raw = context.get_artifact("raw_data", {})

        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=TaskResultStatus.SUCCESS,
            artifacts={
                "processed_data": {
                    "source": "mock",
                    "task": task.name,
                    "normalized": True,
                    "input_records_count": len(raw.get("records", [])),
                    "output": {"status": "cleaned", "quality": 0.98},
                }
            },
            started_at=started,
            completed_at=completed,
        )


class SimpleAnalyzeHandler(TaskHandlerInterface):
    """Mock handler for analysis tasks.

    Capability: "simple.analyze"
    Produces artifact: "analysis"
    Reads artifacts: "raw_data", "processed_data"
    """

    def supported_capability(self) -> str:
        return "simple.analyze"

    def handler_name(self) -> str:
        return "SimpleAnalyzeHandler"

    async def execute(self, task: Task, context) -> TaskResult:
        started = datetime.now(timezone.utc)
        completed = datetime.now(timezone.utc)

        raw = context.get_artifact("raw_data", {})
        processed = context.get_artifact("processed_data", {})

        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=TaskResultStatus.SUCCESS,
            artifacts={
                "analysis": {
                    "source": "mock",
                    "task": task.name,
                    "findings": [
                        "Liquidity conditions are neutral",
                        "No extreme signals detected",
                    ],
                    "confidence": 0.75,
                    "inputs_used": [
                        f"raw_data: {len(raw.get('records', []))} records",
                        f"processed_data: quality={processed.get('output', {}).get('quality', 'N/A')}",
                    ],
                }
            },
            started_at=started,
            completed_at=completed,
        )


class SimpleGenerateHandler(TaskHandlerInterface):
    """Mock handler for content generation tasks.

    Capability: "simple.generate"
    Produces artifact: "output"
    Reads artifact: "analysis"
    """

    def supported_capability(self) -> str:
        return "simple.generate"

    def handler_name(self) -> str:
        return "SimpleGenerateHandler"

    async def execute(self, task: Task, context) -> TaskResult:
        started = datetime.now(timezone.utc)
        completed = datetime.now(timezone.utc)

        analysis = context.get_artifact("analysis", {})

        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=TaskResultStatus.SUCCESS,
            artifacts={
                "output": {
                    "source": "mock",
                    "task": task.name,
                    "content": "Based on current indicators, macro conditions are stable.",
                    "based_on_findings": analysis.get("findings", []),
                    "confidence": analysis.get("confidence", 0.5),
                }
            },
            started_at=started,
            completed_at=completed,
        )


class SimpleValidateHandler(TaskHandlerInterface):
    """Mock handler for validation tasks.

    Capability: "simple.validate"
    Produces artifact: "validation"
    Reads all upstream artifacts.
    """

    def supported_capability(self) -> str:
        return "simple.validate"

    def handler_name(self) -> str:
        return "SimpleValidateHandler"

    async def execute(self, task: Task, context) -> TaskResult:
        started = datetime.now(timezone.utc)
        completed = datetime.now(timezone.utc)

        all_artifacts = context.artifacts

        return TaskResult(
            task_id=task.id,
            task_name=task.name,
            status=TaskResultStatus.SUCCESS,
            artifacts={
                "validation": {
                    "source": "mock",
                    "task": task.name,
                    "valid": True,
                    "checks_performed": [
                        "Data completeness: OK",
                        "Processing integrity: OK",
                        "Analysis coherence: OK",
                    ],
                    "artifacts_available": list(all_artifacts.keys()),
                    "score": 0.95,
                }
            },
            started_at=started,
            completed_at=completed,
        )
