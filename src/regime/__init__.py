"""V3.5 Regime Engine — "where are we in the cycle?"

Dalio-style macro regime classification + historical analogy matching.

Modules:
    - RegimeClassifier: Multi-dimensional regime classification
    - RegimeTransition: Transition probability estimation
    - HistoricalSimilarity: Match current to historical periods
"""

from src.regime.historical_similarity import HistoricalSimilarity
from src.regime.regime_classifier import RegimeClassifier
from src.regime.regime_transition import RegimeTransitionDetector
from src.regime.schemas import (
    HistoricalAnalog,
    MacroRegime,
    RegimeReport,
    RegimeTransitionModel,
)

__all__ = [
    "MacroRegime",
    "HistoricalAnalog",
    "RegimeTransitionModel",
    "RegimeReport",
    "RegimeClassifier",
    "RegimeTransitionDetector",
    "HistoricalSimilarity",
]
