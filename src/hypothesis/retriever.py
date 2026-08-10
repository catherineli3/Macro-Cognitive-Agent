"""Historical Retriever — Find similar past hypotheses and analog periods.

Milestone A: Multi-factor similarity scoring (regime + dimension + keyword + performance).
Returns historical context for each candidate hypothesis to inform competition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.hypothesis.signal_engine import SignalReport
from src.schemas.hypothesis_library import HypothesisLibraryEntry, HypothesisScore
from src.schemas.hypothesis_v3_1 import CandidateHypothesis
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Retrieval Result ─────────────────────────────────────────────────────────


@dataclass
class HistoricalMatch:
    """A single historical hypothesis matched to a candidate."""
    entry: HypothesisLibraryEntry
    similarity_score: float = 0.0         # 0~1
    regime_match: bool = False
    dimension_match: bool = False
    direction_match: bool = False
    historical_accuracy: float = 0.0      # 0~1

    @property
    def is_strong_match(self) -> bool:
        return self.similarity_score >= 0.6


@dataclass
class RetrievalContext:
    """Historical context for a candidate hypothesis."""
    candidate_id: str
    matches: list[HistoricalMatch] = field(default_factory=list)
    best_match: Optional[HistoricalMatch] = None
    avg_historical_accuracy: float = 0.0
    regime_support: float = 0.0
    recommendation: str = ""


@dataclass
class RetrievalReport:
    """Complete retrieval output for all candidates."""
    total_matches: int = 0
    contexts: dict = field(default_factory=dict)
    analog_periods_found: int = 0


# ── Keyword Index ────────────────────────────────────────────────────────────

# Dimension-related keywords for similarity scoring
_DIMENSION_KEYWORDS: dict[str, list[str]] = {
    "liquidity": ["liquidity", "dollar", "fed", "easing", "tightening", "monetary",
                  "balance sheet", "reserve", "capital flow", "funding", "rate cut"],
    "credit": ["credit", "spread", "high yield", "hyg", "default", "corporate bond",
               "leverage", "lending", "bank", "financial condition"],
    "growth": ["growth", "gdp", "expansion", "recession", "slowdown", "recovery",
               "employment", "earnings", "industrial", "manufacturing", "pmi"],
    "risk_appetite": ["risk", "appetite", "volatility", "vix", "sentiment",
                      "positioning", "crowded", "fear", "greed", "safe haven"],
    "inflation": ["inflation", "cpi", "ppi", "deflation", "disinflation",
                  "real yield", "tips", "breakeven", "commodity", "gold"],
}

_DIRECTION_KEYWORDS: dict[str, list[str]] = {
    "bullish": ["rising", "higher", "increase", "expansion", "easing", "weakening dollar",
                "rally", "upside", "growth", "accelerating", "outperform"],
    "bearish": ["falling", "lower", "decrease", "contraction", "tightening", "strengthening dollar",
                "selloff", "downside", "decline", "decelerating", "underperform"],
}


# ── Retriever ────────────────────────────────────────────────────────────────


class HistoricalRetriever:
    """Retrieves historical hypotheses similar to current candidates.

    Uses multi-factor similarity:
        - Regime match (40%)
        - Dimension match (25%)
        - Keyword overlap (25%)
        - Direction match (10%)

    For Milestone A, we use keyword-based similarity. Embedding-based semantic
    search can be added in a later iteration.
    """

    def __init__(self) -> None:
        self._similarity_threshold = 0.35  # Minimum similarity to count as a match

    def retrieve(
        self,
        candidates: list[CandidateHypothesis],
        library_entries: list[HypothesisLibraryEntry],
        signal_report: SignalReport,
    ) -> RetrievalReport:
        """Retrieve historical context for each candidate hypothesis.

        Args:
            candidates: Current candidate hypotheses
            library_entries: All entries in the Hypothesis Library
            signal_report: Current macro signal analysis

        Returns:
            RetrievalReport with per-candidate historical context
        """
        report = RetrievalReport()
        current_regime = signal_report.regime

        for candidate in candidates:
            ctx = self._retrieve_for_candidate(candidate, library_entries, current_regime)
            report.contexts[candidate.candidate_id] = ctx
            report.total_matches += len(ctx.matches)
            if ctx.best_match is not None:
                report.analog_periods_found += 1

        logger.info(
            "retrieval_complete candidates=%d matches=%d analogs=%d",
            len(candidates), report.total_matches, report.analog_periods_found,
        )
        return report

    def _retrieve_for_candidate(
        self,
        candidate: CandidateHypothesis,
        library: list[HypothesisLibraryEntry],
        current_regime: str,
    ) -> RetrievalContext:
        """Compute historical matches for a single candidate."""
        matches: list[HistoricalMatch] = []

        for entry in library:
            if entry.status == "deprecated":
                continue

            similarity = self._compute_similarity(candidate, entry, current_regime)
            if similarity < self._similarity_threshold:
                continue

            accuracy = entry.current_score.prediction_accuracy if entry.current_score else 0.5

            matches.append(HistoricalMatch(
                entry=entry,
                similarity_score=round(similarity, 4),
                regime_match=self._regime_matches(entry, current_regime),
                dimension_match=entry.dimension.lower() == candidate.dimension.lower(),
                direction_match=entry.direction.lower() == candidate.direction.lower(),
                historical_accuracy=accuracy,
            ))

        # Sort by similarity descending
        matches.sort(key=lambda m: m.similarity_score, reverse=True)

        # Compute aggregate stats
        best = matches[0] if matches else None
        avg_acc = (
            sum(m.historical_accuracy for m in matches) / len(matches)
            if matches else 0.0
        )
        regime_frac = (
            sum(1 for m in matches if m.regime_match) / len(matches)
            if matches else 0.0
        )

        # Recommendation
        if best and best.similarity_score >= 0.70 and best.historical_accuracy >= 0.65:
            recommendation = "strong_backing"
        elif matches:
            recommendation = "mixed"
        else:
            recommendation = "no_history"

        return RetrievalContext(
            candidate_id=candidate.candidate_id,
            matches=matches,
            best_match=best,
            avg_historical_accuracy=round(avg_acc, 4),
            regime_support=round(regime_frac, 4),
            recommendation=recommendation,
        )

    def _compute_similarity(
        self,
        candidate: CandidateHypothesis,
        entry: HypothesisLibraryEntry,
        current_regime: str,
    ) -> float:
        """Compute multi-factor similarity between candidate and historical entry.

        Weights:
            - Regime match: 0.40
            - Dimension match: 0.25
            - Keyword overlap: 0.25
            - Direction match: 0.10
        """
        # Regime similarity (binary for now)
        regime_sim = 1.0 if self._regime_matches(entry, current_regime) else 0.3

        # Dimension similarity
        dim_sim = 1.0 if entry.dimension.lower() == candidate.dimension.lower() else 0.2

        # Keyword overlap
        kw_sim = self._keyword_similarity(candidate, entry)

        # Direction similarity
        dir_sim = 1.0 if entry.direction.lower() == candidate.direction.lower() else 0.3

        return 0.40 * regime_sim + 0.25 * dim_sim + 0.25 * kw_sim + 0.10 * dir_sim

    @staticmethod
    def _regime_matches(entry: HypothesisLibraryEntry, current_regime: str) -> bool:
        """Check if the entry's regime context matches current regime."""
        # For simplicity: check if regime keyword appears in the statement
        # In Milestone B, entries will carry explicit regime context
        stmt = entry.statement.lower()
        if current_regime == "easing":
            return any(w in stmt for w in ["easing", "dovish", "loosening", "expansionary"])
        elif current_regime == "tightening":
            return any(w in stmt for w in ["tightening", "hawkish", "restrictive", "contractionary"])
        return True  # neutral matches everything

    @staticmethod
    def _keyword_similarity(candidate: CandidateHypothesis, entry: HypothesisLibraryEntry) -> float:
        """Compute keyword overlap between candidate thesis and entry statement."""
        dim_kws = _DIMENSION_KEYWORDS.get(candidate.dimension, [])
        dir_kws = _DIRECTION_KEYWORDS.get(candidate.direction, [])
        all_kws = set(dim_kws + dir_kws)

        entry_text = (entry.statement + " " + entry.dimension).lower()
        candidate_text = (candidate.thesis + " " + candidate.narrative).lower()

        # Count keyword matches in candidate text vs entry text
        candidate_kws = {kw for kw in all_kws if kw in candidate_text}
        entry_kws = {kw for kw in all_kws if kw in entry_text}

        if not candidate_kws:
            return 0.3

        overlap = len(candidate_kws & entry_kws)
        total = len(candidate_kws)
        return overlap / total if total > 0 else 0.3

    def set_threshold(self, threshold: float) -> None:
        self._similarity_threshold = max(0.1, min(0.9, threshold))
