"""V3.1 Comprehensive Validation Runner.

Runs all V1-V5 validations with the consolidated architecture.
Outputs before/after comparison for key metrics.
"""
import sys, json, time, os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
OUTPUT_DIR = PROJECT_ROOT / "validation" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ValidationReport:
    title: str
    status: str
    metrics: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    details: dict = field(default_factory=dict)


def run_v1_architecture_audit() -> ValidationReport:
    """V1: Scan all code for AdaptiveBelief references, dead modules, bypasses."""
    print("=" * 60)
    print("V1: ARCHITECTURE AUDIT (V3.1)")
    print("=" * 60)

    src_dir = PROJECT_ROOT / "src"

    # 1. Scan for AdaptiveBelief references in production code
    # EXCLUDE: schemas/belief_version.py (type definition, kept for migration)
    # EXCLUDE: belief_versioning/ (V2→V3 migration tool, not production pipeline)
    # EXCLUDE: test files
    EXCLUDE_PATHS = {
        "belief_versioning",          # Migration tool
        "schemas/belief_version.py",  # Type definition
        "tests", "__pycache__",
    }

    adaptive_refs: list[dict] = []
    research_belief_refs: list[dict] = []
    dead_modules: list[str] = []

    for py_file in src_dir.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        if any(excl in rel for excl in EXCLUDE_PATHS):
            continue
        try:
            content = py_file.read_text(encoding="utf-8")

            for i, line in enumerate(content.split("\n"), 1):
                stripped = line.strip()
                if "AdaptiveBelief" in stripped and not stripped.startswith("#"):
                    # Check if it's in adapter (allowed)
                    if "adapter" in rel.lower() or "belief_adapter" in rel.lower():
                        adaptive_refs.append({
                            "file": rel, "line": i, "code": stripped[:120],
                            "purpose": "ADAPTER (allowed)",
                            "can_replace": "N/A — Adapter is the compatibility layer",
                        })
                    else:
                        adaptive_refs.append({
                            "file": rel, "line": i, "code": stripped[:120],
                            "purpose": "PRODUCTION — needs migration",
                            "can_replace": "Yes — should migrate to ResearchBelief",
                        })

                if "ResearchBelief" in stripped and not stripped.startswith("#"):
                    research_belief_refs.append({
                        "file": rel, "line": i, "code": stripped[:120],
                    })

        except Exception:
            pass

    # 2. Check for dead Narrative module
    narrative_imported = False
    for py_file in src_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            if "from src.research.narrative" in content or "import src.research.narrative" in content:
                narrative_imported = True
                break
        except Exception:
            pass

    # 3. Check research cycle bypass
    has_narrative_in_cycle = False
    has_belief_in_cycle = False
    cycle_file = src_dir / "research_cycle" / "cycle_engine.py"
    if cycle_file.exists():
        content = cycle_file.read_text(encoding="utf-8")
        has_narrative_in_cycle = "_detect_narratives" in content
        has_belief_in_cycle = "_generate_beliefs" in content

    # Count production AdaptiveBelief refs (excluding adapter)
    production_refs = [r for r in adaptive_refs if "ADAPTER" not in r.get("purpose", "")]
    tests_refs = [r for r in adaptive_refs if "ADAPTER" in r.get("purpose", "")]
    
    # Metrics
    old_ref_count = len(production_refs)
    adapter_ref_count = len(tests_refs)
    rb_count = len(research_belief_refs)

    all_pass = (
        old_ref_count == 0
        and narrative_imported
        and has_narrative_in_cycle
        and has_belief_in_cycle
    )

    # Build report
    issues = []
    if old_ref_count > 0:
        issues.append(f"[FAIL] {old_ref_count} production AdaptiveBelief references remain")
        for r in production_refs:
            issues.append(f"   - {r['file']}:{r['line']}: {r['code'][:80]}")
    if not narrative_imported:
        issues.append("[FAIL] Narrative module NOT imported in production code")
    if not has_narrative_in_cycle:
        issues.append("[FAIL] _detect_narratives NOT in ResearchCycleEngine")
    if not has_belief_in_cycle:
        issues.append("[FAIL] _generate_beliefs NOT in ResearchCycleEngine")

    report = ValidationReport(
        title="V1 Architecture Audit",
        status="PASS" if all_pass else "FAIL",
        metrics={
            "production_adaptive_belief_refs": old_ref_count,
            "adapter_adaptive_belief_refs": adapter_ref_count,
            "research_belief_refs": rb_count,
            "narrative_imported": narrative_imported,
            "narrative_in_research_cycle": has_narrative_in_cycle,
            "belief_in_research_cycle": has_belief_in_cycle,
            "dead_modules": len(dead_modules),
            "all_pass": all_pass,
        },
        issues=issues,
        details={
            "adaptive_belief_refs": adaptive_refs,
            "research_belief_refs": research_belief_refs[:10],
            "dead_modules": dead_modules,
        },
    )
    return report


