"""Phase 1 Baseline: Run 100 research cycles with seed=42.

Agent First Principle:
    - Zero modification to Agent source code
    - SnapshotManager injected via constructor parameter (already designed for this)
    - BeliefAdapter bridges AdaptiveBelief ↔ BeliefMemoryStore (Schema in runner, not Agent)
    - Market data generated via PaperTrader's existing synthetic generator

Output:
    snapshot/day_001/ through day_100/   — 100 complete snapshots
    snapshot/run_manifest.json            — Full run index
    data/baseline_run/                    — Clean research memory for this run

Usage:
    cd macro-research-agent
    python scripts/run_baseline_100.py
"""

from __future__ import annotations

import json
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Inject project root ───────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.paper_trader import PaperTrader
from src.research_cycle.cycle_engine import ResearchCycleEngine, CycleResult
from src.research.snapshot import SnapshotManager
from src.memory.store import BeliefMemoryStore
from src.schemas.macro_snapshot import MacroSnapshot, MarketSnapshot
from src.research.evolution.regime_gate import RegimeSnapshot
from src.shared.logging import get_logger

logger = get_logger(__name__)

SEED = 42
TOTAL_CYCLES = 100

# ── Clean data environment for this run ───────────────────────────────────
BASELINE_DIR = PROJECT_ROOT / "data" / "baseline_run"
SNAPSHOT_DIR = PROJECT_ROOT / "snapshot"


def setup_clean_environment() -> tuple[Path, Path]:
    """Create fresh data directories for the baseline run."""
    if BASELINE_DIR.exists():
        shutil.rmtree(BASELINE_DIR)
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)

    # Clean snapshot directory
    if SNAPSHOT_DIR.exists():
        shutil.rmtree(SNAPSHOT_DIR)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    memory_path = str(BASELINE_DIR / "research_memory.json")
    belief_path = str(BASELINE_DIR / "beliefs.json")

    return Path(memory_path), Path(belief_path)


# ── Belief Adapter: Bridge EvolutionPipeline.belief_manager → SnapshotWriter ──
class BeliefAdapter:
    """Adapts EvolutionPipeline's BeliefLifecycleManager to BeliefMemoryStore API.

    The SnapshotWriter expects a BeliefMemoryStore with .all_beliefs().
    EvolutionPipeline produces AdaptiveBelief objects via BeliefLifecycleManager.
    This adapter bridges them WITHOUT modifying any Agent source code.
    """

    def __init__(self, belief_manager: Any = None, persistence: BeliefMemoryStore | None = None):
        self._manager = belief_manager
        self._persistence = persistence

    def all_beliefs(self) -> list[Any]:
        """Return all beliefs from both live manager and persisted store."""
        records: list[Any] = []

        # Live beliefs from EvolutionPipeline
        if self._manager is not None:
            try:
                live = self._manager.get_active_beliefs()
                records.extend(live)
            except Exception:
                pass

        # Persisted beliefs from BeliefMemoryStore
        if self._persistence is not None:
            try:
                persisted = self._persistence.all_beliefs()
                # Deduplicate by belief_id
                live_ids = {
                    getattr(b, 'belief_id', '') for b in records
                    if hasattr(b, 'belief_id')
                }
                for p in persisted:
                    pid = getattr(p, 'belief_id', '') if hasattr(p, 'belief_id') else ''
                    if pid not in live_ids:
                        records.append(p)
            except Exception:
                pass

        return records

    def record(self, record: Any) -> None:
        """Proxy to persistence store if available."""
        if self._persistence is not None:
            self._persistence.record(record)

    @property
    def belief_count(self) -> int:
        return len(self.all_beliefs())


