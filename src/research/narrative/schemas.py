"""M3 Narrative Schemas — Narrative detection and reasoning data structures.

V3.2: Upgraded NarrativeObject with causal chain reasoning, evidence classification,
and asset impact analysis — moving from Signal Detection to Narrative Reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class NarrativeCategory(Enum):
    """Narrative category enum (V3.0, kept for backward compat)."""

    MONETARY = "monetary"
    INFLATION = "inflation"
    GROWTH = "growth"
    RISK = "risk"
    CREDIT = "credit"
    SECTORAL = "sectoral"
    GEOPOLITICAL = "geopolitical"
    LIQUIDITY = "liquidity"
    DOLLAR = "dollar"


class NarrativeTimeHorizon(Enum):
    """Time horizon for narrative signals."""

    SHORT_TERM = "short_term"  # 1-2 weeks
    MEDIUM_TERM = "medium_term"  # 1-3 months
    LONG_TERM = "long_term"  # 3+ months
    SHORT = "short_term"  # Alias
    MEDIUM = "medium_term"  # Alias
    LONG = "long_term"  # Alias


@dataclass
class NarrativeSignal:
    """Individual signal supporting a narrative detection."""

    name: str = ""
    value: str = ""  # Signal reading
    direction: str = "neutral"  # bullish / bearish / neutral
    strength: float = 0.5  # 0-1
    source: str = ""  # "macro_data" / "model" / "inference"
    interpretation: str = ""  # Human-readable explanation


@dataclass
class NarrativeTemplate:
    """Pre-defined narrative pattern for template-based detection."""

    title_template: str
    category: NarrativeCategory
    description_template: str = ""
    time_horizon: NarrativeTimeHorizon = field(default=NarrativeTimeHorizon.MEDIUM_TERM)
    required_dimensions: list[str] = field(default_factory=list)
    required_directions: list[str] = field(default_factory=list)
    affected_assets: list[str] = field(default_factory=list)
    base_confidence: float = 0.5
    # Backward compat aliases
    trigger_signals: list[str] = field(default_factory=list)
    signal_conditions: dict[str, str] = field(default_factory=dict)
    base_score: float = 0.5

    def match(self, state_vector: dict, conclusions: list | None = None) -> float:
        """Compute match score between this template and current state.

        Scoring formula:
          dimension_match × 0.6 + direction_match × 0.4

        Returns 0-1 float.
        """
        if not self.required_dimensions:
            return self.base_confidence

        dim_score = 0.0
        dir_score = 0.0
        n = len(self.required_dimensions)

        for dim in self.required_dimensions:
            # Try multiple key formats
            dim_data = state_vector.get(
                dim, state_vector.get(dim.lower(), state_vector.get(dim.replace("_", " "), {}))
            )

            if isinstance(dim_data, dict) and dim_data.get("score") is not None:
                # Dimension exists: base dimension match
                dim_score += 1.0 / n

                # Direction alignment
                actual_dir = str(dim_data.get("direction", "")).lower()
                for expected_dir in self.required_directions:
                    if expected_dir.lower() in actual_dir:
                        dir_score += 1.0 / n
                        break
            elif isinstance(dim_data, (int, float)):
                dim_score += 1.0 / n
                direction_raw = str(state_vector.get(f"{dim}_direction", {}))
                for expected_dir in self.required_directions:
                    if expected_dir.lower() in direction_raw.lower():
                        dir_score += 1.0 / n
                        break

        # If no required directions specified, full marks for direction
        if not self.required_directions:
            dir_score = 1.0

        return dim_score * 0.6 + dir_score * 0.4


# ─────────────── Existing V3.0/V3.1 Schemas (kept for backward compat) ────────────


@dataclass
class Narrative:
    """Detected market narrative (V3.2 extended — supports both flat and rich usage)."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    title: str = ""
    description: str = ""
    category: str = ""  # e.g. "monetary", "growth", "inflation"
    score: float = 0.0  # 0-1 detection confidence
    source_signals: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Backward compat
    is_active: bool = True
    composite_score: float = 0.0
    # V3.2 extended fields (may be passed by template matcher, belief engine, etc.)
    strength: float = 0.0
    time_horizon: str = ""
    affected_assets: list[str] = field(default_factory=list)
    source_list: list[str] = field(default_factory=list)
    market_consensus: float = 0.5
    supporting_models: list[str] = field(default_factory=list)
    contradicting_models: list[str] = field(default_factory=list)
    supporting_signals: list[NarrativeSignal] = field(default_factory=list)
    novelty_score: float = 0.0

    @property
    def confidence(self) -> float:
        """Backward compat alias — some callers use `confidence` for `score`."""
        return self.score

    @confidence.setter
    def confidence(self, value: float) -> None:
        self.score = value

    def compute_composite_score(self) -> None:
        """Compute composite confidence score from signals and base score."""
        self.composite_score = self.score


@dataclass
class NarrativeResult:
    """Output from NarrativeDetector.detect()."""

    narratives: list[Narrative] = field(default_factory=list)
    dominant_narrative: Narrative | None = None
    regime_context: str = ""
    summary: str = ""


