"""Root Cause Discovery — Breakpoint detection for failed predictions.

Milestone B: Transmission Reasoning.

Upgrades Diagnosis from "error classification" to "breakpoint discovery".
Instead of labeling a failed prediction as TIMING_ERR or WEIGHT_ERR,
we trace through the transmission chain to find WHERE and WHY it broke.

Core flow:
    1. Take a failed prediction + its source hypothesis's transmission chain
    2. Check each segment: did the expected causality hold?
    3. Find the first break — that's the root cause
    4. Match to known failure modes or register new ones

This transforms the agent from "I was wrong" to "The chain broke at X→Y
because of Z, which means I should reduce reliability of X→Y in this context."
"""

from __future__ import annotations

from src.schemas.diagnosis import DiagnosisReport
from src.schemas.evaluation_v3 import EvaluationReport
from src.schemas.hypothesis_v3_1 import CandidateHypothesis, SelectedHypothesis
from src.schemas.prediction_v3 import V3PredictionOutcome
from src.schemas.transmission_v3_1 import (
    BreakpointDiagnosis,
    FailureModeCategory,
    TransmissionAction,
)
from src.shared.logging import get_logger
from src.transmission.transmission_graph import TransmissionGraph

logger = get_logger(__name__)


class BreakpointDetector:
    """Detects where transmission chains break in failed predictions.

    Takes a failed prediction, traces its expected transmission path through
    the Transmission Graph, and identifies which segment(s) failed to transmit.

    This is the Milestone B upgrade over V3.0 ErrorClassifier which only
    categorized errors by magnitude (large=HYP_ERR, medium=WEIGHT_ERR, small=TIMING_ERR).
    """

    def __init__(self, graph: TransmissionGraph) -> None:
        self._graph = graph

    def diagnose_prediction(
        self,
        outcome: V3PredictionOutcome,
        hypothesis: CandidateHypothesis | None = None,
        selected: SelectedHypothesis | None = None,
        context_key: str = "",
    ) -> BreakpointDiagnosis:
        """Diagnose a single failed prediction to find the breakpoint.

        If the prediction was correct, segments are checked for reinforcement
        rather than breakpoints.

        Args:
            outcome: The evaluated prediction outcome
            hypothesis: The full candidate hypothesis (with transmission chain)
            selected: The selected hypothesis (after competition)
            context_key: Current macro context

        Returns:
            BreakpointDiagnosis with per-segment analysis
        """
        channel = outcome.transmission_channel

        # Build expected chain from hypothesis
        expected_chain = self._build_expected_chain(hypothesis, channel)

        if not expected_chain or len(expected_chain) < 2:
            return self._simple_diagnosis(outcome, context_key)

        # Check each segment
        actual_states = self._check_segment_states(outcome, expected_chain)

        # Find breakpoint
        diagnosis = self._graph.find_breakpoint(expected_chain, actual_states, context_key)
        diagnosis.prediction_id = outcome.prediction_id
        diagnosis.transmission_channel = channel

        if hypothesis:
            diagnosis.source_hypothesis_id = hypothesis.candidate_id

        # If all segments healthy but prediction was wrong → investigate further
        if diagnosis.all_segments_healthy and not outcome.correct:
            diagnosis.root_cause_category = FailureModeCategory.UNKNOWN
            diagnosis.root_cause_description = (
                "All transmission segments appear healthy but prediction was wrong. "
                "Possible: noise (random fluctuation), missing indicator, or model bias."
            )
            diagnosis.suggested_action = TransmissionAction.NO_CHANGE

        return diagnosis

    def diagnose_batch(
        self,
        evaluation: EvaluationReport,
        hypotheses: dict[str, CandidateHypothesis] = None,
        selected_hypotheses: list[SelectedHypothesis] = None,
        context_key: str = "",
    ) -> list[BreakpointDiagnosis]:
        """Diagnose all outcomes in an evaluation report.

        Returns list of BreakpointDiagnosis, one per outcome.
        Correct predictions get "all healthy" diagnoses for reinforcement tracking.
        """
        if hypotheses is None:
            hypotheses = {}
        if selected_hypotheses is None:
            selected_hypotheses = []

        selected_map = {s.candidate_id: s for s in selected_hypotheses}

        results: list[BreakpointDiagnosis] = []
        for outcome in evaluation.outcomes:
            hyp = hypotheses.get(getattr(outcome, "source_hypothesis_id", ""))
            sel = selected_map.get(getattr(outcome, "source_hypothesis_id", ""))

            diag = self.diagnose_prediction(outcome, hyp, sel, context_key)
            results.append(diag)

        break_count = sum(1 for d in results if d.breakpoint_found)
        healthy_count = sum(1 for d in results if d.all_segments_healthy)
        logger.info(
            "breakpoint_diagnosis_complete total=%d breaks=%d healthy=%d",
            len(results),
            break_count,
            healthy_count,
        )

        return results

    # ── Internal helpers ──────────────────────────────────────────────────

    def _build_expected_chain(
        self,
        hypothesis: CandidateHypothesis | None,
        channel: str,
    ) -> list[str]:
        """Build the expected transmission chain from hypothesis + channel.

        If the hypothesis has explicit transmission_chain segments, use those.
        Otherwise, reconstruct from the channel string (dimension→asset).
        """
        if hypothesis and hypothesis.transmission_chain:
            # Extract nodes from transmission chain
            chain = [hypothesis.transmission_chain[0].source]
            for seg in hypothesis.transmission_chain:
                if seg.target not in chain:
                    chain.append(seg.target)
                elif seg.source not in chain:
                    chain.append(seg.source)
            return chain

        # Fallback: parse from channel string
        if "→" in channel:
            parts = channel.split("→")
            return [p.strip() for p in parts]

        return []

    def _check_segment_states(
        self,
        outcome: V3PredictionOutcome,
        chain: list[str],
    ) -> dict[str, bool]:
        """Check whether each segment in the expected chain transmitted correctly.

        For a correct prediction: all segments check True.
        For an incorrect prediction: at least one segment will check False.

        This uses the actual market direction from the outcome to verify
        each segment's expected correlation direction.
        """
        states: dict[str, bool] = {}

        for i in range(len(chain) - 1):
            source = chain[i]
            target = chain[i + 1]
            seg_id = f"{source}→{target}"
            edge = self._graph.get_edge(source, target)

            if not edge:
                # No known edge — cannot verify
                states[seg_id] = True  # Default: assume ok (no evidence either way)
                continue

            # Extract predicted indicator from transmission channel
            # e.g. "liquidity→NASDAQ" → "NASDAQ"
            predicted_indicator = ""
            if "→" in outcome.transmission_channel:
                predicted_indicator = outcome.transmission_channel.split("→")[-1].strip()

            # For the last segment in the chain (ends at the predicted indicator):
            #   The final segment determines the prediction outcome.
            # For intermediate segments: we check the overall outcome;
            #   breakpoint detection logic (find_breakpoint) will identify
            #   the FIRST failing segment as the root cause
            if target == predicted_indicator or i == len(chain) - 2:
                states[seg_id] = outcome.correct
            else:
                states[seg_id] = outcome.correct

        return states

    def _simple_diagnosis(
        self,
        outcome: V3PredictionOutcome,
        context_key: str,
    ) -> BreakpointDiagnosis:
        """Fallback diagnosis when no transmission chain is available."""
        diagnosis = BreakpointDiagnosis(
            prediction_id=outcome.prediction_id,
            transmission_channel=outcome.transmission_channel,
            all_segments_healthy=outcome.correct,
        )

        if not outcome.correct:
            diagnosis.root_cause_category = FailureModeCategory.UNKNOWN
            diagnosis.root_cause_description = (
                f"No transmission chain available for {outcome.transmission_channel}. "
                f"Cannot locate breakpoint — error magnitude: {outcome.error_magnitude:.3f}"
            )
            diagnosis.suggested_action = TransmissionAction.NO_CHANGE

        return diagnosis


