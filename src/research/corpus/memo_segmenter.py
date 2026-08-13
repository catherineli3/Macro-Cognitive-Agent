"""V5.1 Memo Segmenter — Segment research documents into semantic sections.

Identifies standard sections found in institutional research:
    Executive Summary, Market Review, Macro Outlook, Key Themes,
    Policy Analysis, Risk Factors, Investment Implications,
    Asset Allocation, Conclusions, Disclaimers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.research.corpus.schemas import Paragraph, ResearchDocument


@dataclass
class MemoSection:
    """A named, semantically meaningful section of a research memo."""

    name: str
    heading: str
    paragraphs: list[Paragraph] = field(default_factory=list)
    start_index: int = 0
    end_index: int = 0
    word_count: int = 0

    @property
    def text(self) -> str:
        return " ".join(p.text for p in self.paragraphs)


class MemoSegmenter:
    """Segment ResearchDocument paragraphs into standard memo sections.

    Identifies the logical structure of institutional research:
    - Executive Summary → overview of key conclusions
    - Market Review → what happened in markets
    - Macro Outlook → economic projections
    - Key Themes → dominant narratives
    - Policy Analysis → central bank / fiscal analysis
    - Risk Factors → key risks identified
    - Investment Implications → what it means for portfolios
    - Conclusion → final synthesis
    """

    # Section heading patterns mapped to standard section names
    SECTION_PATTERNS: dict[str, list[str]] = {
        "executive_summary": [
            r"executive\s+summary",
            r"summary\s+(?:and\s+)?conclusions?",
            r"key\s+takeaways?",
            r"in\s+brief",
            r"at\s+a\s+glance",
            r"bottom\s+line",
            r"overview",
        ],
        "market_review": [
            r"market\s+(?:review|recap|wrap|summary|update)",
            r"(?:last|this)\s+week(?:\s+in\s+markets?)?",
            r"performance\s+review",
            r"market\s+action",
            r"price\s+action",
            r"asset\s+class\s+performance",
        ],
        "macro_outlook": [
            r"macro\s+(?:outlook|view|forecast|update)",
            r"economic\s+(?:outlook|projections?|forecast|update)",
            r"growth\s+(?:outlook|forecast)",
            r"global\s+(?:outlook|economy)",
            r"gdp\s+(?:growth\s+)?(?:forecast|outlook)",
        ],
        "key_themes": [
            r"key\s+themes?",
            r"(?:dominant|major|top)\s+(?:themes?|narratives?)",
            r"what\s+(?:we|i)\s+(?:are|am)\s+(?:watching|tracking|monitoring)",
            r"(?:our|the)\s+(?:view|take|read)",
        ],
        "policy_analysis": [
            r"(?:monetary|fiscal)\s+policy",
            r"central\s+bank",
            r"fed(?:eral\s+reserve)?\s+(?:policy|outlook|watch)",
            r"ecb|boj|pboc|boe",
            r"rate\s+(?:decision|path|outlook)",
            r"policy\s+(?:analysis|outlook|update|review)",
        ],
        "risk_factors": [
            r"risk\s+(?:factors?|assessment|analysis|monitor|watch)",
            r"key\s+risks?",
            r"downside\s+risks?",
            r"upside\s+risks?",
            r"tail\s+risks?",
            r"what\s+(?:could|could)\s+go\s+wrong",
            r"vulnerabilit",
            r"worries?",
            r"concerns?",
        ],
        "investment_implications": [
            r"investment\s+(?:implications?|conclusions?|strategy|view)",
            r"portfolio\s+(?:implications?|strategy|positioning)",
            r"asset\s+allocation",
            r"positioning",
            r"what\s+(?:to\s+do|this\s+means)",
            r"strategy\s+implications?",
            r"trade\s+(?:ideas?|recommendations?)",
        ],
        "conclusion": [
            r"conclusion",
            r"final\s+thoughts?",
            r"wrap(?:\s*up|-up)",
            r"summary\s+(?:and\s+)?outlook",
            r"looking\s+ahead",
            r"what\s+(?:comes|lies)\s+ahead",
            r"forward\s+(?:view|outlook)",
        ],
    }

    # Section ordering (typical institutional memo structure)
    SECTION_ORDER = [
        "executive_summary",
        "market_review",
        "macro_outlook",
        "key_themes",
        "policy_analysis",
        "risk_factors",
        "investment_implications",
        "conclusion",
    ]

    def __init__(self):
        pass

    # ── Public Interface ─────────────────────────────────────────────

    def segment(self, doc: ResearchDocument) -> list[MemoSection]:
        """Segment a ResearchDocument into standard memo sections.

        Returns ordered list of MemoSection objects, each containing
        the paragraphs that belong to that logical section.
        """
        if not doc.paragraphs:
            return []

        # First pass: identify section boundaries
        section_boundaries = self._find_section_boundaries(doc.paragraphs)

        # Second pass: assign paragraphs to sections
        sections = self._assign_paragraphs(doc.paragraphs, section_boundaries)

        # Third pass: classify unlabeled sections
        sections = self._classify_unlabeled(doc.paragraphs, sections)

        # Fourth pass: merge adjacent same-type sections
        sections = self._merge_adjacent(sections)

        return sections

    def segment_text(self, text: str) -> list[MemoSection]:
        """Segment raw text (quick path without full ResearchDocument)."""
        from src.research.corpus.pdf_parser import PDFParser

        parser = PDFParser()
        doc = parser.parse_from_text(text)
        return self.segment(doc)

    def extract_section(self, doc: ResearchDocument, section_name: str) -> MemoSection | None:
        """Extract a specific named section from a document."""
        sections = self.segment(doc)
        for s in sections:
            if s.name == section_name:
                return s
        return None

    # ── Section Boundary Detection ────────────────────────────────────

    def _find_section_boundaries(self, paragraphs: list[Paragraph]) -> list[tuple[int, str, str]]:
        """Find section boundaries by matching heading patterns.

        Returns: list of (paragraph_index, section_name, matched_heading)
        """
        boundaries = []
        compressed = re.compile(r"\s+")

        for i, para in enumerate(paragraphs):
            text = para.text
            # Check if short enough to be a heading
            if para.word_count > 20:
                continue

            text_normalized = compressed.sub(" ", text.lower())

            for section_name, patterns in self.SECTION_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, text_normalized):
                        boundaries.append((i, section_name, text))
                        break
                else:
                    continue
                break

        # Always add "preamble" if text before first heading
        if not boundaries or boundaries[0][0] > 0:
            boundaries.insert(0, (0, "preamble", ""))

        return boundaries

    def _assign_paragraphs(
        self,
        paragraphs: list[Paragraph],
        boundaries: list[tuple[int, str, str]],
    ) -> list[MemoSection]:
        """Assign paragraphs to sections based on detected boundaries."""
        sections = []

        for idx, (start_idx, name, heading) in enumerate(boundaries):
            end_idx = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(paragraphs)

            # Heading paragraph is boundary marker; content starts after it
            content_start = start_idx + 1 if heading else start_idx
            section_paras = paragraphs[content_start:end_idx]

            word_count = sum(p.word_count for p in section_paras)

            sections.append(
                MemoSection(
                    name=name,
                    heading=heading,
                    paragraphs=section_paras,
                    start_index=start_idx,
                    end_index=end_idx,
                    word_count=word_count,
                )
            )

        return sections

    def _classify_unlabeled(
        self,
        paragraphs: list[Paragraph],
        sections: list[MemoSection],
    ) -> list[MemoSection]:
        """Attempt to classify sections labeled 'preamble' using content signals."""
        content_signals = {
            "executive_summary": [
                r"(?:in\s+summary|key\s+takeaway|bottom\s+line|our\s+core\s+view)",
                r"(?:we\s+(?:believe|see|expect|think|forecast|project))",
            ],
            "market_review": [
                r"(?:s&p\s+500|nasdaq|dow\s+jones|equity\s+market)",
                r"(?:treasury\s+yield|bond\s+market|credit\s+spread)",
                r"(?:rall(?:y|ied)|s(?:old\s+off|elloff)|decline)",
            ],
            "macro_outlook": [
                r"(?:gdp\s+growth|economic\s+growth|recession|expansion)",
                r"(?:leading\s+indicators?|pmi|ism|industrial\s+production)",
            ],
        }

        for section in sections:
            if section.name != "preamble":
                continue

            section_text = " ".join(p.text.lower() for p in section.paragraphs)

            best_match = ""
            best_score = 0
            for name, patterns in content_signals.items():
                score = sum(1 for p in patterns if re.search(p, section_text, re.IGNORECASE))
                if score > best_score:
                    best_score = score
                    best_match = name

            if best_score >= 2 and best_match:
                section.name = best_match

        return sections

    def _merge_adjacent(self, sections: list[MemoSection]) -> list[MemoSection]:
        """Merge adjacent sections of the same type."""
        if not sections:
            return []

        merged = [sections[0]]
        for current in sections[1:]:
            last = merged[-1]
            if current.name == last.name and current.name != "preamble":
                # Merge into last
                last.paragraphs.extend(current.paragraphs)
                last.end_index = current.end_index
                last.word_count += current.word_count
            else:
                merged.append(current)

        return merged

    # ── Analysis Helpers ──────────────────────────────────────────────

    def get_section_distribution(self, doc: ResearchDocument) -> dict[str, int]:
        """Get word count distribution across sections."""
        sections = self.segment(doc)
        return {s.name: s.word_count for s in sections}

    def find_reasoning_sections(self, doc: ResearchDocument) -> list[MemoSection]:
        """Find sections most likely to contain causal reasoning."""
        reasoning_section_names = {
            "key_themes",
            "macro_outlook",
            "policy_analysis",
            "investment_implications",
            "conclusion",
        }
        sections = self.segment(doc)
        return [s for s in sections if s.name in reasoning_section_names]
