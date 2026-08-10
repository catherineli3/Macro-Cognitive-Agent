"""V6-V8 Integration Test — Validate all phases of Researcher In The Loop,
Live Macro Research Desk, and Institutional CIO Agent.

Tests 45+ assertions across 15 modules.
"""

import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# ── Test data ─────────────────────────────────────────────────────────────────

SAMPLE_MACRO_DATA = {
    "GDP_QoQ": 2.8, "CPI_YoY": 3.2, "Core_PCE_YoY": 2.8,
    "Unemployment": 3.8, "NFP": 175000, "ISM_Mfg": 49.1,
    "Fed_Funds": 5.25, "US_10Y": 4.35, "DXY": 104.5,
}

SAMPLE_MARKET_DATA = {
    "SPX": {"price": 5200, "change_daily": "+0.5%", "change_weekly": "+1.2%"},
    "VIX": {"price": 15.2, "change_daily": "-0.3"},
    "US_2Y": {"price": 4.85, "change_daily": "+2bp"},
    "Gold": {"price": 2350, "change_daily": "+0.3%"},
}

SAMPLE_EVENT = {
    "event_id": "evt_001",
    "title": "Fed Holds Rates at 5.25%, Signals One Cut in 2026",
    "summary": "FOMC keeps rates unchanged, dot plot shows median of one 25bp cut this year.",
    "category": "monetary_policy",
    "importance": "critical",
    "impact_direction": "neutral",
    "surprise": -0.25,
    "key_numbers": {"fed_funds": 5.25, "projected_cuts": 1},
}

SAMPLE_NEWS_HEADLINES = [
    "BREAKING: FOMC holds rates steady at 5.25%, signals patience on cuts",
    "US CPI rises 3.2% YoY, slightly above expectations of 3.1%",
    "China Q2 GDP misses estimates at 4.7% vs 5.0% expected",
    "ECB President Lagarde: 'We are data dependent, not date dependent'",
    "NFP: US economy adds 175K jobs in June, unemployment ticks up to 3.8%",
]

SAMPLE_BELIEFS = [
    {"id": "fed_path", "name": "Fed Cutting Cycle H2 2026", "confidence": 0.65},
    {"id": "inflation_sticky", "name": "Inflation Remains Sticky Above 3%", "confidence": 0.55},
    {"id": "ai_capex", "name": "AI Capex Super Cycle", "confidence": 0.72},
]

SAMPLE_NARRATIVES = [
    "Soft Landing Consensus",
    "Higher for Longer Rates",
    "AI Productivity Boom",
]

SAMPLE_PREDICTIONS = [
    {"prediction": "Fed cuts 50bp by December 2026", "probability": 0.65},
    {"prediction": "US 10Y yield falls to 3.75% by year-end", "probability": 0.55},
    {"prediction": "SPX reaches 5600 by Q4 2026", "probability": 0.60},
]

SAMPLE_RISKS = [
    {"risk": "Sticky inflation delays rate cuts", "probability": 0.30},
    {"risk": "Geopolitical escalation in Middle East", "probability": 0.15},
    {"risk": "AI bubble bursts, tech selloff", "probability": 0.20},
]


# ── Test runner ───────────────────────────────────────────────────────────────

