"""Sprint 7 — HypothesisReviewer.

Reviews belief by answering three questions:
1. Is the evidence sufficient?
2. Is the evidence internally consistent?
3. Should we still believe this hypothesis?

This is a belief review, NOT a rule engine. No individual assumption
evaluation, no causation analysis, no alternative explanation generation.
"""

from src.domain.reflection import FindingSeverity, ReflectionVerdict
from src.schemas.hypothesis import HypothesisSchema
from src.schemas.reflection import ReflectionFinding, ReflectionReport


class HypothesisReviewer:
    """Evaluates whether the agent should still believe a hypothesis.

    Operates exclusively on the HypothesisSchema's built-in evidence —
    no external data, no signal re-query, no LLM.
    """

    # ── Evidence sufficiency thresholds ──────────────────────────────────

    SUFFICIENCY_THRESHOLDS = {
        "high": {"min_items": 4, "min_indicators": 3},
        "medium": {"min_items": 2, "min_indicators": 2},
    }

    # ── Public API ───────────────────────────────────────────────────────

    def review(self, hypothesis: HypothesisSchema) -> ReflectionReport:
        """Perform a complete belief review on one hypothesis.

        Returns a ReflectionReport with all findings, sufficiency,
        consistency, and verdict.
        """
        findings: list[ReflectionFinding] = []

        # Question 1: Is evidence sufficient?
        sufficiency = self._assess_sufficiency(hypothesis)
        if sufficiency == "low":
            findings.append(
                ReflectionFinding(
                    type="evidence_insufficient",
                    severity=FindingSeverity.MAJOR,
                    description=(
                        f"Only {hypothesis.evidence_count} evidence "
                        f"item(s) support this hypothesis. "
                        f"More independent indicators are needed to "
                        f"build confidence."
                    ),
                )
            )
        elif sufficiency == "medium":
            findings.append(
                ReflectionFinding(
                    type="evidence_insufficient",
                    severity=FindingSeverity.MINOR,
                    description=(
                        f"Evidence count ({hypothesis.evidence_count} items) "
                        f"is adequate but not strong. Additional data would "
                        f"strengthen the conclusion."
                    ),
                )
            )

        # Single-source risk
        supporting_indicators = {
            e.indicator for e in hypothesis.supporting_evidence
        }
        if len(supporting_indicators) == 1 and hypothesis.evidence_count > 1:
            findings.append(
                ReflectionFinding(
                    type="single_source_risk",
                    severity=FindingSeverity.MAJOR,
                    description=(
                        f"All supporting evidence comes from a single "
                        f"indicator source ({next(iter(supporting_indicators))}). "
                        f"This increases vulnerability to data errors."
                    ),
                )
            )

        # Question 2: Is evidence internally consistent?
        consistency = self._assess_consistency(hypothesis)
        if consistency == "conflicting":
            findings.append(
                ReflectionFinding(
                    type="conflicting_evidence",
                    severity=FindingSeverity.CRITICAL,
                    description=(
                        f"{len(hypothesis.contradicting_evidence)} contradicting "
                        f"evidence item(s) directly oppose this hypothesis. "
                        f"Internal consistency is broken."
                    ),
                )
            )
        elif consistency == "mixed":
            findings.append(
                ReflectionFinding(
                    type="conflicting_evidence",
                    severity=FindingSeverity.MAJOR,
                    description=(
                        f"Contradicting evidence from "
                        f"{', '.join(e.indicator for e in hypothesis.contradicting_evidence)} "
                        f"suggests the situation is not clear-cut."
                    ),
                )
            )

        # Evidence quality check
        avg_contribution = self._avg_supporting_contribution(hypothesis)
        if avg_contribution < 0.4 and hypothesis.evidence_count > 0:
            findings.append(
                ReflectionFinding(
                    type="evidence_quality_low",
                    severity=FindingSeverity.MAJOR,
                    description=(
                        f"Average supporting evidence contribution "
                        f"({avg_contribution:.2f}) is weak. The evidence "
                        f"supporting this belief is not strong."
                    ),
                )
            )

        # Build report
        report = ReflectionReport(
            hypothesis_id=hypothesis.hypothesis_id,
            statement=hypothesis.statement,
            original_confidence=hypothesis.confidence,
            updated_confidence=hypothesis.confidence,  # placeholder — BeliefScorer updates
            verdict=self._determine_verdict(findings, hypothesis),
            findings=findings,
            evidence_sufficiency=sufficiency,
            evidence_consistency=consistency,
            review_summary=self._build_summary(
                sufficiency, consistency, findings, hypothesis
            ),
        )

        return report

    # ── Question 1: Sufficiency ──────────────────────────────────────────

    def _assess_sufficiency(self, h: HypothesisSchema) -> str:
        """Determine if we have enough evidence.

        Returns: 'high' | 'medium' | 'low'
        """
        total_items = h.evidence_count
        all_indicators = {e.indicator for e in h.supporting_evidence}
        all_indicators |= {e.indicator for e in h.contradicting_evidence}
        unique_count = len(all_indicators)

        high = self.SUFFICIENCY_THRESHOLDS["high"]
        if total_items >= high["min_items"] and unique_count >= high["min_indicators"]:
            return "high"

        medium = self.SUFFICIENCY_THRESHOLDS["medium"]
        if total_items >= medium["min_items"] and unique_count >= medium["min_indicators"]:
            return "medium"

        return "low"

    # ── Question 2: Consistency ──────────────────────────────────────────

    def _assess_consistency(self, h: HypothesisSchema) -> str:
        """Check if evidence tells a coherent story.

        Returns: 'consistent' | 'mixed' | 'conflicting'
        """
        if not h.contradicting_evidence:
            return "consistent"

        contra_total = sum(e.contribution for e in h.contradicting_evidence)
        support_total = sum(e.contribution for e in h.supporting_evidence)
        total = support_total + contra_total

        if total == 0:
            return "consistent"

        contra_ratio = contra_total / total

        if contra_ratio > 0.4:
            return "conflicting"
        if contra_ratio > 0.15:
            return "mixed"
        return "consistent"

    # ── Question 3: Verdict ──────────────────────────────────────────────

    def _determine_verdict(
        self,
        findings: list[ReflectionFinding],
        hypothesis: HypothesisSchema,
    ) -> ReflectionVerdict:
        """Decide: confirmed, refuted, or uncertain?"""
        has_critical = any(
            f.severity == FindingSeverity.CRITICAL for f in findings
        )
        has_major = any(
            f.severity == FindingSeverity.MAJOR for f in findings
        )

        # Empty hypothesis (no evidence at all) → uncertain
        if hypothesis.evidence_count == 0:
            return ReflectionVerdict.UNCERTAIN

        # Critical conflicting evidence → refuted
        if has_critical:
            return ReflectionVerdict.REFUTED

        # Multiple major issues → uncertain
        major_count = sum(1 for f in findings if f.severity == FindingSeverity.MAJOR)
        if major_count >= 2:
            return ReflectionVerdict.UNCERTAIN

        # Clean evidence (no findings) → confirmed
        if not findings:
            return ReflectionVerdict.CONFIRMED

        # One minor/major issue but evidence otherwise solid → confirmed
        if not has_major and not has_critical:
            return ReflectionVerdict.CONFIRMED

        # One major issue only → uncertain
        if major_count == 1:
            return ReflectionVerdict.UNCERTAIN

        return ReflectionVerdict.UNCERTAIN

    # ── Helpers ──────────────────────────────────────────────────────────

    def _avg_supporting_contribution(self, h: HypothesisSchema) -> float:
        if not h.supporting_evidence:
            return 0.0
        return sum(e.contribution for e in h.supporting_evidence) / len(
            h.supporting_evidence
        )

    def _build_summary(
        self,
        sufficiency: str,
        consistency: str,
        findings: list[ReflectionFinding],
        h: HypothesisSchema,
    ) -> str:
        parts: list[str] = []

        if sufficiency == "high":
            parts.append("Evidence is sufficient")
        elif sufficiency == "medium":
            parts.append("Evidence is adequate")
        else:
            parts.append("Evidence is insufficient")

        if consistency == "conflicting":
            parts.append("but internally conflicting")
        elif consistency == "mixed":
            parts.append("with minor internal tension")
        else:
            parts.append("and internally consistent")

        verdict = self._determine_verdict(findings, h)
        if verdict == ReflectionVerdict.CONFIRMED:
            parts.append("— belief is CONFIRMED.")
        elif verdict == ReflectionVerdict.REFUTED:
            parts.append("— belief is REFUTED.")
        else:
            parts.append("— belief is UNCERTAIN.")

        return " ".join(parts)
