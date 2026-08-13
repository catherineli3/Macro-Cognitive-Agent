"""V3 Scheduler — Periodic Pipeline Execution & KPI Reporting.

Extended from V2 scheduler to support:
- Periodic pipeline execution with V3 prediction loop
- Outcome evaluation scheduling
- Weekly KPI report generation
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from src.shared.logging import get_logger

logger = get_logger(__name__)


class EvaluationScheduler:
    """Schedules periodic evaluation of pending predictions.

    In Release 3.0, this is a simple polling-based scheduler.
    In Release 3.1+, this can integrate with async task queues.
    """

    def __init__(self, check_interval_hours: int = 24) -> None:
        self._check_interval = check_interval_hours * 3600  # seconds
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_run: datetime | None = None

    async def start(self, callback) -> None:
        """Start periodic evaluation checks."""
        if self._running:
            logger.warning("scheduler_already_running")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(callback))
        logger.info("scheduler_started interval_hours=%d", self._check_interval // 3600)

    async def stop(self) -> None:
        """Stop periodic evaluation checks."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("scheduler_stopped")

    async def _loop(self, callback) -> None:
        """Main loop: sleep → callback → sleep."""
        while self._running:
            try:
                self._last_run = datetime.now(UTC)
                logger.info("scheduler_tick")
                await callback()
            except Exception as e:
                logger.error("scheduler_callback_failed error=%s", e)
            await asyncio.sleep(self._check_interval)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def last_run_at(self) -> datetime | None:
        return self._last_run


class KPIReporter:
    """Generates KPI reports on a weekly schedule.

    Computes 30d, 90d, and all-time 4-KPI reports using KPIMetricsEngine.
    """

    def __init__(self, metrics_engine=None) -> None:
        from src.metrics import KPIMetricsEngine

        self._metrics = metrics_engine or KPIMetricsEngine()
        self._report_history: list = []

    async def generate_weekly_report(self) -> dict:
        """Generate a weekly 4-KPI report.

        In Release 3.0, this produces a baseline report.
        In Release 3.1+, it checks for regression.
        """
        logger.info("weekly_kpi_report_generating")
        # Placeholder — actual computation depends on accumulated data
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "no_data_yet" if not self._report_history else "active",
            "reports_count": len(self._report_history),
        }
        return report

    def get_report_history(self) -> list:
        return self._report_history