# ── Market Data Generation ────────────────────────────────────────────────
def generate_market_data(num_days: int = 100) -> list[dict[str, float]]:
    """Generate synthetic market data for baseline experiment.

    Uses PaperTrader's generate_synthetic_data with seed=42 for reproducibility.
    Returns market_data dicts suitable for building MacroSnapshots.
    """
    import random
    random.seed(SEED)

    start_date = "2024-01-01"
    from datetime import date, timedelta
    start = date(2024, 1, 1)

    base_values = {
        "spx": 4000.0, "vix": 20.0, "dxy": 100.0,
        "us10y": 3.5, "us2y": 3.8, "hyg": 75.0,
        "gold": 1900.0, "copper": 3.8,
    }

    current = dict(base_values)
    prev = dict(base_values)
    market_days: list[dict[str, float]] = []

    day_count = 0
    d = 0
    while day_count < num_days:
        date_obj = start + timedelta(days=d)
        d += 1

        # Skip weekends
        if date_obj.weekday() >= 5:
            continue

        day_data: dict[str, float] = {}

        # Current values
        day_data["spx"] = current["spx"]
        day_data["prev_spx"] = prev["spx"]
        day_data["vix"] = current["vix"]
        day_data["prev_vix"] = prev["vix"]
        day_data["dxy"] = current["dxy"]
        day_data["prev_dxy"] = prev["dxy"]
        day_data["us10y"] = current["us10y"]
        day_data["prev_us10y"] = prev["us10y"]
        day_data["us2y"] = current["us2y"]
        day_data["prev_us2y"] = prev["us2y"]
        day_data["hyg"] = current["hyg"]
        day_data["prev_hyg"] = prev["hyg"]
        day_data["gold"] = current["gold"]
        day_data["prev_gold"] = prev["gold"]
        day_data["copper"] = current["copper"]
        day_data["prev_copper"] = prev["copper"]

        # CPI and Fed rate for richer signal generation
        day_data["cpi_yoy"] = 3.0 + random.gauss(0, 0.1)
        day_data["prev_cpi_yoy"] = day_data["cpi_yoy"] - random.gauss(0, 0.05)
        day_data["fed_rate"] = 5.25 + max(0, (3.0 - day_data["cpi_yoy"]) * 0.5)
        day_data["prev_fed_rate"] = day_data["fed_rate"]  # same-day for simple sim

        market_days.append(day_data)

        # Update for next day (random walk)
        prev = dict(current)
        spx_return = random.gauss(0.0003, 0.01)
        current["spx"] = int(current["spx"] * (1 + spx_return))
        current["vix"] = max(8, min(50, current["vix"] - spx_return * 100 + random.gauss(0, 0.5)))
        current["dxy"] = current["dxy"] * (1 + random.gauss(0, 0.003))
        current["us10y"] = max(0.5, current["us10y"] + random.gauss(0, 0.03))
        current["us2y"] = max(0.5, current["us2y"] + random.gauss(0, 0.03))
        current["hyg"] = current["hyg"] * (1 + spx_return * 0.5 + random.gauss(0, 0.002))
        current["gold"] = current["gold"] * (1 - 0.5 * (current["us10y"] - 3.5) / 100 + random.gauss(0, 0.005))
        current["copper"] = current["copper"] * (1 + spx_return * 0.7 + random.gauss(0, 0.005))

        day_count += 1

    logger.info("Generated %d trading days of market data (seed=%d)", len(market_days), SEED)
    return market_days


# ── MacroSnapshot Builder ─────────────────────────────────────────────────
# These are static utility methods copied from DailyRunner.
# They are pure data transformation — NO agent logic modification.

BEARISH_INDICATORS = {"vix", "dxy", "us10y", "us2y", "gold", "cpi_yoy", "fed_rate"}

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


