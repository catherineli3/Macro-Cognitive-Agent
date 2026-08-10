"""NarrativeEngine v2 — Synthesize full cognitive chain with learning data.

v2.0 Upgrade:
    - Historical Accuracy section (how has the Agent performed?)
    - Belief Evolution section (how have beliefs changed over time?)
    - What We Learned section (patterns mined from outcome data)
    - Confidence Trend section (calibrated vs raw confidence)
    - Prediction Accuracy section (hit rate, Brier Score)

All content sources from cognitive chain + v2.0 engines — no free generation.
"""

from datetime import datetime, timezone
from typing import Optional

from src.domain.narrative import ConfidenceLevel
from src.schemas.calibration import CalibratedConfidenceSet
from src.schemas.hypothesis import HypothesisSchema, HypothesisSet
from src.schemas.learning import LearningSummary
from src.schemas.memory import BeliefRecord
from src.schemas.narrative import (
    BeliefChangeNote,
    ConfidenceExplanation,
    DimensionNarrative,
    MacroNarrative,
    RiskItem,
    ScenarioProbability,
)
from src.schemas.outcome import OutcomeSummary
from src.schemas.reflection import ReflectionFinding, ReflectionReport, ReflectionSet
from src.schemas.signal import MacroSignalSchema, SignalSnapshot
from src.shared.logging import get_logger

logger = get_logger(__name__)

_DIMENSION_NAMES = ["liquidity", "credit", "growth", "inflation"]

_SCENARIO_TEMPLATES = [
    {
        "name": "Soft Landing",
        "condition": lambda sigs, hyps, refs: (
            _count_bullish(sigs, "growth") >= 1
            and _count_bearish(sigs, "inflation") >= 1
            and len(refs.confirmed) >= len(refs.refuted)
        ),
        "base_probability": 0.55,
        "rationale": "Growth signals remain supportive while inflation pressures ease. "
                      "Reflection confirms the majority of hypotheses. "
                      "This is consistent with a controlled slowdown toward trend growth.",
        "watch": ["PMI", "CPI", "NFP", "Retail Sales"],
    },
    {
        "name": "Hard Landing / Recession",
        "condition": lambda sigs, hyps, refs: (
            _count_bearish(sigs, "growth") >= 1
            and len(refs.refuted) >= len(refs.confirmed)
        ),
        "base_probability": 0.30,
        "rationale": "Growth signals are deteriorating and reflection refutes key "
                      "supporting hypotheses. Risk of an abrupt economic contraction "
                      "is elevated relative to baseline.",
        "watch": ["Initial Claims", "ISM New Orders", "Yield Curve", "Consumer Confidence"],
    },
    {
        "name": "Inflation Re-acceleration",
        "condition": lambda sigs, hyps, refs: (
            _count_bullish(sigs, "inflation") >= 1
        ),
        "base_probability": 0.25,
        "rationale": "Inflation signals suggest upward pressure. If growth remains "
                      "resilient, the Fed may need to maintain or resume tightening, "
                      "creating a stagflationary risk.",
        "watch": ["CPI MoM", "PCE Core", "Wage Growth", "Inflation Expectations"],
    },
    {
        "name": "Dollar Strength Regime",
        "condition": lambda sigs, hyps, refs: (
            _count_bullish(sigs, "liquidity") >= 1
        ),
        "base_probability": 0.45,
        "rationale": "Liquidity signals point to dollar strength, which tightens "
                      "global financial conditions and pressures emerging markets.",
        "watch": ["DXY", "Fed Funds Futures", "EM FX Indices", "Carry Trade"],
    },
    {
        "name": "Risk-On Rally",
        "condition": lambda sigs, hyps, refs: (
            _count_bullish(sigs, "credit") >= 1
            and _count_bullish(sigs, "growth") >= 1
        ),
        "base_probability": 0.40,
        "rationale": "Credit and growth signals both supportive — risk appetite "
                      "appears to be broadening. Watch for confirmation in volume "
                      "and breadth indicators.",
        "watch": ["VIX", "Credit Spreads", "HYG Flows", "Equity Breadth"],
    },
]


def _count_bullish(signals: SignalSnapshot, dimension: str) -> int:
    return sum(
        1 for s in signals.signals
        if s.dimension.lower() == dimension.lower()
        and s.direction.value == "bullish"
    )


def _count_bearish(signals: SignalSnapshot, dimension: str) -> int:
    return sum(
        1 for s in signals.signals
        if s.dimension.lower() == dimension.lower()
        and s.direction.value == "bearish"
    )


