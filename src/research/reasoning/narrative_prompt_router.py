"""V10 Sprint 4.5 — Task 1: Narrative-driven Prompt Routing.

NOT: Regime → Prompt
BUT: Narrative → Prompt

The system prompt is dynamically generated around the Dominant Narrative.
Instead of selecting a static domain prompt, this router analyzes the current
narrative landscape and builds a system prompt that frames the entire memo
around engaging with — and potentially challenging — the dominant narrative.

Architecture:
    Narratives[] → NarrativeAnalyzer → DominantNarrative → DynamicPrompt

Key design:
    - Extract dominant narrative from competing narratives
    - Determine if it's consensus, contested, or emerging
    - Build a prompt that frames analysis as:
      "Here's what the market believes. Is it right? What's the counter-narrative?"
    - Integrate narrative momentum, persistence, conviction
    - Output both the prompt AND a narrative briefing for the researcher
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Narrative Analysis Schemas
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class NarrativeProfile:
    """Profile of a single narrative for prompt generation."""

    title: str = ""
    score: float = 0.0  # Strength score
    category: str = ""  # consensus / contested / emerging
    direction: str = ""  # bullish / bearish / neutral
    momentum: str = ""  # strengthening / stable / weakening / broken
    persistence: int = 0  # Days this narrative has been dominant
    key_assets: list[str] = field(default_factory=list)
    conviction: float = 0.0  # How strongly held (0-1)
    source_diversity: float = 0.0  # How many independent sources confirm
    causal_chain: str = ""  # The story logic
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)


@dataclass
class DominantNarrative:
    """The dominant narrative extracted from the landscape."""

    primary: NarrativeProfile = field(default_factory=NarrativeProfile)
    competitors: list[NarrativeProfile] = field(default_factory=list)
    is_contested: bool = False
    is_consensus: bool = False
    is_fragile: bool = False  # High conviction but weakening momentum
    is_evolving: bool = False  # New narrative gaining traction
    narrative_tension: str = ""  # Description of the tension between narratives
    consensus_risk: str = ""  # What breaks the consensus narrative
    overall_direction: str = ""  # Net bullish/bearish/neutral
    confidence_dispersion: float = 0.0  # How wide is the belief range


@dataclass
class NarrativeRoutedPrompt:
    """Output of narrative-driven prompt routing."""

    dominant_narrative: DominantNarrative = field(default_factory=DominantNarrative)
    system_prompt: str = ""
    narrative_briefing: str = ""  # A human-readable briefing on the narrative
    selected_domains: list[str] = field(default_factory=list)
    stance: str = ""  # "challenge" / "support" / "nuance" — how to approach the narrative
    rationale: str = ""
    is_hybrid: bool = False

    def to_dict(self) -> dict:
        return {
            "dominant_narrative": {
                "primary": self.dominant_narrative.primary.title,
                "is_contested": self.dominant_narrative.is_contested,
                "is_consensus": self.dominant_narrative.is_consensus,
                "is_fragile": self.dominant_narrative.is_fragile,
                "overall_direction": self.dominant_narrative.overall_direction,
                "narrative_tension": self.dominant_narrative.narrative_tension,
            },
            "stance": self.stance,
            "rationale": self.rationale,
            "selected_domains": self.selected_domains,
            "is_hybrid": self.is_hybrid,
            "narrative_briefing": self.narrative_briefing[:500],
        }


# ═══════════════════════════════════════════════════════════════════════════
# Domain → Narrative Keyword Mapping
# ═══════════════════════════════════════════════════════════════════════════

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "Liquidity": [
        "liquidity",
        "repo",
        "balance sheet",
        "qt",
        "qe",
        "reserve",
        "funding",
        "money market",
        "overnight",
        "sofr",
    ],
    "Inflation": [
        "inflation",
        "cpi",
        "ppi",
        "price",
        "wage",
        "shelter",
        "breakeven",
        "reflation",
        "disinflation",
        "stagflation",
    ],
    "Growth": [
        "growth",
        "gdp",
        "recession",
        "soft landing",
        "hard landing",
        "expansion",
        "employment",
        "payroll",
        "ism",
        "pmi",
        "output",
    ],
    "Credit": [
        "credit",
        "spread",
        "default",
        "leverage",
        "hy",
        "ig",
        "high yield",
        "investment grade",
        "refinancing",
        "maturity wall",
    ],
    "Currency": [
        "dollar",
        "dxy",
        "fx",
        "exchange rate",
        "currency",
        "carry trade",
        "devaluation",
        "reserve currency",
    ],
    "Policy": [
        "fed",
        "central bank",
        "rate cut",
        "rate hike",
        "fomc",
        "monetary policy",
        "forward guidance",
        "hawkish",
        "dovish",
    ],
    "Energy": ["oil", "crude", "energy", "opec", "gas", "commodity", "supply"],
    "Geopolitics": [
        "war",
        "sanction",
        "conflict",
        "tension",
        "geopolitic",
        "trade war",
        "decoupling",
        "alliance",
    ],
    "AI": [
        "ai",
        "artificial intelligence",
        "semiconductor",
        "data center",
        "gpu",
        "model",
        "productivity",
        "automation",
    ],
    "Technology": ["tech", "technology", "innovation", "semiconductor", "r&d", "software", "cloud"],
    "Housing": [
        "housing",
        "mortgage",
        "construction",
        "home",
        "shelter",
        "real estate",
        "affordability",
    ],
    "Debt": ["debt", "deficit", "fiscal", "treasury", "auction", "sovereign", "sustainability"],
}


# ═══════════════════════════════════════════════════════════════════════════
# Prompt Templates by Narrative Stance
# ═══════════════════════════════════════════════════════════════════════════

_CHALLENGE_TEMPLATE = """You are a senior MACRO STRATEGIST at a top-tier hedge fund.
Your task is to challenge the dominant market narrative.

