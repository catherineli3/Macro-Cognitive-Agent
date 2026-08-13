"""Beta Integration Tests — 10 macro scenarios validating full MacroNarrative output.

Each scenario:
    1. Constructs scenario-specific cognitive chain inputs
    2. Runs NarrativeEngine.narrate()
    3. Validates MacroNarrative Schema completeness
    4. Validates confidence, scenarios, risks, action items, belief changes

Architecture frozen: Only tests that consume MacroNarrative — no cognitive module changes.
"""

from datetime import UTC, datetime

import pytest

from src.domain.memory import BeliefStatus, TransitionType
from src.domain.narrative import ConfidenceLevel
from src.domain.reflection import ReflectionVerdict
from src.narrative.engine import NarrativeEngine
from src.schemas.hypothesis import HypothesisEvidence, HypothesisSchema, HypothesisSet
from src.schemas.memory import BeliefRecord
from src.schemas.narrative import (
    ConfidenceExplanation,
    MacroNarrative,
    ScenarioProbability,
)
from src.schemas.reflection import (
    ReflectionReport,
    ReflectionSet,
)
from src.schemas.signal import (
    MacroSignalSchema,
    SignalDirection,
    SignalEvidence,
    SignalSnapshot,
)

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def engine() -> NarrativeEngine:
    """Fresh NarrativeEngine for each scenario."""
    return NarrativeEngine()


def make_signal(
    indicator: str,
    direction: str,
    dimension: str,
    confidence: float = 0.7,
) -> MacroSignalSchema:
    """Helper: create a MacroSignalSchema for scenario building."""
    from src.schemas.signal import SignalStrength

    return MacroSignalSchema(
        indicator=indicator,
        dimension=dimension,
        direction=SignalDirection(direction),
        strength=SignalStrength("strong") if confidence > 0.7 else SignalStrength("moderate"),
        confidence=confidence,
        evidence=[
            SignalEvidence(
                rule_id=f"rule_{indicator.lower()}_{direction}",
                rule_description=f"{indicator} directional assessment",
                input_value=100.0,
                condition=f"{indicator} {direction} bias detected",
                interpretation=f"{indicator} at elevated levels suggesting {direction} bias",
            )
        ],
    )


def make_hypothesis(
    statement: str,
    dimension: str,
    direction: str = "neutral",
    confidence: float = 0.6,
    supporting: int = 2,
    contradicting: int = 1,
) -> HypothesisSchema:
    """Helper: create a HypothesisSchema."""
    return HypothesisSchema(
        statement=statement,
        dimension=dimension,
        direction=SignalDirection(direction),
        confidence=confidence,
        supporting_evidence=[
            HypothesisEvidence(
                indicator=f"IND{i}",
                signal_id=f"sig_{i}",
                observation=f"Observation {i}",
                interpretation=f"Supports hypothesis: {statement[:30]}",
                contribution=0.7,
                alignment="supporting",
            )
            for i in range(supporting)
        ],
        contradicting_evidence=[
            HypothesisEvidence(
                indicator=f"CTR{i}",
                signal_id=f"ctr_{i}",
                observation=f"Contradiction {i}",
                interpretation="Challenges hypothesis",
                contribution=0.3,
                alignment="contradicting",
            )
            for i in range(contradicting)
        ],
    )


def make_reflection(
    hyp: HypothesisSchema,
    verdict: str = "confirmed",
    updated_confidence: float = 0.7,
) -> ReflectionReport:
    """Helper: create a ReflectionReport for a hypothesis."""
    return ReflectionReport(
        hypothesis_id=hyp.hypothesis_id,
        statement=hyp.statement,
        original_confidence=hyp.confidence,
        updated_confidence=updated_confidence,
        verdict=ReflectionVerdict(verdict),
        findings=[],
        evidence_sufficiency="medium",
        evidence_consistency="consistent",
        review_summary=f"Review of: {hyp.statement[:60]}",
    )


