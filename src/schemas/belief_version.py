"""V3 Belief Versioning Schemas — Immutable Versioned Beliefs (DDR-V3-008).

Key design:
    - Every Belief carries a monotonic version number
    - Old versions are immutable and queryable
    - Every version change records: trigger, diagnosis, before/after snapshots
    - The complete version history is the Agent's reasoning journey
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

# ── Belief Version ───────────────────────────────────────────────────────────


class BeliefVersion(BaseModel):
    """An immutable snapshot of a belief at a point in time.

    DDR-V3-008: Every learning action creates a new version.
    Old versions are never modified — they form an immutable audit trail.

    Example evolution:
        v1: weight=0.85, horizon=5d, preconditions={}
        v2: weight=0.81 ← TIMING_ERR × 2
        v3: weight=0.83, horizon=10d ← correct after extension
        v4: weight=0.83, precondition="core_cpi > 3%" ← EVID_MISSING
    """

    belief_id: str = Field(..., min_length=1, max_length=64)
    version_number: int = Field(..., ge=1, description="Monotonic: 1, 2, 3...")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    # ── Snapshot of the 5 Learning Unit attributes at this version ───────
    weight: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    preconditions: dict[str, Any] = Field(default_factory=dict)
    valid_horizon: str = Field(default="5d")
    supporting_evidence: list[str] = Field(default_factory=list)

    # ── What triggered this version? ─────────────────────────────────────
    trigger: str = Field(
        default="initial",
        description="'initial' | 'prediction_outcome' | 'manual' | 'deprecation'",
    )
    trigger_detail: str = Field(default="", max_length=512)
    diagnosis_report_id: str | None = Field(
        default=None,
        description="Which diagnosis caused this version change",
    )

    # ── Diff from previous version (for v2+) ─────────────────────────────
    changes_from_previous: dict[str, Any] | None = Field(
        default=None,
        description="Key-value pairs of changed attributes",
    )

    @property
    def is_initial(self) -> bool:
        return self.version_number == 1

    def __repr__(self) -> str:
        precond_count = len(self.preconditions)
        return (
            f"<BeliefVersion v{self.version_number} "
            f"w={self.weight:.2f} c={self.confidence:.2f} "
            f"horizon={self.valid_horizon} preconds={precond_count} "
            f"trigger={self.trigger}>"
        )


# ── Adaptive Belief ──────────────────────────────────────────────────────────


class AdaptiveBelief(BaseModel):
    """A V3 belief with version history and 5 Learning Unit attributes.

    DDR-V3-003: Progressive evolution — no rule deletion, no knowledge replacement.
    DDR-V3-008: Full immutable version history, queryable and auditable.

    This replaces V2's BeliefWeight + BeliefRecord with a unified,
    versioned belief that carries its complete evolution trace.
    """

    belief_id: str = Field(..., min_length=1, max_length=64)
    dimension: str = Field(..., min_length=1, max_length=40)
    transmission_channel: str = Field(
        default="",
        max_length=80,
        description="The transmission channel this belief applies to (DDR-V3-009)",
    )

    # ── Current state (derived from latest version) ──────────────────────
    current_version: int = Field(default=1, ge=1)
    weight: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    preconditions: dict[str, Any] = Field(default_factory=dict)
    valid_horizon: str = Field(default="5d")
    supporting_evidence: list[str] = Field(default_factory=list)

    # ── Principle lineage ─────────────────────────────────────────────────
    founded_on_principles: list[str] = Field(
        default_factory=list,
        description="Principle IDs this belief was derived from",
    )

    # ── Full version history (append-only, oldest first) ────────────────
    version_history: list[BeliefVersion] = Field(default_factory=list)

    # ── Performance tracking ────────────────────────────────────────────
    cycle_count: int = Field(default=0, ge=0)
    correct_count: int = Field(default=0, ge=0)
    streak: int = Field(default=0, description="Consecutive correct (+) or wrong (-)")
    status: str = Field(default="active", description="'active' | 'deprecated' | 'review'")

    @property
    def historical_accuracy(self) -> float:
        """Accuracy across all evaluated cycles."""
        if self.cycle_count == 0:
            return 0.5
        return self.correct_count / self.cycle_count

    @property
    def id(self) -> str:
        """Alias for belief_id — compatibility with code that expects .id."""
        return self.belief_id

    @property
    def domain(self) -> str:
        """Alias for dimension — compatibility with BeliefStore(domain=...)."""
        return self.dimension

    @property
    def stage(self) -> str:
        """Alias for status — compatibility with BeliefStore(stage=...)."""
        return self.status

    @property
    def is_deprecated(self) -> bool:
        return self.status == "deprecated"

    def get_version(self, v: int) -> BeliefVersion | None:
        """Retrieve a specific version of this belief."""
        for version in self.version_history:
            if version.version_number == v:
                return version
        return None

    def get_weight_trajectory(self) -> list[tuple[int, float]]:
        """Get weight evolution over versions: [(v1, 0.85), (v2, 0.81), ...]."""
        return [(bv.version_number, bv.weight) for bv in self.version_history]

    def get_accuracy_trajectory_slope(self) -> float:
        """Compute slope of weight trajectory (positive = improving)."""
        trajectory = self.get_weight_trajectory()
        if len(trajectory) < 2:
            return 0.0
        # Simple linear regression slope
        n = len(trajectory)
        x_mean = sum(v for v, _ in trajectory) / n
        y_mean = sum(w for _, w in trajectory) / n
        num = sum((v - x_mean) * (w - y_mean) for v, w in trajectory)
        den = sum((v - x_mean) ** 2 for v, _ in trajectory)
        return num / den if den != 0 else 0.0

    def why_changed(self, v: int) -> str:
        """Human-readable explanation of why this version was created."""
        version = self.get_version(v)
        if version is None:
            return f"Version {v} not found."
        if version.is_initial:
            return "v1: Initial belief — created by Hypothesis Generator."
        parts = [f"v{v}: "]
        if version.changes_from_previous:
            for attr, change in version.changes_from_previous.items():
                parts.append(f"{attr} changed ({change}). ")
        parts.append(f"Trigger: {version.trigger_detail or version.trigger}.")
        return "".join(parts)

    def __repr__(self) -> str:
        return (
            f"<AdaptiveBelief [{self.dimension}] v{self.current_version} "
            f"w={self.weight:.2f} c={self.confidence:.2f} "
            f"cycles={self.cycle_count} acc={self.historical_accuracy:.0%} "
            f"status={self.status}>"
        )
