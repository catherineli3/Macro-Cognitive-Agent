"""V10.1 — Evidence Source Registry.

Lightweight data structure defining all evidence sources,
their attributes, and how they map to coverage dimensions.

Not a framework — just a catalog that the GapAnalyzer and SourcePlanner
query to determine what evidence is missing and what to collect next.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── Source categories ─────────────────────────────────────────────


class SourceCategory:
    MACRO = "macro_data"
    POLICY = "policy"
    POSITIONING = "positioning"
    LIQUIDITY = "liquidity"
    SENTIMENT = "sentiment"
    FLOW = "capital_flow"
    VALUATION = "valuation"


# ── Coverage dimensions ──────────────────────────────────────────
# These map 1:1 with SourceCategory for EvidenceCoverage computation.

COVERAGE_DIMENSIONS = [
    "macro",        # GDP, PMI, CPI, employment — BLS, BEA, Reuters, Bloomberg
    "liquidity",    # Treasury auctions, credit spreads, repo — Treasury Auction
    "policy",       # Central bank speeches, minutes, decisions — FOMC, Fed/ECB/BOJ Speeches
    "positioning",  # CFTC COT, 13F, options data
    "flow",         # ETF flows, mutual fund allocations
    "valuation",    # P/E, earnings, guidance — Earnings Call, Company Guidance
    "sentiment",    # News, analyst consensus, macro calendar events
]


# ── Source definitions ────────────────────────────────────────────


@dataclass
class EvidenceSource:
    """A single evidence source with its attributes."""
    name: str
    category: str
    priority: int = 50          # 0-100: how essential is this source?
    latency: str = "daily"      # "realtime", "daily", "weekly", "monthly", "quarterly"
    coverage: list[str] = field(default_factory=list)  # Which COVERAGE_DIMENSIONS?
    reliability: float = 0.7    # 0-1

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "priority": self.priority,
            "latency": self.latency,
            "coverage": self.coverage,
            "reliability": self.reliability,
        }


# ── The Registry ──────────────────────────────────────────────────


EVIDENCE_SOURCES: dict[str, EvidenceSource] = {
    # ── Macro Data ──
    "Reuters": EvidenceSource(
        name="Reuters",
        category=SourceCategory.MACRO,
        priority=90,
        latency="realtime",
        coverage=["macro", "sentiment"],
        reliability=0.85,
    ),
    "Bloomberg": EvidenceSource(
        name="Bloomberg",
        category=SourceCategory.MACRO,
        priority=90,
        latency="realtime",
        coverage=["macro", "sentiment", "valuation"],
        reliability=0.88,
    ),
    "BLS": EvidenceSource(
        name="BLS",
        category=SourceCategory.MACRO,
        priority=95,
        latency="monthly",
        coverage=["macro"],
        reliability=0.92,
    ),
    "BEA": EvidenceSource(
        name="BEA",
        category=SourceCategory.MACRO,
        priority=95,
        latency="monthly",
        coverage=["macro"],
        reliability=0.92,
    ),
    "Macro Calendar": EvidenceSource(
        name="Macro Calendar",
        category=SourceCategory.MACRO,
        priority=70,
        latency="daily",
        coverage=["macro", "sentiment"],
        reliability=0.75,
    ),

    # ── Policy ──
    "FOMC Minutes": EvidenceSource(
        name="FOMC Minutes",
        category=SourceCategory.POLICY,
        priority=95,
        latency="monthly",
        coverage=["policy", "liquidity"],
        reliability=0.90,
    ),
    "Fed Speech": EvidenceSource(
        name="Fed Speech",
        category=SourceCategory.POLICY,
        priority=95,
        latency="realtime",
        coverage=["policy"],
        reliability=0.80,
    ),
    "ECB Speech": EvidenceSource(
        name="ECB Speech",
        category=SourceCategory.POLICY,
        priority=80,
        latency="realtime",
        coverage=["policy"],
        reliability=0.78,
    ),
    "BOJ Speech": EvidenceSource(
        name="BOJ Speech",
        category=SourceCategory.POLICY,
        priority=75,
        latency="realtime",
        coverage=["policy"],
        reliability=0.76,
    ),

    # ── Positioning ──
    "CFTC COT": EvidenceSource(
        name="CFTC COT",
        category=SourceCategory.POSITIONING,
        priority=85,
        latency="weekly",
        coverage=["positioning"],
        reliability=0.82,
    ),
    "13F": EvidenceSource(
        name="13F",
        category=SourceCategory.POSITIONING,
        priority=70,
        latency="quarterly",
        coverage=["positioning", "flow"],
        reliability=0.75,
    ),

    # ── Flow ──
    "ETF Flow": EvidenceSource(
        name="ETF Flow",
        category=SourceCategory.FLOW,
        priority=80,
        latency="daily",
        coverage=["flow"],
        reliability=0.78,
    ),

    # ── Liquidity ──
    "Treasury Auction": EvidenceSource(
        name="Treasury Auction",
        category=SourceCategory.LIQUIDITY,
        priority=85,
        latency="weekly",
        coverage=["liquidity"],
        reliability=0.85,
    ),
    "CME FedWatch": EvidenceSource(
        name="CME FedWatch",
        category=SourceCategory.LIQUIDITY,
        priority=80,
        latency="realtime",
        coverage=["policy", "liquidity"],
        reliability=0.80,
    ),

    # ── Valuation / Sentiment ──
    "Earnings Call": EvidenceSource(
        name="Earnings Call",
        category=SourceCategory.VALUATION,
        priority=75,
        latency="daily",
        coverage=["valuation", "sentiment"],
        reliability=0.70,
    ),
    "Company Guidance": EvidenceSource(
        name="Company Guidance",
        category=SourceCategory.VALUATION,
        priority=70,
        latency="daily",
        coverage=["valuation", "sentiment"],
        reliability=0.65,
    ),
}


# ── Helper: map source name → EvidenceSource ──────────────────────


def get_source(name: str) -> Optional[EvidenceSource]:
    """Look up a source by name. Returns None if not found."""
    return EVIDENCE_SOURCES.get(name)


def get_sources_by_category(category: str) -> list[EvidenceSource]:
    """Return all sources in a given category."""
    return [s for s in EVIDENCE_SOURCES.values() if s.category == category]


def get_sources_by_coverage(dimension: str) -> list[EvidenceSource]:
    """Return all sources that cover a given coverage dimension."""
    return [s for s in EVIDENCE_SOURCES.values() if dimension in s.coverage]


def get_all_source_names() -> list[str]:
    """Return all registered source names."""
    return list(EVIDENCE_SOURCES.keys())


def get_priority_order() -> list[EvidenceSource]:
    """Return all sources sorted by priority (highest first)."""
    return sorted(EVIDENCE_SOURCES.values(), key=lambda s: s.priority, reverse=True)
