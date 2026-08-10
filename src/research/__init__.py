"""Research Evolution Package — Milestone C.

Architecture Freeze: Finding → Principle → Belief → Framework.
The four cognitive layers are independent. No cross-layer direct modification.

Module structure:
    findings/    — Migrated from transmission/ (B.5 code)
    principles/  — Finding → Principle admission gate
    framework/   — Framework formation, evolution, multi-framework coexistence
    evolution/   — Complete evolution pipeline, conflict resolution, belief lifecycle
"""

from src.research.findings.engine import ResearchFindingsEngine
from src.research.findings.note_generator import ResearchNoteGenerator
from src.research.principles.admission_gate import PrincipleAdmissionGate
from src.research.principles.principle_extractor import PrincipleExtractor
from src.research.principles.candidate_manager import CandidatePrincipleManager
from src.research.principles.principle_store import PrincipleStore
from src.research.framework.cluster_detector import PrincipleClusterDetector
from src.research.framework.framework_evaluator import FrameworkEvaluator
from src.research.framework.framework_store import FrameworkStore
from src.research.framework.framework_orchestrator import FrameworkOrchestrator
from src.research.evolution.regime_gate import RegimeGate
from src.research.evolution.temporary_layer import TemporaryEventLayer
from src.research.evolution.conflict_resolver import ConflictResolver
from src.research.evolution.belief_lifecycle import BeliefLifecycleManager
from src.research.evolution.evolution_pipeline import EvolutionPipeline

__all__ = [
    # Findings
    "ResearchFindingsEngine",
    "ResearchNoteGenerator",
    # Principles
    "PrincipleAdmissionGate",
    "PrincipleExtractor",
    "CandidatePrincipleManager",
    "PrincipleStore",
    # Framework
    "PrincipleClusterDetector",
    "FrameworkEvaluator",
    "FrameworkStore",
    "FrameworkOrchestrator",
    # Evolution
    "RegimeGate",
    "TemporaryEventLayer",
    "ConflictResolver",
    "BeliefLifecycleManager",
    "EvolutionPipeline",
]
