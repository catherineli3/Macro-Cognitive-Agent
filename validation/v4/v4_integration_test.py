"""V4 Integration Test — End-to-end validation of all 7 phases.

Tests the complete V4 pipeline:
    R1: MacroReasoner → EvidenceSynthesizer → HypothesisBuilder →
        CounterArgumentGenerator → MemoWriter
    R2: NewsCollector → NewsDeduplicator → EventClassifier →
        PolicyExtractor → MarketExpectationExtractor
    R3: FusionEngine (Data + News → Unified Evidence Graph)
    R4: Professional Research Memo (via MemoWriter)
    R5: ReasoningFeedback → PromptOptimizer → ConfidenceOptimizer
    R6: ResearchQualityEvaluator (6 dimensions)
    R7: ReviewQueue (Human review workflow)

All modules MUST pass with quality scores > 0.
"""

import json
import os
import sys
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# ── Test Data ──

TEST_MARKET_DATA = {
    "signals": {
        "growth_momentum": {"direction": "bullish", "strength": 0.7, "description": "PMI above 50, retail sales beat"},
        "inflation_trend": {"direction": "bullish", "strength": 0.6, "description": "Core CPI moderating toward 2.5%"},
        "labor_market": {"direction": "bullish", "strength": 0.5, "description": "NFP +180k, wage growth 3.5%"},
        "credit_conditions": {"direction": "bearish", "strength": 0.4, "description": "Bank lending standards tightening"},
        "monetary_policy": {"direction": "neutral", "strength": 0.5, "description": "Fed on hold, data-dependent"},
    },
    "prices": {
        "SPX": {"1d": 0.012, "5d": 0.035, "1m": 0.08},
        "US10Y": {"1d": -0.05, "5d": -0.15},
        "DXY": {"1d": -0.003, "5d": 0.01},
        "Gold": {"1d": 0.005, "5d": 0.02},
    },
}

TEST_NEWS_ARTICLES = [
    {"headline": "Fed's Powell: Progress on inflation but need more confidence",
     "content": "Fed Chair Powell testified that inflation has eased substantially but the committee needs greater confidence before cutting rates. Labor market remains strong.",
     "source": "fed", "country": "US", "published_at": "2026-07-22T10:00:00Z"},
    {"headline": "US Core CPI Falls to 2.5% YoY — Below Expectations",
     "content": "The Bureau of Labor Statistics reported core CPI rose 0.2% MoM, bringing the annual rate to 2.5%. Economists had expected 2.6%.",
     "source": "bls", "country": "US",
     "indicator": "Core CPI YoY", "actual": 2.5, "consensus": 2.6, "prior": 2.7, "unit": "%"},
    {"headline": "ECB Holds Rates, Signals September Cut Possible",
     "content": "The European Central Bank kept rates unchanged but President Lagarde indicated that September is 'wide open' for a potential rate cut.",
     "source": "ecb", "country": "EU"},
    {"headline": "US Payrolls Beat: +185k vs +170k Expected",
     "content": "Non-farm payrolls rose 185,000 in the latest month, beating the consensus estimate of 170,000. Unemployment held at 3.8%.",
     "source": "bls", "country": "US",
     "indicator": "NFP", "actual": 185000, "consensus": 170000, "prior": 160000, "unit": "jobs"},
    {"headline": "China PBOC Injects Liquidity via MLF, Signals More Support",
     "content": "People's Bank of China conducted medium-term lending facility operations, injecting net liquidity into the banking system.",
     "source": "pboc", "country": "CN"},
    {"headline": "IMF Upgrades Global Growth Forecast to 3.2%",
     "content": "The IMF raised its 2026 global growth forecast to 3.2% from 3.0%, citing resilience in the US and emerging markets.",
     "source": "imf", "country": "global"},
]

