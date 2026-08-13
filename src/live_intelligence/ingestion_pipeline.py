"""V6.1 Ingestion Pipeline — Orchestrated real-time information intake.

Full pipeline:
    1. Poll sources based on EventScheduler
    2. Route raw events → NormalizedEvent via SourceRouter
    3. Deduplicate via DuplicateDetector
    4. Check freshness via FreshnessMonitor
    5. Feed into Evidence Graph (via V4 FusionEngine)

This is the main entry point for all live information.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime

from src.live_intelligence.duplicate_detector import DuplicateDetector
from src.live_intelligence.event_scheduler import EventScheduler
from src.live_intelligence.freshness_monitor import FreshnessMonitor
from src.live_intelligence.schemas import (
    IngestionResult,
    IngestionStatus,
    NormalizedEvent,
    PipelineStatus,
    RawEvent,
    SourceType,
)
from src.live_intelligence.source_router import SourceRouter


class IngestionPipeline:
    """Unified ingestion pipeline: Raw → Normalized → Deduplicated → Fresh → Evidence Graph.

    Usage:
        pipeline = IngestionPipeline()
        pipeline.set_evidence_graph_feed(my_fusion_engine)

        # Ingest a batch
        raw_events = collect_from_sources()
        result = pipeline.ingest(raw_events)

        # Or ingest a single event
        result = pipeline.ingest_single(raw_event)

        # Continuous mode (background polling)
        pipeline.start_continuous()
    """

    def __init__(
        self,
        scheduler: EventScheduler | None = None,
        router: SourceRouter | None = None,
        deduplicator: DuplicateDetector | None = None,
        monitor: FreshnessMonitor | None = None,
    ):

        self.scheduler = scheduler or EventScheduler()
        self.router = router or SourceRouter()
        self.deduplicator = deduplicator or DuplicateDetector()
        self.monitor = monitor or FreshnessMonitor()

        # Optional evidence graph feed callback
        self._evidence_feed: Callable | None = None

        # Pipeline state
        self._is_running = False
        self._started_at: str = ""
        self._total_ingested = 0
        self._total_errors = 0
        self._last_result: IngestionResult | None = None

        # Source pollers (callables that return lists of RawEvent)
        self._pollers: dict[SourceType, Callable[[], list[RawEvent]]] = {}

        # Event buffer for batch processing
        self._buffer: list[NormalizedEvent] = []
        self._buffer_max = 1000

    # ── Core API ──────────────────────────────────────────────────────────

    def ingest(self, raw_events: list[RawEvent]) -> IngestionResult:
        """Ingest a batch of raw events through the full pipeline."""
        t0 = time.time()
        result = IngestionResult()
        result.raw_events_ingested = len(raw_events)

        if not raw_events:
            result.completed_at = datetime.now(UTC).isoformat()
            return result

        try:
            # Step 1: Route → Normalize
            normalized = self.router.route_batch(raw_events)

            # Step 2: Deduplicate
            unique, dup_report = self.deduplicator.deduplicate(normalized)
            result.duplicates_detected = dup_report.duplicate_count
            result.normalized_events = len(unique)

            # Step 3: Freshness check
            self.monitor.register_batch(unique)
            freshness_report = self.monitor.check_all()
            result.stale_events_dropped = freshness_report.stale_count

            # Filter to fresh events
            fresh_events = [e for e in unique if e.is_fresh]

            # Step 4: Tag critical events
            result.critical_events = [e for e in fresh_events if e.is_critical]

            # Step 5: Feed to evidence graph
            if self._evidence_feed:
                self._evidence_feed(fresh_events)
                result.events_to_evidence_graph = len(fresh_events)

            # Store
            result.events = fresh_events
            result.status = IngestionStatus.SUCCESS

            self._total_ingested += len(fresh_events)

        except Exception as e:
            result.status = IngestionStatus.FAILED
            result.errors.append(str(e))
            self._total_errors += 1

        result.duration_ms = (time.time() - t0) * 1000
        result.completed_at = datetime.now(UTC).isoformat()
        self._last_result = result

        return result

    def ingest_single(self, raw: RawEvent) -> IngestionResult:
        """Ingest a single raw event."""
        return self.ingest([raw])

    def poll_and_ingest(self, source: SourceType) -> IngestionResult:
        """Poll a specific source and ingest results."""
        poller = self._pollers.get(source)
        if not poller:
            result = IngestionResult(status=IngestionStatus.SKIPPED)
            result.warnings.append(f"No poller registered for {source}")
            result.completed_at = datetime.now(UTC).isoformat()
            return result

        try:
            raw_events = poller()
            self.scheduler.record_poll(source, success=True)
            return self.ingest(raw_events)
        except Exception as e:
            self.scheduler.record_poll(source, success=False)
            result = IngestionResult(status=IngestionStatus.FAILED)
            result.errors.append(f"Poll failed for {source}: {e}")
            result.completed_at = datetime.now(UTC).isoformat()
            return result

    def poll_all_due(self) -> IngestionResult:
        """Poll all sources that are due, combine results."""
        due_sources = self.scheduler.get_due_sources()

        if not due_sources:
            result = IngestionResult(status=IngestionStatus.SKIPPED)
            result.warnings.append("No sources due for polling")
            result.completed_at = datetime.now(UTC).isoformat()
            return result

        all_raws = []
        for source in due_sources:
            poller = self._pollers.get(source)
            if poller:
                try:
                    raws = poller()
                    all_raws.extend(raws)
                    self.scheduler.record_poll(source, success=True)
                except Exception:
                    self.scheduler.record_poll(source, success=False)

        return self.ingest(all_raws)

    # ── Source Registration ───────────────────────────────────────────────

    def register_poller(self, source: SourceType, poller: Callable[[], list[RawEvent]]):
        """Register a poller function for a specific source.

        The poller should return a list of RawEvent objects.
        Example:
            def poll_reuters() -> list[RawEvent]:
                articles = fetch_reuters_headlines()
                return [RawEvent(source=SourceType.REUTERS, headline=a.title, ...)
                        for a in articles]
            pipeline.register_poller(SourceType.REUTERS, poll_reuters)
        """
        self._pollers[source] = poller

    def set_evidence_graph_feed(self, feed: Callable[[list[NormalizedEvent]], None]):
        """Set callback that feeds normalized events into the Evidence Graph.

        This should point to the V4 FusionEngine's build_graph or similar method.
        """
        self._evidence_feed = feed

    # ── Buffer Management ─────────────────────────────────────────────────

    def buffer_event(self, event: NormalizedEvent):
        """Add event to buffer for batch processing."""
        self._buffer.append(event)
        if len(self._buffer) >= self._buffer_max:
            self.flush_buffer()

    def flush_buffer(self) -> IngestionResult:
        """Flush buffered events through dedup + freshness + evidence."""
        if not self._buffer:
            result = IngestionResult(status=IngestionStatus.SKIPPED)
            result.completed_at = datetime.now(UTC).isoformat()
            return result

        buffered = list(self._buffer)
        self._buffer.clear()
        return self._process_buffered(buffered)

    def _process_buffered(self, events: list[NormalizedEvent]) -> IngestionResult:
        """Process pre-normalized events through remaining pipeline steps."""
        t0 = time.time()
        result = IngestionResult(raw_events_ingested=len(events))

        unique, dup_report = self.deduplicator.deduplicate(events)
        result.duplicates_detected = dup_report.duplicate_count
        result.normalized_events = len(unique)

        self.monitor.register_batch(unique)
        freshness = self.monitor.check_all()
        result.stale_events_dropped = freshness.stale_count

        fresh = [e for e in unique if e.is_fresh]
        result.critical_events = [e for e in fresh if e.is_critical]
        result.events = fresh

        if self._evidence_feed:
            self._evidence_feed(fresh)
            result.events_to_evidence_graph = len(fresh)

        result.duration_ms = (time.time() - t0) * 1000
        result.completed_at = datetime.now(UTC).isoformat()
        return result

    # ── Continuous Mode ──────────────────────────────────────────────────

    def start_continuous(self, poll_interval_seconds: int = 60):
        """Start continuous polling (blocking — run in background thread)."""
        self._is_running = True
        self._started_at = datetime.now(UTC).isoformat()

        # This is a simplified continuous loop; in production, use asyncio or threading
        import threading

        def _loop():
            while self._is_running:
                try:
                    self.poll_all_due()
                except Exception:
                    pass
                time.sleep(poll_interval_seconds)

        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()
        return thread

    def stop_continuous(self):
        """Stop continuous polling."""
        self._is_running = False

    # ── Status & Monitoring ───────────────────────────────────────────────

    def get_status(self) -> PipelineStatus:
        """Get current pipeline health status."""
        status = PipelineStatus(
            is_running=self._is_running,
            is_healthy=self._total_errors < max(self._total_ingested * 0.1, 1),
            last_run=self._last_result.completed_at if self._last_result else "",
            last_success=(
                self._last_result.completed_at
                if self._last_result and self._last_result.status == IngestionStatus.SUCCESS
                else ""
            ),
            total_events_processed=self._total_ingested,
            events_last_24h=self._count_last_24h(),
            sources_active=len(self._pollers),
            sources_error=sum(
                1
                for s in self.scheduler.get_health().values()
                if isinstance(s, dict) and s.get("failures", 0) > 3
            ),
            source_statuses=self.scheduler.get_source_status(),
            error_rate=(self._total_errors / max(self._total_ingested + self._total_errors, 1)),
        )
        return status

    def get_last_result(self) -> IngestionResult | None:
        """Get the most recent ingestion result."""
        return self._last_result

    def get_stats(self) -> dict:
        """Get comprehensive pipeline statistics."""
        return {
            "pipeline": {
                "total_ingested": self._total_ingested,
                "total_errors": self._total_errors,
                "is_running": self._is_running,
            },
            "scheduler": self.scheduler.get_health(),
            "router": self.router.get_stats(),
            "deduplicator": self.deduplicator.get_stats(),
            "monitor": self.monitor.get_stats(),
            "pollers_registered": len(self._pollers),
        }

    def reset(self):
        """Reset all pipeline state."""
        self.deduplicator.reset()
        self.monitor.reset()
        self._buffer.clear()
        self._total_ingested = 0
        self._total_errors = 0
        self._last_result = None

    # ── Internal ──────────────────────────────────────────────────────────

    def _count_last_24h(self) -> int:
        """Count events ingested in the last 24 hours."""
        if not self._last_result:
            return 0
        return self._total_ingested  # Simplified; in production, track timestamps
