"""Tests for Signal API routes — GET /signals/snapshot."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.schemas.signal import (
    MacroSignalSchema,
    SignalDirection,
    SignalEvidence,
    SignalStrength,
)
from src.storage.signal_repository import SqlSignalRepository
from src.storage.engine import dispose_engine

_uid = 0


def _make_seeded_signal(indicator: str = "API_TEST") -> MacroSignalSchema:
    global _uid
    _uid += 1
    return MacroSignalSchema(
        signal_id=f"api_test_{_uid}",
        indicator=indicator,
        dimension="Liquidity",
        direction=SignalDirection.BEARISH,
        strength=SignalStrength.MODERATE,
        confidence=0.80,
        timestamp=datetime(2026, 7, 13, 12, _uid, 0, tzinfo=timezone.utc),
        evidence=[
            SignalEvidence(
                rule_id="api_test_rule",
                rule_description="API test rule",
                input_value=106.0,
                condition="value gt 105",
                interpretation="API Test Signal — Financial Conditions Tightening",
            )
        ],
    )


@pytest.fixture(autouse=True)
async def _cleanup() -> None:
    yield
    await dispose_engine()


class TestSignalAPI:
    """Signal API endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        return TestClient(app)

    def test_snapshot_returns_200(self, client: TestClient) -> None:
        response = client.get("/signals/snapshot")
        assert response.status_code == 200

    def test_snapshot_has_summary(self, client: TestClient) -> None:
        response = client.get("/signals/snapshot")
        data = response.json()
        assert "summary" in data
        assert isinstance(data["summary"], str)

    def test_snapshot_has_signals_list(self, client: TestClient) -> None:
        response = client.get("/signals/snapshot")
        data = response.json()
        assert "signals" in data
        assert isinstance(data["signals"], list)

    def test_snapshot_has_generated_at(self, client: TestClient) -> None:
        response = client.get("/signals/snapshot")
        data = response.json()
        assert "generated_at" in data

    @pytest.mark.asyncio
    async def test_snapshot_with_data(self, client: TestClient) -> None:
        """Seed a signal, then verify snapshot contains it."""
        repo = SqlSignalRepository()
        sig = _make_seeded_signal()
        await repo.save(sig)

        response = client.get("/signals/snapshot")
        data = response.json()
        indicators = [s["indicator"] for s in data["signals"]]
        assert sig.indicator in indicators

    def test_snapshot_signals_have_evidence(self, client: TestClient) -> None:
        """Each signal in snapshot must have evidence."""
        response = client.get("/signals/snapshot")
        data = response.json()
        for signal in data["signals"]:
            assert "evidence" in signal
            if signal["evidence"]:
                ev = signal["evidence"][0]
                assert "interpretation" in ev
