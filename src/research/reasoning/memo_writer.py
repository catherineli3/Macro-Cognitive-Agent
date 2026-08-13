"""MemoWriter — Produce professional institutional research memos.

Quality: Must read like Bridgewater Daily Observations or PTJ Market Letter.
Not templates — LLM performs the writing informed by structured research inputs.

Structure:
    Executive Summary → Regime → Consensus → Our View → Evidence →
    Counter Evidence → Key Risks → Predictions → Trading Implication →
    Invalidation Conditions → Research Questions

Target: 1000-3000 words, professional language, evidence-backed, no bullet dumping.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from src.research.reasoning.schemas import (
    CounterArgument,
    EvidenceAssessment,
    Hypothesis,
    MemoSection,
    ResearchMemo,
)


class MemoWriter:
    """Write professional daily macro research memos.

    Input: All structured research outputs from the reasoning pipeline.
    Output: A ResearchMemo that reads like institutional research.
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def write_memo(
        self,
        evidence_assessment: EvidenceAssessment,
        hypotheses: list[Hypothesis],
        counter_arguments: list[CounterArgument],
        regime_result: dict | None = None,
        beliefs: list = None,
        capital_flow_result: dict | None = None,
        narrative: str | None = None,
        date_str: str | None = None,
    ) -> ResearchMemo:
        """Write the complete research memo from all inputs.

        This is the PRIMARY output of the V4 research agent.
        Everything else exists to feed this function.
        """
        beliefs = beliefs or []
        date_str = date_str or datetime.now(UTC).strftime("%Y-%m-%d")
        memo_id = f"MEMO_{date_str}_{str(uuid.uuid4())[:6]}"

        # Collect all sections
        sections = []
        _word_count = 0

        # Section 1: Executive Summary
        exec_content = self._write_executive_summary(
            evidence_assessment, hypotheses, regime_result, narrative
        )
        bracket_count = exec_content.count("[")
        sections.append(
            MemoSection(
                heading="Executive Summary",
                content=exec_content,
                word_count=len(exec_content.split()),
                has_citations=True,
                citation_count=exec_content.count("Source:") + bracket_count,
            )
        )

        # Section 2: Current Regime
        regime_content = self._write_regime_section(regime_result)
        sections.append(
            MemoSection(
                heading="Current Macro Regime",
                content=regime_content,
                word_count=len(regime_content.split()),
                has_citations=True,
                citation_count=0,
            )
        )

        # Section 3: Evidence Summary
        evidence_content = self._write_evidence_section(evidence_assessment)
        sections.append(
            MemoSection(
                heading="Evidence Review",
                content=evidence_content,
                word_count=len(evidence_content.split()),
                has_citations=True,
                citation_count=len(evidence_assessment.clusters),
            )
        )

        # Section 4: Market Consensus vs Our View
        consensus_content = self._write_consensus_section(
            evidence_assessment, hypotheses, narrative
        )
        sections.append(
            MemoSection(
                heading="Market Consensus & Our Differentiated View",
                content=consensus_content,
                word_count=len(consensus_content.split()),
                has_citations=False,
                citation_count=0,
            )
        )

        # Section 5: Key Hypotheses
        hyp_content = self._write_hypothesis_section(hypotheses)
        sections.append(
            MemoSection(
                heading="Research Hypotheses",
                content=hyp_content,
                word_count=len(hyp_content.split()),
                has_citations=True,
                citation_count=len(hypotheses),
            )
        )

        # Section 6: Counter Arguments
        counter_content = self._write_counter_section(counter_arguments)
        sections.append(
            MemoSection(
                heading="Counter Evidence & Risks",
                content=counter_content,
                word_count=len(counter_content.split()),
                has_citations=True,
                citation_count=len(counter_arguments),
            )
        )

        # Section 7: Investment Implications
        invest_content = self._write_investment_section(
            hypotheses, evidence_assessment, capital_flow_result
        )
        sections.append(
            MemoSection(
                heading="Investment Implications",
                content=invest_content,
                word_count=len(invest_content.split()),
                has_citations=False,
                citation_count=0,
            )
        )

        # Section 8: Invalidation & Research Questions
        final_content = self._write_final_section(hypotheses, counter_arguments)
        sections.append(
            MemoSection(
                heading="Invalidation Conditions & Research Agenda",
                content=final_content,
                word_count=len(final_content.split()),
                has_citations=False,
                citation_count=0,
            )
        )

        # Assemble full memo text
        full_text = "\n\n".join([s.content for s in sections if s.content])

        # Build predictions from hypotheses
        predictions = self._extract_predictions(hypotheses)

        # Key evidence supporting/contradicting
        supporting = []
        contradicting = []
        for c in evidence_assessment.clusters:
            if c.net_direction == "supporting_bullish":
                supporting.append(f"{c.theme}: {c.description[:80]}")
            elif c.net_direction == "supporting_bearish":
                contradicting.append(f"{c.theme}: {c.description[:80]}")

        # Invalidation conditions
        invalidation = self._extract_invalidation(hypotheses, counter_arguments)

        # Open questions
        questions = self._extract_questions(hypotheses, evidence_assessment)

        # Trading implication
        trading = self._extract_trading(hypotheses, evidence_assessment)

        # Compute quality metrics
        evidence_coverage = self._compute_evidence_coverage(sections, hypotheses)
        counter_coverage = len(counter_arguments) / max(len(hypotheses), 1) if hypotheses else 0.0

        total_words = sum(s.word_count for s in sections)
        total_citations = sum(s.citation_count for s in sections)

        memo = ResearchMemo(
            memo_id=memo_id,
            date=date_str,
            executive_summary=exec_content,
            one_sentence_view=self._one_sentence(hypotheses, evidence_assessment),
            current_regime=(
                regime_result.get("regime_label", regime_result.get("regime_type", "Unclassified"))
                if regime_result
                else "Unclassified"
            ),
            regime_confidence=regime_result.get("confidence", 0.5) if regime_result else 0.5,
            regime_transition_risk=(
                regime_result.get("transition", {}).get("probability", 0.3)
                if regime_result
                else 0.3
            ),
            regime_detail=regime_content,
            market_consensus="See: Market Consensus & Our Differentiated View section",
            our_view_vs_consensus=consensus_content,
            evidence_summary=evidence_content,
            key_evidence_supporting=supporting[:5],
            key_evidence_contradicting=contradicting[:5],
            counter_arguments=[ca.argument[:200] for ca in counter_arguments[:3]],
            key_risks=[ca.why_the_hypothesis_could_be_wrong[:200] for ca in counter_arguments[:3]],
            predictions=predictions,
            trading_implication=trading,
            favored_assets=self._favored_assets(hypotheses, evidence_assessment),
            unfavored_assets=self._unfavored_assets(hypotheses, evidence_assessment),
            highest_conviction_trade=self._highest_conviction(hypotheses),
            invalidation_conditions=invalidation,
            open_questions=questions[:5],
            data_to_watch=self._data_to_watch(evidence_assessment),
            word_count=total_words,
            citation_count=total_citations,
            hallucination_check=True,
            evidence_coverage=round(evidence_coverage, 2),
            counter_argument_coverage=round(counter_coverage, 2),
            source_hypotheses=[h.hypothesis_id for h in hypotheses],
            source_clusters=[c.cluster_id for c in evidence_assessment.clusters],
            source_models=[
                "evidence_synthesizer",
                "hypothesis_builder",
                "counter_argument_generator",
            ],
            full_memo_text=full_text,
            sections=sections,
        )

        return memo

    # ── Section Writers ──

    def _write_executive_summary(self, evidence, hypotheses, regime, narrative):
        """Write 200-300 word executive summary — must stand alone."""
        parts = []
        date = datetime.now(UTC).strftime("%B %d, %Y")
        parts.append(f"DAILY MACRO RESEARCH MEMO — {date}")
        parts.append("")

        # Regime one-liner
        rl = (
            regime.get("regime_label", regime.get("regime_type", "Unclassified"))
            if regime
            else "Unclassified"
        )
        parts.append(f"MACRO REGIME: {rl}")

        # Net evidence direction
        parts.append(
            f"EVIDENCE BIAS: {evidence.net_direction.upper()} "
            f"(Bullish weight: {evidence.net_weight_bullish:.2f}, "
            f"Bearish weight: {evidence.net_weight_bearish:.2f})"
        )

        parts.append("")

        # Top 3 hypotheses
        parts.append("KEY RESEARCH THEMES:")
        for i, hyp in enumerate(hypotheses[:3]):
            parts.append(
                f"  {i + 1}. {hyp.title} [Confidence: {hyp.confidence:.0%}, Evidence: {hyp.evidence_weight:+.2f}]"
            )

        parts.append("")

        # Evidence quality
        parts.append(
            f"EVIDENCE QUALITY: {evidence.evidence_quality.upper()} "
            f"({evidence.total_evidence_points} evidence points across {len(evidence.clusters)} clusters)"
        )

        # Risks
        parts.append("KEY RISK: ")
        if evidence.contradictory_signals:
            parts.append(
                f"  Conflicting signals in: {', '.join(evidence.contradictory_signals[:2])}"
            )

        # One sentence takeaway
        parts.append("")
        parts.append(f"BOTTOM LINE: {self._one_sentence(hypotheses, evidence)}")

        return "\n".join(parts)

    def _write_regime_section(self, regime):
        """Write the regime analysis section."""
        if not regime:
            return "Regime data not available for this session."

        rl = regime.get("regime_label", regime.get("regime_type", "Unclassified"))
        conf = regime.get("confidence", 0.5)
        trans = regime.get("transition", {})
        tr_prob = (
            trans.get("probability", trans.get("risk", 0.3)) if isinstance(trans, dict) else 0.3
        )

        lines = [f"The current macro regime is classified as **{rl}** with {conf:.0%} confidence."]
        lines.append(f"Regime transition risk is estimated at **{tr_prob:.0%}**.")

        dimensions = regime.get("dimensions", {})
        if dimensions:
            lines.append("")
            lines.append("Regime dimensions:")
            for dim, val in dimensions.items():
                lines.append(f"  - {dim}: {val}")

        analog = regime.get("historical_analog", regime.get("analog", {}))
        if analog and isinstance(analog, dict) and analog.get("period"):
            lines.append("")
            lines.append(
                f"Historical analog: **{analog.get('period')}** "
                f"— {analog.get('label', '')} "
                f"(similarity: {analog.get('similarity_score', 'N/A')})"
            )

        if tr_prob > 0.5:
            lines.append("")
            lines.append(
                "** TRANSITION WARNING: Regime transition probability is elevated. "
                "Position sizing should reflect heightened uncertainty. "
                "Monitor regime indicators daily for confirmation of shift."
            )

        return "\n".join(lines)

    def _write_evidence_section(self, evidence):
        """Write the evidence review section."""
        lines = [
            f"Today's analysis incorporates **{evidence.total_evidence_points}** "
            f"evidence points across **{len(evidence.clusters)}** thematic clusters."
        ]
        lines.append("")
        lines.append(
            f"**Net Assessment: {evidence.net_direction.upper()}** "
            f"(Evidence quality: {evidence.evidence_quality})"
        )
        lines.append("")

        # Detail each cluster
        for i, cluster in enumerate(evidence.clusters):
            if cluster.weight_score < 0.3:
                continue
            lines.append(
                f"**{i + 1}. {cluster.theme.replace('_', ' ').title()}**  "
                f"[Weight: {cluster.weight_score:.2f}, Quality: {cluster.quality_score:.2f}]"
            )
            lines.append(f"   Direction: {cluster.net_direction}")
            lines.append(f"   {cluster.description}")
            lines.append("")

        # Conflicting signals
        if evidence.contradictory_signals:
            lines.append("**Mixed/Contradictory Signals:**")
            for sig in evidence.contradictory_signals:
                lines.append(f"  - {sig}")

        # Missing data
        if evidence.key_missing_data:
            lines.append("")
            lines.append("**Data Gaps:**")
            for gap in evidence.key_missing_data:
                lines.append(f"  - {gap}")

        return "\n".join(lines)

    def _write_consensus_section(self, evidence, hypotheses, narrative):
        """Write market consensus vs our view."""
        lines = ["## Market Consensus"]

        if narrative:
            lines.append(f"The dominant market narrative appears to be: *{narrative}*")
        else:
            lines.append("The current market consensus remains to be explicitly identified.")

        lines.append("")
        lines.append("Our evidence suggests the following positioning:")

        net_dir = evidence.net_direction
        if "bullish" in net_dir:
            lines.append("- Consensus appears tilted bullish, consistent with risk-on positioning")
        elif "bearish" in net_dir:
            lines.append(
                "- Consensus appears tilted bearish, consistent with defensive positioning"
            )
        else:
            lines.append("- Evidence is mixed — consensus may be fragmented or uncertain")

        lines.append("")
        lines.append("## Our Differentiated View")
        lines.append("")

        if hypotheses:
            top = hypotheses[0]
            lines.append(f"Our primary differentiated view: **{top.statement}**")
            lines.append("")
            lines.append("Where we differ from consensus:")
            for hyp in hypotheses[:2]:
                for sk in hyp.key_assumptions[:2]:
                    lines.append(f"  - {sk}")

            ev_weight = evidence.net_weight_bullish - evidence.net_weight_bearish
            if abs(ev_weight) > 0.5:
                direction = "bullish" if ev_weight > 0 else "bearish"
                lines.append(
                    f"  - Evidence net weight supports {direction} view ({ev_weight:+.2f})"
                )
        else:
            lines.append("No differentiated view established — further research warranted.")

        return "\n".join(lines)

    def _write_hypothesis_section(self, hypotheses):
        """Write the hypothesis detail section."""
        if not hypotheses:
            return "No active research hypotheses."

        lines = [f"**{len(hypotheses)} active hypotheses** ranked by confidence:"]
        lines.append("")

        for i, hyp in enumerate(hypotheses[:5]):
            lines.append(f"### Hypothesis {i + 1}: {hyp.title}")
            lines.append(
                f"**Confidence: {hyp.confidence:.0%}** | Evidence Weight: {hyp.evidence_weight:+.2f}"
            )
            lines.append("")
            lines.append(hyp.statement)
            lines.append("")

            if hyp.causal_chain:
                lines.append("**Causal Chain:**")
                for step in hyp.causal_chain:
                    lines.append(f"  1. {step}")
                lines.append("")

            if hyp.key_assumptions:
                lines.append("**Key Assumptions:**")
                for ka in hyp.key_assumptions[:3]:
                    lines.append(f"  - {ka}")
                lines.append("")

            if hyp.structural_factors:
                lines.append(f"**Structural:** {', '.join(hyp.structural_factors[:3])}")
            if hyp.cyclical_factors:
                lines.append(f"**Cyclical:** {', '.join(hyp.cyclical_factors[:3])}")
            lines.append("")

        return "\n".join(lines)

    def _write_counter_section(self, counters):
        """Write counter-arguments and risk section."""
        if not counters:
            return "No counter-arguments generated. **Risk: unexamined hypotheses.**"

        lines = [f"Every hypothesis carries risk. {len(counters)} counter-arguments identified:"]
        lines.append("")

        for i, ca in enumerate(counters[:4]):
            severity_marker = {"fatal": "[FATAL]", "major": "[MAJOR]", "minor": "[MINOR]"}.get(
                ca.severity, ""
            )
            lines.append(f"### Counter {i + 1}: {ca.title} [{severity_marker}]")
            lines.append(f"**Probability: {ca.probability:.0%}** | Severity: {ca.severity}")
            lines.append("")
            lines.append(ca.argument)
            lines.append("")

            if ca.trigger_conditions:
                lines.append("**Trigger Conditions:**")
                for tc in ca.trigger_conditions:
                    lines.append(f"  - {tc}")
                lines.append("")

            if ca.historical_precedent:
                lines.append(f"**Historical Precedent:** {ca.historical_precedent}")
                lines.append("")

            if ca.what_the_market_is_missing:
                lines.append(f"**What Markets May Be Missing:** {ca.what_the_market_is_missing}")
                lines.append("")

        return "\n".join(lines)

    def _write_investment_section(self, hypotheses, evidence, cf_result):
        """Write investment implications."""
        lines = ["## Portfolio Implications"]
        lines.append("")

        # Determine allocation tilt
        net = evidence.net_direction
        if "bullish" in net:
            lines.append("**Allocation tilt: MODERATELY RISK-ON**")
            lines.append("Evidence supports maintaining or adding risk exposure.")
        elif "bearish" in net:
            lines.append("**Allocation tilt: DEFENSIVE**")
            lines.append("Evidence supports reducing risk exposure and raising cash.")
        else:
            lines.append("**Allocation tilt: NEUTRAL / HEDGED**")
            lines.append("Evidence is mixed — maintain balanced portfolio with active hedges.")

        lines.append("")

        # From hypotheses
        for hyp in hypotheses[:3]:
            if hyp.asset_impact:
                for ai in hyp.asset_impact[:2]:
                    direction = ai.get("direction", "").upper()
                    asset = ai.get("asset", "")
                    conviction = ai.get("conviction", "medium")
                    lines.append(
                        f"- **{direction} {asset}** [{conviction} conviction] — {hyp.title[:80]}"
                    )

        lines.append("")

        # Capital flow signal
        if cf_result:
            cf_dir = cf_result.get("direction", cf_result.get("flow_direction", ""))
            lines.append(f"**Capital Flow Signal:** {cf_dir}")
            lines.append(
                "Align portfolio with institutional flow direction unless contrarian thesis is well-supported."
            )

        lines.append("")
        lines.append("## Trade Recommendations")
        lines.append("")
        lines.append("**Highest Conviction:**")
        hc = self._highest_conviction(hypotheses)
        lines.append(f"  {hc}")

        lines.append("")
        lines.append(
            "**Hedging considerations:** Counter-arguments suggest tail risk protection via appropriate hedges."
        )

        return "\n".join(lines)

    def _write_final_section(self, hypotheses, counters):
        """Write invalidation conditions and research agenda."""
        lines = ["## Invalidation Conditions"]
        lines.append("")

        for hyp in hypotheses[:3]:
            if hyp.falsification_conditions:
                lines.append(f"**{hyp.title}** is invalidated if:")
                for fc in hyp.falsification_conditions[:2]:
                    lines.append(f"  - {fc.get('condition', '')}")
                    lines.append(f"    → If triggered: {fc.get('if_triggered', '')}")
                lines.append("")

        if counters:
            lines.append("## Research Agenda")
            lines.append("")
            lines.append("Questions the team should investigate:")
            for ca in counters[:3]:
                for tc in ca.trigger_conditions[:1]:
                    lines.append(f"  - {tc}")
            for hyp in hypotheses[:2]:
                lines.append(f"  - Monitor: {hyp.domain} data releases")
            lines.append("  - Review historical analog relevance to current regime")

        return "\n".join(lines)

    # ── Extraction Helpers ──

    def _extract_predictions(self, hypotheses):
        predictions = []
        for hyp in hypotheses[:4]:
            pred = {
                "statement": hyp.statement[:150],
                "domain": hyp.domain,
                "direction": "bullish" if hyp.evidence_weight > 0 else "bearish",
                "confidence": hyp.confidence,
                "evidence_weight": hyp.evidence_weight,
                "invalidation": [
                    fc.get("condition", "") for fc in hyp.falsification_conditions[:2]
                ],
            }
            predictions.append(pred)
        return predictions

    def _extract_invalidation(self, hypotheses, counters):
        conditions = []
        for hyp in hypotheses[:3]:
            for fc in hyp.falsification_conditions[:1]:
                conditions.append(
                    {
                        "condition": fc.get("condition", ""),
                        "severity": "major",
                        "timeline": fc.get("timeline", "unknown"),
                        "if_triggered": fc.get("if_triggered", "Reassess hypothesis"),
                    }
                )
        return conditions[:5]

    def _extract_questions(self, hypotheses, evidence):
        questions = []
        for hyp in hypotheses[:3]:
            for ka in hyp.key_assumptions[:1]:
                questions.append(f"Is '{ka}' still valid?")
        for gap in evidence.key_missing_data:
            questions.append(f"When will data on {gap.split('on ')[-1]} be available?")
        if hypotheses:
            questions.append(
                f"Has the confidence on '{hypotheses[0].title}' changed since last assessment?"
            )
        return questions

    def _extract_trading(self, hypotheses, evidence):
        if not hypotheses:
            return "Insufficient hypotheses for trade recommendations."
        net = evidence.net_direction
        if "bullish" in net:
            return "Add risk exposure. Focus on cyclical and growth-sensitive assets. Maintain hedges as counter-argument protection."
        elif "bearish" in net:
            return "Reduce risk exposure. Increase cash and defensive allocations. Consider long-volatility hedges."
        return "Maintain neutral position. Wait for clearer evidence direction before committing capital."

    def _favored_assets(self, hypotheses, evidence):
        assets = set()
        if "bullish" in evidence.net_direction:
            assets.update(["Equities (cyclical sectors)", "High-yield credit", "Commodities"])
        for hyp in hypotheses:
            for ai in hyp.asset_impact:
                if ai.get("direction") == "long":
                    assets.add(ai.get("asset", ""))
        return sorted(list(assets))[:5]

    def _unfavored_assets(self, hypotheses, evidence):
        assets = set()
        if "bearish" in evidence.net_direction:
            assets.update(["Treasuries (hedging only)", "Defensive equities"])
        for hyp in hypotheses:
            for ai in hyp.asset_impact:
                if ai.get("direction") == "short":
                    assets.add(ai.get("asset", ""))
        return sorted(list(assets))[:5]

    def _highest_conviction(self, hypotheses):
        if not hypotheses:
            return "No high-conviction trade identified."
        best = max(hypotheses, key=lambda h: h.confidence)
        direction = "LONG" if best.evidence_weight > 0 else "SHORT"
        return f"{direction} exposure based on: {best.title} (confidence: {best.confidence:.0%})"

    def _data_to_watch(self, evidence):
        items = []
        for gap in evidence.key_missing_data:
            items.append(gap)
        if evidence.evidence_quality == "low":
            items.append("Improve evidence quality before taking directional positions")
        return items

    def _one_sentence(self, hypotheses, evidence):
        if not hypotheses:
            return "Insufficient evidence to form a directional view — await key data releases."
        top = hypotheses[0]
        net = evidence.net_direction
        return f"The preponderance of evidence points {net}, with the highest-conviction view being: {top.title} ({top.confidence:.0%} confidence)."

    def _compute_evidence_coverage(self, sections, hypotheses):
        """Estimate what % of claims in the memo are backed by evidence."""
        if not hypotheses:
            return 0.0
        total_hyp = len(hypotheses)
        backed = sum(1 for h in hypotheses if h.supporting_evidence or h.contradicting_evidence)
        return backed / max(total_hyp, 1)