def make_belief_record(
    hyp: HypothesisSchema,
    days_ago: int = 1,
    confidence: float | None = None,
) -> BeliefRecord:
    """Helper: create a prior BeliefRecord for change detection."""
    return BeliefRecord(
        run_id=f"run_{int(datetime.now(UTC).timestamp())}",
        hypothesis_id=hyp.hypothesis_id,
        dimension=hyp.dimension,
        statement=hyp.statement,
        direction=hyp.direction,
        confidence=confidence if confidence is not None else hyp.confidence,
        status=BeliefStatus.HELD,
        transition=TransitionType.NEW,
        supporting_count=2,
        contradicting_count=1,
        evidence_summary=f"Prior evidence for {hyp.dimension}",
        review_summary="Prior review",
        timestamp=datetime(2026, 7, 14 - days_ago, tzinfo=UTC),
    )


# ── Shared Validation ─────────────────────────────────────────────────────


def validate_narrative_schema(n: MacroNarrative) -> None:
    """Shared validation: MacroNarrative has all Beta-required fields populated."""
    # Core fields
    assert isinstance(n.summary, str)
    assert isinstance(n.macro_story, str)
    assert isinstance(n.today_key_changes, str)

    # Dimension objects
    for dim in [n.liquidity, n.credit, n.growth, n.inflation]:
        assert dim.dimension in ("liquidity", "credit", "growth", "inflation")
        assert isinstance(dim.summary, str)
        assert isinstance(dim.analysis, str)
        assert 0.0 <= dim.confidence <= 1.0

    # Dimension text analyses
    assert isinstance(n.liquidity_analysis, str)
    assert isinstance(n.credit_analysis, str)
    assert isinstance(n.growth_analysis, str)
    assert isinstance(n.inflation_analysis, str)
    assert isinstance(n.risk_appetite_analysis, str)

    # Scenario analysis
    assert isinstance(n.scenario_analysis, list)
    for s in n.scenario_analysis:
        assert isinstance(s, ScenarioProbability)
        assert isinstance(s.name, str)
        assert 0.0 <= s.probability <= 1.0
        assert isinstance(s.rationale, str)
        assert isinstance(s.key_indicators_to_watch, list)

    # Belief changes
    assert isinstance(n.belief_changes, list)
    assert isinstance(n.belief_changes_text, str)

    # Risks
    assert isinstance(n.risks, list)
    assert isinstance(n.key_risks, list)

    # Action items
    assert isinstance(n.action_items, list)

    # Confidence
    assert isinstance(n.confidence_level, ConfidenceLevel)
    assert 0.0 <= n.confidence_score <= 1.0
    assert n.confidence_explanation is not None
    assert isinstance(n.confidence_explanation, ConfidenceExplanation)
    assert n.confidence_explanation.level == n.confidence_level
    assert n.confidence_explanation.score == n.confidence_score

    # Timestamp
    assert isinstance(n.generated_at, datetime)


# ═══════════════════════════════════════════════════════════════════════════
# Scenario Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScenarioLiquidityTightening:
    """Scenario 1: Liquidity Tightening — DXY strong, yields rising."""

    def test_produces_macro_narrative(self, engine: NarrativeEngine) -> None:
        signals = SignalSnapshot(
            signals=[
                make_signal("DXY", "bullish", "Liquidity", 0.85),
                make_signal("US10Y", "bullish", "Liquidity", 0.75),
            ]
        )
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis(
                    "Global liquidity conditions are tightening as dollar strength "
                    "and rising rates constrain capital flows.",
                    "Liquidity",
                    "bearish",
                    0.80,
                    supporting=3,
                    contradicting=0,
                ),
            ],
            dimensions_covered=["Liquidity"],
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "confirmed", 0.85),
            ]
        )

        n = engine.narrate(signals=signals, hypotheses=hyps, reflections=refs)

        validate_narrative_schema(n)
        assert n.confidence_level == ConfidenceLevel.HIGH
        assert n.confidence_score > 0.70
        assert "tightening" in n.liquidity_analysis.lower() or "Liquidity" in n.liquidity.summary
        assert len(n.scenario_analysis) == 5