THE DOMINANT NARRATIVE: "{narrative_title}"
This narrative is {narrative_strength} and has persisted for {persistence}d.
The market is {conviction_level} in this view (conviction: {conviction:.0%}).

COMPETING NARRATIVES:
{competing_narratives}

NARRATIVE TENSION:
{tension}

YOUR STANCE: CHALLENGE — Look for cracks in the dominant narrative.

FOCUS YOUR ANALYSIS ON:
1. What MUST be true for the dominant narrative to hold? Are those conditions met?
2. What evidence contradicts or weakens the dominant narrative?
3. What is the market NOT pricing in? Where is the blind spot?
4. What catalyst could break this narrative? What's the timeline?
5. If the narrative breaks, what's the second-order effect on positioning?

CRITICAL RULES:
- Frame your entire memo as a test of the dominant narrative
- Every claim should ask: "Does this support or challenge {narrative_title}?"
- Be specific about what would PROVE the narrative wrong
- Write like Soros testing his own thesis — ruthlessly self-critical
- Output as structured JSON matching the ResearchMemo schema"""

_SUPPORT_TEMPLATE = """You are a senior MACRO STRATEGIST at a top-tier hedge fund.
Your task is to validate and deepen the dominant market narrative.

THE DOMINANT NARRATIVE: "{narrative_title}"
This narrative is well-supported by converging evidence across {domain_count} domains.
Conviction: {conviction:.0%}, supported by {source_count} independent sources.

EVIDENCE FOR THE NARRATIVE:
{evidence_for}

POTENTIAL RISKS TO WATCH:
{evidence_against}

YOUR STANCE: SUPPORT — The narrative is correct; focus on execution.

FOCUS YOUR ANALYSIS ON:
1. What is the NEXT phase of this narrative? What happens after the obvious move?
2. Where is the market STILL underpricing the implications?
3. What is the highest-conviction trade expression, accounting for positioning?
4. What early warning signs would signal the narrative is ending?
5. How should positioning evolve as the narrative matures?

