"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path

# Ensure project root is on sys.path so `from src.xxx` works
# regardless of whether the package is installed in editable mode.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from datetime import UTC, datetime

import pytest

from src.domain.macro_indicator import Frequency, HypothesisDimension, MacroIndicator
from src.schemas.macro_data import MacroDataSchema


@pytest.fixture
def sample_settings() -> dict:
    """Provide sample application settings for tests."""
    return {
        "app": {"name": "Macro Research Agent", "version": "0.1.0", "env": "test"},
        "database": {"url": "sqlite+aiosqlite:///./data/test.db"},
    }


@pytest.fixture(scope="session", autouse=True)
def _ensure_db_tables() -> None:
    """Create all database tables once per test session (autouse)."""
    import asyncio
    import sys

    from src.storage.engine import get_engine
    from src.storage.models import Base
    from src.storage.signal_models import Base as SignalBase

    # Windows: use SelectorEventLoop for aiosqlite compatibility
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except AttributeError:
            pass  # Python < 3.8

    async def _create() -> None:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(SignalBase.metadata.create_all)

    asyncio.run(_create())


# ── Sprint 2 Shared Fixtures ──────────────────────────────────────────


@pytest.fixture
def dxy_indicator() -> MacroIndicator:
    """Standard DXY indicator definition for tests."""
    return MacroIndicator(
        symbol="DXY",
        name="US Dollar Index",
        category="Currency",
        frequency=Frequency.DAILY,
        unit="Index",
        source="Yahoo",
        hypothesis_dimension=HypothesisDimension.LIQUIDITY,
    )


@pytest.fixture
def vix_indicator() -> MacroIndicator:
    """Standard VIX indicator definition for tests."""
    return MacroIndicator(
        symbol="^VIX",
        name="CBOE Volatility Index",
        category="Volatility",
        frequency=Frequency.DAILY,
        unit="Index",
        source="Yahoo",
        hypothesis_dimension=HypothesisDimension.RISK_APPETITE,
    )


@pytest.fixture
def sample_dxy_data_high() -> MacroDataSchema:
    """DXY at 106.5 — above 105 threshold."""
    return MacroDataSchema(
        symbol="DXY",
        timestamp=datetime(2026, 7, 13, 10, 0, 0, tzinfo=UTC),
        value=106.5,
        source="Yahoo",
    )


@pytest.fixture
def sample_dxy_data_mid() -> MacroDataSchema:
    """DXY at 102.0 — between thresholds (no rule triggered)."""
    return MacroDataSchema(
        symbol="DXY",
        timestamp=datetime(2026, 7, 13, 10, 0, 0, tzinfo=UTC),
        value=102.0,
        source="Yahoo",
    )


@pytest.fixture
def sample_dxy_data_low() -> MacroDataSchema:
    """DXY at 98.0 — below 100 threshold."""
    return MacroDataSchema(
        symbol="DXY",
        timestamp=datetime(2026, 7, 13, 10, 0, 0, tzinfo=UTC),
        value=98.0,
        source="Yahoo",
    )


@pytest.fixture
def sample_vix_data_high() -> MacroDataSchema:
    """VIX at 28.0 — above 25 threshold."""
    return MacroDataSchema(
        symbol="^VIX",
        timestamp=datetime(2026, 7, 13, 10, 0, 0, tzinfo=UTC),
        value=28.0,
        source="Yahoo",
    )


@pytest.fixture
def sample_history() -> list[MacroDataSchema]:
    """5-day historical DXY data."""
    return [
        MacroDataSchema(
            symbol="DXY",
            timestamp=datetime(2026, 7, day, 10, 0, 0, tzinfo=UTC),
            value=104.0 + i * 0.5,
            source="Yahoo",
        )
        for i, day in enumerate(range(8, 13))
    ]


@pytest.fixture(autouse=True)
def _disable_rate_limit_sleeps(monkeypatch):
    """Neutralize collector rate-limit sleeps (3-6s per Yahoo indicator) in tests.

    collector_manager staggers Yahoo/Sina requests with time.sleep(random.uniform(...))
    to be polite to live APIs. In tests this serves no purpose and dominates runtime.
    """
    from types import SimpleNamespace

    try:
        import src.data_pipeline.collector_manager as cm

        monkeypatch.setattr(cm, "random", SimpleNamespace(uniform=lambda a, b: 0.0))
    except Exception:
        pass
