"""Tests — Integration: full pipeline flow.

End-to-end test: Collector → Validator → Normalizer → Repository.

This verifies the complete Sprint 1 data pipeline works end-to-end.
"""

from datetime import UTC, datetime

import pytest

from src.collector.yahoo import YahooCollector
from src.domain.macro_indicator import Frequency, HypothesisDimension, MacroIndicator
from src.normalizer.normalizer import DataNormalizer
from src.schemas.macro_data import MacroDataSchema
from src.storage.engine import dispose_engine
from src.storage.repository import SqlMacroRepository
from src.validation.validator import DataValidator


@pytest.fixture(autouse=True)
async def _pipeline_cleanup() -> None:
    yield
    await dispose_engine()


class TestPipelineIntegration:
    """Full pipeline: Collector → Validator → Normalizer → Repository."""

    @pytest.mark.asyncio
    async def test_full_pipeline_dxy(self) -> None:
        """End-to-end: fetch DXY, validate, normalize, persist, retrieve.

        Note: Yahoo Finance API may rate-limit. If this test fails with
        YFRateLimitError, it's an infrastructure issue, not a code bug.
        """
        from src.shared.exceptions import CollectionError

        # ── Step 1: Collect ──────────────────────────────────────
        collector = YahooCollector()
        indicator = MacroIndicator(
            symbol="DXY",
            name="US Dollar Index",
            category="Currency",
            frequency=Frequency.DAILY,
            unit="Index",
            source="Yahoo",
            hypothesis_dimension=HypothesisDimension.LIQUIDITY,
        )
        try:
            raw = await collector.collect(indicator)
        except CollectionError as exc:
            if "Rate limited" in str(exc) or "Too Many Requests" in str(exc):
                pytest.skip("Yahoo Finance rate limited — skipping integration test")
            raise

        assert raw.symbol == "DXY"
        assert isinstance(raw.value, float)

        # ── Step 2: Validate ─────────────────────────────────────
        validator = DataValidator(quality_threshold=0.5)
        validated = validator.validate_sync(raw)

        assert validated is not None
        assert validated.quality.overall > 0

        # ── Step 3: Normalize ────────────────────────────────────
        normalizer = DataNormalizer()
        normalized = normalizer.normalize(validated)

        assert normalized.symbol == "DXY"
        assert normalized.value == raw.value  # value preserved
        assert normalized.source == "Yahoo"

        # ── Step 4: Persist ──────────────────────────────────────
        repo = SqlMacroRepository()
        await repo.save(normalized)

        # ── Step 5: Retrieve ─────────────────────────────────────
        retrieved = await repo.get_latest("DXY")
        assert retrieved is not None
        assert retrieved.symbol == "DXY"
        assert retrieved.value == raw.value

    @pytest.mark.asyncio
    async def test_pipeline_rejects_bad_data_before_storage(self) -> None:
        """Bad data should be rejected by Validator, never reaching Repository."""
        from src.interfaces.validator import ValidationError

        # Simulate bad data directly (bypassing Collector)
        bad_data = MacroDataSchema(
            symbol="DXY",
            timestamp=datetime(2099, 1, 1, tzinfo=UTC),  # far future
            value=-999.0,  # impossible value
            source="Yahoo",
        )

        validator = DataValidator(quality_threshold=0.5)
        with pytest.raises(ValidationError):
            validator.validate_sync(bad_data)