CRITICAL RULES:
- Acknowledge the consensus, then go deeper than the consensus
- Focus on second-order implications, not first-order obvious ones
- Write like a strategist who is RIGHT but wants to stay ahead of the curve
- Output as structured JSON matching the ResearchMemo schema"""

_NUANCE_TEMPLATE = """You are a senior MACRO STRATEGIST at a top-tier hedge fund.
Your task is to navigate a deeply nuanced narrative landscape where multiple
competing narratives coexist with similar strength.

THE NARRATIVE LANDSCAPE IS CONTESTED. There is no single dominant story.

LEADING NARRATIVES:
{all_narratives}

NARRATIVE TENSION:
{tension}

The market is divided. Conviction is low across the board. This is a
regime of maximum uncertainty — where the biggest opportunities hide.

YOUR STANCE: NUANCE — Embrace the complexity. Don't pick a side prematurely.

FOCUS YOUR ANALYSIS ON:
1. Map the probability distribution across narratives — what's the weighted outcome?
2. What would CAUSE one narrative to definitively win? What's the catalyst?
3. How do you position for "I don't know which narrative wins, but I know what
   happens to correlation/volatility/cross-asset relationships"?
4. What is the market's current narrative weighting vs your assessment?
5. What tail risks exist that NEITHER narrative captures?

