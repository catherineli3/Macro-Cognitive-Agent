"""Milestone E validation script."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
from collections import namedtuple
from pathlib import Path

tmpdir = tempfile.gettempdir()

# ── Module Import ──────────────────────────────────────
from src.runtime import (
    DailyRunner,
    OutcomeScheduler,
    PaperTrader,
    PredictionRegistry,
    ReportGenerator,
)

print("[PASS] All runtime modules imported")

# ── Prediction Registry ──────────────────────────────
tmp_db = os.path.join(tmpdir, "test_preds_e.db")
reg = PredictionRegistry(db_path=tmp_db)
s = reg.stats()
assert s["total"] == 0
print(f"[PASS] PredictionRegistry init: {s}")

# Register test predictions
from src.schemas.research_thesis import ResearchThesis

Pred = namedtuple(
    "Pred", ["prediction_id", "direction", "asset", "confidence", "horizon", "transmission_channel"]
)
thesis = ResearchThesis(
    title="Test E",
    core_belief="X causes Y",
    transmission_chain=["A", "B"],
    evidence=["E1", "E2"],
    invalidation_conditions=["C1"],
    confidence=0.65,
)
preds = [Pred(f"p-{i}", "UP", "spx", 0.7, 30, "liquidity") for i in range(3)]
count = reg.register_predictions(thesis, preds)
assert count == 3
s2 = reg.stats()
assert s2["total"] == 3 and s2["pending"] == 3
print(f"[PASS] Registered {count} predictions")

# Mark outcomes
reg.mark_outcome("p-0", success=True, actual_value=5300.0)
reg.mark_outcome("p-1", success=False, actual_value=4900.0)
s3 = reg.stats()
assert s3["evaluated"] == 2
hit_rate = s3["hit_rate"]
print(f"[PASS] Hit rate after marking: {hit_rate:.1%}")
reg.close()
os.remove(tmp_db)

# ── Outcome Scheduler ─────────────────────────────────
tmp_db = os.path.join(tmpdir, "test_sched.db")
reg2 = PredictionRegistry(db_path=tmp_db)
sched = OutcomeScheduler(registry=reg2)
result = sched.run(market_data={"spx": 5200, "prev_spx": 5100})
assert result.predictions_due == 0
print(f"[PASS] OutcomeScheduler: 0 due -> {result.summary().splitlines()[0]}")
reg2.close()
os.remove(tmp_db)

# ── Report Generator ──────────────────────────────────
from src.research.evolution.regime_gate import RegimeSnapshot
from src.research_cycle.cycle_engine import CycleResult
from src.schemas.macro_snapshot import MacroSnapshot, MarketSnapshot

gen = ReportGenerator(output_dir=os.path.join(tmpdir, "test_reports"))
cr = CycleResult(
    cycle_id="test-1",
    cycle_number=1,
    status="completed",
    macro_snapshot=MacroSnapshot(
        regime=RegimeSnapshot(monetary_policy="easing"),
        market=MarketSnapshot(indicators={"spx": 5200, "vix": 15, "dxy": 104}),
    ),
    thesis=thesis,
)
cr.framework_selection = type(
    "FWS",
    (),
    {
        "top_framework_id": "liquidity_expansion",
        "best_weight": 0.72,
        "ranked": [],
    },
)()
report_path = gen.generate(cr, date_str="2026-07-18")
assert os.path.exists(report_path)
print("[PASS] ReportGenerator: saved to report")
os.remove(report_path)

# ── Daily Runner (2-day test) ─────────────────────────
runner = DailyRunner(
    memory_path=os.path.join(tmpdir, "test_dr_mem.json"),
    registry_path=os.path.join(tmpdir, "test_dr_preds.db"),
    report_dir=os.path.join(tmpdir, "test_dr_reports"),
)

result = runner.run_today(
    macro_data={
        "spx": 5200,
        "prev_spx": 5100,
        "vix": 15,
        "prev_vix": 18,
        "dxy": 104,
        "prev_dxy": 103,
        "us10y": 4.2,
        "prev_us10y": 4.0,
        "us2y": 3.8,
        "prev_us2y": 3.6,
    },
    date_str="2026-07-18",
)
assert result.is_success, f"First day failed: {result.error}"
print(f"[PASS] Day 1: {result.status.upper()} — {result.predictions_registered} preds registered")
t = result.cycle_result.thesis
print(f"       Thesis: {t.title[:60]}...")
print(f"       Confidence: {t.confidence:.0%}")
print(f"       Evidence: {len(t.evidence)} items")
print(f"       Invalidation: {len(t.invalidation_conditions)} conditions")

# Run day 2
result2 = runner.run_today(
    macro_data={
        "spx": 5250,
        "prev_spx": 5200,
        "vix": 14,
        "prev_vix": 15,
        "dxy": 103,
        "prev_dxy": 104,
        "us10y": 4.1,
        "prev_us10y": 4.2,
        "us2y": 3.7,
        "prev_us2y": 3.8,
    },
    date_str="2026-07-19",
)
assert result2.is_success, f"Day 2 failed: {result2.error}"
print(f"[PASS] Day 2: {result2.status.upper()} — {result2.predictions_registered} preds")

print(f'[PASS] Registry total: {runner.registry.stats()["total"]}')

runner.close()

# Clean up test files
for f in [
    os.path.join(tmpdir, "test_dr_mem.json"),
    os.path.join(tmpdir, "test_dr_preds.db"),
    os.path.join(tmpdir, "test_dr_reports", "2026-07-18.md"),
    os.path.join(tmpdir, "test_dr_reports", "2026-07-19.md"),
]:
    try:
        os.remove(f)
    except OSError:
        pass

# ── Paper Trader (4-day synthetic test) ────────────────
print()
print("--- Paper Trader: 4-day synthetic replay ---")
trader = PaperTrader(output_dir=os.path.join(tmpdir, "test_replay"))
days = PaperTrader.generate_synthetic_days("2026-07-15", "2026-07-18")
print(f"[PASS] Generated {len(days)} synthetic trading days")

replay_result = trader.replay(days)
s = replay_result.stats
print(f"[PASS] Replay: {s.completed_cycles}/{s.total_days} cycles completed")
print(f"       Hit rate: {s.hit_rate:.1%} ({s.predictions_correct}/{s.predictions_evaluated})")
print(f"       Principles created: {s.principles_created}")
assert s.total_days > 0 and s.completed_cycles > 0
print("[PASS] PaperTrader replay successful")

# Verify output files
output_dir = Path(trader.output_dir)
assert (output_dir / "summary.json").exists()
assert (output_dir / "predictions.csv").exists()
assert (output_dir / "daily_summary.csv").exists()
assert (output_dir / "growth_report.md").exists()
print("[PASS] All replay output files created")

print()
print("=" * 60)
print("ALL MILESTONE E TESTS PASSED")
print("=" * 60)
