"""Narrative domain concepts — report format, risk level, and confidence enums.

MVP: ReportFormat represents presentation layer concerns.
RiskLevel is used by MacroNarrative for risk classification.
ConfidenceLevel provides human-readable confidence tier classification.
"""

from enum import Enum


class ReportFormat(str, Enum):
    """Presentation formats — NOT part of cognitive pipeline."""

    MARKDOWN = "markdown"
    JSON = "json"
    PLAINTEXT = "plaintext"
    HTML = "html"
    PDF = "pdf"


class RiskLevel(str, Enum):
    """Risk severity classification for risk items in MacroNarrative."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfidenceLevel(str, Enum):
    """Human-readable confidence tier for narrative output.

    Beta: Replaces raw float confidence display with interpretable tiers.
    Used by MacroNarrative.confidence_level alongside confidence_score.
    """

    HIGH = "HIGH"  # confidence >= 0.70
    MEDIUM = "MEDIUM"  # 0.40 <= confidence < 0.70
    LOW = "LOW"  # confidence < 0.40
