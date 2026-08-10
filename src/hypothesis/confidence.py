"""ConfidenceCalculator — Compute the Agent's belief confidence in a Hypothesis.

Sprint 6 MVP: multi-factor proxy formula.

Semantic note (important):
    Confidence here measures **how strongly the Agent believes the explanation**,
    NOT "what proportion of signals agree."

    The MVP uses signal-level metrics (strength, agreement ratio, coverage)
    as a PROXY for belief confidence. This is an acceptable simplification
    for a rule-based system. Future iterations (LLM-based, learned weights)
    will replace the proxy with true belief modeling.

Multi-factor formula:
    Final Confidence = 0.35 × Agreement + 0.35 × Strength + 0.30 × Coverage

    Agreement Score  = supporting / (supporting + contradicting), capped at 1.0
                       If no evidence, defaults to 0.30.
    Strength Score   = mean(evidence.contribution) across supporting evidence.
                       If no supporting evidence, defaults to 0.10.
    Coverage Score   = min(unique_indicators / min_required, 1.0)
                       min_required = 2 by default.

Edge cases:
    - No evidence at all → confidence = 0.10 (complete uncertainty)
    - All supporting, no contradicting → agreement = 1.0
    - All contradicting, no supporting → confidence = very low
"""

from src.schemas.hypothesis import HypothesisEvidence
from src.shared.logging import get_logger

logger = get_logger(__name__)


class ConfidenceCalculator:
    """Multi-factor confidence scoring for hypotheses.

    Responsibilities:
        - Compute a single confidence score from evidence.
        - Use agreement, strength, and coverage as proxy factors.
        - Return 0.0–1.0 with proper edge case handling.

    Non-responsibilities:
        - Does NOT modify the hypothesis.
        - Does NOT access external data.
        - Does NOT learn or adapt (MVP — future: ML-based).
    """

    # Factor weights — must sum to 1.0
    _W_AGREEMENT: float = 0.35
    _W_STRENGTH: float = 0.35
    _W_COVERAGE: float = 0.30

    # Minimum number of indicators expected for full coverage
    _MIN_INDICATORS: int = 2

    def calculate(
        self,
        supporting: list[HypothesisEvidence],
        contradicting: list[HypothesisEvidence],
    ) -> float:
        """Calculate the Agent's belief confidence in a hypothesis.

        Args:
            supporting:    Evidence items that support the hypothesis.
            contradicting: Evidence items that challenge the hypothesis.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        total = len(supporting) + len(contradicting)

        if total == 0:
            logger.debug("confidence_no_evidence -> 0.10")
            return 0.10

        # ── Agreement Score ──────────────────────────────────────────
        agreement = self._agreement_score(supporting, contradicting, total)

        # ── Strength Score ───────────────────────────────────────────
        strength = self._strength_score(supporting)

        # ── Coverage Score ───────────────────────────────────────────
        coverage = self._coverage_score(supporting, contradicting)

        # ── Weighted Final ───────────────────────────────────────────
        confidence = round(
            self._W_AGREEMENT * agreement
            + self._W_STRENGTH * strength
            + self._W_COVERAGE * coverage,
            4,
        )

        # Clamp
        confidence = max(0.0, min(1.0, confidence))

        logger.debug(
            "confidence_calculated "
            "agreement=%.2f strength=%.2f coverage=%.2f → final=%.2f",
            agreement,
            strength,
            coverage,
            confidence,
        )

        return confidence

    # ── Factor Computations ───────────────────────────────────────────

    @staticmethod
    def _agreement_score(
        supporting: list[HypothesisEvidence],
        contradicting: list[HypothesisEvidence],
        total: int,
    ) -> float:
        """Proportion of evidence that supports the hypothesis.

        If no evidence at all, returns 0.30 (weak default).
        """
        if total == 0:
            return 0.30
        return round(len(supporting) / total, 4)

    @staticmethod
    def _strength_score(supporting: list[HypothesisEvidence]) -> float:
        """Mean contribution of supporting evidence.

        If no supporting evidence, returns 0.10.
        """
        if not supporting:
            return 0.10
        mean_contribution = sum(e.contribution for e in supporting) / len(supporting)
        return round(mean_contribution, 4)

    @staticmethod
    def _coverage_score(
        supporting: list[HypothesisEvidence],
        contradicting: list[HypothesisEvidence],
    ) -> float:
        """Indicator diversity score — how many distinct indicators contribute.

        Both supporting and contradicting evidence count toward coverage,
        because even contradicting evidence demonstrates awareness.
        """
        all_evidence = supporting + contradicting
        unique = set(e.indicator for e in all_evidence)
        return round(min(len(unique) / ConfidenceCalculator._MIN_INDICATORS, 1.0), 4)
