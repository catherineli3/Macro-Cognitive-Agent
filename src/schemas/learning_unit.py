"""V3 Learning Unit Schemas — The 5 Modifiable Attributes (DDR-V3-007).

Key design:
    - Learning Engine constrained to modify exactly 5 attribute types
    - Prohibited: delete belief, rewrite rule, modify weight >±0.15/cycle, remove preconditions
    - Every LearningAction must specify which attribute(s) it modifies
    - LearningUnit validated before any modification is applied
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

# ── Learning Action Type ─────────────────────────────────────────────────────


class LearningActionType(str, Enum):
    """Permitted learning actions on beliefs (DDR-V3-003)."""

    WEIGHT_ADJUST = "WEIGHT_ADJUST"
    CONFIDENCE_DECAY = "CONFIDENCE_DECAY"
    CONDITION_ADD = "CONDITION_ADD"
    CONDITION_NARROW = "CONDITION_NARROW"
    HORIZON_EXTEND = "HORIZON_EXTEND"
    HORIZON_SHORTEN = "HORIZON_SHORTEN"
    EVIDENCE_ADD = "EVIDENCE_ADD"
    EVIDENCE_DEPRECATE = "EVIDENCE_DEPRECATE"
    MARK_EVENT = "MARK_EVENT"
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"
    DEPRECATE = "DEPRECATE"


# ── Precondition Change ──────────────────────────────────────────────────────


class PreconditionChange(BaseModel):
    """A change to a belief's preconditions.

    DDR-V3-007: Preconditions are additive only — can be added or narrowed,
    NEVER removed.
    """

    action: str = Field(..., description="'add' | 'narrow' (no 'remove')")
    key: str = Field(..., min_length=1, max_length=80)
    value: Any = Field(...)
    old_value: Any | None = Field(default=None)

    @model_validator(mode="after")
    def validate_action(self) -> "PreconditionChange":
        if self.action not in ("add", "narrow"):
            raise ValueError(
                f"PreconditionChange action must be 'add' or 'narrow', got '{self.action}'"
            )
        return self


class EvidenceChange(BaseModel):
    """A change to a belief's supporting evidence.

    DDR-V3-007: Evidence can be added or deprecated, never deleted.
    """

    action: str = Field(..., description="'add' | 'deprecate'")
    evidence_id: str = Field(..., min_length=1, max_length=64)
    reason: str = Field(default="", max_length=512)

    @model_validator(mode="after")
    def validate_action(self) -> "EvidenceChange":
        if self.action not in ("add", "deprecate"):
            raise ValueError(
                f"EvidenceChange action must be 'add' or 'deprecate', got '{self.action}'"
            )
        return self


# ── Learning Unit ────────────────────────────────────────────────────────────


class LearningUnit(BaseModel):
    """The atom of learning — exactly 5 modifiable attributes.

    DDR-V3-007: Only these 5 attributes on a Belief can be modified.
    At least one must be modified (non-None). No attributes outside these 5.
    """

    belief_id: str = Field(..., min_length=1, max_length=64)

    # ── Attribute 1: Weight (0~1) ────────────────────────────────────────
    weight_delta: float | None = Field(
        default=None,
        ge=-0.15,
        le=0.15,
        description="Weight adjustment per cycle. Bounded to ±0.15 (DDR-V3-007).",
    )

    # ── Attribute 2: Confidence (0~1) ────────────────────────────────────
    confidence_delta: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Meta-confidence adjustment about the weight itself.",
    )

    # ── Attribute 3: Preconditions ───────────────────────────────────────
    precondition_change: PreconditionChange | None = Field(default=None)

    # ── Attribute 4: Time Horizon ────────────────────────────────────────
    horizon_change: str | None = Field(
        default=None,
        description="New horizon value: '1d', '3d', '5d', '10d', '21d'",
    )

    # ── Attribute 5: Supporting Evidence ─────────────────────────────────
    evidence_change: EvidenceChange | None = Field(default=None)

    @model_validator(mode="after")
    def at_least_one_change(self) -> "LearningUnit":
        """DDR-V3-007: At least one Learning Unit attribute must be modified."""
        has_change = any(
            [
                self.weight_delta is not None,
                self.confidence_delta is not None,
                self.precondition_change is not None,
                self.horizon_change is not None,
                self.evidence_change is not None,
            ]
        )
        if not has_change:
            raise ValueError("LearningUnit must modify at least one of the 5 attributes")
        return self

    def modified_attributes(self) -> list[str]:
        """List which of the 5 attributes were modified."""
        attrs = []
        if self.weight_delta is not None:
            attrs.append("weight")
        if self.confidence_delta is not None:
            attrs.append("confidence")
        if self.precondition_change is not None:
            attrs.append("preconditions")
        if self.horizon_change is not None:
            attrs.append("horizon")
        if self.evidence_change is not None:
            attrs.append("evidence")
        return attrs

    def __repr__(self) -> str:
        changed = self.modified_attributes()
        return f"<LearningUnit belief={self.belief_id[:8]} changed={changed}>"


# ── Learning Action ──────────────────────────────────────────────────────────


class LearningAction(BaseModel):
    """A specific learning action taken on a belief.

    Maps a diagnosis result to a concrete, constrained modification
    via the 5 Learning Unit attributes.
    """

    action_id: str = Field(default="", description="Unique action identifier")
    action_type: LearningActionType = Field(...)
    belief_id: str = Field(..., min_length=1, max_length=64)
    diagnosis_report_id: str = Field(..., min_length=1, max_length=64)
    learning_unit: LearningUnit = Field(...)
    reason: str = Field(default="", max_length=512)
    executed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @property
    def is_noop(self) -> bool:
        """Whether this action effectively changes nothing (MARK_EVENT)."""
        return self.action_type == LearningActionType.MARK_EVENT

    def __repr__(self) -> str:
        return (
            f"<LearningAction {self.action_type.value} "
            f"belief={self.belief_id[:8]} attrs={self.learning_unit.modified_attributes()}>"
        )
