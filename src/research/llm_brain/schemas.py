"""ResearchMemo — The V3.4 deep reasoning output schema.

Upgrades the agent from structured analysis to senior-researcher-level output.
A ResearchMemo is the bridge between "reading the world" (V3.2) and
"understanding the world" (V3.4).

Design principle:
    MacroStateVector + MentalModels + Narratives + Beliefs
        → LLM deep reasoning
        → ResearchMemo (executable analysis, not just description)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# ═══════════════════════════════════════════════════════════════════════════
# Sub-components
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class RegimeAnalysis:
    """Deep regime characterization — goes beyond label to dynamics."""

    regime_label: str = ""
    regime_confidence: float = 0.0
    regime_transition_risk: float = 0.0  # 0–1: probability of regime change
    next_regime_candidates: list[str] = field(default_factory=list)
    regime_duration_estimate: str = ""  # e.g. "3–6 months"
    defining_characteristics: list[str] = field(default_factory=list)
    historical_analogs: list[str] = field(default_factory=list)

    # Five dimensions from RegimeSnapshot
    growth_assessment: str = ""
    inflation_assessment: str = ""
    monetary_assessment: str = ""
    risk_assessment: str = ""
    credit_assessment: str = ""


@dataclass
class NarrativeAnalysis:
    """Deep narrative deconstruction — not just "what" but "why now"."""

    dominant_narrative: str = ""
    narrative_confidence: float = 0.0
    narrative_stage: str = ""  # emerging / consensus / stretched / breaking

    competing_narratives: list[dict] = field(default_factory=list)
    # Each: {"title": ..., "probability": ..., "key_assumption": ...}

    narrative_catalyst: str = ""  # What triggered this narrative
    narrative_durability: str = ""  # "weeks" / "months" / "quarters"
    narrative_risks: list[str] = field(default_factory=list)

    consensus_positioning: str = ""  # crowded / balanced / contrarian
    narrative_gap: str = ""  # What the market narrative misses


@dataclass
class CausalAnalysis:
    """Deep causal reasoning with chain-of-thought."""

    primary_causal_chain: list[str] = field(default_factory=list)
    # e.g. ["DXY↑ → EM FX pressure", "→ Commodity demand ↓", "→ Risk aversion ↑"]

    counterfactual_scenarios: list[dict] = field(default_factory=list)
    # Each: {"trigger": ..., "chain": [...], "probability": ...}

    key_causal_assumptions: list[str] = field(default_factory=list)
    # What must hold true for the causal chain to work

    structural_vs_cyclical: str = ""  # Disentanglement
    feedback_loops_identified: list[str] = field(default_factory=list)
    # E.g. "Narrative → Positioning → Price → Narrative"


@dataclass
class EvidenceAssessment:
    """Weight-of-evidence analysis."""

    supporting_evidence: list[dict] = field(default_factory=list)
    # Each: {"signal": ..., "strength": "strong/moderate/weak", "recency": ...}

    contradicting_evidence: list[dict] = field(default_factory=list)
    # Same structure

    evidence_score: float = 0.0  # Net evidence weight (-1 to +1)
    evidence_quality: str = ""  # "high" / "mixed" / "low"
    missing_evidence: list[str] = field(default_factory=list)
    # What data would change the view

    data_surprises_to_watch: list[str] = field(default_factory=list)


@dataclass
class BeliefSynthesis:
    """Integrated belief synthesis from multiple mental models."""

    core_belief: str = ""  # 1-sentence conviction
    belief_confidence: float = 0.0
    belief_models_used: list[str] = field(default_factory=list)

    model_consensus: str = ""  # Where models agree
    model_divergence: str = ""  # Where models disagree
    highest_conviction_view: str = ""
    lowest_conviction_view: str = ""

    belief_update_triggers: list[str] = field(default_factory=list)
    # What would change these beliefs


@dataclass
class FalsificationCheck:
    """Popperian falsification — what proves us wrong."""

    falsification_conditions: list[dict] = field(default_factory=list)
    # Each: {"condition": ..., "if_triggered": ..., "severity": "fatal/major/minor"}

    current_falsification_status: str = ""  # "none triggered" / "monitoring" / "triggered"
    falsification_timeline: str = ""  # When conditions might be testable
    base_case_if_wrong: str = ""  # What the world looks like if base case fails


@dataclass
class AssetImplication:
    """Investment-relevant asset views."""

    asset_views: list[dict] = field(default_factory=list)
    # Each: {"asset": ..., "view": "bullish/bearish/neutral", "conviction": ..., "timeframe": ...}

    highest_conviction_trades: list[str] = field(default_factory=list)
    regime_favored_assets: list[str] = field(default_factory=list)
    regime_unfavored_assets: list[str] = field(default_factory=list)

    portfolio_positioning: str = ""  # risk-on / neutral / hedged / defensive
    cross_asset_signals: list[str] = field(default_factory=list)


@dataclass
class TailRisk:
    """Tail risk assessment."""

    tail_risks: list[dict] = field(default_factory=list)
    # Each: {"risk": ..., "probability": ..., "impact": ..., "hedge": ...}

    black_swan_candidates: list[str] = field(default_factory=list)
    fat_tail_assessment: str = ""  # "normal" / "elevated" / "extreme"
    correlation_regime: str = ""  # "diversification works" / "everything together"

    stress_scenarios: list[dict] = field(default_factory=list)
    # Each: {"scenario": ..., "triggers": [...], "market_impact": ...}


@dataclass
class ConfidenceCalibration:
    """Confidence calibration — are we overconfident?"""

    overall_confidence: float = 0.0  # 0–1
    confidence_breakdown: dict = field(default_factory=dict)
    # {"regime": ..., "narrative": ..., "causal": ..., "asset_view": ...}

    calibration_note: str = ""  # "well-calibrated" / "potentially overconfident" / "too uncertain"
    key_uncertainties: list[str] = field(default_factory=list)
    known_unknowns: list[str] = field(default_factory=list)
    unknown_unknowns_awareness: str = ""  # What might we be missing entirely


# ═══════════════════════════════════════════════════════════════════════════
# Main ResearchMemo
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ResearchMemo:
    """The V3.4 output: a senior macro researcher's structured analysis.

    This is what separates an "advanced data tool" from a "macro researcher":
    it contains judgment, falsification, tail risk, and calibration — not
    just data aggregation.
    """

    memo_id: str = ""
    title: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    analyst: str = "MacroResearchAgent V3.4"

    # Executive summary
    executive_summary: str = ""
    one_sentence_view: str = ""
    conviction_level: str = ""  # "high" / "medium" / "low"

    # Core analysis components
    regime: RegimeAnalysis = field(default_factory=RegimeAnalysis)
    narrative: NarrativeAnalysis = field(default_factory=NarrativeAnalysis)
    causal: CausalAnalysis = field(default_factory=CausalAnalysis)
    evidence: EvidenceAssessment = field(default_factory=EvidenceAssessment)
    belief: BeliefSynthesis = field(default_factory=BeliefSynthesis)

    # Judgment
    falsification: FalsificationCheck = field(default_factory=FalsificationCheck)
    assets: AssetImplication = field(default_factory=AssetImplication)
    tail_risk: TailRisk = field(default_factory=TailRisk)
    confidence: ConfidenceCalibration = field(default_factory=ConfidenceCalibration)

    # Meta
    reasoning_mode: str = ""  # "rule-based" / "llm-deep" / "hybrid"
    llm_model: str = ""
    llm_temperature: float = 0.3
    input_data_summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        return {
            "memo_id": self.memo_id,
            "title": self.title,
            "timestamp": self.timestamp,
            "analyst": self.analyst,
            "executive_summary": self.executive_summary,
            "one_sentence_view": self.one_sentence_view,
            "conviction_level": self.conviction_level,
            "regime": {
                "label": self.regime.regime_label,
                "confidence": self.regime.regime_confidence,
                "transition_risk": self.regime.regime_transition_risk,
                "next_candidates": self.regime.next_regime_candidates,
                "duration_estimate": self.regime.regime_duration_estimate,
                "characteristics": self.regime.defining_characteristics,
                "analogs": self.regime.historical_analogs,
                "dimensions": {
                    "growth": self.regime.growth_assessment,
                    "inflation": self.regime.inflation_assessment,
                    "monetary": self.regime.monetary_assessment,
                    "risk": self.regime.risk_assessment,
                    "credit": self.regime.credit_assessment,
                },
            },
            "narrative": {
                "dominant": self.narrative.dominant_narrative,
                "confidence": self.narrative.narrative_confidence,
                "stage": self.narrative.narrative_stage,
                "competing": self.narrative.competing_narratives,
                "catalyst": self.narrative.narrative_catalyst,
                "durability": self.narrative.narrative_durability,
                "risks": self.narrative.narrative_risks,
                "consensus_positioning": self.narrative.consensus_positioning,
                "gap": self.narrative.narrative_gap,
            },
            "causal": {
                "primary_chain": self.causal.primary_causal_chain,
                "counterfactuals": self.causal.counterfactual_scenarios,
                "assumptions": self.causal.key_causal_assumptions,
                "structural_vs_cyclical": self.causal.structural_vs_cyclical,
                "feedback_loops": self.causal.feedback_loops_identified,
            },
            "evidence": {
                "supporting": self.evidence.supporting_evidence,
                "contradicting": self.evidence.contradicting_evidence,
                "score": self.evidence.evidence_score,
                "quality": self.evidence.evidence_quality,
                "missing": self.evidence.missing_evidence,
                "surprises_to_watch": self.evidence.data_surprises_to_watch,
            },
            "belief": {
                "core": self.belief.core_belief,
                "confidence": self.belief.belief_confidence,
                "models_used": self.belief.belief_models_used,
                "consensus": self.belief.model_consensus,
                "divergence": self.belief.model_divergence,
                "highest_conviction": self.belief.highest_conviction_view,
                "lowest_conviction": self.belief.lowest_conviction_view,
                "update_triggers": self.belief.belief_update_triggers,
            },
            "falsification": {
                "conditions": self.falsification.falsification_conditions,
                "status": self.falsification.current_falsification_status,
                "timeline": self.falsification.falsification_timeline,
                "base_case_if_wrong": self.falsification.base_case_if_wrong,
            },
            "assets": {
                "views": self.assets.asset_views,
                "highest_conviction": self.assets.highest_conviction_trades,
                "favored": self.assets.regime_favored_assets,
                "unfavored": self.assets.regime_unfavored_assets,
                "positioning": self.assets.portfolio_positioning,
                "cross_asset_signals": self.assets.cross_asset_signals,
            },
            "tail_risk": {
                "risks": self.tail_risk.tail_risks,
                "black_swans": self.tail_risk.black_swan_candidates,
                "fat_tail": self.tail_risk.fat_tail_assessment,
                "correlation_regime": self.tail_risk.correlation_regime,
                "stress_scenarios": self.tail_risk.stress_scenarios,
            },
            "confidence_calibration": {
                "overall": self.confidence.overall_confidence,
                "breakdown": self.confidence.confidence_breakdown,
                "note": self.confidence.calibration_note,
                "key_uncertainties": self.confidence.key_uncertainties,
                "known_unknowns": self.confidence.known_unknowns,
                "unknown_unknowns": self.confidence.unknown_unknowns_awareness,
            },
            "meta": {
                "reasoning_mode": self.reasoning_mode,
                "llm_model": self.llm_model,
                "temperature": self.llm_temperature,
                "input_summary": self.input_data_summary,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ResearchMemo":
        """Deserialize from dict."""
        r = data.get("regime", {})
        n = data.get("narrative", {})
        c = data.get("causal", {})
        e = data.get("evidence", {})
        b = data.get("belief", {})
        f = data.get("falsification", {})
        a = data.get("assets", {})
        t = data.get("tail_risk", {})
        cc = data.get("confidence_calibration", {})
        m = data.get("meta", {})

        return cls(
            memo_id=data.get("memo_id", ""),
            title=data.get("title", ""),
            timestamp=data.get("timestamp", ""),
            analyst=data.get("analyst", "MacroResearchAgent V3.4"),
            executive_summary=data.get("executive_summary", ""),
            one_sentence_view=data.get("one_sentence_view", ""),
            conviction_level=data.get("conviction_level", ""),
            regime=RegimeAnalysis(
                regime_label=r.get("label", ""),
                regime_confidence=r.get("confidence", 0.0),
                regime_transition_risk=r.get("transition_risk", 0.0),
                next_regime_candidates=r.get("next_candidates", []),
                regime_duration_estimate=r.get("duration_estimate", ""),
                defining_characteristics=r.get("characteristics", []),
                historical_analogs=r.get("analogs", []),
                **{f"{k}_assessment": r.get("dimensions", {}).get(k, "")
                   for k in ["growth", "inflation", "monetary", "risk", "credit"]},
            ),
            narrative=NarrativeAnalysis(
                dominant_narrative=n.get("dominant", ""),
                narrative_confidence=n.get("confidence", 0.0),
                narrative_stage=n.get("stage", ""),
                competing_narratives=n.get("competing", []),
                narrative_catalyst=n.get("catalyst", ""),
                narrative_durability=n.get("durability", ""),
                narrative_risks=n.get("risks", []),
                consensus_positioning=n.get("consensus_positioning", ""),
                narrative_gap=n.get("gap", ""),
            ),
            causal=CausalAnalysis(
                primary_causal_chain=c.get("primary_chain", []),
                counterfactual_scenarios=c.get("counterfactuals", []),
                key_causal_assumptions=c.get("assumptions", []),
                structural_vs_cyclical=c.get("structural_vs_cyclical", ""),
                feedback_loops_identified=c.get("feedback_loops", []),
            ),
            evidence=EvidenceAssessment(
                supporting_evidence=e.get("supporting", []),
                contradicting_evidence=e.get("contradicting", []),
                evidence_score=e.get("score", 0.0),
                evidence_quality=e.get("quality", ""),
                missing_evidence=e.get("missing", []),
                data_surprises_to_watch=e.get("surprises_to_watch", []),
            ),
            belief=BeliefSynthesis(
                core_belief=b.get("core", ""),
                belief_confidence=b.get("confidence", 0.0),
                belief_models_used=b.get("models_used", []),
                model_consensus=b.get("consensus", ""),
                model_divergence=b.get("divergence", ""),
                highest_conviction_view=b.get("highest_conviction", ""),
                lowest_conviction_view=b.get("lowest_conviction", ""),
                belief_update_triggers=b.get("update_triggers", []),
            ),
            falsification=FalsificationCheck(
                falsification_conditions=f.get("conditions", []),
                current_falsification_status=f.get("status", ""),
                falsification_timeline=f.get("timeline", ""),
                base_case_if_wrong=f.get("base_case_if_wrong", ""),
            ),
            assets=AssetImplication(
                asset_views=a.get("views", []),
                highest_conviction_trades=a.get("highest_conviction", []),
                regime_favored_assets=a.get("favored", []),
                regime_unfavored_assets=a.get("unfavored", []),
                portfolio_positioning=a.get("positioning", ""),
                cross_asset_signals=a.get("cross_asset_signals", []),
            ),
            tail_risk=TailRisk(
                tail_risks=t.get("risks", []),
                black_swan_candidates=t.get("black_swans", []),
                fat_tail_assessment=t.get("fat_tail", ""),
                correlation_regime=t.get("correlation_regime", ""),
                stress_scenarios=t.get("stress_scenarios", []),
            ),
            confidence=ConfidenceCalibration(
                overall_confidence=cc.get("overall", 0.0),
                confidence_breakdown=cc.get("breakdown", {}),
                calibration_note=cc.get("note", ""),
                key_uncertainties=cc.get("key_uncertainties", []),
                known_unknowns=cc.get("known_unknowns", []),
                unknown_unknowns_awareness=cc.get("unknown_unknowns", ""),
            ),
            reasoning_mode=m.get("reasoning_mode", ""),
            llm_model=m.get("llm_model", ""),
            llm_temperature=m.get("temperature", 0.3),
            input_data_summary=m.get("input_summary", {}),
        )
