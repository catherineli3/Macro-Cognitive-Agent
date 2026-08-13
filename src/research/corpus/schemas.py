"""V5.1 Corpus Schemas — Data models for institutional research document parsing."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# ── Document Source Enum ────────────────────────────────────────────────


class DocumentSource(str, Enum):
    BRIDGEWATER = "bridgewater"
    TS_LOMBARD = "ts_lombard"
    BCA = "bca_research"
    GAVEKAL = "gavekal"
    GOLDMAN = "goldman_sachs"
    MORGAN_STANLEY = "morgan_stanley"
    FED_MINUTES = "fed_minutes"
    FOMC_SPEECH = "fomc_speech"
    ECB_SPEECH = "ecb_speech"
    BOJ_SPEECH = "boj_speech"
    BIS = "bis"
    IMF = "imf"
    WORLD_BANK = "world_bank"
    BROOKINGS = "brookings"
    DALIO = "ray_dalio"
    PTJ = "paul_tudor_jones"
    HOWARD_MARKS = "howard_marks"
    APOLLO = "apollo_macro"
    BLACKROCK = "blackrock"


class DocumentType(str, Enum):
    DAILY_OBSERVATION = "daily_observation"
    WEEKLY_STRATEGY = "weekly_strategy"
    MONTHLY_OUTLOOK = "monthly_outlook"
    SPECIAL_REPORT = "special_report"
    SPEECH = "speech"
    MINUTES = "minutes"
    ANNUAL_LETTER = "annual_letter"
    POLICY_BRIEF = "policy_brief"
    MACRO_NOTE = "macro_note"


# ── Core Units ──────────────────────────────────────────────────────────


@dataclass
class Paragraph:
    """Single paragraph from a research document."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    index: int = 0
    text: str = ""
    section_heading: str = ""
    word_count: int = 0
    contains_citation: bool = False
    citations: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.text and not self.word_count:
            self.word_count = len(self.text.split())


@dataclass
class ReasoningUnit:
    """Extracted reasoning chain from a paragraph."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    observation: str = ""  # What was observed
    evidence: list[str] = field(default_factory=list)  # Supporting evidence cited
    pattern: str = ""  # Pattern or regime identified
    historical_analogy: str = ""  # Historical comparison made
    hypothesis: str = ""  # Causal hypothesis
    counter_consideration: str = ""  # Acknowledged counter
    conclusion: str = ""  # Final judgment
    confidence_marker: str = ""  # e.g. "likely", "almost certain", "possible"
    source_paragraph_ids: list[str] = field(default_factory=list)
    quality_score: float = 0.0  # 0-1 quality of extracted reasoning


@dataclass
class PredictionUnit:
    """Extracted prediction from a research document."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    claim: str = ""  # What is predicted
    probability: float = 0.0  # Explicit or implied probability
    time_horizon: str = ""  # e.g. "3 months", "end of 2026", "Q4"
    conditions: list[str] = field(default_factory=list)  # Conditions
    invalidation: str = ""  # What would prove it wrong
    asset_implication: str = ""  # What it means for markets
    source_paragraph_ids: list[str] = field(default_factory=list)


@dataclass
class TradeIdea:
    """Extracted trade idea from a research document."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    direction: str = ""  # long, short, neutral
    instrument: str = ""  # e.g. "SPX", "10Y UST", "EUR/USD"
    rationale: str = ""  # Why this trade
    conviction: float = 0.0  # 0-1
    stop_loss: str = ""
    target: str = ""
    time_horizon: str = ""
    risk_factors: list[str] = field(default_factory=list)
    source_paragraph_ids: list[str] = field(default_factory=list)


@dataclass
class CorpusCounterArgument:
    """Extracted counterargument from a research document."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    counter_claim: str = ""
    against_hypothesis: str = ""
    evidence_for_counter: list[str] = field(default_factory=list)
    why_dismissed: str = ""  # Why author dismisses this counter
    severity: str = ""  # minor, major, fatal
    source_paragraph_ids: list[str] = field(default_factory=list)


# ── Document-Level Models ───────────────────────────────────────────────


@dataclass
class ResearchDocument:
    """Full parsed research document."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    author: str = ""
    source: DocumentSource = DocumentSource.BRIDGEWATER
    doc_type: DocumentType = DocumentType.DAILY_OBSERVATION
    publication_date: str = ""  # ISO date string
    url: str = ""
    raw_text: str = ""
    paragraphs: list[Paragraph] = field(default_factory=list)
    reasoning_units: list[ReasoningUnit] = field(default_factory=list)
    predictions: list[PredictionUnit] = field(default_factory=list)
    trade_ideas: list[TradeIdea] = field(default_factory=list)
    counter_arguments: list[CorpusCounterArgument] = field(default_factory=list)
    key_themes: list[str] = field(default_factory=list)
    word_count: int = 0
    parse_quality: float = 0.0  # 0-1

    def __post_init__(self):
        if self.raw_text and not self.word_count:
            self.word_count = len(self.raw_text.split())


@dataclass
class CorpusEntry:
    """Indexed entry in the macro research corpus."""

    doc: ResearchDocument
    embedding_id: str = ""  # Vector DB reference
    indexed_at: str = ""  # ISO datetime
    quality_grade: str = "B"  # A/B/C/D


@dataclass
class MacroResearchCorpus:
    """The assembled corpus of institutional macro research."""

    name: str = "Macro Research Corpus"
    version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    total_documents: int = 0
    total_reasoning_units: int = 0
    total_predictions: int = 0
    total_trade_ideas: int = 0
    documents: list[ResearchDocument] = field(default_factory=list)
    entries: list[CorpusEntry] = field(default_factory=list)
    source_distribution: dict[str, int] = field(default_factory=dict)
    theme_index: dict[str, list[str]] = field(default_factory=dict)  # theme → doc_ids

    def summary(self) -> str:
        return (
            f"MacroResearchCorpus(v{self.version}): "
            f"{self.total_documents} docs, "
            f"{self.total_reasoning_units} reasoning units, "
            f"{self.total_predictions} predictions, "
            f"{self.total_trade_ideas} trades"
        )
