# =============================================================================
# V9 Benchmark Runner — Main integration runner for all V9 validation
# =============================================================================
# Runs the complete V9 validation pipeline:
#   1. Load 100+ historical cases
#   2. Run blind tests with simulated agent
#   3. Score agent understanding (Phase 2)
#   4. Run prediction calibration (Phase 3)
#   5. Run report quality benchmark (Phase 4)
#   6. Generate final capability assessment (Phase 7)
# =============================================================================

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from validation.v9.historical_cases import (
    HistoricalCase,
    CASES,
    build_all_cases,
    get_cases_by_cycle,
    get_cases_by_difficulty,
)
from validation.v9.blind_test import (
    BlindTestRunner,
    BlindTestSuite,
    BlindTestCase,
    v10_agent_research,      # V10: real LLM agent
    simulate_agent_research,  # Backward compat
)
from validation.v9.scoring_engine import (
    MacroUnderstandingScorer,
    BlindTestResult,
    DimensionScore,
)
from validation.v9.prediction_calibration import (
    EnhancedPredictionLedger,
    PredictionRecord,
    ErrorDiagnosis,
    ErrorType,
)
from validation.v9.report_benchmark import (
    ReportBenchmark,
    MemoComparisonResult,
)
from validation.v9.agent_evaluation import (
    AgentEvaluator,
    CapabilityReport,
)


# ══════════════════════════════════════════════════════════════════════
# V9 Benchmark Runner
# ══════════════════════════════════════════════════════════════════════


