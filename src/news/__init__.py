"""V4 News Intelligence — Real-world news integration for macro research.

Professional macro research = Numbers × News × Policy × CB Communication ×
Market Expectations.

Modules:
    NewsCollector — Aggregate from multiple source types (data, CB, policy, institutions)
    NewsDeduplicator — Merge duplicate stories into canonical events
    EventClassifier — Classify by type, country, asset class, impact
    PolicyExtractor — Extract policy signals from central bank communication
    MarketExpectationExtractor — Extract market-implied expectations vs reality

Output: Each news item becomes a ResearchEvent with full metadata,
then feeds into the Evidence Graph via the Fusion Engine.
"""

from src.news.schemas import (
    ResearchEvent,
    NewsArticle,
    PolicySignal,
    MarketExpectation,
    NewsSourceType,
    EventCategory,
    ImpactDirection,
    ImpactSeverity,
)
from src.news.news_collector import NewsCollector
from src.news.news_deduplicator import NewsDeduplicator
from src.news.event_classifier import EventClassifier
from src.news.policy_extractor import PolicyExtractor
from src.news.market_expectation_extractor import MarketExpectationExtractor
from src.news.fusion_engine import FusionEngine, UnifiedEvidenceGraph, EvidenceNode, EvidenceEdge

__all__ = [
    # Schemas
    "ResearchEvent",
    "NewsArticle",
    "PolicySignal",
    "MarketExpectation",
    "NewsSourceType",
    "EventCategory",
    "ImpactDirection",
    "ImpactSeverity",
    # Engines
    "NewsCollector",
    "NewsDeduplicator",
    "EventClassifier",
    "PolicyExtractor",
    "MarketExpectationExtractor",
    # R3: Fusion
    "FusionEngine",
    "UnifiedEvidenceGraph",
    "EvidenceNode",
    "EvidenceEdge",
]
