"""Candidate Principle Manager — tracks principle candidates awaiting cross-regime validation (Milestone C).

When a finding cluster passes P2-P4 but fails P1 (cross-regime), it enters
candidate status. The CandidateManager tracks these, actively seeks cross-regime
validation, and manages graduation.
"""

from __future__ import annotations

from typing import Optional

from src.schemas.research import ResearchPrinciple, PrincipleStrength, PrincipleStatus
from src.shared.logging import get_logger

logger = get_logger(__name__)


class CandidatePrincipleManager:
    """Manages candidate principles that need cross-regime validation.

    A principle enters CANDIDATE status when P2-P4 are met but P1 (cross-regime)
    is pending. The manager tracks them and handles graduation when P1 is satisfied.
    """

    def __init__(self) -> None:
        self._candidates: dict[str, ResearchPrinciple] = {}
        self._graduated: dict[str, ResearchPrinciple] = {}
        self._rejected: dict[str, ResearchPrinciple] = {}
        self._regime_checks: dict[str, list[str]] = {}  # principle_id → [regime_keys]

    def register_candidate(self, principle: ResearchPrinciple) -> bool:
        """Register a candidate principle for cross-regime tracking.

        Returns True if successfully registered, False if already exists.
        """
        if principle.principle_id in self._candidates:
            logger.debug("Candidate %s already registered", principle.principle_id)
            return False

        if principle.strength != PrincipleStrength.CANDIDATE:
            logger.warning(
                "Cannot register non-candidate principle %s (strength=%s)",
                principle.principle_id, principle.strength.value,
            )
            return False

        self._candidates[principle.principle_id] = principle
        self._regime_checks[principle.principle_id] = list(
            principle.evidence.regimes_validated
        )
        logger.info(
            "Registered candidate: %s (domain=%s, obs=%d, regimes=%d)",
            principle.principle_id, principle.domain,
            principle.evidence.total_observations,
            principle.evidence.regimes_count,
        )
        return True

    def record_regime_validation(self, principle_id: str,
                                  regime_key: str,
                                  validated: bool = True) -> bool:
        """Record a regime check result. Returns True if candidate graduated."""
        if principle_id not in self._candidates:
            return False

        if validated:
            if regime_key not in self._regime_checks.get(principle_id, []):
                self._regime_checks.setdefault(principle_id, []).append(regime_key)

            candidate = self._candidates[principle_id]
            candidate.evidence.regimes_count = len(self._regime_checks[principle_id])
            candidate.evidence.regimes_validated = list(self._regime_checks[principle_id])

            # Check P1 threshold
            if candidate.evidence.regimes_count >= 2:
                return self._graduate(principle_id)

        return False

    def _graduate(self, principle_id: str) -> bool:
        """Promote a candidate to validated status."""
        candidate = self._candidates.pop(principle_id, None)
        if not candidate:
            return False

        candidate.strength = PrincipleStrength.VALIDATED
        candidate.status = PrincipleStatus.ACTIVE
        self._graduated[principle_id] = candidate
        logger.info(
            "Graduated candidate → VALIDATED: %s (regimes=%d, obs=%d)",
            principle_id, candidate.evidence.regimes_count,
            candidate.evidence.total_observations,
        )
        return True

    def check_maturity(self, principle_id: str) -> bool:
        """Check if a validated principle should advance to MATURE."""
        p = self._graduated.get(principle_id)
        if not p:
            p = self._candidates.get(principle_id)
        if not p:
            return False

        if (p.evidence.total_observations >= 50
                and p.evidence.regimes_count >= 3
                and p.evidence.contradiction_count <= 2):
            p.strength = PrincipleStrength.MATURE
            logger.info("Principle graduated to MATURE: %s", principle_id)
            return True
        return False

    def check_foundational(self, principle_id: str) -> bool:
        """Check if a mature principle should advance to FOUNDATIONAL."""
        p = self._graduated.get(principle_id)
        if not p:
            return False

        if (p.evidence.total_observations >= 100
                and p.evidence.regimes_count >= 5
                and p.evidence.contradiction_count == 0):
            p.strength = PrincipleStrength.FOUNDATIONAL
            logger.info("Principle graduated to FOUNDATIONAL: %s", principle_id)
            return True
        return False

    def reject_candidate(self, principle_id: str, reason: str = "") -> bool:
        """Reject a candidate that cannot be validated."""
        candidate = self._candidates.pop(principle_id, None)
        if candidate:
            candidate.status = PrincipleStatus.RETIRED
            self._rejected[principle_id] = candidate
            logger.info("Rejected candidate %s: %s", principle_id, reason)
            return True
        return False

    def get_candidate(self, principle_id: str) -> ResearchPrinciple | None:
        return self._candidates.get(principle_id)

    def get_graduated(self, principle_id: str) -> ResearchPrinciple | None:
        return self._graduated.get(principle_id)

    def get_all_validated(self) -> list[ResearchPrinciple]:
        """Get all graduated (validated or higher) principles."""
        return list(self._graduated.values())

    def get_pending_candidates(self) -> list[ResearchPrinciple]:
        """Get candidates still awaiting cross-regime validation."""
        return [
            p for p in self._candidates.values()
            if p.evidence.regimes_count < 2
        ]

    @property
    def candidate_count(self) -> int:
        return len(self._candidates)

    @property
    def graduated_count(self) -> int:
        return len(self._graduated)

    @property
    def rejected_count(self) -> int:
        return len(self._rejected)

    def summary(self) -> str:
        return (
            f"CandidateManager: {self.candidate_count} pending, "
            f"{self.graduated_count} graduated, {self.rejected_count} rejected"
        )
