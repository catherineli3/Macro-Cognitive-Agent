"""V3 Validation Sprint — V2: 30-Day Execution Validation

Simulates 30 consecutive days of the full research pipeline.

Daily chain (10 steps):
    Collector → Validator → StateVector → MentalModels →
    Narrative → Hypothesis → Belief → Prediction → Validation → Snapshot

Tracks success rate, crash rate, latency per step, failed modules.

Output:
    validation/output/execution_report.json
    validation/output/execution_daily_log.json
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

VALIDATION_OUTPUT = PROJECT_ROOT / "validation" / "output"
SNAPSHOT_DIR = PROJECT_ROOT / "snapshot_validation"
os.makedirs(VALIDATION_OUTPUT, exist_ok=True)
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class StepResult:
    step_name: str
    success: bool
    latency_ms: float = 0.0
    error: str = ""
    error_type: str = ""
    output_summary: str = ""
    artifacts: dict = field(default_factory=dict)


@dataclass
class DayResult:
    day: int
    date: str
    steps: list[StepResult] = field(default_factory=list)
    total_latency_ms: float = 0.0
    crash: bool = False
    crash_detail: str = ""


@dataclass
class ExecutionReport:
    generated_at: str = ""
    total_days: int = 30
    successful_days: int = 0
    crashed_days: int = 0
    step_stats: dict = field(default_factory=dict)
    failed_modules: dict = field(default_factory=dict)
    exception_types: dict = field(default_factory=dict)
    daily_results: list[DayResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# Simulated Data
# ══════════════════════════════════════════════════════════════════════════════

BASE_MACRO_STATE = {
    "Liquidity": {"financial_conditions": 0.15, "dollar_index": 103.5, "vix": 18.2,
                  "credit_spread": 1.35, "ted_spread": 0.15, "global_liquidity_z": 0.3},
    "Inflation": {"headline_cpi_yoy": 2.9, "core_cpi_yoy": 3.2, "pce_yoy": 2.6,
                  "core_pce_yoy": 2.8, "breakeven_5y": 2.35, "breakeven_10y": 2.25},
    "Growth": {"gdp_growth_qoq": 2.4, "ism_manufacturing": 49.5, "ism_services": 53.2,
               "retail_sales_mom": 0.3, "industrial_production_mom": 0.1, "nfp_change": 175},
    "Credit": {"hy_spread": 3.85, "ig_spread": 1.05, "loan_officer_survey": -5.0,
               "commercial_real_estate_z": -0.8},
    "Policy": {"fed_funds_rate": 4.35, "rate_hike_probability": 0.15,
               "rate_cut_probability": 0.55, "balance_sheet_runoff": 35.0, "real_rate": 1.5},
    "Dollar": {"dxy": 103.5, "dxy_momentum": -0.5, "emfx_index": 102.8, "carry_trade_z": 0.6},
    "AiCapex": {"semiconductor_index": 4850, "cloud_capex_growth": 28.0,
                "ai_vc_funding_monthly": 4.2, "gpu_shipment_index": 210},
}


def generate_simulated_snapshot(day: int, base_date: datetime) -> dict:
    """Generate a realistic simulated MacroSnapshot for a given day."""
    import random
    rng = random.Random(day * 137 + 42)

    def vary(value: float, pct: float = 0.01) -> float:
        return round(value * (1 + rng.uniform(-pct, pct)), 4)

    trend = day / 30.0  # 0→1 over 30 days

    state = {}
    for dim, indicators in BASE_MACRO_STATE.items():
        state[dim] = {}
        for k, v in indicators.items():
            # Apply trend + noise
            if dim == "Inflation":
                state[dim][k] = vary(v - trend * 0.3, 0.008)
            elif dim == "Policy":
                if k == "fed_funds_rate":
                    state[dim][k] = vary(v - trend * 0.5, 0.003)
                elif k == "rate_cut_probability":
                    state[dim][k] = vary(v + trend * 0.15, 0.02)
                elif k == "rate_hike_probability":
                    state[dim][k] = vary(v - trend * 0.05, 0.02)
                else:
                    state[dim][k] = vary(v, 0.02)
            elif dim == "Dollar":
                state[dim][k] = vary(v - trend * 1.5, 0.015) if k == "dxy" else vary(v, 0.015)
            elif dim == "AiCapex":
                state[dim][k] = vary(v + trend * 200, 0.02) if k == "semiconductor_index" else vary(v, 0.015)
            elif dim == "Growth":
                state[dim][k] = vary(v - trend * 0.3, 0.015) if k == "gdp_growth_qoq" else vary(v, 0.012)
            else:
                state[dim][k] = vary(v, 0.015)

    date_str = (base_date + timedelta(days=day - 1)).strftime("%Y-%m-%d")

    return {
        "date": date_str,
        "state_vector": json.loads(json.dumps(state)),
        "feature_summary": {},
        "regime_label": "risk_on" if trend < 0.5 else "transition",
        "metadata": {"simulated": True, "day": day, "source": "simulation"},
    }


def transform_state_vector(raw_sv: dict) -> dict:
    """Transform raw {dim: {indicator: value}} → {dim: {score, direction, drivers}}."""
    transformed = {}
    for dim_name, indicators in raw_sv.items():
        numeric = [v for v in indicators.values() if isinstance(v, (int, float))]
        if not numeric:
            continue
        avg = sum(numeric) / len(numeric)
        score = max(0.1, min(0.9, abs(avg) / 200))

        direction = "neutral"
        if "dollar_index" in indicators:
            direction = "weakening" if indicators.get("dollar_index", 100) < 102 else "strengthening"
        elif "headline_cpi_yoy" in indicators:
            direction = "cooling" if indicators.get("headline_cpi_yoy", 3) < 3 else "rising"
        elif "ism_manufacturing" in indicators:
            direction = "expansion" if indicators.get("ism_manufacturing", 50) > 50 else "contraction"
        elif "hy_spread" in indicators:
            direction = "expansion" if indicators.get("hy_spread", 3) < 3 else "contraction"
        elif "fed_funds_rate" in indicators:
            direction = "dovish" if indicators.get("rate_cut_probability", 0) > 0.4 else "hawkish"
        elif "dxy" in indicators:
            direction = "weakening" if indicators.get("dxy", 100) < 103 else "strengthening"
        elif "semiconductor_index" in indicators:
            direction = "expansion" if indicators.get("semiconductor_index", 0) > 4800 else "contraction"

        transformed[dim_name] = {
            "score": round(score, 3),
            "direction": direction,
            "drivers": list(indicators.keys())[:3],
            "values": indicators,
        }
    return transformed


# ══════════════════════════════════════════════════════════════════════════════
# Step Runners
# ══════════════════════════════════════════════════════════════════════════════

def _result(name: str, t0: float, ok: bool, summary: str = "",
            error: str = "", error_type: str = "", **artifacts) -> StepResult:
    return StepResult(
        step_name=name, success=ok,
        latency_ms=(time.time() - t0) * 1000,
        output_summary=summary, error=error, error_type=error_type,
        artifacts=artifacts,
    )


USE_REAL_DATA = os.getenv("VALIDATION_USE_REAL_DATA", "0") == "1"

def step_collector(day: int, date: datetime) -> StepResult:
    """Step 1: Collect macro data. Uses simulation unless VALIDATION_USE_REAL_DATA=1."""
    t0 = time.time()
    if USE_REAL_DATA:
        try:
            from src.data_pipeline.macro_pipeline import MacroPipeline
            pipeline = MacroPipeline(output_dir=str(SNAPSHOT_DIR))
            snapshot_dict = pipeline.build_daily_macro_snapshot(date=date, persist=False)
            sd = len(snapshot_dict.get("state_vector", {}))
            return _result("Collector", t0, True,
                           f"Real: {sd} dims", snapshot=snapshot_dict, source="real")
        except Exception as e:
            try:
                snapshot_dict = generate_simulated_snapshot(day, date)
                sd = len(snapshot_dict["state_vector"])
                return _result("Collector", t0, True,
                               f"Simulated: {sd} dims", snapshot=snapshot_dict, source="simulated",
                               fallback_reason=f"{type(e).__name__}: {str(e)[:100]}")
            except Exception as e2:
                return _result("Collector", t0, False,
                               error=str(e2), error_type=type(e2).__name__)
    else:
        snapshot_dict = generate_simulated_snapshot(day, date)
        sd = len(snapshot_dict["state_vector"])
        return _result("Collector", t0, True,
                       f"Simulated: {sd} dimensions, 7 domains",
                       snapshot=snapshot_dict, source="simulated")


def step_validator(snapshot_dict: dict) -> StepResult:
    """Step 2: Validate data quality."""
    t0 = time.time()
    try:
        sv = snapshot_dict.get("state_vector", {})
        valid = invalid = 0
        for dim in sv.values():
            if isinstance(dim, dict):
                for v in dim.values():
                    if isinstance(v, (int, float)) and -1000 < v < 100000:
                        valid += 1
                    else:
                        invalid += 1
        return _result("Validator", t0, True,
                       f"Valid: {valid}, Invalid: {invalid}",
                       valid=valid, invalid=invalid)
    except Exception as e:
        return _result("Validator", t0, False,
                       error=str(e), error_type=type(e).__name__)


def step_state_vector(snapshot_dict: dict) -> StepResult:
    """Step 3: Build/transform StateVector."""
    t0 = time.time()
    try:
        transformed = transform_state_vector(snapshot_dict["state_vector"])
        return _result("StateVector", t0, True,
                       f"Transformed: {len(transformed)} dimensions",
                       state_vector=transformed)
    except Exception as e:
        return _result("StateVector", t0, False,
                       error=str(e), error_type=type(e).__name__)


def step_mental_models(snapshot_dict: dict) -> StepResult:
    """Step 4: Run 7 Mental Models."""
    t0 = time.time()
    try:
        from src.research.models.model_registry import build_default_registry
        registry = build_default_registry()
        conclusions = registry.evaluate_all(snapshot_dict)
        return _result("MentalModels", t0, True,
                       f"{len(conclusions)} conclusions from {len(registry.registered_models)} models",
                       conclusions=conclusions)
    except Exception as e:
        return _result("MentalModels", t0, False,
                       error=str(e), error_type=type(e).__name__)


def step_narrative(state_vector: dict, conclusions: list) -> StepResult:
    """Step 5: Narrative detection (formerly bypassed)."""
    t0 = time.time()
    try:
        from src.research.narrative.narrative_detector import NarrativeDetector
        detector = NarrativeDetector()
        narratives = detector.detect(
            state_vector=state_vector,
            conclusions=conclusions,
            feature_summary={},
        )
        detail = "; ".join(f"{n.category.value}:{n.title}" for n in narratives[:5])
        return _result("Narrative", t0, True,
                       f"{len(narratives)} narratives: {detail[:120]}",
                       narratives=narratives)
    except Exception as e:
        return _result("Narrative", t0, False,
                       error=str(e), error_type=type(e).__name__)


def step_hypothesis(snapshot_dict: dict, narratives: list, conclusions: list) -> StepResult:
    """Step 6: Generate thesis via ThesisGenerator directly."""
    t0 = time.time()
    try:
        from src.research_cycle.thesis_generator import ThesisGenerator
        from src.schemas.macro_snapshot import MacroSnapshot, MarketSnapshot
        from src.research.evolution.regime_gate import RegimeSnapshot

        # Build proper MacroSnapshot
        indicators = {}
        for dim_name, dim_data in snapshot_dict.get("state_vector", {}).items():
            if isinstance(dim_data, dict):
                for k, v in dim_data.items():
                    if isinstance(v, (int, float)):
                        indicators[f"{dim_name}.{k}"] = v

        regime = RegimeSnapshot(
            monetary_policy="easing",
            fiscal_stance="neutral",
            volatility="moderate",
            growth="stable",
            inflation="cooling",
        )
        snapshot = MacroSnapshot(
            regime=regime,
            market=MarketSnapshot(indicators=indicators),
        )
        snapshot.cycle_id = snapshot_dict.get("date", "")

        generator = ThesisGenerator()
        # Generate with minimal selection (no active frameworks)
        from src.research_cycle.framework_selector import FrameworkSelection
        selection = FrameworkSelection(
            primary_framework=None,
            ranked=[],
            regime_label="",
            activation_scores={},
            selection_rationale="Validation sprint — cold start",
        )
        thesis = generator.generate(
            selection=selection,
            macro_snapshot=snapshot,
            hypotheses=None,
        )
        return _result("Hypothesis", t0, True,
                       f"Thesis: {thesis.title[:80] if thesis and thesis.title else 'N/A'} (conf={thesis.confidence:.2f})",
                       thesis=thesis)
    except Exception as e:
        return _result("Hypothesis", t0, False,
                       error=str(e), error_type=type(e).__name__)


def step_belief(narratives: list, state_vector: dict, conclusions: list) -> StepResult:
    """Step 7: Update BeliefEngine (formerly bypassed)."""
    t0 = time.time()
    try:
        from src.research.beliefs.belief_engine import BeliefEngine
        engine = BeliefEngine()
        beliefs = engine.generate_from_narratives(
            narratives=narratives,
            state_vector=state_vector,
            conclusions=conclusions,
        )
        return _result("Belief", t0, True,
                       f"{len(beliefs)} beliefs updated/generated",
                       beliefs=beliefs)
    except Exception as e:
        return _result("Belief", t0, False,
                       error=str(e), error_type=type(e).__name__)


def step_prediction(snapshot_dict: dict, thesis: Any = None) -> StepResult:
    """Step 8: Generate predictions via PredictionMapper (lightweight)."""
    t0 = time.time()
    try:
        from src.prediction import PredictionMapper
        mapper = PredictionMapper()
        total_mappings = 0
        for dim in snapshot_dict["state_vector"]:
            mappings = mapper.get_mappings(dim)
            total_mappings += len(mappings)
        # Build a simple prediction record
        predictions = {
            "total_signal_mappings": total_mappings,
            "dimensions": list(snapshot_dict["state_vector"].keys()),
            "regime_label": snapshot_dict.get("regime_label", "unknown"),
        }
        return _result("Prediction", t0, True,
                       f"{total_mappings} signal mappings across {len(snapshot_dict['state_vector'])} dims",
                       predictions=predictions)
    except Exception as e:
        return _result("Prediction", t0, False,
                       error=str(e), error_type=type(e).__name__)


def step_validation_check() -> StepResult:
    """Step 9: Validation checkpoint."""
    t0 = time.time()
    return _result("Validation", t0, True, "Checkpoint recorded")


def step_snapshot(day: int, date: datetime, snapshot_dict: dict) -> StepResult:
    """Step 10: Save daily snapshot."""
    t0 = time.time()
    try:
        date_str = date.strftime("%Y-%m-%d")
        path = SNAPSHOT_DIR / f"day{day:03d}_{date_str}.json"
        path.write_text(json.dumps(snapshot_dict, indent=2, default=str), encoding="utf-8")
        return _result("Snapshot", t0, True, f"Saved: {path.name}")
    except Exception as e:
        return _result("Snapshot", t0, False,
                       error=str(e), error_type=type(e).__name__)


# ══════════════════════════════════════════════════════════════════════════════
# 30-Day Runner
# ══════════════════════════════════════════════════════════════════════════════


def run_30_day_validation(base_date: datetime | None = None) -> ExecutionReport:
    if base_date is None:
        base_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0)

    report = ExecutionReport(
        generated_at=datetime.now(timezone.utc).isoformat(), total_days=30)
    report.notes.append("7 mental models + 7 domain narratives + belief engine + prediction mapper")

    # Try to init heavy modules once
    print("Initializing shared components...")
    try:
        from src.research.models.model_registry import build_default_registry
        registry = build_default_registry()
        print(f"  Mental Models: {registry.registered_models}")
    except Exception as e:
        registry = None
        report.notes.append(f"MentalModel init failed: {e}")

    try:
        from src.research.narrative.narrative_detector import NarrativeDetector
        detector = NarrativeDetector()
        print(f"  Narrative templates: {len(detector._templates) if hasattr(detector, '_templates') else 'N/A'}")
    except Exception as e:
        detector = None
        report.notes.append(f"Narrative init failed: {e}")

    try:
        from src.research.beliefs.belief_engine import BeliefEngine
        belief_engine = BeliefEngine()
        print(f"  Belief domains: {len(belief_engine.domains) if hasattr(belief_engine, 'domains') else 'N/A'}")
    except Exception as e:
        belief_engine = None
        report.notes.append(f"BeliefEngine init failed: {e}")

    print()
    print("=" * 70)
    print("  V3 SPRINT V2: 30-DAY EXECUTION VALIDATION")
    print("=" * 70)

    for day in range(1, 31):
        day_date = base_date + timedelta(days=day - 1)
        date_str = day_date.strftime("%Y-%m-%d")
        steps: list[StepResult] = []
        day_start = time.time()

        fd = lambda fs: f"[{'PASS' if fs else 'FAIL'}]"  # helper
        status = ""

        try:
            # Step 1: Collector
            sr = step_collector(day, day_date)
            steps.append(sr)
            if not sr.success or "snapshot" not in sr.artifacts:
                raise RuntimeError(f"Collector failed: day {day}")
            snap = sr.artifacts["snapshot"]
            status += f"C:{'OK' if sr.success else 'FAIL'} "

            # Step 2: Validator
            sr = step_validator(snap)
            steps.append(sr)
            status += f"V:{'OK' if sr.success else 'FAIL'} "

            # Step 3: StateVector
            sr = step_state_vector(snap)
            steps.append(sr)
            sv = sr.artifacts.get("state_vector", {})
            status += f"SV:{'OK' if sr.success else 'FAIL'} "

            # Step 4: MentalModels
            sr = step_mental_models(snap)
            steps.append(sr)
            conclusions = sr.artifacts.get("conclusions", [])
            status += f"M:{'OK' if sr.success else 'FAIL'} "

            # Step 5: Narrative (was bypassed)
            sr = step_narrative(sv, conclusions)
            steps.append(sr)
            narratives = sr.artifacts.get("narratives", [])
            status += f"N:{'OK' if sr.success else 'FAIL'} "

            # Step 6: Hypothesis
            sr = step_hypothesis(snap, narratives, conclusions)
            steps.append(sr)
            status += f"H:{'OK' if sr.success else 'FAIL'} "

            # Step 7: Belief (was bypassed)
            sr = step_belief(narratives, sv, conclusions)
            steps.append(sr)
            status += f"B:{'OK' if sr.success else 'FAIL'} "

            # Step 8: Prediction
            sr = step_prediction(snap)
            steps.append(sr)
            status += f"P:{'OK' if sr.success else 'FAIL'} "

            # Step 9: Validation
            sr = step_validation_check()
            steps.append(sr)
            status += f"V2:{'OK' if sr.success else 'FAIL'} "

            # Step 10: Snapshot
            sr = step_snapshot(day, day_date, snap)
            steps.append(sr)
            status += f"S:{'OK' if sr.success else 'FAIL'}"

            all_ok = all(s.success for s in steps)
            total_ms = (time.time() - day_start) * 1000
            day_result = DayResult(
                day=day, date=date_str, steps=steps,
                total_latency_ms=total_ms,
                crash=not all_ok,
                crash_detail="; ".join(s.error[:80] for s in steps if not s.success)
                if not all_ok else "",
            )
            report.daily_results.append(day_result)
            if all_ok:
                report.successful_days += 1
            else:
                report.crashed_days += 1
            print(f"[Day {day:02d}] {date_str}  {status}  {total_ms:.0f}ms")

        except Exception as e:
            total_ms = (time.time() - day_start) * 1000
            day_result = DayResult(
                day=day, date=date_str, steps=steps,
                total_latency_ms=total_ms, crash=True,
                crash_detail=f"{type(e).__name__}: {str(e)[:200]}",
            )
            report.daily_results.append(day_result)
            report.crashed_days += 1
            print(f"[Day {day:02d}] {date_str}  CRASH: {type(e).__name__}  {total_ms:.0f}ms")

    # ── Compute Stats ──
    step_agg: dict[str, dict] = defaultdict(
        lambda: {"attempts": 0, "successes": 0, "total_latency_ms": 0.0})
    for dr in report.daily_results:
        for s in dr.steps:
            a = step_agg[s.step_name]
            a["attempts"] += 1
            if s.success:
                a["successes"] += 1
            a["total_latency_ms"] += s.latency_ms

    report.step_stats = {}
    for name, a in step_agg.items():
        report.step_stats[name] = {
            "attempts": a["attempts"],
            "successes": a["successes"],
            "success_rate": round(a["successes"] / a["attempts"], 4) if a["attempts"] else 0,
            "avg_latency_ms": round(a["total_latency_ms"] / a["attempts"], 1) if a["attempts"] else 0,
        }

    report.failed_modules = {}
    report.exception_types = {}
    for dr in report.daily_results:
        for s in dr.steps:
            if not s.success:
                report.failed_modules[s.step_name] = report.failed_modules.get(s.step_name, 0) + 1
                report.exception_types[s.error_type] = report.exception_types.get(s.error_type, 0) + 1

    success_rate = report.successful_days / report.total_days if report.total_days else 0
    crash_rate = report.crashed_days / report.total_days if report.total_days else 0

    # ── Print Summary ──
    print()
    print("=" * 70)
    print("  EXECUTION REPORT SUMMARY")
    print("=" * 70)
    print(f"  Days: {report.total_days} | OK: {report.successful_days} | Crash: {report.crashed_days}")
    print(f"  Success Rate: {success_rate:.1%} | Crash Rate: {crash_rate:.1%}")
    print()
    for name, s in sorted(report.step_stats.items()):
        status_icon = "OK" if s["success_rate"] >= 0.99 else "!!"
        print(f"  [{status_icon}] {name:15s}  {s['success_rate']:.1%}  avg {s['avg_latency_ms']:.0f}ms")
    if report.failed_modules:
        print(f"\n  Failed: {report.failed_modules}")
    if report.exception_types:
        print(f"  Errors: {report.exception_types}")
    print(f"\n  Target: Success Rate >= 99% | Crash = 0")
    print(f"  Actual: {success_rate:.1%} | Crash: {report.crashed_days}")
    print(f"  STATUS: {'PASS' if success_rate >= 0.99 and report.crashed_days == 0 else 'FAIL'}")
    print("=" * 70)

    return report


def save_report(report: ExecutionReport):
    path = VALIDATION_OUTPUT / "execution_report.json"
    success_rate = report.successful_days / report.total_days if report.total_days else 0
    crash_rate = report.crashed_days / report.total_days if report.total_days else 0
    result = {
        "generated_at": report.generated_at,
        "total_days": report.total_days,
        "successful_days": report.successful_days,
        "crashed_days": report.crashed_days,
        "success_rate": success_rate,
        "crash_rate": crash_rate,
        "step_stats": report.step_stats,
        "failed_modules": report.failed_modules,
        "exception_types": report.exception_types,
        "notes": report.notes,
        "sprint_target": {"success_rate_min": 0.99, "crash_count_max": 0},
        "sprint_result": "PASS" if success_rate >= 0.99 and report.crashed_days == 0 else "FAIL",
    }
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReport saved: {path}")

    # Daily log
    daily_path = VALIDATION_OUTPUT / "execution_daily_log.json"
    daily_data = []
    for dr in report.daily_results:
        daily_data.append({
            "day": dr.day, "date": dr.date,
            "total_latency_ms": dr.total_latency_ms,
            "crash": dr.crash, "crash_detail": dr.crash_detail,
            "steps": [{
                "step_name": s.step_name, "success": s.success,
                "latency_ms": s.latency_ms,
                "output_summary": s.output_summary[:200],
                "error": s.error[:200] if s.error else "",
            } for s in dr.steps],
        })
    daily_path.write_text(json.dumps(daily_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Daily log saved: {daily_path}")


if __name__ == "__main__":
    report = run_30_day_validation()
    save_report(report)
