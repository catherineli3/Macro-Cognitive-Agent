"""SignalGeneratorInterface — Abstract contract for signal generation.

Design:
    SignalGenerator is a pure function: (indicator, current, history) → MacroSignalSchema.
    It depends on RuleEngine for rule evaluation but MUST NOT access the database,
    perform analysis, or use LLM.

    The historical_context parameter is critical: signals come from CHANGES,
    not from static single-point values. A DXY of 104 means nothing without
    knowing it was 106 last week.
"""

from abc import ABC, abstractmethod

from src.domain.macro_indicator import MacroIndicator
from src.schemas.macro_data import MacroDataSchema
from src.schemas.signal import MacroSignalSchema


class SignalGeneratorInterface(ABC):
    """Abstract contract for signal generation.

    Implementations:
        - ThresholdSignalGenerator (Sprint 2)
        - TrendSignalGenerator (future)
        - CompositeSignalGenerator (future)
    """

    @abstractmethod
    async def generate(
        self,
        indicator: MacroIndicator,
        current: MacroDataSchema,
        history: list[MacroDataSchema],
    ) -> MacroSignalSchema:
        """Generate a signal from current and historical macro data.

        Args:
            indicator: The indicator metadata (carries hypothesis_dimension).
            current: The latest validated & normalized observation.
            history: Historical observations (chronological, oldest first)
                     used for change detection and context.

        Returns:
            A deterministic, explainable MacroSignalSchema.

        Raises:
            SignalGenerationError: If rule evaluation fails unexpectedly.
        """
        ...

    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name of this generator (for logging & health)."""
        ...
