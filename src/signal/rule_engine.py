"""Rule Engine — Loads and evaluates configurable signal rules.

Architecture:
    The Rule Engine is designed to accommodate multiple rule types
    (Threshold, Trend, Momentum, Spread, Correlation, Regime).
    Sprint 2 implements Threshold only. All other types are reserved
    for future Sprints with no refactoring required.

    Rules are defined in configs/signal_rules.yaml — NO hardcoded
    thresholds in Python code.
"""

from pydantic import BaseModel, Field

from src.domain.signal import RuleType
from src.schemas.macro_data import MacroDataSchema
from src.shared.config import load_yaml
from src.shared.exceptions import SignalGenerationError
from src.shared.logging import get_logger

logger = get_logger(__name__)

# ── Data structures ───────────────────────────────────────────────────────


class RuleCondition(BaseModel):
    """A single condition within a signal rule."""

    operator: str = Field(..., description="Comparison operator: gt, lt, gte, lte, eq")
    field: str = Field(default="value", description="Field to evaluate")
    threshold: float = Field(..., description="Threshold value")


class SignalRuleDefinition(BaseModel):
    """A parsed signal rule from YAML configuration."""

    rule_id: str
    description: str
    indicator: str
    dimension: str
    type: str  # RuleType value — Sprint 2: "threshold" only
    condition: RuleCondition
    signal_direction: str  # bullish | bearish | neutral
    signal_strength: str  # strong | moderate | weak
    signal_confidence: float = 0.5
    interpretation: str


class RuleEvaluation(BaseModel):
    """Result of evaluating a single rule against current data."""

    rule: SignalRuleDefinition
    triggered: bool = False
    input_value: float | None = None
    condition_str: str = ""


# ── Rule Engine ───────────────────────────────────────────────────────────


class RuleEngine:
    """Evaluates signal rules against macro data.

    Responsibilities:
        - Load rules from YAML configuration
        - Evaluate rules against data (Sprint 2: threshold rules only)
        - Return triggered rules as RuleEvaluation results

    Non-responsibilities:
        - Does NOT generate signals (that's SignalGenerator's job)
        - Does NOT access the database
        - Does NOT perform analysis
    """

    def __init__(self, rules_path: str = "signal_rules.yaml") -> None:
        """Initialize the rule engine by loading rules from config.

        Args:
            rules_path: Filename in configs/ directory. Default: signal_rules.yaml.
        """
        self._rules: list[SignalRuleDefinition] = self._load_rules(rules_path)
        logger.info(
            "rule_engine_initialized rule_count=%d path=%s",
            len(self._rules),
            rules_path,
        )

    @property
    def rules(self) -> list[SignalRuleDefinition]:
        """Return all loaded rules (read-only)."""
        return list(self._rules)

    def get_rules_for_indicator(self, indicator: str) -> list[SignalRuleDefinition]:
        """Return rules applicable to a specific indicator."""
        return [r for r in self._rules if r.indicator == indicator]

    # ── Evaluation ─────────────────────────────────────────────────

    def evaluate(
        self,
        indicator: str,
        current: MacroDataSchema,
        history: list[MacroDataSchema],
    ) -> list[RuleEvaluation]:
        """Evaluate all applicable rules for an indicator.

        Args:
            indicator: The indicator symbol.
            current: The current (latest) observation.
            history: Historical observations (for context, used by future rule types).

        Returns:
            List of RuleEvaluation results (triggered + non-triggered).

        Raises:
            SignalGenerationError: If rule evaluation encounters an error.
        """
        applicable = self.get_rules_for_indicator(indicator)
        if not applicable:
            logger.debug("no_rules_for_indicator indicator=%s", indicator)
            return []

        results: list[RuleEvaluation] = []
        for rule in applicable:
            try:
                result = self._evaluate_one(rule, current, history)
                results.append(result)
            except Exception as exc:
                logger.warning(
                    "rule_evaluation_error rule_id=%s error=%s",
                    rule.rule_id,
                    exc,
                )
                raise SignalGenerationError(
                    f"Rule evaluation failed for {rule.rule_id}: {exc}",
                    details={"rule_id": rule.rule_id, "indicator": indicator},
                ) from exc

        triggered = sum(1 for r in results if r.triggered)
        logger.debug(
            "rule_evaluation_done indicator=%s total=%d triggered=%d",
            indicator,
            len(results),
            triggered,
        )
        return results

    def _evaluate_one(
        self,
        rule: SignalRuleDefinition,
        current: MacroDataSchema,
        history: list[MacroDataSchema],
    ) -> RuleEvaluation:
        """Evaluate a single rule against current data.

        Dispatches to the appropriate evaluator based on rule type.
        Sprint 2: threshold only.
        Future: trend, momentum, spread, correlation, regime.
        """
        supported = {RuleType.THRESHOLD.value}
        if rule.type not in supported:
            logger.warning(
                "unsupported_rule_type rule_id=%s type=%s",
                rule.rule_id,
                rule.type,
            )
            return RuleEvaluation(rule=rule, triggered=False)

        return self._evaluate_threshold(rule, current)

    # ── Threshold Evaluator (Sprint 2) ─────────────────────────────

    def _evaluate_threshold(
        self, rule: SignalRuleDefinition, data: MacroDataSchema
    ) -> RuleEvaluation:
        """Evaluate a threshold rule: value OP threshold.

        Supported operators: gt, lt, gte, lte, eq
        """
        value = data.value
        threshold = rule.condition.threshold
        operator = rule.condition.operator

        condition_str = f"{rule.condition.field} {operator} {threshold}"

        triggered: bool
        if operator == "gt":
            triggered = value > threshold
        elif operator == "lt":
            triggered = value < threshold
        elif operator == "gte":
            triggered = value >= threshold
        elif operator == "lte":
            triggered = value <= threshold
        elif operator == "eq":
            triggered = abs(value - threshold) < 1e-9
        else:
            logger.warning(
                "unknown_operator rule_id=%s operator=%s",
                rule.rule_id,
                operator,
            )
            triggered = False

        logger.debug(
            "threshold_eval rule_id=%s value=%.4f %s %.4f triggered=%s",
            rule.rule_id,
            value,
            operator,
            threshold,
            triggered,
        )

        return RuleEvaluation(
            rule=rule,
            triggered=triggered,
            input_value=value,
            condition_str=condition_str,
        )

    # ── Private ────────────────────────────────────────────────────

    @staticmethod
    def _load_rules(path: str) -> list[SignalRuleDefinition]:
        """Load and parse signal rules from YAML configuration."""
        raw = load_yaml(path)
        rules_raw: list[dict] = raw.get("rules", [])

        parsed: list[SignalRuleDefinition] = []
        for r in rules_raw:
            condition_raw = r.get("condition", {})
            signal_raw = r.get("signal", {})

            parsed.append(
                SignalRuleDefinition(
                    rule_id=r["rule_id"],
                    description=r.get("description", ""),
                    indicator=r["indicator"],
                    dimension=r["dimension"],
                    type=r["type"],
                    condition=RuleCondition(
                        operator=condition_raw.get("operator", "gt"),
                        field=condition_raw.get("field", "value"),
                        threshold=float(condition_raw["threshold"]),
                    ),
                    signal_direction=signal_raw.get("direction", "neutral"),
                    signal_strength=signal_raw.get("strength", "moderate"),
                    signal_confidence=float(signal_raw.get("confidence", 0.5)),
                    interpretation=r.get("interpretation", ""),
                )
            )
        return parsed