def build_macro_snapshot(market_data: dict[str, float],
                         cycle_number: int) -> MacroSnapshot:
    """Build a MacroSnapshot from raw market data dict.

    Pure data transformation — replicates DailyRunner._build_snapshot.
    """
    from src.schemas.signal import (
        MacroSignalSchema, SignalDirection, SignalStrength, SignalEvidence,
    )

    # Regime inference
    monetary = _infer_monetary(market_data)
    growth = _infer_growth(market_data)
    inflation = _infer_inflation(market_data)
    volatility = _infer_volatility(market_data)

    regime = RegimeSnapshot(
        monetary_policy=monetary,
        growth=growth,
        inflation=inflation,
        volatility=volatility,
        fiscal_stance="neutral",
    )

    # Market snapshot
    market = MarketSnapshot(indicators=market_data)

    # Signals
    signals = []
    for key, value in market_data.items():
        if key.startswith("prev_"):
            continue
        prev_key = f"prev_{key}"
        prev_value = market_data.get(prev_key, value)

        if not prev_value or prev_value == 0 or value == 0:
            continue

        change = (value - prev_value) / abs(prev_value)

        if change > 0.01:
            direction = (SignalDirection.BEARISH if key in BEARISH_INDICATORS
                         else SignalDirection.BULLISH)
        elif change < -0.01:
            direction = (SignalDirection.BULLISH if key in BEARISH_INDICATORS
                         else SignalDirection.BEARISH)
        else:
            direction = SignalDirection.NEUTRAL

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

    return MacroSnapshot(
        cycle_id=f"cycle-{cycle_number:04d}",
        regime=regime,
        market=market,
        signals=signals,
    )


def _infer_monetary(data: dict[str, float]) -> str:
    fed_rate = data.get("fed_rate", 0)
    prev_fed = data.get("prev_fed_rate", 0)
    us2y = data.get("us2y", 0)
    us10y = data.get("us10y", 0)

    if prev_fed and fed_rate and fed_rate < prev_fed:
        return "easing"
    if prev_fed and fed_rate and fed_rate > prev_fed:
        return "tightening"
    if us2y and us10y and us2y > us10y:
        return "tightening"
    return "neutral"


def _infer_growth(data: dict[str, float]) -> str:
    spx = data.get("spx", 0)
    prev_spx = data.get("prev_spx", 0)
    copper = data.get("copper", 0)
    prev_copper = data.get("prev_copper", 0)

    gs = 0
    if spx and prev_spx and spx > prev_spx * 1.02:
        gs += 1
    elif spx and prev_spx and spx < prev_spx * 0.98:
        gs -= 1
    if copper and prev_copper and copper > prev_copper * 1.02:
        gs += 1
    elif copper and prev_copper and copper < prev_copper * 0.98:
        gs -= 1

    if gs >= 2:
        return "accelerating"
    if gs <= -2:
        return "decelerating"
    return "stable"


def _infer_inflation(data: dict[str, float]) -> str:
    cpi = data.get("cpi_yoy", 0)
    prev_cpi = data.get("prev_cpi_yoy", 0)
    gold = data.get("gold", 0)
    prev_gold = data.get("prev_gold", 0)

    result = "stable"
    if cpi and prev_cpi:
        if cpi > prev_cpi * 1.05:
            result = "rising"
        elif cpi < prev_cpi * 0.95:
            result = "falling"
    if gold and prev_gold and gold > prev_gold * 1.05 and result == "stable":
        result = "rising"
    return result


def _infer_volatility(data: dict[str, float]) -> str:
    vix = data.get("vix", 15)
    if vix > 30:
        return "high"
    if vix > 20:
        return "elevated"
    if vix < 12:
        return "low"
    return "moderate"


