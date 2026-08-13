"""SqlSignalRepository — Persists and queries generated macro signals.

Implements SignalRepositoryInterface.
Separate from SqlMacroRepository because signals have different
schema, lifecycle, and query patterns.

Dependency: SQLAlchemy async engine (via src/storage/engine.py).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import desc, select

from src.interfaces.signal_repository import SignalRepositoryInterface
from src.schemas.signal import (
    MacroSignalSchema,
    SignalDirection,
    SignalEvidence,
    SignalStrength,
)
from src.shared.exceptions import RepositoryError
from src.shared.logging import get_logger
from src.storage.engine import check_db_health, get_session_factory
from src.storage.signal_models import SignalRecord

logger = get_logger(__name__)


class SqlSignalRepository(SignalRepositoryInterface):
    """SQL-based repository for macro signal data.

    Usage:
        repo = SqlSignalRepository()
        await repo.save(signal)
        snapshot = await repo.get_snapshot()
    """

    # ── Write ───────────────────────────────────────────────────────

    async def save(self, signal: MacroSignalSchema) -> None:
        """Persist a single generated signal."""
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                record = _signal_to_model(signal)
                session.add(record)
                await session.commit()
                logger.debug(
                    "signal_saved signal_id=%s indicator=%s direction=%s",
                    signal.signal_id,
                    signal.indicator,
                    signal.direction.value,
                )
        except Exception as exc:
            raise RepositoryError(
                f"Failed to save signal {signal.signal_id}: {exc}",
                details={"signal_id": signal.signal_id},
            ) from exc

    async def save_batch(self, signals: list[MacroSignalSchema]) -> int:
        """Persist multiple signals atomically."""
        if not signals:
            return 0
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                records = [_signal_to_model(s) for s in signals]
                session.add_all(records)
                await session.commit()
                logger.info("signal_batch_saved count=%d", len(signals))
                return len(signals)
        except Exception as exc:
            raise RepositoryError(
                f"Batch signal save failed: {exc}",
                details={"batch_size": len(signals)},
            ) from exc

    # ── Read ────────────────────────────────────────────────────────

    async def get_latest_by_indicator(self, indicator: str) -> MacroSignalSchema | None:
        """Retrieve the most recent signal for a given indicator."""
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                stmt = (
                    select(SignalRecord)
                    .where(SignalRecord.indicator == indicator)
                    .order_by(desc(SignalRecord.timestamp))
                    .limit(1)
                )
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                return _model_to_signal(row) if row else None
        except Exception as exc:
            raise RepositoryError(
                f"Failed to get latest signal for {indicator}: {exc}",
                details={"indicator": indicator},
            ) from exc

    async def get_snapshot(self, since: datetime | None = None) -> list[MacroSignalSchema]:
        """Retrieve latest signal per indicator (macro snapshot).

        Uses DISTINCT ON (indicator) with timestamp ordering to get
        the latest signal for each unique indicator.

        Args:
            since: Optional time filter — signals after this timestamp only.
        """
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                # Subquery: max timestamp per indicator
                subq = select(
                    SignalRecord.indicator,
                    select(SignalRecord.timestamp)
                    .where(SignalRecord.indicator == SignalRecord.indicator)
                    .order_by(desc(SignalRecord.timestamp))
                    .limit(1)
                    .correlate(SignalRecord)
                    .scalar_subquery()
                    .label("max_ts"),
                ).group_by(SignalRecord.indicator)

                if since is not None:
                    subq = subq.where(SignalRecord.timestamp >= since)

                # Main query: join back to get full rows
                stmt = select(SignalRecord).order_by(
                    SignalRecord.indicator, desc(SignalRecord.timestamp)
                )

                result = await session.execute(stmt)
                rows = result.scalars().all()

                # Deduplicate: keep only latest per indicator
                seen: set[str] = set()
                latest: list[SignalRecord] = []
                for row in rows:
                    if row.indicator not in seen:
                        seen.add(row.indicator)
                        latest.append(row)

                signals = [_model_to_signal(r) for r in latest]
                logger.debug("snapshot_retrieved count=%d", len(signals))
                return signals
        except Exception as exc:
            raise RepositoryError(
                f"Failed to get signal snapshot: {exc}",
            ) from exc

    # ── Health ──────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Verify repository connectivity."""
        return await check_db_health()


# ── Private helpers ───────────────────────────────────────────────────────


def _signal_to_model(signal: MacroSignalSchema) -> SignalRecord:
    """Map MacroSignalSchema → SQLAlchemy SignalRecord."""
    interpretations = [e.interpretation for e in signal.evidence]
    return SignalRecord(
        signal_id=signal.signal_id,
        indicator=signal.indicator,
        dimension=signal.dimension,
        direction=signal.direction.value,
        strength=signal.strength.value,
        confidence=signal.confidence,
        timestamp=signal.timestamp,
        data_timestamp=signal.data_timestamp,
        evidence_json=json.dumps(
            [e.model_dump(mode="json") for e in signal.evidence],
            default=str,
        ),
        interpretation_summary=" | ".join(interpretations) if interpretations else "",
        ingested_at=datetime.now(UTC),
    )


def _model_to_signal(model: SignalRecord) -> MacroSignalSchema:
    """Map SQLAlchemy SignalRecord → MacroSignalSchema."""
    try:
        evidence_raw = json.loads(model.evidence_json)
        evidence = [SignalEvidence(**e) for e in evidence_raw]
    except (json.JSONDecodeError, TypeError):
        evidence = []

    return MacroSignalSchema(
        signal_id=model.signal_id,
        indicator=model.indicator,
        dimension=model.dimension,
        direction=SignalDirection(model.direction),
        strength=SignalStrength(model.strength),
        confidence=model.confidence,
        timestamp=model.timestamp,
        evidence=evidence,
        data_timestamp=model.data_timestamp,
    )
