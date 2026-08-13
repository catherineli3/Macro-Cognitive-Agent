"""V5.4 Learning Orchestrator — Coordinate the full learning cycle.

Manages the complete feedback → diagnosis → improvement cycle:
    1. Collect resolved predictions/trades
    2. For each failure, diagnose root cause
    3. Generate narrative and trade improvements
    4. Track patterns over time
    5. Apply learned improvements to the system

This is the brain that makes the Agent better over time.
"""

from __future__ import annotations

from datetime import datetime

from src.research.learning.narrative_feedback import NarrativeFeedback
from src.research.learning.reasoning_feedback_v5 import ReasoningFeedbackV5
from src.research.learning.root_cause_analyzer import RootCauseAnalyzer
from src.research.learning.schemas import (
    ImprovementAction,
    LearningEvent,
    LearningLog,
)
from src.research.learning.trade_feedback import TradeFeedback


class LearningOrchestrator:
    """Orchestrate the continuous learning cycle.

    Usage:
        orch = LearningOrchestrator()

        # Record a resolved prediction
        event = LearningEvent(
            original_claim="Inflation will moderate to 3% by Q4",
            original_probability=0.7,
            actual_outcome="Inflation remained at 4.5%",
            was_correct=False,
        )
        orch.learn(event, context={"data_revisions": True})

        # Get improvement actions
        actions = orch.get_pending_actions()

        # Apply to system
        orch.apply_actions(actions)

        # Get learning report
        report = orch.get_report()
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}

        # Feedback analyzers
        self.reasoning_feedback = ReasoningFeedbackV5(config)
        self.narrative_feedback = NarrativeFeedback(config)
        self.trade_feedback = TradeFeedback(config)
        self.root_cause_analyzer = RootCauseAnalyzer(config)

        # State
        self.log = LearningLog()
        self._pending_actions: list[ImprovementAction] = []

    # ── Public Interface ─────────────────────────────────────────────

    def learn(
        self,
        event: LearningEvent,
        context: dict | None = None,
        original_narrative: str = "",
        actual_narrative: str = "",
        trade_details: dict | None = None,
    ) -> list[ImprovementAction]:
        """Learn from a resolved event.

        Full cycle:
            1. Diagnose root cause
            2. Generate narrative feedback (if applicable)
            3. Generate trade feedback (if applicable)
            4. Track in log
            5. Return improvement actions

        Args:
            event: The learning event (prediction/trade outcome)
            context: Additional diagnostic context
            original_narrative: Narrative used in original prediction
            actual_narrative: Narrative that actually played out
            trade_details: Trade execution details

        Returns:
            List of ImprovementAction to apply
        """
        actions = []

        # Step 1: Root cause diagnosis
        diagnosis = self.reasoning_feedback.analyze(event, context)
        self.log.diagnoses.append(diagnosis)

        # Step 2: Narrative feedback
        if original_narrative:
            narrative_action = self.narrative_feedback.analyze(
                diagnosis, original_narrative, actual_narrative
            )
            if narrative_action:
                actions.append(narrative_action)

        # Step 3: Trade feedback
        if trade_details:
            trade_action = self.trade_feedback.analyze(event, diagnosis, trade_details)
            if trade_action:
                actions.append(trade_action)

        # Step 4: Update log
        self.log.events.append(event)
        self.log.total_predictions += 1
        if event.was_correct:
            self.log.correct_predictions += 1

        self._pending_actions.extend(actions)

        # Step 5: Update root cause distribution
        for cause in diagnosis.root_causes:
            self.log.root_cause_distribution[cause.value] = (
                self.log.root_cause_distribution.get(cause.value, 0) + 1
            )

        return actions

    def learn_batch(
        self,
        events_with_context: list[tuple[LearningEvent, dict | None]],
    ) -> list[ImprovementAction]:
        """Learn from multiple events at once."""
        all_actions = []
        for event, context in events_with_context:
            actions = self.learn(event, context=context)
            all_actions.extend(actions)
        return all_actions

    def get_pending_actions(self) -> list[ImprovementAction]:
        """Get all pending improvement actions."""
        return list(self._pending_actions)

    def apply_actions(self, actions: list[ImprovementAction]) -> dict:
        """Apply improvement actions to the system.

        Returns summary of what was applied.
        """
        applied = {
            "applied_count": 0,
            "by_target": {},
            "details": [],
        }

        for action in actions:
            action.applied = True
            action.applied_at = datetime.now().isoformat()
            applied["applied_count"] += 1
            applied["by_target"][action.target] = applied["by_target"].get(action.target, 0) + 1
            applied["details"].append(
                {
                    "action_id": action.action_id,
                    "target": action.target,
                    "type": action.action_type,
                    "description": action.description[:100],
                }
            )

        # Add to log
        self.log.actions.extend(actions)
        self._pending_actions = [
            a
            for a in self._pending_actions
            if a.action_id not in {act.action_id for act in actions}
        ]

        return applied

    def get_report(self) -> dict:
        """Get comprehensive learning report."""
        # Update log statistics
        self.log.total_predictions = len(self.log.events)
        self.log.correct_predictions = sum(1 for e in self.log.events if e.was_correct)

        # Track accuracy trend
        if self.log.events:
            current_accuracy = self.log.accuracy_rate()
            self.log.accuracy_trend.append(current_accuracy)

            if not self.log.baseline_accuracy:
                self.log.baseline_accuracy = current_accuracy
            self.log.current_accuracy = current_accuracy

        # Root cause analysis
        pattern_analysis = self.root_cause_analyzer.analyze(
            self.log.events[-20:],  # Last 20 events
            self.log.diagnoses[-20:],
            self.log,
        )

        return {
            "log_summary": self.log.summary(),
            "total_events": len(self.log.events),
            "total_diagnoses": len(self.log.diagnoses),
            "total_actions": len(self.log.actions),
            "actions_applied": sum(1 for a in self.log.actions if a.applied),
            "root_cause_distribution": dict(self.log.root_cause_distribution),
            "accuracy": self.log.accuracy_rate(),
            "accuracy_trend": list(self.log.accuracy_trend[-10:]),
            "improvement_delta": self.log.improvement_delta(),
            "patterns": pattern_analysis.get("recurring_patterns", []),
            "systemic_issues": pattern_analysis.get("systemic_issues", []),
            "recommendations": pattern_analysis.get("recommendations", []),
        }

    def print_report(self):
        """Print a human-readable learning report."""
        report = self.get_report()

        lines = []
        lines.append("=" * 60)
        lines.append("CONTINUOUS LEARNING REPORT")
        lines.append("=" * 60)
        lines.append(f"Total predictions tracked: {report['total_events']}")
        lines.append(f"Current accuracy: {report['accuracy']:.1%}")
        lines.append(f"Improvement delta: {report['improvement_delta']:+.1%}")
        lines.append(f"Actions applied: {report['actions_applied']}")
        lines.append("")

        if report["root_cause_distribution"]:
            lines.append("Root Cause Distribution:")
            for cause, count in sorted(
                report["root_cause_distribution"].items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                lines.append(f"  {cause}: {count}")
            lines.append("")

        if report["systemic_issues"]:
            lines.append("Systemic Issues:")
            for issue in report["systemic_issues"]:
                lines.append(f"  ! {issue}")
            lines.append("")

        if report["recommendations"]:
            lines.append("Recommendations:")
            for rec in report["recommendations"]:
                lines.append(f"  > {rec}")

        lines.append("=" * 60)
        print("\n".join(lines))

    # ── Status ────────────────────────────────────────────────────────

    def reset(self):
        """Reset all learning state."""
        self.log = LearningLog()
        self._pending_actions.clear()
