from __future__ import annotations

"""SignalRepositoryInterface — Abstract contract for signal persistence.

Separate from RepositoryInterface (macro data) because:
    - Signals have a different schema (MacroSignalSchema vs MacroDataSchema)
    - Signals have different access patterns (snapshot queries)
    - Separate concerns → separate repositories → separate interfaces

Implementations:
    - SqlSignalRepository (Sprint 2)
    - RedisSignalCache (future)
"""

from abc import ABC, abstractmethod
from datetime import datetime

from src.schemas.signal import MacroSignalSchema


class SignalRepositoryInterface(ABC):
    """Abstract contract for persisting and querying macro signals."""

    @abstractmethod
    async def save(self, signal: MacroSignalSchema) -> None:
        """Persist a single signal.

        Args:
            signal: The generated signal to store.

        Raises:
            RepositoryError: If persistence fails.
        """
        ...

    @abstractmethod
    async def save_batch(self, signals: list[MacroSignalSchema]) -> int:
        """Persist multiple signals atomically.

        Returns:
            Number of rows inserted.
        """
        ...

    @abstractmethod
    async def get_latest_by_indicator(self, indicator: str) -> MacroSignalSchema | None:
        """Retrieve the most recent signal for a given indicator.

        Returns:
            The latest signal or None if no signal exists for this indicator.
        """
        ...

    @abstractmethod
    async def get_snapshot(
        self, since: datetime | None = None
    ) -> list[MacroSignalSchema]:
        """Retrieve the latest signal per indicator (macro snapshot).

        Args:
            since: Optional time filter — only signals generated after this time.

        Returns:
            List of latest signals, one per distinct indicator.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify repository connectivity."""
        ...
