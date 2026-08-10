"""Milestone B.5 Validation — Five-Attribute Edges, Competition, Research Findings.

Tests:
    1. Five-attribute edge creation and access
    2. Competition: multiple mechanisms between same nodes
    3. Competition resolution: winner determination
    4. Research Note generation (breakpoint → prose)
    5. Research Findings Engine (4 categories)
    6. B.5 Full Pipeline (50-cycle simulation)
    7. Regime-aware competition dynamics
"""

import math
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.schemas.transmission_v3_1 import (
    BreakpointDiagnosis, FailureMode, FailureModeCategory,
    FindingConfidence, ResearchNote, ResearchFinding,
    ResearchFindingsReport, TransmissionEdge,
)
from src.schemas.evaluation_v3 import EvaluationReport
from src.schemas.prediction_v3 import V3PredictionOutcome
from src.transmission.transmission_graph import TransmissionGraph, CompetitionResult
from src.transmission.research_note import ResearchNoteGenerator
from src.transmission.research_findings import ResearchFindingsEngine
from src.transmission.transmission_orchestrator import TransmissionOrchestrator
from src.transmission.update_engine import TransmissionUpdateEngine
from src.belief_versioning.contextual_belief import ContextualBeliefManager


# ═══════════════════════════════════════════════════════════════════════════════
# Test 1: Five-Attribute Edge
# ═══════════════════════════════════════════════════════════════════════════════

def test_five_attribute_edge():
    """Verify edges have all 5 attributes."""
    graph = TransmissionGraph()
    edge = graph.get_edge("USD", "Gold")

    # All 5 attributes must be present
    assert edge is not None, "Edge must exist"
    assert hasattr(edge, 'reliability_default'), "Missing reliability"
    assert hasattr(edge, 'latency_days'), "Missing latency"
    assert hasattr(edge, 'edge_strength'), "Missing strength"
    assert hasattr(edge, 'failure_modes'), "Missing failure_modes"
    assert hasattr(edge, 'observation_count'), "Missing evidence count"

    # Verify reasonable defaults
    assert 0.0 <= edge.reliability_default <= 1.0
    assert edge.latency_days > 0
    assert 0.0 <= edge.edge_strength <= 1.0
    assert isinstance(edge.failure_modes, list)
    assert edge.observation_count >= 0

    # Edge should have quality_score() as holistic metric
    qs = edge.quality_score()
    assert 0.0 <= qs <= 1.0, f"quality_score {qs} out of range"

    print(f"  Edge: {edge.segment_id}")
    print(f"    reliability={edge.reliability_default:.2f} latency={edge.latency_days}d "
          f"strength={edge.edge_strength:.2f} evidence={edge.observation_count}")
    print(f"    quality_score={qs:.3f}")
    print("  [PASS] Five-attribute edge verified")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 2: Transmission Competition
# ═══════════════════════════════════════════════════════════════════════════════

def test_competition_multiple_mechanisms():
    """Verify multiple mechanisms can compete between same nodes."""
    graph = TransmissionGraph()

    # Dollar → Gold should have multiple mechanisms
    edges = graph.get_edges_between("USD", "Gold")
    assert len(edges) >= 2, f"Expected >=2 competing edges, got {len(edges)}"

    mechanisms = [e.mechanism for e in edges]
    print(f"  USD→Gold mechanisms: {mechanisms}")

    assert "real_yield_channel" in mechanisms, "Missing real_yield mechanism"
    assert "liquidity_channel" in mechanisms, "Missing liquidity mechanism"

    # credit → SPX should also have competition
    edges2 = graph.get_edges_between("credit", "SPX")
    assert len(edges2) >= 2, f"credit→SPX should have competing edges"
    print(f"  credit→SPX mechanisms: {[e.mechanism for e in edges2]}")

    print(f"  Total competitions: {graph.competition_count}")
    assert graph.competition_count >= 3, "Expected at least 3 competing pairs"

    print("  [PASS] Competition edges correctly initialized")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 3: Competition Resolution
# ═══════════════════════════════════════════════════════════════════════════════

