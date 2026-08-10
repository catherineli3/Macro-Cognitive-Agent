"""Research Cycle Engine — the autonomous daily research loop (V3.2).

The ResearchCycleEngine is the heart of the macro research agent. V3.2 upgrades:

    V3.0/3.1 (Signal Detection)        → V3.2 (Narrative Reasoning)
    Single Narrative                     → Multiple Competing Narratives
    Isolated Beliefs                     → Belief Graph (SUPPORTS/COMPETES/CONTRADICTS/EXPLAINS)
    Raw Conclusions                     → Research Judgments (falsifiable, owned)

Full V3.2 cycle:
    Market Data → Framework Selection → Narrative Detection (V3.0) →
    Narrative Reasoning (V3.2) → Narrative Competition (V3.2) →
    Belief Generation → Belief Graph (V3.2) → Research Judgment (V3.2) →
    Thesis Generation → Hypothesis Competition → Transmission Reasoning →
    Prediction → Outcome → Diagnosis → Postmortem → Evolution → Memory
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.schemas.macro_snapshot import MacroSnapshot
from src.schemas.research_thesis import ResearchThesis, ThesisOutcome, ThesisStatus
from src.research_cycle.framework_selector import FrameworkSelector, FrameworkSelection
from src.research_cycle.thesis_generator import ThesisGenerator
from src.research_cycle.research_memory import ResearchMemory, ResearchMemoryEntry
from src.research_cycle.outcome_tracker import OutcomeTracker
from src.research_cycle.postmortem import Postmortem
from src.transmission.transmission_graph import TransmissionGraph
from src.research.narrative.schemas import Narrative, NarrativeObject, NarrativeCompetitionResult
from src.research.narrative.narrative_reasoner import NarrativeReasoner
from src.research.narrative.narrative_competition import NarrativeCompetition
from src.research.beliefs.belief_engine import BeliefEngine
from src.research.beliefs.belief_graph import BeliefGraph
from src.research.judgment.research_judgment import ResearchJudgmentEngine, JudgmentOutput
from src.research.narrative.narrative_detector import NarrativeDetector
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CycleResult — unified output of a research cycle
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CycleResult:
    """Unified output of one complete research cycle."""

    cycle_id: str = ""
    cycle_number: int = 0
    status: str = "pending"  # "pending" | "running" | "completed" | "failed"
    macro_snapshot: MacroSnapshot | None = None
    framework_selection: FrameworkSelection | None = None
    thesis: ResearchThesis | None = None
    narratives: list = field(default_factory=list)       # Narrative[] — V3.1
    narrative_objects: list = field(default_factory=list) # NarrativeObject[] — V3.2
    narrative_competition: Any = None                     # NarrativeCompetitionResult — V3.2
    beliefs: list = field(default_factory=list)           # ResearchBelief[] — V3.1
    belief_graph_stats: dict | None = None                # BeliefGraph stats — V3.2
    research_judgments: Any = None                        # JudgmentOutput — V3.2
    hypothesis_set: Any = None              # HypothesisSet | None
    findings_report: Any = None             # ResearchFindingsReport | None
    prediction_batch: Any = None            # PredictionBatch | None
    outcome_from_previous: ThesisOutcome | None = None  # Previous cycle's outcome
    diagnosis_report: Any = None            # DiagnosisReport | None
    postmortem: Any = None                  # PostmortemReport | None
    evolution_result: dict | None = None    # From EvolutionPipeline.run()
    memory_entry_id: str | None = None
    artifacts: dict = field(default_factory=dict)
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return self.status == "completed"

    @property
    def has_thesis(self) -> bool:
        return self.thesis is not None

    def summary(self) -> str:
        lines = [
            f"=== Cycle #{self.cycle_number} [{self.cycle_id}] ===",
            f"Status: {self.status.value}",
        ]
        if self.error:
            lines.append(f"ERROR: {self.error}")
        if self.warnings:
            for w in self.warnings:
                lines.append(f"WARN: {w}")
        if self.macro_snapshot:
            lines.append(f"Regime: {self.macro_snapshot.regime_label}")
        if self.framework_selection:
            lines.append(f"Framework: {self.framework_selection.top_framework_id or 'None'}")
        if self.thesis:
            lines.append(f"Thesis: {self.thesis.title[:80]}")
            lines.append(f"  Confidence: {self.thesis.confidence:.0%}")
            lines.append(f"  Window: {self.thesis.expected_window}")
        if self.outcome_from_previous:
            lines.append(f"Prev Outcome: {self.outcome_from_previous.describe()}")
        if self.narratives:
            lines.append(f"Narratives: {len(self.narratives)} detected")
        if self.beliefs:
            lines.append(f"Beliefs: {len(self.beliefs)} formed")
        if self.evolution_result:
            ev = self.evolution_result
            lines.append(
                f"Evolution: {ev.get('principles_created', 0)}P "
                f"{ev.get('frameworks_created', 0)}F "
                f"{ev.get('conflicts_resolved', 0)}C"
            )
        if self.memory_entry_id:
            lines.append(f"Memory: {self.memory_entry_id}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# ResearchCycleEngine
# ═══════════════════════════════════════════════════════════════════════════════


class ResearchCycleEngine:
    """The complete autonomous research cycle engine.

    Orchestrates the full daily loop:
        Input → Framework → Thesis → Hypothesis → Transmission →
        Prediction → Diagnosis → Postmortem → Evolution → Memory

    This engine DOES NOT create new knowledge modules. It connects:
        - Milestone A: Hypothesis competition engine
        - Milestone B: Transmission reasoning engine
        - Milestone C: Research evolution engine (EvolutionPipeline)
        + Milestone D: Framework selector, Thesis generator, Postmortem, Memory

    All A/B/C engines are lazily initialized and optional — the cycle
    gracefully degrades when sub-engines are unavailable.
    """

    def __init__(self, memory_path: str | None = None, snapshot_manager: Any = None):
        """Initialize the cycle engine.

        Args:
            memory_path: Optional path for research memory storage
            snapshot_manager: Optional SnapshotManager for auto-exporting snapshots
        """
        # ── Milestone D engines (always available) ──────────────────
        self.memory = ResearchMemory(memory_path)
        self.framework_selector = FrameworkSelector()
        self.thesis_generator = ThesisGenerator()
        self.outcome_tracker = OutcomeTracker()
        self.postmortem = Postmortem()

        # ── Milestone B: Transmission Graph (persistent across cycles) ──
        self._transmission_graph: TransmissionGraph = TransmissionGraph()

        # ── Milestone C engine (lazy) ───────────────────────────────
        self._evolution_pipeline: Any = None

        # ── V3.1 Narrative + Belief engines (lazy) ──────────────────
        self._narrative_detector: Any = None
        self._belief_engine: Any = None

        # ── Milestone A + B engines (lazy) ──────────────────────────
        self._hypothesis_engine: Any = None
        self._findings_engine: Any = None
        self._prediction_engine: Any = None
        self._diagnosis_engine: Any = None

        # ── Snapshot Layer (Milestone F0.5) ──────────────────────────
        self.snapshot_manager: Any = snapshot_manager

        # ── State ────────────────────────────────────────────────────
        self._cycle_count: int = 0
        self._previous_thesis: ResearchThesis | None = None

    # ── Lazy Engine Initialization ──────────────────────────────────────

    def _ensure_evolution(self) -> None:
        """Lazy-init the EvolutionPipeline (Milestone C)."""
        if self._evolution_pipeline is not None:
            return
        try:
            from src.research.evolution.evolution_pipeline import EvolutionPipeline
            self._evolution_pipeline = EvolutionPipeline()
            # Bind to dependents
            self.framework_selector.set_evolution_pipeline(self._evolution_pipeline)
            self.thesis_generator.set_evolution_pipeline(self._evolution_pipeline)
            logger.info("EvolutionPipeline initialized")
        except Exception as e:
            self._evolution_pipeline = False  # Sentinel for "tried, failed"
            logger.warning("EvolutionPipeline not available: %s", e)

    def _ensure_hypothesis_engine(self) -> Any:
        """Lazy-init the Hypothesis engine (Milestone A)."""
        if self._hypothesis_engine is not None:
            return self._hypothesis_engine
        try:
            from src.hypothesis.engine import HypothesisEngine
            self._hypothesis_engine = HypothesisEngine()
            logger.info("HypothesisEngine initialized")
            return self._hypothesis_engine
        except Exception as e:
            logger.warning("HypothesisEngine not available: %s", e)
            self._hypothesis_engine = False  # Sentinel
            return None

    def _ensure_findings_engine(self) -> Any:
        """Lazy-init findings engine (Milestone B)."""
        if self._findings_engine is not None:
            return self._findings_engine
        try:
            from src.research.findings.engine import ResearchFindingsEngine
            self._findings_engine = ResearchFindingsEngine(graph=self._transmission_graph)
            return self._findings_engine
        except Exception as e:
            logger.warning("ResearchFindingsEngine not available: %s", e)
            self._findings_engine = False
            return None

    def _ensure_prediction_engine(self) -> Any:
        """Lazy-init prediction engine."""
        if self._prediction_engine is not None:
            return self._prediction_engine
        try:
            from src.prediction import MultiPredictionEngine
            self._prediction_engine = MultiPredictionEngine()
            return self._prediction_engine
        except Exception as e:
            logger.warning("PredictionEngine not available: %s", e)
            self._prediction_engine = False
            return None

    def _ensure_diagnosis_engine(self) -> Any:
        """Lazy-init diagnosis engine."""
        if self._diagnosis_engine is not None:
            return self._diagnosis_engine
        try:
            from src.diagnosis import DiagnosisEngine
            self._diagnosis_engine = DiagnosisEngine()
            return self._diagnosis_engine
        except Exception as e:
            logger.warning("DiagnosisEngine not available: %s", e)
            self._diagnosis_engine = False
            return None

    def _ensure_narrative_detector(self) -> Any:
        """Lazy-init NarrativeDetector (V3.1)."""
        if self._narrative_detector is not None:
            return self._narrative_detector
        try:
            from src.research.narrative.narrative_detector import NarrativeDetector
            self._narrative_detector = NarrativeDetector()
            logger.info("NarrativeDetector initialized (V3.1)")
            return self._narrative_detector
        except Exception as e:
            logger.warning("NarrativeDetector not available: %s", e)
            self._narrative_detector = False
            return None

    def _ensure_belief_engine(self) -> Any:
        """Lazy-init BeliefEngine (V3.1)."""
        if self._belief_engine is not None:
            return self._belief_engine
        try:
            from src.research.beliefs.belief_engine import BeliefEngine
            self._belief_engine = BeliefEngine()
            logger.info("BeliefEngine initialized (V3.1)")
            return self._belief_engine
        except Exception as e:
            logger.warning("BeliefEngine not available: %s", e)
            self._belief_engine = False
            return None

    # ── V3.2 Lazy Init Methods ──────────────────────────────────────────

    def _ensure_narrative_reasoner(self) -> NarrativeReasoner | None:
        """Lazy-init NarrativeReasoner (V3.2)."""
        if hasattr(self, '_narrative_reasoner') and self._narrative_reasoner is not None:
            return self._narrative_reasoner
        try:
            self._narrative_reasoner = NarrativeReasoner()
            logger.info("NarrativeReasoner initialized (V3.2)")
            return self._narrative_reasoner
        except Exception as e:
            logger.warning("NarrativeReasoner not available: %s", e)
            self._narrative_reasoner = False
            return None

    def _ensure_narrative_competition(self) -> NarrativeCompetition | None:
        """Lazy-init NarrativeCompetition (V3.2)."""
        if hasattr(self, '_narrative_competition') and self._narrative_competition is not None:
            return self._narrative_competition
        try:
            reasoner = self._ensure_narrative_reasoner()
            self._narrative_competition = NarrativeCompetition(reasoner=reasoner)
            logger.info("NarrativeCompetition initialized (V3.2)")
            return self._narrative_competition
        except Exception as e:
            logger.warning("NarrativeCompetition not available: %s", e)
            self._narrative_competition = False
            return None

    def _ensure_judgment_engine(self) -> ResearchJudgmentEngine | None:
        """Lazy-init ResearchJudgmentEngine (V3.2)."""
        if hasattr(self, '_judgment_engine') and self._judgment_engine is not None:
            return self._judgment_engine
        try:
            self._judgment_engine = ResearchJudgmentEngine()
            logger.info("ResearchJudgmentEngine initialized (V3.2)")
            return self._judgment_engine
        except Exception as e:
            logger.warning("ResearchJudgmentEngine not available: %s", e)
            self._judgment_engine = False
            return None

    # ══════════════════════════════════════════════════════════════════════
    # Main Entry: run_cycle
    # ══════════════════════════════════════════════════════════════════════

    def run_cycle(
        self,
        macro_snapshot: MacroSnapshot,
        previous_outcomes: dict[str, tuple[dict[str, float], str]] | None = None,
        skip_evolution: bool = False,
    ) -> CycleResult:
        """Run one complete research cycle.

        This is the single entry point. Call once per market day.

        Args:
            macro_snapshot: Current market state (regime + signals + data)
            previous_outcomes: Optional outcomes from previous theses.
                               Dict of {thesis_id: (actual_data, diagnosis_notes)}
            skip_evolution: Skip the evolution step (for testing)

        Returns:
            CycleResult with complete cycle output
        """
        self._cycle_count += 1
        cycle = self._cycle_count
        cycle_id = macro_snapshot.cycle_id or f"cycle-{cycle:04d}"

        result = CycleResult(
            cycle_id=cycle_id,
            cycle_number=cycle,
            status="running",
            macro_snapshot=macro_snapshot,
        )

        logger.info("=" * 60)
        logger.info("Research Cycle #%d starting — Regime: %s [V3.2]",
                     cycle, macro_snapshot.regime_label)
        logger.info("=" * 60)

        try:
            # ── Step 1: Process previous outcomes ─────────────────
            if previous_outcomes:
                self._process_previous_outcomes(result, previous_outcomes)

            # ── Step 2: Framework Selection ────────────────────────
            self._ensure_evolution()
            result.framework_selection = self.framework_selector.select(macro_snapshot)
            logger.info("Step 1/14: Framework selected — %s",
                        result.framework_selection.top_framework_id or "none")

            # ── Step 3: Narrative Detection (V3.1) ────────────────
            result.narratives = self._detect_narratives(macro_snapshot)
            logger.info("Step 2/14: Narrative detection — %d narratives",
                        len(result.narratives))

            # ── Step 4: Narrative Reasoning (V3.2 NEW) ─────────────
            result.narrative_objects = self._reason_narratives(
                result.narratives, macro_snapshot
            )
            logger.info("Step 3/14: Narrative reasoning — %d narrative objects (depth=%s)",
                        len(result.narrative_objects),
                        [n.causal_depth for n in result.narrative_objects])

            # ── Step 5: Narrative Competition (V3.2 NEW) ───────────
            result.narrative_competition = self._compete_narratives(
                macro_snapshot, result.narrative_objects
            )
            n_comp = (
                len(result.narrative_competition.narratives)
                if result.narrative_competition else 0
            )
            logger.info("Step 4/14: Narrative competition — %d competing narratives",
                        n_comp)

            # ── Step 6: Belief Generation (V3.2 enhanced) ──────────
            # Use V3.2 NarrativeObjects for richer belief generation
            narratives_for_beliefs = (
                result.narrative_objects
                if result.narrative_objects
                else result.narratives
            )
            result.beliefs = self._generate_beliefs(
                narratives_for_beliefs, macro_snapshot
            )
            # V3.2: Capture belief graph stats
            belief_engine = self._ensure_belief_engine()
            if belief_engine and hasattr(belief_engine, 'graph'):
                result.belief_graph_stats = belief_engine.graph.get_graph_stats()
            logger.info("Step 5/14: Belief generation — %d beliefs (graph stats: %s)",
                        len(result.beliefs),
                        result.belief_graph_stats)

            # ── Step 7: Research Judgment (V3.2 NEW) ───────────────
            result.research_judgments = self._generate_judgments(
                result.beliefs, result.narrative_objects
            )
            j_count = (
                result.research_judgments.count
                if result.research_judgments else 0
            )
            logger.info("Step 6/14: Research judgments — %d judgments (stance=%s)",
                        j_count,
                        result.research_judgments.macro_stance if result.research_judgments else "N/A")

            # ── Step 8: Thesis Generation ─────────────────────────
            result.thesis = self.thesis_generator.generate(
                selection=result.framework_selection,
                macro_snapshot=macro_snapshot,
                hypotheses=None,  # Will be set after hypothesis step
                narratives=result.narratives,        # V3.1
                beliefs=result.beliefs,              # V3.1
                judgments=result.research_judgments,  # V3.2
            )
            logger.info("Step 7/14: Thesis generated — c=%.0f%%",
                        result.thesis.confidence * 100)

            # ── Step 9: Hypothesis Competition (Milestone A) ──────
            if macro_snapshot.signals:
                hypothesis_engine = self._ensure_hypothesis_engine()
                if hypothesis_engine:
                    try:
                        result.hypothesis_set = hypothesis_engine.reason(
                            macro_snapshot.signals
                        )
                        # Regenerate thesis with hypothesis context
                        result.thesis = self.thesis_generator.generate(
                            selection=result.framework_selection,
                            macro_snapshot=macro_snapshot,
                            hypotheses=result.hypothesis_set,
                            beliefs=result.beliefs,
                            judgments=result.research_judgments,
                        )
                        logger.info("Step 8/14: Hypothesis competition — %d hypotheses",
                                    len(result.hypothesis_set.hypotheses) if result.hypothesis_set else 0)
                    except Exception as e:
                        result.warnings.append(f"Hypothesis step failed: {e}")
                        logger.warning("Hypothesis step failed: %s", e)
            else:
                logger.info("Step 8/14: No signals, skipping hypothesis competition")

            # ── Step 10: Transmission Reasoning (Milestone B) ──────
            findings_engine = self._ensure_findings_engine()
            if findings_engine:
                try:
                    diagnoses = self._build_transmission_diagnoses(
                        regime_label=macro_snapshot.regime_label,
                    )
                    if diagnoses:
                        result.findings_report = findings_engine.analyze(
                            diagnoses=diagnoses,
                            context_key=macro_snapshot.regime_label,
                            cycle_number=cycle,
                        )
                        total_f = (
                            len(result.findings_report.reliability_ranking) +
                            len(result.findings_report.failure_warnings) +
                            len(result.findings_report.failure_event_correlations) +
                            len(result.findings_report.regime_similarities)
                        ) if result.findings_report else 0
                        logger.info("Step 9/14: Transmission findings — %d findings from %d diagnoses",
                                    total_f, len(diagnoses))
                    else:
                        logger.info("Step 9/14: No transmission diagnoses to analyze")
                except Exception as e:
                    result.warnings.append(f"Findings step failed: {e}")
                    logger.warning("Findings step failed: %s", e)
            else:
                logger.info("Step 9/14: Skipping transmission reasoning (no engine)")

            # ── Step 11: Prediction (Milestone A/V3) ───────────────
            prediction_engine = self._ensure_prediction_engine()
            if prediction_engine and result.hypothesis_set:
                try:
                    result.prediction_batch = prediction_engine.predict(
                        result.hypothesis_set
                    )
                    self.outcome_tracker.register_thesis(
                        result.thesis,
                        predictions=result.prediction_batch if hasattr(result.prediction_batch, 'predictions') else None,
                    )
                    logger.info("Step 10/14: Predictions generated")
                except Exception as e:
                    result.warnings.append(f"Prediction step failed: {e}")
                    logger.warning("Prediction step failed: %s", e)
            else:
                logger.info("Step 10/14: Skipping prediction (no engine/data)")

            # ── Step 12: Postmortem (from PREVIOUS cycle) ─────────
            if result.outcome_from_previous and self._previous_thesis:
                pm = self.postmortem.analyze(
                    self._previous_thesis,
                    result.outcome_from_previous,
                    diagnosis_notes=getattr(result.diagnosis_report, 'summary', '') if result.diagnosis_report else '',
                )
                result.postmortem = pm
                logger.info("Step 11/14: Postmortem — %s", pm.root_cause[:60])
            else:
                logger.info("Step 11/14: No previous outcome to postmortem")

            # ── Step 13: Evolution (Milestone C) ───────────────────
            if not skip_evolution and self._evolution_pipeline and result.findings_report:
                try:
                    regime_snapshot = macro_snapshot.regime
                    diagnoses = [result.diagnosis_report] if result.diagnosis_report else []
                    result.evolution_result = self._evolution_pipeline.run(
                        result.findings_report,
                        diagnoses=diagnoses,
                        current_regime=regime_snapshot,
                    )
                    logger.info("Step 12/14: Evolution — %s",
                                {k: v for k, v in result.evolution_result.items()
                                 if k in ('principles_created', 'frameworks_created', 'conflicts_resolved')})
                except Exception as e:
                    result.warnings.append(f"Evolution step failed: {e}")
                    logger.warning("Evolution step failed: %s", e)
            else:
                logger.info("Step 12/14: Skipping evolution (no pipeline/findings)")

            # ── Store in Research Memory ───────────────────────────
            memory_entry = self._build_memory_entry(result, cycle)
            result.memory_entry_id = self.memory.record_entry(memory_entry)

            # ── Activate thesis for next cycle's tracking ──────────
            result.thesis.activate()

            self._previous_thesis = result.thesis

            result.status = "completed"

            # ── Snapshot Export (Milestone F0.5) ─────────────────────
            if self.snapshot_manager is not None:
                try:
                    self.snapshot_manager.capture(
                        cycle_number=cycle,
                        cycle_result=result,
                    )
                except Exception as snap_err:
                    result.warnings.append(f"Snapshot export failed: {snap_err}")
                    logger.warning("Snapshot export failed for cycle #%d: %s", cycle, snap_err)

            logger.info("=" * 60)
            logger.info("Research Cycle #%d completed — Memory: %s",
                         cycle, result.memory_entry_id)
            logger.info("=" * 60)

        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            logger.error("Research Cycle #%d FAILED: %s", cycle, e)

        return result

    # ── Step Helpers ────────────────────────────────────────────────────

    def _process_previous_outcomes(
        self,
        result: CycleResult,
        outcomes: dict[str, tuple[dict[str, float], str]],
    ) -> None:
        """Process market outcomes for theses from previous cycles.

        Updates the TransmissionGraph based on thesis validation:
        - Validated thesis → reinforce the edges that transmitted correctly
        - Invalidated thesis → weaken the broken edges
        """
        if not self._previous_thesis:
            return

        thesis_id = self._previous_thesis.thesis_id
        if thesis_id in outcomes:
            actual_data, notes = outcomes[thesis_id]
            outcome = self.outcome_tracker.determine_outcome(
                self._previous_thesis, actual_data, notes,
            )
            result.outcome_from_previous = outcome

            # ── Update TransmissionGraph based on thesis outcome ──
            regime_label = result.macro_snapshot.regime_label if result.macro_snapshot else ""
            self._update_graph_from_outcome(outcome, notes, regime_label)

            # Also run diagnosis if available
            diagnosis_engine = self._ensure_diagnosis_engine()
            if diagnosis_engine:
                try:
                    result.diagnosis_report = diagnosis_engine.diagnose(
                        self._previous_thesis, outcome,
                    ) if hasattr(diagnosis_engine, 'diagnose') else None
                except Exception:
                    pass

    def _update_graph_from_outcome(
        self,
        outcome: ThesisOutcome,
        notes: str,
        regime_label: str = "",
    ) -> None:
        """Update TransmissionGraph edges based on thesis validation result.

        Maps thesis outcome to graph edge updates:
        - verified → reinforce edges in the transmission chain
        - not verified → weaken the broken edges
        """
        g = self._transmission_graph
        chains = self._get_transmission_chains(regime_label)

        if outcome.verified:
            # Thesis validated — reinforce the transmission edges
            for chain in chains:
                for i in range(len(chain) - 1):
                    src, tgt = chain[i], chain[i + 1]
                    g.reinforce_edge(src, tgt, context_key=regime_label,
                                     amount=0.03, reason=f"Thesis validated: {notes[:60]}")
        else:
            # Thesis invalidated — weaken the transmission edges
            for chain in chains:
                for i in range(len(chain) - 1):
                    src, tgt = chain[i], chain[i + 1]
                    g.weaken_edge(src, tgt, context_key=regime_label,
                                  amount=-0.04, reason=f"Thesis contradicted: {notes[:60]}")

    @staticmethod
    def _get_transmission_chains(
        regime_label: str,
    ) -> list[list[str]]:
        """Build expected transmission chains based on regime context.

        Each chain is a list of node names representing a causal path
        that the macro theory expects to activate.
        """
        label_lower = regime_label.lower() if regime_label else ""

        # Default: generic multi-asset chain
        chains: list[list[str]] = [
            ["liquidity", "credit", "risk_appetite", "SPX"],
            ["growth", "US10Y", "DXY"],
        ]

        # Regime-specific chains
        if "tighten" in label_lower or "hawk" in label_lower:
            chains = [
                ["liquidity", "USD", "Gold"],
                ["credit", "SPX"],
                ["growth", "US10Y"],
            ]
        elif "easing" in label_lower or "dove" in label_lower:
            chains = [
                ["liquidity", "risk_appetite", "SPX"],
                ["liquidity", "NASDAQ"],
                ["credit", "HYG", "SPX"],
            ]
        elif "vol" in label_lower or "high vol" in label_lower:
            chains = [
                ["risk_appetite", "VIX", "SPX"],
                ["credit", "risk_appetite"],
            ]
        elif "inflation" in label_lower:
            chains = [
                ["inflation", "US10Y", "Gold"],
                ["inflation", "TIPS"],
                ["growth", "credit"],
            ]

        return chains

    def _build_transmission_diagnoses(
        self,
        regime_label: str,
    ) -> list:
        """Build BreakpointDiagnosis objects by testing transmission chains.

        Simulates whether each segment in each chain transmitted correctly,
        then uses TransmissionGraph.find_breakpoint() to produce proper
        BreakpointDiagnosis objects with severity, root cause, etc.
        """
        from src.schemas.transmission_v3_1 import BreakpointDiagnosis

        diagnoses: list = []
        g = self._transmission_graph
        chains = self._get_transmission_chains(regime_label)

        # Build simulated segment states based on graph reliability
        for chain in chains:
            # Decide which segments "transmitted correctly" based on edge reliability
            actual_states: dict[str, bool] = {}
            for i in range(len(chain) - 1):
                src, tgt = chain[i], chain[i + 1]
                seg_id = f"{src}→{tgt}"
                edge = g.get_edge(src, tgt)
                if edge:
                    # Higher reliability → more likely to transmit
                    actual_states[seg_id] = edge.reliability_default > 0.45
                else:
                    actual_states[seg_id] = True  # Unknown edges pass through

            bp = g.find_breakpoint(
                expected_chain=chain,
                actual_segment_states=actual_states,
                context_key=regime_label,
            )
            diagnoses.append(bp)

        return diagnoses

    def _detect_narratives(self, macro_snapshot: MacroSnapshot) -> list:
        """Step 3 (V3.1): Run Narrative Detection on current macro snapshot.

        Uses NarrativeDetector to extract market narratives from
        the macro state, regime, and mental model outputs.
        """
        detector = self._ensure_narrative_detector()
        if not detector:
            return []

        try:
            # Build state_vector in the format NarrativeDetector expects:
            # {dim: {score, direction, drivers, ...}}
            state_vector = self._build_state_vector_for_narrative(macro_snapshot)

            # Build ResearchConclusion list from:
            #  1. Actual MentalModel outputs if available (primary signal)
            #  2. state_vector inference as fallback
            from src.research.models.mental_model import ResearchConclusion
            conclusions: list = []

            # ── Primary: MentalModel outputs from MacroSnapshot ──────
            if hasattr(macro_snapshot, 'snapshot_data') and macro_snapshot.snapshot_data:
                mm_outputs = macro_snapshot.snapshot_data.get('mental_model_outputs', [])
                for mm in mm_outputs:
                    if isinstance(mm, dict):
                        conclusions.append(ResearchConclusion(
                            model_name=mm.get('model_name', 'MentalModel'),
                            domain=mm.get('domain', mm.get('dimension', '')),
                            conclusion=mm.get('conclusion', ''),
                            confidence=mm.get('confidence', 0.5),
                            direction=mm.get('direction', 'neutral'),
                            raw_score=mm.get('raw_score', mm.get('score', 0.5)),
                        ))

            # ── Fallback: state_vector inference ─────────────────────
            if not conclusions and state_vector:
                for dim, data in state_vector.items():
                    if isinstance(data, dict) and data.get('score') is not None:
                        conclusions.append(ResearchConclusion(
                            model_name="RegimeInference",
                            domain=dim,
                            conclusion=f"{dim}: {data.get('direction', 'neutral')} "
                                       f"(score={data.get('score', 0)})",
                            confidence=abs(data.get('score', 0)),
                        ))

            narratives = detector.detect(
                state_vector=state_vector,
                conclusions=conclusions,
            )
            return narratives if isinstance(narratives, list) else []
        except Exception as e:
            logger.warning("Narrative detection failed: %s", e)
            return []

    @staticmethod
    def _build_state_vector_for_narrative(macro_snapshot: MacroSnapshot) -> dict:
        """Build M1-style state_vector from MacroSnapshot for NarrativeDetector.

        Extracts dimension scores, directions, and drivers from:
        - Market indicators
        - Regime data (monetary_policy, growth, inflation, etc.)
        """
        state_vector: dict[str, dict] = {}

        # ── Market indicators ─────────────────────────────────────
        if hasattr(macro_snapshot, 'market') and macro_snapshot.market:
            indicators = getattr(macro_snapshot.market, 'indicators', {}) or {}
            for key, value in indicators.items():
                dim_name = key.split('.')[0] if '.' in key else key
                sv = state_vector.setdefault(dim_name, {
                    'score': 0.0, 'direction': 'neutral', 'drivers': [],
                })
                if isinstance(value, (int, float)):
                    sv['drivers'].append(f"{key}={value:.2f}")

        # ── Regime data ────────────────────────────────────────────
        if hasattr(macro_snapshot, 'regime') and macro_snapshot.regime:
            regime = macro_snapshot.regime
            regime_map = {
                'monetary_policy': 'POLICY',
                'inflation': 'INFLATION',
                'growth': 'GROWTH',
            }
            for attr, dim in regime_map.items():
                val = getattr(regime, attr, None)
                if val is not None:
                    sv = state_vector.setdefault(dim, {
                        'score': 0.0, 'direction': 'neutral', 'drivers': [],
                    })
                    sv['drivers'].append(f"regime.{attr}={val}")

                    # Set direction based on regime value
                    val_str = str(val).lower()
                    if any(w in val_str for w in ('tighten', 'hawk', 'easing')):
                        if 'tighten' in val_str or 'hawk' in val_str:
                            sv['direction'] = 'tightening'
                            sv['score'] = 0.7
                        elif 'easing' in val_str or 'dovish' in val_str:
                            sv['direction'] = 'easing'
                            sv['score'] = 0.7
                    elif attr == 'inflation':
                        sv['direction'] = val_str
                        sv['score'] = 0.5
                    elif attr == 'growth':
                        sv['direction'] = val_str
                        sv['score'] = 0.5

        # ── Ensure at minimum some dimensions exist ─────────────────
        if not state_vector:
            state_vector = {
                'LIQUIDITY': {'score': 0.5, 'direction': 'neutral',
                               'drivers': ['placeholder']},
                'GROWTH': {'score': 0.5, 'direction': 'stable',
                            'drivers': ['placeholder']},
            }

        return state_vector

    def _generate_beliefs(self, narratives: list, macro_snapshot: MacroSnapshot) -> list:
        """Step 6 (V3.2): Generate ResearchBeliefs from narratives.

        V3.2: Accepts both Narrative (V3.0) and NarrativeObject (V3.2).
        Uses BeliefEngine.generate_from_narratives().
        """
        if not narratives:
            return []

        engine = self._ensure_belief_engine()
        if not engine:
            return []

        try:
            # Extract state vector for context
            state_vector = {}
            if hasattr(macro_snapshot, 'indicators') and macro_snapshot.indicators:
                state_vector = macro_snapshot.indicators
            elif hasattr(macro_snapshot, 'snapshot_data'):
                state_vector = macro_snapshot.snapshot_data.get('state_vector', {})

            beliefs = engine.generate_from_narratives(narratives, state_vector)
            return beliefs if isinstance(beliefs, list) else []
        except Exception as e:
            logger.warning("Belief generation failed: %s", e)
            return []

    # ── V3.2 Step Helpers ──────────────────────────────────────────────

    def _reason_narratives(
        self,
        narratives: list,
        macro_snapshot: MacroSnapshot,
    ) -> list:
        """Step 4 (V3.2): Reason about detected narratives → NarrativeObjects.

        Each flat Narrative (V3.0) is enriched with:
        - Causal chain reasoning
        - Supporting/contradicting evidence
        - Affected assets
        - Regime fit assessment
        """
        if not narratives:
            return []

        reasoner = self._ensure_narrative_reasoner()
        if not reasoner:
            logger.warning("NarrativeReasoner unavailable — skipping narrative reasoning")
            return []

        try:
            # Build state vector
            state_vector = {}
            if hasattr(macro_snapshot, 'indicators') and macro_snapshot.indicators:
                state_vector = macro_snapshot.indicators
            elif hasattr(macro_snapshot, 'snapshot_data'):
                state_vector = macro_snapshot.snapshot_data.get('state_vector', {})

            regime = macro_snapshot.regime_label if hasattr(macro_snapshot, 'regime_label') else ""

            # Get mental model outputs if available
            mental_model_outputs = []
            if hasattr(macro_snapshot, 'snapshot_data'):
                mental_model_outputs = macro_snapshot.snapshot_data.get('mental_model_outputs', [])

            # Filter to Narrative type only
            from src.research.narrative.schemas import Narrative
            v3_narratives = [n for n in narratives if isinstance(n, Narrative)]

            if not v3_narratives and narratives:
                # If all are already NarrativeObjects, just return them
                first = narratives[0]
                if hasattr(first, 'causal_chain'):
                    return narratives

            narrative_objects = reasoner.reason_batch(
                v3_narratives or narratives,
                state_vector=state_vector,
                regime=regime,
                mental_model_outputs=mental_model_outputs,
            )

            return narrative_objects
        except Exception as e:
            logger.warning("Narrative reasoning failed: %s", e)
            return []

    def _compete_narratives(
        self,
        macro_snapshot: MacroSnapshot,
        narrative_objects: list,
    ) -> NarrativeCompetitionResult | None:
        """Step 5 (V3.2): Generate competing narrative scenarios.

        If narrative_objects already contain competition results (from
        NarrativeCompetition), use those. Otherwise, run competition
        from state_vector.
        """
        # Check if we already have a competition result
        for n_obj in narrative_objects:
            if hasattr(n_obj, 'probability') and n_obj.probability > 0:
                # Already competed
                pass

        competition = self._ensure_narrative_competition()
        if not competition:
            logger.warning("NarrativeCompetition unavailable — skipping competition")
            return None

        try:
            state_vector = {}
            if hasattr(macro_snapshot, 'indicators') and macro_snapshot.indicators:
                state_vector = macro_snapshot.indicators
            elif hasattr(macro_snapshot, 'snapshot_data'):
                state_vector = macro_snapshot.snapshot_data.get('state_vector', {})

            regime = macro_snapshot.regime_label if hasattr(macro_snapshot, 'regime_label') else ""

            # Convert NarrativeObjects back to Narratives for the competition engine
            from src.research.narrative.schemas import Narrative
            v3_narratives = [
                Narrative(
                    id=n.id, title=n.title, description=n.description,
                    category=n.category, score=n.confidence,
                    source_signals=n.supporting_evidence,
                )
                for n in narrative_objects
            ] if narrative_objects else None

            result = competition.compete(
                state_vector=state_vector,
                regime=regime,
                existing_narratives=v3_narratives,
            )

            return result
        except Exception as e:
            logger.warning("Narrative competition failed: %s", e)
            return None

    def _generate_judgments(
        self,
        beliefs: list,
        narrative_objects: list,
    ) -> JudgmentOutput | None:
        """Step 7 (V3.2): Generate research judgments from beliefs.

        Each belief becomes a ResearchJudgment with:
        - Conviction statement ("I believe X")
        - Reasoning chain ("because A/B/C")
        - Confidence calibration
        - Falsification conditions
        """
        if not beliefs:
            logger.info("No beliefs — skipping research judgment")
            return None

        judgment_engine = self._ensure_judgment_engine()
        if not judgment_engine:
            logger.warning("ResearchJudgmentEngine unavailable — skipping judgments")
            return None

        try:
            # Get belief graph from belief engine
            graph = None
            belief_engine = self._ensure_belief_engine()
            if belief_engine and hasattr(belief_engine, 'graph'):
                graph = belief_engine.graph

            output = judgment_engine.judge(
                beliefs=beliefs,
                graph=graph,
                narrative_objects=narrative_objects,
            )

            return output
        except Exception as e:
            logger.warning("Research judgment failed: %s", e)
            return None

    def _build_memory_entry(self, result: CycleResult, cycle: int) -> ResearchMemoryEntry:
        """Build a ResearchMemoryEntry from the cycle result."""
        # ── V3.2: Collect judgment and narrative competition info ────
        judgment_summary = ""
        if result.research_judgments:
            j_output = result.research_judgments
            judgment_summary = (
                f"V3.2 Judgments: {j_output.count} beliefs judged, "
                f"stance={j_output.macro_stance}, "
                f"falsifiable={j_output.falsifiable_count}/{j_output.count}, "
                f"competition={j_output.competition_count}/{j_output.count}"
            )

        narrative_competition_summary = ""
        if result.narrative_competition:
            nc = result.narrative_competition
            narrative_competition_summary = (
                f"V3.2 Competition: {len(nc.narratives)} competing narratives, "
                f"dominant='{nc.dominant.title if nc.dominant else 'none'}'"
            )

        learning_note = ""
        if result.postmortem and result.postmortem.learning:
            learning_note = result.postmortem.learning
        if judgment_summary:
            learning_note = f"{judgment_summary}\n{narrative_competition_summary}\n{learning_note}".strip()

        entry = ResearchMemoryEntry(
            entry_id=f"mem-cycle-{cycle:04d}",
            cycle_number=cycle,
            date=datetime.now(timezone.utc),
            market_regime=result.macro_snapshot.regime if result.macro_snapshot else None,
            regime_label=result.macro_snapshot.regime_label if result.macro_snapshot else "",
            framework_used=result.framework_selection.ranked_ids[:3] if result.framework_selection else [],
            thesis=result.thesis,
            hypothesis_count=len(result.hypothesis_set.hypotheses) if result.hypothesis_set else 0,
            outcome=result.outcome_from_previous,
            diagnosis_notes=getattr(result.diagnosis_report, 'summary', '') if result.diagnosis_report else '',
            postmortem=result.postmortem,
            learning_note=learning_note,
        )

        # Record post-cycle state
        if self._evolution_pipeline:
            try:
                entry.frameworks_after = [
                    fw.framework_id
                    for fw in self._evolution_pipeline.get_active_frameworks()
                ]
                entry.principles_after = [
                    p.principle_id
                    for p in self._evolution_pipeline.get_active_principles()
                ]
            except Exception:
                pass

        return entry

    # ── Query ──────────────────────────────────────────────────────────

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def has_evolution(self) -> bool:
        self._ensure_evolution()
        return self._evolution_pipeline is not None and self._evolution_pipeline is not False

    def get_last_thesis(self) -> ResearchThesis | None:
        return self._previous_thesis

    def get_pending_outcomes(self) -> list[str]:
        return self.outcome_tracker.get_pending_theses()

    def summary(self) -> str:
        """Comprehensive cycle engine summary."""
        lines = [
            f"=== ResearchCycleEngine (Cycle {self._cycle_count}) ===",
            f"",
            f"Memory entries: {self.memory.total_entries} "
            f"(success rate: {self.memory.success_rate:.0%})",
            f"Pending outcomes: {self.outcome_tracker.pending_count}",
            f"Postmortems: {self.postmortem.report_count} "
            f"(success rate: {self.postmortem.success_rate:.0%})",
            f"",
            f"Framework Selector: {'connected' if self._evolution_pipeline else 'not connected'}",
            f"Thesis Generator: {'connected' if self._evolution_pipeline else 'not connected'}",
            f"Evolution Pipeline: {'available' if self.has_evolution else 'unavailable'}",
        ]
        if self._previous_thesis:
            lines.append(f"")
            lines.append(f"Active Thesis: {self._previous_thesis.title[:80]}")
        return "\n".join(lines)
