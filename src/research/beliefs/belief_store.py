"""Belief Store — versioned persistence and query layer for ResearchBelief objects.

Supports daily snapshot save/load, domain-based querying, lifecycle stage
filtering, and version history. Works alongside BeliefGraph and BeliefEngine.

Storage model:
    _beliefs: dict[str, ResearchBelief]        — active beliefs by belief.id
    _history: dict[str, list[ResearchBelief]]  — date → full snapshot
    _by_domain: dict[str, set[str]]            — domain_name → belief IDs
    _by_stage: dict[str, set[str]]             — stage_name → belief IDs
    _retired: dict[str, ResearchBelief]        — retired beliefs by belief.id
"""

from __future__ import annotations

import copy
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from src.research.beliefs.schemas import BeliefDomain, BeliefStage, ResearchBelief

# Active (non-retired) stages
_ACTIVE_STAGES = frozenset(
    {
        BeliefStage.HYPOTHESIS.value,
        BeliefStage.EVIDENCE_GATHERING.value,
        BeliefStage.CONFIRMATION.value,
        BeliefStage.CHALLENGE.value,
        BeliefStage.CONSOLIDATION.value,
        BeliefStage.EROSION.value,
    }
)

# Validated stages (at or beyond CONFIRMATION)
_VALIDATED_STAGES = frozenset(
    {
        BeliefStage.CONFIRMATION.value,
        BeliefStage.CHALLENGE.value,
        BeliefStage.CONSOLIDATION.value,
        BeliefStage.EROSION.value,
    }
)


