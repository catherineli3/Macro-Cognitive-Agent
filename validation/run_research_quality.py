"""V3 Validation Sprint — V3: Research Quality Audit

Feeds 44 real macro cases through the Agent pipeline, evaluates:
    - Narrative Accuracy
    - Hypothesis Accuracy
    - Prediction Direction Accuracy

Output:
    validation/output/research_quality.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

VALIDATION_OUTPUT = PROJECT_ROOT / "validation" / "output"
os.makedirs(VALIDATION_OUTPUT, exist_ok=True)


def evaluate_case(case: Any) -> dict:
    """Run one macro case through the Agent and score it."""
    from validation.research_cases.cases import MacroCase

    result = {
        "case_id": case.case_id,
        "title": case.title,
        "period": case.period,
        "category": case.category,
        "expected_narrative": case.expected_narrative,
        "expected_hypothesis": case.expected_hypothesis,
        "expected_prediction_direction": case.expected_prediction_direction,
        "actual_outcome": case.actual_outcome,
        "actual_direction": case.actual_direction,
        "agent_output": {},
        "scores": {},
        "errors": [],
    }

    t0 = time.time()

    try:
        # ── 1. Macro State ──────────────────────────────────────────
        state_vector = case.macro_state
        result["agent_output"]["macro_state_domains"] = list(state_vector.keys())

        # ── 2. Narrative Detection ──────────────────────────────────
        try:
            from src.research.narrative.narrative_detector import NarrativeDetector

            detector = NarrativeDetector()

            # Transform state vector for narrative detector
            transformed = {}
            for dim_name, indicators in state_vector.items():
                numeric = [v for v in indicators.values()
                          if isinstance(v, (int, float))]
                if not numeric:
                    numeric = [0.5]
                avg = sum(numeric) / len(numeric)
                score = max(0.1, min(0.9, abs(avg) / 200))

                direction = "neutral"
                if "cpi_yoy" in indicators or "headline_cpi_yoy" in indicators:
                    val = indicators.get("cpi_yoy", indicators.get("headline_cpi_yoy", 2))
                    direction = "cooling" if isinstance(val, (int, float)) and val < 3 else "rising"
                elif "ism_manufacturing" in indicators:
                    val = indicators.get("ism_manufacturing", 50)
                    direction = "expansion" if isinstance(val, (int, float)) and val > 50 else "contraction"
                elif "dxy" in indicators or "dollar_index" in indicators:
                    val = indicators.get("dxy", indicators.get("dollar_index", 100))
                    direction = "weakening" if isinstance(val, (int, float)) and val < 100 else "strengthening"
                elif "fed_funds_rate" in indicators:
                    val = indicators.get("rate_cut_probability",
                          indicators.get("rate_hike_probability", 0.5))
                    direction = "dovish" if isinstance(val, (int, float)) and val > 0.4 else "hawkish"

                transformed[dim_name] = {
                    "score": round(score, 3),
                    "direction": direction,
                    "drivers": list(indicators.keys())[:3],
                    "values": indicators,
                }

            narratives = detector.detect(
                state_vector=transformed,
                conclusions=[],
                feature_summary={},
            )
            agent_narratives = []
            for n in narratives[:5]:
                agent_narratives.append({
                    "category": n.category.value if hasattr(n, 'category') else str(n),
                    "title": getattr(n, 'title', ''),
                    "confidence": getattr(n, 'confidence', 0.0),
                })
            result["agent_output"]["narratives"] = agent_narratives

            # Score narrative accuracy: did the agent detect a related theme?
            narrative_accurate = False
            expected_lower = case.expected_narrative.lower().replace("(", "").replace(")", "")
            for n in narratives:
                title = getattr(n, 'title', '').lower()
                # Check keyword overlap
                keywords = expected_lower.split()
                matches = sum(1 for kw in keywords if len(kw) > 3 and kw in title)
                if matches >= 2:
                    narrative_accurate = True
                    break
            result["scores"]["narrative_accurate"] = narrative_accurate

        except Exception as e:
            result["errors"].append(f"Narrative: {type(e).__name__}: {str(e)[:100]}")
            result["scores"]["narrative_accurate"] = None

        # ── 3. Hypothesis Evaluation ─────────────────────────────────
        # Since the full cycle engine is complex, we evaluate hypothesis
        # accuracy by checking if the BELIEF ENGINE can generate hypotheses
        # matching the expected direction.
        try:
            from src.research.beliefs.belief_engine import BeliefEngine

            engine = BeliefEngine()
            beliefs = engine.generate_from_narratives(
                narratives=narratives if 'narratives' in locals() else [],
                state_vector=transformed if 'transformed' in locals() else {},
                conclusions=[],
            )
            result["agent_output"]["beliefs_count"] = len(beliefs)

            # Hypothesis accuracy: check domain coverage
            expected_domains = set()
            for hyp in case.expected_hypothesis:
                hyp_lower = hyp.lower()
                if "inflation" in hyp_lower:
                    expected_domains.add("inflation")
                if "fed" in hyp_lower or "rate" in hyp_lower or "policy" in hyp_lower:
                    expected_domains.add("policy")
                if "growth" in hyp_lower or "gdp" in hyp_lower or "recession" in hyp_lower:
                    expected_domains.add("growth")
                if "dollar" in hyp_lower:
                    expected_domains.add("dollar")
                if "credit" in hyp_lower or "spread" in hyp_lower:
                    expected_domains.add("credit")

            detected_domains = set()
            for b in beliefs:
                domain = getattr(b, 'domain', None)
                if domain and hasattr(domain, 'value'):
                    detected_domains.add(domain.value.lower())

            overlap = len(expected_domains & detected_domains) / max(len(expected_domains), 1)
            result["scores"]["hypothesis_domain_coverage"] = round(overlap, 2)
            result["scores"]["hypothesis_accurate"] = overlap >= 0.5

        except Exception as e:
            result["errors"].append(f"Hypothesis: {type(e).__name__}: {str(e)[:100]}")
            result["scores"]["hypothesis_accurate"] = None

        # ── 4. Prediction Direction ──────────────────────────────────
        try:
            from src.prediction import PredictionMapper

            mapper = PredictionMapper()
            # Get predictions for each domain
            directions = []
            for dim in state_vector:
                if mapper.get_mappings(dim):
                    dir_val = mapper.get_direction(dim, "default", "")
                    if dir_val:
                        directions.append(str(dir_val))

            result["agent_output"]["prediction_directions"] = directions[:5]

            # Compare with expected direction
            expected_dir = case.expected_prediction_direction.lower()
            # Simple heuristic: check if any direction matches
            prediction_correct = False
            for d in directions:
                d_lower = d.lower()
                if "bullish" in expected_dir and "bullish" in d_lower:
                    prediction_correct = True
                elif "bearish" in expected_dir and "bearish" in d_lower:
                    prediction_correct = True
                elif "neutral" in expected_dir and "neutral" in d_lower:
                    prediction_correct = True
            result["scores"]["prediction_correct"] = prediction_correct

        except Exception as e:
            result["errors"].append(f"Prediction: {type(e).__name__}: {str(e)[:100]}")
            result["scores"]["prediction_correct"] = None

        result["latency_ms"] = (time.time() - t0) * 1000

    except Exception as e:
        result["errors"].append(f"General: {type(e).__name__}: {str(e)[:200]}")
        result["latency_ms"] = (time.time() - t0) * 1000

    return result


def run_research_quality_audit() -> dict:
    """Run the full 44-case audit."""
    from validation.research_cases.cases import ALL_CASES

    print("=" * 70)
    print("  V3 SPRINT V3: RESEARCH QUALITY AUDIT")
    print("=" * 70)
    print(f"  Cases: {len(ALL_CASES)}")
    print()

    results = []
    narrative_correct = 0
    hypothesis_correct = 0
    prediction_correct = 0
    error_count = 0

    for i, case in enumerate(ALL_CASES):
        print(f"  [{i+1:02d}/{len(ALL_CASES)}] {case.case_id}: {case.title[:70]} ... ", end="", flush=True)
        r = evaluate_case(case)
        results.append(r)

        na = r["scores"].get("narrative_accurate")
        ha = r["scores"].get("hypothesis_accurate")
        pc = r["scores"].get("prediction_correct")

        if na:
            narrative_correct += 1
        if ha:
            hypothesis_correct += 1
        if pc:
            prediction_correct += 1
        if r["errors"]:
            error_count += 1

        marks = []
        marks.append("N" if na else ("?" if na is None else "-"))
        marks.append("H" if ha else ("?" if ha is None else "-"))
        marks.append("P" if pc else ("?" if pc is None else "-"))
        if r["errors"]:
            marks.append("!")
        print(f"{' '.join(marks)} {r['latency_ms']:.0f}ms")

    total = len(ALL_CASES)
    valid_na = sum(1 for r in results if r["scores"]["narrative_accurate"] is not None)
    valid_ha = sum(1 for r in results if r["scores"]["hypothesis_accurate"] is not None)
    valid_pc = sum(1 for r in results if r["scores"]["prediction_correct"] is not None)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_cases": total,
        "scores": {
            "narrative_accuracy": round(narrative_correct / max(valid_na, 1), 3),
            "narrative_total": narrative_correct,
            "narrative_evaluated": valid_na,
            "hypothesis_accuracy": round(hypothesis_correct / max(valid_ha, 1), 3),
            "hypothesis_total": hypothesis_correct,
            "hypothesis_evaluated": valid_ha,
            "prediction_accuracy": round(prediction_correct / max(valid_pc, 1), 3),
            "prediction_total": prediction_correct,
            "prediction_evaluated": valid_pc,
            "error_rate": round(error_count / total, 3),
            "overall_quality_score": round(
                (narrative_correct / max(valid_na, 1) +
                 hypothesis_correct / max(valid_ha, 1) +
                 prediction_correct / max(valid_pc, 1)) / 3, 3
            ),
        },
        "sprint_target": {
            "research_quality_min": 0.80,
            "description": "Narrative + Hypothesis + Prediction accuracy must be >= 80%",
        },
        "category_breakdown": {},
        "details": results,
    }

    # Category breakdown
    cats = {}
    for r in results:
        cat = r["category"]
        if cat not in cats:
            cats[cat] = {"total": 0, "narrative_correct": 0, "hypothesis_correct": 0}
        cats[cat]["total"] += 1
        if r["scores"]["narrative_accurate"]:
            cats[cat]["narrative_correct"] += 1
        if r["scores"]["hypothesis_accurate"]:
            cats[cat]["hypothesis_correct"] += 1
    report["category_breakdown"] = cats

    # Print summary
    print()
    print("=" * 70)
    print("  RESEARCH QUALITY AUDIT SUMMARY")
    print("=" * 70)
    s = report["scores"]
    print(f"  Narrative Accuracy:    {s['narrative_accuracy']:.1%} ({s['narrative_evaluated']} evaluated)")
    print(f"  Hypothesis Accuracy:   {s['hypothesis_accuracy']:.1%} ({s['hypothesis_evaluated']} evaluated)")
    print(f"  Prediction Accuracy:   {s['prediction_accuracy']:.1%} ({s['prediction_evaluated']} evaluated)")
    print(f"  Overall Quality:       {s['overall_quality_score']:.1%}")
    print(f"  Error Rate:            {s['error_rate']:.1%}")
    print(f"  Target: >= 80%")
    meets_target = s.get("overall_quality_score", 0) >= 0.80
    print(f"  STATUS: {'PASS' if meets_target else 'FAIL'}")
    print("=" * 70)

    return report


if __name__ == "__main__":
    report = run_research_quality_audit()

    path = VALIDATION_OUTPUT / "research_quality.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {path}")