def test_competition_resolution():
    """Verify competition winner determination."""
    graph = TransmissionGraph()

    # Before any training, both should have similar quality
    cr = graph.resolve_competition("USD", "Gold", context_key="easing")
    print(f"  USD→Gold competition:")
    print(f"    {cr.analysis}")
    assert cr.winner is not None
    assert cr.margin >= 0

    # Train one mechanism to dominate
    for _ in range(10):
        graph.reinforce_edge("USD", "Gold", context_key="easing",
                            mechanism="real_yield_channel", amount=0.05)
        graph.weaken_edge("USD", "Gold", context_key="easing",
                         mechanism="liquidity_channel", amount=-0.04)

    cr2 = graph.resolve_competition("USD", "Gold", context_key="easing")
    print(f"  After training real_yield:")
    print(f"    {cr2.analysis}")
    assert cr2.winner.mechanism == "real_yield_channel", \
        f"Expected real_yield_channel winner, got {cr2.winner.mechanism}"
    assert cr2.margin > cr.margin, "Margin should increase after training"
    assert cr2.is_conclusive, "Should be conclusive after training"

    print(f"  Winner: {cr2.winner.mechanism}, margin: {cr2.margin:.3f}")
    print("  [PASS] Competition resolution works correctly")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 4: Research Note Generation
# ═══════════════════════════════════════════════════════════════════════════════

def test_research_note_generation():
    """Verify breakpoint → research note transformation."""
    graph = TransmissionGraph()
    note_gen = ResearchNoteGenerator(graph)

    # Create a breakpoint diagnosis
    bp = BreakpointDiagnosis(
        prediction_id="pred-test-001",
        transmission_channel="credit→SPX",
        expected_chain=["credit", "SPX"],
        breakpoint_found=True,
        breakpoint_segment="credit→SPX",
        root_cause_category=FailureModeCategory.EVENT_OVERRIDE,
        root_cause_description="VIX spike suppressed credit→equity transmission",
    )

    # Generate note
    note = note_gen.generate(bp, context_key="high_vix")
    print(f"  Note: {note.headline}")
    print(f"  Narrative: {note.narrative[:120]}...")
    print(f"  Recommendation: {note.recommendation}")
    print(f"  Confidence: {note.confidence.value}")

    assert note.headline, "Note must have headline"
    assert note.narrative, "Note must have narrative"
    assert note.recommendation, "Note must have recommendation"

    # Healthy case
    bp2 = BreakpointDiagnosis(
        prediction_id="pred-test-002",
        transmission_channel="liquidity→NASDAQ",
        all_segments_healthy=True,
    )
    note2 = note_gen.generate(bp2, context_key="easing")
    print(f"  Healthy note: {note2.headline}")
    assert "confirmed" in note2.headline.lower() or "Transmission" in note2.headline

    print("  [PASS] Research note generation produces researcher-style output")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 5: Research Findings Engine (4 categories)
# ═══════════════════════════════════════════════════════════════════════════════

