"""Sprint 7 — BeliefScorer.

Updates confidence based on belief review findings.
This is NOT a new confidence formula — it adjusts the existing
confidence in light of the review's findings about sufficiency
and consistency.
"""

from src.domain.reflection import FindingSeverity
from src.schemas.reflection import ReflectionFinding, ReflectionReport


class BeliefScorer:
    """Adjusts belief confidence based on review findings.

    Principles:
    - Strong evidence + no problems → confidence maintained
    - Evidence quality issues → moderate downward adjustment
    - Conflicting internal evidence → significant downward adjustment
    - Insufficient evidence → capped at moderate confidence

    All adjustments are multiplicative — they compound each other.
    """

    # ── Adjustment factors ────────────────────────────────────────────────

    # Evidence sufficiency factors
    SUFFICIENCY_FACTORS = {
        "high": 1.0,
        "medium": 0.90,
        "low": 0.75,
    }

    # Evidence consistency factors
    CONSISTENCY_FACTORS = {
        "consistent": 1.0,
        "mixed": 0.85,
        "conflicting": 0.65,
    }

    # Finding severity penalties (applied per-finding, multiplicative)
    SEVERITY_PENALTIES = {
        FindingSeverity.CRITICAL: 0.75,
        FindingSeverity.MAJOR: 0.90,
        FindingSeverity.MINOR: 0.97,
    }

    # Maximum penalty from cumulative findings
    MAX_CUMULATIVE_PENALTY = 0.40

    # ── Public API ────────────────────────────────────────────────────────

    def score(
        self,
        report: ReflectionReport,
        original_confidence: float,
    ) -> float:
        """Compute updated confidence for a reviewed hypothesis.

        Args:
            report: The review report with findings, sufficiency, consistency.
            original_confidence: The pre-review belief confidence.

        Returns:
            Updated confidence value clamped to [0.0, 1.0].
        """
        if original_confidence <= 0.0:
            return 0.0

        # 1. Base multiplier from sufficiency and consistency
        base = 1.0
        base *= self.SUFFICIENCY_FACTORS.get(
            report.evidence_sufficiency, 1.0
        )
        base *= self.CONSISTENCY_FACTORS.get(
            report.evidence_consistency, 1.0
        )

        # 2. Cumulative finding penalties
        finding_factor = self._compute_finding_penalty(report.findings)

        # 3. Apply
        updated = original_confidence * base * finding_factor
        return max(0.0, min(1.0, updated))

    def update_report_confidence(self, report: ReflectionReport) -> ReflectionReport:
        """Compute updated_confidence and write it into the report in place.

        Returns the same report object (mutated).
        """
        updated = self.score(report, report.original_confidence)
        report.updated_confidence = updated
        return report

    # ── Internal ──────────────────────────────────────────────────────────

    def _compute_finding_penalty(
        self, findings: list[ReflectionFinding]
    ) -> float:
        """Compound severity penalties. More findings = more penalty,
        but capped at MAX_CUMULATIVE_PENALTY to avoid over-reaction.
        """
        if not findings:
            return 1.0

        penalty = 1.0
        for f in findings:
            factor = self.SEVERITY_PENALTIES.get(
                f.severity, 1.0
            )
            penalty *= factor

        return max(penalty, self.MAX_CUMULATIVE_PENALTY)
