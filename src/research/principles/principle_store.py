"""Principle Store — persistent storage for Research Principles (Milestone C).

Provides create, read, update, query, and retire operations for ResearchPrinciples.
Maintains the complete principle library.
"""

from __future__ import annotations

from src.schemas.research import PrincipleStatus, PrincipleStrength, ResearchPrinciple
from src.shared.logging import get_logger

logger = get_logger(__name__)


class PrincipleStore:
    """Persistent store for Research Principles with query capabilities.

    Stores principles at all strength levels: candidate, validated, mature, foundational.
    Supports retirement, contradiction tracking, and relationship queries.
    """

    def __init__(self) -> None:
        self._principles: dict[str, ResearchPrinciple] = {}
        self._by_domain: dict[str, list[str]] = {}  # domain → [principle_ids]
        self._by_strength: dict[str, list[str]] = {}  # strength → [principle_ids]
        self._retired: dict[str, ResearchPrinciple] = {}
        self._total_created: int = 0

    def save(self, principle: ResearchPrinciple) -> str:
        """Save a principle. Returns its ID."""
        pid = principle.principle_id
        self._principles[pid] = principle
        self._total_created += 1

        # Index by domain
        domain = principle.domain or "unknown"
        self._by_domain.setdefault(domain, []).append(pid)

        # Index by strength
        strength = principle.strength.value
        self._by_strength.setdefault(strength, []).append(pid)

        logger.debug("Saved principle: %s (domain=%s, strength=%s)", pid, domain, strength)
        return pid

    def get(self, principle_id: str) -> ResearchPrinciple | None:
        return self._principles.get(principle_id)

    def get_many(self, principle_ids: list[str]) -> dict[str, ResearchPrinciple]:
        return {pid: self._principles[pid] for pid in principle_ids if pid in self._principles}

    def get_all(self) -> list[ResearchPrinciple]:
        return list(self._principles.values())

    def get_active(self) -> list[ResearchPrinciple]:
        """Get all non-retired, non-archived principles."""
        return [
            p
            for p in self._principles.values()
            if p.status not in (PrincipleStatus.RETIRED, PrincipleStatus.ARCHIVED)
        ]

    def get_by_domain(self, domain: str) -> list[ResearchPrinciple]:
        ids = self._by_domain.get(domain, [])
        return [self._principles[pid] for pid in ids if pid in self._principles]

    def get_by_strength(self, strength: PrincipleStrength) -> list[ResearchPrinciple]:
        ids = self._by_strength.get(strength.value, [])
        return [self._principles[pid] for pid in ids if pid in self._principles]

    def get_validated_or_higher(self) -> list[ResearchPrinciple]:
        """Get principles at validated, mature, or foundational level."""
        result = []
        for s in (
            PrincipleStrength.VALIDATED,
            PrincipleStrength.MATURE,
            PrincipleStrength.FOUNDATIONAL,
        ):
            result.extend(self.get_by_strength(s))
        return result

    def get_competing_pairs(self) -> list[tuple[str, str]]:
        """Get pairs of principles in active competition."""
        pairs: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for p in self._principles.values():
            if p.status == PrincipleStatus.ACTIVE_COMPETITION:
                for other_id in p.competes_with:
                    if other_id in self._principles:
                        key = tuple(sorted([p.principle_id, other_id]))
                        if key not in seen:
                            seen.add(key)
                            pairs.append((p.principle_id, other_id))
        return pairs

    def retire(self, principle_id: str, reason: str = "") -> bool:
        """Retire a principle. Moves to retired store."""
        p = self._principles.pop(principle_id, None)
        if not p:
            return False
        p.status = PrincipleStatus.RETIRED
        self._retired[principle_id] = p

        # Re-index
        self._remove_from_indices(principle_id, p)
        logger.info("Retired principle %s: %s", principle_id, reason)
        return True

    def weaken(self, principle_id: str) -> bool:
        """Mark a principle as weakening."""
        p = self._principles.get(principle_id)
        if not p:
            return False
        p.status = PrincipleStatus.WEAKENING
        logger.info("Weakening principle: %s", principle_id)
        return True

    def record_contradiction(self, principle_id: str) -> bool:
        """Record a contradiction against a principle."""
        p = self._principles.get(principle_id)
        if not p:
            return False
        p.evidence.contradiction_count += 1
        if p.evidence.contradiction_count >= 10:
            self.retire(
                principle_id,
                f"Exceeded contradiction threshold " f"({p.evidence.contradiction_count})",
            )
        elif p.evidence.contradiction_count >= 5:
            self.weaken(principle_id)
        return True

    def update_strength(self, principle_id: str, new_strength: PrincipleStrength) -> bool:
        """Update a principle's strength level."""
        p = self._principles.get(principle_id)
        if not p:
            return False
        old_strength = p.strength.value
        p.strength = new_strength
        # Re-index
        if old_strength in self._by_strength:
            self._by_strength[old_strength] = [
                pid for pid in self._by_strength[old_strength] if pid != principle_id
            ]
        self._by_strength.setdefault(new_strength.value, []).append(principle_id)
        return True

    def _remove_from_indices(self, principle_id: str, p: ResearchPrinciple) -> None:
        domain = p.domain or "unknown"
        if domain in self._by_domain:
            self._by_domain[domain] = [
                pid for pid in self._by_domain[domain] if pid != principle_id
            ]
        strength = p.strength.value
        if strength in self._by_strength:
            self._by_strength[strength] = [
                pid for pid in self._by_strength[strength] if pid != principle_id
            ]

    def get_principle_for_finding(self, finding_id: str) -> ResearchPrinciple | None:
        """Find a principle that was promoted from a specific finding."""
        for p in self._principles.values():
            if finding_id in (p.source_findings or []):
                return p
        for p in self._retired.values():
            if finding_id in (p.source_findings or []):
                return p
        return None

    @property
    def count(self) -> int:
        return len(self._principles)

    @property
    def total_ever_created(self) -> int:
        return self._total_created + len(self._retired)

    @property
    def active_count(self) -> int:
        return len([p for p in self._principles.values() if p.status == PrincipleStatus.ACTIVE])

    @property
    def competing_count(self) -> int:
        return len(
            [p for p in self._principles.values() if p.status == PrincipleStatus.ACTIVE_COMPETITION]
        )

    def summary(self) -> str:
        return (
            f"PrincipleStore: {self.count} active ({self.active_count} active, "
            f"{self.competing_count} competing), {len(self._retired)} retired, "
            f"{self.total_ever_created} total created"
        )
