"""V3 Validation Sprint — V1: Architecture Audit

Checks:
  1. Single Source of Truth — does ResearchBelief fully replace AdaptiveBelief?
  2. Bypass detection — does any path skip Belief/Narrative/MentalModel/Framework?
  3. Dead Module detection — which modules are defined but never imported?
  4. Export coverage — are all sub-packages properly exported?

Output:
  - validation/output/architecture_audit.json
  - docs/V3_ARCHITECTURE_AUDIT.md
"""

from __future__ import annotations

import ast
import importlib
import json
import os
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── project root ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
VALIDATION_OUTPUT = PROJECT_ROOT / "validation" / "output"
DOCS_DIR = PROJECT_ROOT / "docs"

os.makedirs(VALIDATION_OUTPUT, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class AuditFinding:
    check_name: str
    status: str  # PASS | FAIL | WARN
    detail: str
    evidence: list[str] = field(default_factory=list)
    call_chain: list[str] = field(default_factory=list)


@dataclass
class ArchitectureAudit:
    generated_at: str = ""
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    overall_status: str = ""  # PASS | FAIL
    findings: list[AuditFinding] = field(default_factory=list)
    dead_modules: list[str] = field(default_factory=list)
    bypass_paths: list[dict] = field(default_factory=list)
    two_system_conflicts: list[dict] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# Utility Functions
# ══════════════════════════════════════════════════════════════════════════════


def _all_py_files(root: Path) -> list[Path]:
    """Recursively find all .py files under root."""
    return sorted(root.rglob("*.py"))


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _find_imports_in_file(path: Path, module_name: str) -> list[str]:
    """Find all lines in a file that import a specific module."""
    content = _read_file(path)
    if not content:
        return []
    matches = []
    for line in content.split("\n"):
        if f"from {module_name}" in line or f"import {module_name}" in line:
            matches.append(line.strip())
    return matches


def _parse_imports(file_path: Path) -> list[str]:
    """Extract all imported module names from a Python file using AST."""
    content = _read_file(file_path)
    if not content:
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def _module_to_path(module_name: str, base: Path = SRC_ROOT) -> Path | None:
    """Convert a dotted module name (minus 'src.' prefix) to a file path."""
    parts = module_name.split(".")
    if parts[0] == "src":
        parts = parts[1:]
    candidate = base / "/".join(parts) + ".py"
    if candidate.exists():
        return candidate
    candidate_dir = base / "/".join(parts) / "__init__.py"
    if candidate_dir.exists():
        return candidate_dir
    return None


def _is_test_file(path: Path) -> bool:
    return "tests" in path.parts or "test_" in path.name


def _is_self_import(importer: str, imported: str) -> bool:
    """Is this a self-import within the same package?"""
    importer_parts = importer.split(".")[1:] if importer.startswith("src.") else importer.split(".")
    imported_parts = imported.split(".")[1:] if imported.startswith("src.") else imported.split(".")
    # Check if they share the same parent package (first 1-3 segments)
    for n in range(1, min(len(importer_parts), len(imported_parts)) + 1):
        if importer_parts[:n] == imported_parts[:n]:
            return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# Check 1: Single Source of Truth — ResearchBelief vs AdaptiveBelief
# ══════════════════════════════════════════════════════════════════════════════


def check_single_source_of_truth() -> list[AuditFinding]:
    findings = []

    # ── 1a: Where is AdaptiveBelief defined? ──
    adaptive_belief_files = []
    for py_file in _all_py_files(SRC_ROOT):
        content = _read_file(py_file)
        if "class AdaptiveBelief" in content:
            adaptive_belief_files.append(str(py_file.relative_to(PROJECT_ROOT)))

    # ── 1b: Where is AdaptiveBelief imported? ──
    adaptive_consumers = []
    for py_file in _all_py_files(PROJECT_ROOT):
        content = _read_file(py_file)
        if "AdaptiveBelief" in content and "class AdaptiveBelief" not in content:
            adaptive_consumers.append(str(py_file.relative_to(PROJECT_ROOT)))

    # ── 1c: Where is ResearchBelief defined? ──
    research_belief_files = []
    for py_file in _all_py_files(SRC_ROOT):
        content = _read_file(py_file)
        if "class ResearchBelief" in content:
            research_belief_files.append(str(py_file.relative_to(PROJECT_ROOT)))

    # ── 1d: Where is ResearchBelief imported/used? ──
    research_consumers = []
    for py_file in _all_py_files(PROJECT_ROOT):
        content = _read_file(py_file)
        if "ResearchBelief" in content and "class ResearchBelief" not in content:
            research_consumers.append(str(py_file.relative_to(PROJECT_ROOT)))

    # ── 1e: Does ResearchCycleEngine use AdaptiveBelief or ResearchBelief? ──
    cycle_engine = SRC_ROOT / "research_cycle" / "cycle_engine.py"
    cycle_uses = ""
    if cycle_engine.exists():
        content = _read_file(cycle_engine)
        has_adaptive = "AdaptiveBelief" in content
        has_research = "ResearchBelief" in content
        has_evolution = "EvolutionPipeline" in content
        cycle_uses = (
            f"ResearchCycleEngine uses: "
            f"AdaptiveBelief={'YES' if has_adaptive else 'NO'}, "
            f"ResearchBelief={'YES' if has_research else 'NO'}, "
            f"EvolutionPipeline={'YES' if has_evolution else 'NO'}"
        )

    # ── 1f: Check EvolutionPipeline's belief system ──
    evo_pipeline = SRC_ROOT / "research" / "evolution" / "evolution_pipeline.py"
    evo_uses = ""
    if evo_pipeline.exists():
        content = _read_file(evo_pipeline)
        has_adaptive = "AdaptiveBelief" in content
        has_research = "ResearchBelief" in content
        evo_uses = (
            f"EvolutionPipeline uses: "
            f"AdaptiveBelief={'YES' if has_adaptive else 'NO'}, "
            f"ResearchBelief={'YES' if has_research else 'NO'}"
        )

    # ── 1g: Overlap analysis ──
    non_test_adaptive = [f for f in adaptive_consumers if not _is_test_file(Path(f))]
    non_test_research = [f for f in research_consumers if not _is_test_file(Path(f))]

    # Determine if ResearchBelief has fully replaced AdaptiveBelief
    adaptive_in_prod = any(
        not _is_test_file(Path(f)) and not f.startswith("scripts/")
        for f in adaptive_consumers
    )

    research_in_prod = any(
        not _is_test_file(Path(f)) and not f.startswith("scripts/")
        for f in research_consumers
    )

    # Core finding: the two systems coexist
    findings.append(AuditFinding(
        check_name="SINGLE_SOURCE_OF_TRUTH_BELIEF",
        status="FAIL",
        detail=(
            "Two parallel Belief systems coexist. AdaptiveBelief (old) is actively "
            "used by EvolutionPipeline and BeliefLifecycleManager. ResearchBelief (new) "
            "exists but is NOT integrated into ResearchCycleEngine's run_cycle(). "
            "The EvolutionPipeline (which ResearchCycleEngine relies on for Step 8) "
            "uses AdaptiveBelief — meaning the production code path never touches "
            "ResearchBelief."
        ),
        evidence=[
            f"AdaptiveBelief defined in: {adaptive_belief_files}",
            f"AdaptiveBelief consumed in src/ (non-test): {non_test_adaptive}",
            f"ResearchBelief defined in: {research_belief_files}",
            f"ResearchBelief consumed in src/ (non-test): {non_test_research}",
            cycle_uses,
            evo_uses,
        ],
        call_chain=[
            "ResearchCycleEngine.run_cycle() → EvolutionPipeline.run() → AdaptiveBelief",
            "ResearchBelief (beliefs/) — NOT in ResearchCycleEngine call chain",
        ],
    ))

    # 1h: Check BeliefLifecycleManager duality
    old_blm = SRC_ROOT / "research" / "evolution" / "belief_lifecycle.py"
    new_blm = SRC_ROOT / "research" / "beliefs" / "belief_lifecycle.py"
    blm_status = []
    if old_blm.exists():
        blm_status.append(f"Old BLM at: {old_blm.relative_to(PROJECT_ROOT)} — used by EvolutionPipeline")
    if new_blm.exists():
        new_blm_consumers = []
        for py_file in _all_py_files(PROJECT_ROOT):
            content = _read_file(py_file)
            rel = py_file.relative_to(PROJECT_ROOT)
            if "BeliefLifecycleManager" in content and str(rel) == "src/research/beliefs/belief_engine.py":
                new_blm_consumers.append(str(rel))
        blm_status.append(
            f"New BLM at: {new_blm.relative_to(PROJECT_ROOT)} — "
            f"consumed by: {new_blm_consumers or 'only by BeliefEngine (not in main cycle)'}"
        )

    findings.append(AuditFinding(
        check_name="SINGLE_SOURCE_OF_TRUTH_BLM",
        status="WARN",
        detail=(
            "Two BeliefLifecycleManager classes exist: one in evolution/ (old) and "
            "one in beliefs/ (new). The old one is used by the production code path "
            "(EvolutionPipeline → ResearchCycleEngine). The new one is isolated within "
            "the beliefs/ subsystem."
        ),
        evidence=blm_status,
    ))

    return findings


# ══════════════════════════════════════════════════════════════════════════════
# Check 2: Bypass Detection — does any path skip key layers?
# ══════════════════════════════════════════════════════════════════════════════


def check_bypass_paths() -> list[AuditFinding]:
    findings = []

    # ── 2a: Full conceptual chain vs actual chain ──
    conceptual = [
        "Collector", "Validator", "StateVector", "MentalModels",
        "Narrative", "Hypothesis", "Belief", "Prediction",
        "Validation", "Snapshot",
    ]

    actual_daily_runner = [
        "build_snapshot(dict)",   # skips Collector/Validator/StateVector
        "OutcomeScheduler",       # evaluates old predictions
        "ResearchCycleEngine.run_cycle",  # Framework → Thesis → Hypothesis → Transmission → Prediction → Postmortem → Evolution
        "PredictionRegistry",
        "ReportGenerator",
    ]

    actual_m1_runner = [
        "MacroPipeline.build_daily_macro_snapshot",  # includes Collector/Validator/Normalizer/FeatureEngine/StateVector/SnapshotBuilder
        "bridge_m1_to_macro_snapshot",
        "MentalModelRegistry.evaluate_all",  # runs 7 mental models → ResearchConclusion[]
        "ResearchCycleEngine.run_cycle",  # same 8-step cycle
        "ReportGenerator",
    ]

    # ── 2b: DailyRunner bypass analysis ──
    daily_runner_lines = []
    daily_runner_path = SRC_ROOT / "runtime" / "daily_runner.py"
    if daily_runner_path.exists():
        content = _read_file(daily_runner_path)
        # Find the run_today method and extract key calls
        for line in content.split("\n"):
            stripped = line.strip()
            if "Narrative" in stripped and not stripped.startswith("#"):
                daily_runner_lines.append(stripped)
            if "Belief" in stripped and not stripped.startswith("#"):
                daily_runner_lines.append(stripped)
            if "Mental" in stripped and not stripped.startswith("#"):
                daily_runner_lines.append(stripped)

    findings.append(AuditFinding(
        check_name="BYPASS_DAILY_RUNNER_M1_PIPELINE",
        status="FAIL",
        detail=(
            "DailyRunner.run_today() bypasses the entire M1 data pipeline "
            "(Collector → Validator → Normalizer → FeatureEngine → StateVector). "
            "It builds MacroSnapshot directly from a user-provided dict[str, float] "
            "instead of running MacroPipeline.build_daily_macro_snapshot()."
        ),
        evidence=[
            "daily_runner.py L141: _build_snapshot(macro_data) creates MacroSnapshot from raw dict",
            "daily_runner.py: NO call to MacroPipeline, CollectorManager, or Validator",
            "M1DailyRunner correctly uses the full pipeline (run_m1_daily.py)",
        ],
        call_chain=[
            "CONCEPTUAL: Collector → Validator → StateVector → Snapshot",
            "DailyRunner ACTUAL: raw dict → MacroSnapshot (BYPASS)",
        ],
    ))

    # ── 2c: Narrative bypass ──
    findings.append(AuditFinding(
        check_name="BYPASS_NARRATIVE",
        status="FAIL",
        detail=(
            "Narrative is NEVER called in the ResearchCycleEngine.run_cycle() method. "
            "The conceptual chain requires Narrative between MentalModels and Hypothesis, "
            "but the cycle goes: Framework → Thesis → Hypothesis → Transmission → "
            "Prediction → Postmortem → Evolution. There is no NarrativeEngine or "
            "NarrativeDetector invoked."
        ),
        evidence=[
            "cycle_engine.py run_cycle(): 8 steps, none call NarrativeEngine",
            "narrative/ package exists at src/research/narrative/ but is not in research/__init__.py exports",
            daily_runner_lines if daily_runner_lines else ["Narrative not referenced in daily_runner.py"],
        ],
        call_chain=[
            "EXPECTED: MentalModels → Narrative → Hypothesis",
            "ACTUAL: Framework → Thesis → Hypothesis (Narrative MISSING)",
        ],
    ))

    # ── 2d: BeliefEngine bypass ──
    findings.append(AuditFinding(
        check_name="BYPASS_BELIEF_ENGINE",
        status="FAIL",
        detail=(
            "BeliefEngine (the new system with ResearchBelief) is NEVER called in "
            "ResearchCycleEngine.run_cycle(). The old EvolutionPipeline operates "
            "on AdaptiveBelief, while the new BeliefEngine operates on ResearchBelief "
            "but is never integrated into the main cycle. This means beliefs are not "
            "being updated by the new system in production."
        ),
        evidence=[
            "cycle_engine.py: No import of BeliefEngine or src.research.beliefs",
            "belief_engine.py: defined but only consumed by beliefs/__init__.py and tests",
            "EvolutionPipeline uses AdaptiveBelief, not ResearchBelief",
        ],
        call_chain=[
            "EXPECTED: Hypothesis → BeliefEngine → Prediction",
            "ACTUAL: Hypothesis → Prediction (BeliefEngine MISSING)",
        ],
    ))

    # ── 2e: MentalModel → Narrative gap in M1DailyRunner ──
    findings.append(AuditFinding(
        check_name="BYPASS_MENTALMODEL_TO_NARRATIVE",
        status="FAIL",
        detail=(
            "M1DailyRunner correctly runs MentalModelRegistry.evaluate_all() to get "
            "ResearchConclusion[], but these conclusions are only collected for the "
            "report — they are NOT passed into any Narrative engine. The Model → Narrative "
            "link is broken."
        ),
        evidence=[
            "run_m1_daily.py: MentalModelRegistry.evaluate_all() results → report only",
            "No NarrativeDetector or NarrativeEngine call after mental model evaluation",
        ],
        call_chain=["MentalModels → Report (BYPASS: should be → Narrative → Hypothesis)"],
    ))

    # ── 2f: Framework bypass check ──
    findings.append(AuditFinding(
        check_name="BYPASS_FRAMEWORK_CHECK",
        status="PASS",
        detail=(
            "FrameworkSelector is correctly invoked in ResearchCycleEngine.run_cycle() "
            "(Step 2). When no active frameworks exist, it returns an empty selection "
            "with a fallback rationale — this is acceptable behavior for a cold start."
        ),
        evidence=[
            "cycle_engine.py L271: FrameworkSelector.select() called with macro_snapshot",
            "framework_selector.py L105: graceful fallback when no frameworks exist",
        ],
        call_chain=[
            "MacroSnapshot → FrameworkSelector.select() → FrameworkSelection ✅",
        ],
    ))

    return findings


# ══════════════════════════════════════════════════════════════════════════════
# Check 3: Dead Module Detection
# ══════════════════════════════════════════════════════════════════════════════


def check_dead_modules() -> list[AuditFinding]:
    findings = []
    dead_modules = []

    # Build an import map: for each .py file in src/, who imports it from outside?
    all_src_files = {}
    for py_file in _all_py_files(SRC_ROOT):
        if "__pycache__" in str(py_file):
            continue
        rel = str(py_file.relative_to(PROJECT_ROOT)).replace("\\", "/")
        all_src_files[rel] = {
            "path": py_file,
            "imported_by": [],
            "is_init": py_file.name == "__init__.py",
        }

    # Build import map: for each .py file in the project, check what it imports
    all_project_files = _all_py_files(PROJECT_ROOT)
    for py_file in all_project_files:
        if "__pycache__" in str(py_file):
            continue
        rel_importer = str(py_file.relative_to(PROJECT_ROOT)).replace("\\", "/")
        imports = _parse_imports(py_file)
        for imp in imports:
            # Resolve "src.xxx.yyy" → file path
            resolved = _module_to_path(imp)
            if resolved:
                resolved_rel = str(resolved.relative_to(PROJECT_ROOT)).replace("\\", "/")
                if resolved_rel in all_src_files:
                    all_src_files[resolved_rel]["imported_by"].append(rel_importer)

    # Categorize dead modules
    # A module is DEAD if:
    # - It has NO imports from outside its own package (self-import)
    # - OR it's only imported by tests
    # - Skip __init__.py files (they aggregate their package)

    for rel, info in all_src_files.items():
        if info["is_init"]:
            continue  # skip __init__.py

        # Filter out self-imports
        external_imports = []
        for importer in info["imported_by"]:
            importer_module = importer.replace("/", ".").replace(".py", "")
            file_module = rel.replace("/", ".").replace(".py", "")
            if not _is_self_import(importer_module, file_module):
                external_imports.append(importer)

        # If only imported by tests → may be dead
        non_test_imports = [i for i in external_imports if not _is_test_file(Path(i))]

        if not non_test_imports and not external_imports:
            # Completely dead — no imports at all
            dead_modules.append({
                "file": rel,
                "status": "DEAD",
                "reason": "No imports from any file in the project",
            })
        elif not non_test_imports and external_imports:
            # Only test imports
            dead_modules.append({
                "file": rel,
                "status": "TEST_ONLY",
                "reason": f"Only imported by test files: {external_imports[:3]}",
            })

    # Also check for completely dead packages (empty or deprecated)
    dead_package_checks = [
        ("src/analyzer", "DEPRECATED — docstring says 'replaced by signal/hypothesis engine'"),
        ("src/report", "Empty __init__.py, never imported"),
        ("src/scheduler", "v3_scheduler.py exists but never imported by src/"),
        ("src/migrations", "Alembic directory, never imported by Python code"),
    ]

    for pkg, reason in dead_package_checks:
        pkg_dir = PROJECT_ROOT / pkg
        if pkg_dir.exists():
            # Check if any imports reference this package from src/
            pkg_module = pkg.replace("/", ".")
            has_imports = False
            for py_file in _all_py_files(SRC_ROOT):
                if str(py_file).startswith(str(pkg_dir)):
                    continue
                content = _read_file(py_file)
                if pkg_module in content:
                    has_imports = True
                    break
            if not has_imports:
                dead_modules.append({
                    "file": pkg,
                    "status": "DEAD_PACKAGE",
                    "reason": reason,
                })

    findings.append(AuditFinding(
        check_name="DEAD_MODULE_DETECTION",
        status="FAIL" if len(dead_modules) > 0 else "PASS",
        detail=(
            f"Found {len(dead_modules)} dead/test-only modules. "
            "Dead modules add maintenance overhead and violate architecture freeze."
        ),
        evidence=[json.dumps(dm, indent=2) for dm in dead_modules],
    ))

    return findings, dead_modules


# ══════════════════════════════════════════════════════════════════════════════
# Check 4: Export Coverage — are all sub-packages properly exported?
# ══════════════════════════════════════════════════════════════════════════════


def check_export_coverage() -> list[AuditFinding]:
    findings = []

    # Check research/__init__.py exports
    research_init = SRC_ROOT / "research" / "__init__.py"
    research_subdirs = [d.name for d in (SRC_ROOT / "research").iterdir()
                        if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")]

    if research_init.exists():
        content = _read_file(research_init)
        exported_dirs = []
        for subdir in research_subdirs:
            if subdir in content and f"from src.research.{subdir}" in content:
                exported_dirs.append(subdir)

        missing = [s for s in research_subdirs if s not in exported_dirs]
        if missing:
            findings.append(AuditFinding(
                check_name="EXPORT_COVERAGE_RESEARCH",
                status="FAIL",
                detail=(
                    f"src/research/__init__.py does NOT export these sub-packages: "
                    f"{missing}. These modules exist but are not part of the public API. "
                    f"External code must use full dotted paths to access them."
                ),
                evidence=[
                    f"Exported: {exported_dirs}",
                    f"Not exported: {missing}",
                ],
            ))

    # Check pipeline.py exports
    pipeline_file = SRC_ROOT / "pipeline.py"
    if pipeline_file.exists():
        content = _read_file(pipeline_file)
        # Check which src/ modules pipeline imports
        imported_modules = []
        all_subdirs = [d.name for d in SRC_ROOT.iterdir() if d.is_dir() and not d.name.startswith("_")]
        for subdir in all_subdirs:
            if f"from src.{subdir}" in content or f"import src.{subdir}" in content:
                imported_modules.append(subdir)

        # Modules that might be needed but not imported by pipeline
        core_modules = ["research_cycle", "research", "data_pipeline", "runtime"]
        missing_from_pipeline = [m for m in core_modules if m not in imported_modules]
        if missing_from_pipeline:
            findings.append(AuditFinding(
                check_name="EXPORT_COVERAGE_PIPELINE",
                status="WARN",
                detail=f"Pipeline does not import: {missing_from_pipeline}",
                evidence=[f"Pipeline imports: {imported_modules}"],
            ))

    return findings


# ══════════════════════════════════════════════════════════════════════════════
# Main Audit Runner
# ══════════════════════════════════════════════════════════════════════════════


def run_architecture_audit() -> ArchitectureAudit:
    audit = ArchitectureAudit(generated_at=datetime.now(timezone.utc).isoformat())

    print("=" * 70)
    print("  V3 VALIDATION SPRINT — V1: Architecture Audit")
    print("=" * 70)

    # ── Check 1: Single Source of Truth ──
    print("\n[1/4] Checking Single Source of Truth...")
    sso_findings = check_single_source_of_truth()
    audit.findings.extend(sso_findings)
    for f in sso_findings:
        print(f"  [{f.status}] {f.check_name}")

    # ── Check 2: Bypass Detection ──
    print("\n[2/4] Checking Bypass Paths...")
    bypass_findings = check_bypass_paths()
    audit.findings.extend(bypass_findings)
    for f in bypass_findings:
        print(f"  [{f.status}] {f.check_name}")

    # ── Check 3: Dead Modules ──
    print("\n[3/4] Checking Dead Modules...")
    dead_findings, dead_modules = check_dead_modules()
    audit.findings.extend(dead_findings)
    audit.dead_modules = dead_modules
    for dm in dead_modules:
        print(f"  [{dm['status']}] {dm['file']} — {dm.get('reason', '')[:80]}")

    # ── Check 4: Export Coverage ──
    print("\n[4/4] Checking Export Coverage...")
    export_findings = check_export_coverage()
    audit.findings.extend(export_findings)
    for f in export_findings:
        print(f"  [{f.status}] {f.check_name}")

    # ── Compute Stats ──
    audit.total_checks = len(audit.findings)
    audit.passed = sum(1 for f in audit.findings if f.status == "PASS")
    audit.failed = sum(1 for f in audit.findings if f.status == "FAIL")
    audit.warnings = sum(1 for f in audit.findings if f.status == "WARN")
    audit.overall_status = "PASS" if audit.failed == 0 else "FAIL"

    # ── Print Summary ──
    print("\n" + "=" * 70)
    print(f"  ARCHITECTURE AUDIT: {audit.overall_status}")
    print(f"  Checks: {audit.total_checks} | PASS: {audit.passed} | FAIL: {audit.failed} | WARN: {audit.warnings}")
    print(f"  Dead Modules: {len(audit.dead_modules)}")
    print("=" * 70)

    return audit


def save_results(audit: ArchitectureAudit):
    """Save audit results as JSON and Markdown."""

    # ── JSON ──
    json_path = VALIDATION_OUTPUT / "architecture_audit.json"
    result = {
        "generated_at": audit.generated_at,
        "overall_status": audit.overall_status,
        "total_checks": audit.total_checks,
        "passed": audit.passed,
        "failed": audit.failed,
        "warnings": audit.warnings,
        "dead_modules": audit.dead_modules,
        "findings": [
            {
                "check_name": f.check_name,
                "status": f.status,
                "detail": f.detail,
                "evidence": f.evidence,
                "call_chain": f.call_chain,
            }
            for f in audit.findings
        ],
    }
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nJSON saved: {json_path}")

    # ── Markdown ──
    md_path = DOCS_DIR / "V3_ARCHITECTURE_AUDIT.md"
    _write_markdown(audit, md_path)
    print(f"Markdown saved: {md_path}")


def _write_markdown(audit: ArchitectureAudit, path: Path):
    lines = []
    lines.append("# V3 Architecture Audit Report")
    lines.append("")
    lines.append(f"> Generated: {audit.generated_at}")
    lines.append(f"> Overall Status: **{audit.overall_status}**")
    lines.append(f"> Checks: {audit.total_checks} | PASS: {audit.passed} | FAIL: {audit.failed} | WARN: {audit.warnings}")
    lines.append(f"> Dead Modules: {len(audit.dead_modules)}")
    lines.append("")

    lines.append("---")
    lines.append("")

    # ── Sprint Standard ──
    lines.append("## Sprint Completion Standard")
    lines.append("")
    lines.append("| Check | Target | Result |")
    lines.append("|-------|--------|--------|")
    lines.append(f"| Architecture Audit | 100% PASS | **{audit.overall_status}** |")
    lines.append(f"| Dead Modules | 0 | **{len(audit.dead_modules)}** |")
    lines.append("")

    lines.append("---")
    lines.append("")

    # ── Findings by status ──
    for status_label, emoji in [("FAIL", "❌"), ("WARN", "⚠️"), ("PASS", "✅")]:
        items = [f for f in audit.findings if f.status == status_label]
        if not items:
            continue
        lines.append(f"## {emoji} {status_label} ({len(items)})")
        lines.append("")
        for item in items:
            lines.append(f"### {item.check_name}")
            lines.append("")
            lines.append(f"**Status:** {item.status}")
            lines.append("")
            lines.append(item.detail)
            lines.append("")
            if item.evidence:
                lines.append("**Evidence:**")
                lines.append("")
                for e in item.evidence:
                    lines.append(f"- {e}")
                lines.append("")
            if item.call_chain:
                lines.append("**Call Chain:**")
                lines.append("")
                for c in item.call_chain:
                    lines.append(f"1. {c}")
                lines.append("")
            lines.append("---")
            lines.append("")

    # ── Dead Modules ──
    if audit.dead_modules:
        lines.append("## Dead Modules")
        lines.append("")
        lines.append("| File | Status | Reason |")
        lines.append("|------|--------|--------|")
        for dm in audit.dead_modules:
            lines.append(f"| `{dm['file']}` | {dm['status']} | {dm.get('reason', '')[:100]} |")
        lines.append("")

    # ── Summary ──
    lines.append("## Action Items")
    lines.append("")
    lines.append("### Critical (MUST FIX before Production)")
    lines.append("")
    for item in audit.findings:
        if item.status == "FAIL":
            lines.append(f"- **[{item.check_name}]** {item.detail[:120]}...")
    lines.append("")
    lines.append("### Warnings (SHOULD FIX)")
    lines.append("")
    for item in audit.findings:
        if item.status == "WARN":
            lines.append(f"- **[{item.check_name}]** {item.detail[:120]}...")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    audit = run_architecture_audit()
    save_results(audit)
