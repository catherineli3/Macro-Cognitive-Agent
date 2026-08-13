"""M4 Belief Schemas — unified data structures for the Belief Engine.

Contract First: ResearchBelief replaces AdaptiveBelief.
All belief data structures are defined here only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

# ── Enums ────────────────────────────────────────────────────────────────────


class BeliefStage(str, Enum):
    """7-stage belief lifecycle (upgraded from legacy 6-stage).

    1. HYPOTHESIS        — Initial idea, low confidence
    2. EVIDENCE_GATHERING — Actively collecting data
    3. CONFIRMATION      — Evidence supports belief
    4. CHALLENGE          — Evidence contradicts belief
    5. CONSOLIDATION     — Belief stabilizes, high confidence
    6. EROSION            — Belief weakening, confidence declining
    7. RETIRED            — Belief no longer active
    """

    HYPOTHESIS = "hypothesis"
    EVIDENCE_GATHERING = "evidence_gathering"
    CONFIRMATION = "confirmation"
    CHALLENGE = "challenge"
    CONSOLIDATION = "consolidation"
    EROSION = "erosion"
    RETIRED = "retired"


class EvidenceSource(str, Enum):
    """Six-source classification of evidence."""

    MACRO_DATA = "macro_data"  # Economic indicators, policy data
    MARKET_DATA = "market_data"  # Price, volume, spreads
    NEWS = "news"  # Headlines, sentiment
    COMPANY = "company"  # Earnings, guidance
    HISTORY = "history"  # Historical analogs, backtest
    INFERENCE = "inference"  # Model-derived conclusions


class BeliefRelationType(str, Enum):
    SUPPORTS = "supports"
    COMPETES = "competes"
    CONTRADICTS = "contradicts"
    EXPLAINS = "explains"


class BeliefDomain(str, Enum):
    LIQUIDITY = "Liquidity"
    CREDIT = "Credit"
    INFLATION = "Inflation"
    GROWTH = "Growth"
    POLICY = "Policy"
    DOLLAR = "Dollar"
    AI_CAPEX = "AI_Capex"
    RISK = "Risk_Appetite"
    EMPLOYMENT = "Employment"


# ── Core Data Structures ─────────────────────────────────────────────────────


@dataclass
class EvidenceItem:
    """A single piece of evidence with source classification."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    source: EvidenceSource = EvidenceSource.MACRO_DATA
    description: str = ""
    weight: float = 1.0  # 0–1: evidential weight
    direction: str = "neutral"  # supporting / contradicting / neutral
    value: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source.value,
            "description": self.description,
            "weight": self.weight,
            "direction": self.direction,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Prediction:
    """A verifiable prediction generated from a belief."""

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    belief_id: str = ""
    statement: str = ""  # What is predicted
    asset: str = ""  # Target asset/index
    direction: str = ""  # up / down / flat
    target_value: float = 0.0
    confidence: float = 0.5  # 0–1
    time_horizon_days: int = 30
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    outcome: str = ""  # correct / wrong / pending
    actual_value: float = 0.0
    resolved_at: datetime | None = None
    score: float = 0.0  # 1.0 = perfectly correct, 0.0 = wrong

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "belief_id": self.belief_id,
            "statement": self.statement,
            "asset": self.asset,
            "direction": self.direction,
            "target_value": self.target_value,
            "confidence": self.confidence,
            "time_horizon_days": self.time_horizon_days,
            "created_at": self.created_at.isoformat(),
            "outcome": self.outcome,
            "actual_value": self.actual_value,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "score": self.score,
        }


