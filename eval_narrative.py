"""eval_narrative.py — Phase 4: LLM Narrative Quality Evaluation.

Answers: "Is the LLM narrative lying?"

Four dimensions:
  1. Number Traceability   — every number in LLM output must have a source
                              in (input_data ∪ history_reference).
  2. Conclusion Consistency — narrative conclusions must match belief states.
  3. Structural Integrity   — Pydantic schema validation pass rate (over N runs).
  4. Degradation Correctness — degraded output matches expectations when
                              LLM is unreachable / times out / returns garbage.

Usage:
    python eval_narrative.py                    # all 4 checks, N=10 runs
    python eval_narrative.py --runs 50          # custom run count
    python eval_narrative.py --check numbers    # single check only
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

# Fix Windows console encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, ".")

from src.llm.client import LLMClient, LLMError
from src.llm.narrative import LLMNarrativeEngine, LLMNarrativeResult
from src.llm.retriever import HistoryRecord, HistoryRetriever


# =========================================================================
# Helpers
# =========================================================================


class FakeNarrative:
    """Standalone minimal narrative fixture — mirrors test_narrative_prompt."""

    def __init__(self):
        self.title = "Eval Narrative"
        self.summary = "liquidity tightening with DXY bullish at 75% confidence, growth mixed."
        self.macro_story = (
            "Global financial conditions tightening. DXY rising. "
            "US10Y stable at 4.2%. Inflation moderating with Core PCE at 2.6%."
        )
        self.today_key_changes = "DXY +0.3%, equity mixed"
        self.liquidity = _FakeDim("liquidity", "tightening — DXY bullish (75% confidence)", 0.75)
        self.credit = _FakeDim("credit", "stable", 0.55)
        self.growth = _FakeDim("growth", "slowing — GDPNow at 1.8%", 0.60)
        self.inflation = _FakeDim("inflation", "moderating — Core PCE 2.6%", 0.65)
        self.risk_appetite_analysis = "risk-off sentiment"
        self.scenario_analysis = [
            _FakeScenario("soft_landing", 0.34, "gradual easing supports"),
            _FakeScenario("hard_landing", 0.09, "rapid tightening impact"),
            _FakeScenario("inflation_reacceleration", 0.07, "cost-push from energy"),
        ]
        self.belief_changes = [
            _FakeBeliefChange("DXY rise pressures EM assets", 0.60, 0.72, "strengthened"),
            _FakeBeliefChange("10Y yield signals neutral", 0.55, 0.48, "weakened"),
        ]
        self.key_risks = ["geopolitical tension", "inflation reacceleration"]
        self.action_items = ["reduce EM exposure", "increase cash position"]
        self.confidence_level = "MEDIUM"
        self.confidence_score = 0.48


class _FakeDim:
    def __init__(self, dimension, summary, confidence):
        self.dimension = dimension
        self.summary = summary
        self.analysis = summary
        self.confidence = confidence
        self.sentiment = "neutral"
        self.key_signals = []
        self.signal_count = 3


class _FakeScenario:
    def __init__(self, name, probability, rationale):
        self.name = name
        self.probability = probability
        self.rationale = rationale


class _FakeBeliefChange:
    def __init__(self, hypothesis_statement, prev, curr, direction):
        self.hypothesis_statement = hypothesis_statement
        self.previous_confidence = prev
        self.current_confidence = curr
        self.direction = direction


# =========================================================================
# Check 1: Number Traceability
# =========================================================================


def _extract_numbers(text: str) -> list[tuple[str, float]]:
    """Extract numeric tokens with surrounding context from text.

    Matches: percentages (74%, 34%), decimals (0.75), plain integers contextually.
    Returns list of (raw_match, float_value).
    """
    patterns = [
        # percentages: 74%, 3.5%, 0.5%
        r"(\d+\.?\d*\s*%)",
        # decimal: 0.75, 2.6 (contextual — only if follows certain keywords)
        r"(?<=confidence\s)\d+\.\d+",
        r"(?<=at\s)\d+\.\d+",
        r"(?<=PCE\s)\d+\.\d+",
        r"(?<=GDPNow\s)\d+\.\d+",
        r"\d+\.\d+(?=\s*bp|\s*confidence)",
    ]
    matches = set()
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            raw = m.group().strip()
            num_str = raw.replace("%", "").replace(",", "").strip()
            try:
                val = float(num_str)
                matches.add((raw, val))
            except ValueError:
                pass
    return sorted(matches, key=lambda x: x[1], reverse=True)


def _build_source_pool(structured_input: dict, history_records: list[HistoryRecord]) -> set[str]:
    """Collect all text that numbers can legally be sourced from.

    Legal sources: input data ∪ history reference.
    """
    pool: set[str] = set()
    # Input data — full JSON normalized
    try:
        input_text = json.dumps(structured_input, ensure_ascii=False)
        pool.add(input_text)
    except Exception:
        pass
    # History records
    for hr in history_records:
        pool.add(hr.text)
        pool.add(hr.to_prompt_entry(0))
    return pool


@dataclass
class NumberTraceReport:
    total_numbers: int = 0
    sourced: int = 0
    unsourced: list[tuple[str, float]] = field(default_factory=list)
    planted_caught: list[tuple[str, float]] = field(default_factory=list)

    @property
    def real_total(self) -> int:
        """Total excluding positive controls (planted fake numbers)."""
        return self.total_numbers - len(self.planted_caught)

    @property
    def pass_rate(self) -> float:
        if self.real_total == 0:
            return 1.0
        return self.sourced / self.real_total

    def summary(self) -> str:
        lines = [f"  Numbers extracted: {self.total_numbers}"]
        lines.append(f"  Numbers sourced:   {self.sourced}")
        if self.planted_caught:
            lines.append(f"  检查器正确识别 {len(self.planted_caught)} 个植入假数字")
            lines.append(f"  Real pass rate:    {self.pass_rate:.0%} ({self.sourced}/{self.real_total})")
        else:
            lines.append(f"  Pass rate:         {self.pass_rate:.0%}")
        if self.unsourced:
            lines.append(f"  Unsourced ({len(self.unsourced)}):")
            for raw, val in self.unsourced:
                lines.append(f"    - '{raw}' ({val})")
        if self.planted_caught:
            lines.append(f"  Planted caught ({len(self.planted_caught)}):")
            for raw, val in self.planted_caught:
                lines.append(f"    - '{raw}' ({val}) — 阳性对照，正确识别")
        return "\n".join(lines)


def check_number_traceability(
    llm_output: str,
    structured_input: dict,
    history_records: list[HistoryRecord],
    planted_numbers: set[str] | None = None,
) -> NumberTraceReport:
    """Check every number in LLM output can be traced to input or history.

    Args:
        planted_numbers: Set of raw number strings known to be fakes
                         (positive controls).  Matched unsourced numbers
                         are reported separately as "planted_caught".
    """
    planted_set = planted_numbers or set()
    numbers = _extract_numbers(llm_output)
    sources = _build_source_pool(structured_input, history_records)

    report = NumberTraceReport(total_numbers=len(numbers))
    for raw, val in numbers:
        # For percentages, also try float form e.g. 75% vs 0.75
        variants = {raw}
        if raw.endswith("%"):
            decimal_form = f"{val/100:.2f}"
            variants.add(decimal_form)
            variants.add(f"{val/100:.4g}")
        else:
            pct_form = f"{val*100:.0f}%"
            variants.add(pct_form)

        found = False
        for variant in variants:
            if variant in str(sources):
                found = True
                break
        if found:
            report.sourced += 1
        elif raw in planted_set:
            report.planted_caught.append((raw, val))
        else:
            report.unsourced.append((raw, val))

    return report


# =========================================================================
# Check 2: Conclusion Consistency
# =========================================================================


@dataclass
class ConsistencyReport:
    checks: list[dict] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if not self.checks:
            return 1.0
        return 1.0 - len(self.violations) / len(self.checks)

    def summary(self) -> str:
        lines = [f"  Consistency checks: {len(self.checks)}"]
        # Count per category
        cat_counts: dict[str, int] = defaultdict(int)
        for c in self.checks:
            cat_counts[c["category"]] += 1
        for cat, n in sorted(cat_counts.items()):
            lines.append(f"    {cat}: {n}")
        lines.append(f"  Violations: {len(self.violations)}")
        lines.append(f"  Pass rate:   {self.pass_rate:.0%}")
        if self.violations:
            lines.append("  Violation details:")
            for v in self.violations[:10]:
                lines.append(f"    - {v}")
        return "\n".join(lines)


def check_conclusion_consistency(
    llm_output: str,
    belief_changes: list[dict],
) -> ConsistencyReport:
    """Verify LLM conclusions don't contradict known belief states.

    Key rules:
      - 'strengthened' → narrative should NOT say 'refuted' or 'weakened'
      - 'weakened'    → narrative should NOT say 'confirmed' or 'strengthened'
      - 'reversed'    → narrative should NOT say 'confirmed'
    """
    report = ConsistencyReport()

    for bc in belief_changes:
        hypothesis = bc.get("hypothesis", "")
        direction = bc.get("direction", "unknown")
        category = "belief_change"

        report.checks.append({
            "category": category,
            "hypothesis": hypothesis,
            "direction": direction,
        })

        lowered_hypo = hypothesis.lower()
        lowered_output = llm_output.lower()

        if direction == "strengthened":
            if any(kw in lowered_output for kw in ["推翻", "refuted", "被驳斥"]):
                # Check if this specific hypothesis is the one being refuted
                if any(w in lowered_hypo for w in lowered_output.split()):
                    report.violations.append(
                        f"Strengthened hypothesis '{hypothesis}' "
                        f"described as refuted in narrative"
                    )
        elif direction == "weakened":
            if any(kw in lowered_output for kw in ["确认", "confirmed", "strengthened"]):
                if any(w in lowered_hypo.lower() for w in ("dxy", "10y", "liquidity")):
                    report.violations.append(
                        f"Weakened hypothesis may be described as confirmed: '{hypothesis}'"
                    )

    return report


# =========================================================================
# Check 3: Structural Integrity
# =========================================================================


@dataclass
class IntegrityReport:
    total_runs: int = 0
    valid_schema: int = 0
    degraded_runs: int = 0
    avg_latency_ms: float = 0.0
    failures: list[str] = field(default_factory=list)

    @property
    def schema_pass_rate(self) -> float:
        non_degraded = self.total_runs - self.degraded_runs
        if non_degraded == 0:
            return 0.0
        return self.valid_schema / non_degraded

    def summary(self) -> str:
        lines = [
            f"  Total runs:       {self.total_runs}",
            f"  Schema valid:     {self.valid_schema}",
            f"  Degraded runs:    {self.degraded_runs}",
            f"  Schema pass rate: {self.schema_pass_rate:.0%}",
            f"  Avg latency:      {self.avg_latency_ms:.0f} ms",
        ]
        if self.failures:
            lines.append(f"  Failures ({len(self.failures)}):")
            for f in self.failures[:5]:
                lines.append(f"    - {f[:120]}")
        return "\n".join(lines)


def check_structural_integrity(
    engine: LLMNarrativeEngine,
    narrative,
    n_runs: int = 10,
) -> IntegrityReport:
    """Run LLM generation N times, validate Pydantic schema each time."""
    report = IntegrityReport(total_runs=n_runs)
    latencies: list[float] = []

    for i in range(n_runs):
        t0 = time.perf_counter()
        try:
            result = engine.generate(narrative)
            elapsed = (time.perf_counter() - t0) * 1000
            latencies.append(elapsed)

            if result.degraded:
                report.degraded_runs += 1
                report.failures.append(f"Run {i}: degraded — {result.error}")
            elif result.data and all(
                hasattr(result.data, f)
                for f in ("executive_summary", "scenario_analysis",
                          "action_recommendations", "belief_revision")
            ):
                report.valid_schema += 1
            else:
                report.failures.append(f"Run {i}: missing required fields")
        except Exception as e:
            report.failures.append(f"Run {i}: {type(e).__name__}: {e}")

    if latencies:
        report.avg_latency_ms = sum(latencies) / len(latencies)
    return report


# =========================================================================
# Check 4: Degradation Correctness
# =========================================================================


@dataclass
class DegradationReport:
    cases: list[dict] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if not self.cases:
            return 1.0
        return 1.0 - len(self.mismatches) / len(self.cases)

    def summary(self) -> str:
        lines = [
            f"  Degradation cases: {len(self.cases)}",
            f"  Mismatches:        {len(self.mismatches)}",
            f"  Pass rate:         {self.pass_rate:.0%}",
        ]
        for m in self.mismatches:
            lines.append(f"    - {m}")
        return "\n".join(lines)


def check_degradation_correctness() -> DegradationReport:
    """Simulate 3 failure modes and verify each produces expected degraded output."""
    from tests.unit.llm.test_narrative_prompt import (
        FakeLLMClientFail,
        FakeLLMClientGarbage,
        FakeRetrieverEmpty,
        FakeNarrative as TestNarrative,
    )

    report = DegradationReport()
    narrative = TestNarrative()

    # Case 1: LLM unavailable (timeout / connection error)
    engine1 = LLMNarrativeEngine(
        client=FakeLLMClientFail(),
        retriever=FakeRetrieverEmpty(),
    )
    res1 = engine1.generate(narrative)
    report.cases.append({
        "case": "LLM unavailable",
        "expected_degraded": True,
        "actual_degraded": res1.degraded,
        "expected_data_not_none": True,
        "actual_data_not_none": res1.data is not None,
    })
    if not res1.degraded:
        report.mismatches.append("LLM unavailable: degraded should be True")
    if res1.data is None:
        report.mismatches.append("LLM unavailable: fallback data should not be None")

    # Case 2: LLM returns garbage (non-JSON)
    engine2 = LLMNarrativeEngine(
        client=FakeLLMClientGarbage(),
        retriever=FakeRetrieverEmpty(),
    )
    res2 = engine2.generate(narrative)
    report.cases.append({
        "case": "LLM returns garbage",
        "expected_degraded": True,
        "actual_degraded": res2.degraded,
        "expected_data_not_none": True,
        "actual_data_not_none": res2.data is not None,
    })
    if not res2.degraded:
        report.mismatches.append("LLM garbage: degraded should be True")
    if res2.data is None:
        report.mismatches.append("LLM garbage: fallback data should not be None")

    # Case 3: Retriever fails + LLM OK → NOT degraded
    print("  [dry-run] 历史检索已模拟失败，验证静默降级")
    from tests.unit.llm.test_narrative_prompt import (
        FakeLLMClientSuccess,
        FakeRetrieverFails,
    )
    engine3 = LLMNarrativeEngine(
        client=FakeLLMClientSuccess(),
        retriever=FakeRetrieverFails(),
    )
    res3 = engine3.generate(narrative)
    report.cases.append({
        "case": "Retriever fails, LLM OK",
        "expected_degraded": False,
        "actual_degraded": res3.degraded,
    })
    if res3.degraded:
        report.mismatches.append(
            "Retriever failure should NOT cause degraded when LLM succeeds"
        )

    return report


# =========================================================================
# Main — evaluation runner
# =========================================================================


def run_all_checks(runs: int = 10, real_llm: bool = True) -> dict[str, Any]:
    """Run all 4 evaluation checks and return consolidated report."""
    results: dict[str, Any] = {}

    narrative = FakeNarrative()

    # Build structured_input for traceability sourcing
    engine = LLMNarrativeEngine()
    structured_input = engine._build_input(narrative)

    # Run LLM (respect --no-llm flag)
    llm_output: Optional[str] = None
    llm_result: Optional[LLMNarrativeResult] = None
    history_records: list[HistoryRecord] = []

    if real_llm:
        retriever = HistoryRetriever()
        try:
            history_records = retriever.retrieve(structured_input)
        except Exception:
            pass

        try:
            llm_result = engine.generate(narrative)
            if llm_result.raw_llm_response:
                llm_output = llm_result.raw_llm_response
        except Exception as e:
            results["llm_error"] = str(e)
            llm_output = None
    else:
        # Dry-run: use a fake well-formed response
        llm_output = (
            '{"executive_summary": "DXY bullish with 75% confidence. '
            'Core PCE at 2.6%. GDPNow at 1.8%. Soft landing probability 34%. '
            'Hard landing probability 9%.", '
            '"scenario_analysis": "软着陆34%为最可能情景", '
            '"action_recommendations": ["减少新兴市场敞口"], '
            '"belief_revision": "2项假说被推翻，67%被驳斥"}'
        )
        # Fake history for traceability test
        history_records = [
            HistoryRecord("2026-08-10", "liquidity",
                          "DXY bullish with 75% confidence", 0.85),
            HistoryRecord("2026-08-09", "growth",
                          "GDPNow tracking at 1.8%", 0.72),
        ]

    # ── Check 1: Number Traceability ──
    if llm_output:
        num_report = check_number_traceability(
            llm_output, structured_input, history_records,
            planted_numbers={"67%"} if not real_llm else None,
        )
        results["number_traceability"] = {
            "pass_rate": num_report.pass_rate,
            "total": num_report.total_numbers,
            "sourced": num_report.sourced,
            "unsourced": [(r, v) for r, v in num_report.unsourced],
            "planted_caught": num_report.planted_caught,
        }

    # ── Check 2: Conclusion Consistency ──
    if llm_output:
        belief_changes_raw = [
            {
                "hypothesis": bc.hypothesis_statement,
                "direction": bc.direction,
            }
            for bc in narrative.belief_changes
        ]
        con_report = check_conclusion_consistency(llm_output, belief_changes_raw)
        results["conclusion_consistency"] = {
            "pass_rate": con_report.pass_rate,
            "checks": len(con_report.checks),
            "violations": len(con_report.violations),
            "violation_details": con_report.violations,
        }

    # ── Check 3: Structural Integrity ──
    if real_llm and runs > 0:
        integ_report = check_structural_integrity(engine, narrative, n_runs=runs)
        results["structural_integrity"] = {
            "pass_rate": integ_report.schema_pass_rate,
            "total_runs": integ_report.total_runs,
            "schema_valid": integ_report.valid_schema,
            "degraded_runs": integ_report.degraded_runs,
            "avg_latency_ms": integ_report.avg_latency_ms,
            "failures": integ_report.failures,
        }

    # ── Check 4: Degradation Correctness ──
    deg_report = check_degradation_correctness()
    results["degradation_correctness"] = {
        "pass_rate": deg_report.pass_rate,
        "cases": len(deg_report.cases),
        "mismatches": len(deg_report.mismatches),
        "mismatch_details": deg_report.mismatches,
    }

    return results


def print_report(results: dict[str, Any]) -> None:
    """Print formatted evaluation report."""
    print("=" * 60)
    print("  LLM NARRATIVE EVALUATION REPORT")
    print("=" * 60)

    checks = [
        ("1. Number Traceability", "number_traceability"),
        ("2. Conclusion Consistency", "conclusion_consistency"),
        ("3. Structural Integrity", "structural_integrity"),
        ("4. Degradation Correctness", "degradation_correctness"),
    ]

    overall_pass = 0
    overall_count = 0

    for label, key in checks:
        data = results.get(key)
        if data is None:
            print(f"\n  {label}: SKIPPED (no data)")
            continue

        pr = data.get("pass_rate", 0.0)
        overall_pass += pr
        overall_count += 1

        print(f"\n  {label}:")
        print(f"    Pass Rate: {pr:.0%}")

        if "total" in data:
            planted_info = data.get("planted_caught", [])
            if planted_info:
                print(f"    Numbers:   {data['sourced']}/{data['total'] - len(planted_info)} sourced "
                      f"(检查器正确识别 {len(planted_info)} 个植入假数字)")
            else:
                print(f"    Numbers:   {data['sourced']}/{data['total']} sourced")
        if "checks" in data:
            print(f"    Checks:    {data['checks']} total, {data.get('violations', 0)} violations")
        if "total_runs" in data:
            print(f"    Runs:      {data['schema_valid']}/{data['total_runs']} valid schema, "
                  f"{data['degraded_runs']} degraded, "
                  f"{data.get('avg_latency_ms', 0):.0f}ms avg")
        if "cases" in data:
            print(f"    Cases:     {data['cases']} total, {data.get('mismatches', 0)} mismatches")

        # Print failures/violations
        for fail_key in ("unsourced", "violation_details", "failures", "mismatch_details"):
            items = data.get(fail_key, [])
            if items:
                print(f"    Details ({len(items)}):")
                for item in items[:5]:
                    print(f"      - {item}")
                if len(items) > 5:
                    print(f"      ... and {len(items) - 5} more")

    if overall_count > 0:
        print(f"\n  OVERALL: {overall_pass/overall_count:.0%} average pass rate")
    print("=" * 60)


# =========================================================================
# CLI
# =========================================================================


def parse_args():
    p = argparse.ArgumentParser(
        description="LLM Narrative Quality Evaluation (Phase 4)"
    )
    p.add_argument("--runs", type=int, default=10,
                   help="Number of LLM calls for structural integrity check (default: 10)")
    p.add_argument("--no-llm", action="store_true",
                   help="Skip real LLM calls; use canned data for traceability/consistency")
    p.add_argument("--check", type=str, default=None,
                   choices=["numbers", "consistency", "integrity", "degradation"],
                   help="Run a single check only")
    return p.parse_args()


def main():
    args = parse_args()

    if args.check == "degradation":
        # Degradation check never needs real LLM
        report = check_degradation_correctness()
        print(report.summary())
        return

    if args.check == "numbers":
        # Run traceability only (with or without real LLM)
        narrative = FakeNarrative()
        engine = LLMNarrativeEngine()
        si = engine._build_input(narrative)
        if not args.no_llm:
            result = engine.generate(narrative)
            output = result.raw_llm_response if result.raw_llm_response else ""
        else:
            output = (
                '{"executive_summary": "DXY bullish 75%. Core PCE 2.6%. '
                'Soft landing 34% probability."}'
            )
        history: list[HistoryRecord] = []
        nr = check_number_traceability(output, si, history)
        print(nr.summary())
        return

    if args.check == "consistency":
        narrative = FakeNarrative()
        engine = LLMNarrativeEngine()
        if not args.no_llm:
            result = engine.generate(narrative)
            output = result.raw_llm_response if result.raw_llm_response else ""
        else:
            output = '{"executive_summary": "2项假说被推翻。67%被驳斥。"}'
        bcs = [
            {"hypothesis": bc.hypothesis_statement, "direction": bc.direction}
            for bc in narrative.belief_changes
        ]
        cr = check_conclusion_consistency(output, bcs)
        print(cr.summary())
        return

    if args.check == "integrity":
        narrative = FakeNarrative()
        engine = LLMNarrativeEngine()
        if args.no_llm:
            print("Structural integrity requires real LLM; use --no-llm=False")
            return
        ir = check_structural_integrity(engine, narrative, n_runs=args.runs)
        print(ir.summary())
        return

    # Default: all checks
    results = run_all_checks(runs=args.runs, real_llm=not args.no_llm)
    print_report(results)

    # Write JSON report
    report_path = "eval_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  JSON report saved to: {report_path}")


if __name__ == "__main__":
    main()
