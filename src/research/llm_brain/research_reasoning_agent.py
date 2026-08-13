"""ResearchReasoningAgent — The V3.4 reasoning brain.

Transforms structured macro analysis data into deep ResearchMemos using LLM
reasoning. This is the bridge from "reading the world" to "understanding it."

Architecture:
    Input (Structured Data) → Prompt Building → LLM Call → Parse → ResearchMemo
    ├── MacroStateVector (regime, market data)
    ├── MentalModels (thinking frameworks)
    ├── Narratives (detected + competed)
    └── Beliefs (existing convictions)
            ↓
    PromptArchitecture composes context + few-shot + instructions
            ↓
    LLMClient executes deep reasoning
            ↓
    Structured JSON → ResearchMemo dataclass
            ↓
    Fallback: Rule-based memo when LLM unavailable

Design:
    - Primary path: LLM deep reasoning
    - Fallback path: Rule-based memo synthesis (ensures system always works)
    - Hybrid mode: Rule-based structural analysis + LLM judgment overlay
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.research.llm_brain.llm_client import LLMClient, LLMResponse
from src.research.llm_brain.prompts import (
    PromptArchitecture,
)
from src.research.llm_brain.schemas import (
    AssetImplication,
    BeliefSynthesis,
    CausalAnalysis,
    ConfidenceCalibration,
    EvidenceAssessment,
    FalsificationCheck,
    NarrativeAnalysis,
    RegimeAnalysis,
    ResearchMemo,
    TailRisk,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Input data container
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ReasoningInput:
    """All structured data that feeds into the reasoning agent."""

    # Regime
    regime_label: str = ""
    regime_confidence: float = 0.0
    regime_dimensions: dict = field(default_factory=dict)

    # Market data — raw indicators
    market_indicators: dict = field(default_factory=dict)
    market_summary: str = ""

    # Narratives (from NarrativeCompetition / NarrativeReasoner)
    dominant_narrative: str = ""
    narrative_confidence: float = 0.0
    competing_narratives: list[dict] = field(default_factory=list)
    narrative_stage: str = ""

    # Beliefs (from BeliefEngine)
    core_beliefs: list[str] = field(default_factory=list)
    belief_confidence: float = 0.0
    active_mental_models: list[str] = field(default_factory=list)

    # Research Judgment (from V3.2 ResearchJudgment)
    judgment_text: str = ""
    judgment_confidence: float = 0.0
    falsification_conditions: list[str] = field(default_factory=list)

    # Meta
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    case_id: str = ""

    # Additional context
    historical_context: str = ""
    recent_events: list[str] = field(default_factory=list)

    # V10: Blind test support — prevents hindsight bias
    blind_test_date: str = ""  # e.g. "2022-01" — agent only sees data before this
    blind_test_title: str = ""  # Case title for the blind test preamble

    def to_context_string(self) -> str:
        """Build a comprehensive context string for the LLM prompt."""
        parts = []

        # Regime
        parts.append(f"### Regime: {self.regime_label} (置信度: {self.regime_confidence:.2f})")
        if self.regime_dimensions:
            dims = ", ".join(f"{k}: {v}" for k, v in self.regime_dimensions.items())
            parts.append(f"各维度: {dims}")

        # Market data
        if self.market_indicators:
            parts.append("\n### 市场数据")
            items = []
            for k, v in self.market_indicators.items():
                if isinstance(v, float):
                    items.append(f"  {k}: {v:.2f}")
                else:
                    items.append(f"  {k}: {v}")
            parts.append("\n".join(items))
        if self.market_summary:
            parts.append(f"\n市场摘要: {self.market_summary}")

        # Narratives
        parts.append("\n### 叙事")
        parts.append(
            f"主导叙事: {self.dominant_narrative} (置信度: {self.narrative_confidence:.2f})"
        )
        if self.narrative_stage:
            parts.append(f"叙事阶段: {self.narrative_stage}")
        if self.competing_narratives:
            parts.append("竞争叙事:")
            for cn in self.competing_narratives[:5]:
                title = cn.get("title", cn.get("dominant", str(cn)[:60]))
                prob = cn.get("probability", cn.get("confidence", "?"))
                parts.append(f"  - {title} (概率: {prob})")

        # Beliefs
        if self.core_beliefs:
            parts.append(f"\n### 既有信念 (置信度: {self.belief_confidence:.2f})")
            for b in self.core_beliefs[:5]:
                parts.append(f"  - {b}")
        if self.active_mental_models:
            parts.append(f"\n活跃心理模型: {', '.join(self.active_mental_models)}")

        # Judgment
        if self.judgment_text:
            parts.append(f"\n### V3.2 研究判断 (置信度: {self.judgment_confidence:.2f})")
            parts.append(self.judgment_text[:500])
        if self.falsification_conditions:
            parts.append("证伪条件:")
            for fc in self.falsification_conditions[:5]:
                parts.append(f"  - {fc}")

        # Historical context
        if self.historical_context:
            parts.append(f"\n### 历史背景\n{self.historical_context}")
        if self.recent_events:
            parts.append(f"\n最近事件: {', '.join(self.recent_events[:5])}")

        return "\n".join(parts)

    def to_prompt_args(self) -> dict:
        """Build keyword arguments for MACRO_REASONING_PROMPT.format()."""
        return {
            "timestamp": self.timestamp,
            "regime_snapshot": f"{self.regime_label} (置信度: {self.regime_confidence:.2f})\n"
            f"维度: {json.dumps(self.regime_dimensions, ensure_ascii=False)}",
            "market_data": (
                json.dumps(self.market_indicators, indent=2, ensure_ascii=False)
                if self.market_indicators
                else self.market_summary
            ),
            "existing_beliefs": (
                "\n".join(f"- {b}" for b in self.core_beliefs)
                if self.core_beliefs
                else "无既有信念"
            ),
            "active_narratives": (
                f"主导: {self.dominant_narrative} (阶段: {self.narrative_stage})\n"
                f"竞争: {json.dumps(self.competing_narratives[:5], ensure_ascii=False)}"
                if self.competing_narratives
                else self.dominant_narrative
            ),
            "mental_models": (
                ", ".join(self.active_mental_models)
                if self.active_mental_models
                else "默认: 多模型综合"
            ),
            # V10: Blind test parameters
            "blind_test_date": self.blind_test_date,
            "blind_test_title": self.blind_test_title,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Rule-based fallback memo generator
# ═══════════════════════════════════════════════════════════════════════════


def _rule_based_memo(input_data: ReasoningInput) -> ResearchMemo:
    """Generate a ResearchMemo without LLM (rule-based fallback).

    Uses the structured data from V3.2 pipeline to produce a reasonable memo.
    This ensures the system degrades gracefully when LLM is unavailable.
    """

    # Regime analysis from inputs
    valid_dims = {"growth", "inflation", "monetary", "risk", "credit"}
    dim_assessments = {
        f"{k}_assessment": str(v)
        for k, v in input_data.regime_dimensions.items()
        if k in valid_dims
    }
    regime = RegimeAnalysis(
        regime_label=input_data.regime_label,
        regime_confidence=input_data.regime_confidence,
        regime_transition_risk=0.3,  # Conservative default
        next_regime_candidates=[],
        regime_duration_estimate="不确定 (无LLM推理)",
        defining_characteristics=list(input_data.regime_dimensions.values())[:5],
        historical_analogs=[],
        **dim_assessments,
    )

    # Narrative analysis
    narrative = NarrativeAnalysis(
        dominant_narrative=input_data.dominant_narrative,
        narrative_confidence=input_data.narrative_confidence,
        narrative_stage=input_data.narrative_stage or "未知",
        competing_narratives=input_data.competing_narratives[:3],
        narrative_risks=[],
    )

    # Causal (minimal from available data)
    causal = CausalAnalysis(
        primary_causal_chain=[],
        counterfactual_scenarios=[],
        key_causal_assumptions=[],
    )

    # Evidence from market data
    evidence_items = []
    for k, v in input_data.market_indicators.items():
        if isinstance(v, (int, float)):
            evidence_items.append({"signal": k, "strength": "moderate", "value": v})
    evidence = EvidenceAssessment(
        supporting_evidence=evidence_items[:8],
        evidence_quality="low (rule-based, no LLM reasoning)",
    )

    # Belief synthesis
    belief = BeliefSynthesis(
        core_belief=input_data.core_beliefs[0] if input_data.core_beliefs else "",
        belief_confidence=input_data.belief_confidence,
        belief_models_used=input_data.active_mental_models,
        highest_conviction_view=input_data.judgment_text[:200] if input_data.judgment_text else "",
        belief_update_triggers=input_data.falsification_conditions,
    )

    # Falsification
    falsification = FalsificationCheck(
        falsification_conditions=[
            {"condition": c, "severity": "major"} for c in input_data.falsification_conditions[:5]
        ],
        current_falsification_status="monitoring",
        base_case_if_wrong="需要LLM推理评估 (当前为规则引擎输出)",
    )

    # Assets — conservative
    assets = AssetImplication(
        asset_views=[],
        portfolio_positioning="neutral (保守默认, 无LLM推理)",
    )

    # Tail risk
    tail_risk = TailRisk(
        fat_tail_assessment="elevated (保守默认)",
    )

    # Confidence — conservative default
    confidence = ConfidenceCalibration(
        overall_confidence=min(
            input_data.regime_confidence,
            input_data.narrative_confidence,
            input_data.judgment_confidence,
            input_data.belief_confidence,
            0.6,  # Cap at 0.6 for rule-based
        ),
        confidence_breakdown={
            "regime": input_data.regime_confidence,
            "narrative": input_data.narrative_confidence,
            "causal": 0.4,
            "asset_view": 0.35,
        },
        calibration_note="规则引擎输出, 置信度保守校准",
        key_uncertainties=["需要LLM深度推理来识别不确定性"],
    )

    return ResearchMemo(
        memo_id=input_data.case_id or f"memo-{int(time.time())}",
        title=f"宏观研究报告: {input_data.regime_label} regime",
        executive_summary=(
            f"当前处于 {input_data.regime_label} regime。"
            f"主导叙事: {input_data.dominant_narrative[:100]}。"
            f"\n注意: 此分析由规则引擎生成(非LLM)，推理深度有限。"
        ),
        one_sentence_view=input_data.judgment_text[:150] if input_data.judgment_text else "",
        conviction_level="low",
        regime=regime,
        narrative=narrative,
        causal=causal,
        evidence=evidence,
        belief=belief,
        falsification=falsification,
        assets=assets,
        tail_risk=tail_risk,
        confidence=confidence,
        reasoning_mode="rule-based",
        llm_model="none",
        llm_temperature=0.0,
        input_data_summary={
            "regime": input_data.regime_label,
            "narratives_count": len(input_data.competing_narratives),
            "beliefs_count": len(input_data.core_beliefs),
            "indicators_count": len(input_data.market_indicators),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# Main Agent
# ═══════════════════════════════════════════════════════════════════════════


class ResearchReasoningAgent:
    """V3.4 Research Reasoning Agent — the "brain" of the macro research system.

    Takes all structured outputs from V3.2 pipeline (regime, narratives, beliefs,
    data) and produces deep ResearchMemos — either via LLM or rule-based fallback.

    Usage:
        agent = ResearchReasoningAgent(model="gpt-4o")
        memo = agent.reason(input_data)

    The agent supports three modes:
        1. llm-only: Pure LLM reasoning (requires API key)
        2. rule-based: Pure rule engine (always available, lower quality)
        3. hybrid: Rule-based structural + LLM overlay (experimental)
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        provider: str = "",
        api_key: str = "",
        base_url: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        reasoning_mode: str = "llm",  # "llm" / "rule" / "hybrid"
        prompt_architecture: PromptArchitecture | None = None,
    ):
        """Initialize the research reasoning agent.

        Args:
            model: LLM model name (e.g. "gpt-4o", "claude-3-opus", "deepseek-v3")
            provider: LLM provider. Auto-detected if empty.
            api_key: API key. Reads from env if empty.
            base_url: Custom API base URL.
            temperature: LLM temperature (0.0–1.0). Lower = more consistent.
            max_tokens: Max output tokens for LLM response.
            reasoning_mode: "llm" (deep reasoning), "rule" (fallback), "hybrid" (both)
            prompt_architecture: Custom prompt configuration.
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reasoning_mode = reasoning_mode

        self.prompts = prompt_architecture or PromptArchitecture()

        # Initialize LLM client
        if reasoning_mode in ("llm", "hybrid"):
            try:
                self.llm = LLMClient(
                    model=model,
                    provider=provider,
                    api_key=api_key,
                    base_url=base_url,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                health = self.llm.health_check()
                self.llm_available = health["status"] == "ok"
                if not self.llm_available:
                    logger.warning(
                        "LLM not available (status: %s). Will fallback to rule-based reasoning.",
                        health["status"],
                    )
            except Exception as e:
                logger.warning("LLM init failed: %s. Using rule-based reasoning.", e)
                self.llm = None
                self.llm_available = False
        else:
            self.llm = None
            self.llm_available = False
            logger.info("Reasoning mode set to '%s'. Rule-based only.", reasoning_mode)

    # ── Public API ────────────────────────────────────────────────────

    def reason(self, input_data: ReasoningInput) -> ResearchMemo:
        """Main entry point: reason about the macro environment.

        Args:
            input_data: All structured data from the V3.2 pipeline.

        Returns:
            ResearchMemo with deep analysis, judgment, and calibration.
        """
        t0 = time.time()

        if self.reasoning_mode == "rule":
            memo = _rule_based_memo(input_data)
            memo.reasoning_mode = "rule-based"
            logger.info(
                "Rule-based memo generated for %s in %.0fms",
                input_data.case_id,
                (time.time() - t0) * 1000,
            )
            return memo

        if not self.llm_available:
            logger.warning("LLM unavailable, falling back to rule-based reasoning.")
            memo = _rule_based_memo(input_data)
            memo.reasoning_mode = "rule-based (LLM fallback)"
            return memo

        # ── LLM path ──
        memo = self._reason_with_llm(input_data)
        elapsed = (time.time() - t0) * 1000
        logger.info(
            "LLM memo generated for %s in %.0fms (model: %s, confidence: %.2f)",
            input_data.case_id,
            elapsed,
            self.model,
            memo.confidence.overall_confidence,
        )
        return memo

    def reason_batch(
        self,
        inputs: list[ReasoningInput],
        concurrency: int = 1,
    ) -> list[ResearchMemo]:
        """Reason about multiple scenarios.

        Args:
            inputs: List of reasoning inputs.
            concurrency: Number of concurrent LLM calls (1 = sequential).

        Returns:
            List of ResearchMemos in the same order as inputs.
        """
        memos = []
        for inp in inputs:
            memos.append(self.reason(inp))
        return memos

    # ── Internal: LLM Reasoning ───────────────────────────────────────

    def _reason_with_llm(self, input_data: ReasoningInput) -> ResearchMemo:
        """Use LLM for deep reasoning."""

        # Build prompt
        prompt_args = input_data.to_prompt_args()
        user_prompt = self.prompts.build_reasoning_prompt(
            **prompt_args,
            include_fewshot=True,
        )

        # Call LLM
        response = self.llm.research_chat(
            system_prompt=self.prompts.system_prompt,
            user_prompt=user_prompt,
            temperature=self.temperature,
        )

        if response.success and response.parsed_json:
            memo = self._parse_llm_response(response, input_data)
            memo.reasoning_mode = "llm"
            memo.llm_model = self.model
            memo.llm_temperature = self.temperature
            memo.input_data_summary = {
                "regime": input_data.regime_label,
                "narratives_count": len(input_data.competing_narratives),
                "beliefs_count": len(input_data.core_beliefs),
                "indicators_count": len(input_data.market_indicators),
            }
            return memo

        # If JSON parsing fails but we have content, try to salvage
        if response.success and response.content:
            logger.warning(
                "LLM response couldn't be parsed as JSON. Falling back to rule-based with LLM text."
            )
            memo = _rule_based_memo(input_data)
            memo.executive_summary = (
                response.content[:500]
                + "\n\n(以上为LLM原始输出，系统无法解析为结构化JSON，已使用规则引擎补充)"
            )
            memo.reasoning_mode = "hybrid (LLM text + rule-based structure)"
            return memo

        # Total failure
        logger.error("LLM call failed: %s", response.error)
        memo = _rule_based_memo(input_data)
        memo.reasoning_mode = "rule-based (LLM error)"
        return memo

    # ── Internal: Parse LLM Response ──────────────────────────────────

    def _parse_llm_response(
        self, response: LLMResponse, input_data: ReasoningInput
    ) -> ResearchMemo:
        """Parse structured LLM JSON output into ResearchMemo."""

        data = response.parsed_json or {}

        # Basic fields
        memo = ResearchMemo(
            memo_id=input_data.case_id or f"memo-{int(time.time())}",
            title=data.get("title", f"宏观研究: {input_data.regime_label}"),
            executive_summary=data.get("executive_summary", ""),
            one_sentence_view=data.get("one_sentence_view", ""),
            conviction_level=data.get("conviction_level", "medium"),
        )

        # ── Regime ──
        r = data.get("regime", {})
        memo.regime = RegimeAnalysis(
            regime_label=r.get("label", input_data.regime_label),
            regime_confidence=r.get("confidence", input_data.regime_confidence),
            regime_transition_risk=r.get("transition_risk", 0.3),
            next_regime_candidates=r.get("next_candidates", []),
            regime_duration_estimate=r.get("duration_estimate", ""),
            defining_characteristics=r.get("characteristics", []),
            historical_analogs=r.get("analogs", []),
            **{
                f"{k}_assessment": r.get("dimensions", {}).get(k, "")
                for k in ["growth", "inflation", "monetary", "risk", "credit"]
            },
        )

        # ── Narrative ──
        n = data.get("narrative", {})
        memo.narrative = NarrativeAnalysis(
            dominant_narrative=n.get("dominant", input_data.dominant_narrative),
            narrative_confidence=n.get("confidence", input_data.narrative_confidence),
            narrative_stage=n.get("stage", input_data.narrative_stage),
            competing_narratives=n.get("competing", input_data.competing_narratives),
            narrative_catalyst=n.get("catalyst", ""),
            narrative_durability=n.get("durability", ""),
            narrative_risks=n.get("risks", []),
            consensus_positioning=n.get("consensus_positioning", ""),
            narrative_gap=n.get("gap", ""),
        )

        # ── Causal ──
        c = data.get("causal", {})
        memo.causal = CausalAnalysis(
            primary_causal_chain=c.get("primary_chain", []),
            counterfactual_scenarios=c.get("counterfactuals", []),
            key_causal_assumptions=c.get("assumptions", []),
            structural_vs_cyclical=c.get("structural_vs_cyclical", ""),
            feedback_loops_identified=c.get("feedback_loops", []),
        )

        # ── Evidence ──
        e = data.get("evidence", {})
        memo.evidence = EvidenceAssessment(
            supporting_evidence=e.get("supporting", []),
            contradicting_evidence=e.get("contradicting", []),
            evidence_score=e.get("score", 0.0),
            evidence_quality=e.get("quality", ""),
            missing_evidence=e.get("missing", []),
            data_surprises_to_watch=e.get("surprises_to_watch", []),
        )

        # ── Belief ──
        b = data.get("belief", {})
        memo.belief = BeliefSynthesis(
            core_belief=b.get("core", ""),
            belief_confidence=b.get("confidence", input_data.belief_confidence),
            belief_models_used=b.get("models_used", input_data.active_mental_models),
            model_consensus=b.get("consensus", ""),
            model_divergence=b.get("divergence", ""),
            highest_conviction_view=b.get("highest_conviction", ""),
            lowest_conviction_view=b.get("lowest_conviction", ""),
            belief_update_triggers=b.get("update_triggers", input_data.falsification_conditions),
        )

        # ── Falsification ──
        f = data.get("falsification", {})
        memo.falsification = FalsificationCheck(
            falsification_conditions=f.get("conditions", []),
            current_falsification_status=f.get("status", ""),
            falsification_timeline=f.get("timeline", ""),
            base_case_if_wrong=f.get("base_case_if_wrong", ""),
        )

        # ── Assets ──
        a = data.get("assets", {})
        memo.assets = AssetImplication(
            asset_views=a.get("views", []),
            highest_conviction_trades=a.get("highest_conviction", []),
            regime_favored_assets=a.get("favored", []),
            regime_unfavored_assets=a.get("unfavored", []),
            portfolio_positioning=a.get("positioning", ""),
            cross_asset_signals=a.get("cross_asset_signals", []),
        )

        # ── Tail Risk ──
        t = data.get("tail_risk", {})
        memo.tail_risk = TailRisk(
            tail_risks=t.get("risks", []),
            black_swan_candidates=t.get("black_swans", []),
            fat_tail_assessment=t.get("fat_tail", ""),
            correlation_regime=t.get("correlation_regime", ""),
            stress_scenarios=t.get("stress_scenarios", []),
        )

        # ── Confidence ──
        cc = data.get("confidence_calibration", {})
        memo.confidence = ConfidenceCalibration(
            overall_confidence=cc.get("overall", 0.5),
            confidence_breakdown=cc.get("breakdown", {}),
            calibration_note=cc.get("note", ""),
            key_uncertainties=cc.get("key_uncertainties", []),
            known_unknowns=cc.get("known_unknowns", []),
            unknown_unknowns_awareness=cc.get("unknown_unknowns", ""),
        )

        return memo
