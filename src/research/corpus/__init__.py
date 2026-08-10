"""V5.1 Research Corpus Builder — Parse and extract from institutional research.

Purpose:
    Build a professional macro research corpus from real sources:
    Bridgewater, TS Lombard, BCA, Gavekal, Goldman, Morgan Stanley,
    Fed Minutes, FOMC, ECB, BOJ, BIS, IMF, World Bank, Brookings,
    Dalio, PTJ, Howard Marks, Apollo, BlackRock.

    Extracted elements become training data for reasoning prompts.
    No more hand-written prompts. All from real research.

Output:
    ResearchDocument, Paragraph, ReasoningUnit, PredictionUnit,
    TradeIdea, CounterArgument → MacroResearchCorpus
"""

from src.research.corpus.schemas import (
    ResearchDocument,
    Paragraph,
    ReasoningUnit,
    PredictionUnit,
    TradeIdea,
    CorpusCounterArgument,
    CorpusEntry,
    MacroResearchCorpus,
    DocumentSource,
    DocumentType,
)

from src.research.corpus.pdf_parser import PDFParser
from src.research.corpus.html_parser import HTMLParser
from src.research.corpus.memo_segmenter import MemoSegmenter
from src.research.corpus.reasoning_extractor import ReasoningExtractor
from src.research.corpus.argument_extractor import ArgumentExtractor
from src.research.corpus.prediction_extractor import PredictionExtractor
from src.research.corpus.trade_extractor import TradeExtractor
from src.research.corpus.corpus_builder import CorpusBuilder

__all__ = [
    # Schemas
    "ResearchDocument",
    "Paragraph",
    "ReasoningUnit",
    "PredictionUnit",
    "TradeIdea",
    "CorpusCounterArgument",
    "CorpusEntry",
    "MacroResearchCorpus",
    "DocumentSource",
    "DocumentType",
    # Engines
    "PDFParser",
    "HTMLParser",
    "MemoSegmenter",
    "ReasoningExtractor",
    "ArgumentExtractor",
    "PredictionExtractor",
    "TradeExtractor",
    "CorpusBuilder",
]
