"""Tests for SqlSignalRepository — save, query, snapshot."""

from datetime import UTC, datetime

import pytest

from src.schemas.signal import (
    MacroSignalSchema,
    SignalDirection,
    SignalEvidence,
    SignalStrength,
)
from src.storage.engine import dispose_engine
from src.storage.signal_repository import SqlSignalRepository

_uid = 0


def _make_signal(indicator: str = "DXY", direction: str = "bearish") -> MacroSignalSchema:
    global _uid
    _uid += 1
    return MacroSignalSchema(
        signal_id=f"test_{_uid}",
        indicator=indicator,
        dimension="Liquidity",
        direction=SignalDirection(direction),
        strength=SignalStrength.MODERATE,
        confidence=0.75,
        timestamp=datetime(2026, 7, 13, 10, _uid, 0, tzinfo=UTC),
        evidence=[
            SignalEvidence(
                rule_id=f"test_rule_{_uid}",
                rule_description="Test rule",
                input_value=105.0,
                condition="value gt 100",
                interpretation="Test interpretation",
            )
        ],
        data_timestamp=datetime(2026, 7, 13, tzinfo=UTC),
    )


@pytest.fixture(autouse=True)
async def _cleanup() -> None:
    yield
    await dispose_engine()


class TestSignalRepository:
    """CRUD operations for signals."""

    @pytest.mark.asyncio
    async def test_save_signal(self) -> None:
        repo = SqlSignalRepository()
        sym = f"SAVE_{_uid}"
        sig = _make_signal(sym)
        await repo.save(sig)
        retrieved = await repo.get_latest_by_indicator(sym)
        assert retrieved is not None
        assert retrieved.indicator == sym
        assert retrieved.direction == SignalDirection.BEARISH

    @pytest.mark.asyncio
    async def test_get_latest_returns_most_recent(self) -> None:
        repo = SqlSignalRepository()
        sym = f"LATEST_{_uid}"
        s1 = _make_signal(sym, "bearish")
        s2 = _make_signal(sym, "bullish")
        await repo.save(s1)
        await repo.save(s2)
        latest = await repo.get_latest_by_indicator(sym)
        assert latest is not None
        # s2 should be later
        assert latest.signal_id == s2.signal_id

    @pytest.mark.asyncio
    async def test_get_latest_nonexistent(self) -> None:
        repo = SqlSignalRepository()
        result = await repo.get_latest_by_indicator("NEVER_SEEN")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_batch(self) -> None:
        repo = SqlSignalRepository()
        sigs = [_make_signal(f"BATCH_{i}") for i in range(3)]
        count = await repo.save_batch(sigs)
        assert count == 3

    @pytest.mark.asyncio
    async def test_save_batch_empty(self) -> None:
        repo = SqlSignalRepository()
        count = await repo.save_batch([])
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_snapshot_deduplicates(self) -> None:
        """Snapshot should return latest per indicator, not all rows."""
        repo = SqlSignalRepository()
        sym = f"SNAP_{_uid}"
        s1 = _make_signal(sym, "bullish")
        s2 = _make_signal(sym, "bearish")
        await repo.save(s1)
        await repo.save(s2)
        snapshot = await repo.get_snapshot()
        signals_for_sym = [s for s in snapshot if s.indicator == sym]
        assert len(signals_for_sym) == 1  # only latest

    @pytest.mark.asyncio
    async def test_get_snapshot_empty(self) -> None:
        repo = SqlSignalRepository()
        snapshot = await repo.get_snapshot()
        assert isinstance(snapshot, list)
        # May be empty or contain previous test data — just verify no error

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        repo = SqlSignalRepository()
        assert await repo.health_check() is True
