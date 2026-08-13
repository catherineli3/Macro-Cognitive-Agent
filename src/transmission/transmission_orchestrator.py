"""Transmission Orchestrator V3.1 — Milestone B + B.5 pipeline.

Flow:
    Prediction Outcome
        → Breakpoint Detection (with competition analysis)
        → Research Notes (researcher prose, not debug)
        → Transmission Graph Update (5-attribute edges)
        → Competition Resolution (promote/demote mechanisms)
        → Cascade to Belief Weights
        → Research Findings (Milestone B.5 engine)
        → ResearchFindingsReport
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.belief_versioning.contextual_belief import ContextualBeliefManager
from src.diagnosis.breakpoint_detector import BreakpointDetector, DiagnosisUpgrader
from src.schemas.diagnosis import DiagnosisReport
from src.schemas.evaluation_v3 import EvaluationReport
from src.schemas.hypothesis_v3_1 import (
    CandidateHypothesis,
    HypothesisEvolutionResult,
    SelectedHypothesis,
)
from src.schemas.prediction_v3 import PredictionBatch
from src.schemas.transmission_v3_1 import (
    BreakpointDiagnosis,
    ContextualBelief,
    ResearchFindingsReport,
    ResearchNote,
    TransmissionUpdateBatch,
)
from src.shared.logging import get_logger
from src.transmission.research_findings import ResearchFindingsEngine
from src.transmission.research_note import ResearchNoteGenerator
from src.transmission.transmission_graph import TransmissionGraph
from src.transmission.update_engine import TransmissionUpdateEngine

logger = get_logger(__name__)


class TransmissionOrchestrator:
    """Milestone B+B.5 orchestrator: Transmission Reasoning + Research Findings."""

    def __init__(self) -> None:
        self._graph = TransmissionGraph()
        self._detector = BreakpointDetector(self._graph)
        self._upgrader = DiagnosisUpgrader(self._graph)
        self._update_engine = TransmissionUpdateEngine(self._graph)
        self._belief_manager = ContextualBeliefManager()

        # B.5: Research engines
        self._note_generator = ResearchNoteGenerator(self._graph)
        self._findings_engine = ResearchFindingsEngine(self._graph)

        self._cycle_count: int = 0
        self._total_breakpoints: int = 0
        self._total_updates: int = 0
        self._research_reports: list[ResearchFindingsReport] = []

    # ── Bootstrap ────────────────────────────────────────────────────────

    def bootstrap_beliefs_from_hypotheses(
        self,
        result: HypothesisEvolutionResult,
    ) -> list[ContextualBelief]:
        beliefs = []
        for sh in result.selected_hypotheses:
            belief = self._belief_manager.create(
                belief_id=f"cb-{sh.candidate_id}",
                dimension=sh.dimension,
                hypothesis_text=sh.thesis,
                transmission_segments=(
                    sh.transmission_summary.split(" → ") if sh.transmission_summary else []
                ),
                default_regime=result.regime or "neutral",
            )
            default_ctx = belief.contexts.get(belief.default_context_key)
            if default_ctx:
                default_ctx.derived_weight = sh.confidence
            beliefs.append(belief)

        self._update_engine.register_beliefs(beliefs)
        logger.info("bootstrapped_beliefs count=%d regime=%s", len(beliefs), result.regime)
        return beliefs

    def bootstrap_from_prediction_batch(
        self,
        batch: PredictionBatch,
        regime: str = "neutral",
    ) -> list[ContextualBelief]:
        beliefs = []
        seen = set()
        for pred in batch.predictions:
            ch = pred.transmission_channel
            if ch in seen:
                continue
            seen.add(ch)
            dim = pred.dimension
            belief = self._belief_manager.create(
                belief_id=f"cb-{ch.replace('→', '_')}",
                dimension=dim,
                hypothesis_text=f"{dim} → {pred.indicator}",
                transmission_segments=[ch],
                default_regime=regime,
            )
            beliefs.append(belief)

        self._update_engine.register_beliefs(beliefs)
        return beliefs

    # ── Main Pipeline ────────────────────────────────────────────────────

    def run_cycle(
        self,
        evaluation: EvaluationReport,
        v3_diagnosis: DiagnosisReport | None = None,
        hypotheses: dict[str, CandidateHypothesis] = None,
        selected_hypotheses: list[SelectedHypothesis] = None,
        context_key: str = "",
        run_id: str = "",
    ) -> TransmissionCycleResult:
        if not run_id:
            run_id = f"tr-cycle-{uuid4().hex[:8]}"
        self._cycle_count += 1

        # Step 1: Breakpoint Detection
        if v3_diagnosis:
            enriched = self._upgrader.enrich(v3_diagnosis, evaluation, hypotheses, context_key)
            breakpoints = list(enriched.values())
        else:
            breakpoints = self._detector.diagnose_batch(
                evaluation,
                hypotheses or {},
                selected_hypotheses or [],
                context_key,
            )

        self._total_breakpoints += sum(1 for b in breakpoints if b.breakpoint_found)

        # Step 2: Generate Research Notes (B.5 upgrade: breakpoint → research prose)
        notes = self._note_generator.generate_batch(breakpoints, context_key)

        # Step 3: Competition Resolution (B.5: promote/demote competing mechanisms)
        competition_results = self._resolve_all_competitions(context_key)

        # Step 4: Generate transmission updates
        update_batch = self._update_engine.generate_updates(breakpoints, context_key, run_id)

        # Step 5: Apply to graph + cascade beliefs
        cascade_changes = self._update_engine.apply_and_cascade(update_batch)
        self._total_updates += len(update_batch.updates)

        # Step 6: Context splits
        new_contexts = []
        for bid in list(self._belief_manager._beliefs.keys()):
            new_ctx = self._belief_manager.check_context_split(bid)
            if new_ctx:
                new_contexts.append((bid, new_ctx))

        # Step 7: Recalculate all beliefs
        self._update_engine.recalculate_all_beliefs()

        # Step 8: Research Findings (B.5 engine)
        findings_report = self._findings_engine.analyze(
            breakpoints,
            context_key,
            self._cycle_count,
        )
        self._research_reports.append(findings_report)

        result = TransmissionCycleResult(
            cycle_id=run_id,
            cycle_number=self._cycle_count,
            context_key=context_key,
            breakpoints=breakpoints,
            research_notes=notes,
            update_batch=update_batch,
            cascade_changes=cascade_changes,
            new_contexts=new_contexts,
            competition_results=competition_results,
            findings_report=findings_report,
            graph_snapshot={
                "edges": self._graph.edge_count,
                "nodes": self._graph.node_count,
                "total_obs": self._graph.total_observations,
                "stability": self._graph.reliability_stability(),
                "competitions": self._graph.competition_count,
                "total_updates": self._graph._total_updates,
            },
            belief_summary={
                "total_beliefs": len(self._belief_manager._beliefs),
                "total_contexts": sum(
                    len(b.contexts) for b in self._belief_manager._beliefs.values()
                ),
                "total_observations": sum(
                    b.total_samples for b in self._belief_manager._beliefs.values()
                ),
            },
        )

        logger.info(
            "cycle_complete #%d breaks=%d updates=%d cascade=%d "
            "competitions=%d findings=%d notes=%d stability=%.2f",
            self._cycle_count,
            result.breakpoints_found,
            len(update_batch.updates),
            len(cascade_changes),
            len(competition_results),
            findings_report.total_findings,
            findings_report.total_notes,
            self._graph.reliability_stability(),
        )
        return result

    # ── Competition ──────────────────────────────────────────────────────

    def _resolve_all_competitions(self, ctx: str) -> list[dict]:
        results = []
        for src, tgt in self._graph.competing_pairs():
            cr = self._graph.resolve_competition(src, tgt, ctx)
            results.append(
                {
                    "source": src,
                    "target": tgt,
                    "winner": cr.winner.mechanism if cr.winner else "none",
                    "margin": cr.margin,
                    "is_conclusive": cr.is_conclusive,
                    "analysis": cr.analysis,
                }
            )
            # Apply competition updates if conclusive
            if cr.is_conclusive and cr.winner:
                for edge in cr.mechanisms:
                    if edge.edge_id != cr.winner.edge_id:
                        self._graph.demote_mechanism(src, tgt, edge.mechanism, ctx)
                self._graph.promote_mechanism(src, tgt, cr.winner.mechanism, ctx)

        return results

    # ── Accessors ────────────────────────────────────────────────────────

    @property
    def graph(self) -> TransmissionGraph:
        return self._graph

    @property
    def belief_manager(self) -> ContextualBeliefManager:
        return self._belief_manager

    @property
    def cycles_completed(self) -> int:
        return self._cycle_count

    @property
    def total_breakpoints(self) -> int:
        return self._total_breakpoints

    @property
    def latest_report(self) -> ResearchFindingsReport | None:
        return self._research_reports[-1] if self._research_reports else None

    def summary(self) -> str:
        lines = [
            "=== Transmission Orchestrator (Milestone B.5) ===",
            f"Cycles: {self._cycle_count}",
            f"Breakpoints: {self._total_breakpoints}",
            f"Updates: {self._total_updates}",
            f"Research reports: {len(self._research_reports)}",
        ]
        if self.latest_report:
            lines.append("")
            lines.append(self.latest_report.describe())
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Cycle Result (B.5 enhanced)
# ═══════════════════════════════════════════════════════════════════════════════


class TransmissionCycleResult:
    """Result of one B.5 transmission reasoning cycle."""

    def __init__(
        self,
        cycle_id: str,
        cycle_number: int,
        context_key: str,
        breakpoints: list[BreakpointDiagnosis],
        research_notes: list[ResearchNote],
        update_batch: TransmissionUpdateBatch,
        cascade_changes: dict[str, float],
        new_contexts: list[tuple[str, str]],
        competition_results: list[dict],
        findings_report: ResearchFindingsReport,
        graph_snapshot: dict,
        belief_summary: dict,
    ) -> None:
        self.cycle_id = cycle_id
        self.cycle_number = cycle_number
        self.context_key = context_key
        self.breakpoints = breakpoints
        self.research_notes = research_notes
        self.update_batch = update_batch
        self.cascade_changes = cascade_changes
        self.new_contexts = new_contexts
        self.competition_results = competition_results
        self.findings_report = findings_report
        self.graph_snapshot = graph_snapshot
        self.belief_summary = belief_summary
        self.completed_at = datetime.now(UTC)

    @property
    def breakpoints_found(self) -> int:
        return sum(1 for b in self.breakpoints if b.breakpoint_found)

    @property
    def actionable_breakpoints(self) -> int:
        return sum(1 for b in self.breakpoints if b.is_actionable)

    @property
    def healthy_predictions(self) -> int:
        return sum(1 for b in self.breakpoints if b.all_segments_healthy)

    @property
    def cascade_impact(self) -> float:
        if not self.cascade_changes:
            return 0.0
        return sum(abs(v) for v in self.cascade_changes.values()) / len(self.cascade_changes)

    @property
    def competitions_conclusive(self) -> int:
        return sum(1 for c in self.competition_results if c.get("is_conclusive"))

    def describe(self) -> str:
        new_ctx = ", ".join(f"{b[:12]}→{c}" for b, c in self.new_contexts)
        comp = (
            f", {self.competitions_conclusive} competitions resolved"
            if self.competition_results
            else ""
        )
        lines = [
            f"Cycle #{self.cycle_number} [{self.context_key or 'default'}]",
            f"  Predictions: {len(self.breakpoints)} ({self.healthy_predictions} healthy, "
            f"{self.breakpoints_found} broken)",
            f"  Updates: {len(self.update_batch.updates)} "
            f"(R:{self.update_batch.total_reinforcements} "
            f"W:{self.update_batch.total_weakenings} "
            f"F:{self.update_batch.total_failure_registrations} "
            f"C:{self.update_batch.total_competition_updates}){comp}",
            f"  Cascade: {len(self.cascade_changes)} beliefs adjusted",
            f"  New contexts: {new_ctx if new_ctx else 'none'}",
            f"  Research notes: {len(self.research_notes)}",
            f"  Findings: {self.findings_report.total_findings} total",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<TransmissionCycleResult #{self.cycle_number} breaks={self.breakpoints_found} findings={self.findings_report.total_findings}>"