@dataclass
class V9BenchmarkResult:
    """Aggregate result of the complete V9 benchmark run."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Phase 2: Blind test results
    blind_test_suite: Optional[BlindTestSuite] = None
    blind_test_average: float = 0.0
    blind_test_pass_rate: float = 0.0
    blind_test_dimensions: dict = field(default_factory=dict)

    # Phase 3: Prediction calibration
    calibration_ledger: Optional[EnhancedPredictionLedger] = None
    ece: float = 0.0  # Expected Calibration Error
    hit_rate: float = 0.0

    # Phase 4: Report quality
    report_benchmark_score: float = 0.0
    report_benchmark_results: list = field(default_factory=list)

    # Phase 1: Case coverage
    total_cases: int = 0
    cases_by_cycle: dict = field(default_factory=dict)

    # Meta
    errors: list[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0

    def summary(self) -> str:
        """Generate a one-page benchmark summary report."""
        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║          V9 Benchmark Run — Complete Results                  ║",
            "╚══════════════════════════════════════════════════════════════╝",
            f"  Timestamp: {self.timestamp}",
            f"  Execution Time: {self.execution_time_seconds:.1f}s",
            "",
            "── Phase 1: Case Database ──",
            f"  Total Cases: {self.total_cases}",
        ]
        for cycle, count in sorted(self.cases_by_cycle.items()):
            lines.append(f"    {cycle}: {count}")

        lines.extend([
            "",
            "── Phase 2: Blind Research Test ──",
            f"  Average Score: {self.blind_test_average:.1f}/100",
            f"  Pass Rate (≥70): {self.blind_test_pass_rate:.1%}",
            f"  V9 Target: ≥75 | Status: {'✅' if self.blind_test_average >= 75 else '❌'}",
            "",
            "  Dimension Averages:",
        ])
        for dim, score in self.blind_test_dimensions.items():
            dim_name = dim.replace("_", " ").title()
            lines.append(f"    {dim_name}: {score:.1f}/20")

        lines.extend([
            "",
            "── Phase 3: Prediction Calibration ──",
            f"  ECE: {self.ece:.3f} | V9 Target: <0.15 | Status: {'✅' if self.ece < 0.15 else '❌'}",
            f"  Hit Rate: {self.hit_rate:.1%}",
            "",
            "── Phase 4: Report Quality ──",
            f"  Benchmark Score: {self.report_benchmark_score:.1f}/100",
            f"  V9 Target: ≥85 | Status: {'✅' if self.report_benchmark_score >= 85 else '❌'}",
            "",
            "── V9 Success Summary ──",
            f"  Historical Benchmark ≥75: {self.blind_test_average:.0f}/100 {'✅' if self.blind_test_average >= 75 else '❌'}",
            f"  ECE <0.15: {self.ece:.3f} {'✅' if self.ece < 0.15 else '❌'}",
            f"  Research Memo ≥85: {self.report_benchmark_score:.0f}/100 {'✅' if self.report_benchmark_score >= 85 else '❌'}",
        ])

        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
# Main Runner
# ══════════════════════════════════════════════════════════════════════


class V9BenchmarkRunner:
    """Main V9 benchmark runner. Runs all phases and aggregates results.

    Usage:
        runner = V9BenchmarkRunner()
        result = runner.run_full_benchmark()
        print(result.summary())
    """

    def __init__(self, agent_fn=None, output_dir: Optional[Path] = None):
        self.agent_fn = agent_fn or v10_agent_research  # V10: default to real LLM agent
        self.output_dir = output_dir or Path("validation/v9/runs")
        self.scorer = MacroUnderstandingScorer()
        self.blind_runner = BlindTestRunner(agent_fn=self.agent_fn)
        self.ledger = EnhancedPredictionLedger()
        self.report_benchmark = ReportBenchmark()
        self.evaluator = AgentEvaluator()

    def run_full_benchmark(
        self,
        sample_size: Optional[int] = None,
        cycles: Optional[list[str]] = None,
        skip_calibration: bool = False,
        skip_reports: bool = False,
    ) -> V9BenchmarkResult:
        """Run the complete V9 benchmark pipeline.

        Args:
            sample_size: If set, sample N cases randomly (for quick runs).
                         If None, run ALL 102 cases.
            cycles: If set, only run cases from specified cycles.
            skip_calibration: Skip Phase 3 (prediction calibration).
            skip_reports: Skip Phase 4 (report quality benchmark).
        """
        result = V9BenchmarkResult()
        t0 = time.time()

        # Ensure cases are loaded
        _ensure_all_cases()

        # Filter cases
        cases = list(CASES)
        if cycles:
            from validation.v9.historical_cases import MacroCycle
            cycle_enums = [MacroCycle(c) for c in cycles]
            cases = [c for c in cases if c.cycle in cycle_enums]

        if sample_size and sample_size < len(cases):
            import random
            random.seed(42)
            cases = random.sample(cases, sample_size)

        result.total_cases = len(cases)
        result.cases_by_cycle = _count_by_cycle(cases)

        # ── Phase 2: Blind Research Test ─────────────────────────────
        try:
            suite = BlindTestSuite(name="V9 Full Benchmark")
            suite.add_cases(cases)

            agent_outputs = [self.agent_fn(tc.blind_prompt) for tc in suite.cases]
            suite = self.blind_runner.run_suite(suite, agent_outputs=agent_outputs)

            result.blind_test_suite = suite
            result.blind_test_average = suite.average_score
            result.blind_test_pass_rate = suite.pass_rate
            result.blind_test_dimensions = suite.dimension_averages
        except Exception as e:
            result.errors.append(f"Phase 2 error: {e}")

        # ── Phase 3: Prediction Calibration ──────────────────────────
        if not skip_calibration:
            try:
                for tc, ao in zip(suite.cases, agent_outputs):
                    prediction = ao.get("prediction", "")
                    confidence_raw = ao.get("confidence", 0.7)
                    try:
                        confidence = float(confidence_raw)
                    except (TypeError, ValueError):
                        confidence = 0.5

                    rec = self.ledger.record(
                        prediction_id=f"pred_v9_{tc.case.case_id}",
                        belief_name=prediction[:50] if prediction else "no_prediction",
                        confidence=min(max(confidence, 0.0), 1.0),
                        expected_outcome=ao.get("prediction", ""),
                        time_window="6m",
                    )
                    was_correct = self._determine_correctness(ao, tc.case)
                    self.ledger.evaluate(
                        rec.prediction_id,
                        tc.case.actual_outcome,
                        was_correct,
                    )
                    # Record error classification for incorrect predictions
                    if not was_correct:
                        record = self.ledger.records.get(rec.prediction_id)
                        if record and record.error_diagnosis:
                            error_str = self._classify_error(ao, tc.case)
                            try:
                                record.error_diagnosis.primary_error = ErrorType(error_str)
                            except ValueError:
                                record.error_diagnosis.primary_error = ErrorType.WRONG_CAUSALITY

                calibration_stats = self.ledger.calibration_stats
                result.ece = calibration_stats.get("ece", 1.0)
                result.hit_rate = calibration_stats.get("hit_rate", 0.0)
                result.calibration_ledger = self.ledger
            except Exception as e:
                result.errors.append(f"Phase 3 error: {e}")

        # ── Phase 4: Report Quality Benchmark ────────────────────────
        if not skip_reports:
            try:
                # Generate memo from first 5 cases for quality benchmark
                sample_for_reports = cases[:min(5, len(cases))]
                memo_results = []
                for tc in sample_for_reports:
                    memo = _generate_agent_memo(tc, self.agent_fn(tc.blind_prompt))
                    comparison = self.report_benchmark.evaluate_memo(
                        case_id=tc.case.case_id,
                        case_title=tc.case.title,
                        memo_content=str(memo),
                        memo_sections=memo,
                    )
                    memo_results.append(comparison)

                result.report_benchmark_results = [
                    {"case": r.case_id if hasattr(r, "case_id") else "", "score": r.overall_score if hasattr(r, "overall_score") else 0}
                    for r in memo_results
                ]
                if memo_results:
                    scores = [r.overall_score for r in memo_results if hasattr(r, "overall_score")]
                    result.report_benchmark_score = sum(scores) / len(scores) if scores else 0
            except Exception as e:
                result.errors.append(f"Phase 4 error: {e}")

        result.execution_time_seconds = time.time() - t0
        return result

    def run_cycle_benchmarks(self) -> dict[str, V9BenchmarkResult]:
        """Run benchmark per cycle for detailed analysis."""
        cycle_results = {}
        for cycle_name in ["liquidity", "inflation", "technology", "credit", "currency", "growth"]:
            cycle_results[cycle_name] = self.run_full_benchmark(
                cycles=[cycle_name],
            )
        return cycle_results

    def run_turning_point_analysis(self) -> BlindTestSuite:
        """Run blind test specifically on turning point cases."""
        suite = self.blind_runner.build_turning_point_suite()
        agent_outputs = [self.agent_fn(tc.blind_prompt) for tc in suite.cases]
        return self.blind_runner.run_suite(suite, agent_outputs=agent_outputs)

    def run_difficulty_breakdown(self) -> dict[str, BlindTestSuite]:
        """Run blind test broken down by difficulty level."""
        results = {}
        for difficulty in ["easy", "medium", "hard"]:
            suite = self.blind_runner.build_difficulty_suite(difficulty)
            agent_outputs = [self.agent_fn(tc.blind_prompt) for tc in suite.cases]
            results[difficulty] = self.blind_runner.run_suite(suite, agent_outputs=agent_outputs)
        return results

    def save_results(self, result: V9BenchmarkResult,
                     filename: Optional[str] = None):
        """Save benchmark results to output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if filename is None:
            filename = f"v9_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filepath = self.output_dir / filename
        output = {
            "timestamp": result.timestamp,
            "execution_time_seconds": result.execution_time_seconds,
            "total_cases": result.total_cases,
            "cases_by_cycle": result.cases_by_cycle,
            "phase2_blind_test": {
                "average_score": result.blind_test_average,
                "pass_rate": result.blind_test_pass_rate,
                "dimensions": result.blind_test_dimensions,
            },
            "phase3_calibration": {
                "ece": result.ece,
                "hit_rate": result.hit_rate,
            },
            "phase4_report_quality": {
                "average_score": result.report_benchmark_score,
            },
            "errors": result.errors,
            "v9_status": {
                "historical_benchmark_75": result.blind_test_average >= 75,
                "ece_under_015": result.ece < 0.15,
                "report_memo_85": result.report_benchmark_score >= 85,
            }
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)
        return filepath

    def _determine_correctness(self, agent_output: dict, case: HistoricalCase) -> bool:
        """Determine if the agent's prediction was correct.

        Compares the agent's directional call with the actual historical outcome.
        """
        prediction = (agent_output.get("prediction", "") or "").lower()
        actual = case.actual_outcome.lower()

        if not prediction:
            return False

        bullish_keywords = ["rally", "bullish", "up", "gain", "rise", "positive", "increase", "outperform"]
        bearish_keywords = ["selloff", "bearish", "crash", "decline", "fall", "negative", "decrease", "underperform"]

        agent_is_bullish = any(kw in prediction for kw in bullish_keywords)
        agent_is_bearish = any(kw in prediction for kw in bearish_keywords)
        actual_is_bullish = any(kw in actual for kw in bullish_keywords)
        actual_is_bearish = any(kw in actual for kw in bearish_keywords)

        # If agent is neutral, consider it wrong (no actionable call)
        if not agent_is_bullish and not agent_is_bearish:
            return False

        # Directional alignment check
        if (agent_is_bullish and actual_is_bullish) or (agent_is_bearish and actual_is_bearish):
            return True

        return False

    def _classify_error(self, agent_output: dict, case: HistoricalCase) -> str:
        """Classify the type of prediction error."""
        prediction = agent_output.get("prediction", "").lower()
        actual = case.actual_outcome.lower()

        if not prediction:
            return ErrorType.WRONG_DATA.value

        # Check narrative alignment
        narrative = case.dominant_narrative.lower()
        if any(w in prediction for w in ["no data", "uncertain", "can't predict"]):
            return ErrorType.WRONG_DATA.value

        # Check if regime was misidentified
        regime = case.macro_regime
        agent_regime = agent_output.get("regime", "").lower()

        regime_matched = True
        for key in ["monetary", "fiscal", "growth", "inflation"]:
            if regime.get(key, "") not in agent_regime:
                regime_matched = False
                break

        if not regime_matched:
            return ErrorType.WRONG_REGIME.value

        # Check narrative direction
        direction = case.asset_reaction.get("direction", "")
        bullish_keywords = ["rally", "bullish", "up", "gain", "rise", "positive"]
        bearish_keywords = ["selloff", "bearish", "crash", "decline", "fall"]

        agent_is_bullish = any(kw in prediction for kw in bullish_keywords)
        agent_is_bearish = any(kw in prediction for kw in bearish_keywords)

        actual_is_bullish = any(kw in actual for kw in bullish_keywords)
        actual_is_bearish = any(kw in actual for kw in bearish_keywords)

        if (agent_is_bullish and actual_is_bearish) or (agent_is_bearish and actual_is_bullish):
            return ErrorType.WRONG_NARRATIVE.value

        if not agent_is_bullish and not agent_is_bearish:
            return ErrorType.WRONG_NARRATIVE.value

        # Check confidence
        confidence = agent_output.get("confidence", 0.5)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.5

        if confidence > 0.9:
            return ErrorType.OVERCONFIDENCE.value

        return ErrorType.WRONG_CAUSALITY.value


