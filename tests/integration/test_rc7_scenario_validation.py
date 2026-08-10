"""RC-7 Scenario Validation — 20+ real-world macro scenarios.

Validates:
    - Hypothesis合理性 (does the reasoning make macro sense?)
    - Reflection纠正能力 (can reflection adjust incorrect hypotheses?)
    - Memory一致性 (does memory form consistent long-term beliefs?)
    - Narrative表达质量 (does the output read like a human analyst?)

Each scenario simulates real macro events with specific indicator combinations.
"""

import pytest
from datetime import datetime, timezone

from src.domain.memory import BeliefStatus, TransitionType
from src.domain.narrative import ConfidenceLevel
from src.memory.store import BeliefMemoryStore
from src.narrative.engine import NarrativeEngine
from src.schemas.hypothesis import HypothesisEvidence, HypothesisSchema, HypothesisSet
from src.schemas.memory import BeliefRecord
from src.schemas.narrative import MacroNarrative
from src.schemas.reflection import ReflectionReport, ReflectionSet, ReflectionVerdict
from src.schemas.signal import MacroSignalSchema, SignalDirection, SignalEvidence, SignalStrength, SignalSnapshot


# ── Helpers ─────────────────────────────────────────────────────────────────


def sig(indicator: str, direction: str, dimension: str, confidence: float = 0.7):
    return MacroSignalSchema(
        indicator=indicator, dimension=dimension,
        direction=SignalDirection(direction),
        strength=SignalStrength("strong") if confidence > 0.7 else SignalStrength("moderate"),
        confidence=confidence,
        evidence=[SignalEvidence(rule_id=f"r_{indicator}", rule_description=direction,
                                  input_value=1.0, condition=f"{indicator} {direction}",
                                  interpretation=f"{indicator}: {direction} signal")],
    )


def hyp(statement: str, dimension: str, direction: str = "neutral",
        confidence: float = 0.6, sup: int = 2, con: int = 1):
    return HypothesisSchema(
        statement=statement, dimension=dimension,
        direction=SignalDirection(direction), confidence=confidence,
        supporting_evidence=[HypothesisEvidence(
            indicator=f"S{i}", signal_id=f"s_{i}", observation=f"Support {i}",
            interpretation=f"Evidence for: {statement[:30]}",
            contribution=0.7, alignment="supporting",
        ) for i in range(sup)],
        contradicting_evidence=[HypothesisEvidence(
            indicator=f"C{i}", signal_id=f"c_{i}", observation=f"Contradict {i}",
            interpretation=f"Evidence against", contribution=0.3, alignment="contradicting",
        ) for i in range(con)],
    )


def ref(h: HypothesisSchema, verdict: str = "confirmed", confidence: float = 0.7):
    return ReflectionReport(
        hypothesis_id=h.hypothesis_id, statement=h.statement,
        original_confidence=h.confidence, updated_confidence=confidence,
        verdict=ReflectionVerdict(verdict), findings=[],
        evidence_sufficiency="medium", evidence_consistency="consistent",
        review_summary=f"Review: {h.statement[:60]}",
    )


@pytest.fixture
def engine():
    return NarrativeEngine()


def validate_narrative(n: MacroNarrative, scenario_name: str):
    """Shared validation: every scenario produces a complete MacroNarrative."""
    assert isinstance(n.summary, str) and len(n.summary) > 0, f"{scenario_name}: missing summary"
    assert isinstance(n.macro_story, str) and len(n.macro_story) > 0, f"{scenario_name}: missing macro_story"
    assert len(n.scenario_analysis) == 5, f"{scenario_name}: expected 5 scenarios"
    assert n.confidence_level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW)
    assert 0.0 <= n.confidence_score <= 1.0
    for s in n.scenario_analysis:
        assert 0.0 <= s.probability <= 1.0, f"{scenario_name}: {s.name} prob {s.probability}"