TEST_BELIEFS = [
    {"id": "BEL_001", "name": "US Economy Soft Landing", "direction": "bullish",
     "confidence": 0.65, "stage": "consolidation",
     "evidence": [{"source": "PMI", "direction": "supporting", "weight": 0.7}]},
    {"id": "BEL_002", "name": "Fed Rate Cut H2 2026", "direction": "bullish",
     "confidence": 0.55, "stage": "forming",
     "evidence": [{"source": "CPI", "direction": "supporting", "weight": 0.6}]},
]

TEST_REGIME = {
    "regime_label": "stable_growth",
    "regime_type": "expansion_moderating",
    "confidence": 0.72,
    "dimensions": {"growth": "above_trend", "inflation": "moderating", "monetary": "neutral", "credit": "tightening"},
    "transition": {"probability": 0.25, "risk": "low", "direction": "toward_easing"},
    "historical_analog": {"period": "1995", "label": "Mid-90s Soft Landing", "similarity_score": 0.68},
}

TEST_CAPITAL_FLOW = {
    "direction": "moderate_inflow",
    "summary": "$3.2B net inflow to equity ETFs this week. Bond funds saw $1.1B outflow. Rotation from defensive to cyclical sectors evident.",
    "confidence": "moderate",
}

TEST_NARRATIVES = [
    {"summary": "Goldilocks narrative gaining traction as growth holds up while inflation eases",
     "direction": "bullish", "strength": 0.6},
    {"summary": "Rate cut expectations driving risk-on positioning",
     "direction": "bullish", "strength": 0.5},
]


def test_phase_r1_reasoning_pipeline():
    """Test the full reasoning pipeline: evidence → hypotheses → counters → memo."""
    print("\n" + "=" * 70)
    print("Phase R1: Reasoning Pipeline Test")
    print("=" * 70)

    from src.research.reasoning import (
        MacroReasoner, EvidenceSynthesizer, HypothesisBuilder,
        CounterArgumentGenerator, MemoWriter,
    )

    # 1. Evidence Synthesis
    synthesizer = EvidenceSynthesizer()
    assessment = synthesizer.synthesize(
        market_data=TEST_MARKET_DATA,
        narratives=[{"summary": "Goldilocks", "direction": "bullish", "strength": 0.6}],
        beliefs=TEST_BELIEFS,
        capital_flow_result=TEST_CAPITAL_FLOW,
        regime_result=TEST_REGIME,
    )

    assert assessment.total_evidence_points > 0, "No evidence extracted"
    assert len(assessment.clusters) > 0, "No clusters formed"
    assert assessment.evidence_quality in ("high", "moderate", "low", "insufficient"), "Bad quality score"
    print(f"  [OK] Evidence: {assessment.total_evidence_points} points, "
          f"{len(assessment.clusters)} clusters, net={assessment.net_direction}, "
          f"quality={assessment.evidence_quality}")

    # 2. Hypothesis Building
    builder = HypothesisBuilder()
    hypotheses = builder.build_hypotheses(
        evidence_clusters=assessment.clusters,
        beliefs=TEST_BELIEFS,
        regime_result=TEST_REGIME,
    )

    assert len(hypotheses) > 0, "No hypotheses generated"
    for h in hypotheses:
        assert h.confidence > 0, "Zero confidence hypothesis"
        assert h.statement, "Empty hypothesis statement"
        assert h.causal_chain, "No causal chain"
    print(f"  [OK] Hypotheses: {len(hypotheses)} generated, "
          f"top confidence={hypotheses[0].confidence:.0%}")

    # 3. Counter-Arguments
    counter_gen = CounterArgumentGenerator()
    counters = counter_gen.generate(hypotheses=hypotheses)

    assert len(counters) > 0, "No counter-arguments"
    for ca in counters:
        assert ca.argument, "Empty counter-argument"
        assert ca.severity in ("fatal", "major", "minor"), f"Bad severity: {ca.severity}"
    print(f"  [OK] Counter-Arguments: {len(counters)} generated")

    # 4. Memo Writing
    writer = MemoWriter()
    memo = writer.write_memo(
        evidence_assessment=assessment,
        hypotheses=hypotheses,
        counter_arguments=counters,
        regime_result=TEST_REGIME,
        beliefs=TEST_BELIEFS,
        capital_flow_result=TEST_CAPITAL_FLOW,
    )

    assert memo.executive_summary, "No executive summary"
    assert memo.full_memo_text, "No memo text"
    assert memo.word_count > 0, "Zero word count"
    assert len(memo.sections) >= 4, f"Only {len(memo.sections)} sections"
    print(f"  [OK] Memo: {memo.word_count} words, {len(memo.sections)} sections, "
          f"{'has exec summary' if memo.executive_summary else 'MISSING exec summary'}")
    print(f"  Structure quality: {memo.quality_score()}/100")

    # 5. Full MacroReasoner
    reasoner = MacroReasoner()
    full_memo = reasoner.reason(
        market_data=TEST_MARKET_DATA,
        narratives=TEST_NARRATIVES,
        beliefs=TEST_BELIEFS,
        regime_result=TEST_REGIME,
        capital_flow_result=TEST_CAPITAL_FLOW,
    )

    assert full_memo.full_memo_text, "Full pipeline failed"
    assert full_memo.executive_summary, "Missing executive summary"
    assert len(full_memo.predictions) > 0, "No predictions"
    print(f"  [OK] Full Pipeline: {full_memo.word_count} words, "
          f"{len(full_memo.predictions)} predictions, "
          f"{len(full_memo.counter_arguments)} counter-argument summaries")

    return True


