"""EventClassifier — Classify news events by type, country, asset class, and impact.

Quality: Without proper classification, news cannot reliably feed into the
Evidence Graph or influence beliefs. Classification must be deterministic
and auditable.
"""

from __future__ import annotations

from src.news.schemas import (
    EventCategory,
    ImpactDirection,
    ImpactSeverity,
    NewsSourceType,
    ResearchEvent,
)


class EventClassifier:
    """Classify and re-classify research events.

    Handles both initial classification and re-classification after
    deduplication or additional context becomes available.
    """

    ASSET_CLASS_MAP = {
        "equity": ["stock", "equity", "s&p", "nasdaq", "dow", "share"],
        "fixed_income": ["bond", "yield", "treasury", "fixed income", "credit"],
        "currency": ["forex", "fx", "dollar", "eur", "usd", "jpy", "cny", "currency"],
        "commodity": ["oil", "gold", "copper", "commodity", "energy", "metal"],
        "real_estate": ["housing", "real estate", "property", "mortgage"],
        "crypto": ["bitcoin", "crypto", "btc", "eth", "digital asset"],
    }

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def classify(self, event: ResearchEvent) -> ResearchEvent:
        """Classify or re-classify a single event.

        Updates: category, impact_severity, market_impact, is_important,
        asset class associations.
        """
        event.category = self._determine_category(event)
        event.impact_severity = self._determine_severity(event)
        event.market_impact = self._refine_impact(event)
        event.is_important = self._is_important(event)
        return event

    def classify_batch(self, events: list[ResearchEvent]) -> list[ResearchEvent]:
        """Classify a batch of events."""
        return [self.classify(e) for e in events]

    def filter_important(self, events: list[ResearchEvent]) -> list[ResearchEvent]:
        """Return only events that matter for macro research."""
        return [e for e in events if self._is_important(e)]

    def assign_asset_classes(self, event: ResearchEvent) -> dict[str, float]:
        """Map event to affected asset classes with relevance scores.

        Returns:
            {asset_class: relevance_score (0-1)}
        """
        text = (event.title + " " + event.description).lower()
        scores = {}
        for asset_class, keywords in self.ASSET_CLASS_MAP.items():
            hits = sum(1 for k in keywords if k in text)
            if hits:
                scores[asset_class] = min(hits / 3, 1.0)
        return scores

    # ── Classification Methods ──

    def _determine_category(self, event: ResearchEvent) -> EventCategory:
        """Determine event category from title + description + source."""
        text = (event.title + " " + event.description).lower()

        # Source-based hints
        if event.source_type == NewsSourceType.CENTRAL_BANK:
            return EventCategory.MONETARY_POLICY
        if event.source_type == NewsSourceType.CENTRAL_BANK_SPEECH:
            return EventCategory.SPEECH_COMMENTARY
        if event.source_type == NewsSourceType.MARKET_DATA:
            return EventCategory.ECONOMIC_DATA

        # Text-based rules
        rules = [
            (
                [
                    "rate hike",
                    "rate cut",
                    "interest rate decision",
                    "fomc",
                    "monetary",
                    "tighten",
                    "easing",
                    "qe",
                    "quantitative",
                    "balance sheet",
                    "forward guidance",
                ],
                EventCategory.MONETARY_POLICY,
            ),
            (
                [
                    "fiscal",
                    "budget",
                    "deficit",
                    "spending bill",
                    "tax cut",
                    "tax increase",
                    "stimulus",
                    "debt ceiling",
                    "treasury borrowing",
                ],
                EventCategory.FISCAL_POLICY,
            ),
            (
                [
                    "gdp",
                    "cpi",
                    "ppi",
                    "nfp",
                    "payroll",
                    "unemployment",
                    "jobs report",
                    "pmi",
                    "ism",
                    "retail sales",
                    "housing starts",
                    "consumer confidence",
                    "industrial production",
                    "trade balance",
                ],
                EventCategory.ECONOMIC_DATA,
            ),
            (
                [
                    "war",
                    "sanction",
                    "conflict",
                    "election",
                    "tariff",
                    "trade dispute",
                    "geopolit",
                    "tension",
                    "invasion",
                ],
                EventCategory.GEOPOLITICAL,
            ),
            (
                [
                    "stock market",
                    "bond market",
                    "currency",
                    "oil price",
                    "gold price",
                    "market sell",
                    "market rally",
                    "volatility",
                ],
                EventCategory.MARKET_EVENT,
            ),
            (
                ["speech", "remarks", "testimony", "press conference", "interview"],
                EventCategory.SPEECH_COMMENTARY,
            ),
            (
                ["regulation", "sec", "cftc", "fdic", "compliance", "capital rule", "basel"],
                EventCategory.REGULATORY,
            ),
        ]

        for keywords, cat in rules:
            if any(k in text for k in keywords):
                return cat

        return event.category  # Keep existing

    def _determine_severity(self, event: ResearchEvent) -> ImpactSeverity:
        """Determine event impact severity."""
        # Source authority boosts severity
        authoritative_sources = {
            NewsSourceType.CENTRAL_BANK,
            NewsSourceType.GOVERNMENT_AGENCY,
            NewsSourceType.INTERNATIONAL_ORG,
        }
        if event.source_type in authoritative_sources:
            base = ImpactSeverity.HIGH
        else:
            base = ImpactSeverity.MEDIUM

        # Category adjustments
        high_impact_categories = {EventCategory.MONETARY_POLICY, EventCategory.FISCAL_POLICY}
        if event.category in high_impact_categories:
            if base == ImpactSeverity.HIGH:
                return ImpactSeverity.CRITICAL
            return ImpactSeverity.HIGH

        # Breaking news
        if event.is_breaking:
            if base == ImpactSeverity.HIGH:
                return ImpactSeverity.CRITICAL
            return ImpactSeverity.HIGH

        # Market reaction context
        text = (event.title + " " + event.description).lower()
        crisis_words = ["crisis", "crash", "collapse", "emergency", "turmoil", "panic"]
        if any(w in text for w in crisis_words):
            return ImpactSeverity.CRITICAL

        return base

    def _refine_impact(self, event: ResearchEvent) -> ImpactDirection:
        """Refine market impact direction with more context."""
        text = (event.title + " " + event.description).lower()

        # Data surprise based
        if event.surprise is not None:
            if event.surprise > 0:
                return ImpactDirection.BULLISH
            elif event.surprise < 0:
                return ImpactDirection.BEARISH
            return ImpactDirection.NEUTRAL

        # Policy direction hints
        hawkish = ["hawkish", "tightening", "rate hike", "taper", "restrictive"]
        dovish = ["dovish", "easing", "rate cut", "accommodative", "support"]

        if any(w in text for w in hawkish):
            if event.category == EventCategory.MONETARY_POLICY:
                return ImpactDirection.BEARISH  # Hawkish = bad for risk assets
            return ImpactDirection.BEARISH

        if any(w in text for w in dovish):
            if event.category == EventCategory.MONETARY_POLICY:
                return ImpactDirection.BULLISH  # Dovish = good for risk assets
            return ImpactDirection.BULLISH

        return event.market_impact  # Keep existing

    def _is_important(self, event: ResearchEvent) -> bool:
        """Determine if this event is important for macro research.

        Criteria:
        1. From authoritative source (CB, government, international org)
        2. Critical or high severity
        3. In a macro-relevant category
        4. Contains key economic numbers
        """
        if event.impact_severity in (ImpactSeverity.CRITICAL, ImpactSeverity.HIGH):
            return True

        authoritative = {
            NewsSourceType.CENTRAL_BANK,
            NewsSourceType.GOVERNMENT_AGENCY,
            NewsSourceType.INTERNATIONAL_ORG,
        }
        if event.source_type in authoritative:
            return True

        macro_categories = {
            EventCategory.MONETARY_POLICY,
            EventCategory.FISCAL_POLICY,
            EventCategory.ECONOMIC_DATA,
        }
        if event.category in macro_categories:
            if event.key_numbers or event.surprise is not None:
                return True

        if event.is_breaking:
            return True

        return False
