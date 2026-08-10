"""MarkdownRenderer — Full 12-section research report from MacroNarrative.

Beta upgrade: Complete professional research report template with:
    - Executive Summary
    - Today's Key Changes
    - Current Macro Story
    - Liquidity / Credit / Growth / Inflation Analysis
    - Risk Appetite
    - Scenario Probability
    - Belief Changes
    - Key Risks
    - Action Items
    - Confidence Explanation

Consumes: MacroNarrative (never raw artifacts)
Output:  Markdown string
"""

from src.schemas.narrative import MacroNarrative
from src.shared.logging import get_logger

logger = get_logger(__name__)


class MarkdownRenderer:
    """Render MacroNarrative → professional Markdown research report."""

    def render(self, narrative: MacroNarrative) -> str:
        """Render a MacroNarrative as a full Markdown report.

        Args:
            narrative: The structured MacroNarrative to render.

        Returns:
            Complete Markdown-formatted research report.
        """
        lines: list[str] = []

        self._add_header(lines, narrative)
        self._add_executive_summary(lines, narrative)
        self._add_today_changes(lines, narrative)
        self._add_macro_story(lines, narrative)
        self._add_dimension_analysis(lines, narrative)
        self._add_risk_appetite(lines, narrative)
        self._add_scenario_analysis(lines, narrative)
        self._add_belief_changes(lines, narrative)
        self._add_key_risks(lines, narrative)
        self._add_action_items(lines, narrative)
        self._add_confidence_explanation(lines, narrative)
        self._add_footer(lines, narrative)

        return "\n".join(lines)

    # ── Section Builders ─────────────────────────────────────────────────

    @staticmethod
    def _add_header(lines: list[str], n: MacroNarrative) -> None:
        level_icon = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(
            n.confidence_level.value, "⚪"
        )
        lines.extend([
            f"# Macro Research Report",
            f"",
            f"**Generated**: {n.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Overall Confidence**: {level_icon} {n.confidence_level.value} ({n.confidence_score:.0%})",
            f"**Risk Count**: {len(n.risks)} | **Scenarios**: {len(n.scenario_analysis)}",
            f"",
            f"---",
            f"",
        ])

    @staticmethod
    def _add_executive_summary(lines: list[str], n: MacroNarrative) -> None:
        lines.extend([
            f"## 1. Executive Summary",
            f"",
            n.summary if n.summary else "_No summary available._",
            f"",
        ])

    @staticmethod
    def _add_today_changes(lines: list[str], n: MacroNarrative) -> None:
        lines.extend([
            f"## 2. Today's Key Changes",
            f"",
            n.today_key_changes if n.today_key_changes else "_No significant changes today._",
            f"",
        ])

    @staticmethod
    def _add_macro_story(lines: list[str], n: MacroNarrative) -> None:
        lines.extend([
            f"## 3. Current Macro Story",
            f"",
            n.macro_story if n.macro_story else "_Insufficient data for macro narrative._",
            f"",
        ])

    @staticmethod
    def _add_dimension_analysis(lines: list[str], n: MacroNarrative) -> None:
        lines.extend([
            f"## 4. Dimension Analysis",
            f"",
        ])

        for dim_name, dim_obj, dim_text in [
            ("Liquidity", n.liquidity, n.liquidity_analysis),
            ("Credit", n.credit, n.credit_analysis),
            ("Growth", n.growth, n.growth_analysis),
            ("Inflation", n.inflation, n.inflation_analysis),
        ]:
            conf_bar = _confidence_bar(dim_obj.confidence)
            lines.extend([
                f"### 4.{['Liquidity','Credit','Growth','Inflation'].index(dim_name)+1} {dim_name} {conf_bar}",
                f"",
                f"**Assessment**: {dim_obj.summary}",
                f"",
                f"**Analysis**: {dim_text}" if dim_text else f"_No detailed analysis available._",
                f"",
            ])
            if dim_obj.key_signals:
                lines.append("**Key Signals**:")
                for s in dim_obj.key_signals:
                    lines.append(f"- {s}")
                lines.append("")
            if dim_obj.hypothesis_summary:
                lines.append(f"**Hypothesis**: {dim_obj.hypothesis_summary}")
                lines.append("")

    @staticmethod
    def _add_risk_appetite(lines: list[str], n: MacroNarrative) -> None:
        lines.extend([
            f"## 5. Risk Appetite",
            f"",
            n.risk_appetite_analysis if n.risk_appetite_analysis else "_No risk appetite data available._",
            f"",
        ])

    @staticmethod
    def _add_scenario_analysis(lines: list[str], n: MacroNarrative) -> None:
        lines.extend([
            f"## 6. Scenario Analysis",
            f"",
        ])

        if not n.scenario_analysis:
            lines.append("_No scenario analysis generated._")
            lines.append("")
            return

        for i, scenario in enumerate(n.scenario_analysis, 1):
            prob_bar = _probability_bar(scenario.probability)
            lines.extend([
                f"### Scenario {i}: {scenario.name} — {scenario.probability:.0%} probability {prob_bar}",
                f"",
                f"**Rationale**: {scenario.rationale}",
                f"",
            ])
            if scenario.supporting_signals:
                lines.append("**Supporting Signals**:")
                for s in scenario.supporting_signals:
                    lines.append(f"- {s}")
                lines.append("")
            if scenario.contradicting_signals:
                lines.append("**Contradicting Signals**:")
                for s in scenario.contradicting_signals:
                    lines.append(f"- {s}")
                lines.append("")
            if scenario.key_indicators_to_watch:
                lines.append("**Key Indicators to Watch**:")
                for ind in scenario.key_indicators_to_watch:
                    lines.append(f"- {ind}")
                lines.append("")

    @staticmethod
    def _add_belief_changes(lines: list[str], n: MacroNarrative) -> None:
        lines.extend([
            f"## 7. Belief Changes",
            f"",
        ])

        if n.belief_changes_text:
            lines.append(n.belief_changes_text)
        elif n.belief_changes:
            for bc in n.belief_changes:
                arrow = {"increased": "↑", "decreased": "↓", "unchanged": "→", "reversed": "⇄", "new": "🆕"}.get(bc.direction, "→")
                dim_label = f"**[{bc.dimension}]** " if bc.dimension else ""
                lines.append(
                    f"- {arrow} {dim_label}{bc.hypothesis_statement[:120]} "
                    f"({bc.previous_confidence:.0%} → {bc.current_confidence:.0%})"
                )
                if bc.prior_summary:
                    lines.append(f"  Prior: {bc.prior_summary}")
                lines.append(f"  Note: {bc.note}")
        else:
            lines.append("_No belief changes detected._")

        lines.append("")

    @staticmethod
    def _add_key_risks(lines: list[str], n: MacroNarrative) -> None:
        lines.extend([
            f"## 8. Key Risks",
            f"",
        ])

        if n.key_risks:
            for i, risk in enumerate(n.key_risks, 1):
                lines.append(f"{i}. {risk}")
        elif n.risks:
            for risk in n.risks:
                severity_marker = {
                    "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"
                }.get(risk.severity, "⚪")
                lines.append(f"- {severity_marker} **[{risk.category}]** {risk.description}")
        else:
            lines.append("_No risks identified in this analysis cycle._")

        lines.append("")

    @staticmethod
    def _add_action_items(lines: list[str], n: MacroNarrative) -> None:
        lines.extend([
            f"## 9. Action Items",
            f"",
        ])

        if n.action_items:
            for i, item in enumerate(n.action_items, 1):
                lines.append(f"{i}. {item}")
        else:
            lines.append("_No action items generated._")

        lines.append("")

    @staticmethod
    def _add_confidence_explanation(lines: list[str], n: MacroNarrative) -> None:
        lines.extend([
            f"## 10. Confidence Assessment",
            f"",
        ])

        level_icon = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(
            n.confidence_level.value, "⚪"
        )
        lines.extend([
            f"**Overall Confidence**: {level_icon} **{n.confidence_level.value}**",
            f"",
            f"**Score**: {n.confidence_score:.2f} / 1.00",
            f"",
        ])

        if n.confidence_explanation:
            ce = n.confidence_explanation
            if ce.why_low:
                lines.extend([
                    f"### Why Confidence is {n.confidence_level.value}",
                    f"",
                    ce.why_low,
                    f"",
                ])
            lines.extend([
                f"### Supporting Evidence",
                f"",
                ce.supporting_evidence_summary,
                f"",
                f"### Contradicting Evidence",
                f"",
                ce.contradicting_evidence_summary,
                f"",
                f"### Reflection Findings",
                f"",
                ce.reflection_findings_summary,
                f"",
            ])
            if ce.hypothesis_verdict_breakdown:
                vb = ce.hypothesis_verdict_breakdown
                lines.extend([
                    f"### Verdict Breakdown",
                    f"",
                    f"| Verdict    | Count |",
                    f"|------------|-------|",
                    f"| Confirmed  | {vb.get('confirmed', 0)} |",
                    f"| Refuted    | {vb.get('refuted', 0)} |",
                    f"| Uncertain  | {vb.get('uncertain', 0)} |",
                    f"| **Total**  | **{vb.get('total', 0)}** |",
                    f"",
                ])
        else:
            lines.append("_No detailed confidence breakdown available._")
            lines.append("")

    @staticmethod
    def _add_footer(lines: list[str], n: MacroNarrative) -> None:
        lines.extend([
            f"---",
            f"",
            f"*Report generated by Macro Research Agent (Beta) on "
            f"{n.generated_at.strftime('%Y-%m-%d %H:%M UTC')}*",
            f"",
            f"*Disclaimer: This is an automated research product. "
            f"All content is rule-based and does not constitute investment advice.*",
        ])


# ── Visual Helpers ──────────────────────────────────────────────────────────


def _confidence_bar(score: float, width: int = 10) -> str:
    """Draw a visual confidence bar."""
    filled = int(round(score * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"`[{bar}] {score:.0%}`"


def _probability_bar(prob: float, width: int = 10) -> str:
    """Draw a visual probability bar."""
    filled = int(round(prob * width))
    bar = "▓" * filled + "░" * (width - filled)
    return f"`[{bar}]`"
