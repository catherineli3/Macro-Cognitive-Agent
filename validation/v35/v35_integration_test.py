"""V3.5 Integration test — runs the full daily pipeline."""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.agent import DailyMacroAgent


def test_full_pipeline():
    """Test the complete V3.5 daily pipeline."""
    print("=" * 60)
    print("V3.5 DailyMacroAgent — Full Pipeline Test")
    print("=" * 60)

    # Test market data
    market = {
        "vix": 19.5,
        "dxy": 105.3,
        "dxy_trend": 2.1,
        "cpi_yoy": 3.2,
        "yield_curve": -0.25,
        "hy_spread": 380,
        "ig_spread": 125,
        "fed_rate": 5.25,
        "rate_change_bps": 0,
        "spx_ytd": 12.5,
    }

    mental = {
        "growth": type("M", (), {"status": "stable"})(),
        "inflation": None,
        "liquidity": None,
        "credit": type("M", (), {"status": "peaking"})(),
    }

    # Create beliefs for test using actual schema fields
    from src.research.beliefs.schemas import ResearchBelief, BeliefDomain, BeliefStage
    beliefs = [
        ResearchBelief(
            id="b1", title="AI capex cycle remains strong",
            description="AI infrastructure investment continuing at high levels",
            domain=BeliefDomain.AI_CAPEX, confidence=0.75, evidence_count=4,
            stage=BeliefStage.CONSOLIDATION,

        ),
        ResearchBelief(
            id="b2", title="US dollar strength near peak",
            description="Dollar strength driven by rate differentials",
            domain=BeliefDomain.DOLLAR, confidence=0.55, evidence_count=2,
            stage=BeliefStage.HYPOTHESIS,
        ),
        ResearchBelief(
            id="b3", title="Credit cycle approaching peak",
            description="HY spreads widening from lows, loan standards tightening",
            domain=BeliefDomain.CREDIT, confidence=0.65, evidence_count=5,
            stage=BeliefStage.CONSOLIDATION,

        ),
        ResearchBelief(
            id="b4", title="Inflation disinflation trend intact",
            description="CPI trending lower but services sticky",
            domain=BeliefDomain.INFLATION, confidence=0.60, evidence_count=3,
            stage=BeliefStage.HYPOTHESIS,
        ),
        ResearchBelief(
            id="b5", title="Global liquidity tightening",
            description="Central bank balance sheets contracting, QT continuing",
            domain=BeliefDomain.LIQUIDITY, confidence=0.70, evidence_count=6,
            stage=BeliefStage.CONSOLIDATION,

        ),
    ]

    # Initialize agent
    agent = DailyMacroAgent(use_llm=False, verbosity=1)

    # Run daily
    report = agent.run_daily(
        date="2026-07-22",
        market_data=market,
        mental_models=mental,
        beliefs=beliefs,
    )

    # Summary
    print("\n" + "=" * 60)
    print(report.summary())
    print("=" * 60)

    # Assertions
    assert report.regime_classification is not None, "Regime must be classified"
    assert report.capital_flow_report is not None, "Capital flow must be reported"
    assert report.learning_report is not None, "Learning must run"
    assert report.curiosity_report is not None, "Curiosity must run"

    assert len(report.modules_executed) >= 4, f"Expected >=4 modules, got {len(report.modules_executed)}"
    assert len(report.modules_failed) == 0, f"Expected 0 failures, got {report.modules_failed}"

    print(f"\nModules executed: {report.modules_executed}")
    print(f"Modules failed: {report.modules_failed}")
    if report.errors:
        print(f"Errors: {report.errors}")
    print(f"Duration: {report.pipeline_duration_seconds:.1f}s")

    # Detail checks
    regime = report.regime_classification
    print(f"\nRegime details:")
    print(f"  Label: {regime.regime_label}")
    print(f"  Growth: {regime.growth_phase}")
    print(f"  Inflation: {regime.inflation_regime}")
    print(f"  Monetary: {regime.monetary_stance}")
    print(f"  Credit: {regime.credit_cycle}")
    print(f"  Dollar: {regime.dollar_regime}")
    print(f"  Volatility: {regime.volatility_regime}")
    print(f"  Transition prob: {regime.transition_probability}")
    print(f"  Transition dir: {regime.transition_direction}")
    print(f"  Historical: {regime.historical_period_label}")
    print(f"  Warnings: {regime.early_warning_signals}")

    if report.historical_analogs:
        print(f"\nTop historical analogs:")
        for a in report.historical_analogs[:3]:
            print(f"  {a.period_name} ({a.period_label}): similarity={a.similarity_score:.0%}")

    flow = report.capital_flow_report
    print(f"\nCapital Flow:")
    print(f"  Regime: {flow.regime.regime_label}")
    print(f"  Net flow: {flow.regime.net_flow_bn:+.1f}B")
    print(f"  Sentiment: {flow.cross_asset.risk_sentiment}")

    if report.curiosity_report:
        cur = report.curiosity_report
        print(f"\nCuriosity Top Questions:")
        for q in cur.priority_questions[:5]:
            print(f"  [{q.domain}] {q.question} (P:{q.priority:.0%})")

    if report.learning_report:
        lr = report.learning_report
        print(f"\nLearning:")
        print(f"  Resolved: {lr.predictions_resolved}")
        print(f"  Accuracy: {lr.overall_accuracy:.0%}")

    print("\n" + "=" * 60)
    print("ALL V3.5 INTEGRATION TESTS PASSED")
    print("=" * 60)

    return report


if __name__ == "__main__":
    test_full_pipeline()
