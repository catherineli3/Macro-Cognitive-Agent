"""V5.1 Prediction Extractor — Extract predictions and forecasts from research.

Institutional macro research almost always contains explicit or
implicit predictions. This module extracts:
    - The prediction claim
    - Probability (explicit or implied)
    - Time horizon
    - Conditions / assumptions
    - Invalidation conditions
    - Asset market implications

These become training data for V5.2 Prediction Stage prompts.
"""

from __future__ import annotations

import re

from src.research.corpus.memo_segmenter import MemoSegmenter
from src.research.corpus.schemas import (
    Paragraph,
    PredictionUnit,
    ResearchDocument,
)


class PredictionExtractor:
    """Extract predictions from institutional macro research documents."""

    # ── Prediction Markers ────────────────────────────────────────────

    PREDICTION_MARKERS = [
        r"(?:we\s+)?(?:forecast|project|predict|expect|anticipate|estimate)\s+(?:that\s+)?",
        r"(?:we\s+)?(?:see|look\s+for)\s+(?:\w+\s+){0,5}(?:a|an|the)\s+",
        r"(?:our\s+)?(?:forecast|projection|prediction|estimate)\s+(?:is|for|of)",
        r"(?:we\s+)?(?:are\s+)?(?:looking|positioning|preparing)\s+for",
        r"(?:likely|expected|projected|forecast)\s+to\s+(?:be|reach|rise|fall|grow|decline)",
        r"(?:will\s+(?:likely|probably|almost\s+certainly|very\s+likely)\s+)?(?:rise|fall|grow|decline|increase|decrease)",
        r"(?:should\s+)?(?:end\s+the\s+(?:year|quarter|month)\s+at|reach\s+\d)",
        r"(?:we\s+)?(?:target|are\s+targeting)\s+(?:a|an|the)\s+",
        r"(?:our\s+(?:year[\s-]?end|q\d|12[\s-]?month)\s+(?:target|forecast))",
    ]

    PROBABILITY_PATTERNS: dict[str, float] = {
        r"\b(?:almost\s+certain|certainly|virtually\s+certain|near[\s-]?certainty)\b": 0.95,
        r"\b(?:very\s+likely|highly\s+likely|strong\s+probability)\b": 0.85,
        r"\b(?:likely|probable|expected\s+to|base\s+case)\b": 0.75,
        r"\b(?:more\s+likely\s+than\s+not|on\s+balance|probably)\b": 0.60,
        r"\b(?:may|might|could|possibly|potential)\b": 0.45,
        r"\b(?:unlikely|improbable|low\s+probability)\b": 0.25,
        r"\b(?:very\s+unlikely|highly\s+unlikely|remote\s+chance)\b": 0.10,
    }

    # Explicit probability patterns
    EXPLICIT_PROB_PATTERNS = [
        r"(\d{1,2})%\s+(?:probability|chance|likelihood|odds)",
        r"(?:probability|chance|likelihood)\s+(?:of|is)\s+(\d{1,2})%",
        r"(\d{1,2})/(\d{1,2})\s+(?:odds|chance)",
    ]

    TIME_HORIZON_PATTERNS: dict[str, str] = {
        r"\b(?:next|coming|following|upcoming)\s+week\b": "1 week",
        r"\b(?:next|coming|following|upcoming)\s+month\b": "1 month",
        r"\b(?:next|coming)\s+quarter\b": "1 quarter",
        r"\b(?:end\s+of\s+)?(?:Q[1-4]|q[1-4])\s*(\d{4})?\b": "quarter",
        r"\b(?:end[\s-]?of[\s-]?year|year[\s-]?end|end[\s-]?202\d)\b": "year-end",
        r"\b(?:H[1-2]\s*(\d{4})?|first\s+half|second\s+half)\b": "half-year",
        r"\b(?:over\s+the\s+next\s+)?(\d+)[\s-]*(?:month|week|quarter|year)s?\b": "period",
        r"\b(?:by\s+)?(?:mid[\s-]?(?:20)?\d{2}|early\s+(?:20)?\d{2}|late\s+(?:20)?\d{2})\b": "date",
        r"\b(?:in\s+the\s+)?(?:near|medium|longer?|short)\s+term\b": "term",
    }

    INVALIDATION_MARKERS = [
        r"(?:unless|except\s+if|provided\s+that\s+not|barring)",
        r"(?:this\s+(?:view|forecast|prediction|call)\s+(?:would\s+be\s+)?)?(?:invalid|wrong|incorrect|off)\s+if",
        r"(?:if\s+)?(?:contrary|opposite)\s+(?:to\s+our\s+)?(?:view|expectation)",
        r"(?:the\s+key\s+risk\s+to\s+this\s+(?:view|forecast|call)\s+is)",
        r"(?:what\s+would\s+(?:prove|make)\s+(?:us|this|the\s+view)\s+wrong)",
        r"(?:we\s+would\s+(?:revisit|reassess|change|reverse)\s+(?:this|our)\s+(?:view|call)\s+if)",
    ]

    ASSET_IMPLICATION_MARKERS = [
        r"(?:this\s+)?(?:implies|suggests|means|points\s+to)\s+(?:a\s+)?(?:bullish|bearish|positive|negative|favorable|unfavorable)\s+(?:outlook|environment|backdrop)\s+for",
        r"(?:we\s+)?(?:favor|prefer|like|are\s+bullish\s+on|are\s+bearish\s+on|overweight|underweight)\s+",
        r"(?:should\s+)?(?:benefit|support|boost|help|hurt|pressure|weigh\s+on|drag\s+on)\s+(?:the\s+)?",
        r"(?:in\s+this\s+environment|scenario)\s*,?\s*(?:we\s+)?(?:would|should)\s+(?:own|hold|buy|sell|avoid)",
    ]

    def __init__(self):
        self.segmenter = MemoSegmenter()

    # ── Public Interface ─────────────────────────────────────────────

    def extract(self, doc: ResearchDocument) -> list[PredictionUnit]:
        """Extract all predictions from a ResearchDocument.

        Focuses on macro_outlook, investment_implications, and conclusion sections.
        """
        sections = self.segmenter.segment(doc)
        predictions = []

        pred_section_names = {
            "macro_outlook",
            "investment_implications",
            "conclusion",
            "executive_summary",
            "key_themes",
        }

        for section in sections:
            if section.name in pred_section_names:
                section_preds = self._extract_from_section(section)
                predictions.extend(section_preds)

        return predictions

    def extract_from_text(self, text: str) -> list[PredictionUnit]:
        """Extract predictions from raw text."""
        # Create minimal paragraphs
        paras = []
        for i, para_text in enumerate(text.split("\n\n")):
            if para_text.strip():
                paras.append(Paragraph(index=i, text=para_text.strip()))
        return self._extract_predictions(paras)

    # ── Extraction Logic ──────────────────────────────────────────────

    def _extract_from_section(self, section) -> list[PredictionUnit]:
        """Extract predictions from a MemoSection."""
        return self._extract_predictions(section.paragraphs)

    def _extract_predictions(self, paragraphs: list[Paragraph]) -> list[PredictionUnit]:
        """Extract predictions from paragraphs."""
        predictions = []

        for para in paragraphs:
            if para.word_count < 10:
                continue

            text = para.text
            if self._contains_prediction(text):
                pred = PredictionUnit(source_paragraph_ids=[para.id])

                pred.claim = self._extract_claim(text)
                pred.probability = self._extract_probability(text)
                pred.time_horizon = self._extract_time_horizon(text)
                pred.conditions = self._extract_conditions(text)
                pred.invalidation = self._extract_invalidation(text)
                pred.asset_implication = self._extract_asset_implication(text)

                if pred.claim:
                    predictions.append(pred)

        return predictions

    def _contains_prediction(self, text: str) -> bool:
        """Check if text contains a prediction."""
        return any(re.search(p, text, re.IGNORECASE) for p in self.PREDICTION_MARKERS)

    def _extract_claim(self, text: str) -> str:
        """Extract the prediction claim from text."""
        for pattern in self.PREDICTION_MARKERS:
            match = re.search(pattern + r".{20,200}[.!?]", text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return ""

    def _extract_probability(self, text: str) -> float:
        """Extract probability from text (explicit or implied)."""
        # Check explicit probability first
        for pattern in self.EXPLICIT_PROB_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return float(groups[0]) / float(groups[1])
                return float(match.group(1)) / 100.0

        # Check probability phrases
        text_lower = text.lower()
        for pattern, prob in self.PROBABILITY_PATTERNS.items():
            if re.search(pattern, text_lower):
                return prob

        return 0.55  # Default moderate probability

    def _extract_time_horizon(self, text: str) -> str:
        """Extract time horizon from text."""
        text_lower = text.lower()

        for pattern, horizon in self.TIME_HORIZON_PATTERNS.items():
            match = re.search(pattern, text_lower)
            if match:
                if horizon == "period":
                    number = match.group(1)
                    unit = match.group(0).replace(number, "").strip()
                    return f"{number} {unit}"
                if horizon in ("quarter", "half-year", "date", "term"):
                    return match.group(0)
                return horizon

        return "unspecified"

    def _extract_conditions(self, text: str) -> list[str]:
        """Extract conditions or assumptions."""
        conditions = []

        # Find conditional clauses
        if_clauses = re.findall(
            r"(?:if|assuming|provided\s+that|as\s+long\s+as|given\s+that)\s+(.{10,100})[.,]",
            text,
            re.IGNORECASE,
        )
        conditions.extend([c.strip() for c in if_clauses[:3]])

        return conditions

    def _extract_invalidation(self, text: str) -> str:
        """Extract invalidation conditions."""
        for pattern in self.INVALIDATION_MARKERS:
            match = re.search(pattern + r".{10,150}[.!?]", text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return ""

    def _extract_asset_implication(self, text: str) -> str:
        """Extract asset market implications."""
        for pattern in self.ASSET_IMPLICATION_MARKERS:
            match = re.search(pattern + r".{10,150}[.!?]", text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return ""
