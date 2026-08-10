"""Narrative Module — V3.2 Narrative Reasoning.

Upgraded from signal detection (V3.0) to narrative reasoning (V3.2).

Capabilities:
- NarrativeObject: Rich narrative with causal chains, evidence classification, asset impact
- NarrativeDetector: Signal-based narrative detection (V3.0, kept for backward compat)
- NarrativeReasoner: V3.2 reasoning — transforms Narrative → NarrativeObject
- NarrativeCompetition: Multi-narrative generation with probability scoring
"""

from src.research.narrative.schemas import (
    Narrative,
    NarrativeObject,
    NarrativeResult,
    NarrativeCompetitionResult,
)
from src.research.narrative.narrative_detector import NarrativeDetector
from src.research.narrative.narrative_reasoner import NarrativeReasoner
from src.research.narrative.narrative_competition import NarrativeCompetition

__all__ = [
    # Schemas
    "Narrative",
    "NarrativeObject",
    "NarrativeResult",
    "NarrativeCompetitionResult",
    # Engines
    "NarrativeDetector",
    "NarrativeReasoner",
    "NarrativeCompetition",
]
