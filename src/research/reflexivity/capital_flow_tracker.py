"""CapitalFlowTracker — Tracks capital flows as the "Capital" leg of reflexivity.

The Narrative → Capital → Price → Narrative loop requires tracking how money
actually moves. This module synthesizes flow signals from price/volume data
and market indicators to estimate capital movement direction and momentum.

Without real flow data (which requires Bloomberg, EPFR, etc.), we infer flows
from price action, volume, and cross-asset correlations.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.research.reflexivity.schemas import CapitalFlowSnapshot
from src.shared.logging import get_logger

logger = get_logger(__name__)


class CapitalFlowTracker:
    """Infers capital flow direction from available market data.

    In the absence of real flow data (EPFR, ICI, CFTC COT), this module
    estimates flow direction from:
        - Price momentum (direction + magnitude)
        - Cross-asset correlation changes
        - Volatility regime (VIX as flow signaler)
        - Rate differential signals
        - Sector rotation patterns
    """

    def __init__(self):
        self._flow_history: list[CapitalFlowSnapshot] = []
        self._max_history = 252  # ~1 year of daily data

    # ── Public API ────────────────────────────────────────────────────

    def snapshot(self, market_data: dict) -> CapitalFlowSnapshot:
        """Take a capital flow snapshot from current market data.

        Args:
            market_data: Dict with vix, dxy, us10y, us2y, spx_ytd, etc.

        Returns:
            CapitalFlowSnapshot with inferred flow signals
        """
        snap = CapitalFlowSnapshot()
        _now = datetime.now(UTC)

        vix = float(market_data.get("vix", 18))
        dxy = float(market_data.get("dxy", 100))
        us10y = float(market_data.get("us10y", 4.0))
        spx_ytd = float(market_data.get("spx_ytd", 0) or market_data.get("nasdaq_ytd", 0))
        hyg = float(market_data.get("hyg_spread", 400))
        gold = float(market_data.get("gold", 1800))
        oil = float(market_data.get("oil", 70))
        nasdaq_ytd = float(market_data.get("nasdaq_ytd", spx_ytd))

        # ── Equity flows ──
        if spx_ytd > 10:
            snap.equity_flow_direction = "inflow"
            snap.equity_flow_magnitude = "strong" if spx_ytd > 20 else "moderate"
        elif spx_ytd < -5:
            snap.equity_flow_direction = "outflow"
            snap.equity_flow_magnitude = "strong" if spx_ytd < -15 else "moderate"
        else:
            snap.equity_flow_direction = "neutral"
            snap.equity_flow_magnitude = "weak"

        # Sector rotation (simplified)
        if nasdaq_ytd > spx_ytd * 1.3:
            snap.sector_rotation.append({"from": "defensive", "to": "tech/growth", "strength": 0.7})
        elif nasdaq_ytd < spx_ytd * 0.5:
            snap.sector_rotation.append(
                {"from": "tech/growth", "to": "value/defensive", "strength": 0.6}
            )

        # ── Fixed income flows ──
        if us10y > 4.5:
            snap.bond_flow_direction = "outflow"  # Sell-off = outflows
            snap.duration_positioning = "short"
        elif us10y < 3.0:
            snap.bond_flow_direction = "inflow"
            snap.duration_positioning = "long"
        else:
            snap.bond_flow_direction = "neutral"
            snap.duration_positioning = "neutral"

        if hyg > 600:
            snap.credit_flow_direction = "outflow"
        elif hyg < 350:
            snap.credit_flow_direction = "inflow"
        else:
            snap.credit_flow_direction = "neutral"

        # ── Currency flows ──
        if dxy > 103:
            snap.usd_flow_direction = "inflow"
        elif dxy < 97:
            snap.usd_flow_direction = "outflow"
        else:
            snap.usd_flow_direction = "neutral"

        snap.em_fx_flow_direction = (
            "outflow" if dxy > 102 else ("inflow" if dxy < 98 else "neutral")
        )

        # ── Commodity flows ──
        snap.gold_flow_direction = (
            "inflow" if gold > 1900 else ("outflow" if gold < 1600 else "neutral")
        )
        snap.oil_flow_signal = "bullish" if oil > 85 else ("bearish" if oil < 50 else "neutral")

        # ── Aggregate ──
        risk_signals = []
        if vix < 15:
            risk_signals.append(1)
        if spx_ytd > 10:
            risk_signals.append(1)
        if hyg < 350:
            risk_signals.append(1)
        if vix > 25:
            risk_signals.append(-1)
        if spx_ytd < -10:
            risk_signals.append(-1)
        if hyg > 500:
            risk_signals.append(-1)

        risk_avg = sum(risk_signals) / len(risk_signals) if risk_signals else 0
        if risk_avg > 0.3:
            snap.risk_appetite_flow = "risk-on"
        elif risk_avg < -0.3:
            snap.risk_appetite_flow = "risk-off"
        else:
            snap.risk_appetite_flow = "neutral"

        snap.flow_momentum = risk_avg

        # ── Store history ──
        self._flow_history.append(snap)
        if len(self._flow_history) > self._max_history:
            self._flow_history = self._flow_history[-self._max_history :]

        return snap

    def get_flow_history(self, days: int = 20) -> list[CapitalFlowSnapshot]:
        """Return recent flow history."""
        return self._flow_history[-days:]

    def detect_flow_regime_change(self) -> dict | None:
        """Detect if flow regime has changed significantly.

        Compares most recent flow snapshot against the average of last N.
        """
        if len(self._flow_history) < 5:
            return None

        current = self._flow_history[-1]
        prev_window = (
            self._flow_history[-10:-1] if len(self._flow_history) >= 10 else self._flow_history[:-1]
        )

        changes = []

        # Check equity flow direction change
        prev_eq = [s.equity_flow_direction for s in prev_window]
        prev_eq_mode = max(set(prev_eq), key=prev_eq.count) if prev_eq else "neutral"
        if current.equity_flow_direction != prev_eq_mode:
            changes.append(f"equity_flow: {prev_eq_mode} → {current.equity_flow_direction}")

        # Check risk appetite change
        prev_risk = [s.risk_appetite_flow for s in prev_window]
        prev_risk_mode = max(set(prev_risk), key=prev_risk.count) if prev_risk else "neutral"
        if current.risk_appetite_flow != prev_risk_mode:
            changes.append(f"risk_appetite: {prev_risk_mode} → {current.risk_appetite_flow}")

        if not changes:
            return None

        return {
            "detected": True,
            "changes": changes,
            "current_regime": current.risk_appetite_flow,
            "severity": "major" if len(changes) >= 2 else "moderate",
        }

    def flow_summary(self) -> str:
        """Text summary of current flow picture."""
        if not self._flow_history:
            return "无资本流动数据"

        snap = self._flow_history[-1]
        parts = [
            f"风险偏好: {snap.risk_appetite_flow}",
            f"权益流向: {snap.equity_flow_direction} ({snap.equity_flow_magnitude})",
            f"债券流向: {snap.bond_flow_direction}",
            f"美元流向: {snap.usd_flow_direction}",
            f"信用流向: {snap.credit_flow_direction}",
        ]
        return " | ".join(parts)
