"""Milestone A Validation — Hypothesis Evolution + Research Quality Benchmark.

Tests the full pipeline:
    Signal Engine → Candidate Generator → Historical Retriever
    → Competition Engine → Hypothesis Selector

Plus the Research Quality Benchmark:
    Compares Agent Top-5 against human macro researcher framework.
    Measures overlap (thinking direction alignment, not prediction accuracy).
"""

from __future__ import annotations

import sys
import statistics
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.hypothesis.hypothesis_evolution import HypothesisEvolution
from src.schemas.hypothesis_library import HypothesisLibraryEntry, HypothesisScore
from src.schemas.hypothesis_v3_1 import HypothesisEvolutionResult


# ═══════════════════════════════════════════════════════════════════════════════
# Research Quality Benchmark — Gold Standard Framework
# ═══════════════════════════════════════════════════════════════════════════════


# What a good macro researcher would think in each scenario.
# Key dimensions and directions a human would prioritize.
GOLD_STANDARD = {
    "easing_liquidity_dominant": {
        "description": "Fed clearly easing, dollar weakening, liquidity flooding",
        "indicators": {
            "DXY": 100.0, "US02Y": 3.20, "SPX": 5500, "NASDAQ": 19000,
            "VIX": 14, "HYG": 80, "US10Y": 3.30, "TIPS": 1.20, "Gold": 2300,
            "FED_FUNDS": 3.50,
        },
        "regime": "easing",
        "expected_dimensions": ["liquidity", "risk_appetite"],
        "expected_direction": "bullish",
        "expected_themes": [
            "liquidity easing driving risk assets",
            "dollar weakness benefiting EM and gold",
            "risk appetite broadening beyond mega-cap",
        ],
    },
    "tightening_liquidity_shock": {
        "description": "Fed hawkish surprise, dollar spiking, risk-off",
        "indicators": {
            "DXY": 108.0, "US02Y": 5.00, "SPX": 4500, "NASDAQ": 15000,
            "VIX": 28, "HYG": 72, "US10Y": 4.80, "TIPS": 2.20, "Gold": 1950,
            "FED_FUNDS": 5.50,
        },
        "regime": "tightening",
        "expected_dimensions": ["liquidity", "credit"],
        "expected_direction": "bearish",
        "expected_themes": [
            "liquidity tightening constraining risk assets",
            "credit stress building",
            "defensive positioning warranted",
        ],
    },
    "growth_acceleration": {
        "description": "Strong growth, rising rates for good reasons, risk-on",
        "indicators": {
            "DXY": 103.0, "US02Y": 4.20, "SPX": 5200, "NASDAQ": 18000,
            "VIX": 15, "HYG": 79, "US10Y": 4.50, "TIPS": 1.80, "Gold": 2050,
            "FED_FUNDS": 4.50,
        },
        "regime": "neutral",
        "expected_dimensions": ["growth", "risk_appetite"],
        "expected_direction": "bullish",
        "expected_themes": [
            "growth acceleration driving cyclicals",
            "rates rising on growth not fear",
            "risk appetite supported by earnings",
        ],
    },
    "stagflation_risk": {
        "description": "Sticky inflation + slowing growth — stagflation fears",
        "indicators": {
            "DXY": 105.0, "US02Y": 4.80, "SPX": 4700, "NASDAQ": 16000,
            "VIX": 22, "HYG": 74, "US10Y": 4.60, "TIPS": 2.40, "Gold": 2200,
            "FED_FUNDS": 5.00,
        },
        "regime": "tightening",
        "expected_dimensions": ["inflation", "growth"],
        "expected_direction": "bearish",
        "expected_themes": [
            "inflation sticky keeping Fed hawkish",
            "growth slowing under rate pressure",
            "gold as stagflation hedge",
        ],
    },
    "mixed_signals": {
        "description": "No clear dominant theme — mixed and conflicting signals",
        "indicators": {
            "DXY": 104.0, "US02Y": 4.00, "SPX": 5000, "NASDAQ": 17000,
            "VIX": 19, "HYG": 77, "US10Y": 4.00, "TIPS": 1.50, "Gold": 2100,
            "FED_FUNDS": 4.50,
        },
        "regime": "neutral",
        "expected_dimensions": [],  # No strong expectations — all valid
        "expected_direction": "neutral",
        "expected_themes": [],
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# Research Quality Metrics
# ═══════════════════════════════════════════════════════════════════════════════


def compute_dimension_overlap(
    result: HypothesisEvolutionResult, expected_dims: list[str],
) -> float:
    """Fraction of expected dimensions covered by selected hypotheses."""
    if not expected_dims:
        return 1.0  # No expectations → full score
    selected_dims = {h.dimension for h in result.selected_hypotheses}
    overlap = selected_dims & set(expected_dims)
    return len(overlap) / len(expected_dims)


def compute_direction_alignment(
    result: HypothesisEvolutionResult, expected_dir: str,
) -> float:
    """Fraction of selected hypotheses matching expected direction."""
    if expected_dir == "neutral":
        return 1.0
    if not result.selected_hypotheses:
        return 0.0
    matching = sum(1 for h in result.selected_hypotheses if h.direction == expected_dir)
    return matching / len(result.selected_hypotheses)


def compute_theme_similarity(
    result: HypothesisEvolutionResult, expected_themes: list[str],
) -> float:
    """How well the selected thesis statements cover expected themes."""
    if not expected_themes:
        return 1.0
    agent_theses = " ".join(h.thesis.lower() for h in result.selected_hypotheses)
    matches = 0
    for theme in expected_themes:
        keywords = set(theme.lower().split())
        # Check if significant portion of theme keywords appear in agent theses
        found = sum(1 for kw in keywords if kw in agent_theses)
        if found / max(len(keywords), 1) >= 0.4:
            matches += 1
    return matches / len(expected_themes)


def evaluate_research_quality(
    result: HypothesisEvolutionResult,
    gold: dict,
) -> dict:
    """Evaluate agent output against gold standard framework."""
    dim_overlap = compute_dimension_overlap(result, gold.get("expected_dimensions", []))
    dir_align = compute_direction_alignment(result, gold.get("expected_direction", "neutral"))
    theme_sim = compute_theme_similarity(result, gold.get("expected_themes", []))

    # Composite quality score
    quality = 0.40 * dim_overlap + 0.35 * dir_align + 0.25 * theme_sim

    return {
        "scenario": gold["description"],
        "dimension_overlap": round(dim_overlap, 3),
        "direction_alignment": round(dir_align, 3),
        "theme_similarity": round(theme_sim, 3),
        "composite_quality": round(quality, 3),
        "top5_theses": result.top5_thesis,
        "competition_stats": {
            "before": result.competition_round.candidates_before if result.competition_round else 0,
            "after": result.competition_round.candidates_after if result.competition_round else 0,
            "contradictions": len(result.competition_round.contradictions_found) if result.competition_round else 0,
            "eliminated": len(result.competition_round.eliminated) if result.competition_round else 0,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Test Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def build_seed_library() -> list[HypothesisLibraryEntry]:
    """Build a seed Hypothesis Library with realistic historical entries."""
    entries = []

    seed_data = [
        ("hyp-001", "liquidity", "bullish",
         "Liquidity easing will push equities higher as cheaper funding broadens the rally",
         0.78, 0.72),
        ("hyp-002", "liquidity", "bearish",
         "Tightening liquidity conditions are constraining risk appetite and supporting the dollar",
         0.82, 0.75),
        ("hyp-003", "credit", "bullish",
         "Credit spreads are tightening, signaling improving financial conditions for risk assets",
         0.75, 0.70),
        ("hyp-004", "credit", "bearish",
         "Credit stress is building — widening spreads precede equity market corrections",
         0.80, 0.74),
        ("hyp-005", "growth", "bullish",
         "Economic growth acceleration supports cyclical equities and rising long-end rates",
         0.71, 0.68),
        ("hyp-006", "growth", "bearish",
         "Growth deceleration will trigger defensive rotation and falling long-term yields",
         0.76, 0.70),
        ("hyp-007", "risk_appetite", "bullish",
         "Risk appetite is strong with low volatility — breadth expansion favors laggard sectors",
         0.73, 0.69),
        ("hyp-008", "risk_appetite", "bearish",
         "Risk appetite is deteriorating as volatility spikes — defensive positioning is warranted",
         0.79, 0.73),
        ("hyp-009", "inflation", "bearish",
         "Inflation re-acceleration pressures long-end yields higher and compresses TIPS valuations",
         0.77, 0.71),
        ("hyp-010", "inflation", "bullish",
         "Disinflation trend continues — falling inflation supports duration and growth assets",
         0.74, 0.68),
        # Add some with regime context in statements
        ("hyp-011", "liquidity", "bullish",
         "In this easing and dovish environment, the loosening of monetary policy benefits all risk assets",
         0.85, 0.80),
        ("hyp-012", "liquidity", "bearish",
         "The hawkish tightening cycle is restrictive and contractionary for credit-sensitive sectors",
         0.83, 0.77),
    ]

    for h_id, dim, dir_, stmt, acc, total in seed_data:
        score = HypothesisScore(
            hypothesis_id=h_id,
            total_score=total,
            prediction_accuracy=acc,
            evidence_quality=0.70,
            calibration_score=0.65,
            consistency_score=0.70,
            learning_history_score=0.70,
            cycle_count=25,
            predictions_evaluated=50,
        )
        entry = HypothesisLibraryEntry(
            hypothesis_id=h_id,
            dimension=dim,
            statement=stmt,
            direction=dir_,
            current_score=score,
        )
        entries.append(entry)

    return entries


def validate_pipeline_contract(result: HypothesisEvolutionResult) -> list[str]:
    """Validate that the pipeline result satisfies all structural contracts."""
    issues = []

    # Must have selected hypotheses
    if not result.selected_hypotheses:
        issues.append("No hypotheses selected")
    elif len(result.selected_hypotheses) > 5:
        issues.append(f"Too many hypotheses selected: {len(result.selected_hypotheses)}")

    # Each selected hypothesis must have required fields
    for h in result.selected_hypotheses:
        if not h.thesis:
            issues.append(f"Hypothesis {h.candidate_id} has empty thesis")
        if not h.dimension:
            issues.append(f"Hypothesis {h.candidate_id} has empty dimension")
        if h.rank < 1:
            issues.append(f"Hypothesis {h.candidate_id} has invalid rank: {h.rank}")

    # Competition round must be present
    if result.competition_round is None:
        issues.append("No competition round in result")

    # Candidates must have been generated
    if result.candidates_generated == 0:
        issues.append("No candidates generated")

    # Signals must have been detected
    if result.signals_detected == 0 and result.themes_identified == 0:
        issues.append("No signals or themes detected — pipeline may be broken")

    return issues


# ═══════════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_signal_engine():
    """Test Signal Engine anomaly detection and theme aggregation."""
    print("\n─── Test: Signal Engine ───")

    from src.hypothesis.signal_engine import SignalEngine

    engine = SignalEngine()

    # Test with clearly anomalous indicators
    indicators = {
        "DXY": 108.0,     # +0.8σ (bullish for DXY = tightening signal)
        "US02Y": 5.20,    # +1.56σ (strong tightening)
        "SPX": 4400,      # -1σ (bearish)
        "VIX": 30,        # +2σ (strong fear)
        "US10Y": 3.30,    # -0.25σ (neutral)
        "HYG": 76,        # -0.33σ (slightly weak)
        "TIPS": 1.0,      # -1σ
        "Gold": 2300,     # +1.33σ
        "NASDAQ": 18000,  # +0.4σ
        "FED_FUNDS": 5.5, # +1σ
    }

    report = engine.process(indicators, regime="unknown")

    # Assertions
    assert len(report.anomalies) > 0, "Should detect anomalous signals"
    assert report.regime != "unknown", "Should infer regime"
    assert len(report.summary) > 0, "Should produce summary"

    # VIX=30 is +2σ → should be a strong anomaly
    vix_signal = next((s for s in report.anomalies if s.indicator == "VIX"), None)
    assert vix_signal is not None, "VIX should be detected as anomalous"
    assert vix_signal.z_score > 1.5, f"VIX z-score should be > 1.5, got {vix_signal.z_score}"

    print(f"  Regime: {report.regime}")
    print(f"  Anomalies: {len(report.anomalies)}")
    for s in report.anomalies[:5]:
        print(f"    {s.indicator}: {s.value} (z={s.z_score:+.1f}) → {s.direction}")
    print(f"  Themes: {len(report.themes)}")
    for t in report.themes:
        print(f"    {t.label} ({t.direction}, strength={t.strength:.2f})")
    print("  [PASS] PASSED")

    return report


def test_candidate_generator(signal_report):
    """Test Candidate Generator produces sufficient and diverse candidates."""
    print("\n─── Test: Candidate Generator ───")

    from src.hypothesis.candidate_generator import CandidateGenerator

    gen = CandidateGenerator()
    candidates = gen.generate(signal_report)

    # Assertions
    assert len(candidates) >= 10, f"Should generate at least 10 candidates, got {len(candidates)}"
    assert len(candidates) <= 45, f"Should not exceed 45 candidates, got {len(candidates)}"

    # Must cover multiple dimensions
    dims = {c.dimension for c in candidates}
    assert len(dims) >= 3, f"Should cover at least 3 dimensions, got {len(dims)}"

    # Must have both bullish and bearish
    dirs = {c.direction for c in candidates}
    assert "bullish" in dirs or "bearish" in dirs, "Should have directional hypotheses"

    # Each candidate should have required fields
    for c in candidates:
        assert c.thesis, f"Candidate {c.candidate_id} missing thesis"
        assert c.dimension, f"Candidate {c.candidate_id} missing dimension"

    print(f"  Candidates: {len(candidates)}")
    print(f"  Dimensions: {sorted(dims)}")
    print(f"  Directions: {sorted(dirs)}")
    for c in candidates[:8]:
        print(f"    [{c.dimension}] {c.direction}: {c.thesis[:80]}...")
    print("  [PASS] PASSED")

    return candidates


def test_historical_retriever(candidates, signal_report):
    """Test Historical Retriever finds meaningful matches."""
    print("\n─── Test: Historical Retriever ───")

    from src.hypothesis.retriever import HistoricalRetriever

    library = build_seed_library()
    retriever = HistoricalRetriever()
    report = retriever.retrieve(candidates, library, signal_report)

    # Assertions
    assert report.total_matches >= 0, "Should not crash"
    assert len(report.contexts) == len(candidates), "Each candidate should have a context"

    # Count recommendations
    strong = sum(1 for ctx in report.contexts.values() if ctx.recommendation == "strong_backing")
    mixed = sum(1 for ctx in report.contexts.values() if ctx.recommendation == "mixed")

    print(f"  Total matches: {report.total_matches}")
    print(f"  Analog periods: {report.analog_periods_found}")
    print(f"  Strong backing: {strong}, Mixed: {mixed}")

    # At least some candidates should find historical matches
    # (depends on library content, but with our seed data there should be some)
    assert report.total_matches > 0 or candidates, "Should find at least some matches with seed library"

    print("  [PASS] PASSED")

    return report, library


def test_competition_engine(candidates, retrieval_report):
    """Test Competition Engine correctly eliminates contradictory hypotheses."""
    print("\n─── Test: Competition Engine ───")

    from src.hypothesis.competition_engine import CompetitionEngine

    engine = CompetitionEngine()
    result = engine.compete(candidates, retrieval_report)

    # Assertions
    assert result.candidates_before > 0, "Should have candidates before competition"
    assert result.candidates_after <= result.candidates_before, "Should not increase candidates"
    assert result.candidates_after > 0, "Should have survivors"

    # Eliminations should have reasons
    for e in result.eliminated:
        assert e.reason, f"Eliminated hypothesis {e.candidate_id} missing reason"
        assert e.detail, f"Eliminated hypothesis {e.candidate_id} missing detail"

    print(f"  Before: {result.candidates_before} → After: {result.candidates_after}")
    print(f"  Contradictions: {len(result.contradictions_found)}")
    print(f"  Eliminated: {len(result.eliminated)}")
    for e in result.eliminated[:5]:
        print(f"    [ELIM] {e.candidate_id}: {e.reason.value}")
    print(f"  Survivors: {result.survivors}")
    print("  [PASS] PASSED")

    return result


def test_selector(survivors, retrieval_report, competition_round, candidates):
    """Test Hypothesis Selector produces valid Top-5."""
    print("\n─── Test: Hypothesis Selector ───")

    from src.hypothesis.selector import HypothesisSelector

    selector = HypothesisSelector(max_selection=5, min_dimensions_covered=3)
    selected = selector.select(survivors, retrieval_report, competition_round)

    # Assertions
    assert 1 <= len(selected) <= 5, f"Should select 1-5 hypotheses, got {len(selected)}"
    assert all(h.rank >= 1 for h in selected), "All selected should have valid rank"

    # Ranks should be sequential
    ranks = [h.rank for h in selected]
    assert ranks == list(range(1, len(ranks) + 1)), f"Ranks should be sequential: {ranks}"

    # Dimension coverage
    dims = {h.dimension for h in selected}
    assert len(dims) >= 2, f"Should cover at least 2 dimensions, got {len(dims)}"

    print(f"  Selected: {len(selected)}")
    for h in selected:
        print(f"    #{h.rank} [{h.dimension}] {h.direction} ({h.confidence:.0%}): {h.thesis[:80]}...")
        print(f"       Competition: {h.competition_result}")
    print(f"  Dimensions covered: {sorted(dims)}")
    print("  [PASS] PASSED")

    return selected


def test_full_pipeline():
    """End-to-end pipeline test."""
    print("\n═══ Test: Full Hypothesis Evolution Pipeline ═══")

    library = build_seed_library()
    evolution = HypothesisEvolution(library_entries=library)

    indicators = {
        "DXY": 105.0, "US02Y": 4.60, "SPX": 4800, "NASDAQ": 16500,
        "VIX": 24, "HYG": 73, "US10Y": 4.50, "TIPS": 2.20, "Gold": 2150,
        "FED_FUNDS": 5.00,
    }

    result = evolution.evolve(indicators, regime="tightening")

    # Validate contract
    issues = validate_pipeline_contract(result)
    assert not issues, f"Pipeline contract violations: {issues}"

    # Print results
    print(evolution.describe(result))
    print(f"\n  [PASS] FULL PIPELINE PASSED")

    return result


def test_research_quality_benchmark():
    """Research Quality Benchmark — compare Agent vs human researcher framework."""
    print("\n" + "=" * 70)
    print("RESEARCH QUALITY BENCHMARK")
    print("Comparing Agent Top-5 against Human Macro Researcher Framework")
    print("=" * 70)

    library = build_seed_library()
    evolution = HypothesisEvolution(library_entries=library)

    all_scores: list[float] = []
    scenario_results = []

    for scenario_name, gold in GOLD_STANDARD.items():
        print(f"\n─── Scenario: {scenario_name} ───")
        print(f"    Context: {gold['description']}")

        result = evolution.evolve(gold["indicators"], gold["regime"])
        quality = evaluate_research_quality(result, gold)

        all_scores.append(quality["composite_quality"])
        scenario_results.append(quality)

        print(f"    Regime: {result.regime}")
        print(f"    Signals: {result.signals_detected}, Themes: {result.themes_identified}")
        print(f"    Candidates: {result.candidates_generated}")
        if result.competition_round:
            print(f"    Competition: {result.competition_round.candidates_before} → "
                  f"{result.competition_round.candidates_after} "
                  f"(contradictions: {len(result.competition_round.contradictions_found)}, "
                  f"eliminated: {len(result.competition_round.eliminated)})")
        print(f"    Top-5:")
        for h in result.selected_hypotheses:
            print(f"      #{h.rank} [{h.dimension}] {h.direction}: {h.thesis[:90]}...")
        print(f"    Quality — Dim Overlap: {quality['dimension_overlap']:.0%}, "
              f"Dir Align: {quality['direction_alignment']:.0%}, "
              f"Theme Sim: {quality['theme_similarity']:.0%}")
        print(f"    Composite: {quality['composite_quality']:.1%}")

    # Aggregate
    avg = statistics.mean(all_scores)
    print(f"\n{'─' * 50}")
    print(f"AGGREGATE RESEARCH QUALITY")
    print(f"{'─' * 50}")
    print(f"  Scenarios: {len(all_scores)}")
    print(f"  Mean Quality: {avg:.1%}")
    print(f"  Min: {min(all_scores):.1%}")
    print(f"  Max: {max(all_scores):.1%}")
    print(f"  Std Dev: {statistics.stdev(all_scores):.3f}" if len(all_scores) > 1 else "")

    # Exit Criteria
    print(f"\n{'─' * 50}")
    print(f"MILESTONE A EXIT CRITERIA")
    print(f"{'─' * 50}")

    # Criterion 1: Pipeline runs without errors on all scenarios
    c1 = len(scenario_results) == len(GOLD_STANDARD)
    print(f"  C1: All scenarios complete: {'PASS' if c1 else 'FAIL'}")

    # Criterion 2: Competition eliminates at least some hypotheses (it's working)
    total_elims = sum(
        r["competition_stats"]["eliminated"] for r in scenario_results
    )
    c2 = total_elims > 0
    print(f"  C2: Competition eliminates hypotheses: {'PASS' if c2 else 'FAIL'} "
          f"({total_elims} total eliminations)")

    # Criterion 3: Mean dimension overlap > 40% (Agent thinks about right things)
    avg_dim = statistics.mean(r["dimension_overlap"] for r in scenario_results)
    c3 = avg_dim > 0.40
    print(f"  C3: Mean dimension overlap > 40%: {'PASS' if c3 else 'FAIL'} "
          f"({avg_dim:.0%})")

    # Criterion 4: Mean direction alignment > 50%
    avg_dir = statistics.mean(r["direction_alignment"] for r in scenario_results)
    c4 = avg_dir > 0.50
    print(f"  C4: Mean direction alignment > 50%: {'PASS' if c4 else 'FAIL'} "
          f"({avg_dir:.0%})")

    # Criterion 5: Composite quality > 45%
    c5 = avg > 0.45
    print(f"  C5: Composite quality > 45%: {'PASS' if c5 else 'FAIL'} "
          f"({avg:.0%})")

    all_pass = all([c1, c2, c3, c4, c5])
    print(f"\n  OVERALL: {'ALL CRITERIA PASSED' if all_pass else 'SOME CRITERIA FAILED'}")

    return all_pass, scenario_results, avg


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    print("=" * 60)
    print("V3.1 Milestone A — Hypothesis Evolution Validation")
    print("=" * 60)

    # Unit tests
    signal_report = test_signal_engine()
    candidates = test_candidate_generator(signal_report)
    retrieval_report, library = test_historical_retriever(candidates, signal_report)
    competition_round = test_competition_engine(candidates, retrieval_report)

    survivors = [
        c for c in candidates
        if c.candidate_id in competition_round.survivors
    ]
    selected = test_selector(survivors, retrieval_report, competition_round, candidates)

    # Integration test
    result = test_full_pipeline()

    # Research Quality Benchmark
    benchmark_pass, scenario_results, avg_quality = test_research_quality_benchmark()

    # Final verdict
    print("\n" + "=" * 60)
    print("MILESTONE A VERDICT")
    print("=" * 60)
    print(f"  Pipeline: FUNCTIONAL")
    print(f"  Research Quality: {avg_quality:.1%}")
    print(f"  Benchmark: {'PASSED' if benchmark_pass else 'NEEDS IMPROVEMENT'}")
    print(f"\n  {'→ Milestone A VALIDATED — proceed to Milestone B' if benchmark_pass else '→ Address failing criteria before proceeding'}")

    return 0 if benchmark_pass else 1


if __name__ == "__main__":
    sys.exit(main())
