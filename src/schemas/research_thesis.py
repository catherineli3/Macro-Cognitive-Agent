"""Research Thesis Schema — the final output of the Autonomous Research Cycle (Milestone D).

A Research Thesis is the agent's top-level deliverable, replacing the old Hypothesis
as the primary research output. It bundles:
    - Core causal belief
    - Framework used
    - Transmission chain
    - Supporting evidence
    - Counter arguments
    - Falsifiable invalidation conditions

This is what a PTJ-style macro researcher produces after morning research.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


# ═══════════════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════════════


class ThesisStatus(str, Enum):
    """Lifecycle of a Research Thesis."""
    DRAFT = "draft"             # Generated, not yet output
    ACTIVE = "active"           # Currently being tested by markets
    VALIDATED = "validated"     # Market outcome aligned with thesis
    INVALIDATED = "invalidated" # An invalidation condition triggered
    ARCHIVED = "archived"       # Time-window expired, no trigger
    SUPERSEDED = "superseded"  # Replaced by a newer, better thesis


# ═══════════════════════════════════════════════════════════════════════════════
# Thesis Outcome — records what happened after the thesis was issued
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ThesisOutcome:
    """Record of market validation result for a thesis.

    Set after the expected window passes or an invalidation condition fires.
    """

    thesis_id: str = ""
    verified: bool = False
    # Which invalidation condition triggered (None if validated)
    invalidation_triggered: str | None = None
    # Realized return in the relevant asset (optional)
    realized_return: float | None = None
    # When the outcome was determined
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Detailed outcome notes
    actual_events: list[str] = field(default_factory=list)
    transmission_verified: bool | None = None  # Was the chain correct?
    timing_correct: bool | None = None         # Was the window right?
    notes: str = ""

    @property
    def is_success(self) -> bool:
        return self.verified and not self.invalidation_triggered

    def describe(self) -> str:
        if self.verified:
            base = "VALIDATED"
        elif self.invalidation_triggered:
            base = f"INVALIDATED (trigger: {self.invalidation_triggered})"
        else:
            base = "PENDING"
        if self.realized_return is not None:
            base += f" | return: {self.realized_return:+.2%}"
        return base


# ═══════════════════════════════════════════════════════════════════════════════
# Research Thesis — the agent's final output
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ResearchThesis:
    """The final output of a research cycle.

    A Research Thesis is the agent's structured macro view, including:
    - What it believes and why
    - Which framework supports it
    - How the transmission mechanism works
    - What evidence supports it
    - What would prove it wrong
    - How confident it is
    - When it expects to be validated or invalidated

    This is NOT a prediction ("NASDAQ +5%"). It IS a causal research statement
    ("Liquidity expansion drives long duration assets because...").
    """

    # ── Identity ──────────────────────────────────────────────────────
    thesis_id: str = field(default_factory=lambda: f"thesis-{uuid4().hex[:12]}")
    title: str = ""                         # One-line thesis statement

    # ── Core Content ──────────────────────────────────────────────────
    regime_label: str = ""                  # e.g. "Early Easing"
    core_belief: str = ""                   # The central causal claim
    transmission_chain: list[str] = field(default_factory=list)
    # e.g. ["Fed Balance Sheet ↑", "USD Liquidity ↑", "Credit Spread ↓",
    #       "Long Duration Equities ↑"]

    # ── Evidence ──────────────────────────────────────────────────────
    evidence: list[str] = field(default_factory=list)
    # Supporting observations, 3-7 items
    counter_arguments: list[str] = field(default_factory=list)
    # What could go wrong, 1-3 items
    invalidation_conditions: list[str] = field(default_factory=list)
    # Falsifiable conditions, e.g. "10Y > 5%" or "Credit spread widening"

    # ── Confidence ────────────────────────────────────────────────────
    confidence: float = 0.0                 # 0.0 ~ 1.0
    expected_window: str = ""              # e.g. "30-90 days"

    # ── Provenance ────────────────────────────────────────────────────
    framework_used: list[str] = field(default_factory=list)
    # framework_ids that generated this thesis
    generated_hypotheses: list[str] = field(default_factory=list)
    # hypothesis_ids linked to this thesis
    source_principles: list[str] = field(default_factory=list)
    # principle_ids that informed this thesis

    # ── Lifecycle ─────────────────────────────────────────────────────
    status: ThesisStatus = ThesisStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    activated_at: datetime | None = None
    outcome: ThesisOutcome | None = None

    # ── Metadata ──────────────────────────────────────────────────────
    metadata: dict = field(default_factory=dict)

    # ── Properties ────────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self.status == ThesisStatus.ACTIVE

    @property
    def is_resolved(self) -> bool:
        return self.status in (
            ThesisStatus.VALIDATED,
            ThesisStatus.INVALIDATED,
            ThesisStatus.ARCHIVED,
        )

    @property
    def has_outcome(self) -> bool:
        return self.outcome is not None

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    @property
    def chain_depth(self) -> int:
        return len(self.transmission_chain)

    @property
    def is_well_formed(self) -> bool:
        """A thesis is well-formed if it has all critical components."""
        return bool(
            self.title
            and self.core_belief
            and len(self.transmission_chain) >= 2
            and len(self.evidence) >= 2
            and len(self.invalidation_conditions) >= 1
            and self.confidence > 0
        )

    # ── Lifecycle Methods ─────────────────────────────────────────────

    def activate(self) -> None:
        """Mark the thesis as active (being tested by markets)."""
        self.status = ThesisStatus.ACTIVE
        self.activated_at = datetime.now(timezone.utc)

    def validate(self, outcome: ThesisOutcome | None = None) -> None:
        """Mark as validated by market outcome."""
        self.status = ThesisStatus.VALIDATED
        if outcome:
            outcome.verified = True
            self.outcome = outcome

    def invalidate(self, triggered_condition: str,
                   outcome: ThesisOutcome | None = None) -> None:
        """Mark as invalidated by a specific condition."""
        self.status = ThesisStatus.INVALIDATED
        if outcome:
            outcome.invalidation_triggered = triggered_condition
            self.outcome = outcome
        else:
            self.outcome = ThesisOutcome(
                thesis_id=self.thesis_id,
                verified=False,
                invalidation_triggered=triggered_condition,
            )

    def archive(self, reason: str = "") -> None:
        """Archive without validation/invalidation."""
        self.status = ThesisStatus.ARCHIVED
        self.metadata["archive_reason"] = reason

    def supersede(self, new_thesis_id: str) -> None:
        """Mark as superseded by a newer thesis."""
        self.status = ThesisStatus.SUPERSEDED
        self.metadata["superseded_by"] = new_thesis_id

    # ── Serialization ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "thesis_id": self.thesis_id,
            "title": self.title,
            "regime_label": self.regime_label,
            "core_belief": self.core_belief,
            "transmission_chain": self.transmission_chain,
            "evidence": self.evidence,
            "counter_arguments": self.counter_arguments,
            "invalidation_conditions": self.invalidation_conditions,
            "confidence": self.confidence,
            "expected_window": self.expected_window,
            "framework_used": self.framework_used,
            "generated_hypotheses": self.generated_hypotheses,
            "source_principles": self.source_principles,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "outcome": {
                "verified": self.outcome.verified,
                "invalidation_triggered": self.outcome.invalidation_triggered,
                "notes": self.outcome.notes,
            } if self.outcome else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ResearchThesis:
        outcome = None
        if data.get("outcome"):
            od = data["outcome"]
            outcome = ThesisOutcome(
                thesis_id=data.get("thesis_id", ""),
                verified=od.get("verified", False),
                invalidation_triggered=od.get("invalidation_triggered"),
                notes=od.get("notes", ""),
            )
        thesis = cls(
            thesis_id=data.get("thesis_id", ""),
            title=data.get("title", ""),
            regime_label=data.get("regime_label", ""),
            core_belief=data.get("core_belief", ""),
            transmission_chain=data.get("transmission_chain", []),
            evidence=data.get("evidence", []),
            counter_arguments=data.get("counter_arguments", []),
            invalidation_conditions=data.get("invalidation_conditions", []),
            confidence=data.get("confidence", 0.0),
            expected_window=data.get("expected_window", ""),
            framework_used=data.get("framework_used", []),
            generated_hypotheses=data.get("generated_hypotheses", []),
            source_principles=data.get("source_principles", []),
            status=ThesisStatus(data.get("status", "draft")),
            metadata=data.get("metadata", {}),
        )
        if outcome:
            thesis.outcome = outcome
        return thesis

    # ── Display ───────────────────────────────────────────────────────

    def format(self) -> str:
        """Format the thesis as a human-readable research note."""
        lines = [
            "=" * 60,
            f"RESEARCH THESIS: {self.title}",
            "=" * 60,
            "",
            f"REGIME: {self.regime_label}",
            f"STATUS: {self.status.value.upper()}",
            f"CONFIDENCE: {self.confidence:.0%}",
            f"WINDOW: {self.expected_window}",
            "",
            "CORE BELIEF:",
            f"  {self.core_belief}",
            "",
            "TRANSMISSION CHAIN:",
        ]
        for i, link in enumerate(self.transmission_chain, 1):
            arrow = "  └──" if i == len(self.transmission_chain) else "  ├──"
            lines.append(f"{arrow} {link}")

        lines.append("")
        lines.append("EVIDENCE:")
        for i, e in enumerate(self.evidence, 1):
            lines.append(f"  {i}. {e}")

        if self.counter_arguments:
            lines.append("")
            lines.append("COUNTER ARGUMENTS:")
            for i, ca in enumerate(self.counter_arguments, 1):
                lines.append(f"  {i}. {ca}")

        lines.append("")
        lines.append("INVALIDATION CONDITIONS:")
        for i, ic in enumerate(self.invalidation_conditions, 1):
            lines.append(f"  {i}. {ic}")

        if self.framework_used:
            lines.append("")
            lines.append(f"FRAMEWORKS: {', '.join(self.framework_used)}")

        if self.outcome:
            lines.append("")
            lines.append(f"OUTCOME: {self.outcome.describe()}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<ResearchThesis[{self.status.value}] '{self.title[:40]}...' c={self.confidence:.0%}>"
