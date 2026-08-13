"""TemplateMatcher — maps narratives to belief templates."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.research.beliefs.schemas import BeliefDomain
from src.research.narrative.schemas import Narrative
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BeliefTemplate:
    narrative_pattern: str
    belief_title: str
    belief_description: str
    domain: BeliefDomain
    base_confidence: float = 0.5
    affected_assets: list[str] = field(default_factory=list)


_DEFAULT_TEMPLATES: list[BeliefTemplate] = [
    BeliefTemplate(
        "Liquidity Tightening",
        "Liquidity Is Tightening",
        "Global liquidity contracting due to USD strength and rising real yields.",
        BeliefDomain.LIQUIDITY,
        0.75,
        ["SP500", "Nasdaq", "EM", "Gold"],
    ),
    BeliefTemplate(
        "Liquidity Easing",
        "Liquidity Is Easing",
        "Financial conditions loosening: USD weakening, liquidity expanding.",
        BeliefDomain.LIQUIDITY,
        0.70,
        ["SP500", "Nasdaq", "EM", "HYG"],
    ),
    BeliefTemplate(
        "Higher for Longer",
        "Rates Will Stay Higher for Longer",
        "Fed maintaining restrictive policy for extended period.",
        BeliefDomain.POLICY,
        0.70,
        ["SP500", "Nasdaq", "Bonds", "DXY"],
    ),
    BeliefTemplate(
        "Fed Pivot",
        "Fed Will Pivot to Easing",
        "Fed preparing rate cuts as inflation cools.",
        BeliefDomain.POLICY,
        0.60,
        ["SP500", "Nasdaq", "Bonds", "Gold"],
    ),
    BeliefTemplate(
        "Soft Landing",
        "Economy Will Achieve Soft Landing",
        "Gradual slowdown without recession, inflation normalizing.",
        BeliefDomain.GROWTH,
        0.65,
        ["SP500", "Russell", "HYG", "Copper"],
    ),
    BeliefTemplate(
        "Growth Scare",
        "Growth Is Deteriorating",
        "Growth indicators rolling over; recession risk rising.",
        BeliefDomain.GROWTH,
        0.80,
        ["SP500", "Russell", "Copper", "Oil"],
    ),
    BeliefTemplate(
        "Growth Resilience",
        "Growth Remains Resilient",
        "Despite headwinds, growth and consumer spending hold strong.",
        BeliefDomain.GROWTH,
        0.65,
        ["SP500", "Russell", "Copper"],
    ),
    BeliefTemplate(
        "Inflation",
        "Inflation Is Reaccelerating",
        "Inflation rising again: commodities, wages, shelter stay elevated.",
        BeliefDomain.INFLATION,
        0.75,
        ["Gold", "Oil", "TIPS", "US10Y"],
    ),
    BeliefTemplate(
        "Disinflation",
        "Disinflation Trend Continues",
        "Inflation cooling across categories toward target.",
        BeliefDomain.INFLATION,
        0.70,
        ["Nasdaq", "Bonds", "SP500"],
    ),
    BeliefTemplate(
        "Risk-On",
        "Risk Appetite Is Surging",
        "Broad bullish sentiment: VIX low, spreads tight.",
        BeliefDomain.RISK,
        0.70,
        ["SP500", "Nasdaq", "Russell", "HYG"],
    ),
    BeliefTemplate(
        "Risk-Off",
        "Risk Appetite Has Collapsed",
        "Flight to safety: VIX spiking, safe-haven demand surging.",
        BeliefDomain.RISK,
        0.80,
        ["Gold", "US10Y", "VIX", "USD"],
    ),
    BeliefTemplate(
        "Dollar Strength",
        "USD Is Strengthening",
        "Broad USD strength: rate differentials favor USD.",
        BeliefDomain.DOLLAR,
        0.75,
        ["DXY", "EM", "Gold", "Commodities"],
    ),
    BeliefTemplate(
        "Dollar Weakness",
        "USD Is Weakening",
        "USD weakening: rate differentials narrowing, capital to EM.",
        BeliefDomain.DOLLAR,
        0.70,
        ["EM", "Gold", "Copper", "Oil"],
    ),
    BeliefTemplate(
        "Credit",
        "Credit Conditions Are Shifting",
        "Credit markets signaling change in financial conditions.",
        BeliefDomain.CREDIT,
        0.70,
        ["HYG", "LQD", "SP500"],
    ),
    BeliefTemplate(
        "AI Capex",
        "AI Investment Cycle Remains Strong",
        "AI capex robust: semiconductor demand high, supply chain healthy.",
        BeliefDomain.AI_CAPEX,
        0.70,
        ["NVDA", "SMH", "ASML", "Nasdaq"],
    ),
    BeliefTemplate(
        "Stagflation",
        "Stagflation Risk Is Rising",
        "Inflation rising while growth slowing — policy dilemma.",
        BeliefDomain.GROWTH,
        0.85,
        ["Gold", "Oil", "TIPS", "SP500"],
    ),
    BeliefTemplate(
        "Goldilocks",
        "Goldilocks Environment",
        "Perfect macro: growth solid, inflation moderate, policy neutral.",
        BeliefDomain.GROWTH,
        0.75,
        ["SP500", "Nasdaq", "Russell", "HYG"],
    ),
]


class TemplateMatcher:
    """Match detected narratives to belief templates and create beliefs."""

    def __init__(self) -> None:
        self._templates = list(_DEFAULT_TEMPLATES)

    def match(self, narratives: list[Narrative]) -> list[dict]:
        """Match narratives to belief templates.

        Every active narrative generates at least one belief.

        Returns:
            List of dicts with template info and match score for belief creation.
        """
        matches = []
        for narrative in narratives:
            if not narrative.is_active:
                continue

            # Ensure composite score is computed
            if narrative.composite_score == 0.0:
                narrative.compute_composite_score()

            # ── Phase 1: Exact substring match ────────────────────────
            title_lower = narrative.title.lower()
            desc_lower = (narrative.description or "").lower()
            matched = False
            for template in self._templates:
                pattern_lower = template.narrative_pattern.lower()
                if pattern_lower in title_lower or pattern_lower in desc_lower:
                    composite = max(narrative.composite_score, 0.15)
                    match_score = min(1.0, template.base_confidence * composite * 1.2)
                    matches.append(
                        {
                            "narrative_id": narrative.id,
                            "narrative_title": narrative.title,
                            "belief_title": template.belief_title,
                            "belief_description": template.belief_description,
                            "domain": template.domain,
                            "base_confidence": template.base_confidence,
                            "match_score": match_score,
                            "affected_assets": template.affected_assets,
                            "source_narrative": narrative.title,
                        }
                    )
                    matched = True

            # ── Phase 2: Keyword-based fallback ───────────────────────
            if not matched:
                match = self._match_by_keywords(narrative)
                if match:
                    matches.append(match)
                    matched = True

            # ── Phase 3: Category-based generic belief ────────────────
            if not matched:
                generic = self._create_generic_match(narrative)
                if generic:
                    matches.append(generic)

        logger.info(
            "template_matcher | %d matches from %d narratives", len(matches), len(narratives)
        )
        return matches

    def _match_by_keywords(self, narrative: Narrative) -> dict | None:
        """Try keyword-based matching when exact template match fails."""
        title = narrative.title.lower()
        desc = (narrative.description or "").lower()
        text = title + " " + desc

        keyword_map: dict[tuple[str, ...], BeliefTemplate] = {}
        for t in self._templates:
            words = tuple(w.lower() for w in t.narrative_pattern.lower().split() if len(w) > 2)
            keyword_map[words] = t

        best_score = 0
        best_template = None
        for keywords, template in keyword_map.items():
            hit_count = sum(1 for kw in keywords if kw in text)
            if len(keywords) > 0:
                ratio = hit_count / len(keywords)
                if ratio > best_score and ratio >= 0.5:
                    best_score = ratio
                    best_template = template

        if best_template:
            composite = max(narrative.composite_score, 0.15)
            return {
                "narrative_id": narrative.id,
                "narrative_title": narrative.title,
                "belief_title": best_template.belief_title,
                "belief_description": best_template.belief_description,
                "domain": best_template.domain,
                "base_confidence": best_template.base_confidence * best_score,
                "match_score": min(1.0, best_template.base_confidence * composite * best_score),
                "affected_assets": best_template.affected_assets,
                "source_narrative": narrative.title,
            }
        return None

    @staticmethod
    def _create_generic_match(narrative: Narrative) -> dict | None:
        """Create a generic belief when no template matches at all.

        Maps narrative category to a belief domain and generates a
        belief that captures the narrative's core message.
        """
        category_to_domain = {
            "monetary": BeliefDomain.LIQUIDITY,
            "policy": BeliefDomain.POLICY,
            "fiscal": BeliefDomain.POLICY,
            "growth": BeliefDomain.GROWTH,
            "inflation": BeliefDomain.INFLATION,
            "credit": BeliefDomain.CREDIT,
            "risk": BeliefDomain.RISK,
            "geopolitical": BeliefDomain.RISK,
            "sectoral": BeliefDomain.AI_CAPEX,
            "technical": BeliefDomain.GROWTH,
        }
        cat = (
            narrative.category.value
            if hasattr(narrative.category, "value")
            else str(narrative.category)
        ).lower()
        domain = category_to_domain.get(cat, BeliefDomain.GROWTH)

        composite = max(narrative.composite_score, 0.10)
        return {
            "narrative_id": narrative.id,
            "narrative_title": narrative.title,
            "belief_title": narrative.title or "Market Narrative Detected",
            "belief_description": narrative.description or "Narrative-derived belief.",
            "domain": domain,
            "base_confidence": max(0.40, narrative.confidence),
            "match_score": composite,
            "affected_assets": narrative.affected_assets or [],
            "source_narrative": narrative.title or "narrative-detected",
        }

    def get_templates_for_domain(self, domain: BeliefDomain) -> list[BeliefTemplate]:
        return [t for t in self._templates if t.domain == domain]
