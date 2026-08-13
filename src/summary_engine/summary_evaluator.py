"""Phase 5: SummaryEvaluator — Quality scoring for CIO Brief.

Scores each brief on 5 dimensions:
    1. Data Accuracy      — Are all values from real data? Score based on data source quality.
    2. Context            — Does the brief connect data to broader macro themes?
    3. Causality          — Are causal chains clear and logically sound?
    4. Investment Usefulness — Is the brief actionable for portfolio decisions?
    5. Risk Awareness     — Are key risks and tail scenarios identified?

Target: Macro Summary Quality > 85/100.

Reuses: Evaluation patterns from ResearchJudgmentEngine quality scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.shared.logging import get_logger
from src.summary_engine.change_detector import ChangeSignals
from src.summary_engine.cio_brief import CIOBrief
from src.summary_engine.macro_state_layer import MacroState
from src.summary_engine.narrative_generator import MacroNarrative

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class DimensionScore:
    """Score for a single quality dimension."""

    name: str
    score: float  # 0-100
    weight: float  # weight in overall score
    rationale: str = ""
    issues: list[str] = field(default_factory=list)


@dataclass
class SummaryQuality:
    """Complete quality assessment of a CIO brief."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Dimension scores
    data_accuracy: float = 0.0  # 0-100
    context: float = 0.0
    causality: float = 0.0
    investment_usefulness: float = 0.0
    risk_awareness: float = 0.0

    # Overall
    overall_score: float = 0.0  # 0-100
    grade: str = ""  # "A+", "A", "B", etc.
    meets_target: bool = False  # > 85?

    # Details
    dimension_details: list[DimensionScore] = field(default_factory=list)
    improvement_areas: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "scores": {
                "data_accuracy": round(self.data_accuracy, 1),
                "context": round(self.context, 1),
                "causality": round(self.causality, 1),
                "investment_usefulness": round(self.investment_usefulness, 1),
                "risk_awareness": round(self.risk_awareness, 1),
            },
            "overall_score": round(self.overall_score, 1),
            "grade": self.grade,
            "meets_target": self.meets_target,
            "improvement_areas": self.improvement_areas,
            "strengths": self.strengths,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SummaryEvaluator
# ═══════════════════════════════════════════════════════════════════════════════


