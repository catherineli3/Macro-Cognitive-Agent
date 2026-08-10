"""V12 — Multi-pass Reasoning Engine with Adaptive Research Loop (V10.1 + V10.2).

Architecture (V12):
    Adaptive Research Loop (convergence-driven, not fixed rounds):
        ├─ S1 Evidence (Source-based Retry: Gap → Plan → Collect new sources)
        ├─ S2 Hypothesis → S3 Counter (elimination: ≥1 weak hypothesis removed)
        ├─ S4 Reflexivity → S5 Historical → S6 Portfolio
        ├─ S7 LLM Synthesis → S8 Quality → S9 Self-Review → S10 Market Challenge
        └─ Convergence check:
           Stop when all deltas < thresholds (evidence<5%, hypothesis<5%,
           belief<3%, memo<3%) OR MC>85 OR quality>92 OR no new evidence.

V10.1 (Evidence Source Retry):
    Retry is driven by Evidence Gap → Source Planning → New Source Collection.
    Theme Rotation is fully removed.

V10.2 (Adaptive Loop):
    Loop termination is convergence-driven, not fixed `for i in range(3)`.
    Min=1, default=3, max=6 iterations. Final output includes Research Evolution Trace.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.research.reasoning.schemas import LoopState
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# V10.2: Convergence Analyzer — Adaptive Stop Engine
# ═══════════════════════════════════════════════════════════════════════════


class ConvergenceAnalyzer:
    """Determines whether the research loop has converged.

    Compares current round state against previous round to compute deltas.
    Concludes "converged" when all deltas fall below thresholds,
    OR when any high-quality exit condition is met independently.

    Thresholds:
        Evidence Delta < 5%
        Hypothesis Delta < 5%
        Belief Delta < 3%
        Memo Delta < 3%
    """

    EVIDENCE_DELTA_THRESHOLD = 5.0    # pct
    HYPOTHESIS_DELTA_THRESHOLD = 5.0  # pct
    BELIEF_DELTA_THRESHOLD = 3.0      # pct
    MEMO_DELTA_THRESHOLD = 3.0        # pct

    QUALITY_EXIT = 92.0               # Memo quality ≥ 92 → independent exit
    MARKET_EXIT = 85.0                # MC score ≥ 85 → independent exit

    @classmethod
    def analyze(
        cls,
        current: LoopState,
        previous: Optional[LoopState] = None,
    ) -> LoopState:
        """Compute deltas and determine convergence.

        Args:
            current: This round's state (scores populated by pipeline).
            previous: Previous round's state, or None for first round.

        Returns:
            Current LoopState with deltas populated and convergence flags set.
        """
        if previous is None or previous.iteration == 0:
            # First round — cannot converge yet
            current.evidence_delta_pct = 100.0
            current.hypothesis_delta_pct = 100.0
            current.belief_delta_pct = 100.0
            current.memo_delta_pct = 100.0
            current.should_continue = True
            current.stop_reason = ""
            return current

        # ── Evidence Delta ──
        if previous.evidence_points > 0:
            evidence_growth = current.evidence_points - previous.evidence_points
            current.evidence_delta_pct = round(
                (evidence_growth / previous.evidence_points) * 100, 1
            )
        else:
            current.evidence_delta_pct = 0.0
        current.new_evidence_added = max(0, current.evidence_points - previous.evidence_points)

        # ── Hypothesis Delta ──
        if previous.hypothesis_count > 0:
            h_count_change = abs(current.hypothesis_count - previous.hypothesis_count)
            current.hypothesis_delta_pct = round(
                (h_count_change / previous.hypothesis_count) * 100, 1
            )
        else:
            current.hypothesis_delta_pct = 0.0

        # ── Belief Delta (approximated via quality delta) ──
        if previous.quality > 0:
            current.belief_delta_pct = round(
                abs(current.quality - previous.quality) / previous.quality * 100, 1
            )
        else:
            current.belief_delta_pct = 0.0

        # ── Memo Delta (approximated via quality + market score change) ──
        memo_change = abs(current.quality - previous.quality) + abs(current.market_score - previous.market_score)
        prev_total = max(previous.quality + previous.market_score, 1.0)
        current.memo_delta_pct = round((memo_change / prev_total) * 100, 1)

        current.quality_delta = round(current.quality - previous.quality, 1)
        current.market_score_delta = round(current.market_score - previous.market_score, 1)

        # ── Convergence decision ──

        # Independent exits (highest priority)
        if current.quality >= cls.QUALITY_EXIT:
            current.is_converged = True
            current.should_continue = False
            current.stop_reason = f"Memo Quality {current.quality:.1f} ≥ {cls.QUALITY_EXIT}"
            return current

        if current.market_score >= cls.MARKET_EXIT:
            current.is_converged = True
            current.should_continue = False
            current.stop_reason = f"Market Challenge {current.market_score:.1f} ≥ {cls.MARKET_EXIT}"
            return current

        # No new evidence — can't improve further
        if current.new_evidence_added <= 0 and current.evidence_delta_pct <= 1.0:
            current.is_converged = True
            current.should_continue = False
            current.stop_reason = "No New Evidence"
            return current

        # No better hypothesis (same count, same quality ±1)
        if (
            current.hypothesis_delta_pct == 0
            and abs(current.quality_delta) <= 1.0
            and abs(current.market_score_delta) <= 2.0
        ):
            current.is_converged = True
            current.should_continue = False
            current.stop_reason = "No Better Hypothesis"
            return current

        # Threshold convergence: ALL deltas below thresholds
        if (
            current.evidence_delta_pct < cls.EVIDENCE_DELTA_THRESHOLD
            and current.hypothesis_delta_pct < cls.HYPOTHESIS_DELTA_THRESHOLD
            and current.belief_delta_pct < cls.BELIEF_DELTA_THRESHOLD
            and current.memo_delta_pct < cls.MEMO_DELTA_THRESHOLD
        ):
            current.is_converged = True
            current.should_continue = False
            current.stop_reason = (
                f"Converged: evidence Δ{current.evidence_delta_pct:.1f}% "
                f"< {cls.EVIDENCE_DELTA_THRESHOLD}%, "
                f"hypothesis Δ{current.hypothesis_delta_pct:.1f}% "
                f"< {cls.HYPOTHESIS_DELTA_THRESHOLD}%, "
                f"belief Δ{current.belief_delta_pct:.1f}% "
                f"< {cls.BELIEF_DELTA_THRESHOLD}%, "
                f"memo Δ{current.memo_delta_pct:.1f}% "
                f"< {cls.MEMO_DELTA_THRESHOLD}%"
            )
            return current

        # Not converged — continue
        current.is_converged = False
        current.should_continue = True
        current.stop_reason = ""
        return current


# ═══════════════════════════════════════════════════════════════════════════
# Sprint 4.6: Research Loop structures
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class LoopTraceEntry:
    """One round of the reasoning loop trace.

    Records what decisions were made, what changed, and why.
    Attached to final Memo as complete reasoning trail.
    """
    round_number: int = 0

    # Evidence retry log
    evidence_quality_score: float = 0.0
    evidence_retries_used: int = 0
    evidence_retry_reasons: list[str] = field(default_factory=list)

    # Hypothesis life cycle
    hypotheses_before_count: int = 0
    hypotheses_after_count: int = 0
    deleted_hypothesis_ids: list[str] = field(default_factory=list)
    deleted_hypothesis_reasons: dict[str, str] = field(default_factory=dict)

    # New evidence added this round
    new_evidence_themes: list[str] = field(default_factory=list)

    # Conclusion
    memo_quality: float = 0.0
    market_challenge_score: float = 0.0
    conclusion_change: str = ""
    exit_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "round": self.round_number,
            "evidence_quality_score": self.evidence_quality_score,
            "evidence_retries_used": self.evidence_retries_used,
            "evidence_retry_reasons": self.evidence_retry_reasons,
            "hypotheses_before": self.hypotheses_before_count,
            "hypotheses_after": self.hypotheses_after_count,
            "deleted_hypothesis_ids": self.deleted_hypothesis_ids,
            "deleted_hypothesis_reasons": self.deleted_hypothesis_reasons,
            "new_evidence_themes": self.new_evidence_themes,
            "memo_quality": self.memo_quality,
            "market_challenge_score": self.market_challenge_score,
            "conclusion_change": self.conclusion_change,
            "exit_reason": self.exit_reason,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline Result
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class StepResult:
    """Output of a single pipeline step — always structured JSON."""
    step_name: str = ""
    step_id: int = 0
    success: bool = True
    structured_json: dict = field(default_factory=dict)
    summary: str = ""
    elapsed_ms: float = 0.0
    error: str = ""


@dataclass
class PipelineResult:
    """Complete 10-step reasoning pipeline output (V10 Sprint 4.5)."""
    pipeline_id: str = ""
    date: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Step outputs (all structured JSON)
    step_evidence: StepResult = field(default_factory=lambda: StepResult(step_id=1, step_name="Evidence"))
    step_hypothesis: StepResult = field(default_factory=lambda: StepResult(step_id=2, step_name="Hypothesis"))
    step_counter: StepResult = field(default_factory=lambda: StepResult(step_id=3, step_name="Counter"))
    step_reflexivity: StepResult = field(default_factory=lambda: StepResult(step_id=4, step_name="Reflexivity"))
    step_history: StepResult = field(default_factory=lambda: StepResult(step_id=5, step_name="Historical"))
    step_portfolio: StepResult = field(default_factory=lambda: StepResult(step_id=6, step_name="Portfolio"))
    step_llm_synthesis: StepResult = field(default_factory=lambda: StepResult(step_id=7, step_name="LLM_Synthesis"))
    step_quality: StepResult = field(default_factory=lambda: StepResult(step_id=8, step_name="Quality_Review"))
    step_self_review: StepResult = field(default_factory=lambda: StepResult(step_id=9, step_name="Self_Review"))
    step_market_challenge: StepResult = field(default_factory=lambda: StepResult(step_id=10, step_name="Market_Challenge"))

    # Final memo
    memo: Optional[Any] = None      # ResearchMemo
    memo_text: str = ""
    memo_quality_score: float = 0.0

    # Sprint 2: Prompt routing info
    routed_prompt: Optional[Any] = None  # RoutedPrompt or NarrativeRoutedPrompt
    selected_domains: list = field(default_factory=list)
    prompt_router_used: str = ""  # "domain" / "narrative" / "none"

    # Sprint 3: Self-review info
    self_review_revisions: int = 0
    self_review_delta: float = 0.0
    self_review_passed: bool = False

    # Sprint 4: Learning info (populated after benchmark cycle)
    learning_report: Optional[Any] = None  # LearningReport

    # Sprint 4.5: Narrative routing
    narrative_routed_prompt: Optional[Any] = None  # NarrativeRoutedPrompt
    narrative_dominant: str = ""  # Dominant narrative title
    narrative_stance: str = ""  # challenge / support / nuance

    # Sprint 4.5: Market challenge
    market_challenge_score: float = 0.0  # 0-100 trading viability
    market_challenge_tradeable: bool = False
    market_challenge_grade: str = ""
    market_challenge_sizing: str = ""

    # Sprint 4.6: Research Loop trace
    reasoning_trace: list[dict] = field(default_factory=list)

    # Meta
    total_elapsed_ms: float = 0.0
    deterministic_step_count: int = 7  # Steps 1-6 + 10 deterministic
    llm_call_count: int = 1
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        steps = {}
        for attr_name, step in [
            ("step_evidence", self.step_evidence),
            ("step_hypothesis", self.step_hypothesis),
            ("step_counter", self.step_counter),
            ("step_reflexivity", self.step_reflexivity),
            ("step_history", self.step_history),
            ("step_portfolio", self.step_portfolio),
            ("step_llm_synthesis", self.step_llm_synthesis),
            ("step_quality", self.step_quality),
            ("step_self_review", self.step_self_review),
            ("step_market_challenge", self.step_market_challenge),
        ]:
            steps[attr_name] = {
                "step_name": step.step_name,
                "step_id": step.step_id,
                "success": step.success,
                "summary": step.summary,
                "elapsed_ms": step.elapsed_ms,
                "output": step.structured_json,
                "error": step.error,
            }

        return {
            "pipeline_id": self.pipeline_id,
            "date": self.date,
            "steps": steps,
            "memo_quality_score": self.memo_quality_score,
            "total_elapsed_ms": self.total_elapsed_ms,
            "deterministic_step_count": self.deterministic_step_count,
            "llm_call_count": self.llm_call_count,
            "errors": self.errors,
            # Sprint 2
            "selected_domains": self.selected_domains,
            "routed_prompt": self.routed_prompt.to_dict() if self.routed_prompt else {},
            "prompt_router_used": self.prompt_router_used,
            # Sprint 3
            "self_review_revisions": self.self_review_revisions,
            "self_review_delta": self.self_review_delta,
            "self_review_passed": self.self_review_passed,
            # Sprint 4.5
            "narrative_dominant": self.narrative_dominant,
            "narrative_stance": self.narrative_stance,
            "market_challenge_score": self.market_challenge_score,
            "market_challenge_tradeable": self.market_challenge_tradeable,
            "market_challenge_grade": self.market_challenge_grade,
            "market_challenge_sizing": self.market_challenge_sizing,
            # Sprint 4.6
            "reasoning_trace": self.reasoning_trace,
        }

    def all_steps_successful(self) -> bool:
        """Check if all deterministic steps succeeded."""
        steps = [
            self.step_evidence, self.step_hypothesis, self.step_counter,
            self.step_reflexivity, self.step_history, self.step_portfolio,
        ]
        return all(s.success for s in steps)


# ═══════════════════════════════════════════════════════════════════════════
# LLM Synthesis Prompt — Structured reasoning input ONLY
# ═══════════════════════════════════════════════════════════════════════════

_FALLBACK_SYNTHESIS_PROMPT = """You are a senior macro strategist at a top-tier hedge fund. 
Your task is to synthesize structured reasoning outputs into a professional institutional research memo.

