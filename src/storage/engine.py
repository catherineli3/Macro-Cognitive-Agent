from __future__ import annotations

"""Storage engine factory — Async SQLAlchemy engine creation.

Supports:
    - SQLite (development, via aiosqlite)
    - PostgreSQL (production, via asyncpg)

Engine is created lazily and configured based on settings.yaml or DATABASE_URL env.
"""

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from src.shared.config import get_database_url
from src.shared.logging import get_logger

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def get_engine() -> AsyncEngine:
    """Return the singleton async SQLAlchemy engine.

    Created on first call with URL from settings.yaml or DATABASE_URL env.
    """
    global _engine
    if _engine is None:
        url = get_database_url()
        connect_args: dict = {}
        if "sqlite" in url:
            connect_args = {"check_same_thread": False}
        _engine = create_async_engine(
            url,
            echo=False,
            connect_args=connect_args,
        )
        logger.info("db_engine_created url=%s", url.split("@")[-1] if "@" in url else url)
    return _engine


def get_session_factory() -> async_sessionmaker:
    """Return an async session factory bound to the singleton engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
        )
    return _session_factory


async def check_db_health() -> bool:
    """Verify the database is reachable by executing a simple query."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        return True
    except Exception as exc:
        logger.error("db_health_check_failed error=%s", exc)
        return False


async def dispose_engine() -> None:
    """Dispose of the global engine (for graceful shutdown)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
