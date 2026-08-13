"""BeliefGraph — relationship graph between beliefs (V3.2 Enhanced).

V3.2 upgrades auto_discover_relations() with:
- Semantic CONTRADICTS detection: opposite directions on correlated assets
- Causal EXPLAINS detection: one belief's outputs match another's inputs
- Keyword overlap scoring beyond simple domain matching
- Each new belief checks ALL existing beliefs

Relationships:
    SUPPORTS    → Belief A reinforces belief B
    COMPETES    → Belief A and B are competing explanations
    CONTRADICTS → Belief A contradicts belief B
    EXPLAINS    → Belief A explains belief B
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.research.beliefs.schemas import (
    BeliefDomain,
    BeliefRelationType,
    ResearchBelief,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BeliefRelation:
    """A directed relationship between two beliefs."""

    source_id: str
    target_id: str
    relation_type: BeliefRelationType
    strength: float = 0.5
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ── V3.2: Domain adjacency for cross-domain relationships ──────────────

DOMAIN_ADJACENCY: dict[BeliefDomain, dict[BeliefDomain, float]] = {
    BeliefDomain.POLICY: {
        BeliefDomain.INFLATION: 0.8,
        BeliefDomain.DOLLAR: 0.9,
        BeliefDomain.LIQUIDITY: 0.85,
        BeliefDomain.GROWTH: 0.6,
        BeliefDomain.RISK: 0.5,
    },
    BeliefDomain.INFLATION: {
        BeliefDomain.POLICY: 0.8,
        BeliefDomain.DOLLAR: 0.5,
        BeliefDomain.GROWTH: 0.4,
        BeliefDomain.EMPLOYMENT: 0.5,
    },
    BeliefDomain.GROWTH: {
        BeliefDomain.POLICY: 0.6,
        BeliefDomain.CREDIT: 0.8,
        BeliefDomain.RISK: 0.75,
        BeliefDomain.EMPLOYMENT: 0.85,
    },
    BeliefDomain.LIQUIDITY: {
        BeliefDomain.POLICY: 0.85,
        BeliefDomain.CREDIT: 0.9,
        BeliefDomain.RISK: 0.8,
        BeliefDomain.DOLLAR: 0.5,
    },
    BeliefDomain.RISK: {
        BeliefDomain.LIQUIDITY: 0.8,
        BeliefDomain.GROWTH: 0.75,
        BeliefDomain.DOLLAR: 0.5,
    },
    BeliefDomain.CREDIT: {
        BeliefDomain.GROWTH: 0.8,
        BeliefDomain.LIQUIDITY: 0.9,
        BeliefDomain.RISK: 0.7,
    },
    BeliefDomain.DOLLAR: {
        BeliefDomain.POLICY: 0.9,
        BeliefDomain.INFLATION: 0.5,
        BeliefDomain.RISK: 0.4,
        BeliefDomain.LIQUIDITY: 0.5,
    },
    BeliefDomain.AI_CAPEX: {
        BeliefDomain.GROWTH: 0.7,
        BeliefDomain.RISK: 0.6,
        BeliefDomain.POLICY: 0.3,
    },
    BeliefDomain.EMPLOYMENT: {
        BeliefDomain.GROWTH: 0.85,
        BeliefDomain.INFLATION: 0.5,
        BeliefDomain.POLICY: 0.4,
    },
}

# ── V3.2: Directional signal mapping for contradiction detection ──────

DOMAIN_SIGNALS: dict[BeliefDomain, list[str]] = {
    BeliefDomain.POLICY: ["dxy", "rates", "ust10y", "ust2y", "fed", "yield", "curve"],
    BeliefDomain.INFLATION: ["cpi", "pce", "tips", "breakeven", "expectations", "commodity"],
    BeliefDomain.GROWTH: ["gdp", "pmi", "ism", "employment", "payroll", "earnings"],
    BeliefDomain.LIQUIDITY: ["repo", "sofr", "reserve", "balance_sheet", "credit_spread"],
    BeliefDomain.RISK: ["vix", "vol", "skew", "put_call", "sentiment", "appetite"],
    BeliefDomain.CREDIT: ["hyg", "spread", "cdx", "corporate", "ig", "hy", "default"],
    BeliefDomain.DOLLAR: ["dxy", "usd", "dollar", "fx", "em_fx", "capital_flow"],
    BeliefDomain.AI_CAPEX: ["nasdaq", "semiconductor", "ai", "capex", "tech", "nvidia"],
    BeliefDomain.EMPLOYMENT: ["payroll", "unemployment", "nfp", "wage", "jolts", "labor"],
}

# ── V3.2: Term-level synonyms for semantic matching ────────────────────

TERM_SYNONYMS: dict[str, list[str]] = {
    "hawk": ["hawkish", "tightening", "hike", "restrictive", "hawk"],
    "dove": ["dovish", "easing", "cut", "accommodative", "dove"],
    "bull": ["bullish", "rally", "upside", "positive", "expansion"],
    "bear": ["bearish", "selloff", "downside", "negative", "contraction"],
    "rise": ["rising", "increase", "higher", "surge", "spike"],
    "fall": ["falling", "decrease", "lower", "decline", "drop", "collapse"],
    "tight": ["tighten", "tightening", "restrictive", "constrain"],
    "easy": ["easing", "loose", "accommodative", "expansionary"],
}


def _tokenize_title(title: str) -> set[str]:
    """Tokenize and normalize belief title."""
    import re

    tokens = set()
    for word in title.lower().split():
        word = re.sub(r"[^a-z]", "", word)
        if len(word) >= 3:
            tokens.add(word)
    # Expand synonyms
    expanded = set(tokens)
    for token in tokens:
        for root, synonyms in TERM_SYNONYMS.items():
            if token in synonyms:
                expanded.add(root)
                expanded.update(s for s in synonyms if s != token)
    return expanded


def _opposite_direction(title_a: str, title_b: str) -> bool:
    """Check if two belief titles indicate opposite directions."""
    tokens_a = _tokenize_title(title_a)
    tokens_b = _tokenize_title(title_b)

    # Check for explicit opposite word pairs
    opposite_pairs = [
        (
            {"bull", "bullish", "rally", "upside", "expansion"},
            {"bear", "bearish", "selloff", "downside", "contraction"},
        ),
        (
            {"rise", "rising", "higher", "surge", "spike"},
            {"fall", "falling", "lower", "decline", "drop"},
        ),
        (
            {"tight", "tighten", "tightening", "hawk", "hawkish"},
            {"easy", "easing", "loose", "dove", "dovish"},
        ),
    ]

    for up_set, down_set in opposite_pairs:
        if tokens_a & up_set and tokens_b & down_set:
            return True
        if tokens_a & down_set and tokens_b & up_set:
            return True

    return False


def _has_causal_link(belief_a: ResearchBelief, belief_b: ResearchBelief) -> tuple[bool, str]:
    """Check if belief A could explain belief B through causal domain linkage.

    Returns (is_explanatory, reason).
    """
    # Domain adjacency tells us plausible causal chains
    adjacency = DOMAIN_ADJACENCY.get(belief_a.domain, {}).get(belief_b.domain, 0)
    if adjacency < 0.5:
        return False, ""

    # Check if A's keywords appear in B's title (A explains B)
    tokens_a = _tokenize_title(belief_a.title)
    tokens_b = _tokenize_title(belief_b.title)
    overlap = tokens_a & tokens_b

    if len(overlap) >= 2 and adjacency >= 0.7:
        return (
            True,
            f"Domain adjacency ({adjacency:.0%}) + keyword overlap: {', '.join(list(overlap)[:3])}",
        )

    if adjacency >= 0.85:
        return True, f"Strong domain adjacency ({adjacency:.0%})"

    return False, ""


@dataclass
class BeliefGraph:
    """V3.2 Enhanced directed graph of beliefs and their relationships.

    Automatically discovers SUPPORTS / COMPETES / CONTRADICTS / EXPLAINS
    relationships when new beliefs are added.
    """

    beliefs: dict[str, ResearchBelief] = field(default_factory=dict)
    relations: list[BeliefRelation] = field(default_factory=list)
    _new_belief_ids: set[str] = field(default_factory=set)

    def add_belief(self, belief: ResearchBelief) -> None:
        """Add a belief and auto-discover relationships with existing ones."""
        is_new = belief.id not in self.beliefs
        self.beliefs[belief.id] = belief
        if is_new:
            self._new_belief_ids.add(belief.id)
            # V3.2: Immediately discover relations for this new belief
            self._discover_relations_for(belief)

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: BeliefRelationType,
        strength: float = 0.5,
        description: str = "",
    ) -> BeliefRelation | None:
        """Add a relationship between two beliefs."""
        if source_id not in self.beliefs or target_id not in self.beliefs:
            return None

        if source_id == target_id:
            return None

        # Avoid duplicates
        for r in self.relations:
            if (
                r.source_id == source_id
                and r.target_id == target_id
                and r.relation_type == relation_type
            ):
                return r

        rel = BeliefRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            strength=strength,
            description=description,
        )
        self.relations.append(rel)

        # Update belief link lists
        source = self.beliefs.get(source_id)
        target = self.beliefs.get(target_id)
        if source and target:
            if relation_type == BeliefRelationType.SUPPORTS:
                source.support_links.append(target_id)
                target.support_links.append(source_id)
            elif relation_type == BeliefRelationType.COMPETES:
                source.competition_links.append(target_id)
                target.competition_links.append(source_id)
            elif relation_type == BeliefRelationType.CONTRADICTS:
                source.contradiction_links.append(target_id)
                target.contradiction_links.append(source_id)
            elif relation_type == BeliefRelationType.EXPLAINS:
                source.explanation_links.append(target_id)

        return rel

    # ── V3.2: Auto-discovery ──────────────────────────────────────────

    def _discover_relations_for(self, new_belief: ResearchBelief) -> int:
        """V3.2: Discover all relations between a new belief and existing ones.

        Returns number of new relations added.
        """
        added = 0
        for bid, existing in self.beliefs.items():
            if bid == new_belief.id:
                continue

            # Phase 1: Same domain → COMPETES or SUPPORTS
            if new_belief.domain == existing.domain:
                if _opposite_direction(new_belief.title, existing.title):
                    rel = self.add_relation(
                        new_belief.id,
                        existing.id,
                        BeliefRelationType.COMPETES,
                        strength=0.7,
                        description=f"Same domain ({new_belief.domain.value}) — competing interpretations",
                    )
                    if rel:
                        added += 1
                else:
                    rel = self.add_relation(
                        new_belief.id,
                        existing.id,
                        BeliefRelationType.SUPPORTS,
                        strength=0.55,
                        description=f"Same domain ({new_belief.domain.value}) — aligned interpretations",
                    )
                    if rel:
                        added += 1
                continue

            # Phase 2: Check CONTRADICTS — one says up, other says down
            if _opposite_direction(new_belief.title, existing.title):
                # Only recognize as contradiction if domains are adjacent
                adjacency = DOMAIN_ADJACENCY.get(new_belief.domain, {}).get(existing.domain, 0)
                if adjacency >= 0.4:
                    rel = self.add_relation(
                        new_belief.id,
                        existing.id,
                        BeliefRelationType.CONTRADICTS,
                        strength=0.5 + adjacency * 0.3,
                        description=f"Opposite direction across {new_belief.domain.value}/{existing.domain.value}",
                    )
                    if rel:
                        added += 1
                continue

            # Phase 3: Check EXPLAINS — causal domain chain
            is_explanatory, reason = _has_causal_link(new_belief, existing)
            if is_explanatory:
                rel = self.add_relation(
                    new_belief.id,
                    existing.id,
                    BeliefRelationType.EXPLAINS,
                    strength=0.6,
                    description=reason,
                )
                if rel:
                    added += 1
                continue

            # Also check reverse: existing explains new
            is_explanatory, reason = _has_causal_link(existing, new_belief)
            if is_explanatory:
                rel = self.add_relation(
                    existing.id,
                    new_belief.id,
                    BeliefRelationType.EXPLAINS,
                    strength=0.6,
                    description=reason,
                )
                if rel:
                    added += 1
                continue

            # Phase 4: Cross-domain SUPPORTS via keyword overlap
            tokens_a = _tokenize_title(new_belief.title)
            tokens_b = _tokenize_title(existing.title)
            overlap = tokens_a & tokens_b
            if len(overlap) >= 2:
                rel = self.add_relation(
                    new_belief.id,
                    existing.id,
                    BeliefRelationType.SUPPORTS,
                    strength=0.35 + min(len(overlap) * 0.1, 0.3),
                    description=f"Cross-domain keyword overlap: {', '.join(list(overlap)[:3])}",
                )
                if rel:
                    added += 1

        return added

    def auto_discover_relations(self) -> int:
        """V3.2: Discover ALL pairwise relationships across all beliefs.

        This is the batch version for when loading persisted beliefs.
        Uses the same enhanced logic as per-belief discovery.
        """
        added = 0
        belief_list = list(self.beliefs.values())

        for i, a in enumerate(belief_list):
            for b in belief_list[i + 1 :]:
                # Skip if relationship already exists (any type between these two)
                existing = False
                for r in self.relations:
                    if (r.source_id == a.id and r.target_id == b.id) or (
                        r.source_id == b.id and r.target_id == a.id
                    ):
                        existing = True
                        break
                if existing:
                    continue

                # Same domain
                if a.domain == b.domain:
                    if _opposite_direction(a.title, b.title):
                        rel = self.add_relation(
                            a.id,
                            b.id,
                            BeliefRelationType.COMPETES,
                            strength=0.7,
                            description=f"Same domain ({a.domain.value}) — competing",
                        )
                        if rel:
                            added += 1
                    else:
                        rel = self.add_relation(
                            a.id,
                            b.id,
                            BeliefRelationType.SUPPORTS,
                            strength=0.55,
                            description=f"Same domain ({a.domain.value}) — aligned",
                        )
                        if rel:
                            added += 1
                    continue

                # CONTRADICTS
                if _opposite_direction(a.title, b.title):
                    adj = DOMAIN_ADJACENCY.get(a.domain, {}).get(b.domain, 0)
                    if adj >= 0.4:
                        rel = self.add_relation(
                            a.id,
                            b.id,
                            BeliefRelationType.CONTRADICTS,
                            strength=0.5 + adj * 0.3,
                        )
                        if rel:
                            added += 1
                    continue

                # EXPLAINS
                is_expl, reason = _has_causal_link(a, b)
                if is_expl:
                    rel = self.add_relation(
                        a.id, b.id, BeliefRelationType.EXPLAINS, strength=0.6, description=reason
                    )
                    if rel:
                        added += 1
                    continue
                is_expl, reason = _has_causal_link(b, a)
                if is_expl:
                    rel = self.add_relation(
                        b.id, a.id, BeliefRelationType.EXPLAINS, strength=0.6, description=reason
                    )
                    if rel:
                        added += 1
                    continue

                # SUPPORTS via keywords
                tokens_a = _tokenize_title(a.title)
                tokens_b = _tokenize_title(b.title)
                overlap = tokens_a & tokens_b
                if len(overlap) >= 2:
                    rel = self.add_relation(
                        a.id,
                        b.id,
                        BeliefRelationType.SUPPORTS,
                        strength=0.35 + min(len(overlap) * 0.1, 0.3),
                    )
                    if rel:
                        added += 1

        logger.info(
            "belief_graph_auto_v32 | %d new relations discovered (%d beliefs)",
            added,
            len(belief_list),
        )
        return added

    # ── Query Methods ─────────────────────────────────────────────────

    def get_connected(self, belief_id: str) -> list[ResearchBelief]:
        """Get all beliefs directly connected to this one."""
        connected = set()
        for r in self.relations:
            if r.source_id == belief_id:
                connected.add(r.target_id)
            elif r.target_id == belief_id:
                connected.add(r.source_id)
        return [self.beliefs[bid] for bid in connected if bid in self.beliefs]

    def get_relations_for(self, belief_id: str) -> list[BeliefRelation]:
        """Get all relations involving this belief."""
        return [r for r in self.relations if r.source_id == belief_id or r.target_id == belief_id]

    def get_relations_by_type(
        self, belief_id: str, relation_type: BeliefRelationType
    ) -> list[BeliefRelation]:
        """Get relations of a specific type involving this belief."""
        return [
            r
            for r in self.relations
            if (r.source_id == belief_id or r.target_id == belief_id)
            and r.relation_type == relation_type
        ]

    def get_support_chain(self, belief_id: str, depth: int = 2) -> list[list[ResearchBelief]]:
        """Get transitive support chain for a belief up to given depth."""
        chains: list[list[ResearchBelief]] = []
        visited = {belief_id}
        current = [belief_id]

        for _ in range(depth):
            next_level = []
            chain_beliefs = []
            for bid in current:
                for r in self.relations:
                    if r.relation_type == BeliefRelationType.SUPPORTS:
                        if r.source_id == bid and r.target_id not in visited:
                            next_level.append(r.target_id)
                            visited.add(r.target_id)
                            if r.target_id in self.beliefs:
                                chain_beliefs.append(self.beliefs[r.target_id])
                        elif r.target_id == bid and r.source_id not in visited:
                            next_level.append(r.source_id)
                            visited.add(r.source_id)
                            if r.source_id in self.beliefs:
                                chain_beliefs.append(self.beliefs[r.source_id])
            if chain_beliefs:
                chains.append(chain_beliefs)
            current = next_level

        return chains

    def find_contradictions(self) -> list[tuple[ResearchBelief, ResearchBelief, BeliefRelation]]:
        """Find all contradicting belief pairs."""
        results = []
        for r in self.relations:
            if r.relation_type == BeliefRelationType.CONTRADICTS:
                a = self.beliefs.get(r.source_id)
                b = self.beliefs.get(r.target_id)
                if a and b:
                    results.append((a, b, r))
        return results

    def find_competition_clusters(self) -> list[list[ResearchBelief]]:
        """V3.2: Find clusters of competing beliefs.

        Returns groups of beliefs that all compete with each other.
        """
        # Build competition adjacency
        comp: dict[str, set[str]] = {bid: set() for bid in self.beliefs}
        for r in self.relations:
            if r.relation_type == BeliefRelationType.COMPETES:
                comp.setdefault(r.source_id, set()).add(r.target_id)
                comp.setdefault(r.target_id, set()).add(r.source_id)

        # Find connected components (simple, not full clustering)
        visited: set[str] = set()
        clusters: list[list[ResearchBelief]] = []

        for bid in self.beliefs:
            if bid in visited or not comp.get(bid):
                continue
            # BFS to find cluster
            queue = [bid]
            cluster_ids: set[str] = set()
            while queue:
                current = queue.pop()
                if current in cluster_ids:
                    continue
                cluster_ids.add(current)
                visited.add(current)
                for neighbor in comp.get(current, set()):
                    if neighbor not in cluster_ids:
                        queue.append(neighbor)
            if len(cluster_ids) >= 2:
                clusters.append([self.beliefs[cid] for cid in cluster_ids if cid in self.beliefs])

        return clusters

    def get_graph_stats(self) -> dict:
        """V3.2: Get graph statistics."""
        rel_counts = {}
        for rt in BeliefRelationType:
            rel_counts[rt.value] = sum(1 for r in self.relations if r.relation_type == rt)

        return {
            "belief_count": len(self.beliefs),
            "relation_count": len(self.relations),
            "relations_by_type": rel_counts,
            "avg_relations_per_belief": (
                len(self.relations) / len(self.beliefs) if self.beliefs else 0
            ),
            "competition_clusters": len(self.find_competition_clusters()),
            "contradiction_pairs": len(self.find_contradictions()),
        }

    # ── Serialization ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "belief_count": len(self.beliefs),
            "relation_count": len(self.relations),
            "beliefs": {bid: b.to_dict() for bid, b in self.beliefs.items()},
            "relations": [
                {
                    "source_id": r.source_id[:8],
                    "target_id": r.target_id[:8],
                    "type": r.relation_type.value,
                    "strength": round(r.strength, 3),
                    "description": r.description,
                }
                for r in self.relations
            ],
            "stats": self.get_graph_stats(),
        }
