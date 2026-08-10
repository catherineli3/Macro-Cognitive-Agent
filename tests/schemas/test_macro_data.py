"""Tests — MacroDataSchema (Data Contract).

The single data contract for the entire pipeline.
All modules must produce/consume this schema.
"""

from datetime import datetime, timezone

import pytest

from src.schemas.macro_data import MacroDataSchema, QualityFactor, QualityScore


class TestQualityScore:
    """QualityScore — default values and threshold checking."""

    def test_default_is_perfect(self) -> None:
        q = QualityScore()
        assert q.overall == 1.0
        assert all(v == 1.0 for v in q.factors.values())

    def test_is_acceptable_default_threshold(self) -> None:
        good = QualityScore(overall=0.8)
        assert good.is_acceptable() is True

        bad = QualityScore(overall=0.5)
        assert bad.is_acceptable() is False

    def test_is_acceptable_custom_threshold(self) -> None:
        q = QualityScore(overall=0.6)
        assert q.is_acceptable(threshold=0.5) is True
        assert q.is_acceptable(threshold=0.7) is False

    def test_flags_default_empty(self) -> None:
        q = QualityScore()
        assert q.flags == []

    def test_with_flags(self) -> None:
        q = QualityScore(flags=["delayed", "interpolated"])
        assert "delayed" in q.flags

    def test_factors_include_all_dimensions(self) -> None:
        q = QualityScore()
        assert QualityFactor.COMPLETENESS in q.factors
        assert QualityFactor.TIMELINESS in q.factors
        assert QualityFactor.CONSISTENCY in q.factors
        assert QualityFactor.OUTLIER in q.factors
        assert QualityFactor.DUPLICATE in q.factors


class TestMacroDataSchema:
    """MacroDataSchema — the canonical data contract."""

    @pytest.fixture
    def valid_data(self) -> dict:
        return {
            "symbol": "DXY",
            "timestamp": datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc),
            "value": 104.5,
            "currency": "USD",
            "unit": "Index",
            "source": "Yahoo",
        }

    def test_create_valid_schema(self, valid_data: dict) -> None:
        ms = MacroDataSchema(**valid_data)
        assert ms.symbol == "DXY"
        assert ms.value == 104.5
        assert ms.quality.overall == 1.0  # default quality

    def test_timestamp_auto_utc(self) -> None:
        """Naive datetime should be converted to UTC."""
        ms = MacroDataSchema(
            symbol="DXY",
            timestamp=datetime(2026, 7, 13, 10, 0, 0),  # naive
            value=104.5,
            source="Yahoo",
        )
        assert ms.timestamp.tzinfo is not None

    def test_reject_empty_symbol(self) -> None:
        with pytest.raises(ValueError):
            MacroDataSchema(
                symbol="",
                timestamp=datetime(2026, 7, 13, tzinfo=timezone.utc),
                value=104.5,
                source="Yahoo",
            )

    def test_ingested_at_auto_generated(self, valid_data: dict) -> None:
        ms = MacroDataSchema(**valid_data)
        assert ms.ingested_at is not None
        assert ms.ingested_at.tzinfo is not None

    def test_repr_format(self, valid_data: dict) -> None:
        ms = MacroDataSchema(**valid_data)
        rep = repr(ms)
        assert "DXY" in rep
        assert "104.5" in rep

    def test_custom_quality(self, valid_data: dict) -> None:
        q = QualityScore(overall=0.85)
        ms = MacroDataSchema(**valid_data, quality=q)
        assert ms.quality.overall == 0.85

    def test_future_timestamp_allowed_by_schema(self, valid_data: dict) -> None:
        """Schema itself doesn't validate future timestamps.
        That's the Validator's job.
        """
        ms = MacroDataSchema(
            symbol="DXY",
            timestamp=datetime(2099, 1, 1, tzinfo=timezone.utc),
            value=104.5,
            source="Yahoo",
        )
        assert ms.timestamp.year == 2099

    def test_negative_value_allowed_by_schema(self, valid_data: dict) -> None:
        """Schema allows negative values — Validator rejects them."""
        ms = MacroDataSchema(
            symbol="US10Y",
            timestamp=datetime(2026, 7, 13, tzinfo=timezone.utc),
            value=-5.0,
            source="Yahoo",
        )
        assert ms.value == -5.0
