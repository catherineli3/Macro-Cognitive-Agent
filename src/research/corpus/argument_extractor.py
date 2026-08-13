"""V5.1 Argument Extractor — Extract arguments and counterarguments from research.

Extracts:
    - Main arguments / claims from document paragraphs
    - Counterarguments acknowledged by the author
    - Evidence cited for and against each argument
    - Why the author dismisses certain counterarguments

These become training data for the V5.2 Counter Stage prompt.
"""

from __future__ import annotations

import re

from src.research.corpus.memo_segmenter import MemoSection, MemoSegmenter
from src.research.corpus.schemas import (
    CorpusCounterArgument,
    ResearchDocument,
)


class ArgumentExtractor:
    """Extract arguments and counterarguments from institutional research.

    Distinguishes between:
        - Author's own argument (thesis)
        - Counterargument acknowledged but dismissed
        - Counterargument acknowledged as valid risk

    Institutional research almost always includes counterargument.
    The quality of counter handling is a key differentiator between
    amateur and professional macro research.
    """

    # ── Argument Patterns ─────────────────────────────────────────────

    ARGUMENT_MARKERS = [
        r"(?:we\s+)?(?:argue|contend|maintain|assert|posit|submit)\s+that",
        r"(?:our\s+(?:thesis|argument|view|case)\s+(?:is|rests\s+on)\s+that)",
        r"(?:the\s+)?(?:case\s+for|argument\s+for|bull\s+case)\s+(?:is|rests?\s+on)",
        r"(?:we\s+)?(?:are\s+)?(?:convinced|confident|persuaded)\s+that",
        r"(?:there\s+is\s+a\s+)?(?:strong|compelling|powerful)\s+(?:case|argument)\s+(?:for|that)",
    ]

    COUNTER_ARGUMENT_MARKERS = [
        r"(?:the\s+)?(?:bear\s+case|counter[\s-]?argument|skeptical\s+view)\s+(?:is|would\s+be|rests?\s+on)",
        r"(?:critics?\s+(?:argue|say|point\s+out|note|contend)\s+that)",
        r"(?:some\s+(?:argue|say|believe|think)\s+that)",
        r"(?:a\s+)?(?:common\s+)?(?:objection|critique|criticism)\s+(?:is|would\s+be)\s+that",
        r"(?:one\s+)?(?:might|could)\s+(?:argue|counter|object)\s+that",
        r"(?:the\s+)?(?:alternative\s+view|opposing\s+view)\s+(?:is|holds?\s+that)",
        r"(?:a\s+)?(?:plausible\s+)?(?:counter[\s-]?narrative|alternative\s+narrative)\s+(?:is|would\s+be)",
    ]

    DISMISSAL_MARKERS = [
        r"(?:however|but|yet|though)\s*,?\s*(?:this|that|we|i)\s+(?:view|see|think|believe)",
        r"(?:we\s+)?(?:disagree|dismiss|reject|push\s+back\s+on|take\s+issue\s+with)",
        r"(?:this\s+(?:argument|view|concern|worry)\s+(?:is|seems)\s+)?(?:overblown|overstated|misplaced|exaggerated)",
        r"(?:we\s+(?:would|do)\s+)?(?:not\s+(?:agree|concur|share|buy|subscribe\s+to))",
        r"(?:the\s+)?(?:evidence\s+(?:does\s+not|doesn\'t|fails?\s+to)\s+support)",
        r"(?:while\s+this\s+(?:is|may\s+be|might\s+be)\s+)?(?:true|valid|correct|plausible)",
        r"(?:this\s+)?(?:ignores|overlooks|misses|fails?\s+to\s+account\s+for)",
    ]

    EVIDENCE_FOR_COUNTER_MARKERS = [
        r"(?:they|critics|skeptics)\s+(?:point\s+to|cite|reference|highlight|note)",
        r"(?:supported\s+by|backed\s+by|evidenced\s+by)",
        r"(?:the\s+)?(?:data\s+showing|evidence\s+that)",
        r"(?:as\s+(?:seen|shown|evidenced|demonstrated)\s+(?:in|by))",
    ]

    SEVERITY_MARKERS: dict[str, str] = {
        r"\b(?:fatal|devastating|game[\s-]?changing|paradigm[\s-]?shifting|invalidating)\b": "fatal",
        r"\b(?:serious|significant|major|substantial|important|meaningful)\b": "major",
        r"\b(?:minor|modest|limited|small|marginal|nuanced)\b": "minor",
    }

    def __init__(self):
        self.segmenter = MemoSegmenter()

    # ── Public Interface ─────────────────────────────────────────────

    def extract(self, doc: ResearchDocument) -> list[CorpusCounterArgument]:
        """Extract all counterarguments from a ResearchDocument."""
        all_sections = self.segmenter.segment(doc)
        counters = []

        for section in all_sections:
            section_text = " ".join(p.text for p in section.paragraphs)
            section_counters = self._extract_from_text(
                section_text,
                [p.id for p in section.paragraphs],
            )
            counters.extend(section_counters)

        return counters

    def extract_with_context(
        self, doc: ResearchDocument
    ) -> list[tuple[CorpusCounterArgument, MemoSection]]:
        """Extract counterarguments with their section context."""
        all_sections = self.segmenter.segment(doc)
        results = []

        for section in all_sections:
            section_text = " ".join(p.text for p in section.paragraphs)
            section_counters = self._extract_from_text(
                section_text,
                [p.id for p in section.paragraphs],
            )
            for counter in section_counters:
                results.append((counter, section))

        return results

    # ── Extraction Logic ──────────────────────────────────────────────

    def _extract_from_text(
        self,
        text: str,
        para_ids: list[str],
    ) -> list[CorpusCounterArgument]:
        """Extract counterarguments from a text block."""
        counters = []

        # Find counterargument sentences
        sentences = self._split_sentences(text)

        for i, sentence in enumerate(sentences):
            if self._is_counterargument(sentence):
                counter = CorpusCounterArgument(source_paragraph_ids=para_ids)

                # The counter claim itself
                counter.counter_claim = sentence

                # What hypothesis is it against?
                counter.against_hypothesis = self._find_target_hypothesis(sentences, i)

                # Evidence for the counter
                counter.evidence_for_counter = self._find_evidence(sentences, i)

                # Why dismissed (look in following sentences or dismissal phrases)
                counter.why_dismissed = self._find_dismissal(sentences, i)

                # Severity
                counter.severity = self._detect_severity(sentence)

                counters.append(counter)

        return counters

    def _is_counterargument(self, text: str) -> bool:
        """Check if text contains a counterargument."""
        return any(re.search(p, text, re.IGNORECASE) for p in self.COUNTER_ARGUMENT_MARKERS)

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple but effective sentence splitting
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    def _find_target_hypothesis(
        self,
        sentences: list[str],
        counter_idx: int,
    ) -> str:
        """Find the hypothesis that the counter is arguing against."""
        # Look in preceding 2 sentences
        start = max(0, counter_idx - 2)
        for s in sentences[start:counter_idx]:
            for marker in ["believe", "think", "expect", "argue", "view", "case", "hypothesis"]:
                if marker in s.lower():
                    return s
        return ""

    def _find_evidence(self, sentences: list[str], counter_idx: int) -> list[str]:
        """Find evidence cited for the counterargument."""
        evidence = []
        # Look in same sentence and next 2
        end = min(len(sentences), counter_idx + 3)
        for s in sentences[counter_idx:end]:
            if any(re.search(p, s, re.IGNORECASE) for p in self.EVIDENCE_FOR_COUNTER_MARKERS):
                evidence.append(s)
        return evidence[:3]

    def _find_dismissal(self, sentences: list[str], counter_idx: int) -> str:
        """Find how the author dismisses the counterargument."""
        # Look in same sentence and next 3
        end = min(len(sentences), counter_idx + 4)
        for s in sentences[counter_idx:end]:
            for pattern in self.DISMISSAL_MARKERS:
                if re.search(pattern, s, re.IGNORECASE):
                    return s
        return ""

    def _detect_severity(self, text: str) -> str:
        """Detect severity of the counterargument."""
        text_lower = text.lower()
        for pattern, severity in self.SEVERITY_MARKERS.items():
            if re.search(pattern, text_lower):
                return severity
        return "major"  # Default severity for acknowledged counters
