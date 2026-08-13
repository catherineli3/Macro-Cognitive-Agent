"""LLM Narrative Engine — LLM-powered report generation with degradation fallback.

Design contract:
  1. Schema First: all inputs are typed Pydantic, never dict/Any.
  2. LLM only expresses, never computes — prompt forbids fabricating data/opinions.
  3. Every call path ends with a valid LLMNarrativeResult; failure -> degraded=True.

Input:  MacroNarrative (from template engine) — the structured engine output.
Output: LLMNarrativeResult — validated JSON report + degraded flag.

Integration:
  - Called from MacroResearchPipeline.run() when use_llm=True.
  - API endpoint GET /v2/narrative/llm returns the result directly.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError

from src.llm.client import LLMClient, LLMError
from src.llm.retriever import HistoryRetriever, assemble_history_prompt
from src.schemas.narrative import MacroNarrative
from src.shared.config import load_yaml
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pydantic output schema — strict contract for LLM response
# ---------------------------------------------------------------------------


class LLMNarrativeData(BaseModel):
    """LLM-generated narrative fields, validated before returning."""

    executive_summary: str = Field(
        default="",
        description="Executive summary synthesizing macro assessment",
    )
    scenario_analysis: str = Field(
        default="",
        description="Scenario probability analysis with supporting/contradicting signals",
    )
    action_recommendations: list[str] = Field(
        default_factory=list,
        description="Investment action items derived from analysis",
    )
    belief_revision: str = Field(
        default="",
        description="Comparison with past beliefs: reinforced vs overturned",
    )


class LLMNarrativeResult(BaseModel):
    """Wrapper returned to caller; degraded=True when LLM failed."""

    degraded: bool = Field(
        default=False,
        description="True if LLM failed and template output was used",
    )
    data: LLMNarrativeData = Field(
        default_factory=LLMNarrativeData,
        description="Validated narrative data (LLM or fallback)",
    )
    error: str | None = Field(
        default=None,
        description="Error message if degraded",
    )
    raw_llm_response: str | None = Field(
        default=None,
        description="Raw LLM response for debugging, None if degraded",
    )


# ---------------------------------------------------------------------------
# LLM Narrative Engine
# ---------------------------------------------------------------------------


class LLMNarrativeEngine:
    """Generate narrative report via Kimi LLM; degrade to template on failure.

    Usage:
        engine = LLMNarrativeEngine()
        result = engine.generate(narrative=macro_narrative)
        if result.degraded:
            logger.warning("LLM unavailable, using template output")
    """

    _SYSTEM_PROMPT = (
        "你是一位宏观研究撰稿人，负责将结构化引擎数据转化为专业的宏观研报。"
        "当提供历史参考时，须标注引用来源、不得将历史数据与当日数据混淆。"
    )

    _USER_TEMPLATE = (
        "根据以下结构化宏观分析数据，生成一份专业研究报告。\n"
        "\n"
        "【严格规则】\n"
        "1. 只可使用输入数据与历史参考中已有的结论与数字，不得新增任何数据、预测或观点。\n"
        "2. 输出严格 JSON，格式示例：\n"
        '  {"executive_summary": "summary here", "scenario_analysis": "analysis here", '
        '"action_recommendations": ["item1", "item2"], "belief_revision": "belief here"}\n'
        "\n"
        "{history_context}"
        "【输入数据】\n"
        "{input_json}\n"
    )

    def __init__(
        self,
        client: LLMClient | None = None,
        retriever: HistoryRetriever | None = None,
    ) -> None:
        self._client = client or LLMClient()
        self._retriever = retriever  # lazy-init on first generate() if None
        self._prompts = self._load_prompts()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, narrative: MacroNarrative) -> LLMNarrativeResult:
        """Generate LLM-powered narrative; never raises, always returns result.

        Args:
            narrative: Structured engine output from template pipeline.

        Returns:
            LLMNarrativeResult with degraded=False on success, degraded=True on failure.
        """
        structured_input = self._build_input(narrative)

        # --- RAG: retrieve historical context (silent degradation) ---
        if self._retriever is None:
            self._retriever = HistoryRetriever()

        history_records: list = []
        try:
            history_records = self._retriever.retrieve(structured_input)
        except Exception:
            logger.warning("history_retrieval_failed_degrading_silently")
            history_records = []

        history_context, _token_count = assemble_history_prompt(history_records)

        try:
            raw = self._call_llm(structured_input, history_context)
            data = self._validate(raw)
            return LLMNarrativeResult(
                degraded=False,
                data=data,
                raw_llm_response=raw,
            )
        except (LLMError, ValidationError, json.JSONDecodeError, Exception) as exc:
            return LLMNarrativeResult(
                degraded=True,
                data=self._fallback_data(narrative),
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Internal — prompt construction
    # ------------------------------------------------------------------

    def _load_prompts(self) -> dict:
        """Load prompt templates from configs/prompts.yaml with fallback."""
        try:
            prompts = load_yaml("prompts.yaml")
            report_prompts = prompts.get("report", {}) if isinstance(prompts, dict) else {}
            return {
                "system": report_prompts.get("system", "") or self._SYSTEM_PROMPT,
                "user": report_prompts.get("user", "") or self._USER_TEMPLATE,
            }
        except Exception:
            return {"system": self._SYSTEM_PROMPT, "user": self._USER_TEMPLATE}

    def _build_input(self, narrative: MacroNarrative) -> dict[str, object]:
        """Serialize typed MacroNarrative into dict for prompt injection."""
        return {
            "summary": narrative.summary,
            "macro_story": narrative.macro_story,
            "today_key_changes": narrative.today_key_changes,
            "liquidity": {
                "summary": narrative.liquidity.summary,
                "analysis": narrative.liquidity.analysis,
                "confidence": narrative.liquidity.confidence,
            },
            "credit": {
                "summary": narrative.credit.summary,
                "analysis": narrative.credit.analysis,
                "confidence": narrative.credit.confidence,
            },
            "growth": {
                "summary": narrative.growth.summary,
                "analysis": narrative.growth.analysis,
                "confidence": narrative.growth.confidence,
            },
            "inflation": {
                "summary": narrative.inflation.summary,
                "analysis": narrative.inflation.analysis,
                "confidence": narrative.inflation.confidence,
            },
            "risk_appetite_analysis": narrative.risk_appetite_analysis,
            "scenarios": [
                {"name": s.name, "probability": s.probability, "rationale": s.rationale}
                for s in narrative.scenario_analysis
            ],
            "belief_changes": [
                {
                    "hypothesis": b.hypothesis_statement,
                    "previous": b.previous_confidence,
                    "current": b.current_confidence,
                    "direction": b.direction,
                }
                for b in narrative.belief_changes
            ],
            "risks": narrative.key_risks,
            "action_items": narrative.action_items,
            "confidence_level": (
                narrative.confidence_level.value
                if hasattr(narrative.confidence_level, "value")
                else narrative.confidence_level
            ),
            "confidence_score": narrative.confidence_score,
        }

    # ------------------------------------------------------------------
    # Internal — LLM call + validation
    # ------------------------------------------------------------------

    def _call_llm(self, structured_input: dict[str, object], history_context: str = "") -> str:
        """Send structured input to LLM, return raw response text.

        When history_context is non-empty, it is injected before the input
        data block as 【历史参考】.  The template uses {input_json} and
        {history_context} placeholders; .replace() is used to avoid JSON
        brace collision with str.format().
        """
        system_prompt = self._prompts["system"]
        user_template = self._prompts["user"]
        input_str = json.dumps(structured_input, ensure_ascii=False, indent=2)
        # Use .replace() instead of .format() because the template contains
        # JSON example braces {} that conflict with str.format placeholders.
        user_prompt = user_template.replace("{input_json}", input_str)
        user_prompt = user_prompt.replace("{history_context}", history_context)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._client.chat(messages, temperature=0.3)

    @staticmethod
    def _validate(raw: str) -> LLMNarrativeData:
        """Parse + validate LLM output against Pydantic schema.

        Handles markdown code fences (```json ... ```) that some models emit.
        """
        obj = LLMNarrativeEngine._parse_json(raw)
        return LLMNarrativeData(**obj)

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Extract and parse JSON from LLM output, stripping markdown fences."""
        # Strip markdown code fences: ```json ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if fence_match:
            raw = fence_match.group(1).strip()
        return json.loads(raw)

    # ------------------------------------------------------------------
    # Internal — fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_data(narrative: MacroNarrative) -> LLMNarrativeData:
        """Build narrative data from template engine output when LLM unavailable."""
        scenarios_text = (
            "; ".join(
                f"{s.name}({s.probability:.0%}): {s.rationale}"
                for s in narrative.scenario_analysis[:3]
            )
            or "暂无场景分析"
        )

        belief_text = (
            "; ".join(
                f"{b.direction}: {b.hypothesis_statement}" for b in narrative.belief_changes[:3]
            )
            or "暂无信念变化"
        )

        actions = narrative.action_items[:5] if narrative.action_items else []

        return LLMNarrativeData(
            executive_summary=narrative.summary,
            scenario_analysis=scenarios_text,
            action_recommendations=actions,
            belief_revision=belief_text,
        )
