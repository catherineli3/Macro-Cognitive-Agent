"""CollectorInterface — Abstract contract for all data collectors.

Every data source (Yahoo, FRED, Bloomberg, Wind) MUST implement this interface.
The Pipeline depends on this interface, not on any concrete collector.

Design goals:
    → If we add FRED tomorrow, only a new class is needed.
    → Pipeline code never changes.
"""

from abc import ABC, abstractmethod

from src.domain.macro_indicator import MacroIndicator
from src.schemas.macro_data import MacroDataSchema


class CollectorInterface(ABC):
    """Abstract contract for fetching macro data from an external source.

    Single Responsibility:
        External API → MacroDataSchema

    Prohibited:
        - Database writes (use Repository)
        - Data analysis (use Analyzer)
        - LLM calls
        - Data transformation beyond format mapping
    """

    @abstractmethod
    async def collect(self, indicator: MacroIndicator) -> MacroDataSchema:
        """Fetch the latest observation for a given indicator.

        Args:
            indicator: The macro indicator metadata to collect data for.

        Returns:
            A MacroDataSchema with the latest value.

        Raises:
            CollectionError: If the external API is unreachable or
                             returns an unexpected response format.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify the data source is reachable and responding correctly.

        Returns:
            True if the source is healthy.
        """
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable source identifier, e.g. 'Yahoo'."""
        ...
