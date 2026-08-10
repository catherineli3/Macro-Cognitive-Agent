"""NormalizerInterface — Abstract contract for data canonicalization.

CRITICAL: The Normalizer performs ONLY canonicalization:
    - Timezone normalization (→ UTC)
    - Unit standardization
    - Format normalization

PROHIBITED:
    - Business semantic transformations
    - Statistical adjustments
    - Value rewriting based on domain logic
    - Any logic that changes the MEANING of the data
"""

from abc import ABC, abstractmethod

from src.schemas.macro_data import MacroDataSchema


class NormalizerInterface(ABC):
    """Abstract contract for canonicalizing data format.

    This is NOT a "data cleaning" module with business rules.
    It performs mechanical, reversible transformations only.
    """

    @abstractmethod
    def normalize(self, data: MacroDataSchema) -> MacroDataSchema:
        """Apply canonicalization rules to a data point.

        Guarantees:
            - Timezone is UTC
            - Units are standardized
            - All string fields are trimmed and normalized

        Args:
            data: The validated data point.

        Returns:
            A new MacroDataSchema with canonicalized fields.
            Original value is NOT semantically altered.
        """
        ...