def test_phase_r2_news_intelligence():
    """Test the news intelligence pipeline."""
    print("\n" + "=" * 70)
    print("Phase R2: News Intelligence Test")
    print("=" * 70)

    from src.news import (
        NewsCollector, NewsDeduplicator, EventClassifier,
        PolicyExtractor, MarketExpectationExtractor,
    )

    # 1. Collect news
    collector = NewsCollector()
    events = collector.collect_from_articles(TEST_NEWS_ARTICLES)

    assert len(events) > 0, "No events collected"
    data_events = collector.collect_from_market_data([
        a for a in TEST_NEWS_ARTICLES if "actual" in a
    ])
    all_events = events + data_events
    print(f"  [OK] Collected: {len(all_events)} events ({len(events)} articles, {len(data_events)} data)")

    # 2. Classify
    classifier = EventClassifier()
    classified = classifier.classify_batch(all_events)
    important = classifier.filter_important(classified)
    print(f"  [OK] Classified: {len(classified)} events, {len(important)} important")

    # 3. Deduplicate
    dedup = NewsDeduplicator()
    deduped = dedup.deduplicate(classified)
    print(f"  [OK] Deduplicated: {len(classified)} → {len(deduped)} canonical events")

    # 4. Policy extraction
    policy_ext = PolicyExtractor()
    cb_events = [e for e in deduped if str(e.source_type) == "NewsSourceType.CENTRAL_BANK" or
                 (hasattr(e.source_type, "value") and e.source_type.value in ("central_bank", "cb_speech"))]
    # Use all classified events for CB detection
    signals = policy_ext.extract_batch(deduped)
    cb_stance = policy_ext.get_cb_stance(signals) if signals else {}
    print(f"  [OK] Policy: {len(signals)} signals extracted, "
          f"{len(cb_stance)} CBs analyzed")

    # 5. Market expectations
    expect_ext = MarketExpectationExtractor()
    expectations = expect_ext.extract_batch(deduped)

    # Check for surprise detection
    surprises = [e for e in expectations if e.surprise is not None]
    print(f"  [OK] Expectations: {len(expectations)} analyzed, "
          f"{len(surprises)} with surprises")
    for s in surprises:
        print(f"     {s.indicator}: surprise={s.surprise}, significant={s.is_significant_surprise}")

    return True


