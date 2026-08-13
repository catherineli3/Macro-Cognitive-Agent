"""Research Note Generator — transforms BreakpointDiagnosis → ResearchNote.

Milestone B.5: The "researcher upgrade" — instead of "BROKEN: credit→capex",
the agent produces:

    "Historically, Credit→Capex works 82%. During High VIX only 31%.
     Current Regime: VIX 34. Therefore: This transmission should be discounted."
"""

from __future__ import annotations

from src.schemas.transmission_v3_1 import (
    BreakpointDiagnosis,
    FindingConfidence,
    ResearchNote,
)
from src.shared.logging import get_logger
from src.transmission.transmission_graph import TransmissionGraph

logger = get_logger(__name__)


def _action_to_recommendation(action, seg_desc: str, ctx: str) -> str:
    ctx_str = f" in {ctx}" if ctx else ""
    mapping = {
        "reinforce": f"Boost {seg_desc} reliability{ctx_str}.",
        "weaken": f"Reduce {seg_desc} reliability{ctx_str} and monitor for further breaks.",
        "register_failure": f"Log new failure mode for {seg_desc}{ctx_str}. May indicate structural change.",
        "promote_mechanism": f"Promote this mechanism as dominant for {seg_desc}{ctx_str}.",
        "demote_mechanism": f"Downgrade this mechanism for {seg_desc}{ctx_str}.",
        "add_condition": f"Add validity condition for {seg_desc}{ctx_str}.",
    }
    return mapping.get(
        action.value if hasattr(action, "value") else str(action), f"Monitor {seg_desc}{ctx_str}."
    )


class ResearchNoteGenerator:
    """Transforms BreakpointDiagnosis → researcher-prose ResearchNote."""

    def __init__(self, graph: TransmissionGraph) -> None:
        self._graph = graph

    def generate(self, diagnosis: BreakpointDiagnosis, context_key: str = "") -> ResearchNote:
        if diagnosis.all_segments_healthy:
            return self._healthy_note(diagnosis, context_key)
        elif diagnosis.breakpoint_found:
            return self._breakpoint_note(diagnosis, context_key)
        else:
            return self._unknown_note(diagnosis, context_key)

    def generate_batch(
        self, diagnoses: list[BreakpointDiagnosis], context_key: str = ""
    ) -> list[ResearchNote]:
        return [self.generate(d, context_key) for d in diagnoses]

    # ── Internal ─────────────────────────────────────────────────────────

    def _healthy_note(self, d: BreakpointDiagnosis, ctx: str) -> ResearchNote:
        segs = d.segment_diagnoses
        avg_rel = sum(sd.evidence.get("reliability", 0.5) for sd in segs) / max(len(segs), 1)
        seg_desc = " → ".join(sd.segment_id for sd in segs)
        total_obs = sum(sd.evidence.get("observations", 0) for sd in segs)

        return ResearchNote(
            headline=f"Transmission confirmed: {seg_desc}",
            narrative=(
                f"All segments in the {seg_desc} chain transmitted correctly. "
                f"Average segment reliability: {avg_rel:.1%}. "
                f"This reinforces confidence under current conditions."
            ),
            key_numbers={"avg_reliability": round(avg_rel, 3), "segment_count": len(segs)},
            source_diagnosis_id=d.diagnosis_id,
            context_key=ctx,
            segment_id=seg_desc,
            evidence_count=total_obs,
            confidence=self._confidence(total_obs),
            recommendation="REINFORCE all segments.",
        )

    def _breakpoint_note(self, d: BreakpointDiagnosis, ctx: str) -> ResearchNote:
        segs = d.segment_diagnoses
        bp_sd = next((sd for sd in segs if sd.is_breakpoint), None)
        if not bp_sd:
            return self._unknown_note(d, ctx)

        edge = self._graph.get_edge(bp_sd.source, bp_sd.target, bp_sd.mechanism)
        baseline = edge.reliability_default if edge else 0.50
        ctx_rel = edge.reliability_by_context.get(ctx, baseline) if edge and ctx else baseline
        obs = edge.observation_count if edge else 0
        strength = edge.edge_strength if edge else 0.0
        failures = edge.named_failure_modes if edge else []
        seg_desc = bp_sd.segment_id

        parts = [f"Transmission failure at {seg_desc}."]

        if ctx and abs(ctx_rel - baseline) > 0.02:
            parts.append(
                f"Historically, {seg_desc} works {baseline:.0%} of the time, "
                f"but during {ctx} conditions, only {ctx_rel:.0%}."
            )

        parts.append(f"Root cause: {d.root_cause_description}.")

        if failures:
            parts.append(f"Known failure triggers: {', '.join(failures[:3])}.")

        if edge and obs > 0:
            parts.append(
                f"Evidence: {obs} observations, {edge.break_count} breaks "
                f"({edge.break_rate:.0%} break rate)."
            )

        rec = _action_to_recommendation(d.suggested_action, seg_desc, ctx)

        return ResearchNote(
            headline=(
                f"Break: {seg_desc} — {baseline:.0%} baseline "
                f"→ {ctx_rel:.0%} in {ctx or 'current'}"
            ),
            narrative=" ".join(parts),
            key_numbers={
                "baseline_reliability": round(baseline, 3),
                "context_reliability": round(ctx_rel, 3),
                "edge_strength": round(strength, 3),
                "observation_count": obs,
                "break_count": edge.break_count if edge else 0,
                "break_rate": round(edge.break_rate, 3) if edge else 0.0,
                "latency_days": edge.latency_days if edge else 0,
                "failure_modes": failures[:5],
            },
            source_diagnosis_id=d.diagnosis_id,
            context_key=ctx,
            segment_id=seg_desc,
            source=bp_sd.source,
            target=bp_sd.target,
            mechanism=bp_sd.mechanism,
            evidence_count=obs,
            confidence=self._confidence(obs),
            recommendation=rec,
        )

    def _unknown_note(self, d: BreakpointDiagnosis, ctx: str) -> ResearchNote:
        return ResearchNote(
            headline=f"Inconclusive: {d.transmission_channel}",
            narrative=(f"Cannot determine breakpoint. {d.root_cause_description or ''}"),
            key_numbers={},
            source_diagnosis_id=d.diagnosis_id,
            context_key=ctx,
            confidence=FindingConfidence.PRELIMINARY,
            recommendation="Gather more data before concluding.",
        )

    @staticmethod
    def _confidence(obs: int) -> FindingConfidence:
        if obs >= 100:
            return FindingConfidence.ROBUST
        if obs >= 50:
            return FindingConfidence.ESTABLISHED
        if obs >= 20:
            return FindingConfidence.OBSERVED
        return FindingConfidence.PRELIMINARY
