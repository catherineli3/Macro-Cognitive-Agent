"""V6.1 Source Router — Route raw events to the correct normalizer.

Each source type has its own handler. The router dispatches RawEvent → NormalizedEvent
based on source taxonomy, extracting the canonical fields regardless of input format.
"""

from __future__ import annotations

import re

from src.live_intelligence.schemas import (
    EventImportance,
    NormalizedEvent,
    RawEvent,
    SourceType,
)


class SourceRouter:
    """Route raw events from any source to normalized canonical format.

    Each source handler knows how to:
    1. Extract title, summary, key numbers
    2. Classify importance
    3. Map to asset classes and beliefs
    4. Determine impact direction
    """

    # ── Source handler registry ────────────────────────────────────────────

    HANDLERS = {
        SourceType.REUTERS: "_handle_wire_service",
        SourceType.BLOOMBERG: "_handle_wire_service",
        SourceType.FED_SPEECH: "_handle_cb_speech",
        SourceType.ECB_SPEECH: "_handle_cb_speech",
        SourceType.BOJ_SPEECH: "_handle_cb_speech",
        SourceType.PBOC: "_handle_cb_speech",
        SourceType.FOMC_MINUTES: "_handle_cb_minutes",
        SourceType.FOMC_STATEMENT: "_handle_cb_statement",
        SourceType.ECB_MINUTES: "_handle_cb_minutes",
        SourceType.BOJ_MINUTES: "_handle_cb_minutes",
        SourceType.TREASURY: "_handle_gov_data",
        SourceType.BLS: "_handle_economic_data",
        SourceType.BEA: "_handle_economic_data",
        SourceType.SEC_FILING: "_handle_filing",
        SourceType.ETF_FLOW: "_handle_flow_data",
        SourceType.CME_FEDWATCH: "_handle_market_pricing",
        SourceType.INSTITUTIONAL_13F: "_handle_filing",
        SourceType.IMF: "_handle_institution_report",
        SourceType.BIS: "_handle_institution_report",
        SourceType.WORLD_BANK: "_handle_institution_report",
        SourceType.OECD: "_handle_institution_report",
    }

    def __init__(self):
        self._handler_cache: dict[str, str] = {}
        self._route_count: dict[str, int] = {}

    def route(self, raw: RawEvent) -> NormalizedEvent:
        """Route a raw event to its handler and produce a NormalizedEvent."""
        handler_name = self.HANDLERS.get(raw.source, "_handle_unknown")
        handler = getattr(self, handler_name, self._handle_unknown)

        event = handler(raw)

        # Track routing stats
        source_key = raw.source.value if isinstance(raw.source, SourceType) else str(raw.source)
        self._route_count[source_key] = self._route_count.get(source_key, 0) + 1

        return event

    def route_batch(self, raws: list[RawEvent]) -> list[NormalizedEvent]:
        """Route multiple raw events."""
        return [self.route(r) for r in raws]

    # ── Generic fallback ───────────────────────────────────────────────────

    def _base_normalize(self, raw: RawEvent) -> NormalizedEvent:
        """Minimal normalization — used when no specific handler exists."""
        event = NormalizedEvent(
            raw_ids=[raw.raw_id],
            sources=[raw.source],
            title=raw.headline or "Untitled Event",
            summary=raw.content[:300] if raw.content else raw.headline,
            full_text=raw.content,
            countries=[raw.country] if raw.country else [],
            asset_classes=[raw.asset_class] if raw.asset_class else [],
            key_numbers=self._extract_numbers(raw.content),
            occurred_at=raw.published_at or raw.received_at,
            importance=self._estimate_importance(raw),
            confidence=raw.source_reliability,
        )
        return event

    def _handle_unknown(self, raw: RawEvent) -> NormalizedEvent:
        """Fallback handler for unknown sources."""
        return self._base_normalize(raw)

    # ── Wire Service Handler ───────────────────────────────────────────────

    def _handle_wire_service(self, raw: RawEvent) -> NormalizedEvent:
        """Handle Reuters / Bloomberg articles."""
        event = self._base_normalize(raw)

        # Wire services are generally high-quality
        event.confidence = max(event.confidence, 0.7)

        # Classify based on headline/content keywords
        category, importance = self._classify_by_keywords(raw.headline + " " + raw.content[:500])
        event.category = category
        event.importance = EventImportance(importance) if importance else event.importance

        # Extract entities
        event.entities = self._extract_entities(raw.content)

        # Impact direction
        event.impact_direction = self._detect_sentiment(raw.headline + " " + raw.content[:300])

        return event

    # ── Central Bank Speech Handler ────────────────────────────────────────

    def _handle_cb_speech(self, raw: RawEvent) -> NormalizedEvent:
        """Handle central bank speeches (Fed, ECB, BOJ, PBOC)."""
        event = self._base_normalize(raw)

        # CB speeches are high importance
        event.category = "monetary_policy"
        event.confidence = max(event.confidence, 0.65)

        # Detect hawkish/dovish from content
        hawkish_score = self._hawkish_dovish_score(raw.content)
        if hawkish_score > 0.3:
            event.impact_direction = "bearish"  # Tighter policy = bearish risk
        elif hawkish_score < -0.3:
            event.impact_direction = "bullish"
        else:
            event.impact_direction = "neutral"

        event.impact_magnitude = abs(hawkish_score)
        event.importance = (
            EventImportance.HIGH if abs(hawkish_score) > 0.5 else EventImportance.MEDIUM
        )

        return event

    def _handle_cb_statement(self, raw: RawEvent) -> NormalizedEvent:
        """Handle FOMC/ECB/BOJ policy statements — highest importance."""
        event = self._handle_cb_speech(raw)  # Share logic
        event.importance = EventImportance.CRITICAL  # Policy statements are always critical
        return event

    def _handle_cb_minutes(self, raw: RawEvent) -> NormalizedEvent:
        """Handle central bank meeting minutes."""
        event = self._handle_cb_speech(raw)
        event.importance = EventImportance.HIGH  # Minutes are high but not critical like statements
        return event

    # ── Economic Data Handler ──────────────────────────────────────────────

    def _handle_economic_data(self, raw: RawEvent) -> NormalizedEvent:
        """Handle BLS, BEA, and other economic data releases."""
        event = self._base_normalize(raw)
        event.category = "economic_data"
        event.confidence = max(event.confidence, 0.8)  # Hard data = high confidence

        # Extract key numbers (CPI, NFP, GDP, etc.)
        numbers = self._extract_economic_numbers(raw.content, raw.raw_data)
        event.key_numbers.update(numbers)

        # Determine surprise
        if "consensus" in raw.raw_data and "actual" in raw.raw_data:
            expected = raw.raw_data.get("consensus", 0)
            actual = raw.raw_data.get("actual", 0)
            event.surprise = actual - expected
            event.impact_magnitude = min(
                abs(event.surprise) / abs(expected) if expected else 0, 1.0
            )

            if event.surprise > 0:
                event.impact_direction = (
                    "bullish" if self._is_good_surprise(raw.headline) else "bearish"
                )
            elif event.surprise < 0:
                event.impact_direction = (
                    "bearish" if self._is_good_surprise(raw.headline) else "bullish"
                )

        # Importance based on indicator type
        event.importance = self._economic_data_importance(raw.headline)

        return event

    # ── Government Data Handler ────────────────────────────────────────────

    def _handle_gov_data(self, raw: RawEvent) -> NormalizedEvent:
        """Handle Treasury, fiscal, and other government agency data."""
        event = self._base_normalize(raw)
        event.category = "fiscal_policy"
        event.confidence = max(event.confidence, 0.7)
        event.importance = EventImportance.MEDIUM

        # Treasury auctions, debt ceiling = high
        if any(
            kw in (raw.headline + raw.content).lower()
            for kw in ["auction", "debt ceiling", "issuance", "quarterly refunding"]
        ):
            event.importance = EventImportance.HIGH

        return event

    # ── Flow Data Handler ──────────────────────────────────────────────────

    def _handle_flow_data(self, raw: RawEvent) -> NormalizedEvent:
        """Handle ETF flow data."""
        event = self._base_normalize(raw)
        event.category = "market_event"
        event.confidence = max(event.confidence, 0.6)
        event.importance = EventImportance.MEDIUM

        # Large flows = high importance
        content = raw.content.lower()
        if any(kw in content for kw in ["record", "largest", "billions", "massive"]):
            event.importance = EventImportance.HIGH

        return event

    # ── Market Pricing Handler ─────────────────────────────────────────────

    def _handle_market_pricing(self, raw: RawEvent) -> NormalizedEvent:
        """Handle CME FedWatch and similar market-implied pricing."""
        event = self._base_normalize(raw)
        event.category = "monetary_policy"
        event.confidence = max(event.confidence, 0.75)
        event.importance = EventImportance.HIGH  # Market pricing is always relevant

        # Extract probability numbers
        numbers = self._extract_numbers(raw.content)
        event.key_numbers.update(numbers)

        return event

    # ── Institution Report Handler ─────────────────────────────────────────

    def _handle_institution_report(self, raw: RawEvent) -> NormalizedEvent:
        """Handle IMF, BIS, World Bank, OECD reports."""
        event = self._base_normalize(raw)
        event.category = "economic_data"
        event.confidence = max(event.confidence, 0.8)
        event.importance = EventImportance.MEDIUM

        # Flagship reports = high
        content_lower = (raw.headline + raw.content[:200]).lower()
        if any(
            kw in content_lower
            for kw in [
                "world economic outlook",
                "global financial stability",
                "flagship",
                "annual report",
            ]
        ):
            event.importance = EventImportance.HIGH

        return event

    # ── Filing Handler ─────────────────────────────────────────────────────

    def _handle_filing(self, raw: RawEvent) -> NormalizedEvent:
        """Handle SEC filings and 13F."""
        event = self._base_normalize(raw)
        event.category = (
            "corporate_event" if raw.source == SourceType.SEC_FILING else "market_event"
        )
        event.confidence = max(event.confidence, 0.9)  # Filings are factual
        event.importance = EventImportance.LOW

        # 13F from major funds = high
        if raw.source == SourceType.INSTITUTIONAL_13F:
            event.importance = EventImportance.MEDIUM

        return event

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_numbers(text: str) -> dict:
        """Extract key numerical values from text."""
        if not text:
            return {}
        numbers = {}
        # Pattern: "indicator: value" or "indicator at value" or "indicator +value%"
        patterns = [
            (
                r"(CPI|PCE|PPI|GDP|NFP|unemployment|payrolls?)\s*(?::|at|of|rose|fell|increased|decreased)\s*([\d.]+%?)",
                1,
            ),
            (r"([\d.]+%)\s*(CPI|PCE|GDP|inflation|growth)", 0),
            (r"(\d+)\s*basis\s*points?", 0),
        ]
        for pattern, value_group in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                if isinstance(m, tuple):
                    key = m[1 - value_group].strip().replace("%", "_pct")
                    val_str = m[value_group].replace("%", "")
                    try:
                        numbers[key] = float(val_str)
                    except ValueError:
                        numbers[key] = val_str
        return numbers

    @staticmethod
    def _extract_entities(text: str) -> list[str]:
        """Extract named entities from text."""
        if not text:
            return []
        entities = []
        # Central banks
        cb_map = {
            "fed": "Federal Reserve",
            "federal reserve": "Federal Reserve",
            "fomc": "FOMC",
            "ecb": "ECB",
            "european central bank": "ECB",
            "boj": "BOJ",
            "bank of japan": "BOJ",
            "pboc": "PBOC",
            "people's bank of china": "PBOC",
            "boe": "BOE",
            "bank of england": "BOE",
        }
        # Countries
        country_map = {
            "us": "United States",
            "united states": "United States",
            "america": "United States",
            "china": "China",
            "eurozone": "Eurozone",
            "europe": "Europe",
            "japan": "Japan",
            "uk": "United Kingdom",
            "britain": "United Kingdom",
            "germany": "Germany",
            "france": "France",
        }
        text_lower = text.lower()
        for key, name in {**cb_map, **country_map}.items():
            if key in text_lower:
                entities.append(name)
        return list(set(entities))[:10]

    @staticmethod
    def _classify_by_keywords(text: str) -> tuple[str, str | None]:
        """Classify event category and importance from keywords."""
        t = text.lower()

        # Category
        if any(
            kw in t
            for kw in [
                "fed ",
                "fomc",
                "rate hike",
                "rate cut",
                "interest rate",
                "monetary policy",
                "central bank",
                "basis points",
            ]
        ):
            category = "monetary_policy"
        elif any(
            kw in t
            for kw in [
                "cpi ",
                "inflation",
                "pce",
                "ppi",
                "nfp",
                "payroll",
                "gdp ",
                "unemployment",
                "jobs report",
                "ism ",
            ]
        ):
            category = "economic_data"
        elif any(kw in t for kw in ["war", "conflict", "sanction", "geopolitical", "tariff"]):
            category = "geopolitical"
        elif any(
            kw in t
            for kw in [
                "stock",
                "equity",
                "bond",
                "yield",
                "currency",
                "oil ",
                "gold ",
                "market",
                "selloff",
                "rally",
            ]
        ):
            category = "market_event"
        else:
            category = "other"

        # Importance
        if any(
            kw in t
            for kw in [
                "breaking",
                "urgent",
                "crisis",
                "crash",
                "surprise",
                "unexpected",
                "shock",
                "pivot",
                "emergency",
            ]
        ):
            importance = "critical"
        elif any(kw in t for kw in ["significant", "major", "key", "important", "record"]):
            importance = "high"
        elif any(kw in t for kw in ["moderate", "notable"]):
            importance = "medium"
        else:
            importance = "low"

        return category, importance

    @staticmethod
    def _detect_sentiment(text: str) -> str:
        """Simple lexicon-based sentiment detection."""
        if not text:
            return "neutral"
        t = text.lower()

        bullish = sum(
            1
            for w in [
                "surge",
                "rally",
                "jump",
                "beat",
                "strong",
                "boost",
                "optimistic",
                "easing",
                "dovish",
                "accommodative",
            ]
            if w in t
        )
        bearish = sum(
            1
            for w in [
                "plunge",
                "crash",
                "tumble",
                "miss",
                "weak",
                "recession",
                "tightening",
                "hawkish",
                "contraction",
                "fear",
            ]
            if w in t
        )

        if bullish > bearish + 1:
            return "bullish"
        elif bearish > bullish + 1:
            return "bearish"
        return "neutral"

    @staticmethod
    def _hawkish_dovish_score(text: str) -> float:
        """Score text on hawkish (-1 dove) to (+1 hawk) scale."""
        if not text:
            return 0.0
        t = text.lower()

        hawkish_words = [
            "tighten",
            "hawkish",
            "restrictive",
            "inflation risk",
            "overheating",
            "raise rates",
            "hike",
            "taper",
            "normalize",
            "exit",
            "withdraw",
        ]
        dovish_words = [
            "ease",
            "dovish",
            "accommodative",
            "patient",
            "gradual",
            "data dependent",
            "below target",
            "slack",
            "uncertainty",
            "downside risk",
            "patience",
        ]

        hawk_score = sum(1 for w in hawkish_words if w in t)
        dove_score = sum(1 for w in dovish_words if w in t)
        total = hawk_score + dove_score

        return (hawk_score - dove_score) / max(total, 1)

    @staticmethod
    def _extract_economic_numbers(text: str, raw_data: dict) -> dict:
        """Extract specific economic indicator values."""
        numbers = {}
        # From raw_data first
        for key in ["actual", "forecast", "previous", "prior", "consensus"]:
            if key in raw_data and raw_data[key] is not None:
                numbers[key] = raw_data[key]

        # From text patterns
        patterns = [
            (r"(CPI|inflation)\s*(?:YoY|y/y)?\s*:?\s*([\d.]+)%", "cpi_yoy"),
            (r"(Core\s*CPI|core\s*inflation)\s*:?\s*([\d.]+)%", "core_cpi_yoy"),
            (r"(NFP|nonfarm|payrolls?)\s*:?\s*([\d,]+)", "nfp"),
            (r"(unemployment\s*rate)\s*:?\s*([\d.]+)%", "unemployment_rate"),
            (r"(GDP)\s*(?:QoQ|growth)?\s*:?\s*([\d.]+)%", "gdp_qoq"),
            (r"(ISM)\s*(?:manufacturing)?\s*:?\s*([\d.]+)", "ism_manufacturing"),
        ]
        for pattern, key in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                try:
                    numbers[key] = float(m.group(2).replace(",", ""))
                except ValueError:
                    pass

        return numbers

    @staticmethod
    def _is_good_surprise(headline: str) -> bool:
        """Determine if a higher number is 'good' for this indicator."""
        good_high = [
            "nfp",
            "payroll",
            "gdp",
            "ism",
            "retail sales",
            "industrial production",
            "consumer confidence",
            "housing starts",
        ]
        _good_low = ["unemployment", "jobless claims", "inventory"]
        h = headline.lower()
        return any(g in h for g in good_high)

    @staticmethod
    def _economic_data_importance(headline: str) -> EventImportance:
        """Rate importance of economic data release."""
        h = headline.lower()
        tier1 = ["nfp", "cpi", "fomc", "gdp"]
        tier2 = ["ppi", "retail sales", "ism", "unemployment", "pce"]

        if any(t in h for t in tier1):
            return EventImportance.HIGH
        elif any(t in h for t in tier2):
            return EventImportance.MEDIUM
        return EventImportance.LOW

    @staticmethod
    def _estimate_importance(raw: RawEvent) -> EventImportance:
        """Quick importance estimate from raw event metadata."""
        if raw.is_breaking and raw.priority > 5:
            return EventImportance.CRITICAL
        if raw.priority >= 3:
            return EventImportance.HIGH
        if raw.priority >= 1:
            return EventImportance.MEDIUM
        return EventImportance.LOW

    def get_stats(self) -> dict:
        return {
            "route_count": dict(self._route_count),
            "total_routed": sum(self._route_count.values()),
            "handlers_registered": len(self.HANDLERS),
        }
