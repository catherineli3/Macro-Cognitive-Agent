"""Research Judgment Engine (V3.2).

Transforms Agent from "reading the world" (pattern recognition) to
"explaining the world" (reasoned judgment with falsifiability).

Core Philosophy:
    A Senior Macro Researcher does not just say "X is happening."
    They say:
        1. "I believe X" — conviction with ownership
        2. "Because evidence A/B/C" — transparent reasoning
        3. "Confidence: 72%" — calibrated uncertainty
        4. "If Y happens, I'm wrong" — falsifiability

Output Format (per conclusion):
    ┌─────────────────────────────────────────┐
    │ Research Judgment                       │
    ├─────────────────────────────────────────┤
    │ Belief: I believe inflation is peaking   │
    │ Why: CPI 3-month trend declining,        │
    │      shelter costs lagging, ISM prices   │
    │ Confidence: 72%                          │
    │ Changes if: CPI MoM prints >0.3% or      │
    │             breakevens break above 2.5%  │
    └─────────────────────────────────────────┘
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.research.beliefs.belief_graph import BeliefGraph
from src.research.beliefs.schemas import BeliefDomain, BeliefRelationType, ResearchBelief
from src.research.narrative.schemas import NarrativeObject
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Falsification condition templates by domain ───────────────────────

FALSIFICATION_TEMPLATES: dict[BeliefDomain, dict[str, list[str]]] = {
    BeliefDomain.POLICY: {
        "hawkish": [
            "Fed signals rate cut in next FOMC",
            "CPI prints below 2.5% YoY for 2 consecutive months",
            "Labor market shows meaningful deterioration (UE rate +0.5%)",
            "DXY drops below 100",
        ],
        "dovish": [
            "Fed hikes unexpectedly or signals further tightening",
            "CPI re-accelerates above 3.5% YoY",
            "Wage growth exceeds 4.5% YoY",
            "Financial conditions ease too much (FCI < -1.0)",
        ],
        "neutral": [
            "Clear directional shift in Fed communication",
            "Inflation or employment surprises >2σ",
        ],
    },
    BeliefDomain.INFLATION: {
        "elevated": [
            "Core PCE prints below 2.5% for 2 consecutive months",
            "Shelter/OER shows sustained decline in CPI data",
            "Breakevens decline below 2.2%",
            "ISM prices paid drops below 45",
        ],
        "moderating": [
            "Headline CPI re-accelerates above 0.3% MoM",
            "Wage-price spiral evidence in employment data",
            "Commodity prices surge 20%+ in one quarter",
            "5Y5Y forward breakeven exceeds 2.8%",
        ],
        "neutral": [
            "Sustained deviation from trend in CPI/PCE prints",
        ],
    },
    BeliefDomain.GROWTH: {
        "bullish": [
            "ISM Manufacturing drops below 45",
            "Initial jobless claims exceed 300k for 2+ weeks",
            "2s10s curve deepens inversion beyond -100bp",
            "Corporate earnings guidance turns broadly negative",
        ],
        "bearish": [
            "ISM Manufacturing rebounds above 52",
            "Payrolls print >250k for 2+ consecutive months",
            "Leading indicators (Conference Board LEI) turn positive",
            "Credit spreads tighten below 300bp",
        ],
        "neutral": [
            "Clear recession or expansion signal from multiple coincident indicators",
        ],
    },
    BeliefDomain.LIQUIDITY: {
        "tight": [
            "SOFR-Fed Funds spread normalizes below 5bp",
            "Fed injects liquidity (repo operations expand)",
            "Credit spreads tighten meaningfully",
            "VIX declines below 15",
        ],
        "ample": [
            "Repo rates spike >50bp above IOER",
            "Credit spreads widen >50bp in one week",
            "Bank reserves drop significantly",
            "VIX spikes above 28",
        ],
        "neutral": [
            "Liquidity conditions clearly shift to extreme",
        ],
    },
    BeliefDomain.RISK: {
        "risk_on": [
            "VIX spikes above 30",
            "Credit spreads widen >50bp in one week",
            "Correlation across assets jumps (all-correlated selloff)",
            "Safe-haven flows into UST/JPY/CHF accelerate",
        ],
        "risk_off": [
            "VIX declines below 14",
            "Credit spreads tighten to cycle lows",
            "Put/call ratio drops below 0.5",
            "Cross-asset volatility collapses",
        ],
        "neutral": [
            "Clear risk-on or risk-off signals across multiple assets",
        ],
    },
    BeliefDomain.CREDIT: {
        "stress": [
            "IG spreads tighten below 80bp",
            "HY spreads tighten below 300bp",
            "Default rate expectations decline in CDS market",
            "Primary issuance market re-opens strongly",
        ],
        "benign": [
            "IG spreads widen above 150bp",
            "HY spreads widen above 500bp",
            "New issue market freezes (zero primary deals in a week)",
            "Distressed ratio rises above 8%",
        ],
        "neutral": [
            "Spreads break recent range by more than 20% either direction",
        ],
    },
    BeliefDomain.DOLLAR: {
        "strengthening": [
            "DXY drops 5% in one month",
            "Fed signals rate cut cycle begins",
            "EM FX stabilizes broadly",
        ],
        "weakening": [
            "DXY rises above 108",
            "Fed unexpectedly hikes",
            "Global risk-off with flight to USD",
        ],
        "neutral": [
            "DXY breaks recent range by >3% either direction",
        ],
    },
}


def _infer_direction_from_belief(belief: ResearchBelief) -> str:
    """Infer directional signal from a belief's title and domain."""
    title = belief.title.lower()

    directional_words = {
        "hawkish": [
            "hawkish",
            "hawk",
            "tighten",
            "tightening",
            "hike",
            "restrictive",
            "aggressive",
            "strong",
        ],
        "dovish": [
            "dovish",
            "dove",
            "easing",
            "ease",
            "cut",
            "accommodative",
            "loose",
            "pivot",
            "pause",
        ],
        "elevated": [
            "elevated",
            "rising",
            "high",
            "surge",
            "upside",
            "sticky",
            "persistent",
            "reaccelerate",
            "shock",
        ],
        "moderating": [
            "moderating",
            "declining",
            "cooling",
            "falling",
            "disinflation",
            "peaking",
            "transitory",
        ],
        "bullish": [
            "bullish",
            "acceleration",
            "expanding",
            "boom",
            "growth",
            "recovery",
            "optimism",
            "upside",
        ],
        "bearish": [
            "bearish",
            "slowing",
            "slowdown",
            "contraction",
            "recession",
            "declining",
            "deteriorating",
            "downside",
        ],
        "risk_on": ["risk_on", "risk on", "appetite", "complacency", "leverage"],
        "risk_off": ["risk_off", "risk off", "aversion", "flight", "deleverage", "de-risk"],
        "tight": ["tight", "tightening", "stress", "drain", "constrain", "squeeze"],
        "ample": ["ample", "abundant", "easy", "loose", "flush", "flood"],
        "stress": ["stress", "distress", "widen", "deterioration", "default"],
        "benign": ["benign", "tight", "narrow", "healthy", "strong"],
        "rally": ["rally", "surge", "bull", "supercycle", "bid"],
        "decline": ["decline", "bear", "selloff", "collapse", "drop"],
    }

    for direction, keywords in directional_words.items():
        for kw in keywords:
            if kw in title:
                return direction

    # Fallback to domain-based neutral
    domain_map = {
        BeliefDomain.POLICY: "neutral",
        BeliefDomain.INFLATION: "neutral",
        BeliefDomain.GROWTH: "neutral",
        BeliefDomain.LIQUIDITY: "neutral",
        BeliefDomain.RISK: "neutral",
        BeliefDomain.CREDIT: "neutral",
        BeliefDomain.DOLLAR: "neutral",
        BeliefDomain.AI_CAPEX: "neutral",
        BeliefDomain.EMPLOYMENT: "neutral",
    }
    return domain_map.get(belief.domain, "neutral")


