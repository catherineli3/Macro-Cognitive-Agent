"""NarrativeRanker — multi-factor ranking of narratives.

score = confidence × breadth × source_diversity × model_agreement × novelty

This is NOT a simple sort. Each factor is weighted and normalized.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.research.narrative.schemas import Narrative
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RankedNarrative:
    """A narrative with its full ranking breakdown."""
    narrative: Narrative
    rank: int = 0
    composite_score: float = 0.0

    # Factor breakdown
    confidence_score: float = 0.0
    breadth_score: float = 0.0
    source_diversity_score: float = 0.0
    model_agreement_score: float = 0.0
    novelty_score: float = 0.0

    # Time-weighted scores
    recency_bonus: float = 0.0
    persistence_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "title": self.narrative.title,
            "composite_score": round(self.composite_score, 4),
            "confidence_score": round(self.confidence_score, 4),
            "breadth_score": round(self.breadth_score, 4),
            "source_diversity_score": round(self.source_diversity_score, 4),
            "model_agreement_score": round(self.model_agreement_score, 4),
            "novelty_score": round(self.novelty_score, 4),
            "recency_bonus": round(self.recency_bonus, 4),
        }


class NarrativeRanker:
    """Multi-factor narrative ranking engine.

    Usage:
        ranker = NarrativeRanker()
        ranked = ranker.rank(narratives)
        for r in ranked[:5]:
            print(f"#{r.rank} {r.narrative.title}: {r.composite_score:.4f}")
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
    ) -> None:
        """Initialize with optional custom factor weights.

        Default weights:
            confidence: 0.30
            breadth: 0.20
            source_diversity: 0.15
            model_agreement: 0.20
            novelty: 0.10
            recency: 0.05
        """
        self._weights = weights or {
            "confidence": 0.30,
            "breadth": 0.20,
            "source_diversity": 0.15,
            "model_agreement": 0.20,
            "novelty": 0.10,
            "recency": 0.05,
        }

    def rank(self, narratives: list[Narrative]) -> list[RankedNarrative]:
        """Rank narratives by multi-factor weighted score.

        Returns:
            List of RankedNarrative sorted by composite_score descending.
        """
        if not narratives:
            return []

        rankings = []
        for n in narratives:
            rn = self._score_single(n)
            rankings.append(rn)

        # Normalize composite scores to 0-1 range
        if rankings:
            max_score = max(r.composite_score for r in rankings) or 1.0
            for r in rankings:
                r.composite_score = r.composite_score / max_score

        # Sort and assign ranks
        rankings.sort(key=lambda r: r.composite_score, reverse=True)
        for i, r in enumerate(rankings):
            r.rank = i + 1

        logger.info(
            "narrative_ranking_complete | count=%d top=%s (%.4f)",
            len(rankings),
            rankings[0].narrative.title if rankings else "none",
            rankings[0].composite_score if rankings else 0,
        )
        return rankings

    def _score_single(self, narrative: Narrative) -> RankedNarrative:
        """Score a single narrative on all factors."""
        w = self._weights

        # ── Factor 1: Confidence ─────────────────────────────────────────
        confidence_score = narrative.confidence

        # ── Factor 2: Breadth ────────────────────────────────────────────
        breadth_count = len(narrative.supporting_signals)
        breadth_score = min(1.0, breadth_count / 8.0)

        # ── Factor 3: Source Diversity ───────────────────────────────────
        unique_sources = len(set(s.source for s in narrative.supporting_signals))
        source_diversity_score = min(1.0, unique_sources / 6.0)

        # ── Factor 4: Model Agreement ────────────────────────────────────
        total_models = len(narrative.supporting_models) + len(
            narrative.contradicting_models
        )
        if total_models > 0:
            agreement_ratio = len(narrative.supporting_models) / total_models
        else:
            agreement_ratio = 0.5
        model_agreement_score = agreement_ratio

        # ── Factor 5: Novelty ────────────────────────────────────────────
        novelty_score = narrative.novelty_score

        # ── Factor 6: Recency bonus ──────────────────────────────────────
        recency_bonus = 0.0

        # ── Weighted composite ───────────────────────────────────────────
        composite = (
            w["confidence"] * confidence_score
            + w["breadth"] * breadth_score
            + w["source_diversity"] * source_diversity_score
            + w["model_agreement"] * model_agreement_score
            + w["novelty"] * novelty_score
            + w["recency"] * recency_bonus
        )

        # ── Persistence (if narrative existed in prior runs) ─────────────
        persistence_score = 0.1 if narrative.version > 1 else 0.0

        return RankedNarrative(
            narrative=narrative,
            composite_score=composite,
            confidence_score=confidence_score,
            breadth_score=breadth_score,
            source_diversity_score=source_diversity_score,
            model_agreement_score=model_agreement_score,
            novelty_score=novelty_score,
            recency_bonus=recency_bonus,
            persistence_score=persistence_score,
        )

    def get_top(self, narratives: list[Narrative], n: int = 5) -> list[RankedNarrative]:
        """Get the top N ranked narratives."""
        ranked = self.rank(narratives)
        return ranked[:n]

    def get_contradicting_pairs(
        self,
        rankings: list[RankedNarrative],
    ) -> list[tuple[RankedNarrative, RankedNarrative]]:
        """Identify pairs of highly-ranked but contradicting narratives."""
        pairs = []
        bullish_kw = {"easing", "expansion", "cooling", "dovish",
                       "soft landing", "goldilocks", "risk-on"}
        bearish_kw = {"tightening", "contraction", "rising", "hawkish",
                       "scare", "stress", "risk-off", "stagflation"}

        for i, a in enumerate(rankings):
            a_title = a.narrative.title.lower()
            a_bullish = any(kw in a_title for kw in bullish_kw)
            a_bearish = any(kw in a_title for kw in bearish_kw)

            for b in rankings[i + 1:]:
                b_title = b.narrative.title.lower()
                b_bullish = any(kw in b_title for kw in bullish_kw)
                b_bearish = any(kw in b_title for kw in bearish_kw)

                if (a_bullish and b_bearish) or (a_bearish and b_bullish):
                    if a.composite_score > 0.5 and b.composite_score > 0.5:
                        pairs.append((a, b))

        return pairs
