"""Hypothesis Competition Engine — Let hypotheses fight each other.

Milestone A: Structured contradiction detection + evidence attribution + elimination.
This is NOT an LLM debate. It is deterministic, rule-based competition:
    - Direction contradiction: two hypotheses predict the same indicator in opposite directions
    - Mechanism contradiction: incompatible causal mechanisms
    - Evidence comparison: whose evidence is stronger/more complete
    - Transmission comparison: whose transmission chain is more reliable
"""

from __future__ import annotations

from src.hypothesis.retriever import RetrievalContext, RetrievalReport
from src.schemas.hypothesis_v3_1 import (
    CandidateHypothesis,
    CompetitionRound,
    Contradiction,
    ContradictionType,
    EliminatedHypothesis,
    EliminationReason,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Competition Config ───────────────────────────────────────────────────────


# Indicator overlap: which indicators do two hypotheses need to share
# for a directional contradiction to be meaningful?
_INDICATOR_BY_DIMENSION: dict[str, set[str]] = {
    "liquidity": {"DXY", "USD", "US02Y", "NASDAQ"},
    "credit": {"HYG", "SPX"},
    "growth": {"SPX", "US10Y", "DXY"},
    "risk_appetite": {"SPX", "VIX", "HYG"},
    "inflation": {"TIPS", "US10Y", "Gold"},
}

# Weights for competition scoring
_EVIDENCE_WEIGHT = 0.40
_TRANSMISSION_WEIGHT = 0.25
_HISTORICAL_WEIGHT = 0.20
_NARRATIVE_WEIGHT = 0.15


# ── Engine ───────────────────────────────────────────────────────────────────


class CompetitionEngine:
    """Drives hypothesis competition: contradiction detection → evidence comparison → elimination.

    The engine operates in rounds:
        Round 1: Direction contradictions (fast elimination of directly opposing hypotheses)
        Round 2: Evidence strength comparison (weaker evidence eliminated)
        Round 3: Transmission reliability comparison (less reliable chains eliminated)
        Round 4: Dimension overlap deduplication (too many in same dim/direction)
    """

    def __init__(self) -> None:
        self._min_confidence = 0.25  # Minimum score to survive
        self._max_per_dim_direction = 2  # Max hypotheses per dimension+direction

    def compete(
        self,
        candidates: list[CandidateHypothesis],
        retrieval_report: RetrievalReport,
    ) -> CompetitionRound:
        """Run the full competition process.

        Args:
            candidates: All candidate hypotheses
            retrieval_report: Historical context for each candidate

        Returns:
            CompetitionRound with all eliminations and survivors
        """
        survivors = candidates.copy()
        eliminated: list[EliminatedHypothesis] = []
        contradictions: list[Contradiction] = []

        # Build index
        contexts = retrieval_report.contexts

        # ── Round 1: Direction Contradictions ─────────────────────────────
        contra_results = self._detect_direction_contradictions(survivors)
        contradictions.extend(contra_results["contradictions"])
        for elim in contra_results["eliminated"]:
            eliminated.append(elim)
            survivors = [s for s in survivors if s.candidate_id != elim.candidate_id]

        # ── Round 2: Evidence Strength Comparison ─────────────────────────
        evidence_results = self._compare_evidence(survivors, contexts)
        for elim in evidence_results["eliminated"]:
            eliminated.append(elim)
            survivors = [s for s in survivors if s.candidate_id != elim.candidate_id]

        # ── Round 3: Transmission Comparison ──────────────────────────────
        tx_results = self._compare_transmission(survivors)
        for elim in tx_results["eliminated"]:
            eliminated.append(elim)
            survivors = [s for s in survivors if s.candidate_id != elim.candidate_id]

        # ── Round 4: Dimension Overlap ────────────────────────────────────
        overlap_elims = self._deduplicate_dimensions(survivors)
        for elim in overlap_elims:
            eliminated.append(elim)
            survivors = [s for s in survivors if s.candidate_id != elim.candidate_id]

        # ── Final: Low Confidence Filter ──────────────────────────────────
        for c in list(survivors):
            if c.competition_score < self._min_confidence:
                eliminated.append(
                    EliminatedHypothesis(
                        candidate_id=c.candidate_id,
                        eliminated_by="",
                        reason=EliminationReason.LOW_CONFIDENCE,
                        detail=f"Competition score {c.competition_score:.3f} below minimum {self._min_confidence}",
                    )
                )
                survivors.remove(c)

        # Log
        logger.info(
            "competition_complete before=%d after=%d eliminated=%d contradictions=%d",
            len(candidates),
            len(survivors),
            len(eliminated),
            len(contradictions),
        )

        return CompetitionRound(
            candidates_before=len(candidates),
            candidates_after=len(survivors),
            contradictions_found=contradictions,
            eliminated=eliminated,
            survivors=[s.candidate_id for s in survivors],
        )

    # ── Round 1: Direction Contradictions ─────────────────────────────────

    def _detect_direction_contradictions(
        self,
        candidates: list[CandidateHypothesis],
    ) -> dict:
        """Detect direct directional contradictions between hypotheses."""
        contradictions: list[Contradiction] = []
        eliminated: list[EliminatedHypothesis] = []

        # Group by indicator predictions
        indicator_preds: dict[str, list[CandidateHypothesis]] = {}
        for c in candidates:
            for seg in c.transmission_chain:
                ind = seg.target
                indicator_preds.setdefault(ind, []).append(c)

        seen_pairs: set[tuple] = set()
        for indicator, hyps in indicator_preds.items():
            bulls = [h for h in hyps if h.direction == "bullish"]
            bears = [h for h in hyps if h.direction == "bearish"]

            if not bulls or not bears:
                continue

            # Each bull vs each bear on same indicator = contradiction
            for bull in bulls:
                for bear in bears:
                    pair_key = tuple(sorted([bull.candidate_id, bear.candidate_id]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    contra = Contradiction(
                        hypothesis_a=bull.candidate_id,
                        hypothesis_b=bear.candidate_id,
                        contradiction_type=ContradictionType.DIRECTION,
                        indicator=indicator,
                        description=(
                            f"{bull.candidate_id} predicts {indicator} bullish, "
                            f"{bear.candidate_id} predicts {indicator} bearish — "
                            f"they cannot both be right"
                        ),
                        severity=0.8,
                    )
                    contradictions.append(contra)

                    # Eliminate the one with weaker competition score
                    if bull.competition_score >= bear.competition_score:
                        loser, winner = bear, bull
                    else:
                        loser, winner = bull, bear

                    eliminated.append(
                        EliminatedHypothesis(
                            candidate_id=loser.candidate_id,
                            eliminated_by=winner.candidate_id,
                            reason=EliminationReason.DIRECT_CONTRADICTION,
                            contradiction=contra,
                            detail=(
                                f"Direct directional contradiction on {indicator}: "
                                f"{loser.candidate_id} ({loser.direction}) vs "
                                f"{winner.candidate_id} ({winner.direction}). "
                                f"Eliminated due to weaker competition score "
                                f"({loser.competition_score:.3f} < {winner.competition_score:.3f})."
                            ),
                            revival_condition=(
                                f"If {indicator} moves in {loser.direction} direction, "
                                f"this hypothesis should be reconsidered."
                            ),
                        )
                    )

        return {"contradictions": contradictions, "eliminated": eliminated}

    # ── Round 2: Evidence Comparison ──────────────────────────────────────

    def _compare_evidence(
        self,
        candidates: list[CandidateHypothesis],
        contexts: dict[str, RetrievalContext],
    ) -> dict:
        """Eliminate hypotheses with weak or missing evidence relative to peers."""
        eliminated: list[EliminatedHypothesis] = []

        # Group by dimension
        by_dim: dict[str, list[CandidateHypothesis]] = {}
        for c in candidates:
            by_dim.setdefault(c.dimension, []).append(c)

        for dim, hyps in by_dim.items():
            if len(hyps) <= 1:
                continue

            # Compute evidence strength scores
            scores: dict[str, float] = {}
            for h in hyps:
                ev_score = h.avg_evidence_strength if h.evidence else 0.2
                # Boost from historical backing
                ctx = contexts.get(h.candidate_id)
                hist_boost = 0.0
                if ctx and ctx.recommendation == "strong_backing":
                    hist_boost = 0.15
                elif ctx and ctx.recommendation == "mixed":
                    hist_boost = 0.05
                scores[h.candidate_id] = ev_score + hist_boost

            # Find the max score
            max_score = max(scores.values()) if scores else 0.0

            # Eliminate those significantly below the max (gap > 0.35)
            for h in hyps:
                score = scores.get(h.candidate_id, 0.0)
                if max_score - score > 0.35 and len(hyps) > 2:
                    # Find the stronger peer for the elimination record
                    stronger = max(
                        (o for o in hyps if o.candidate_id != h.candidate_id),
                        key=lambda x: scores.get(x.candidate_id, 0),
                        default=None,
                    )
                    eliminated.append(
                        EliminatedHypothesis(
                            candidate_id=h.candidate_id,
                            eliminated_by=stronger.candidate_id if stronger else "",
                            reason=EliminationReason.WEAKER_EVIDENCE,
                            detail=(
                                f"Weak evidence support (score={score:.3f}) vs peer max ({max_score:.3f}). "
                                f"Evidence count: {h.evidence_count}, avg strength: {h.avg_evidence_strength:.3f}."
                            ),
                            revival_condition="If confirming evidence for this dimension emerges.",
                        )
                    )

        return {"eliminated": eliminated}

    # ── Round 3: Transmission Comparison ─────────────────────────────────

    def _compare_transmission(
        self,
        candidates: list[CandidateHypothesis],
    ) -> dict:
        """Compare transmission chains — eliminate hypotheses with unreliable chains."""
        eliminated: list[EliminatedHypothesis] = []

        # Group by dimension
        by_dim: dict[str, list[CandidateHypothesis]] = {}
        for c in candidates:
            by_dim.setdefault(c.dimension, []).append(c)

        for dim, hyps in by_dim.items():
            if len(hyps) <= 1:
                continue

            for h in hyps:
                if h.chain_length == 0:
                    continue

                avg_rel = h.avg_chain_reliability

                # Very unreliable chain + better alternatives exist
                if avg_rel < 0.35 and len(hyps) > 2:
                    alternatives = [o for o in hyps if o.candidate_id != h.candidate_id]
                    better_alt = max(
                        alternatives, key=lambda x: x.avg_chain_reliability, default=None
                    )
                    eliminated.append(
                        EliminatedHypothesis(
                            candidate_id=h.candidate_id,
                            eliminated_by=better_alt.candidate_id if better_alt else "",
                            reason=EliminationReason.BROKEN_TRANSMISSION,
                            detail=(
                                f"Transmission chain has low average reliability ({avg_rel:.3f}). "
                                f"Chain length: {h.chain_length}, segments: "
                                f"{', '.join(s.segment_id for s in h.transmission_chain)}."
                            ),
                            revival_condition=(
                                "If transmission segments are validated by future data, "
                                "reliability scores will increase and this hypothesis can be reconsidered."
                            ),
                        )
                    )

        return {"eliminated": eliminated}

    # ── Round 4: Dimension Overlap Deduplication ─────────────────────────

    def _deduplicate_dimensions(
        self,
        candidates: list[CandidateHypothesis],
    ) -> list[EliminatedHypothesis]:
        """Ensure max N hypotheses per dimension+direction."""
        eliminated: list[EliminatedHypothesis] = []

        by_key: dict[str, list[CandidateHypothesis]] = {}
        for c in candidates:
            key = f"{c.dimension}:{c.direction}"
            by_key.setdefault(key, []).append(c)

        for key, hyps in by_key.items():
            if len(hyps) <= self._max_per_dim_direction:
                continue

            # Sort by competition score, keep the top ones
            hyps.sort(key=lambda h: h.competition_score, reverse=True)
            to_keep = hyps[: self._max_per_dim_direction]
            to_elim = hyps[self._max_per_dim_direction :]
            _keeper_ids = {h.candidate_id for h in to_keep}

            for h in to_elim:
                best = to_keep[0]
                eliminated.append(
                    EliminatedHypothesis(
                        candidate_id=h.candidate_id,
                        eliminated_by=best.candidate_id,
                        reason=EliminationReason.DIMENSION_OVERLAP,
                        detail=(
                            f"Too many {h.direction} hypotheses in {h.dimension} ({len(hyps)} > {self._max_per_dim_direction}). "
                            f"Eliminated in favor of higher-scoring hypothesis {best.candidate_id} "
                            f"(score {best.competition_score:.3f} vs {h.competition_score:.3f})."
                        ),
                        revival_condition=f"If {best.candidate_id} is disproven, this can be reconsidered.",
                    )
                )

        return eliminated

    # ── Utilities ────────────────────────────────────────────────────────

    @property
    def min_confidence(self) -> float:
        return self._min_confidence

    def set_min_confidence(self, threshold: float) -> None:
        self._min_confidence = max(0.1, min(0.9, threshold))
