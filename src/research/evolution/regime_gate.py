"""Regime Gate — cross-regime validation for principle admission (Milestone C).

Implements P1 of the admission criteria: validates that a principle has been
observed in >=2 distinct market regimes.

Regime definition per architecture:
    monetary_policy: "tightening" | "neutral" | "easing"
    fiscal_stance:   "expansionary" | "neutral" | "contractionary"
    volatility:      "low" | "moderate" | "high"
    growth:          "accelerating" | "stable" | "decelerating" | "contracting"
    inflation:       "rising" | "stable" | "falling"

Two regimes are "distinct" if >=2 dimensions differ in category.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.schemas.research import ResearchPrinciple, PrincipleStrength
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RegimeSnapshot:
    """A snapshot of the macro regime at a specific point in time."""
    regime_id: str = ""
    monetary_policy: str = "neutral"    # "tightening" | "neutral" | "easing"
    fiscal_stance: str = "neutral"      # "expansionary" | "neutral" | "contractionary"
    volatility: str = "moderate"        # "low" | "moderate" | "high"
    growth: str = "stable"             # "accelerating" | "stable" | "decelerating" | "contracting"
    inflation: str = "stable"           # "rising" | "stable" | "falling"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cycle: int = 0

    def to_dict(self) -> dict:
        return {
            "monetary_policy": self.monetary_policy,
            "fiscal_stance": self.fiscal_stance,
            "volatility": self.volatility,
            "growth": self.growth,
            "inflation": self.inflation,
        }

    @property
    def key(self) -> str:
        """A hashable string representation for comparison."""
        return f"{self.monetary_policy}|{self.fiscal_stance}|{self.volatility}|{self.growth}|{self.inflation}"

    def is_distinct_from(self, other: RegimeSnapshot) -> bool:
        """Two regimes are distinct if >=2 dimensions differ."""
        dims = [
            (self.monetary_policy, other.monetary_policy),
            (self.fiscal_stance, other.fiscal_stance),
            (self.volatility, other.volatility),
            (self.growth, other.growth),
            (self.inflation, other.inflation),
        ]
        diff_count = sum(1 for a, b in dims if a != b)
        return diff_count >= 2

    def describe(self) -> str:
        return (
            f"Regime[{self.key}]: mon={self.monetary_policy}, "
            f"fiscal={self.fiscal_stance}, vol={self.volatility}, "
            f"growth={self.growth}, infl={self.inflation}"
        )

    def __repr__(self) -> str:
        return f"<RegimeSnapshot {self.key}>"


class RegimeGate:
    """Cross-regime validation engine for principle admission (P1).

    Tracks regime history and validates that principles have been
    observed under multiple distinct market regimes.
    """

    # Valid values per dimension
    VALID_VALUES = {
        "monetary_policy": {"tightening", "neutral", "easing"},
        "fiscal_stance": {"expansionary", "neutral", "contractionary"},
        "volatility": {"low", "moderate", "high"},
        "growth": {"accelerating", "stable", "decelerating", "contracting"},
        "inflation": {"rising", "stable", "falling"},
    }

    def __init__(self) -> None:
        self._regime_history: list[RegimeSnapshot] = []
        self._principle_regimes: dict[str, list[str]] = {}  # principle_id → [regime_keys]
        self._current_regime: RegimeSnapshot | None = None

    def set_current_regime(self, regime: RegimeSnapshot) -> None:
        """Update the current regime."""
        self._current_regime = regime
        # Only add to history if distinct from last entry
        if not self._regime_history or regime.is_distinct_from(self._regime_history[-1]):
            self._regime_history.append(regime)
            logger.info("New regime detected: %s (total: %d distinct regimes)",
                        regime.key, len(self._regime_history))

    def record_principle_observation(self, principle_id: str,
                                      regime: RegimeSnapshot) -> None:
        """Record that a principle was observed under a specific regime."""
        if principle_id not in self._principle_regimes:
            self._principle_regimes[principle_id] = []
        if regime.key not in self._principle_regimes[principle_id]:
            self._principle_regimes[principle_id].append(regime.key)

    def is_cross_regime_validated(self, principle: ResearchPrinciple) -> bool:
        """Check P1: Has this principle been observed in >=2 distinct regimes?"""
        regime_keys = self._principle_regimes.get(principle.principle_id, [])
        return len(regime_keys) >= 2

    def get_distinct_regime_count(self, principle_id: str) -> int:
        return len(self._principle_regimes.get(principle_id, []))

    def get_principle_regimes(self, principle_id: str) -> list[str]:
        return self._principle_regimes.get(principle_id, [])

    @classmethod
    def from_dict(cls, data: dict) -> RegimeSnapshot:
        """Create a RegimeSnapshot from a dictionary, with validation."""
        return RegimeSnapshot(
            regime_id=data.get("regime_id", ""),
            monetary_policy=data.get("monetary_policy", "neutral"),
            fiscal_stance=data.get("fiscal_stance", "neutral"),
            volatility=data.get("volatility", "moderate"),
            growth=data.get("growth", "stable"),
            inflation=data.get("inflation", "stable"),
            cycle=data.get("cycle", 0),
        )

    def get_regime_for_cycle(self, cycle: int) -> RegimeSnapshot | None:
        """Get the regime snapshot closest to a given cycle."""
        closest = None
        min_dist = float("inf")
        for r in self._regime_history:
            dist = abs(r.cycle - cycle)
            if dist < min_dist:
                min_dist = dist
                closest = r
        return closest

    @property
    def distinct_regime_count(self) -> int:
        """Count of distinct regimes observed."""
        unique_keys = set(r.key for r in self._regime_history)
        return len(unique_keys)

    @property
    def current_regime(self) -> RegimeSnapshot | None:
        return self._current_regime

    @property
    def total_observations(self) -> int:
        return len(self._regime_history)

    def summary(self) -> str:
        return (f"RegimeGate: {self.distinct_regime_count} distinct regimes "
                f"across {self.total_observations} observations. "
                f"Current: {self._current_regime.describe() if self._current_regime else 'N/A'}")