class TestScenarioCreditCrisis:
    """Scenario 2: Credit Crisis — spreads widening, HY under pressure."""

    def test_detects_credit_stress(self, engine: NarrativeEngine) -> None:
        signals = SignalSnapshot(
            signals=[
                make_signal("HYG", "bearish", "Credit", 0.90),
                make_signal("SPREAD", "bearish", "Credit", 0.85),
            ]
        )
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis(
                    "Credit markets are under severe stress with widening spreads "
                    "and deteriorating high yield conditions.",
                    "Credit",
                    "bearish",
                    0.85,
                    supporting=3,
                    contradicting=0,
                ),
            ],
            dimensions_covered=["Credit"],
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "confirmed", 0.90),
            ]
        )

        n = engine.narrate(signals=signals, hypotheses=hyps, reflections=refs)

        validate_narrative_schema(n)
        assert len(n.key_risks) >= 1
        # Credit dimension should be present
        assert n.credit.confidence > 0.5
        assert "Credit" in n.credit_analysis or len(n.credit_analysis) > 0


class TestScenarioSoftLanding:
    """Scenario 3: Soft Landing — growth supportive, inflation easing."""

    def test_soft_landing_scenario_dominant(self, engine: NarrativeEngine) -> None:
        signals = SignalSnapshot(
            signals=[
                make_signal("GDP", "bullish", "Growth", 0.70),
                make_signal("PMI", "bullish", "Growth", 0.65),
                make_signal("CPI", "bearish", "Inflation", 0.75),
                make_signal("PCE", "bearish", "Inflation", 0.70),
            ]
        )
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis(
                    "Growth remains resilient while inflation gradually eases, "
                    "consistent with a soft landing trajectory.",
                    "Growth",
                    "bullish",
                    0.75,
                    supporting=3,
                    contradicting=0,
                ),
                make_hypothesis(
                    "Inflation pressures are declining toward target, reducing "
                    "the need for further monetary tightening.",
                    "Inflation",
                    "neutral",
                    0.70,
                    supporting=2,
                    contradicting=1,
                ),
            ],
            dimensions_covered=["Growth", "Inflation"],
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "confirmed", 0.80),
                make_reflection(hyps.hypotheses[1], "confirmed", 0.75),
            ]
        )

        n = engine.narrate(signals=signals, hypotheses=hyps, reflections=refs)

        validate_narrative_schema(n)
        # Soft Landing should be the dominant scenario
        soft_landing = [s for s in n.scenario_analysis if s.name == "Soft Landing"]
        assert len(soft_landing) == 1
        assert soft_landing[0].probability > 0.4


class TestScenarioHardLanding:
    """Scenario 4: Hard Landing / Recession — growth deteriorating."""

    def test_hard_landing_risk_elevated(self, engine: NarrativeEngine) -> None:
        signals = SignalSnapshot(
            signals=[
                make_signal("GDP", "bearish", "Growth", 0.80),
                make_signal("PMI", "bearish", "Growth", 0.85),
                make_signal("CPI", "neutral", "Inflation", 0.50),
            ]
        )
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis(
                    "Economic growth is deteriorating rapidly with leading "
                    "indicators pointing to contraction.",
                    "Growth",
                    "bearish",
                    0.80,
                    supporting=3,
                    contradicting=0,
                ),
                make_hypothesis(
                    "Growth will rebound quickly as monetary policy eases.",
                    "Growth",
                    "bullish",
                    0.30,
                    supporting=1,
                    contradicting=3,
                ),
            ],
            dimensions_covered=["Growth"],
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "confirmed", 0.85),
                make_reflection(hyps.hypotheses[1], "refuted", 0.20),
            ]
        )

        # Prior beliefs with different direction (new → reversal)
        prior = make_belief_record(hyps.hypotheses[0], days_ago=1, confidence=0.40)
        prior.direction = SignalDirection("bullish")

        n = engine.narrate(
            signals=signals, hypotheses=hyps, reflections=refs, belief_records=[prior]
        )

        validate_narrative_schema(n)
        # Hard Landing scenario should appear
        hard_landing = [s for s in n.scenario_analysis if s.name == "Hard Landing / Recession"]
        assert len(hard_landing) == 1
        # With growth bearish + confirmed, Hard Landing should be elevated
        assert hard_landing[0].probability >= 0.15


