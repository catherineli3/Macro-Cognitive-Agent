"""MacroSignalSchema — The data contract for Signal Engine output.

Sprint 2 defines the canonical signal format. Every signal in the system
MUST conform to this schema. No dict or DataFrame across module boundaries.
"""

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

# ── Shared enums ─────────────────────────────────────────────────────────


class SignalDirection(str, Enum):
    """Market-implied direction of the signal."""

    BULLISH = "bullish"  # Positive for risk assets / accommodative conditions
    BEARISH = "bearish"  # Negative for risk assets / tightening conditions
    NEUTRAL = "neutral"  # No clear directional bias


class SignalStrength(str, Enum):
    """Confidence-weighted severity of the signal."""

    STRONG = "strong"  # Clear rule breach, high confidence
    MODERATE = "moderate"  # Rule breach, medium confidence
    WEAK = "weak"  # Borderline breach, low confidence


# ── Evidence ──────────────────────────────────────────────────────────────


class SignalEvidence(BaseModel):
    """Structured evidence explaining WHY a signal was generated.

    This is the explainability foundation. Every signal carries its
    full provenance — what rule fired, what value triggered it, and
    the financial interpretation in plain language.
    """

    rule_id: str = Field(..., description="Unique rule identifier, e.g. 'threshold_dxy_strong'")
    rule_description: str = Field(..., description="Human-readable rule description")
    input_value: float = Field(..., description="Actual observed value that triggered the rule")
    condition: str = Field(
        ..., description="The condition that was evaluated, e.g. 'value > 105.0'"
    )
    interpretation: str = Field(
        ...,
        description="Financial meaning in plain language, e.g. 'Financial Conditions Tightening'",
    )
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the rule was evaluated",
    )


# ── Signal Schema ─────────────────────────────────────────────────────────


class MacroSignalSchema(BaseModel):
    """Canonical data contract for a single macro signal.

    A signal answers: "What is happening?" based on observed macro data
    and explicit, deterministic rules. It does NOT answer "Why?" or
    "What will happen?" — those belong to later Sprints.

    Design principles:
        - Deterministic: same input → same signal
        - Explainable: evidence field carries full provenance
        - Repeatable: signal_id is deterministically generated
        - Testable: pure data, no side effects
    """

    signal_id: str = Field(
        default_factory=lambda: uuid4().hex[:12],
        description="Unique signal identifier (deterministic in production via hash)",
    )
    indicator: str = Field(
        ..., min_length=1, max_length=20, description="Indicator symbol, e.g. 'DXY'"
    )
    dimension: str = Field(..., description="Hypothesis dimension, e.g. 'Liquidity', 'Credit'")
    direction: SignalDirection = Field(..., description="Market-implied direction")
    strength: SignalStrength = Field(..., description="Signal severity level")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score 0-1")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Signal generation timestamp (timezone-aware)",
    )
    evidence: list[SignalEvidence] = Field(
        default_factory=list,
        description="Structured evidence chain explaining signal provenance",
    )
    data_timestamp: datetime | None = Field(
        default=None,
        description="Timestamp of the input data that generated this signal",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Extensible metadata for future use (e.g. batch_id, source_version)",
    )

    def add_evidence(self, evidence: SignalEvidence) -> None:
        """Append an evidence item to the signal chain."""
        self.evidence.append(evidence)

    def __repr__(self) -> str:
        dim = self.dimension
        d = self.direction.value
        s = self.strength.value
        return f"<Signal {self.indicator} [{dim}] {d}/{s} c={self.confidence:.2f}>"


# ── Batch ─────────────────────────────────────────────────────────────────


class SignalSnapshot(BaseModel):
    """A point-in-time snapshot of all current macro signals.

    Returned by GET /signals/snapshot — represents the complete
    macro signal picture at a given moment.
    """

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    signals: list[MacroSignalSchema] = Field(default_factory=list)
    summary: str = Field(default="", description="One-line summary of the macro signal picture")

    @property
    def count(self) -> int:
        return len(self.signals)

    @property
    def dimensions_covered(self) -> list[str]:
        return sorted(set(s.dimension for s in self.signals))