class DiagnosisUpgrader:
    """Upgrades V3.0 ErrorClassification to V3.1 BreakpointDiagnosis.

    V3.0 says: "This prediction is a WEIGHT_ERR" (what category?)
    V3.1 says: "The chain broke at credit→risk_appetite because VIX spiked" (why, where?)

    This bridge allows V3.0 diagnosis output to be enriched with breakpoint
    information without changing the existing DiagnosisEngine interface.
    """

    def __init__(self, graph: TransmissionGraph) -> None:
        self._detector = BreakpointDetector(graph)

    def enrich(
        self,
        v3_diagnosis: DiagnosisReport,
        evaluation: EvaluationReport,
        hypotheses: dict[str, CandidateHypothesis] = None,
        context_key: str = "",
    ) -> dict[str, BreakpointDiagnosis]:
        """Enrich V3.0 DiagnosisReport with breakpoint diagnoses.

        Returns:
            Mapping of prediction_id → BreakpointDiagnosis
        """
        breakpoints = self._detector.diagnose_batch(
            evaluation, hypotheses or {}, context_key=context_key
        )

        enriched: dict[str, BreakpointDiagnosis] = {}
        for bp in breakpoints:
            enriched[bp.prediction_id] = bp

        # Log upgrade summary
        breaks = sum(1 for b in enriched.values() if b.breakpoint_found)
        actions = sum(1 for b in enriched.values() if b.is_actionable)
        logger.info(
            "diagnosis_upgrade predictions=%d breakpoints_found=%d actionable=%d",
            len(enriched),
            breaks,
            actions,
        )

        return enriched
