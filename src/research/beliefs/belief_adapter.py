"""BeliefAdapter — Convert between ResearchBelief (V3.1) and AdaptiveBelief (legacy).

V3.1 Architecture Consolidation:
    ResearchBelief is the SINGLE source of truth.
    This adapter exists ONLY for backward compatibility with code
    that still expects AdaptiveBelief (e.g., BeliefLifecycleManager).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.research.beliefs.schemas import ResearchBelief
    from src.schemas.belief_version import AdaptiveBelief


class BeliefAdapter:
    """Bidirectional converter between ResearchBelief and AdaptiveBelief.

    Usage:
        r = ResearchBelief(...)
        a = BeliefAdapter.to_adaptive(r)   # ResearchBelief → AdaptiveBelief
        r2 = BeliefAdapter.from_adaptive(a)  # AdaptiveBelief → ResearchBelief
    """

    # ── Domain Mapping ────────────────────────────────────────────────

    _DOMAIN_REVERSE = {
        "LIQUIDITY": "Liquidity",
        "INFLATION": "Inflation",
        "GROWTH": "Growth",
        "POLICY": "Policy",
        "RISK": "Risk",
        "CREDIT": "Credit",
        "DOLLAR": "Dollar",
        "AI_CAPEX": "AI_Capex",
    }

    @staticmethod
    def to_adaptive(belief) -> AdaptiveBelief:
        """Convert ResearchBelief → AdaptiveBelief for legacy compatibility."""
        from src.schemas.belief_version import AdaptiveBelief

        domain_str = getattr(belief, "domain", None)
        if hasattr(domain_str, "value"):
            domain_str = domain_str.value

        conf = getattr(belief, "confidence", 0.5)

        return AdaptiveBelief(
            belief_id=getattr(belief, "id", getattr(belief, "belief_id", "")),
            name=getattr(belief, "title", ""),
            dimension=domain_str or "unknown",
            description=getattr(belief, "description", ""),
            confidence=conf,
            weight=conf,  # Map confidence → weight
            maturity=0.5,  # Default maturity
            source=(
                ", ".join(getattr(belief, "source_narratives", []))
                if hasattr(belief, "source_narratives")
                else ""
            ),
            created_at=getattr(belief, "created_at", datetime.now(UTC)),
            updated_at=getattr(belief, "updated_at", datetime.now(UTC)),
        )

    @staticmethod
    def from_adaptive(adaptive_belief: AdaptiveBelief) -> ResearchBelief:
        """Convert AdaptiveBelief → ResearchBelief."""
        from src.research.beliefs.schemas import BeliefDomain, BeliefStage, ResearchBelief

        # Map dimension string to BeliefDomain enum
        dim = (adaptive_belief.dimension or "").upper()
        domain_map = {
            "LIQUIDITY": BeliefDomain.LIQUIDITY,
            "INFLATION": BeliefDomain.INFLATION,
            "GROWTH": BeliefDomain.GROWTH,
            "POLICY": BeliefDomain.POLICY,
            "RISK": BeliefDomain.RISK,
            "CREDIT": BeliefDomain.CREDIT,
            "DOLLAR": BeliefDomain.DOLLAR,
            "AI_CAPEX": BeliefDomain.AI_CAPEX,
        }
        domain = domain_map.get(dim, BeliefDomain.GROWTH)

        return ResearchBelief(
            id=adaptive_belief.belief_id,
            title=adaptive_belief.name or "",
            description=adaptive_belief.description or "",
            domain=domain,
            confidence=adaptive_belief.confidence,
            stage=BeliefStage.HYPOTHESIS,
            version=1,
        )
