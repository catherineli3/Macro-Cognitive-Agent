"""V5.3 Memo Grader — Orchestrates all QA checks and produces ResearchScoreCard.

The central QA orchestrator. Runs all 6 checkers against a memo,
computes weighted scores, assigns grade, and returns verdict.

Score < 80 → REJECT (must regenerate)
Score 70-79 → CONDITIONAL (can publish with warnings)
Score >= 80 → PASS

Usage:
    grader = MemoGrader()
    scorecard = grader.grade(memo_text)
    if scorecard.verdict == QAVerdict.REJECT:
        # Regenerate memo
        ...
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from src.research.qa.schemas import (
    ResearchScoreCard,
    DimensionScore,
    MemoGrade,
    QAVerdict,
)
from src.research.qa.hallucination_checker import HallucinationChecker
from src.research.qa.source_verifier import SourceVerifier
from src.research.qa.reasoning_checker import ReasoningChecker
from src.research.qa.causal_checker import CausalChecker
from src.research.qa.trade_checker import TradeChecker


class MemoGrader:
    """Orchestrate all QA checks on a research memo.

    Can grade:
        - Raw text memo
        - PipelineState output (V5.2)
        - ResearchMemo object (V4)
    """

    QUALITY_THRESHOLD = 80  # Minimum score to pass

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

        self.hallucination = HallucinationChecker()
        self.source_verifier = SourceVerifier()
        self.reasoning = ReasoningChecker()
        self.causal = CausalChecker()
        self.trade = TradeChecker()

    # ── Public Interface ─────────────────────────────────────────────

    def grade(self, text: str, memo_id: str = "") -> ResearchScoreCard:
        """Grade a research memo and return a scorecard.

        Args:
            text: Full text of the research memo
            memo_id: Optional identifier for the memo

        Returns:
            ResearchScoreCard with all dimension scores
        """
        if not text.strip():
            return self._empty_scorecard(memo_id)

        scorecard = ResearchScoreCard(
            evaluated_at=datetime.now().isoformat(),
            memo_id=memo_id,
        )

        # Extract sections for targeted analysis
        sections = self._extract_sections(text)

        # Run all checkers
        scorecard.evidence_coverage = self._check_evidence_coverage(
            text, sections
        )
        scorecard.reasoning_consistency = self.reasoning.verify(text)
        scorecard.causal_completeness = self.causal.verify(text)
        scorecard.counter_quality = self._check_counter_quality(text, sections)
        scorecard.prediction_testability = self._check_prediction_testability(
            text, sections
        )
        scorecard.hallucination_risk = self.hallucination.check(text)
        scorecard.source_traceability = self.source_verifier.verify(text)

        # Trade check on trade-specific section
        trade_text = sections.get("trade", text)
        scorecard.trade_actionability = self.trade.verify(trade_text)

        # Compute total
        scorecard.compute_total()

        # Generate assessment
        scorecard.overall_assessment = self._generate_assessment(scorecard)
        scorecard.critical_issues = self._identify_critical_issues(scorecard)
        scorecard.improvement_actions = self._generate_improvements(scorecard)

        return scorecard

    def grade_from_pipeline(self, pipeline_state) -> ResearchScoreCard:
        """Grade from V5.2 PipelineState output."""
        # Extract text from pipeline state
        from src.research.reasoning_pipeline.pipeline import ReasoningPipeline
        pipeline = ReasoningPipeline(self.config)
        text = pipeline._build_summary(pipeline_state)
        return self.grade(text, memo_id=pipeline_state.pipeline_id)

    def quick_check(self, text: str) -> dict:
        """Quick quality check (lighter weight, no full grading).

        Returns:
            dict with pass/reject and key issues
        """
        scorecard = self.grade(text)
        return {
            "pass": scorecard.verdict != QAVerdict.REJECT,
            "score": scorecard.total_score,
            "grade": scorecard.grade.value,
            "verdict": scorecard.verdict.value,
            "top_issues": scorecard.critical_issues[:3],
        }

    # ── Section Extraction ────────────────────────────────────────────

    def _extract_sections(self, text: str) -> dict[str, str]:
        """Extract named sections from memo text."""
        sections = {}

        # Common section headers
        section_patterns = {
            "executive_summary": r'(?:EXECUTIVE\s+SUMMARY|Executive\s+Summary)',
            "observations": r'(?:KEY\s+OBSERVATIONS|Key\s+Observations|OBSERVATIONS)',
            "evidence": r'(?:EVIDENCE|Evidence\s+Table|SUPPORTING\s+EVIDENCE)',
            "hypothesis": r'(?:HYPOTHESIS|Central\s+Hypothesis|OUR\s+VIEW)',
            "counter": r'(?:COUNTER|Counter[\s-]?Argument|RISK\s+TO\s+VIEW)',
            "prediction": r'(?:FORECAST|Prediction|OUTLOOK)',
            "trade": r'(?:TRADE|Trade\s+Expression|POSITIONING)',
            "risk": r'(?:RISK|Risk\s+Dashboard|WATCHLIST)',
        }

        current_section = "body"
        sections[current_section] = ""

        for line in text.split('\n'):
            line_stripped = line.strip()
            matched = False
            for name, pattern in section_patterns.items():
                if re.search(pattern, line_stripped, re.IGNORECASE):
                    current_section = name
                    sections.setdefault(current_section, "")
                    matched = True
                    break
            if not matched:
                sections[current_section] = (
                    sections.get(current_section, "") + line_stripped + "\n"
                )

        return sections

    # ── Dimension Checkers (custom) ────────────────────────────────────

    def _check_evidence_coverage(
        self,
        text: str,
        sections: dict[str, str],
    ) -> DimensionScore:
        """Check if conclusions are backed by evidence."""
        score = DimensionScore(
            dimension="evidence_coverage",
            score=100.0,
            weight=0.20,
        )

        text_lower = text.lower()
        deductions = 0

        # Count evidence markers
        evidence_markers = [
            r'data\s+(?:show|indicate|confirm|suggest|reveal)',
            r'(?:chart|figure|table)\s+\d+',
            r'according\s+to\s+(?:the\s+)?(?:latest|recent|data)',
            r'(?:source|data):\s+',
            r'supported\s+by',
            r'evidenced?\s+(?:by|from)',
            r'(?:we|i)\s+(?:find|found)\s+that',
        ]
        evidence_count = sum(
            len(re.findall(p, text_lower)) for p in evidence_markers
        )

        if evidence_count < 3:
            deductions += 35
            score.findings.append("Insufficient evidence citations")
        elif evidence_count < 6:
            deductions += 15
            score.findings.append(f"Moderate evidence: {evidence_count} citations")

        # Check if claims match evidence count
        claim_markers = [
            r'\b(?:believe|think|expect|forecast|predict|estimate)\b',
            r'\b(?:suggest|indicate|imply|point\s+to)\b',
        ]
        claim_count = sum(
            len(re.findall(p, text_lower)) for p in claim_markers
        )

        if claim_count > evidence_count * 2:
            deductions += 20
            score.findings.append(
                f"Claims ({claim_count}) outnumber evidence ({evidence_count}) — "
                "assertions without backing"
            )

        score.score = max(100 - deductions, 0)
        score.grade = self._to_grade(score.score)

        if score.score < 80:
            score.recommendations.append("Add data citations for each conclusion")
            score.recommendations.append("Include specific data points with sources")

        return score

    def _check_counter_quality(
        self,
        text: str,
        sections: dict[str, str],
    ) -> DimensionScore:
        """Check counterargument quality."""
        score = DimensionScore(
            dimension="counter_quality",
            score=100.0,
            weight=0.15,
        )

        counter_text = sections.get("counter", text)
        counter_lower = counter_text.lower()
        deductions = 0

        # Check for counter language
        counter_markers = [
            r'counter[\s-]?argument', r'bear\s+case', r'skeptical\s+view',
            r'however', r'on\s+the\s+other\s+hand', r'risk\s+is\s+that',
            r'what\s+could\s+go\s+wrong', r'alternative\s+(?:view|scenario)',
        ]
        counter_count = sum(
            len(re.findall(p, counter_lower)) for p in counter_markers
        )

        if counter_count == 0:
            deductions += 40
            score.findings.append("NO counterarguments — fatal flaw in research")
        elif counter_count < 3:
            deductions += 20
            score.findings.append(f"Weak counter treatment: only {counter_count} references")

        # Check if counters have severity labels
        severity_marks = re.findall(
            r'\b(?:fatal|major|serious|significant|minor|modest)\b',
            counter_lower,
        )
        if not severity_marks and counter_count > 0:
            deductions += 15
            score.findings.append("Counters not severity-graded")

        # Check invalidation conditions
        invalidation = re.findall(
            r'(?:invalid|wrong|incorrect|prove\s+wrong|revisit|reassess)',
            counter_lower,
        )
        if not invalidation:
            deductions += 10
            score.findings.append("No invalidation conditions defined")

        score.score = max(100 - deductions, 0)
        score.grade = self._to_grade(score.score)

        if score.score < 80:
            score.recommendations.append("Add at least 3 structured counterarguments")
            score.recommendations.append("Grade each counter by severity (fatal/major/minor)")
            score.recommendations.append("Define explicit invalidation conditions")

        return score

    def _check_prediction_testability(
        self,
        text: str,
        sections: dict[str, str],
    ) -> DimensionScore:
        """Check if predictions are testable."""
        score = DimensionScore(
            dimension="prediction_testability",
            score=100.0,
            weight=0.10,
        )

        pred_text = sections.get("prediction", text)
        pred_lower = pred_text.lower()
        deductions = 0

        # Check predictions have probability
        prob_count = len(re.findall(
            r'\b(\d{1,2})%\s+(?:probability|chance|confidence)',
            pred_lower,
        ))
        if prob_count < 1:
            deductions += 25
            score.findings.append("No probability-quantified predictions")

        # Check predictions have horizon
        horizon_count = len(re.findall(
            r'\b(?:week|month|quarter|year|Q[1-4]|H[12])\b',
            pred_lower,
        ))
        if horizon_count < 1:
            deductions += 20
            score.findings.append("No time horizon for predictions")

        # Check for vague predictions
        vague_preds = len(re.findall(
            r'\b(?:may|might|could|possibly|maybe|perhaps)\s+\w+\s+\w+\b',
            pred_lower,
        ))
        if vague_preds > 3 and prob_count == 0:
            deductions += 15
            score.findings.append("Vague predictions without probability calibration")

        # Check invalidation conditions
        if "invalidation" not in pred_lower and "prove wrong" not in pred_lower:
            deductions += 10
            score.findings.append("No invalidation conditions for predictions")

        score.score = max(100 - deductions, 0)
        score.grade = self._to_grade(score.score)

        if score.score < 80:
            score.recommendations.append(
                "Every prediction needs: probability, horizon, invalidation condition"
            )

        return score

    # ── Assessment Generation ─────────────────────────────────────────

    def _generate_assessment(self, sc: ResearchScoreCard) -> str:
        """Generate overall assessment text."""
        if sc.total_score >= 90:
            return (
                f"Excellent research quality ({sc.total_score:.1f}/100, {sc.grade.value}). "
                "Professional-grade analysis with strong evidence base, clear causal reasoning, "
                "and well-calibrated predictions. Suitable for institutional distribution."
            )
        elif sc.total_score >= 80:
            return (
                f"Good research quality ({sc.total_score:.1f}/100, {sc.grade.value}). "
                "Solid macro analysis meeting professional standards. Minor improvements "
                "recommended in weaker dimensions."
            )
        elif sc.total_score >= 70:
            return (
                f"Adequate research quality ({sc.total_score:.1f}/100, {sc.grade.value}). "
                "Publishable with caveats. Critical gaps exist in evidence or reasoning "
                "that should be addressed before distribution."
            )
        elif sc.total_score >= 60:
            return (
                f"Below standard ({sc.total_score:.1f}/100, {sc.grade.value}). "
                "Significant quality issues. Not suitable for publication. "
                "Requires substantive revision focused on evidence and counterarguments."
            )
        else:
            return (
                f"Unacceptable quality ({sc.total_score:.1f}/100, {sc.grade.value}). "
                "Fundamental issues with reasoning, evidence, or structure. "
                "Complete regeneration required."
            )

    def _identify_critical_issues(self, sc: ResearchScoreCard) -> list[str]:
        """Identify critical issues requiring immediate attention."""
        issues = []

        for dim in sc.dimensions:
            if dim.score < 60:
                issues.append(
                    f"[CRITICAL] {dim.dimension}: score {dim.score:.0f}/100 — "
                    f"{'; '.join(dim.findings[:2])}"
                )
            elif dim.score < 75:
                issues.append(
                    f"[WARNING] {dim.dimension}: score {dim.score:.0f}/100 — "
                    f"{dim.findings[0] if dim.findings else 'Needs improvement'}"
                )

        return issues

    def _generate_improvements(self, sc: ResearchScoreCard) -> list[str]:
        """Generate prioritized improvement actions."""
        actions = []

        # Sort dimensions by score (worst first)
        sorted_dims = sorted(sc.dimensions, key=lambda d: d.score)

        for dim in sorted_dims[:3]:
            if dim.recommendations:
                actions.extend(dim.recommendations[:2])

        # Add global recommendations
        if sc.total_score < 80:
            actions.append(
                "GLOBAL: Reduce unsupported assertions; increase citation density"
            )
            actions.append(
                "GLOBAL: Ensure each section has clear evidence linkage"
            )

        return actions[:8]

    def _empty_scorecard(self, memo_id: str) -> ResearchScoreCard:
        """Return a zero scorecard for empty input."""
        sc = ResearchScoreCard(memo_id=memo_id)
        sc.compute_total()
        sc.overall_assessment = "Empty memo — no content to evaluate"
        sc.critical_issues = ["No content provided"]
        return sc

    def _to_grade(self, score: float) -> MemoGrade:
        if score >= 90:
            return MemoGrade.A
        elif score >= 80:
            return MemoGrade.B
        elif score >= 65:
            return MemoGrade.C
        return MemoGrade.D