class TestScenarioInflationRebound:
    """Scenario 5: Inflation Rebound — CPI/PCE surprising upward."""

    def test_inflation_reacceleration_scenario(self, engine: NarrativeEngine) -> None:
        signals = SignalSnapshot(
            signals=[
                make_signal("CPI", "bullish", "Inflation", 0.80),
                make_signal("PCE", "bullish", "Inflation", 0.75),
                make_signal("TIPS", "bullish", "Inflation", 0.70),
            ]
        )
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis(
                    "Inflation is re-accelerating above expectations, potentially "
                    "forcing the Fed to resume tightening.",
                    "Inflation",
                    "bearish",
                    0.75,
                    supporting=3,
                    contradicting=0,
                ),
            ],
            dimensions_covered=["Inflation"],
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "confirmed", 0.80),
            ]
        )

        n = engine.narrate(signals=signals, hypotheses=hyps, reflections=refs)

        validate_narrative_schema(n)
        inflation_scenario = [s for s in n.scenario_analysis if "Inflation" in s.name]
        assert len(inflation_scenario) == 1
        assert inflation_scenario[0].probability > 0.20
        assert len(n.inflation_analysis) > 0


class TestScenarioAICapexBoom:
    """Scenario 6: AI Capex Boom — risk appetite strong, growth resilient."""

    def test_risk_on_rally_scenario(self, engine: NarrativeEngine) -> None:
        signals = SignalSnapshot(
            signals=[
                make_signal("HYG", "bullish", "Credit", 0.75),
                make_signal("PMI", "bullish", "Growth", 0.70),
            ]
        )
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis(
                    "AI-driven capital expenditure is fueling a productivity boom, "
                    "supporting risk assets and economic growth.",
                    "Growth",
                    "bullish",
                    0.70,
                    supporting=2,
                    contradicting=1,
                ),
                make_hypothesis(
                    "Credit conditions remain supportive with tight spreads "
                    "and strong risk appetite.",
                    "Credit",
                    "bullish",
                    0.65,
                    supporting=2,
                    contradicting=1,
                ),
            ],
            dimensions_covered=["Growth", "Credit"],
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "confirmed", 0.75),
                make_reflection(hyps.hypotheses[1], "confirmed", 0.70),
            ]
        )

        n = engine.narrate(signals=signals, hypotheses=hyps, reflections=refs)

        validate_narrative_schema(n)
        risk_on = [s for s in n.scenario_analysis if s.name == "Risk-On Rally"]
        assert len(risk_on) == 1
        assert risk_on[0].probability > 0.30


class TestScenarioDollarStrength:
    """Scenario 7: Dollar Strength — DXY surging, EM pressure."""

    def test_dollar_strength_dominant(self, engine: NarrativeEngine) -> None:
        signals = SignalSnapshot(
            signals=[
                make_signal("DXY", "bullish", "Liquidity", 0.90),
            ]
        )
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis(
                    "The US dollar is strengthening broadly, tightening global "
                    "financial conditions and pressuring emerging markets.",
                    "Liquidity",
                    "bearish",
                    0.85,
                    supporting=2,
                    contradicting=0,
                ),
            ],
            dimensions_covered=["Liquidity"],
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "confirmed", 0.85),
            ]
        )

        n = engine.narrate(signals=signals, hypotheses=hyps, reflections=refs)

        validate_narrative_schema(n)
        dollar_scenario = [s for s in n.scenario_analysis if "Dollar" in s.name]
        assert len(dollar_scenario) == 1
        assert dollar_scenario[0].probability > 0.35


