"""Signal domain concepts — Signal classification enums.

These are pure domain definitions for signal semantics.
They belong in domain/ because they define what a Signal IS,
not how it flows between modules (that's schemas/signal.py).
"""

from enum import Enum


class SignalDirection(str, Enum):
    """Market-implied direction.

    Re-exported from schemas/signal.py for domain purity.
    The canonical definition lives in schemas; domain reuses it
    to avoid circular dependencies.
    """

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SignalStrength(str, Enum):
    """Signal severity level."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class RuleType(str, Enum):
    """Types of signal generation rules supported by the Rule Engine.

    Sprint 2 implements THRESHOLD only. The remaining types are
    reserved for future Sprints — the Rule Engine architecture
    is designed to accommodate them without refactoring.
    """

    THRESHOLD = "threshold"  # Sprint 2: value vs threshold comparison
    # ── Reserved for future Sprints ──────────────────────────────────
    TREND = "trend"  # Future: moving average direction
    MOMENTUM = "momentum"  # Future: rate-of-change acceleration
    SPREAD = "spread"  # Future: difference between two indicators
    CORRELATION = "correlation"  # Future: rolling correlation break
    REGIME = "regime"  # Future: statistical regime detection
