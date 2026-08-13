"""HypothesisEngine — Reasoning Engine orchestrator.

Sprint 6 introduces the Agent's ability to REASON about macro signals
and produce structured Hypotheses. This is the first cognitive capability
beyond pure execution.

Conceptual model:
    Observations → Signals → REASONING → Hypotheses
                                  ↑
                             Assumptions

Design (per Architecture Review):
    - Public API: reason(signals) — expresses cognition, not data transformation.
    - Hypothesis = explanation, not signal aggregation.
    - Evidence is a first-class object (not signal_id references).
    - Confidence = belief, not agreement percentage.
    - Assumptions enable Reflection (Sprint 7).
    - No LLM, no memory, no reflection — pure rule-based MVP.

Internal pipeline:
    HypothesisGenerator   → generates explanation hypotheses
    EvidenceAggregator    → classifies supporting/contradicting evidence
    ConfidenceCalculator  → computes belief confidence
"""

from src.hypothesis.aggregator import EvidenceAggregator
from src.hypothesis.confidence import ConfidenceCalculator
from src.hypothesis.generator import HypothesisGenerator
from src.schemas.hypothesis import HypothesisSchema, HypothesisSet
from src.schemas.signal import MacroSignalSchema
from src.shared.exceptions import HypothesisError
from src.shared.logging import get_logger

logger = get_logger(__name__)


class HypothesisEngine:
    """Orchestrates the reasoning pipeline: Signals → Hypotheses.

    The HypothesisEngine is the SINGLE entry point for hypothesis generation.
    It coordinates three internal components to transform raw macro signals
    into structured, evidence-backed explanations.

    Usage:
        engine = HypothesisEngine()
        hypotheses = engine.reason(signals)

    Input:  list[MacroSignalSchema]
    Output: HypothesisSet

    The engine is STATELESS — each call to reason() is independent.
    Future Sprints (Memory, Reflection) will add stateful context
    without changing this interface.
    """

    def __init__(self) -> None:
        """Initialize the hypothesis engine with its component pipeline."""
        self._generator = HypothesisGenerator()
        self._aggregator = EvidenceAggregator()
        self._confidence = ConfidenceCalculator()

    # ── Public API ──────────────────────────────────────────────────────

    def reason(self, signals: list[MacroSignalSchema]) -> HypothesisSet:
        """Reason about macro signals and produce structured hypotheses.

        This is the primary entry point. The name "reason" reflects that
        this is a cognitive act — the Agent is forming explanations about
        the macro environment, not just aggregating data.

        Args:
            signals: All current macro signals from the Signal Engine.

        Returns:
            HypothesisSet containing 1+ structured hypotheses with
            evidence, assumptions, and confidence scores.

        Raises:
            HypothesisError: If reasoning fails fatally (should not
                             happen for rule-based MVP).
        """
        if not signals:
            logger.warning("reason_called_with_no_signals — returning empty set")
            return HypothesisSet()

        try:
            logger.info("reasoning_started signal_count=%d", len(signals))

            # Step 1: Generate hypotheses from signal patterns
            hypotheses = self._generator.generate(signals)

            # Step 2: For each hypothesis, aggregate evidence
            for hypothesis in hypotheses:
                self._populate_evidence(hypothesis, signals)

            # Step 3: Compute confidence for each hypothesis
            for hypothesis in hypotheses:
                self._populate_confidence(hypothesis)

            # Assemble the result set
            dimensions = sorted(set(h.dimension for h in hypotheses))
            summary = self._summarize(hypotheses)

            result = HypothesisSet(
                hypotheses=hypotheses,
                dimensions_covered=dimensions,
                summary=summary,
            )

            logger.info(
                "reasoning_complete hypothesis_count=%d dimensions=%s",
                len(hypotheses),
                ", ".join(dimensions),
            )

            return result

        except Exception as exc:
            raise HypothesisError(
                f"Hypothesis reasoning failed: {exc}",
                details={"signal_count": len(signals)},
            ) from exc

    # ── Private: Pipeline Steps ─────────────────────────────────────────

    def _populate_evidence(
        self,
        hypothesis: HypothesisSchema,
        signals: list[MacroSignalSchema],
    ) -> None:
        """Aggregate and attach evidence to a hypothesis.

        Evidence is classified as supporting or contradicting
        based on the hypothesis's stated direction.
        """
        supporting, contradicting = self._aggregator.aggregate(
            signals=signals,
            hypothesis_direction=hypothesis.direction,
        )

        hypothesis.supporting_evidence = supporting
        hypothesis.contradicting_evidence = contradicting

    def _populate_confidence(self, hypothesis: HypothesisSchema) -> None:
        """Compute and attach belief confidence to a hypothesis.

        Confidence measures how strongly the Agent believes
        this explanation — not the proportion of agreeing signals.
        """
        hypothesis.confidence = self._confidence.calculate(
            supporting=hypothesis.supporting_evidence,
            contradicting=hypothesis.contradicting_evidence,
        )

    # ── Private: Summary ────────────────────────────────────────────────

    @staticmethod
    def _summarize(hypotheses: list[HypothesisSchema]) -> str:
        """Produce a one-sentence overview of the macro picture."""
        if not hypotheses:
            return "No hypotheses generated — insufficient signals."

        # Find the highest-confidence hypothesis
        best = max(hypotheses, key=lambda h: h.confidence)

        direction_map = {
            "bearish": "tightening or risk-averse",
            "bullish": "easing or risk-supportive",
            "neutral": "mixed or transitional",
        }
        mood = direction_map.get(best.direction.value, "uncertain")

        count = len(hypotheses)
        dims = ", ".join(sorted(set(h.dimension for h in hypotheses)))

        return (
            f"The dominant macro narrative suggests conditions are {mood} "
            f"(across {dims}, {count} hypotheses generated)."
        )
