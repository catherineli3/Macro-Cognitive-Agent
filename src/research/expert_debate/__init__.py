"""Expert Debate — Multi-persona internal debate engine (V3.4).

Implements a 4-persona internal debate:
    - Paul Tudor Jones (PTJ): Momentum, asymmetry, trading-focused
    - Ray Dalio: Systems, cycles, historical analog
    - George Soros: Reflexivity, fallibility, boom-bust
    - Bridgewater (All-Weather): Regime-based, environment-first

Each persona analyzes the same data through their distinct lens. The debate
produces:
    1. Individual analyses from each expert persona
    2. Points of agreement (consensus) and disagreement (divergence)
    3. A "synthesis" that integrates all perspectives
    4. Weighted confidence based on persona alignment

The power of this approach: Different mental models applied to the same data
reveal blind spots that a single-model approach would miss. When all four
personas agree, conviction is high. When they diverge, that's a warning signal.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Optional

from src.research.llm_brain.llm_client import LLMClient, LLMResponse, extract_json_from_text
from src.research.llm_brain.prompts import EXPERT_PERSONAS, PromptArchitecture
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ExpertView:
    """A single expert's analysis."""

    persona: str = ""  # "ptj" / "dalio" / "soros" / "bridgewater"
    persona_name: str = ""  # "Paul Tudor Jones" etc.

    # Core analysis
    regime_view: str = ""
    highest_conviction: str = ""
    key_risk: str = ""
    trade_idea: str = ""
    disagreement_with_consensus: str = ""
    reflexivity_observation: str = ""

    # Metadata
    confidence: float = 0.0
    reasoning_time_ms: float = 0.0
    raw_response: str = ""
    parsed_json: dict = field(default_factory=dict)


@dataclass
class DebateSynthesis:
    """Synthesis of the four-persona debate."""

    # Consensus
    consensus_views: list[str] = field(default_factory=list)
    consensus_score: float = 0.0  # 0-1 how much agreement

    # Divergence
    divergence_views: list[dict] = field(default_factory=list)
    # e.g., [{"topic": ..., "ptj": ..., "dalio": ..., "resolution": ...}]

    # Integrated view
    integrated_regime: str = ""
    integrated_narrative: str = ""
    integrated_trade: str = ""
    integrated_risk: str = ""

    # Persona weights
    persona_weights: dict = field(default_factory=dict)
    # Who to listen to more in current market

    # Meta
    synthesis_confidence: float = 0.0
    synthesis_timestamp: str = ""


@dataclass
class DebateResult:
    """Complete debate output."""

    debate_id: str = ""
    timestamp: str = ""

    # Individual views
    expert_views: dict[str, ExpertView] = field(default_factory=dict)  # persona → view

    # Synthesis
    synthesis: DebateSynthesis = field(default_factory=DebateSynthesis)

    # Meta
    debate_duration_ms: float = 0.0
    model_used: str = ""
    debate_mode: str = ""  # "llm" / "rule-based"


# ═══════════════════════════════════════════════════════════════════════════
# Rule-based fallback debate (no LLM required)
# ═══════════════════════════════════════════════════════════════════════════