# ── Main Baseline Runner ──────────────────────────────────────────────────
class BaselineRunner:
    """Runs the 100-cycle Phase 1 baseline experiment.

    Follows Agent First Principle:
        - SnapshotManager injected via existing constructor parameter
        - BeliefAdapter bridges schema gap (in runner, not Agent)
        - Zero modification to src/ files
    """

    def __init__(self, memory_path: str, belief_path: str):
        self.memory_path = memory_path
        self.belief_path = belief_path
        self.engine: ResearchCycleEngine | None = None
        self.snapshot_mgr: SnapshotManager | None = None
        self.belief_adapter: BeliefAdapter | None = None
        self.results: list[CycleResult] = []
        self.market_data: list[dict[str, float]] = []
        self.cycle_timings: list[float] = []

    def run(self) -> dict:
        """Execute the full 100-cycle baseline experiment."""
        import time

        logger.info("=" * 70)
        logger.info("PHASE 1 BASELINE: %d Cycles | Seed=%d", TOTAL_CYCLES, SEED)
        logger.info("=" * 70)

        # ── Step 1: Generate market data ─────────────────────────
        logger.info("Generating %d days of synthetic market data...", TOTAL_CYCLES)
        self.market_data = generate_market_data(TOTAL_CYCLES)
        logger.info("Market data ready: %d days", len(self.market_data))

        # ── Step 2: Create engine ─────────────────────────────────
        logger.info("Initializing ResearchCycleEngine...")
        self.engine = ResearchCycleEngine(memory_path=self.memory_path)

        # ── Step 3: Run cycle 1 (no snapshot yet, initializes evolution) ──
        logger.info("--- Cycle 1/100 (cold start, initializing evolution pipeline) ---")
        t0 = time.time()
        snapshot1 = build_macro_snapshot(self.market_data[0], 1)
        result_1 = self.engine.run_cycle(macro_snapshot=snapshot1)
        elapsed = time.time() - t0
        self.results.append(result_1)
        self.cycle_timings.append(elapsed)
        logger.info("Cycle 1 completed in %.1fs — Status: %s", elapsed, result_1.status)

        # ── Step 4: Wire SnapshotManager ──────────────────────────
        # After cycle 1, evolution pipeline is initialized.
        # Now inject SnapshotManager so cycles 2-100 auto-export.
        # ALSO backfill cycle 1 snapshot IMMEDIATELY (before further cycles run).
        if self.engine._evolution_pipeline and self.engine._evolution_pipeline is not False:
            # Create BeliefAdapter from belief_manager
            belief_manager = getattr(
                self.engine._evolution_pipeline, "belief_manager", None
            )
            belief_store = BeliefMemoryStore(file_path=str(self.belief_path))
            self.belief_adapter = BeliefAdapter(
                belief_manager=belief_manager,
                persistence=belief_store,
            )

            self.snapshot_mgr = SnapshotManager(
                evolution_pipeline=self.engine._evolution_pipeline,
                research_memory=self.engine.memory,
                belief_store=self.belief_adapter,
                root_dir=SNAPSHOT_DIR,
                seed=SEED,
            )
            self.engine.snapshot_manager = self.snapshot_mgr
            logger.info("SnapshotManager wired: capturing cycles 2-%d automatically", TOTAL_CYCLES)

            # Backfill cycle 1 snapshot NOW (not after all cycles)
            self.snapshot_mgr.capture(cycle_number=1, cycle_result=result_1)
            logger.info("Cycle 1 snapshot backfilled")
        else:
            logger.warning("Evolution pipeline unavailable — snapshots will be empty")

        # ── Step 5: Run cycles 2-100 (auto-snapshot) ─────────────
        for i in range(1, TOTAL_CYCLES):
            cycle_num = i + 1
            t0 = time.time()
            snapshot = build_macro_snapshot(self.market_data[i], cycle_num)

            # Gather "previous outcomes" by simulating evaluation against next day
            previous_outcomes = self._build_synthetic_outcome(i, cycle_num)

            result = self.engine.run_cycle(
                macro_snapshot=snapshot,
                previous_outcomes=previous_outcomes,
            )
            elapsed = time.time() - t0
            self.results.append(result)
            self.cycle_timings.append(elapsed)

            logger.info(
                "Cycle %3d/100 | %5.1fs | %s | Thesis: %s",
                cycle_num,
                elapsed,
                result.status,
                result.thesis.title[:60] if result.thesis else "N/A",
            )

        # ── Step 6: Export run manifest ───────────────────────────
        if self.snapshot_mgr:
            manifest_path = self.snapshot_mgr.export_run_manifest()
            logger.info("Run manifest: %s", manifest_path)

        # ── Step 8: Summary ───────────────────────────────────────
        summary = self._build_summary()
        summary_path = BASELINE_DIR / "baseline_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
        logger.info("Summary saved: %s", summary_path)

        return summary

    def _build_synthetic_outcome(self, day_index: int,
                                  cycle_num: int) -> dict | None:
        """Simulate previous cycle outcome evaluation.

        Uses next day's actual market data to determine if previous thesis
        was directionally correct. This simulates what the scheduler would
        do with real data — but using synthetic data's "next day" values.
        """
        if day_index < 1 or not self.engine or not self.engine._previous_thesis:
            return None

        prev_thesis = self.engine._previous_thesis
        thesis_id = prev_thesis.thesis_id

        # Compare previous day's market with current day's
        prev_data = self.market_data[day_index - 1]
        curr_data = self.market_data[day_index]

        # Simple heuristic: SPX direction as "outcome"
        spx_change = (curr_data["spx"] - prev_data["spx"]) / prev_data["spx"]

        direction = "UP" if spx_change > 0.002 else "DOWN" if spx_change < -0.002 else "FLAT"

        actual_data = {
            "spx": curr_data["spx"],
            "vix": curr_data["vix"],
            "dxy": curr_data["dxy"],
            "us10y": curr_data["us10y"],
        }

        notes = f"Market {direction} ({spx_change:+.2%}) — synthetic evaluation"

        return {thesis_id: (actual_data, notes)}

    def _build_summary(self) -> dict:
        """Build the Phase 1 baseline experiment summary."""
        completed = [r for r in self.results if r.status == "completed"]
        failed = [r for r in self.results if r.status != "completed"]

        avg_time = (
            sum(self.cycle_timings) / len(self.cycle_timings)
            if self.cycle_timings else 0
        )

        framework_trajectory = []
        principle_trajectory = []
        for r in self.results:
            ev = getattr(r, "evolution_result", None) or {}
            fw = getattr(r, "framework_selection", None)
            framework_trajectory.append(
                fw.top_framework_id if fw and hasattr(fw, "top_framework_id") else "none"
            )
            principle_trajectory.append(
                ev.get("principles_created", 0) if ev else 0
            )

        snapshot_count = 0
        if SNAPSHOT_DIR.exists():
            snapshot_count = len([
                d for d in SNAPSHOT_DIR.iterdir()
                if d.is_dir() and d.name.startswith("day_")
            ])

        return {
            "experiment": "Phase 1 Baseline",
            "seed": SEED,
            "total_cycles": TOTAL_CYCLES,
            "completed": len(completed),
            "failed": len(failed),
            "snapshots_generated": snapshot_count,
            "avg_cycle_time_sec": round(avg_time, 2),
            "total_time_sec": round(sum(self.cycle_timings), 2),
            "first_framework_use": framework_trajectory.index(
                next((f for f in framework_trajectory if f != "none"), "none")
            ) if any(f != "none" for f in framework_trajectory) else -1,
            "total_principles_created": sum(principle_trajectory),
            "framework_trajectory_length": len(set(framework_trajectory)),
            "snapshot_dir": str(SNAPSHOT_DIR),
            "data_dir": str(BASELINE_DIR),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }


# ── CLI Entry Point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'='*70}")
    print(f"  Phase 1 Baseline: {TOTAL_CYCLES}-Cycle Experiment")
    print(f"  Seed: {SEED}")
    print(f"  Project: {PROJECT_ROOT}")
    print(f"{'='*70}\n")

    memory_path, belief_path = setup_clean_environment()
    print(f"Data dir:     {BASELINE_DIR}")
    print(f"Snapshot dir: {SNAPSHOT_DIR}")
    print()

    runner = BaselineRunner(
        memory_path=str(memory_path),
        belief_path=str(belief_path),
    )
    summary = runner.run()

    print(f"\n{'='*70}")
    print(f"  BASELINE COMPLETE")
    print(f"{'='*70}")
    print(f"  Cycles:         {summary['completed']}/{summary['total_cycles']} completed")
    print(f"  Snapshots:      {summary['snapshots_generated']}")
    print(f"  Avg time/cycle: {summary['avg_cycle_time_sec']:.1f}s")
    print(f"  Total time:     {summary['total_time_sec']:.1f}s")
    print(f"  Principles:     {summary['total_principles_created']} created")
    print(f"  Framework uses: {summary['framework_trajectory_length']} unique")
    print(f"{'='*70}")
