"""V3.1 Transmission Learning Schemas — Transmission Graph & Breakpoint Diagnosis.

Milestone B + B.5: Transmission Reasoning + Research Findings Engine.

Key design upgrades (from B → B.5):
    - TransmissionEdge: 5 attributes per edge (not just reliability)
        [Reliability | Latency | Strength | Failure Modes | Evidence Count]
    - Transmission Competition: multiple mechanisms between same source→target
    - Research Note: diagnosis output as researcher prose, not debug log
    - Research Finding: structured finding from accumulated diagnosis history
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

# ═══════════════════════════════════════════════════════════════════════════════
# Failure Mode
# ═══════════════════════════════════════════════════════════════════════════════


class FailureModeCategory(str, Enum):
    """Category of transmission failure."""

    EVENT_OVERRIDE = "event_override"  # External event suppressed transmission
    REGIME_INCOMPATIBLE = "regime_incompatible"  # Not valid in current regime
    THRESHOLD_NONLINEAR = "threshold_nonlinear"  # Diminishing returns at extremes
    STRUCTURAL_BREAK = "structural_break"  # Relationship fundamentally changed
    SIGNAL_NOISE = "signal_noise"  # Normal fluctuation, no structural issue
    COMPETITION_LOSS = "competition_loss"  # Alternative mechanism dominated
    UNKNOWN = "unknown"  # Not yet classified


class TransmissionAction(str, Enum):
    """Action to apply to a transmission edge."""

    REINFORCE = "reinforce"  # Transmission succeeded → reliability up
    WEAKEN = "weaken"  # Transmission broke → reliability down
    REGISTER_FAILURE = "register_failure"  # New failure mode discovered
    ADD_CONDITION = "add_condition"  # New validity condition discovered
    PROMOTE_MECHANISM = "promote_mechanism"  # This mechanism won competition
    DEMOTE_MECHANISM = "demote_mechanism"  # This mechanism lost competition
    NO_CHANGE = "no_change"  # No significant update needed


# ═══════════════════════════════════════════════════════════════════════════════
# Failure Mode Record
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class FailureMode:
    """A recorded failure pattern on a transmission edge."""

    mode_id: str = field(default_factory=lambda: f"fm-{uuid4().hex[:8]}")
    category: FailureModeCategory = FailureModeCategory.UNKNOWN
    name: str = ""  # Named failure: "Treasury Supply Shock", "VIX Spike"
    condition: dict = field(default_factory=dict)
    # e.g. {"vix_threshold": 30, "fiscal_dominance": True}
    description: str = ""
    occurrence_count: int = 0
    first_observed: datetime | None = None
    last_observed: datetime | None = None

    def __repr__(self) -> str:
        return f"<FailureMode {self.name or self.category.value} x{self.occurrence_count}>"


# ═══════════════════════════════════════════════════════════════════════════════
# Transmission Edge — Five Attributes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TransmissionEdge:
    """A transmission edge between two macro nodes, with 5 key attributes.

    Five Attributes (the "research-quality edge"):
    ┌──────────────┬──────────────────────────────────────────────────┐
    │ Attribute    │ Meaning                                          │
    ├──────────────┼──────────────────────────────────────────────────┤
    │ Reliability  │ How often the edge transmits correctly (0-1)     │
    │ Latency      │ Typical transmission delay in days              │
    │ Strength     │ Correlation strength / effect size (0-1)        │
    │ FailureModes │ Named patterns of why it breaks                 │
    │ EvidenceCnt  │ How many observations support this estimate     │
    └──────────────┴──────────────────────────────────────────────────┘

    Competition support:
        Multiple edges can exist between the same (source, target) pair,
        differentiated by `mechanism`. This enables the agent to learn
        WHICH mechanism dominates under which conditions.

    Example: Dollar → Gold
        Edge A: mechanism="real_yield_channel"   (Dollar↓ → RealYield↓ → Gold↑)
        Edge B: mechanism="liquidity_channel"     (Dollar↓ → Liquidity↑ → Gold↑)
        → Agent learns: mechanism A dominates in rate-drive markets;
          mechanism B dominates in liquidity-drive markets.
    """

    edge_id: str = ""
    source: str = ""  # e.g. "liquidity", "credit", "Dollar"
    target: str = ""  # e.g. "NASDAQ", "Gold"
    direction: str = "+"  # "+" (positive corr) / "-" (negative corr)
    mechanism: str = ""  # Named transmission mechanism (for competition)

    # ── Five Attributes ──────────────────────────────────────────────────
    # 1. Reliability: P(transmission succeeds) in [0, 1]
    reliability_default: float = 0.50
    reliability_by_context: dict[str, float] = field(default_factory=dict)

    # 2. Latency: typical transmission delay in days (numeric)
    latency_days: int = 5
    latency_range: tuple[int, int] = (2, 14)  # (min, max) observed latency

    # 3. Strength: correlation / effect size, 0=no effect, 1=deterministic
    edge_strength: float = 0.50  # Base correlation strength
    strength_by_context: dict[str, float] = field(default_factory=dict)

    # 4. Failure Modes: named patterns of why it breaks
    failure_modes: list[FailureMode] = field(default_factory=list)

    # 5. Evidence Count: observation count for statistical confidence
    observation_count: int = 0
    success_count: int = 0
    break_count: int = 0

    # Validity conditions
    conditions_for_validity: list[str] = field(default_factory=list)

    # Metadata
    last_updated: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def segment_id(self) -> str:
        """Unique segment identifier including mechanism for competition support."""
        base = f"{self.source}→{self.target}"
        return f"{base}[{self.mechanism}]" if self.mechanism else base

    @property
    def key(self) -> str:
        """Short key for lookup."""
        return self.segment_id

    @property
    def recent_reliability(self) -> float:
        """Recent success rate."""
        if self.observation_count == 0:
            return self.reliability_default
        return self.success_count / max(self.observation_count, 1)

    @property
    def break_rate(self) -> float:
        if self.observation_count == 0:
            return 0.0
        return self.break_count / self.observation_count

    @property
    def evidence_count(self) -> int:
        """Alias: how many data points support this edge estimate."""
        return self.observation_count

    @property
    def named_failure_modes(self) -> list[str]:
        """Just the names of failure modes, for display."""
        return [fm.name for fm in self.failure_modes if fm.name]

    @property
    def dominant_failure_mode(self) -> FailureMode | None:
        """The most frequently observed failure mode."""
        if not self.failure_modes:
            return None
        return max(self.failure_modes, key=lambda fm: fm.occurrence_count)

    def reliability_in_context(self, context_key: str) -> float:
        return self.reliability_by_context.get(context_key, self.reliability_default)

    def strength_in_context(self, context_key: str) -> float:
        return self.strength_by_context.get(context_key, self.edge_strength)

    def is_stable(self, recent_window: int = 20) -> bool:
        if self.observation_count < recent_window:
            return False
        return self.break_rate < 0.2

    def confidence(self) -> float:
        """Statistical confidence based on evidence count."""
        if self.observation_count < 5:
            return 0.2
        if self.observation_count < 20:
            return 0.5
        if self.observation_count < 50:
            return 0.7
        return min(0.95, self.observation_count / 80)

    def quality_score(self) -> float:
        """Composite edge quality: f(reliability, strength, confidence, stability).

        Used for ranking edges in research findings.
        """
        rel = self.reliability_default
        strength = self.edge_strength
        conf = self.confidence()
        stability = 1.0 - min(self.break_rate, 0.5) * 2  # 0=unstable, 1=stable
        return round(0.35 * rel + 0.30 * strength + 0.20 * conf + 0.15 * stability, 4)

    def describe(self) -> str:
        """Human-readable edge description (research-note style)."""
        parts = [f"{self.segment_id}: rel={self.reliability_default:.2f}"]
        if self.mechanism:
            parts.append(f"mechanism={self.mechanism}")
        parts.append(f"strength={self.edge_strength:.2f}")
        parts.append(f"latency={self.latency_days}d")
        parts.append(f"evidence={self.observation_count}")
        if self.named_failure_modes:
            parts.append(f"failures=[{', '.join(self.named_failure_modes[:3])}]")
        return " ".join(parts)

    def __repr__(self) -> str:
        mech = f" [{self.mechanism}]" if self.mechanism else ""
        return (
            f"<TransmissionEdge {self.source}→{self.target}{mech} "
            f"rel={self.reliability_default:.2f} "
            f"str={self.edge_strength:.2f} "
            f"lat={self.latency_days}d "
            f"obs={self.observation_count}>"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Segment Diagnosis & Breakpoint
# ═══════════════════════════════════════════════════════════════════════════════


class BreakpointSeverity(str, Enum):
    MINOR = "minor"
    SIGNIFICANT = "significant"
    CRITICAL = "critical"
    STRUCTURAL = "structural"


@dataclass
class SegmentDiagnosis:
    """Diagnosis of a single transmission segment's performance."""

    segment_id: str = ""
    source: str = ""
    target: str = ""
    mechanism: str = ""  # Which mechanism (for competition edges)
    expected_direction: str = ""
    actual_direction: str = ""
    transmitted_correctly: bool = False
    is_breakpoint: bool = False
    breakpoint_severity: BreakpointSeverity | None = None
    matched_failure_mode: str | None = None
    evidence: dict = field(default_factory=dict)
    diagnosis_rationale: str = ""


