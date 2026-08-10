"""SQLAlchemy ORM models for macro research data.

Schema version: 001_initial
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class MacroObservation(Base):
    """Persistent storage for a single macro-economic observation.

    Maps 1:1 to MacroDataSchema. Stores the canonical data contract
    in a relational format for querying and historical tracking.

    Indexes:
        - (symbol, timestamp) UNIQUE — prevents duplicate observations
        - (symbol, ingested_at) — efficient time-range queries
    """

    __tablename__ = "macro_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, default=1.0)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Indexes ──────────────────────────────────────────────────────

    __table_args__ = (
        # Prevent exact duplicate observations
        {"sqlite_autoincrement": True},
    )

    def __repr__(self) -> str:
        return (
            f"<MacroObservation {self.symbol}={self.value}"
            f" @ {self.timestamp:%Y-%m-%d} [{self.source}]>"
        )
