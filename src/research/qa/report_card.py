"""V5.3 Report Card — Format and present ResearchScoreCard results.

Generates formatted output for:
    - Console display
    - JSON export
    - Markdown report
    - Integration with memo generation pipeline
"""

from __future__ import annotations

from src.research.qa.schemas import (
    QAVerdict,
    ResearchScoreCard,
)


class ReportCard:
    """Format and present QA results in various output formats."""

    BAR_LENGTH = 30

    def __init__(self):
        pass

    # ── Console Output ────────────────────────────────────────────────

    def format_console(self, scorecard: ResearchScoreCard) -> str:
        """Format scorecard for console display with visual bars."""
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  RESEARCH QUALITY SCORECARD")
        lines.append("=" * 70)
        lines.append(
            f"  Score: {scorecard.total_score:.1f}/100  |  "
            f"Grade: {scorecard.grade.value}  |  "
            f"Verdict: {scorecard.verdict.value.upper()}"
        )
        lines.append("=" * 70)
        lines.append("")

        # Dimension scores with visual bars
        lines.append("  DIMENSION SCORES:")
        lines.append("  " + "-" * 68)

        for dim in scorecard.dimensions:
            bar = self._make_bar(dim.score)
            name = dim.dimension.replace("_", " ").title()
            weight_pct = f"{dim.weight*100:.0f}%"
            lines.append(
                f"  {dim.grade.value:3s} | {name:30s} " f"[{bar}] {dim.score:5.1f} ({weight_pct})"
            )

        lines.append("  " + "-" * 68)
        lines.append("")

        # Overall assessment
        lines.append(f"  Assessment: {scorecard.overall_assessment}")
        lines.append("")

        # Critical issues
        if scorecard.critical_issues:
            lines.append("  CRITICAL ISSUES:")
            for issue in scorecard.critical_issues:
                lines.append(f"    ! {issue}")
            lines.append("")

        # Improvement actions
        if scorecard.improvement_actions:
            lines.append("  IMPROVEMENT ACTIONS:")
            for action in scorecard.improvement_actions[:5]:
                lines.append(f"    > {action}")
            lines.append("")

        # Verdict status
        verdict_color = {
            QAVerdict.PASS: "PASSED",
            QAVerdict.CONDITIONAL: "CONDITIONAL PASS (review required)",
            QAVerdict.REJECT: "REJECTED — must regenerate",
        }
        lines.append(f"  FINAL: {verdict_color[scorecard.verdict]}")
        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)

    # ── Markdown Output ───────────────────────────────────────────────

    def format_markdown(self, scorecard: ResearchScoreCard) -> str:
        """Format scorecard as Markdown for inclusion in reports."""
        lines = []
        lines.append("## Research Quality Scorecard")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| **Total Score** | **{scorecard.total_score:.1f}/100** |")
        lines.append(f"| **Grade** | **{scorecard.grade.value}** |")
        lines.append(f"| **Verdict** | **{scorecard.verdict.value.upper()}** |")
        lines.append("")

        lines.append("### Dimension Breakdown")
        lines.append("")
        lines.append("| Grade | Dimension | Score | Weight | Key Finding |")
        lines.append("|-------|-----------|-------|--------|-------------|")

        for dim in scorecard.dimensions:
            name = dim.dimension.replace("_", " ").title()
            finding = dim.findings[0][:60] + "..." if dim.findings else "-"
            lines.append(
                f"| {dim.grade.value} | {name} | {dim.score:.1f} | "
                f"{dim.weight*100:.0f}% | {finding} |"
            )

        lines.append("")

        if scorecard.critical_issues:
            lines.append("### Critical Issues")
            for issue in scorecard.critical_issues:
                lines.append(f"- {issue}")
            lines.append("")

        if scorecard.improvement_actions:
            lines.append("### Recommended Actions")
            for action in scorecard.improvement_actions[:5]:
                lines.append(f"- {action}")
            lines.append("")

        lines.append(f"**Assessment:** {scorecard.overall_assessment}")
        lines.append("")

        return "\n".join(lines)

    # ── JSON Export ───────────────────────────────────────────────────

    def format_json(self, scorecard: ResearchScoreCard) -> dict:
        """Export scorecard as JSON-serializable dict."""
        return scorecard.to_dict()

    # ── Minimal Badge ─────────────────────────────────────────────────

    def format_badge(self, scorecard: ResearchScoreCard) -> str:
        """Single-line badge for inline display.

        Example: "[A] 85.5/100 PASS"
        """
        verdict_map = {
            QAVerdict.PASS: "PASS",
            QAVerdict.CONDITIONAL: "COND",
            QAVerdict.REJECT: "FAIL",
        }
        return (
            f"[{scorecard.grade.value}] "
            f"{scorecard.total_score:.1f}/100 "
            f"{verdict_map[scorecard.verdict]}"
        )

    # ── Comparison ─────────────────────────────────────────────────────

    def compare(self, before: ResearchScoreCard, after: ResearchScoreCard) -> str:
        """Compare two scorecards to show improvement/degradation."""
        lines = []
        lines.append("Scorecard Comparison:")
        lines.append(f"  Before: {before.total_score:.1f} ({before.grade.value})")
        lines.append(f"  After:  {after.total_score:.1f} ({after.grade.value})")

        delta = after.total_score - before.total_score
        direction = "IMPROVED" if delta > 0 else "DECLINED" if delta < 0 else "UNCHANGED"
        lines.append(f"  Delta: {delta:+.1f} → {direction}")

        lines.append("")
        lines.append("  Dimension changes:")
        before_dims = {d.dimension: d.score for d in before.dimensions}
        for dim in after.dimensions:
            before_score = before_dims.get(dim.dimension, 0)
            delta = dim.score - before_score
            delta_str = f"{delta:+.1f}" if delta != 0 else " 0.0"
            name = dim.dimension.replace("_", " ").title()
            lines.append(f"    {name:30s}: {before_score:.1f} → {dim.score:.1f} ({delta_str})")

        return "\n".join(lines)

    # ── Helpers ────────────────────────────────────────────────────────

    def _make_bar(self, score: float) -> str:
        """Create a visual progress bar."""
        filled = int(score / 100 * self.BAR_LENGTH)
        empty = self.BAR_LENGTH - filled

        # Color-coded characters (using ASCII-safe alternatives)
        if score >= 85:
            bar_char = "#"
        elif score >= 70:
            bar_char = "="
        elif score >= 55:
            bar_char = "-"
        else:
            bar_char = "."

        return f"{bar_char * filled}{' ' * empty}"
