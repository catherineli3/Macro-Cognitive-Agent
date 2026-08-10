"""Transmission Update Engine — Apply breakpoint diagnoses to the graph.

Milestone B: Transmission Reasoning.

Core responsibility:
    1. Take BreakpointDiagnosis results → generate TransmissionUpdateRecords
    2. Apply updates to TransmissionGraph edges
    3. Cascade reliability changes to ContextualBelief weights

Key insight (from design doc Section 6.2):
    A belief's weight is NOT an independent parameter.
    It is a function of its transmission segments' reliability:
    
        belief.context_weight[context] = 
            avg(edge_i.reliability[context]) × (1 - penalty_for_recent_failures)

    When a segment's reliability drops, ALL beliefs depending on it in that
    context get their weight auto-adjusted. This is the agent's "knowledge
    transfer" — discovering a broken chain affects all related judgments.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from src.schemas.transmission_v3_1 import (
    BreakpointDiagnosis,
    ContextProfile,
    ContextualBelief,
    FailureModeCategory,
    TransmissionAction,
    TransmissionUpdateBatch,
    TransmissionUpdateRecord,
)
from src.transmission.transmission_graph import TransmissionGraph
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Update policy constants ──────────────────────────────────────────────────

# How much to reinforce a segment that transmitted correctly
REINFORCE_AMOUNT = +0.02

# How much to weaken a segment that broke
WEAKEN_AMOUNT = -0.06

# Context-specific multiplier (context changes are amplified)
CONTEXT_DELTA_MULTIPLIER = 1.2

# Recent failure penalty window (cycles)
RECENT_FAILURE_WINDOW = 10


class TransmissionUpdateEngine:
    """Generates and applies TransmissionUpdateRecords from breakpoint diagnoses.

    Flow:
        BreakpointDiagnosis[] → TransmissionUpdateRecord[] → Graph.apply_update()
        → Cascade to ContextualBelief[].weight recalculation
    """

    def __init__(self, graph: TransmissionGraph) -> None:
        self._graph = graph
        self._belief_map: dict[str, ContextualBelief] = {}
        self._belief_segment_index: dict[str, list[str]] = defaultdict(list)
        # ^ segment_id → [belief_id]  (reverse index for cascade)

    # ── Register beliefs for cascade ──────────────────────────────────────

    def register_belief(self, belief: ContextualBelief) -> None:
        """Register a contextual belief for cascade updates.

        Builds a reverse index: segment_id → belief_ids that depend on it.
        """
        self._belief_map[belief.belief_id] = belief

        for ctx_key, profile in belief.contexts.items():
            for seg_id in profile.active_transmission_segments:
                if belief.belief_id not in self._belief_segment_index[seg_id]:
                    self._belief_segment_index[seg_id].append(belief.belief_id)

    def register_beliefs(self, beliefs: list[ContextualBelief]) -> None:
        for b in beliefs:
            self.register_belief(b)
        logger.info(
            "registered_beliefs count=%d indexed_segments=%d",
            len(beliefs),
            len(self._belief_segment_index),
        )

    def get_affected_beliefs(self, segment_id: str) -> list[str]:
        """Which beliefs depend on this segment (for cascade)."""
        return self._belief_segment_index.get(segment_id, [])

    # ── Update generation ─────────────────────────────────────────────────

    def generate_updates(
        self,
        diagnoses: list[BreakpointDiagnosis],
        context_key: str = "",
        run_id: str = "",
    ) -> TransmissionUpdateBatch:
        """Generate TransmissionUpdateRecords from breakpoint diagnoses.

        For each diagnosis:
            - If all segments healthy + prediction correct → REINFORCE all segments
            - If breakpoint found → WEAKEN the breakpoint segment
            - If breakpoint found + new failure mode → REGISTER_FAILURE
            - Downstream segments (after breakpoint) → NO_CHANGE (cascaded from break)

        Returns:
            TransmissionUpdateBatch with all updates, including cascade info
        """
        updates: list[TransmissionUpdateRecord] = []

        for bp in diagnoses:
            # Process each segment in the diagnosis
            for sd in bp.segment_diagnoses:
                if sd.is_breakpoint:
                    # The breakpoint — weaken it
                    update = self._create_weaken_update(sd, bp, context_key, run_id)
                    updates.append(update)

                elif sd.transmitted_correctly:
                    # Correct segment — reinforce it
                    # Only reinforce if overall prediction was correct
                    # (if prediction was wrong but this segment was fine,
                    #  reinforce it lightly — it worked despite overall failure)
                    if bp.all_segments_healthy:
                        amount = REINFORCE_AMOUNT
                    else:
                        amount = REINFORCE_AMOUNT * 0.5  # Reduced reinforcement

                    update = self._create_reinforce_update(
                        sd, bp, context_key, run_id, amount
                    )
                    updates.append(update)

                # Downstream segments (after breakpoint) → skip
                # They didn't get a fair test since the upstream broke

            # If new failure mode discovered
            if bp.new_failure_mode and bp.breakpoint_found:
                update = self._create_failure_registration(
                    bp, context_key, run_id
                )
                updates.append(update)

        # Collapse multiple updates to the same segment (take the strongest action)
        updates = self._deduplicate_updates(updates)

        # Add cascade info: which beliefs are affected
        for update in updates:
            update.affected_belief_ids = self.get_affected_beliefs(update.segment_id)

        batch = TransmissionUpdateBatch(
            run_id=run_id,
            updates=updates,
        )

        logger.info(
            "updates_generated total=%d reinforce=%d weaken=%d failures=%d affected_beliefs=%d",
            len(updates),
            batch.total_reinforcements,
            batch.total_weakenings,
            batch.total_failure_registrations,
            len(batch.affected_beliefs),
        )

        return batch

    def apply_batch(self, batch: TransmissionUpdateBatch) -> list[str]:
        """Apply all updates in a batch to the graph.

        Returns list of belief IDs that need weight recalculation (cascade).
        """
        for update in batch.updates:
            self._graph.apply_update(update)

        cascade_beliefs = batch.affected_beliefs
        if cascade_beliefs:
            logger.info(
                "cascade_triggered beliefs=%d updates=%d",
                len(cascade_beliefs), len(batch.updates),
            )

        return cascade_beliefs

    def apply_and_cascade(
        self,
        batch: TransmissionUpdateBatch,
    ) -> dict[str, float]:
        """Apply updates to graph AND recalculate affected belief weights.

        Returns:
            Mapping of belief_id → new_weight (for tracking)
        """
        cascade_ids = self.apply_batch(batch)
        weight_changes: dict[str, float] = {}

        for belief_id in cascade_ids:
            belief = self._belief_map.get(belief_id)
            if not belief:
                continue

            old_weights = {
                ctx: profile.derived_weight
                for ctx, profile in belief.contexts.items()
            }

            self.recalculate_belief_weight(belief)

            for ctx, profile in belief.contexts.items():
                old_w = old_weights.get(ctx, 0.50)
                if abs(profile.derived_weight - old_w) > 0.001:
                    weight_changes[f"{belief_id}:{ctx}"] = profile.derived_weight - old_w

        if weight_changes:
            logger.info(
                "cascade_complete changed_beliefs=%d avg_delta=%.4f",
                len(weight_changes),
                sum(abs(v) for v in weight_changes.values()) / len(weight_changes),
            )

        return weight_changes

    # ── Belief weight recalculation ────────────────────────────────────────

    def _find_edge(self, seg_id: str):
        """Find an edge by segment_id (supports both old and new graph key systems)."""
        for e in self._graph._edges.values():
            if e.segment_id == seg_id:
                return e
        return None

    def recalculate_belief_weight(self, belief: ContextualBelief) -> None:
        """Recalculate a belief's weight from its active transmission segments.

        Formula:
            weight = avg(reliability of active segments) × (1 - recent_failure_penalty)

        This is called automatically during cascade, but can also be called
        explicitly when a belief's context changes.
        """
        for ctx_key, profile in belief.contexts.items():
            active = profile.active_transmission_segments
            if not active:
                profile.derived_weight = profile.derived_weight  # Keep current
                profile.derived_confidence = 0.30
                continue

            reliabilities = []
            failure_count = 0
            total_obs = 0

            for seg_id in active:
                edge = self._find_edge(seg_id)
                if edge:
                    rel = edge.reliability_in_context(ctx_key) if ctx_key else edge.reliability_default
                    reliabilities.append(rel)
                    failure_count += edge.break_count
                    total_obs += edge.observation_count
                else:
                    reliabilities.append(0.50)

            if not reliabilities:
                continue

            # Average reliability
            avg_rel = sum(reliabilities) / len(reliabilities)

            failure_penalty = (failure_count / max(total_obs, 1)) * 0.5 if total_obs > 0 else 0.0
            failure_penalty = min(0.4, failure_penalty)  # Cap at 40%

            # Compute weight
            adjusted = avg_rel * (1.0 - failure_penalty)
            profile.derived_weight = round(max(0.05, min(0.95, adjusted)), 4)

            # Confidence: based on observation count and weight consistency
            if total_obs < 5:
                confidence = 0.30
            elif total_obs < 20:
                confidence = 0.50 + 0.01 * total_obs  # Linear growth 0.50→0.65
            else:
                confidence = 0.65 + 0.005 * min(total_obs - 20, 40)  # 0.65→0.85

            # Adjust confidence based on reliability spread
            rel_spread = max(reliabilities) - min(reliabilities) if len(reliabilities) > 1 else 0
            confidence *= (1.0 - rel_spread * 0.3)  # High spread → lower confidence

            profile.derived_confidence = round(max(0.10, min(0.95, confidence)), 4)

    def recalculate_all_beliefs(self) -> int:
        """Recalculate all registered beliefs. Returns count."""
        count = 0
        for belief in self._belief_map.values():
            self.recalculate_belief_weight(belief)
            count += 1
        if count > 0:
            logger.info("recalculated_all_beliefs count=%d", count)
        return count

    # ── Internal helpers ──────────────────────────────────────────────────

    def _create_reinforce_update(
        self,
        sd,  # SegmentDiagnosis
        bp: BreakpointDiagnosis,
        context_key: str,
        run_id: str,
        amount: float,
    ) -> TransmissionUpdateRecord:
        return TransmissionUpdateRecord(
            run_id=run_id,
            segment_id=sd.segment_id,
            source=sd.source,
            target=sd.target,
            action=TransmissionAction.REINFORCE,
            context_key=context_key,
            reliability_delta=amount,
            context_reliability_delta=amount * CONTEXT_DELTA_MULTIPLIER if context_key else 0.0,
            breakpoint_diagnosis_id=bp.diagnosis_id,
            reason=f"Transmission confirmed: {sd.segment_id} ({sd.diagnosis_rationale})",
        )

    def _create_weaken_update(
        self,
        sd,  # SegmentDiagnosis
        bp: BreakpointDiagnosis,
        context_key: str,
        run_id: str,
    ) -> TransmissionUpdateRecord:
        # Larger weakening for higher severity
        if sd.breakpoint_severity:
            severity_map = {
                "minor": WEAKEN_AMOUNT * 0.5,
                "significant": WEAKEN_AMOUNT,
                "critical": WEAKEN_AMOUNT * 1.5,
                "structural": WEAKEN_AMOUNT * 2.0,
            }
            amount = severity_map.get(sd.breakpoint_severity.value, WEAKEN_AMOUNT)
        else:
            amount = WEAKEN_AMOUNT

        return TransmissionUpdateRecord(
            run_id=run_id,
            segment_id=sd.segment_id,
            source=sd.source,
            target=sd.target,
            action=TransmissionAction.WEAKEN,
            context_key=context_key,
            reliability_delta=amount,
            context_reliability_delta=amount * CONTEXT_DELTA_MULTIPLIER if context_key else 0.0,
            breakpoint_diagnosis_id=bp.diagnosis_id,
            reason=f"Transmission broken: {sd.segment_id} — {bp.root_cause_description}",
        )

    def _create_failure_registration(
        self,
        bp: BreakpointDiagnosis,
        context_key: str,
        run_id: str,
    ) -> TransmissionUpdateRecord:
        return TransmissionUpdateRecord(
            run_id=run_id,
            segment_id=bp.breakpoint_segment,
            action=TransmissionAction.REGISTER_FAILURE,
            context_key=context_key,
            failure_category=bp.root_cause_category,
            failure_description=bp.root_cause_description,
            breakpoint_diagnosis_id=bp.diagnosis_id,
            reason=f"New failure mode: {bp.root_cause_category.value} on {bp.breakpoint_segment}",
        )

    def _deduplicate_updates(
        self,
        updates: list[TransmissionUpdateRecord],
    ) -> list[TransmissionUpdateRecord]:
        """Merge multiple updates to the same segment. Strongest action wins.

        Priority: REGISTER_FAILURE > WEAKEN > REINFORCE > NO_CHANGE
        """
        merged: dict[str, TransmissionUpdateRecord] = {}
        action_priority = {
            TransmissionAction.REGISTER_FAILURE: 3,
            TransmissionAction.ADD_CONDITION: 3,
            TransmissionAction.WEAKEN: 2,
            TransmissionAction.REINFORCE: 1,
            TransmissionAction.NO_CHANGE: 0,
        }

        action_priority = {
            TransmissionAction.REGISTER_FAILURE: 3,
            TransmissionAction.ADD_CONDITION: 3,
            TransmissionAction.WEAKEN: 2,
            TransmissionAction.DEMOTE_MECHANISM: 2,
            TransmissionAction.REINFORCE: 1,
            TransmissionAction.PROMOTE_MECHANISM: 1,
            TransmissionAction.NO_CHANGE: 0,
        }

        for u in updates:
            key = f"{u.segment_id}:{u.context_key}"
            if key not in merged or action_priority[u.action] > action_priority[merged[key].action]:
                merged[key] = u

        return list(merged.values())