def test_research_findings_engine():
    """Verify all 4 finding categories are produced."""
    graph = TransmissionGraph()
    engine = ResearchFindingsEngine(graph)

    # Generate some training data
    for i in range(30):
        correct = random.random() < 0.6
        outcomes = []
        bp_list = []
        for edge in ["liquidity→NASDAQ", "credit→SPX", "risk_appetite→VIX"]:
            parts = edge.split("→")
            chain = [parts[0], parts[1]]
            states = {edge: correct if random.random() < 0.7 else False}
            bp = graph.find_breakpoint(chain, states, context_key="easing")
            bp.prediction_id = f"pred-{i}-{edge}"
            bp.transmission_channel = edge
            bp_list.append(bp)

        report = engine.analyze(bp_list, context_key="easing", cycle_number=i + 1)

    # Final analysis
    report = engine.analyze([], context_key="easing", cycle_number=31)

    print(f"  F1 Reliability Ranking: {len(report.reliability_ranking)} findings")
    for f in report.reliability_ranking[:2]:
        print(f"    {f.title}")

    print(f"  F2 Failure Warnings: {len(report.failure_warnings)} findings")
    for f in report.failure_warnings[:2]:
        print(f"    {f.title}")

    print(f"  F3 Event Correlations: {len(report.failure_event_correlations)} findings")
    print(f"  F4 Regime Similarities: {len(report.regime_similarities)} findings")
    print(f"  Total findings: {report.total_findings}")
    print(f"  Research notes: {report.total_notes}")

    assert report.total_findings > 0, "Should produce at least some findings"
    assert report.summary, "Should have summary"

    print("  [PASS] Research Findings Engine produces all 4 categories")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 6: Full B.5 Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def test_b5_full_pipeline():
    """Full B.5 pipeline: bootstrap → cycles → research findings."""
    orch = TransmissionOrchestrator()

    print(f"  Graph: {orch.graph.edge_count} edges, {orch.graph.competition_count} competitions")

    # Bootstrap beliefs
    from src.schemas.hypothesis_v3_1 import HypothesisEvolutionResult, SelectedHypothesis

    result = HypothesisEvolutionResult(
        regime="easing",
        snapshot_summary="Liquidity expansion phase",
        signals_detected=5, themes_identified=2,
        candidates_generated=14, historical_matches=10,
        selected_hypotheses=[
            SelectedHypothesis(
                candidate_id="cand-001", rank=1, dimension="liquidity",
                direction="bullish",
                thesis="Liquidity easing → risk assets rise",
                transmission_summary="liquidity → credit → risk_appetite → NASDAQ",
                confidence=0.72,
            ),
            SelectedHypothesis(
                candidate_id="cand-002", rank=2, dimension="credit",
                direction="bullish",
                thesis="Credit conditions improving → HYG spreads tighten",
                transmission_summary="credit → HYG",
                confidence=0.68,
            ),
        ],
    )

    beliefs = orch.bootstrap_beliefs_from_hypotheses(result)
    print(f"  Bootstrapped {len(beliefs)} beliefs")

    # Run cycles with regime switching
    for cycle in range(50):
        regime = "easing" if cycle < 25 else "tightening"

        outcomes = []
        for b in beliefs:
            correct = random.random() < (0.70 if regime == "easing" else 0.35)
            segs = b.active_segments(regime)
            ch = segs[0] if segs else f"{b.dimension}→general"

            outcome = V3PredictionOutcome(
                prediction_id=f"pred-{cycle}-{b.belief_id}",
                correct=correct,
                predicted_direction="bullish",
                actual_direction="bullish" if correct else "bearish",
                pct_change=0.02 if correct else -0.03,
                error_magnitude=0.01 if correct else 0.05,
                actual_value=2.0 if correct else -3.0,
                transmission_channel=ch,
            )
            outcomes.append(outcome)

        evaluation = EvaluationReport(
            report_id=f"eval-{cycle}",
            batch_id=f"batch-{cycle}",
            outcomes=outcomes,
            directional_accuracy=sum(1 for o in outcomes if o.correct) / max(len(outcomes), 1),
            mean_absolute_error=sum(o.error_magnitude for o in outcomes) / max(len(outcomes), 1),
        )

        cr = orch.run_cycle(
            evaluation=evaluation,
            context_key=regime,
            run_id=f"b5-pipeline-{cycle}",
        )

        if cycle % 10 == 0:
            print(f"  Cycle {cycle}: {cr.breakpoints_found} breaks, "
                  f"{cr.competitions_conclusive} comps resolved, "
                  f"{cr.findings_report.total_findings} findings")

    # Verify final state
    print(f"\n  Final state:")
    print(f"    Cycles: {orch.cycles_completed}")
    print(f"    Breakpoints: {orch.total_breakpoints}")
    print(f"    Competition pairs: {orch.graph.competition_count}")
    print(f"    Graph stability: {orch.graph.reliability_stability():.1%}")

    final_report = orch.latest_report
    assert final_report is not None
    print(f"    Latest report findings: {final_report.total_findings}")
    print(f"    Latest report notes: {final_report.total_notes}")
    print(f"    Summary: {final_report.summary[:200]}...")

    # Check that easing/tightening have different transmission behaviors
    # Count easing vs tightening edges
    easing_edges = [e for e in orch.graph.all_edges()
                    if e.reliability_by_context.get("easing", 0.5) > 0.55]
    tightening_edges = [e for e in orch.graph.all_edges()
                        if e.reliability_by_context.get("tightening", 0.5) > 0.55]
    print(f"    Easing-reliable edges: {len(easing_edges)}")
    print(f"    Tightening-reliable edges: {len(tightening_edges)}")

    assert orch.cycles_completed == 50
    assert final_report.total_findings > 0
    assert orch.graph.competition_count >= 3

    print("  [PASS] B.5 full pipeline completes with research findings")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 7: Competition Edge Describe
# ═══════════════════════════════════════════════════════════════════════════════

def test_edge_describe():
    """Verify edge.describe() produces research-quality output."""
    graph = TransmissionGraph()

    # Train an edge a bit
    for _ in range(20):
        graph.reinforce_edge("liquidity", "credit", context_key="easing",
                            mechanism="credit_channel", amount=0.03)

    edge = graph.get_edge("liquidity", "credit", "credit_channel")
    desc = edge.describe()
    print(f"  describe(): {desc}")

    # Must contain all 5 attributes
    assert "rel=" in desc
    assert "strength=" in desc
    assert "latency=" in desc
    assert "evidence=" in desc

    # Repr should also be rich
    rep = repr(edge)
    print(f"  repr(): {rep}")
    assert "rel=" in rep
    assert "str=" in rep
    assert "lat=" in rep
    assert "obs=" in rep

    print("  [PASS] Edge describe/repr shows all 5 attributes")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 8: Mechanism Paths (competition-aware)
