"""BeliefUpdateEngine — Beta-Bayesian belief updating.

Posterior = Prior + Evidence

Uses Beta distribution:
    α (alpha): count of supporting evidence (weighted)
    β (beta):  count of contradicting evidence (weighted)

    confidence = α / (α + β)
    uncertainty ≈ 1 / (α + β)
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.research.beliefs.evidence_weight import compute_evidence_weight
from src.research.beliefs.schemas import (
    BeliefDomain,
    BeliefStage,
    EvidenceItem,
    EvidenceSource,
    ResearchBelief,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


class BeliefUpdateEngine:
    """Update beliefs using Beta-Bayesian inference.

    Each piece of evidence is:
        1. Classified by source type (6-source system)
        2. Weighted by confidence, recency, corroboration
        3. Applied as α-increment (supporting) or β-increment (contradicting)

    Usage:
        engine = BeliefUpdateEngine()
        belief = engine.initialize_belief("Dollar Strengthening", BeliefDomain.DOLLAR)

        # Add evidence
        engine.add_evidence(belief,
            "DXY broke above 106 resistance",
            EvidenceSource.MARKET_DATA, "supporting")

        engine.add_evidence(belief,
            "Rate differentials widening in USD favor",
            EvidenceSource.MACRO_DATA, "supporting")
    """

    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0) -> None:
        """Initialize with default Beta prior.

        Alpha=1, Beta=1 → uniform prior (50% confidence, max uncertainty).
        """
        self._default_alpha = prior_alpha
        self._default_beta = prior_beta

    def initialize_belief(
        self,
        title: str,
        domain: BeliefDomain,
        description: str = "",
        initial_evidence: list[dict] | None = None,
    ) -> ResearchBelief:
        """Create a new belief with Beta(1,1) prior."""
        belief = ResearchBelief(
            title=title,
            description=description,
            domain=domain,
            alpha=self._default_alpha,
            beta=self._default_beta,
            stage=BeliefStage.HYPOTHESIS,
        )
        belief.update_confidence()

        # Bootstrap with initial evidence if provided
        if initial_evidence:
            for ev_data in initial_evidence:
                self.add_evidence(
                    belief,
                    description=ev_data.get("description", ""),
                    source=ev_data.get("source", EvidenceSource.MACRO_DATA),
                    direction=ev_data.get("direction", "supporting"),
                    confidence=ev_data.get("confidence", 0.7),
                )

        logger.info(
            "belief_initialized | %s | domain=%s alpha=%.2f beta=%.2f",
            belief.id[:8],
            domain.value,
            belief.alpha,
            belief.beta,
        )
        return belief

    def add_evidence(
        self,
        belief: ResearchBelief,
        description: str,
        source: EvidenceSource,
        direction: str = "supporting",
        confidence: float = 0.7,
        value: float = 0.0,
        recency_days: float = 0.0,
    ) -> EvidenceItem:
        """Add evidence and update belief via Bayesian inference.

        Args:
            belief: The belief to update.
            description: Human-readable evidence description.
            source: Evidence source type.
            direction: "supporting" or "contradicting".
            confidence: Source confidence 0-1.
            value: Numerical value associated with evidence.
            recency_days: Days since evidence was observed.

        Returns:
            The created EvidenceItem.
        """
        # Compute weighted evidence
        weight = compute_evidence_weight(
            source=source,
            confidence=confidence,
            recency_days=recency_days,
            corroboration_count=len(belief.evidence),
        )

        item = EvidenceItem(
            source=source,
            description=description,
            weight=weight,
            direction=direction,
            value=value,
        )

        # Apply Bayesian update
        old_conf = belief.confidence
        belief.add_evidence(item)

        logger.info(
            "belief_evidence | %s | %s weight=%.2f dir=%s conf: %.2f→%.2f",
            belief.id[:8],
            description[:50],
            item.weight,
            direction,
            old_conf,
            belief.confidence,
        )

        # Auto-stage transition
        new_stage = belief.auto_stage()
        if new_stage and new_stage != belief.stage:
            belief.advance_stage(new_stage, reason="Auto-triggered based on evidence state")

        return item

    def batch_update(
        self,
        belief: ResearchBelief,
        evidence_batch: list[dict],
    ) -> list[EvidenceItem]:
        """Apply a batch of evidence items in sequence."""
        items = []
        for ev in evidence_batch:
            item = self.add_evidence(
                belief,
                description=ev.get("description", ""),
                source=ev.get("source", EvidenceSource.INFERENCE),
                direction=ev.get("direction", "supporting"),
                confidence=ev.get("confidence", 0.7),
                value=ev.get("value", 0.0),
            )
            items.append(item)
        return items

    def apply_decay(self, belief: ResearchBelief, half_life_days: float = 30.0) -> None:
        """Apply time-based decay to belief confidence.

        As time passes without new evidence, confidence should decay
        towards the prior (0.5).

        decay = belief.prior × (1 - 2^(-Δt / half_life))
        """
        if not belief.last_evidence_at:
            return

        delta_days = (datetime.now(UTC) - belief.last_evidence_at).total_seconds() / 86400.0

        if delta_days <= 0:
            return

        decay_factor = 2.0 ** (-delta_days / half_life_days)

        # Move alpha and beta towards prior
        prior_alpha = 1.0
        prior_beta = 1.0
        belief.alpha = prior_alpha + (belief.alpha - prior_alpha) * decay_factor
        belief.beta = prior_beta + (belief.beta - prior_beta) * decay_factor
        belief.decay = 1.0 - decay_factor
        belief.update_confidence()

        logger.info(
            "belief_decay | %s delta=%.1fd decay=%.3f conf=%.3f",
            belief.id[:8],
            delta_days,
            belief.decay,
            belief.confidence,
        )

    def get_evidence_breakdown(self, belief: ResearchBelief) -> dict:
        """Get a breakdown of evidence by source type."""
        breakdown: dict[str, dict] = {}
        for source in EvidenceSource:
            items = [e for e in belief.evidence if e.source == source]
            supporting = sum(1 for e in items if e.direction == "supporting")
            contradicting = sum(1 for e in items if e.direction == "contradicting")
            total_weight = sum(e.weight for e in items)

            if items:
                breakdown[source.value] = {
                    "count": len(items),
                    "supporting": supporting,
                    "contradicting": contradicting,
                    "total_weight": round(total_weight, 2),
                    "avg_weight": round(total_weight / len(items), 3),
                }

        return breakdown
