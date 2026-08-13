"""V5.4 Trade Feedback — Learn from trade outcomes.

Not just P&L. Diagnose WHY the trade failed:
    - Right macro view, wrong expression?
    - Wrong entry timing?
    - Stop too tight?
    - Position size mismatch with conviction?
    - Correlation breakdown?
"""

from __future__ import annotations

from src.research.learning.schemas import (
    FailureDiagnosis,
    ImprovementAction,
    LearningEvent,
    RootCauseCategory,
)


class TradeFeedback:
    """Analyze trade failures and generate execution improvements."""

    TRADE_FAILURE_TYPES = {
        "view_correct_expression_wrong": (
            "Macro view was directionally correct but the trade expression "
            "(instrument choice, structure) was wrong."
        ),
        "timing_error": ("Entry was too early/late. The trade was right but timing caused loss."),
        "stop_too_tight": ("Stop loss was triggered by noise before the trade worked."),
        "sizing_error": ("Position size was inappropriate for the conviction level."),
        "correlation_breakdown": (
            "Assumed correlation between instrument and macro driver broke down."
        ),
        "liquidity_event": ("Liquidity dried up, causing execution at unfavorable prices."),
        "view_wrong": ("The underlying macro view was wrong — no trade expression could fix this."),
    }

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def analyze(
        self,
        event: LearningEvent,
        diagnosis: FailureDiagnosis,
        trade_details: dict | None = None,
    ) -> ImprovementAction | None:
        """Generate trade rule improvements from a failure.

        Args:
            event: The learning event
            diagnosis: Root cause diagnosis
            trade_details: Trade execution details (entry, stop, size, etc.)

        Returns:
            ImprovementAction or None
        """
        trade_details = trade_details or {}

        action = ImprovementAction(
            diagnosis_id=diagnosis.diagnosis_id,
            target="trade_execution",
            action_type="modify_trade_rule",
        )

        # 1. Determine trade failure type
        failure_type = self._classify_failure(event, diagnosis, trade_details)
        failure_desc = self.TRADE_FAILURE_TYPES.get(
            failure_type, self.TRADE_FAILURE_TYPES["view_wrong"]
        )

        # 2. Generate specific action
        if failure_type == "view_correct_expression_wrong":
            action.action_type = "modify_instrument_selection"
            action.description = (
                f"Trade expression mismatch: {failure_desc}. "
                "Consider simpler, more direct expressions of the macro view."
            )
            action.expected_improvement = "Better instrument-idea alignment → fewer false negatives"

        elif failure_type == "timing_error":
            action.action_type = "add_entry_rule"
            action.description = (
                f"Timing error: {failure_desc}. "
                "Add confirmation signal before entry (e.g., wait for catalyst)."
            )
            action.before_value = "Enter immediately on view"
            action.after_value = "Enter after catalyst/confirmation signal"
            action.expected_improvement = "Reduce premature entries, improve win rate"

        elif failure_type == "stop_too_tight":
            action.action_type = "widen_stop_rule"
            action.description = (
                f"Stop too tight: {failure_desc}. "
                "Widen stops or use time-based stops instead of price-based."
            )
            action.expected_improvement = "Reduce stop-outs on noise, improve holding power"

        elif failure_type == "sizing_error":
            conviction = event.original_conviction
            suggested_size = "1-2%" if conviction > 0.7 else "0.5-1%"
            action.action_type = "adjust_sizing_rule"
            action.description = (
                f"Sizing error: {failure_desc}. "
                f"Suggested position size: {suggested_size} risk per idea."
            )
            action.expected_improvement = "Better risk-reward alignment with conviction"

        elif failure_type == "correlation_breakdown":
            action.action_type = "add_correlation_check"
            action.description = (
                f"Correlation breakdown: {failure_desc}. "
                "Add correlation stability check before trade entry."
            )
            action.expected_improvement = "Identify unstable correlations before they hurt"

        elif failure_type == "liquidity_event":
            action.action_type = "add_liquidity_filter"
            action.description = (
                f"Liquidity issue: {failure_desc}. "
                "Add liquidity filter: avoid trading in illiquid conditions."
            )
            action.expected_improvement = "Avoid execution during liquidity gaps"

        else:  # view_wrong or unknown
            action.description = (
                f"Underlying view was wrong: {failure_desc}. "
                "Root cause is in the research process, not trade execution."
            )
            action.action_type = "no_trade_rule_change"
            action.expected_improvement = "None — fix the research, not the execution"

        return action

    def _classify_failure(
        self,
        event: LearningEvent,
        diagnosis: FailureDiagnosis,
        trade_details: dict,
    ) -> str:
        """Classify the type of trade failure."""
        # If the view was directionally correct
        if event.was_directionally_correct:
            # But still lost money → expression or execution issue
            if trade_details.get("stop_triggered"):
                return "stop_too_tight"
            if trade_details.get("correlation_broke"):
                return "correlation_breakdown"
            if trade_details.get("liquidity_issue"):
                return "liquidity_event"
            if trade_details.get("entry_too_early"):
                return "timing_error"
            return "view_correct_expression_wrong"

        # View was wrong
        if diagnosis.primary_cause in (
            RootCauseCategory.EVIDENCE_WRONG,
            RootCauseCategory.NARRATIVE_WRONG,
            RootCauseCategory.REGIME_WRONG,
        ):
            return "view_wrong"

        if diagnosis.primary_cause == RootCauseCategory.CONVICTION_ERROR:
            return "sizing_error"

        return "view_wrong"

    def generate_trade_rules_update(
        self,
        actions: list[ImprovementAction],
    ) -> dict:
        """Generate updated trade rules based on accumulated learning."""
        rules = {
            "entry_rules": [],
            "sizing_rules": [],
            "stop_rules": [],
            "instrument_rules": [],
            "filter_rules": [],
        }

        for action in actions:
            if "entry" in action.action_type:
                rules["entry_rules"].append(action.description)
            elif "sizing" in action.action_type:
                rules["sizing_rules"].append(action.description)
            elif "stop" in action.action_type:
                rules["stop_rules"].append(action.description)
            elif "instrument" in action.action_type:
                rules["instrument_rules"].append(action.description)
            elif "filter" in action.action_type or "liquidity" in action.action_type:
                rules["filter_rules"].append(action.description)

        return rules