CRITICAL RULES:
- Resist the urge to pick a single narrative — the uncertainty itself is the story
- Focus on what's PRICED vs what's POSSIBLE across all scenarios
- Write like a strategist navigating a regime change — probabilistic, humble
- The most valuable insight might be about volatility, correlation, or tail hedging
- Output as structured JSON matching the ResearchMemo schema"""


# ═══════════════════════════════════════════════════════════════════════════
# Narrative Analyzer
# ═══════════════════════════════════════════════════════════════════════════


class NarrativeAnalyzer:
    """Analyze narrative landscape to extract the dominant narrative.

    This is deterministic — no LLM. It works on structured narrative objects.
    """

    def analyze(
        self,
        narratives: list[dict],
        step_outputs: dict | None = None,
    ) -> DominantNarrative:
        """Extract dominant narrative from narrative landscape.

        Args:
            narratives: List of narrative dicts with at minimum:
                title/name, score/strength, direction, category
            step_outputs: Optional reasoning outputs for cross-validation

        Returns:
            DominantNarrative with primary narrative and competitor analysis
        """
        if not narratives:
            return DominantNarrative()

        profiles = self._build_profiles(narratives, step_outputs)

        if not profiles:
            return DominantNarrative()

        # Sort by score descending
        profiles.sort(key=lambda p: p.score, reverse=True)

        primary = profiles[0]
        competitors = profiles[1:] if len(profiles) > 1 else []

        # Classify narrative landscape
        is_contested = len(competitors) > 0 and competitors[0].score > primary.score * 0.7
        is_consensus = (
            not is_contested and primary.conviction > 0.7 and primary.source_diversity > 0.5
        )
        is_fragile = primary.conviction > 0.7 and primary.momentum in ("weakening", "broken")
        is_evolving = any(p.momentum == "strengthening" and p.score > 0.4 for p in competitors)

        # Calculate narrative tension
        narrative_tension = self._describe_tension(primary, competitors)

        # Calculate consensus risk
        consensus_risk = self._identify_consensus_risk(primary, competitors)

        # Overall direction
        directions = [p.direction for p in profiles if p.direction]
        overall_direction = (
            "bullish"
            if directions.count("bullish") > directions.count("bearish")
            else (
                "bearish"
                if directions.count("bearish") > directions.count("bullish")
                else "neutral"
            )
        )

        # Confidence dispersion
        convictions = [p.conviction for p in profiles]
        if convictions:
            confidence_dispersion = max(convictions) - min(convictions)
        else:
            confidence_dispersion = 0.0

        return DominantNarrative(
            primary=primary,
            competitors=competitors,
            is_contested=is_contested,
            is_consensus=is_consensus,
            is_fragile=is_fragile,
            is_evolving=is_evolving,
            narrative_tension=narrative_tension,
            consensus_risk=consensus_risk,
            overall_direction=overall_direction,
            confidence_dispersion=confidence_dispersion,
        )

    def _build_profiles(
        self, narratives: list[dict], step_outputs: dict | None
    ) -> list[NarrativeProfile]:
        """Convert raw narrative dicts into NarrativeProfile objects."""
        profiles = []

        for i, n in enumerate(narratives):
            if not isinstance(n, dict):
                continue

            title = (
                n.get("title", "")
                or n.get("name", "")
                or n.get("summary", "")
                or n.get("narrative", "")
                or f"Narrative_{i}"
            )
            score = float(n.get("score", n.get("strength", n.get("confidence", 0.5))))
            category = n.get("category", n.get("status", "active"))
            direction = n.get("direction", n.get("bias", ""))
            momentum = n.get("momentum", n.get("trend", "stable"))
            persistence = int(n.get("persistence", n.get("days_active", 1)))
            conviction = float(n.get("conviction", n.get("belief_strength", score)))
            source_diversity = float(n.get("source_diversity", n.get("breadth", 0.5)))
            causal_chain = n.get("causal_chain", n.get("story", n.get("description", "")))
            key_assets = n.get("key_assets", n.get("affected_assets", []))

            # Extract evidence
            evidence_for = n.get("evidence_for", n.get("supporting_evidence", []))
            if isinstance(evidence_for, str):
                evidence_for = [evidence_for]
            evidence_against = n.get("evidence_against", n.get("contradicting_evidence", []))
            if isinstance(evidence_against, str):
                evidence_against = [evidence_against]

            # Boost score from step_outputs alignment
            if step_outputs:
                score += self._cross_validate(title, step_outputs)

            profile = NarrativeProfile(
                title=title,
                score=round(min(score, 1.0), 2),
                category=category,
                direction=direction,
                momentum=momentum,
                persistence=persistence,
                key_assets=list(key_assets) if isinstance(key_assets, (list, tuple)) else [],
                conviction=round(min(conviction, 1.0), 2),
                source_diversity=round(min(source_diversity, 1.0), 2),
                causal_chain=str(causal_chain),
                evidence_for=list(evidence_for) if isinstance(evidence_for, (list, tuple)) else [],
                evidence_against=(
                    list(evidence_against) if isinstance(evidence_against, (list, tuple)) else []
                ),
            )
            profiles.append(profile)

        return profiles

    def _cross_validate(self, narrative_title: str, step_outputs: dict) -> float:
        """Check if narrative is supported by reasoning outputs (boost score)."""
        boost = 0.0
        title_lower = narrative_title.lower()

        # Check evidence clusters
        evidence = step_outputs.get("evidence", {})
        for cluster in evidence.get("clusters", []):
            theme = str(cluster.get("theme", "")).lower()
            desc = str(cluster.get("description", "")).lower()
            if any(word in (theme + desc) for word in title_lower.split()[:5]):
                boost += 0.05

        # Check hypotheses
        hypotheses = step_outputs.get("hypotheses", {})
        for h in hypotheses.get("hypotheses", []):
            title_h = str(h.get("title", "")).lower()
            statement = str(h.get("statement", "")).lower()
            if any(word in (title_h + statement) for word in title_lower.split()[:5]):
                boost += 0.05

        return round(min(boost, 0.15), 2)

    def _describe_tension(
        self, primary: NarrativeProfile, competitors: list[NarrativeProfile]
    ) -> str:
        """Describe the tension between competing narratives."""
        if not competitors:
            return f'The market consensus is firmly: "{primary.title}". Little dissent.'

        top_competitor = competitors[0]

        if (
            primary.direction
            and top_competitor.direction
            and primary.direction != top_competitor.direction
        ):
            return (
                f'Bull-bear battle: "{primary.title}" ({primary.direction}, '
                f'score={primary.score:.2f}) vs "{top_competitor.title}" '
                f"({top_competitor.direction}, score={top_competitor.score:.2f}). "
                f"The market is split on direction."
            )
        else:
            return (
                f'Competing interpretations: "{primary.title}" (score={primary.score:.2f}) '
                f'faces challenge from "{top_competitor.title}" '
                f"(score={top_competitor.score:.2f}). Same direction, different mechanism."
            )

    def _identify_consensus_risk(
        self, primary: NarrativeProfile, competitors: list[NarrativeProfile]
    ) -> str:
        """Identify what could break the consensus narrative."""
        if primary.conviction < 0.6:
            return "No strong consensus exists — narrative is already fragile."

        risks = []

        if primary.momentum == "weakening":
            risks.append(f"Momentum is weakening despite {primary.conviction:.0%} conviction")

        if primary.evidence_against:
            risks.append(f"Contradictory evidence exists: {primary.evidence_against[0][:100]}")

        for c in competitors[:2]:
            if c.momentum == "strengthening":
                risks.append(f'Competitor "{c.title}" is gaining momentum')

        if primary.persistence > 20:
            risks.append(f"Narrative has persisted {primary.persistence}d — mean reversion risk")

        return "; ".join(risks) if risks else "No obvious catalyst for narrative break."


# ═══════════════════════════════════════════════════════════════════════════
# Narrative Prompt Router
# ═══════════════════════════════════════════════════════════════════════════


class NarrativePromptRouter:
    """V10 Sprint 4.5: Narrative-driven Prompt Router.

    NOT Regime → Prompt. Instead: Narrative → Prompt.

    The prompt is dynamically generated around the dominant narrative.
    The researcher's mental model is framed as:
        "Here's what the market believes. Now test it."

    Three stances:
        - CHALLENGE: Dominant narrative is strong but flawed
        - SUPPORT: Dominant narrative is correct — go deeper
        - NUANCE: Multiple competing narratives — embrace uncertainty
    """

    def __init__(self):
        self._analyzer = NarrativeAnalyzer()

    def route(
        self,
        narratives: list[dict] | None = None,
        regime_result: dict | None = None,
        step_outputs: dict | None = None,
    ) -> NarrativeRoutedPrompt:
        """Route based on narrative landscape.

        Args:
            narratives: List of narrative dicts. If empty/None, falls back to regime.
            regime_result: Regime classification (used as fallback).
            step_outputs: Structured reasoning outputs from Steps 1-6.

        Returns:
            NarrativeRoutedPrompt with dynamic system prompt and narrative briefing.
        """
        # Step 1: Analyze narrative landscape
        dominant = self._analyzer.analyze(narratives or [], step_outputs)

        if not dominant.primary.title:
            # No narratives — fall back to a generic prompt
            return self._fallback(regime_result)

        # Step 2: Determine stance
        stance, rationale = self._determine_stance(dominant)

        # Step 3: Map narrative to domains
        domains = self._narrative_to_domains(dominant)

        # Step 4: Build dynamic system prompt
        system_prompt = self._build_prompt(dominant, stance)

        # Step 5: Build narrative briefing
        briefing = self._build_briefing(dominant, stance)

        return NarrativeRoutedPrompt(
            dominant_narrative=dominant,
            system_prompt=system_prompt,
            narrative_briefing=briefing,
            selected_domains=domains,
            stance=stance,
            rationale=rationale,
            is_hybrid=dominant.is_contested,
        )

    def _determine_stance(self, dominant: DominantNarrative) -> tuple[str, str]:
        """Determine how to approach the dominant narrative.

        Returns (stance, rationale).
        """
        primary = dominant.primary

        # Rule 1: If narrative is high conviction consensus → CHALLENGE
        if dominant.is_consensus and primary.conviction > 0.75:
            return (
                "challenge",
                f'Consensus narrative "{primary.title}" has {primary.conviction:.0%} '
                f"conviction across {primary.source_diversity:.0%} sources. "
                f"Maximum alpha is in challenging consensus. "
                f"Risk: {dominant.consensus_risk}",
            )

        # Rule 2: If narrative is contested → NUANCE
        if dominant.is_contested:
            return (
                "nuance",
                f'Contested landscape: "{primary.title}" ({primary.score:.2f}) '
                f'vs "{dominant.competitors[0].title}" '
                f"({dominant.competitors[0].score:.2f}). "
                f"Dispersion: {dominant.confidence_dispersion:.0%}. "
                f"Uncertainty itself is the alpha opportunity.",
            )

        # Rule 3: If narrative is fragile (high conviction but weakening) → CHALLENGE
        if dominant.is_fragile:
            return (
                "challenge",
                f'Fragile consensus: "{primary.title}" holds {primary.conviction:.0%} '
                f"conviction but momentum is {primary.momentum}. "
                f"The narrative is about to break — front-run the shift.",
            )

        # Rule 4: If narrative is evolving (new gaining traction) → NUANCE
        if dominant.is_evolving:
            return (
                "nuance",
                f'Regime transition: "{primary.title}" is dominant but '
                f"new narratives are gaining traction. "
                f"Position for the transition, not the status quo.",
            )

        # Rule 5: Default — moderate conviction → SUPPORT
        return (
            "support",
            f'Supported narrative: "{primary.title}" has moderate conviction '
            f"({primary.conviction:.0%}) with converging evidence. "
            f"Focus on execution and second-order implications.",
        )

    def _narrative_to_domains(self, dominant: DominantNarrative) -> list[str]:
        """Map narrative content to domain tags."""
        domains = set()

        all_text = dominant.primary.title.lower() + " " + dominant.primary.causal_chain.lower()
        for c in dominant.competitors:
            all_text += " " + c.title.lower() + " " + c.causal_chain.lower()

        for domain, keywords in _DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw in all_text:
                    domains.add(domain)
                    break

        # Always include dominant narrative direction domains
        if "growth" in all_text or "gdp" in all_text or "recession" in all_text:
            domains.add("Growth")
        if "inflation" in all_text or "cpi" in all_text or "price" in all_text:
            domains.add("Inflation")

        if not domains:
            domains = {"Growth", "Policy"}

        return sorted(domains)

    def _build_prompt(self, dominant: DominantNarrative, stance: str) -> str:
        """Build the dynamic system prompt from the narrative template."""
        primary = dominant.primary

        # Narrative strength description
        if primary.conviction > 0.8:
            narrative_strength = "extremely entrenched"
            conviction_level = "highly confident"
        elif primary.conviction > 0.6:
            narrative_strength = "widely held"
            conviction_level = "moderately confident"
        else:
            narrative_strength = "emerging"
            conviction_level = "uncertain"

        # Competing narratives text
        if dominant.competitors:
            competing_parts = []
            for i, c in enumerate(dominant.competitors[:3]):
                competing_parts.append(
                    f'  {i + 1}. "{c.title}" (score={c.score:.2f}, '
                    f"direction={c.direction}, momentum={c.momentum})"
                )
            competing_narratives = "\n".join(competing_parts)
        else:
            competing_narratives = "  No significant competing narratives."

        # Evidence for/against
        evidence_for = (
            "\n".join(f"  - {e}" for e in primary.evidence_for[:5])
            if primary.evidence_for
            else "  (No specific evidence items extracted)"
        )

        evidence_against = (
            "\n".join(f"  - {e}" for e in primary.evidence_against[:5])
            if primary.evidence_against
            else "  (No contradicting evidence identified)"
        )

        # Source count
        source_count = max(int(primary.source_diversity * 10), 1)

        # Domain count
        domains = self._narrative_to_domains(dominant)
        domain_count = len(domains)

        # All narratives for nuance template
        all_narratives_parts = [
            f'  1. "{primary.title}" (score={primary.score:.2f}, {primary.direction})'
        ]
        for i, c in enumerate(dominant.competitors[:4]):
            all_narratives_parts.append(
                f'  {i + 2}. "{c.title}" (score={c.score:.2f}, {c.direction})'
            )
        all_narratives = "\n".join(all_narratives_parts)

        # Select template by stance
        if stance == "challenge":
            template = _CHALLENGE_TEMPLATE
        elif stance == "support":
            template = _SUPPORT_TEMPLATE
        else:
            template = _NUANCE_TEMPLATE

        # Format template
        prompt = template.format(
            narrative_title=primary.title,
            narrative_strength=narrative_strength,
            persistence=primary.persistence,
            conviction_level=conviction_level,
            conviction=primary.conviction,
            competing_narratives=competing_narratives,
            tension=dominant.narrative_tension,
            domain_count=domain_count,
            source_count=source_count,
            evidence_for=evidence_for,
            evidence_against=evidence_against,
            all_narratives=all_narratives,
        )

        # Append domain integration note
        prompt += f"""