# ─────────────── V3.2: NarrativeObject — Rich Narrative Reasoning ────────────


@dataclass
class NarrativeObject:
    """V3.2 Rich Narrative — from Signal Detection to Narrative Reasoning.

    Unlike flat Narrative (V3.0), NarrativeObject captures:
    - Causal chain reasoning (WHY, not just WHAT)
    - Supporting AND contradicting evidence
    - Affected assets with direction
    - Regime context
    - Source diversity metric

    Example output:
        NarrativeObject(
            title="Liquidity tightening is dominating risk assets",
            causal_chain=[
                "DXY↑ + Real Yield↑",
                "→ Financial Conditions Tighten",
                "→ Risk Appetite Declines",
                "→ Equity Multiple Compression",
            ],
            affected_assets=["NASDAQ (-)", "HYG (-)", "Copper (-)"],
            confidence=0.72,
        )
    """

    id: str = field(default_factory=lambda: uuid4().hex[:12])
    title: str = ""
    description: str = ""

    # ── Causal Reasoning (V3.2 core) ───────────────────────────────
    causal_chain: list[str] = field(default_factory=list)
    """Ordered causal steps from driver → outcome.
    e.g. ["DXY↑ + Real Yield↑", "→ Financial Conditions Tighten", ...]"""

    # ── Evidence (bidirectional) ───────────────────────────────────
    supporting_evidence: list[str] = field(default_factory=list)
    """Facts/data that support this narrative."""

    contradicting_evidence: list[str] = field(default_factory=list)
    """Facts/data that challenge this narrative."""

    # ── Asset Impact ───────────────────────────────────────────────
    affected_assets: list[str] = field(default_factory=list)
    """Assets affected with direction, e.g. "NASDAQ (-)", "HYG (-)", "Gold (+)"."""

    # ── Classification ─────────────────────────────────────────────
    category: str = ""  # monetary, growth, inflation, risk, etc.
    regime: str = ""  # Current regime this narrative operates in
    regime_score: float = 0.0  # 0-1: how well narrative fits current regime

    # ── Confidence & Diversity ─────────────────────────────────────
    confidence: float = 0.5  # 0-1: overall confidence
    source_diversity: float = 0.0  # 0-1: how many independent sources support this

    # ── Competition ────────────────────────────────────────────────
    competing_narrative_ids: list[str] = field(default_factory=list)
    probability: float = 0.0  # Competition weight (0-1)

    # ── Meta ───────────────────────────────────────────────────────
    derived_from: list[str] = field(default_factory=list)  # source Narrative IDs
    mental_models_used: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def evidence_ratio(self) -> float:
        """Supporting / total evidence ratio."""
        total = len(self.supporting_evidence) + len(self.contradicting_evidence)
        if total == 0:
            return 0.5
        return len(self.supporting_evidence) / total

    @property
    def causal_depth(self) -> int:
        """Number of reasoning steps in causal chain."""
        return len(self.causal_chain)

    @property
    def is_robust(self) -> bool:
        """Narrative is robust if confidence > 0.6 and has causal reasoning."""
        return self.confidence >= 0.6 and self.causal_depth >= 2

    @property
    def is_contested(self) -> bool:
        """Has significant contradicting evidence."""
        return len(self.contradicting_evidence) > 0 and self.evidence_ratio < 0.7

    @property
    def asset_count(self) -> int:
        return len(self.affected_assets)

    def summary(self) -> str:
        """One-line summary."""
        return (
            f"[{self.category}] {self.title} "
            f"(c={self.confidence:.0%}, depth={self.causal_depth}, "
            f"assets={self.asset_count}, diversity={self.source_diversity:.0%})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "causal_chain": self.causal_chain,
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "affected_assets": self.affected_assets,
            "category": self.category,
            "regime": self.regime,
            "regime_score": self.regime_score,
            "confidence": self.confidence,
            "source_diversity": self.source_diversity,
            "competing_narrative_ids": self.competing_narrative_ids,
            "probability": self.probability,
            "derived_from": self.derived_from,
            "mental_models_used": self.mental_models_used,
            "created_at": self.created_at.isoformat(),
            "evidence_ratio": self.evidence_ratio,
            "causal_depth": self.causal_depth,
            "is_robust": self.is_robust,
            "is_contested": self.is_contested,
        }


@dataclass
class NarrativeCompetitionResult:
    """Output from NarrativeCompetition.competing_narratives()."""

    market_state_summary: str = ""
    regime: str = ""
    narratives: list[NarrativeObject] = field(default_factory=list)
    """Ordered by probability descending."""

    @property
    def dominant(self) -> NarrativeObject | None:
        return self.narratives[0] if self.narratives else None

    @property
    def alternatives(self) -> list[NarrativeObject]:
        return self.narratives[1:] if len(self.narratives) > 1 else []

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_state_summary": self.market_state_summary,
            "regime": self.regime,
            "narratives": [n.to_dict() for n in self.narratives],
            "narrative_count": len(self.narratives),
        }
