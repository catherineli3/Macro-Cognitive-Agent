"""Belief Versioning Manager — Immutable Versioned Beliefs (DDR-V3-008).

Manages the creation, storage, and querying of versioned beliefs.
Every belief modification creates a new immutable BeliefVersion.
Full version history is retained for audit and trajectory analysis.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from src.schemas.belief_version import AdaptiveBelief, BeliefVersion
from src.schemas.learning_unit import LearningUnit
from src.shared.logging import get_logger

logger = get_logger(__name__)


class BeliefVersionManager:
    """Manages the versioned lifecycle of AdaptiveBeliefs.

    DDR-V3-008: All beliefs are versioned. Old versions are immutable.
    Every learning action creates a new version with full provenance.
    """

    def __init__(self, storage_dir: str | Path = "data/belief_versions") -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._beliefs: dict[str, AdaptiveBelief] = {}
        self._loaded = False

    # ── Belief CRUD ─────────────────────────────────────────────────────

    async def create_belief(
        self,
        dimension: str,
        transmission_channel: str = "",
        weight: float = 0.5,
        confidence: float = 0.5,
        preconditions: dict[str, Any] | None = None,
        valid_horizon: str = "5d",
        supporting_evidence: list[str] | None = None,
    ) -> AdaptiveBelief:
        """Create a new belief with v1 recorded."""
        await self._ensure_loaded()
        belief_id = f"belief-{uuid4().hex[:8]}"

        v1 = BeliefVersion(
            belief_id=belief_id,
            version_number=1,
            weight=weight,
            confidence=confidence,
            preconditions=preconditions or {},
            valid_horizon=valid_horizon,
            supporting_evidence=supporting_evidence or [],
            trigger="initial",
            trigger_detail="Created by Hypothesis Generator",
            changes_from_previous=None,
        )

        belief = AdaptiveBelief(
            belief_id=belief_id,
            dimension=dimension,
            transmission_channel=transmission_channel,
            current_version=1,
            weight=weight,
            confidence=confidence,
            preconditions=preconditions or {},
            valid_horizon=valid_horizon,
            supporting_evidence=supporting_evidence or [],
            version_history=[v1],
        )

        self._beliefs[belief_id] = belief
        await self._persist_belief(belief)
        logger.info(
            "belief_created id=%s dim=%s channel=%s v=1", belief_id, dimension, transmission_channel
        )
        return belief

    async def create_version(
        self,
        belief: AdaptiveBelief,
        learning_unit: LearningUnit,
        diagnosis_report_id: str,
        trigger_detail: str = "",
    ) -> AdaptiveBelief:
        """Create a new version of an existing belief from a LearningUnit.

        DDR-V3-008: Learning actions produce new versions.
        Old versions are immutable.
        """
        await self._ensure_loaded()

        new_version_num = belief.current_version + 1

        # Compute new values
        new_weight = belief.weight
        new_confidence = belief.confidence
        new_preconditions = dict(belief.preconditions)
        new_horizon = belief.valid_horizon
        new_evidence = list(belief.supporting_evidence)

        changes: dict[str, Any] = {}

        if learning_unit.weight_delta is not None:
            old_w = new_weight
            new_weight = max(0.0, min(1.0, new_weight + learning_unit.weight_delta))
            changes["weight"] = f"{old_w:.2f} → {new_weight:.2f}"

        if learning_unit.confidence_delta is not None:
            old_c = new_confidence
            new_confidence = max(0.0, min(1.0, new_confidence + learning_unit.confidence_delta))
            changes["confidence"] = f"{old_c:.2f} → {new_confidence:.2f}"

        if learning_unit.precondition_change is not None:
            pc = learning_unit.precondition_change
            _old_val = new_preconditions.get(pc.key)
            new_preconditions[pc.key] = pc.value
            changes["preconditions"] = f"+{pc.key}={pc.value}"

        if learning_unit.horizon_change is not None:
            old_h = new_horizon
            new_horizon = learning_unit.horizon_change
            changes["horizon"] = f"{old_h} → {new_horizon}"

        if learning_unit.evidence_change is not None:
            ec = learning_unit.evidence_change
            if ec.action == "add" and ec.evidence_id not in new_evidence:
                new_evidence.append(ec.evidence_id)
                changes["evidence"] = f"+{ec.evidence_id}"
            elif ec.action == "deprecate" and ec.evidence_id in new_evidence:
                new_evidence.remove(ec.evidence_id)
                changes["evidence"] = f"-{ec.evidence_id}"

        # Create new version
        new_version = BeliefVersion(
            belief_id=belief.belief_id,
            version_number=new_version_num,
            weight=new_weight,
            confidence=new_confidence,
            preconditions=new_preconditions,
            valid_horizon=new_horizon,
            supporting_evidence=new_evidence,
            trigger="prediction_outcome",
            trigger_detail=trigger_detail,
            diagnosis_report_id=diagnosis_report_id,
            changes_from_previous=changes if changes else None,
        )

        # Update belief
        belief.current_version = new_version_num
        belief.weight = new_weight
        belief.confidence = new_confidence
        belief.preconditions = new_preconditions
        belief.valid_horizon = new_horizon
        belief.supporting_evidence = new_evidence
        belief.version_history.append(new_version)

        await self._persist_belief(belief)
        logger.info(
            "belief_versioned id=%s v=%d changes=%s",
            belief.belief_id,
            new_version_num,
            list(changes.keys()),
        )
        return belief

    async def get(self, belief_id: str) -> AdaptiveBelief | None:
        """Retrieve a belief by ID."""
        await self._ensure_loaded()
        return self._beliefs.get(belief_id)

    async def get_all(self) -> list[AdaptiveBelief]:
        """Get all beliefs."""
        await self._ensure_loaded()
        return list(self._beliefs.values())

    async def get_by_dimension(self, dimension: str) -> list[AdaptiveBelief]:
        """Get all beliefs for a dimension."""
        await self._ensure_loaded()
        return [b for b in self._beliefs.values() if b.dimension.lower() == dimension.lower()]

    async def get_by_channel(self, channel: str) -> list[AdaptiveBelief]:
        """Get all beliefs for a transmission channel."""
        await self._ensure_loaded()
        return [b for b in self._beliefs.values() if b.transmission_channel == channel]

    async def get_version_history(self, belief_id: str) -> list[BeliefVersion]:
        """Get full version history for a belief."""
        belief = await self.get(belief_id)
        if belief is None:
            return []
        return belief.version_history

    async def update_performance(
        self,
        belief_id: str,
        was_correct: bool,
    ) -> AdaptiveBelief | None:
        """Update cycle_count, correct_count, and streak after an outcome."""
        belief = await self.get(belief_id)
        if belief is None:
            return None
        belief.cycle_count += 1
        if was_correct:
            belief.correct_count += 1
            belief.streak = max(0, belief.streak) + 1
        else:
            belief.streak = min(0, belief.streak) - 1

        # Auto-deprecate after 10 consecutive errors
        if belief.streak <= -10 and belief.status == "active":
            belief.status = "deprecated"
            logger.info("belief_auto_deprecated id=%s streak=%d", belief_id, belief.streak)

        await self._persist_belief(belief)
        return belief

    async def rollback(self, belief_id: str, target_version: int) -> AdaptiveBelief | None:
        """Emergency rollback to a prior version."""
        belief = await self.get(belief_id)
        if belief is None:
            return None
        target = belief.get_version(target_version)
        if target is None:
            logger.warning("rollback_version_not_found id=%s v=%d", belief_id, target_version)
            return None

        # Create a new version that reverts to target state
        new_v = BeliefVersion(
            belief_id=belief_id,
            version_number=belief.current_version + 1,
            weight=target.weight,
            confidence=target.confidence,
            preconditions=dict(target.preconditions),
            valid_horizon=target.valid_horizon,
            supporting_evidence=list(target.supporting_evidence),
            trigger="manual",
            trigger_detail=f"Rollback to v{target_version}",
            changes_from_previous={"rollback": f"v{belief.current_version} → v{target_version}"},
        )

        belief.current_version = belief.current_version + 1
        belief.weight = target.weight
        belief.confidence = target.confidence
        belief.preconditions = dict(target.preconditions)
        belief.valid_horizon = target.valid_horizon
        belief.supporting_evidence = list(target.supporting_evidence)
        belief.version_history.append(new_v)

        await self._persist_belief(belief)
        logger.warning(
            "belief_rolled_back id=%s from=v%d to=v%d",
            belief_id,
            belief.current_version,
            target_version,
        )
        return belief

    # ── Migration: V2 → V3 ──────────────────────────────────────────────

    async def migrate_from_v2(
        self,
        belief_records: list[Any],  # list of BeliefRecord (V2)
    ) -> list[AdaptiveBelief]:
        """Migrate V2 BeliefRecords to V3 AdaptiveBeliefs with v1 recorded."""
        await self._ensure_loaded()
        created: list[AdaptiveBelief] = []
        for record in belief_records:
            belief_id = getattr(record, "belief_id", "")
            if belief_id in self._beliefs:
                continue
            belief = await self.create_belief(
                dimension=getattr(record, "dimension", "unknown"),
                weight=getattr(record, "confidence", 0.5),
                confidence=0.5,
                valid_horizon="5d",
                supporting_evidence=[],
            )
            # Override belief_id to match V2
            belief.belief_id = belief_id
            belief.version_history[0].belief_id = belief_id
            self._beliefs[belief_id] = belief
            created.append(belief)
        await self._persist_all()
        logger.info("v2_migration_complete migrated=%d total=%d", len(created), len(self._beliefs))
        return created

    # ── Persistence ─────────────────────────────────────────────────────

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        index_path = self._storage_dir / "belief_index.json"
        if index_path.exists():
            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))
                for belief_data in data.get("beliefs", []):
                    belief = AdaptiveBelief.model_validate(belief_data)
                    self._beliefs[belief.belief_id] = belief
                logger.info("beliefs_loaded count=%d", len(self._beliefs))
            except Exception as e:
                logger.warning("beliefs_load_failed: %s", e)
        self._loaded = True

    async def _persist_belief(self, belief: AdaptiveBelief) -> None:
        """Persist a single belief to its individual file."""
        file_path = self._storage_dir / f"{belief.belief_id}.json"
        file_path.write_text(
            json.dumps(belief.model_dump(mode="json"), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    async def _persist_all(self) -> None:
        """Persist all beliefs to index."""
        index_path = self._storage_dir / "belief_index.json"
        beliefs_data = [b.model_dump(mode="json") for b in self._beliefs.values()]
        data = {
            "beliefs": beliefs_data,
            "total": len(beliefs_data),
            "persisted_at": datetime.now(UTC).isoformat(),
        }
        index_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
