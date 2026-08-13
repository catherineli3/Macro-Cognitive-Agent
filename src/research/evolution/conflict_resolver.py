"""Conflict Resolver — detects and resolves principle conflicts (Milestone C, Q4).

Review 3: Competing Principles may coexist indefinitely. Resolution is
evidence-driven, not time-driven. No forced merge. The only penalty is
a weight discount on beliefs citing competing principles.

Key rules:
    - Two validated principles with contradictory claims → ACTIVE_COMPETITION
    - Both remain active (strength preserved)
    - Beliefs citing either are weight-penalized (×0.5)
    - Resolution: one wins >=70% of next 30 cycles → opponent enters WEAKENING
    - Neither dominates after 50 cycles → both archived as "unresolved regime-dependent"
"""

from __future__ import annotations

from src.research.principles.principle_store import PrincipleStore
from src.schemas.research import (
    CompetingPrinciple,
    ConflictRecord,
    ConflictResolution,
    PrincipleStatus,
    ResearchPrinciple,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


class ConflictResolver:
    """Detects and manages conflicts between Research Principles.

    Competing Principles coexist. Resolution is evidence-driven.
    Weight penalty applied to beliefs citing competing principles.
    """

    MAX_UNRESOLVED_CYCLES = 50
    RESOLUTION_WIN_RATE = 0.70
    RESOLUTION_MIN_CYCLES = 30

    def __init__(self, store: PrincipleStore | None = None) -> None:
        self._store = store or PrincipleStore()
        self._active_competitions: dict[str, CompetingPrinciple] = {}
        self._resolved_competitions: dict[str, ConflictRecord] = {}
        self._conflict_history: list[ConflictRecord] = []

    def detect_conflicts(self) -> list[CompetingPrinciple]:
        """Scan all active principles for contradictory claims.

        Returns list of newly detected competing pairs.
        """
        active = self._store.get_validated_or_higher()
        detected: list[CompetingPrinciple] = []

        for i, p_a in enumerate(active):
            for p_b in active[i + 1 :]:
                if self._are_contradictory(p_a, p_b):
                    pair_key = self._pair_key(p_a.principle_id, p_b.principle_id)
                    if pair_key not in self._active_competitions:
                        competition = CompetingPrinciple(
                            principle_a_id=p_a.principle_id,
                            principle_b_id=p_b.principle_id,
                            domain=p_a.domain or p_b.domain,
                        )
                        self._active_competitions[pair_key] = competition

                        # Mark both principles as in competition
                        p_a.status = PrincipleStatus.ACTIVE_COMPETITION
                        p_a.competes_with.append(p_b.principle_id)
                        p_b.status = PrincipleStatus.ACTIVE_COMPETITION
                        p_b.competes_with.append(p_a.principle_id)

                        detected.append(competition)
                        logger.info(
                            "Detected competing principles: %s vs %s",
                            p_a.principle_id[:8],
                            p_b.principle_id[:8],
                        )

        return detected

    def record_evidence(
        self, principle_id: str, correct: bool, cycle: int = 0
    ) -> list[ConflictResolution]:
        """Record evidence for/against a principle in its active competitions.

        Returns list of resolved competitions (if any resolution occurred).
        """
        resolved: list[ConflictResolution] = []

        for pair_key, comp in list(self._active_competitions.items()):
            if comp.principle_a_id == principle_id:
                comp.record_evidence(for_a=correct)
            elif comp.principle_b_id == principle_id:
                comp.record_evidence(for_a=not correct)
            else:
                continue

            comp.advance_cycle()

            # Check resolution conditions
            if comp.cycles_since_start >= self.RESOLUTION_MIN_CYCLES:
                if comp.is_decisive:
                    winner = (
                        comp.principle_a_id
                        if comp.a_win_rate >= self.RESOLUTION_WIN_RATE
                        else comp.principle_b_id
                    )
                    loser = (
                        comp.principle_b_id
                        if winner == comp.principle_a_id
                        else comp.principle_a_id
                    )
                    resolution = (
                        ConflictResolution.A_WINS
                        if winner == comp.principle_a_id
                        else ConflictResolution.B_WINS
                    )
                    comp.resolution = resolution
                    comp.winner_id = winner
                    comp.loser_id = loser
                    comp.status = "resolved"
                    comp.resolved_at_cycle = cycle

                    self._apply_resolution(comp, resolution)
                    resolved.append(resolution)

                    # Remove from active
                    self._resolved_competitions[pair_key] = ConflictRecord(
                        competing_pair=comp,
                        principle_a_id=comp.principle_a_id,
                        principle_b_id=comp.principle_b_id,
                        action="resolved",
                        resolution=resolution,
                    )
                    del self._active_competitions[pair_key]

                elif comp.is_stalemate:
                    comp.resolution = ConflictResolution.ARCHIVED_REGIME
                    comp.status = "resolved"
                    comp.resolved_at_cycle = cycle

                    # Both archived as regime-dependent
                    self._store.retire(
                        comp.principle_a_id, "Competition stalemate — regime-dependent"
                    )
                    self._store.retire(
                        comp.principle_b_id, "Competition stalemate — regime-dependent"
                    )

                    self._resolved_competitions[pair_key] = ConflictRecord(
                        competing_pair=comp,
                        principle_a_id=comp.principle_a_id,
                        principle_b_id=comp.principle_b_id,
                        action="archived",
                        resolution=ConflictResolution.ARCHIVED_REGIME,
                    )
                    del self._active_competitions[pair_key]
                    resolved.append(ConflictResolution.ARCHIVED_REGIME)

        return resolved

    def _apply_resolution(self, comp: CompetingPrinciple, resolution: ConflictResolution) -> None:
        """Apply resolution: update principle statuses."""
        if resolution == ConflictResolution.A_WINS:
            self._store.weaken(comp.principle_b_id)
            p_b = self._store.get(comp.principle_b_id)
            if p_b:
                p_b.status = PrincipleStatus.WEAKENING
            # Restore winner
            p_a = self._store.get(comp.principle_a_id)
            if p_a:
                p_a.status = PrincipleStatus.ACTIVE
                p_a.competes_with = [pid for pid in p_a.competes_with if pid != comp.principle_b_id]
                p_a.competition_resolution = resolution

        elif resolution == ConflictResolution.B_WINS:
            self._store.weaken(comp.principle_a_id)
            p_a = self._store.get(comp.principle_a_id)
            if p_a:
                p_a.status = PrincipleStatus.WEAKENING
            p_b = self._store.get(comp.principle_b_id)
            if p_b:
                p_b.status = PrincipleStatus.ACTIVE
                p_b.competes_with = [pid for pid in p_b.competes_with if pid != comp.principle_a_id]
                p_b.competition_resolution = resolution

    def get_competition(
        self, principle_a_id: str, principle_b_id: str
    ) -> CompetingPrinciple | None:
        return self._active_competitions.get(self._pair_key(principle_a_id, principle_b_id))

    def get_competitions_for(self, principle_id: str) -> list[CompetingPrinciple]:
        return [
            comp
            for comp in self._active_competitions.values()
            if principle_id in (comp.principle_a_id, comp.principle_b_id)
        ]

    def get_penalty(self, principle_id: str) -> float:
        """Get the weight penalty for a principle in competition.

        Review 3: Beliefs citing competing principles are weight-penalized (x0.5).
        """
        competitions = self.get_competitions_for(principle_id)
        if competitions:
            return 0.5  # Standard penalty
        return 1.0

    def get_double_penalty(self, principle_a_id: str, principle_b_id: str) -> float:
        """If a belief cites two competing principles, apply double penalty."""
        comp = self.get_competition(principle_a_id, principle_b_id)
        if comp:
            return 0.25  # 0.5 × 0.5
        return 1.0

    @staticmethod
    def _are_contradictory(p_a: ResearchPrinciple, p_b: ResearchPrinciple) -> bool:
        """Check if two principles make contradictory claims.

        Contradiction: same domain, same causal relationship, opposite direction.
        """
        if p_a.domain != p_b.domain:
            return False

        # Check for opposite-direction claims on same relationship
        stmt_a = p_a.statement.lower()
        stmt_b = p_b.statement.lower()

        # Simplistic but effective: look for directional opposites
        if ("increases" in stmt_a and "decreases" in stmt_b) or (
            "decreases" in stmt_a and "increases" in stmt_b
        ):
            if ConflictResolver._share_subject(stmt_a, stmt_b):
                return True

        if ("reliable" in stmt_a and "unreliable" in stmt_b) or (
            "unreliable" in stmt_a and "reliable" in stmt_b
        ):
            if ConflictResolver._share_subject(stmt_a, stmt_b):
                return True

        return False

    @staticmethod
    def _share_subject(stmt_a: str, stmt_b: str) -> bool:
        """Check if two statements share a common subject."""
        words_a = set(stmt_a.split())
        words_b = set(stmt_b.split())
        common = words_a & words_b
        # Need more than just stop words
        stop_words = {"in", "the", "a", "an", "is", "to", "of", "and", "or", "for"}
        meaningful = common - stop_words
        return len(meaningful) >= 2

    @staticmethod
    def _pair_key(pid_a: str, pid_b: str) -> str:
        return "|".join(sorted([pid_a, pid_b]))

    @property
    def active_competition_count(self) -> int:
        return len(self._active_competitions)

    @property
    def total_resolved(self) -> int:
        return len(self._resolved_competitions)

    def summary(self) -> str:
        return (
            f"ConflictResolver: {self.active_competition_count} active competitions, "
            f"{self.total_resolved} resolved"
        )
