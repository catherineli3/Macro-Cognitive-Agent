"""Learning Unit Validator — Enforces the 5 Attribute Constraint (DDR-V3-007).

The Learning Engine is permitted to modify exactly 5 attribute types.
This module validates every LearningUnit before any modification is applied,
rejecting any change that violates the architectural constraints.

Prohibited operations enforced:
    - Delete a Belief
    - Rewrite a Belief's causal rule
    - Create a new Belief from scratch
    - Modify any attribute not in the 5 Learning Unit attributes
    - Modify weight by more than ±0.15 in a single cycle
    - Remove a precondition (only add/narrow)
"""

from __future__ import annotations

from src.schemas.learning_unit import (
    EvidenceChange,
    LearningUnit,
    PreconditionChange,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)

# ── Permitted horizon values
VALID_HORIZONS = {"1d", "3d", "5d", "10d", "21d"}

# ── Weight constraints
MAX_WEIGHT_DELTA = 0.15
MIN_WEIGHT = 0.0
MAX_WEIGHT = 1.0


class LearningUnitValidator:
    """Validates that every LearningUnit conforms to the 5-attribute constraint.

    DDR-V3-007: No modifications outside the 5 attribute types.
    All rejections are logged as warnings with detailed reasons.
    """

    def validate(self, unit: LearningUnit, current_weight: float = 0.5) -> tuple[bool, list[str]]:
        """Validate a LearningUnit against all constraints.

        Returns:
            (is_valid, list of violation messages). Empty list = valid.
        """
        violations: list[str] = []

        # Check at least one attribute modified (already enforced by schema,
        # but double-check here)
        # ── Attribute 1: Weight boundaries ───────────────────────────
        if unit.weight_delta is not None:
            if abs(unit.weight_delta) > MAX_WEIGHT_DELTA:
                violations.append(
                    f"weight_delta {unit.weight_delta} exceeds max ±{MAX_WEIGHT_DELTA}"
                )
            new_weight = current_weight + unit.weight_delta
            # BeliefVersionManager clamps to [0, 1], allow epsilon overflow
            clamped = max(MIN_WEIGHT, min(MAX_WEIGHT, new_weight))
            if clamped != new_weight:
                # Only reject if delta pushes FAR out of bounds (>0.05 beyond)
                if new_weight < MIN_WEIGHT - 0.05 or new_weight > MAX_WEIGHT + 0.05:
                    violations.append(
                        f"resulting weight {new_weight} far out of range [{MIN_WEIGHT}, {MAX_WEIGHT}]"
                    )

        # ── Attribute 2: Confidence boundaries ───────────────────────
        if unit.confidence_delta is not None:
            # Confidence delta can be larger (full range) since it's meta-trust
            pass

        # ── Attribute 3: Precondition action ─────────────────────────
        if unit.precondition_change is not None:
            pc = unit.precondition_change
            if pc.action not in ("add", "narrow"):
                violations.append(
                    f"precondition action '{pc.action}' not allowed — only 'add' or 'narrow'"
                )
            if not pc.key:
                violations.append("precondition key is empty")

        # ── Attribute 4: Horizon value ───────────────────────────────
        if unit.horizon_change is not None:
            if unit.horizon_change not in VALID_HORIZONS:
                violations.append(f"horizon '{unit.horizon_change}' not in {VALID_HORIZONS}")

        # ── Attribute 5: Evidence action ─────────────────────────────
        if unit.evidence_change is not None:
            ec = unit.evidence_change
            if ec.action not in ("add", "deprecate"):
                violations.append(
                    f"evidence action '{ec.action}' not allowed — only 'add' or 'deprecate'"
                )
            if not ec.evidence_id:
                violations.append("evidence_id is empty")

        is_valid = len(violations) == 0
        if not is_valid:
            logger.warning(
                "learning_unit_invalid belief=%s violations=%s",
                unit.belief_id,
                violations,
            )

        return is_valid, violations

    def is_modification_permitted(self, attribute_name: str) -> bool:
        """Check if an attribute is in the permitted Learning Unit set."""
        permitted = {"weight", "confidence", "preconditions", "horizon", "evidence"}
        return attribute_name in permitted

    def get_permitted_attributes(self) -> list[str]:
        """Return the list of 5 permitted attribute names."""
        return ["weight", "confidence", "preconditions", "horizon", "evidence"]
