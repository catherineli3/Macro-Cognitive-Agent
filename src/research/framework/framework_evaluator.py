"""Framework Evaluator — tracks framework accuracy and performance (Milestone C).

Evaluates how well a framework's principles predict regime classification
and tracks accuracy over time.
"""

from __future__ import annotations

from src.schemas.research import FrameworkStatus, ResearchFramework, ResearchPrinciple
from src.shared.logging import get_logger

logger = get_logger(__name__)


class FrameworkEvaluator:
    """Evaluates framework performance and determines lifecycle transitions.

    Handles:
        - Accuracy tracking over cycles
        - Framework validation (>=70% over 30 cycles)
        - Under-review detection (accuracy declining)
        - Retirement triggers (accuracy < 40% over 50 cycles)
    """

    MIN_VALIDATION_CYCLES = 30
    MIN_VALIDATION_ACCURACY = 0.70
    REVIEW_ACCURACY_THRESHOLD = 0.50
    RETIREMENT_CYCLES = 50
    RETIREMENT_ACCURACY_THRESHOLD = 0.40
    MIN_PRINCIPLES_FOR_ACTIVE = 3

    def __init__(self) -> None:
        self._accuracy_history: dict[str, list[float]] = {}  # framework_id → [scores]
        self._validation_results: dict[str, list[bool]] = {}  # framework_id → [pass/fail]

    def record_accuracy(self, framework_id: str, accuracy: float, cycle: int = 0) -> None:
        """Record a framework's accuracy for a cycle."""
        self._accuracy_history.setdefault(framework_id, []).append(accuracy)

    def evaluate(self, framework: ResearchFramework, cycle: int = 0) -> FrameworkStatus:
        """Evaluate a framework's current status based on performance history.

        Returns the appropriate FrameworkStatus.
        """
        history = self._accuracy_history.get(framework.framework_id, [])

        if framework.status == FrameworkStatus.CANDIDATE:
            if len(history) >= self.MIN_VALIDATION_CYCLES:
                recent = history[-self.MIN_VALIDATION_CYCLES :]
                avg = sum(recent) / len(recent)
                if avg >= self.MIN_VALIDATION_ACCURACY:
                    logger.info(
                        "Framework %s validated: %.1f%% accuracy over %d cycles",
                        framework.framework_id,
                        avg * 100,
                        self.MIN_VALIDATION_CYCLES,
                    )
                    return FrameworkStatus.ACTIVE

        if framework.status in (FrameworkStatus.ACTIVE, FrameworkStatus.UNDER_REVIEW):
            if len(history) >= self.RETIREMENT_CYCLES:
                recent = history[-self.RETIREMENT_CYCLES :]
                avg = sum(recent) / len(recent)
                if avg < self.RETIREMENT_ACCURACY_THRESHOLD:
                    logger.warning(
                        "Framework %s retirement signal: %.1f%% accuracy over %d cycles",
                        framework.framework_id,
                        avg * 100,
                        self.RETIREMENT_CYCLES,
                    )
                    return FrameworkStatus.RETIRED

            if len(history) >= 20:
                recent = history[-20:]
                avg = sum(recent) / len(recent)
                if avg < self.REVIEW_ACCURACY_THRESHOLD:
                    return FrameworkStatus.UNDER_REVIEW

        return framework.status

    def compute_accuracy(
        self, framework: ResearchFramework, principles: dict[str, ResearchPrinciple]
    ) -> float:
        """Compute current accuracy from principle evidence.

        Accuracy = weighted average of principle accuracies, where
        principles with more observations contribute more.
        """
        if not framework.principles:
            return 0.0

        total_obs = 0
        weighted_acc = 0.0
        for pid in framework.principles:
            p = principles.get(pid)
            if not p:
                continue
            obs = p.evidence.total_observations
            acc = p.evidence.accuracy
            weighted_acc += obs * acc
            total_obs += obs

        return weighted_acc / total_obs if total_obs > 0 else 0.0

    def get_accuracy_trajectory(self, framework_id: str, window: int = 50) -> list[float]:
        """Get the recent accuracy trajectory for a framework."""
        history = self._accuracy_history.get(framework_id, [])
        if not history:
            return []
        return history[-min(window, len(history)) :]

    def trend(self, framework_id: str) -> str:
        """Determine accuracy trend: 'improving', 'stable', or 'declining'."""
        history = self._accuracy_history.get(framework_id, [])
        if len(history) < 20:
            return "insufficient_data"

        first_half = history[-20:-10]
        second_half = history[-10:]

        avg_first = sum(first_half) / len(first_half) if first_half else 0
        avg_second = sum(second_half) / len(second_half) if second_half else 0

        diff = avg_second - avg_first
        if diff > 0.03:
            return "improving"
        elif diff < -0.03:
            return "declining"
        return "stable"

    def is_validated(self, framework_id: str) -> bool:
        """Check if a framework has met validation criteria."""
        history = self._accuracy_history.get(framework_id, [])
        if len(history) < self.MIN_VALIDATION_CYCLES:
            return False
        recent = history[-self.MIN_VALIDATION_CYCLES :]
        return sum(recent) / len(recent) >= self.MIN_VALIDATION_ACCURACY

    @property
    def tracked_frameworks(self) -> int:
        return len(self._accuracy_history)
