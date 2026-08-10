"""Validation module — Shared data validation engine.

Independent of any specific Collector. Every data point entering the
pipeline passes through validation before normalization or storage.

Sprint 1 checks:
    - Value range (reject impossible values, e.g. DXY < 0, yield < -10%)
    - Timestamp sanity (reject future timestamps)
    - Null/missing fields
    - QualityScore computation

Design:
    → This module is a shared capability.
    → Any Collector (Yahoo, FRED, Bloomberg) uses the same validation.
    → Quality score is computed here, not in the Collector.
"""

import math
from datetime import datetime, timezone

from src.domain.macro_indicator import HypothesisDimension
from src.interfaces.validator import ValidationError, ValidatorInterface
from src.schemas.macro_data import MacroDataSchema, QualityFactor, QualityScore
from src.shared.logging import get_logger

logger = get_logger(__name__)

# ── Per-dimension value range rules ────────────────────────────────────
# Format: (min_acceptable, max_acceptable, description)
_RANGE_RULES: dict[HypothesisDimension, tuple[float, float, str]] = {
    HypothesisDimension.LIQUIDITY: (0.0, 200.0, "0-200 (DXY, Rates)"),
    HypothesisDimension.CREDIT: (0.0, 500.0, "0-500 (Spreads, HYG)"),
    HypothesisDimension.GROWTH: (-50.0, 100.0, "-50%-100% (GDP, PMI)"),
    HypothesisDimension.RISK_APPETITE: (0.0, 100.0, "0-100 (VIX), 0+ (Commodities)"),
    HypothesisDimension.INFLATION: (-10.0, 50.0, "-10%-50% (CPI range)"),
}

# Maximum number of hours in the future a timestamp may be
# (allows for timezone differences, but rejects obvious errors)
_MAX_FUTURE_HOURS: float = 26.0

# Minimum overall quality score for data to pass validation
_DEFAULT_QUALITY_THRESHOLD: float = 0.7


