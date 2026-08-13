"""Capital Flow schemas — data structures for tracking global capital movement."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class FlowSignal:
    """A single flow signal — money moving into or out of an asset class."""

    asset_class: str = ""  # "equities", "bonds", "gold", "crypto", "cash", "commodities"
    region: str = ""  # "US", "EM", "Japan", "Europe", "China", "Global"
    direction: str = ""  # "inflow" / "outflow" / "neutral"
    magnitude: float = 0.0  # Normalized -1 to 1 (-1 = massive outflow, 1 = massive inflow)
    weekly_flow_bn: float = 0.0  # Flow amount in billions
    monthly_flow_bn: float = 0.0
    ytd_flow_bn: float = 0.0
    percentile: float = 50.0  # Where this flow sits vs. 5-year history
    description: str = ""
    source: str = ""  # "ETF", "CFTC", "13F", "cross-asset"

    def to_dict(self) -> dict:
        return {
            "asset_class": self.asset_class,
            "region": self.region,
            "direction": self.direction,
            "magnitude": self.magnitude,
            "weekly_flow_bn": self.weekly_flow_bn,
            "percentile": self.percentile,
            "description": self.description,
        }


@dataclass
class ETFDay:
    """Single-day ETF flow record."""

    date: str = ""
    ticker: str = ""
    name: str = ""
    category: str = ""
    flow_mm: float = 0.0  # Flow in millions
    aum_bn: float = 0.0  # AUM in billions
    flow_pct: float = 0.0  # Flow as % of AUM
    price_change_pct: float = 0.0

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "ticker": self.ticker,
            "name": self.name,
            "category": self.category,
            "flow_mm": self.flow_mm,
            "flow_pct": self.flow_pct,
        }


@dataclass
class ETFSummary:
    """Weekly/monthly ETF flow summary by category."""

    category: str = ""
    weekly_flow_bn: float = 0.0
    monthly_flow_bn: float = 0.0
    ytd_flow_bn: float = 0.0
    aum_bn: float = 0.0
    flow_momentum: float = 0.0  # Accelerating/decelerating (-1 to 1)
    days: list[ETFDay] = field(default_factory=list)
    description: str = ""


@dataclass
class PositionSnapshot:
    """Institutional positioning snapshot (CFTC COT / 13F style)."""

    date: str = ""
    asset: str = ""
    asset_class: str = ""

    # Positioning
    long_contracts: float = 0
    short_contracts: float = 0
    net_position: float = 0
    net_pct_of_oi: float = 0.0  # Net as % of open interest

    # Changes
    weekly_change: float = 0
    monthly_change: float = 0

    # Context
    positioning_percentile: float = 50.0  # Where is positioning vs. history?
    is_extreme: bool = False  # >90th or <10th percentile
    is_crowded: bool = False
    description: str = ""


@dataclass
class CapitalFlowRegime:
    """Classification of the current capital flow regime."""

    regime_label: str = ""  # "risk_on_inflow", "risk_off_outflow", "rotation", etc.
    confidence: float = 0.5

    # Money entering / leaving
    inflow_assets: list[str] = field(default_factory=list)
    outflow_assets: list[str] = field(default_factory=list)

    # Flow characteristics
    total_weekly_inflow_bn: float = 0
    total_weekly_outflow_bn: float = 0
    net_flow_bn: float = 0

    # Interpretation
    interpretation: str = ""
    signal_strength: float = 0.0  # 0-1, how clear is the signal?

    # Regime history
    prior_regime: str = ""
    regime_change_days: int = 0

    def to_dict(self) -> dict:
        return {
            "regime_label": self.regime_label,
            "confidence": self.confidence,
            "inflow_assets": self.inflow_assets,
            "outflow_assets": self.outflow_assets,
            "net_flow_bn": self.net_flow_bn,
            "interpretation": self.interpretation,
            "signal_strength": self.signal_strength,
        }


@dataclass
class CrossAssetFlowReport:
    """Cross-asset flow analysis report."""

    report_id: str = ""
    date: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Flow signals by asset class
    signals: list[FlowSignal] = field(default_factory=list)

    # Key rotations detected
    rotations: list[dict] = field(default_factory=list)

    # Summary narrative
    narrative: str = ""
    risk_sentiment: str = ""  # "risk_on", "risk_off", "neutral"
    conviction: float = 0.5

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "date": self.date,
            "signals": [s.to_dict() for s in self.signals],
            "rotations": self.rotations,
            "narrative": self.narrative,
            "risk_sentiment": self.risk_sentiment,
            "conviction": self.conviction,
        }


@dataclass
class CapitalFlowReport:
    """Complete capital flow report combining all sources."""

    report_id: str = ""
    date: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    regime: CapitalFlowRegime = field(default_factory=CapitalFlowRegime)
    cross_asset: CrossAssetFlowReport = field(default_factory=CrossAssetFlowReport)
    rotation_signals: list[dict] = field(default_factory=list)

    # Integration with reflexivity
    reflexivity_warning: bool = False
    reflexivity_detail: str = ""

    # Key takeaway
    summary: str = ""
    actionable_insight: str = ""

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "date": self.date,
            "regime": self.regime.to_dict(),
            "cross_asset": self.cross_asset.to_dict(),
            "rotation_signals": self.rotation_signals,
            "reflexivity_warning": self.reflexivity_warning,
            "summary": self.summary,
            "actionable_insight": self.actionable_insight,
        }