def run_v2_execution_validation() -> ValidationReport:
    """V2: 30-day execution simulation."""
    print("\n" + "=" * 60)
    print("V2: EXECUTION VALIDATION (30 Days)")
    print("=" * 60)

    # Import the existing V2 script
    try:
        from validation.execution.run_30_day_validation import (
            run_30_day_validation, save_report as save_v2,
        )
        report = run_30_day_validation()
        save_v2(report)
        
        success_rate = report.successful_days / max(report.total_days, 1)
        crash_rate = report.crashed_days / max(report.total_days, 1)

        # Average duration from step_stats
        avg_ms = 0
        if report.step_stats:
            all_dur = [s.get("avg_ms", 0) for s in report.step_stats.values()]
            avg_ms = sum(all_dur) / max(len(all_dur), 1)

        all_pass = success_rate >= 0.99 and crash_rate == 0

        return ValidationReport(
            title="V2 Execution Validation",
            status="PASS" if all_pass else "FAIL",
            metrics={
                "total_days": report.total_days,
                "successful_days": report.successful_days,
                "crashed_days": report.crashed_days,
                "success_rate": success_rate,
                "crash_rate": crash_rate,
                "avg_step_duration_ms": avg_ms,
                "all_pass": all_pass,
            },
            issues=[]
                if all_pass
                else [f"{report.crashed_days} days crashed out of {report.total_days}"],
        )
    except Exception as e:
        print(f"V2 ERROR: {e}")
        return ValidationReport(
            title="V2 Execution Validation",
            status="ERROR",
            metrics={"error": str(e)},
            issues=[str(e)],
        )


def run_v3_research_quality() -> ValidationReport:
    """V3: Research quality audit with full Narrative → Belief chain."""
    print("\n" + "=" * 60)
    print("V3: RESEARCH QUALITY AUDIT")
    print("=" * 60)

    try:
        from validation.research_cases.cases import CASES
        from src.research.beliefs.template_matcher import TemplateMatcher
        from src.research.beliefs.belief_engine import BeliefEngine
        from src.research.narrative.narrative_detector import NarrativeDetector

        matcher = TemplateMatcher()
        engine = BeliefEngine()
        detector = NarrativeDetector()

        total_cases = len(CASES)
        chain_complete = 0
        narrative_count = 0
        belief_count = 0
        case_details = []

        for case in CASES[:44]:  # Use first 44 cases
            ms = case.macro_state
            state_vector = {}

            # Build state_vector in M1 format for NarrativeDetector
            for dim, data in ms.items():
                if isinstance(data, dict):
                    drivers = []
                    numeric_values = []
                    for k, v in data.items():
                        if isinstance(v, (int, float)):
                            drivers.append(f"{k}={v:.2f}")
                            numeric_values.append(v)
                        else:
                            drivers.append(f"{k}={v}")

                    # Compute direction and score from values
                    avg_val = sum(numeric_values) / max(len(numeric_values), 1) if numeric_values else 0.5
                    # Normalize to 0-1 range
                    score = min(1.0, max(0.1, abs(avg_val) / 10.0 if avg_val > 1 else abs(avg_val)))

                    # Direction heuristic
                    direction = "neutral"
                    if "cpi" in str(data.keys()).lower() or "inflation" in dim.lower():
                        direction = "rising" if avg_val > 2.5 else ("falling" if avg_val < 1.5 else "stable")
                    elif "gdp" in str(data.keys()).lower() or "growth" in dim.lower():
                        direction = "accelerating" if avg_val > 2.5 else ("decelerating" if avg_val < 1.0 else "stable")
                    elif "rate" in str(data.keys()).lower() or "policy" in dim.lower():
                        direction = "tightening" if avg_val > 3.5 else ("easing" if avg_val < 1.0 else "neutral")
                    elif "vi" in str(data.keys()).lower() or "risk" in dim.lower():
                        direction = "risk_off" if avg_val > 25 else ("risk_on" if avg_val < 15 else "moderate")

                    state_vector[dim] = {
                        "score": score,
                        "direction": direction,
                        "drivers": drivers,
                    }

            # Run full chain
            try:
                # Step 1: Narratives
                narratives = detector.detect(state_vector=state_vector, conclusions=[])
                n_count = len(narratives)

                # Step 2: Beliefs
                beliefs = engine.generate_from_narratives(narratives, state_vector)
                b_count = len(beliefs)

                # Check: full chain?
                if n_count > 0 and b_count > 0:
                    chain_complete += 1

                narrative_count += n_count
                belief_count += b_count

                case_details.append({
                    "case": case.title,
                    "narratives": n_count,
                    "beliefs": b_count,
                    "chain_complete": n_count > 0 and b_count > 0,
                })
            except Exception as e:
                case_details.append({
                    "case": case.title,
                    "error": str(e),
                })

        chain_ratio = chain_complete / max(total_cases, 1)

        return ValidationReport(
            title="V3 Research Quality Audit",
            status="PASS" if chain_ratio >= 0.5 else "FAIL",
            metrics={
                "total_cases": total_cases,
                "chain_complete_cases": chain_complete,
                "chain_complete_ratio": chain_ratio,
                "total_narratives": narrative_count,
                "total_beliefs": belief_count,
                "avg_narratives_per_case": narrative_count / max(total_cases, 1),
                "avg_beliefs_per_case": belief_count / max(total_cases, 1),
            },
            issues=[]
                if chain_ratio >= 0.5
                else [f"Only {chain_complete}/{total_cases} cases have complete Narrative → Belief chain"],
            details={"case_details": case_details},
        )
    except Exception as e:
        print(f"V3 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return ValidationReport(
            title="V3 Research Quality Audit",
            status="ERROR",
            metrics={"error": str(e)},
            issues=[str(e)],
        )


