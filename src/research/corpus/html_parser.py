"""V5.1 HTML Parser — Extract research content from web-based institutional sources.

Handles HTML content from:
    FOMC speeches (federalreserve.gov), ECB speeches (ecb.europa.eu),
    BOJ speeches (boj.or.jp), BIS publications (bis.org),
    IMF blogs/papers (imf.org), World Bank (worldbank.org),
    Brookings (brookings.edu), BlackRock (blackrock.com),
    Apollo Academy (apolloacademy.com).
"""

from __future__ import annotations

import re

from src.research.corpus.pdf_parser import PDFParser
from src.research.corpus.schemas import ResearchDocument


class HTMLParser:
    """Parse HTML research content into structured ResearchDocument.

    Uses regex-based extraction to avoid dependency on html.parser stdlib module
    (which can conflict with the module's own name).
    """

    DOMAIN_SOURCE_MAP = {
        "federalreserve.gov": "fed",
        "ecb.europa.eu": "ecb",
        "boj.or.jp": "boj",
        "bis.org": "bis",
        "imf.org": "imf",
        "worldbank.org": "world_bank",
        "brookings.edu": "brookings",
        "blackrock.com": "blackrock",
        "apolloacademy.com": "apollo",
        "oaktreecapital.com": "howard_marks",
        "bridgewater.com": "bridgewater",
        "gavekal.com": "gavekal",
        "bcaresearch.com": "bca",
    }

    def __init__(self):
        self._pdf_parser = PDFParser()

    # ── Public Interface ─────────────────────────────────────────────

    def parse_html(self, html_content: str, url: str = "", title: str = "") -> ResearchDocument:
        """Parse HTML content into a ResearchDocument."""
        if not html_content.strip():
            return ResearchDocument(url=url, parse_quality=0.0)

        text = self._extract_text(html_content)
        text = self._clean_html_text(text)

        source_hint = self._domain_to_source_hint(url)
        doc = self._pdf_parser.parse_from_text(text, source_hint=source_hint)
        doc.url = url
        if title:
            doc.title = title

        return doc

    def parse_from_url(self, url: str) -> ResearchDocument:
        """Fetch and parse HTML from URL."""
        import urllib.request

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MacroResearchAgent/5.1"})
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode("utf-8", errors="replace")
            return self.parse_html(html, url=url)
        except urllib.error.URLError as e:
            raise OSError(f"Failed to fetch {url}: {e}")

    def parse_batch(self, urls: list[str]) -> list[ResearchDocument]:
        """Parse multiple URLs."""
        docs = []
        for url in urls:
            try:
                docs.append(self.parse_from_url(url))
            except OSError:
                docs.append(ResearchDocument(url=url, parse_quality=0.0))
        return docs

    # ── Text Extraction (regex-based) ─────────────────────────────────

    def _extract_text(self, html: str) -> str:
        """Extract clean text from HTML using regex."""
        # Remove scripts and styles
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
        html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # Remove all HTML tags
        text = re.sub(r"<[^>]+>", " ", html)

        # Decode common HTML entities
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
        text = text.replace("&nbsp;", " ")

        return text

    def _clean_html_text(self, text: str) -> str:
        """Clean extracted HTML text."""
        # Collapse whitespace
        text = re.sub(r"[ \t]+", " ", text)
        # Remove multiple blank lines
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        # Strip each line
        lines = [line.strip() for line in text.split("\n")]
        # Remove leading/trailing empty lines
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)

    def _domain_to_source_hint(self, url: str) -> str:
        """Map URL domain to source identification hint."""
        if not url:
            return ""
        url_lower = url.lower()
        for domain, hint in self.DOMAIN_SOURCE_MAP.items():
            if domain in url_lower:
                return hint
        return ""