class BeliefStore:
    """Versioned store for ResearchBelief objects.

    Provides snapshot persistence with date-keyed history, CRUD operations,
    domain/stage queries, and lifecycle management.

    Usage:
        store = BeliefStore()
        store.save(beliefs)
        latest = store.load_latest()
        liq_beliefs = store.query_by_domain(BeliefDomain.LIQUIDITY)
        active_only = store.query_active()
    """

    def __init__(self) -> None:
        # Main storage: active beliefs keyed by id
        self._beliefs: dict[str, ResearchBelief] = {}

        # Domain index: domain_name → set of belief IDs
        self._by_domain: dict[str, set[str]] = defaultdict(set)

        # Stage index: stage_name → set of belief IDs
        self._by_stage: dict[str, set[str]] = defaultdict(set)

        # Snapshot history: date_str → deep-copied list of beliefs
        self._history: dict[str, list[ResearchBelief]] = {}

        # Retired beliefs archive
        self._retired: dict[str, ResearchBelief] = {}

    # ── Core Persistence ─────────────────────────────────────────────────

    def save(
        self,
        beliefs: list[ResearchBelief],
        date_str: str | None = None,
    ) -> str:
        """Save a snapshot of beliefs, keyed by date.

        If date_str is None, uses today's date (UTC) in YYYY-MM-DD format.

        Args:
            beliefs: List of ResearchBelief objects to persist.
            date_str: Optional date key (e.g. "2026-07-21"). Auto-generated if None.

        Returns:
            The date string used as the snapshot key.
        """
        if date_str is None:
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")

        # Deep copy beliefs into the history
        self._history[date_str] = [copy.deepcopy(b) for b in beliefs]

        # Also update active store and rebuild indices
        self._rebuild_indices(beliefs)

        return date_str

    def load_latest(self) -> list[ResearchBelief]:
        """Load the most recent snapshot of beliefs.

        Returns:
            List of ResearchBelief objects from the latest saved snapshot.
            Empty list if no snapshots exist.
        """
        if not self._history:
            return []
        return self._history[max(self._history.keys())]

    def load_by_date(self, date_str: str) -> list[ResearchBelief]:
        """Load beliefs saved on a specific date.

        Args:
            date_str: Date key in YYYY-MM-DD format.

        Returns:
            List of ResearchBelief objects. Empty list if date not found.
        """
        return self._history.get(date_str, [])

    # ── CRUD Operations ──────────────────────────────────────────────────

    def add(self, belief: ResearchBelief) -> str:
        """Add a single belief to the active store.

        Args:
            belief: The ResearchBelief to add.

        Returns:
            The belief id (auto-generated if empty).
        """
        if not belief.id:
            belief.id = f"BLF-{uuid.uuid4().hex[:8].upper()}"

        self._beliefs[belief.id] = belief

        # Index by domain
        domain_key = (
            belief.domain.value if isinstance(belief.domain, BeliefDomain) else str(belief.domain)
        )
        self._by_domain[domain_key].add(belief.id)

        # Index by stage
        stage_key = (
            belief.stage.value if isinstance(belief.stage, BeliefStage) else str(belief.stage)
        )
        self._by_stage[stage_key].add(belief.id)

        return belief.id

    def get(self, belief_id: str) -> ResearchBelief | None:
        """Retrieve a belief by ID (active or retired).

        Args:
            belief_id: The belief identifier.

        Returns:
            ResearchBelief if found, None otherwise.
        """
        return self._beliefs.get(belief_id) or self._retired.get(belief_id)

    def get_many(self, belief_ids: list[str]) -> list[ResearchBelief]:
        """Retrieve multiple beliefs by their IDs.

        Args:
            belief_ids: List of belief identifiers.

        Returns:
            List of found ResearchBelief objects (missing IDs are skipped).
        """
        return [b for bid in belief_ids if (b := self.get(bid)) is not None]

    def update(self, belief: ResearchBelief) -> bool:
        """Update an existing belief in the store.

        The belief object may share a reference with the stored object,
        so we clear ALL old index entries before re-indexing with new values.

        Args:
            belief: Updated ResearchBelief (matched by id).

        Returns:
            True if the belief existed and was updated, False otherwise.
        """
        if belief.id not in self._beliefs:
            return False

        # Clear old indices (cannot trust old reference — caller may have
        # modified the object in place, sharing our stored reference)
        for domain_set in self._by_domain.values():
            domain_set.discard(belief.id)
        for stage_set in self._by_stage.values():
            stage_set.discard(belief.id)

        # Update belief
        self._beliefs[belief.id] = belief

        # Re-index with current values
        new_domain_key = (
            belief.domain.value if isinstance(belief.domain, BeliefDomain) else str(belief.domain)
        )
        self._by_domain[new_domain_key].add(belief.id)

        new_stage_key = (
            belief.stage.value if isinstance(belief.stage, BeliefStage) else str(belief.stage)
        )
        self._by_stage[new_stage_key].add(belief.id)

        return True

    def retire(self, belief_id: str, reason: str = "") -> bool:
        """Move a belief from active to retired archive.

        Args:
            belief_id: The belief to retire.
            reason: Optional reason for retirement.

        Returns:
            True if the belief was retired, False if not found.
        """
        if belief_id not in self._beliefs:
            return False

        belief = self._beliefs.pop(belief_id)
        belief.advance_stage(BeliefStage.RETIRED, reason)

        # Clean indices
        domain_key = (
            belief.domain.value if isinstance(belief.domain, BeliefDomain) else str(belief.domain)
        )
        self._by_domain.get(domain_key, set()).discard(belief_id)

        stage_key = belief.stage.value
        self._by_stage.get(stage_key, set()).discard(belief_id)

        # Archive
        self._retired[belief_id] = belief
        return True

    def count(self) -> int:
        """Return the number of active beliefs."""
        return len(self._beliefs)

    # ── Query Operations ─────────────────────────────────────────────────

    def query_by_domain(self, domain: str | BeliefDomain) -> list[ResearchBelief]:
        """Query active beliefs by domain.

        Args:
            domain: Domain name (e.g. "Liquidity", BeliefDomain.LIQUIDITY).

        Returns:
            List of matching ResearchBelief objects.
        """
        key = domain.value if isinstance(domain, BeliefDomain) else domain
        ids = self._by_domain.get(key, set())
        return [self._beliefs[bid] for bid in ids if bid in self._beliefs]

    def query_by_stage(self, stage: str | BeliefStage) -> list[ResearchBelief]:
        """Query active beliefs by lifecycle stage.

        Args:
            stage: Stage string or BeliefStage enum.

        Returns:
            List of matching ResearchBelief objects.
        """
        key = stage.value if isinstance(stage, BeliefStage) else stage
        ids = self._by_stage.get(key, set())
        return [self._beliefs[bid] for bid in ids if bid in self._beliefs]

    def query_active(self) -> list[ResearchBelief]:
        """Get all beliefs in active (non-retired) stages."""
        results: list[ResearchBelief] = []
        for stage_key, belief_ids in self._by_stage.items():
            if stage_key in _ACTIVE_STAGES:
                results.extend(self._beliefs[bid] for bid in belief_ids if bid in self._beliefs)
        return results

    def query_validated(self) -> list[ResearchBelief]:
        """Get all beliefs that have reached at least CONFIRMATION stage."""
        results: list[ResearchBelief] = []
        for stage_key, belief_ids in self._by_stage.items():
            if stage_key in _VALIDATED_STAGES:
                results.extend(self._beliefs[bid] for bid in belief_ids if bid in self._beliefs)
        return results

    def query_dominant(self) -> list[ResearchBelief]:
        """Get all beliefs currently at CONSOLIDATION stage."""
        return self.query_by_stage(BeliefStage.CONSOLIDATION)

    def all_beliefs(self) -> list[ResearchBelief]:
        """Return all active beliefs as a list."""
        return list(self._beliefs.values())

    # ── History & Statistics ─────────────────────────────────────────────

    def history_dates(self) -> list[str]:
        """Return all historical snapshot dates, sorted chronologically."""
        return sorted(self._history.keys())

    def snapshot_count(self) -> int:
        """Return the number of saved snapshots."""
        return len(self._history)

    def diff(self, date_a: str, date_b: str) -> dict[str, list[ResearchBelief]]:
        """Compute the difference between two snapshots.

        Args:
            date_a: Earlier date key.
            date_b: Later date key.

        Returns:
            Dict with keys: 'added', 'removed', 'modified', 'unchanged'.
        """
        beliefs_a = {b.id: b for b in self.load_by_date(date_a)}
        beliefs_b = {b.id: b for b in self.load_by_date(date_b)}

        ids_a = set(beliefs_a.keys())
        ids_b = set(beliefs_b.keys())

        added = [beliefs_b[bid] for bid in (ids_b - ids_a)]
        removed = [beliefs_a[bid] for bid in (ids_a - ids_b)]

        modified: list[ResearchBelief] = []
        unchanged: list[ResearchBelief] = []
        for bid in ids_a & ids_b:
            if beliefs_a[bid].to_dict() != beliefs_b[bid].to_dict():
                modified.append(beliefs_b[bid])
            else:
                unchanged.append(beliefs_b[bid])

        return {
            "added": added,
            "removed": removed,
            "modified": modified,
            "unchanged": unchanged,
        }

    def summary(self) -> dict:
        """Return a summary of the current store state."""
        stage_counts = {
            stage_key: len(belief_ids) for stage_key, belief_ids in self._by_stage.items()
        }
        domain_counts = {domain: len(belief_ids) for domain, belief_ids in self._by_domain.items()}

        return {
            "total_active": len(self._beliefs),
            "total_retired": len(self._retired),
            "total_snapshots": len(self._history),
            "latest_snapshot_date": max(self._history.keys()) if self._history else None,
            "by_stage": stage_counts,
            "by_domain": domain_counts,
        }

    def clear(self) -> None:
        """Clear all stored beliefs, indices, and history."""
        self._beliefs.clear()
        self._by_domain.clear()
        self._by_stage.clear()
        self._history.clear()
        self._retired.clear()

    # ── Private Helpers ──────────────────────────────────────────────────

    def _rebuild_indices(self, beliefs: list[ResearchBelief]) -> None:
        """Rebuild the belief store and all indices from a list of beliefs."""
        self._beliefs.clear()
        self._by_domain.clear()
        self._by_stage.clear()

        for b in beliefs:
            self._beliefs[b.id] = b

            domain_key = b.domain.value if isinstance(b.domain, BeliefDomain) else str(b.domain)
            self._by_domain[domain_key].add(b.id)

            stage_key = b.stage.value if isinstance(b.stage, BeliefStage) else str(b.stage)
            self._by_stage[stage_key].add(b.id)