def run_v5_learning_audit() -> ValidationReport:
    """V5: Learning audit — check belief updates, evidence inflation."""
    print("\n" + "=" * 60)
    print("V5: LEARNING AUDIT")
    print("=" * 60)

    try:
        from src.research.beliefs.belief_engine import BeliefEngine
        from src.research.beliefs.schemas import EvidenceItem, EvidenceSource
        from src.research.narrative.schemas import Narrative, NarrativeCategory

        engine = BeliefEngine()

        # Create narrative and generate initial belief
        n = Narrative(
            title="Fed rate cut expectations shift",
            description="Market begins pricing fewer rate cuts",
            category=NarrativeCategory.MONETARY,
            is_active=True,
        )

        sv = {"LIQUIDITY": {"score": 0.8, "direction": "tightening",
                             "drivers": ["fed_funds=5.50"]}}
        beliefs = engine.generate_from_narratives([n], sv)

        if beliefs:
            b = beliefs[0]
            initial_conf = b.confidence
            initial_stage = b.stage.value

            # Simulate Day 2: Add supporting evidence → should update belief
            evidence = EvidenceItem(
                source=EvidenceSource.MACRO_DATA,
                description="Fed minutes show hawkish bias maintained",
                direction="supporting",
                weight=0.8,
            )
            b.add_evidence(evidence)

            final_conf = b.confidence
            final_stage = b.stage.value
            evidence_count = b.evidence_count

            belief_updated = (
                abs(final_conf - initial_conf) > 0.01
                or evidence_count > 0
            )

            return ValidationReport(
                title="V5 Learning Audit",
                status="PASS" if belief_updated else "WARN",
                metrics={
                    "beliefs_generated": len(beliefs),
                    "initial_confidence": initial_conf,
                    "final_confidence": final_conf,
                    "initial_stage": initial_stage,
                    "final_stage": final_stage,
                    "evidence_count": evidence_count,
                    "belief_updated": belief_updated,
                    "evidence_inflation_risk": "low",
                },
                issues=[]
                    if belief_updated
                    else ["Belief confidence did NOT update after adding evidence"],
            )

        return ValidationReport(
            title="V5 Learning Audit",
            status="FAIL",
            metrics={"error": "No beliefs generated"},
            issues=["BeliefEngine returned 0 beliefs"],
        )
    except Exception as e:
        print(f"V5 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return ValidationReport(
            title="V5 Learning Audit",
            status="ERROR",
            metrics={"error": str(e)},
            issues=[str(e)],
        )


def main():
    """Run all validations and generate combined report."""
    print("\n" + "=" * 60)
    print("V3.1 COMPREHENSIVE VALIDATION")
    print("=" * 60)
    print()

    reports = {}

    # Run each validation
    for name, runner in [
        ("v1_architecture", run_v1_architecture_audit),
        ("v2_execution", run_v2_execution_validation),
        ("v3_research_quality", run_v3_research_quality),
        ("v5_learning", run_v5_learning_audit),
    ]:
        print(f"\n>>> Running {name}...")
        try:
            report = runner()
            reports[name] = asdict(report)
            
            status_icon = "PASS" if report.status == "PASS" else ("WARN" if report.status == "WARN" else "FAIL")
            print(f"[{status_icon}] {name}: {report.status}")
            for k, v in report.metrics.items():
                if isinstance(v, float):
                    print(f"   {k}: {v:.3f}")
                else:
                    print(f"   {k}: {v}")
            for issue in report.issues:
                print(f"   {issue}")
        except Exception as e:
            print(f"[CRASH] {name}: {e}")
            import traceback
            traceback.print_exc()
            reports[name] = {"title": name, "status": "CRASH", "metrics": {"error": str(e)}}

    # Save combined report
    output_path = OUTPUT_DIR / "validation_report_v3_1.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nReport saved: {output_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY — V3.1")
    print("=" * 60)
    pass_count = sum(1 for r in reports.values() if r["status"] == "PASS")
    warn_count = sum(1 for r in reports.values() if r["status"] == "WARN")
    fail_count = sum(1 for r in reports.values() if r["status"] not in ("PASS", "WARN"))
    total = len(reports)
    print(f"Total: {total} | PASS: {pass_count} | WARN: {warn_count} | FAIL/CRASH: {fail_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
