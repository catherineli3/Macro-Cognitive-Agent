"""Milestone C Research Evolution Schemas.

Defines the four-level cognitive hierarchy:
    Finding → Principle → Belief → Framework

Architecture Freeze Clause:
    Research Findings are observations.
    Research Principles are reusable knowledge.
    Beliefs are decision weights.
    Frameworks are organizing worldviews.
    The system must never collapse these four layers into one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4


# ═══════════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════════


class PrincipleStrength(str, Enum):
    """Progressive strength levels for Research Principles."""
    CANDIDATE = "candidate"       # P2-P4 met, P1 pending
    VALIDATED = "validated"       # P1-P5 all met, >=30 obs
    MATURE = "mature"             # >=50 obs, >=3 regimes, <=2 contradictions/30 cycles
    FOUNDATIONAL = "foundational" # >=100 obs, >=5 regimes, 0 contradictions


class PrincipleStatus(str, Enum):
    """Operational status of a Research Principle."""
    ACTIVE = "active"
    ACTIVE_COMPETITION = "active_competition"  # Competing with another principle
    WEAKENING = "weakening"                     # Evidence shifting against
    RETIRED = "retired"
    ARCHIVED = "archived"


class FrameworkStatus(str, Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    RETIRED = "retired"


class ConflictResolution(str, Enum):
    """How a conflict between principles was resolved."""
    A_WINS = "a_wins"
    B_WINS = "b_wins"
    MERGED = "merged"           # Principles combined into new formulation
    UNRESOLVED = "unresolved"    # Neither dominates after evaluation period
    ARCHIVED_REGIME = "archived_regime"  # Both archived as regime-dependent


class FindingTTLStatus(str, Enum):
    ACTIVE = "active"
    FROZEN = "frozen"           # TTL paused due to conflict citation
    EXTENDED = "extended"        # TTL extended due to citation
    PROMOTED = "promoted"        # Became a Principle (immune to TTL)
    EXPIRED = "expired"          # Auto-archived
    ARCHIVED = "archived"        # Manually archived


class SynthesisStrategy(str, Enum):
    WEIGHTED_AVERAGE = "weighted_average"
    DOMAIN_PARTITION = "domain_partition"
    BEST_FRAMEWORK = "best_framework"


# ═══════════════════════════════════════════════════════════════════════════════
# Level 2: Research Principle
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class PrincipleEvidence:
    """Evidence backing a Research Principle.

    G3 (F1.6): Evidence Feedback Loop — tracks prediction outcomes
    to drive strength increase/decrease/retirement decisions.
    """
    total_observations: int = 0
    correct_in_scope: int = 0
    correct_count: int = 0          # G3: times principle correctly predicted outcome
    incorrect_count: int = 0        # G3: times principle incorrectly predicted
    accuracy: float = 0.0
    regimes_count: int = 0
    regimes_validated: list[str] = field(default_factory=list)
    channels_validated: list[str] = field(default_factory=list)
    last_validated_cycle: int = 0
    last_evaluated_cycle: int = 0   # G3: last cycle this principle was evaluated
    sustained_cycles: int = 0
    contradiction_count: int = 0
    failure_modes: list[str] = field(default_factory=list)  # G3: types of failures observed

    @property
    def computed_accuracy(self) -> float:
        """G3: Accuracy computed from actual prediction outcomes, not hardcoded."""
        total = self.correct_count + self.incorrect_count
        if total == 0:
            return 0.0
        return round(self.correct_count / total, 4)

    @property
    def strength_score(self) -> float:
        """0-1 score derived from evidence volume and consistency."""
        if self.total_observations == 0:
            return 0.0
        volume = min(1.0, self.total_observations / 100)
        consistency = self.computed_accuracy if (self.correct_count + self.incorrect_count) > 0 else self.accuracy
        regime_bonus = min(0.1, self.regimes_count * 0.025)
        sustained_bonus = min(0.1, self.sustained_cycles / 200)
        return round(min(1.0, 0.4 * volume + 0.4 * consistency + regime_bonus + sustained_bonus), 4)

    def record_outcome(self, correct: bool, cycle: int, failure_mode: str = "") -> None:
        """G3: Record a prediction outcome observation."""
        self.total_observations += 1
        self.last_evaluated_cycle = cycle
        if correct:
            self.correct_count += 1
            self.correct_in_scope += 1
        else:
            self.incorrect_count += 1
            if failure_mode:
                self.failure_modes.append(failure_mode)
                # Keep only last 10 failure modes
                if len(self.failure_modes) > 10:
                    self.failure_modes = self.failure_modes[-10:]
        # Update computed accuracy
        self.accuracy = self.computed_accuracy


@dataclass
class ResearchPrinciple:
    """A validated, cross-regime causal pattern. Level 2 of the cognitive hierarchy.

    Granularity Rules (GR-1~5):
        GR-1: Single causal edge — one directed relationship between exactly two nodes
        GR-2: Independently falsifiable — a single observation can disprove it
        GR-3: Single condition domain — at most one compound precondition
        GR-4: Atomic domain — operates within exactly one transmission dimension
        GR-5: Minimal scope — if splittable into two simpler principles, MUST be split

    A Principle is the minimum indivisible learning unit.
    One Principle = one causal edge. No aggregation.
    """

    principle_id: str = field(default_factory=lambda: f"pr-{uuid4().hex[:8]}")
    name: str = ""
    statement: str = ""                              # Declarative causal claim
    domain: str = ""                                 # Transmission channel / dimension
    preconditions: dict = field(default_factory=dict)

    strength: PrincipleStrength = PrincipleStrength.CANDIDATE
    status: PrincipleStatus = PrincipleStatus.ACTIVE

    evidence: PrincipleEvidence = field(default_factory=PrincipleEvidence)
    source_findings: list[str] = field(default_factory=list)

    # Granularity & composition
    prerequisite_principles: list[str] = field(default_factory=list)
    implies_principles: list[str] = field(default_factory=list)
    composes_with: list[str] = field(default_factory=list)

    # Competition tracking
    competes_with: list[str] = field(default_factory=list)   # IDs of competing principles
    competition_resolution: Optional[ConflictResolution] = None

    # Metadata
    created_at_cycle: int = 0
    promoted_from_findings: list[str] = field(default_factory=list)
    last_updated: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_competition_active(self) -> bool:
        return self.status == PrincipleStatus.ACTIVE_COMPETITION

    @property
    def is_atomic(self) -> bool:
        """GR-4: operates within ONE dimension."""
        return "," not in self.domain and "&" not in self.domain

    def strength_score(self) -> float:
        return self.evidence.strength_score

    def describe(self) -> str:
        comp = f" [competes with {', '.join(self.competes_with[:3])}]" if self.competes_with else ""
        return (
            f"[{self.strength.value.upper()}] {self.name}: {self.statement} "
            f"(domain={self.domain}, obs={self.evidence.total_observations}, "
            f"regimes={self.evidence.regimes_count}, acc={self.evidence.accuracy:.1%}){comp}"
        )

    def __repr__(self) -> str:
        return f"<ResearchPrinciple [{self.strength.value}] {self.name[:50]}>"


# ═══════════════════════════════════════════════════════════════════════════════
# Level 4: Research Framework & Framework Set
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class FrameworkExplainability:
    """Mandatory explainability output for every Framework.

    Review 2: A Framework that cannot explain itself is architecturally invalid.
    """
    name: str = ""
    thesis: str = ""                        # >=100 char explanatory paragraph
    confidence: float = 0.0                 # Computed, NOT labeled
    supporting_principles_count: int = 0
    contradicting_principles_count: int = 0
    historical_win_rate: float = 0.0        # Regime classification accuracy
    activated_since_cycle: int = 0
    activated_since_date: Optional[datetime] = None
    parent_framework: Optional[str] = None  # Framework lineage
    competing_frameworks: list[str] = field(default_factory=list)

    def describe(self) -> str:
        return (
            f"Framework: {self.name}\n"
            f"  Thesis: {self.thesis}\n"
            f"  Confidence: {self.confidence:.2f} | "
            f"Supporting: {self.supporting_principles_count} | "
            f"Contradicting: {self.contradicting_principles_count}\n"
            f"  Win Rate: {self.historical_win_rate:.0%} | "
            f"Active since cycle {self.activated_since_cycle}\n"
            f"  Parent: {self.parent_framework or 'none'} | "
            f"Competing: {', '.join(self.competing_frameworks) if self.competing_frameworks else 'none'}"
        )


@dataclass
class ResearchFramework:
    """The agent's highest-level organizing worldview. Level 4 of the hierarchy.

    A Framework is a coherent cluster of Principles that together define
    how the agent interprets the macro environment.

    Review 3 (Competing Principles), Review 4 (Framework Set):
        - Frameworks coexist as a SET, not a singleton
        - Multiple frameworks operate concurrently
        - Domain-weighted synthesis determines hypothesis generation
    """

    framework_id: str = field(default_factory=lambda: f"fw-{uuid4().hex[:8]}")
    name: str = ""
    thesis: str = ""                                # 1-3 paragraph explanation
    status: FrameworkStatus = FrameworkStatus.CANDIDATE

    # Principle composition
    principles: list[str] = field(default_factory=list)    # Principle IDs
    principle_weights: dict[str, float] = field(default_factory=dict)

    # Performance
    accuracy_trajectory: list[float] = field(default_factory=list)
    cycle_count: int = 0

    # Framework Set fields (Review 4)
    framework_set_id: Optional[str] = None
    domain_coverage: dict[str, float] = field(default_factory=dict)
    competes_with: list[str] = field(default_factory=list)
    synthesis_weight: float = 0.0

    # Lineage
    parent_framework: Optional[str] = None
    created_from: str = "principle_cluster"  # "principle_cluster" | "framework_conflict"
    created_at_cycle: int = 0
    retired_at_cycle: Optional[int] = None
    retirement_reason: Optional[str] = None

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_active(self) -> bool:
        return self.status == FrameworkStatus.ACTIVE

    @property
    def recent_accuracy(self) -> float:
        if not self.accuracy_trajectory:
            return 0.0
        window = self.accuracy_trajectory[-50:]
        return sum(window) / len(window) if window else 0.0

    def compute_confidence(self, principles: dict[str, ResearchPrinciple]) -> float:
        """Compute framework confidence from principle consensus + accuracy.

        confidence = 0.4 × mean(supporting_principle_strength)
                   + 0.2 × (1 - mean(contradicting_principle_strength))
                   + 0.3 × historical_win_rate
                   + 0.1 × supporting_ratio
        """
        supporting = [
            p.evidence.strength_score
            for pid in self.principles
            if (p := principles.get(pid)) and p.status != PrincipleStatus.RETIRED
        ]
        contradicting = [
            p.evidence.strength_score
            for pid in (self.competes_with or [])
            if (p := principles.get(pid))
        ]

        sup_mean = sum(supporting) / len(supporting) if supporting else 0.3
        con_mean = sum(contradicting) / len(contradicting) if contradicting else 0.0
        total = len(supporting) + len(contradicting)
        sup_ratio = len(supporting) / total if total > 0 else 0.5
        win_rate = self.recent_accuracy

        return round(0.4 * sup_mean + 0.2 * (1 - con_mean) + 0.3 * win_rate + 0.1 * sup_ratio, 4)

    def compute_explainability(self,
                               principles: dict[str, ResearchPrinciple]) -> FrameworkExplainability:
        """Mandatory: produces the full explainability output (Review 2)."""
        supporting_count = sum(
            1 for pid in self.principles
            if (p := principles.get(pid)) and p.status != PrincipleStatus.RETIRED
        )
        contradicting_count = sum(
            1 for pid in (self.competes_with or [])
            if (p := principles.get(pid))
        )
        return FrameworkExplainability(
            name=self.name,
            thesis=self.thesis,
            confidence=self.compute_confidence(principles),
            supporting_principles_count=supporting_count,
            contradicting_principles_count=contradicting_count,
            historical_win_rate=self.recent_accuracy,
            activated_since_cycle=self.created_at_cycle,
            activated_since_date=self.created_at,
            parent_framework=self.parent_framework,
            competing_frameworks=list(self.competes_with),
        )

    def describe(self) -> str:
        return (
            f"[{self.status.value.upper()}] {self.name}\n"
            f"  Thesis: {self.thesis[:200]}...\n"
            f"  Principles: {len(self.principles)}, "
            f"Accuracy: {self.recent_accuracy:.1%} over {len(self.accuracy_trajectory)} obs\n"
            f"  Parent: {self.parent_framework or 'none'}"
        )

    def __repr__(self) -> str:
        return f"<ResearchFramework [{self.status.value}] {self.name[:40]}>"


@dataclass
class FrameworkSet:
    """The agent's complete set of active frameworks at any point in time.

    Review 4: Multiple frameworks operate concurrently. The agent synthesizes
    across them. Framework failure does not mean agent failure.
    """

    set_id: str = field(default_factory=lambda: f"fs-{uuid4().hex[:8]}")

    active_frameworks: list[str] = field(default_factory=list)    # Ordered by confidence
    framework_weights: dict[str, float] = field(default_factory=dict)
    domain_assignment: dict[str, list[str]] = field(default_factory=dict)

    max_active: int = 5
    min_active: int = 1
    synthesis_strategy: SynthesisStrategy = SynthesisStrategy.WEIGHTED_AVERAGE

    framework_lineage: dict[str, str] = field(default_factory=dict)
    retired_frameworks: list[str] = field(default_factory=list)

    # Metadata
    last_updated: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def active_count(self) -> int:
        return len(self.active_frameworks)

    @property
    def is_at_capacity(self) -> bool:
        return self.active_count >= self.max_active

    def add_framework(self, framework_id: str, initial_weight: float = 0.0) -> bool:
        """Try to add a framework. Returns False if at capacity and new is
        not better than weakest."""
        if not self.is_at_capacity:
            self.active_frameworks.append(framework_id)
            # Rebalance weights
            n = len(self.active_frameworks)
            w = 1.0 / n
            for fid in self.active_frameworks:
                self.framework_weights[fid] = w
            return True
        return False  # Caller must evaluate weakest and retry

    def replace_weakest(self, new_id: str, new_weight: float,
                        retire_id: str) -> bool:
        """Replace the weakest framework with a new one."""
        if retire_id not in self.active_frameworks:
            return False
        self.active_frameworks.remove(retire_id)
        self.retired_frameworks.append(retire_id)
        self.active_frameworks.append(new_id)
        # Rebalance
        total_w = sum(self.framework_weights.get(fid, 0.0) for fid in self.active_frameworks)
        for fid in self.active_frameworks:
            self.framework_weights[fid] = self.framework_weights.get(fid, 0.0) / max(total_w, 0.001)
        return True

    def retire_framework(self, framework_id: str) -> bool:
        """Retire a framework. Minimum 1 must remain."""
        if len(self.active_frameworks) <= self.min_active:
            return False
        if framework_id not in self.active_frameworks:
            return False
        self.active_frameworks.remove(framework_id)
        self.retired_frameworks.append(framework_id)
        self._rebalance_weights()
        return True

    def _rebalance_weights(self) -> None:
        n = len(self.active_frameworks)
        if n == 0:
            return
        w = 1.0 / n
        for fid in self.active_frameworks:
            self.framework_weights[fid] = w

    def weight_for(self, framework_id: str) -> float:
        return self.framework_weights.get(framework_id, 0.0)

    def domains_for(self, framework_id: str) -> list[str]:
        return self.domain_assignment.get(framework_id, [])

    def describe(self) -> str:
        lines = [f"FrameworkSet ({self.active_count} active, {len(self.retired_frameworks)} retired):"]
        for fid in self.active_frameworks:
            w = self.weight_for(fid)
            domains = self.domains_for(fid)
            lines.append(f"  {fid}: weight={w:.3f}, domains={domains}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<FrameworkSet active={self.active_count} retired={len(self.retired_frameworks)}>"


# ═══════════════════════════════════════════════════════════════════════════════
# Competing Principles & Conflict
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CompetingPrinciple:
    """Tracks a pair of competing principles.

    Review 3: Competing Principles may coexist indefinitely.
    Resolution is evidence-driven, not time-driven.
    """

    competition_id: str = field(default_factory=lambda: f"cp-{uuid4().hex[:8]}")
    principle_a_id: str = ""
    principle_b_id: str = ""
    domain: str = ""

    # Evidence accumulation
    evidence_for_a: int = 0
    evidence_for_b: int = 0
    cycles_since_start: int = 0

    # Resolution
    status: str = "competing"  # "competing" | "resolving" | "resolved"
    resolution: Optional[ConflictResolution] = None
    winner_id: Optional[str] = None
    loser_id: Optional[str] = None
    resolved_at_cycle: int = 0

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def a_win_rate(self) -> float:
        total = self.evidence_for_a + self.evidence_for_b
        return self.evidence_for_a / total if total > 0 else 0.5

    @property
    def b_win_rate(self) -> float:
        total = self.evidence_for_a + self.evidence_for_b
        return self.evidence_for_b / total if total > 0 else 0.5

    @property
    def is_decisive(self) -> bool:
        return max(self.a_win_rate, self.b_win_rate) >= 0.70

    @property
    def is_stalemate(self) -> bool:
        return self.cycles_since_start >= 50 and not self.is_decisive

    def record_evidence(self, for_a: bool = True) -> None:
        if for_a:
            self.evidence_for_a += 1
        else:
            self.evidence_for_b += 1

    def advance_cycle(self) -> None:
        self.cycles_since_start += 1

    def __repr__(self) -> str:
        return (f"<CompetingPrinciple {self.principle_a_id[:8]} vs {self.principle_b_id[:8]} "
                f"({self.evidence_for_a}:{self.evidence_for_b}) "
                f"status={self.status}>")


@dataclass
class ConflictRecord:
    """A record of a detected and processed conflict between principles."""

    conflict_id: str = field(default_factory=lambda: f"cr-{uuid4().hex[:8]}")
    competing_pair: Optional[CompetingPrinciple] = None
    principle_a_id: str = ""
    principle_b_id: str = ""

    source_diagnosis_ids: list[str] = field(default_factory=list)
    source_finding_ids: list[str] = field(default_factory=list)

    action: str = ""  # "queued" | "activated_competition" | "resolved" | "archived"
    resolution: Optional[ConflictResolution] = None

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    def __repr__(self) -> str:
        return (f"<ConflictRecord {self.principle_a_id[:8]} vs {self.principle_b_id[:8]} "
                f"action={self.action}>")


# ═══════════════════════════════════════════════════════════════════════════════
# Finding TTL & Lifecycle
# ═══════════════════════════════════════════════════════════════════════════════


# Default TTL for Research Findings (Review 5)
DEFAULT_FINDING_TTL_DAYS = 90
EXTENDED_FINDING_TTL_DAYS = 180    # For ESTABLISHED/ROBUST confidence
PRELIMINARY_FINDING_TTL_DAYS = 45
CITATION_EXTENSION_DAYS = 30


@dataclass
class FindingLifecycle:
    """Tracks the lifecycle and TTL of a Research Finding.

    Review 5: Findings have finite TTL. Default 90 days.
    Expired findings auto-archive. Only promoted or conflict-cited findings persist.
    """

    finding_id: str = ""
    status: FindingTTLStatus = FindingTTLStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_days: int = DEFAULT_FINDING_TTL_DAYS
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=DEFAULT_FINDING_TTL_DAYS)
    )

    # Extensions
    extension_count: int = 0
    last_extended_at: Optional[datetime] = None
    frozen_at: Optional[datetime] = None  # When TTL was frozen for conflict

    # Promotion
    promoted_to_principle_id: Optional[str] = None
    promoted_at: Optional[datetime] = None

    # Conflict
    cited_in_conflicts: list[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        if self.status == FindingTTLStatus.FROZEN:
            return False
        if self.status in (FindingTTLStatus.PROMOTED, FindingTTLStatus.ARCHIVED):
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def days_remaining(self) -> int:
        if self.status == FindingTTLStatus.FROZEN:
            return -1  # Indefinite while frozen
        remaining = (self.expires_at - datetime.now(timezone.utc)).days
        return max(0, remaining)

    def set_ttl(self, confidence_str: str) -> None:
        """Set TTL based on confidence level."""
        if confidence_str in ("established", "robust"):
            self.ttl_days = EXTENDED_FINDING_TTL_DAYS
        elif confidence_str == "preliminary":
            self.ttl_days = PRELIMINARY_FINDING_TTL_DAYS
        else:
            self.ttl_days = DEFAULT_FINDING_TTL_DAYS
        self.expires_at = self.created_at + timedelta(days=self.ttl_days)

    def extend(self, days: int = CITATION_EXTENSION_DAYS) -> None:
        """Extend TTL (e.g., due to citation by active Principle)."""
        if self.status == FindingTTLStatus.FROZEN:
            return
        self.status = FindingTTLStatus.EXTENDED
        self.expires_at += timedelta(days=days)
        self.extension_count += 1
        self.last_extended_at = datetime.now(timezone.utc)

    def freeze(self, conflict_id: str) -> None:
        """Freeze TTL while finding is cited in an active conflict."""
        self.status = FindingTTLStatus.FROZEN
        self.frozen_at = datetime.now(timezone.utc)
        self.cited_in_conflicts.append(conflict_id)

    def unfreeze(self) -> None:
        """Unfreeze TTL after conflict resolution."""
        if self.status == FindingTTLStatus.FROZEN:
            self.status = FindingTTLStatus.ACTIVE
            # Reset expiry from now
            self.expires_at = datetime.now(timezone.utc) + timedelta(days=self.ttl_days)

    def promote(self, principle_id: str) -> None:
        """Mark as promoted to Principle (immune to TTL)."""
        self.status = FindingTTLStatus.PROMOTED
        self.promoted_to_principle_id = principle_id
        self.promoted_at = datetime.now(timezone.utc)

    def expire(self) -> None:
        """Mark as expired."""
        self.status = FindingTTLStatus.EXPIRED

    def archive(self) -> None:
        """Manually archive."""
        self.status = FindingTTLStatus.ARCHIVED

    def __repr__(self) -> str:
        return (f"<FindingLifecycle {self.finding_id[:12]} "
                f"status={self.status.value} "
                f"ttl={self.days_remaining}d>")