@dataclass
class BreakpointDiagnosis:
    """Root cause discovery result for a failed prediction.

    Answers: "Where in the transmission chain did the break occur, and why?"

    Upgraded for B.5: now includes mechanism-level detail for competition analysis.
    """

    diagnosis_id: str = field(default_factory=lambda: f"bpd-{uuid4().hex[:8]}")
    source_hypothesis_id: str = ""
    prediction_id: str = ""
    transmission_channel: str = ""

    expected_chain: list[str] = field(default_factory=list)
    segment_diagnoses: list[SegmentDiagnosis] = field(default_factory=list)

    breakpoint_found: bool = False
    breakpoint_segment: str = ""
    root_cause_category: FailureModeCategory = FailureModeCategory.UNKNOWN
    root_cause_description: str = ""

    all_segments_healthy: bool = False
    suggested_action: TransmissionAction = TransmissionAction.NO_CHANGE
    new_failure_mode: FailureMode | None = None

    # Competition tracking (Milestone B.5)
    competing_mechanisms: list[str] = field(default_factory=list)
    winning_mechanism: str = ""  # Which mechanism actually transmitted
    losing_mechanisms: list[str] = field(default_factory=list)

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_actionable(self) -> bool:
        return self.breakpoint_found and self.suggested_action != TransmissionAction.NO_CHANGE

    def describe(self) -> str:
        parts = []
        for sd in self.segment_diagnoses:
            status = "[OK]" if sd.transmitted_correctly else "[BROKEN]"
            marker = " ◀ BREAKPOINT" if sd.is_breakpoint else ""
            parts.append(f"  {status} {sd.segment_id}: {sd.diagnosis_rationale}{marker}")
        chain_desc = " → ".join(sd.segment_id for sd in self.segment_diagnoses)
        brk = f"\n  Breakpoint: {self.breakpoint_segment}" if self.breakpoint_found else ""
        root = (
            f"\n  Root cause: {self.root_cause_description}" if self.root_cause_description else ""
        )
        comp = ""
        if self.winning_mechanism:
            comp = f"\n  Winning mechanism: {self.winning_mechanism}"
            if self.losing_mechanisms:
                comp += f" (lost: {', '.join(self.losing_mechanisms)})"
        return f"Chain: {chain_desc}\n" + "\n".join(parts) + brk + root + comp

    def __repr__(self) -> str:
        health = (
            "healthy"
            if self.all_segments_healthy
            else f"broken_at={self.breakpoint_segment}" if self.breakpoint_found else "diagnosed"
        )
        return f"<BreakpointDiagnosis {health} cat={self.root_cause_category.value}>"