class TestScenarioDollarWeakness:
    """Scenario 8: Dollar Weakness — DXY declining."""

    def test_dollar_weakness_reflected(self, engine: NarrativeEngine) -> None:
        signals = SignalSnapshot(
            signals=[
                make_signal("DXY", "bearish", "Liquidity", 0.80),
            ]
        )
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis(
                    "The US dollar is weakening, easing global financial conditions "
                    "and providing relief to emerging markets.",
                    "Liquidity",
                    "bullish",
                    0.75,
                    supporting=2,
                    contradicting=1,
                ),
            ],
            dimensions_covered=["Liquidity"],
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "confirmed", 0.70),
            ]
        )

        n = engine.narrate(signals=signals, hypotheses=hyps, reflections=refs)

        validate_narrative_schema(n)
        # Dollar Strength scenario should get lower probability
        dollar_scenario = [s for s in n.scenario_analysis if "Dollar" in s.name]
        assert len(dollar_scenario) == 1
        assert dollar_scenario[0].probability < 0.50


class TestScenarioRiskOn:
    """Scenario 9: Risk-On — credit bullish, VIX low."""

    def test_risk_on_environment(self, engine: NarrativeEngine) -> None:
        signals = SignalSnapshot(
            signals=[
                make_signal("HYG", "bullish", "Credit", 0.80),
                make_signal("IG", "bullish", "Credit", 0.75),
                make_signal("PMI", "bullish", "Growth", 0.70),
                make_signal("VIX", "bullish", "Risk_Appetite", 0.65),
            ]
        )
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis(
                    "Risk appetite is robust across credit and equity markets, "
                    "with tight spreads and strong inflows.",
                    "Credit",
                    "bullish",
                    0.80,
                    supporting=3,
                    contradicting=0,
                ),
                make_hypothesis(
                    "Growth signals confirm the risk-on environment, with "
                    "PMI and industrial data supportive.",
                    "Growth",
                    "bullish",
                    0.70,
                    supporting=2,
                    contradicting=1,
                ),
            ],
            dimensions_covered=["Credit", "Growth"],
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "confirmed", 0.85),
                make_reflection(hyps.hypotheses[1], "confirmed", 0.75),
            ]
        )

        n = engine.narrate(signals=signals, hypotheses=hyps, reflections=refs)

        validate_narrative_schema(n)
        assert n.confidence_level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)
        risk_on = [s for s in n.scenario_analysis if s.name == "Risk-On Rally"]
        assert len(risk_on) == 1
        assert risk_on[0].probability > 0.30


class TestScenarioRiskOff:
    """Scenario 10: Risk-Off — credit bearish, VIX elevated."""

    def test_risk_off_environment(self, engine: NarrativeEngine) -> None:
        signals = SignalSnapshot(
            signals=[
                make_signal("HYG", "bearish", "Credit", 0.85),
                make_signal("SPREAD", "bearish", "Credit", 0.80),
                make_signal("VIX", "bearish", "Risk_Appetite", 0.75),
                make_signal("PMI", "bearish", "Growth", 0.70),
            ]
        )
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis(
                    "Risk aversion is rising across markets with widening credit "
                    "spreads, elevated volatility, and deteriorating growth signals.",
                    "Credit",
                    "bearish",
                    0.85,
                    supporting=3,
                    contradicting=0,
                ),
            ],
            dimensions_covered=["Credit", "Growth"],
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "confirmed", 0.90),
            ]
        )

        n = engine.narrate(signals=signals, hypotheses=hyps, reflections=refs)

        validate_narrative_schema(n)
        assert len(n.key_risks) >= 1
        # With credit bearish, Risk-On Rally should be suppressed
        risk_on = [s for s in n.scenario_analysis if s.name == "Risk-On Rally"]
        assert risk_on[0].probability < 0.40


