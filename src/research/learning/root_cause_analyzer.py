"""V5.4 Root Cause Analyzer — Deep analysis of why predictions/trades failed.

Goes beyond surface-level "prediction wrong":
    1. Traces the full reasoning chain
    2. Identifies where in the chain the error occurred
    3. Distinguishes between skill failures and luck
    4. Tracks recurring error patterns over time
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from src.research.learning.schemas import (
    LearningEvent,
    FailureDiagnosis,
    RootCauseCategory,
    LearningLog,
)


class RootCauseAnalyzer:
    """Deep root cause analysis of prediction and reasoning failures."""

    ERROR_PATTERNS = {
        "overconfidence": (
            'Agent consistently overestimates probability of favorable outcomes'
        ),
        "recency_bias": (
            'Agent overweights recent data points relative to longer-term trends'
        ),
        "narrative_lock": (
            'Agent fails to update narrative when contrary evidence emerges'
        ),
        "counter_neglect": (
            'Agent systematically underestimates or ignores counterarguments'
        ),
        "regime_blindness": (
            'Agent fails to detect or adapt to regime changes'
        ),
        "horizon_mismatch": (
            'Agent uses wrong time horizon for the prediction type'
        ),
        "correlation_assumption": (
            'Agent assumes stable correlations that break under stress'
        ),
    }

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._pattern_history: dict[str, list[str]] = defaultdict(list)

    def analyze(
        self,
        events: list[LearningEvent],
        diagnoses: list[FailureDiagnosis],
        log: LearningLog | None = None,
    ) -> dict:
        """Analyze multiple events to find recurring error patterns.

        Args:
            events: List of learning events
            diagnoses: Corresponding failure diagnoses
            log: Cumulative learning log (optional)

        Returns:
            Analysis report with patterns and recommendations
        """
        report = {
            "total_events": len(events),
            "total_failures": sum(1 for e in events if not e.was_correct),
            "accuracy": 0.0,
            "root_cause_distribution": {},
            "recurring_patterns": [],
            "improving_areas": [],
            "worsening_areas": [],
            "systemic_issues": [],
            "recommendations": [],
        }

        if not events:
            return report

        # Calculate accuracy
        correct = sum(1 for e in events if e.was_correct)
        report["accuracy"] = correct / len(events)

        # Root cause distribution
        cause_counts = defaultdict(int)
        for d in diagnoses:
            cause_counts[d.primary_cause.value] += 1
        report["root_cause_distribution"] = dict(cause_counts)

        # Find recurring patterns
        report["recurring_patterns"] = self._find_patterns(diagnoses)

        # Systemic issues
        report["systemic_issues"] = self._find_systemic_issues(
            report["root_cause_distribution"], report["recurring_patterns"]
        )

        # Recommendations
        report["recommendations"] = self._generate_recommendations(report)

        # Track trend (if log provided)
        if log and log.accuracy_trend:
            report["accuracy_trend"] = log.accuracy_trend
            if len(log.accuracy_trend) >= 2:
                delta = log.accuracy_trend[-1] - log.accuracy_trend[0]
                if delta > 0.05:
                    report["trend"] = "improving"
                elif delta < -0.05:
                    report["trend"] = "worsening"
                else:
                    report["trend"] = "stable"

        return report

    def _find_patterns(self, diagnoses: list[FailureDiagnosis]) -> list[dict]:
        """Find recurring error patterns across multiple diagnoses."""
        patterns = []

        # Check overconfidence (high original probability + wrong)
        overconfident = [
            d for d in diagnoses
            if d.primary_cause in (
                RootCauseCategory.COUNTER_MISSED,
                RootCauseCategory.NARRATIVE_WRONG,
            )
        ]
        if len(overconfident) >= 3:
            patterns.append({
                "pattern": "overconfidence",
                "description": self.ERROR_PATTERNS["overconfidence"],
                "count": len(overconfident),
                "severity": "high" if len(overconfident) > 5 else "medium",
            })

        # Check narrative lock (multiple narrative failures)
        narrative_failures = [
            d for d in diagnoses
            if d.primary_cause == RootCauseCategory.NARRATIVE_WRONG
        ]
        if len(narrative_failures) >= 3:
            patterns.append({
                "pattern": "narrative_lock",
                "description": self.ERROR_PATTERNS["narrative_lock"],
                "count": len(narrative_failures),
                "severity": "high",
            })

        # Check counter neglect
        counter_missed = [
            d for d in diagnoses
            if d.primary_cause == RootCauseCategory.COUNTER_MISSED
        ]
        if len(counter_missed) >= 2:
            patterns.append({
                "pattern": "counter_neglect",
                "description": self.ERROR_PATTERNS["counter_neglect"],
                "count": len(counter_missed),
                "severity": "high",
            })

        # Check regime blindness
        regime_wrong = [
            d for d in diagnoses
            if d.primary_cause == RootCauseCategory.REGIME_WRONG
        ]
        if len(regime_wrong) >= 2:
            patterns.append({
                "pattern": "regime_blindness",
                "description": self.ERROR_PATTERNS["regime_blindness"],
                "count": len(regime_wrong),
                "severity": "high" if len(regime_wrong) > 3 else "medium",
            })

        return patterns

    def _find_systemic_issues(
        self,
        cause_dist: dict[str, int],
        patterns: list[dict],
    ) -> list[str]:
        """Identify systemic (not one-off) issues."""
        issues = []

        total = sum(cause_dist.values())
        if total == 0:
            return issues

        # If > 30% of failures are from one cause → systemic
        for cause, count in cause_dist.items():
            if count / total > 0.3:
                issues.append(
                    f"Systemic issue: {cause} accounts for {count/total:.0%} of failures"
                )

        # If high-severity patterns exist
        for pattern in patterns:
            if pattern["severity"] == "high":
                issues.append(
                    f"Systemic issue: {pattern['pattern']} — {pattern['description']}"
                )

        return issues

    def _generate_recommendations(self, report: dict) -> list[str]:
        """Generate prioritized recommendations."""
        recs = []

        cause_dist = report["root_cause_distribution"]
        total = sum(cause_dist.values())

        if total == 0:
            return ["Insufficient data for recommendations"]

        # Most frequent cause → top priority
        sorted_causes = sorted(cause_dist.items(), key=lambda x: x[1], reverse=True)
        top_cause = sorted_causes[0][0]

        if top_cause == "evidence_wrong":
            recs.append(
                "PRIORITY: Strengthen evidence quality checks. "
                "Add data source verification to pipeline Stage 2."
            )
        elif top_cause == "narrative_wrong":
            recs.append(
                "PRIORITY: Add narrative diversity check. "
                "Require at least 3 competing narratives in Stage 5."
            )
        elif top_cause == "regime_wrong":
            recs.append(
                "PRIORITY: Enhance regime detection. "
                "Use multiple independent regime signals in Stage 3."
            )
        elif top_cause == "counter_missed":
            recs.append(
                "PRIORITY: Mandatory counterargument quota. "
                "Minimum 5 structured counters in Stage 6."
            )

        # General recommendations
        if report["accuracy"] < 0.5:
            recs.append(
                "Accuracy below 50% — fundamental reasoning issues. "
                "Consider complete review of analytical framework."
            )

        return recs