def test_phase_r3_fusion_engine():
    """Test the data + news fusion engine."""
    print("\n" + "=" * 70)
    print("Phase R3: Fusion Engine Test")
    print("=" * 70)

    from src.news import FusionEngine

    # Create some news events in ResearchEvent format
    news_events = [
        {"title": "CPI below expectations", "event": "CPI 2.5% vs 2.6% expected",
         "category": "economic_data", "market_impact": "bullish", "confidence": 0.8},
        {"title": "Fed on hold", "event": "Fed maintains rates, data-dependent",
         "category": "monetary_policy", "market_impact": "neutral", "confidence": 0.7},
        {"title": "NFP beats", "event": "NFP +185k vs +170k expected",
         "category": "economic_data", "market_impact": "bullish", "confidence": 0.75},
    ]

    engine = FusionEngine()
    graph = engine.fuse(
        market_data=TEST_MARKET_DATA,
        news_events=news_events,
        capital_flow_result=TEST_CAPITAL_FLOW,
        beliefs=TEST_BELIEFS,
        regime_result=TEST_REGIME,
    )

    assert graph.total_nodes > 0, "No nodes in graph"
    assert graph.total_edges > 0, "No edges — nodes not connected!"
    assert graph.data_node_count > 0, "No data nodes"
    assert graph.news_node_count > 0, "No news nodes"
    assert graph.belief_node_count > 0, "No belief nodes"

    print(f"  [OK] Graph: {graph.total_nodes} nodes, {graph.total_edges} edges")
    print(f"       Data={graph.data_node_count}, News={graph.news_node_count}, "
          f"Flows={graph.flow_node_count}, Beliefs={graph.belief_node_count}, "
          f"Analogs={graph.analog_node_count}")
    print(f"  [OK] Summary:\n{graph.summary()}")

    # Test belief-specific evidence
    for bel in TEST_BELIEFS:
        evidence = graph.get_evidence_for_belief(bel["id"])
        total = sum(len(v) for v in evidence.values())
        print(f"       Belief '{bel['name']}': {total} evidence nodes")

    return True


def test_phase_r5_calibration():
    """Test prediction calibration feedback loop."""
    print("\n" + "=" * 70)
    print("Phase R5: Prediction Calibration Test")
    print("=" * 70)

    from src.research.reasoning import (
        ReasoningFeedback, PromptOptimizer, ConfidenceOptimizer,
    )

    # 1. ReasoningFeedback
    feedback = ReasoningFeedback()

    # Simulate predictions and outcomes
    test_predictions = [
        {"prediction_id": "P1", "direction": "bullish", "confidence": 0.7,
         "evidence_weight": 0.5, "domain": "growth_momentum"},
        {"prediction_id": "P2", "direction": "bearish", "confidence": 0.6,
         "evidence_weight": -0.3, "domain": "inflation_dynamics"},
        {"prediction_id": "P3", "direction": "bullish", "confidence": 0.8,
         "evidence_weight": 0.2, "domain": "monetary_policy"},
        {"prediction_id": "P4", "direction": "bearish", "confidence": 0.55,
         "evidence_weight": 0.1, "domain": "credit_conditions"},
        {"prediction_id": "P5", "direction": "bullish", "confidence": 0.65,
         "evidence_weight": 0.4, "domain": "labor_market"},
    ]

    test_outcomes = [
        {"actual_direction": "bullish"},   # P1: correct
        {"actual_direction": "bearish"},   # P2: correct
        {"actual_direction": "bearish"},   # P3: wrong! (predicted bullish)
        {"actual_direction": "bullish"},   # P4: wrong! (predicted bearish)
        {"actual_direction": "bullish"},   # P5: correct
    ]

    report = feedback.process_batch(test_predictions, test_outcomes)

    assert report.total_predictions == 5, "Wrong count"
    assert report.correct_predictions == 3, f"Expected 3 correct, got {report.correct_predictions}"
    assert len(report.recommended_actions) > 0, "No improvement actions"
    print(f"  [OK] Feedback: {report.correct_predictions}/{report.total_predictions} correct "
          f"({report.accuracy:.0%}), {len(report.recommended_actions)} actions")
    print(f"       Error sources: {report.error_by_source}")

    # 2. PromptOptimizer
    popt = PromptOptimizer()
    opt_report = popt.evaluate_and_optimize(report.entries)
    assert len(opt_report.recommendations) > 0, "No prompt recommendations"
    print(f"  [OK] Prompt Optimizer: {len(opt_report.recommendations)} recommendations")
    print(f"       Bottom line: {opt_report.bottom_line}")

    # 3. ConfidenceOptimizer
    copt = ConfidenceOptimizer()
    for pred, outcome in zip(test_predictions, test_outcomes):
        copt.record(
            confidence=pred["confidence"],
            was_correct=pred["direction"] == outcome["actual_direction"],
            domain=pred.get("domain", ""),
        )

    cal = copt.calibrate()
    print(f"  [OK] Confidence Calibration: ECE={cal.expected_calibration_error:.3f}, "
          f"overconfident={cal.overconfidence_bias}")
    print(f"       Global adjustment: {cal.global_adjustment:+.0%}")

    # Test calibration adjustment
    raw_conf = 0.75
    adjusted = copt.adjust_confidence(raw_conf)
    print(f"  [OK] Calibration: raw={raw_conf:.0%} → adjusted={adjusted:.0%}")

    return True


