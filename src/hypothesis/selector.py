"""Hypothesis Selector — Transform competition survivors into a ranked Top-N.

Milestone A: Applies diversity filters, historical backing scoring, and final ranking.
Outputs SelectedHypothesis objects with full reasoning trail.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.hypothesis.competition_engine import CompetitionEngine, CompetitionRound
from src.hypothesis.retriever import HistoricalRetriever, RetrievalContext, RetrievalReport
from src.schemas.hypothesis_v3_1 import (
    CandidateHypothesis,
    SelectedHypothesis,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Diversity Config ─────────────────────────────────────────────────────────

# Maximum hypotheses per dimension in the final selection
_MAX_PER_DIMENSION = 2

# Dimensions that MUST be represented if possible
_REQUIRED_DIMENSIONS = ["liquidity", "credit", "growth", "risk_appetite", "inflation"]


# ── Selector ─────────────────────────────────────────────────────────────────


class HypothesisSelector:
    """Selects the final Top-N hypotheses from competition survivors.

    Selection strategy:
        1. Score each survivor with a composite formula
        2. Apply diversity constraints (max per dimension)
        3. Enforce minimum dimension coverage
        4. Rank by final score and output Top-N
    """

    def __init__(self, max_selection: int = 5, min_dimensions_covered: int = 3) -> None:
        self._max = max_selection
        self._min_dims = min_dimensions_covered

    def select(
        self,
        survivors: list[CandidateHypothesis],
        retrieval_report: RetrievalReport,
        competition_round: CompetitionRound,
    ) -> list[SelectedHypothesis]:
        """Select the final Top-N hypotheses from competition survivors.

        Args:
            survivors: Hypotheses that survived competition
            retrieval_report: Historical context per candidate
            competition_round: Competition results and eliminations

        Returns:
            Ranked list of SelectedHypothesis (max N)
        """
        contexts = retrieval_report.contexts

        # ── Score each survivor ───────────────────────────────────────────
        scored: list[tuple[CandidateHypothesis, float, RetrievalContext]] = []
        for h in survivors:
            ctx = contexts.get(h.candidate_id, RetrievalContext(candidate_id=h.candidate_id))
            score = self._compute_final_score(h, ctx)
            scored.append((h, score, ctx))

        scored.sort(key=lambda x: x[1], reverse=True)

        # ── Diversity-filtered selection ──────────────────────────────────
        selected: list[SelectedHypothesis] = []
        dim_counts: dict[str, int] = {}
        covered_dims: set[str] = set()

        for h, score, ctx in scored:
            dim = h.dimension

            # Enforce per-dimension cap
            if dim_counts.get(dim, 0) >= _MAX_PER_DIMENSION:
                continue

            # Determine competition result description
            comp_desc = self._describe_competition_result(
                h, competition_round, survivors,
            )

            # Build historical backing string
            hist_backing = self._describe_historical_backing(ctx)

            selected.append(SelectedHypothesis(
                candidate_id=h.candidate_id,
                rank=len(selected) + 1,
                dimension=h.dimension,
                direction=h.direction,
                thesis=h.thesis,
                evidence_summary=[e.claim for e in h.evidence[:3]],
                transmission_summary=" → ".join(
                    s.segment_id for s in h.transmission_chain[:4]
                ),
                confidence=round(score, 4),
                competition_result=comp_desc,
                historical_backing=hist_backing,
            ))

            dim_counts[dim] = dim_counts.get(dim, 0) + 1
            covered_dims.add(dim)

            if len(selected) >= self._max:
                break

        # ── Ensure minimum dimension coverage ─────────────────────────────
        if len(covered_dims) < self._min_dims and len(scored) > len(selected):
            # Add the best survivor from each uncovered dimension
            for h, score, ctx in scored:
                if h.dimension not in covered_dims and len(selected) < self._max:
                    comp_desc = self._describe_competition_result(h, competition_round, survivors)
                    hist_backing = self._describe_historical_backing(ctx)

                    selected.append(SelectedHypothesis(
                        candidate_id=h.candidate_id,
                        rank=len(selected) + 1,
                        dimension=h.dimension,
                        direction=h.direction,
                        thesis=h.thesis,
                        evidence_summary=[e.claim for e in h.evidence[:3]],
                        transmission_summary=" → ".join(
                            s.segment_id for s in h.transmission_chain[:4]
                        ),
                        confidence=round(score, 4),
                        competition_result=comp_desc,
                        historical_backing=hist_backing,
                    ))
                    covered_dims.add(h.dimension)

                if len(selected) >= self._max:
                    break

        # Re-rank
        for i, s in enumerate(selected):
            s.rank = i + 1

        logger.info(
            "selection_complete selected=%d dimensions_covered=%s",
            len(selected), sorted(covered_dims),
        )
        return selected

    # ── Scoring ───────────────────────────────────────────────────────────

    def _compute_final_score(
        self,
        hypothesis: CandidateHypothesis,
        context: RetrievalContext,
    ) -> float:
        """Compute final composite score for a hypothesis.

        Weights:
            - Competition score (from evidence + chain): 0.35
            - Historical backing: 0.25
            - Evidence completeness: 0.20
            - Transmission chain quality: 0.20
        """
        comp = hypothesis.competition_score

        # Historical backing
        hist = 0.5  # Default
        if context.recommendation == "strong_backing":
            hist = 0.85
        elif context.recommendation == "mixed":
            hist = 0.60
        elif context.recommendation == "no_history":
            hist = 0.40

        # Evidence completeness
        ev = hypothesis.evidence_count / 5.0 if hypothesis.evidence_count else 0.2
        ev = min(ev, 1.0)

        # Transmission chain quality
        tx = hypothesis.avg_chain_reliability if hypothesis.chain_length > 0 else 0.3

        return 0.35 * comp + 0.25 * hist + 0.20 * ev + 0.20 * tx

    # ── Description Helpers ───────────────────────────────────────────────

    @staticmethod
    def _describe_competition_result(
        hypothesis: CandidateHypothesis,
        round_: CompetitionRound,
        all_survivors: list[CandidateHypothesis],
    ) -> str:
        """Describe how this hypothesis performed in competition."""
        # Was it involved in a contradiction that it won?
        for elim in round_.eliminated:
            if elim.eliminated_by == hypothesis.candidate_id:
                return f"won_direct_contradiction_against_{elim.candidate_id}"

        # Did it survive uncontested?
        was_contradicted = any(
            c.hypothesis_a == hypothesis.candidate_id or
            c.hypothesis_b == hypothesis.candidate_id
            for c in round_.contradictions_found
        )
        if not was_contradicted:
            return "survived_uncontested"

        # Survived contradiction (was the stronger side)
        # Check if it had any contraction where it was involved
        for c in round_.contradictions_found:
            if hypothesis.candidate_id in (c.hypothesis_a, c.hypothesis_b):
                other = c.hypothesis_b if c.hypothesis_a == hypothesis.candidate_id else c.hypothesis_a
                if other not in round_.survivors:
                    return f"survived_contradiction_eliminated_{other}"
                return f"survived_contradiction_coexists_with_{other}"

        return "survived_all_rounds"

    @staticmethod
    def _describe_historical_backing(ctx: RetrievalContext) -> str:
        """Build a concise description of historical backing."""
        if ctx.recommendation == "strong_backing" and ctx.best_match:
            entry = ctx.best_match.entry
            return (
                f"Strongly backed by history: similar hypothesis '{entry.statement[:80]}...' "
                f"achieved {ctx.best_match.historical_accuracy:.0%} accuracy in {ctx.best_match.similarity_score:.0%} similar context"
            )
        elif ctx.recommendation == "mixed" and ctx.matches:
            return (
                f"Mixed historical precedent: {len(ctx.matches)} similar hypotheses found, "
                f"avg accuracy {ctx.avg_historical_accuracy:.0%}"
            )
        return "No direct historical analog — novel hypothesis formation"

    @property
    def max_selection(self) -> int:
        return self._max

    def set_max_selection(self, n: int) -> None:
        self._max = max(1, min(15, n))
