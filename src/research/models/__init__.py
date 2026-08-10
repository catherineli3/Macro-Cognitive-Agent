"""Mental Model Library — M2 Knowledge Layer.

The Agent should think like an economist, not like a rule engine.

Each MentalModel:
    1. Accepts a MacroSnapshot (from M1 pipeline).
    2. Evaluates a specific macro domain (Liquidity, Credit, Growth, etc.).
    3. Produces a structured ResearchConclusion with:
       - Conclusion (e.g., "Liquidity Tightening")
       - Confidence (0-1)
       - Supporting evidence
       - Contradicting evidence
       - Assumptions
       - Possible narratives (for M3 Narrative Engine)

Design:
    - All models registered via ModelRegistry.
    - No hardcoded if/else in ResearchCycle.
    - Every conclusion is traceable to source indicators.
"""

from src.research.models.mental_model import (
    EvidenceItem,
    MentalModel,
    ModelInput,
    ResearchConclusion,
)
from src.research.models.model_registry import ModelRegistry, build_default_registry

__all__ = [
    "MentalModel",
    "ModelInput",
    "ResearchConclusion",
    "EvidenceItem",
    "ModelRegistry",
    "build_default_registry",
]
