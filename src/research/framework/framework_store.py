"""Framework Store — persistent storage for Research Frameworks (Milestone C).

Provides CRUD operations, lifecycle management, and query capabilities.
"""

from __future__ import annotations

from typing import Optional

from src.schemas.research import ResearchFramework, FrameworkStatus
from src.shared.logging import get_logger

logger = get_logger(__name__)


class FrameworkStore:
    """Persistent store for Research Frameworks."""

    def __init__(self) -> None:
        self._frameworks: dict[str, ResearchFramework] = {}
        self._by_status: dict[str, list[str]] = {}
        self._retired: dict[str, ResearchFramework] = {}
        self._total_created: int = 0

    def save(self, framework: ResearchFramework) -> str:
        """Save a framework. Returns its ID."""
        fid = framework.framework_id
        self._frameworks[fid] = framework
        self._total_created += 1

        status = framework.status.value
        self._by_status.setdefault(status, []).append(fid)

        logger.debug("Saved framework: %s (status=%s, principles=%d)",
                     fid, status, len(framework.principles))
        return fid

    def get(self, framework_id: str) -> ResearchFramework | None:
        return self._frameworks.get(framework_id)

    def get_many(self, framework_ids: list[str]) -> dict[str, ResearchFramework]:
        return {fid: self._frameworks[fid] for fid in framework_ids if fid in self._frameworks}

    def get_all(self) -> list[ResearchFramework]:
        return list(self._frameworks.values())

    def get_active(self) -> list[ResearchFramework]:
        """Get all active frameworks (not retired)."""
        return [f for f in self._frameworks.values()
                if f.status != FrameworkStatus.RETIRED]

    def get_candidates(self) -> list[ResearchFramework]:
        return self._get_by_status(FrameworkStatus.CANDIDATE)

    def get_under_review(self) -> list[ResearchFramework]:
        return self._get_by_status(FrameworkStatus.UNDER_REVIEW)

    def activate(self, framework_id: str) -> bool:
        """Activate a candidate framework."""
        return self._update_status(framework_id, FrameworkStatus.ACTIVE)

    def mark_review(self, framework_id: str) -> bool:
        """Mark a framework as under review."""
        return self._update_status(framework_id, FrameworkStatus.UNDER_REVIEW)

    def retire(self, framework_id: str, reason: str = "") -> bool:
        """Retire a framework."""
        f = self._frameworks.pop(framework_id, None)
        if not f:
            return False
        f.status = FrameworkStatus.RETIRED
        f.retirement_reason = reason
        self._retired[framework_id] = f

        self._remove_from_status_index(framework_id, f.status.value if f.status.value != "retired"
                                       else None)
        logger.info("Retired framework %s: %s", framework_id, reason)
        return True

    def add_principle(self, framework_id: str, principle_id: str,
                      weight: float = 1.0) -> bool:
        """Add a principle to a framework."""
        f = self._frameworks.get(framework_id)
        if not f:
            return False
        if principle_id not in f.principles:
            f.principles.append(principle_id)
        f.principle_weights[principle_id] = weight
        return True

    def remove_principle(self, framework_id: str, principle_id: str) -> bool:
        """Remove a principle from a framework."""
        f = self._frameworks.get(framework_id)
        if not f:
            return False
        if principle_id in f.principles:
            f.principles.remove(principle_id)
        f.principle_weights.pop(principle_id, None)
        return True

    def update_accuracy(self, framework_id: str, accuracy: float) -> bool:
        """Append a new accuracy data point."""
        f = self._frameworks.get(framework_id)
        if not f:
            return False
        f.accuracy_trajectory.append(accuracy)
        f.cycle_count += 1
        return True

    def _update_status(self, framework_id: str, new_status: FrameworkStatus) -> bool:
        f = self._frameworks.get(framework_id)
        if not f:
            return False
        old_status = f.status.value
        f.status = new_status

        if old_status in self._by_status:
            self._by_status[old_status] = [
                fid for fid in self._by_status[old_status] if fid != framework_id
            ]
        self._by_status.setdefault(new_status.value, []).append(framework_id)
        return True

    def _remove_from_status_index(self, framework_id: str,
                                   old_status: Optional[str]) -> None:
        if old_status and old_status in self._by_status:
            self._by_status[old_status] = [
                fid for fid in self._by_status[old_status] if fid != framework_id
            ]

    def _get_by_status(self, status: FrameworkStatus) -> list[ResearchFramework]:
        ids = self._by_status.get(status.value, [])
        return [self._frameworks[fid] for fid in ids if fid in self._frameworks]

    def get_for_principle(self, principle_id: str) -> list[ResearchFramework]:
        """Get all frameworks that contain a specific principle."""
        return [f for f in self._frameworks.values()
                if principle_id in f.principles]

    @property
    def count(self) -> int:
        return len(self._frameworks)

    @property
    def active_count(self) -> int:
        return len([f for f in self._frameworks.values()
                    if f.status == FrameworkStatus.ACTIVE])

    @property
    def total_ever_created(self) -> int:
        return self._total_created

    def summary(self) -> str:
        return (
            f"FrameworkStore: {self.count} active ({self.active_count} active, "
            f"{len(self._get_by_status(FrameworkStatus.CANDIDATE))} candidates, "
            f"{len(self._retired)} retired)"
        )