# ═══════════════════════════════════════════════════════════════════════════════
# Research Note (replaces "Breakpoint" as diagnosis output)
# ═══════════════════════════════════════════════════════════════════════════════


class FindingConfidence(str, Enum):
    """How confident is this research finding."""

    PRELIMINARY = "preliminary"  # < 20 observations
    OBSERVED = "observed"  # 20-50 observations
    ESTABLISHED = "established"  # 50-100 observations
    ROBUST = "robust"  # > 100 observations


@dataclass
class ResearchNote:
    """A human-readable research finding synthesized from transmission data.

    This is what replaces the "breakpoint" log — it reads like a research memo,
    not a debug trace. The agent's output becomes:

        "Historically, Credit→Capex works 82%. During High VIX only 31%.
         Current Regime: VIX 34. Therefore: This transmission should be discounted."

    Instead of:

        "Breakpoint found at credit→capex, severity=significant"
    """

    note_id: str = field(default_factory=lambda: f"rn-{uuid4().hex[:8]}")

    # What edge / mechanism
    segment_id: str = ""
    source: str = ""
    target: str = ""
    mechanism: str = ""

    # The finding (researcher prose)
    headline: str = ""  # One-line summary
    narrative: str = ""  # Full research-note style paragraph
    key_numbers: dict = field(default_factory=dict)
    # e.g. {"baseline_reliability": 0.82, "regime_reliability": 0.31, "current_vix": 34}

    # Source data
    source_diagnosis_id: str = ""
    context_key: str = ""
    evidence_count: int = 0
    confidence: FindingConfidence = FindingConfidence.PRELIMINARY

    # Actionable insight
    recommendation: str = ""  # What the agent should do
    competing_notes: list[str] = field(default_factory=list)  # IDs of competing research notes

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def describe(self) -> str:
        return (
            f"[{self.confidence.value.upper()}] {self.headline}\n"
            f"{self.narrative}\n"
            f"Recommendation: {self.recommendation}"
        )

    def __repr__(self) -> str:
        return f"<ResearchNote {self.headline[:60]}>"