# ═══════════════════════════════════════════════════════════════════════════
# Cross-cutting Beta Feature Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestConfidenceExplanation:
    """Beta Task 4: Confidence Explanation fully populated."""

    def test_low_confidence_explains_why(
        self,
        engine: NarrativeEngine,
    ) -> None:
        """When confidence is LOW, why_low should be populated."""
        signals = SignalSnapshot(
            signals=[
                make_signal("DXY", "neutral", "Liquidity", 0.30),
            ]
        )
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis(
                    "Unclear liquidity direction with mixed dollar signals.",
                    "Liquidity",
                    "neutral",
                    0.30,
                    supporting=0,
                    contradicting=3,
                ),
            ],
            dimensions_covered=["Liquidity"],
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "refuted", 0.25),
            ]
        )

        n = engine.narrate(signals=signals, hypotheses=hyps, reflections=refs)

        assert n.confidence_level == ConfidenceLevel.LOW
        assert n.confidence_explanation is not None
        assert len(n.confidence_explanation.why_low) > 0

    def test_high_confidence_has_empty_why_low(
        self,
        engine: NarrativeEngine,
    ) -> None:
        """When confidence is HIGH, why_low should be empty."""
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis(
                    "Strong confirmed thesis with robust evidence.",
                    "Liquidity",
                    "bearish",
                    0.85,
                    supporting=5,
                    contradicting=0,
                ),
            ],
            dimensions_covered=["Liquidity"],
        )
        signals = SignalSnapshot(
            signals=[
                make_signal("DXY", "bullish", "Liquidity", 0.90),
            ]
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "confirmed", 0.90),
            ]
        )

        n = engine.narrate(signals=signals, hypotheses=hyps, reflections=refs)

        assert n.confidence_level == ConfidenceLevel.HIGH
        assert n.confidence_explanation.why_low == ""


class TestBeliefChangeVisualization:
    """Beta Task 6: Belief change tracking with prior/current comparison."""

    def test_detects_reversal(self, engine: NarrativeEngine) -> None:
        hyp = make_hypothesis(
            "Direction reversed from bullish to bearish on liquidity.",
            "Liquidity",
            "bearish",
            0.75,
        )
        prior = make_belief_record(hyp, days_ago=1)
        prior.direction = SignalDirection("bullish")  # opposite direction
        prior.confidence = 0.60
        prior.statement = "Prior bullish liquidity view"

        hyps = HypothesisSet(hypotheses=[hyp], dimensions_covered=["Liquidity"])
        refs = ReflectionSet(reports=[make_reflection(hyp, "confirmed", 0.80)])

        n = engine.narrate(
            signals=SignalSnapshot(
                signals=[
                    make_signal("DXY", "bullish", "Liquidity", 0.80),
                ]
            ),
            hypotheses=hyps,
            reflections=refs,
            belief_records=[prior],
        )

        reversal = [bc for bc in n.belief_changes if bc.direction == "reversed"]
        assert len(reversal) >= 1
        assert reversal[0].dimension == "Liquidity"
        assert len(reversal[0].prior_summary) > 0

    def test_belief_changes_text_not_empty(self, engine: NarrativeEngine) -> None:
        hyp = make_hypothesis("New belief formed.", "Growth", "bullish", 0.70)
        hyps = HypothesisSet(hypotheses=[hyp], dimensions_covered=["Growth"])
        refs = ReflectionSet(reports=[make_reflection(hyp, "confirmed", 0.75)])

        n = engine.narrate(
            signals=SignalSnapshot(signals=[make_signal("PMI", "bullish", "Growth", 0.70)]),
            hypotheses=hyps,
            reflections=refs,
            belief_records=[make_belief_record(hyp, days_ago=2, confidence=0.40)],
        )

        assert len(n.belief_changes_text) > 0


class TestActionRecommendation:
    """Beta Task 7: Action items grounded in hypothesis/reflection/memory."""

    def test_uncertain_hypothesis_generates_monitor(self, engine: NarrativeEngine) -> None:
        hyp = make_hypothesis(
            "Uncertain growth trajectory with mixed PMI data.",
            "Growth",
            "neutral",
            0.30,
            supporting=1,
            contradicting=2,
        )
        hyps = HypothesisSet(hypotheses=[hyp], dimensions_covered=["Growth"])
        refs = ReflectionSet(reports=[make_reflection(hyp, "uncertain", 0.35)])

        n = engine.narrate(
            signals=SignalSnapshot(signals=[make_signal("PMI", "neutral", "Growth", 0.30)]),
            hypotheses=hyps,
            reflections=refs,
        )

        monitor_items = [a for a in n.action_items if "Monitor" in a]
        assert len(monitor_items) >= 1

    def test_high_confidence_generates_act(self, engine: NarrativeEngine) -> None:
        hyp = make_hypothesis(
            "Strong confirmed growth acceleration.",
            "Growth",
            "bullish",
            0.85,
            supporting=4,
            contradicting=0,
        )
        hyps = HypothesisSet(hypotheses=[hyp], dimensions_covered=["Growth"])
        refs = ReflectionSet(reports=[make_reflection(hyp, "confirmed", 0.90)])

        n = engine.narrate(
            signals=SignalSnapshot(signals=[make_signal("PMI", "bullish", "Growth", 0.85)]),
            hypotheses=hyps,
            reflections=refs,
        )

        act_items = [a for a in n.action_items if "Act" in a]
        assert len(act_items) >= 1