class DataValidator(ValidatorInterface):
    """Validates raw macro data before normalization and storage.

    Implements ValidatorInterface. Independent of any Collector.

    Checks applied:
        1. Value within dimension-specific range
        2. Timestamp is not in the future
        3. Value is not NaN or Infinity
        4. Computes QualityScore per data point
    """

    def __init__(self, quality_threshold: float = _DEFAULT_QUALITY_THRESHOLD) -> None:
        self._quality_threshold = quality_threshold

    # ── Public API ─────────────────────────────────────────────────

    async def validate(self, data: MacroDataSchema) -> MacroDataSchema:
        """Async wrapper — delegates to sync validation (no I/O operations)."""
        return self.validate_sync(data)

    def validate_sync(self, data: MacroDataSchema) -> MacroDataSchema:
        """Validate a single data point synchronously.

        Returns:
            The same MacroDataSchema with quality score populated.

        Raises:
            ValidationError: If data fails any check.
        """
        self._check_value_finite(data)  # MUST come before range check
        self._check_value_range(data)
        self._check_timestamp(data)

        # Compute quality score
        quality = self._compute_quality(data)
        if not quality.is_acceptable(self._quality_threshold):
            raise ValidationError(
                data,
                f"Quality score {quality.overall:.2f} below threshold {self._quality_threshold}",
            )

        return data.model_copy(update={"quality": quality})

    # ── Private checks ─────────────────────────────────────────────

    @staticmethod
    def _check_value_range(data: MacroDataSchema) -> None:
        """Validate value is within a plausible range for its indicator."""
        # Use a default wide range for symbols without explicit rules
        min_val, max_val, desc = _RANGE_RULES.get(
            _guess_dimension(data.symbol), (-1e6, 1e6, "unbounded")
        )
        if data.value < min_val:
            raise ValidationError(
                data,
                f"Value {data.value} below minimum {min_val} (expected range: {desc})",
                field="value",
            )
        if data.value > max_val:
            raise ValidationError(
                data,
                f"Value {data.value} above maximum {max_val} (expected range: {desc})",
                field="value",
            )

    @staticmethod
    def _check_timestamp(data: MacroDataSchema) -> None:
        """Reject timestamps that are unreasonably in the future."""
        now = datetime.now(timezone.utc)
        future_limit = now.timestamp() + _MAX_FUTURE_HOURS * 3600
        if data.timestamp.timestamp() > future_limit:
            raise ValidationError(
                data,
                f"Timestamp {data.timestamp.isoformat()} is in the future "
                f"(now={now.isoformat()}, max_future_hours={_MAX_FUTURE_HOURS})",
                field="timestamp",
            )

    @staticmethod
    def _check_value_finite(data: MacroDataSchema) -> None:
        """Reject NaN, Infinity, or None values."""
        if data.value is None:
            raise ValidationError(data, "Value is None", field="value")
        if math.isnan(data.value):
            raise ValidationError(data, "Value is NaN", field="value")
        if math.isinf(data.value):
            raise ValidationError(data, "Value is infinite", field="value")

    # ── Quality scoring ────────────────────────────────────────────

    @staticmethod
    def _compute_quality(data: MacroDataSchema) -> QualityScore:
        """Compute a per-data-point quality score.

        Sprint 1: baseline scores based on surface-level checks.
        Future: integrate missing data detection, outlier analysis,
                duplicate detection, and source reputation weighting.
        """
        factors: dict[QualityFactor, float] = {}

        # Completeness: no null fields → 1.0
        required = {"symbol", "timestamp", "value", "currency", "unit", "source"}
        present = sum(1 for f in required if getattr(data, f, None) is not None)
        factors[QualityFactor.COMPLETENESS] = present / len(required)

        # Timeliness: within 24h → 1.0, degrades to 0 over 7 days
        age_hours = (datetime.now(timezone.utc) - data.timestamp).total_seconds() / 3600
        if age_hours <= 24:
            factors[QualityFactor.TIMELINESS] = 1.0
        elif age_hours >= 168:  # 7 days
            factors[QualityFactor.TIMELINESS] = 0.0
        else:
            factors[QualityFactor.TIMELINESS] = 1.0 - (age_hours - 24) / (168 - 24)

        # Consistency: always 1.0 in Sprint 1 (no historical comparison yet)
        factors[QualityFactor.CONSISTENCY] = 1.0

        # Outlier: always 1.0 in Sprint 1 (no distribution model yet)
        factors[QualityFactor.OUTLIER] = 1.0

        # Duplicate: always 1.0 in Sprint 1 (no duplicate detection yet)
        factors[QualityFactor.DUPLICATE] = 1.0

        # Overall = weighted average (all equal in Sprint 1)
        weights = {
            QualityFactor.COMPLETENESS: 0.3,
            QualityFactor.TIMELINESS: 0.3,
            QualityFactor.CONSISTENCY: 0.15,
            QualityFactor.OUTLIER: 0.15,
            QualityFactor.DUPLICATE: 0.10,
        }
        overall = sum(factors[k] * weights[k] for k in QualityFactor)

        return QualityScore(
            overall=round(overall, 4),
            factors=factors,
        )


# ── Helper ─────────────────────────────────────────────────────────────


def _guess_dimension(symbol: str) -> HypothesisDimension:
    """Approximate which hypothesis dimension a symbol belongs to.

    Used by _check_value_range when no explicit mapping is available.
    This is a fallback — MacroIndicator should always carry explicit dimension.
    """
    symbol_upper = symbol.upper()
    if any(t in symbol_upper for t in ("DXY", "US10Y", "US2Y", "US5Y", "US30Y", "FED")):
        return HypothesisDimension.LIQUIDITY
    if any(t in symbol_upper for t in ("HYG", "LQD", "IG", "CDX", "SPREAD")):
        return HypothesisDimension.CREDIT
    if any(t in symbol_upper for t in ("VIX", "GC=", "GOLD", "COPPER", "HG=")):
        return HypothesisDimension.RISK_APPETITE
    if any(t in symbol_upper for t in ("CPI", "PPI", "BREAKEVEN", "INFLATION")):
        return HypothesisDimension.INFLATION
    return HypothesisDimension.GROWTH