# ── v2.0: Cross-Indicator Reasoning ──────────────────────────────────────────


class CompositeSignal(BaseModel):
    """A composite signal that combines multiple individual signals into one.

    v2.0: Replaces single-indicator analysis with multi-indicator reasoning.
    E.g., DXY↑ + US10Y↑ + JPY↓ + Copper↓ → Liquidity Tightening.
    """

    composite_id: str = Field(
        default_factory=lambda: uuid4().hex[:12],
    )
    theme: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Macro theme name (e.g., 'Liquidity Tightening')",
    )
    description: str = Field(
        default="",
        max_length=512,
        description="Human-readable description of the combined signal",
    )
    source_signals: list[str] = Field(
        default_factory=list,
        description="signal_ids of the constituent individual signals",
    )
    indicators: list[str] = Field(
        default_factory=list,
        description="Indicator names that contributed to this composite",
    )
    dimensions: list[str] = Field(
        default_factory=list,
        description="Dimensions spanned by this composite",
    )

    # ── Combined assessment ────────────────────────────────────────────
    combined_direction: SignalDirection = Field(
        default=SignalDirection.NEUTRAL,
        description="Net direction after combining all constituent signals",
    )
    combined_strength: SignalStrength = Field(
        default=SignalStrength.MODERATE,
    )
    combined_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Aggregated confidence from constituent signals",
    )

    # ── Evidence ───────────────────────────────────────────────────────
    agreement_ratio: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Ratio of signals that agree on direction (1.0 = unanimous)",
    )
    signal_diversity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How diverse the contributing indicators are (high = broad confirmation)",
    )
    contradiction_note: str = Field(
        default="",
        max_length=256,
        description="Any contradictory signals found during composition",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<CompositeSignal [{self.theme}] "
            f"dir={self.combined_direction.value} "
            f"conf={self.combined_confidence:.0%} "
            f"agree={self.agreement_ratio:.0%}>"
        )


class MacroTheme(BaseModel):
    """A high-level macro theme inferred from composite signals.

    v2.0: Answers "What is the macro regime?" by synthesizing cross-indicator
    composites into a small number of actionable themes.

    Examples:
        - Liquidity Tightening
        - Credit Stress
        - Growth Recovery
        - Inflation Resurgence
        - Risk-On
        - Risk-Off
    """

    theme_id: str = Field(
        default_factory=lambda: uuid4().hex[:12],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=64,
    )
    activated: bool = Field(
        default=True,
        description="Whether this theme is currently active",
    )
    activation_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How strongly this theme is activated (0=not, 1=strongly)",
    )

    # ── Signal support ─────────────────────────────────────────────────
    supporting_composites: list[str] = Field(
        default_factory=list,
        description="CompositeSignal IDs that support this theme",
    )
    underlying_indicators: list[str] = Field(
        default_factory=list,
        description="Raw indicator names that contribute to this theme",
    )

    # ── Description ────────────────────────────────────────────────────
    summary: str = Field(
        default="",
        max_length=512,
    )
    implications: str = Field(
        default="",
        max_length=512,
        description="What this theme implies for macro positioning",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        status = "ACTIVE" if self.activated else "inactive"
        return f"<MacroTheme [{self.name}] {status} score={self.activation_score:.0%}>"


class CompositeSignalSnapshot(BaseModel):
    """A point-in-time snapshot of all composite signals and macro themes."""

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    composite_signals: list[CompositeSignal] = Field(default_factory=list)
    macro_themes: list[MacroTheme] = Field(default_factory=list)
    dominant_theme: str | None = Field(
        default=None,
        description="The single most dominant macro theme",
    )

    @property
    def active_themes(self) -> list[MacroTheme]:
        return [t for t in self.macro_themes if t.activated]

    def __repr__(self) -> str:
        return (
            f"<CompositeSignalSnapshot composites={len(self.composite_signals)} "
            f"themes={len(self.macro_themes)} "
            f"dominant={self.dominant_theme or 'none'}>"
        )
