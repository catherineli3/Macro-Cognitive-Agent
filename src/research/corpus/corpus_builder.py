"""V5.1 Corpus Builder — Assemble, index, and query the Macro Research Corpus.

Orchestrates the full corpus pipeline:
    1. Parse documents (PDF/HTML)
    2. Segment into sections
    3. Extract reasoning, arguments, predictions, trades
    4. Build theme index
    5. Generate quality-graded corpus entries

The assembled corpus becomes the foundation for V5.2 Reasoning Pipeline
prompts — all prompts derived from real institutional research.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from src.research.corpus.argument_extractor import ArgumentExtractor
from src.research.corpus.html_parser import HTMLParser
from src.research.corpus.memo_segmenter import MemoSegmenter
from src.research.corpus.pdf_parser import PDFParser
from src.research.corpus.prediction_extractor import PredictionExtractor
from src.research.corpus.reasoning_extractor import ReasoningExtractor
from src.research.corpus.schemas import (
    CorpusCounterArgument,
    CorpusEntry,
    DocumentSource,
    MacroResearchCorpus,
    PredictionUnit,
    ReasoningUnit,
    ResearchDocument,
    TradeIdea,
)
from src.research.corpus.trade_extractor import TradeExtractor


class CorpusBuilder:
    """Build and manage the Macro Research Corpus.

    Orchestrates parsing, extraction, and indexing of institutional
    research documents into a queryable corpus for prompt training.

    Usage:
        builder = CorpusBuilder()
        builder.add_pdf("bridgewater_daily.pdf")
        builder.add_url("https://www.federalreserve.gov/newsevents/speech/powell20260101a.htm")
        builder.add_directory("./research_docs/")
        corpus = builder.build()
        corpus.save("macro_corpus_v1.json")
    """

    # Quality thresholds
    MIN_PARSE_QUALITY = 0.3  # Minimum parse quality to include
    MIN_REASONING_SCORE = 0.25  # Minimum reasoning unit quality
    GRADE_THRESHOLDS = {
        "A": 0.80,
        "B": 0.60,
        "C": 0.40,
        "D": 0.0,
    }

    def __init__(self, output_dir: str = ""):
        self.output_dir = output_dir
        self.pdf_parser = PDFParser()
        self.html_parser = HTMLParser()
        self.segmenter = MemoSegmenter()
        self.reasoning_extractor = ReasoningExtractor()
        self.argument_extractor = ArgumentExtractor()
        self.prediction_extractor = PredictionExtractor()
        self.trade_extractor = TradeExtractor()

        self._documents: list[ResearchDocument] = []
        self._entries: list[CorpusEntry] = []

    # ── Document Ingestion ────────────────────────────────────────────

    def add_pdf(self, file_path: str) -> ResearchDocument:
        """Parse and queue a PDF document."""
        doc = self.pdf_parser.parse_file(file_path)
        self._documents.append(doc)
        return doc

    def add_pdf_text(self, text: str, source_hint: str = "") -> ResearchDocument:
        """Parse raw PDF text."""
        doc = self.pdf_parser.parse_from_text(text, source_hint=source_hint)
        self._documents.append(doc)
        return doc

    def add_url(self, url: str, title: str = "") -> ResearchDocument:
        """Fetch and parse a URL."""
        doc = self.html_parser.parse_from_url(url)
        if title:
            doc.title = title
        self._documents.append(doc)
        return doc

    def add_html(self, html: str, url: str = "", title: str = "") -> ResearchDocument:
        """Parse HTML content."""
        doc = self.html_parser.parse_html(html, url=url, title=title)
        self._documents.append(doc)
        return doc

    def add_directory(self, dir_path: str, recursive: bool = True) -> list[ResearchDocument]:
        """Parse all PDF files in a directory."""
        path = Path(dir_path)
        if not path.exists():
            return []

        pattern = "**/*.pdf" if recursive else "*.pdf"
        pdf_files = list(path.glob(pattern))

        docs = []
        for pdf_file in pdf_files:
            try:
                doc = self.add_pdf(str(pdf_file))
                docs.append(doc)
            except Exception:
                # Log and skip failed parses
                pass

        return docs

    def clear(self):
        """Clear all loaded documents."""
        self._documents.clear()
        self._entries.clear()

    # ── Extraction Pipeline ───────────────────────────────────────────

    def process_document(self, doc: ResearchDocument) -> ResearchDocument:
        """Run full extraction pipeline on a single document."""
        # Extract reasoning units
        reasoning_units = self.reasoning_extractor.extract(doc)
        doc.reasoning_units = reasoning_units

        # Extract counterarguments
        counters = self.argument_extractor.extract(doc)
        doc.counter_arguments = counters

        # Extract predictions
        predictions = self.prediction_extractor.extract(doc)
        doc.predictions = predictions

        # Extract trade ideas
        trades = self.trade_extractor.extract(doc)
        doc.trade_ideas = trades

        # Calculate parse quality
        doc.parse_quality = self._calculate_doc_quality(doc)

        return doc

    # ── Build ─────────────────────────────────────────────────────────

    def build(self, min_quality: float = None) -> MacroResearchCorpus:
        """Build the complete Macro Research Corpus.

        Args:
            min_quality: Minimum parse quality to include (default: MIN_PARSE_QUALITY)

        Returns:
            A fully populated MacroResearchCorpus
        """
        threshold = min_quality or self.MIN_PARSE_QUALITY

        # Process all documents
        processed_docs = []
        for doc in self._documents:
            if doc.parse_quality >= threshold:
                processed = self.process_document(doc)
                processed_docs.append(processed)

        # Grade and create entries
        entries = []
        for doc in processed_docs:
            grade = self._grade_document(doc)
            entry = CorpusEntry(
                doc=doc,
                embedding_id="",
                indexed_at=datetime.now().isoformat(),
                quality_grade=grade,
            )
            entries.append(entry)

        # Build theme index
        theme_index = self._build_theme_index(processed_docs)

        # Calculate source distribution
        source_dist = self._calculate_source_distribution(processed_docs)

        # Aggregate statistics
        total_reasoning = sum(len(doc.reasoning_units) for doc in processed_docs)
        total_predictions = sum(len(doc.predictions) for doc in processed_docs)
        total_trades = sum(len(doc.trade_ideas) for doc in processed_docs)

        corpus = MacroResearchCorpus(
            name="Macro Research Corpus",
            version="1.0",
            created_at=datetime.now().isoformat(),
            total_documents=len(processed_docs),
            total_reasoning_units=total_reasoning,
            total_predictions=total_predictions,
            total_trade_ideas=total_trades,
            documents=processed_docs,
            entries=entries,
            source_distribution=source_dist,
            theme_index=theme_index,
        )

        self._documents = processed_docs
        self._entries = entries

        return corpus

    # ── Query ─────────────────────────────────────────────────────────

    def query_by_source(self, source: DocumentSource) -> list[ResearchDocument]:
        """Get all documents from a specific source."""
        return [doc for doc in self._documents if doc.source == source]

    def query_by_theme(self, theme: str) -> list[ResearchDocument]:
        """Get all documents about a specific theme."""
        # Build index if needed
        if not hasattr(self, "_theme_index") or not self._theme_index:
            self._theme_index = self._build_theme_index(self._documents)

        doc_ids = self._theme_index.get(theme, [])
        return [doc for doc in self._documents if doc.id in doc_ids]

    def get_best_reasoning_units(self, limit: int = 100) -> list[ReasoningUnit]:
        """Get the highest quality reasoning units across all documents."""
        all_units = []
        for doc in self._documents:
            all_units.extend(doc.reasoning_units)
        all_units.sort(key=lambda u: u.quality_score, reverse=True)
        return all_units[:limit]

    def get_predictions_by_horizon(self, horizon_filter: str = "") -> list[PredictionUnit]:
        """Get predictions filtered by time horizon."""
        predictions = []
        for doc in self._documents:
            for pred in doc.predictions:
                if not horizon_filter or horizon_filter.lower() in pred.time_horizon.lower():
                    predictions.append(pred)
        return predictions

    def get_trades_by_direction(self, direction: str) -> list[TradeIdea]:
        """Get trade ideas by direction (long/short/neutral)."""
        trades = []
        for doc in self._documents:
            trades.extend([t for t in doc.trade_ideas if t.direction == direction])
        return trades

    def get_counterarguments_by_severity(self, severity: str) -> list[CorpusCounterArgument]:
        """Get counterarguments by severity level."""
        counters = []
        for doc in self._documents:
            counters.extend([c for c in doc.counter_arguments if c.severity == severity])
        return counters

    # ── Export ────────────────────────────────────────────────────────

    def export_summary(self) -> dict:
        """Export a JSON-serializable summary of the corpus."""
        return {
            "total_documents": len(self._documents),
            "total_reasoning_units": sum(len(d.reasoning_units) for d in self._documents),
            "total_predictions": sum(len(d.predictions) for d in self._documents),
            "total_trade_ideas": sum(len(d.trade_ideas) for d in self._documents),
            "total_counter_arguments": sum(len(d.counter_arguments) for d in self._documents),
            "source_distribution": self._calculate_source_distribution(self._documents),
            "avg_parse_quality": (
                sum(d.parse_quality for d in self._documents) / max(len(self._documents), 1)
            ),
            "top_themes": sorted(
                self._build_theme_index(self._documents).items(),
                key=lambda x: len(x[1]),
                reverse=True,
            )[:10],
            "grade_distribution": self._grade_distribution(),
        }

    def export_prompt_training_data(self) -> dict[str, list]:
        """Export data for V5.2 prompt construction.

        Returns structured training data organized by reasoning stage.
        """
        if not self._documents:
            self.build()

        return {
            "observations": self._extract_field_samples("observation", 500),
            "evidence_examples": self._extract_evidence_samples(500),
            "pattern_examples": self._extract_field_samples("pattern", 500),
            "analogy_examples": self._extract_field_samples("historical_analogy", 500),
            "hypothesis_examples": self._extract_field_samples("hypothesis", 500),
            "counter_examples": [
                {
                    "claim": c.counter_claim,
                    "against": c.against_hypothesis,
                    "dismissal": c.why_dismissed,
                    "severity": c.severity,
                }
                for doc in self._documents
                for c in doc.counter_arguments
            ],
            "prediction_examples": [
                {
                    "claim": p.claim,
                    "probability": p.probability,
                    "horizon": p.time_horizon,
                    "invalidation": p.invalidation,
                }
                for doc in self._documents
                for p in doc.predictions
            ],
            "trade_examples": [
                {
                    "description": t.description,
                    "direction": t.direction,
                    "instrument": t.instrument,
                    "conviction": t.conviction,
                }
                for doc in self._documents
                for t in doc.trade_ideas
            ],
        }

    # ── Internal Helpers ──────────────────────────────────────────────

    def _calculate_doc_quality(self, doc: ResearchDocument) -> float:
        """Calculate document quality based on extraction completeness."""
        score = doc.parse_quality * 0.3

        if doc.reasoning_units:
            avg_quality = sum(u.quality_score for u in doc.reasoning_units) / len(
                doc.reasoning_units
            )
            score += avg_quality * 0.3

        if doc.predictions:
            score += min(len(doc.predictions) * 0.05, 0.2)

        if doc.counter_arguments:
            score += min(len(doc.counter_arguments) * 0.05, 0.1)

        if doc.trade_ideas:
            score += min(len(doc.trade_ideas) * 0.05, 0.1)

        return min(score, 1.0)

    def _grade_document(self, doc: ResearchDocument) -> str:
        """Assign quality grade to a document."""
        quality = doc.parse_quality
        for grade, threshold in sorted(
            self.GRADE_THRESHOLDS.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            if quality >= threshold:
                return grade
        return "D"

    def _build_theme_index(self, docs: list[ResearchDocument]) -> dict[str, list[str]]:
        """Build inverted index: theme → list of document IDs."""
        theme_index = defaultdict(list)
        for doc in docs:
            for theme in doc.key_themes:
                theme_index[theme].append(doc.id)
        return dict(theme_index)

    def _calculate_source_distribution(
        self,
        docs: list[ResearchDocument],
    ) -> dict[str, int]:
        """Calculate document count per source."""
        dist = defaultdict(int)
        for doc in docs:
            dist[doc.source.value] += 1
        return dict(dist)

    def _grade_distribution(self) -> dict[str, int]:
        """Calculate document grade distribution."""
        dist = defaultdict(int)
        for doc in self._documents:
            grade = self._grade_document(doc)
            dist[grade] += 1
        return dict(dist)

    def _extract_field_samples(self, field: str, limit: int) -> list[str]:
        """Extract non-empty field values as training samples."""
        samples = []
        for doc in self._documents:
            for unit in doc.reasoning_units:
                value = getattr(unit, field, "")
                if value and len(value) > 20:
                    samples.append(value)
                    if len(samples) >= limit:
                        return samples
        return samples

    def _extract_evidence_samples(self, limit: int) -> list[str]:
        """Extract evidence examples as training samples."""
        samples = []
        for doc in self._documents:
            for unit in doc.reasoning_units:
                for ev in unit.evidence:
                    if ev and len(ev) > 10:
                        samples.append(ev)
                        if len(samples) >= limit:
                            return samples
        return samples
