"""V6.1 Live Information Intake — Unified real-time intelligence ingestion.

Design principle: Every piece of macro-relevant information enters through
a single unified pipeline, regardless of source (Reuters, Fed speeches,
economic data, ETF flows, CME FedWatch, 13F filings, etc.).

Pipeline:
    Raw Event (source-specific format)
        → SourceRouter (route to handler)
        → NormalizedEvent (canonical format)
        → DuplicateDetector (merge similar)
        → FreshnessMonitor (track staleness)
        → IngestionPipeline (orchestrate)
        → Evidence Graph (via existing FusionEngine)

All information feeds into the existing V4 Evidence Graph system.
"""

from src.live_intelligence.duplicate_detector import DuplicateDetector, DuplicateReport
from src.live_intelligence.event_scheduler import EventScheduler, SourceSchedule
from src.live_intelligence.freshness_monitor import FreshnessMonitor, FreshnessReport
from src.live_intelligence.ingestion_pipeline import IngestionPipeline
from src.live_intelligence.schemas import (
    EventImportance,
    IngestionResult,
    NormalizedEvent,
    PipelineStatus,
    RawEvent,
    SourceType,
)
from src.live_intelligence.source_router import SourceRouter

__all__ = [
    # Schemas
    "RawEvent",
    "NormalizedEvent",
    "SourceType",
    "EventImportance",
    "IngestionResult",
    "PipelineStatus",
    # Engines
    "SourceRouter",
    "EventScheduler",
    "SourceSchedule",
    "IngestionPipeline",
    "FreshnessMonitor",
    "FreshnessReport",
    "DuplicateDetector",
    "DuplicateReport",
]