@dataclass
class ResearchJudgment:
    """A single research conclusion — what a Senior Researcher would write.

    Each judgment is OWNABLE ("I believe"), REASONED ("because"), CALIBRATED
    ("72% confidence"), and FALSIFIABLE ("if X, I'm wrong").
    """

    id: str = field(default_factory=lambda: uuid4().hex[:8])
    belief_title: str = ""
    belief_id: str = ""

    # ── Core Judgment ───────────────────────────────────
    conviction_statement: str = ""
    """Formatted: 'I believe [belief_title]'"""

    reasoning_chain: list[str] = field(default_factory=list)
    """Evidence chain explaining WHY this belief is held."""

    confidence: float = 0.5  # 0-1

    # ── Falsifiability (V3.2 key) ────────────────────────
    falsification_conditions: list[str] = field(default_factory=list)
    """Specific, observable conditions that would invalidate this belief.

    e.g. "CPI MoM prints >0.3% for 2 consecutive months"
         "DXY breaks above 108"
         "Fed explicitly signals no cut in next SEP"
    """

    # ── Graph Context ────────────────────────────────────
    competing_beliefs: list[str] = field(default_factory=list)
    supporting_beliefs: list[str] = field(default_factory=list)
    contradicting_beliefs: list[str] = field(default_factory=list)

    # ── Meta ─────────────────────────────────────────────
    domain: str = ""
    source_narrative_titles: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def confidence_label(self) -> str:
        """Human-readable confidence label."""
        if self.confidence >= 0.8:
            return "High Conviction"
        elif self.confidence >= 0.65:
            return "Confident"
        elif self.confidence >= 0.5:
            return "Moderate"
        else:
            return "Speculative"

    @property
    def is_falsifiable(self) -> bool:
        """Has explicit falsification conditions (V3.2 requirement)."""
        return len(self.falsification_conditions) > 0

    @property
    def has_competition(self) -> bool:
        """Has competing beliefs (V3.2 requirement)."""
        return len(self.competing_beliefs) > 0

    def format_conclusion(self) -> str:
        """Format as senior researcher memo output."""
        lines = [
            "=" * 60,
            f"RESEARCH JUDGMENT  |  {self.domain.upper()}  |  {self.confidence_label}",
            "=" * 60,
            "",
            f"  I believe: {self.conviction_statement}",
            "",
            "  Why:",
        ]
        for i, reason in enumerate(self.reasoning_chain, 1):
            lines.append(f"    {i}. {reason}")

        lines.append("")
        lines.append(f"  Confidence: {self.confidence:.0%}")

        if self.competing_beliefs:
            lines.append("")
            lines.append("  Competing views:")
            for comp in self.competing_beliefs:
                lines.append(f"    ⚡ {comp}")

        if self.falsification_conditions:
            lines.append("")
            lines.append("  What would change my mind:")
            for cond in self.falsification_conditions:
                lines.append(f"    ✗ If {cond}")

        if self.contradicting_beliefs:
            lines.append("")
            lines.append("  Active contradictions to monitor:")
            for c in self.contradicting_beliefs:
                lines.append(f"    ⚠ {c}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "belief_title": self.belief_title,
            "belief_id": self.belief_id,
            "conviction_statement": self.conviction_statement,
            "reasoning_chain": self.reasoning_chain,
            "confidence": self.confidence,
            "confidence_label": self.confidence_label,
            "falsification_conditions": self.falsification_conditions,
            "is_falsifiable": self.is_falsifiable,
            "competing_beliefs": self.competing_beliefs,
            "supporting_beliefs": self.supporting_beliefs,
            "contradicting_beliefs": self.contradicting_beliefs,
            "domain": self.domain,
            "source_narrative_titles": self.source_narrative_titles,
            "has_competition": self.has_competition,
        }


