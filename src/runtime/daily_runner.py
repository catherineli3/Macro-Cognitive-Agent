"""Daily Runner — the single entry point for each day's research (Milestone E, Task 1).

This is THE file that makes V3 "live". Every market day, call:

    runner = DailyRunner()
    result = runner.run_today(macro_data=market_data)

No new intelligence. Just connects the existing Research Cycle Engine
with the runtime infrastructure (registry, scheduler, reports).

Flow:
    Market Data → MacroSnapshot → ResearchCycle → Register Predictions
    → Schedule Outcomes → Generate Report → Return RunReport
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_type
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.schemas.macro_snapshot import MacroSnapshot, MarketSnapshot
from src.research.evolution.regime_gate import RegimeSnapshot
from src.research_cycle.cycle_engine import ResearchCycleEngine, CycleResult
from src.runtime.prediction_registry import PredictionRegistry
from src.runtime.outcome_scheduler import OutcomeScheduler, SchedulerReport
from src.runtime.report_generator import ReportGenerator
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RunReport:
    """Complete output of one daily run."""

    date: str = ""
    status: str = "pending"                # "completed" | "failed"
    cycle_result: CycleResult | None = None
    scheduler_report: SchedulerReport | None = None
    predictions_registered: int = 0
    report_path: str = ""
    error: str = ""
    artifacts: dict = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status == "completed"

    def summary(self) -> str:
        lines = [
            f"Daily Run — {self.date} — {self.status.upper()}",
            f"  Predictions: {self.predictions_registered} registered",
        ]
        if self.cycle_result:
            lines.append(f"  Thesis: {self.cycle_result.thesis.title[:80] if self.cycle_result.thesis else 'N/A'}")
        if self.scheduler_report:
            lines.append(f"  Evaluations: {self.scheduler_report.predictions_evaluated} eval'd, "
                         f"{self.scheduler_report.hit_rate:.1%} hit rate")
        if self.report_path:
            lines.append(f"  Report: {self.report_path}")
        if self.error:
            lines.append(f"  ERROR: {self.error}")
        return "\n".join(lines)


class DailyRunner:
    """The daily research runner.

    One call per market day. Connects all layers:
        - Data ingestion → MacroSnapshot
        - Research Cycle → Thesis + Predictions
        - Runtime infrastructure → Registry + Scheduler + Report

    Settings (local file overrides):
        data/research_memory.json  — cycle history
        data/predictions.db        — prediction registry
        reports/YYYY-MM-DD.md      — daily output

    Usage:
        runner = DailyRunner()
        report = runner.run_today(macro_data={
            "spx": 5200, "prev_spx": 5100,
            "vix": 15, "dxy": 104, "us10y": 4.2,
        })
    """

    def __init__(
        self,
        memory_path: str | None = None,
        registry_path: str | None = None,
        report_dir: str | None = None,
    ):
        """Initialize the daily runner.

        Args:
            memory_path: Research memory JSON path.
            registry_path: SQLite prediction registry path.
            report_dir: Directory for daily markdown reports.
        """
        # ── Core engine ──────────────────────────────────────────
        self.engine = ResearchCycleEngine(memory_path=memory_path)

        # ── Runtime infrastructure ───────────────────────────────
        self.registry = PredictionRegistry(db_path=registry_path)
        self.scheduler = OutcomeScheduler(registry=self.registry, engine=self.engine)
        self.reporter = ReportGenerator(output_dir=report_dir)

        # ── State ──────────────────────────────────────────────────
        self._previous_result: CycleResult | None = None
        self._run_count: int = 0

    # ── Main Entry: run_today ────────────────────────────────────────

    def run_today(
        self,
        macro_data: dict[str, float] | None = None,
        date_str: str | None = None,
        regime_override: RegimeSnapshot | None = None,
    ) -> RunReport:
        """Execute one complete daily research cycle.

        Args:
            macro_data: Today's market data dict.
                e.g. {"spx": 5200, "prev_spx": 5100, "vix": 15, ...}
            date_str: Override date (YYYY-MM-DD). Default: today.
            regime_override: Optional pre-determined RegimeSnapshot.

        Returns:
            RunReport with full daily output.
        """
        today = date_str or date_type.today().isoformat()
        self._run_count += 1

        report = RunReport(date=today)

        try:
            # ── Step 1: Build MacroSnapshot ──────────────────
            snapshot = self._build_snapshot(macro_data or {}, regime_override)
            logger.info("Daily Run #%d — %s — Regime: %s",
                         self._run_count, today, snapshot.regime_label)

            # ── Step 2: Outcome Evaluation (yesterday's predictions) ──
            scheduler_report = self.scheduler.run(
                date_str=today,
                market_data=macro_data,
            )
            report.scheduler_report = scheduler_report
            logger.info("Evaluated %d predictions (hit rate: %.1f%%)",
                         scheduler_report.predictions_evaluated,
                         scheduler_report.hit_rate * 100)

            # ── Step 3: Build previous outcomes map ──────────
            previous_outcomes = self._gather_previous_outcomes()

            # ── Step 4: Run Research Cycle ───────────────────
            cycle_result = self.engine.run_cycle(
                macro_snapshot=snapshot,
                previous_outcomes=previous_outcomes if previous_outcomes else None,
                skip_evolution=False,
            )
            report.cycle_result = cycle_result

            if not cycle_result.is_success:
                report.status = "failed"
                report.error = cycle_result.error or "Cycle failed"
                return report

            # ── Step 5: Register Predictions ─────────────────
            if cycle_result.thesis and cycle_result.prediction_batch:
                count = self.registry.register_predictions(
                    thesis=cycle_result.thesis,
                    predictions=cycle_result.prediction_batch,
                    date_str=today,
                )
                report.predictions_registered = count

            # ── Step 6: Generate Daily Report ────────────────
            report_path = self.reporter.generate(
                cycle_result=cycle_result,
                date_str=today,
                previous_result=self._previous_result,
                memory=self.engine.memory,
                registry=self.registry,
            )
            report.report_path = report_path

            # ── Step 7: Store for next cycle ─────────────────
            self._previous_result = cycle_result

            report.status = "completed"
            logger.info("Daily Run #%d completed — %s", self._run_count, today)

        except Exception as e:
            report.status = "failed"
            report.error = str(e)
            logger.error("Daily Run #%d FAILED: %s", self._run_count, e)

        return report

    # ── Snapshot Builder ─────────────────────────────────────────────

    def _build_snapshot(
        self,
        macro_data: dict[str, float],
        regime_override: RegimeSnapshot | None = None,
    ) -> MacroSnapshot:
        """Build a MacroSnapshot from market data.

        V3.1: Prefers the full MacroPipeline. Falls back to raw dict
        heuristic inference when pipeline is unavailable.

        If no regime_override is provided, infers regime from data heuristics.
        """
        # ── V3.1: Try full MacroPipeline first ──────────────────
        try:
            from src.data_pipeline.macro_pipeline import MacroPipeline
            pipeline = MacroPipeline()
            m1_snapshot = pipeline.build_daily_macro_snapshot(
                for_dimension=None,
                persist=False,
            )
            if m1_snapshot.get("state_vector"):
                # Bridge M1 output to MacroSnapshot
                return self._bridge_pipeline_to_snapshot(m1_snapshot, regime_override)
        except Exception as e:
            logger.debug("MacroPipeline unavailable, using heuristic: %s", e)

        # ── Fallback: Heuristic from raw dict ─────────────────
        # Determine regime
        if regime_override:
            regime = regime_override
        else:
            regime = self._infer_regime(macro_data)

        # Build MarketSnapshot
        market = MarketSnapshot(indicators=macro_data)

        # Build signal list from data
        signals = self._build_signals(macro_data)

        snapshot = MacroSnapshot(
            regime=regime,
            market=market,
            signals=signals,
        )
        return snapshot

    @staticmethod
    def _bridge_pipeline_to_snapshot(
        m1_snapshot: dict,
        regime_override: RegimeSnapshot | None = None,
    ) -> MacroSnapshot:
        """Bridge M1 pipeline output to MacroSnapshot (V3.1 unified path)."""
        # Re-use the bridge function from M1DailyRunner
        try:
            from scripts.run_m1_daily import bridge_m1_to_macro_snapshot
            snapshot = bridge_m1_to_macro_snapshot(m1_snapshot)
            if regime_override:
                snapshot.regime = regime_override
            return snapshot
        except ImportError:
            # Fallback: build directly
            return DailyRunner._bridge_m1_manually(m1_snapshot, regime_override)

    @staticmethod
    def _bridge_m1_manually(
        m1_snapshot: dict,
        regime_override: RegimeSnapshot | None = None,
    ) -> MacroSnapshot:
        """Manual M1 pipeline → MacroSnapshot bridge (fallback)."""
        from src.schemas.macro_snapshot import MarketSnapshot

        sv = m1_snapshot.get("state_vector", {})
        indicators = {}
        for dim_name, dim_data in sv.items():
            if isinstance(dim_data, dict):
                for k, v in dim_data.items():
                    if isinstance(v, (int, float)):
                        indicators[f"{dim_name}.{k}"] = v

        if regime_override:
            regime = regime_override
        else:
            # Infer from state vector
            liquidity = sv.get("Liquidity", {})
            growth = sv.get("Growth", {})
            inflation = sv.get("Inflation", {})
            risk = sv.get("Risk_Appetite", {})

            def _dir(d, default="neutral"):
                d_map = {
                    "tightening": "tightening", "easing": "easing",
                    "expansion": "accelerating", "contraction": "decelerating",
                    "risk_on": "low", "risk_off": "high",
                }
                return d_map.get(d.get("direction", default), default)

            regime = RegimeSnapshot(
                monetary_policy=_dir(liquidity, "neutral"),
                growth=_dir(growth, "stable"),
                inflation=_dir(inflation, "stable"),
                volatility=_dir(risk, "moderate"),
                fiscal_stance="neutral",
            )

        market = MarketSnapshot(indicators=indicators)
        return MacroSnapshot(regime=regime, market=market)

    @staticmethod
    def _infer_regime(data: dict[str, float]) -> RegimeSnapshot:
        """Infer macro regime from data heuristics.

        Uses simple thresholds to classify regime dimensions.
        This is a lightweight heuristic — not a full regime detection engine.
        """
        monetary = "neutral"
        growth_label = "stable"
        inflation_label = "stable"
        vol_label = "moderate"
        fiscal = "neutral"

        # Monetary: check Fed rate trend
        fed_rate = data.get("fed_rate", 0)
        prev_fed = data.get("prev_fed_rate", 0)
        us2y = data.get("us2y", 0)
        us10y = data.get("us10y", 0)

        if prev_fed and fed_rate:
            if fed_rate < prev_fed:
                monetary = "easing"
            elif fed_rate > prev_fed:
                monetary = "tightening"

        # Yield curve inversion = tightening pressure
        if us2y and us10y and us2y > us10y:
            if monetary != "easing":
                monetary = "tightening"

        # Growth: check equity trend and commodity indicators
        spx = data.get("spx", 0)
        prev_spx = data.get("prev_spx", 0)
        copper = data.get("copper", 0)
        prev_copper = data.get("prev_copper", 0)

        growth_signals = 0
        if spx and prev_spx and spx > prev_spx * 1.02:
            growth_signals += 1
        elif spx and prev_spx and spx < prev_spx * 0.98:
            growth_signals -= 1

        if copper and prev_copper and copper > prev_copper * 1.02:
            growth_signals += 1
        elif copper and prev_copper and copper < prev_copper * 0.98:
            growth_signals -= 1

        if growth_signals >= 2:
            growth_label = "accelerating"
        elif growth_signals <= -2:
            growth_label = "decelerating"

        # Inflation: check CPI, gold
        cpi = data.get("cpi_yoy", 0)
        prev_cpi = data.get("prev_cpi_yoy", 0)
        gold = data.get("gold", 0)
        prev_gold = data.get("prev_gold", 0)

        if cpi and prev_cpi:
            if cpi > prev_cpi * 1.05:
                inflation_label = "rising"
            elif cpi < prev_cpi * 0.95:
                inflation_label = "falling"

        if gold and prev_gold and gold > prev_gold * 1.05:
            if inflation_label == "stable":
                inflation_label = "rising"

        # Volatility: VIX
        vix = data.get("vix", 15)
        if vix > 30:
            vol_label = "high"
        elif vix > 20:
            vol_label = "elevated"
        elif vix < 12:
            vol_label = "low"

        # DXY strength
        dxy = data.get("dxy", 100)
        if dxy > 105:
            fiscal = "tight" if fiscal == "neutral" else fiscal
        elif dxy < 95:
            fiscal = "loose" if fiscal == "neutral" else fiscal

        return RegimeSnapshot(
            monetary_policy=monetary,
            growth=growth_label,
            inflation=inflation_label,
            volatility=vol_label,
            fiscal_stance=fiscal,
        )

    @staticmethod
    def _build_signals(data: dict[str, float]) -> list[Any]:
        """Build MacroSignalSchema list from market data for hypothesis competition."""
        from src.schemas.signal import (
            MacroSignalSchema, SignalDirection, SignalStrength, SignalEvidence,
        )

        # Map indicator keys to hypothesis dimensions
        DIMENSION_MAP = {
            "spx": "Risk Appetite",
            "vix": "Volatility",
            "dxy": "Liquidity",
            "us10y": "Rates",
            "us2y": "Rates",
            "hyg": "Credit",
            "gold": "Inflation",
            "copper": "Growth",
            "cpi_yoy": "Inflation",
            "fed_rate": "Monetary Policy",
        }

        signals = []
        for key, value in data.items():
            if key.startswith("prev_"):
                continue
            prev_key = f"prev_{key}"
            prev_value = data.get(prev_key, value)

            if prev_value and prev_value != 0 and value != 0:
                change = (value - prev_value) / abs(prev_value)

                # Direction: BULLISH = good for risk assets
                # BEARISH indicators: VIX↑, DXY↑, rates↑, CPI↑, gold↑
                BEARISH_INDICATORS = {"vix", "dxy", "us10y", "us2y", "gold",
                                       "cpi_yoy", "fed_rate"}
                if change > 0.01:
                    direction = (SignalDirection.BEARISH if key in BEARISH_INDICATORS
                                 else SignalDirection.BULLISH)
                elif change < -0.01:
                    direction = (SignalDirection.BULLISH if key in BEARISH_INDICATORS
                                 else SignalDirection.BEARISH)
                else:
                    direction = SignalDirection.NEUTRAL

                # Strength
                abs_change = abs(change)
                if abs_change > 0.05:
                    strength = SignalStrength.STRONG
                elif abs_change > 0.02:
                    strength = SignalStrength.MODERATE
                else:
                    strength = SignalStrength.WEAK

                dimension = DIMENSION_MAP.get(key, "Macro")
                confidence = min(0.85, abs_change * 8)

                signal = MacroSignalSchema(
                    indicator=key.upper(),
                    dimension=dimension,
                    direction=direction,
                    strength=strength,
                    confidence=confidence,
                    evidence=[SignalEvidence(
                        rule_id=f"market_data_{key}",
                        rule_description=f"Market data change for {key}",
                        input_value=value,
                        condition=f"prev={prev_value}, current={value}, change={change:.2%}",
                        interpretation=f"{key.upper()}: {prev_value} → {value} ({change:+.2%})",
                    )],
                    metadata={"raw_change": change, "raw_previous": prev_value},
                )
                signals.append(signal)

        return signals

    # ── Previous Outcome Gathering ───────────────────────────────────

    def _gather_previous_outcomes(
        self,
    ) -> dict[str, tuple[dict[str, float], str]] | None:
        """Gather outcomes from the previous cycle's thesis AND any recently
        evaluated predictions from the registry.

        This ensures that when the OutcomeScheduler evaluates 30-day-old
        predictions, those outcomes are fed back to the cycle engine as
        previous_outcomes — completing the learning feedback loop.
        """
        outcomes: dict[str, tuple[dict[str, float], str]] = {}

        # ── Check 1: Immediately previous cycle's thesis ──────
        if self._previous_result and self._previous_result.thesis:
            prev_thesis = self._previous_result.thesis
            thesis_id = prev_thesis.thesis_id
            preds = self.registry.get_by_thesis(thesis_id)
            if preds:
                actual_data: dict[str, float] = {}
                notes_parts: list[str] = []
                for p in preds:
                    if p.actual_value is not None:
                        actual_data[p.asset] = p.actual_value
                    if p.evaluation:
                        notes_parts.append(f"[{p.asset}] {p.evaluation}")
                notes = "; ".join(notes_parts) if notes_parts else "Evaluated by scheduler"
                if actual_data:
                    outcomes[thesis_id] = (actual_data, notes)

        # ── Check 2: Recently evaluated predictions from older theses ──
        # The scheduler may have just evaluated 30-day-old predictions.
        # Scan registry for recently-evaluated (non-pending, non-invalidated)
        # predictions that haven't yet been fed to the cycle engine.
        recently_evaluated = self.registry.get_recently_evaluated(days=7)
        for pred in recently_evaluated:
            tid = pred.thesis_id
            if tid in outcomes:
                # Already captured via Check 1
                continue
            if tid not in outcomes:
                outcomes[tid] = ({}, "")
            data_map, existing_notes = outcomes[tid]
            if pred.actual_value is not None:
                data_map[pred.asset] = pred.actual_value
            note = pred.evaluation or f"[{pred.asset}] {pred.status}"
            combined = existing_notes + "; " + note if existing_notes else note
            outcomes[tid] = (data_map, combined)

        # ── Check 3: Invalidated theses from scheduler ─────────
        invalidated = self.registry.get_recently_invalidated(days=7)
        for pred in invalidated:
            tid = pred.thesis_id
            if tid not in outcomes:
                outcomes[tid] = ({}, "")
            data_map, existing_notes = outcomes[tid]
            note = pred.evaluation or f"[{pred.asset}] INVALIDATED"
            combined = existing_notes + "; " + note if existing_notes else note
            outcomes[tid] = (data_map, combined)

        return outcomes if outcomes else None

    # ── Status & Summary ────────────────────────────────────────────

    @property
    def run_count(self) -> int:
        return self._run_count

    @property
    def registry_stats(self) -> dict:
        return self.registry.stats()

    def summary(self) -> str:
        """Comprehensive daily runner summary."""
        lines = [
            f"=== Daily Runner (Run {self._run_count}) ===",
            f"",
            f"{self.engine.summary()}",
            f"",
            f"{self.registry.summary()}",
            f"",
            f"Report dir: {self.reporter._output_dir}",
        ]
        return "\n".join(lines)

    def close(self) -> None:
        """Clean up resources."""
        self.registry.close()