class SummaryEvaluator:
    """Evaluate CIO Brief quality on 5 dimensions.

    Target: > 85/100.
    Each dimension scored 0-100 with rationales.
    """

    # Dimension weights
    WEIGHTS = {
        "data_accuracy": 0.30,  # Most important — must use real data
        "context": 0.20,  # Macro context matters
        "causality": 0.20,  # Causal chains = insight quality
        "investment_usefulness": 0.20,  # Actionable for portfolios
        "risk_awareness": 0.10,  # Risk identification
    }

    # Grade boundaries
    GRADES = [
        (95, "A+"),
        (90, "A"),
        (85, "A-"),
        (80, "B+"),
        (75, "B"),
        (70, "B-"),
        (65, "C+"),
        (60, "C"),
        (0, "D"),
    ]

    def evaluate(
        self,
        brief: CIOBrief,
        macro_state: MacroState,
        change_signals: ChangeSignals,
        narrative: MacroNarrative,
        data_source_info: dict,
    ) -> SummaryQuality:
        """Evaluate CIO brief quality.

        Args:
            brief: Generated CIOBrief
            macro_state: Phase 1 state
            change_signals: Phase 2 signals
            narrative: Phase 3 narrative
            data_source_info: Dict with data source stats for accuracy scoring
        """
        sq = SummaryQuality()

        # Score each dimension
        sq.data_accuracy = self._score_data_accuracy(data_source_info)
        sq.context = self._score_context(brief, macro_state, change_signals)
        sq.causality = self._score_causality(brief, narrative)
        sq.investment_usefulness = self._score_investment_usefulness(brief)
        sq.risk_awareness = self._score_risk_awareness(brief, change_signals)

        # Build dimension details
        sq.dimension_details = [
            DimensionScore(
                name="Data Accuracy",
                score=sq.data_accuracy,
                weight=self.WEIGHTS["data_accuracy"],
                rationale=self._data_accuracy_rationale(data_source_info),
                issues=self._data_accuracy_issues(data_source_info),
            ),
            DimensionScore(
                name="Context",
                score=sq.context,
                weight=self.WEIGHTS["context"],
                rationale=self._context_rationale(brief),
            ),
            DimensionScore(
                name="Causality",
                score=sq.causality,
                weight=self.WEIGHTS["causality"],
                rationale=self._causality_rationale(brief, narrative),
            ),
            DimensionScore(
                name="Investment Usefulness",
                score=sq.investment_usefulness,
                weight=self.WEIGHTS["investment_usefulness"],
                rationale=self._investment_rationale(brief),
            ),
            DimensionScore(
                name="Risk Awareness",
                score=sq.risk_awareness,
                weight=self.WEIGHTS["risk_awareness"],
                rationale=self._risk_rationale(brief),
            ),
        ]

        # Overall score
        sq.overall_score = sum(d.score * d.weight for d in sq.dimension_details)

        # Grade
        sq.grade = self._assign_grade(sq.overall_score)
        sq.meets_target = sq.overall_score >= 85.0

        # Strengths and improvements
        sq.strengths = self._identify_strengths(sq)
        sq.improvement_areas = self._identify_improvements(sq)

        logger.info(
            "summary_evaluator_done | overall=%.1f grade=%s target=%s",
            sq.overall_score,
            sq.grade,
            "PASS" if sq.meets_target else "FAIL",
        )
        return sq

    # ── Scoring Functions ────────────────────────────────────────────────────

    def _score_data_accuracy(self, data_source_info: dict) -> float:
        """Score data accuracy based on real data coverage.

        Base 60 + up to 40 bonus for real data coverage.
        """
        total = data_source_info.get("total_indicators", 0)
        valid = data_source_info.get("valid_data", 0)
        sources = data_source_info.get("sources", {})
        worldbank_count = sources.get("WorldBank", 0)
        sina_count = sources.get("Sina", 0)

        if total == 0:
            return 0.0

        valid_ratio = valid / total

        # Base: 60 * valid_ratio
        score = 60 * valid_ratio

        # Bonus: up to 30 for using real sources (WorldBank + Sina)
        real_sources = worldbank_count + sina_count
        score += min(30, (real_sources / total) * 30)

        # Bonus: up to 10 for >95% valid
        if valid_ratio >= 0.95:
            score += 10
        elif valid_ratio >= 0.85:
            score += 5

        return min(100, score)

    def _score_context(
        self, brief: CIOBrief, macro_state: MacroState, change_signals: ChangeSignals
    ) -> float:
        """Score macro context quality."""
        score = 70.0  # Base: regime section always populated

        # Regime description quality
        if len(brief.regime_description) > 50:
            score += 5

        # Indicator detail
        if len(brief.regime_indicators) >= 5:
            score += 5

        # What Changed section
        if len(brief.what_changed) >= 3:
            score += 10
        elif len(brief.what_changed) > 0:
            score += 5

        # Divergence detection
        div_count = sum(1 for d in change_signals.divergence_signals if d.is_diverging)
        if div_count > 0:
            score += min(10, div_count * 3)

        return min(100, score)

    def _score_causality(self, brief: CIOBrief, narrative: MacroNarrative) -> float:
        """Score causal chain quality."""
        score = 65.0  # Base

        # Narrative has clear theme
        if narrative.narrative_theme and narrative.narrative_theme != "mixed_signals":
            score += 10

        # Supporting evidence count
        if len(brief.evidence_supporting) >= 4:
            score += 10
        elif len(brief.evidence_supporting) >= 2:
            score += 5

        # Contradicting evidence (shows balanced thinking)
        if len(brief.evidence_contradicting) >= 2:
            score += 5

        # Evidence balance is reasonable
        if 0.3 < narrative.evidence_balance < 0.7:
            score += 5

        # Narrative strength
        score += narrative.narrative_strength * 5

        return min(100, score)

    def _score_investment_usefulness(self, brief: CIOBrief) -> float:
        """Score investment actionability."""
        score = 60.0  # Base

        # Clear implication statement
        if len(brief.investment_implication) > 100:
            score += 10

        # Asset class views
        asset_count = len(brief.asset_views)
        if asset_count >= 5:
            score += 15
        elif asset_count >= 3:
            score += 10
        elif asset_count > 0:
            score += 5

        # Key levels provided
        if len(brief.key_levels) >= 3:
            score += 10
        elif len(brief.key_levels) > 0:
            score += 5

        # Diverse asset views
        if "equities" in brief.asset_views and "fixed_income" in brief.asset_views:
            score += 5

        return min(100, score)

    def _score_risk_awareness(self, brief: CIOBrief, change_signals: ChangeSignals) -> float:
        """Score risk identification quality."""
        score = 65.0  # Base

        # Risk count
        risk_count = len(brief.risks_to_monitor)
        if risk_count >= 4:
            score += 15
        elif risk_count >= 2:
            score += 10

        # Tail risks
        tail_count = len(brief.tail_risks)
        if tail_count >= 3:
            score += 10
        elif tail_count > 0:
            score += 5

        # Specific risks (not just generic)
        specific_count = sum(
            1
            for r in brief.risks_to_monitor
            if any(kw in r.lower() for kw in ["divergence", "positioning", "correlation", "regime"])
        )
        score += specific_count * 3

        # Key levels
        if brief.key_levels:
            score += 5

        return min(100, score)

    # ── Rationale Generation ─────────────────────────────────────────────────

    def _data_accuracy_rationale(self, info: dict) -> str:
        total = info.get("total_indicators", 0)
        valid = info.get("valid_data", 0)
        sources = info.get("sources", {})
        return (
            f"{valid}/{total} indicators with valid data. "
            f"Sources: {', '.join(f'{k}={v}' for k, v in sources.items()) if sources else 'none'}. "
            f"Data accuracy: {'Excellent' if valid/total >= 0.95 else 'Good' if valid/total >= 0.85 else 'Needs improvement'}"
        )

    def _data_accuracy_issues(self, info: dict) -> list[str]:
        issues = []
        if info.get("synthetic_used", False):
            issues.append("Synthetic data used — replace with real sources")
        if info.get("missing_count", 0) > 0:
            issues.append(f"{info['missing_count']} indicators missing data")
        return issues

    def _context_rationale(self, brief: CIOBrief) -> str:
        return (
            f"Regime assessment: {brief.current_regime}. "
            f"{len(brief.what_changed)} change signals detected. "
            f"Context quality: {'Strong' if len(brief.what_changed) >= 3 else 'Adequate'}"
        )

    def _causality_rationale(self, brief: CIOBrief, narrative: MacroNarrative) -> str:
        return (
            f"Theme: {narrative.narrative_theme}. "
            f"Supporting evidence: {len(brief.evidence_supporting)}, "
            f"contradicting: {len(brief.evidence_contradicting)}. "
            f"Evidence balance: {narrative.evidence_balance:.0%} supporting."
        )

    def _investment_rationale(self, brief: CIOBrief) -> str:
        return (
            f"{len(brief.asset_views)} asset classes with explicit views. "
            f"Key levels tracked for {len(brief.key_levels)} instruments. "
            f"{'Highly actionable' if len(brief.asset_views) >= 5 else 'Actionable'}"
        )

    def _risk_rationale(self, brief: CIOBrief) -> str:
        return (
            f"{len(brief.risks_to_monitor)} primary risks identified. "
            f"{len(brief.tail_risks)} tail risk scenarios mapped. "
            f"Risk coverage: {'Comprehensive' if len(brief.tail_risks) >= 3 else 'Adequate'}"
        )

    # ── Grade Assignment ─────────────────────────────────────────────────────

    @classmethod
    def _assign_grade(cls, score: float) -> str:
        for threshold, grade in cls.GRADES:
            if score >= threshold:
                return grade
        return "D"

    # ── Strength / Improvement Identification ────────────────────────────────

    def _identify_strengths(self, sq: SummaryQuality) -> list[str]:
        strengths = []
        for d in sq.dimension_details:
            if d.score >= 90:
                strengths.append(f"{d.name}: {d.score:.0f}/100 — exceptional")
            elif d.score >= 80:
                strengths.append(f"{d.name}: {d.score:.0f}/100 — strong")
        if not strengths:
            strengths.append("All dimensions at baseline or above")
        return strengths

    def _identify_improvements(self, sq: SummaryQuality) -> list[str]:
        improvements = []
        for d in sq.dimension_details:
            if d.score < 70:
                improvements.append(f"{d.name} ({d.score:.0f}/100): {d.rationale[:100]}")
        if not improvements:
            improvements.append("All dimensions above threshold — maintain quality")
        return improvements
