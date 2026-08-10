# =============================================================================
# V9 Paper Trading Portfolio — Simulated Macro Investment Tracking
# =============================================================================
# NOT investment advice. Research tool for validating agent's macro views.
# Daily: agent outputs macro view, risk level, preferred/avoid assets, confidence.
# Tracked: 30/90/180 days → evaluate hit rate, Sharpe, drawdown, calibration.
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional


@dataclass
class TradeRecommendation:
    """A single asset recommendation from agent."""
    asset: str
    action: str  # "increase", "decrease", "neutral", "avoid"
    confidence: float  # 0-1
    reasoning: str = ""
    macro_view_relevance: str = ""  # why this asset connects to macro view


@dataclass
class PortfolioSnapshot:
    """Daily portfolio state."""
    date: str
    macro_view: str = ""
    risk_level: str = "medium"  # low/medium/high/extreme

    # Agent recommendations
    preferred_assets: list[TradeRecommendation] = field(default_factory=list)
    avoid_assets: list[TradeRecommendation] = field(default_factory=list)

    # Confidence
    overall_confidence: float = 0.5

    # Performance tracking (filled retroactively)
    entry_prices: dict = field(default_factory=dict)
    exit_prices: dict = field(default_factory=dict)


class PaperPortfolio:
    """Paper trading portfolio for V9 validation.

    Tracks agent's macro-driven asset recommendations over time,
    evaluating performance at 30/90/180-day intervals.
    """

    def __init__(self, name: str = "Macro Research Paper Portfolio"):
        self.name = name
        self.snapshots: list[PortfolioSnapshot] = []
        self.start_date: Optional[str] = None

        # Performance metrics
        self.total_recommendations: int = 0
        self.correct_recommendations: int = 0

        # Confidence calibration tracking (per-outcome)
        self._confidence_outcomes: list[tuple[float, bool]] = []

    def add_snapshot(self, macro_view: str, risk_level: str,
                     preferred: list[tuple], avoid: list[tuple],
                     overall_confidence: float = 0.5) -> PortfolioSnapshot:
        """Add a daily portfolio snapshot.

        preferred/avoid: list of (asset, confidence, reasoning) tuples
        """
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if not self.start_date:
            self.start_date = date

        snapshot = PortfolioSnapshot(
            date=date,
            macro_view=macro_view,
            risk_level=risk_level,
            overall_confidence=overall_confidence,
        )

        for asset, conf, reason in preferred:
            snapshot.preferred_assets.append(
                TradeRecommendation(asset=asset, action="increase", confidence=conf, reasoning=reason))
        for asset, conf, reason in avoid:
            snapshot.avoid_assets.append(
                TradeRecommendation(asset=asset, action="avoid", confidence=conf, reasoning=reason))

        self.snapshots.append(snapshot)
        return snapshot

    def record_outcome(self, snapshot_date: str, asset: str,
                       was_correct: bool, price_change: float,
                       confidence: Optional[float] = None):
        """Record whether a recommendation turned out correct.

        Args:
            snapshot_date: Date of the recommendation
            asset: Asset ticker/name
            was_correct: Whether the directional call was correct
            price_change: Actual price movement
            confidence: Agent's stated confidence (0-1). Used for ECE calibration.
        """
        self.total_recommendations += 1
        if was_correct:
            self.correct_recommendations += 1
        if confidence is not None:
            self._confidence_outcomes.append((confidence, was_correct))

    # ── Performance Metrics ──────────────────────────────────────────

    @property
    def hit_rate(self) -> float:
        if self.total_recommendations == 0:
            return 0.0
        return self.correct_recommendations / self.total_recommendations

    @property
    def total_days(self) -> int:
        return len(self.snapshots)

    @property
    def confidence_alignment(self) -> float:
        """Expected Calibration Error (ECE) — lower is better.

        Measures how well agent's stated confidence aligns with actual accuracy.
        A perfectly calibrated agent: when it says 80% confident, it's right 80% of the time.

        V10 Target: ECE < 0.10

        Returns:
            ECE value (0.0 = perfect calibration, higher = worse alignment)
        """
        if len(self._confidence_outcomes) < 5:
            return 0.0

        # Bucket confidence into 5 bins: [0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0]
        num_bins = 5
        bin_size = 1.0 / num_bins
        bins = [(i * bin_size, (i + 1) * bin_size) for i in range(num_bins)]

        ece = 0.0
        n = len(self._confidence_outcomes)

        for low, high in bins:
            bucket = [(c, o) for c, o in self._confidence_outcomes if low <= c < high]
            if not bucket:
                continue
            bucket_confidence = sum(c for c, _ in bucket) / len(bucket)
            bucket_accuracy = sum(1 for _, correct in bucket if correct) / len(bucket)
            bucket_weight = len(bucket) / n
            ece += bucket_weight * abs(bucket_accuracy - bucket_confidence)

        return round(ece, 4)

    @property
    def calibration_quality(self) -> str:
        """Human-readable calibration assessment."""
        ece = self.confidence_alignment
        if ece < 0.05:
            return "excellent"
        elif ece < 0.10:
            return "good"
        elif ece < 0.15:
            return "fair"
        elif ece < 0.20:
            return "poor"
        else:
            return "uncalibrated"

    @property
    def risk_adjusted_return(self) -> float:
        """Simple risk-adjusted metric. Positive if hit_rate > 50%."""
        return (self.hit_rate - 0.5) * 2  # scale to roughly -1 to +1

    @property
    def performance_summary(self) -> dict:
        return {
            "name": self.name,
            "start_date": self.start_date,
            "total_days": self.total_days,
            "total_recommendations": self.total_recommendations,
            "hit_rate": round(self.hit_rate, 3),
            "risk_adjusted_return": round(self.risk_adjusted_return, 3),
            "is_positive_risk_adjusted": self.risk_adjusted_return > 0,
            "confidence_alignment_ece": self.confidence_alignment,
            "calibration_quality": self.calibration_quality,
            "calibration_outcomes_tracked": len(self._confidence_outcomes),
        }

    def summary(self) -> str:
        """Portfolio performance summary."""
        ps = self.performance_summary
        lines = [
            f"Paper Portfolio: {self.name}",
            f"{'─'*50}",
            f"Period: {ps['start_date']} — Present ({ps['total_days']} days)",
            f"Total Recommendations: {ps['total_recommendations']}",
            f"Hit Rate: {ps['hit_rate']:.1%}",
            f"Risk-Adjusted Return: {ps['risk_adjusted_return']:.2f}",
            f"V9 Target (Positive): {'PASS' if ps['is_positive_risk_adjusted'] else 'FAIL'}",
            "",
            f"Asset Allocation View:",
        ]
        if self.snapshots:
            last = self.snapshots[-1]
            lines.append(f"  Macro View: {last.macro_view[:100]}")
            lines.append(f"  Risk Level: {last.risk_level}")
            lines.append(f"  Confidence: {last.overall_confidence:.0%}")
            lines.append(f"  Preferred Assets: {[r.asset for r in last.preferred_assets]}")
            lines.append(f"  Avoid Assets: {[r.asset for r in last.avoid_assets]}")
        return "\n".join(lines)

    def get_snapshots_in_window(self, days: int) -> list[PortfolioSnapshot]:
        """Get snapshots from last N days."""
        if not self.snapshots:
            return []
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        return [s for s in self.snapshots if s.date >= cutoff]

    def calculate_window_performance(self, days: int) -> dict:
        """Calculate performance over a specific time window."""
        snapshots = self.get_snapshots_in_window(days)
        pref_count = sum(len(s.preferred_assets) for s in snapshots)
        avoid_count = sum(len(s.avoid_assets) for s in snapshots)

        return {
            "window_days": days,
            "snapshots": len(snapshots),
            "preferred_recommendations": pref_count,
            "avoid_recommendations": avoid_count,
            "avg_confidence": sum(s.overall_confidence for s in snapshots) / max(len(snapshots), 1),
        }

    def reset(self):
        """Reset portfolio for new paper trading period."""
        self.snapshots.clear()
        self.start_date = None
        self.total_recommendations = 0
        self.correct_recommendations = 0
