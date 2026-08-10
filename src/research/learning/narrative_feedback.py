"""V5.4 Narrative Feedback — Learn from narrative failures.

When the macro story is wrong, the entire research output is compromised.
Narrative feedback diagnoses:
    - Was the narrative too simplistic?
    - Did we anchor on the wrong narrative?
    - Were alternative narratives adequately considered?
    - Did the narrative fail to adapt to new data?
"""

from __future__ import annotations

from typing import Optional

from src.research.learning.schemas import (
    LearningEvent,
    FailureDiagnosis,
    ImprovementAction,
    RootCauseCategory,
)


class NarrativeFeedback:
    """Analyze narrative failures and generate improvements."""

    NARRATIVE_HEALTH_CHECKS = [
        "coherence",           # Internal logical consistency
        "evidence_support",     # Backed by data
        "adaptability",        # Can it handle new data?
        "counter_coverage",    # Does it account for counter-narratives?
        "timeliness",          # Is it still relevant?
    ]

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def analyze(
        self,
        diagnosis: FailureDiagnosis,
        original_narrative: str = "",
        actual_narrative: str = "",
    ) -> ImprovementAction | None:
        """Generate narrative improvement from a failure diagnosis.

        Only relevant if the root cause is narrative-related.

        Args:
            diagnosis: Failure diagnosis from ReasoningFeedbackV5
            original_narrative: The narrative that was used
            actual_narrative: The narrative that actually played out

        Returns:
            ImprovementAction or None if not narrative-related
        """
        if RootCauseCategory.NARRATIVE_WRONG not in diagnosis.root_causes:
            return None

        action = ImprovementAction(
            diagnosis_id=diagnosis.diagnosis_id,
            target="narrative",
            action_type="modify_narrative_framework",
        )

        # What went wrong with the narrative?
        issues = self._diagnose_narrative_issues(
            original_narrative, actual_narrative
        )

        action.description = (
            f"Narrative adjustment: {issues['primary_issue']}. "
            f"Original: '{original_narrative[:80]}...' "
            f"→ Adjusted: '{issues['suggested_fix'][:80]}...'"
        )
        action.before_value = original_narrative[:200]
        action.after_value = issues['suggested_fix'][:200]
        action.expected_improvement = (
            f"Improve narrative accuracy by incorporating {issues['primary_issue']} check"
        )

        return action

    def evaluate_narrative_health(
        self,
        narrative: str,
        evidence_support: float = 0.5,
    ) -> dict:
        """Evaluate the health of a narrative."""
        health = {
            "coherence": self._check_coherence(narrative),
            "evidence_support": evidence_support,
            "adaptability": self._check_adaptability(narrative),
            "counter_coverage": self._check_counter_coverage(narrative),
            "timeliness": 0.5,  # Default, needs external data
        }

        health["overall"] = sum(health.values()) / len(health)
        return health

    def _diagnose_narrative_issues(
        self,
        original: str,
        actual: str,
    ) -> dict:
        """Diagnose what was wrong with the original narrative."""
        issues = {
            "primary_issue": "Narrative did not account for actual mechanism",
            "suggested_fix": "",
            "checks_to_add": [],
        }

        # Oversimplification
        if len(original.split()) < 20 and len(actual.split()) > 20:
            issues["primary_issue"] = "Narrative was oversimplified"
            issues["checks_to_add"].append("complexity_check")
            issues["suggested_fix"] = (
                "Expand narrative to include multiple interacting mechanisms, "
                "not just a single causal chain. Macro outcomes are rarely "
                "driven by one factor."
            )

        # Missing mechanism
        if actual and original:
            issues["suggested_fix"] = (
                f"Incorporate '{actual[:80]}...' as a primary mechanism. "
                "Add mechanism diversity check before finalizing narratives."
            )

        # Anchoring bias
        if self._likely_anchoring(original):
            issues["primary_issue"] = "Possible anchoring on a popular narrative"
            issues["checks_to_add"].append("consensus_bias_check")
            issues["suggested_fix"] = (
                "Explicitly compare narrative to consensus and identify "
                "where and why it diverges before adopting."
            )

        return issues

    def _check_coherence(self, narrative: str) -> float:
        """Check narrative internal coherence."""
        if not narrative.strip():
            return 0.0

        words = narrative.lower().split()

        # Check for contradictory pairs
        contradictions = 0
        contradiction_pairs = [
            (["rising", "increase", "higher"], ["falling", "decrease", "lower"]),
            (["strong", "robust", "solid"], ["weak", "fragile", "soft"]),
            (["hawkish", "tighten"], ["dovish", "easing"]),
        ]

        for pos, neg in contradiction_pairs:
            has_pos = any(w in words for w in pos)
            has_neg = any(w in words for w in neg)
            if has_pos and has_neg:
                contradictions += 1

        if contradictions == 0:
            return 0.9
        elif contradictions == 1:
            return 0.6
        return 0.3

    def _check_adaptability(self, narrative: str) -> float:
        """Check if narrative can adapt to new data."""
        adaptability_phrases = [
            "depends on", "if...then", "conditional on",
            "unless", "provided that", "as long as",
            "could change if", "subject to",
        ]

        count = sum(
            1 for phrase in adaptability_phrases
            if phrase in narrative.lower()
        )

        if count >= 3:
            return 0.9
        elif count >= 1:
            return 0.6
        return 0.3

    def _check_counter_coverage(self, narrative: str) -> float:
        """Check if narrative acknowledges counter-views."""
        counter_phrases = [
            "however", "on the other hand", "alternatively",
            "risk is that", "counter", "skeptics",
            "could be wrong if", "the bear case",
        ]

        count = sum(
            1 for phrase in counter_phrases
            if phrase in narrative.lower()
        )

        if count >= 4:
            return 0.9
        elif count >= 2:
            return 0.65
        elif count >= 1:
            return 0.4
        return 0.1

    def _likely_anchoring(self, narrative: str) -> bool:
        """Check if narrative shows signs of anchoring bias."""
        anchoring_phrases = [
            "everyone agrees", "consensus is", "widely expected",
            "clearly", "obviously", "without doubt",
        ]
        return any(phrase in narrative.lower() for phrase in anchoring_phrases)