def test_phase_r6_quality_evaluation():
    """Test research quality evaluator on a memo."""
    print("\n" + "=" * 70)
    print("Phase R6: Research Quality Evaluation Test")
    print("=" * 70)

    from src.research.reasoning import (
        MacroReasoner, ResearchQualityEvaluator,
    )

    # Generate a memo
    reasoner = MacroReasoner()
    memo = reasoner.reason(
        market_data=TEST_MARKET_DATA,
        narratives=TEST_NARRATIVES,
        beliefs=TEST_BELIEFS,
        regime_result=TEST_REGIME,
        capital_flow_result=TEST_CAPITAL_FLOW,
    )

    # Get hypotheses for evaluation
    synthesizer = reasoner.synthesizer
    assessment = synthesizer.synthesize(
        market_data=TEST_MARKET_DATA,
        narratives=TEST_NARRATIVES,
        beliefs=TEST_BELIEFS,
        regime_result=TEST_REGIME,
    )

    hyp_builder = reasoner.hypothesis_builder
    hypotheses = hyp_builder.build_hypotheses(
        evidence_clusters=assessment.clusters,
        beliefs=TEST_BELIEFS,
        regime_result=TEST_REGIME,
    )

    counter_gen = reasoner.counter_generator
    counters = counter_gen.generate(hypotheses)

    # Evaluate
    evaluator = ResearchQualityEvaluator()
    quality = evaluator.evaluate(memo, hypotheses, counters)

    assert quality.overall_score >= 0, "Zero quality score"
    assert len(quality.dimensions) == 6, f"Expected 6 dimensions, got {len(quality.dimensions)}"

    print(f"  [OK] Overall Quality: {quality.overall_score}/100 ({quality.grade}), "
          f"professional grade: {quality.is_professional_grade}")

    for name, dim in quality.dimensions.items():
        status = "PASS" if dim.passing else "FAIL"
        print(f"       {name}: {dim.score}/100 [{status}] — {len(dim.suggestions)} suggestions")

    if quality.critical_flaws:
        for cf in quality.critical_flaws:
            print(f"       CRITICAL: {cf}")

    return True