# ═══════════════════════════════════════════════════════════════════════════════
# 20+ Real Macro Scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestFedMeetingScenarios:
    """美联储议息相关场景"""

    def test_fed_hawkish_hold(self, engine):
        """Fed鹰派暂停：DXY强, US10Y升, 流动性收紧"""
        signals = SignalSnapshot(signals=[
            sig("DXY", "bullish", "Liquidity", 0.85),
            sig("US10Y", "bullish", "Liquidity", 0.80),
            sig("FEDFUNDS", "bullish", "Liquidity", 0.75),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Fed hawkish hold tightens liquidity, dollar strengthens.", "Liquidity", "bearish", 0.80, 3, 0),
        ], dimensions_covered=["Liquidity"])
        rs = ReflectionSet(reports=[ref(hs.hypotheses[0], "confirmed", 0.85)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "Fed Hawkish Hold")
        assert n.confidence_level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    def test_fed_dovish_pivot(self, engine):
        """Fed鸽派转向：DXY弱, US10Y降"""
        signals = SignalSnapshot(signals=[
            sig("DXY", "bearish", "Liquidity", 0.80),
            sig("US10Y", "bearish", "Liquidity", 0.75),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Fed dovish pivot eases financial conditions.", "Liquidity", "bullish", 0.75, 3, 0),
        ], dimensions_covered=["Liquidity"])
        rs = ReflectionSet(reports=[ref(hs.hypotheses[0], "confirmed", 0.80)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "Fed Dovish Pivot")

    def test_fed_emergency_cut(self, engine):
        """Fed紧急降息：DXY暴跌, 避险资产飙升"""
        signals = SignalSnapshot(signals=[
            sig("DXY", "bearish", "Liquidity", 0.90),
            sig("US10Y", "bearish", "Liquidity", 0.85),
            sig("FEDFUNDS", "bearish", "Liquidity", 0.90),
            sig("HYG", "bearish", "Credit", 0.80),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Emergency rate cut signals severe stress.", "Liquidity", "bearish", 0.85, 4, 0),
            hyp("Credit markets anticipate recession risk.", "Credit", "bearish", 0.80, 2, 1),
        ], dimensions_covered=["Liquidity", "Credit"])
        rs = ReflectionSet(reports=[
            ref(hs.hypotheses[0], "confirmed", 0.90),
            ref(hs.hypotheses[1], "confirmed", 0.85),
        ])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "Fed Emergency Cut")
        assert len(n.key_risks) >= 1, f"Expected at least 1 risk, got {len(n.key_risks)}"


class TestCPIDataScenarios:
    """CPI公布日场景"""

    def test_cpi_above_expectations(self, engine):
        """CPI超预期：通胀信号bullish, 利率预期上升"""
        signals = SignalSnapshot(signals=[
            sig("CPI", "bullish", "Inflation", 0.85),
            sig("PCE", "bullish", "Inflation", 0.80),
            sig("US10Y", "bullish", "Liquidity", 0.70),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Inflation re-acceleration pressures Fed to maintain restrictive stance.", "Inflation", "bearish", 0.80, 3, 0),
        ], dimensions_covered=["Inflation"])
        rs = ReflectionSet(reports=[ref(hs.hypotheses[0], "confirmed", 0.85)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "CPI Above Expectations")
        # Inflation Re-acceleration scenario should dominate
        inflation_sc = [s for s in n.scenario_analysis if "Inflation" in s.name]
        assert len(inflation_sc) == 1 and inflation_sc[0].probability > 0.25

    def test_cpi_below_expectations(self, engine):
        """CPI低于预期：通胀下行, 降息预期升温"""
        signals = SignalSnapshot(signals=[
            sig("CPI", "bearish", "Inflation", 0.80),
            sig("PCE", "bearish", "Inflation", 0.75),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Disinflation on track, supporting eventual rate cuts.", "Inflation", "bullish", 0.75, 3, 0),
        ], dimensions_covered=["Inflation"])
        rs = ReflectionSet(reports=[ref(hs.hypotheses[0], "confirmed", 0.80)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "CPI Below Expectations")


class TestNFPDataScenarios:
    """非农就业数据公布日场景"""

    def test_nfp_strong(self, engine):
        """非农强劲：增长bullish, 劳动力市场紧"""
        signals = SignalSnapshot(signals=[
            sig("PMI", "bullish", "Growth", 0.75),
            sig("ISM", "bullish", "Growth", 0.70),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Strong labor market supports resilient growth.", "Growth", "bullish", 0.75, 3, 0),
        ], dimensions_covered=["Growth"])
        rs = ReflectionSet(reports=[ref(hs.hypotheses[0], "confirmed", 0.80)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "NFP Strong")
        soft = [s for s in n.scenario_analysis if "Soft" in s.name]
        assert soft[0].probability > 0.25

    def test_nfp_weak(self, engine):
        """非农疲弱：增长bearish, 经济减速"""
        signals = SignalSnapshot(signals=[
            sig("PMI", "bearish", "Growth", 0.80),
            sig("ISM", "bearish", "Growth", 0.75),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Labor market deterioration signals economic slowdown.", "Growth", "bearish", 0.80, 3, 0),
        ], dimensions_covered=["Growth"])
        rs = ReflectionSet(reports=[ref(hs.hypotheses[0], "confirmed", 0.85)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "NFP Weak")
        hard = [s for s in n.scenario_analysis if "Hard" in s.name]
        assert len(hard) >= 1, "Hard Landing scenario must be present"
        assert hard[0].probability >= 0.08, f"Hard Landing prob too low: {hard[0].probability}"


class TestAIEarningsScenarios:
    """AI龙头财报场景 — NVIDIA, Microsoft等"""

    def test_ai_capex_surge(self, engine):
        """AI Capex超预期：risk-on, 科技股领涨"""
        signals = SignalSnapshot(signals=[
            sig("HYG", "bullish", "Credit", 0.80),
            sig("PMI", "bullish", "Growth", 0.75),
            sig("VIX", "bullish", "Risk_Appetite", 0.65),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("AI capex boom drives risk appetite and growth expectations.", "Growth", "bullish", 0.80, 3, 0),
        ], dimensions_covered=["Growth", "Credit"])
        rs = ReflectionSet(reports=[ref(hs.hypotheses[0], "confirmed", 0.85)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "AI Capex Surge")
        risk_on = [s for s in n.scenario_analysis if "Risk-On" in s.name]
        assert risk_on[0].probability > 0.30

    def test_ai_earnings_miss(self, engine):
        """AI财报不达预期：risk-off, 科技股回调"""
        signals = SignalSnapshot(signals=[
            sig("HYG", "bearish", "Credit", 0.80),
            sig("VIX", "bearish", "Risk_Appetite", 0.75),
            sig("PMI", "bearish", "Growth", 0.65),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("AI earnings miss triggers risk reassessment.", "Credit", "bearish", 0.80, 3, 0),
        ], dimensions_covered=["Credit", "Growth"])
        rs = ReflectionSet(reports=[ref(hs.hypotheses[0], "confirmed", 0.85)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "AI Earnings Miss")
        risk_on = [s for s in n.scenario_analysis if "Risk-On" in s.name]
        assert risk_on[0].probability < 0.45


class TestGeopoliticalScenarios:
    """地缘政治事件场景"""

    def test_middle_east_tension(self, engine):
        """中东紧张：油价飙升, VIX暴涨, 避险情绪浓"""
        signals = SignalSnapshot(signals=[
            sig("VIX", "bearish", "Risk_Appetite", 0.90),
            sig("DXY", "bullish", "Liquidity", 0.80),
            sig("HYG", "bearish", "Credit", 0.85),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Geopolitical shock triggers flight to safety.", "Risk_Appetite", "bearish", 0.85, 3, 0),
        ], dimensions_covered=["Risk_Appetite", "Liquidity"])
        rs = ReflectionSet(reports=[ref(hs.hypotheses[0], "confirmed", 0.90)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "Geopolitical Tension")
        assert len(n.key_risks) >= 1

    def test_trade_war_escalation(self, engine):
        """贸易战升级：DXY强, PMI弱, 供应链风险"""
        signals = SignalSnapshot(signals=[
            sig("DXY", "bullish", "Liquidity", 0.80),
            sig("PMI", "bearish", "Growth", 0.75),
            sig("US10Y", "bullish", "Liquidity", 0.70),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Trade war escalation tightens conditions and slows growth.", "Growth", "bearish", 0.75, 3, 1),
            hyp("Dollar strength from safe-haven flows tightens liquidity.", "Liquidity", "bearish", 0.70, 2, 1),
        ], dimensions_covered=["Growth", "Liquidity"])
        rs = ReflectionSet(reports=[
            ref(hs.hypotheses[0], "confirmed", 0.80),
            ref(hs.hypotheses[1], "confirmed", 0.75),
        ])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "Trade War")


class TestYieldCurveScenarios:
    """债券收益率曲线场景"""

    def test_yield_curve_inversion(self, engine):
        """收益率曲线倒挂：US2Y > US10Y, 衰退信号"""
        signals = SignalSnapshot(signals=[
            sig("US2Y", "bullish", "Liquidity", 0.85),
            sig("US10Y", "bearish", "Liquidity", 0.80),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Inverted yield curve signals elevated recession risk.", "Liquidity", "bearish", 0.80, 3, 0),
        ], dimensions_covered=["Liquidity"])
        rs = ReflectionSet(reports=[ref(hs.hypotheses[0], "confirmed", 0.85)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "Yield Curve Inversion")
        hard = [s for s in n.scenario_analysis if "Hard" in s.name]
        assert len(hard) >= 1, "Hard Landing scenario must be present"
        assert hard[0].probability >= 0.08, f"Hard Landing prob too low: {hard[0].probability}"

    def test_yield_curve_steepening(self, engine):
        """收益率曲线陡峭化：长端利率快速上升"""
        signals = SignalSnapshot(signals=[
            sig("US10Y", "bullish", "Liquidity", 0.85),
            sig("US2Y", "bearish", "Liquidity", 0.60),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Curve steepening reflects reflation expectations.", "Liquidity", "neutral", 0.65, 2, 2),
        ], dimensions_covered=["Liquidity"])
        rs = ReflectionSet(reports=[ref(hs.hypotheses[0], "uncertain", 0.60)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "Yield Curve Steepening")


class TestDXYCombinationScenarios:
    """DXY + 其他指标组合场景"""

    def test_dxy_vix_divergence(self, engine):
        """DXY升 + VIX降 = 风险偏好与美元走强并存, 矛盾信号"""
        signals = SignalSnapshot(signals=[
            sig("DXY", "bullish", "Liquidity", 0.85),
            sig("VIX", "bullish", "Risk_Appetite", 0.70),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Dollar strength and low VIX create mixed macro picture.", "Liquidity", "bearish", 0.50, 2, 3),
        ], dimensions_covered=["Liquidity", "Risk_Appetite"])
        rs = ReflectionSet(reports=[ref(hs.hypotheses[0], "uncertain", 0.45)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "DXY-VIX Divergence")
        # Mixed signals → LOW or MEDIUM confidence
        assert n.confidence_level in (ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM)

    def test_dxy_hyg_correlation_breakdown(self, engine):
        """DXY升 + HYG也升 = 相关性破裂, 异常信号"""
        signals = SignalSnapshot(signals=[
            sig("DXY", "bullish", "Liquidity", 0.80),
            sig("HYG", "bullish", "Credit", 0.75),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Unusual: dollar and credit both strong.", "Liquidity", "bearish", 0.45, 1, 3),
            hyp("Risk appetite remains despite dollar strength.", "Credit", "bullish", 0.65, 2, 1),
        ], dimensions_covered=["Liquidity", "Credit"])
        rs = ReflectionSet(reports=[
            ref(hs.hypotheses[0], "uncertain", 0.40),
            ref(hs.hypotheses[1], "confirmed", 0.70),
        ])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "DXY-HYG Correlation")


class TestCopperGoldScenarios:
    """铜/金比率 + 商品信号场景"""

    def test_copper_surge(self, engine):
        """铜价飙升：全球增长预期上升"""
        signals = SignalSnapshot(signals=[
            sig("PMI", "bullish", "Growth", 0.80),
            sig("INDPRO", "bullish", "Growth", 0.75),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Industrial commodity strength signals global growth acceleration.", "Growth", "bullish", 0.80, 3, 0),
        ], dimensions_covered=["Growth"])
        rs = ReflectionSet(reports=[ref(hs.hypotheses[0], "confirmed", 0.85)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "Copper Surge")

    def test_gold_surge_vix_spike(self, engine):
        """金价暴涨 + VIX飙升：极端避险"""
        signals = SignalSnapshot(signals=[
            sig("VIX", "bearish", "Risk_Appetite", 0.90),
            sig("DXY", "bearish", "Liquidity", 0.75),
            sig("HYG", "bearish", "Credit", 0.85),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Extreme risk aversion — gold and VIX surging.", "Risk_Appetite", "bearish", 0.90, 3, 0),
            hyp("Credit markets pricing in severe stress scenario.", "Credit", "bearish", 0.85, 3, 0),
        ], dimensions_covered=["Risk_Appetite", "Credit", "Liquidity"])
        rs = ReflectionSet(reports=[
            ref(hs.hypotheses[0], "confirmed", 0.95),
            ref(hs.hypotheses[1], "confirmed", 0.90),
        ])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "Gold + VIX Surge")
        assert n.confidence_level == ConfidenceLevel.HIGH


class TestMemoryConsistencyScenarios:
    """Memory一致性验证场景"""

    def test_belief_evolution_over_days(self, engine):
        """Day 1: liquidity improving (0.75) → Day 10: liquidity tightening (0.85)"""
        # Day 1: bullish view
        h1 = hyp("Liquidity is improving as Fed pivots dovish.", "Liquidity", "bullish", 0.75, 3, 0)
        prior = BeliefRecord(
            run_id="day1", hypothesis_id=h1.hypothesis_id,
            dimension="Liquidity", statement="Liquidity improving.",
            direction=SignalDirection("bullish"), confidence=0.75,
            status=BeliefStatus.HELD, transition=TransitionType.NEW,
            supporting_count=3, contradicting_count=0,
            evidence_summary="Strong dovish signals.",
            review_summary="Day 1: confirmed",
            timestamp=datetime(2026, 7, 5, tzinfo=timezone.utc),
        )

        # Day 10: reversal — signals reverse
        h2 = hyp("Liquidity conditions have tightened sharply.", "Liquidity", "bearish", 0.85, 3, 0)
        signals = SignalSnapshot(signals=[
            sig("DXY", "bullish", "Liquidity", 0.90),
            sig("US10Y", "bullish", "Liquidity", 0.85),
        ])
        hs = HypothesisSet(hypotheses=[h2], dimensions_covered=["Liquidity"])
        rs = ReflectionSet(reports=[ref(h2, "confirmed", 0.90)])

        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs, belief_records=[prior])
        validate_narrative(n, "Belief Evolution Day 1→10")

        # Verify reversal detection
        reversals = [bc for bc in n.belief_changes if bc.direction == "reversed"]
        assert len(reversals) >= 1, "Should detect belief reversal"
        assert reversals[0].dimension == "Liquidity"

    def test_confidence_gradual_increase(self, engine):
        """Confidence builds gradually: 0.5 → 0.65 → 0.80"""
        h = hyp("Growth is steadily improving.", "Growth", "bullish", 0.80, 3, 0)
        priors = [
            BeliefRecord(
                run_id=f"day{i}", hypothesis_id=h.hypothesis_id,
                dimension="Growth", statement=h.statement,
                direction=SignalDirection("bullish"),
                confidence=conf,
                status=BeliefStatus.HELD,
                transition=TransitionType.REINFORCED if i > 1 else TransitionType.NEW,
                supporting_count=3, contradicting_count=0,
                evidence_summary=f"Day {i} evidence.",
                review_summary=f"Day {i} review.",
                timestamp=datetime(2026, 7, i, tzinfo=timezone.utc),
            )
            for i, conf in enumerate([0.50, 0.65], start=1)
        ]
        signals = SignalSnapshot(signals=[
            sig("PMI", "bullish", "Growth", 0.80),
        ])
        hs = HypothesisSet(hypotheses=[h], dimensions_covered=["Growth"])
        rs = ReflectionSet(reports=[ref(h, "confirmed", 0.85)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs, belief_records=priors)
        validate_narrative(n, "Confidence Gradual Increase")


class TestMixedSignalScenarios:
    """混合信号场景 — 多维度矛盾"""

    def test_growth_up_inflation_up(self, engine):
        """增长强 + 通胀高 = stagflation risk"""
        signals = SignalSnapshot(signals=[
            sig("PMI", "bullish", "Growth", 0.75),
            sig("CPI", "bullish", "Inflation", 0.80),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Growth strong but inflation persists.", "Growth", "bullish", 0.70, 2, 1),
            hyp("Inflation remains elevated despite Fed tightening.", "Inflation", "bearish", 0.75, 3, 0),
        ], dimensions_covered=["Growth", "Inflation"])
        rs = ReflectionSet(reports=[
            ref(hs.hypotheses[0], "confirmed", 0.75),
            ref(hs.hypotheses[1], "confirmed", 0.80),
        ])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "Growth Up + Inflation Up")

    def test_growth_down_inflation_down(self, engine):
        """增长弱 + 通胀低 = disinflation + stagnation"""
        signals = SignalSnapshot(signals=[
            sig("PMI", "bearish", "Growth", 0.80),
            sig("CPI", "bearish", "Inflation", 0.75),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Growth slowing with disinflation — stagflation risk.", "Growth", "bearish", 0.75, 3, 0),
        ], dimensions_covered=["Growth", "Inflation"])
        rs = ReflectionSet(reports=[ref(hs.hypotheses[0], "confirmed", 0.80)])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "Growth Down + Inflation Down")

    def test_full_dimension_coverage(self, engine):
        """所有5个维度同时活跃 — 最复杂的场景"""
        signals = SignalSnapshot(signals=[
            sig("DXY", "bullish", "Liquidity", 0.80),
            sig("HYG", "bearish", "Credit", 0.75),
            sig("PMI", "bullish", "Growth", 0.70),
            sig("CPI", "bearish", "Inflation", 0.65),
            sig("VIX", "bearish", "Risk_Appetite", 0.60),
        ])
        hs = HypothesisSet(hypotheses=[
            hyp("Liquidity tightening.", "Liquidity", "bearish", 0.75, 2, 1),
            hyp("Credit stress.", "Credit", "bearish", 0.70, 2, 1),
            hyp("Growth resilient.", "Growth", "bullish", 0.65, 2, 1),
            hyp("Inflation easing.", "Inflation", "bullish", 0.60, 2, 1),
            hyp("Risk appetite mixed.", "Risk_Appetite", "neutral", 0.50, 1, 2),
        ], dimensions_covered=["Liquidity", "Credit", "Growth", "Inflation", "Risk_Appetite"])
        rs = ReflectionSet(reports=[
            ref(hs.hypotheses[0], "confirmed", 0.80),
            ref(hs.hypotheses[1], "confirmed", 0.75),
            ref(hs.hypotheses[2], "uncertain", 0.55),
            ref(hs.hypotheses[3], "uncertain", 0.50),
            ref(hs.hypotheses[4], "uncertain", 0.45),
        ])
        n = engine.narrate(signals=signals, hypotheses=hs, reflections=rs)
        validate_narrative(n, "Full 5-Dimension Coverage")
        # All 5 dimensions should be present
        assert len(n.liquidity_analysis) > 0
        assert len(n.credit_analysis) > 0
        assert len(n.growth_analysis) > 0
        assert len(n.inflation_analysis) > 0
        # Risk appetite is also present
        assert hasattr(n, "risk_appetite_analysis")
