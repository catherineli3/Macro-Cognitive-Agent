"""ReflexivityCycleDetector — The core Soros-style reflexivity engine.

Detects self-reinforcing feedback loops in financial markets:
    Narrative forms → Capital flows follow → Price confirms → Narrative strengthens

A reflexivity cycle IS a boom-bust sequence in formation. This detector:
    1. Combines MarketBelief and CapitalFlow data
    2. Detects when Narrative-Capital-Price are mutually reinforcing
    3. Identifies the cycle stage (forming/accelerating/extreme/cracking/reversing)
    4. Generates break trigger candidates
    5. Scores self-reinforcement intensity

Philosophy (Soros):
    "Financial markets are not passive reflectors of reality — they are active
     participants that can change the course of events they purport to reflect."
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.research.reflexivity.capital_flow_tracker import CapitalFlowTracker
from src.research.reflexivity.market_belief_model import MarketBeliefModel
from src.research.reflexivity.schemas import (
    CapitalFlowSnapshot,
    MarketBelief,
    ReflexivityCycle,
    ReflexivityReport,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Pre-defined cycle patterns ────────────────────────────────────────────

CYCLE_PATTERNS: dict[str, dict] = {
    "inflation_cycle": {
        "title": "通胀-加息-衰退循环",
        "narrative_driver": "Persistent inflation → Fed must hike",
        "stages": {
            "forming": "通胀数据超预期，市场开始怀疑'transitory'叙事",
            "accelerating": "Fed转向鹰派，利率预期急剧上修，债券和权益同时下跌",
            "extreme": "市场悲观嵌入——'Fed will break something'，所有风险资产被抛售",
            "cracking": "劳动力市场出现裂痕，市场开始定价'Fed pivot'",
            "reversing": "Fed转向鸽派，风险资产暴力反弹",
        },
        "historical_analogs": [
            "2022 Fed tightening cycle",
            "2018 Q4 selloff",
            "1994 bond massacre",
        ],
        "break_triggers": [
            {"trigger": "核心CPI连续三个月下降", "impact": "鹰派预期松动"},
            {"trigger": "失业率上升0.5%", "impact": "Fed pivot预期形成"},
            {"trigger": "信用利差>800bp", "impact": "金融稳定风险 → Fed pause"},
        ],
    },
    "dollar_supercycle": {
        "title": "强美元周期",
        "narrative_driver": "US exceptionalism → Strong USD",
        "stages": {
            "forming": "美国增长相对优势显现，利差扩大",
            "accelerating": "DXY突破关键水平，EM资金加速流出",
            "extreme": "DXY极值，EM危机风险上升，'美元荒'叙事主导",
            "cracking": "Fed转向或非美增长改善，DXY见顶信号",
            "reversing": "DXY大跌，EM资产暴力反弹",
        },
        "historical_analogs": ["2014-2015 USD bull run", "DXY 2001 peak", "Plaza Accord 1985"],
        "break_triggers": [
            {"trigger": "Fed明确转向鸽派", "impact": "利率优势消失"},
            {"trigger": "欧洲/中国增长加速", "impact": "增长差距缩小"},
            {"trigger": "DXY突破114但快速回落", "impact": "技术性顶部的确认信号"},
        ],
    },
    "risk_on_bubble": {
        "title": "风险偏好泡沫",
        "narrative_driver": "TINA / FOMO → Buy everything",
        "stages": {
            "forming": "政策宽松 + 低波动 + 增长稳定 → 'Goldilocks'",
            "accelerating": "估值扩张加速，散户/杠杆资金涌入",
            "extreme": "VIX极低，IPO狂热，'这次不一样'叙事",
            "cracking": "某个触发事件（加息意外/信用事件），波动率脉冲",
            "reversing": "波动率爆炸，杠杆强制平仓，相关性→1",
        },
        "historical_analogs": [
            "2020-2021 post-COVID rally",
            "2017 low-vol melt-up",
            "1999-2000 dot-com",
        ],
        "break_triggers": [
            {"trigger": "VIX突破25", "impact": "波动率regime改变"},
            {"trigger": "信用利差骤升100bp+", "impact": "credit作为预警信号"},
            {"trigger": "央行意外收紧", "impact": "流动性环境逆转"},
        ],
    },
    "ai_boom": {
        "title": "AI叙事驱动循环",
        "narrative_driver": "AI is transformational → Buy tech",
        "stages": {
            "forming": "AI突破性技术出现，少数股票领涨",
            "accelerating": "AI叙事扩散，资金追逐AI主题，估值快速扩张",
            "extreme": "'AI will change everything'成为共识，非AI公司也蹭概念",
            "cracking": "AI盈利不达预期，或监管风险显现",
            "reversing": "AI股票杀估值，叙事从'革命'变为'泡沫'",
        },
        "historical_analogs": ["1999-2000 dot-com (internet analogy)", "2023 AI rally"],
        "break_triggers": [
            {"trigger": "主要AI公司盈利miss", "impact": "信心动摇"},
            {"trigger": "AI监管立法加速", "impact": "估值重估"},
            {"trigger": "AI capex ROI不达预期", "impact": "叙事根本性证伪"},
        ],
    },
}

# ── Reinforcement scoring by pattern ──────────────────────────────────────


def _score_reinforcement(
    cycle_key: str,
    beliefs: list[MarketBelief],
    flows: CapitalFlowSnapshot | None,
    market_data: dict,
) -> dict:
    """Score how strongly the Narrative-Capital-Price loop is reinforcing.

    Returns dict with scores for each leg of the triangle.
    """
    vix = float(market_data.get("vix", 18))
    spx_ytd = float(market_data.get("spx_ytd", 0) or market_data.get("nasdaq_ytd", 0))

    # Narrative reinforcement: are beliefs multi-directionally consistent?
    narrative_score = 0.5
    if beliefs:
        # Strong beliefs = strong narrative
        avg_strength = sum(b.strength for b in beliefs) / len(beliefs)
        # High consensus = more reinforcement
        avg_consensus = sum(b.consensus_level for b in beliefs) / len(beliefs)
        narrative_score = avg_strength * 0.6 + avg_consensus * 0.4

    # Capital flow reinforcement
    flow_score = 0.5
    if flows:
        flow_momentum = abs(flows.flow_momentum)
        if flows.risk_appetite_flow in ("risk-on", "risk-off"):
            flow_score = 0.5 + flow_momentum * 0.5  # Directional flows = higher reinforcement

    # Price reinforcement: strong trends = price confirms narrative
    price_score = 0.5
    if abs(spx_ytd) > 20:
        price_score = 0.8  # Strong trend
    elif abs(spx_ytd) > 10:
        price_score = 0.65
    if vix < 12:
        price_score = min(price_score + 0.15, 1.0)  # Low vol = smooth trend = reinforcement

    overall = narrative_score * 0.4 + flow_score * 0.3 + price_score * 0.3

    return {
        "narrative_reinforcement": narrative_score,
        "capital_reinforcement": flow_score,
        "price_reinforcement": price_score,
        "overall_reinforcement": overall,
    }


def _estimate_cycle_maturity(stage: str) -> float:
    """Estimate how far along the cycle we are."""
    stage_map = {
        "forming": 0.15,
        "accelerating": 0.4,
        "extreme": 0.75,
        "cracking": 0.85,
        "reversing": 0.95,
    }
    return stage_map.get(stage, 0.5)


def _determine_cycle_stage(
    reinforcement_score: float,
    beliefs: list[MarketBelief],
    vix: float,
    spx_ytd: float,
) -> str:
    """Determine cycle stage based on reinforcement + market conditions."""
    # Check if beliefs are in extreme/cracking/broken stage
    if beliefs:
        stages = [b.stage for b in beliefs]
        if "broken" in stages:
            return "reversing"
        if "challenged" in stages and reinforcement_score < 0.4:
            return "cracking"
        if "extreme" in stages:
            return "extreme"

    if reinforcement_score > 0.7:
        return "extreme" if vix < 15 else "accelerating"
    elif reinforcement_score > 0.5:
        return "accelerating"
    elif reinforcement_score > 0.3:
        return "forming"
    else:
        return "cracking" if vix > 30 else "forming"


# ═══════════════════════════════════════════════════════════════════════════
# ReflexivityCycleDetector
# ═══════════════════════════════════════════════════════════════════════════


class ReflexivityCycleDetector:
    """Detects self-reinforcing reflexivity cycles in financial markets.

    Combines MarketBelief and CapitalFlow data to identify when
    Narrative, Capital, and Price form a self-reinforcing loop —
    the core mechanism of boom-bust sequences.

    Usage:
        detector = ReflexivityCycleDetector()
        report = detector.detect(market_data, beliefs, flows)

    The report contains:
        - Active reflexivity cycles with stage classification
        - Break trigger candidates
        - Vulnerability scoring
        - Historical analog references
    """

    def __init__(self):
        self.belief_model = MarketBeliefModel()
        self.flow_tracker = CapitalFlowTracker()
        self._cycle_history: list[ReflexivityCycle] = []

    # ── Public API ────────────────────────────────────────────────────

    def detect(
        self,
        market_data: dict,
        beliefs: list[MarketBelief] | None = None,
        flows: CapitalFlowSnapshot | None = None,
        dominant_narrative: str = "",
        narrative_objects: list = None,
    ) -> ReflexivityReport:
        """Main entry point: detect active reflexivity cycles.

        Args:
            market_data: Market indicators dict
            beliefs: Pre-identified market beliefs (auto-detected if None)
            flows: Capital flow snapshot (auto-generated if None)
            dominant_narrative: Dominant narrative description
            narrative_objects: Narrative objects from competition engine

        Returns:
            ReflexivityReport with detected cycles and warnings
        """
        now = datetime.now(UTC)
        report_id = f"reflex-{now.strftime('%Y%m%d-%H%M')}"

        # Auto-generate if not provided
        if beliefs is None:
            beliefs = self.belief_model.identify_beliefs(
                market_data, dominant_narrative, narrative_objects
            )
        if flows is None:
            flows = self.flow_tracker.snapshot(market_data)

        # ── Match active cycles ──
        cycles = []
        narrative_text = dominant_narrative.lower()

        vix = float(market_data.get("vix", 18))
        spx_ytd = float(market_data.get("spx_ytd", 0) or market_data.get("nasdaq_ytd", 0))
        cpi = float(market_data.get("cpi_yoy", 0))
        dxy = float(market_data.get("dxy", 100))

        # 1. Inflation cycle
        if cpi > 4 or "inflation" in narrative_text:
            cycle = self._build_cycle("inflation_cycle", beliefs, flows, market_data, now)
            if cycle.self_reinforcement_score > 0.2:
                cycles.append(cycle)

        # 2. Dollar cycle
        if dxy > 100 or dxy < 95 or "dollar" in narrative_text or "dxy" in narrative_text:
            cycle = self._build_cycle("dollar_supercycle", beliefs, flows, market_data, now)
            if cycle.self_reinforcement_score > 0.2:
                cycles.append(cycle)

        # 3. Risk-on bubble / Risk-off spiral
        if vix < 15 or vix > 25:
            cycle = self._build_cycle("risk_on_bubble", beliefs, flows, market_data, now)
            if cycle.self_reinforcement_score > 0.3:
                cycles.append(cycle)

        # 4. AI boom (structural)
        if "ai" in narrative_text or "tech" in narrative_text:
            nasdaq_ytd = float(market_data.get("nasdaq_ytd", spx_ytd))
            if abs(nasdaq_ytd) > 15:
                cycle = self._build_cycle("ai_boom", beliefs, flows, market_data, now)
                if cycle.self_reinforcement_score > 0.3:
                    cycles.append(cycle)

        # ── Sort by danger ──
        cycles.sort(key=lambda c: c.self_reinforcement_score * c.vulnerability_score, reverse=True)
        most_dangerous = cycles[0] if cycles else None

        # ── Warning signals ──
        warnings = self._generate_warnings(cycles, market_data, beliefs, flows)

        # ── Overall reflexivity score ──
        overall = self._compute_overall_reflexivity(cycles, market_data)

        report = ReflexivityReport(
            report_id=report_id,
            active_beliefs=beliefs,
            capital_flows=flows,
            detected_cycles=cycles,
            reflexivity_score=overall,
            most_dangerous_cycle=most_dangerous,
            key_warning_signals=warnings,
            summary=self._build_summary(cycles, overall, warnings),
        )

        # Record history
        self._cycle_history.extend(cycles)

        logger.info(
            "Reflexivity report: %d cycles, score=%.2f, warnings=%d",
            len(cycles),
            overall,
            len(warnings),
        )
        return report

    def _build_cycle(
        self,
        cycle_key: str,
        beliefs: list[MarketBelief],
        flows: CapitalFlowSnapshot | None,
        market_data: dict,
        timestamp: datetime,
    ) -> ReflexivityCycle:
        """Build a ReflexivityCycle from a matched pattern."""
        pattern = CYCLE_PATTERNS.get(cycle_key, {})
        vix = float(market_data.get("vix", 18))
        spx_ytd = float(market_data.get("spx_ytd", 0) or market_data.get("nasdaq_ytd", 0))

        # Score reinforcement
        scores = _score_reinforcement(cycle_key, beliefs, flows, market_data)
        reinforcement = scores["overall_reinforcement"]

        # Determine stage
        stage = _determine_cycle_stage(reinforcement, beliefs, vix, spx_ytd)
        maturity = _estimate_cycle_maturity(stage)

        # Vulnerability
        vuln = 1.0 - reinforcement if stage == "extreme" else 0.5
        if stage == "cracking":
            vuln = 0.8

        # Capital flow direction
        flow_dir = "unknown"
        if flows:
            if flows.risk_appetite_flow == "risk-on":
                flow_dir = "inflow to risk assets"
            elif flows.risk_appetite_flow == "risk-off":
                flow_dir = "outflow from risk assets"

        # Price feedback
        price_feedback = f"Equities {'up' if spx_ytd > 0 else 'down'} {abs(spx_ytd):.0f}% YTD"
        if vix < 13:
            price_feedback += ", VIX extremely low (complacency signal)"
        elif vix > 30:
            price_feedback += ", VIX elevated (stress signal)"

        # Stage description
        stage_desc = pattern.get("stages", {}).get(stage, "")

        now_str = timestamp.isoformat()

        return ReflexivityCycle(
            cycle_id=f"{cycle_key}-{timestamp.strftime('%Y%m%d')}",
            title=pattern.get("title", cycle_key),
            description=f"{pattern.get('narrative_driver', '')} | Stage: {stage} — {stage_desc}",
            narrative_driver=pattern.get("narrative_driver", ""),
            capital_flow_direction=flow_dir,
            price_feedback=price_feedback,
            stage=stage,
            self_reinforcement_score=round(reinforcement, 2),
            cycle_maturity=round(maturity, 2),
            estimated_duration="weeks" if stage in ("extreme", "cracking") else "months",
            break_trigger_candidates=pattern.get("break_triggers", []),
            vulnerability_score=round(vuln, 2),
            historical_analogs=pattern.get("historical_analogs", []),
            favored_assets=self._get_favored_assets(cycle_key, stage),
            unfavored_assets=self._get_unfavored_assets(cycle_key, stage),
            reversal_candidates=self._get_reversal_candidates(cycle_key),
            detected_at=now_str,
            confidence=round(reinforcement, 2),
        )

    # ── Asset impact helpers ──────────────────────────────────────────

    def _get_favored_assets(self, cycle_key: str, stage: str) -> list[str]:
        """Get assets favored in this cycle/stage."""
        mapping = {
            "inflation_cycle": ["short-duration bonds", "commodities", "TIPS", "value stocks"],
            "dollar_supercycle": ["USD", "US equities (relative)", "short EM FX"],
            "risk_on_bubble": ["equities", "credit", "carry trades", "growth stocks"],
            "ai_boom": ["tech stocks", "semiconductors", "AI-exposed equities"],
        }
        return mapping.get(cycle_key, [])

    def _get_unfavored_assets(self, cycle_key: str, stage: str) -> list[str]:
        """Get assets unfavored in this cycle/stage."""
        mapping = {
            "inflation_cycle": ["long-duration bonds", "growth stocks (high PE)", "EM local debt"],
            "dollar_supercycle": ["EM currencies", "gold (temporarily)", "EM equities"],
            "risk_on_bubble": ["cash", "volatility shorts", "safe havens"],
            "ai_boom": ["value stocks", "traditional industrials", "non-AI tech"],
        }
        return mapping.get(cycle_key, [])

    def _get_reversal_candidates(self, cycle_key: str) -> list[str]:
        """Assets that would benefit most from cycle reversal."""
        mapping = {
            "inflation_cycle": ["long-duration Treasuries", "gold", "growth/tech stocks"],
            "dollar_supercycle": ["EM equities", "EM FX", "gold", "commodities"],
            "risk_on_bubble": ["VIX longs", "safe-haven bonds", "USD", "gold"],
            "ai_boom": ["value stocks", "defensive sectors", "ex-US equities"],
        }
        return mapping.get(cycle_key, [])

    # ── Warnings & Summary ────────────────────────────────────────────

    def _generate_warnings(
        self,
        cycles: list[ReflexivityCycle],
        market_data: dict,
        beliefs: list[MarketBelief],
        flows: CapitalFlowSnapshot | None,
    ) -> list[str]:
        """Generate key warning signals."""
        warnings = []
        vix = float(market_data.get("vix", 18))

        for cycle in cycles:
            if cycle.stage == "extreme":
                warnings.append(
                    f"[{cycle.title}] 处于极端阶段 — "
                    f"自强化分数 {cycle.self_reinforcement_score:.2f}，"
                    f"脆弱性 {cycle.vulnerability_score:.2f}"
                )
            if cycle.stage == "cracking":
                warnings.append(f"[{cycle.title}] 出现裂痕 — 监控反转风险")
            if cycle.vulnerability_score > 0.7 and cycle.stage == "extreme":
                warnings.append(f"高脆弱性循环: [{cycle.title}] — " f"技术性反转风险显著")

        # VIX warning
        if vix < 13:
            warnings.append("VIX极端低位(<13) — 市场自满信号，波动率回升风险")
        elif vix > 30:
            warnings.append("VIX高位(>30) — 恐慌可能自我强化，关注流动性风险")

        # Belief fragility
        fragile = self.belief_model.get_most_fragile_beliefs(beliefs, top_n=2)
        for fb in fragile:
            if fb.vulnerability_to_disconfirmation > 0.6:
                warnings.append(
                    f"脆弱信念: [{fb.title}] — "
                    f"如果被证伪，反转幅度可能为 [{fb.reversal_magnitude_estimate}]"
                )

        return warnings

    def _compute_overall_reflexivity(
        self, cycles: list[ReflexivityCycle], market_data: dict
    ) -> float:
        """Compute overall reflexivity intensity score."""
        if not cycles:
            return 0.1

        # Weight by cycle maturity and reinforcement
        scores = []
        for c in cycles:
            weight = c.cycle_maturity if c.stage == "extreme" else 0.5
            scores.append(c.self_reinforcement_score * weight)

        return round(sum(scores) / len(scores), 2) if scores else 0.0

    def _build_summary(
        self, cycles: list[ReflexivityCycle], overall: float, warnings: list[str]
    ) -> str:
        """Build executive summary text."""
        if not cycles:
            return "未检测到显著的反身性循环。市场可能处于均衡或方向不明确的状态。"

        parts = [f"检测到 {len(cycles)} 个活跃的反身性循环，总体反身性强度: {overall:.2f}\n"]

        for c in cycles[:3]:
            parts.append(
                f"- {c.title}: 阶段={c.stage}, "
                f"自强化={c.self_reinforcement_score:.2f}, "
                f"成熟度={c.cycle_maturity:.2f}"
            )

        if warnings:
            parts.append(f"\n⚠  警告信号 ({len(warnings)}个):")
            for w in warnings[:3]:
                parts.append(f"  - {w}")

        return "\n".join(parts)
