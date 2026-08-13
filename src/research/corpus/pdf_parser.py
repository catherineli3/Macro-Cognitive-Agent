"""V5.1 PDF Parser — Extract raw text and structure from PDF research documents.

Handles institutional PDFs from Bridgewater, TS Lombard, BCA, Gavekal,
Goldman, Morgan Stanley, Fed Minutes, IMF, BIS, World Bank, etc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.research.corpus.schemas import DocumentSource, DocumentType, Paragraph, ResearchDocument


@dataclass
class PDFMetadata:
    """Extracted metadata from PDF headers/footers."""

    title: str = ""
    author: str = ""
    date: str = ""
    source_detected: str = ""
    page_count: int = 0


class PDFParser:
    """Parse PDF research documents into structured ResearchDocument.

    Supports both native text extraction (PyPDF2/pdfplumber) and
    OCR fallback for scanned documents. Extracts document structure:
    sections, paragraphs, footnotes, and metadata.
    """

    # Common patterns in institutional research PDFs
    SECTION_HEADER_PATTERNS = [
        r"^(?:Executive\s+)?Summary$",
        r"^(?:Macro\s+)?Outlook$",
        r"^(?:Market\s+)?Review$",
        r"^(?:Key\s+)?Themes?$",
        r"^(?:Investment\s+)?Implications?$",
        r"^(?:Risk\s+)?Factors?$",
        r"^(?:Asset\s+)?Allocation$",
        r"^(?:Economic\s+)?Projections?$",
        r"^(?:Policy\s+)?Analysis$",
        r"^Conclusion$",
        r"^Disclaimer$",
    ]

    # Source identification by header/footer text
    SOURCE_FINGERPRINTS = {
        DocumentSource.BRIDGEWATER: ["bridgewater", "daily observations", "bw"],
        DocumentSource.TS_LOMBARD: ["ts lombard", "trusted sources"],
        DocumentSource.BCA: ["bca research", "bank credit analyst"],
        DocumentSource.GAVEKAL: ["gavekal", "gavekal research"],
        DocumentSource.GOLDMAN: ["goldman sachs", "gs macro"],
        DocumentSource.MORGAN_STANLEY: ["morgan stanley", "ms research"],
        DocumentSource.FED_MINUTES: ["federal open market committee", "fomc minutes"],
        DocumentSource.FOMC_SPEECH: ["federal reserve", "chair powell", "governor"],
        DocumentSource.ECB_SPEECH: ["european central bank", "ecb", "president lagarde"],
        DocumentSource.BOJ_SPEECH: ["bank of japan", "boj", "governor ueda"],
        DocumentSource.BIS: ["bank for international settlements", "bis"],
        DocumentSource.IMF: ["international monetary fund", "imf", "weo"],
        DocumentSource.WORLD_BANK: ["world bank", "global economic prospects"],
        DocumentSource.BROOKINGS: ["brookings", "hutchins center"],
        DocumentSource.DALIO: ["ray dalio", "principles"],
        DocumentSource.PTJ: ["paul tudor jones", "tudor"],
        DocumentSource.HOWARD_MARKS: ["howard marks", "oaktree", "memo"],
        DocumentSource.APOLLO: ["apollo global", "apollo academy"],
        DocumentSource.BLACKROCK: ["blackrock", "weekly commentary"],
    }

    TITLE_INDICATORS = [
        "daily observations",
        "macro outlook",
        "global macro",
        "weekly strategy",
        "monthly outlook",
        "economic outlook",
        "market outlook",
        "investment strategy",
        "policy note",
        "special report",
        "global economic prospects",
        "world economic outlook",
        "annual report",
    ]

    def __init__(self, use_ocr: bool = False, language: str = "en"):
        self.use_ocr = use_ocr
        self.language = language
        self._parser_status = "initialized"

    # ── Public Interface ─────────────────────────────────────────────

    def parse_file(self, file_path: str) -> ResearchDocument:
        """Parse a PDF file into a ResearchDocument."""
        raw_text = self._extract_text(file_path)
        return self.parse_from_text(raw_text, file_path)

    def parse_from_text(self, text: str, source_hint: str = "") -> ResearchDocument:
        """Parse raw extracted text into a ResearchDocument."""
        if not text.strip():
            return ResearchDocument(raw_text=text, parse_quality=0.0)

        metadata = self._extract_metadata(text)
        source = self._detect_source(text, source_hint)
        doc_type = self._detect_document_type(text)
        title = metadata.title or self._extract_title(text)
        date = metadata.date or self._extract_date(text)

        paragraphs = self._segment_paragraphs(text)
        key_themes = self._extract_key_themes(text)

        return ResearchDocument(
            title=title,
            author=metadata.author,
            source=source,
            doc_type=doc_type,
            publication_date=date,
            raw_text=text,
            paragraphs=paragraphs,
            key_themes=key_themes,
            word_count=len(text.split()),
            parse_quality=self._evaluate_quality(text, paragraphs, title),
        )

    def parse_batch(self, file_paths: list[str]) -> list[ResearchDocument]:
        """Parse multiple PDF files."""
        return [self.parse_file(fp) for fp in file_paths]

    # ── Text Extraction ──────────────────────────────────────────────

    def _extract_text(self, file_path: str) -> str:
        """Extract raw text from PDF file path."""
        try:
            import pdfplumber

            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        cleaned = self._clean_page_text(page_text)
                        text_parts.append(cleaned)
            return "\n\n".join(text_parts)
        except ImportError:
            try:
                from PyPDF2 import PdfReader

                reader = PdfReader(file_path)
                text_parts = []
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(self._clean_page_text(page_text))
                return "\n\n".join(text_parts)
            except ImportError:
                raise ImportError(
                    "pdfplumber or PyPDF2 required for PDF parsing. "
                    "Install: pip install pdfplumber PyPDF2"
                )

    def _clean_page_text(self, text: str) -> str:
        """Clean extracted page text: remove headers/footers, fix hyphenation."""
        lines = text.split("\n")
        cleaned = []

        for line in lines:
            line = line.strip()
            if not line:
                cleaned.append("")
                continue
            # Skip page numbers
            if re.match(r"^\d{1,3}$", line):
                continue
            # Skip header/footer lines (short, contains date or page)
            if len(line) < 20 and re.search(r"(page|www\.|©|confidential)", line, re.IGNORECASE):
                continue
            # Fix line-break hyphenation
            if cleaned and cleaned[-1].endswith("-") and len(cleaned[-1]) > 2:
                cleaned[-1] = cleaned[-1][:-1] + line
                continue
            cleaned.append(line)

        return "\n".join(cleaned)

    # ── Metadata Extraction ───────────────────────────────────────────

    def _extract_metadata(self, text: str) -> PDFMetadata:
        """Extract title, author, date from document text."""
        metadata = PDFMetadata()

        first_2000 = text[:2000]
        lines = first_2000.split("\n")

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Date patterns
            date_match = re.search(
                r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4})",
                line,
                re.IGNORECASE,
            )
            if date_match and not metadata.date:
                metadata.date = date_match.group(1)

            # Author patterns
            if re.search(r"^(?:By|Author|Prepared by):?\s", line, re.IGNORECASE):
                metadata.author = re.sub(
                    r"^(?:By|Author|Prepared by):?\s*", "", line, re.IGNORECASE
                )

            # Title (first substantial line)
            if not metadata.title and len(line) > 10 and not date_match:
                has_indicator = any(ind in line.lower() for ind in self.TITLE_INDICATORS)
                if has_indicator or (i == 0 and len(line) < 120):
                    metadata.title = line

        return metadata

    # ── Source Detection ──────────────────────────────────────────────

    def _detect_source(self, text: str, hint: str = "") -> DocumentSource:
        """Detect document source from text fingerprints."""
        text_lower = text.lower()

        if hint:
            hint_lower = hint.lower()
            for source, fingerprints in self.SOURCE_FINGERPRINTS.items():
                if any(fp in hint_lower for fp in fingerprints):
                    return source

        # Score-based detection
        scores: dict[DocumentSource, int] = {}
        for source, fingerprints in self.SOURCE_FINGERPRINTS.items():
            score = sum(2 if fp in text_lower else 0 for fp in fingerprints)
            if score > 0:
                scores[source] = score

        if scores:
            return max(scores, key=scores.get)
        return DocumentSource.BRIDGEWATER

    def _detect_document_type(self, text: str) -> DocumentType:
        """Detect document type from content patterns."""
        text_lower = text.lower()

        type_indicators = {
            DocumentType.DAILY_OBSERVATION: ["daily observation", "daily note", "morning note"],
            DocumentType.WEEKLY_STRATEGY: ["weekly", "week ahead", "week in review"],
            DocumentType.MONTHLY_OUTLOOK: ["monthly", "month ahead", "monthly outlook"],
            DocumentType.SPECIAL_REPORT: ["special report", "deep dive", "in focus"],
            DocumentType.SPEECH: ["speech", "remarks", "prepared remarks", "testimony"],
            DocumentType.MINUTES: ["minutes", "meeting of the", "committee"],
            DocumentType.ANNUAL_LETTER: ["annual letter", "shareholder letter"],
            DocumentType.POLICY_BRIEF: ["policy brief", "policy note", "working paper"],
        }

        for doc_type, indicators in type_indicators.items():
            if any(ind in text_lower for ind in indicators):
                return doc_type

        return DocumentType.MACRO_NOTE

    def _extract_title(self, text: str) -> str:
        """Extract document title."""
        lines = text.split("\n")
        for line in lines[:10]:
            line = line.strip()
            if 10 < len(line) < 150 and not re.search(r"(http|www\.)", line):
                has_indicator = any(ind in line.lower() for ind in self.TITLE_INDICATORS)
                if has_indicator:
                    return line
        # Fallback: first substantial line
        for line in lines[:5]:
            line = line.strip()
            if len(line) > 20:
                return line
        return "Untitled"

    def _extract_date(self, text: str) -> str:
        """Extract publication date."""
        date_patterns = [
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4})",
            r"(\d{4}-\d{2}-\d{2})",
            r"(\d{2}/\d{2}/\d{4})",
        ]
        first_1000 = text[:1000]
        for pattern in date_patterns:
            match = re.search(pattern, first_1000, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    # ── Paragraph Segmentation ────────────────────────────────────────

    def _segment_paragraphs(self, text: str) -> list[Paragraph]:
        """Segment text into paragraphs, identifying section headings."""
        raw_paragraphs = re.split(r"\n\s*\n", text)
        paragraphs = []
        current_section = ""

        for i, para_text in enumerate(raw_paragraphs):
            para_text = para_text.strip()
            if not para_text:
                continue

            # Check if this is a section heading
            compressed = " ".join(para_text.split())
            is_heading = self._is_section_heading(compressed)

            if is_heading:
                current_section = compressed
                continue

            # Detect citations
            citations = []
            has_citation = bool(re.search(r"\[[\d,\s]+\]|\(\w+\s+\d{4}\)", para_text))
            if has_citation:
                citation_matches = re.findall(r"\[([\d,\s]+)\]", para_text)
                citations = [m.strip() for m in citation_matches]

            paragraphs.append(
                Paragraph(
                    index=i,
                    text=compressed,
                    section_heading=current_section,
                    word_count=len(compressed.split()),
                    contains_citation=has_citation,
                    citations=citations,
                )
            )

        return paragraphs

    def _is_section_heading(self, text: str) -> bool:
        """Determine if a text line is a section heading."""
        if len(text.split()) > 15:
            return False
        for pattern in self.SECTION_HEADER_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        # All-caps short lines are likely headings
        if text.isupper() and 2 <= len(text.split()) <= 8:
            return True
        return False

    # ── Theme Extraction ──────────────────────────────────────────────

    def _extract_key_themes(self, text: str) -> list[str]:
        """Extract key themes from document content."""
        theme_keywords = {
            "inflation": ["inflation", "cpi", "ppi", "pce", "price pressure", "deflation"],
            "growth": ["gdp growth", "economic growth", "recession", "expansion", "slowdown"],
            "monetary policy": [
                "monetary policy",
                "fed",
                "rate hike",
                "rate cut",
                "hawkish",
                "dovish",
            ],
            "fiscal policy": ["fiscal policy", "deficit", "government spending", "tax"],
            "labor market": ["labor market", "employment", "unemployment", "wages", "job"],
            "china": ["china", "chinese", "pboc", "beijing"],
            "geopolitics": ["geopolitical", "conflict", "sanctions", "war", "tension"],
            "energy": ["energy", "oil", "crude", "opec", "natural gas"],
            "credit": ["credit", "spreads", "default", "corporate debt", "leverage"],
            "currency": ["currency", "dollar", "eur", "yen", "fx", "exchange rate"],
            "equities": ["equity", "stocks", "s&p", "nasdaq", "valuation"],
            "bonds": ["bond", "yield", "treasury", "duration", "fixed income"],
            "emerging markets": ["emerging market", "em", "developing economy"],
            "supply chain": ["supply chain", "trade", "tariff", "export", "import"],
        }

        text_lower = text.lower()
        themes = []

        for theme, keywords in theme_keywords.items():
            occurrences = sum(text_lower.count(kw) for kw in keywords)
            if occurrences >= 3:
                themes.append(theme)

        return themes

    # ── Quality Evaluation ────────────────────────────────────────────

    def _evaluate_quality(self, text: str, paragraphs: list[Paragraph], title: str) -> float:
        """Evaluate parse quality 0-1."""
        score = 0.0

        if text.strip():
            score += 0.2
        if paragraphs and len(paragraphs) >= 3:
            score += 0.2
        if title and title != "Untitled":
            score += 0.2
        if len(text.split()) > 200:
            score += 0.2
        # Check for clean text (no garbled extraction)
        garbled_ratio = len(re.findall(r"[^\x20-\x7E\s]", text)) / max(len(text), 1)
        if garbled_ratio < 0.02:
            score += 0.2

        return min(score, 1.0)
