"""SnapshotBuilder — assemble the final MacroSnapshot with full traceability.

This is the final stage of the M1 pipeline. Takes the state vector,
feature snapshot, quality report, and builds the unified MacroSnapshot
that ResearchCycleEngine consumes.

Adds to MacroSnapshot:
    - state_vector: MacroStateVector (9-dimension scores)
    - feature_summary: dict (extracted features summary)
    - quality_report: QualityReport (validation statistics)
    - source_report: SourceReport (data source attribution)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from src.data_pipeline.feature_engine import FeatureSnapshot
from src.data_pipeline.state_vector import MacroStateVector
from src.data_pipeline.validator import ValidationResult
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Report Data Classes ─────────────────────────────────────────────────────


@dataclass
class QualityReport:
    """Aggregated data quality report for the snapshot."""

    total_indicators: int = 0
    valid: int = 0
    degraded: int = 0
    failed: int = 0
    pass_rate: float = 1.0
    issues: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class SourceReport:
    """Data source attribution report."""

    sources_used: list[str] = field(default_factory=list)
    indicators_per_source: dict[str, int] = field(default_factory=dict)
    collection_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    notes: str = ""


# ── SnapshotBuilder ─────────────────────────────────────────────────────────


class SnapshotBuilder:
    """Builds the final MacroSnapshot with full provenance.

    The output is a dict-compatible structure that can be persisted or
    passed directly to ResearchCycleEngine.

    Usage:
        builder = SnapshotBuilder(output_dir="snapshot/")
        snapshot = builder.build(state_vector, features, validation_result)
        builder.persist(snapshot, date_str="2026-07-21")
    """

    def __init__(self, output_dir: str = "snapshot") -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ──────────────────────────────────────────────────────────

    def build(
        self,
        state_vector: MacroStateVector,
        features: FeatureSnapshot,
        validation: ValidationResult | None = None,
    ) -> dict:
        """Build the final MacroSnapshot as a dictionary.

        Returns a dict matching the existing MacroSnapshot schema
        but enhanced with state_vector, feature_summary, quality_report,
        and source_report.
        """
        quality = self._build_quality_report(validation) if validation else QualityReport()
        source = self._build_source_report(features)

        snapshot = {
            "meta": {
                "pipeline_version": "M1",
                "timestamp": datetime.now(UTC).isoformat(),
                "risk_regime": state_vector.risk_regime,
                "dominant_theme": state_vector.dominant_theme,
                "aggregate_score": state_vector.aggregate_score,
            },
            "state_vector": {
                dim.value: {
                    "score": s.score,
                    "confidence": s.confidence,
                    "direction": s.direction,
                    "drivers": s.drivers,
                    "supporting_indicators": s.supporting_indicators,
                    "narrative_seeds": s.narrative_seeds,
                }
                for dim, s in state_vector.dimensions.items()
            },
            "feature_summary": {
                "total_indicators": len(features.indicators),
                "dimension_summaries": features.dimension_summaries,
                "indicators": {
                    name: {
                        "name": ind.name,
                        "dimension": ind.macro_dimension,
                        "raw_value": ind.raw_value,
                        "features": [
                            {"dimension": f.dimension.value, "value": f.value, "label": f.label}
                            for f in ind.features
                        ],
                    }
                    for name, ind in features.indicators.items()
                },
            },
            "quality_report": {
                "total_indicators": quality.total_indicators,
                "valid": quality.valid,
                "degraded": quality.degraded,
                "failed": quality.failed,
                "pass_rate": quality.pass_rate,
                "issues": quality.issues,
            },
            "source_report": {
                "sources_used": source.sources_used,
                "indicators_per_source": source.indicators_per_source,
                "collection_timestamp": source.collection_timestamp.isoformat(),
            },
            "summary": state_vector.summary,
        }

        logger.info(
            "snapshot_builder_done | indicators=%d | quality=%.0f%% | regime=%s | theme=%s",
            len(features.indicators),
            quality.pass_rate * 100,
            state_vector.risk_regime,
            state_vector.dominant_theme,
        )
        return snapshot

    def persist(self, snapshot: dict, date_str: str | None = None) -> str:
        """Persist snapshot to JSON file.

        Args:
            snapshot: The snapshot dict from build().
            date_str: ISO date string for filename (defaults to today).

        Returns:
            Path to the saved file.
        """
        if date_str is None:
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")

        filename = self._output_dir / f"macro_snapshot_{date_str}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False, default=str)

        logger.info("snapshot_persisted | file=%s", filename)
        return str(filename)

    # ── Internal ────────────────────────────────────────────────────────────

    def _build_quality_report(self, validation: ValidationResult) -> QualityReport:
        return QualityReport(
            total_indicators=validation.total_points,
            valid=validation.valid_points,
            degraded=validation.degraded_points,
            failed=validation.failed_points,
            pass_rate=validation.pass_rate,
            issues=validation.issues,
        )

    def _build_source_report(self, features: FeatureSnapshot) -> SourceReport:
        sources: set[str] = set()
        per_source: dict[str, int] = {}

        for ind in features.indicators.values():
            source = "Yahoo"  # Currently all come from Yahoo
            sources.add(source)
            per_source[source] = per_source.get(source, 0) + 1

        return SourceReport(
            sources_used=sorted(sources),
            indicators_per_source=per_source,
        )