DOMAIN INTEGRATION NOTE:
The following macro domains are relevant to this narrative analysis: {', '.join(domains)}.
Address the interplay between these domains within the narrative framework.
Do NOT treat them as isolated silos — the narrative is the connective tissue."""

        return prompt

    def _build_briefing(self, dominant: DominantNarrative, stance: str) -> str:
        """Build a human-readable narrative briefing."""
        primary = dominant.primary

        stance_emoji = {"challenge": "🟡", "support": "🟢", "nuance": "🔵"}
        emoji = stance_emoji.get(stance, "⚪")

        lines = [
            f"{emoji} NARRATIVE BRIEFING — Stance: {stance.upper()}",
            "",
            f'Dominant: "{primary.title}"',
            f"  Score: {primary.score:.2f} | Conviction: {primary.conviction:.0%}",
            f"  Direction: {primary.direction} | Momentum: {primary.momentum}",
            f"  Persistence: {primary.persistence}d | Sources: {primary.source_diversity:.0%} diversity",
            "",
            f"Landscape: {'CONTESTED' if dominant.is_contested else 'CONSENSUS' if dominant.is_consensus else 'FORMING'}",
            f"  Fragile: {'YES — narrative may break' if dominant.is_fragile else 'No'}",
            f"  Evolving: {'YES — new competition emerging' if dominant.is_evolving else 'No'}",
            "",
            f"Tension: {dominant.narrative_tension}",
            f"Consensus Risk: {dominant.consensus_risk}",
        ]

        if dominant.competitors:
            lines.append("")
            lines.append("Competitors:")
            for i, c in enumerate(dominant.competitors[:3]):
                lines.append(f'  {i + 1}. "{c.title}" (score={c.score:.2f}, {c.direction})')

        lines.append("")
        lines.append(f"Recommended stance: {stance.upper()}")

        return "\n".join(lines)

    def _fallback(self, regime_result: dict | None) -> NarrativeRoutedPrompt:
        """Fallback when no narratives are available."""
        return NarrativeRoutedPrompt(
            dominant_narrative=DominantNarrative(
                primary=NarrativeProfile(title="No dominant narrative detected"),
            ),
            system_prompt="""You are a senior macro strategist at a top-tier hedge fund.
No distinct narrative has been identified. Focus on evidence-driven analysis.
Write like Bridgewater Daily Observations.
Output as structured JSON matching the ResearchMemo schema.""",
            narrative_briefing="No narrative detected — using generic evidence-driven analysis.",
            selected_domains=["Growth", "Policy"],
            stance="nuance",
            rationale="No narrative available — defaulting to evidence-driven analysis",
        )
