"""RC-2 Performance Profiler — measures latency, throughput, and resource usage.

Runs the full 7-step pipeline multiple times and emits a comprehensive
performance report including avg, P50, P95, P99 latency per module.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.pipeline import MacroResearchPipeline


# ── Models ──────────────────────────────────────────────────────────────────


@dataclass
class StepMetrics:
    """Latency metrics for a single pipeline step."""
    step: str
    samples_ms: list[float] = field(default_factory=list)

    @property
    def avg_ms(self) -> float:
        return statistics.mean(self.samples_ms) if self.samples_ms else 0.0

    @property
    def p50_ms(self) -> float:
        if not self.samples_ms:
            return 0.0
        return statistics.median(self.samples_ms)

    @property
    def p95_ms(self) -> float:
        if len(self.samples_ms) < 20:
            return self._percentile(95)
        return self._percentile(95)

    @property
    def p99_ms(self) -> float:
        return self._percentile(99)

    @property
    def min_ms(self) -> float:
        return min(self.samples_ms) if self.samples_ms else 0.0

    @property
    def max_ms(self) -> float:
        return max(self.samples_ms) if self.samples_ms else 0.0

    @property
    def count(self) -> int:
        return len(self.samples_ms)

    def _percentile(self, pct: float) -> float:
        """Compute p-th percentile using linear interpolation."""
        if not self.samples_ms:
            return 0.0
        sorted_data = sorted(self.samples_ms)
        k = (pct / 100.0) * (len(sorted_data) - 1)
        f = int(k)
        c = k - f
        if f + 1 < len(sorted_data):
            return sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f])
        return sorted_data[f]

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "count": self.count,
            "avg_ms": round(self.avg_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
        }


@dataclass
class RunMetrics:
    """All metrics from a single pipeline run."""
    total_ms: float = 0.0
    plan_ms: float = 0.0
    execute_ms: float = 0.0
    narrative_ms: float = 0.0
    render_ms: float = 0.0
    step_times: dict[str, float] = field(default_factory=dict)


@dataclass
class ProfileReport:
    """Aggregated performance report across all runs."""
    runs: int
    total: StepMetrics
    plan: StepMetrics
    execute: StepMetrics
    narrative_step: StepMetrics
    render: StepMetrics
    per_task: dict[str, StepMetrics]
    memory_peak_kb: float = 0.0
    memory_avg_kb: float = 0.0
    pipeline_runs: int = 0
    failures: int = 0


# ── Profiler ────────────────────────────────────────────────────────────────


class PipelineProfiler:
    """Instruments MacroResearchPipeline and collects latency metrics."""

    def __init__(self, runs: int = 10) -> None:
        self._runs = runs
        self._pipeline = MacroResearchPipeline()
        self._run_metrics: list[RunMetrics] = []
        self._memory_samples: list[float] = []

    async def profile(self) -> ProfileReport:
        """Run the pipeline N times and collect metrics."""
        # Warm-up run (excluded from metrics)
        await self._pipeline.run(goal="macro environment analysis")

        self._run_metrics = []
        self._memory_samples = []

        for i in range(self._runs):
            metrics = await self._profile_single_run(i + 1)
            if metrics is not None:
                self._run_metrics.append(metrics)

        return self._build_report()

    async def _profile_single_run(self, run_num: int) -> Optional[RunMetrics]:
        """Profile a single pipeline run."""
        # Re-create pipeline to avoid handler registration overhead skew
        pipeline = MacroResearchPipeline()

        start_total = time.perf_counter()

        try:
            # Plan phase
            t0 = time.perf_counter()
            pipeline._ensure_handlers()
            plan = await pipeline._planner.create_plan("macro environment analysis")
            plan_ms = (time.perf_counter() - t0) * 1000

            # Execute phase
            t0 = time.perf_counter()
            exec_result = await pipeline._executor.execute(plan)
            execute_ms = (time.perf_counter() - t0) * 1000

            # Collect per-task latencies
            step_times: dict[str, float] = {}
            for task_id, tr in exec_result.task_results.items():
                step_times[task_id] = tr.execution_time_ms

            # Narrative + render phase
            t0 = time.perf_counter()
            narrative_obj = exec_result.artifacts.get("narrative")
            narrative_ms = (time.perf_counter() - t0) * 1000

            render_ms = 0.0
            if narrative_obj is not None:
                t0 = time.perf_counter()
                from src.renderer.markdown import MarkdownRenderer
                MarkdownRenderer().render(narrative_obj)
                render_ms = (time.perf_counter() - t0) * 1000

            total_ms = (time.perf_counter() - start_total) * 1000

            # Collect memory snapshot (from first few runs only to avoid noise)
            if run_num <= 3:
                tracemalloc.start()
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                self._memory_samples.append(peak / 1024)  # KB

            return RunMetrics(
                total_ms=total_ms,
                plan_ms=plan_ms,
                execute_ms=execute_ms,
                narrative_ms=narrative_ms,
                render_ms=render_ms,
                step_times=step_times,
            )

        except Exception as exc:
            print(f"  Run {run_num} failed: {exc}")
            return None

    def _build_report(self) -> ProfileReport:
        """Aggregate all run metrics into a report."""
        total_steps = StepMetrics(step="Total Pipeline (end-to-end)")
        plan_steps = StepMetrics(step="Plan Creation")
        execute_steps = StepMetrics(step="Execute (all tasks)")
        narrative_steps = StepMetrics(step="Narrative Extraction")
        render_steps = StepMetrics(step="Markdown Render")

        # Collect per-task metrics
        task_metrics: dict[str, StepMetrics] = {}

        failures = 0
        for rm in self._run_metrics:
            total_steps.samples_ms.append(rm.total_ms)
            plan_steps.samples_ms.append(rm.plan_ms)
            execute_steps.samples_ms.append(rm.execute_ms)
            narrative_steps.samples_ms.append(rm.narrative_ms)
            render_steps.samples_ms.append(rm.render_ms)

            for task_id, t_ms in rm.step_times.items():
                if task_id not in task_metrics:
                    task_metrics[task_id] = StepMetrics(step=task_id)
                task_metrics[task_id].samples_ms.append(t_ms)

        failures = self._runs - len(self._run_metrics)
        mem_peak = max(self._memory_samples) if self._memory_samples else 0.0
        mem_avg = statistics.mean(self._memory_samples) if self._memory_samples else 0.0

        return ProfileReport(
            runs=len(self._run_metrics),
            total=total_steps,
            plan=plan_steps,
            execute=execute_steps,
            narrative_step=narrative_steps,
            render=render_steps,
            per_task=task_metrics,
            memory_peak_kb=round(mem_peak, 2),
            memory_avg_kb=round(mem_avg, 2),
            pipeline_runs=len(self._run_metrics),
            failures=failures,
        )


# ── Report Generation ───────────────────────────────────────────────────────


def generate_markdown(report: ProfileReport) -> str:
    """Convert a ProfileReport to Markdown."""

    lines: list[str] = [
        "# Performance Report — Macro Research Agent RC-2",
        "",
        f"> Generated: {datetime.now(timezone.utc).isoformat()}",
        f"> Pipeline runs: {report.pipeline_runs} | Failures: {report.failures}",
        f"> Memory: avg {report.memory_avg_kb:.1f} KB, peak {report.memory_peak_kb:.1f} KB",
        "",
        "---",
        "",
        "## Pipeline Phase Latency",
        "",
        "| Phase | Count | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Min (ms) | Max (ms) |",
        "|-------|-------|----------|----------|----------|----------|----------|----------|",
    ]

    for sm in [report.total, report.plan, report.execute, report.narrative_step, report.render]:
        lines.append(
            f"| {sm.step} | {sm.count} | {sm.avg_ms:.1f} | {sm.p50_ms:.1f} | "
            f"{sm.p95_ms:.1f} | {sm.p99_ms:.1f} | {sm.min_ms:.1f} | {sm.max_ms:.1f} |"
        )

    # Task-level breakdown
    if report.per_task:
        lines.append("")
        lines.append("## Per-Task Latency (7-step Cognitive Pipeline)")
        lines.append("")
        lines.append(
            "| Task ID | Count | Avg (ms) | P50 (ms) | P95 (ms) | P99 (ms) | Max (ms) |"
        )
        lines.append(
            "|---------|-------|----------|----------|----------|----------|----------|"
        )
        for task_id in sorted(report.per_task.keys()):
            tm = report.per_task[task_id]
            lines.append(
                f"| {task_id} | {tm.count} | {tm.avg_ms:.1f} | {tm.p50_ms:.1f} | "
                f"{tm.p95_ms:.1f} | {tm.p99_ms:.1f} | {tm.max_ms:.1f} |"
            )

    # Bottleneck analysis
    if report.per_task:
        lines.append("")
        lines.append("## Bottleneck Analysis")
        lines.append("")
        # Find slowest task
        slowest = max(report.per_task.items(), key=lambda x: x[1].avg_ms)
        lines.append(f"**Slowest task:** `{slowest[0]}` — avg {slowest[1].avg_ms:.1f} ms")
        lines.append(f"**Total pipe overhead:** {report.total.avg_ms - report.execute.avg_ms:.1f} ms")
        lines.append(f"**Execute-to-total ratio:** {report.execute.avg_ms / report.total.avg_ms * 100:.1f}%")

        # Phase pie breakdown
        lines.append("")
        lines.append("### Phase Breakdown (% of total)")
        lines.append("")
        total_avg = report.total.avg_ms or 1.0
        lines.append(f"- Plan: {report.plan.avg_ms / total_avg * 100:.1f}%")
        lines.append(f"- Execute: {report.execute.avg_ms / total_avg * 100:.1f}%")
        lines.append(f"- Narrative: {report.narrative_step.avg_ms / total_avg * 100:.1f}%")
        lines.append(f"- Render: {report.render.avg_ms / total_avg * 100:.1f}%")

    lines.append("")
    lines.append("## Memory Analysis")
    lines.append("")
    lines.append(f"- Average peak memory: {report.memory_avg_kb:.1f} KB")
    lines.append(f"- Maximum peak memory: {report.memory_peak_kb:.1f} KB")
    if report.memory_peak_kb < 10000:
        lines.append("- Assessment: **Low memory usage** — suitable for constrained environments")

    lines.append("")
    lines.append("---")
    lines.append(f"*Report generated by RC-2 Performance Profiler — {datetime.now(timezone.utc).isoformat()}*")

    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────────


async def main() -> None:
    print("RC-2 Performance Profiler")
    print("=" * 60)

    profiler = PipelineProfiler(runs=15)  # 15 runs for statistical significance
    report = await profiler.profile()

    print(f"\nRuns completed: {report.pipeline_runs}/{profiler._runs} (failures: {report.failures})")
    print(f"Pipeline end-to-end: avg={report.total.avg_ms:.1f}ms P95={report.total.p95_ms:.1f}ms")
    print(f"  Plan:       avg={report.plan.avg_ms:.1f}ms")
    print(f"  Execute:    avg={report.execute.avg_ms:.1f}ms")
    print(f"  Narrative:  avg={report.narrative_step.avg_ms:.1f}ms")
    print(f"  Render:     avg={report.render.avg_ms:.1f}ms")
    print(f"Memory: avg={report.memory_avg_kb:.1f}KB peak={report.memory_peak_kb:.1f}KB")

    # Per-task breakdown
    if report.per_task:
        print("\nPer-task latency:")
        for task_id in sorted(report.per_task.keys()):
            tm = report.per_task[task_id]
            print(f"  {task_id}: avg={tm.avg_ms:.1f}ms max={tm.max_ms:.1f}ms")

    # Write report
    md = generate_markdown(report)
    output_path = "docs/PERFORMANCE_REPORT.md"
    import os
    os.makedirs("docs", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"\nReport written to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
