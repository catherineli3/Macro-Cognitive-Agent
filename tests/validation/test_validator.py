"""Tests — Validator module (DataValidator).

Covers:
    - Value range validation (per dimension)
    - Timestamp validation (future rejection)
    - NaN / Infinity / None rejection
    - Quality score computation
"""

from datetime import datetime, timezone

import pytest

from src.domain.macro_indicator import HypothesisDimension
from src.interfaces.validator import ValidationError
from src.schemas.macro_data import MacroDataSchema, QualityScore
from src.validation.validator import DataValidator, _guess_dimension


@pytest.fixture
def validator() -> DataValidator:
    return DataValidator(quality_threshold=0.5)  # lower threshold for tests


@pytest.fixture
def valid_dxy() -> MacroDataSchema:
    return MacroDataSchema(
        symbol="DXY",
        timestamp=datetime(2026, 7, 13, 10, 0, 0, tzinfo=timezone.utc),
        value=104.5,
        currency="USD",
        unit="Index",
        source="Yahoo",
    )


class TestValueRange:
    """Reject out-of-range values."""

    def test_valid_value_passes(self, validator: DataValidator, valid_dxy: MacroDataSchema) -> None:
        result = validator.validate_sync(valid_dxy)
        assert result.value == 104.5

    def test_negative_dxy_rejected(self, validator: DataValidator, valid_dxy: MacroDataSchema) -> None:
        data = valid_dxy.model_copy(update={"value": -5.0})
        with pytest.raises(ValidationError, match="below minimum"):
            validator.validate_sync(data)

    def test_extreme_high_value_rejected(self, validator: DataValidator, valid_dxy: MacroDataSchema) -> None:
        data = valid_dxy.model_copy(update={"value": 99999.0})
        with pytest.raises(ValidationError, match="above maximum"):
            validator.validate_sync(data)

    def test_negative_yield_rejected(self, validator: DataValidator) -> None:
        data = MacroDataSchema(
            symbol="US10Y",  # mapped to LIQUIDITY → range 0-200
            timestamp=datetime(2026, 7, 13, tzinfo=timezone.utc),
            value=-500.0,  # < 0 → reject
            source="Yahoo",
        )
        with pytest.raises(ValidationError):
            validator.validate_sync(data)


class TestTimestampValidation:
    """Reject timestamps unreasonably in the future."""

    def test_current_timestamp_passes(self, validator: DataValidator, valid_dxy: MacroDataSchema) -> None:
        result = validator.validate_sync(valid_dxy)
        assert result is not None

    def test_far_future_rejected(self, validator: DataValidator, valid_dxy: MacroDataSchema) -> None:
        data = valid_dxy.model_copy(
            update={"timestamp": datetime(2099, 1, 1, tzinfo=timezone.utc)}
        )
        with pytest.raises(ValidationError, match="future"):
            validator.validate_sync(data)

    def test_near_future_passes(self, validator: DataValidator, valid_dxy: MacroDataSchema) -> None:
        """Within the ~26h grace window should be allowed."""
        from datetime import timedelta

        near_future = datetime.now(timezone.utc) + timedelta(hours=2)
        data = valid_dxy.model_copy(update={"timestamp": near_future})
        result = validator.validate_sync(data)
        assert result is not None


class TestValueFiniteness:
    """Reject NaN, Infinity, and None values."""

    def test_nan_rejected(self, validator: DataValidator, valid_dxy: MacroDataSchema) -> None:
        import math

        data = valid_dxy.model_copy(update={"value": float("nan")})
        with pytest.raises(ValidationError, match="NaN"):
            validator.validate_sync(data)

    def test_infinity_rejected(self, validator: DataValidator, valid_dxy: MacroDataSchema) -> None:
        data = valid_dxy.model_copy(update={"value": float("inf")})
        with pytest.raises(ValidationError, match="infinite"):
            validator.validate_sync(data)


class TestQualityComputation:
    """Quality score is computed during validation."""

    def test_quality_score_attached(self, validator: DataValidator, valid_dxy: MacroDataSchema) -> None:
        result = validator.validate_sync(valid_dxy)
        assert isinstance(result.quality, QualityScore)
        assert result.quality.overall > 0

    def test_quality_below_threshold_rejected(self, valid_dxy: MacroDataSchema) -> None:
        strict = DataValidator(quality_threshold=0.95)
        # Old data will have low timeliness → low overall score
        old_data = valid_dxy.model_copy(
            update={
                "timestamp": datetime(2026, 7, 1, tzinfo=timezone.utc),  # 12 days old
            }
        )
        with pytest.raises(ValidationError, match="Quality score"):
            strict.validate_sync(old_data)

    def test_quality_flags_empty_by_default(self, validator: DataValidator, valid_dxy: MacroDataSchema) -> None:
        result = validator.validate_sync(valid_dxy)
        assert result.quality.flags == []


class TestGuessDimension:
    """Fallback dimension guessing from symbol name."""

    def test_dxy_guesses_liquidity(self) -> None:
        assert _guess_dimension("DXY") == HypothesisDimension.LIQUIDITY

    def test_us10y_guesses_liquidity(self) -> None:
        assert _guess_dimension("US10Y") == HypothesisDimension.LIQUIDITY

    def test_hyg_guesses_credit(self) -> None:
        assert _guess_dimension("HYG") == HypothesisDimension.CREDIT

    def test_vix_guesses_risk_appetite(self) -> None:
        assert _guess_dimension("^VIX") == HypothesisDimension.RISK_APPETITE

    def test_gold_guesses_risk_appetite(self) -> None:
        assert _guess_dimension("GC=F") == HypothesisDimension.RISK_APPETITE

    def test_unknown_guesses_growth(self) -> None:
        assert _guess_dimension("SOMETHING_ELSE") == HypothesisDimension.GROWTH


class TestValidationError:
    """ValidationError carries context for debugging."""

    def test_error_contains_reason(self, validator: DataValidator, valid_dxy: MacroDataSchema) -> None:
        data = valid_dxy.model_copy(update={"value": float("nan")})
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_sync(data)
        assert "NaN" in str(exc_info.value)

    def test_error_contains_schema(self, validator: DataValidator, valid_dxy: MacroDataSchema) -> None:
        data = valid_dxy.model_copy(update={"value": float("nan")})
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_sync(data)
        assert exc_info.value.schema is data