@dataclass
class ResearchBelief:
    """Core belief object — replaces AdaptiveBelief from legacy system.

    Uses Beta-Bayesian updating:
        Posterior = Prior + Evidence (weighted by source)

    Fields:
        alpha: Success count in Beta distribution
        beta: Failure count in Beta distribution
        confidence: alpha / (alpha + beta)
        uncertainty: 1 - abs(bias)
    """

    id: str = field(default_factory=lambda: uuid4().hex[:12])
    title: str = ""
    description: str = ""
    domain: BeliefDomain = BeliefDomain.GROWTH
    stage: BeliefStage = BeliefStage.HYPOTHESIS

    # ── Beta-Bayesian state ─────────────────────────────────────────────
    alpha: float = 1.0  # Prior successes (Beta distribution α)
    beta: float = 1.0  # Prior failures (Beta distribution β)
    confidence: float = 0.5  # alpha / (alpha + beta)
    uncertainty: float = 0.5  # 1 / (alpha + beta) normalized
    decay: float = 0.0  # Time-decay factor

    # ── Evidence ─────────────────────────────────────────────────────────
    evidence: list[EvidenceItem] = field(default_factory=list)
    evidence_count: int = 0
    last_evidence_at: datetime | None = None

    # ── Regime awareness ─────────────────────────────────────────────────
    regimes: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)

    # ── Graph connections ────────────────────────────────────────────────
    support_links: list[str] = field(default_factory=list)
    competition_links: list[str] = field(default_factory=list)
    contradiction_links: list[str] = field(default_factory=list)
    explanation_links: list[str] = field(default_factory=list)

    # ── Prediction tracking ──────────────────────────────────────────────
    prediction_history: list[Prediction] = field(default_factory=list)
    track_record: dict[str, float] = field(default_factory=dict)

    # ── Derived from M1/M2/M3 ────────────────────────────────────────────
    source_narratives: list[str] = field(default_factory=list)
    source_models: list[str] = field(default_factory=list)

    # ── Lifecycle ────────────────────────────────────────────────────────
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    retired_at: datetime | None = None
    is_active: bool = True
    version: int = 1

    # ── Stage history ────────────────────────────────────────────────────
    stage_history: list[dict] = field(default_factory=list)

    def update_confidence(self) -> None:
        """Recalculate confidence from Beta distribution."""
        total = self.alpha + self.beta
        if total > 0:
            self.confidence = self.alpha / total
            self.uncertainty = min(1.0, 1.0 / total)

    def add_evidence(self, item: EvidenceItem) -> None:
        """Add evidence and update Beta distribution.

        Args:
            item: Evidence item with direction (supporting/contradicting).
        """
        self.evidence.append(item)
        self.evidence_count = len(self.evidence)
        self.last_evidence_at = item.timestamp

        if item.direction == "supporting":
            self.alpha += item.weight
        elif item.direction == "contradicting":
            self.beta += item.weight

        self.update_confidence()
        self.updated_at = datetime.now(UTC)
        self.version += 1

    def predict(
        self,
        statement: str,
        asset: str,
        direction: str,
        target_value: float = 0.0,
        time_horizon_days: int = 30,
    ) -> Prediction:
        """Generate a verifiable prediction from this belief."""
        p = Prediction(
            belief_id=self.id,
            statement=statement,
            asset=asset,
            direction=direction,
            target_value=target_value,
            confidence=self.confidence,
            time_horizon_days=time_horizon_days,
        )
        self.prediction_history.append(p)
        return p

    def resolve_prediction(
        self,
        prediction_id: str,
        actual_value: float,
        was_correct: bool,
    ) -> Prediction | None:
        """Resolve a prediction with actual outcome."""
        for p in self.prediction_history:
            if p.id == prediction_id:
                p.actual_value = actual_value
                p.resolved_at = datetime.now(UTC)
                p.outcome = "correct" if was_correct else "wrong"
                p.score = 1.0 if was_correct else 0.0

                # Update track record
                self.track_record[p.id] = p.score

                # If wrong, this is evidence against the belief
                if not was_correct:
                    self.add_evidence(
                        EvidenceItem(
                            source=EvidenceSource.MARKET_DATA,
                            description=f"Prediction '{p.statement}' was wrong",
                            direction="contradicting",
                            weight=0.8,
                            value=actual_value,
                        )
                    )
                else:
                    self.add_evidence(
                        EvidenceItem(
                            source=EvidenceSource.MARKET_DATA,
                            description=f"Prediction '{p.statement}' was correct",
                            direction="supporting",
                            weight=0.8,
                            value=actual_value,
                        )
                    )

                return p
        return None

    def advance_stage(self, new_stage: BeliefStage, reason: str = "") -> None:
        """Advance belief to a new lifecycle stage."""
        old_stage = self.stage
        self.stage = new_stage
        self.stage_history.append(
            {
                "from": old_stage.value,
                "to": new_stage.value,
                "reason": reason,
                "timestamp": datetime.now(UTC).isoformat(),
                "confidence": self.confidence,
            }
        )

        if new_stage == BeliefStage.RETIRED:
            self.retired_at = datetime.now(UTC)
            self.is_active = False

        self.updated_at = datetime.now(UTC)
        self.version += 1

    def auto_stage(self) -> BeliefStage | None:
        """Auto-determine lifecycle stage based on evidence and confidence."""
        n_supporting = sum(1 for e in self.evidence if e.direction == "supporting")
        n_contradicting = sum(1 for e in self.evidence if e.direction == "contradicting")

        total = n_supporting + n_contradicting

        if total == 0:
            return (
                BeliefStage.HYPOTHESIS
                if self.stage == BeliefStage.HYPOTHESIS
                else BeliefStage.EVIDENCE_GATHERING
            )

        if total < 3:
            return BeliefStage.EVIDENCE_GATHERING

        if n_contradicting > n_supporting:
            return BeliefStage.CHALLENGE

        if self.confidence > 0.8 and total >= 5:
            return BeliefStage.CONSOLIDATION

        if self.confidence > 0.6:
            return BeliefStage.CONFIRMATION

        # Check erosion: confidence declining with age
        if self.confidence < 0.4 and total >= 3:
            return BeliefStage.EROSION

        return None

    def track_record_summary(self) -> dict:
        """Summarize prediction track record."""
        if not self.track_record:
            return {"total": 0, "correct": 0, "accuracy": 0.0}

        total = len(self.track_record)
        correct = sum(1 for v in self.track_record.values() if v > 0.5)
        return {
            "total": total,
            "correct": correct,
            "accuracy": correct / total if total > 0 else 0.0,
        }

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "domain": self.domain.value,
            "stage": self.stage.value,
            "alpha": self.alpha,
            "beta": self.beta,
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "decay": self.decay,
            "evidence_count": self.evidence_count,
            "regimes": self.regimes,
            "failure_modes": self.failure_modes,
            "support_links": self.support_links,
            "competition_links": self.competition_links,
            "prediction_history_count": len(self.prediction_history),
            "track_record": self.track_record_summary(),
            "source_narratives": self.source_narratives,
            "source_models": self.source_models,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "stage_history": self.stage_history,
        }
