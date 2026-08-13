"""MentalModel — base class and shared types for all macro mental models.

Every mental model in the library follows this interface:
    evaluate(snapshot) → ResearchConclusion[]

This ensures all models produce structured, traceable output that
flows directly into the Hypothesis Engine.

Key Design:
    - No model outputs raw strings. Everything is structured.
    - Every conclusion has confidence, evidence, counter-evidence, and assumptions.
    - Narrative seeds are generated for the downstream M3 Narrative Engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# ── Shared Types ────────────────────────────────────────────────────────────


@dataclass
class EvidenceItem:
    """A single piece of evidence supporting or contradicting a conclusion."""

    indicator: str
    value: float
    interpretation: str
    weight: float = 1.0  # Relative importance
    source: str = "MacroPipeline"
    timestamp: datetime | None = None


@dataclass
class ModelInput:
    """Input to a mental model's evaluate() method.

    Contains the full M1 MacroSnapshot dict plus any pre-extracted signals.
    """

    snapshot: dict
    date: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_state_dimension(self, dimension_name: str) -> dict | None:
        """Extract a specific dimension from the state vector."""
        sv = self.snapshot.get("state_vector", {})
        return sv.get(dimension_name)

    def get_indicator(self, name: str) -> dict | None:
        """Get a specific indicator's features from the snapshot."""
        fs = self.snapshot.get("feature_summary", {})
        indicators = fs.get("indicators", {})
        return indicators.get(name.upper())


@dataclass
class ResearchConclusion:
    """A single research conclusion from a mental model.

    This is the UNIVERSAL output format. Every model must produce
    at least one ResearchConclusion.

    Attributes:
        model_name: Which model produced this (e.g., "LiquidityModel").
        domain: Macro domain (e.g., "Liquidity", "Credit").
        conclusion: Human-readable conclusion (e.g., "Liquidity Tightening").
        confidence: 0.0-1.0 confidence score.
        supporting_evidence: Evidence favoring this conclusion.
        contradicting_evidence: Evidence against this conclusion.
        assumptions: Explicit assumptions made.
        narrative_seeds: Possible narrative directions.
        raw_score: Underlying dimension score from state vector.
        direction: Directional label (e.g., "tightening", "expansion").
    """

    model_name: str
    domain: str
    conclusion: str
    confidence: float
    supporting_evidence: list[EvidenceItem] = field(default_factory=list)
    contradicting_evidence: list[EvidenceItem] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    narrative_seeds: list[str] = field(default_factory=list)
    raw_score: float = 0.5
    direction: str = "neutral"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_confident(self) -> bool:
        return self.confidence >= 0.65

    @property
    def is_uncertain(self) -> bool:
        return self.confidence < 0.4

    @property
    def evidence_ratio(self) -> float:
        """Ratio of supporting to total evidence."""
        total = len(self.supporting_evidence) + len(self.contradicting_evidence)
        if total == 0:
            return 0.5
        return len(self.supporting_evidence) / total


# ── Base Mental Model ───────────────────────────────────────────────────────


class MentalModel(ABC):
    """Abstract base class for all macro mental models.

    Subclasses must implement:
        - evaluate(input: ModelInput) → list[ResearchConclusion]
        - model_name: str (class-level identifier)
        - domain: str (macro domain)

    The evaluate() method receives a full M1 MacroSnapshot.
    Models should NOT access raw data directly — only through ModelInput.
    """

    model_name: str
    domain: str
    description: str = ""

    @abstractmethod
    def evaluate(self, input: ModelInput) -> list[ResearchConclusion]:
        """Evaluate the macro domain based on the current snapshot.

        Args:
            input: ModelInput wrapping the full M1 MacroSnapshot.

        Returns:
            List of ResearchConclusion (typically 1, may be multiple
            for models that detect competing regimes).
        """
        ...

    def __repr__(self) -> str:
        return f"{self.model_name}(domain={self.domain})"

    # ── Helper utilities for model implementations ──────────────────────

    @staticmethod
    def _extract_dimension_score(
        input: ModelInput,
        dimension_name: str,
    ) -> tuple[float, str, dict]:
        """Extract score, direction, and raw data for a state vector dimension."""
        dim = input.get_state_dimension(dimension_name)
        if dim:
            return dim.get("score", 0.5), dim.get("direction", "neutral"), dim
        return 0.5, "neutral", {}

    @staticmethod
    def _build_evidence(
        input: ModelInput,
        indicator_names: list[str],
        interpretation_fn,
    ) -> tuple[list[EvidenceItem], list[EvidenceItem]]:
        """Build supporting/contradicting evidence from indicators."""
        supporting = []
        contradicting = []

        for name in indicator_names:
            ind = input.get_indicator(name)
            if not ind:
                continue

            raw_value = ind.get("raw_value", 0)
            features = ind.get("features", [])

            interp = interpretation_fn(name, raw_value, features)

            evidence = EvidenceItem(
                indicator=name,
                value=raw_value,
                interpretation=interp["text"],
                weight=interp.get("weight", 1.0),
            )

            if interp.get("contradicts", False):
                contradicting.append(evidence)
            else:
                supporting.append(evidence)

        return supporting, contradicting

    @staticmethod
    def _compute_confidence(
        dimension_score: float,
        num_supporting: int,
        num_contradicting: int,
        num_indicators: int,
    ) -> float:
        """Compute confidence from dimension score and evidence balance."""
        if num_indicators == 0:
            return 0.3

        # Base: distance from 0.5 (extreme scores → higher confidence)
        base = abs(dimension_score - 0.5) * 2.0

        # Evidence bonus: more supporting than contradicting
        total_evidence = num_supporting + num_contradicting
        if total_evidence > 0:
            evidence_bonus = (num_supporting - num_contradicting) / total_evidence * 0.2
        else:
            evidence_bonus = 0.0

        # Indicator coverage bonus
        coverage = min(1.0, num_indicators / 3.0) * 0.15

        confidence = base * 0.65 + evidence_bonus + coverage
        return max(0.1, min(0.95, confidence))