@dataclass
class JudgmentOutput:
    """Collection of research judgments from a single cycle."""

    judgments: list[ResearchJudgment] = field(default_factory=list)
    summary: str = ""
    macro_stance: str = ""  # Net macro stance: hawkish/dovish/neutral
    highest_conviction: ResearchJudgment | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def count(self) -> int:
        return len(self.judgments)

    @property
    def falsifiable_count(self) -> int:
        return sum(1 for j in self.judgments if j.is_falsifiable)

    @property
    def competition_count(self) -> int:
        return sum(1 for j in self.judgments if j.has_competition)

    @property
    def avg_confidence(self) -> float:
        if not self.judgments:
            return 0.0
        return sum(j.confidence for j in self.judgments) / len(self.judgments)

    def to_dict(self) -> dict[str, Any]:
        return {
            "judgments": [j.to_dict() for j in self.judgments],
            "count": self.count,
            "falsifiable_count": self.falsifiable_count,
            "competition_count": self.competition_count,
            "avg_confidence": round(self.avg_confidence, 3),
            "summary": self.summary,
            "macro_stance": self.macro_stance,
        }

    def print_all(self) -> str:
        """Print all judgments formatted."""
        parts = [j.format_conclusion() for j in self.judgments]
        return "\n\n".join(parts)


