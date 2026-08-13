"""Signal Generator — Converts macro data into structured signals.

Implements SignalGeneratorInterface.
Pure function: (indicator, current, history) → MacroSignalSchema.

Design:
    - Receives current observation + historical context
    - Delegates rule evaluation to RuleEngine
    - Assembles triggered rules into a MacroSignalSchema
    - Signal comes from CHANGES, not static values — history enables this

Non-responsibilities:
    - Does NOT access the database
    - Does NOT perform analysis
    - Does NOT use LLM
    - Does NOT handle multi-indicator rules (that's RuleEngine's job)
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.domain.macro_indicator import MacroIndicator
from src.interfaces.signal_generator import SignalGeneratorInterface
from src.schemas.macro_data import MacroDataSchema
from src.schemas.signal import (
    MacroSignalSchema,
    SignalDirection,
    SignalEvidence,
    SignalStrength,
)
from src.shared.exceptions import SignalGenerationError
from src.shared.logging import get_logger
from src.signal.rule_engine import RuleEngine, RuleEvaluation

logger = get_logger(__name__)


class ThresholdSignalGenerator(SignalGeneratorInterface):
    """Generates signals using threshold-based rules from the Rule Engine.

    Sprint 2 MVP: single rule type (threshold), single indicator input.
    The Rule Engine handles all rule evaluation logic; this generator
    orchestrates the flow: data → rules → evidence → signal.

    Usage:
        engine = RuleEngine("configs/signal_rules.yaml")
        generator = ThresholdSignalGenerator(engine)
        signal = await generator.generate(dxy_indicator, current_dxy, dxy_history)
    """

    def __init__(self, rule_engine: RuleEngine | None = None) -> None:
        """Initialize the signal generator.

        Args:
            rule_engine: Pre-configured RuleEngine instance.
                         If None, creates one with default config path.
        """
        self._engine = rule_engine or RuleEngine()

    def source_name(self) -> str:
        return "ThresholdSignalGenerator"

    # ── Core Logic ────────────────────────────────────────────────

    async def generate(
        self,
        indicator: MacroIndicator,
        current: MacroDataSchema,
        history: list[MacroDataSchema],
    ) -> MacroSignalSchema:
        """Generate a signal from current and historical macro data.

        Workflow:
            1. Evaluate all applicable rules via RuleEngine
            2. Collect triggered rules as evidence
            3. Determine overall direction, strength, confidence
            4. Assemble and return MacroSignalSchema

        Edge cases:
            - No rules triggered → returns NEUTRAL/weak signal with no evidence
            - Multiple rules triggered → most conservative direction wins
            - Empty history → signal still generated (single-point threshold)
        """
        try:
            evaluations = self._engine.evaluate(
                indicator=indicator.symbol,
                current=current,
                history=history,
            )

            triggered = [e for e in evaluations if e.triggered]

            # Build evidence from triggered rules
            evidence_items = [
                SignalEvidence(
                    rule_id=ev.rule.rule_id,
                    rule_description=ev.rule.description,
                    input_value=current.value,
                    condition=ev.condition_str,
                    interpretation=ev.rule.interpretation,
                    evaluated_at=datetime.now(UTC),
                )
                for ev in triggered
            ]

            # Determine aggregate signal properties
            direction = self._aggregate_direction(triggered)
            strength = self._aggregate_strength(triggered)
            confidence = self._aggregate_confidence(triggered)

            signal = MacroSignalSchema(
                indicator=indicator.symbol,
                dimension=indicator.hypothesis_dimension.value,
                direction=direction,
                strength=strength,
                confidence=confidence,
                timestamp=datetime.now(UTC),
                evidence=evidence_items,
                data_timestamp=current.timestamp,
            )

            logger.info(
                "signal_generated indicator=%s direction=%s strength=%s "
                "confidence=%.2f evidence_count=%d",
                indicator.symbol,
                direction.value,
                strength.value,
                confidence,
                len(evidence_items),
            )

            return signal

        except SignalGenerationError:
            raise
        except Exception as exc:
            raise SignalGenerationError(
                f"Failed to generate signal for {indicator.symbol}: {exc}",
                details={"indicator": indicator.symbol},
            ) from exc

    # ── Aggregation Helpers ─────────────────────────────────────────

    @staticmethod
    def _aggregate_direction(
        triggered: list[RuleEvaluation],
    ) -> SignalDirection:
        """Determine the overall direction from triggered rules.

        If there are conflicting directions (both bullish and bearish
        rules triggered), the most conservative (bearish) wins.
        This is a deliberate design choice — a risk-management bias.
        """
        if not triggered:
            return SignalDirection.NEUTRAL

        directions = {e.rule.signal_direction for e in triggered}

        if "bearish" in directions and "bullish" in directions:
            # Conflict: conservative bias → bearish
            return SignalDirection.BEARISH
        if "bearish" in directions:
            return SignalDirection.BEARISH
        if "bullish" in directions:
            return SignalDirection.BULLISH
        return SignalDirection.NEUTRAL

    @staticmethod
    def _aggregate_strength(
        triggered: list[RuleEvaluation],
    ) -> SignalStrength:
        """Determine overall signal strength from triggered rules.

        Uses the maximum strength among triggered rules.
        """
        if not triggered:
            return SignalStrength.WEAK

        strength_order = {
            "strong": 3,
            "moderate": 2,
            "weak": 1,
        }
        max_s = max(strength_order.get(e.rule.signal_strength, 1) for e in triggered)

        for name, val in strength_order.items():
            if val == max_s:
                return SignalStrength(name)
        return SignalStrength.WEAK

    @staticmethod
    def _aggregate_confidence(
        triggered: list[RuleEvaluation],
    ) -> float:
        """Compute overall confidence from triggered rules.

        Uses the maximum confidence among triggered rules, capped at 1.0.
        If no rules triggered, returns 0.3 (low-confidence neutral).
        """
        if not triggered:
            return 0.3
        return min(max(e.rule.signal_confidence for e in triggered), 1.0)