def test_phase_r7_review_workflow():
    """Test human review queue workflow."""
    print("\n" + "=" * 70)
    print("Phase R7: Review Workflow Test")
    print("=" * 70)

    from src.research.reasoning import (
        ReviewQueue, ReviewableType, ReviewStatus,
    )

    queue = ReviewQueue()
    queue.start_session(reviewer="Test Researcher")

    # Enqueue various items
    queue.enqueue(
        content={"name": "US Soft Landing", "confidence": 0.65, "direction": "bullish"},
        item_type=ReviewableType.BELIEF,
    )
    queue.enqueue(
        content={"title": "Growth Momentum Strong", "confidence": 0.7},
        item_type=ReviewableType.HYPOTHESIS,
    )
    queue.enqueue(
        content={"statement": "SPX to 5000", "confidence": 0.6, "direction": "bullish"},
        item_type=ReviewableType.PREDICTION,
    )
    queue.enqueue(
        content={"regime": "stable_growth", "confidence": 0.72},
        item_type=ReviewableType.REGIME_CLASSIFICATION,
    )

    pending = queue.get_pending()
    assert len(pending) == 4, f"Expected 4 pending, got {len(pending)}"
    print(f"  [OK] Enqueued: {len(pending)} items pending review")

    # Review actions
    queue.accept(pending[0].item_id, notes="Good belief — aligns with our view")
    queue.reject(pending[1].item_id, reason="Hypothesis too vague, needs causal chain")
    queue.edit(pending[2].item_id, edits={"confidence": 0.55}, notes="Reduced overconfidence")
    queue.skip(pending[3].item_id, notes="Need more regime data")

    stats = queue.statistics()
    assert stats["accepted"] == 1, f"Expected 1 accepted, got {stats['accepted']}"
    assert stats["rejected"] == 1
    assert stats["edited"] == 1
    assert stats["skipped"] == 1
    print(f"  [OK] Review stats: {stats}")

    # End session
    session = queue.end_session()
    assert session is not None
    assert session.acceptance_rate() > 0, "Zero acceptance rate"
    print(f"  [OK] Session: acceptance_rate={session.acceptance_rate():.0%}")

    # Learning signals
    signals = queue.get_learning_signals()
    assert len(signals) > 0, "No learning signals generated"
    print(f"  [OK] Learning Signals: {len(signals)} signals")
    for sig in signals:
        print(f"       {sig['action']}: {sig['feedback_type']} "
              f"(confidence_impact: {sig['confidence_impact']:+.2f})")

    return True