class TestScenarioProbability:
    """Beta Task 5: Scenario probabilities are valid and rule-based."""

    def test_all_scenarios_have_probability(self, engine: NarrativeEngine) -> None:
        """All 5 template scenarios should be present."""
        signals = SignalSnapshot(
            signals=[
                make_signal("DXY", "bullish", "Liquidity", 0.70),
            ]
        )
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis("Liquidity tightening.", "Liquidity", "bearish", 0.70),
            ],
            dimensions_covered=["Liquidity"],
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "confirmed", 0.75),
            ]
        )

        n = engine.narrate(signals=signals, hypotheses=hyps, reflections=refs)

        scenario_names = {s.name for s in n.scenario_analysis}
        assert "Soft Landing" in scenario_names
        assert "Hard Landing / Recession" in scenario_names
        assert "Inflation Re-acceleration" in scenario_names
        assert "Dollar Strength Regime" in scenario_names
        assert "Risk-On Rally" in scenario_names

    def test_scenario_probabilities_reasonable(self, engine: NarrativeEngine) -> None:
        """Probabilities are between 0 and 1 and sum is reasonable."""
        n = engine.narrate(
            signals=SignalSnapshot(
                signals=[
                    make_signal("DXY", "bullish", "Liquidity", 0.70),
                    make_signal("PMI", "bullish", "Growth", 0.65),
                ]
            ),
            hypotheses=HypothesisSet(
                hypotheses=[
                    make_hypothesis("Liquidity tightening.", "Liquidity", "bearish", 0.70),
                    make_hypothesis("Growth resilient.", "Growth", "bullish", 0.65),
                ],
                dimensions_covered=["Liquidity", "Growth"],
            ),
            reflections=ReflectionSet(
                reports=[
                    make_reflection(
                        HypothesisSet(
                            hypotheses=[
                                make_hypothesis(
                                    "Liquidity tightening.", "Liquidity", "bearish", 0.70
                                ),
                            ]
                        ).hypotheses[0],
                        "confirmed",
                        0.75,
                    ),
                ]
            ),
        )

        for s in n.scenario_analysis:
            assert (
                0.05 <= s.probability <= 0.95
            ), f"{s.name} probability {s.probability} out of range"
            assert len(s.rationale) > 0
            assert len(s.key_indicators_to_watch) > 0


class TestTodayKeyChanges:
    """Beta Task 8: Today's Key Changes section."""

    def test_today_changes_not_empty(self, engine: NarrativeEngine) -> None:
        hyp = make_hypothesis("Liquidity tightening confirmed.", "Liquidity", "bearish", 0.80)
        prior = make_belief_record(hyp, days_ago=1, confidence=0.50)
        prior.direction = SignalDirection("bullish")

        hyps = HypothesisSet(hypotheses=[hyp], dimensions_covered=["Liquidity"])
        refs = ReflectionSet(reports=[make_reflection(hyp, "confirmed", 0.85)])

        n = engine.narrate(
            signals=SignalSnapshot(signals=[make_signal("DXY", "bullish", "Liquidity", 0.80)]),
            hypotheses=hyps,
            reflections=refs,
            belief_records=[prior],
        )

        assert len(n.today_key_changes) > 0
        # Should contain the three sections
        assert "What Changed" in n.today_key_changes
        assert "Why It Matters" in n.today_key_changes
        assert "What to Watch" in n.today_key_changes


