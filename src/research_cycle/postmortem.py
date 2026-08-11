"""Postmortem — post-cycle analysis of thesis outcomes (Milestone D, D6.2).

Analyzes why a thesis was validated or invalidated:
    1. Trace transmission chain failures
    2. Assess framework appropriateness
    3. Extract learning for future cycles
    4. Suggest framework/principle updates

This is the retrospective step that closes the research loop.
"""

from __future__ import annotations

from src.schemas.research_thesis import ResearchThesis, ThesisOutcome
from src.research_cycle.research_memory import PostmortemReport
from src.shared.logging import get_logger

logger = get_logger(__name__)


class Postmortem:
    """Analyzes thesis outcomes to extract learning.

    The postmortem is run AFTER market data confirms or refutes a thesis.
    It answers: "What happened, and what should we learn?"
    """

    # Known transmission breakage categories
    TRANSMISSION_BREAK_CATEGORIES = {
        "policy_misread": "Central bank policy direction was misread",
        "transmission_blocked": "Monetary transmission mechanism was blocked",
        "credit_channel_failed": "Credit channel did not transmit as expected",
        "currency_interference": "FX movements neutralized domestic policy",
        "external_shock": "External event overrode the macro thesis",
        "timing_error": "Direction was correct but timing was wrong",
        "magnitude_error": "Direction was correct but magnitude different",
        "regime_shift": "Macro regime changed mid-window",
        "correlation_breakdown": "Expected asset correlations broke down",
        "framework_wrong": "The framework itself was inappropriate for the regime",
    }

    def __init__(self):
        self._reports: list[PostmortemReport] = []

    # ── Main Entry ──────────────────────────────────────────────────────

    def analyze(
        self,
        thesis: ResearchThesis,
        outcome: ThesisOutcome,
        diagnosis_notes: str = "",
        transmission_findings: list[str] | None = None,
    ) -> PostmortemReport:
        """Analyze a thesis outcome and produce a postmortem report.

        Args:
            thesis: The thesis that was tested
            outcome: The determined outcome
            diagnosis_notes: Notes from the diagnosis engine
            transmission_findings: Any transmission chain findings from research

        Returns:
            PostmortemReport with root cause and learning
        """
        report_id = f"pm-{thesis.thesis_id}"

        if outcome.verified:
            report = self._analyze_success(thesis, outcome, diagnosis_notes, report_id)
        else:
            report = self._analyze_failure(
                thesis, outcome, diagnosis_notes,
                transmission_findings or [], report_id,
            )

        self._reports.append(report)
        logger.info(
            "Postmortem %s: %s → %s",
            report_id,
            "VALIDATED" if report.thesis_validated else "INVALIDATED",
            report.root_cause[:80],
        )
        return report

    # ── Analysis ────────────────────────────────────────────────────────

    def _analyze_success(
        self,
        thesis: ResearchThesis,
        outcome: ThesisOutcome,
        diagnosis_notes: str,
        report_id: str,
    ) -> PostmortemReport:
        """Analyze a validated thesis — what went right?"""
        transmission_ok = True
        problems = []

        # Check if transmission chain held
        for i, link in enumerate(thesis.transmission_chain):
            if self._link_possibly_broken(link, outcome):
                problems.append(link)
                transmission_ok = False

        if transmission_ok:
            root_cause = (
                "Transmission mechanism operated as expected. "
                "Framework was appropriate for the regime."
            )
            learning = (
                f"The transmission chain from {thesis.transmission_chain[0] if thesis.transmission_chain else 'regime'} "
                f"to outcome was confirmed. Framework principles should be strengthened."
            )
        else:
            root_cause = (
                f"Partial validation: {len(problems)} transmission links did not verify, "
                f"but overall outcome aligned with thesis direction."
            )
            learning = "Framework partially correct; review links that did not verify."

        suggested = [
            "Increase confidence in framework used" if transmission_ok
            else "Review specific transmission links",
            "Record this regime as a successful framework application",
        ]

        return PostmortemReport(
            report_id=report_id,
            thesis_id=thesis.thesis_id,
            thesis_validated=True,
            root_cause=root_cause,
            transmission_problems=problems,
            framework_assessment="Framework was appropriate for this regime.",
            learning=learning,
            suggested_actions=suggested,
            diagnosis_notes=diagnosis_notes,
        )

    def _analyze_failure(
        self,
        thesis: ResearchThesis,
        outcome: ThesisOutcome,
        diagnosis_notes: str,
        transmission_findings: list[str],
        report_id: str,
    ) -> PostmortemReport:
        """Analyze an invalidated thesis — what went wrong?"""
        problems = list(transmission_findings)
        root_cause_category = self._classify_failure(thesis, outcome, diagnosis_notes)
        root_cause = self.TRANSMISSION_BREAK_CATEGORIES.get(
            root_cause_category,
            "Thesis invalidated: outcome did not align with expected mechanism.",
        )

        # Add specifics
        if outcome.invalidation_triggered:
            root_cause += f" Triggered by: {outcome.invalidation_triggered}."

        # Determine learning
        learnings = {
            "policy_misread": "Reassess policy signal interpretation. The framework's policy read was incorrect.",
            "transmission_blocked": "Monetary transmission is not functioning as expected in current environment. Update transmission priors.",
            "credit_channel_failed": "Credit channel assumptions need revision. Financial conditions indices may be misleading.",
            "currency_interference": "Add FX channel to transmission analysis. Currency moves can neutralize domestic policy.",
            "external_shock": "Recognize that external events can override macro frameworks. Add geopolitical tail-risk to invalidation.",
            "regime_shift": "Regime detection may have been wrong. Review regime classification criteria.",
            "correlation_breakdown": "Asset correlations are regime-dependent. Framework should account for correlation shifts.",
            "framework_wrong": "The core framework was wrong for this regime. Consider framework retirement or narrowing scope.",
            "timing_error": "Direction was right but timing was off. Expected window should be widened.",
            "magnitude_error": "Direction correct but magnitude different. Confidence calibration needs adjustment.",
        }
        learning = learnings.get(root_cause_category, "Review thesis construction methodology.")

        # Suggested actions
        suggested = self._suggest_actions(root_cause_category, thesis)

        return PostmortemReport(
            report_id=report_id,
            thesis_id=thesis.thesis_id,
            thesis_validated=False,
            root_cause=root_cause,
            transmission_problems=problems,
            framework_assessment=self._assess_framework(thesis, root_cause_category),
            learning=learning,
            suggested_actions=suggested,
            diagnosis_notes=diagnosis_notes,
        )

    def _classify_failure(
        self,
        thesis: ResearchThesis,
        outcome: ThesisOutcome,
        diagnosis_notes: str,
    ) -> str:
        """Classify the type of thesis failure."""
        notes = (diagnosis_notes or "").lower()
        triggered = (outcome.invalidation_triggered or "").lower()
        belief = thesis.core_belief.lower()

        # Check diagnosis notes for known patterns
        # NOTE: "credit" must be checked BEFORE "transmission" because
        # "Credit transmission broke" matches both; we want the more
        # specific "credit_channel_failed".
        if "credit" in notes or "spread" in notes:
            return "credit_channel_failed"
        if "transmission" in notes or "chain" in notes:
            return "transmission_blocked"
        if "fx" in notes or "currency" in notes or "dollar" in notes:
            return "currency_interference"
        if "shock" in notes or "event" in notes or "geopolitical" in notes:
            return "external_shock"
        if "regime" in notes or "shift" in notes or "transition" in notes:
            return "regime_shift"
        if "correlation" in notes or "correlation" in triggered:
            return "correlation_breakdown"
        if "rate" in triggered or "fed" in triggered or "policy" in triggered:
            return "policy_misread"
        if "below" in triggered or "above" in triggered:
            # Price-level triggers suggest magnitude or timing
            return "magnitude_error"

        # Check thesis construction
        if not thesis.transmission_chain:
            return "framework_wrong"
        if len(thesis.evidence) < 3:
            return "framework_wrong"  # Insufficient evidence = framework issue

        return "framework_wrong"  # Default: framework was not right for this

    @staticmethod
    def _assess_framework(thesis: ResearchThesis, failure_category: str) -> str:
        """Assess whether the framework was appropriate."""
        if failure_category == "framework_wrong":
            return (
                f"Framework {thesis.framework_used} was inappropriate for this regime. "
                "Consider retiring or narrowing its scope to specific regime types."
            )
        elif failure_category in ("external_shock", "regime_shift"):
            return (
                f"Framework {thesis.framework_used} may be valid but was overridden "
                "by exogenous factors. Framework should include tail-risk conditions."
            )
        else:
            return (
                f"Framework {thesis.framework_used} has issues in transmission reasoning. "
                "Review and potentially adjust transmission chain modeling."
            )

    @staticmethod
    def _suggest_actions(failure_category: str, thesis: ResearchThesis) -> list[str]:
        """Suggest post-cycle actions based on failure type."""
        common_actions = {
            "policy_misread": [
                "Review policy signal interpretation methodology",
                "Add policy divergence indicators to signal set",
            ],
            "transmission_blocked": [
                "Update transmission priors for current environment",
                "Add financial conditions check to transmission chain",
            ],
            "credit_channel_failed": [
                "Add HYG/IG spread to invalidation conditions",
                "Review credit impulse measurement",
            ],
            "currency_interference": [
                "Add DXY trend to macro snapshot",
                "Include FX pass-through in transmission chain",
            ],
            "external_shock": [
                "Add geopolitical risk premium to confidence adjustment",
                "Define tail-risk override conditions",
            ],
            "regime_shift": [
                "Increase regime detection frequency",
                "Reduce expected window for high-volatility regimes",
            ],
            "correlation_breakdown": [
                "Review cross-asset correlation assumptions",
                "Add correlation regime flag to thesis confidence",
            ],
            "framework_wrong": [
                "Flag framework for retirement review",
                "Search for alternative framework with better regime match",
            ],
            "timing_error": [
                "Widen expected window by 2x",
                "Add timing indicators to evidence set",
            ],
            "magnitude_error": [
                "Calibrate confidence more conservatively",
                "Add magnitude-specific indicators",
            ],
        }
        actions = common_actions.get(failure_category, ["Review thesis construction"])
        actions.append(f"Record in research memory for future cycle comparison")
        return actions

    @staticmethod
    def _link_possibly_broken(link: str, outcome: ThesisOutcome) -> bool:
        """Heuristic: check if a specific transmission link may have broken."""
        link_lower = link.lower()
        if outcome.invalidation_triggered:
            triggered_lower = outcome.invalidation_triggered.lower()
            # If the trigger directly contradicts a link, it's broken
            if any(word in triggered_lower for word in link_lower.split()[:3]):
                return True
        return False

    # ── Query ───────────────────────────────────────────────────────────

    def get_reports(self) -> list[PostmortemReport]:
        return list(self._reports)

    def get_last_report(self) -> PostmortemReport | None:
        return self._reports[-1] if self._reports else None

    @property
    def report_count(self) -> int:
        return len(self._reports)

    @property
    def success_rate(self) -> float:
        if not self._reports:
            return 0.0
        return sum(1 for r in self._reports if r.thesis_validated) / len(self._reports)

    def summary(self) -> str:
        if not self._reports:
            return "Postmortem: No analyses completed yet."
        last = self._reports[-1]
        return (
            f"Postmortem: {self.report_count} analyses, "
            f"{self.success_rate:.0%} success rate.\n"
            f"  Last: {last.describe()}"
        )
