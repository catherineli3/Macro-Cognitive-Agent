"""Sprint 7 — ReflectionEngine.

Orchestrates belief review: HypothesisSet → ReflectionSet.

Pipeline:
    1. HypothesisReviewer → reviews each hypothesis, produces findings + verdict
    2. BeliefScorer → adjusts confidence based on review
    3. Assembly → ReflectionSet with overall summary
"""

from src.schemas.hypothesis import HypothesisSchema, HypothesisSet
from src.schemas.reflection import ReflectionReport, ReflectionSet
from src.critic.reviewer import HypothesisReviewer
from src.critic.scorer import BeliefScorer
from src.domain.reflection import ReflectionVerdict


class ReflectionEngine:
    """Belief Review Engine.

    Given a HypothesisSet, evaluates whether the agent should still
    believe each hypothesis. Produces a ReflectionSet with updated
    confidence and verdicts.

    This is a stateless, deterministic engine — no LLM, no memory,
    no external data access.
    """

    def __init__(self) -> None:
        self._reviewer = HypothesisReviewer()
        self._scorer = BeliefScorer()

    # ── Public API ────────────────────────────────────────────────────────

    def review(self, hypothesis_set: HypothesisSet) -> ReflectionSet:
        """Review all hypotheses and produce belief-updated ReflectionSet.

        Args:
            hypothesis_set: Output from Sprint 6 (HypothesisEngine.reason).

        Returns:
            ReflectionSet with one report per hypothesis, each containing
            findings, updated confidence, and a verdict.
        """
        reports: list[ReflectionReport] = []

        for hypothesis in hypothesis_set.hypotheses:
            report = self._review_one(hypothesis)
            reports.append(report)

        result = ReflectionSet(
            reports=reports,
            summary=self._build_overall_summary(reports),
        )
        return result

    # ── Internal ──────────────────────────────────────────────────────────

    def _review_one(self, hypothesis: HypothesisSchema) -> ReflectionReport:
        """Review a single hypothesis end-to-end."""
        # Step 1: Review → findings, sufficiency, consistency, verdict
        report = self._reviewer.review(hypothesis)

        # Step 2: Score → updated_confidence
        self._scorer.update_report_confidence(report)

        # Step 3: Re-determine verdict if confidence dropped too far
        if report.updated_confidence < 0.25:
            report.verdict = ReflectionVerdict.REFUTED

        return report

    def _build_overall_summary(
        self, reports: list[ReflectionReport]
    ) -> str:
        """Build a one-sentence overall summary."""
        total = len(reports)
        if total == 0:
            return "No hypotheses to review."

        confirmed = sum(
            1 for r in reports if r.verdict == ReflectionVerdict.CONFIRMED
        )
        refuted = sum(
            1 for r in reports if r.verdict == ReflectionVerdict.REFUTED
        )
        uncertain = total - confirmed - refuted

        parts: list[str] = []
        if confirmed:
            parts.append(f"{confirmed} confirmed")
        if refuted:
            parts.append(f"{refuted} refuted")
        if uncertain:
            parts.append(f"{uncertain} uncertain")

        return f"Reviewed {total} hypotheses: {', '.join(parts)}."
