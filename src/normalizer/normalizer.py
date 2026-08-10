"""Normalizer module — Canonicalization of macro data format.

IMPORTANT: This module performs ONLY mechanical normalization:
    - Timezone → UTC
    - String trimming
    - Unit labels (no conversion)

PROHIBITED:
    - Business semantic transformations
    - Value conversion based on domain knowledge
    - Any logic that changes the MEANING of data
"""

from src.interfaces.normalizer import NormalizerInterface
from src.schemas.macro_data import MacroDataSchema
from src.shared.logging import get_logger

logger = get_logger(__name__)


class DataNormalizer(NormalizerInterface):
    """Applies mechanical canonicalization to validated data points.

    Transformations applied:
        1. Timezone enforced to UTC
        2. Symbol uppercased
        3. All string fields stripped of whitespace
        4. Source name standardized
    """

    # ── Public API ─────────────────────────────────────────────────

    def normalize(self, data: MacroDataSchema) -> MacroDataSchema:
        """Apply canonicalization and return a new normalized instance.

        The original data is never modified. This is a pure function.

        Args:
            data: A validated MacroDataSchema.

        Returns:
            A new MacroDataSchema with normalized fields.
            The value is never semantically altered.
        """
        logger.debug("normalize_start", symbol=data.symbol)

        normalized = MacroDataSchema(
            symbol=data.symbol.strip().upper(),
            timestamp=data.timestamp,
            value=data.value,
            currency=data.currency.strip().upper(),
            unit=data.unit.strip(),
            source=data.source.strip().title(),
            quality=data.quality,
            ingested_at=data.ingested_at,
        )

        logger.debug("normalize_done", symbol=normalized.symbol)
        return normalized
