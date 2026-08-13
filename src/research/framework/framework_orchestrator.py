"""Framework Orchestrator — full lifecycle management (Milestone C).

Orchestrates the complete framework lifecycle:
    Principle clustering → Framework formation → Validation → Activation
    → Monitoring → Under Review → Retirement.

Integrates with FrameworkSet for multi-framework coexistence.
"""

from __future__ import annotations

from src.research.framework.cluster_detector import PrincipleClusterDetector
from src.research.framework.framework_evaluator import FrameworkEvaluator
from src.research.framework.framework_store import FrameworkStore
from src.schemas.research import (
    FrameworkSet,
    FrameworkStatus,
    ResearchFramework,
    ResearchPrinciple,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


class FrameworkOrchestrator:
    """Orchestrates the complete framework lifecycle.

    Coordinates:
        - Framework formation from principle clusters
        - Framework validation and activation
        - Performance monitoring
        - Retirement and replacement
        - FrameworkSet management (multi-framework coexistence)
    """

    MAX_ACTIVE_FRAMEWORKS = 5
    MIN_ACTIVE_FRAMEWORKS = 1

    def __init__(
        self,
        cluster_detector: PrincipleClusterDetector | None = None,
        evaluator: FrameworkEvaluator | None = None,
        store: FrameworkStore | None = None,
    ) -> None:
        self._cluster_detector = cluster_detector or PrincipleClusterDetector()
        self._evaluator = evaluator or FrameworkEvaluator()
        self._store = store or FrameworkStore()
        self._framework_set = FrameworkSet()

    # ── Formation ─────────────────────────────────────────────────────────

    def form_candidate(
        self,
        principle_ids: list[str],
        principles: dict[str, ResearchPrinciple],
        name: str = "",
        thesis: str = "",
        cycle: int = 0,
    ) -> ResearchFramework | None:
        """Attempt to form a candidate framework from a principle cluster.

        Requires >=5 principles with validated+ strength.
        """
        if len(principle_ids) < PrincipleClusterDetector.MIN_CLUSTER_SIZE:
            logger.info(
                "Not enough principles for framework: %d < %d",
                len(principle_ids),
                PrincipleClusterDetector.MIN_CLUSTER_SIZE,
            )
            return None

        # Verify principle quality
        cluster_principles: dict[str, ResearchPrinciple] = {}
        for pid in principle_ids:
            pr = principles.get(pid)
            if pr and pr.strength.value in ("validated", "mature", "foundational"):
                cluster_principles[pid] = pr
        if len(cluster_principles) < PrincipleClusterDetector.MIN_CLUSTER_SIZE:
            return None

        # Compute initial accuracy
        init_accuracy = self._evaluator.compute_accuracy(
            ResearchFramework(principles=list(cluster_principles.keys())),
            cluster_principles,
        )

        # Auto-generate name if not provided
        if not name:
            domains = set(p.domain for p in cluster_principles.values() if p.domain)
            name = f"Framework-{'-'.join(sorted(domains)[:3])}" if domains else "Unnamed-Framework"

        # Auto-generate thesis if not provided
        if not thesis:
            thesis_parts = []
            for pid, p in list(cluster_principles.items())[:3]:
                thesis_parts.append(p.statement)
            thesis = ". ".join(thesis_parts) + "."
            if len(thesis) < 100:
                thesis = (
                    f"Framework synthesizing {len(cluster_principles)} principles "
                    f"across {len(domains)} domains. " + thesis
                )

        framework = ResearchFramework(
            name=name,
            thesis=thesis,
            status=FrameworkStatus.CANDIDATE,
            principles=list(cluster_principles.keys()),
            principle_weights={pid: 1.0 / len(cluster_principles) for pid in cluster_principles},
            accuracy_trajectory=[init_accuracy],
            created_at_cycle=cycle,
            created_from="principle_cluster",
            domain_coverage={
                d: len([p for p in cluster_principles.values() if p.domain == d])
                / len(cluster_principles)
                for d in domains
            },
        )
        framework.compute_confidence(cluster_principles)  # Pre-compute

        self._store.save(framework)
        logger.info("Formed candidate framework: %s (%d principles)", name, len(cluster_principles))
        return framework

    def attempt_formation(
        self, principles: dict[str, ResearchPrinciple], cycle: int = 0
    ) -> list[ResearchFramework]:
        """Detect clusters and form candidate frameworks."""
        clusters = self._cluster_detector.detect_clusters(principles)
        candidates = []

        for cluster in clusters:
            fw = self.form_candidate(cluster, principles, cycle=cycle)
            if fw:
                candidates.append(fw)

        return candidates

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def validate_candidates(self, cycle: int = 0) -> list[str]:
        """Check candidate frameworks for validation eligibility."""
        promoted: list[str] = []
        for fw in self._store.get_candidates():
            new_status = self._evaluator.evaluate(fw, cycle)
            if new_status == FrameworkStatus.ACTIVE:
                # Try to add to framework set
                if not self._framework_set.is_at_capacity:
                    self._store.activate(fw.framework_id)
                    self._framework_set.add_framework(
                        fw.framework_id,
                        initial_weight=1.0 / max(self._framework_set.active_count, 1),
                    )
                    promoted.append(fw.framework_id)
                else:
                    # At capacity: compare with weakest
                    self._handle_capacity_competition(fw)
        return promoted

    def evaluate_active(self, cycle: int = 0) -> list[str]:
        """Evaluate all active frameworks for status changes."""
        status_changes: list[str] = []

        for fw in self._store.get_active():
            new_status = self._evaluator.evaluate(fw, cycle)
            if new_status == FrameworkStatus.UNDER_REVIEW:
                self._store.mark_review(fw.framework_id)
                status_changes.append(f"{fw.framework_id}:active→review")
            elif new_status == FrameworkStatus.RETIRED:
                self._retire_framework(fw)
                status_changes.append(f"{fw.framework_id}:active→retired")

        # Also check under-review frameworks for recovery
        for fw in self._store.get_under_review():
            if self._evaluator.trend(fw.framework_id) == "improving":
                self._store.activate(fw.framework_id)
                status_changes.append(f"{fw.framework_id}:review→active")

        return status_changes

    def _handle_capacity_competition(self, new_fw: ResearchFramework) -> None:
        """Handle case where framework set is at capacity."""
        # Find weakest active framework
        weakest_id = None
        weakest_score = float("inf")
        for fid in self._framework_set.active_frameworks:
            fw = self._store.get(fid)
            if fw:
                score = self._evaluator.compute_accuracy(fw, {})
                if score < weakest_score:
                    weakest_score = score
                    weakest_id = fid

        new_score = self._evaluator.compute_accuracy(new_fw, {})
        if weakest_id and new_score > weakest_score:
            self._retire_framework(self._store.get(weakest_id))
            self._store.activate(new_fw.framework_id)
            self._framework_set.replace_weakest(
                new_fw.framework_id,
                1.0 / self._framework_set.active_count,
                weakest_id,
            )
            logger.info(
                "Replaced framework %s (score=%.3f) with %s (score=%.3f)",
                weakest_id,
                weakest_score,
                new_fw.framework_id,
                new_score,
            )

    def _retire_framework(self, framework: ResearchFramework | None, reason: str = "") -> None:
        if not framework:
            return
        self._store.retire(framework.framework_id, reason)
        self._framework_set.retire_framework(framework.framework_id)

    def retire_by_id(self, framework_id: str, reason: str = "") -> bool:
        """Retire a framework by ID."""
        fw = self._store.get(framework_id)
        if not fw:
            return False
        self._retire_framework(fw, reason)
        return True

    # ── Framework Set Management ──────────────────────────────────────────

    def get_framework_set(self) -> FrameworkSet:
        return self._framework_set

    def compute_framework_set_weights(
        self, frameworks: dict[str, ResearchFramework], principles: dict[str, ResearchPrinciple]
    ) -> None:
        """Recalculate framework weights based on confidence + recency + coverage."""
        if not self._framework_set.active_frameworks:
            return

        scores: dict[str, float] = {}
        for fid in self._framework_set.active_frameworks:
            fw = frameworks.get(fid)
            if not fw:
                continue
            confidence = fw.compute_confidence(principles)
            accuracy = self._evaluator.compute_accuracy(fw, principles)
            domain_coverage = sum(fw.domain_coverage.values()) / max(len(fw.domain_coverage), 1)
            scores[fid] = 0.4 * confidence + 0.4 * accuracy + 0.2 * domain_coverage

        total = sum(scores.values())
        if total > 0:
            for fid in scores:
                self._framework_set.framework_weights[fid] = scores[fid] / total

    def get_synthesized_view(
        self, frameworks: dict[str, ResearchFramework], principles: dict[str, ResearchPrinciple]
    ) -> str:
        """Get a synthesized view across all active frameworks."""
        if not self._framework_set.active_frameworks:
            return "No active frameworks."

        parts = []
        for fid in self._framework_set.active_frameworks:
            fw = frameworks.get(fid)
            if not fw:
                continue
            w = self._framework_set.weight_for(fid)
            explain = fw.compute_explainability(principles)
            parts.append(
                f"  [{w:.0%}] {fw.name}: "
                f"confidence={explain.confidence:.2f}, "
                f"win_rate={explain.historical_win_rate:.0%}, "
                f"principles={explain.supporting_principles_count}"
            )

        synthesis = self._framework_set.synthesis_strategy.value
        return (
            f"Synthesized view ({synthesis}, {len(self._framework_set.active_frameworks)} frameworks):\n"
            + "\n".join(parts)
        )

    # ── Recording ─────────────────────────────────────────────────────────

    def record_principle_activation(self, principle_ids: list[str], cycle: int = 0) -> None:
        """Feed principle activation data to the cluster detector."""
        self._cluster_detector.record_activation(principle_ids, cycle)

    def record_accuracy(self, framework_id: str, accuracy: float, cycle: int = 0) -> None:
        """Record accuracy and update store."""
        self._evaluator.record_accuracy(framework_id, accuracy, cycle)
        self._store.update_accuracy(framework_id, accuracy)

    @property
    def active_framework_ids(self) -> list[str]:
        return list(self._framework_set.active_frameworks)

    def summary(self) -> str:
        fw_summary = self._store.summary()
        fs_summary = self._framework_set.describe()
        return f"FrameworkOrchestrator:\n  {fw_summary}\n  {fs_summary}"
