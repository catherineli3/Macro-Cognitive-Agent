"""Signal ORM model — Persistent storage for generated signals.

Sprint 2: signals table — separate from macro_observations.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class SignalRecord(Base):
    """Persistent storage for a generated macro signal.

    Maps 1:1 to MacroSignalSchema. Separate from MacroObservation
    because signals have different schema, lifecycle, and query patterns.

    Note: Uses its own DeclarativeBase. If this causes metadata conflicts,
    import Base from src.storage.models instead.
    """

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    indicator: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    strength: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    data_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    interpretation_summary: Mapped[str] = mapped_column(String(500), nullable=True, default="")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = ({"sqlite_autoincrement": True},)

    def __repr__(self) -> str:
        return (
            f"<SignalRecord {self.indicator} [{self.dimension}] "
            f"{self.direction}/{self.strength} c={self.confidence:.2f}>"
        )
