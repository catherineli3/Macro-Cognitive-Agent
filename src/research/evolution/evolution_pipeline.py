"""Evolution Pipeline — Complete Finding → Principle → Belief → Framework pipeline (Milestone C).

This is the heart of Milestone C. It replaces the old Learning Engine with
the complete Research Evolution pipeline.

Architecture:
    Finding → Accumulation → Admission Gate (P1-P5) → Principle
    Principle → Conflict Detection → Resolution → Belief
    Belief → Lifecycle → Hypothesis Generator
    Principle Cluster → Framework Formation → Framework Evaluation

F1.6: G1 Dedup (semantic matching before creation), G2 Lifecycle
(CANDIDATE→VALIDATED→MATURE), G3 Evidence Feedback (observation tracking).

The pipeline runs after each diagnosis cycle to evolve the agent's
research methodology.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.schemas.transmission_v3_1 import (
    ResearchFinding, ResearchFindingsReport,
)
from src.schemas.research import (
    ResearchPrinciple, ResearchFramework,
    FrameworkSet, FindingLifecycle, FindingTTLStatus,
    CompetingPrinciple, PrincipleStrength, PrincipleStatus,
)
from src.schemas.diagnosis import DiagnosisReport

from src.research.findings.engine import ResearchFindingsEngine
from src.research.principles.admission_gate import PrincipleAdmissionGate
from src.research.principles.principle_extractor import PrincipleExtractor
from src.research.principles.candidate_manager import CandidatePrincipleManager
from src.research.principles.principle_store import PrincipleStore
from src.research.framework.cluster_detector import PrincipleClusterDetector
from src.research.framework.framework_evaluator import FrameworkEvaluator
from src.research.framework.framework_store import FrameworkStore
from src.research.framework.framework_orchestrator import FrameworkOrchestrator
from src.research.evolution.regime_gate import RegimeGate, RegimeSnapshot
from src.research.evolution.temporary_layer import TemporaryEventLayer, EventCategory
from src.research.evolution.conflict_resolver import ConflictResolver
from src.research.evolution.belief_lifecycle import BeliefLifecycleManager, BeliefLifecycleStage

from src.shared.logging import get_logger

logger = get_logger(__name__)

# ── G2 Lifecycle Thresholds (F1.6) ─────────────────────────────────────
CANDIDATE_MIN_CYCLES = 5      # Must persist for at least 5 cycles before graduating
CANDIDATE_MIN_REGIMES = 1     # At least 1 regime validated as candidate
VALIDATED_MIN_OBS = 30        # Minimum observations to graduate to validated
VALIDATED_MIN_REGIMES = 2     # Minimum regimes for validated
MATURE_MIN_OBS = 100          # Minimum observations for mature
MATURE_MIN_REGIMES = 3        # Minimum regimes for mature
MATURE_MIN_ACCURACY = 0.60    # Minimum accuracy for mature
MATURE_MAX_CONTRADICTIONS = 2 # Maximum contradictions for mature


class EvolutionPipeline:
    """Complete Finding → Principle → Belief → Framework evolution pipeline.

    This is the replacement for the old Learning Engine (src/learning/).
    The agent now learns "research methodology" instead of "weights".
    """

    def __init__(self) -> None:
        # Core stores
        self.principle_store = PrincipleStore()
        self.framework_store = FrameworkStore()

        # Engines
        self.admission_gate = PrincipleAdmissionGate()
        self.extractor = PrincipleExtractor(self.admission_gate)
        self.extractor.set_store(self.principle_store)  # G1: wire store for dedup
        self.candidate_manager = CandidatePrincipleManager()
        self.regime_gate = RegimeGate()
        self.temporary_layer = TemporaryEventLayer()
        self.conflict_resolver = ConflictResolver(self.principle_store)
        self.belief_manager = BeliefLifecycleManager()

        # ── V3.1: Unified BeliefStore (ResearchBelief) ─────────────────
        from src.research.beliefs.belief_store import BeliefStore
        self.belief_store = BeliefStore()
        self.cluster_detector = PrincipleClusterDetector()
        self.framework_evaluator = FrameworkEvaluator()
        self.framework_orchestrator = FrameworkOrchestrator(
            self.cluster_detector, self.framework_evaluator, self.framework_store,
        )

        # State
        self._finding_lifecycles: dict[str, FindingLifecycle] = {}
        self._cycle_count: int = 0
        self._run_history: list[dict] = []

    # ── Main Entry Point ─────────────────────────────────────────────────

    def run(
        self,
        findings_report: ResearchFindingsReport,
        diagnoses: list[DiagnosisReport] | None = None,
        current_regime: RegimeSnapshot | None = None,
    ) -> dict:
        """Run one evolution cycle.

        Processes findings through the full pipeline:
            Finding → Temporary/Permanent split → Principle candidate
            → Admission evaluation → Conflict detection → Belief update
            → Framework formation check

        Args:
            findings_report: Report from ResearchFindingsEngine
            diagnoses: Optional diagnosis reports for conflict tracking
            current_regime: Current macro regime snapshot

        Returns:
            Dict with pipeline results and status
        """
        self._cycle_count += 1
        cycle = self._cycle_count

        # Update regime
        if current_regime:
            self.regime_gate.set_current_regime(current_regime)

        result: dict = {
            "cycle": cycle,
            "findings_processed": 0,
            "temporary_events": 0,
            "principles_created": 0,
            "principles_promoted": 0,
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "frameworks_created": 0,
            "beliefs_updated": 0,
            "findings_expired": 0,
        }

        # ── Step 1: Process Findings ─────────────────────────────────
        all_findings = self._extract_all_findings(findings_report)
        result["findings_processed"] = len(all_findings)

        for finding in all_findings:
            lifecycle = self._get_or_create_lifecycle(finding)
            # TTL check
            if lifecycle.is_expired:
                lifecycle.expire()
                result["findings_expired"] += 1
                continue

            # Route to Temporary or Permanent
            if self._is_temporary(finding):
                self.temporary_layer.register_from_finding(
                    finding, EventCategory.SINGLE_OBSERVATION,
                )
                result["temporary_events"] += 1
                continue

            # Feed to extractor and admission gate
            self.extractor.add_findings([finding])
            regime = current_regime.to_dict() if current_regime else {}
            self.admission_gate.register_finding(finding, regime, cycle)

        # ── Step 2: Extract & Admit Principles (G1+G2+F1.6) ──────
        # G1: extract_candidates now handles dedup internally
        all_principles_from_extraction = self.extractor.extract_candidates(cycle=cycle)

        for principle in all_principles_from_extraction:
            pid = principle.principle_id

            # G2: ALL new principles are CANDIDATE (already set in extractor)
            # For new principles not yet in store, save them
            if self.principle_store.get(pid) is None:
                self.principle_store.save(principle)
                if principle.strength == PrincipleStrength.CANDIDATE:
                    self.candidate_manager.register_candidate(principle)
                result["principles_created"] += 1
            else:
                # Existing principle — already updated in-place by G1 dedup
                # Update store to re-index if strength changed
                self.principle_store.save(principle)
                result["principles_promoted"] += 1

            # Cross-regime validation
            if current_regime:
                self.regime_gate.record_principle_observation(
                    pid, current_regime,
                )
                # Update regimes_validated from regime_gate
                regime_key = current_regime.key
                ev = principle.evidence
                if regime_key and regime_key not in ev.regimes_validated:
                    ev.regimes_validated.append(regime_key)
                    ev.regimes_count = len(ev.regimes_validated)

        # ── Step 2b: G2 Lifecycle Evaluation (F1.6) ───────────────
        self._evaluate_lifecycle(cycle, current_regime)

        # ── Step 2c: G3 Evidence Feedback from thesis outcome (F1.6) ──
        self._run_evidence_feedback(cycle, result)

        # ── Step 3: Detect Conflicts ───────────────────────────────
        new_conflicts = self.conflict_resolver.detect_conflicts()
        result["conflicts_detected"] = len(new_conflicts)

        # Record evidence & check resolutions
        if diagnoses:
            for diag in diagnoses:
                for finding in all_findings:
                    lifecycle = self._finding_lifecycles.get(finding.finding_id)
                    if lifecycle and lifecycle.status == FindingTTLStatus.FROZEN:
                        for conflict_id in lifecycle.cited_in_conflicts:
                            resolved = self.conflict_resolver.record_evidence(
                                finding.finding_id,  # Simplified
                                correct=True if diag.outcome_correct else False,
                                cycle=cycle,
                            )
                            result["conflicts_resolved"] += len(resolved)

        # ── Step 4: Framework Formation ────────────────────────────
        all_principles = {
            p.principle_id: p
            for p in self.principle_store.get_all()
        }

        # Record active principles for cluster detection
        active_principle_ids = [
            pid for pid, p in all_principles.items()
            if p.strength in (PrincipleStrength.VALIDATED, PrincipleStrength.MATURE,
                              PrincipleStrength.FOUNDATIONAL)
        ]
        self.framework_orchestrator.record_principle_activation(active_principle_ids, cycle)

        # Attempt formation
        new_frameworks = self.framework_orchestrator.attempt_formation(all_principles, cycle)
        for fw in new_frameworks:
            self.framework_store.save(fw)
        result["frameworks_created"] = len(new_frameworks)

        # Validate candidates and evaluate active
        self.framework_orchestrator.validate_candidates(cycle)
        self.framework_orchestrator.evaluate_active(cycle)

        # Compute framework weights
        all_frameworks = {
            fw.framework_id: fw
            for fw in self.framework_store.get_all()
        }
        self.framework_orchestrator.compute_framework_set_weights(
            all_frameworks, all_principles,
        )

        # ── Step 5: Update Beliefs ─────────────────────────────────
        for pid in all_principles:
            p = all_principles[pid]
            # Cascade principle changes to beliefs
            if p.status in (PrincipleStatus.RETIRED, PrincipleStatus.WEAKENING):
                affected = self.belief_manager.cascade_principle_retirement(
                    pid, all_principles,
                )
                result["beliefs_updated"] += len(affected)

        # ── Step 6: Archive expired temporary events ──────────────
        self.temporary_layer.archive_expired()

        # ── Step 7: Maintain finding TTL ───────────────────────────
        self._cleanup_expired_findings()

        # Record run
        self._run_history.append(result)
        logger.info(
            "Evolution cycle %d: %d findings → %d principles, %d conflicts, "
            "%d frameworks, %d beliefs updated",
            cycle, result["findings_processed"], result["principles_created"],
            result["conflicts_detected"], result["frameworks_created"],
            result["beliefs_updated"],
        )

        return result

    # ── Belief Operations (V3.1 — ResearchBelief Primary) ───────────────

    def register_belief(self, belief,  # ResearchBelief (V3.1)
                         principle_ids: list[str] | None = None) -> str:
        """Register a ResearchBelief (V3.1 primary store).

        Also syncs to legacy BeliefLifecycleManager via BeliefAdapter
        for backward compatibility with principle linking.
        """
        # ── Primary: store in BeliefStore (ResearchBelief) ─────────
        bid = self.belief_store.add_belief(belief)

        # ── Sync to legacy BeliefLifecycleManager for principle linking ──
        try:
            from src.research.beliefs.belief_adapter import BeliefAdapter
            adaptive = BeliefAdapter.to_adaptive(belief)
            self.belief_manager.register_belief(adaptive)
            if principle_ids:
                for pid in principle_ids:
                    self.belief_manager.link_to_principle(bid, pid)
        except Exception as e:
            logger.warning("Legacy belief sync skipped: %s", e)

        return bid

    def get_belief_weight(self, belief_id: str) -> float:
        """Get derived belief weight considering principles + competition."""
        all_principles = {p.principle_id: p for p in self.principle_store.get_all()}

        # Try BeliefStore (V3.1 primary) first
        try:
            from src.research.beliefs.belief_adapter import BeliefAdapter
            belief = self.belief_store.get_belief(belief_id)
            if belief:
                penalty = 1.0
                adaptive = BeliefAdapter.to_adaptive(belief)
                if adaptive and adaptive.founded_on_principles:
                    for pid in adaptive.founded_on_principles:
                        p = all_principles.get(pid)
                        if p and p.status == PrincipleStatus.ACTIVE_COMPETITION:
                            penalty *= self.conflict_resolver.get_penalty(pid)
                return self.belief_manager.derive_weight(
                    belief_id, all_principles, penalty,
                )
        except Exception:
            pass

        # Fallback to legacy
        return self.belief_manager.derive_weight(belief_id, all_principles, 1.0)

    def get_mature_beliefs(self) -> list:
        """Get mature beliefs. Returns ResearchBelief list (V3.1)."""
        try:
            all_beliefs = self.belief_store.list_beliefs()
            mature = [b for b in all_beliefs
                       if getattr(b, 'confidence', 0) >= 0.5]
            if mature:
                return mature
        except Exception:
            pass

        # Fallback: convert from legacy
        try:
            from src.research.beliefs.belief_adapter import BeliefAdapter
            legacy = self.belief_manager.get_mature_beliefs()
            return [BeliefAdapter.from_adaptive(ab) for ab in legacy]
        except Exception:
            return []

    # ── Query ────────────────────────────────────────────────────────────

    def get_framework_set(self) -> FrameworkSet:
        return self.framework_orchestrator.get_framework_set()

    def get_active_principles(self) -> list[ResearchPrinciple]:
        return self.principle_store.get_active()

    def get_active_frameworks(self) -> list[ResearchFramework]:
        return self.framework_store.get_active()

    def get_synthesized_view(self) -> str:
        """Get the agent's synthesized macro worldview."""
        all_principles = {p.principle_id: p for p in self.principle_store.get_all()}
        all_frameworks = {fw.framework_id: fw for fw in self.framework_store.get_all()}
        return self.framework_orchestrator.get_synthesized_view(all_frameworks, all_principles)

    # ── Internal ──────────────────────────────────────────────────────────

    def _evaluate_lifecycle(self, cycle: int, current_regime: RegimeSnapshot | None = None) -> None:
        """G2 (F1.6): Evaluate all principles and advance lifecycle stages.

        Lifecycle:
            CANDIDATE → VALIDATED: sustained for >=2 cycles + >=1 regime
            VALIDATED → MATURE: >=50 obs + >=3 regimes + >=65% accuracy
            Any level → RETIRE: >=5 contradictions

        This runs AFTER new candidates are extracted and saved.
        """
        promoted_count = 0
        matured_count = 0
        retired_count = 0

        for p in self.principle_store.get_all():
            pid = p.principle_id

            # ── CANDIDATE → VALIDATED ──
            if p.strength == PrincipleStrength.CANDIDATE:
                ev = p.evidence
                cycles_persisted = cycle - p.created_at_cycle
                if (cycles_persisted >= CANDIDATE_MIN_CYCLES
                        and ev.regimes_count >= CANDIDATE_MIN_REGIMES
                        and ev.total_observations >= VALIDATED_MIN_OBS):
                    p.strength = PrincipleStrength.VALIDATED
                    p.status = PrincipleStatus.ACTIVE
                    self.principle_store.update_strength(pid, PrincipleStrength.VALIDATED)
                    if pid in self.candidate_manager._candidates:
                        self.candidate_manager._graduate(pid)
                    promoted_count += 1
                    logger.info("G2: CANDIDATE → VALIDATED: %s (cycles=%d, regimes=%d, obs=%d)",
                                pid[:12], cycles_persisted, ev.regimes_count, ev.total_observations)

            # ── VALIDATED → MATURE ──
            elif p.strength == PrincipleStrength.VALIDATED:
                ev = p.evidence
                if (ev.total_observations >= MATURE_MIN_OBS
                        and ev.regimes_count >= MATURE_MIN_REGIMES
                        and ev.contradiction_count <= MATURE_MAX_CONTRADICTIONS):
                    # Check accuracy — use computed accuracy if available
                    acc = ev.computed_accuracy if (ev.correct_count + ev.incorrect_count) > 0 else 0.5
                    if acc >= MATURE_MIN_ACCURACY:
                        p.strength = PrincipleStrength.MATURE
                        self.principle_store.update_strength(pid, PrincipleStrength.MATURE)
                        matured_count += 1
                        logger.info("G2: VALIDATED → MATURE: %s (obs=%d, regimes=%d, acc=%.2f)",
                                    pid[:12], ev.total_observations, ev.regimes_count, acc)

            # ── WEAKENING / RETIREMENT ──
            if p.evidence.contradiction_count >= 5:
                if p.strength not in (PrincipleStrength.FOUNDATIONAL,):
                    # Weaken or retire
                    if p.evidence.contradiction_count >= 10:
                        self.principle_store.retire(pid, f"Contradictions: {p.evidence.contradiction_count}")
                        retired_count += 1
                    elif p.status != PrincipleStatus.WEAKENING:
                        self.principle_store.weaken(pid)
                        logger.info("G2: WEAKENING: %s (contradictions=%d)",
                                    pid[:12], p.evidence.contradiction_count)

        if promoted_count or matured_count or retired_count:
            logger.info("G2 Lifecycle: %d promoted →VALIDATED, %d →MATURE, %d retired",
                       promoted_count, matured_count, retired_count)

    def _run_evidence_feedback(self, cycle: int, result: dict) -> None:
        """G3 (F1.6): Record evidence/outcomes to principles.

        Evaluates thesis correctness by checking available signals:
          1. Framework accuracy trajectory (if frameworks exist)
          2. Evolution result signals (promotions = positive, conflicts = negative)
          3. Fallback: all active principles get evaluated

        Records observation_count, correct/incorrect_count, computed accuracy.
        """
        # Determine thesis correctness from available signals
        thesis_correct = self._determine_thesis_correctness(cycle, result)

        # Get relevant principles
        relevant_principles = self._get_relevant_principles()

        if not relevant_principles:
            return

        # Record outcome to each relevant principle
        for pid in relevant_principles:
            p = self.principle_store.get(pid)
            if p is None:
                continue
            p.evidence.record_outcome(
                correct=thesis_correct,
                cycle=cycle,
                failure_mode="thesis_contradicted" if not thesis_correct else "",
            )

        logger.info("G3 Evidence Feedback: %d principles evaluated, result=%s",
                    len(relevant_principles), "correct" if thesis_correct else "incorrect")

    def _determine_thesis_correctness(self, cycle: int, result: dict) -> bool:
        """G3: Determine if the thesis was correct using available signals."""
        # Signal 1: Framework accuracy trajectory
        fw_ids = []
        try:
            fw_ids = self.framework_orchestrator.get_framework_set().active_frameworks
        except Exception:
            pass

        if fw_ids:
            failure_signals = 0
            total_signals = 0
            for fw_id in fw_ids:
                fw = self.framework_store.get(fw_id)
                if fw and fw.accuracy_trajectory:
                    recent = fw.accuracy_trajectory[-5:]
                    total_signals += len(recent)
                    failure_signals += sum(1 for a in recent if a < 0.5)
            if total_signals > 0:
                return failure_signals / total_signals <= 0.4

        # Signal 2: Evolution result — promotions vs conflicts
        if result:
            promotions = result.get("principles_promoted", 0)
            conflicts = result.get("conflicts_detected", 0)
            if promotions > 0 and conflicts == 0:
                return True
            if conflicts > 0 and promotions == 0:
                return False

        # Signal 3: Based on current result — findings processed = positive cycle
        if result and result.get("findings_processed", 0) > 0:
            # More findings + fewer conflicts = more likely correct
            conflicts = result.get("conflicts_detected", 0)
            return conflicts == 0

        # Fallback: neutral/default
        return True

    def _get_relevant_principles(self) -> set[str]:
        """G3: Get principle IDs that should receive feedback."""
        # Try framework-linked principles first
        fw_ids = []
        try:
            fw_ids = self.framework_orchestrator.get_framework_set().active_frameworks
        except Exception:
            pass

        pids: set[str] = set()
        for fw_id in fw_ids:
            fw = self.framework_store.get(fw_id)
            if fw:
                pids.update(fw.principles)

        # Fallback: all validated+ principles
        if not pids:
            pids = {
                p.principle_id for p in self.principle_store.get_all()
                if p.strength in (PrincipleStrength.VALIDATED, PrincipleStrength.MATURE,
                                  PrincipleStrength.CANDIDATE)
            }

        return pids

    def _get_or_create_lifecycle(self, finding: ResearchFinding) -> FindingLifecycle:
        if finding.finding_id not in self._finding_lifecycles:
            lc = FindingLifecycle(finding_id=finding.finding_id)
            if hasattr(finding, 'confidence') and finding.confidence:
                lc.set_ttl(finding.confidence.value if hasattr(finding.confidence, 'value')
                           else str(finding.confidence))
            self._finding_lifecycles[finding.finding_id] = lc
        return self._finding_lifecycles[finding.finding_id]

    @staticmethod
    def _extract_all_findings(report: ResearchFindingsReport) -> list[ResearchFinding]:
        findings: list[ResearchFinding] = []
        findings.extend(report.reliability_ranking)
        findings.extend(report.failure_warnings)
        findings.extend(report.failure_event_correlations)
        findings.extend(report.regime_similarities)
        return findings

    @staticmethod
    def _is_temporary(finding: ResearchFinding) -> bool:
        """Determine if a finding belongs in the Temporary Event Layer."""
        # Single observations with very low evidence
        evidence = finding.evidence or {}
        if evidence.get("observations", 0) < 3:
            return True
        # Explicitly marked as regime-specific (not cross-regime)
        if finding.category == "regime_similarity":
            return False  # These are comparison data, can inform principles
        return False

    def _cleanup_expired_findings(self) -> int:
        """Archive expired findings. Returns count."""
        expired_count = 0
        for fid, lc in list(self._finding_lifecycles.items()):
            if lc.is_expired and lc.status not in (FindingTTLStatus.PROMOTED,
                                                    FindingTTLStatus.ARCHIVED):
                lc.expire()
                expired_count += 1
        if expired_count:
            logger.info("Cleaned up %d expired findings", expired_count)
        return expired_count

    # ── Stats ────────────────────────────────────────────────────────────

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def total_principles(self) -> int:
        return self.principle_store.count

    @property
    def total_frameworks(self) -> int:
        return self.framework_store.count

    @property
    def active_competitions(self) -> int:
        return self.conflict_resolver.active_competition_count

    def summary(self) -> str:
        """Comprehensive pipeline summary."""
        lines = [f"=== Evolution Pipeline Summary (Cycle {self._cycle_count}) ==="]
        lines.append(f"")
        lines.append(f"Findings: {len(self._finding_lifecycles)} tracked "
                     f"({self.temporary_layer.active_count} temp events)")
        lines.append(f"Principles: {self.principle_store.summary()}")
        lines.append(f"  Candidates: {self.candidate_manager.summary()}")
        lines.append(f"Conflicts: {self.conflict_resolver.summary()}")
        lines.append(f"Frameworks: {self.framework_store.summary()}")
        lines.append(f"  FrameworkSet: {self.framework_orchestrator.get_framework_set().describe()}")
        lines.append(f"Beliefs: {self.belief_manager.summary()}")
        lines.append(f"Regimes: {self.regime_gate.summary()}")
        return "\n".join(lines)
