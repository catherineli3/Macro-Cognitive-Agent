"""EvidenceAggregator — Transforms signal evidence into hypothesis evidence.

Sprint 6 MVP: rule-based aggregation.
Each MacroSignal's evidence chain is converted into HypothesisEvidence objects,
classified as "supporting" or "contradicting" relative to the hypothesis direction.

Design:
    - Evidence is FIRST-CLASS — not a signal_id reference.
      Reflection (Sprint 7) consumes HypothesisEvidence directly.
    - Alignment determines whether evidence supports or contradicts.
    - Contribution is computed from signal strength × confidence.
"""

from src.schemas.hypothesis import HypothesisEvidence
from src.schemas.signal import MacroSignalSchema, SignalDirection
from src.shared.logging import get_logger

logger = get_logger(__name__)

# Weight mapping: signal strength → base contribution
_STRENGTH_WEIGHT: dict[str, float] = {
    "strong": 0.80,
    "moderate": 0.55,
    "weak": 0.30,
}


class EvidenceAggregator:
    """Aggregates signal-level evidence into hypothesis-level evidence.

    Responsibilities:
        - Convert SignalEvidence → HypothesisEvidence
        - Classify each item as "supporting" or "contradicting"
        - Compute contribution weight from signal strength × confidence

    Non-responsibilities:
        - Does NOT calculate hypothesis-level confidence (that's ConfidenceCalculator)
        - Does NOT decide which signals belong to which hypothesis (that's Generator)
        - Does NOT access external systems
    """

    def aggregate(
        self,
        signals: list[MacroSignalSchema],
        hypothesis_direction: SignalDirection,
    ) -> tuple[list[HypothesisEvidence], list[HypothesisEvidence]]:
        """Aggregate all signals into supporting and contradicting evidence.

        Args:
            signals: All signals relevant to a hypothesis.
            hypothesis_direction: The direction the hypothesis claims.

        Returns:
            (supporting_evidence, contradicting_evidence) tuple.
            Both are list[HypothesisEvidence].
        """
        supporting: list[HypothesisEvidence] = []
        contradicting: list[HypothesisEvidence] = []

        for signal in signals:
            evidence_items = self._signal_to_evidence(signal, hypothesis_direction)

            for item in evidence_items:
                if item.alignment == "supporting":
                    supporting.append(item)
                else:
                    contradicting.append(item)

        logger.debug(
            "evidence_aggregated total_signals=%d supporting=%d contradicting=%d",
            len(signals),
            len(supporting),
            len(contradicting),
        )

        return supporting, contradicting

    # ── Private ─────────────────────────────────────────────────────────

    def _signal_to_evidence(
        self,
        signal: MacroSignalSchema,
        hypothesis_direction: SignalDirection,
    ) -> list[HypothesisEvidence]:
        """Convert one MacroSignal into HypothesisEvidence items.

        Each SignalEvidence in the signal becomes one HypothesisEvidence.
        Alignment is determined by comparing signal direction to hypothesis direction.
        """
        # Determine alignment
        if signal.direction == SignalDirection.NEUTRAL:
            # Neutral signals are treated as weak supporting evidence
            alignment = "supporting"
        elif signal.direction == hypothesis_direction:
            alignment = "supporting"
        else:
            alignment = "contradicting"

        # Compute base contribution from signal strength
        base = _STRENGTH_WEIGHT.get(signal.strength.value, 0.30)

        items: list[HypothesisEvidence] = []

        if signal.evidence:
            for ev in signal.evidence:
                interpretation = ev.interpretation or (
                    f"{signal.indicator} signal: {signal.direction.value} / {signal.strength.value}"
                )
                items.append(
                    HypothesisEvidence(
                        indicator=signal.indicator,
                        signal_id=signal.signal_id,
                        observation=f"{signal.indicator} at {ev.input_value} "
                        f"(condition: {ev.condition})",
                        interpretation=interpretation,
                        contribution=round(min(base * signal.confidence, 1.0), 4),
                        alignment=alignment,
                    )
                )
        else:
            # Signal without explicit evidence — create a minimal evidence item
            items.append(
                HypothesisEvidence(
                    indicator=signal.indicator,
                    signal_id=signal.signal_id,
                    observation=f"{signal.indicator} direction={signal.direction.value} "
                    f"strength={signal.strength.value}",
                    interpretation=f"{signal.indicator} {signal.direction.value} signal "
                    f"({signal.strength.value} strength)",
                    contribution=round(min(base * signal.confidence, 1.0), 4),
                    alignment=alignment,
                )
            )

        return items
