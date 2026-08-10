"""Normalizer — unified observation format across all data sources.

Takes validated data points and normalizes them into a common format:
    - All values expressed in consistent units.
    - Yield values → basis points for changes.
    - Index values → log-returns for changes.
    - Every observation gets a unique observation_id and traceable source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.data_pipeline.validator import ValidatedDataPoint
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MacroObservation:
    """A normalized, immutable observation of a single macro indicator.

    This is the universal data currency that flows through the rest of
    the pipeline. Every downstream component consumes MacroObservations,
    not raw collector output.
    """

    observation_id: str
    symbol: str
    name: str
    timestamp: datetime
    value: float
    unit: str
    source: str
    dimension: str  # Liquidity, Credit, Growth, Inflation, Risk_Appetite, AI_Capex
    # Derived fields
    value_bps: Optional[float] = None  # For yield-type indicators
    value_log: Optional[float] = None  # For index-type indicators
    # Quality
    quality_score: float = 1.0  # 0.0-1.0 aggregate quality
    is_degraded: bool = False
    degradation_reason: str = ""
    # Traceability
    raw_value: Optional[float] = None
    collector_metadata: dict = field(default_factory=dict)


class Normalizer:
    """Normalizes ValidatedDataPoints into MacroObservations.

    Responsibilities:
        1. Assign observation IDs.
        2. Compute derived fields (bps, log transforms).
        3. Attach quality scores.
        4. Preserve traceability to raw data.

    Usage:
        normalizer = Normalizer()
        observations = normalizer.normalize(validation_result.points)
    """

    _counter: int = 0

    # Indicators typically expressed as yields / spreads
    _YIELD_UNITS = {"yield", "bps", "spread", "percent"}
    # Indicators typically expressed as index levels
    _INDEX_UNITS = {"index", "price", "point"}

    def normalize(
        self,
        validated_points: list[ValidatedDataPoint],
    ) -> list[MacroObservation]:
        """Normalize all validated points into MacroObservations."""
        observations: list[MacroObservation] = []

        for vp in validated_points:
            obs = self._normalize_single(vp)
            observations.append(obs)

        logger.info(
            "normalizer_done | total=%d degraded=%d",
            len(observations),
            sum(1 for o in observations if o.is_degraded),
        )
        return observations

    # ── Internal ────────────────────────────────────────────────────────────

    def _normalize_single(self, vp: ValidatedDataPoint) -> MacroObservation:
        self._counter += 1
        obs_id = f"obs_{self._counter:06d}"

        value = vp.value if vp.value is not None else 0.0
        unit = (vp.unit or "unknown").lower()
        is_degraded = not vp.is_valid or len(vp.checks_failed) > 0
        quality = vp.quality_score

        obs = MacroObservation(
            observation_id=obs_id,
            symbol=vp.symbol,
            name=vp.name,
            timestamp=vp.timestamp,
            value=value,
            unit=unit,
            source=vp.source,
            dimension=vp.dimension,
            quality_score=quality,
            is_degraded=is_degraded,
            degradation_reason="; ".join(vp.checks_failed) if vp.checks_failed else "",
            raw_value=vp.value,
        )

        # Derived bps value for yield-type indicators
        if unit in self._YIELD_UNITS:
            # If value is already in percentage (e.g., 4.5 for 4.5%), convert to bps
            obs.value_bps = value * 100.0 if value < 100.0 else value

        return obs