# ── Helpers ──────────────────────────────────────────────────────────

def _ensure_all_cases():
    """Ensure all cases are loaded. Force refresh of CASES list."""
    global CASES
    fresh = build_all_cases()
    CASES.clear()
    CASES.extend(fresh)


def _count_by_cycle(cases: list[HistoricalCase]) -> dict:
    """Count cases by cycle."""
    from collections import Counter
    return dict(Counter(c.cycle.value for c in cases))


def _generate_agent_memo(tc: BlindTestCase, agent_output: dict) -> dict:
    """Generate a V10 professional research memo from agent output.
    
    Produces an institutional-quality memo with all required sections
    for Phase 4 report quality benchmarking. Structured to match
    Bridgewater/Goldman/MS research memo format.
    """
    case = tc.case
    
    # Build the professional memo
    memo_sections = {
        "title": f"Macro Strategy: {case.title}",
        "date": case.date,
        "case_id": case.case_id,
        
        # Executive Summary
        "executive_summary": agent_output.get("executive_summary", "")[:500],
        
        # Core sections
        "regime_assessment": agent_output.get("regime", ""),
        "dominant_narrative": agent_output.get("narrative", ""),
        "core_beliefs": agent_output.get("beliefs", []),
        "prediction": agent_output.get("prediction", ""),
        "risk_analysis": agent_output.get("risk", ""),
        "invalidation_conditions": agent_output.get("invalidation", ""),
        "asset_implications": agent_output.get("asset_implication", ""),
        
        # V10 enhanced fields
        "confidence": agent_output.get("confidence", 0.5),
        "conviction_level": agent_output.get("conviction_level", "low"),
        "reasoning_mode": agent_output.get("reasoning_mode", "unknown"),
        "llm_model": agent_output.get("llm_model", "none"),
        
        # Expert comparison fields
        "vs_expert_narrative": "",  # Filled by expert_comparison
        "vs_expert_logic": "",
        "vs_expert_evidence": "",
        "vs_expert_prediction": "",
        "vs_expert_writing": "",
        
        # Meta
        "generation_timestamp": datetime.now().isoformat(),
    }
    
    return memo_sections