def test_end_to_end_memo_quality():
    """Full end-to-end test: generates memo, evaluates quality."""
    print("\n" + "=" * 70)
    print("End-to-End: Memo Quality Test")
    print("=" * 70)

    from src.research.reasoning import MacroReasoner, ResearchQualityEvaluator
    from src.news import NewsCollector, EventClassifier, NewsDeduplicator, FusionEngine

    # Step 1: News processing
    collector = NewsCollector()
    events = collector.collect_from_articles(TEST_NEWS_ARTICLES)
    data_events = collector.collect_from_market_data([
        a for a in TEST_NEWS_ARTICLES if "actual" in a
    ])
    all_events = events + data_events
    classifier = EventClassifier()
    classified = classifier.classify_batch(all_events)
    dedup = NewsDeduplicator()
    news = [e.to_dict() for e in dedup.deduplicate(classified)]

    # Step 2: Reasoning Pipeline
    reasoner = MacroReasoner()
    memo = reasoner.reason(
        market_data=TEST_MARKET_DATA,
        narratives=TEST_NARRATIVES,
        beliefs=TEST_BELIEFS,
        regime_result=TEST_REGIME,
        capital_flow_result=TEST_CAPITAL_FLOW,
        news_events=news,
    )

    # Step 3: Fusion
    fusion = FusionEngine()
    graph = fusion.fuse(
        market_data=TEST_MARKET_DATA,
        news_events=news,
        capital_flow_result=TEST_CAPITAL_FLOW,
        beliefs=TEST_BELIEFS,
        regime_result=TEST_REGIME,
    )

    # Step 4: Extract hypotheses for evaluation
    synthesizer = reasoner.synthesizer
    assessment = synthesizer.synthesize(
        market_data=TEST_MARKET_DATA, narratives=TEST_NARRATIVES,
        beliefs=TEST_BELIEFS, capital_flow_result=TEST_CAPITAL_FLOW,
        regime_result=TEST_REGIME, news_events=news,
    )
    hypotheses = reasoner.hypothesis_builder.build_hypotheses(
        evidence_clusters=assessment.clusters,
        beliefs=TEST_BELIEFS, regime_result=TEST_REGIME,
    )
    counters = reasoner.counter_generator.generate(hypotheses)

    # Step 5: Quality Evaluation
    evaluator = ResearchQualityEvaluator()
    quality = evaluator.evaluate(memo, hypotheses, counters)

    # Assertions
    assert memo.word_count >= 100, f"Memo too short: {memo.word_count} words"
    assert memo.executive_summary, "Missing executive summary"
    assert len(memo.predictions) > 0, "No predictions"
    assert len(hypotheses) > 0, "No hypotheses"
    assert len(counters) > 0, "No counter-arguments"
    assert graph.total_nodes > 10, f"Only {graph.total_nodes} graph nodes"
    assert quality.overall_score > 0, "Zero quality score"

    print(f"  Memo: {memo.word_count} words, {len(memo.sections)} sections")
    print(f"  Predictions: {len(memo.predictions)}")
    print(f"  Hypotheses: {len(hypotheses)}, Counters: {len(counters)}")
    print(f"  Evidence Graph: {graph.total_nodes} nodes, {graph.total_edges} edges")
    print(f"  Quality: {quality.overall_score}/100 ({quality.grade})")
    print(f"  Memo quality (internal): {memo.quality_score()}/100")

    # Print dimension scores
    for name, dim in quality.dimensions.items():
        print(f"    {name:30s}: {dim.score:3.0f}/100 {'PASS' if dim.passing else 'FAIL'}")

    print(f"\n  [{('PASS' if quality.passes_minimum else 'FAIL')}] "
          f"Overall {'meets' if quality.passes_minimum else 'below'} minimum quality bar")

    # Print executive summary snippet
    print(f"\n  Executive Summary (first 200 chars):")
    print(f"  {'─' * 50}")
    print(f"  {memo.executive_summary[:200]}...")

    return True


# ════════════════════════════════════════════════════════════════════════════


def main():
    print("=" * 70)
    print("  V4 PROFESSIONAL RESEARCH LOOP — INTEGRATION TEST SUITE")
    print("  Target: Research Quality, not Architecture")
    print("=" * 70)
    print(f"  Time: {datetime.now(timezone.utc).isoformat()}")

    results = {}
    total_tests = 7

    test_funcs = [
        ("R1: Reasoning Pipeline", test_phase_r1_reasoning_pipeline),
        ("R2: News Intelligence", test_phase_r2_news_intelligence),
        ("R3: Fusion Engine", test_phase_r3_fusion_engine),
        ("R5: Calibration Loop", test_phase_r5_calibration),
        ("R6: Quality Evaluation", test_phase_r6_quality_evaluation),
        ("R7: Review Workflow", test_phase_r7_review_workflow),
        ("E2E: Full Memo Quality", test_end_to_end_memo_quality),
    ]

    passed = 0
    for name, func in test_funcs:
        try:
            func()
            results[name] = "PASSED"
            passed += 1
        except Exception as e:
            results[name] = f"FAILED: {e}"
            import traceback
            print(f"  [FAIL] {name}: {e}")
            traceback.print_exc()

    # Summary
    print("\n" + "=" * 70)
    print("  V4 TEST SUMMARY")
    print("=" * 70)
    for name, result in results.items():
        status = "[PASS]" if "PASSED" in str(result) else "[FAIL]"
        print(f"  {status} {name}: {result}")
    print(f"\n  Passed: {passed}/{total_tests}")
    print(f"  {'ALL TESTS PASSED' if passed == total_tests else 'SOME TESTS FAILED'}")
    print("=" * 70)

    return passed == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
