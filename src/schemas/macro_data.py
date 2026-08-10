"""MacroDataSchema — The single data contract for the entire Pipeline.

ALL modules communicate exclusively through MacroDataSchema.
Direct dict, JSON, or DataFrame across module boundaries is PROHIBITED.

This is the canonical data format enforced from Sprint 1 onward.
"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class QualityFactor(str, Enum):
    """Dimensions that contribute to the data quality score."""

    COMPLETENESS = "completeness"
    TIMELINESS = "timeliness"
    CONSISTENCY = "consistency"
    OUTLIER = "outlier"
    DUPLICATE = "duplicate"


class QualityScore(BaseModel):
    """Composite data quality score for a single observation.

    Each factor is scored 0.0 (worst) to 1.0 (best).
    The overall score is a weighted combination.

    Future expansion:
        - Source reputation weighting
        - Historical consistency tracking
        - Cross-source validation
    """

    overall: float = Field(default=1.0, ge=0.0, le=1.0, description="Aggregated quality score 0-1")
    factors: dict[QualityFactor, float] = Field(
        default_factory=lambda: {
            QualityFactor.COMPLETENESS: 1.0,
            QualityFactor.TIMELINESS: 1.0,
            QualityFactor.CONSISTENCY: 1.0,
            QualityFactor.OUTLIER: 1.0,
            QualityFactor.DUPLICATE: 1.0,
        },
        description="Per-factor quality scores 0-1",
    )
    flags: list[str] = Field(default_factory=list, description="Human-readable quality flags, e.g. ['delayed', 'interpolated']")

    def is_acceptable(self, threshold: float = 0.7) -> bool:
        """Return True if overall quality meets the minimum threshold."""
        return self.overall >= threshold


class MacroDataSchema(BaseModel):
    """Canonical data contract for a single macro-economic observation.

    Every Collector, Normalizer, and Validator MUST produce/consume
    this schema. No other data format is permitted across module boundaries.

    Examples:
        >>> ms = MacroDataSchema(
        ...     symbol="DXY",
        ...     timestamp=datetime(2026, 7, 13, tzinfo=timezone.utc),
        ...     value=104.5,
        ...     currency="Index",
        ...     unit="Point",
        ...     source="Yahoo",
        ... )
    """

    symbol: str = Field(..., min_length=1, max_length=20, description="Ticker symbol, e.g. 'DXY', 'US10Y'")
    timestamp: datetime = Field(..., description="Observation timestamp (must be timezone-aware)")
    value: float = Field(..., description="Numeric observation value")
    currency: str = Field(default="USD", description="Currency denomination")
    unit: str = Field(default="Index", description="Unit of measurement, e.g. 'Percent', 'Index', 'USD'")
    source: str = Field(..., min_length=1, description="Data source name, e.g. 'Yahoo', 'FRED'")
    quality: QualityScore = Field(default_factory=QualityScore, description="Data quality assessment")

    # ── Pipeline metadata (auto-populated) ──────────────────────────────
    ingested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the data entered the pipeline",
    )

    @model_validator(mode="after")
    def _ensure_tz_aware(self) -> "MacroDataSchema":
        """All timestamps MUST be timezone-aware (UTC enforced)."""
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
        return self

    def __repr__(self) -> str:
        return f"<MacroData {self.symbol}={self.value} @ {self.timestamp:%Y-%m-%d} [{self.source}] q={self.quality.overall:.2f}>"
