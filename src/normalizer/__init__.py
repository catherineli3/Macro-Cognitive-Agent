"""Normalizer module — Clean and standardize raw macro data.

Responsibilities:
    1. Canonicalization: timezone, string normalization, format
    2. Emit normalized MacroDataSchema

Prohibited:
    - Business semantic transformations
    - Value rewriting based on domain logic

Dependencies: interfaces, schemas, shared
"""

from src.normalizer.normalizer import DataNormalizer

__all__ = ["DataNormalizer"]
