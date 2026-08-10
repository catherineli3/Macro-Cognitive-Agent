"""Sprint 7 — Reflection domain enums.

Reflection is a Belief Review Engine.
It answers: "Should the agent still believe this hypothesis?"
"""

from enum import Enum


class ReflectionVerdict(str, Enum):
    """Outcome of belief review for a single hypothesis."""

    CONFIRMED = "confirmed"
    """Evidence supports continued belief. Confidence is maintained or slightly adjusted."""

    REFUTED = "refuted"
    """Evidence no longer supports belief. Confidence has dropped significantly."""

    UNCERTAIN = "uncertain"
    """Evidence is too weak or mixed to reach a conclusion."""


class FindingSeverity(str, Enum):
    """How strongly a finding impacts belief."""

    CRITICAL = "critical"
    """Finding substantially undermines belief in this hypothesis."""

    MAJOR = "major"
    """Finding notably weakens confidence."""

    MINOR = "minor"
    """Finding raises a question but does not materially shift belief."""
