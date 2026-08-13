"""NarrativeGraph — builds and maintains relationship graphs between narratives.

Narrative relationships:
    SUPPORTS    → A reinforces B
    CONTRADICTS → A opposes B
    DEPENDS_ON  → A requires B to be true
    CAUSES      → A leads to B
    COMPETES    → A and B are competing explanations
"""

from __future__ import annotations

from src.research.narrative.schemas import (
    Narrative,
    NarrativeCategory,
    NarrativeGraph,
    NarrativeRelation,
    NarrativeRelationType,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Relationship Patterns ────────────────────────────────────────────────────

# Pre-defined relationship patterns between narrative categories/directions
_RELATIONSHIP_RULES: list[dict] = [
    # Dollar strength → liquidity tightening
    {
        "source_pattern": "Dollar Strength",
        "target_pattern": "Liquidity",
        "type": NarrativeRelationType.CAUSES,
        "strength": 0.85,
        "desc": "Dollar strength causes global liquidity tightening",
    },
    # Liquidity tightening → growth scare
    {
        "source_pattern": "Liquidity",
        "target_pattern": "Growth Scare",
        "type": NarrativeRelationType.CAUSES,
        "strength": 0.70,
        "desc": "Liquidity tightening can lead to growth scares",
    },
    # Liquidity easing → risk-on
    {
        "source_pattern": "Liquidity Easing",
        "target_pattern": "Risk-On",
        "type": NarrativeRelationType.SUPPORTS,
        "strength": 0.80,
        "desc": "Liquidity easing supports risk-on sentiment",
    },
    # Higher for longer → dollar strength
    {
        "source_pattern": "Higher for Longer",
        "target_pattern": "Dollar",
        "type": NarrativeRelationType.SUPPORTS,
        "strength": 0.75,
        "desc": "Higher rates support USD strength",
    },
    # Higher for longer → contradicts Soft Landing
    {
        "source_pattern": "Higher for Longer",
        "target_pattern": "Soft Landing",
        "type": NarrativeRelationType.CONTRADICTS,
        "strength": 0.65,
        "desc": "Prolonged tight policy makes soft landing harder",
    },
    # Fed pivot → supports Soft Landing
    {
        "source_pattern": "Fed Pivot",
        "target_pattern": "Soft Landing",
        "type": NarrativeRelationType.SUPPORTS,
        "strength": 0.80,
        "desc": "Fed pivot enables soft landing scenario",
    },
    # AI Capex → supports Growth Resilience
    {
        "source_pattern": "AI Capex",
        "target_pattern": "Growth",
        "type": NarrativeRelationType.SUPPORTS,
        "strength": 0.60,
        "desc": "AI investment supports growth resilience",
    },
    # Inflation cooling → supports Fed pivot
    {
        "source_pattern": "Disinflation",
        "target_pattern": "Fed Pivot",
        "type": NarrativeRelationType.CAUSES,
        "strength": 0.85,
        "desc": "Disinflation trend enables Fed pivot",
    },
    # Inflation rising → contradicts Fed pivot
    {
        "source_pattern": "Inflation",
        "target_pattern": "Fed Pivot",
        "type": NarrativeRelationType.CONTRADICTS,
        "strength": 0.80,
        "desc": "Rising inflation prevents Fed pivot",
    },
    # Credit stress → contradicts risk-on
    {
        "source_pattern": "Credit",
        "target_pattern": "Risk-On",
        "type": NarrativeRelationType.CONTRADICTS,
        "strength": 0.75,
        "desc": "Credit stress undermines risk-on sentiment",
    },
    # Stagflation → contradicts Goldilocks
    {
        "source_pattern": "Stagflation",
        "target_pattern": "Goldilocks",
        "type": NarrativeRelationType.CONTRADICTS,
        "strength": 0.95,
        "desc": "Stagflation and Goldilocks are opposites",
    },
    # Risk-off → supports Dollar Strength
    {
        "source_pattern": "Risk-Off",
        "target_pattern": "Dollar",
        "type": NarrativeRelationType.SUPPORTS,
        "strength": 0.70,
        "desc": "Flight to safety supports USD",
    },
    # Risk-off → supports Gold (safe haven)
    {
        "source_pattern": "Risk-Off",
        "target_pattern": "Gold",
        "type": NarrativeRelationType.SUPPORTS,
        "strength": 0.65,
        "desc": "Risk-off drives safe-haven gold demand",
    },
    # Labor market strength → supports Growth Resilience
    {
        "source_pattern": "Labor",
        "target_pattern": "Growth",
        "type": NarrativeRelationType.SUPPORTS,
        "strength": 0.75,
        "desc": "Strong labor market supports growth",
    },
    # AI Capex Peak → Growth Scare (if AI-dependent)
    {
        "source_pattern": "AI Capex Peak",
        "target_pattern": "Growth Scare",
        "type": NarrativeRelationType.CAUSES,
        "strength": 0.55,
        "desc": "AI investment pullback could trigger growth concerns",
    },
]


class NarrativeGraphBuilder:
    """Builds and maintains the narrative relationship graph.

    Usage:
        builder = NarrativeGraphBuilder()
        graph = builder.build(narratives)
        # Graph now has all relationships between narratives
    """

    def __init__(self) -> None:
        self._rules = list(_RELATIONSHIP_RULES)

    def build(self, narratives: list[Narrative]) -> NarrativeGraph:
        """Build a complete narrative graph with all detected relationships.

        Detects relationships from:
        1. Pre-defined pattern matching rules
        2. Category-based inference
        3. Same-category competition
        4. Opposite-direction contradictions
        """
        graph = NarrativeGraph(narratives=narratives)

        # ── Rule-based relationships ─────────────────────────────────────
        for rule in self._rules:
            sources = self._find_matching(narratives, rule["source_pattern"])
            targets = self._find_matching(narratives, rule["target_pattern"])
            for src in sources:
                for tgt in targets:
                    if src.id != tgt.id and not self._relation_exists(graph, src.id, tgt.id):
                        graph.relations.append(
                            NarrativeRelation(
                                source_id=src.id,
                                target_id=tgt.id,
                                relation_type=rule["type"],
                                strength=rule["strength"],
                                description=rule["desc"],
                            )
                        )

        # ── Same-category competition ────────────────────────────────────
        by_category: dict[NarrativeCategory, list[Narrative]] = {}
        for n in narratives:
            by_category.setdefault(n.category, []).append(n)

        for cat_narratives in by_category.values():
            if len(cat_narratives) >= 2:
                # Narratives in same category with opposite directions compete
                for i, n1 in enumerate(cat_narratives):
                    for n2 in cat_narratives[i + 1 :]:
                        if not self._relation_exists(graph, n1.id, n2.id):
                            # Check if they have conflicting supporting models
                            if self._are_competing(n1, n2):
                                graph.relations.append(
                                    NarrativeRelation(
                                        source_id=n1.id,
                                        target_id=n2.id,
                                        relation_type=NarrativeRelationType.COMPETES,
                                        strength=0.60,
                                        description=f"Competing narratives in {n1.category.value}",
                                    )
                                )

        # ── Cross-category contradictions ────────────────────────────────
        # Opposing directions across linked categories (e.g., Growth↑ but Credit↓)
        contradiction_pairs = [
            (NarrativeCategory.GROWTH, NarrativeCategory.CREDIT),
            (NarrativeCategory.INFLATION, NarrativeCategory.MONETARY),
            (NarrativeCategory.RISK, NarrativeCategory.GROWTH),
            (NarrativeCategory.MONETARY, NarrativeCategory.CREDIT),
        ]

        for cat_a, cat_b in contradiction_pairs:
            ns_a = by_category.get(cat_a, [])
            ns_b = by_category.get(cat_b, [])
            for a in ns_a:
                for b in ns_b:
                    if not self._relation_exists(graph, a.id, b.id):
                        # Check opposite directions via supporting models
                        if self._have_opposite_directions(a, b):
                            graph.relations.append(
                                NarrativeRelation(
                                    source_id=a.id,
                                    target_id=b.id,
                                    relation_type=NarrativeRelationType.CONTRADICTS,
                                    strength=0.50,
                                    description=f"{cat_a.value} vs {cat_b.value} divergence",
                                )
                            )

        logger.info(
            "narrative_graph_built | narratives=%d relations=%d",
            len(graph.narratives),
            len(graph.relations),
        )
        return graph

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _find_matching(
        narratives: list[Narrative],
        pattern: str,
    ) -> list[Narrative]:
        """Find narratives whose title contains the pattern (case-insensitive)."""
        pattern_lower = pattern.lower()
        return [n for n in narratives if pattern_lower in n.title.lower()]

    @staticmethod
    def _relation_exists(
        graph: NarrativeGraph,
        source_id: str,
        target_id: str,
    ) -> bool:
        """Check if a relation already exists between these two narratives."""
        for r in graph.relations:
            if r.source_id == source_id and r.target_id == target_id:
                return True
        return False

    @staticmethod
    def _are_competing(a: Narrative, b: Narrative) -> bool:
        """Check if two narratives are competing explanations."""
        # Same category, both have high confidence → compete
        if a.category == b.category and a.confidence > 0.6 and b.confidence > 0.6:
            return True
        # Different supporting models → compete
        a_models = set(a.supporting_models)
        b_models = set(b.supporting_models)
        overlap = a_models & b_models
        if a_models and b_models and not overlap:
            return True
        return False

    @staticmethod
    def _have_opposite_directions(a: Narrative, b: Narrative) -> bool:
        """Check if two narratives imply opposite market directions."""
        bullish = {
            "easing",
            "expansion",
            "cooling",
            "dovish",
            "strengthening",
            "growth",
            "risk_on",
            "soft_landing",
            "goldilocks",
        }
        bearish = {
            "tightening",
            "contraction",
            "rising",
            "hawkish",
            "weakening",
            "recession",
            "risk_off",
            "stagflation",
            "scare",
            "stress",
        }

        title_a = a.title.lower()
        title_b = b.title.lower()

        a_bullish = any(w in title_a for w in bullish)
        a_bearish = any(w in title_a for w in bearish)
        b_bullish = any(w in title_b for w in bullish)
        b_bearish = any(w in title_b for w in bearish)

        # If one is bullish and the other is bearish → opposite
        return (a_bullish and b_bearish) or (a_bearish and b_bullish)