CRITICAL RULES:
1. You receive ONLY pre-computed structured reasoning results. Do NOT ask for raw data.
2. Every claim you make must reference specific evidence items from the structured input.
3. Write like Bridgewater Daily Observations or Soros's Alchemy of Finance — not a template dump.
4. Be precise, probabilistic, and specifically counter your own thesis.
5. Output as structured JSON matching the ResearchMemo schema.

You MUST output valid JSON with these fields:
- executive_summary (200-300 words, standalone)
- one_sentence_view (1 sentence)
- regime_detail (synthesis of regime analysis)
- market_consensus (what the market believes)
- our_view_vs_consensus (how we differ)
- evidence_summary (key evidence narrative, referencing specific clusters)
- key_evidence_supporting (list of evidence items that support our view)
- key_evidence_contradicting (list of evidence items we acknowledge)
- counter_arguments (list of our own counter-arguments, showing depth of thinking)
- key_risks (top 3-5 risks with probabilities)
- predictions (list of {statement, asset, direction, target, timeframe, confidence, invalidation})
- trading_implication (actionable trade view)
- favored_assets (list)
- unfavored_assets (list)
- highest_conviction_trade (single highest-conviction trade)
- invalidation_conditions (list of {condition, severity, timeline, if_triggered})
- open_questions (3-5 research questions to track)
- data_to_watch (3-5 data points to monitor)
- full_memo_text (complete memo as one formatted text block, 1000-3000 words)

