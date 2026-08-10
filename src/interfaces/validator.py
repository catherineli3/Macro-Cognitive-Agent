from __future__ import annotations

"""ValidatorInterface — Abstract contract for data validation.

Validation is a shared pipeline capability, NOT coupled to any single Collector.
Every data point entering the pipeline passes through validation before
normalization or storage.
"""

from abc import ABC, abstractmethod

from src.schemas.macro_data import MacroDataSchema


class ValidationError(Exception):
    """Raised when a MacroDataSchema fails validation.

    Attributes:
        schema: The failing data point (for inspection).
        reason: Human-readable explanation of the failure.
        field: Optional specific field that caused the failure.
    """

    def __init__(self, schema: MacroDataSchema, reason: str, field: str | None = None) -> None:
        self.schema = schema
        self.reason = reason
        self.field = field
        super().__init__(f"Validation failed for {schema.symbol}: {reason}" + (f" (field={field})" if field else ""))


class ValidatorInterface(ABC):
    """Abstract contract for data validation rules.

    Implementations MUST reject (raise ValidationError) for:
        - Out-of-range values (e.g. DXY < 0)
        - Future timestamps
        - Null/missing required fields
        - Impossible values (e.g. yield = -500%)

    Valid data should have a QualityScore computed.
    """

    @abstractmethod
    async def validate(self, data: MacroDataSchema) -> MacroDataSchema:
        """Validate and annotate a data point with quality score.

        Args:
            data: The raw data point from a Collector.

        Returns:
            The same data point with quality score populated.

        Raises:
            ValidationError: If the data point fails validation.
        """
        ...

    @abstractmethod
    def validate_sync(self, data: MacroDataSchema) -> MacroDataSchema:
        """Synchronous validation variant — used when no I/O is needed.

        Args:
            data: The raw data point to validate.

        Returns:
            The data point with quality score populated.

        Raises:
            ValidationError: If the data point fails validation.
        """
        ...
