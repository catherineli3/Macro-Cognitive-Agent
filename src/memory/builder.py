"""BeliefRecordBuilder — Transforms Hypothesis + Reflection into BeliefRecords.

Sprint 8 introduces a dedicated builder to decouple Memory from the
internal structure of Hypothesis and Reflection schemas.

Design:
    - Builder maps ReflectionVerdict → BeliefStatus. This is the ONLY
      place where Memory code touches Reflection types.
    - Builder is stateless — a pure transformer function.
    - Builder does NOT compute TransitionType (that's the Store's job).
"""

from src.domain.memory import BeliefStatus
from src.domain.reflection import ReflectionVerdict
from src.schemas.hypothesis import HypothesisSchema, HypothesisSet
from src.schemas.memory import BeliefRecord
from src.schemas.reflection import ReflectionReport, ReflectionSet

# ── ReflectionVerdict → BeliefStatus Mapping ──────────────────────────────

_VERDICT_TO_STATUS: dict[ReflectionVerdict, BeliefStatus] = {
    ReflectionVerdict.CONFIRMED: BeliefStatus.HELD,
    ReflectionVerdict.REFUTED: BeliefStatus.ABANDONED,
    ReflectionVerdict.UNCERTAIN: BeliefStatus.IN_DOUBT,
}


class BeliefRecordBuilder:
    """Builds BeliefRecords from HypothesisSet + ReflectionSet.

    Usage:
        builder = BeliefRecordBuilder()
        records = builder.build(
            hypotheses=hypothesis_set,
            reflections=reflection_set,
            run_id="plan_abc123",
        )
    """

    def build(
        self,
        hypotheses: HypothesisSet,
        reflections: ReflectionSet,
        run_id: str,
    ) -> list[BeliefRecord]:
        """Transform a complete reasoning cycle into BeliefRecords.

        Each HypothesisSchema + its corresponding ReflectionReport
        produces one BeliefRecord.

        Args:
            hypotheses: Output from HypothesisEngine.reason().
            reflections: Output from ReflectionEngine.review().
            run_id: The ExecutionPlan.plan_id for provenance.

        Returns:
            One BeliefRecord per hypothesis (in the same order as hypotheses).
        """
        # Build a lookup: hypothesis_id → ReflectionReport
        report_by_id: dict[str, ReflectionReport] = {}
        for report in reflections.reports:
            report_by_id[report.hypothesis_id] = report

        records: list[BeliefRecord] = []

        for hypothesis in hypotheses.hypotheses:
            report = report_by_id.get(hypothesis.hypothesis_id)

            if report is None:
                # Hypothesis without a matching reflection — record as-is
                record = self._build_without_reflection(hypothesis, run_id)
            else:
                record = self._build_from_pair(hypothesis, report, run_id)

            records.append(record)

        return records

    # ── Private Builders ────────────────────────────────────────────────

    def _build_from_pair(
        self,
        hypothesis: HypothesisSchema,
        report: ReflectionReport,
        run_id: str,
    ) -> BeliefRecord:
        """Build a BeliefRecord from a matched hypothesis + reflection."""
        status = _VERDICT_TO_STATUS.get(report.verdict, BeliefStatus.IN_DOUBT)

        return BeliefRecord(
            run_id=run_id,
            hypothesis_id=hypothesis.hypothesis_id,
            dimension=hypothesis.dimension,
            statement=hypothesis.statement,
            direction=hypothesis.direction,
            confidence=report.updated_confidence,
            status=status,
            supporting_count=len(hypothesis.supporting_evidence),
            contradicting_count=len(hypothesis.contradicting_evidence),
            evidence_summary=self._summarize_evidence(hypothesis),
            review_summary=report.review_summary,
            metadata={
                "original_confidence": hypothesis.confidence,
                "verdict": report.verdict.value,
                "evidence_sufficiency": report.evidence_sufficiency,
                "evidence_consistency": report.evidence_consistency,
                "finding_count": report.finding_count,
                "hypothesis_generated_at": hypothesis.generated_at.isoformat(),
                "reflection_reviewed_at": report.reviewed_at.isoformat(),
            },
        )

    def _build_without_reflection(
        self,
        hypothesis: HypothesisSchema,
        run_id: str,
    ) -> BeliefRecord:
        """Build a BeliefRecord for a hypothesis that wasn't reviewed.

        This handles the edge case where a hypothesis exists but
        no matching ReflectionReport was produced.
        """
        return BeliefRecord(
            run_id=run_id,
            hypothesis_id=hypothesis.hypothesis_id,
            dimension=hypothesis.dimension,
            statement=hypothesis.statement,
            direction=hypothesis.direction,
            confidence=hypothesis.confidence,
            status=BeliefStatus.IN_DOUBT,
            supporting_count=len(hypothesis.supporting_evidence),
            contradicting_count=len(hypothesis.contradicting_evidence),
            evidence_summary=self._summarize_evidence(hypothesis),
            review_summary="",
            metadata={
                "original_confidence": hypothesis.confidence,
                "hypothesis_generated_at": hypothesis.generated_at.isoformat(),
                "note": "No matching reflection report found",
            },
        )

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _summarize_evidence(hypothesis: HypothesisSchema) -> str:
        """Produce a one-sentence evidence summary."""
        s = len(hypothesis.supporting_evidence)
        c = len(hypothesis.contradicting_evidence)

        if s == 0 and c == 0:
            return "No evidence."

        indicators = sorted(
            set(e.indicator for e in hypothesis.supporting_evidence)
            | set(e.indicator for e in hypothesis.contradicting_evidence)
        )

        parts = [f"{s} supporting"]
        if c > 0:
            parts.append(f"{c} contradicting")
        source_str = ", ".join(indicators) if indicators else "unknown sources"

        return f"{', '.join(parts)} evidence items from {source_str}."
