"""NewsCollector — Aggregate news from multiple source types.

Sources: Reuters, Bloomberg, FOMC, ECB, BOJ, PBOC, Fed Speeches,
Treasury, BLS, BEA, IMF, BIS, OECD.

Quality: news → ResearchEvent is the first bridge from real-world
information into the agent's cognitive system.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from src.news.schemas import (
    NewsArticle, ResearchEvent, NewsSourceType, EventCategory,
    ImpactDirection, ImpactSeverity,
)


class NewsCollector:
    """Collect and normalize news from diverse sources into ResearchEvents."""

    SUPPORTED_SOURCES = {
        "reuters": NewsSourceType.WIRE_SERVICE,
        "bloomberg": NewsSourceType.WIRE_SERVICE,
        "fomc": NewsSourceType.CENTRAL_BANK,
        "ecb": NewsSourceType.CENTRAL_BANK,
        "boj": NewsSourceType.CENTRAL_BANK,
        "pboc": NewsSourceType.CENTRAL_BANK,
        "fed_speech": NewsSourceType.CENTRAL_BANK_SPEECH,
        "treasury": NewsSourceType.GOVERNMENT_AGENCY,
        "bls": NewsSourceType.GOVERNMENT_AGENCY,
        "bea": NewsSourceType.GOVERNMENT_AGENCY,
        "imf": NewsSourceType.INTERNATIONAL_ORG,
        "bis": NewsSourceType.INTERNATIONAL_ORG,
        "oecd": NewsSourceType.INTERNATIONAL_ORG,
    }

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def collect_from_articles(
        self, articles: list[dict], source_type: str = "unknown"
    ) -> list[ResearchEvent]:
        """Convert raw article dicts into ResearchEvents.

        Args:
            articles: List of raw article dicts with headline, content, source, etc.
            source_type: Override source type

        Returns:
            List of ResearchEvent objects, one per article
        """
        events = []
        for art_dict in articles:
            article = self._dict_to_article(art_dict, source_type)
            if article:
                event = self._article_to_event(article)
                events.append(event)
        return events

    def collect_from_market_data(
        self, data_releases: list[dict], provider: str = "bloomberg"
    ) -> list[ResearchEvent]:
        """Convert economic data releases into ResearchEvents.

        Args:
            data_releases: List of release dicts with indicator name,
                          actual value, consensus, prior
            provider: Data provider name

        Returns:
            ResearchEvent list with proper economic data classification
        """
        events = []
        for release in data_releases:
            event = self._data_release_to_event(release, provider)
            events.append(event)
        return events

    def collect_from_cb_communication(
        self, statements: list[dict], cb_name: str
    ) -> list[ResearchEvent]:
        """Convert central bank communications into ResearchEvents.

        Args:
            statements: List of statement/speech/minutes dicts
            cb_name: Central bank name (fed, ecb, boj, pboc)

        Returns:
            ResearchEvent list with policy classification
        """
        events = []
        for stmt in statements:
            event = self._cb_statement_to_event(stmt, cb_name)
            events.append(event)
        return events

    # ── Internal Conversion Methods ──

    def _dict_to_article(self, d: dict, source_type_str: str) -> Optional[NewsArticle]:
        if not d.get("headline") and not d.get("title"):
            return None

        st = self.SUPPORTED_SOURCES.get(source_type_str, NewsSourceType.UNKNOWN)

        return NewsArticle(
            article_id=d.get("id", str(uuid.uuid4())[:12]),
            headline=d.get("headline", d.get("title", "")),
            content=d.get("content", d.get("body", d.get("summary", ""))),
            url=d.get("url", ""),
            source=st,
            source_name=d.get("source", d.get("source_name", source_type_str)),
            published_at=d.get("published_at", d.get("timestamp", "")),
            language=d.get("language", "en"),
            country=d.get("country", ""),
            tickers=d.get("tickers", []),
            topics=d.get("topics", d.get("tags", [])),
            author=d.get("author", ""),
        )

    def _article_to_event(self, article: NewsArticle) -> ResearchEvent:
        category = self._classify_headline(article.headline)
        direction = self._infer_direction(article.headline, article.content)

        return ResearchEvent(
            event_id=f"EVT_{str(uuid.uuid4())[:8]}",
            title=article.headline,
            description=article.content[:300] if article.content else article.headline,
            category=category,
            source_type=article.source,
            sources=[article.to_dict()],
            news_articles=[article],
            entities=self._extract_entities(article),
            country=article.country or self._infer_country(article),
            market_impact=direction,
            impact_severity=ImpactSeverity.MEDIUM,
            impact_confidence=0.6,
            timestamp=article.published_at or datetime.now(timezone.utc).isoformat(),
            is_breaking="breaking" in article.headline.lower(),
            is_important=category != EventCategory.OTHER,
        )

    def _data_release_to_event(self, release: dict, provider: str) -> ResearchEvent:
        indicator = release.get("indicator", release.get("name", ""))
        actual = release.get("actual", release.get("value"))
        consensus = release.get("consensus", release.get("forecast", release.get("expected")))
        prior = release.get("prior", release.get("previous"))
        unit = release.get("unit", "")

        # Compute surprise
        surprise = None
        if actual is not None and consensus is not None:
            try:
                surprise = float(actual) - float(consensus)
            except (ValueError, TypeError):
                pass

        # Direction
        if surprise and surprise > 0:
            direction = ImpactDirection.BULLISH
        elif surprise and surprise < 0:
            direction = ImpactDirection.BEARISH
        else:
            direction = ImpactDirection.NEUTRAL

        return ResearchEvent(
            event_id=f"DATA_{str(uuid.uuid4())[:8]}",
            title=f"{indicator}: {actual}{' '+unit if unit else ''} (Consensus: {consensus}, Prior: {prior})",
            description=f"Economic data release: {indicator}. "
                        f"Actual: {actual}, Consensus: {consensus}, Prior: {prior}.",
            category=EventCategory.ECONOMIC_DATA,
            source_type=NewsSourceType.MARKET_DATA,
            sources=[{"provider": provider, "indicator": indicator}],
            entities=[indicator, provider],
            country=release.get("country", "US"),
            market_impact=direction,
            impact_severity=ImpactSeverity.HIGH if surprise and abs(float(surprise)) > 1.5 else ImpactSeverity.MEDIUM,
            impact_confidence=0.8,
            timestamp=release.get("timestamp", datetime.now(timezone.utc).isoformat()),
            key_numbers={"actual": actual, "consensus": consensus, "prior": prior},
            consensus_expectation=float(consensus) if consensus is not None else None,
            actual_value=float(actual) if actual is not None else None,
            surprise=surprise,
        )

    def _cb_statement_to_event(self, stmt: dict, cb_name: str) -> ResearchEvent:
        name_map = {"fed": "Federal Reserve", "ecb": "European Central Bank",
                     "boj": "Bank of Japan", "pboc": "People's Bank of China", "boe": "Bank of England"}

        title = stmt.get("title", f"{name_map.get(cb_name, cb_name)} Communication")
        content = stmt.get("text", stmt.get("content", stmt.get("summary", "")))

        source_type = NewsSourceType.CENTRAL_BANK if "statement" in title.lower() or "minutes" in title.lower() else NewsSourceType.CENTRAL_BANK_SPEECH

        return ResearchEvent(
            event_id=f"CB_{str(uuid.uuid4())[:8]}",
            title=title,
            description=content[:300],
            category=EventCategory.MONETARY_POLICY,
            source_type=source_type,
            sources=[{"central_bank": cb_name, "type": "statement"}],
            entities=[name_map.get(cb_name, cb_name)],
            country=self._cb_country(cb_name),
            market_impact=ImpactDirection.NEUTRAL,  # Will be refined by PolicyExtractor
            impact_severity=ImpactSeverity.HIGH,
            impact_confidence=0.7,
            timestamp=stmt.get("date", datetime.now(timezone.utc).isoformat()),
        )

    # ── Classification Helpers ──

    def _classify_headline(self, headline: str) -> EventCategory:
        hl = headline.lower()
        rules = [
            (["rate hike", "rate cut", "interest rate", "fomc", "ecb", "boj", "monetary policy",
              "tightening", "easing", "quantitative"], EventCategory.MONETARY_POLICY),
            (["fiscal", "budget", "deficit", "spending", "tax", "stimulus", "treasury",
              "debt ceiling"], EventCategory.FISCAL_POLICY),
            (["gdp", "cpi", "ppi", "nfp", "payroll", "unemployment", "pmi", "ism",
              "retail sales", "industrial", "housing", "consumer confidence"], EventCategory.ECONOMIC_DATA),
            (["war", "sanction", "conflict", "election", "trade war", "tariff",
              "geopolit"], EventCategory.GEOPOLITICAL),
            (["stock", "bond", "currency", "oil", "gold", "market rally", "market sell",
              "volatility", "vix"], EventCategory.MARKET_EVENT),
            (["speech", "remarks", "testimony", "press conference", "interview",
              "comment"], EventCategory.SPEECH_COMMENTARY),
            (["regulation", "sec", "cftc", "fdic", "basel", "capital requirement",
              "compliance"], EventCategory.REGULATORY),
        ]
        for keywords, cat in rules:
            if any(k in hl for k in keywords):
                return cat
        return EventCategory.OTHER

    def _infer_direction(self, headline: str, content: str) -> ImpactDirection:
        text = (headline + " " + content[:200]).lower()

        bullish_keywords = ["beat", "exceed", "strong", "surge", "rally", "growth",
                            "expansion", "recovery", "upgrade", "optimistic", "dovish",
                            "cut rate", "easing", "stimulus"]
        bearish_keywords = ["miss", "below", "weak", "plunge", "selloff", "recession",
                            "contraction", "downgrade", "pessimistic", "hawkish",
                            "hike rate", "tightening", "crash", "crisis", "default"]

        bull_count = sum(1 for k in bullish_keywords if k in text)
        bear_count = sum(1 for k in bearish_keywords if k in text)

        if bull_count > bear_count * 1.5:
            return ImpactDirection.BULLISH
        elif bear_count > bull_count * 1.5:
            return ImpactDirection.BEARISH
        return ImpactDirection.NEUTRAL

    def _extract_entities(self, article: NewsArticle) -> list[str]:
        entities = []
        if article.tickers:
            entities.extend(article.tickers)
        if article.country:
            entities.append(article.country)
        if article.source_name:
            entities.append(article.source_name)
        return entities

    @staticmethod
    def _infer_country(article: NewsArticle) -> str:
        text = (article.headline + " " + article.content[:200]).lower()
        country_keywords = {
            "US": ["us", "u.s.", "america", "fed", "fomc", "dollar"],
            "CN": ["china", "chinese", "pboc", "beijing"],
            "EU": ["eurozone", "europe", "ecb", "euro"],
            "JP": ["japan", "boj", "tokyo", "yen"],
            "UK": ["uk", "britain", "boe", "london", "sterling"],
        }
        for country, keywords in country_keywords.items():
            if any(k in text for k in keywords):
                return country
        return "US"

    @staticmethod
    def _cb_country(cb_name: str) -> str:
        return {"fed": "US", "ecb": "EU", "boj": "JP", "pboc": "CN", "boe": "UK"}.get(cb_name.lower(), "US")
