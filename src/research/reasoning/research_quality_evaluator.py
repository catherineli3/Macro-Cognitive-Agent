"""ResearchQualityEvaluator — Score research output on 6 quality dimensions.

Quality: Architecture is NOT the evaluation target. Research quality is.

Measures:
    1. Hypothesis Originality — Does agent produce original synthesis?
    2. Evidence Completeness — Does every conclusion cite evidence?
    3. Counterargument Quality — Can the agent argue against itself?
    4. Prediction Usefulness — Would a portfolio manager use this?
    5. Writing Quality — Professional, clear, logical, no repetition.
    6. Hallucination Rate — Every statement must have evidence/citation.

Output: Research Quality Score (0-100)
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.research.reasoning.schemas import CounterArgument, Hypothesis, ResearchMemo


@dataclass
class QualityDimension:
    """Score for a single quality dimension."""

    name: str = ""
    score: float = 0.0  # 0-100
    weight: float = 0.0  # Weight in overall score
    passing: bool = False  # Above threshold?
    details: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class QualityReport:
    """Complete research quality evaluation report."""

    report_id: str = ""
    memo_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Dimensions
    dimensions: dict[str, QualityDimension] = field(default_factory=dict)
    # {
    #     "hypothesis_originality": QualityDimension,
    #     "evidence_completeness": QualityDimension,
    #     ...
    # }

    # Overall
    overall_score: float = 0.0  # 0-100
    grade: str = ""  # A+, A, B, C, D, F
    passes_minimum: bool = False  # Score >= 60?
    is_professional_grade: bool = False  # Score >= 80?

    # Detailed findings
    critical_flaws: list[str] = field(default_factory=list)
    improvement_actions: list[str] = field(default_factory=list)
    hallucination_instances: list[dict] = field(default_factory=list)

    def summary(self) -> str:
        """One-paragraph quality summary."""
        return (
            f"Research Quality: {self.overall_score}/100 ({self.grade}). "
            f"{'Meets' if self.is_professional_grade else 'Does NOT meet'} "
            f"professional grade threshold. "
            f"{len(self.critical_flaws)} critical flaws, "
            f"{len(self.improvement_actions)} improvement actions."
        )


class ResearchQualityEvaluator:
    """Evaluate research memo quality on 6 dimensions.

    The evaluator checks:
    - Substance (originality, evidence, counter-arguments)
    - Utility (prediction usefulness, actionability)
    - Integrity (hallucination rate, citation coverage)
    - Craft (writing quality, structure)

    Score: 0-100
    Threshold: 60 = passing, 80 = professional grade
    """

    # Weight distribution across 6 dimensions
    DIMENSION_WEIGHTS = {
        "hypothesis_originality": 0.15,
        "evidence_completeness": 0.20,
        "counterargument_quality": 0.15,
        "prediction_usefulness": 0.20,
        "writing_quality": 0.15,
        "hallucination_rate": 0.15,
    }

    # Minimum per-dimension thresholds
    DIMENSION_THRESHOLDS = {
        "hypothesis_originality": 40,
        "evidence_completeness": 50,
        "counterargument_quality": 40,
        "prediction_usefulness": 50,
        "writing_quality": 50,
        "hallucination_rate": 60,
    }

    def evaluate(
        self,
        memo: ResearchMemo,
        hypotheses: list[Hypothesis] = None,
        counter_arguments: list[CounterArgument] = None,
    ) -> QualityReport:
        """Evaluate research quality across all 6 dimensions.

        Args:
            memo: The ResearchMemo to evaluate
            hypotheses: Original hypotheses used (for originality assessment)
            counter_arguments: Counter-arguments (for counter quality)

        Returns:
            QualityReport with dimension scores and overall grade
        """
        hypotheses = hypotheses or []
        counter_arguments = counter_arguments or []

        dims = {}

        # 1. Hypothesis Originality
        dims["hypothesis_originality"] = self._score_originality(hypotheses, memo)

        # 2. Evidence Completeness
        dims["evidence_completeness"] = self._score_evidence(memo, hypotheses)

        # 3. Counterargument Quality
        dims["counterargument_quality"] = self._score_counterarguments(
            counter_arguments, hypotheses
        )

        # 4. Prediction Usefulness
        dims["prediction_usefulness"] = self._score_predictions(memo, hypotheses)

        # 5. Writing Quality
        dims["writing_quality"] = self._score_writing(memo)

        # 6. Hallucination Rate
        dims["hallucination_rate"], hall_instances = self._score_hallucination(memo, hypotheses)

        # Overall score
        overall = sum(
            dims[name].score * self.DIMENSION_WEIGHTS[name] for name in self.DIMENSION_WEIGHTS
        )
        overall = round(overall, 1)

        # Grade
        grade = self._assign_grade(overall)

        # Critical flaws
        critical = []
        for name, dim in dims.items():
            threshold = self.DIMENSION_THRESHOLDS.get(name, 50)
            if dim.score < threshold:
                critical.append(f"{name}: {dim.score}/100 (threshold: {threshold})")

        # Improvement actions
        actions = []
        for dim in dims.values():
            actions.extend(dim.suggestions)

        return QualityReport(
            report_id=f"QUAL_{str(uuid.uuid4())[:8]}",
            memo_id=memo.memo_id,
            dimensions=dims,
            overall_score=overall,
            grade=grade,
            passes_minimum=overall >= 60,
            is_professional_grade=overall >= 80,
            critical_flaws=critical,
            improvement_actions=actions,
            hallucination_instances=hall_instances,
        )

    # ── Dimension 1: Hypothesis Originality ──

    def _score_originality(
        self, hypotheses: list[Hypothesis], memo: ResearchMemo
    ) -> QualityDimension:
        """Score hypothesis originality (0-100).

        Key questions:
        - Does the hypothesis go beyond just repeating the news?
        - Is there genuine synthesis?
        - Are causal chains non-obvious?
        """
        dim = QualityDimension(
            name="hypothesis_originality",
            weight=self.DIMENSION_WEIGHTS["hypothesis_originality"],
        )

        if not hypotheses:
            dim.score = 0
            dim.details = ["No hypotheses generated"]
            dim.suggestions = ["Run hypothesis builder before evaluation"]
            dim.passing = False
            return dim

        score = 50  # Baseline

        for hyp in hypotheses:
            # Non-trivial causal chain: +points
            if hyp.causal_chain and len(hyp.causal_chain) >= 3:
                score += 5

            # Structural vs cyclical factor distinction: +points
            if hyp.structural_factors and hyp.cyclical_factors:
                score += 5

            # Named assumptions: +points
            if hyp.key_assumptions:
                score += min(len(hyp.key_assumptions) * 3, 10)

            # Falsification conditions: +points (scientific thinking)
            if hyp.falsification_conditions:
                score += min(len(hyp.falsification_conditions) * 3, 10)

        # Cap
        score = min(100, score)

        details = [
            f"Hypotheses generated: {len(hypotheses)}",
            f"Average causal chain depth: {sum(len(h.causal_chain) for h in hypotheses) / max(len(hypotheses), 1):.1f} steps",
        ]

        suggestions = []
        if score < 60:
            suggestions.append("Deepen causal chains — 3+ steps minimum")
            suggestions.append("Add structural/cyclical factor distinction to all hypotheses")
            suggestions.append("Add falsification conditions")
        elif score < 80:
            suggestions.append("Consider cross-domain synthesis (e.g., labor policy → growth)")

        dim.score = score
        dim.details = details
        dim.suggestions = suggestions
        dim.passing = score >= self.DIMENSION_THRESHOLDS["hypothesis_originality"]

        return dim

    # ── Dimension 2: Evidence Completeness ──

    def _score_evidence(self, memo: ResearchMemo, hypotheses: list[Hypothesis]) -> QualityDimension:
        """Score evidence completeness (0-100).

        Every conclusion must have evidence behind it.
        """
        dim = QualityDimension(
            name="evidence_completeness",
            weight=self.DIMENSION_WEIGHTS["evidence_completeness"],
        )

        score = 0

        # Count evidence-backed claims
        total_hypotheses = len(hypotheses)
        if total_hypotheses == 0:
            dim.score = 0
            dim.details = ["No hypotheses to evaluate"]
            dim.suggestions = ["Run full reasoning pipeline"]
            dim.passing = False
            return dim

        # How many hypotheses have evidence?
        with_evidence = sum(
            1 for h in hypotheses if h.supporting_evidence or h.contradicting_evidence
        )
        evidence_ratio = with_evidence / total_hypotheses

        score += evidence_ratio * 40  # Up to 40 points for hypotheses with evidence

        # Average evidence items per hypothesis
        avg_evidence = (
            sum(len(h.supporting_evidence) + len(h.contradicting_evidence) for h in hypotheses)
            / total_hypotheses
        )
        score += min(avg_evidence * 10, 30)  # Up to 30 for evidence quantity

        # Citing both supporting AND contradicting evidence
        with_both = sum(1 for h in hypotheses if h.supporting_evidence and h.contradicting_evidence)
        score += (with_both / total_hypotheses) * 20  # Up to 20 for balanced evidence

        # Memo citations
        if memo.citation_count > 0:
            score += min(memo.citation_count * 3, 10)

        score = min(100, round(score))

        suggestions = []
        if evidence_ratio < 1.0:
            suggestions.append("Every hypothesis must link to specific evidence")
        if avg_evidence < 2:
            suggestions.append("Aim for 2+ evidence items per hypothesis")
        if with_both / max(total_hypotheses, 1) < 0.5:
            suggestions.append("Include both supporting AND contradicting evidence")

        dim.score = score
        dim.details = [
            f"Hypotheses with evidence: {with_evidence}/{total_hypotheses}",
            f"Average evidence items: {avg_evidence:.1f}",
            f"Balanced coverage: {with_both}/{total_hypotheses}",
            f"Citations: {memo.citation_count}",
        ]
        dim.suggestions = suggestions
        dim.passing = score >= self.DIMENSION_THRESHOLDS["evidence_completeness"]

        return dim

    # ── Dimension 3: Counterargument Quality ──

    def _score_counterarguments(
        self, counters: list[CounterArgument], hypotheses: list[Hypothesis]
    ) -> QualityDimension:
        """Score counterargument quality (0-100).

        Key: Can the agent argue against itself effectively?
        """
        dim = QualityDimension(
            name="counterargument_quality",
            weight=self.DIMENSION_WEIGHTS["counterargument_quality"],
        )

        if not hypotheses:
            dim.score = 0
            dim.passing = False
            return dim

        score = 0

        # Coverage: does every hypothesis have a counter?
        counter_map = {c.target_hypothesis_id: c for c in counters}
        covered = sum(1 for h in hypotheses if h.hypothesis_id in counter_map)
        coverage = covered / len(hypotheses)
        score += coverage * 40  # Up to 40 for coverage

        # Quality: do counters have substance?
        if counters:
            with_evidence = sum(1 for c in counters if c.counter_evidence)
            score += (with_evidence / len(counters)) * 20  # Up to 20

            with_triggers = sum(1 for c in counters if c.trigger_conditions)
            score += (with_triggers / len(counters)) * 15  # Up to 15

            with_precedent = sum(1 for c in counters if c.historical_precedent)
            score += (with_precedent / len(counters)) * 15  # Up to 15

            # Severity distribution: having "fatal" counters = serious thinking
            fatal_count = sum(1 for c in counters if c.severity == "fatal")
            score += min(fatal_count * 5, 10)  # Up to 10

        score = min(100, round(score))

        suggestions = []
        if coverage < 1.0:
            suggestions.append("Every hypothesis needs a counter-argument")
        if not counters:
            suggestions.append("Run counter-argument generator")

        dim.score = score
        dim.details = [
            f"Counter coverage: {covered}/{len(hypotheses)}",
            f"Total counters: {len(counters)}",
        ]
        dim.suggestions = suggestions
        dim.passing = score >= self.DIMENSION_THRESHOLDS["counterargument_quality"]

        return dim

    # ── Dimension 4: Prediction Usefulness ──

    def _score_predictions(
        self, memo: ResearchMemo, hypotheses: list[Hypothesis]
    ) -> QualityDimension:
        """Score prediction usefulness (0-100).

        Would a portfolio manager actually use these predictions?
        """
        dim = QualityDimension(
            name="prediction_usefulness",
            weight=self.DIMENSION_WEIGHTS["prediction_usefulness"],
        )

        score = 0

        predictions = memo.predictions or []
        if not predictions and hypotheses:
            # Can extract from hypotheses
            predictions = [
                {"statement": h.statement, "confidence": h.confidence} for h in hypotheses
            ]

        if not predictions:
            dim.score = 0
            dim.details = ["No predictions in research memo"]
            dim.suggestions = [
                "Add at least 3 predictions with confidence, direction, and invalidation"
            ]
            dim.passing = False
            return dim

        # Count predictions with all required fields
        required_fields = ["statement", "direction", "confidence"]
        complete_preds = sum(1 for p in predictions if all(f in p for f in required_fields))
        score += (complete_preds / len(predictions)) * 30  # Up to 30

        # Have invalidation conditions?
        has_invalidation = memo.invalidation_conditions and len(memo.invalidation_conditions) > 0
        if has_invalidation:
            score += 20

        # Have trading implications?
        if memo.trading_implication:
            score += 20

        # Have favored/unfavored assets?
        if memo.favored_assets or memo.unfavored_assets:
            score += 15

        # Highest conviction trade specified?
        if memo.highest_conviction_trade:
            score += 15

        score = min(100, round(score))

        suggestions = []
        if not has_invalidation:
            suggestions.append("Add invalidation conditions for each prediction")
        if not memo.trading_implication:
            suggestions.append("Add explicit trading implications")
        if not memo.highest_conviction_trade:
            suggestions.append("Specify the highest-conviction trade")

        dim.score = score
        dim.details = [
            f"Predictions: {len(predictions)}",
            f"Complete (all fields): {complete_preds}/{len(predictions)}",
            f"Trading implications: {'Yes' if memo.trading_implication else 'No'}",
            f"Invalidation: {'Yes' if has_invalidation else 'No'}",
        ]
        dim.suggestions = suggestions
        dim.passing = score >= self.DIMENSION_THRESHOLDS["prediction_usefulness"]

        return dim

    # ── Dimension 5: Writing Quality ──

    def _score_writing(self, memo: ResearchMemo) -> QualityDimension:
        """Score writing quality (0-100).

        Professional, clear, logical, no repetition.
        """
        dim = QualityDimension(
            name="writing_quality",
            weight=self.DIMENSION_WEIGHTS["writing_quality"],
        )

        score = 0
        text = memo.full_memo_text or ""

        if not text:
            dim.score = 0
            dim.details = ["No memo text to evaluate"]
            dim.suggestions = ["Generate memo before evaluation"]
            dim.passing = False
            return dim

        # Word count adequacy
        wc = memo.word_count
        if wc >= 1500:
            score += 25
        elif wc >= 1000:
            score += 20
        elif wc >= 500:
            score += 10
        else:
            score += 0

        # Structure completeness
        sections = memo.sections or []
        expected_sections = {
            "Executive Summary",
            "Regime",
            "Evidence",
            "Hypothesis",
            "Counter",
            "Investment",
            "Invalidation",
        }
        found_sections = {s.heading.lower()[:15] for s in sections}
        # Fuzzy check
        section_match = 0
        for expected in expected_sections:
            if any(expected.lower() in fs for fs in found_sections):
                section_match += 1
        score += (section_match / len(expected_sections)) * 25

        # Language quality heuristics
        # - Avoid bullet dumping
        bullet_count = text.count("\n-") + text.count("\n  -")
        word_per_bullet_ratio = wc / max(bullet_count, 1)
        if word_per_bullet_ratio > 50:
            score += 15  # Good: substantial text around bullets
        elif word_per_bullet_ratio > 25:
            score += 10

        # - Professional vocabulary
        professional_terms = [
            "regime",
            "causal",
            "structural",
            "cyclical",
            "transmission",
            "preponderance",
            "contradictory",
            "implication",
            "invalidation",
            "calibration",
            "conviction",
            "tail risk",
            "hedge",
        ]
        term_count = sum(1 for t in professional_terms if t in text.lower())
        score += min(term_count * 3, 15)

        # - No excessive repetition
        paragraphs = [p for p in text.split("\n\n") if len(p) > 50]
        if paragraphs:
            repeat_score = self._repetition_score(paragraphs)
            score += repeat_score * 10  # Up to 10

        # - Has executive summary
        if memo.executive_summary and len(memo.executive_summary) > 100:
            score += 10

        score = min(100, round(score))

        suggestions = []
        if wc < 1000:
            suggestions.append(f"Expand memo to 1000+ words (current: {wc})")
        if section_match < len(expected_sections):
            suggestions.append("Complete all memo sections")
        if word_per_bullet_ratio < 25:
            suggestions.append("Reduce bullet-point density — write in paragraphs")

        dim.score = score
        dim.details = [
            f"Word count: {wc}",
            f"Sections: {section_match}/{len(expected_sections)}",
            f"Professional terms: {term_count}",
        ]
        dim.suggestions = suggestions
        dim.passing = score >= self.DIMENSION_THRESHOLDS["writing_quality"]

        return dim

    # ── Dimension 6: Hallucination Rate ──

    def _score_hallucination(
        self, memo: ResearchMemo, hypotheses: list[Hypothesis]
    ) -> tuple[QualityDimension, list[dict]]:
        """Score hallucination rate (0-100, lower = more hallucinations).

        Every statement must have evidence or citation.
        """
        dim = QualityDimension(
            name="hallucination_rate",
            weight=self.DIMENSION_WEIGHTS["hallucination_rate"],
        )

        score = 100  # Start at 100, deduct for issues
        instances = []

        text = memo.full_memo_text or ""

        # Check 1: Uncited factual claims
        # Claims that look factual but aren't backed by evidence — hard to
        # detect without NLP, so use heuristics
        factual_patterns = [
            (r"\d+\.?\d*\s*%", "percentage claim"),
            (r"\$\d+", "dollar amount"),
            (r"increase[d]? by", "directional claim"),
            (r"decline[d]? by", "directional claim"),
            (r"the \w+ is (rising|falling|increasing|decreasing)", "directional claim"),
        ]

        for pattern, claim_type in factual_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches[:3]:
                # Flag as potential hallucination if not near a citation marker
                instances.append(
                    {
                        "type": claim_type,
                        "pattern": str(m)[:50],
                        "severity": "low",
                    }
                )
                score -= 1

        # Check 2: Claims without evidence linkage
        if hypotheses:
            for h in hypotheses:
                if not h.supporting_evidence and not h.contradicting_evidence:
                    if h.confidence > 0.6:
                        score -= 5
                        instances.append(
                            {
                                "type": "unbacked_claim",
                                "detail": f"Hypothesis '{h.title}' has no evidence but confidence {h.confidence:.0%}",
                                "severity": "medium",
                            }
                        )

        # Check 3: Citation presence
        if memo.citation_count == 0 and len(text) > 500:
            score -= 10
            instances.append(
                {
                    "type": "zero_citations",
                    "detail": "Memo has no citations despite substantial content",
                    "severity": "high",
                }
            )

        score = max(0, min(100, round(score)))

        suggestions = []
        if score < 80:
            suggestions.append("Add evidence citations to all factual claims")
            suggestions.append("Run hallucination check before publishing")
            suggestions.append("Ensure every hypothesis links to specific evidence clusters")

        dim.score = score
        dim.details = [
            f"Hallucination flags: {len(instances)}",
            f"Citations: {memo.citation_count}",
        ]
        dim.suggestions = suggestions
        dim.passing = score >= self.DIMENSION_THRESHOLDS["hallucination_rate"]

        return dim, instances

    # ── Helpers ──

    @staticmethod
    def _assign_grade(score: float) -> str:
        if score >= 90:
            return "A+"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B+"
        elif score >= 60:
            return "B"
        elif score >= 50:
            return "C"
        elif score >= 40:
            return "D"
        return "F"

    @staticmethod
    def _repetition_score(paragraphs: list[str]) -> float:
        """Check for excessive repetition across paragraphs."""
        if len(paragraphs) < 2:
            return 1.0

        repeated = 0
        for i in range(len(paragraphs)):
            for j in range(i + 1, len(paragraphs)):
                words_i = set(paragraphs[i].lower().split())
                words_j = set(paragraphs[j].lower().split())
                if words_i and words_j:
                    overlap = len(words_i & words_j) / max(len(words_i), 1)
                    if overlap > 0.4:
                        repeated += 1

        max_repeats = len(paragraphs) * (len(paragraphs) - 1) / 2
        if max_repeats == 0:
            return 1.0

        ratio = 1.0 - (repeated / max_repeats) * 0.5
        return max(0, min(1, ratio))