# ══════════════════════════════════════════════════════════════════════
# Quick Run (for development/testing)
# ══════════════════════════════════════════════════════════════════════

def quick_benchmark(sample_size: int = 20) -> V9BenchmarkResult:
    """Run a quick benchmark on a smaller sample for development iteration."""
    runner = V9BenchmarkRunner()
    return runner.run_full_benchmark(sample_size=sample_size)


def full_benchmark() -> V9BenchmarkResult:
    """Run the full benchmark on all 102 cases."""
    runner = V9BenchmarkRunner()
    return runner.run_full_benchmark()


# ══════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="V9 Benchmark Runner")
    parser.add_argument("--quick", action="store_true", help="Quick benchmark (20 cases)")
    parser.add_argument("--full", action="store_true", help="Full benchmark (all 102 cases)")
    parser.add_argument("--sample", type=int, help="Sample N cases")
    parser.add_argument("--cycle", type=str, help="Run single cycle benchmark")
    parser.add_argument("--turning-points", action="store_true", help="Run turning point analysis only")
    parser.add_argument("--save", action="store_true", help="Save results to file")

    args = parser.parse_args()

    runner = V9BenchmarkRunner()

    if args.turning_points:
        suite = runner.run_turning_point_analysis()
        print(suite.summary())

    elif args.cycle:
        suite = runner.blind_runner.build_cycle_suite(args.cycle)
        agent_outputs = [runner.agent_fn(tc.blind_prompt) for tc in suite.cases]
        suite = runner.blind_runner.run_suite(suite, agent_outputs=agent_outputs)
        print(suite.summary())

    elif args.full:
        result = runner.run_full_benchmark()
        print(result.summary())
        if args.save:
            path = runner.save_results(result)
            print(f"\nResults saved to: {path}")

    elif args.quick or not args.sample:
        sample = args.sample or 20
        result = runner.run_full_benchmark(sample_size=sample)
        print(result.summary())
        if args.save:
            path = runner.save_results(result)
            print(f"\nResults saved to: {path}")