class ResearchJudgmentEngine:
    """V3.2: Produces senior-researcher-grade research judgments.

    Takes beliefs, narratives, and graph context → outputs structured
    ResearchJudgment objects with conviction, reasoning, and falsifiability.
    """

    def __init__(self):
        self._judgment_count = 0

    # ── Main API ─────────────────────────────────────────────────

    def judge(
        self,
        beliefs: list[ResearchBelief],
        graph: BeliefGraph | None = None,
        narrative_objects: list[NarrativeObject] | None = None,
        regime: str = "",
    ) -> JudgmentOutput:
        """Produce research judgments for a set of beliefs.

        Args:
            beliefs: Current research beliefs (from BeliefEngine)
            graph: Active belief graph for relationship context
            narrative_objects: V3.2 narrative objects for evidence chains
            regime: Current market regime

        Returns:
            JudgmentOutput with all research judgments.
        """
        self._judgment_count += 1
        judgments: list[ResearchJudgment] = []

        for belief in beliefs:
            judgment = self._judge_one(belief, graph, narrative_objects, regime)
            judgments.append(judgment)

        # Determine macro stance
        macro_stance = self._assess_macro_stance(judgments)

        # Find highest conviction
        highest = max(judgments, key=lambda j: j.confidence) if judgments else None

        # Build summary
        summary = self._build_summary(judgments, macro_stance)

        output = JudgmentOutput(
            judgments=judgments,
            summary=summary,
            macro_stance=macro_stance,
            highest_conviction=highest,
        )

        logger.info(
            "judgment_engine | %d judgments | stance=%s | avg_confidence=%.0f%% | "
            "falsifiable=%d/%d | competition=%d/%d",
            output.count,
            macro_stance,
            output.avg_confidence * 100,
            output.falsifiable_count,
            output.count,
            output.competition_count,
            output.count,
        )

        return output

    def _judge_one(
        self,
        belief: ResearchBelief,
        graph: BeliefGraph | None = None,
        narrative_objects: list[NarrativeObject] | None = None,
        regime: str = "",
    ) -> ResearchJudgment:
        """Build a ResearchJudgment for a single belief."""

        # 1. Build conviction statement
        conviction = f"{belief.title}"

        # 2. Build reasoning chain
        reasoning = self._build_reasoning(belief, narrative_objects)

        # 3. Get falsification conditions
        falsification = self._get_falsification_conditions(belief)

        # 4. Get competing/supporting/contradicting beliefs from graph
        competing, supporting, contradicting = self._get_graph_context(belief, graph)

        # 5. Get narrative context
        narrative_titles = self._get_narrative_titles(belief, narrative_objects)

        _direction = _infer_direction_from_belief(belief)

        return ResearchJudgment(
            belief_title=belief.title,
            belief_id=belief.id,
            conviction_statement=conviction,
            reasoning_chain=reasoning,
            confidence=belief.confidence,
            falsification_conditions=falsification,
            competing_beliefs=competing,
            supporting_beliefs=supporting,
            contradicting_beliefs=contradicting,
            domain=belief.domain.value,
            source_narrative_titles=narrative_titles,
        )

    # ── Internal Builders ─────────────────────────────────────────

    @staticmethod
    def _build_reasoning(
        belief: ResearchBelief,
        narrative_objects: list[NarrativeObject] | None = None,
    ) -> list[str]:
        """Build evidence-based reasoning chain."""
        reasons: list[str] = []

        # 1. Evidence from belief's evidence items
        for ev in belief.evidence[:5]:
            reasons.append(ev.description[:150])

        # 2. Narrative causal chain if available
        if narrative_objects:
            for n_obj in narrative_objects:
                if n_obj.id in belief.source_narratives or n_obj.title == belief.title:
                    for step in n_obj.causal_chain[:3]:
                        reasons.append(step)
                    for ev in n_obj.supporting_evidence[:2]:
                        reasons.append(f"Supporting: {ev[:120]}")
                    break

        # 3. If no evidence, add generic domain context
        if not reasons:
            reasons.append(f"Macro model indicates {belief.domain.value} significance")
            reasons.append(f"Current confidence: {belief.confidence:.0%}")

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for r in reasons:
            if r not in seen:
                seen.add(r)
                unique.append(r)

        return unique[:8]

    @staticmethod
    def _get_falsification_conditions(belief: ResearchBelief) -> list[str]:
        """Determine what would falsify this belief."""
        direction = _infer_direction_from_belief(belief)
        domain_templates = FALSIFICATION_TEMPLATES.get(belief.domain, {})

        # Try to match by direction
        conditions = domain_templates.get(direction, [])

        # Fallback: use neutral template
        if not conditions:
            conditions = domain_templates.get("neutral", [])

        # Fallback: generic conditions
        if not conditions:
            conditions = [
                f"Counter-evidence from leading {belief.domain.value} indicators",
                f"Sustained reversal in {belief.domain.value} trend",
            ]

        return list(conditions)

    @staticmethod
    def _get_graph_context(
        belief: ResearchBelief,
        graph: BeliefGraph | None = None,
    ) -> tuple[list[str], list[str], list[str]]:
        """Extract belief relationship context from the graph."""
        competing: list[str] = []
        supporting: list[str] = []
        contradicting: list[str] = []

        if graph is None:
            return competing, supporting, contradicting

        for rel in graph.get_relations_for(belief.id):
            other_id = rel.target_id if rel.source_id == belief.id else rel.source_id
            other = graph.beliefs.get(other_id)
            if other is None:
                continue

            if rel.relation_type == BeliefRelationType.COMPETES:
                competing.append(other.title)
            elif rel.relation_type == BeliefRelationType.SUPPORTS:
                supporting.append(other.title)
            elif rel.relation_type == BeliefRelationType.CONTRADICTS:
                contradicting.append(other.title)
            # EXPLAINS also contributes to context but doesn't get its own list

        return competing, supporting, contradicting

    @staticmethod
    def _get_narrative_titles(
        belief: ResearchBelief,
        narrative_objects: list[NarrativeObject] | None = None,
    ) -> list[str]:
        """Get related narrative titles."""
        titles: list[str] = []

        # From belief's own source_narratives
        titles.extend(belief.source_narratives[:3])

        # From narrative objects
        if narrative_objects:
            for n_obj in narrative_objects:
                if n_obj.id in belief.source_narratives:
                    titles.append(n_obj.title)
                    break

        return list(dict.fromkeys(titles))[:5]  # Deduplicate

    @staticmethod
    def _assess_macro_stance(judgments: list[ResearchJudgment]) -> str:
        """Assess net macro stance from judgments."""
        hawkish_signals = 0
        dovish_signals = 0

        hawkish_domains = {"Policy", "Inflation"}
        dovish_keywords = {"dovish", "easing", "moderating", "bearish", "slowdown", "risk_off"}

        for j in judgments:
            if j.domain in hawkish_domains and j.confidence > 0.55:
                hawkish_signals += 1
            title = j.belief_title.lower()
            if any(kw in title for kw in dovish_keywords) and j.confidence > 0.55:
                dovish_signals += 1

        diff = hawkish_signals - dovish_signals
        if diff > 1:
            return "hawkish"
        elif diff < -1:
            return "dovish"
        else:
            return "neutral"

    @staticmethod
    def _build_summary(judgments: list[ResearchJudgment], macro_stance: str) -> str:
        """Build an executive summary of all judgments."""
        if not judgments:
            return "No active research judgments."

        highest = max(judgments, key=lambda j: j.confidence)

        parts = [
            f"Macro Stance: {macro_stance.upper()}",
            f"Active Judgments: {len(judgments)}",
            f"Highest Conviction: '{highest.belief_title}' ({highest.confidence:.0%})",
        ]

        # Add mention of competition if present
        competing_count = sum(1 for j in judgments if j.has_competition)
        if competing_count > 0:
            parts.append(f"Competing Views Present: {competing_count} beliefs have alternatives")

        falsifiable_count = sum(1 for j in judgments if j.is_falsifiable)
        parts.append(f"Falsifiable Judgments: {falsifiable_count}/{len(judgments)}")

        # Domain coverage
        domains = sorted(set(j.domain for j in judgments))
        parts.append(f"Domain Coverage: {', '.join(domains)}")

        return "; ".join(parts)

    # ── Query ────────────────────────────────────────────────────────

    @property
    def judgment_count(self) -> int:
        return self._judgment_count