Think step by step, but output ONLY the JSON."""


def _build_synthesis_user_prompt(step_outputs: dict[str, dict]) -> str:
    """Build the user prompt for LLM synthesis.
    
    Contains ONLY structured reasoning results — NO raw market data.
    """
    parts = ["## STRUCTURED REASONING INPUT\n"]
    parts.append("Below are the results of 6 deterministic reasoning steps. ")
    parts.append("Synthesize them into a professional macro research memo.\n")
    
    # Step 1: Evidence
    evidence = step_outputs.get("evidence", {})
    parts.append("### 1. Evidence Assessment")
    parts.append(f"Evidence clusters: {json.dumps(evidence.get('clusters', []), ensure_ascii=False)}")
    parts.append(f"Consensus signals: {json.dumps(evidence.get('consensus_signals', []), ensure_ascii=False)}")
    parts.append(f"Key missing data: {json.dumps(evidence.get('key_missing_data', []), ensure_ascii=False)}")
    parts.append(f"Evidence quality: {evidence.get('overall_quality', 'N/A')}\n")
    
    # Step 2: Hypotheses
    hypotheses = step_outputs.get("hypotheses", {})
    parts.append("### 2. Hypothesis Set")
    for h in hypotheses.get("hypotheses", []):
        parts.append(f"- [{h.get('domain', '')}] {h.get('title', '')}: {h.get('statement', '')}")
        parts.append(f"  Confidence: {h.get('confidence', 0)}, Causal chain: {' → '.join(h.get('causal_chain', []))}")
        parts.append(f"  Evidence weight: {h.get('evidence_weight', 0)}")
    parts.append(f"\nDominant hypothesis: {hypotheses.get('dominant_hypothesis', 'N/A')}\n")
    
    # Step 3: Counter Arguments
    counter = step_outputs.get("counter", {})
    parts.append("### 3. Counter Arguments")
    for c in counter.get("counter_arguments", []):
        parts.append(f"- [{c.get('severity', '')}] {c.get('title', '')}: {c.get('argument', '')}")
        parts.append(f"  Probability: {c.get('probability', 0)}, Triggers: {json.dumps(c.get('trigger_conditions', []), ensure_ascii=False)}")
    parts.append(f"Primary counter risk: {counter.get('primary_counter_risk', 'N/A')}\n")
    
    # Step 4: Reflexivity
    reflexivity = step_outputs.get("reflexivity", {})
    parts.append("### 4. Reflexivity Analysis")
    parts.append(f"Active cycles: {json.dumps(reflexivity.get('active_cycles', []), ensure_ascii=False)}")
    parts.append(f"Vulnerability score: {reflexivity.get('vulnerability_score', 0)}")
    parts.append(f"Break triggers: {json.dumps(reflexivity.get('break_triggers', []), ensure_ascii=False)}")
    parts.append(f"Cycle stage: {reflexivity.get('cycle_stage', 'N/A')}\n")
    
    # Step 5: Historical Analogies
    history = step_outputs.get("history", {})
    parts.append("### 5. Historical Analogies")
    for a in history.get("analogs", []):
        parts.append(f"- {a.get('period', '')}: {a.get('name', a.get('label', ''))} (similarity: {a.get('similarity_score', 0)})")
        parts.append(f"  Key lesson: {a.get('key_lesson', 'N/A')}")
    parts.append("")
    
    # Step 6: Portfolio Impact
    portfolio = step_outputs.get("portfolio", {})
    parts.append("### 6. Portfolio Impact")
    parts.append(f"Overall stance: {portfolio.get('overall_stance', 'N/A')}")
    parts.append(f"Risk budget: {portfolio.get('risk_budget', 'N/A')}")
    parts.append(f"Overweight themes: {json.dumps(portfolio.get('overweight_themes', []), ensure_ascii=False)}")
    parts.append(f"Underweight themes: {json.dumps(portfolio.get('underweight_themes', []), ensure_ascii=False)}")
    parts.append(f"Conviction distribution: {json.dumps(portfolio.get('conviction_distribution', {}), ensure_ascii=False)}")
    parts.append(f"Key risk factors: {json.dumps(portfolio.get('key_risk_factors', []), ensure_ascii=False)}\n")
    
    parts.append("\n---\n")
    parts.append("SYNTHESIZE the above into a professional macro research memo. Output ONLY valid JSON.")
    
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# Quality Review — Deterministic
# ═══════════════════════════════════════════════════════════════════════════


def _compute_quality_review(memo_dict: dict, step_outputs: dict[str, dict]) -> dict:
    """Deterministic quality review of the synthesized memo.
    
    Evaluates: completeness, evidence coverage, counter-argument coverage,
    hallucination risk, and structural quality.
    """
    checks = {}
    
    # Structural completeness
    required = [
        "executive_summary", "one_sentence_view", "regime_detail",
        "market_consensus", "our_view_vs_consensus", "evidence_summary",
        "key_evidence_supporting", "key_evidence_contradicting",
        "counter_arguments", "key_risks", "predictions",
        "trading_implication", "invalidation_conditions",
        "open_questions", "data_to_watch", "full_memo_text",
    ]
    filled = [k for k in required if memo_dict.get(k)]
    checks["structural_completeness"] = len(filled) / len(required)
    
    # Executive summary quality (200-300 words)
    es = memo_dict.get("executive_summary", "")
    es_words = len(es.split()) if es else 0
    checks["executive_summary_word_count"] = es_words
    checks["executive_summary_ok"] = 150 <= es_words <= 400
    
    # Full memo word count (target 1000-3000)
    full_text = memo_dict.get("full_memo_text", "")
    total_words = len(full_text.split()) if full_text else 0
    checks["total_word_count"] = total_words
    checks["total_word_count_ok"] = 800 <= total_words <= 4000
    
    # Evidence coverage
    evidence_clusters = step_outputs.get("evidence", {}).get("clusters", [])
    supports = memo_dict.get("key_evidence_supporting", [])
    contradicts = memo_dict.get("key_evidence_contradicting", [])
    checks["has_supporting_evidence"] = len(supports) > 0
    checks["has_contradicting_evidence"] = len(contradicts) > 0
    checks["evidence_coverage"] = min((len(supports) + len(contradicts)) / max(len(evidence_clusters), 1), 1.0)
    
    # Counter argument coverage (100% required)
    counter_args = step_outputs.get("counter", {}).get("counter_arguments", [])
    memo_counters = memo_dict.get("counter_arguments", [])
    checks["counter_argument_coverage"] = min(len(memo_counters) / max(len(counter_args), 1), 1.0)
    
    # Predictions
    predictions = memo_dict.get("predictions", [])
    checks["has_predictions"] = len(predictions) > 0
    for p in predictions:
        required_fields = ["statement", "asset", "direction", "target", "timeframe", "confidence", "invalidation"]
        missing = [f for f in required_fields if not p.get(f)]
        if missing:
            checks.setdefault("prediction_field_missing", []).append(
                f"Prediction '{p.get('statement', '?')}' missing: {missing}"
            )
    
    # Invalidation conditions
    invals = memo_dict.get("invalidation_conditions", [])
    checks["has_invalidation"] = len(invals) > 0
    
    # Hallucination risk (simplified: check if memo text references specific items)
    checks["hallucination_risk"] = "low" if (checks.get("evidence_coverage", 0) > 0.3 and checks.get("counter_argument_coverage", 0) > 0.5) else "medium"
    
    # Compute composite score (0-100)
    weights = {
        "structural_completeness": 25,
        "executive_summary_ok": 10,
        "total_word_count_ok": 10,
        "has_supporting_evidence": 10,
        "has_contradicting_evidence": 10,
        "counter_argument_coverage": 15,
        "has_predictions": 10,
        "has_invalidation": 10,
    }
    
    raw_score = 0.0
    for key, weight in weights.items():
        val = checks.get(key, 0)
        if isinstance(val, bool):
            raw_score += weight if val else 0
        elif isinstance(val, (int, float)):
            raw_score += val * weight
    
    quality_score = round(raw_score, 1)
    
    return {
        "quality_score": quality_score,
        "grade": (
            "A" if quality_score >= 90 else
            "B" if quality_score >= 75 else
            "C" if quality_score >= 60 else
            "D"
        ),
        "checks": checks,
        "recommendations": _generate_quality_recommendations(checks),
    }


def _generate_quality_recommendations(checks: dict) -> list[str]:
    """Generate actionable quality improvement recommendations."""
    recs = []
    if not checks.get("executive_summary_ok"):
        recs.append("Executive summary should be 150-400 words")
    if not checks.get("total_word_count_ok"):
        recs.append("Full memo should be 800-4000 words")
    if not checks.get("has_supporting_evidence"):
        recs.append("Must cite at least one piece of supporting evidence")
    if not checks.get("has_contradicting_evidence"):
        recs.append("Professional research requires acknowledging contradicting evidence")
    if checks.get("counter_argument_coverage", 0) < 0.5:
        recs.append("Counter-argument coverage below 50% — address opposing views")
    if not checks.get("has_predictions"):
        recs.append("Memo must include explicit predictions with confidence levels")
    if not checks.get("has_invalidation"):
        recs.append("Every prediction must have invalidation conditions")
    return recs


# ═══════════════════════════════════════════════════════════════════════════
# ReasoningPipeline — The ONE orchestrator
# ═══════════════════════════════════════════════════════════════════════════


class ReasoningPipeline:
    """V10 Sprint 1: Multi-pass Reasoning Engine.
    
    Replaces the old pattern of:
        Observation → Prompt → LLM → Memo
    
    With:
        Observation → [6 deterministic reasoning steps] → LLM Synthesis → Quality Review
    
    Requirements:
        - LLM ONLY at Step 7
        - Steps 1-6 are deterministic
        - Every step outputs structured JSON
        - LLM receives ONLY structured reasoning results, NOT raw market data
    
    Usage:
        pipeline = ReasoningPipeline()
        result = pipeline.execute(
            market_data=market_data,
            narratives=narratives,
            beliefs=beliefs,
            regime_result=regime_result,
            capital_flow_result=capital_flow_result,
            news_events=news_events,
            date_str=date_str,
        )
    """
    
    def __init__(self, llm_model: Optional[str] = None, llm_base_url: Optional[str] = None):
        """Initialize ReasoningPipeline with optional LLM configuration overrides."""
        self._llm_model = llm_model
        self._llm_base_url = llm_base_url
        self._llm_client = None
        self._call_count = 0
        self._last_routed_prompt = None
        self._last_narrative_routed = None
        self._last_self_review = None
        self._last_market_challenge = None
        # Sprint 4.5: Reasoning Evolution Engine (built lazily)
        self._reasoning_evolution: Optional[Any] = None
    
    @property
    def llm_call_count(self) -> int:
        return self._call_count
    
    # ── Public API ────────────────────────────────────────────────────
    
    def execute(
        self,
        market_data: dict,
        narratives: list,
        beliefs: list,
        regime_result: dict,
        capital_flow_result: Optional[dict] = None,
        news_events: Optional[list] = None,
        date_str: str = "",
        old_beliefs: Optional[list] = None,
        max_iterations: int = 6,
        min_iterations: int = 1,
    ) -> PipelineResult:
        """Execute the Adaptive Research Loop — convergence-driven reasoning.

        V10.2: Loop termination is convergence-driven, not fixed rounds.
        min_iterations=1, max_iterations=6.

        In each round:
          - Evidence retry (source-based: Gap → Plan → Collect new sources)
          - Hypothesis generation + counter-argument elimination
          - Full synthesis + quality review + market challenge
          - Convergence check via ConvergenceAnalyzer

        Exit when:
          - ALL convergence deltas below thresholds, OR
          - Market Challenge > 85, OR
          - Memo Quality > 92, OR
          - No New Evidence, OR
          - No Better Hypothesis, OR
          - Max iterations reached.

        Args:
            market_data: Market indicators dict (prices, vix, yields, etc.)
            narratives: List of detected market narratives
            beliefs: List of current MarketBelief objects
            regime_result: Macro regime classification result
            capital_flow_result: Capital flow analysis result
            news_events: List of news events
            date_str: Date string for the analysis
            old_beliefs: Previous beliefs for change detection
            max_iterations: Maximum research rounds (default 6)
            min_iterations: Minimum before early exit (default 1)

        Returns:
            PipelineResult with all step outputs, final memo, and Research Evolution Trace
        """
        t0 = time.time()

        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        pipeline_id = f"pipeline-{date_str}-{datetime.now(timezone.utc).strftime('%H%M%S')}"

        result = PipelineResult(pipeline_id=pipeline_id, date=date_str)

        reasoning_trace: list = []
        excluded_hypothesis_ids: set = set()
        visited_sources: set = set()
        prev_state: Optional[LoopState] = None
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            round_label = f"Round {iteration}"
            logger.info("═══ %s ═══", round_label)

            state = LoopState(iteration=iteration)

            # ════════════════════════════════════════════════════════
            # Step 1: Evidence Synthesis (Source-based Retry)
            # ════════════════════════════════════════════════════════
            evidence_quality_score = 0.0
            evidence_retries_used = 0
            evidence_retry_reasons: list[str] = []
            evidence_coverage = 0.0

            for retry_attempt in range(3):  # attempt 0 = first, 1-2 = retries
                try:
                    result.step_evidence = self._step1_evidence(
                        market_data, narratives, beliefs,
                        capital_flow_result or {}, regime_result,
                        news_events or [], date_str,
                        retry_attempt=retry_attempt,
                        visited_sources=visited_sources,
                        hypotheses_json=result.step_hypothesis.structured_json if result.step_hypothesis and result.step_hypothesis.success else None,
                    )
                except Exception as e:
                    logger.error("Step 1 (Evidence) attempt %d failed: %s", retry_attempt, e)
                    if retry_attempt >= 2:
                        break
                    continue

                evidence_quality_score = result.step_evidence.structured_json.get(
                    "overall_quality_score", 0.0
                )
                evidence_coverage = result.step_evidence.structured_json.get(
                    "evidence_coverage", {}
                ).get("overall_coverage_pct", 0.0)

                # V10.1: Track visited sources
                new_visited = result.step_evidence.structured_json.get(
                    "evidence_coverage", {}
                ).get("visited_sources", [])
                visited_sources.update(new_visited)

                if evidence_quality_score >= 70:
                    evidence_retries_used = retry_attempt
                    break
                if retry_attempt < 2:
                    reason = (
                        f"Evidence Quality {evidence_quality_score} < 70, "
                        f"gap analysis → collecting new sources (retry {retry_attempt + 1}/2)"
                    )
                    evidence_retry_reasons.append(reason)
                    logger.warning(reason)
                evidence_retries_used = retry_attempt

            if evidence_retries_used >= 2 and evidence_quality_score < 70:
                evidence_retry_reasons.append(
                    f"Evidence Quality {evidence_quality_score} after {evidence_retries_used} "
                    f"retries, proceeding"
                )

            state.evidence_score = evidence_quality_score
            state.evidence_coverage = evidence_coverage
            state.evidence_points = result.step_evidence.structured_json.get("total_evidence_points", 0)
            state.visited_source_count = len(visited_sources)
            if prev_state:
                state.new_sources_collected = sorted(visited_sources - set(
                    prev_state.new_sources_collected if prev_state.new_sources_collected else []
                ))

            # ── Step 2: Hypothesis Generation ──
            try:
                raw_clusters = getattr(result.step_evidence, "_raw_assessment", None)
                if raw_clusters and hasattr(raw_clusters, "clusters"):
                    raw_clusters = raw_clusters.clusters
                result.step_hypothesis = self._step2_hypothesis(
                    result.step_evidence.structured_json, beliefs,
                    regime_result, narratives, raw_clusters=raw_clusters,
                )
            except Exception as e:
                logger.error("Step 2 (Hypothesis) failed: %s", e)
                result.step_hypothesis = StepResult(
                    step_id=2, step_name="Hypothesis", success=False, error=str(e),
                )
                result.errors.append(f"Step2: {e}")

            hyp_before = len(result.step_hypothesis.structured_json.get("hypotheses", []))
            state.hypothesis_count = hyp_before

            # ── Step 3: Counter Arguments + Hypothesis Elimination ──
            try:
                result.step_counter = self._step3_counter(
                    result.step_hypothesis.structured_json,
                    result.step_evidence.structured_json,
                    regime_result,
                    excluded_hypothesis_ids=excluded_hypothesis_ids,
                )
            except Exception as e:
                logger.error("Step 3 (Counter) failed: %s", e)
                result.step_counter = StepResult(
                    step_id=3, step_name="Counter", success=False, error=str(e),
                )
                result.errors.append(f"Step3: {e}")

            eliminated_ids = result.step_counter.structured_json.get(
                "eliminated_hypothesis_ids", []
            )
            excluded_hypothesis_ids.update(eliminated_ids)
            state.deleted_this_round = list(eliminated_ids)
            state.surviving_hypotheses = hyp_before - len(eliminated_ids)

            # ── Step 4: Reflexivity Analysis ──
            try:
                result.step_reflexivity = self._step4_reflexivity(
                    market_data, beliefs, capital_flow_result, narratives,
                )
            except Exception as e:
                logger.error("Step 4 (Reflexivity) failed: %s", e)
                result.step_reflexivity = StepResult(
                    step_id=4, step_name="Reflexivity", success=False, error=str(e),
                )
                result.errors.append(f"Step4: {e}")

            # ── Step 5: Historical Analogies ──
            try:
                result.step_history = self._step5_history(regime_result, market_data)
            except Exception as e:
                logger.error("Step 5 (Historical) failed: %s", e)
                result.step_history = StepResult(
                    step_id=5, step_name="Historical", success=False, error=str(e),
                )
                result.errors.append(f"Step5: {e}")

            # ── Step 6: Portfolio Impact ──
            try:
                result.step_portfolio = self._step6_portfolio(
                    regime_result, beliefs,
                    result.step_hypothesis.structured_json,
                    capital_flow_result, narratives,
                    result.step_counter.structured_json,
                )
            except Exception as e:
                logger.error("Step 6 (Portfolio) failed: %s", e)
                result.step_portfolio = StepResult(
                    step_id=6, step_name="Portfolio", success=False, error=str(e),
                )
                result.errors.append(f"Step6: {e}")

            # ── Step 7: LLM Synthesis ──
            try:
                step_inputs_full = {
                    "evidence": result.step_evidence.structured_json,
                    "hypotheses": result.step_hypothesis.structured_json,
                    "counter": result.step_counter.structured_json,
                    "reflexivity": result.step_reflexivity.structured_json,
                    "history": result.step_history.structured_json,
                    "portfolio": result.step_portfolio.structured_json,
                }
                result.step_llm_synthesis = self._step7_llm_synthesis(
                    step_outputs=step_inputs_full,
                    date_str=date_str,
                    regime_result=regime_result,
                    narratives=narratives,
                )
                self._call_count += 1

                if self._last_routed_prompt:
                    result.routed_prompt = self._last_routed_prompt
                    result.selected_domains = self._last_routed_prompt.selected_domains

                if self._last_narrative_routed:
                    result.narrative_routed_prompt = self._last_narrative_routed
                    result.narrative_dominant = self._last_narrative_routed.dominant_narrative.primary.title
                    result.narrative_stance = self._last_narrative_routed.stance
                    if not result.selected_domains:
                        result.selected_domains = self._last_narrative_routed.selected_domains
                    result.prompt_router_used = "narrative"
                elif self._last_routed_prompt:
                    result.prompt_router_used = "domain"
                else:
                    result.prompt_router_used = "none"
            except Exception as e:
                logger.error("Step 7 (LLM Synthesis) failed: %s", e)
                result.step_llm_synthesis = StepResult(
                    step_id=7, step_name="LLM_Synthesis", success=False, error=str(e),
                )
                result.errors.append(f"Step7: {e}")

            # ── Step 8: Quality Review ──
            try:
                result.step_quality = self._step8_quality_review(
                    result.step_llm_synthesis.structured_json,
                    step_outputs={
                        "evidence": result.step_evidence.structured_json,
                        "counter": result.step_counter.structured_json,
                        "hypotheses": result.step_hypothesis.structured_json,
                        "reflexivity": result.step_reflexivity.structured_json,
                        "history": result.step_history.structured_json,
                        "portfolio": result.step_portfolio.structured_json,
                    },
                )
                result.memo_quality_score = result.step_quality.structured_json.get("quality_score", 0)
            except Exception as e:
                logger.error("Step 8 (Quality) failed: %s", e)
                result.step_quality = StepResult(
                    step_id=8, step_name="Quality_Review", success=False, error=str(e),
                )
                result.errors.append(f"Step8: {e}")

            # ── Step 9: Self-Review ──
            try:
                memo_json = result.step_llm_synthesis.structured_json
                step_outputs_full = {
                    "evidence": result.step_evidence.structured_json,
                    "hypotheses": result.step_hypothesis.structured_json,
                    "counter": result.step_counter.structured_json,
                    "reflexivity": result.step_reflexivity.structured_json,
                    "historical": result.step_history.structured_json,
                    "portfolio": result.step_portfolio.structured_json,
                }
                result.step_self_review = self._step9_self_review(
                    memo_json, step_outputs_full, regime_result, date_str,
                )

                if hasattr(self, "_last_self_review") and self._last_self_review:
                    result.self_review_revisions = self._last_self_review.total_revisions
                    result.self_review_delta = self._last_self_review.overall_improvement
                    result.self_review_passed = self._last_self_review.passed_threshold

                    if self._last_self_review.total_revisions > 0:
                        result.memo_text = self._last_self_review.final_memo_text
                        final_score = self._last_self_review.final_score
                        if final_score > result.memo_quality_score:
                            result.memo_quality_score = final_score

                    self._call_count += self._last_self_review.llm_calls
            except Exception as e:
                logger.warning("Step 9 (Self-Review) failed: %s", e)
                result.step_self_review = StepResult(
                    step_id=9, step_name="Self_Review", success=False, error=str(e),
                )
                result.errors.append(f"Step9: {e}")

            if not result.memo_text:
                memo_data = result.step_llm_synthesis.structured_json
                result.memo_text = memo_data.get("full_memo_text", memo_data.get("executive_summary", ""))

            # ── Step 10: Market Challenge ──
            try:
                step_outputs_full = {
                    "evidence": result.step_evidence.structured_json,
                    "hypotheses": result.step_hypothesis.structured_json,
                    "counter": result.step_counter.structured_json,
                    "reflexivity": result.step_reflexivity.structured_json,
                    "historical": result.step_history.structured_json,
                    "portfolio": result.step_portfolio.structured_json,
                }
                result.step_market_challenge = self._step10_market_challenge(
                    result.memo_text,
                    result.step_llm_synthesis.structured_json,
                    step_outputs_full,
                    market_data,
                )

                if self._last_market_challenge:
                    mc = self._last_market_challenge
                    result.market_challenge_score = mc.overall_score
                    result.market_challenge_tradeable = mc.tradeable
                    result.market_challenge_grade = mc.grade
                    result.market_challenge_sizing = mc.sizing_recommendation
            except Exception as e:
                logger.warning("Step 10 (Market Challenge) failed: %s", e)
                result.step_market_challenge = StepResult(
                    step_id=10, step_name="Market_Challenge", success=False, error=str(e),
                )
                result.errors.append(f"Step10: {e}")

            state.quality = result.memo_quality_score
            state.market_score = result.market_challenge_score

            # ════════════════════════════════════════════════════════
            # V10.2: Convergence Analysis
            # ════════════════════════════════════════════════════════
            state = ConvergenceAnalyzer.analyze(current=state, previous=prev_state)

            # Build trace entry
            trace_entry = self._build_trace_entry(state, evidence_retry_reasons, evidence_retries_used)
            reasoning_trace.append(trace_entry.to_dict())

            logger.info(
                "%s done: quality=%.1f mc=%.1f evidence=%.1f coverage=%.0f%% "
                "hyps=%d→%d evΔ=%.1f%% hyΔ=%.1f%% bΔ=%.1f%% mΔ=%.1f%% converged=%s",
                round_label, state.quality, state.market_score,
                state.evidence_score, state.evidence_coverage,
                state.hypothesis_count, state.surviving_hypotheses,
                state.evidence_delta_pct, state.hypothesis_delta_pct,
                state.belief_delta_pct, state.memo_delta_pct,
                state.is_converged,
            )

            # ── Converged? Stop. ──
            if iteration >= min_iterations and state.is_converged:
                logger.info(
                    "Research Loop converged at round %d: %s",
                    iteration, state.stop_reason,
                )
                break

            # ── Market Challenge Feedback ──
            if state.market_score < 60 and iteration < max_iterations:
                logger.warning(
                    "Market Challenge %.1f < 60 → returning to HypothesisBuilder",
                    state.market_score,
                )

            prev_state = state

        # ── Final: assemble result ──
        result.reasoning_trace = reasoning_trace
        result.total_elapsed_ms = (time.time() - t0) * 1000
        result.llm_call_count = self._call_count

        logger.info(
            "Pipeline %s complete: %.0fms, iterations=%d, quality=%.1f, llm_calls=%d, "
            "errors=%d, domains=%s, revisions=%d, narrative=%s, mc=%.0f/%s, "
            "evolution_entries=%d, stop=%s",
            pipeline_id, result.total_elapsed_ms, iteration, result.memo_quality_score,
            self._call_count, len(result.errors),
            result.selected_domains, result.self_review_revisions,
            result.narrative_dominant[:40] if result.narrative_dominant else "none",
            result.market_challenge_score, result.market_challenge_grade,
            len(reasoning_trace),
            prev_state.stop_reason if prev_state else "",
        )

        return result

    # ── Research Evolution Trace Builder ──────────────────────────

    def _build_trace_entry(
        self,
        state: LoopState,
        retry_reasons: list[str],
        retries_used: int,
    ) -> LoopTraceEntry:
        """Build a trace entry from LoopState for the Research Evolution Trace."""
        entry = LoopTraceEntry(round_number=state.iteration)
        entry.evidence_quality_score = state.evidence_score
        entry.evidence_retries_used = retries_used
        entry.evidence_retry_reasons = retry_reasons
        entry.hypotheses_before_count = state.hypothesis_count
        entry.hypotheses_after_count = state.surviving_hypotheses
        entry.deleted_hypothesis_ids = state.deleted_this_round
        entry.new_evidence_themes = state.new_sources_collected
        entry.memo_quality = state.quality
        entry.market_challenge_score = state.market_score
        entry.exit_reason = state.stop_reason

        if not state.should_continue and state.is_converged:
            entry.conclusion_change = f"Research converged: {state.stop_reason}"

        return entry

    def run_learning_cycle(
        self,
        predictions: list,
        outcomes: list,
        beliefs: list,
    ) -> Optional[Any]:
        """V10 Sprint 4: Run continuous learning after a benchmark cycle.

        Diagnoses prediction errors, updates beliefs/prompts/reasoning,
        and returns a LearningReport.

        Args:
            predictions: List of PredictionRecord objects.
            outcomes: List of OutcomeRecord objects.
            beliefs: Current belief list (mutated in-place).

        Returns:
            LearningReport or None if no predictions to learn from.
        """
        if not predictions or not outcomes:
            return None

        from src.research.reasoning.continuous_learning import ContinuousLearningLoop

        loop = ContinuousLearningLoop()
        return loop.run_cycle(
            predictions=predictions,
            outcomes=outcomes,
            beliefs=beliefs,
            used_domains=self._last_routed_prompt.selected_domains
            if self._last_routed_prompt else ["Growth"],
        )

    # ═════════════════════════════════════════════════════════════════
    
    def _step1_evidence(
        self,
        market_data: dict,
        narratives: list,
        beliefs: list,
        capital_flow_result: dict,
        regime_result: dict,
        news_events: list,
        date_str: str,
        retry_attempt: int = 0,
        visited_sources: Optional[set] = None,
        hypotheses_json: Optional[dict] = None,
    ) -> StepResult:
        """Step 1: Evidence Synthesis — deterministic.

        V10.1: Source-based Retry.
        On retry, the EvidenceSynthesizer runs gap analysis → source planning
        → simulated collection instead of theme rotation.

        Args:
            retry_attempt: 0=first pass, 1-2=retry
            visited_sources: Already-collected source names (for dedup)
            hypotheses_json: Current hypotheses (for gap analysis on retry)
        """
        t0 = time.time()

        from src.research.reasoning.evidence_synthesizer import EvidenceSynthesizer

        synthesizer = EvidenceSynthesizer()
        assessment = synthesizer.synthesize(
            market_data=market_data,
            narratives=narratives,
            beliefs=beliefs,
            capital_flow_result=capital_flow_result,
            regime_result=regime_result,
            news_events=news_events,
            retry_attempt=retry_attempt,
            visited_sources=visited_sources,
            hypotheses_json=hypotheses_json,
        )
        
        elapsed = (time.time() - t0) * 1000
        
        json_output = assessment.to_dict() if hasattr(assessment, "to_dict") else assessment
        cluster_count = len(assessment.clusters)
        
        result = StepResult(
            step_id=1, step_name="Evidence",
            success=True,
            structured_json=json_output,
            summary=f"Synthesized {cluster_count} evidence clusters from {len(assessment.clusters)} themes",
            elapsed_ms=elapsed,
        )
        # Store raw object for downstream consumers that need typed objects
        result._raw_assessment = assessment
        return result
    
    def _step2_hypothesis(
        self,
        evidence_json: dict,
        beliefs: list,
        regime_result: dict,
        narratives: list,
        raw_clusters: Optional[list] = None,
    ) -> StepResult:
        """Step 2: Hypothesis Generation — deterministic.

        Uses HypothesisBuilder to generate causal hypotheses from evidence clusters.
        Accepts raw EvidenceCluster objects when available (preferred over dicts).
        """
        t0 = time.time()
        
        from src.research.reasoning.hypothesis_builder import HypothesisBuilder
        from src.research.reasoning.schemas import Hypothesis, EvidenceCluster
        
        # Prefer raw EvidenceCluster objects (passed via _raw_assessment)
        # Fall back to dict conversion if not available
        if raw_clusters and all(hasattr(c, 'weight_score') for c in raw_clusters):
            clusters = raw_clusters
        else:
            # Convert dicts to EvidenceCluster objects
            clusters = []
            for c_dict in evidence_json.get("clusters", []):
                if hasattr(c_dict, "weight_score"):
                    clusters.append(c_dict)  # Already an object
                else:
                    try:
                        cluster = EvidenceCluster(
                            cluster_id=c_dict.get("cluster_id", ""),
                            theme=c_dict.get("theme", ""),
                            description=c_dict.get("description", ""),
                            evidence_items=c_dict.get("evidence_items", []),
                            net_direction=c_dict.get("net_direction", "neutral"),
                            weight_score=float(c_dict.get("weight_score", 0)),
                            quality_score=float(c_dict.get("quality_score", 0)),
                            recency_score=float(c_dict.get("recency_score", 0)),
                        )
                        clusters.append(cluster)
                    except Exception:
                        # Minimal fallback
                        cluster = EvidenceCluster(
                            cluster_id=c_dict.get("cluster_id", str(hash(str(c_dict)))),
                            theme=c_dict.get("theme", "unknown"),
                            weight_score=float(c_dict.get("weight_score", 0)),
                        )
                        clusters.append(cluster)
        
        builder = HypothesisBuilder()
        hypotheses = builder.build_hypotheses(
            evidence_clusters=clusters,
            beliefs=beliefs,
            regime_result=regime_result,
            narrative=narratives[0] if narratives else None,
        )
        
        elapsed = (time.time() - t0) * 1000
        
        json_output = {
            "hypotheses": [h.to_dict() for h in hypotheses],
            "hypothesis_count": len(hypotheses),
            "dominant_hypothesis": hypotheses[0].title if hypotheses else "",
            "avg_confidence": round(sum(h.confidence for h in hypotheses) / len(hypotheses), 2) if hypotheses else 0,
        }
        
        return StepResult(
            step_id=2, step_name="Hypothesis",
            success=True,
            structured_json=json_output,
            summary=f"Generated {len(hypotheses)} hypotheses, dominant: {json_output['dominant_hypothesis']}",
            elapsed_ms=elapsed,
        )
    
    def _step3_counter(
        self,
        hypothesis_json: dict,
        evidence_json: dict,
        regime_result: dict,
        excluded_hypothesis_ids: Optional[set] = None,
    ) -> StepResult:
        """Step 3: Counter Argument Generation + Hypothesis Elimination.

        Sprint 4.6: Now eliminates at least 1 weak hypothesis per round.
        Previously eliminated hypotheses are skipped automatically.

        Uses CounterArgumentGenerator to systematically challenge every hypothesis
        and return elimination decisions.
        """
        t0 = time.time()

        from src.research.reasoning.counter_argument_generator import CounterArgumentGenerator
        from src.research.reasoning.schemas import Hypothesis, CounterArgument

        # Reconstruct Hypothesis objects from JSON, skipping previously eliminated
        hypotheses = []
        excluded = excluded_hypothesis_ids or set()
        for h_dict in hypothesis_json.get("hypotheses", []):
            hid = h_dict.get("hypothesis_id", "")
            if hid in excluded:
                continue
            hyp = Hypothesis(
                hypothesis_id=hid,
                title=h_dict.get("title", ""),
                statement=h_dict.get("statement", ""),
                domain=h_dict.get("domain", ""),
                causal_chain=h_dict.get("causal_chain", []),
                confidence=h_dict.get("confidence", 0.5),
                evidence_weight=h_dict.get("evidence_weight", 0),
            )
            hypotheses.append(hyp)

        if not hypotheses:
            return StepResult(
                step_id=3, step_name="Counter",
                success=True,
                structured_json={
                    "counter_arguments": [],
                    "primary_counter_risk": "",
                    "eliminated_hypothesis_ids": list(excluded),
                    "elimination_reasons": {},
                },
                summary="No hypotheses to counter (all eliminated)",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        generator = CounterArgumentGenerator()
        counters, eliminated_ids, elimination_reasons = generator.generate(
            hypotheses=hypotheses,
            evidence_clusters=evidence_json.get("clusters", []),
            regime_result=regime_result,
        )

        elapsed = (time.time() - t0) * 1000

        fatal_count = sum(1 for c in counters if c.severity == "fatal")
        major_count = sum(1 for c in counters if c.severity == "major")

        json_output = {
            "counter_arguments": [c.to_dict() for c in counters],
            "counter_count": len(counters),
            "fatal_counter_count": fatal_count,
            "major_counter_count": major_count,
            "primary_counter_risk": counters[0].title if counters else "",
            # Sprint 4.6: Elimination tracking
            "eliminated_hypothesis_ids": eliminated_ids,
            "elimination_reasons": elimination_reasons,
        }

        summary = f"Generated {len(counters)} counter-arguments (fatal={fatal_count}, major={major_count})"
        if eliminated_ids:
            summary += f", eliminated {len(eliminated_ids)} hypotheses"

        return StepResult(
            step_id=3, step_name="Counter",
            success=True,
            structured_json=json_output,
            summary=summary,
            elapsed_ms=elapsed,
        )
    
    def _step4_reflexivity(
        self,
        market_data: dict,
        beliefs: list,
        capital_flow_result: Optional[dict],
        narratives: list,
    ) -> StepResult:
        """Step 4: Reflexivity Analysis — deterministic.
        
        Uses ReflexivityCycleDetector to identify self-reinforcing
        narrative-capital-price feedback loops.
        """
        t0 = time.time()
        
        from src.research.reflexivity.reflexivity_cycle_detector import ReflexivityCycleDetector
        from src.research.reflexivity.schemas import MarketBelief
        
        detector = ReflexivityCycleDetector()
        
        # Convert belief dicts to MarketBelief if needed
        belief_objects = []
        for b in (beliefs or []):
            if hasattr(b, "strength"):
                belief_objects.append(b)
            elif isinstance(b, dict):
                try:
                    mbl = MarketBelief(
                        belief_id=b.get("id", b.get("belief_id", "")),
                        name=b.get("name", b.get("label", "")),
                        strength=float(b.get("confidence", b.get("prior_mean", 0.5))),
                        direction=b.get("direction", "neutral"),
                        stage=b.get("stage", "forming"),
                        consensus_level=float(b.get("consensus", b.get("consensus_level", 0.5))),
                    )
                    belief_objects.append(mbl)
                except Exception:
                    pass
        
        dominant_narrative = ""
        if narratives:
            n = narratives[0]
            if isinstance(n, dict):
                dominant_narrative = n.get("summary", n.get("content", ""))
            elif hasattr(n, "summary"):
                dominant_narrative = n.summary
        
        report = detector.detect(
            market_data=market_data,
            beliefs=belief_objects if belief_objects else None,
            flows=None,
            dominant_narrative=dominant_narrative,
            narrative_objects=narratives if narratives else None,
        )
        
        elapsed = (time.time() - t0) * 1000
        
        json_output = report.to_dict() if hasattr(report, "to_dict") else report
        
        cycles = json_output.get("active_cycles", []) if isinstance(json_output, dict) else []
        vuln_score = json_output.get("vulnerability_score", 0) if isinstance(json_output, dict) else 0
        
        return StepResult(
            step_id=4, step_name="Reflexivity",
            success=True,
            structured_json=json_output if isinstance(json_output, dict) else {"report": str(json_output)},
            summary=f"Detected {len(cycles)} reflexivity cycles, vulnerability={vuln_score}",
            elapsed_ms=elapsed,
        )
    
    def _step5_history(
        self,
        regime_result: dict,
        market_data: dict,
    ) -> StepResult:
        """Step 5: Historical Analogies — deterministic.
        
        Uses HistoricalSimilarity to find analogous historical periods.
        Handles both dict and object input for regime_result.
        """
        t0 = time.time()
        
        from src.regime.historical_similarity import HistoricalSimilarity
        from src.regime.schemas import MacroRegime
        
        similarity = HistoricalSimilarity()
        
        # Convert dict to MacroRegime if needed (HistoricalSimilarity accesses .growth_phase etc.)
        if isinstance(regime_result, dict):
            regime_obj = MacroRegime(
                regime_label=regime_result.get("regime_label", regime_result.get("regime_type", "")),
                growth_phase=regime_result.get("growth_phase", "stable"),
                inflation_regime=regime_result.get("inflation_regime", "disinflation"),
                monetary_stance=regime_result.get("monetary_stance", "neutral"),
                credit_cycle=regime_result.get("credit_cycle", "expansion"),
                dollar_regime=regime_result.get("dollar_regime", regime_result.get("dollar", "neutral")),
                volatility_regime=regime_result.get("volatility_regime", "moderate"),
            )
        elif hasattr(regime_result, "growth_phase"):
            regime_obj = regime_result
        else:
            return StepResult(
                step_id=5, step_name="Historical",
                success=True,
                structured_json={"analogs": [], "analog_count": 0, "top_similarity": 0},
                summary="Cannot perform historical analysis (no valid regime data)",
                elapsed_ms=(time.time() - t0) * 1000,
            )
        
        analogs = similarity.find_analogs(
            current_regime=regime_obj,
            top_n=5,
        )
        
        elapsed = (time.time() - t0) * 1000
        
        json_output = {
            "analogs": [a.to_dict() if hasattr(a, "to_dict") else a for a in analogs],
            "analog_count": len(analogs),
            "top_similarity": analogs[0].similarity_score if analogs and hasattr(analogs[0], "similarity_score") else (analogs[0].get("similarity_score", 0) if analogs else 0),
        }
        
        return StepResult(
            step_id=5, step_name="Historical",
            success=True,
            structured_json=json_output,
            summary=f"Found {len(analogs)} historical analogs, top similarity={json_output['top_similarity']:.2f}",
            elapsed_ms=elapsed,
        )
    
    def _step6_portfolio(
        self,
        regime_result: dict,
        beliefs: list,
        hypothesis_json: dict,
        capital_flow_result: Optional[dict],
        narratives: list,
        counter_json: dict,
    ) -> StepResult:
        """Step 6: Portfolio Impact — deterministic.
        
        Uses PortfolioAdvisor to map macro analysis to asset allocation.
        """
        t0 = time.time()
        
        from src.research.portfolio_advisor import PortfolioAdvisor
        
        advisor = PortfolioAdvisor()
        
        # Extract regime label
        regime_label = regime_result.get("regime_label", regime_result.get("regime_type", ""))
        regime_confidence = float(regime_result.get("confidence", 0.5))
        
        # Convert beliefs to dicts if needed
        belief_dicts = []
        for b in (beliefs or []):
            if isinstance(b, dict):
                belief_dicts.append(b)
            elif hasattr(b, "to_dict"):
                belief_dicts.append(b.to_dict())
        
        # Extract predictions from hypotheses
        predictions = []
        for h in hypothesis_json.get("hypotheses", []):
            if h.get("if_true_implication"):
                predictions.append({
                    "statement": h.get("statement", ""),
                    "asset": h.get("domain", ""),
                    "direction": "bullish" if h.get("confidence", 0) > 0.5 else "bearish",
                    "confidence": h.get("confidence", 0),
                })
        
        # Extract risks from counter arguments
        risks = []
        for c in counter_json.get("counter_arguments", []):
            risks.append({
                "name": c.get("title", ""),
                "probability": c.get("probability", 0),
                "severity": c.get("severity", ""),
                "triggers": c.get("trigger_conditions", []),
            })
        
        # Narrative strings
        narrative_strs = []
        for n in (narratives or []):
            if isinstance(n, dict):
                narrative_strs.append(n.get("summary", n.get("content", "")))
            elif hasattr(n, "summary"):
                narrative_strs.append(n.summary)
        
        rec = advisor.recommend(
            regime=regime_label,
            regime_confidence=regime_confidence,
            beliefs=belief_dicts if belief_dicts else None,
            narratives=narrative_strs if narrative_strs else None,
            capital_flows=capital_flow_result,
            predictions=predictions if predictions else None,
            risks=risks if risks else None,
        )
        
        elapsed = (time.time() - t0) * 1000
        
        json_output = rec.to_dict() if hasattr(rec, "to_dict") else rec
        
        return StepResult(
            step_id=6, step_name="Portfolio",
            success=True,
            structured_json=json_output if isinstance(json_output, dict) else {"recommendation": str(json_output)},
            summary=f"Portfolio stance: {rec.overall_stance if hasattr(rec, 'overall_stance') else 'N/A'}",
            elapsed_ms=elapsed,
        )
    
    def _step7_llm_synthesis(
        self,
        step_outputs: dict[str, dict],
        date_str: str,
        regime_result: Optional[dict] = None,
        narratives: Optional[list] = None,
    ) -> StepResult:
        """Step 7: LLM Synthesis — THE ONLY LLM CALL in the pipeline.

        LLM receives ONLY structured reasoning results from Steps 1-6.
        NO raw market data is passed to the LLM.

        V10 Sprint 4.5 Task 1: Narrative-driven Prompt Routing (priority).
        If narratives are available, dynamically builds prompt around dominant narrative.
        Falls back to Sprint 2's domain-based PromptRouter if no narratives.
        """
        t0 = time.time()

        # Sprint 4.5 Task 1: Try narrative-driven routing first
        narrative_routed = None
        domain_routed = None

        if narratives and len(narratives) > 0:
            try:
                from src.research.reasoning.narrative_prompt_router import NarrativePromptRouter
                npr = NarrativePromptRouter()
                narrative_routed = npr.route(
                    narratives=narratives,
                    regime_result=regime_result or {},
                    step_outputs=step_outputs,
                )
                self._last_narrative_routed = narrative_routed
                logger.info(
                    "Sprint4.5 NarrativeRouter: dominant=%s, stance=%s, domains=%s",
                    narrative_routed.dominant_narrative.primary.title[:50],
                    narrative_routed.stance,
                    narrative_routed.selected_domains,
                )
            except Exception as e:
                logger.warning("NarrativePromptRouter failed: %s, falling back", e)

        # Sprint 2: Always run domain router as fallback
        from src.research.reasoning.prompt_router import PromptRouter
        router = PromptRouter()
        domain_routed = router.route(
            regime_result=regime_result or {},
            step_outputs=step_outputs,
        )
        self._last_routed_prompt = domain_routed
        logger.info(
            "Sprint2 PromptRouter: domains=%s, hybrid=%s, regime=%s",
            domain_routed.selected_domains, domain_routed.is_hybrid,
            domain_routed.regime_label,
        )

        client = self._get_llm_client()
        if client is None:
            # No LLM available — use deterministic memo writer
            return self._step7_fallback_deterministic(step_outputs, date_str, t0)

        # Prefer narrative prompt if available, else domain prompt
        if narrative_routed and narrative_routed.system_prompt:
            system_prompt = narrative_routed.system_prompt
            used_domains = narrative_routed.selected_domains
            prompt_source = "narrative"
        else:
            system_prompt = domain_routed.system_prompt or _FALLBACK_SYNTHESIS_PROMPT
            used_domains = domain_routed.selected_domains
            prompt_source = "domain"

        # Retrieve past reasoning failures for context (Sprint 4.5 Task 3)
        retrieval_context = ""
        if self._reasoning_evolution:
            try:
                retrieval = self._reasoning_evolution.retrieve_for_reasoning(
                    query_context=str(step_outputs)[:2000],
                    domains=used_domains,
                    regime=regime_result.get("regime_label", "") if regime_result else "",
                )
                if retrieval and retrieval.retrieval_context:
                    retrieval_context = "\n\n" + retrieval.retrieval_context
                    logger.info(
                        "ReasoningEvolution: injected %d past failure cases as context",
                        retrieval.total_matches,
                    )
            except Exception as e:
                logger.debug("ReasoningEvolution retrieval skipped: %s", e)

        user_prompt = _build_synthesis_user_prompt(step_outputs)
        # Inject past failure context into the user prompt
        if retrieval_context:
            user_prompt = retrieval_context + "\n\n---\n\n" + user_prompt

        response = client.research_chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
        )

        elapsed = (time.time() - t0) * 1000

        # Build routing metadata
        routing_meta = {
            "prompt_source": prompt_source,
            "domains": used_domains,
            "narrative": (
                self._last_narrative_routed.to_dict()
                if self._last_narrative_routed else {}
            ),
            "domain_routing": domain_routed.to_dict(),
        }

        if response.success and response.parsed_json:
            memo_data = response.parsed_json
            memo_data["_prompt_routing"] = routing_meta
            summary = f"LLM synthesis via {prompt_source} prompt [{', '.join(used_domains)}]"
        elif response.content:
            from src.research.llm_brain.llm_client import extract_json_from_text
            memo_data = extract_json_from_text(response.content) or {
                "full_memo_text": response.content,
                "executive_summary": response.content[:300],
            }
            memo_data["_prompt_routing"] = routing_meta
            summary = (
                f"LLM synthesis via {prompt_source} prompt "
                f"[{', '.join(used_domains)}] (JSON extracted)"
            )
        else:
            return self._step7_fallback_deterministic(step_outputs, date_str, t0)

        return StepResult(
            step_id=7, step_name="LLM_Synthesis",
            success=True,
            structured_json=memo_data,
            summary=summary,
            elapsed_ms=elapsed,
        )
    
    def _step7_fallback_deterministic(
        self,
        step_outputs: dict[str, dict],
        date_str: str,
        t0: float,
    ) -> StepResult:
        """Deterministic fallback when LLM is unavailable."""
        elapsed = (time.time() - t0) * 1000
        
        from src.research.reasoning.memo_writer import MemoWriter
        from src.research.reasoning.schemas import Hypothesis, CounterArgument
        
        writer = MemoWriter()
        
        # Reconstruct objects for MemoWriter
        hypotheses = []
        for h_dict in step_outputs.get("hypotheses", {}).get("hypotheses", []):
            hypotheses.append(Hypothesis(
                hypothesis_id=h_dict.get("hypothesis_id", ""),
                title=h_dict.get("title", ""),
                statement=h_dict.get("statement", ""),
                domain=h_dict.get("domain", ""),
                causal_chain=h_dict.get("causal_chain", []),
                confidence=h_dict.get("confidence", 0.5),
                evidence_weight=h_dict.get("evidence_weight", 0),
                if_true_implication=h_dict.get("if_true_implication", ""),
            ))
        
        counters = []
        for c_dict in step_outputs.get("counter", {}).get("counter_arguments", []):
            counters.append(CounterArgument(
                counter_id=c_dict.get("counter_id", ""),
                title=c_dict.get("title", ""),
                argument=c_dict.get("argument", ""),
                severity=c_dict.get("severity", ""),
                probability=c_dict.get("probability", 0),
                trigger_conditions=c_dict.get("trigger_conditions", []),
            ))
        
        evidence_json = step_outputs.get("evidence", {})
        regime_label = step_outputs.get("portfolio", {}).get("regime",
                       step_outputs.get("portfolio", {}).get("overall_stance", "unknown"))
        
        # Build minimal EvidenceAssessment from dict
        from src.research.reasoning.schemas import EvidenceAssessment, EvidenceCluster
        
        clusters = []
        for c_dict in evidence_json.get("clusters", []):
            clusters.append(EvidenceCluster(
                cluster_id=c_dict.get("cluster_id", f"c{len(clusters)}"),
                theme=c_dict.get("theme", "unknown"),
                description=c_dict.get("description", c_dict.get("theme", "")),
                weight_score=float(c_dict.get("weight_score", 0)),
                evidence_items=c_dict.get("evidence_items", []),
            ))
        evidence_assessment = EvidenceAssessment(
            clusters=clusters,
            total_evidence_points=len(evidence_json.get("clusters", [])),
            net_direction=evidence_json.get("net_direction", "mixed"),
            evidence_quality=evidence_json.get("overall_quality", "moderate"),
        )
        
        memo = writer.write_memo(
            evidence_assessment=evidence_assessment,
            hypotheses=hypotheses,
            counter_arguments=counters,
            regime_result={"regime_label": regime_label, "regime_type": regime_label},
            date_str=date_str,
        )
        
        memo_data = memo.to_dict()
        
        return StepResult(
            step_id=7, step_name="LLM_Synthesis",
            success=True,
            structured_json=memo_data,
            summary="Deterministic synthesis (LLM unavailable)",
            elapsed_ms=elapsed,
        )
    
    def _step8_quality_review(
        self,
        memo_json: dict,
        step_outputs: dict[str, dict],
    ) -> StepResult:
        """Step 8: Quality Review — deterministic.
        
        Evaluates the synthesized memo against quality criteria:
        completeness, evidence coverage, counter-argument coverage, etc.
        """
        t0 = time.time()
        
        review = _compute_quality_review(memo_json, step_outputs)
        
        elapsed = (time.time() - t0) * 1000
        
        return StepResult(
            step_id=8, step_name="Quality_Review",
            success=True,
            structured_json=review,
            summary=f"Quality score: {review['quality_score']}/100 (Grade {review['grade']})",
            elapsed_ms=elapsed,
        )

    def _step9_self_review(
        self,
        memo_json: dict,
        step_outputs: dict[str, dict],
        regime_result: Optional[dict],
        date_str: str,
    ) -> StepResult:
        """Step 9: Self-Review — V10 Sprint 3.

        Reviewer → Critic → Challenge → Rewrite → Score loop.
        Continues until quality >= 90 or max 3 revisions.

        Only the Rewrite step uses LLM. Reviewer and Critic are deterministic.
        """
        t0 = time.time()

        # Get the memo text
        memo_text = memo_json.get("full_memo_text", "")
        if not memo_text:
            memo_text = memo_json.get("executive_summary", "") + "\n"
            memo_text += json.dumps(memo_json.get("evidence_summary", ""), ensure_ascii=False)

        if not memo_text.strip():
            return StepResult(
                step_id=9, step_name="Self_Review",
                success=True,
                structured_json={"revisions": 0, "passed": True, "note": "Empty memo, skipping review"},
                summary="Self-review skipped (empty memo)",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        from src.research.reasoning.memo_reviewer import MemoSelfReviewPipeline

        # Get LLM client for rewrites
        llm_client = self._get_llm_client()

        reviewer = MemoSelfReviewPipeline(llm_client=llm_client)
        result = reviewer.review_and_improve(
            memo_text=memo_text,
            step_outputs=step_outputs,
            regime_result=regime_result,
            date_str=date_str,
        )

        elapsed = (time.time() - t0) * 1000

        # Store self-review info on pipeline result
        self._last_self_review = result

        # Build structured output
        review_json = {
            "initial_score": result.initial_score,
            "final_score": result.final_score,
            "total_revisions": result.total_revisions,
            "passed_threshold": result.passed_threshold,
            "overall_improvement": result.overall_improvement,
            "final_grade": result.final_grade,
            "llm_calls": result.llm_calls,
            "revisions": [
                {
                    "revision": r.revision_number,
                    "before_score": r.before_score,
                    "after_score": r.after_score,
                    "delta": r.improvement_delta,
                }
                for r in result.revisions
            ],
            "final_memo": result.final_memo_text,
        }

        status = "PASS" if result.passed_threshold else f"stopped after {result.total_revisions} revisions"

        return StepResult(
            step_id=9, step_name="Self_Review",
            success=True,
            structured_json=review_json,
            summary=(
                f"Self-review: {result.initial_score:.0f}→{result.final_score:.0f} "
                f"(Δ{result.overall_improvement:+.0f}), "
                f"{result.total_revisions} revisions, threshold {status}"
            ),
            elapsed_ms=elapsed,
        )

    def _step10_market_challenge(
        self,
        memo_text: str,
        memo_json: dict,
        step_outputs: dict[str, dict],
        market_data: dict,
    ) -> StepResult:
        """Step 10: Market Challenge — V10 Sprint 4.5 Task 2.

        NOT a quality/grammar review. Checks TRADING VALUE:
            Consensus? Crowded? Positioning? Catalyst? Market Reaction?

        Deterministic — no LLM call.
        """
        t0 = time.time()

        from src.research.reasoning.market_challenge import MarketChallenge

        challenger = MarketChallenge()
        result = challenger.challenge(
            memo_text=memo_text,
            memo_json=memo_json,
            step_outputs=step_outputs,
            market_context=market_data,
        )
        self._last_market_challenge = result

        elapsed = (time.time() - t0) * 1000

        summary = (
            f"Market Challenge: {result.overall_score:.0f}/100 "
            f"(Grade {result.grade}), T={'TRADEABLE' if result.tradeable else 'PASS'}, "
            f"Size: {result.sizing_recommendation}, "
            f"Key concern: {result.key_concern}"
        )

        return StepResult(
            step_id=10, step_name="Market_Challenge",
            success=True,
            structured_json=result.to_dict(),
            summary=summary,
            elapsed_ms=elapsed,
        )

    # ═══════════════════════════════════════════════════════════════════
    # Sprint 4.5 Task 3: Reasoning Evolution Engine
    # ═══════════════════════════════════════════════════════════════════

    @property
    def reasoning_evolution(self):
        """Get or create reasoning evolution engine (lazy init)."""
        if self._reasoning_evolution is None:
            from src.research.reasoning.reasoning_evolution import ReasoningEvolutionEngine
            self._reasoning_evolution = ReasoningEvolutionEngine()
        return self._reasoning_evolution

    def run_reasoning_evolution(
        self,
        predictions: list[dict],
        outcomes: list[dict],
        pipeline_results: Optional[list] = None,
    ) -> Optional[Any]:
        """V10 Sprint 4.5 Task 3: Evolve reasoning templates from outcomes.

        Unlike belief updates (Sprint 4), this creates REUSABLE REASONING PATTERNS:
            Old reasoning → Mistake → New reasoning → Reasoning Library

        Future reasoning steps will automatically retrieve past failures
        and inject them as context (handled automatically in Step 7).

        Args:
            predictions: List of prediction dicts.
            outcomes: List of outcome dicts.
            pipeline_results: Optional list of PipelineResult objects.

        Returns:
            EvolutionReport with cases created, templates updated, patterns found.
        """
        engine = self.reasoning_evolution
        report = engine.process_batch(predictions, outcomes, pipeline_results)

        logger.info(
            "ReasoningEvolution: %d cases created, %d templates updated, "
            "library size=%d, patterns: %s",
            report.cases_created, report.templates_updated,
            report.library_size, report.patterns_discovered,
        )

        return report

    def get_reasoning_library_stats(self) -> dict:
        """Get reasoning library statistics."""
        engine = self.reasoning_evolution
        return engine.get_library_stats()

    # ── LLM Client ────────────────────────────────────────────────────
    
    def _get_llm_client(self):
        """Get or create the LLM client (lazy initialization).
        
        Reads model from: constructor arg > LLM_MODEL env var > default.
        Reads base_url from: constructor arg > OPENAI_BASE_URL env var > default.
        """
        if self._llm_client is not None:
            return self._llm_client
        
        try:
            from src.research.llm_brain.llm_client import LLMClient
            
            kwargs = {}
            # Model: explicit > env var > default
            model = self._llm_model or os.environ.get("LLM_MODEL", "gpt-4o")
            kwargs["model"] = model
            # Base URL: explicit > env var > default
            base_url = self._llm_base_url or os.environ.get("OPENAI_BASE_URL", "")
            if base_url:
                kwargs["base_url"] = base_url
            
            self._llm_client = LLMClient(**kwargs)
            
            # Check if actually usable
            health = self._llm_client.health_check()
            if health.get("status") != "ok":
                logger.warning("LLM client not healthy: %s", health)
                self._llm_client = None
                return None
            
            return self._llm_client
        except Exception as e:
            logger.warning("LLM client unavailable, using deterministic fallback: %s", e)
            self._llm_client = None
            return None
