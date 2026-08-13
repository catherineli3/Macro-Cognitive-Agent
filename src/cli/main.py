"""CLI entry point for Macro Research Agent (Beta).

Subcommands:
    macro-agent analyze    — Run full pipeline, output Markdown report
    macro-agent report     — View a cached report by ID
    macro-agent latest     — Show the latest generated report
    macro-agent beliefs    — Display current belief state from memory

Usage:
    python -m src.cli.main analyze --goal "macro environment analysis"
    python -m src.cli.main analyze -o report.md
    python -m src.cli.main report <report_id>
    python -m src.cli.main latest
    python -m src.cli.main beliefs
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from src.pipeline import MacroResearchPipeline
from src.schemas.narrative import MacroNarrative


def main() -> None:
    """CLI entry point — parse subcommand and dispatch."""
    parser = argparse.ArgumentParser(
        description="Macro Research Agent — AI-powered macroeconomic analysis (Beta)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── analyze ────────────────────────────────────────────────────────
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Run a full macro research pipeline and output a report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  macro-agent analyze
  macro-agent analyze --goal "liquidity analysis" -o liquidity_report.md
  macro-agent analyze --goal "macro environment" --format json
  macro-agent analyze --indicators DXY US10Y VIX
        """,
    )
    analyze_parser.add_argument(
        "--goal",
        default="macro environment analysis",
        help="Research goal (e.g., 'liquidity analysis', 'risk assessment')",
    )
    analyze_parser.add_argument(
        "--indicators",
        nargs="*",
        default=None,
        help="Specific indicators to focus on",
    )
    analyze_parser.add_argument(
        "--format",
        choices=["markdown", "json", "text"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    analyze_parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path (default: stdout)",
    )
    analyze_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    # ── report ──────────────────────────────────────────────────────────
    report_parser = subparsers.add_parser(
        "report",
        help="View a cached report by ID",
    )
    report_parser.add_argument(
        "report_id",
        help="Report ID to retrieve",
    )
    report_parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )

    # ── latest ──────────────────────────────────────────────────────────
    subparsers.add_parser(
        "latest",
        help="Show the most recently generated report",
    )

    # ── beliefs ─────────────────────────────────────────────────────────
    subparsers.add_parser(
        "beliefs",
        help="Display current belief state from memory",
    )

    # ── V3: predict ─────────────────────────────────────────────────────
    predict_parser = subparsers.add_parser(
        "predict",
        help="Run V3 pipeline: hypothesis → multi-prediction → evaluation → diagnosis",
    )
    predict_parser.add_argument("--goal", default="macro environment analysis")
    predict_parser.add_argument("--output", "-o", default=None)

    # ── V3: metrics ─────────────────────────────────────────────────────
    subparsers.add_parser(
        "metrics",
        help="Display V3 4-KPI dashboard",
    )

    # ── V3: library ─────────────────────────────────────────────────────
    subparsers.add_parser(
        "library",
        help="Display Hypothesis Library status",
    )

    args = parser.parse_args()

    if args.verbose and hasattr(args, "verbose") and args.command == "analyze":
        from src.shared.logging import configure_logging

        configure_logging(level="DEBUG")

    if args.command == "analyze":
        _cmd_analyze(args)
    elif args.command == "report":
        _cmd_report(args)
    elif args.command == "latest":
        _cmd_latest(args)
    elif args.command == "beliefs":
        _cmd_beliefs()
    elif args.command == "predict":
        _cmd_predict(args)
    elif args.command == "metrics":
        _cmd_metrics()
    elif args.command == "library":
        _cmd_library()
    else:
        parser.print_help()
        sys.exit(1)


# ── Command Handlers ─────────────────────────────────────────────────────


def _cmd_analyze(args) -> None:
    """Handle 'analyze' command."""
    result = asyncio.run(_run_pipeline(args.goal, args.indicators))

    if result.narrative_obj is None:
        print(f"Pipeline failed: {result.error or 'No narrative produced.'}", file=sys.stderr)
        sys.exit(1)

    # Render output
    if args.format == "json":
        import json as _json

        output = result.narrative_json or _json.dumps(
            result.narrative_obj.model_dump(mode="json"), indent=2, ensure_ascii=False
        )
    elif args.format == "text":
        output = _render_plaintext(result.narrative_obj)
    else:
        output = result.narrative or _render_fallback_markdown(result.narrative_obj)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report saved to {args.output}")
    else:
        print(output)


