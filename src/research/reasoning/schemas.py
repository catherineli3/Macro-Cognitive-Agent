"""V4 Reasoning Schemas — data structures for professional macro reasoning.

Design principle: Every field must contribute to the quality of the final
research memo. No architectural bloat.

Key data flows:
    MacroContext → EvidenceSynthesizer → EvidenceCluster[]
    EvidenceCluster[] + Beliefs → HypothesisBuilder → Hypothesis[]
    Hypothesis[] → CounterArgumentGenerator → CounterArgument[]
    All → MemoWriter → ResearchMemo
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

# ═══════════════════════════════════════════════════════════════════════════
# Evidence Structures
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class EvidenceCluster:
    """A cluster of related evidence pieces, organized by theme.

    Not just a list — each cluster tells a mini-story about what the
    evidence means as a group.
    """

    cluster_id: str = ""
    theme: str = ""  # e.g., "Labor Market Tightness", "Inflation Persistence"
    description: str = ""  # Narrative description of what this cluster says
    evidence_items: list[dict] = field(default_factory=list)
    # Each item: {source, description, direction, strength, recency}

    # Scoring
    net_direction: str = ""  # "supporting_bullish", "supporting_bearish", "mixed", "neutral"
    weight_score: float = 0.0  # 0-1: How weighty is this cluster?
    quality_score: float = 0.0  # 0-1: How trustworthy is the evidence?
    recency_score: float = 0.0  # 0-1: How fresh is the data?

    # Bridge to beliefs
    relevant_beliefs: list[str] = field(default_factory=list)  # belief IDs this affects
    supports: list[str] = field(default_factory=list)  # beliefs this supports
    contradicts: list[str] = field(default_factory=list)  # beliefs this contradicts

    # Missing
    data_gaps: list[str] = field(default_factory=list)  # What data would clarify this?

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "theme": self.theme,
            "description": self.description,
            "evidence_count": len(self.evidence_items),
            "net_direction": self.net_direction,
            "weight_score": self.weight_score,
            "quality_score": self.quality_score,
            "recency_score": self.recency_score,
            "relevant_beliefs": self.relevant_beliefs,
            "supports": self.supports,
            "contradicts": self.contradicts,
            "data_gaps": self.data_gaps,
        }


@dataclass
class EvidenceAssessment:
    """Complete evidence assessment across all clusters.

    The key question this answers: "On net, what does the evidence say?"
    """

    clusters: list[EvidenceCluster] = field(default_factory=list)
    total_evidence_points: int = 0

    # Net assessment
    net_weight_bullish: float = 0.0  # Total weight for bullish evidence
    net_weight_bearish: float = 0.0  # Total weight for bearish evidence
    net_direction: str = ""  # "bullish", "bearish", "mixed"

    # Quality
    evidence_quality: str = ""  # "high" / "moderate" / "low" / "insufficient"
    overall_quality_score: float = 0.0  # 0-100 numeric score for Research Loop gating
    evidence_coverage: dict = field(default_factory=dict)  # V10.1: per-dimension coverage
    contradictory_signals: list[str] = field(default_factory=list)
    consensus_signals: list[str] = field(default_factory=list)

    # Gaps
    key_missing_data: list[str] = field(default_factory=list)
    what_would_change_assessment: str = ""

    def to_dict(self) -> dict:
        return {
            "total_evidence_points": self.total_evidence_points,
            "net_weight_bullish": self.net_weight_bullish,
            "net_weight_bearish": self.net_weight_bearish,
            "net_direction": self.net_direction,
            "evidence_quality": self.evidence_quality,
            "overall_quality_score": self.overall_quality_score,
            "evidence_coverage": self.evidence_coverage,
            "contradictory_signals": self.contradictory_signals,
            "consensus_signals": self.consensus_signals,
            "key_missing_data": self.key_missing_data,
            "clusters": [c.to_dict() for c in self.clusters],
        }


# ═══════════════════════════════════════════════════════════════════════════
# Hypothesis Structures
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class Hypothesis:
    """A causal hypothesis about how the macro world works.

    Not a belief — a hypothesis is a testable proposition with:
    - A causal mechanism
    - Supporting and contradicting evidence
    - Falsification conditions
    - Confidence calibration
    """

    hypothesis_id: str = ""
    title: str = ""  # One-line summary
    statement: str = ""  # Full hypothesis statement
    domain: str = ""  # Growth, Inflation, Policy, etc.

    # Causal chain
    causal_chain: list[str] = field(default_factory=list)
    # e.g., ["Tight labor → wage pressure → sticky services inflation → Fed hawkish"]
    key_assumptions: list[str] = field(default_factory=list)
    structural_factors: list[str] = field(default_factory=list)
    cyclical_factors: list[str] = field(default_factory=list)

    # Evidence linkage
    supporting_evidence: list[dict] = field(default_factory=list)
    contradicting_evidence: list[dict] = field(default_factory=list)
    evidence_weight: float = 0.0  # Net evidence support (-1 to 1)

    # Confidence
    confidence: float = 0.5  # 0-1
    confidence_breakdown: dict = field(default_factory=dict)
    # e.g., {"causal_logic": 0.7, "data_quality": 0.6, "timing": 0.4}

    # Falsification
    falsification_conditions: list[dict] = field(default_factory=list)
    # Each: {condition: str, if_triggered: str, probability: float, timeline: str}

    # Investment implication
    if_true_implication: str = ""
    asset_impact: list[dict] = field(default_factory=list)

    # Meta
    source: str = ""  # How was this generated?
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "hypothesis_id": self.hypothesis_id,
            "title": self.title,
            "statement": self.statement,
            "domain": self.domain,
            "causal_chain": self.causal_chain,
            "key_assumptions": self.key_assumptions,
            "structural_factors": self.structural_factors,
            "cyclical_factors": self.cyclical_factors,
            "evidence_weight": self.evidence_weight,
            "confidence": self.confidence,
            "falsification_conditions": self.falsification_conditions,
            "if_true_implication": self.if_true_implication,
        }


@dataclass
class CounterArgument:
    """A structured counter-argument to a hypothesis.

    Professional researchers don't just state a view — they argue against it.
    This is what separates good research from echo-chamber analysis.
    """

    counter_id: str = ""
    target_hypothesis_id: str = ""

    # The counter
    title: str = ""  # Counter-argument thesis
    argument: str = ""  # Full counter-argument reasoning
    probability: float = 0.0  # How likely is the counter to be right?
    severity: str = ""  # "fatal" (if true, hypothesis is dead) / "major" / "minor"

    # Mechanism
    why_the_hypothesis_could_be_wrong: str = ""
    what_the_market_is_missing: str = ""

    # Evidence
    counter_evidence: list[dict] = field(default_factory=list)

    # Conditions
    trigger_conditions: list[str] = field(default_factory=list)
    # "If X happens, the counter becomes the base case"

    # Historical precedent
    historical_precedent: str = ""

    def to_dict(self) -> dict:
        return {
            "counter_id": self.counter_id,
            "title": self.title,
            "argument": self.argument,
            "probability": self.probability,
            "severity": self.severity,
            "trigger_conditions": self.trigger_conditions,
            "historical_precedent": self.historical_precedent,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Reasoning Chain
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ReasoningChain:
    """The complete chain of reasoning — from observation to conclusion.

    This is the traceable path of logic that a professional researcher
    follows. Every conclusion links to evidence, every assumption is named.
    """

    chain_id: str = ""

    # Steps
    observations: list[str] = field(default_factory=list)  # What we see
    inferences: list[str] = field(default_factory=list)  # What we conclude from what we see
    deductions: list[str] = field(default_factory=list)  # What logically follows
    conclusions: list[str] = field(default_factory=list)  # Final judgments

    # Assumptions
    explicit_assumptions: list[str] = field(default_factory=list)
    implicit_assumptions: list[str] = field(default_factory=list)

    # Risk points
    weakest_links: list[str] = field(default_factory=list)  # Where the chain might break

    # Confidence
    overall_logic_strength: float = 0.0  # 0-1
    weakest_link_probability: float = 0.0  # Probability the weakest link holds

    def summary(self) -> str:
        """Summarize the reasoning chain in 3 sentences."""
        parts = []
        if self.observations:
            parts.append(f"观察: {'; '.join(self.observations[:3])}")
        if self.conclusions:
            parts.append(f"结论: {'; '.join(self.conclusions)}")
        if self.weakest_links:
            parts.append(f"脆弱环节: {', '.join(self.weakest_links[:2])}")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "observations": self.observations,
            "inferences": self.inferences,
            "deductions": self.deductions,
            "conclusions": self.conclusions,
            "explicit_assumptions": self.explicit_assumptions,
            "weakest_links": self.weakest_links,
            "overall_logic_strength": self.overall_logic_strength,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Research Memo
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class MemoSection:
    """A single section of the research memo."""

    heading: str = ""
    content: str = ""
    word_count: int = 0
    has_citations: bool = False
    citation_count: int = 0


@dataclass
class ResearchMemo:
    """The final output — a professional institutional research memo.

    This is the artifact that a macro strategist should be willing to read
    every morning. It should read like Bridgewater Daily Observations,
    not a template dump.

    Target: 1000-3000 words, professional language, no bullet dumping.
    """

    memo_id: str = ""
    date: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # ══ Structure ══

    # 1. Executive Summary (200-300 words, must stand alone)
    executive_summary: str = ""
    one_sentence_view: str = ""

    # 2. Regime Analysis
    current_regime: str = ""
    regime_confidence: float = 0.0
    regime_transition_risk: float = 0.0
    regime_detail: str = ""

    # 3. Market Consensus
    market_consensus: str = ""
    our_view_vs_consensus: str = ""

    # 4. Evidence
    evidence_summary: str = ""
    key_evidence_supporting: list[str] = field(default_factory=list)
    key_evidence_contradicting: list[str] = field(default_factory=list)

    # 5. Counter Evidence
    counter_arguments: list[str] = field(default_factory=list)
    key_risks: list[str] = field(default_factory=list)

    # 6. Predictions
    predictions: list[dict] = field(default_factory=list)
    # [{statement, asset, direction, target, timeframe, confidence, invalidation}]

    # 7. Investment Implications
    trading_implication: str = ""
    favored_assets: list[str] = field(default_factory=list)
    unfavored_assets: list[str] = field(default_factory=list)
    highest_conviction_trade: str = ""

    # 8. Invalidation Conditions
    invalidation_conditions: list[dict] = field(default_factory=list)
    # [{condition, severity, timeline, if_triggered}]

    # 9. Research Questions
    open_questions: list[str] = field(default_factory=list)
    data_to_watch: list[str] = field(default_factory=list)

    # ══ Quality Meta ══

    word_count: int = 0
    citation_count: int = 0
    hallucination_check: bool = False
    evidence_coverage: float = 0.0  # % of claims backed by evidence
    counter_argument_coverage: float = 0.0  # % of hypotheses with counters

    # ══ Source Data ══

    source_hypotheses: list[str] = field(default_factory=list)
    source_clusters: list[str] = field(default_factory=list)
    source_models: list[str] = field(default_factory=list)

    # ══ Full text ══

    full_memo_text: str = ""  # The complete memo as one text block
    sections: list[MemoSection] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "memo_id": self.memo_id,
            "date": self.date,
            "executive_summary": self.executive_summary,
            "one_sentence_view": self.one_sentence_view,
            "current_regime": self.current_regime,
            "regime_confidence": self.regime_confidence,
            "our_view_vs_consensus": self.our_view_vs_consensus,
            "evidence_summary": self.evidence_summary,
            "key_evidence_supporting": self.key_evidence_supporting,
            "key_evidence_contradicting": self.key_evidence_contradicting,
            "counter_arguments": self.counter_arguments,
            "key_risks": self.key_risks,
            "predictions": self.predictions,
            "trading_implication": self.trading_implication,
            "highest_conviction_trade": self.highest_conviction_trade,
            "invalidation_conditions": self.invalidation_conditions,
            "open_questions": self.open_questions,
            "data_to_watch": self.data_to_watch,
            "word_count": self.word_count,
            "citation_count": self.citation_count,
            "evidence_coverage": self.evidence_coverage,
            "counter_argument_coverage": self.counter_argument_coverage,
            "full_memo_text": self.full_memo_text,
        }

    def quality_score(self) -> float:
        """Quick quality heuristic based on structure completeness."""
        score = 0.0
        total = 10.0

        if self.executive_summary and len(self.executive_summary) > 100:
            score += 1
        if self.key_evidence_supporting and self.key_evidence_contradicting:
            score += 1
        if self.counter_arguments:
            score += 1
        if self.predictions:
            score += 1
        if self.invalidation_conditions:
            score += 1
        if self.trading_implication:
            score += 1
        if self.open_questions:
            score += 1
        if self.citation_count >= 3:
            score += 1
        if self.word_count >= 1000:
            score += 1
        if self.counter_argument_coverage >= 0.5:
            score += 1

        return round(score / total * 100, 1)


# ═══════════════════════════════════════════════════════════════════════════
# V10.2: Adaptive Research Loop — Loop State & Convergence
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class LoopState:
    """Per-round state snapshot for adaptive loop convergence tracking.

    Tracks deltas between rounds to determine when research has converged.
    """

    iteration: int = 0

    # Scores this round
    quality: float = 0.0  # Memo quality (0-100)
    market_score: float = 0.0  # Market Challenge score (0-100)
    evidence_score: float = 0.0  # Evidence quality (0-100)
    evidence_coverage: float = 0.0  # Evidence coverage pct (0-100)

    # Hypothesis tracking
    hypothesis_count: int = 0
    surviving_hypotheses: int = 0
    deleted_this_round: list[str] = field(default_factory=list)

    # Evidence tracking
    evidence_points: int = 0
    new_evidence_added: int = 0
    visited_source_count: int = 0
    new_sources_collected: list[str] = field(default_factory=list)

    # Deltas from previous round (populated by ConvergenceAnalyzer)
    evidence_delta_pct: float = 0.0
    hypothesis_delta_pct: float = 0.0
    belief_delta_pct: float = 0.0
    memo_delta_pct: float = 0.0
    quality_delta: float = 0.0
    market_score_delta: float = 0.0

    # Convergence status
    is_converged: bool = False
    stop_reason: str = ""
    should_continue: bool = True

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "quality": self.quality,
            "market_score": self.market_score,
            "evidence_score": self.evidence_score,
            "evidence_coverage": self.evidence_coverage,
            "hypothesis_count": self.hypothesis_count,
            "surviving_hypotheses": self.surviving_hypotheses,
            "deleted_this_round": self.deleted_this_round,
            "evidence_points": self.evidence_points,
            "new_evidence_added": self.new_evidence_added,
            "visited_source_count": self.visited_source_count,
            "new_sources_collected": self.new_sources_collected,
            "evidence_delta_pct": self.evidence_delta_pct,
            "hypothesis_delta_pct": self.hypothesis_delta_pct,
            "belief_delta_pct": self.belief_delta_pct,
            "memo_delta_pct": self.memo_delta_pct,
            "quality_delta": self.quality_delta,
            "market_score_delta": self.market_score_delta,
            "is_converged": self.is_converged,
            "stop_reason": self.stop_reason,
            "should_continue": self.should_continue,
        }