def _get_by_dimension_ci(
    hypotheses: HypothesisSet,
    dimension: str,
) -> list[HypothesisSchema]:
    dim_lower = dimension.lower()
    return [
        h for h in hypotheses.hypotheses
        if h.dimension.lower() == dim_lower
    ]


class NarrativeEngine:
    """Deterministic engine synthesizing cognitive chain + v2.0 learning data."""

    def narrate(
        self,
        signals: Optional[SignalSnapshot] = None,
        hypotheses: Optional[HypothesisSet] = None,
        reflections: Optional[ReflectionSet] = None,
        belief_records: Optional[list[BeliefRecord]] = None,
        # ── v2.0 inputs ──────────────────────────────────────────────────
        learning_summary: Optional[LearningSummary] = None,
        calibrated_confidence: Optional[CalibratedConfidenceSet] = None,
        outcome_summary: Optional[OutcomeSummary] = None,
    ) -> MacroNarrative:
        """Synthesize all cognitive + learning outputs into a MacroNarrative.

        v2.0: Learning data enriches the narrative with historical accuracy
        and calibrated confidence sections.
        """
        sigs = signals or SignalSnapshot()
        hyps = hypotheses or HypothesisSet()
        refs = reflections or ReflectionSet()
        recs = belief_records or []

        # Build dimension narratives
        liquidity_dim = self._build_dimension("liquidity", sigs, hyps, refs)
        credit_dim = self._build_dimension("credit", sigs, hyps, refs)
        growth_dim = self._build_dimension("growth", sigs, hyps, refs)
        inflation_dim = self._build_dimension("inflation", sigs, hyps, refs)

        # Build belief changes
        changes = self._detect_belief_changes(recs, hyps, refs)

        # Build risks
        risks = self._extract_risks(refs)

        # Build scenarios
        scenarios = self._generate_scenarios(sigs, hyps, refs)

        # Build action items
        actions = self._generate_action_items(hyps, refs, recs)

        # Confidence
        confidence_score = self._compute_overall_confidence(hyps, refs)

        # v2.0: Apply calibration if available
        if calibrated_confidence:
            avg_cal = calibrated_confidence.average_calibrated
            confidence_score = round((confidence_score + avg_cal) / 2, 2)

        confidence_level = self._classify_confidence(confidence_score)
        confidence_explanation = self._build_confidence_explanation(
            confidence_score, confidence_level, hyps, refs,
        )

        # Summary and story
        summary = self._build_summary(hyps, refs, learning_summary)
        macro_story = self._build_macro_story(hyps, refs, scenarios, learning_summary)

        # Today's key changes
        today_changes = self._build_today_changes(changes, sigs, refs, learning_summary)

        # Dimension string analyses
        liquidity_analysis = self._build_dimension_analysis("liquidity", sigs, hyps, refs)
        credit_analysis = self._build_dimension_analysis("credit", sigs, hyps, refs)
        growth_analysis = self._build_dimension_analysis("growth", sigs, hyps, refs)
        inflation_analysis = self._build_dimension_analysis("inflation", sigs, hyps, refs)
        risk_appetite = self._build_risk_appetite_analysis(sigs, hyps, refs)

        # Belief changes text
        belief_changes_text = self._render_belief_changes_text(changes)

        # ── v2.0: Learning sections ─────────────────────────────────────
        learning_section = self._build_what_we_learned(learning_summary, outcome_summary)
        accuracy_section = self._build_prediction_accuracy(outcome_summary)
        calibration_section = self._build_calibration_section(calibrated_confidence)

        return MacroNarrative(
            summary=summary,
            macro_story=macro_story,
            today_key_changes=today_changes,
            liquidity=liquidity_dim,
            credit=credit_dim,
            growth=growth_dim,
            inflation=inflation_dim,
            liquidity_analysis=liquidity_analysis,
            credit_analysis=credit_analysis,
            growth_analysis=growth_analysis,
            inflation_analysis=inflation_analysis,
            risk_appetite_analysis=risk_appetite,
            scenario_analysis=scenarios,
            belief_changes=changes,
            belief_changes_text=belief_changes_text,
            risks=risks,
            key_risks=[r.description for r in risks],
            action_items=actions,
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            confidence_explanation=confidence_explanation,
            confidence=confidence_score,
            generated_at=datetime.now(timezone.utc),
            # v2.0: Attach learning data as metadata for renderers
            metadata={
                "learning_summary": learning_summary.model_dump(mode="json") if learning_summary else None,
                "calibrated_confidence": calibrated_confidence.model_dump(mode="json") if calibrated_confidence else None,
                "outcome_summary": outcome_summary.model_dump(mode="json") if outcome_summary else None,
            },
        )

    # ── v2.0: What We Learned ────────────────────────────────────────────

    def _build_what_we_learned(
        self,
        learning: Optional[LearningSummary],
        outcomes: Optional[OutcomeSummary],
    ) -> str:
        """Build the 'What We Learned' section from v2.0 data."""
        if learning is None and outcomes is None:
            return ""

        parts: list[str] = ["## What We Learned\n"]

        if learning and learning.learned_patterns:
            parts.append("### Key Patterns\n")
            for i, pattern in enumerate(learning.learned_patterns, 1):
                parts.append(f"{i}. {pattern}")
            parts.append("")

        if learning and learning.best_dimension:
            parts.append("### Dimension Reliability\n")
            parts.append("| Dimension | Accuracy | Weight | Trend | Streak |")
            parts.append("|-----------|----------|--------|-------|--------|")
            for bw in learning.belief_weights:
                if bw.total_predictions > 0:
                    trend_icon = {"improving": "↑", "declining": "↓", "stable": "→"}.get(bw.accuracy_trend, "")
                    streak_str = f"+{bw.streak}" if bw.streak > 0 else str(bw.streak)
                    parts.append(
                        f"| {bw.dimension.title()} | {bw.historical_accuracy:.0%} | "
                        f"{bw.current_weight:.0%} | {trend_icon} {bw.accuracy_trend} | {streak_str} |"
                    )
            parts.append("")

        if outcomes:
            parts.append("### Global Metrics\n")
            parts.append(f"- **Hit Rate**: {outcomes.hit_rate:.0%} ({outcomes.correct_count}/{outcomes.evaluated_count} correct)")
            parts.append(f"- **Brier Score**: {outcomes.brier_score:.3f} (lower is better)")
            parts.append(f"- **Directional Accuracy**: {outcomes.directional_accuracy:.0%}")
            parts.append(f"- **Total Tracked**: {outcomes.total_predictions} predictions")
            if outcomes.pending_predictions > 0:
                parts.append(f"- **Pending**: {outcomes.pending_predictions} predictions awaiting evaluation")
            parts.append("")

        else:
            parts.append("Insufficient outcome data to generate learning summary.\n\n")

        return "\n".join(parts)

    def _build_prediction_accuracy(self, outcomes: Optional[OutcomeSummary]) -> str:
        """Build the 'Prediction Accuracy' section."""
        if outcomes is None:
            return ""

        parts: list[str] = ["## Prediction Accuracy\n"]

        acc = outcomes.hit_rate
        grade = "A" if acc >= 0.75 else "B" if acc >= 0.60 else "C" if acc >= 0.45 else "D"

        parts.append(f"**Overall Grade: {grade}** ({acc:.0%} hit rate)\n")

        parts.append(f"- Correct: {outcomes.correct_count}")
        parts.append(f"- Incorrect: {outcomes.incorrect_count}")
        parts.append(f"- Partially Correct: {outcomes.partially_correct_count}")
        parts.append(f"- Pending: {outcomes.pending_predictions}")
        parts.append(f"- Brier Score: {outcomes.brier_score:.3f}")
        parts.append("")

        if outcomes.dimension_accuracy:
            parts.append("### Per-Dimension Accuracy\n")
            parts.append("| Dimension | Correct | Total | Hit Rate | Brier |")
            parts.append("|-----------|---------|-------|----------|-------|")
            for dim, data in outcomes.dimension_accuracy.items():
                parts.append(
                    f"| {dim.title()} | {data['correct']} | {data['total']} | "
                    f"{data['hit_rate']:.0%} | {data['brier']:.3f} |"
                )
            parts.append("")

        return "\n".join(parts)

    def _build_calibration_section(
        self,
        calibrated: Optional[CalibratedConfidenceSet],
    ) -> str:
        """Build the 'Confidence Calibration' section."""
        if calibrated is None:
            return ""

        parts: list[str] = ["## Confidence Calibration\n"]

        avg_raw = calibrated.average_raw
        avg_cal = calibrated.average_calibrated
        delta = avg_cal - avg_raw

        parts.append(f"Raw (Reflection): **{avg_raw:.0%}**")
        parts.append(f"Calibrated (with history): **{avg_cal:.0%}**")
        parts.append(f"Adjustment: **{delta:+.0%}**")
        parts.append(f"Global Calibration Factor: **{calibrated.global_calibration_factor:.3f}**")
        parts.append("")

        if calibrated.calibrations:
            parts.append("### Per-Hypothesis Calibration\n")
            for c in calibrated.calibrations[:5]:
                parts.append(
                    f"- **{c.dimension.title()}**: {c.raw_confidence:.0%} → "
                    f"{c.calibrated_confidence:.0%} (Δ={c.calibration_delta:+.0%})"
                )
                if c.calibration_rationale:
                    parts.append(f"  - {c.calibration_rationale}")
            parts.append("")

        return "\n".join(parts)

    # ── Summary & Story (v2.0: enhanced with learning) ──────────────────

    def _build_summary(
        self,
        hypotheses: HypothesisSet,
        reflections: ReflectionSet,
        learning: Optional[LearningSummary] = None,
    ) -> str:
        """Build a one-line macro summary, enriched with learning data."""
        if hypotheses.count == 0:
            return "No macro hypotheses were generated in this analysis cycle."

        top = hypotheses.get_highest_confidence()
        if top is None:
            return "Unable to determine dominant macro theme."

        confirmed = len(reflections.confirmed)
        refuted = len(reflections.refuted)
        dims = ", ".join(hypotheses.dimensions_covered) if hypotheses.dimensions_covered else "macro conditions"

        base = ""
        if confirmed > refuted:
            base = (
                f"Macro analysis confirms {confirmed} hypotheses ({dims}) with "
                f"dominant theme: {top.statement[:120]}"
            )
        elif refuted > confirmed:
            base = (
                f"Macro analysis challenges prevailing views: {refuted} hypotheses refuted "
                f"across {dims}. Dominant finding: {top.statement[:120]}"
            )
        else:
            base = (
                f"Macro outlook is uncertain across {dims}. "
                f"Key open question: {top.statement[:120]}"
            )

        # v2.0: Append accuracy context
        if learning and learning.total_tracked_outcomes >= 3:
            base += (
                f" | Agent accuracy: {learning.global_hit_rate:.0%} "
                f"({learning.total_tracked_outcomes} tracked predictions)"
            )

        return base

    def _build_macro_story(
        self,
        hypotheses: HypothesisSet,
        reflections: ReflectionSet,
        scenarios: Optional[list[ScenarioProbability]] = None,
        learning: Optional[LearningSummary] = None,
    ) -> str:
        """Build 2-3 paragraph macro narrative with learning context."""
        if hypotheses.count == 0:
            return "Insufficient data to construct a macro narrative."

        paragraphs: list[str] = []

        # Paragraph 1: Overall macro picture
        top = hypotheses.get_highest_confidence()
        if top:
            dims_str = ", ".join(hypotheses.dimensions_covered) if hypotheses.dimensions_covered else "macro"
            paras = [
                f"The current {dims_str} environment presents a complex picture. "
                f"{top.statement} Evidence strength is assessed at "
                f"{top.confidence:.0%} confidence, "
                f"supported by {len(top.supporting_evidence)} corroborating observations "
                f"and challenged by {len(top.contradicting_evidence)} contradictory signals.",
            ]
            if scenarios:
                dominant = max(scenarios, key=lambda s: s.probability)
                paras.append(
                    f"The most probable macro scenario is \"{dominant.name}\" "
                    f"({dominant.probability:.0%} probability). {dominant.rationale}"
                )
            paragraphs.append(" ".join(paras))

        # Paragraph 2: Dimension walkthrough
        dim_parts: list[str] = []
        for dim_name in _DIMENSION_NAMES:
            dim_hyps = _get_by_dimension_ci(hypotheses, dim_name)
            if not dim_hyps:
                continue
            best = max(dim_hyps, key=lambda h: h.confidence)
            dim_parts.append(
                f"In the {dim_name} dimension, {best.statement.lower().rstrip('.')} "
                f"(confidence: {best.confidence:.0%})."
            )
        if dim_parts:
            paragraphs.append(" ".join(dim_parts))

        # Paragraph 3: Reflection synthesis
        if reflections.count > 0:
            confirmed_pct = len(reflections.confirmed) / reflections.count * 100 if reflections.count else 0
            refuted_pct = len(reflections.refuted) / reflections.count * 100 if reflections.count else 0
            uncertain_pct = len(reflections.uncertain) / reflections.count * 100 if reflections.count else 0
            paragraphs.append(
                f"After belief review: {confirmed_pct:.0f}% of hypotheses confirmed, "
                f"{refuted_pct:.0f}% refuted, and {uncertain_pct:.0f}% remain uncertain. "
                f"Overall conviction is {'high' if confirmed_pct > 60 else 'moderate' if confirmed_pct > 30 else 'low'} "
                f"based on the weight of corroborating evidence."
            )

        # v2.0: Paragraph 4 — Learning context
        if learning and learning.total_tracked_outcomes >= 3:
            trend = learning.improvement_trend
            trend_text = {
                "improving": "The Agent's predictive accuracy has been improving over recent cycles.",
                "declining": "The Agent's predictive accuracy has declined recently — increased caution is warranted.",
                "stable": "The Agent's predictive accuracy has been stable.",
            }.get(trend, "")

            if learning.best_dimension:
                trend_text += (
                    f" The most reliable dimension is {learning.best_dimension.title()} "
                    f"({learning.get_accuracy(learning.best_dimension):.0%} accuracy), "
                    f"while {learning.worst_dimension.title()} has been least reliable "
                    f"({learning.get_accuracy(learning.worst_dimension):.0%} accuracy)."
                )
            paragraphs.append(trend_text)

        return "\n\n".join(paragraphs)

    def _build_today_changes(
        self,
        belief_changes: list[BeliefChangeNote],
        signals: SignalSnapshot,
        reflections: ReflectionSet,
        learning: Optional[LearningSummary] = None,
    ) -> str:
        """Build the 'Today's Key Changes' section with v2.0 learning context."""
        parts: list[str] = []

        # What changed
        if belief_changes:
            changed = [bc for bc in belief_changes if bc.direction != "unchanged"]
            if changed:
                items = []
                for bc in changed[:3]:
                    dim = bc.dimension or "macro"
                    arrow = {"increased": "↑", "decreased": "↓", "reversed": "⇄", "new": "🆕"}.get(bc.direction, "→")
                    items.append(
                        f"{arrow} **{dim.title()}**: {bc.hypothesis_statement[:100]} "
                        f"({bc.previous_confidence:.0%} → {bc.current_confidence:.0%})"
                    )
                parts.append("### What Changed Today\n" + "\n".join(items))
        else:
            parts.append(
                "### What Changed Today\n"
                "No significant belief changes detected. The macro picture is stable "
                "relative to the prior cycle."
            )

        # Why it matters
        if reflections.count > 0:
            confirmed = len(reflections.confirmed)
            refuted = len(reflections.refuted)
            parts.append(
                f"\n### Why It Matters\n"
                f"Belief review results: {confirmed} hypotheses confirmed, "
                f"{refuted} refuted. "
                + (
                    "Conviction in the current macro view is strengthening."
                    if confirmed > refuted
                    else "The macro view faces significant challenges."
                    if refuted > confirmed
                    else "The macro outlook remains uncertain with mixed evidence."
                )
            )

        # What to watch
        active_indicators = [s.indicator for s in signals.signals[:5]]
        if active_indicators:
            parts.append(
                f"\n### What to Watch Next\n"
                f"Key indicators to monitor: {', '.join(active_indicators)}. "
                f"Watch for signal direction changes that could trigger "
                f"hypothesis revision in the next cycle."
            )

        # v2.0: Learning context
        if learning and learning.total_tracked_outcomes >= 3:
            parts.append(
                f"\n### Historical Context\n"
                f"Agent track record: {learning.global_hit_rate:.0%} accuracy "
                f"across {learning.total_tracked_outcomes} tracked predictions. "
                f"Best dimension: {learning.best_dimension.title() if learning.best_dimension else 'N/A'}."
            )

        return "\n".join(parts) if parts else "No key changes identified in this cycle."

    # ── Dimension Builder ─────────────────────────────────────────────────
    # (Reused from v1.0 — no changes needed)

    def _build_dimension(self, dim, signals, hypotheses, reflections):
        dim_signals = [s for s in signals.signals if s.dimension.lower() == dim.lower()]
        dim_hyps = _get_by_dimension_ci(hypotheses, dim)
        key_signal_descs = [
            f"[{s.direction.value.upper()}] {s.indicator}: {s.evidence[0].interpretation if s.evidence else f'confidence {s.confidence:.0%}'}"
            for s in dim_signals[:5]
        ]
        if dim_hyps:
            best = max(dim_hyps, key=lambda h: h.confidence)
            hyp_summary = best.statement
            dim_conf = best.confidence
        else:
            hyp_summary = f"No {dim}-specific hypotheses generated."
            dim_conf = 0.3
        for report in reflections.reports:
            for hyp in dim_hyps:
                if report.hypothesis_id == hyp.hypothesis_id:
                    dim_conf = report.updated_confidence
                    break
        if dim_signals:
            bullish = sum(1 for s in dim_signals if s.direction.value == "bullish")
            bearish = sum(1 for s in dim_signals if s.direction.value == "bearish")
            bias = "accommodative / supportive" if bullish > bearish else "tightening / restrictive" if bearish > bullish else "neutral / balanced"
            summary = f"{dim.title()} conditions are {bias} ({len(dim_signals)} signals: {bullish}B/{bearish}S). Confidence: {dim_conf:.0%}."
        else:
            summary = f"No {dim} signals available for assessment."
        analysis = self._build_dimension_analysis(dim, signals, hypotheses, reflections)
        return DimensionNarrative(dimension=dim, summary=summary, analysis=analysis, key_signals=key_signal_descs, hypothesis_summary=hyp_summary, confidence=dim_conf)

    def _build_dimension_analysis(self, dim, signals, hypotheses, reflections):
        dim_signals = [s for s in signals.signals if s.dimension.lower() == dim.lower()]
        dim_hyps = _get_by_dimension_ci(hypotheses, dim)
        if not dim_signals and not dim_hyps:
            return f"No data available for {dim} analysis in this cycle."
        parts = []
        if dim_signals:
            signal_parts = [f"{s.indicator} signals {s.direction.value.upper()} ({s.confidence:.0%} confidence)" for s in dim_signals]
            parts.append(f"**Signal Assessment**: {', '.join(signal_parts)}. ")
            bullish = sum(1 for s in dim_signals if s.direction.value == "bullish")
            bearish = sum(1 for s in dim_signals if s.direction.value == "bearish")
            if bullish > bearish:
                parts.append(f"The {dim} signal bias is bullish/expansionary. ")
            elif bearish > bullish:
                parts.append(f"The {dim} signal bias is bearish/contractionary. ")
            else:
                parts.append(f"The {dim} signal bias is neutral. ")
        if dim_hyps:
            best = max(dim_hyps, key=lambda h: h.confidence)
            parts.append(f"**Dominant Hypothesis**: {best.statement} ({len(best.supporting_evidence)} supporting / {len(best.contradicting_evidence)} contradicting evidence items). ")
        relevant_reports = [r for r in reflections.reports for h in dim_hyps if r.hypothesis_id == h.hypothesis_id]
        if relevant_reports:
            confirmed = sum(1 for r in relevant_reports if r.verdict.value == "confirmed")
            refuted = sum(1 for r in relevant_reports if r.verdict.value == "refuted")
            uncertain = sum(1 for r in relevant_reports if r.verdict.value == "uncertain")
            parts.append(f"**Belief Review**: {confirmed} confirmed, {refuted} refuted, {uncertain} uncertain across {len(relevant_reports)} reviews.")
        return "".join(parts)

    def _build_risk_appetite_analysis(self, signals, hypotheses, reflections):
        risk_signals = [s for s in signals.signals if s.dimension.lower() in ("risk_appetite", "credit")]
        risk_hyps = _get_by_dimension_ci(hypotheses, "Risk_Appetite")
        parts = []
        if risk_signals:
            signal_parts = [f"{s.indicator} {s.direction.value.upper()}" for s in risk_signals]
            parts.append(f"**Risk Signals**: {', '.join(signal_parts)}. ")
        if risk_hyps:
            best = max(risk_hyps, key=lambda h: h.confidence)
            parts.append(f"**Risk Outlook**: {best.statement}")
        if not parts:
            return "Insufficient data for risk appetite assessment."
        bullish = sum(1 for s in risk_signals if s.direction.value == "bullish")
        bearish = sum(1 for s in risk_signals if s.direction.value == "bearish")
        if bullish > bearish:
            parts.append(" Overall risk appetite appears elevated / risk-on.")
        elif bearish > bullish:
            parts.append(" Overall risk appetite appears subdued / risk-off.")
        else:
            parts.append(" Risk appetite signals are mixed.")
        return "".join(parts)

    def _generate_scenarios(self, signals, hypotheses, reflections):
        scenarios = []
        for tmpl in _SCENARIO_TEMPLATES:
            try:
                matches = tmpl["condition"](signals, hypotheses, reflections)
            except Exception:
                matches = False
            if not matches:
                prob = max(0.05, tmpl["base_probability"] * 0.3)
                supporting, contradicting = [], [f"Current signals do not match {tmpl['name']} pattern"]
            else:
                prob = tmpl["base_probability"]
                if reflections.count > 0:
                    confirm_ratio = len(reflections.confirmed) / reflections.count
                    prob = prob * (0.8 + 0.4 * confirm_ratio)
                supporting = [f"Signal pattern matches {tmpl['name']} conditions"]
                contradicting = []
            prob = round(max(0.05, min(0.95, prob)), 2)
            scenarios.append(ScenarioProbability(name=tmpl["name"], probability=prob, rationale=tmpl["rationale"], supporting_signals=supporting, contradicting_signals=contradicting, key_indicators_to_watch=tmpl["watch"]))
        if scenarios and all(s.probability < 0.30 for s in scenarios):
            best = max(scenarios, key=lambda s: s.probability)
            best.probability = min(0.95, best.probability * 2.0)
        return scenarios

    def _detect_belief_changes(self, records, hypotheses, reflections):
        changes = []
        if not records:
            for hyp in hypotheses.hypotheses:
                changes.append(BeliefChangeNote(hypothesis_statement=hyp.statement, previous_confidence=0.0, current_confidence=hyp.confidence, direction="new", note=f"First belief formed for {hyp.dimension} dimension.", prior_summary="No prior belief", dimension=hyp.dimension))
            return changes
        prior_by_dim = {}
        for r in records:
            dim_key = r.dimension.lower()
            if dim_key not in prior_by_dim or r.timestamp > prior_by_dim[dim_key].timestamp:
                prior_by_dim[dim_key] = r
        for hyp in hypotheses.hypotheses:
            dim_key = hyp.dimension.lower() if hasattr(hyp, 'dimension') else "unknown"
            prior = prior_by_dim.get(dim_key)
            if prior is None:
                changes.append(BeliefChangeNote(hypothesis_statement=hyp.statement, previous_confidence=0.0, current_confidence=hyp.confidence, direction="new", note=f"First belief formed for {hyp.dimension} dimension.", prior_summary="No prior belief", dimension=hyp.dimension))
                continue
            delta = hyp.confidence - prior.confidence
            direction = "unchanged" if abs(delta) < 0.05 else "increased" if delta > 0 else "decreased"
            prior_summary = f"Prior: {prior.statement[:120]} (direction={prior.direction.value}, confidence={prior.confidence:.0%})"
            if hasattr(hyp, 'direction') and hasattr(prior, 'direction') and hyp.direction != prior.direction:
                direction = "reversed"
                note = f"Direction reversed from {prior.direction.value} to {hyp.direction.value} in {hyp.dimension}. Prior: \"{prior.statement[:100]}\""
            elif direction == "increased":
                note = f"Confidence strengthened: {prior.confidence:.0%} → {hyp.confidence:.0%}. Prior evidence: {prior.evidence_summary}"
            elif direction == "decreased":
                note = f"Confidence weakened: {prior.confidence:.0%} → {hyp.confidence:.0%}. Review: {prior.review_summary[:100] if prior.review_summary else 'No review available'}"
            else:
                note = f"Belief stable at {hyp.confidence:.0%} confidence."
            changes.append(BeliefChangeNote(hypothesis_statement=hyp.statement, previous_confidence=prior.confidence, current_confidence=hyp.confidence, direction=direction, note=note, prior_summary=prior_summary, dimension=hyp.dimension))
        return changes

    def _render_belief_changes_text(self, changes):
        if not changes:
            return "No belief changes detected in this cycle."
        lines = []
        for bc in changes:
            if bc.direction == "unchanged":
                continue
            arrow = {"increased": "↑ Strengthened", "decreased": "↓ Weakened", "reversed": "⇄ Reversed", "new": "🆕 New"}.get(bc.direction, "→")
            dim_label = f"[{bc.dimension}] " if bc.dimension else ""
            lines.append(f"{arrow}: {dim_label}{bc.hypothesis_statement[:120]}\n  {bc.previous_confidence:.0%} → {bc.current_confidence:.0%} | {bc.note}")
        return "\n".join(lines) if lines else "All beliefs are stable (no significant changes)."

    def _extract_risks(self, reflections):
        risks = []
        for report in reflections.reports:
            if report.verdict.value == "refuted":
                risks.append(RiskItem(category="hypothesis_refuted", description=f"Hypothesis '{report.statement[:120]}' was refuted after belief review. Original confidence: {report.original_confidence:.0%}.", severity="medium", related_hypothesis=report.hypothesis_id))
            for finding in report.findings:
                if finding.severity.value in ("critical", "major"):
                    risks.append(RiskItem(category=finding.type, description=finding.description, severity="high" if finding.severity.value == "critical" else "medium", related_hypothesis=report.hypothesis_id))
            if report.evidence_sufficiency == "low":
                risks.append(RiskItem(category="insufficient_evidence", description=f"Insufficient evidence for hypothesis: '{report.statement[:120]}'. Assessment may be unreliable.", severity="high", related_hypothesis=report.hypothesis_id))
            if report.evidence_consistency == "conflicting":
                risks.append(RiskItem(category="conflicting_evidence", description=f"Conflicting evidence detected for: '{report.statement[:120]}'. Directional bias may be unreliable.", severity="medium", related_hypothesis=report.hypothesis_id))
        if not risks:
            risks.append(RiskItem(category="no_risks_identified", description="No significant risks identified in the current analysis cycle.", severity="low"))
        return risks

    def _generate_action_items(self, hypotheses, reflections, belief_records=None):
        items = []
        if belief_records:
            for rec in belief_records:
                if rec.is_reversal:
                    items.append(f"Reassess: Belief in {rec.dimension} reversed from {rec.transition.value}. Review '{rec.statement[:80]}' with additional data before committing.")
        for report in reflections.uncertain[:3]:
            items.append(f"Monitor: Hypothesis '{report.statement[:80]}' is uncertain — seek additional evidence before acting.")
        for report in reflections.confirmed:
            if report.updated_confidence > 0.7:
                items.append(f"Act: Hypothesis '{report.statement[:80]}' is confirmed with high confidence ({report.updated_confidence:.0%}). Consider incorporating into positioning framework.")
        if hypotheses.count == 0:
            items.append("Collect more data to enable hypothesis generation.")
        if reflections.count == 0:
            items.append("Complete belief review cycle before drawing conclusions.")
        if not items:
            for hyp in hypotheses.hypotheses[:3]:
                items.append(f"Continue monitoring {hyp.dimension}: '{hyp.statement[:60]}' (confidence: {hyp.confidence:.0%})")
        return items

    def _compute_overall_confidence(self, hypotheses, reflections):
        if hypotheses.count == 0:
            return 0.1
        base = sum(h.confidence for h in hypotheses.hypotheses) / hypotheses.count
        if reflections.count > 0:
            confirmed = len(reflections.confirmed)
            refuted = len(reflections.refuted)
            adjustment = (confirmed - refuted) / reflections.count * 0.15
            base = max(0.0, min(1.0, base + adjustment))
        return round(base, 2)

    @staticmethod
    def _classify_confidence(score):
        if score >= 0.70:
            return ConfidenceLevel.HIGH
        elif score >= 0.40:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    def _build_confidence_explanation(self, score, level, hypotheses, reflections):
        verdict_breakdown = {"confirmed": len(reflections.confirmed), "refuted": len(reflections.refuted), "uncertain": len(reflections.uncertain), "total": reflections.count}
        if level == ConfidenceLevel.LOW:
            reasons = []
            if verdict_breakdown["refuted"] > verdict_breakdown["confirmed"]:
                reasons.append(f"More hypotheses were refuted ({verdict_breakdown['refuted']}) than confirmed ({verdict_breakdown['confirmed']}), indicating the current macro view has weak evidential support.")
            if verdict_breakdown["uncertain"] > 0:
                reasons.append(f"{verdict_breakdown['uncertain']} hypotheses remain uncertain due to insufficient or conflicting evidence.")
            if hypotheses.count == 0:
                reasons.append("No hypotheses were generated — the system lacks sufficient data for meaningful analysis.")
            if not reasons:
                reasons.append("Overall evidence quality is insufficient to support high-confidence conclusions.")
            why_low = " ".join(reasons)
        else:
            why_low = ""
        supporting_parts = [f"Confirmed: \"{report.statement[:100]}\" (confidence adjusted from {report.original_confidence:.0%} to {report.updated_confidence:.0%})" for report in reflections.confirmed[:2]]
        supporting_summary = "; ".join(supporting_parts) if supporting_parts else "No strongly confirmed hypotheses."
        contradicting_parts = [f"Refuted: \"{report.statement[:100]}\" (original confidence {report.original_confidence:.0%} → {report.updated_confidence:.0%} after review)" for report in reflections.refuted[:2]]
        contradicting_summary = "; ".join(contradicting_parts) if contradicting_parts else "No refuted hypotheses."
        all_findings = []
        for report in reflections.reports:
            all_findings.extend(report.findings)
        findings_summary = "; ".join([f.description[:100] for f in all_findings[:4]]) if all_findings else "No critical findings from belief review."
        return ConfidenceExplanation(level=level, score=score, why_low=why_low, supporting_evidence_summary=supporting_summary, contradicting_evidence_summary=contradicting_summary, reflection_findings_summary=findings_summary, hypothesis_verdict_breakdown=verdict_breakdown)
