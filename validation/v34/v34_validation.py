"""V3.4 Macro Research Brain — Comprehensive Validation Suite.

Tests all five V3.4 modules in rule-based mode (LLM-optional):
    1. LLM Brain — ResearchReasoningAgent, ResearchMemo
    2. Reflexivity — MarketBeliefModel, CapitalFlowTracker, ReflexivityCycleDetector
    3. Narrative Memory — Daily persistence + transitions
    4. Expert Debate — Four-persona analysis + synthesis
    5. Integration — Full pipeline end-to-end

Generates V3_4_VALIDATION_REPORT.json with detailed metrics.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import sys
# Add project root to path
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _project_root)

from src.research.llm_brain import (
    ResearchReasoningAgent,
    ReasoningInput,
    ResearchMemo,
    PromptArchitecture,
)
from src.research.reflexivity import (
    MarketBeliefModel,
    CapitalFlowTracker,
    ReflexivityCycleDetector,
)
from src.research.narrative_memory import NarrativeMemory
from src.research.expert_debate import ExpertDebate

# ═══════════════════════════════════════════════════════════════════════════
# Test cases — 10 diverse macro scenarios
# ═══════════════════════════════════════════════════════════════════════════

TEST_CASES = [
    {
        "case_id": "V34-001",
        "label": "2022Q3 Stagflation",
        "market_data": {
            "vix": 32, "dxy": 112, "us10y": 3.8, "us2y": 4.3,
            "spx_ytd": -25, "cpi_yoy": 8.2, "hyg_spread": 550,
            "gold": 1670, "oil": 85, "nasdaq_ytd": -33,
        },
        "regime": "stagflation_lite",
        "dominant_narrative": "Fed will break something — hard landing incoming",
        "competing_narratives": [
            {"title": "Hard landing inevitable", "probability": 0.55},
            {"title": "Soft landing still possible", "probability": 0.25},
            {"title": "1970s-style stagflation", "probability": 0.20},
        ],
        "beliefs": ["Inflation is entrenched", "Fed behind the curve", "Recession likely"],
    },
    {
        "case_id": "V34-002",
        "label": "2023Q4 Goldilocks",
        "market_data": {
            "vix": 13, "dxy": 104, "us10y": 4.2, "us2y": 4.7,
            "spx_ytd": 24, "cpi_yoy": 3.1, "hyg_spread": 350,
            "gold": 2050, "oil": 72, "nasdaq_ytd": 43,
        },
        "regime": "goldilocks",
        "dominant_narrative": "Soft landing achieved — Fed done hiking",
        "competing_narratives": [
            {"title": "Soft landing / no landing", "probability": 0.60},
            {"title": "Inflation could re-accelerate", "probability": 0.20},
            {"title": "Growth to slow sharply in H2", "probability": 0.20},
        ],
        "beliefs": ["Disinflation is real", "Labor market resilient", "Fed pivot coming"],
    },
    {
        "case_id": "V34-003",
        "label": "2020Q1 COVID Crash",
        "market_data": {
            "vix": 82, "dxy": 103, "us10y": 0.5, "us2y": 0.2,
            "spx_ytd": -34, "cpi_yoy": 1.5, "hyg_spread": 1100,
            "gold": 1500, "oil": 20, "nasdaq_ytd": -28,
        },
        "regime": "crisis",
        "dominant_narrative": "Global pandemic — unprecedented economic shutdown",
        "competing_narratives": [
            {"title": "V-shaped recovery on stimulus", "probability": 0.30},
            {"title": "Prolonged depression", "probability": 0.35},
            {"title": "Structural regime change", "probability": 0.35},
        ],
        "beliefs": ["Economic collapse", "Unprecedented stimulus coming", "Deflation risk"],
    },
    {
        "case_id": "V34-004",
        "label": "2024Q2 AI Boom",
        "market_data": {
            "vix": 12, "dxy": 105, "us10y": 4.4, "us2y": 4.9,
            "spx_ytd": 18, "cpi_yoy": 3.4, "hyg_spread": 320,
            "gold": 2350, "oil": 78, "nasdaq_ytd": 25,
        },
        "regime": "ai_boom",
        "dominant_narrative": "AI revolution — transformational technology cycle",
        "competing_narratives": [
            {"title": "AI boom — secular bull market", "probability": 0.50},
            {"title": "AI bubble — dot-com 2.0", "probability": 0.30},
            {"title": "Concentration risk — narrow market", "probability": 0.20},
        ],
        "beliefs": ["AI is transformational", "Valuations stretched but justified", "Fed can wait"],
    },
    {
        "case_id": "V34-005",
        "label": "2015 EM Crisis",
        "market_data": {
            "vix": 28, "dxy": 100, "us10y": 2.3, "us2y": 1.0,
            "spx_ytd": -2, "cpi_yoy": 0.7, "hyg_spread": 700,
            "gold": 1060, "oil": 37, "nasdaq_ytd": 5,
        },
        "regime": "em_crisis",
        "dominant_narrative": "Strong USD crushing EM — China devaluation risk",
        "competing_narratives": [
            {"title": "EM crisis spreading", "probability": 0.45},
            {"title": "Contained — buying opportunity", "probability": 0.30},
            {"title": "Fed can't hike amidst global weakness", "probability": 0.25},
        ],
        "beliefs": ["EM fragile", "China devaluation imminent", "Commodity supercycle over"],
    },
    {
        "case_id": "V34-006",
        "label": "2019Q3 Fed Pivot",
        "market_data": {
            "vix": 16, "dxy": 98, "us10y": 1.7, "us2y": 1.6,
            "spx_ytd": 29, "cpi_yoy": 1.8, "hyg_spread": 380,
            "gold": 1500, "oil": 55, "nasdaq_ytd": 35,
        },
        "regime": "dovish_turn",
        "dominant_narrative": "Fed pivots dovish — rate cuts ahead",
        "competing_narratives": [
            {"title": "Mid-cycle adjustment — more upside", "probability": 0.50},
            {"title": "Late cycle — recession risk building", "probability": 0.30},
            {"title": "Yield curve warning is real", "probability": 0.20},
        ],
        "beliefs": ["Fed insurance cuts", "Growth slowing but not crashing", "Goldilocks returning"],
    },
    {
        "case_id": "V34-007",
        "label": "2008Q4 GFC",
        "market_data": {
            "vix": 80, "dxy": 88, "us10y": 2.2, "us2y": 0.8,
            "spx_ytd": -38, "cpi_yoy": 0.1, "hyg_spread": 2000,
            "gold": 870, "oil": 40, "nasdaq_ytd": -41,
        },
        "regime": "financial_crisis",
        "dominant_narrative": "Systemic financial collapse — deleveraging",
        "competing_narratives": [
            {"title": "Great Depression 2.0", "probability": 0.40},
            {"title": "Policy response will stabilize", "probability": 0.35},
            {"title": "Structural reset — new world order", "probability": 0.25},
        ],
        "beliefs": ["Systemic banking crisis", "Deflationary collapse", "Unprecedented policy response"],
    },
    {
        "case_id": "V34-008",
        "label": "2021Q2 Reflation",
        "market_data": {
            "vix": 18, "dxy": 90, "us10y": 1.5, "us2y": 0.15,
            "spx_ytd": 15, "cpi_yoy": 5.4, "hyg_spread": 300,
            "gold": 1800, "oil": 75, "nasdaq_ytd": 13,
        },
        "regime": "reflation",
        "dominant_narrative": "Transitory inflation — reopening boom",
        "competing_narratives": [
            {"title": "Inflation is transitory", "probability": 0.55},
            {"title": "Inflation is persistent — Fed wrong", "probability": 0.25},
            {"title": "Growth will decelerate naturally", "probability": 0.20},
        ],
        "beliefs": ["Reopening boom", "Inflation transitory", "Fed can be patient"],
    },
    {
        "case_id": "V34-009",
        "label": "2025H1 Tariff Shock",
        "market_data": {
            "vix": 28, "dxy": 107, "us10y": 4.8, "us2y": 4.5,
            "spx_ytd": -8, "cpi_yoy": 4.2, "hyg_spread": 520,
            "gold": 2700, "oil": 65, "nasdaq_ytd": -12,
        },
        "regime": "tariff_shock",
        "dominant_narrative": "Trade war escalation — stagflation risk",
        "competing_narratives": [
            {"title": "Tariff-driven stagflation", "probability": 0.45},
            {"title": "Negotiation outcome positive", "probability": 0.30},
            {"title": "Fed forced to cut despite inflation", "probability": 0.25},
        ],
        "beliefs": ["Trade war damaging growth", "Inflation sticky due to tariffs", "Policy uncertainty extreme"],
    },
    {
        "case_id": "V34-010",
        "label": "Bond Vigilantes Return",
        "market_data": {
            "vix": 22, "dxy": 102, "us10y": 5.2, "us2y": 4.8,
            "spx_ytd": -5, "cpi_yoy": 3.8, "hyg_spread": 480,
            "gold": 2500, "oil": 70, "nasdaq_ytd": -8,
        },
        "regime": "fiscal_risk",
        "dominant_narrative": "Bond vigilantes return — fiscal dominance risk",
        "competing_narratives": [
            {"title": "Fiscal sustainability crisis", "probability": 0.40},
            {"title": "Growth still strong, yields justified", "probability": 0.30},
            {"title": "Fed will cap yields eventually", "probability": 0.30},
        ],
        "beliefs": ["Fiscal path unsustainable", "Bond market voting", "Risk assets repricing"],
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Metrics
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ValidationMetrics:
    """Aggregated V3.4 validation metrics."""

    # Module availability
    llm_brain_ok: bool = False
    reflexivity_ok: bool = False
    narrative_memory_ok: bool = False
    expert_debate_ok: bool = False

    # LLM Brain metrics
    memo_generation_rate: float = 0.0
    memo_structure_completeness: float = 0.0
    avg_memo_confidence: float = 0.0
    falsification_presence_rate: float = 0.0
    avg_causal_depth: float = 0.0

    # Reflexivity metrics
    active_cycles_detected: int = 0
    avg_reinforcement_score: float = 0.0
    avg_vulnerability_score: float = 0.0
    extreme_cycle_rate: float = 0.0

    # Narrative Memory metrics
    entries_recorded: int = 0
    transitions_detected: int = 0
    avg_narrative_entropy: float = 0.0

    # Expert Debate metrics
    debate_consensus_score: float = 0.0
    persona_coverage: int = 0
    avg_synthesis_confidence: float = 0.0

    # Overall
    total_cases: int = 0
    total_duration_ms: float = 0.0
    overall_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "module_availability": {
                "llm_brain": self.llm_brain_ok,
                "reflexivity": self.reflexivity_ok,
                "narrative_memory": self.narrative_memory_ok,
                "expert_debate": self.expert_debate_ok,
            },
            "llm_brain": {
                "memo_generation_rate": round(self.memo_generation_rate, 3),
                "memo_structure_completeness": round(self.memo_structure_completeness, 3),
                "avg_memo_confidence": round(self.avg_memo_confidence, 3),
                "falsification_presence_rate": round(self.falsification_presence_rate, 3),
                "avg_causal_depth": round(self.avg_causal_depth, 3),
            },
            "reflexivity": {
                "active_cycles_detected": self.active_cycles_detected,
                "avg_reinforcement_score": round(self.avg_reinforcement_score, 3),
                "avg_vulnerability_score": round(self.avg_vulnerability_score, 3),
                "extreme_cycle_rate": round(self.extreme_cycle_rate, 3),
            },
            "narrative_memory": {
                "entries_recorded": self.entries_recorded,
                "transitions_detected": self.transitions_detected,
                "avg_narrative_entropy": round(self.avg_narrative_entropy, 3),
            },
            "expert_debate": {
                "debate_consensus_score": round(self.debate_consensus_score, 3),
                "persona_coverage": self.persona_coverage,
                "avg_synthesis_confidence": round(self.avg_synthesis_confidence, 3),
            },
            "overall": {
                "total_cases": self.total_cases,
                "total_duration_ms": round(self.total_duration_ms, 0),
                "overall_score": round(self.overall_score, 3),
            },
        }


# ═══════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════


def check_memo_structure(memo: ResearchMemo) -> dict:
    """Check ResearchMemo structural completeness."""
    checks = {
        "has_executive_summary": bool(memo.executive_summary),
        "has_one_sentence_view": bool(memo.one_sentence_view),
        "has_conviction": bool(memo.conviction_level),
        "has_regime": bool(memo.regime.regime_label),
        "has_regime_confidence": memo.regime.regime_confidence > 0,
        "has_narrative": bool(memo.narrative.dominant_narrative),
        "has_narrative_stage": bool(memo.narrative.narrative_stage),
        "has_causal_chain": bool(memo.causal.primary_causal_chain),
        "has_evidence_score": memo.evidence.evidence_score != 0,
        "has_belief": bool(memo.belief.core_belief),
        "has_falsification": bool(memo.falsification.falsification_conditions),
        "has_assets": bool(memo.assets.asset_views),
        "has_tail_risk": bool(memo.tail_risk.tail_risks),
        "has_confidence_breakdown": bool(memo.confidence.confidence_breakdown),
    }
    checks["completeness"] = sum(checks.values()) / len(checks)
    return checks


def run_validation(output_dir: str = "validation/v34/output") -> dict:
    """Run the complete V3.4 validation suite."""
    os.makedirs(output_dir, exist_ok=True)
    t_total = time.time()

    metrics = ValidationMetrics(total_cases=len(TEST_CASES))
    per_case_results = []

    # ── Initialize all modules ──────────────────────────────────────
    print("=" * 60)
    print("V3.4 MACRO RESEARCH BRAIN — VALIDATION")
    print("=" * 60)

    print("\n[1/4] Initializing LLM Brain...")
    try:
        agent = ResearchReasoningAgent(
            model="gpt-4o",
            reasoning_mode="rule",  # Rule-based for validation
        )
        memory = NarrativeMemory(storage_dir=f"{output_dir}/narrative_memory")
        metrics.llm_brain_ok = True
        metrics.narrative_memory_ok = True
        print("  OK: LLM Brain (rule-based mode) + Narrative Memory")
    except Exception as e:
        print(f"  ERROR: {e}")
        agent = None
        memory = None

    print("\n[2/4] Initializing Reflexivity Engine...")
    try:
        belief_model = MarketBeliefModel()
        flow_tracker = CapitalFlowTracker()
        reflex_detector = ReflexivityCycleDetector()
        metrics.reflexivity_ok = True
        print("  OK: MarketBeliefModel + CapitalFlowTracker + ReflexivityCycleDetector")
    except Exception as e:
        print(f"  ERROR: {e}")
        reflex_detector = None

    print("\n[3/4] Initializing Expert Debate...")
    try:
        debate = ExpertDebate(debate_mode="rule")
        metrics.expert_debate_ok = True
        print("  OK: Expert Debate (rule-based mode)")
    except Exception as e:
        print(f"  ERROR: {e}")
        debate = None

    # ── Run all test cases ──────────────────────────────────────────
    print(f"\n[4/4] Running {len(TEST_CASES)} test cases...")
    print("-" * 60)

    for i, tc in enumerate(TEST_CASES):
        case_id = tc["case_id"]
        label = tc["label"]
        t_case = time.time()
        case_metrics = {}

        print(f"\n  [{i+1}/{len(TEST_CASES)}] {case_id}: {label}")

        # ── Build ReasoningInput ──
        inp = ReasoningInput(
            case_id=case_id,
            regime_label=tc["regime"],
            regime_confidence=0.7,
            regime_dimensions={"label": tc["regime"]},
            market_indicators=tc["market_data"],
            dominant_narrative=tc["dominant_narrative"],
            narrative_confidence=0.6,
            competing_narratives=tc["competing_narratives"],
            core_beliefs=tc["beliefs"],
            belief_confidence=0.55,
            active_mental_models=["dalio_machine", "ptj_momentum", "bridgewater_4q"],
        )

        # ── 1. LLM Brain → ResearchMemo ──
        if agent:
            memo = agent.reason(inp)
            struct_check = check_memo_structure(memo)
            case_metrics["memo"] = {
                "title": memo.title,
                "conviction": memo.conviction_level,
                "structure_completeness": struct_check["completeness"],
                "regime_confidence": memo.regime.regime_confidence,
                "narrative_confidence": memo.narrative.narrative_confidence,
                "has_falsification": struct_check["has_falsification"],
                "has_causal_chain": struct_check["has_causal_chain"],
                "overall_confidence": memo.confidence.overall_confidence,
            }
            print(f"    Memo: '{memo.title[:60]}' | conviction={memo.conviction_level} | "
                  f"structure={struct_check['completeness']:.0%}")

        # ── 2. Reflexivity → Cycle Detection ──
        if reflex_detector:
            beliefs = belief_model.identify_beliefs(tc["market_data"], tc["dominant_narrative"])
            flows = flow_tracker.snapshot(tc["market_data"])
            reflex_report = reflex_detector.detect(
                tc["market_data"],
                beliefs=beliefs,
                flows=flows,
                dominant_narrative=tc["dominant_narrative"],
            )
            case_metrics["reflexivity"] = {
                "cycles_count": len(reflex_report.detected_cycles),
                "reflexivity_score": reflex_report.reflexivity_score,
                "warnings": reflex_report.key_warning_signals[:3],
                "extreme_cycles": sum(1 for c in reflex_report.detected_cycles if c.stage == "extreme"),
                "cycle_stages": [c.stage for c in reflex_report.detected_cycles],
                "belief_count": len(reflex_report.active_beliefs),
            }
            print(f"    Reflexivity: {len(reflex_report.detected_cycles)} cycles, "
                  f"score={reflex_report.reflexivity_score:.2f}, "
                  f"warnings={len(reflex_report.key_warning_signals)}")

        # ── 3. Narrative Memory ──
        if memory:
            entry = memory.record_daily_snapshot(
                dominant_narrative=tc["dominant_narrative"],
                narrative_confidence=0.6,
                competing_narratives=tc["competing_narratives"],
                regime_label=tc["regime"],
            )
            case_metrics["memory"] = {
                "date": entry.date,
                "narrative_entropy": entry.narrative_entropy,
                "narrative_intensity": entry.narrative_intensity,
            }

        # ── 4. Expert Debate ──
        if debate:
            debate_result = debate.debate(
                market_data=tc["market_data"],
                regime_label=tc["regime"],
                dominant_narrative=tc["dominant_narrative"],
                competing_narratives=tc["competing_narratives"],
            )
            case_metrics["debate"] = {
                "personas": len(debate_result.expert_views),
                "consensus_score": debate_result.synthesis.consensus_score,
                "consensus_items": debate_result.synthesis.consensus_views[:3],
                "divergence_count": len(debate_result.synthesis.divergence_views),
                "persona_weights": debate_result.synthesis.persona_weights,
                "synthesis_confidence": debate_result.synthesis.synthesis_confidence,
                "debate_mode": debate_result.debate_mode,
            }
            print(f"    Debate: {len(debate_result.expert_views)} personas, "
                  f"consensus={debate_result.synthesis.consensus_score:.2f}, "
                  f"mode={debate_result.debate_mode}")

        # ── Aggregate metrics ──
        memo_m = case_metrics.get("memo", {})
        if memo_m:
            metrics.memo_generation_rate += 1
            metrics.memo_structure_completeness += memo_m.get("structure_completeness", 0)
            metrics.avg_memo_confidence += memo_m.get("overall_confidence", 0)
            if memo_m.get("has_falsification"):
                metrics.falsification_presence_rate += 1
            if memo_m.get("has_causal_chain"):
                metrics.avg_causal_depth += 1

        reflex_m = case_metrics.get("reflexivity", {})
        if reflex_m:
            metrics.active_cycles_detected += reflex_m.get("cycles_count", 0)
            metrics.avg_reinforcement_score += reflex_m.get("reflexivity_score", 0)
            metrics.extreme_cycle_rate += reflex_m.get("extreme_cycles", 0)

        debate_m = case_metrics.get("debate", {})
        if debate_m:
            metrics.debate_consensus_score += debate_m.get("consensus_score", 0)
            metrics.persona_coverage = max(metrics.persona_coverage, debate_m.get("personas", 0))
            metrics.avg_synthesis_confidence += debate_m.get("synthesis_confidence", 0)

        per_case_results.append({"case_id": case_id, "label": label, "metrics": case_metrics})

    # ── Normalize averages ──
    n = metrics.total_cases
    if n > 0:
        metrics.memo_generation_rate /= n
        metrics.memo_structure_completeness /= n
        metrics.avg_memo_confidence /= n
        metrics.falsification_presence_rate /= n
        metrics.avg_causal_depth /= n
        metrics.avg_reinforcement_score /= n
        metrics.extreme_cycle_rate /= n
        metrics.debate_consensus_score /= n
        metrics.avg_synthesis_confidence /= n

    # Entries and transitions from memory
    if memory:
        metrics.entries_recorded = len(memory.get_history(days=365))
        metrics.transitions_detected = len(memory.get_transitions(days=365))
        history = memory.get_history(days=365)
        if history:
            metrics.avg_narrative_entropy = sum(e.narrative_entropy for e in history) / len(history)

    # ── Overall score ──
    scores = []
    if metrics.llm_brain_ok:
        scores.extend([
            metrics.memo_structure_completeness * 0.15,
            metrics.falsification_presence_rate * 0.10,
            metrics.avg_causal_depth * 0.10,
        ])
    if metrics.reflexivity_ok:
        scores.extend([
            min(metrics.active_cycles_detected / (n * 2), 1.0) * 0.10,
            metrics.avg_reinforcement_score * 0.10,
        ])
    if metrics.narrative_memory_ok:
        scores.append(min(metrics.entries_recorded / n, 1.0) * 0.10)
    if metrics.expert_debate_ok:
        scores.extend([
            metrics.debate_consensus_score * 0.10,
            min(metrics.persona_coverage / 4, 1.0) * 0.05,
        ])
    # Module coverage bonus
    module_count = sum([metrics.llm_brain_ok, metrics.reflexivity_ok, metrics.narrative_memory_ok, metrics.expert_debate_ok])
    scores.append((module_count / 4) * 0.10)

    metrics.total_duration_ms = (time.time() - t_total) * 1000
    metrics.overall_score = sum(scores)

    # ── Print summary ──
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"""
  Module Status:
    LLM Brain:        {'OK' if metrics.llm_brain_ok else 'ERROR'}
    Reflexivity:      {'OK' if metrics.reflexivity_ok else 'ERROR'}
    Narrative Memory: {'OK' if metrics.narrative_memory_ok else 'ERROR'}
    Expert Debate:    {'OK' if metrics.expert_debate_ok else 'ERROR'}

  LLM Brain:
    Memo generation:      {metrics.memo_generation_rate:.1%}
    Structure complete:   {metrics.memo_structure_completeness:.1%}
    Falsification rate:   {metrics.falsification_presence_rate:.1%}
    Causal chain rate:    {metrics.avg_causal_depth:.1%}
    Avg confidence:       {metrics.avg_memo_confidence:.2f}

  Reflexivity:
    Cycles detected:      {metrics.active_cycles_detected}
    Avg reinforcement:    {metrics.avg_reinforcement_score:.2f}
    Extreme cycle rate:   {metrics.extreme_cycle_rate:.1%}

  Narrative Memory:
    Entries recorded:     {metrics.entries_recorded}
    Transitions detected: {metrics.transitions_detected}
    Avg entropy:          {metrics.avg_narrative_entropy:.3f}

  Expert Debate:
    Consensus score:      {metrics.debate_consensus_score:.2f}
    Persona coverage:     {metrics.persona_coverage}/4

  Overall:
    Cases: {metrics.total_cases}
    Duration: {metrics.total_duration_ms:.0f}ms
    OVERALL SCORE: {metrics.overall_score:.2f} / 1.00
""")

    # ── Save results ──
    output = {
        "validation_id": "V3.4",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics.to_dict(),
        "per_case": per_case_results,
    }

    output_path = os.path.join(output_dir, "V3_4_VALIDATION_REPORT.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)

    print(f"Report saved: {output_path}")

    return output


if __name__ == "__main__":
    result = run_validation()
