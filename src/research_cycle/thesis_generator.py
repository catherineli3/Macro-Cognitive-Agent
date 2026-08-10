"""Thesis Generator — upgrades Hypothesis into Research Thesis (Milestone D, D4).

Converts a Hypothesis (raw view) into a Research Thesis (structured output) by:
    1. Synthesizing core_belief from framework + hypothesis
    2. Deriving transmission_chain from framework principles
    3. Collecting evidence from macro_snapshot signals
    4. Generating counter_arguments from competing framework views
    5. Defining falsifiable invalidation_conditions
    6. Computing confidence = framework_confidence * hypothesis_confidence
"""

from __future__ import annotations

from typing import Any

from src.schemas.research import ResearchFramework, ResearchPrinciple, PrincipleStrength
from src.schemas.research_thesis import ResearchThesis, ThesisStatus
from src.schemas.macro_snapshot import MacroSnapshot
from src.schemas.hypothesis import HypothesisSchema, HypothesisSet
from src.research_cycle.framework_selector import FrameworkSelection
from src.shared.logging import get_logger

logger = get_logger(__name__)


class ThesisGenerator:
    """Upgrades hypotheses into structured Research Theses.

    The key difference from raw Hypothesis:
        - Thesis includes transmission chain (causal mechanism)
        - Thesis includes counter-arguments (what could go wrong)
        - Thesis includes invalidation conditions (falsifiable)
        - Thesis is framework-grounded (not just signal-driven)
    """

    def __init__(self, evolution_pipeline=None):
        """Initialize with an optional EvolutionPipeline reference.

        Args:
            evolution_pipeline: Provides access to principles, frameworks,
                                and the regime gate.
        """
        self._evolution = evolution_pipeline

    def set_evolution_pipeline(self, pipeline) -> None:
        self._evolution = pipeline

    # ── Main Entry ──────────────────────────────────────────────────────

    def generate(
        self,
        selection: FrameworkSelection,
        macro_snapshot: MacroSnapshot,
        hypotheses: HypothesisSet | None = None,
        extra_evidence: list[str] | None = None,
        narratives: list | None = None,     # V3.1
        beliefs: list | None = None,         # V3.1
        judgments: Any = None,                # V3.2: JudgmentOutput
    ) -> ResearchThesis:
        """Generate a Research Thesis from framework selection and data.

        Args:
            selection: FrameworkSelection with ranked active frameworks
            macro_snapshot: Current market snapshot
            hypotheses: Optional hypothesis set from competition engine
            extra_evidence: Additional evidence strings
            narratives: Narrative list from NarrativeDetector (V3.1)
            beliefs: ResearchBelief list from BeliefEngine (V3.1)
            judgments: JudgmentOutput from ResearchJudgmentEngine (V3.2)

        Returns:
            A fully-formed ResearchThesis ready for activation
        """
        thesis = ResearchThesis()

        # ── Step 1: Synthesize core belief ──────────────────────────
        thesis.core_belief = self._synthesize_core_belief(
            selection, hypotheses, macro_snapshot,
            narratives=narratives,
            beliefs=beliefs,
            judgments=judgments,
        )
        thesis.regime_label = macro_snapshot.regime_label

        # ── Step 2: Derive transmission chain ───────────────────────
        thesis.transmission_chain = self._derive_transmission_chain(
            selection, macro_snapshot,
        )

        # ── Step 3: Collect evidence ────────────────────────────────
        thesis.evidence = self._collect_evidence(
            selection, macro_snapshot, extra_evidence,
            narratives=narratives,
            beliefs=beliefs,
            judgments=judgments,
        )

        # ── Step 4: Generate counter arguments ──────────────────────
        thesis.counter_arguments = self._generate_counter_arguments(
            selection, macro_snapshot, judgments=judgments,
        )

        # ── Step 5: Define invalidation conditions ──────────────────
        thesis.invalidation_conditions = self._define_invalidation_conditions(
            selection, macro_snapshot, judgments=judgments,
        )

        # ── Step 6: Set confidence ──────────────────────────────────
        thesis.confidence = self._compute_confidence(selection, hypotheses, judgments)

        # ── Step 7: Set expected window ─────────────────────────────
        thesis.expected_window = self._determine_window(selection, macro_snapshot)

        # ── Step 8: Set title ───────────────────────────────────────
        thesis.title = self._generate_title(thesis)

        # ── Step 9: Set provenance ──────────────────────────────────
        thesis.framework_used = [fw.framework_id for fw, _ in selection.ranked[:3]]
        if hypotheses:
            thesis.generated_hypotheses = [h.hypothesis_id for h in hypotheses.hypotheses]
        thesis.source_principles = self._get_principle_ids(selection)

        # ── Step 10: Validate well-formedness ────────────────────────
        if thesis.is_well_formed:
            thesis.status = ThesisStatus.DRAFT
        else:
            logger.warning("Thesis not well-formed: title=%s, chain=%d, evidence=%d",
                           bool(thesis.title), len(thesis.transmission_chain),
                           len(thesis.evidence))

        logger.info("Generated thesis '%s' confidence=%.2f regime=%s",
                     thesis.title, thesis.confidence, thesis.regime_label)
        return thesis

    # ── Synthesis Steps ────────────────────────────────────────────────

    def _synthesize_core_belief(
        self,
        selection: FrameworkSelection,
        hypotheses: HypothesisSet | None,
        macro_snapshot: MacroSnapshot,
        narratives: list | None = None,
        beliefs: list | None = None,
        judgments: Any = None,
    ) -> str:
        """Synthesize the core causal belief.

        Priority:
            1. V3.2 Research Judgment conviction
            2. V3.1 ResearchBelief statements
            3. V3.1 Narrative-driven belief
            4. Primary framework thesis summary
            5. Top hypothesis belief statement
            6. Regime-based inference
        """
        parts = []

        # ── V3.2: Research Judgment convictions (highest priority) ──
        if judgments and hasattr(judgments, 'judgments'):
            judge_list = sorted(
                judgments.judgments, key=lambda j: j.confidence, reverse=True
            )[:2]
            for j in judge_list:
                parts.append(f"I believe: {j.conviction_statement} ({j.confidence:.0%})")

        # ── V3.1: Narrative-derived beliefs ─────────────────────────
        if beliefs:
            top_beliefs = sorted(
                beliefs, key=lambda b: getattr(b, 'confidence', 0), reverse=True
            )[:3]
            for b in top_beliefs:
                title = getattr(b, 'title', '') or getattr(b, 'belief_title', '')
                conf = getattr(b, 'confidence', 0)
                if title:
                    parts.append(f"Belief[{conf:.0%}]: {title}")
        if narratives:
            top_narr = sorted(
                narratives, key=lambda n: getattr(n, 'composite_score', 0), reverse=True
            )[:2]
            for n in top_narr:
                title = getattr(n, 'title', '')
                if title and not any(title.lower() in p.lower() for p in parts):
                    parts.append(f"Narrative: {title}")

        # Framework thesis provides the structural view
        if selection.primary_framework and selection.primary_framework.thesis:
            fw_thesis = selection.primary_framework.thesis[:200]
            parts.append(fw_thesis)

        # Hypothesis provides the directional view
        if hypotheses and hypotheses.hypotheses:
            top_h = hypotheses.hypotheses[0]
            belief = getattr(top_h, 'belief_summary', None) or getattr(top_h, 'description', None)
            if belief:
                parts.append(str(belief)[:150])

        # Fallback: regime-based inference
        if not parts:
            regime = macro_snapshot.regime
            if regime:
                parts.append(
                    f"Current {macro_snapshot.regime_label} regime "
                    f"is the dominant macro force driving asset allocation."
                )

        belief = ". ".join(parts)
        if not belief.endswith("."):
            belief += "."
        return belief

    def _derive_transmission_chain(
        self,
        selection: FrameworkSelection,
        macro_snapshot: MacroSnapshot,
    ) -> list[str]:
        """Derive the causal transmission chain.

        Traces: Regime → Condition → Market Mechanism → Asset Impact

        Uses framework principles' causal statements to build the chain.
        """
        chain = []

        # Start with regime condition
        regime = macro_snapshot.regime
        if regime:
            chain.append(
                f"Regime: {regime.monetary_policy.title()} monetary policy, "
                f"{regime.growth} growth, {regime.inflation} inflation"
            )

        # Add framework principle chains
        principles = self._get_principles(selection)
        for p in principles[:4]:
            if p.statement and p.statement not in " ".join(chain):
                chain.append(p.statement[:120])

        # Add market mechanism
        if macro_snapshot.dominant_theme:
            chain.append(f"Market theme: {macro_snapshot.dominant_theme}")

        # Add asset impact (inferred from regime)
        asset_impact = self._infer_asset_impact(macro_snapshot)
        if asset_impact:
            chain.append(asset_impact)

        return chain

    @staticmethod
    def _infer_asset_impact(snapshot: MacroSnapshot) -> str:
        """Infer likely asset impact from regime."""
        regime = snapshot.regime
        if not regime:
            return ""

        if regime.monetary_policy == "easing":
            if regime.growth in ("accelerating", "stable"):
                return "Positive for risk assets (equities, credit, EM)"
            else:
                return "Mixed: duration positive, credit cautious"
        elif regime.monetary_policy == "tightening":
            if regime.inflation == "rising":
                return "Negative for duration, commodities favored"
            else:
                return "Defensive positioning across risk assets"
        return ""

    def _collect_evidence(
        self,
        selection: FrameworkSelection,
        macro_snapshot: MacroSnapshot,
        extra_evidence: list[str] | None = None,
        narratives: list | None = None,
        beliefs: list | None = None,
        judgments: Any = None,
    ) -> list[str]:
        """Collect supporting evidence from all available sources."""
        evidence: list[str] = []

        # From macro_snapshot signals
        for signal in macro_snapshot.signals[:5]:
            if hasattr(signal, "indicator") and hasattr(signal, "direction"):
                direction = signal.direction.value if hasattr(signal.direction, "value") else str(signal.direction)
                evidence.append(f"{signal.indicator}: {direction} (confidence: {getattr(signal, 'confidence', 'N/A')})")

        # From framework principles
        principles = self._get_principles(selection)
        for p in principles[:3]:
            if p.statement:
                short = p.statement[:100]
                if short not in str(evidence):
                    evidence.append(f"Principle: {short} (accuracy={p.evidence.accuracy:.0%})")

        # From market data
        if macro_snapshot.market.indicators:
            items = list(macro_snapshot.market.indicators.items())[:3]
            for k, v in items:
                evidence.append(f"{k}: {v:.2f}")

        # Extra evidence
        if extra_evidence:
            evidence.extend(extra_evidence)

        # ── V3.2: Judgment reasoning chains ─────────────────────────
        if judgments and hasattr(judgments, 'judgments'):
            for j in judgments.judgments[:2]:
                for reason in j.reasoning_chain[:2]:
                    evidence.append(f"Judgment reason: {reason[:120]}")

        # ── V3.1: Narrative + Belief evidence ──────────────────────
        if narratives:
            for n in narratives[:2]:
                title = getattr(n, 'title', '')
                if title:
                    evidence.append(f"Narrative: {title}")
        if beliefs:
            for b in beliefs[:2]:
                title = getattr(b, 'title', '') or getattr(b, 'belief_title', '')
                conf = getattr(b, 'confidence', 0)
                if title:
                    evidence.append(f"Belief[{conf:.0%}]: {title}")

        # Deduplicate and limit
        seen = set()
        unique = []
        for e in evidence:
            key = e[:50].lower()
            if key not in seen:
                seen.add(key)
                unique.append(e)

        return unique[:7]  # Max 7 pieces of evidence

    def _generate_counter_arguments(
        self,
        selection: FrameworkSelection,
        macro_snapshot: MacroSnapshot,
        judgments: Any = None,
    ) -> list[str]:
        """Generate counter-arguments from competing frameworks and judgments.

        V3.2: Includes competing beliefs from graph + contradicting evidence.
        What would the SECOND-ranked framework argue?
        """
        counter_args = []

        # ── V3.2: Competing beliefs from judgment graph ─────────────
        if judgments and hasattr(judgments, 'judgments'):
            for j in judgments.judgments:
                for comp_title in j.competing_beliefs:
                    entry = f"Competing belief: {comp_title}"
                    if entry not in counter_args:
                        counter_args.append(entry)
                for contra_title in j.contradicting_beliefs:
                    entry = f"Contradicts: {contra_title}"
                    if entry not in counter_args:
                        counter_args.append(entry)

        # Counter from second-ranked framework
        if len(selection.ranked) > 1:
            second_fw = selection.ranked[1][0]
            if second_fw.thesis:
                counter_args.append(
                    f"Competing view ({second_fw.name}): {second_fw.thesis[:150]}"
                )

        # Counter from regime risk
        regime = macro_snapshot.regime
        if regime:
            if regime.monetary_policy == "easing":
                counter_args.append(
                    "Risk: If inflation re-accelerates, easing may stall or reverse, "
                    "invalidating the liquidity-driven thesis."
                )
            elif regime.monetary_policy == "tightening":
                counter_args.append(
                    "Risk: Tightening may overshoot, causing a financial accident "
                    "that forces an unexpected pivot."
                )
            if regime.volatility == "high":
                counter_args.append(
                    "Risk: High volatility regime implies unstable correlations; "
                    "historical transmission patterns may not hold."
                )

        # Counter from data
        if macro_snapshot.market.indicators:
            # Check for conflicting signals
            dxy = macro_snapshot.market.get("dxy", 0)
            vix = macro_snapshot.market.get("vix", 0)
            if vix > 25:
                counter_args.append(
                    "Risk: Elevated VIX (>25) indicates stress that may override "
                    "fundamental macro logic."
                )

        return counter_args[:3]

    def _define_invalidation_conditions(
        self,
        selection: FrameworkSelection,
        macro_snapshot: MacroSnapshot,
        judgments: Any = None,
    ) -> list[str]:
        """Define falsifiable invalidation conditions.

        V3.2: Prioritizes judgment falsification conditions (from
        ResearchJudgmentEngine) — specific, observable, domain-aware.

        These are specific, observable conditions that would prove the thesis wrong.
        """
        conditions = []

        # ── V3.2: Falsification conditions from ResearchJudgment ────
        if judgments and hasattr(judgments, 'judgments'):
            for j in judgments.judgments[:3]:
                for cond in j.falsification_conditions[:2]:
                    conditions.append(f"{cond}")
            if conditions:
                # V3.2 judgments provide best falsification — return them
                return conditions[:6]

        # Fallback: regime/market-based conditions
        regime = macro_snapshot.regime
        market = macro_snapshot.market

        # From regime
        if regime:
            if regime.monetary_policy == "easing":
                conditions.append("Fed signals rate hike or ends balance sheet reduction")
            elif regime.monetary_policy == "tightening":
                conditions.append("Fed cuts rates (not just pauses)")
            if regime.inflation == "rising":
                conditions.append("CPI prints below 2% for two consecutive months")
            elif regime.inflation == "falling":
                conditions.append("CPI re-accelerates above 3%")

        # From market data thresholds
        us10y = market.get("us10y", 0)
        if us10y:
            conditions.append(f"10Y Treasury yield exceeds {us10y + 0.5:.1f}%")

        vix = market.get("vix", 0)
        if vix:
            conditions.append(f"VIX spikes above {max(30, vix * 1.5):.0f} (sustained >5 days)")

        spx = market.get("spx", 0)
        if spx:
            conditions.append(f"S&P 500 drops below {spx * 0.9:.0f} (10% drawdown)")

        dxy = market.get("dxy", 0)
        if dxy:
            conditions.append(f"DXY breaks above {dxy * 1.03:.1f} (3% rally)")

        # From framework principles
        principles = self._get_principles(selection)
        for p in principles[:2]:
            if p.preconditions:
                for k, v in p.preconditions.items():
                    conditions.append(f"Principle precondition violated: {k} != {v}")

        return conditions[:5]  # Max 5 conditions

    def _compute_confidence(
        self,
        selection: FrameworkSelection,
        hypotheses: HypothesisSet | None,
        judgments: Any = None,
    ) -> float:
        """Compute thesis confidence.

        V3.2 formula:
            Avg(Judgment confidence) × 0.5
            + Framework confidence × 0.3
            + Hypothesis confidence × 0.2
        """
        # ── V3.2: Judgment confidence (primary) ────────────────────
        judgment_conf = 0.5
        if judgments and hasattr(judgments, 'judgments') and judgments.judgments:
            confs = [j.confidence for j in judgments.judgments]
            judgment_conf = sum(confs) / len(confs)

        # Framework confidence
        fw_conf = 0.5  # Default
        if selection.primary_framework:
            acc = selection.primary_framework.accuracy_trajectory
            if acc:
                fw_conf = sum(acc[-5:]) / min(len(acc), 5)

        # Hypothesis confidence
        hyp_conf = 0.5  # Default
        if hypotheses and hypotheses.hypotheses:
            confs = [h.confidence for h in hypotheses.hypotheses if h.confidence]
            if confs:
                hyp_conf = sum(confs) / len(confs)

        # V3.2: Weighted confidence formula
        confidence = judgment_conf * 0.5 + fw_conf * 0.3 + hyp_conf * 0.2
        return round(max(0.1, min(0.95, confidence)), 2)

    def _determine_window(
        self,
        selection: FrameworkSelection,
        macro_snapshot: MacroSnapshot,
    ) -> str:
        """Determine the expected validation window based on regime and thesis scope."""
        regime = macro_snapshot.regime
        if not regime:
            return "30-90 days"

        # Faster-moving regimes = shorter window
        if regime.volatility == "high":
            return "14-45 days"
        elif regime.monetary_policy in ("tightening", "easing"):
            return "30-90 days"
        elif regime.growth in ("decelerating", "contracting"):
            return "60-120 days"
        else:
            return "30-90 days"

    def _generate_title(self, thesis: ResearchThesis) -> str:
        """Generate a concise one-line title for the thesis."""
        if not thesis.core_belief:
            return "Untitled Thesis"

        # Extract first sentence or key claim
        belief = thesis.core_belief.strip()
        # Take up to 100 chars for title
        if len(belief) > 100:
            # Try to cut at first period or natural break
            cut = belief[:100].rfind(".")
            if cut > 40:
                belief = belief[:cut].strip()
            else:
                belief = belief[:97].strip() + "..."

        # Prefix with regime context
        if thesis.regime_label:
            return f"{thesis.regime_label}: {belief}"
        return belief

    # ── Helpers ─────────────────────────────────────────────────────────

    def _get_principles(self, selection: FrameworkSelection) -> list[ResearchPrinciple]:
        """Get active principles linked to the selected frameworks."""
        principles: list[ResearchPrinciple] = []
        if self._evolution:
            try:
                all_principles = self._evolution.get_active_principles()
                # Filter to principles from selected frameworks
                selected_fw_ids = {fw.framework_id for fw, _ in selection.ranked[:3]}
                for p in all_principles:
                    if any(fid in selected_fw_ids for fid in (p.metadata or {}).get("frameworks", [])):
                        principles.append(p)
                # If no framework-linked principles, return all active
                if not principles:
                    principles = all_principles
            except Exception:
                pass
        return principles

    def _get_principle_ids(self, selection: FrameworkSelection) -> list[str]:
        principles = self._get_principles(selection)
        return [p.principle_id for p in principles[:10]]
