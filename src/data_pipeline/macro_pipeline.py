"""MacroPipeline — the single entry point for all macro data.

This is the ONLY way data enters the Macro Research Agent.
No direct calls to YahooCollector or any other source anywhere else.

Architecture:
    CollectorManager  →  DataQualityValidator  →  Normalizer
         ↓                      ↓                     ↓
    MacroData[]          ValidatedData[]        MacroObservation[]
                                                       ↓
                                               FeatureEngine
                                                       ↓
                                               FeatureSnapshot
                                                       ↓
                                            StateVectorBuilder
                                                       ↓
                                             MacroStateVector
                                                       ↓
                                             SnapshotBuilder
                                                       ↓
                                               MacroSnapshot (dict)
                                                       ↓
                                           ResearchCycleEngine

Usage:
    pipeline = MacroPipeline()
    snapshot = pipeline.build_daily_macro_snapshot()
    # Pass snapshot to ResearchCycleEngine
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.data_pipeline.collector_manager import CollectorManager
from src.data_pipeline.feature_engine import FeatureEngine
from src.data_pipeline.normalizer import Normalizer
from src.data_pipeline.snapshot_builder import SnapshotBuilder
from src.data_pipeline.state_vector import StateVectorBuilder
from src.data_pipeline.validator import DataQualityValidator
from src.shared.logging import get_logger

logger = get_logger(__name__)


class MacroPipeline:
    """Unified macro data pipeline — the Agent's perception layer.

    A single call to build_daily_macro_snapshot() produces the complete
    MacroSnapshot that powers all downstream research.

    Design guarantees:
        1. All data from real sources (no synthetic).
        2. Every data point is validated and quality-scored.
        3. Failed data points are degraded, not fatal.
        4. Output is fully traceable to source.
        5. All intermediate stages are inspectable.

    Attributes:
        collector: CollectorManager — manages all data source adapters.
        validator: DataQualityValidator — validates every data point.
        normalizer: Normalizer — normalizes to unified MacroObservation format.
        feature_engine: FeatureEngine — extracts trading features from raw data.
        state_builder: StateVectorBuilder — builds 9-dimension state vector.
        snapshot_builder: SnapshotBuilder — assembles final MacroSnapshot.
    """

    def __init__(
        self,
        output_dir: str = "snapshot",
        history_window: int = 30,
    ) -> None:
        self.collector = CollectorManager()
        self.validator = DataQualityValidator()
        self.normalizer = Normalizer()
        self.feature_engine = FeatureEngine(history_window=history_window)
        self.state_builder = StateVectorBuilder()
        self.snapshot_builder = SnapshotBuilder(output_dir=output_dir)

    # ── Public API ──────────────────────────────────────────────────────────

    def build_daily_macro_snapshot(
        self,
        date: Optional[datetime] = None,
        for_dimension: Optional[str] = None,
        persist: bool = True,
    ) -> dict:
        """Run the complete pipeline and produce a MacroSnapshot.

        Args:
            date: Target date (defaults to now). Used for filename only.
            for_dimension: Optional filter to collect only one dimension.
            persist: Whether to save snapshot to disk.

        Returns:
            Complete MacroSnapshot dict ready for ResearchCycleEngine.

        Raises:
            RuntimeError: If zero indicators could be collected.
        """
        target_date = date or datetime.now(timezone.utc)
        date_str = target_date.strftime("%Y-%m-%d")

        logger.info(
            "macro_pipeline_start | date=%s dimension=%s",
            date_str,
            for_dimension or "all",
        )

        # ── Stage 1: Collect ────────────────────────────────────────────────
        raw_data = self.collector.collect(for_dimension=for_dimension)

        if not raw_data:
            raise RuntimeError(
                f"MacroPipeline: zero indicators collected for {date_str}. "
                "Check network connectivity and data source availability."
            )

        values_collected = sum(1 for d in raw_data if d.value is not None)
        logger.info(
            "pipeline_collect | total=%d with_value=%d",
            len(raw_data),
            values_collected,
        )

        # ── Stage 2: Validate ───────────────────────────────────────────────
        validation_result = self.validator.validate(raw_data)

        # ── Stage 3: Normalize ──────────────────────────────────────────────
        observations = self.normalizer.normalize(validation_result.points)

        # ── Stage 4: Feature Engineering ────────────────────────────────────
        features = self.feature_engine.extract_features(observations)

        # ── Stage 5: State Vector ───────────────────────────────────────────
        state_vector = self.state_builder.build(features)

        # ── Stage 6: Snapshot Assembly ──────────────────────────────────────
        snapshot = self.snapshot_builder.build(
            state_vector=state_vector,
            features=features,
            validation=validation_result,
        )

        # ── Stage 7: Persist ────────────────────────────────────────────────
        if persist:
            self.snapshot_builder.persist(snapshot, date_str=date_str)

        logger.info(
            "macro_pipeline_complete | date=%s | score=%.2f | theme=%s | regime=%s",
            date_str,
            state_vector.aggregate_score,
            state_vector.dominant_theme,
            state_vector.risk_regime,
        )

        return snapshot

    def get_collection_stats(self) -> dict:
        """Return collection statistics from the current session."""
        return self.collector.get_stats()

    def reset(self) -> None:
        """Reset all internal state (history, counters, quality history)."""
        self.validator.reset_history()
        # Re-initialize feature engine to clear history
        self.feature_engine = FeatureEngine(
            history_window=30
        )  # Default window


# ── Module-level convenience ────────────────────────────────────────────────

_default_pipeline: Optional[MacroPipeline] = None


def get_pipeline() -> MacroPipeline:
    """Get or create the default singleton MacroPipeline."""
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = MacroPipeline()
    return _default_pipeline


def build_daily_macro_snapshot(
    date: Optional[datetime] = None,
    for_dimension: Optional[str] = None,
    persist: bool = True,
) -> dict:
    """Convenience function — build snapshot via the default pipeline."""
    return get_pipeline().build_daily_macro_snapshot(
        date=date,
        for_dimension=for_dimension,
        persist=persist,
    )
