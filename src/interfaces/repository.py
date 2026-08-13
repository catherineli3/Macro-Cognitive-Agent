"""RepositoryInterface — Abstract contract for data persistence.

The Repository pattern decouples storage logic from business logic.
Collector never touches the database directly.

Design goal:
    → Swap PostgreSQL for DuckDB/TimescaleDB/Snowflake without changing Collector.
    → Repository depends on StorageInterface, not on a concrete DB driver.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from src.schemas.macro_data import MacroDataSchema


class RepositoryInterface(ABC):
    """Abstract contract for persisting and querying macro data.

    Implementations:
        - SqlMacroRepository (Sprint 1)
        - DuckDBRepository (future)
        - RedisCacheRepository (future)
    """

    @abstractmethod
    async def save(self, data: MacroDataSchema) -> None:
        """Persist a single macro data observation.

        Args:
            data: The validated and normalized data point.

        Raises:
            RepositoryError: If persistence fails.
        """
        ...

    @abstractmethod
    async def save_batch(self, data: list[MacroDataSchema]) -> int:
        """Persist multiple observations atomically.

        Returns:
            Number of rows inserted.
        """
        ...

    @abstractmethod
    async def get_latest(self, symbol: str) -> MacroDataSchema | None:
        """Retrieve the most recent observation for a symbol.

        Returns:
            The latest MacroDataSchema or None if no data exists.
        """
        ...

    @abstractmethod
    async def get_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MacroDataSchema]:
        """Retrieve historical observations within a time range.

        Returns:
            Chronologically ordered list of observations.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify database connectivity.

        Returns:
            True if the database is reachable and responsive.
        """
        ...