def _rule_based_persona_analysis(
    persona: str, market_data: dict, regime: str, dominant_narrative: str
) -> ExpertView:
    """Generate an expert view using rule-based logic (LLM fallback).

    Uses persona-specific rules to analyze market data without LLM calls.
    """
    cpi = float(market_data.get("cpi_yoy", 3))
    vix = float(market_data.get("vix", 18))
    spx_ytd = float(market_data.get("spx_ytd", 0) or market_data.get("nasdaq_ytd", 0))
    _dxy = float(market_data.get("dxy", 100))
    us10y = float(market_data.get("us10y", 4))
    hyg = float(market_data.get("hyg_spread", 400))

    if persona == "ptj":
        # PTJ: Focus on momentum, positioning, asymmetry
        momentum_signal = "bullish" if spx_ytd > 10 else ("bearish" if spx_ytd < -10 else "neutral")
        crowded = "overcrowded" if vix < 13 else ("capitulated" if vix > 30 else "balanced")

        return ExpertView(
            persona="ptj",
            persona_name="Paul Tudor Jones",
            regime_view=f"当前趋势: {momentum_signal}, 波动率: {vix:.0f}, 市场定位: {crowded}",
            highest_conviction=f"VIX在{vix:.0f}——历史表明这是一个{'好的买入机会' if vix > 25 else '需要谨慎的高位'}",
            key_risk=f"'{dominant_narrative[:40]}'叙事{'过于拥挤' if vix < 15 else '仍有空间'}",
            trade_idea=f"SPX趋势{momentum_signal}，{'顺势做多但设止损' if momentum_signal == 'bullish' else '等待动量反转'}",
            disagreement_with_consensus=f"市场共识: {dominant_narrative[:50]}——{'我在找反转信号' if vix < 15 else '仍在趋势中'}",
            reflexivity_observation=f"VIX在{vix:.0f}：{'低波正在自我强化——'if vix < 15 else ''}资金持续流入，推高价格，降低波动，吸引更多资金",
            confidence=0.65 if vix < 15 else 0.55,
        )

    elif persona == "dalio":
        # Dalio: Focus on long/short debt cycles, productivity, transmission
        cpi_assess = (
            "above equilibrium"
            if cpi > 4
            else ("near equilibrium" if 2 < cpi <= 3.5 else "below target")
        )
        debt_cycle = "late long-term debt cycle" if cpi > 4 or us10y > 4.5 else "mid-cycle"

        return ExpertView(
            persona="dalio",
            persona_name="Ray Dalio",
            regime_view=f"长期债务周期: {debt_cycle}. 通胀: {cpi_assess} (CPI={cpi:.1f}%). 生产率判断: 中性.",
            highest_conviction=f"我们处于{debt_cycle}。历史表明，{('利率上升 + 高债务 → 央行面临两难' if cpi > 4 else '当前环境类似1990年代中期')}",
            key_risk="最大的风险是央行在控制通胀和维持债务可持续性之间无法平衡",
            trade_idea=f"持有{'通胀保护资产' if cpi > 3.5 else '多元化组合'}，{'做空长期债券' if us10y > 4 else '保持中性久期'}",
            disagreement_with_consensus=f"市场聚焦短期，但真正重要的是债务结构——{'当前总债务/GDP远超历史正常水平' if True else ''}",
            reflexivity_observation=f"央行政策在改变市场行为：{'紧缩' if cpi > 3.5 else '宽松'} → 资产价格 → 财富效应 → 经济 → 央行政策",
            confidence=0.70,
        )

    elif persona == "soros":
        # Soros: Focus on reflexivity, fallibility, boom-bust
        boom_signals = []
        if vix < 13:
            boom_signals.append("低波动率(自满)")
        if spx_ytd > 20:
            boom_signals.append("强劲动量(自我强化)")
        if hyg < 350:
            boom_signals.append("信用极度宽松")

        return ExpertView(
            persona="soros",
            persona_name="George Soros",
            regime_view=(
                "市场状态: "
                + (
                    "繁荣期(boom)——市场信念正在改变基本面"
                    if boom_signals
                    else "正常/均衡——但任何均衡都是暂时的"
                )
            ),
            highest_conviction=(
                "当前"
                + ("存在" if boom_signals else "可能存在未发现的")
                + "反身性过程: 叙事→资本→价格→叙事强化"
            ),
            key_risk=(
                '主导叙事"'
                + dominant_narrative[:40]
                + '"的可错性: '
                + ("共识叙事总是包含系统性错误——问题是：错误在哪里？" if vix < 15 else "正受到检验")
            ),
            trade_idea=(
                ("做多" if spx_ytd > 0 else "做空")
                + "趋势但"
                + ("准备反转仓位" if vix < 15 else "继续持有")
                + "——我知道我的判断可能是错的"
            ),
            disagreement_with_consensus=(
                '市场共识"' + dominant_narrative[:40] + '"是一个便利的简化——但现实远比这复杂'
            ),
            reflexivity_observation=(
                "当前核心反身性: "
                + dominant_narrative[:50]
                + " → 市场行为 → 经济结果 → "
                + dominant_narrative[:30]
                + "被证实 → 更多相同行为"
            ),
            confidence=0.50,  # Soros is always uncertain
        )

    else:  # bridgewater
        # Bridgewater: Focus on four regimes, environment → assets
        growth_signal = (
            "above trend" if spx_ytd > 10 else ("below trend" if spx_ytd < -5 else "trend")
        )
        infl_signal = "rising" if cpi > 4 else ("falling" if cpi < 2.5 else "stable")
        quadrant = f"Growth {growth_signal} × Inflation {infl_signal}"

        return ExpertView(
            persona="bridgewater",
            persona_name="Bridgewater All-Weather",
            regime_view=f"环境象限: {quadrant}. 当前环境{'有利于风险资产' if growth_signal == 'above trend' else '偏防御'}",
            highest_conviction=f"在{quadrant}环境中，历史表现最好的资产类别是{'权益+商品' if growth_signal == 'above trend' else '通胀保护债券+黄金'}",
            key_risk=f"环境转换风险: 如果{'增长放缓 + 通胀加速' if infl_signal == 'stable' else '通胀突然回落'}→ 资产相关性结构完全改变",
            trade_idea=f"建议{'风险平价配置' if vix < 25 else '降低风险权重'}——{'超配' if growth_signal == 'above trend' else '标配'}权益",
            disagreement_with_consensus=f"市场在以单一叙事定价，但环境可能在改变——{'分散化仍然有效' if vix > 20 else '相关性可能突然改变'}",
            reflexivity_observation=f"环境不会静止——当前通胀{infl_signal} + 增长{growth_signal}的组合不可持续，转换概率在累积",
            confidence=0.60,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Expert Debate Engine
# ═══════════════════════════════════════════════════════════════════════════


class ExpertDebate:
    """Four-persona macro debate engine.

    Usage:
        debate = ExpertDebate(model="gpt-4o")
        result = debate.debate(market_data, regime, narrative)

        # Access individual views
        ptj_view = result.expert_views["ptj"]

        # Access synthesis
        consensus = result.synthesis.consensus_views
        divergence = result.synthesis.divergence_views
    """

    PERSONAS = ["ptj", "dalio", "soros", "bridgewater"]
    PERSONA_NAMES = {
        "ptj": "Paul Tudor Jones",
        "dalio": "Ray Dalio",
        "soros": "George Soros",
        "bridgewater": "Bridgewater All-Weather",
    }

    def __init__(
        self,
        model: str = "gpt-4o",
        provider: str = "",
        api_key: str = "",
        base_url: str = "",
        temperature: float = 0.5,
        debate_mode: str = "llm",  # "llm" or "rule"
    ):
        """Initialize the debate engine.

        Args:
            model: LLM model for persona reasoning.
            provider: LLM provider (auto-detect if empty).
            api_key: API key.
            base_url: Custom API base URL.
            temperature: LLM temperature (higher = more varied persona voices).
            debate_mode: "llm" (deep persona reasoning) or "rule" (rule-based fallback).
        """
        self.model = model
        self.temperature = temperature
        self.debate_mode = debate_mode
        self.prompts = PromptArchitecture()

        if debate_mode == "llm":
            try:
                self.llm = LLMClient(
                    model=model,
                    provider=provider,
                    api_key=api_key,
                    base_url=base_url,
                    temperature=temperature,
                    max_tokens=2048,
                )
                health = self.llm.health_check()
                self.llm_available = health["status"] == "ok"
                if not self.llm_available:
                    logger.warning("LLM unavailable for debate. Using rule-based.")
            except Exception as e:
                logger.warning("LLM init failed: %s. Using rule-based debate.", e)
                self.llm = None
                self.llm_available = False
        else:
            self.llm = None
            self.llm_available = False

    # ── Public API ────────────────────────────────────────────────────

    def debate(
        self,
        market_data: dict,
        regime_label: str = "",
        dominant_narrative: str = "",
        competing_narratives: list[dict] = None,
        key_events: list[str] = None,
    ) -> DebateResult:
        """Run the four-persona debate.

        Args:
            market_data: Market indicators dict.
            regime_label: Current regime.
            dominant_narrative: Current dominant narrative.
            competing_narratives: Other narratives.
            key_events: Recent key events.

        Returns:
            DebateResult with all four expert views + synthesis.
        """
        t0 = time.time()
        now = datetime.now(UTC)
        debate_id = f"debate-{now.strftime('%Y%m%d-%H%M')}"

        # Build market context
        market_context = self._build_context(market_data, regime_label, dominant_narrative)

        # Get each persona's view
        expert_views: dict[str, ExpertView] = {}
        for persona in self.PERSONAS:
            if self.llm_available:
                view = self._get_llm_view(
                    persona, market_context, market_data, regime_label, dominant_narrative
                )
            else:
                view = _rule_based_persona_analysis(
                    persona, market_data, regime_label, dominant_narrative
                )
            expert_views[persona] = view

        # Synthesize
        synthesis = self._synthesize(expert_views, market_data)

        duration = (time.time() - t0) * 1000

        return DebateResult(
            debate_id=debate_id,
            timestamp=now.isoformat(),
            expert_views=expert_views,
            synthesis=synthesis,
            debate_duration_ms=duration,
            model_used=self.model if self.llm_available else "rule-based",
            debate_mode="llm" if self.llm_available else "rule-based",
        )

    # ── Individual views ──────────────────────────────────────────────

    def _get_llm_view(
        self,
        persona: str,
        market_context: str,
        market_data: dict,
        regime: str,
        narrative: str,
    ) -> ExpertView:
        """Get one expert's view via LLM."""
        t0 = time.time()
        prompt = self.prompts.build_expert_debate_prompt(persona, market_context)
        response = self.llm.research_chat(
            system_prompt="你是一位世界级宏观投资专家。用你的专业风格进行分析。",
            user_prompt=prompt,
            temperature=self.temperature,
        )

        elapsed = (time.time() - t0) * 1000

        if response.success and response.parsed_json:
            data = response.parsed_json
            return ExpertView(
                persona=persona,
                persona_name=self.PERSONA_NAMES[persona],
                regime_view=data.get("regime_view", ""),
                highest_conviction=data.get("highest_conviction", ""),
                key_risk=data.get("key_risk", ""),
                trade_idea=data.get("trade_idea", ""),
                disagreement_with_consensus=data.get("disagreement_with_consensus", ""),
                reflexivity_observation=data.get("reflexivity_observation", ""),
                confidence=data.get("confidence", 0.5),
                reasoning_time_ms=elapsed,
                raw_response=response.content,
                parsed_json=data,
            )

        # Fallback
        return _rule_based_persona_analysis(persona, market_data, regime, narrative)

    # ── Synthesis ─────────────────────────────────────────────────────

    def _synthesize(self, views: dict[str, ExpertView], market_data: dict) -> DebateSynthesis:
        """Synthesize the four-persona debate into consensus + divergence."""
        synthesis = DebateSynthesis(
            synthesis_timestamp=datetime.now(UTC).isoformat(),
        )

        # ── Find consensus ──
        consensus_items = self._find_consensus(views, market_data)
        synthesis.consensus_views = consensus_items
        synthesis.consensus_score = min(
            len(consensus_items) / 4.0, 1.0
        )  # Max 1.0 at 4+ agreement items

        # ── Find divergence ──
        synthesis.divergence_views = self._find_divergence(views)

        # ── Integrated view ──
        synthesis.integrated_regime = self._integrate_regime(views)
        synthesis.integrated_narrative = self._integrate_narrative(views)
        synthesis.integrated_trade = self._integrate_trade(views)
        synthesis.integrated_risk = self._integrate_risk(views)

        # ── Persona weights (who to listen to more) ──
        synthesis.persona_weights = self._compute_persona_weights(views, market_data)

        # ── Synthesis confidence ──
        avg_persona_conf = sum(v.confidence for v in views.values()) / max(len(views), 1)
        synthesis.synthesis_confidence = round(
            avg_persona_conf * 0.5 + synthesis.consensus_score * 0.5, 2
        )

        return synthesis

    def _find_consensus(self, views: dict[str, ExpertView], market_data: dict) -> list[str]:
        """Identify points of agreement across personas."""
        consensus = []

        # Check regime agreement
        _regimes = {p: v.regime_view[:50] for p, v in views.items()}
        cpi = float(market_data.get("cpi_yoy", 3))
        vix = float(market_data.get("vix", 18))

        # Simple heuristic: check for shared keywords
        if cpi > 4 and all(
            "通胀" in v.regime_view or "inflation" in v.regime_view.lower() for v in views.values()
        ):
            consensus.append("所有专家一致认为通胀是当前核心关注")
        if vix > 25 and all(
            "风险" in v.regime_view or "risk" in v.regime_view.lower() for v in views.values()
        ):
            consensus.append("所有专家一致认为市场处于避险模式")
        if vix < 13:
            consensus.append("所有专家均识别到低波动率环境")

        # Check risk agreement
        if len(set(v.key_risk[:30] for v in views.values())) <= 2:
            consensus.append("风险认知高度一致")

        # Check reflexivity agreement
        reflex_views = [
            v.reflexivity_observation for v in views.values() if v.reflexivity_observation
        ]
        if len(reflex_views) >= 3:
            consensus.append("多数专家识别到反身性过程")

        return consensus

    def _find_divergence(self, views: dict[str, ExpertView]) -> list[dict]:
        """Identify key disagreements."""
        divergence = []

        # PTJ vs Dalio: momentum vs structural
        if views.get("ptj") and views.get("dalio"):
            ptj_trade = views["ptj"].trade_idea[:60]
            dalio_trade = views["dalio"].trade_idea[:60]
            if ptj_trade != dalio_trade:
                divergence.append(
                    {
                        "topic": "交易/配置视角",
                        "ptj": ptj_trade,
                        "dalio": dalio_trade,
                        "comment": "PTJ关注短期动量，Dalio关注长期结构——时间框架分歧",
                    }
                )

        # Soros vs Bridgewater: reflexivity vs environment
        if views.get("soros") and views.get("bridgewater"):
            divergence.append(
                {
                    "topic": "反身性 vs 均衡",
                    "soros": views["soros"].reflexivity_observation[:80],
                    "bridgewater": views["bridgewater"].regime_view[:80],
                    "comment": "Soros相信反身性主导，Bridgewater相信环境回归均值",
                }
            )

        return divergence

    def _integrate_regime(self, views: dict[str, ExpertView]) -> str:
        """Integrate regime views."""
        return "综合判断: " + " | ".join(
            f"{self.PERSONA_NAMES[p]}: {v.regime_view[:40]}"
            for p, v in views.items()
            if v.regime_view
        )

    def _integrate_narrative(self, views: dict[str, ExpertView]) -> str:
        """Integrate narrative views."""
        convictions = [v.highest_conviction for v in views.values() if v.highest_conviction]
        if not convictions:
            return "无一致判断"
        return f"最强共识 ({len(convictions)}位专家): {convictions[0][:100]}"

    def _integrate_trade(self, views: dict[str, ExpertView]) -> str:
        """Integrate trade ideas."""
        trades = [v.trade_idea for v in views.values() if v.trade_idea]
        if not trades:
            return "无交易建议"
        return " | ".join(trades[:3])

    def _integrate_risk(self, views: dict[str, ExpertView]) -> str:
        """Integrate risk views."""
        risks = [v.key_risk for v in views.values() if v.key_risk]
        if not risks:
            return "未识别共同风险"
        return risks[0][:150]  # Primary risk

    def _compute_persona_weights(self, views: dict[str, ExpertView], market_data: dict) -> dict:
        """Determine which persona's advice is most relevant right now.

        In trending markets → PTJ gets more weight
        In regime transitions → Dalio gets more weight
        In extreme sentiment → Soros gets more weight
        In stable environments → Bridgewater gets more weight
        """
        vix = float(market_data.get("vix", 18))
        spx_ytd = float(market_data.get("spx_ytd", 0) or market_data.get("nasdaq_ytd", 0))
        cpi = float(market_data.get("cpi_yoy", 3))

        weights = {"ptj": 0.25, "dalio": 0.25, "soros": 0.25, "bridgewater": 0.25}

        # PTJ: More weight in clear trending markets
        if abs(spx_ytd) > 15:
            weights["ptj"] += 0.1
            weights["dalio"] -= 0.05

        # Dalio: More weight near regime transitions
        if cpi < 2.5 or cpi > 5:
            weights["dalio"] += 0.1
            weights["bridgewater"] -= 0.05

        # Soros: More weight in extreme sentiment
        if vix < 13 or vix > 30:
            weights["soros"] += 0.15
            weights["ptj"] -= 0.05
            weights["bridgewater"] -= 0.05

        # Bridgewater: More weight in stable/balanced environments
        if 15 <= vix <= 22 and abs(spx_ytd) < 10:
            weights["bridgewater"] += 0.1
            weights["soros"] -= 0.05

        # Normalize
        total = sum(weights.values())
        return {k: round(v / total, 2) for k, v in weights.items()}

    # ── Helpers ───────────────────────────────────────────────────────

    def _build_context(
        self,
        market_data: dict,
        regime: str,
        dominant_narrative: str,
    ) -> str:
        """Build market context string for persona prompts."""
        parts = [
            f"当前Regime: {regime or '未明确'}",
            f"主导叙事: {dominant_narrative or '未明确'}",
            "",
            "### 市场数据",
        ]
        for k, v in market_data.items():
            if isinstance(v, float):
                parts.append(f"  {k}: {v:.2f}")
            else:
                parts.append(f"  {k}: {v}")

        return "\n".join(parts)
