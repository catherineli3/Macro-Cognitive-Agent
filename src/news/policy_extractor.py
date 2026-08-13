"""PolicyExtractor — Extract policy signals from central bank communication.

Quality: Central bank communication is the most important macro input.
Professional researchers parse every word of FOMC/ECB/BOJ/PBOC statements.
This module extracts: stance, forward guidance, reaction function, pivot signals.
"""

from __future__ import annotations

import uuid

from src.news.schemas import NewsSourceType, PolicySignal, ResearchEvent


class PolicyExtractor:
    """Extract structured policy signals from CB communications.

    Input: ResearchEvents from central bank sources
    Output: PolicySignal objects with stance, guidance, hawkish/dovish scoring
    """

    # Known central bank communication patterns
    CB_PATTERNS = {
        "fed": {
            "hawkish_phrases": [
                "restrictive stance",
                "further tightening",
                "inflation remains elevated",
                "above the longer-run goal",
                "additional policy firming",
                "strongly committed",
                "labor market remains tight",
                "insufficiently restrictive",
                "premature to cut",
                "need to see more evidence",
            ],
            "dovish_phrases": [
                "considerable progress",
                "moving toward better balance",
                "moderating inflation",
                "appropriate to dial back",
                "risks to both sides",
                "labor market in better balance",
                "disinflation has resumed",
                "real rate is restrictive",
            ],
            "pivot_phrases": [
                "at or near",
                "peak rate",
                "next move",
                "likely to be",
                "any adjustment",
                "could be appropriate",
            ],
            "watched_indicators": [
                "inflation",
                "labor market",
                "financial conditions",
                "economic activity",
                "global developments",
            ],
        },
        "ecb": {
            "hawkish_phrases": [
                "inflation expectations",
                "wage pressures",
                "restrictive",
                "sufficiently long",
                "forcefully",
                "determined",
                "further tightening",
                "upside risks",
            ],
            "dovish_phrases": [
                "significant progress",
                "declining",
                "data-dependent",
                "gradual",
                "transmission",
                "lagged effects",
            ],
            "pivot_phrases": ["sufficiently restrictive", "terminal rate", "plateau"],
            "watched_indicators": ["inflation", "wages", "profits", "financing conditions"],
        },
        "boj": {
            "hawkish_phrases": [
                "normalization",
                "exit",
                "adjustment",
                "flexibility",
                "yield curve control band",
                "wage growth",
            ],
            "dovish_phrases": [
                "patiently",
                "accommodative",
                "sustainably",
                "virtuous cycle",
                "continued easing",
                "deflation",
                "price stability target",
            ],
            "pivot_phrases": ["review", "assessment", "side effects"],
            "watched_indicators": [
                "wages",
                "service prices",
                "output gap",
                "inflation expectations",
            ],
        },
        "pboc": {
            "hawkish_phrases": [
                "prudent",
                "targeted",
                "structural",
                "property sector risk",
                "shadow banking",
                "financial stability",
            ],
            "dovish_phrases": [
                "counter-cyclical",
                "ample liquidity",
                "credit support",
                "real economy",
                "small and micro",
                "inclusive",
                "moderately accommodative",
                "cut reserve requirement",
            ],
            "pivot_phrases": ["targeted RRR cut", "LPR reform", "MLF operations"],
            "watched_indicators": ["CPI", "PPI", "credit growth", "housing", "investment"],
        },
    }

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def extract(self, event: ResearchEvent) -> PolicySignal | None:
        """Extract policy signal from a CB communication event.

        Returns None if the event is not from a central bank source.
        """
        if event.source_type not in (
            NewsSourceType.CENTRAL_BANK,
            NewsSourceType.CENTRAL_BANK_SPEECH,
        ):
            return None

        # Determine which CB
        cb_name = self._identify_cb(event)
        if not cb_name:
            return None

        patterns = self.CB_PATTERNS.get(cb_name, self._generic_cb_pattern())

        # Extract text
        text = self._get_text(event).lower()

        # Score hawkish vs dovish
        hawkish_score = self._score_phrases(text, patterns.get("hawkish_phrases", []))
        dovish_score = self._score_phrases(text, patterns.get("dovish_phrases", []))
        pivot_score = self._score_phrases(text, patterns.get("pivot_phrases", []))

        net_score = hawkish_score - dovish_score
        net_score = max(-1.0, min(1.0, net_score))

        # Determine stance
        if net_score > 0.3:
            stance = "hawkish"
        elif net_score < -0.3:
            stance = "dovish"
        else:
            stance = "neutral"

        # Pivot detection
        stance_change = "unchanged"
        if pivot_score > 0.3 and abs(net_score) < 0.5:
            stance_change = "pivoting"
        elif net_score > 0.5:
            stance_change = "tightening"
        elif net_score < -0.5:
            stance_change = "easing"

        # Forward guidance extraction
        guidance = self._extract_guidance(text, stance)

        # Rate path
        rate_path = self._extract_rate_path(text, stance)

        # Key phrases found
        key_phrases = self._extract_key_phrases(text, patterns)

        # Market reaction
        market_reaction = self._infer_market_reaction(event, net_score)

        # Build signal
        signal = PolicySignal(
            signal_id=f"SIG_{str(uuid.uuid4())[:8]}",
            central_bank=cb_name.upper(),
            event_id=event.event_id,
            current_stance=stance,
            stance_change=stance_change,
            stance_confidence=0.7 if abs(net_score) > 0.3 else 0.5,
            forward_guidance=guidance,
            rate_path_signal=rate_path,
            key_phrases=key_phrases,
            watched_indicators=patterns.get("watched_indicators", []),
            hawkish_dovish_score=round(net_score, 2),
            market_reaction=market_reaction,
            source_text=event.description[:200],
        )

        # Update the ResearchEvent with policy information
        self._update_event(event, signal)

        return signal

    def extract_batch(self, events: list[ResearchEvent]) -> list[PolicySignal]:
        """Extract policy signals from a batch of events."""
        signals = []
        for event in events:
            signal = self.extract(event)
            if signal:
                signals.append(signal)
        return signals

    def get_cb_stance(self, signals: list[PolicySignal]) -> dict:
        """Aggregate policy stance across multiple CBs.

        Returns:
            {cb_name: {stance, score, trend}}
        """
        by_cb = {}
        for sig in signals:
            if sig.central_bank not in by_cb:
                by_cb[sig.central_bank] = {
                    "stance": sig.current_stance,
                    "score": sig.hawkish_dovish_score,
                    "change": sig.stance_change,
                    "key_phrases": sig.key_phrases,
                }
        return by_cb

    # ── Extraction Helpers ──

    def _identify_cb(self, event: ResearchEvent) -> str | None:
        """Identify which central bank an event relates to."""
        text = (event.title + " " + event.description).lower()
        for entity in event.entities:
            el = entity.lower()
            if "fed" in el or "federal" in el:
                return "fed"
            if "ecb" in el or "european" in el or "lagarde" in el:
                return "ecb"
            if "boj" in el or "bank of japan" in el or "ueda" in el:
                return "boj"
            if "pboc" in el or "people's bank" in el or "china" in el:
                return "pboc"
            if "boe" in el or "bank of england" in el:
                return "boe"

        # Text-based fallback
        if "fed" in text or "fomc" in text or "powell" in text:
            return "fed"
        if "ecb" in text or "european central" in text:
            return "ecb"
        if "boj" in text or "bank of japan" in text:
            return "boj"
        if "pboc" in text or "people's bank" in text:
            return "pboc"

        return None

    @staticmethod
    def _get_text(event: ResearchEvent) -> str:
        """Get combined text for analysis."""
        parts = [event.title, event.description]
        for article in event.news_articles:
            parts.append(article.content)
        return " ".join(parts)

    @staticmethod
    def _score_phrases(text: str, phrases: list[str]) -> float:
        """Score text against a list of known phrases."""
        if not phrases:
            return 0.0
        hits = sum(1 for p in phrases if p in text)
        return min(hits / max(len(phrases), 1), 1.0)

    def _extract_guidance(self, text: str, stance: str) -> str:
        """Extract forward guidance text."""
        guidance_markers = [
            "forward guidance",
            "appropriate path",
            "future adjustments",
            "data dependent",
            "meeting by meeting",
            "any decision",
            "remain data dependent",
            "proceed carefully",
        ]
        found = [m for m in guidance_markers if m in text]
        if found:
            return f"CB signals: data-dependent approach. Key language: {', '.join(found[:3])}"
        return f"Forward guidance not explicitly stated. Current stance: {stance}."

    def _extract_rate_path(self, text: str, stance: str) -> str:
        """Infer rate path signal."""
        if "rate hike" in text or "further tightening" in text or "additional firming" in text:
            return "higher"
        if "rate cut" in text or "dial back" in text or "easing" in text:
            return "lower"
        if "unchanged" in text or "hold" in text or "pause" in text:
            return "steady"
        return "uncertain"

    def _extract_key_phrases(self, text: str, patterns: dict) -> list[str]:
        """Extract key phrases that were found in the text."""
        found = []
        for phrase in patterns.get("hawkish_phrases", []):
            if phrase in text:
                found.append(f"[Hawkish] {phrase}")
        for phrase in patterns.get("dovish_phrases", []):
            if phrase in text:
                found.append(f"[Dovish] {phrase}")
        for phrase in patterns.get("pivot_phrases", []):
            if phrase in text:
                found.append(f"[Pivot] {phrase}")
        return found[:6]

    def _infer_market_reaction(self, event: ResearchEvent, net_score: float) -> str:
        """Infer how markets likely reacted."""
        text = (event.title + " " + event.description).lower()

        if any(w in text for w in ["stocks rallied", "stocks surged", "equities jumped"]):
            return "Risk-on reaction"

        if any(w in text for w in ["stocks fell", "stocks dropped", "selloff"]):
            return "Risk-off reaction"

        if net_score > 0.2:
            return "Bonds sold off, USD strengthened (typical hawkish reaction)"
        elif net_score < -0.2:
            return "Bonds rallied, USD weakened (typical dovish reaction)"

        return "Mixed/ muted reaction"

    def _update_event(self, event: ResearchEvent, signal: PolicySignal):
        """Update the ResearchEvent with policy signal information."""
        if signal.hawkish_dovish_score > 0.2:
            event.market_impact = event.market_impact.__class__.BEARISH
        elif signal.hawkish_dovish_score < -0.2:
            event.market_impact = event.market_impact.__class__.BULLISH

    @staticmethod
    def _generic_cb_pattern() -> dict:
        """Generic CB pattern for unknown central banks."""
        return {
            "hawkish_phrases": ["tightening", "inflation", "restrictive", "hike"],
            "dovish_phrases": ["easing", "accommodative", "support", "cut"],
            "pivot_phrases": ["change", "shift", "adjustment", "review"],
            "watched_indicators": ["inflation", "growth", "labor market"],
        }
