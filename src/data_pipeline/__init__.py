"""Macro Data Intelligence Pipeline — M1 Perception Layer.

The SINGLE data entry point for the Macro Research Agent.
All data flows through MacroPipeline.build_daily_macro_snapshot().

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
                                               MacroSnapshot
                                                       ↓
                                           ResearchCycleEngine

Design:
    - No synthetic data. All data from real sources.
    - Each component is single-responsibility.
    - Failures are logged, not fatal (quality="LOW" continues pipeline).
    - CollectorManager abstracts all data sources behind a single interface.
"""

from src.data_pipeline.collector_manager import CollectorManager
from src.data_pipeline.macro_pipeline import MacroPipeline
from src.data_pipeline.normalizer import MacroObservation, Normalizer
from src.data_pipeline.feature_engine import (
    FeatureDimension,
    FeatureEngine,
    FeaturePoint,
    FeatureSnapshot,
    IndicatorFeatures,
)
from src.data_pipeline.snapshot_builder import QualityReport, SnapshotBuilder, SourceReport
from src.data_pipeline.state_vector import (
    DimensionScore,
    MacroStateVector,
    StateVectorBuilder,
    StateVectorDimension,
)
from src.data_pipeline.validator import DataQualityValidator, ValidationResult, ValidatedDataPoint

__all__ = [
    # Pipeline
    "MacroPipeline",
    # Collector
    "CollectorManager",
    # Validator
    "DataQualityValidator",
    "ValidatedDataPoint",
    "ValidationResult",
    # Normalizer
    "Normalizer",
    "MacroObservation",
    # Feature Engine
    "FeatureEngine",
    "FeatureSnapshot",
    "FeaturePoint",
    "FeatureDimension",
    "IndicatorFeatures",
    # State Vector
    "StateVectorBuilder",
    "MacroStateVector",
    "StateVectorDimension",
    "DimensionScore",
    # Snapshot
    "SnapshotBuilder",
    "QualityReport",
    "SourceReport",
]
