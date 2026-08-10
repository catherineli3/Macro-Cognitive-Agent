"""Validation module — Shared data validation capability.

Independent of any specific Collector. Every data point in the pipeline
passes through this module before normalization or storage.
"""

from src.validation.validator import DataValidator

__all__ = ["DataValidator"]
