"""MacroSnapshot — daily market state snapshot for the Research Cycle Engine (Milestone D).

Extends RegimeSnapshot with market data and signal data to form the complete
input for the autonomous research cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from src.research.evolution.regime_gate import RegimeSnapshot  # noqa: F401 — re-export


# ═══════════════════════════════════════════════════════════════════════════════
# Market Snapshot → builds on top of RegimeSnapshot
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class MarketSnapshot:
    """Key market indicator values at a point in time.

    Intentionally minimal — the agent reasons over signals, not data rows.
    These are reference values for the postmortem and memory.
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    indicators: dict[str, float] = field(default_factory=dict)
    # Examples: {"spx": 5200.0, "vix": 15.3, "dxy": 104.2, "us10y": 4.25,
    #            "hyg": 77.5, "gold": 2350.0, "btc": 68000.0, ...}

    @property
    def count(self) -> int:
        return len(self.indicators)

    def get(self, key: str, default: float = 0.0) -> float:
        return self.indicators.get(key, default)

    def describe(self) -> str:
        if not self.indicators:
            return "No market data"
        items = [f"{k}={v:.1f}" for k, v in list(self.indicators.items())[:5]]
        return f"MarketSnapshot({', '.join(items)}{', ...' if len(self.indicators) > 5 else ''})"


# ═══════════════════════════════════════════════════════════════════════════════
# MacroSnapshot — the unified input for one research cycle
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class MacroSnapshot:
    """Complete daily snapshot for research cycle input.

    Composed of:
        - regime: macro policy & environment regime (RegimeSnapshot from C)
        - market: key market indicator values
        - signals: structured macro signals (from the signal engine)
        - composite: high-level theme detection (from composite signal generator)

    This is the single input object that the ResearchCycleEngine consumes.
    """

    cycle_id: str = ""
    regime: RegimeSnapshot | None = None
    market: MarketSnapshot = field(default_factory=MarketSnapshot)
    signals: list = field(default_factory=list)     # list[MacroSignalSchema]
    composite: object | None = None                  # CompositeSignalSnapshot | None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.cycle_id:
            self.cycle_id = f"cycle-{self.timestamp.strftime('%Y%m%d-%H%M%S')}"

    @property
    def regime_label(self) -> str:
        """Human-readable regime label."""
        if self.regime is None:
            return "Unknown Regime"
        r = self.regime
        # Classify into common macro regime types
        if r.monetary_policy == "easing" and r.growth in ("accelerating", "stable"):
            return "Early Easing / Growth"
        if r.monetary_policy == "easing" and r.growth in ("decelerating", "contracting"):
            return "Easing into Slowdown"
        if r.monetary_policy == "tightening" and r.inflation == "rising":
            return "Tightening / Inflation Fight"
        if r.monetary_policy == "tightening" and r.growth in ("decelerating", "contracting"):
            return "Tightening / Recession Risk"
        if r.volatility == "high":
            return f"High Volatility ({r.monetary_policy})"
        if r.growth == "accelerating" and r.inflation == "stable":
            return "Goldilocks"
        return f"{r.monetary_policy.title()} / {r.growth.title()} Growth"

    @property
    def signal_count(self) -> int:
        return len(self.signals)

    @property
    def dominant_theme(self) -> str | None:
        if self.composite and hasattr(self.composite, "dominant_theme"):
            return self.composite.dominant_theme
        return None

    def to_summary(self) -> str:
        lines = [
            f"MacroSnapshot [{self.cycle_id}]",
            f"  Regime: {self.regime_label}",
            f"  Market: {self.market.describe()}",
            f"  Signals: {self.signal_count}",
        ]
        if self.dominant_theme:
            lines.append(f"  Theme: {self.dominant_theme}")
        return "\n".join(lines)

    # ── Factory ────────────────────────────────────────────────────────────

    @classmethod
    def from_regime(cls, regime: RegimeSnapshot,
                    market_data: dict[str, float] | None = None,
                    signals: list | None = None,
                    composite=None) -> MacroSnapshot:
        """Quick factory from regime + optional data."""
        return cls(
            regime=regime,
            market=MarketSnapshot(indicators=market_data or {}),
            signals=signals or [],
            composite=composite,
        )
