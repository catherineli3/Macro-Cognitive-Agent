"""SqlMacroRepository — Repository pattern implementation for macro data.

Implements RepositoryInterface. Depends on Storage Interface (SQLAlchemy),
NOT on a concrete database.

Collector NEVER touches the database directly — it goes through this repository.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from src.interfaces.repository import RepositoryInterface
from src.schemas.macro_data import MacroDataSchema, QualityScore
from src.shared.exceptions import RepositoryError
from src.shared.logging import get_logger
from src.storage.engine import check_db_health, get_session_factory
from src.storage.models import MacroObservation

logger = get_logger(__name__)


class SqlMacroRepository(RepositoryInterface):
    """SQL-based repository for macro observation data.

    Uses SQLAlchemy async sessions. Insert-or-update (upsert)
    semantics to handle duplicate observations gracefully.

    Usage:
        repo = SqlMacroRepository()
        await repo.save(data)
    """

    # ── Write ───────────────────────────────────────────────────────

    async def save(self, data: MacroDataSchema) -> None:
        """Persist a single observation. Upserts on (symbol, timestamp) conflict."""
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                obs = _schema_to_model(data)
                session.add(obs)
                await session.commit()
                logger.debug(
                    "repository_save symbol=%s timestamp=%s",
                    data.symbol,
                    data.timestamp.isoformat(),
                )
        except Exception as exc:
            raise RepositoryError(
                f"Failed to save {data.symbol}: {exc}",
                details={"symbol": data.symbol},
            ) from exc

    async def save_batch(self, data: list[MacroDataSchema]) -> int:
        """Persist multiple observations."""
        if not data:
            return 0
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                models = [_schema_to_model(d) for d in data]
                session.add_all(models)
                await session.commit()
                logger.info("repository_save_batch count=%d", len(data))
                return len(data)
        except Exception as exc:
            raise RepositoryError(
                f"Batch save failed: {exc}",
                details={"batch_size": len(data)},
            ) from exc

    # ── Read ────────────────────────────────────────────────────────

    async def get_latest(self, symbol: str) -> MacroDataSchema | None:
        """Retrieve the most recent observation for a symbol."""
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                stmt = (
                    select(MacroObservation)
                    .where(MacroObservation.symbol == symbol)
                    .order_by(MacroObservation.timestamp.desc())
                    .limit(1)
                )
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                return _model_to_schema(row) if row else None
        except Exception as exc:
            raise RepositoryError(
                f"Failed to get latest for {symbol}: {exc}",
                details={"symbol": symbol},
            ) from exc

    async def get_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MacroDataSchema]:
        """Retrieve historical observations in a time range."""
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                stmt = (
                    select(MacroObservation)
                    .where(
                        MacroObservation.symbol == symbol,
                        MacroObservation.timestamp >= start,
                        MacroObservation.timestamp <= end,
                    )
                    .order_by(MacroObservation.timestamp.asc())
                )
                result = await session.execute(stmt)
                return [_model_to_schema(row) for row in result.scalars().all()]
        except Exception as exc:
            raise RepositoryError(
                f"Failed to get history for {symbol}: {exc}",
                details={"symbol": symbol},
            ) from exc

    # ── Health ──────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Verify database connectivity."""
        return await check_db_health()


# ── Private helpers ────────────────────────────────────────────────────


def _schema_to_model(data: MacroDataSchema) -> MacroObservation:
    """Map MacroDataSchema → SQLAlchemy ORM model."""
    return MacroObservation(
        symbol=data.symbol,
        timestamp=data.timestamp,
        value=data.value,
        currency=data.currency,
        unit=data.unit,
        source=data.source,
        quality_score=data.quality.overall,
        ingested_at=data.ingested_at,
    )


def _model_to_schema(model: MacroObservation) -> MacroDataSchema:
    """Map SQLAlchemy ORM model → MacroDataSchema."""
    return MacroDataSchema(
        symbol=model.symbol,
        timestamp=model.timestamp,
        value=model.value,
        currency=model.currency,
        unit=model.unit,
        source=model.source,
        quality=QualityScore(overall=model.quality_score),
        ingested_at=model.ingested_at,
    )