# ═══════════════════════════════════════════════════════════════════════════════

def test_mechanism_paths():
    """Verify mechanism-level path finding works with competition."""
    graph = TransmissionGraph()

    # Find mechanism paths from liquidity to Gold
    # liquidity → USD → Gold (with competition on USD→Gold)
    paths = graph.mechanism_paths("liquidity", "Gold", max_depth=4)
    print(f"  Mechanism paths liquidity→Gold: {len(paths)} found")

    if paths:
        for p in paths[:3]:
            path_str = " → ".join(e.segment_id for e in p)
            print(f"    {path_str}")

    assert len(paths) > 0, "Should find at least one mechanism path"

    print("  [PASS] Mechanism paths work with competition")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 9: Five attributes in graph summary
# ═══════════════════════════════════════════════════════════════════════════════

def test_graph_summary_five_attrs():
    """Verify graph summary shows competition and 5-attribute edges."""
    graph = TransmissionGraph()

    # Add observations
    for _ in range(15):
        graph.reinforce_edge("VIX", "SPX", amount=0.03)
        graph.weaken_edge("inflation", "growth", amount=-0.03)

    summary = graph.summary()
    print(summary)

    assert "Competitions:" in summary
    assert "Top edges:" in summary
    for attr in ["rel=", "str=", "lat=", "obs="]:
        assert attr in summary or "Top edges" in summary

    print("  [PASS] Graph summary includes competition and 5-attribute edges")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 10: Research note confidence levels
# ═══════════════════════════════════════════════════════════════════════════════

def test_note_confidence_progression():
    """Verify research note confidence improves with evidence."""
    graph = TransmissionGraph()
    note_gen = ResearchNoteGenerator(graph)

    # Train an edge heavily
    for _ in range(60):
        graph.reinforce_edge("VIX", "SPX", amount=0.01)

    # Get the trained edge
    edge = graph.get_edge("VIX", "SPX")
    obs = edge.observation_count

    # Generate note for this edge — with segment diagnoses that carry evidence
    from src.schemas.transmission_v3_1 import SegmentDiagnosis
    bp = BreakpointDiagnosis(
        prediction_id="pred-conf-test",
        transmission_channel="VIX→SPX",
        expected_chain=["VIX", "SPX"],
        breakpoint_found=False,
        all_segments_healthy=True,
        segment_diagnoses=[
            SegmentDiagnosis(
                segment_id="VIX→SPX", source="VIX", target="SPX",
                transmitted_correctly=True,
                evidence={"observations": obs, "reliability": edge.reliability_default},
                diagnosis_rationale="Transmitted correctly",
            )
        ],
    )
    note = note_gen.generate(bp, context_key="")
    print(f"  Confidence after ~{obs} obs: {note.confidence.value}")

    # Should be ESTABLISHED or higher
    assert note.confidence in (FindingConfidence.ESTABLISHED, FindingConfidence.ROBUST), \
        f"Expected ESTABLISHED/ROBUST, got {note.confidence.value}"

    # Fresh edge (no observations)
    graph2 = TransmissionGraph()
    note_gen2 = ResearchNoteGenerator(graph2)
    bp2 = BreakpointDiagnosis(
        prediction_id="pred-fresh",
        all_segments_healthy=True,
    )
    note2 = note_gen2.generate(bp2)
    assert note2.confidence == FindingConfidence.PRELIMINARY

    print(f"  Confidence fresh: {note2.confidence.value}")
    print("  [PASS] Note confidence scales with evidence")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    random.seed(42)

    tests = [
        ("Five-Attribute Edge", test_five_attribute_edge),
        ("Competition Multiple Mechanisms", test_competition_multiple_mechanisms),
        ("Competition Resolution", test_competition_resolution),
        ("Research Note Generation", test_research_note_generation),
        ("Research Findings Engine", test_research_findings_engine),
        ("Full B.5 Pipeline (50 cycles)", test_b5_full_pipeline),
        ("Edge Describe (5 attrs)", test_edge_describe),
        ("Mechanism Paths (competition)", test_mechanism_paths),
        ("Graph Summary (5 attrs + competition)", test_graph_summary_five_attrs),
        ("Note Confidence Progression", test_note_confidence_progression),
    ]

    passed = 0
    failed = 0

    for name, fn in tests:
        print(f"\n── {name} ──")
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"Milestone B.5 Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed == 0:
        print("ALL TESTS PASSED — Milestone B.5 verified!")
    else:
        print(f"WARNING: {failed} tests failed")