# ═══════════════════════════════════════════════════════════════════════════════
# Research Finding (Milestone B.5)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ResearchFinding:
    """A structured research finding derived from accumulated transmission history.

    Four categories of findings:
        F1: Most reliable transmission in current regime
        F2: Recently failing transmissions (early warning)
        F3: Failure event correlation (what breaks a given transmission)
        F4: Historical regime similarity (when was the last time it looked like this?)
    """

    finding_id: str = field(default_factory=lambda: f"rf-{uuid4().hex[:8]}")
    category: str = ""  # "reliability_ranking" | "failure_warning" |
    # "failure_event_correlation" | "regime_similarity"

    # Human-readable
    title: str = ""  # "Liquidity→Credit is strongest in easing regime"
    description: str = ""  # Full research prose
    evidence: dict = field(default_factory=dict)
    # Supporting data: {transmission: weights, regime_comparison: {...}, etc.}

    # Scoring
    relevance_score: float = 0.0  # How relevant is this finding RIGHT NOW
    confidence: FindingConfidence = FindingConfidence.PRELIMINARY

    # Source
    source_edges: list[str] = field(default_factory=list)
    source_notes: list[str] = field(default_factory=list)
    context_key: str = ""

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"<ResearchFinding [{self.category}] {self.title[:50]}>"


@dataclass
class ResearchFindingsReport:
    """Aggregated research findings from a transmission analysis cycle.

    This is the output of the Research Findings Engine (Milestone B.5).
    It produces a structured research memo that the agent (and eventually,
    the human user in V4) can read to understand WHY the agent thinks
    what it thinks.
    """

    report_id: str = field(default_factory=lambda: f"rfr-{uuid4().hex[:8]}")
    context_key: str = ""
    cycle_number: int = 0

    # Top findings by category
    reliability_ranking: list[ResearchFinding] = field(default_factory=list)
    failure_warnings: list[ResearchFinding] = field(default_factory=list)
    failure_event_correlations: list[ResearchFinding] = field(default_factory=list)
    regime_similarities: list[ResearchFinding] = field(default_factory=list)

    # Edge-level research notes
    research_notes: list[ResearchNote] = field(default_factory=list)

    # Summary
    summary: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def total_findings(self) -> int:
        return (
            len(self.reliability_ranking)
            + len(self.failure_warnings)
            + len(self.failure_event_correlations)
            + len(self.regime_similarities)
        )

    @property
    def total_notes(self) -> int:
        return len(self.research_notes)

    def describe(self) -> str:
        lines = [
            f"=== Research Findings Report [{self.context_key}] ===\n",
        ]
        if self.summary:
            lines.append(f"{self.summary}\n")

        if self.reliability_ranking:
            lines.append("── Most Reliable Transmissions ──")
            for f in self.reliability_ranking[:3]:
                lines.append(f"  {f.title}")
                lines.append(f"  {f.description}")
            lines.append("")

        if self.failure_warnings:
            lines.append("── Early Warning: Failing Transmissions ──")
            for f in self.failure_warnings[:3]:
                lines.append(f"  {f.title}")
                lines.append(f"  {f.description}")
            lines.append("")

        if self.failure_event_correlations:
            lines.append("── Failure Event Correlations ──")
            for f in self.failure_event_correlations[:3]:
                lines.append(f"  {f.title}")
            lines.append("")

        if self.regime_similarities:
            lines.append("── Regime Similarities ──")
            for f in self.regime_similarities[:3]:
                lines.append(f"  {f.title}")

        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"<ResearchFindingsReport ctx={self.context_key} "
            f"findings={self.total_findings} notes={self.total_notes}>"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Transmission Update
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TransmissionUpdateRecord:
    """A single update to a transmission edge, cascaded from prediction outcome."""

    update_id: str = field(default_factory=lambda: f"tup-{uuid4().hex[:8]}")
    run_id: str = ""

    segment_id: str = ""
    source: str = ""
    target: str = ""
    mechanism: str = ""

    action: TransmissionAction = TransmissionAction.NO_CHANGE
    context_key: str = ""

    # Reliability
    reliability_delta: float = 0.0
    context_reliability_delta: float = 0.0
    new_reliability: float = 0.0

    # Strength
    strength_delta: float = 0.0

    # Competition
    competition_delta: float = 0.0  # Boost/demote for mechanism competition

    # Failure
    failure_category: FailureModeCategory | None = None
    failure_description: str = ""

    breakpoint_diagnosis_id: str = ""
    reason: str = ""

    # Cascade
    affected_belief_ids: list[str] = field(default_factory=list)

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return (
            f"<TransmissionUpdate {self.segment_id} "
            f"action={self.action.value} "
            f"delta={self.reliability_delta:+.3f}>"
        )


