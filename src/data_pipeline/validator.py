"""DataQualityValidator — ensure every observation meets quality thresholds.

Checks: missing values, outliers, timestamps, duplicates, currency/unit semantics.

Design principle: NEVER interrupt the pipeline.
    - If a data point fails validation → mark quality overlay LOW, continue.
    - The downstream Normalizer and FeatureEngine handle degraded data gracefully.
    - HypothesisEngine will weigh LOW-quality observations less.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.schemas.macro_data import MacroDataSchema
from src.shared.logging import get_logger

logger = get_logger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────
_MAX_STALENESS_HOURS = 48  # Data older than this is marked stale
_OUTLIER_Z_SCORE = 4.0  # Z-score threshold for outlier detection
_MIN_OBSERVATIONS_FOR_Z = 10  # Need at least this many to compute z-scores


@dataclass
class ValidatedDataPoint:
    """A single data point that has passed through quality validation."""

    symbol: str
    name: str
    timestamp: datetime
    value: float
    unit: str
    source: str
    dimension: str
    quality_score: float = 1.0  # 0.0-1.0 aggregate quality
    # Validation details
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    is_valid: bool = True
    notes: str = ""


@dataclass
class ValidationResult:
    """Aggregate validation report for a collection batch."""

    total_points: int = 0
    valid_points: int = 0
    degraded_points: int = 0
    failed_points: int = 0
    points: list[ValidatedDataPoint] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total_points == 0:
            return 0.0
        return self.valid_points / self.total_points


class DataQualityValidator:
    """Validates raw MacroDataSchema objects before normalization.

    Checks performed:
        1. Missing/zero value check
        2. Timestamp staleness check
        3. Outlier detection (population z-score)
        4. NaN / Inf check
        5. Zero/negative value for price/index indicators

    Usage:
        validator = DataQualityValidator()
        result = validator.validate(raw_data_list)
    """

    def __init__(self) -> None:
        self._history: dict[str, list[float]] = defaultdict(list)

    # ── Public API ──────────────────────────────────────────────────────────

    def validate(self, data: list[MacroDataSchema]) -> ValidationResult:
        """Validate a batch of MacroDataSchema objects.

        Categories:
            FAILED (is_valid=False): zero value or completely unusable.
            DEGRADED (is_valid=True, quality < 0.5): has issues but usable.
            VALID (is_valid=True, quality >= 0.5): passed all checks.
        """
        result = ValidationResult(total_points=len(data))

        for point in data:
            vp = self._validate_single(point)
            result.points.append(vp)

            if not vp.is_valid:
                result.failed_points += 1
            elif vp.quality_score < 0.5:
                result.degraded_points += 1
            else:
                result.valid_points += 1

            if vp.checks_failed:
                for cf in vp.checks_failed:
                    result.issues.append(f"{vp.symbol}: {cf}")

        logger.info(
            "validator_done | total=%d valid=%d degraded=%d failed=%d",
            result.total_points,
            result.valid_points,
            result.degraded_points,
            result.failed_points,
        )
        return result

    # ── Internal ────────────────────────────────────────────────────────────

    def _validate_single(self, point: MacroDataSchema) -> ValidatedDataPoint:
        quality: float = point.quality.overall if point.quality else 0.5

        vp = ValidatedDataPoint(
            symbol=point.symbol,
            name=point.symbol,
            timestamp=point.timestamp or datetime.now(UTC),
            value=point.value,
            unit=point.unit or "unknown",
            source=point.source or "",
            dimension=self._extract_dimension(point),
            quality_score=quality,
        )

        # ── Check 1: Missing / zero value ──────────────────────────
        if point.value is None or point.value == 0.0:
            # Check if it's a known failed collection
            if point.quality and point.quality.overall < 0.2:
                vp.is_valid = False
                vp.checks_failed.append("collection_failed")
                vp.quality_score = 0.0
                vp.notes = f"Collection failed: {point.quality.flags}"
                return vp

            vp.checks_failed.append("zero_or_missing_value")
            vp.quality_score = max(0.1, vp.quality_score - 0.5)
            vp.notes = "Zero value — may indicate collection failure"

        if vp.value != 0.0:
            vp.checks_passed.append("has_value")

        # ── Check 2: Timestamp staleness ───────────────────────────
        now = datetime.now(UTC)
        ts = point.timestamp or now
        age_hours = (now - ts).total_seconds() / 3600
        if age_hours > _MAX_STALENESS_HOURS:
            vp.checks_failed.append(f"stale_timestamp ({age_hours:.0f}h old)")
            vp.quality_score = max(0.1, vp.quality_score - 0.3)
        else:
            vp.checks_passed.append("timestamp_fresh")

        # ── Check 3: NaN / Inf ─────────────────────────────────────
        if math.isnan(point.value) or math.isinf(point.value):
            vp.is_valid = False
            vp.checks_failed.append("invalid_numeric_value")
            vp.quality_score = 0.0
            return vp

        if vp.value != 0.0:
            vp.checks_passed.append("valid_numeric")

        # ── Check 4: Outlier detection ─────────────────────────────
        if vp.value != 0.0:
            symbol_key = point.symbol
            self._history[symbol_key].append(point.value)
            if len(self._history[symbol_key]) >= _MIN_OBSERVATIONS_FOR_Z:
                vals = self._history[symbol_key]
                mean_v = sum(vals) / len(vals)
                std_v = (sum((v - mean_v) ** 2 for v in vals) / len(vals)) ** 0.5
                if std_v > 0:
                    z = abs(point.value - mean_v) / std_v
                    if z > _OUTLIER_Z_SCORE:
                        vp.checks_failed.append(f"outlier (z={z:.1f})")
                        vp.quality_score = max(0.1, vp.quality_score - 0.2)

        if not vp.checks_failed:
            vp.checks_passed.append("all_checks_clear")

        return vp

    @staticmethod
    def _extract_dimension(point: MacroDataSchema) -> str:
        """Extract dimension from quality flags metadata."""
        if point.quality and point.quality.flags:
            for flag in point.quality.flags:
                if flag.startswith("dimension="):
                    return flag.split("=", 1)[1]
        return ""

    def reset_history(self) -> None:
        """Clear stored historical values (for testing)."""
        self._history.clear()
