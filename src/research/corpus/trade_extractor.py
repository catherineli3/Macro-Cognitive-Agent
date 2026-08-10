"""V5.1 Trade Extractor — Extract trade ideas from institutional research documents.

Professional macro research almost always includes actionable trade ideas:
    - Direction (long/short/neutral)
    - Instrument (SPX, 10Y UST, EUR/USD, etc.)
    - Rationale (why this trade)
    - Conviction level
    - Risk factors
    - Stop loss / target levels

These become training data for V5.2 Trade Stage prompts.
"""

from __future__ import annotations

import re
from typing import Optional

from src.research.corpus.schemas import (
    ResearchDocument,
    Paragraph,
    TradeIdea,
)
from src.research.corpus.memo_segmenter import MemoSegmenter


class TradeExtractor:
    """Extract actionable trade ideas from macro research documents."""

    # ── Trade Markers ─────────────────────────────────────────────────

    DIRECTION_MARKERS: dict[str, list[str]] = {
        "long": [
            r'\b(?:long|buy|overweight|add|accumulate|initiate\s+long)\b',
            r'\b(?:bullish|constructive|positive|favorable)\s+(?:on|view|outlook|stance)\b',
            r'\b(?:we\s+(?:like|favor|prefer|recommend|advocate))\b',
            r'\b(?:upside|appreciation|outperformance)\s+(?:potential|case|scenario)\b',
        ],
        "short": [
            r'\b(?:short|sell|underweight|reduce|trim|exit|initiate\s+short)\b',
            r'\b(?:bearish|cautious|negative|unfavorable)\s+(?:on|view|outlook|stance)\b',
            r'\b(?:we\s+(?:dislike|avoid|recommend\s+sell|advise\s+against))\b',
            r'\b(?:downside|depreciation|underperformance)\s+(?:risk|potential|case)\b',
        ],
        "neutral": [
            r'\b(?:neutral|market[\s-]?weight|hold|maintain|no\s+strong\s+view)\b',
            r'\b(?:range[\s-]?bound|sideways|mixed\s+picture)\b',
        ],
    }

    INSTRUMENT_PATTERNS = [
        # Equities
        r'\b(?:S&P\s*500|SPX|Nasdaq|NDX|Dow\s*Jones|DJIA|Russell\s*2000|RTY|MSCI)\b',
        r'\b(?:STOXX\s*600|Euro\s*Stoxx|FTSE\s*100|Nikkei\s*225|CSI\s*300|Hang\s*Seng|HSI)\b',
        r'\b(?:equit(?:y|ies)|stocks?|index|indices)\b',
        # Fixed Income
        r'\b(?:10(?:Y|yr?|[\s-]?year)|2(?:Y|yr?|[\s-]?year)|30(?:Y|yr?|[\s-]?year))\s+(?:UST|Treasury|T[\s-]?note|T[\s-]?bond)\b',
        r'\b(?:Bund|Gilt|JGB|OAT|BTP)\b',
        r'\b(?:yield\s+curve|flattener|steepener|duration|fixed\s+income)\b',
        # FX
        r'\b(?:EUR/USD|USD/JPY|GBP/USD|USD/CNY|AUD/USD|DXY|dollar\s+index)\b',
        r'\b(?:foreign\s+exchange|currency|forex|fx)\b',
        # Commodities
        r'\b(?:WTI|Brent|crude\s+oil|gold|copper|natural\s+gas|commodit(?:y|ies))\b',
        # Credit
        r'\b(?:CDX|ITRAXX|credit\s+spread|HY|IG|high\s+yield|investment\s+grade)\b',
        # Volatility
        r'\b(?:VIX|VSTOXX|volatility|vol)\b',
    ]

    RATIONALE_MARKERS = [
        r'(?:because|since|as|due\s+to|given\s+that|owing\s+to)\s+(.{10,100})',
        r'(?:the\s+)?(?:rationale|thesis|reasoning|logic)\s+(?:is|behind\s+this)\s+(?:is\s+)?(.{10,100})',
        r'(?:this\s+trade\s+)?(?:works|benefits|performs\s+well)\s+(?:when|if|in|because)(.{10,100})',
    ]

    CONVICTION_MARKERS: dict[str, float] = {
        r'\b(?:highest\s+conviction|top\s+pick|best\s+idea|strongest\s+view)\b': 0.95,
        r'\b(?:high\s+conviction|strong\s+view|core\s+position)\b': 0.85,
        r'\b(?:moderate\s+conviction|tactical|opportunistic)\b': 0.65,
        r'\b(?:low\s+conviction|small\s+position|exploratory|pilot)\b': 0.35,
    }

    STOP_TARGET_PATTERNS = [
        r'(?:stop[\s-]?(?:loss|out)\s+(?:at|of|near|around)\s+)?(\d[\d,.]*\s*(?:%|bps|points?)?)',
        r'(?:target\s+(?:at|of|near|around)\s+)?(\d[\d,.]*\s*(?:%|bps|points?)?)',
        r'(?:entry\s+(?:at|of|near|around)\s+)?(\d[\d,.]*)\s*(?:-|to)\s*(\d[\d,.]*)',
    ]

    RISK_MARKERS = [
        r'(?:key\s+)?risk(?:s)?\s+(?:to\s+this\s+(?:trade|view|call)\s+)?(?:is|are|include)',
        r'(?:what\s+(?:could|could)\s+go\s+wrong)',
        r'(?:this\s+trade\s+(?:fails|loses|underperforms)\s+(?:if|when))',
        r'(?:vulnerable?\s+to)',
    ]

    def __init__(self):
        self.segmenter = MemoSegmenter()

    # ── Public Interface ─────────────────────────────────────────────

    def extract(self, doc: ResearchDocument) -> list[TradeIdea]:
        """Extract all trade ideas from a ResearchDocument.

        Focuses on investment_implications and conclusion sections.
        """
        sections = self.segmenter.segment(doc)
        trades = []

        trade_section_names = {
            "investment_implications", "conclusion",
            "executive_summary", "key_themes",
        }

        for section in sections:
            if section.name in trade_section_names:
                section_trades = self._extract_from_section(section)
                trades.extend(section_trades)

        return trades

    def extract_from_text(self, text: str) -> list[TradeIdea]:
        """Extract trade ideas from raw text."""
        paras = []
        for i, para_text in enumerate(text.split('\n\n')):
            if para_text.strip():
                paras.append(Paragraph(index=i, text=para_text.strip()))
        return self._extract_trades(paras)

    # ── Extraction Logic ──────────────────────────────────────────────

    def _extract_from_section(self, section) -> list[TradeIdea]:
        """Extract trades from a MemoSection."""
        return self._extract_trades(section.paragraphs)

    def _extract_trades(self, paragraphs: list[Paragraph]) -> list[TradeIdea]:
        """Extract trade ideas from paragraphs."""
        trades = []

        for para in paragraphs:
            if para.word_count < 10:
                continue

            text = para.text
            direction = self._detect_direction(text)

            if direction:
                trade = TradeIdea(source_paragraph_ids=[para.id])
                trade.direction = direction
                trade.instrument = self._extract_instrument(text)
                trade.rationale = self._extract_rationale(text)
                trade.conviction = self._extract_conviction(text)
                trade.time_horizon = self._extract_horizon(text)
                trade.risk_factors = self._extract_risk_factors(text)

                # Extract stop loss and target
                stop_target = self._extract_stop_target(text)
                if stop_target:
                    trade.stop_loss = stop_target.get("stop", "")
                    trade.target = stop_target.get("target", "")

                # Build description
                trade.description = self._build_description(trade)

                if trade.instrument or trade.rationale:
                    trades.append(trade)

        return trades

    def _detect_direction(self, text: str) -> str:
        """Detect trade direction from text."""
        text_lower = text.lower()
        scores = {}

        for direction, patterns in self.DIRECTION_MARKERS.items():
            score = sum(1 for p in patterns if re.search(p, text_lower))
            if score > 0:
                scores[direction] = score

        if not scores:
            return ""

        return max(scores, key=scores.get)

    def _extract_instrument(self, text: str) -> str:
        """Extract the traded instrument."""
        instruments = []
        for pattern in self.INSTRUMENT_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            instruments.extend(matches)

        if instruments:
            # Return the most specific instrument (longest match)
            return max(instruments, key=len)

        return ""

    def _extract_rationale(self, text: str) -> str:
        """Extract trade rationale."""
        for pattern in self.RATIONALE_MARKERS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                return groups[-1].strip()

        return ""

    def _extract_conviction(self, text: str) -> float:
        """Extract conviction level."""
        text_lower = text.lower()
        best_conviction = 0.5  # Default moderate

        for pattern, conviction in self.CONVICTION_MARKERS.items():
            if re.search(pattern, text_lower):
                return conviction

        # If direction is detected but no explicit conviction,
        # use a moderate default
        return 0.6

    def _extract_horizon(self, text: str) -> str:
        """Extract trade time horizon."""
        horizon_patterns = [
            (r'\b(?:short[\s-]?term|tactical|weeks?)\b', 'short-term'),
            (r'\b(?:medium[\s-]?term|quarter|months?)\b', 'medium-term'),
            (r'\b(?:long[\s-]?term|strategic|year)\b', 'long-term'),
        ]

        for pattern, horizon in horizon_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return horizon

        return "unspecified"

    def _extract_risk_factors(self, text: str) -> list[str]:
        """Extract risk factors."""
        risks = []

        for pattern in self.RISK_MARKERS:
            match = re.search(pattern + r'.{10,120}[.!?]', text, re.IGNORECASE)
            if match:
                risks.append(match.group(0).strip())

        return risks[:3]

    def _extract_stop_target(self, text: str) -> dict[str, str]:
        """Try to extract stop loss and target levels."""
        result = {}

        # Look for explicit stop/target mentions
        stop_match = re.search(
            r'stop[\s-]?(?:loss|out)\s+(?:at|of|near|around)\s+([\d,.]+)',
            text, re.IGNORECASE
        )
        if stop_match:
            result["stop"] = stop_match.group(1)

        target_match = re.search(
            r'target\s+(?:at|of|near|around)\s+([\d,.]+)',
            text, re.IGNORECASE
        )
        if target_match:
            result["target"] = target_match.group(1)

        return result

    def _build_description(self, trade: TradeIdea) -> str:
        """Build a human-readable description of the trade idea."""
        parts = []

        direction_map = {
            "long": "Long",
            "short": "Short",
            "neutral": "Neutral on",
        }
        direction_word = direction_map.get(trade.direction, trade.direction)

        if trade.instrument:
            parts.append(f"{direction_word} {trade.instrument}")

        if trade.rationale:
            parts.append(trade.rationale)

        if trade.time_horizon and trade.time_horizon != "unspecified":
            parts.append(f"Horizon: {trade.time_horizon}")

        return ". ".join(parts) if parts else trade.direction