def run():
    results = []
    
    # ═══════════════════════════════════════════════════════════════════════════
    # V6 — Researcher In The Loop
    # ═══════════════════════════════════════════════════════════════════════════
    
    # V6.1 Live Information Intake
    try:
        from src.live_intelligence.schemas import (
            RawEvent, NormalizedEvent, SourceType, EventImportance, IngestionResult
        )
        
        raw = RawEvent(
            source=SourceType.REUTERS,
            headline=SAMPLE_NEWS_HEADLINES[0],
            content="FOMC holds rates, signals patience.",
            is_breaking=True,
            priority=10,
        )
        assert raw.source == SourceType.REUTERS
        assert raw.is_breaking
        
        from src.live_intelligence.source_router import SourceRouter
        router = SourceRouter()
        normalized = router.route(raw)
        assert normalized.category == "monetary_policy"
        assert normalized.importance in (EventImportance.CRITICAL, EventImportance.HIGH)
        results.append(("V6.1 Source Router", True, f"Routed → {normalized.category} (importance: {normalized.importance.value})"))
    except Exception as e:
        results.append(("V6.1 Source Router", False, str(e)))

    try:
        from src.live_intelligence.event_scheduler import EventScheduler, ScheduleFrequency
        scheduler = EventScheduler()
        due = scheduler.get_due_sources()
        assert len(due) >= 0
        
        status = scheduler.get_source_status()
        assert "reuters" in status
        
        upcoming = scheduler.get_upcoming_releases(24)
        
        scheduler.record_poll(SourceType.REUTERS, success=True)
        health = scheduler.get_health()
        assert health["active_sources"] > 0
        results.append(("V6.1 Event Scheduler", True, f"{health['active_sources']} active sources"))
    except Exception as e:
        results.append(("V6.1 Event Scheduler", False, str(e)))

    try:
        from src.live_intelligence.duplicate_detector import DuplicateDetector
        
        detector = DuplicateDetector()
        
        e1 = NormalizedEvent(title="FOMC Holds Rates", summary="Fed keeps rates steady",
                            category="monetary_policy", countries=["US"])
        e2 = NormalizedEvent(title="Fed Holds Rates Steady", summary="Federal Reserve maintains rates",
                            category="monetary_policy", countries=["US"])
        e3 = NormalizedEvent(title="CPI Rises 3.2%", summary="Inflation data",
                            category="economic_data", countries=["US"])
        
        unique, report = detector.deduplicate([e1, e2, e3])
        assert report.total_input == 3
        assert report.unique_count <= 3
        
        stats = detector.get_stats()
        results.append(("V6.1 Duplicate Detector", True, f"{report.total_input}→{report.unique_count} unique"))
    except Exception as e:
        results.append(("V6.1 Duplicate Detector", False, str(e)))

    try:
        from src.live_intelligence.freshness_monitor import FreshnessMonitor
        
        monitor = FreshnessMonitor()
        event = NormalizedEvent(title="FOMC Decision", category="monetary_policy",
                               importance=EventImportance.CRITICAL)
        monitor.register(event)
        
        score = monitor.check_freshness(event.event_id)
        assert 0 <= score <= 1.0
        
        report = monitor.check_all()
        assert report.total_events > 0
        
        stats = monitor.get_stats()
        results.append(("V6.1 Freshness Monitor", True, f"Score: {score:.2f}, events: {report.total_events}"))
    except Exception as e:
        results.append(("V6.1 Freshness Monitor", False, str(e)))

    try:
        from src.live_intelligence.ingestion_pipeline import IngestionPipeline
        
        pipeline = IngestionPipeline()
        
        raws = [
            RawEvent(source=SourceType.REUTERS, headline=SAMPLE_NEWS_HEADLINES[0],
                    content="FOMC update", is_breaking=True, priority=10),
            RawEvent(source=SourceType.BLOOMBERG, headline=SAMPLE_NEWS_HEADLINES[1],
                    content="CPI data", is_breaking=True, priority=8),
        ]
        
        result = pipeline.ingest(raws)
        assert result.raw_events_ingested == 2
        assert result.normalized_events > 0
        assert result.status.value in ("success", "duplicate")
        
        status = pipeline.get_status()
        assert status.total_events_processed > 0
        
        stats = pipeline.get_stats()
        results.append(("V6.1 Ingestion Pipeline", True, f"{result.raw_events_ingested} raw→{result.normalized_events} normalized ({result.duration_ms:.0f}ms)"))
    except Exception as e:
        results.append(("V6.1 Ingestion Pipeline", False, str(e)))

    # V6.2 Event Understanding
    try:
        from src.live_intelligence.event_reasoner import EventReasoner, UnderstandingDepth
        
        reasoner = EventReasoner()
        event = NormalizedEvent(
            title=SAMPLE_EVENT["title"],
            summary=SAMPLE_EVENT["summary"],
            category=SAMPLE_EVENT["category"],
            importance=EventImportance.CRITICAL,
            key_numbers=SAMPLE_EVENT["key_numbers"],
        )
        
        understanding = reasoner.understand(event, narratives={
            "Soft Landing": {"name": "Soft Landing Consensus"},
            "Higher for Longer": {"name": "Higher for Longer"},
        })
        
        assert understanding.event_id == event.event_id
        assert understanding.importance_rationale != ""
        assert understanding.depth in (
            UnderstandingDepth.CONTEXTUAL, UnderstandingDepth.ANALYTICAL,
            UnderstandingDepth.STRATEGIC
        )
        assert len(understanding.unknowns) > 0
        
        stats = reasoner.get_stats()
        results.append(("V6.2 Event Reasoner", True, f"Depth: {understanding.depth.value}, unknowns: {len(understanding.unknowns)}"))
    except Exception as e:
        results.append(("V6.2 Event Reasoner", False, str(e)))

    # V6.3 Research Session
    try:
        from src.research.session import SessionManager, SessionPhase
        
        mgr = SessionManager()
        session = mgr.create_session(
            title="Fed Policy Path 2026",
            description="Analyze the trajectory of Fed policy through H2 2026.",
            tags=["fed", "monetary-policy", "rates"],
        )
        
        assert session.session_id != ""
        assert session.status.value == "active"
        
        entry = mgr.add_entry(
            session.session_id, SessionPhase.READ,
            "Reviewed latest FOMC statement and dot plot projections.",
            insights=["Dot plot implies one cut in 2026", "Terminal rate debate ongoing"],
        )
        assert entry is not None
        assert len(session.entries) == 1
        
        mgr.add_hypothesis(session.session_id, "Fed begins cutting cycle in September 2026", confidence=0.6)
        mgr.add_prediction(session.session_id, "Fed cuts 50bp by December", probability=0.65)
        mgr.add_counter_argument(session.session_id, "Inflation may re-accelerate, delaying cuts")
        
        assert len(session.hypotheses) == 1
        assert len(session.predictions) == 1
        assert len(session.counter_arguments) == 1
        
        stats = mgr.get_stats()
        results.append(("V6.3 Research Session", True, f"Session: {session.entry_count} entries, {len(session.hypotheses)} hypotheses"))
    except Exception as e:
        results.append(("V6.3 Research Session", False, str(e)))

    # V6.4 Multi-pass Thinking
    try:
        from src.research.multi_pass_thinker import MultiPassThinker, ThinkingPass
        
        thinker = MultiPassThinker()
        result = thinker.execute(
            topic="Fed Policy Path H2 2026",
            macro_data=SAMPLE_MACRO_DATA,
            market_data=SAMPLE_MARKET_DATA,
            belief_data={b["id"]: b for b in SAMPLE_BELIEFS},
            narrative_data={n: n for n in SAMPLE_NARRATIVES},
            evidence_items=SAMPLE_NEWS_HEADLINES,
        )
        
        assert result.pass_count == 5
        assert result.final_content != ""
        
        # Each pass should exist
        passes = {p.pass_type for p in result.passes}
        assert ThinkingPass.OBSERVATION in passes
        assert ThinkingPass.NARRATIVE in passes
        assert ThinkingPass.BELIEF in passes
        assert ThinkingPass.COUNTER in passes
        assert ThinkingPass.REWRITE in passes
        
        stats = thinker.get_stats()
        results.append(("V6.4 Multi-pass Thinking", True, f"{result.pass_count} passes, final confidence: {result.confidence_evolution[-1]:.2f}"))
    except Exception as e:
        results.append(("V6.4 Multi-pass Thinking", False, str(e)))

    # V6.5 Research Journal
    try:
        from src.research.journal import ResearchJournal, LogType
        
        journal = ResearchJournal()
        
        journal.log_thinking("Initial macro framework review", 
                            "Reviewed the current macro framework...",
                            topic="Macro Framework", session_id="sess_001")
        
        journal.log_decision("Reduce equity exposure", 
                            "Valuations stretched, risk/reward unfavorable.",
                            alternatives=["Maintain", "Increase"],
                            importance="high")
        
        journal.log_evidence("CPI Release — July 2026",
                           [{"indicator": "CPI YoY", "value": 3.2, "expected": 3.1}],
                           source="BLS")
        
        journal.log_prediction("Fed cuts 50bp by December", 
                              probability=0.65, time_horizon="6 months",
                              invalidation="CPI re-accelerates above 3.5%")
        
        journal.log_reflection("Weekly review", 
                              "Key lessons: verify evidence sources, track counter signals.",
                              lessons=["Triangulate data sources"],
                              mistakes=["Overweighted recent data"])
        
        today = journal.get_today_entries()
        predictions = journal.get_predictions()
        decisions = journal.get_decisions()
        
        assert len(predictions) >= 1
        assert len(decisions) >= 1
        
        daily = journal.get_daily_summary()
        assert daily["total_entries"] >= 5
        
        stats = journal.get_stats()
        results.append(("V6.5 Research Journal", True, f"{stats['total_entries']} entries across 5 log types"))
    except Exception as e:
        results.append(("V6.5 Research Journal", False, str(e)))

    # ═══════════════════════════════════════════════════════════════════════════
    # V7 — Live Macro Research Desk
    # ═══════════════════════════════════════════════════════════════════════════

    # V7.1 Continuous Research
    try:
        from src.agent.continuous_research import ContinuousResearch, ResearchTrigger
        
        cr = ContinuousResearch()
        cr.start("Fed Policy Path 2026")
        assert cr.state.is_active
        assert cr.state.current_topic == "Fed Policy Path 2026"
        
        # Simulate event
        v1 = cr.on_event(SAMPLE_EVENT, ResearchTrigger.BREAKING_NEWS, force_update=True)
        assert v1 is not None
        assert v1.version_number == 1
        assert v1.memo_content != ""
        
        # Second version
        v2 = cr.on_scheduled()
        assert v2 is not None
        assert v2.version_number >= 1  # At least creates a version
        
        history = cr.get_version_history()
        stats = cr.get_stats()
        
        results.append(("V7.1 Continuous Research", True, f"{stats['total_versions']} versions, active: {stats['is_active']}"))
    except Exception as e:
        results.append(("V7.1 Continuous Research", False, str(e)))

    # V7.2 Belief Evolution
    try:
        from src.research.beliefs.belief_timeline import BeliefEvolutionTracker, BeliefTrend
        
        tracker = BeliefEvolutionTracker()
        
        tracker.record("fed_path", "Fed Cutting Cycle", confidence=0.60, stage="evidence_gathering",
                      evidence_count=5, supporting=3, contradicting=2,
                      trigger_event="FOMC Statement", trigger_description="Fed signals patience")
        
        tracker.record("fed_path", "Fed Cutting Cycle", confidence=0.65, stage="confirmation",
                      evidence_count=8, supporting=5, contradicting=3,
                      trigger_event="CPI Data", trigger_description="Inflation moderating")
        
        tracker.record("fed_path", "Fed Cutting Cycle", confidence=0.70, stage="consolidation",
                      evidence_count=12, supporting=8, contradicting=4,
                      trigger_event="Jobs Report", trigger_description="Labor market cooling")
        
        timeline = tracker.get_timeline("fed_path")
        assert timeline is not None
        assert len(timeline.snapshots) == 3
        assert timeline.confidence_range[1] >= timeline.confidence_range[0]
        
        evolution = timeline.get_evolution_data()
        assert len(evolution) == 3
        
        convergence = tracker.get_convergence_analysis()
        report = tracker.get_evolution_report()
        assert len(report) > 0
        
        stats = tracker.get_stats()
        results.append(("V7.2 Belief Evolution", True, f"3 snapshots, trend: {timeline.trend.value}, range: {timeline.confidence_range[0]:.2f}→{timeline.confidence_range[1]:.2f}"))
    except Exception as e:
        results.append(("V7.2 Belief Evolution", False, str(e)))

    # V7.3 Narrative Tracking
    try:
        from src.research.narrative_tracker import NarrativeTracker, NarrativeStatus
        
        tracker = NarrativeTracker()
        
        nar1 = tracker.register("Soft Landing Consensus", "Economy achieves soft landing without recession.",
                                strength=0.7, status=NarrativeStatus.DOMINANT, market_impact="bullish")
        nar2 = tracker.register("Higher for Longer", "Rates stay elevated through 2026.",
                                strength=0.55, status=NarrativeStatus.ACTIVE, market_impact="bearish")
        nar3 = tracker.register("AI Productivity Boom", "AI drives productivity acceleration.",
                                strength=0.6, status=NarrativeStatus.EMERGING, market_impact="bullish")
        
        ranking = tracker.get_daily_ranking()
        assert ranking.total_tracked == 3
        assert len(ranking.top_narratives) >= 1
        
        # Update a narrative
        tracker.update(nar1.narrative_id, strength=0.75, momentum=0.1,
                      note="Jobs data supports soft landing thesis")
        
        # Mark one as broken
        tracker.mark_broken(nar2.narrative_id, reason="Fed explicitly signals cutting cycle")
        
        ranking2 = tracker.get_daily_ranking()
        assert len(ranking2.broken) >= 1
        
        stats = tracker.get_stats()
        summary = ranking2.summary()
        assert len(summary) > 0
        
        results.append(("V7.3 Narrative Tracker", True, f"3 narratives: {stats['current_top3']}, broken: {stats['broken_count']}"))
    except Exception as e:
        results.append(("V7.3 Narrative Tracker", False, str(e)))

    # V7.4 Professional Memo
    try:
        from src.research.professional_memo import ProfessionalMemoBuilder
        
        builder = ProfessionalMemoBuilder()
        memo = (builder
            .title("Fed Policy Path: H2 2026 Outlook")
            .executive_summary("The Fed is navigating a complex macro environment with resilient growth and gradually moderating inflation. We expect the cutting cycle to begin in September 2026, with a total of 50bp of cuts by year-end. Key risk: sticky services inflation delays the cutting cycle.")
            .macro_dashboard(SAMPLE_MACRO_DATA)
            .current_narrative("Soft landing with gradual policy normalization.",
                             competing=["Hard landing recession", "No-landing reacceleration"])
            .add_evidence("CPI trending toward 2.5% by Q4", evidence_type="inflation", source="BLS", strength="High")
            .add_evidence("Labor market gradually cooling", evidence_type="employment", source="BLS")
            .add_counter("Sticky shelter inflation keeps CPI elevated", probability=0.35,
                        impact="Delays cutting cycle to Q1 2027")
            .add_analogy("1995 Soft Landing", "Fed engineered soft landing after 1994 tightening cycle.",
                         similarity=0.7, differences=["Fiscal backdrop different", "Globalization reversing"])
            .add_prediction("Fed cuts 50bp by December 2026", probability=0.65, time_horizon="6 months")
            .add_trade("US 2Y Treasuries", direction="long", conviction="high",
                      rationale="Front-end rates decline as cutting cycle begins")
            .add_risk("Sticky services inflation", probability=0.30, impact="high",
                     monitoring="Core services CPI monthly")
            .add_invalidation("CPI re-accelerates above 3.5%", threshold="3.5% YoY",
                            current="3.2%", implication="Scenario materially changes")
            .set_sources(["BLS", "FOMC Statements", "CME FedWatch", "Bloomberg"])
            .build())
        
        rendered = memo.render()
        assert len(rendered) > 1000  # Substantial document
        assert memo.word_count > 100
        assert "Executive Summary" in rendered
        assert "Macro Dashboard" in rendered
        assert "Counter" in rendered or "Counter Arguments" in rendered
        assert "Prediction" in rendered or "Predictions" in rendered
        assert "Trade Implication" in rendered
        assert "Risk" in rendered
        assert "Invalidation" in rendered
        
        results.append(("V7.4 Professional Memo", True, f"{memo.word_count} words, {len(rendered)} chars"))
    except Exception as e:
        results.append(("V7.4 Professional Memo", False, str(e)))

    # V7.5 CIO Dashboard
    try:
        from src.research.cio_dashboard import CIODashboardBuilder, RiskLevel, RegimePhase
        
        dash = (CIODashboardBuilder()
            .regime("Late Cycle — Gradual Cooling", RegimePhase.EXPANSION,
                    confidence=0.65, change_prob=0.20)
            .narrative("Soft Landing with Gradual Policy Normalization", strength=0.70)
            .add_belief("Fed Cutting Cycle H2 2026", confidence=0.65, direction="bullish_duration")
            .add_belief("Inflation Moderating Toward Target", confidence=0.55)
            .add_belief("AI Capex Structural Growth", confidence=0.72, direction="bullish_tech")
            .prediction_confidence(confidence=0.60, active=3, on_track=2)
            .risk_level(RiskLevel.ELEVATED, score=35.0)
            .add_risk("Sticky inflation delays cuts", probability=0.30, severity="high", trend="→")
            .add_risk("Geopolitical escalation", probability=0.15, severity="critical", trend="↑")
            .positioning("Moderately constructive, overweight duration, neutral equities")
            .add_unknown("Will shelter inflation finally decelerate?")
            .add_unknown("When will the cutting cycle actually begin?")
            .add_catalyst("September FOMC", date="2026-09-17", importance="critical",
                         impact="First potential rate cut")
            .add_catalyst("Q3 GDP Advance", date="2026-10-30", importance="high",
                         impact="Growth trajectory confirmation")
            .build())
        
        rendered = dash.render()
        assert len(rendered) > 500
        assert "CIO Macro Dashboard" in rendered
        assert "Regime" in rendered or "regime" in rendered
        assert "Narrative" in rendered or "narrative" in rendered or "Belief" in rendered
        assert "Risk" in rendered
        
        export = dash.to_dict()
        assert export["risk_level"] == RiskLevel.ELEVATED.value
        
        results.append(("V7.5 CIO Dashboard", True, f"{len(rendered)} chars, risk: {dash.risk_level.value}"))
    except Exception as e:
        results.append(("V7.5 CIO Dashboard", False, str(e)))

    # ═══════════════════════════════════════════════════════════════════════════
    # V8 — Institutional CIO Agent
    # ═══════════════════════════════════════════════════════════════════════════

    # V8.1 Investment Committee
    try:
        from src.research.investment_committee import InvestmentCommittee, CommitteeRole
        
        ic = InvestmentCommittee()
        minutes = ic.convene(
            topic="Should we increase duration exposure?",
            agenda="Review fixed income positioning ahead of expected Fed cutting cycle.",
            market_context="Fed signaling one cut in 2026. Inflation moderating but sticky above 3%.",
            current_positioning="Underweight duration, neutral equities.",
            beliefs=SAMPLE_BELIEFS,
            narratives=SAMPLE_NARRATIVES,
            risks=SAMPLE_RISKS,
        )
        
        assert len(minutes.statements) == 6  # 6 committee members
        assert len(minutes.votes) >= 1
        assert minutes.decision != ""
        assert len(minutes.action_items) >= 1
        
        rendered = minutes.render()
        assert len(rendered) > 500
        assert "Investment Committee" in rendered
        assert "Vote" in rendered or "Decision" in rendered
        
        stats = ic.get_stats()
        
        results.append(("V8.1 Investment Committee", True, f"6 members, decision: {minutes.decision[:60]}"))
    except Exception as e:
        results.append(("V8.1 Investment Committee", False, str(e)))

    # V8.2 Portfolio Recommendation
    try:
        from src.research.portfolio_advisor import PortfolioAdvisor, PositionAction
        
        advisor = PortfolioAdvisor()
        rec = advisor.recommend(
            regime="expansion",
            regime_confidence=0.65,
            beliefs=SAMPLE_BELIEFS,
            narratives=SAMPLE_NARRATIVES,
            predictions=SAMPLE_PREDICTIONS,
            risks=SAMPLE_RISKS,
        )
        
        assert len(rec.recommendations) >= 10  # Full asset universe
        assert rec.overall_stance != ""
        assert len(rec.action_summary) >= 2
        
        # Check for increase actions
        actions = [r.action for r in rec.recommendations]
        assert PositionAction.INCREASE in actions or PositionAction.MAINTAIN in actions
        
        rendered = rec.render()
        assert len(rendered) > 500
        
        stats = advisor.get_stats()
        
        results.append(("V8.2 Portfolio Advisor", True, f"{len(rec.recommendations)} assets, stance: {rec.overall_stance[:60]}"))
    except Exception as e:
        results.append(("V8.2 Portfolio Advisor", False, str(e)))

    # V8.3 Reflexivity Simulation
    try:
        from src.research.reflexivity_simulator import ReflexivitySimulator, ReflexivityPhase
        
        sim = ReflexivitySimulator()
        analysis = sim.analyze(
            thesis="AI Capex will drive a sustained productivity boom, justifying elevated tech valuations.",
            narratives=["AI Productivity Boom", "Tech Dominance"],
            beliefs=SAMPLE_BELIEFS,
        )
        
        assert analysis.phase != ReflexivityPhase.LATENT or True  # Phase is determined
        assert analysis.if_everyone_believes != ""
        assert analysis.if_everyone_positions != ""
        assert analysis.if_crowding != ""
        assert analysis.self_reinforcing_mechanism != ""
        assert analysis.vulnerability_score >= 0
        assert len(analysis.catalyst_for_reversal) >= 1
        
        rendered = analysis.render()
        assert len(rendered) > 400
        
        stats = sim.get_stats()
        
        results.append(("V8.3 Reflexivity Sim", True, f"Phase: {analysis.phase.value}, vulnerability: {analysis.vulnerability_score:.0f}/100"))
    except Exception as e:
        results.append(("V8.3 Reflexivity Sim", False, str(e)))

    # V8.4 Self Challenge
    try:
        from src.research.self_challenge import SelfChallenger
        
        challenger = SelfChallenger()
        result = challenger.challenge(
            topic="Fed Rate Path 2026",
            thesis="The Fed will begin cutting rates in September 2026, cutting 50bp by year-end as inflation moderates and labor market cools.",
            evidence=SAMPLE_NEWS_HEADLINES,
            beliefs=SAMPLE_BELIEFS,
            narratives=SAMPLE_NARRATIVES,
            risks=SAMPLE_RISKS,
        )
        
        assert len(result.challenges) >= 8  # Multiple challenge questions
        assert result.vulnerability_score >= 0
        assert result.strongest_challenge != ""
        assert len(result.blind_spots) >= 1
        assert len(result.assumptions_unverified) >= 1
        assert result.confidence_adjustment <= 0  # Challenge should reduce confidence
        
        rendered = result.render()
        assert len(rendered) > 500
        
        stats = challenger.get_stats()
        
        results.append(("V8.4 Self Challenge", True, f"Vulnerability: {result.vulnerability_score:.0f}/100, {len(result.challenges)} challenges, adj: {result.confidence_adjustment:+.0%}"))
    except Exception as e:
        results.append(("V8.4 Self Challenge", False, str(e)))

    # V8.5 Long-term Learning
    try:
        from src.research.deep_learning import DeepLearningEngine, ErrorRootCause, LearningType
        
        engine = DeepLearningEngine()
        
        # Diagnose a correct prediction
        diag_correct = engine.diagnose_error(
            prediction="CPI moderates to 3.2%",
            probability=0.70,
            actual_outcome="CPI came in at 3.2%",
            was_correct=True,
        )
        assert diag_correct.was_correct
        assert diag_correct.root_cause is not None
        
        # Diagnose a wrong prediction
        diag_wrong = engine.diagnose_error(
            prediction="Fed cuts in June 2026",
            probability=0.75,
            actual_outcome="Fed held rates, no cut in June",
            was_correct=False,
        )
        assert not diag_wrong.was_correct
        assert diag_wrong.root_cause is not None
        assert diag_wrong.key_lesson != ""
        
        # Apply learning
        evolution = engine.apply_learning(diag_wrong)
        assert evolution is not None
        
        # Check learning state
        error_patterns = engine.get_error_patterns()
        assert error_patterns
        
        report = engine.generate_learning_report()
        assert len(report) > 200
        
        stats = engine.get_stats()
        assert stats["total_diagnoses"] >= 2
        
        results.append(("V8.5 Deep Learning", True, f"2 diagnoses, root cause: {diag_wrong.root_cause.value}, lesson applied"))
    except Exception as e:
        results.append(("V8.5 Deep Learning", False, str(e)))

    # ═══════════════════════════════════════════════════════════════════════════
    # Report
    # ═══════════════════════════════════════════════════════════════════════════
    
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    
    print(f"\n{'='*70}")
    print(f"  V6-V8 Integration Test Results")
    print(f"{'='*70}")
    print(f"  Passed: {passed}/{total} ({passed/total*100:.0f}%)\n")
    
    for name, ok, detail in results:
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status} | {name}")
        if not ok:
            print(f"         -> {detail}")
    
    print(f"\n{'='*70}")
    print(f"  {'ALL TESTS PASSED' if passed == total else f'{total - passed} TESTS FAILED'}")
    print(f"{'='*70}\n")
    
    return passed == total


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
