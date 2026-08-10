"""V5.1 Reasoning Extractor — Extract causal reasoning chains from research memos.

Identifies the full reasoning structure within paragraphs:
    Observation → Evidence → Pattern → Historical Analogy →
    Hypothesis → Counter Consideration → Conclusion

These extracted units become training data for V5.2 Reasoning Pipeline prompts.
No more hand-written prompts. All prompts derived from real research.
"""

from __future__ import annotations

import re
from typing import Optional

from src.research.corpus.schemas import (
    ResearchDocument,
    Paragraph,
    ReasoningUnit,
)
from src.research.corpus.memo_segmenter import MemoSection, MemoSegmenter


class ReasoningExtractor:
    """Extract causal reasoning chains from institutional research documents.

    Scans paragraphs for linguistic markers of each reasoning step:
    observation → evidence → pattern → analogy → hypothesis →
    counter → conclusion → confidence.
    """

    # ── Linguistic Markers ─────────────────────────────────────────────

    OBSERVATION_MARKERS = [
        r'(?:we\s+)?(?:observed?|noted?|saw|seen)\s+that',
        r'(?:the\s+)?data\s+shows?\b',
        r'(?:recent|latest)\s+(?:data|release|report|figure)',
        r'(?:has\s+)?(?:risen|fallen|increased|decreased|declined|surged|plunged)',
        r'(?:came\s+in\s+at|printed\s+at|registered)\s+',
        r'(?:now\s+stands?\s+at|currently\s+(?:at|running\s+at))',
        r'as\s+of\s+\w+\s+\d{1,2}',
    ]

    EVIDENCE_MARKERS = [
        r'(?:as\s+)?evidence[ds]?\s+(?:by|from)',
        r'supported\s+by',
        r'(?:according|based)\s+to\s+(?:the\s+)?(?:latest|recent)',
        r'(?:data\s+)?(?:confirm|support|validate|corroborate)s?\b',
        r'(?:the\s+)?(?:chart|figure|table)\s+(?:\d+|below|above)\s+shows',
        r'(?:source|data):\s+',
        r'suggest(?:s|ed|ing)?\s+(?:that|a)',
    ]

    PATTERN_MARKERS = [
        r'(?:pattern|trend|cycle|regime)\s+(?:of|in|toward|shift)',
        r'(?:consistent|inconsistent)\s+with',
        r'(?:historically|typically|usually|normally)',
        r'(?:this\s+is\s+)?reminiscent\s+of',
        r'(?:fits?\s+(?:the|a)\s+)?(?:pattern|mold|template)',
        r'(?:follow(?:s|ing|ed)\s+(?:the|a)\s+(?:same|similar|familiar)\s+(?:path|pattern))',
        r'(?:the\s+)?(?:bigger|broader|larger)\s+picture',
    ]

    ANALOGY_MARKERS = [
        r'(?:similar|comparable|analogous)\s+to\s+(?:the\s+)?(?:19|20)\d{2}',
        r'(?:reminds?\s+(?:us|me)\s+of|recalls?\s+the)',
        r'(?:like\s+the\s+)(?:19|20)\d{2}\b',
        r'(?:last\s+time\s+(?:this|we)\s+(?:happened|saw))',
        r'(?:historical\s+(?:analog|parallel|precedent))',
        r'(?:echoes?\s+of\s+the\s+)(?:19|20)\d{2}',
        r'(?:not\s+since\s+the\s+)(?:19|20)\d{2}',
        r'(?:look(?:s|ing)\s+(?:a\s+lot\s+)?like)\s+(?:19|20)\d{2}',
    ]

    HYPOTHESIS_MARKERS = [
        r'(?:we\s+)?(?:believe|think|expect|anticipate|forecast|project|estimate)\s+that',
        r'(?:our\s+(?:base\s+case|central\s+case|core\s+view)\s+is\s+that)',
        r'(?:the\s+)?(?:most\s+likely|probable)\s+(?:outcome|scenario|path)\s+is',
        r'(?:this\s+)?(?:implies|suggests|indicates|points\s+to)\s+that',
        r'(?:if\s+this\s+(?:continues|holds|persists|plays\s+out))\s*,?\s*(?:then)?',
        r'(?:we\s+)?(?:are\s+)?(?:bullish|bearish|constructive|cautious)\s+on',
        r'(?:we\s+see|favor|prefer)\s+(?:a|the)\s+(?:scenario|outcome|path)\s+(?:where|of)',
    ]

    COUNTER_MARKERS = [
        r'(?:however|but|although|yet|that\s+said|having\s+said\s+that|nonetheless|nevertheless)',
        r'(?:on\s+the\s+other\s+hand|conversely|alternatively)',
        r'(?:the\s+)?(?:risk|danger|concern|worry)\s+is\s+that',
        r'(?:a\s+)?(?:counter[\s-]?argument|counterpoint|bear\s+case)\s+(?:is|would\s+be)',
        r'(?:skeptics?\s+(?:would|might|may|argue|point\s+out|say))',
        r'(?:one\s+)?(?:caveat|catch|complication|problem)\s+(?:is|with\s+this)',
        r'(?:what\s+(?:could|could)\s+go\s+wrong)',
        r'(?:this\s+)?(?:assumes?|requires?|depends?\s+on)',
    ]

    CONCLUSION_MARKERS = [
        r'(?:in\s+(?:summary|conclusion|short|sum|brief)|to\s+sum\s+up|overall)',
        r'(?:the\s+)?(?:bottom\s+line|net[\s-]?net|takeaway|key\s+point)\s+is',
        r'(?:this\s+(?:means|leads\s+us\s+to|suggests)\s+that)',
        r'(?:therefore|thus|hence|accordingly|consequently)',
        r'(?:our\s+)?(?:conclusion|judgment|assessment)\s+(?:is|remains)',
        r'(?:we\s+(?:therefore|thus)\s+)?(?:recommend|advise|suggest)',
    ]

    CONFIDENCE_MARKERS: dict[str, float] = {
        r'\b(?:almost\s+certain|certainly|undoubtedly|clearly|obviously)\b': 0.95,
        r'\b(?:very\s+likely|highly\s+likely|highly\s+probable)\b': 0.85,
        r'\b(?:likely|probably|we\s+expect|expected\s+to)\b': 0.75,
        r'\b(?:more\s+likely\s+than\s+not|on\s+balance|probably)\b': 0.65,
        r'\b(?:may|might|could|possibly|potentially)\b': 0.50,
        r'\b(?:unlikely|improbable|doubtful)\b': 0.25,
        r'\b(?:very\s+unlikely|highly\s+unlikely|almost\s+impossible)\b': 0.10,
    }

    def __init__(self):
        self.segmenter = MemoSegmenter()

    # ── Public Interface ─────────────────────────────────────────────

    def extract(self, doc: ResearchDocument) -> list[ReasoningUnit]:
        """Extract all reasoning units from a ResearchDocument.

        Focuses on sections most likely to contain causal reasoning:
        key_themes, macro_outlook, policy_analysis, investment_implications.
        """
        reasoning_sections = self.segmenter.find_reasoning_sections(doc)
        all_units = []

        for section in reasoning_sections:
            section_units = self._extract_from_paragraphs(
                section.paragraphs,
                section_name=section.name,
            )
            all_units.extend(section_units)

        # Also scan executive summary for high-level reasoning
        exec_section = self.segmenter.extract_section(doc, "executive_summary")
        if exec_section:
            exec_units = self._extract_from_paragraphs(
                exec_section.paragraphs,
                section_name="executive_summary",
            )
            all_units.extend(exec_units)

        # Score quality
        for unit in all_units:
            unit.quality_score = self._score_reasoning_quality(unit)

        # Sort by quality
        all_units.sort(key=lambda u: u.quality_score, reverse=True)

        return all_units

    def extract_from_sections(self, sections: list[MemoSection]) -> list[ReasoningUnit]:
        """Extract from pre-segmented sections."""
        all_units = []
        for section in sections:
            units = self._extract_from_paragraphs(
                section.paragraphs,
                section_name=section.name,
            )
            all_units.extend(units)
        return all_units

    # ── Individual Paragraph Extraction ───────────────────────────────

    def _extract_from_paragraphs(
        self,
        paragraphs: list[Paragraph],
        section_name: str = "",
    ) -> list[ReasoningUnit]:
        """Extract reasoning units from a group of paragraphs."""
        units = []

        for para in paragraphs:
            text = para.text
            if para.word_count < 15:  # Too short for meaningful reasoning
                continue

            unit = self._extract_single(text, [para.id])
            if unit and self._is_meaningful(unit):
                units.append(unit)

        return units

    def _extract_single(
        self,
        text: str,
        para_ids: list[str],
    ) -> ReasoningUnit | None:
        """Extract a reasoning unit from a single text block."""
        unit = ReasoningUnit(source_paragraph_ids=para_ids)

        # Observation
        obs = self._match_first(self.OBSERVATION_MARKERS, text)
        if obs:
            unit.observation = self._extract_clause(text, obs)

        # Evidence
        evidence_items = self._match_all(self.EVIDENCE_MARKERS, text)
        unit.evidence = [self._extract_clause(text, e) for e in evidence_items[:3]]

        # Pattern
        pattern = self._match_first(self.PATTERN_MARKERS, text)
        if pattern:
            unit.pattern = self._extract_clause(text, pattern)

        # Historical analogy
        analogy = self._match_first(self.ANALOGY_MARKERS, text)
        if analogy:
            unit.historical_analogy = self._extract_clause(text, analogy)

        # Hypothesis
        hypothesis = self._match_first(self.HYPOTHESIS_MARKERS, text)
        if hypothesis:
            unit.hypothesis = self._extract_clause(text, hypothesis)

        # Counter
        counter = self._match_first(self.COUNTER_MARKERS, text)
        if counter:
            unit.counter_consideration = self._extract_clause(text, counter)

        # Conclusion
        conclusion = self._match_first(self.CONCLUSION_MARKERS, text)
        if conclusion:
            unit.conclusion = self._extract_clause(text, conclusion)

        # Confidence
        unit.confidence_marker = self._detect_confidence(text)

        return unit if self._has_any_content(unit) else None

    # ── Text Matching Helpers ─────────────────────────────────────────

    def _match_first(self, patterns: list[str], text: str) -> str:
        """Find the first matching pattern in text. Returns matched substring."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        return ""

    def _match_all(self, patterns: list[str], text: str) -> list[str]:
        """Find all pattern matches in text."""
        results = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            results.extend(matches)
        return results

    def _extract_clause(self, text: str, marker: str) -> str:
        """Extract the clause containing a marker, from the full text."""
        if not marker:
            return ""

        pos = text.lower().find(marker.lower())
        if pos < 0:
            return marker

        # Try to get a meaningful clause: from marker to end of sentence
        clause_start = max(0, text.rfind('.', 0, pos) + 1)
        if clause_start == 0:
            clause_start = pos

        # Find sentence end
        clause_end = text.find('.', pos + len(marker))
        if clause_end < 0:
            clause_end = len(text)

        # Get meaningful range
        start = max(clause_start, pos - 30)
        end = min(clause_end + 1, pos + len(marker) + 200)

        return text[start:end].strip()

    def _detect_confidence(self, text: str) -> str:
        """Detect confidence level from linguistic markers."""
        best_level = ""
        best_score = -1.0

        for pattern, score in self.CONFIDENCE_MARKERS.items():
            if re.search(pattern, text, re.IGNORECASE):
                if score > best_score:
                    best_score = score
                    best_level = pattern.replace(r'\b', '').strip('()')

        # Return human-readable confidence
        if best_score >= 0.90:
            return "very high"
        elif best_score >= 0.75:
            return "high"
        elif best_score >= 0.60:
            return "moderate"
        elif best_score >= 0.35:
            return "low"
        elif best_score >= 0:
            return "very low"
        return "unspecified"

    # ── Quality Assessment ────────────────────────────────────────────

    def _is_meaningful(self, unit: ReasoningUnit) -> bool:
        """Check if a reasoning unit has enough content to be meaningful."""
        filled = sum(bool(getattr(unit, field))
                      for field in ['observation', 'hypothesis', 'conclusion',
                                     'pattern', 'historical_analogy'])
        # Need at least 2 filled fields for meaningful reasoning
        return filled >= 2

    def _has_any_content(self, unit: ReasoningUnit) -> bool:
        """Check if any field is filled."""
        fields = ['observation', 'hypothesis', 'conclusion', 'pattern',
                   'counter_consideration', 'historical_analogy']
        return any(bool(getattr(unit, f)) for f in fields) or bool(unit.evidence)

    def _score_reasoning_quality(self, unit: ReasoningUnit) -> float:
        """Score the quality of an extracted reasoning unit (0-1)."""
        score = 0.0

        # Completeness: how many reasoning steps present
        steps = [
            bool(unit.observation),
            bool(unit.evidence),
            bool(unit.pattern),
            bool(unit.historical_analogy),
            bool(unit.hypothesis),
            bool(unit.counter_consideration),
            bool(unit.conclusion),
        ]
        score += sum(steps) / len(steps) * 0.5

        # Causal linkage: hypothesis follows from observation
        if unit.observation and unit.hypothesis:
            score += 0.2

        # Counter presence: professional research acknowledges counterviews
        if unit.counter_consideration:
            score += 0.15

        # Evidence support
        if unit.evidence:
            score += 0.15

        return min(score, 1.0)