def _cmd_report(args) -> None:
    """Handle 'report' command — view cached report by ID."""
    # Check in-memory cache (same as API)
    from src.api.analyze_routes import _report_cache

    narrative = _report_cache.get(args.report_id)
    if narrative is None:
        print(
            f"Report '{args.report_id}' not found. Generate one via 'analyze' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.format == "json":
        import json as _json

        print(_json.dumps(narrative.model_dump(mode="json"), indent=2, ensure_ascii=False))
    else:
        from src.renderer.markdown import MarkdownRenderer

        print(MarkdownRenderer().render(narrative))


def _cmd_latest(args) -> None:
    """Handle 'latest' command."""
    from src.api.analyze_routes import _latest_report_id, _report_cache

    if _latest_report_id is None or _latest_report_id not in _report_cache:
        print("No reports generated yet. Run 'analyze' first.", file=sys.stderr)
        sys.exit(1)

    narrative = _report_cache[_latest_report_id]
    from src.renderer.markdown import MarkdownRenderer

    print(MarkdownRenderer().render(narrative))


def _cmd_beliefs() -> None:
    """Handle 'beliefs' command."""
    try:
        from src.memory.store import BeliefMemoryStore

        store = BeliefMemoryStore()
        all_beliefs = store.all_beliefs()

        if not all_beliefs:
            print("No beliefs stored yet. Run 'analyze' to generate beliefs.")
            return

        print("=" * 70)
        print("BELIEF STATE")
        print("=" * 70)
        for b in all_beliefs[:20]:
            trans_icon = {
                "NEW": "🆕",
                "STABLE": "→",
                "REINFORCED": "↑",
                "WEAKENED": "↓",
                "REVERSED": "⇄",
            }.get(b.transition.value, "?")
            print(
                f"\n{trans_icon} [{b.dimension}] {b.direction.value} "
                f"(confidence: {b.confidence:.0%})"
            )
            print(f"  Statement: {b.statement[:120]}")
            print(f"  Status: {b.status.value} | Transition: {b.transition.value}")
            print(f"  Evidence: +{b.supporting_count} / -{b.contradicting_count}")
            if b.review_summary:
                print(f"  Review: {b.review_summary[:120]}")
            print(f"  Recorded: {b.timestamp.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"\n{'=' * 70}")
        print(f"Total beliefs: {len(all_beliefs)}")
        print(
            f"Last updated: {max(b.timestamp for b in all_beliefs).strftime('%Y-%m-%d %H:%M UTC')}"
        )

    except Exception as e:
        print(f"Failed to retrieve beliefs: {e}", file=sys.stderr)
        sys.exit(1)


# ── Helpers ─────────────────────────────────────────────────────────────


async def _run_pipeline(goal: str, indicators: list[str] | None):
    """Execute the pipeline asynchronously."""
    pipeline = MacroResearchPipeline()
    return await pipeline.run(goal=goal, indicators=indicators)


def _render_plaintext(narrative: MacroNarrative) -> str:
    """Render MacroNarrative as plain text."""
    lines = [
        "MACRO RESEARCH REPORT",
        f"{'=' * 60}",
        f"Generated: {narrative.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"Confidence: {narrative.confidence_level.value} ({narrative.confidence_score:.0%})",
        "",
        "EXECUTIVE SUMMARY",
        f"{'-' * 40}",
        narrative.summary,
        "",
        "TODAY'S KEY CHANGES",
        f"{'-' * 40}",
        narrative.today_key_changes,
        "",
        "MACRO STORY",
        f"{'-' * 40}",
        narrative.macro_story,
        "",
        "DIMENSION ANALYSIS",
        f"{'-' * 40}",
    ]

    for dim_name, dim_obj in [
        ("LIQUIDITY", narrative.liquidity),
        ("CREDIT", narrative.credit),
        ("GROWTH", narrative.growth),
        ("INFLATION", narrative.inflation),
    ]:
        lines.append("")
        lines.append(f"{dim_name} [{dim_obj.confidence:.0%}]")
        lines.append(f"  {dim_obj.summary}")

    if narrative.scenario_analysis:
        lines.append("")
        lines.append("SCENARIO ANALYSIS")
        lines.append(f"{'-' * 40}")
        for s in narrative.scenario_analysis:
            lines.append(f"  {s.name}: {s.probability:.0%} — {s.rationale[:100]}")

    if narrative.risks:
        lines.append("")
        lines.append("KEY RISKS")
        lines.append(f"{'-' * 40}")
        for risk in narrative.risks:
            lines.append(f"  [{risk.severity.upper()}] [{risk.category}] {risk.description[:120]}")

    if narrative.action_items:
        lines.append("")
        lines.append("ACTION ITEMS")
        lines.append(f"{'-' * 40}")
        for i, item in enumerate(narrative.action_items, 1):
            lines.append(f"  {i}. {item}")

    return "\n".join(lines)


def _render_fallback_markdown(narrative: MacroNarrative) -> str:
    """Fallback Markdown renderer using the Renderer module."""
    from src.renderer.markdown import MarkdownRenderer

    return MarkdownRenderer().render(narrative)


# ── V3 Command Handlers ──────────────────────────────────────────────────


def _cmd_predict(args) -> None:
    """Handle 'predict' command — full V3 pipeline."""
    print(f"V3 Prediction Pipeline — goal: {args.goal}")
    print("=" * 60)
    result = asyncio.run(_run_v3_pipeline(args.goal))

    if result.prediction_batch:
        batch = result.prediction_batch
        print(f"\nPredictions Generated: {batch.total_predictions}")
        print(f"  Hypotheses: {batch.hypothesis_count}")
        print(f"  Channels:   {batch.channel_count}")
        for h_id, preds in batch.by_hypothesis.items():
            print(f"\n  Hypothesis {h_id[:8]}:")
            for p in preds:
                print(
                    f"    [{p.prediction_tier.value}] {p.indicator} {p.direction} "
                    f"({p.transmission_channel}) c={p.confidence:.0%} horizon={p.horizon}"
                )

    if result.evaluation_report:
        er = result.evaluation_report
        print(f"\nEvaluation: DA={er.directional_accuracy:.1%} MAE={er.mean_absolute_error:.3f}")
        if er.accuracy_by_channel:
            print(f"  By Channel: {er.accuracy_by_channel}")

    if result.diagnosis_report:
        dr = result.diagnosis_report
        print(
            f"\nDiagnosis: {dr.total_diagnosed} classified, {dr.correct_count} correct, {dr.incorrect_count} errors"
        )
        if dr.error_distribution:
            print(f"  Errors: {dr.error_distribution}")

    if result.kpi_report:
        kpi = result.kpi_report
        print(f"\n4-KPI Dashboard [{kpi.window.value}]:")
        print(f"  Overall: {kpi.overall_score:.3f}")
        print(f"  KPI-1 Hypothesis Accuracy:  {kpi.kpi1_hypothesis_accuracy.composite_score:.3f}")
        print(f"  KPI-2 Prediction Error:     {kpi.kpi2_prediction_error.composite_score:.3f}")
        print(f"  KPI-3 Calibration:          {kpi.kpi3_calibration.composite_score:.3f}")
        print(f"  KPI-4 Learning Speed:       {kpi.kpi4_learning_speed.composite_score:.3f}")

    if result.error:
        print(f"\nError: {result.error}", file=sys.stderr)


async def _run_v3_pipeline(goal: str):
    """Execute V3 pipeline with prediction."""
    pipeline = MacroResearchPipeline()
    return await pipeline.run_with_prediction(goal=goal)


def _cmd_metrics() -> None:
    """Handle 'metrics' command — display 4-KPI dashboard."""
    print("4-KPI Dashboard")
    print("=" * 60)
    try:
        from src.metrics import KPIMetricsEngine

        km = KPIMetricsEngine()
        if km._baseline:
            b = km._baseline
            print(f"  Baseline [{b.window.value}]: overall={b.overall_score:.3f}")
            print(
                f"    KPI-1 Hypothesis Accuracy: {b.kpi1_hypothesis_accuracy.composite_score:.3f}"
            )
            print(f"    KPI-2 Prediction Error:    {b.kpi2_prediction_error.composite_score:.3f}")
            print(f"    KPI-3 Calibration:         {b.kpi3_calibration.composite_score:.3f}")
            print(f"    KPI-4 Learning Speed:      {b.kpi4_learning_speed.composite_score:.3f}")
        else:
            print("  No baseline established. Run 'predict' first.")
    except Exception as e:
        print(f"  Failed: {e}")


def _cmd_library() -> None:
    """Handle 'library' command — display Hypothesis Library."""
    print("Hypothesis Library")
    print("=" * 60)
    try:
        result = asyncio.run(_get_library_status())
        print(f"  Total hypotheses: {result['total']}")
        print(f"  Active:           {result['active']}")
        print(f"  Deprecated:       {result['deprecated']}")
        print(f"  Avg Score:        {result['avg_score']:.3f}")
        if result["top"]:
            print("\n  Top Hypotheses:")
            for e in result["top"]:
                print(
                    f"    [{e.dimension}] score={e.current_score.total_score:.2f} | {e.statement[:80]}"
                )
    except Exception as e:
        print(f"  Failed: {e}")


async def _get_library_status() -> dict:
    from src.hypothesis_library import HypothesisLibrary

    lib = HypothesisLibrary()
    active = await lib.get_all_active()
    deprecated = await lib.get_deprecated()
    top = await lib.get_top(limit=5)
    avg = await lib.get_library_avg_score()
    return {
        "total": len(active) + len(deprecated),
        "active": len(active),
        "deprecated": len(deprecated),
        "avg_score": avg,
        "top": top,
    }


if __name__ == "__main__":
    main()