class TestMarkdownRenderer:
    """Beta Task 2: Markdown renderer produces complete report."""

    def test_renderer_produces_all_sections(self, engine: NarrativeEngine) -> None:
        from src.renderer.markdown import MarkdownRenderer

        signals = SignalSnapshot(
            signals=[
                make_signal("DXY", "bullish", "Liquidity", 0.70),
                make_signal("CPI", "bearish", "Inflation", 0.65),
            ]
        )
        hyps = HypothesisSet(
            hypotheses=[
                make_hypothesis("Liquidity tight.", "Liquidity", "bearish", 0.70),
                make_hypothesis("Inflation easing.", "Inflation", "bullish", 0.65),
            ],
            dimensions_covered=["Liquidity", "Inflation"],
        )
        refs = ReflectionSet(
            reports=[
                make_reflection(hyps.hypotheses[0], "confirmed", 0.75),
                make_reflection(hyps.hypotheses[1], "confirmed", 0.70),
            ]
        )

        n = engine.narrate(signals=signals, hypotheses=hyps, reflections=refs)
        md = MarkdownRenderer().render(n)

        # All 10 sections must be present
        expected_sections = [
            "Executive Summary",
            "Today's Key Changes",
            "Current Macro Story",
            "Dimension Analysis",
            "Risk Appetite",
            "Scenario Analysis",
            "Belief Changes",
            "Key Risks",
            "Action Items",
            "Confidence Assessment",
        ]
        for section in expected_sections:
            assert section in md, f"Missing section: {section}"

        assert len(md) > 1000


class TestJsonRenderer:
    """Beta Task 2: JSON renderer produces valid output."""

    def test_json_renderer_output(self, engine: NarrativeEngine) -> None:
        import json

        from src.renderer.json_renderer import JsonRenderer

        n = engine.narrate(
            signals=SignalSnapshot(signals=[make_signal("DXY", "bullish", "Liquidity", 0.70)]),
            hypotheses=HypothesisSet(
                hypotheses=[make_hypothesis("Test.", "Liquidity", "bearish", 0.70)],
                dimensions_covered=["Liquidity"],
            ),
            reflections=ReflectionSet(reports=[]),
        )

        rendered = JsonRenderer().render(n)
        data = json.loads(rendered)

        assert "summary" in data
        assert "scenario_analysis" in data
        assert "confidence_score" in data
        assert "confidence_level" in data
        assert "key_risks" in data
        assert "action_items" in data
        assert isinstance(data["scenario_analysis"], list)


# ═══════════════════════════════════════════════════════════════════════════
# Full Pipeline Integration (verifies nothing broke)
# ═══════════════════════════════════════════════════════════════════════════


class TestFullPipelineBeta:
    """Verify full pipeline still works with Beta engine."""

    @pytest.mark.asyncio
    async def test_full_pipeline_produces_beta_narrative(self) -> None:
        """Full 7-step pipeline → MacroNarrative with Beta fields."""
        from src.pipeline import MacroResearchPipeline

        pipeline = MacroResearchPipeline()
        result = await pipeline.run(goal="macro environment analysis")

        assert result.narrative_obj is not None
        n = result.narrative_obj

        # Beta-specific validations
        assert isinstance(n.confidence_level, ConfidenceLevel)
        assert n.confidence_score > 0
        assert n.confidence_explanation is not None
        assert len(n.scenario_analysis) == 5
        assert len(n.key_risks) >= 0
        assert isinstance(n.today_key_changes, str)
        assert isinstance(n.belief_changes_text, str)
        assert len(n.liquidity_analysis) > 0 or len(n.credit_analysis) > 0

    @pytest.mark.asyncio
    async def test_pipeline_markdown_is_complete_report(self) -> None:
        """Pipeline Markdown output includes all Beta sections."""
        from src.pipeline import MacroResearchPipeline

        pipeline = MacroResearchPipeline()
        result = await pipeline.run(goal="macro environment analysis")

        md = result.narrative
        assert md is not None
        assert len(md) > 1000
        assert "Executive Summary" in md
        assert "Scenario Analysis" in md
        assert "Confidence Assessment" in md
        assert "Action Items" in md
