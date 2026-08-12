"""Paper Trader — Historical Replay Engine (Milestone E.5).

The definitive test of V3's research capability: replay years of historical
macro data day-by-day, with the agent seeing only past data.

Rules:
    - Agent NEVER sees future data (strict temporal isolation)
    - Each day: build MacroSnapshot from data up to that day
    - Run full Research Cycle → Thesis → Prediction
    - Register predictions, wait for their horizon to expire
    - Evaluate outcomes using actual future data
    - Track evolution: do principles/frameworks/beliefs improve over time?

Output:
    replay_results/
      ├── summary.json          — overall statistics
      ├── daily/                — YYYY-MM-DD.md daily reports
      ├── predictions.csv       — all predictions with outcomes
      ├── evolution.csv         — principle/framework/belief timeline
      └── growth_report.md      — final analysis of agent growth

This is the "PHD defense" of the V3 agent — if it can't learn from
5-10 years of real data, the knowledge architecture needs revision.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from src.schemas.macro_snapshot import MacroSnapshot, MarketSnapshot
from src.research.evolution.regime_gate import RegimeSnapshot
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ReplayDay:
    """A single day in the replay — market data + metadata."""

    date: str                         # YYYY-MM-DD
    data: dict[str, float] = field(default_factory=dict)
    regime_override: RegimeSnapshot | None = None


@dataclass
class ReplayStats:
    """Accumulated statistics over a replay run."""

    total_days: int = 0
    completed_cycles: int = 0
    failed_cycles: int = 0
    predictions_made: int = 0
    predictions_evaluated: int = 0
    predictions_correct: int = 0
    invalidated_theses: int = 0
    principles_created: int = 0
    principles_promoted: int = 0
    frameworks_created: int = 0
    beliefs_updated: int = 0
    conflicts_resolved: int = 0
    evolving_memory_entries: int = 0

    @property
    def hit_rate(self) -> float:
        if self.predictions_evaluated == 0:
            return 0.0
        return self.predictions_correct / self.predictions_evaluated

    @property
    def completion_rate(self) -> float:
        if self.total_days == 0:
            return 0.0
        return self.completed_cycles / self.total_days

    def to_dict(self) -> dict:
        return {
            "total_days": self.total_days,
            "completed_cycles": self.completed_cycles,
            "failed_cycles": self.failed_cycles,
            "completion_rate": round(self.completion_rate, 4),
            "predictions_made": self.predictions_made,
            "predictions_evaluated": self.predictions_evaluated,
            "predictions_correct": self.predictions_correct,
            "hit_rate": round(self.hit_rate, 4),
            "invalidated_theses": self.invalidated_theses,
            "principles_created": self.principles_created,
            "principles_promoted": self.principles_promoted,
            "frameworks_created": self.frameworks_created,
            "beliefs_updated": self.beliefs_updated,
            "conflicts_resolved": self.conflicts_resolved,
            "evolving_memory_entries": self.evolving_memory_entries,
        }


@dataclass
class ReplayResult:
    """Complete replay output."""

    stats: ReplayStats = field(default_factory=ReplayStats)
    start_date: str = ""
    end_date: str = ""
    output_dir: str = ""
    daily_results: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        s = self.stats
        lines = [
            f"=== Replay: {self.start_date} → {self.end_date} ===",
            f"Days: {s.total_days}, Cycles: {s.completed_cycles}/{s.total_days} "
            f"({s.completion_rate:.1%})",
            f"",
            f"Predictions: {s.predictions_made} made, {s.predictions_evaluated} evaluated",
            f"  Hit Rate: {s.hit_rate:.1%} ({s.predictions_correct}/{s.predictions_evaluated})",
            f"  Invalidated Theses: {s.invalidated_theses}",
            f"",
            f"Evolution:",
            f"  Principles: {s.principles_created} new, {s.principles_promoted} promoted",
            f"  Frameworks: {s.frameworks_created} created",
            f"  Beliefs: {s.beliefs_updated} updated",
            f"  Conflicts: {s.conflicts_resolved} resolved",
            f"  Memory: {s.evolving_memory_entries} entries",
        ]
        if self.errors:
            lines.append(f"")
            lines.append(f"Errors: {len(self.errors)}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Paper Trader
# ═══════════════════════════════════════════════════════════════════════════════


class PaperTrader:
    """Historical replay engine for validating V3 research capability.

    Runs the Daily Runner against a sequence of historical market data,
    ensuring the agent never sees future data.

    Usage:
        trader = PaperTrader()
        result = trader.replay(days=load_data(), start="2020-01-01", end="2023-12-31")
    """

    def __init__(
        self,
        output_dir: str = "replay_results",
        memory_path: str | None = None,
        registry_path: str | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.memory_path = memory_path or "data/replay_memory.json"
        self.registry_path = registry_path or "data/replay_predictions.db"

        # Internal state
        self._stats = ReplayStats()

    # ── Main Entry ──────────────────────────────────────────────────────

    def replay(
        self,
        days: list[ReplayDay],
        progress_callback: Callable[[int, int, ReplayDay], None] | None = None,
    ) -> ReplayResult:
        """Replay a sequence of historical days.

        Each day: the agent sees only that day's data and all prior data.
        Never sees the future.

        Args:
            days: Ordered list of ReplayDay objects (earliest first).
            progress_callback: Optional (current, total, day) callback.

        Returns:
            ReplayResult with full statistics and daily records.
        """
        if not days:
            raise ValueError("No days provided for replay")

        result = ReplayResult(
            start_date=days[0].date,
            end_date=days[-1].date,
            output_dir=str(self.output_dir),
        )

        self._prepare_output_dirs()
        self._stats = ReplayStats()

        # Initialize runner with replay-specific paths
        from src.runtime.daily_runner import DailyRunner

        runner = DailyRunner(
            memory_path=self.memory_path,
            registry_path=self.registry_path,
            report_dir=str(self.output_dir / "daily"),
        )

        total = len(days)

        for i, day in enumerate(days):
            try:
                if progress_callback:
                    progress_callback(i + 1, total, day)

                logger.info("Replay day %d/%d: %s", i + 1, total, day.date)

                # ── Run daily cycle ──────────────────────────
                run_report = runner.run_today(
                    macro_data=day.data,
                    date_str=day.date,
                    regime_override=day.regime_override,
                )

                self._stats.total_days += 1

                if run_report.is_success:
                    self._stats.completed_cycles += 1

                    # Count predictions
                    self._stats.predictions_made += run_report.predictions_registered

                    # Evolution stats
                    if run_report.cycle_result and run_report.cycle_result.evolution_result:
                        ev = run_report.cycle_result.evolution_result
                        self._stats.principles_created += ev.get("principles_created", 0)
                        self._stats.principles_promoted += ev.get("principles_promoted", 0)
                        self._stats.frameworks_created += ev.get("frameworks_created", 0)
                        self._stats.beliefs_updated += ev.get("beliefs_updated", 0)
                        self._stats.conflicts_resolved += ev.get("conflicts_resolved", 0)

                    if run_report.cycle_result and run_report.cycle_result.memory_entry_id:
                        self._stats.evolving_memory_entries += 1

                else:
                    self._stats.failed_cycles += 1
                    result.errors.append(f"{day.date}: {run_report.error}")
                    logger.warning("Day %s failed: %s", day.date, run_report.error)

                # Scheduler stats
                if run_report.scheduler_report:
                    self._stats.predictions_evaluated += run_report.scheduler_report.predictions_evaluated
                    self._stats.predictions_correct += run_report.scheduler_report.correct
                    self._stats.invalidated_theses += run_report.scheduler_report.invalidated_theses

                # Record daily result
                result.daily_results.append({
                    "date": day.date,
                    "status": run_report.status,
                    "preds_registered": run_report.predictions_registered,
                    "preds_evaluated": run_report.scheduler_report.predictions_evaluated if run_report.scheduler_report else 0,
                    "correct": run_report.scheduler_report.correct if run_report.scheduler_report else 0,
                    "thesis_title": (
                        run_report.cycle_result.thesis.title[:120]
                        if run_report.cycle_result and run_report.cycle_result.thesis
                        else ""
                    ),
                })

            except Exception as e:
                self._stats.total_days += 1
                self._stats.failed_cycles += 1
                result.errors.append(f"{day.date}: EXCEPTION {e}")
                logger.error("Day %s crashed: %s", day.date, e)

        result.stats = self._stats

        # ── Save outputs (before closing runner) ────────────
        self._save_summary(result)
        self._save_predictions_csv(runner)
        self._save_daily_csv(result)
        self._save_growth_report(result)

        runner.close()

        logger.info("Replay complete: %s", result.summary())
        return result

    # ── Data Helpers ────────────────────────────────────────────────────

    @staticmethod
    def generate_synthetic_days(
        start_date: str,
        end_date: str,
        base_values: dict[str, float] | None = None,
        seed: int = 42,
    ) -> list[ReplayDay]:
        """Generate synthetic market data for replay testing.

        Uses geometric random walk with realistic correlations.
        Useful for testing the replay infrastructure before connecting
        real data.

        Args:
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            base_values: Starting values for each ticker
            seed: Random seed for reproducibility

        Returns:
            Ordered list of ReplayDay objects.
        """
        import random
        random.seed(seed)

        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        delta = (end - start).days

        if delta <= 0:
            raise ValueError(f"Invalid date range: {start_date} → {end_date}")

        base = base_values or {
            "spx": 4000.0, "vix": 20.0, "dxy": 100.0,
            "us10y": 3.5, "us2y": 3.8, "hyg": 75.0,
            "gold": 1900.0, "copper": 3.8,
        }

        current = dict(base)
        prev = dict(base)
        days = []

        for d in range(delta + 1):
            date = (start + timedelta(days=d)).isoformat()

            # Skip weekends for realism
            if (start + timedelta(days=d)).weekday() >= 5:
                continue

            day_data: dict[str, float] = {}

            # SPX: daily vol ~1%
            day_data["spx"] = current["spx"]
            day_data["prev_spx"] = prev["spx"]

            # VIX: mean-reverting around base
            day_data["vix"] = current["vix"]
            day_data["prev_vix"] = prev["vix"]

            # DXY: low vol
            day_data["dxy"] = current["dxy"]
            day_data["prev_dxy"] = prev["dxy"]

            # US10Y: low vol
            day_data["us10y"] = current["us10y"]
            day_data["prev_us10y"] = prev["us10y"]
            day_data["us2y"] = current["us2y"]
            day_data["prev_us2y"] = prev["us2y"]

            # HYG
            day_data["hyg"] = current["hyg"]
            day_data["prev_hyg"] = prev["hyg"]

            # Gold
            day_data["gold"] = current["gold"]
            day_data["prev_gold"] = prev["gold"]

            days.append(ReplayDay(date=date, data=day_data))

            # Update for next day (random walk)
            prev = dict(current)
            # SPX: 1% daily vol, +0.03% drift
            spx_return = random.gauss(0.0003, 0.01)
            current["spx"] = int(current["spx"] * (1 + spx_return))

            # VIX: correlated with SPX (inverse), mean-revert to base
            vix_delta = -spx_return * 100 + random.gauss(0, 0.5)
            current["vix"] = max(8, min(50, current["vix"] + vix_delta))

            # DXY: low vol
            current["dxy"] = current["dxy"] * (1 + random.gauss(0, 0.003))

            # Rates: slow drift
            current["us10y"] = max(0.5, current["us10y"] + random.gauss(0, 0.03))
            current["us2y"] = max(0.5, current["us2y"] + random.gauss(0, 0.03))

            # HYG: correlated with SPX
            current["hyg"] = current["hyg"] * (1 + spx_return * 0.5 + random.gauss(0, 0.002))

            # Gold: inverse to real rates
            current["gold"] = current["gold"] * (1 - 0.5 * (current["us10y"] - 3.5) / 100 + random.gauss(0, 0.005))

            # Copper: growth proxy
            current["copper"] = current["copper"] * (1 + spx_return * 0.7 + random.gauss(0, 0.005))

        logger.info("Generated %d trading days from %s to %s", len(days), start_date, end_date)
        return days

    @staticmethod
    def load_csv(source: str) -> list[ReplayDay]:
        """Load market data from a CSV file.

        Expected CSV format:
            date,spx,vix,dxy,us10y,us2y,hyg,gold,copper,...
            (sorted by date, earliest first)

        Previous values (prev_spx etc.) are automatically computed.
        """
        import csv as csv_mod
        from collections import defaultdict

        rows = []
        with open(source, "r", encoding="utf-8-sig") as f:
            reader = csv_mod.DictReader(f)
            for row in reader:
                rows.append(row)

        days = []
        prev_values: dict[str, float] = {}

        for row in rows:
            date = row.get("date", "")
            day_data: dict[str, float] = {}
            current_values: dict[str, float] = {}

            for col, val in row.items():
                if col == "date":
                    continue
                try:
                    day_data[col] = float(val)
                    current_values[col] = float(val)
                except (ValueError, TypeError):
                    pass

            # Set previous values
            for col, val in prev_values.items():
                prev_key = f"prev_{col}"
                day_data[prev_key] = val

            days.append(ReplayDay(date=date, data=day_data))
            prev_values = current_values

        logger.info("Loaded %d days from %s", len(days), source)
        return days

    # ── Output ──────────────────────────────────────────────────────────

    def _prepare_output_dirs(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "daily").mkdir(parents=True, exist_ok=True)

    def _save_summary(self, result: ReplayResult) -> None:
        path = self.output_dir / "summary.json"
        summary = {
            "start_date": result.start_date,
            "end_date": result.end_date,
            "stats": result.stats.to_dict(),
            "error_count": len(result.errors),
        }
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Summary saved to %s", path)

    def _save_predictions_csv(self, runner) -> None:
        """Export all predictions from the registry to CSV."""
        path = self.output_dir / "predictions.csv"
        preds = runner.registry.get_history(99999)

        if not preds:
            # Create empty file with headers
            path.write_text(
                "prediction_id,thesis_id,date,direction,asset,confidence,"
                "horizon_days,expected_date,status,actual_value,thesis_title\n"
            )
            return

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "prediction_id", "thesis_id", "date", "direction", "asset",
                "confidence", "horizon_days", "expected_date", "status",
                "actual_value", "thesis_title",
            ])
            for p in preds:
                writer.writerow([
                    p.prediction_id, p.thesis_id, p.date, p.direction,
                    p.asset, p.confidence, p.horizon_days, p.expected_date,
                    p.status, p.actual_value, p.thesis_title,
                ])

        logger.info("Predictions CSV saved to %s (%d rows)", path, len(preds))

    def _save_daily_csv(self, result: ReplayResult) -> None:
        """Export daily summary to CSV."""
        path = self.output_dir / "daily_summary.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "date", "status", "preds_registered", "preds_evaluated",
                "correct", "thesis_title",
            ])
            for d in result.daily_results:
                writer.writerow([
                    d["date"], d["status"], d["preds_registered"],
                    d["preds_evaluated"], d["correct"], d["thesis_title"],
                ])

        logger.info("Daily summary CSV saved to %s", path)

    def _save_growth_report(self, result: ReplayResult) -> None:
        """Generate a markdown growth analysis report."""
        s = result.stats

        lines = [
            f"# Agent Growth Report — {result.start_date} → {result.end_date}",
            f"",
            f"## Executive Summary",
            f"",
            f"- **Days Replayed**: {s.total_days}",
            f"- **Completed Cycles**: {s.completed_cycles}/{s.total_days} ({s.completion_rate:.1%})",
            f"- **Predictions**: {s.predictions_made} made, {s.predictions_evaluated} evaluated",
            f"- **Hit Rate**: {s.hit_rate:.1%}",
            f"- **Evolution**: {s.principles_created} principles, {s.frameworks_created} frameworks",
            f"",
            f"## Hypothesis Quality",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Hit Rate | {s.hit_rate:.1%} |",
            f"| Total Predictions | {s.predictions_made} |",
            f"| Evaluated | {s.predictions_evaluated} |",
            f"| Invalidated Theses | {s.invalidated_theses} |",
            f"",
            f"## Framework Evolution",
            f"",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Frameworks Created | {s.frameworks_created} |",
            f"| Principles Created | {s.principles_created} |",
            f"| Principles Promoted | {s.principles_promoted} |",
            f"| Beliefs Updated | {s.beliefs_updated} |",
            f"| Conflicts Resolved | {s.conflicts_resolved} |",
            f"",
            f"## Assessment",
            f"",
        ]

        # Self-evaluation
        if s.hit_rate > 0.65:
            lines.append("✅ **Strong**: Agent's prediction accuracy is significantly above random.")
        elif s.hit_rate > 0.55:
            lines.append("⚠️ **Moderate**: Agent shows directional edge but room for improvement.")
        else:
            lines.append("❌ **Weak**: Agent does not demonstrate reliable prediction capability.")

        if s.frameworks_created > 0:
            lines.append(f"🧠 **Learning**: Agent formed {s.frameworks_created} new frameworks — knowledge is evolving.")
        else:
            lines.append("⚠️ **Static**: No new frameworks formed — knowledge may not be accumulating.")

        lines.append("")
        lines.append(f"*Generated: {datetime.now(timezone.utc).isoformat()}*")

        path = self.output_dir / "growth_report.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Growth report saved to %s", path)