@dataclass
class TransmissionUpdateBatch:
    """Collection of transmission updates from a single evaluation cycle."""

    batch_id: str = field(default_factory=lambda: f"tub-{uuid4().hex[:8]}")
    run_id: str = ""
    updates: list[TransmissionUpdateRecord] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def total_reinforcements(self) -> int:
        return sum(1 for u in self.updates if u.action == TransmissionAction.REINFORCE)

    @property
    def total_weakenings(self) -> int:
        return sum(1 for u in self.updates if u.action == TransmissionAction.WEAKEN)

    @property
    def total_failure_registrations(self) -> int:
        return sum(1 for u in self.updates if u.action == TransmissionAction.REGISTER_FAILURE)

    @property
    def total_competition_updates(self) -> int:
        return sum(
            1
            for u in self.updates
            if u.action
            in (TransmissionAction.PROMOTE_MECHANISM, TransmissionAction.DEMOTE_MECHANISM)
        )

    @property
    def affected_segments(self) -> set[str]:
        return {u.segment_id for u in self.updates}

    @property
    def affected_beliefs(self) -> list[str]:
        result = []
        for u in self.updates:
            result.extend(u.affected_belief_ids)
        return list(set(result))

    def summary(self) -> str:
        comp = (
            f", {self.total_competition_updates} competition"
            if self.total_competition_updates
            else ""
        )
        return (
            f"TransmissionUpdateBatch: {len(self.updates)} updates "
            f"({self.total_reinforcements} reinforce, "
            f"{self.total_weakenings} weaken, "
            f"{self.total_failure_registrations} new failures{comp}) "
            f"→ {len(self.affected_beliefs)} beliefs affected"
        )

    def __repr__(self) -> str:
        return f"<TransmissionUpdateBatch upd={len(self.updates)} aff={len(self.affected_beliefs)}>"


# ═══════════════════════════════════════════════════════════════════════════════
# Context-aware Belief (Transmission-linked)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ContextProfile:
    """A belief's behavior in a specific macro context."""

    context_id: str = ""
    context_key: str = ""
    context_description: str = ""

    regime: str = ""
    conditions: dict = field(default_factory=dict)

    active_transmission_segments: list[str] = field(default_factory=list)
    inactive_segments: list[str] = field(default_factory=list)

    derived_weight: float = 0.50
    derived_confidence: float = 0.50

    sample_count: int = 0
    success_count: int = 0
    historical_accuracy: float = 0.0

    @property
    def is_stable(self) -> bool:
        return self.sample_count >= 10 and self.historical_accuracy > 0.5


@dataclass
class ContextualBelief:
    """A belief whose weight depends on context and transmission chain reliability."""

    belief_id: str = ""
    dimension: str = ""
    hypothesis_text: str = ""

    contexts: dict[str, ContextProfile] = field(default_factory=dict)
    default_context_key: str = "default"

    discovery_enabled: bool = True
    min_samples_for_split: int = 15

    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_updated: datetime | None = None

    def active_weight(self, context_key: str) -> float:
        profile = self.contexts.get(context_key)
        if profile and profile.sample_count > 0:
            return profile.derived_weight
        default = self.contexts.get(self.default_context_key)
        return default.derived_weight if default else 0.50

    def active_confidence(self, context_key: str) -> float:
        profile = self.contexts.get(context_key)
        if profile and profile.sample_count > 0:
            return profile.derived_confidence
        default = self.contexts.get(self.default_context_key)
        return default.derived_confidence if default else 0.50

    def active_segments(self, context_key: str) -> list[str]:
        profile = self.contexts.get(context_key)
        return profile.active_transmission_segments if profile else []

    @property
    def total_samples(self) -> int:
        return sum(c.sample_count for c in self.contexts.values())

    def __repr__(self) -> str:
        return (
            f"<ContextualBelief {self.belief_id[:12]} "
            f"dim={self.dimension} "
            f"contexts={len(self.contexts)} "
            f"total_obs={self.total_samples}>"
        )
