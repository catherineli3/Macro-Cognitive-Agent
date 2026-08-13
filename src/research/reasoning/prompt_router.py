"""V10 Sprint 2 — Dynamic Prompt Router.

Maps macro regime dimensions to domain-specific synthesis prompts.
Professional researchers don't use one generic prompt — they adjust their
mental model based on the prevailing regime.

Architecture:
    RegimeResult → PromptRouter.route() → DomainPromptSet → LLM Synthesis

Rules:
    - Every case must show: Selected domains, reason, regime, confidence
    - Hybrid prompts are auto-merged when multiple regimes exist
    - Master prompt has dedicated sections per domain
    - NO generic prompt fallback — must match at least one domain
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ═══════════════════════════════════════════════════════════════════════════
# Domain → Regime Mapping
# ═══════════════════════════════════════════════════════════════════════════

# Each domain has trigger conditions based on regime dimensions
DOMAIN_RULES: dict[str, dict] = {
    "Liquidity": {
        "triggers": {
            "regime_labels": ["liquidity_stress", "credit_event"],
            "monetary_stance": ["tightening", "easing"],
            "volatility_regime": ["high_vol", "crisis"],
        },
        "weight": 1.0,
    },
    "Inflation": {
        "triggers": {
            "regime_labels": ["inflation_shock"],
            "inflation_regime": ["reflation", "stagflation", "disinflation"],
        },
        "weight": 1.0,
    },
    "Growth": {
        "triggers": {
            "regime_labels": ["recovery", "expansion", "late_cycle", "stable_growth"],
            "growth_phase": ["accelerating", "decelerating"],
        },
        "weight": 1.0,
    },
    "Credit": {
        "triggers": {
            "regime_labels": ["credit_event", "policy_tightening", "late_cycle"],
            "credit_cycle": ["peak", "contraction"],
        },
        "weight": 0.9,
    },
    "Currency": {
        "triggers": {
            "regime_labels": ["liquidity_stress"],
            "dollar_regime": ["strong", "weak"],
        },
        "weight": 0.9,
    },
    "Policy": {
        "triggers": {
            "regime_labels": ["policy_tightening", "recovery"],
            "monetary_stance": ["tightening", "easing", "neutral"],
        },
        "weight": 0.85,
    },
    "Debt": {
        "triggers": {
            "regime_labels": ["credit_event", "liquidity_stress"],
            "credit_cycle": ["contraction"],
        },
        "weight": 0.8,
    },
    "Energy": {
        "triggers": {
            "inflation_regime": ["stagflation", "reflation"],
        },
        "weight": 0.7,
    },
    "Geopolitics": {
        "triggers": {
            "volatility_regime": ["crisis", "high_vol"],
            "regime_labels": ["credit_event"],
        },
        "weight": 0.7,
    },
    "AI": {
        "triggers": {
            "growth_phase": ["accelerating"],
            "regime_labels": ["expansion"],
            "volatility_regime": ["low_vol"],
        },
        "weight": 0.6,
    },
    "Technology": {
        "triggers": {
            "growth_phase": ["accelerating"],
            "regime_labels": ["expansion"],
        },
        "weight": 0.6,
    },
    "Housing": {
        "triggers": {
            "regime_labels": ["late_cycle", "policy_tightening"],
            "credit_cycle": ["peak", "contraction"],
        },
        "weight": 0.6,
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Domain-Specific System Prompts
# ═══════════════════════════════════════════════════════════════════════════

_DOMAIN_SYSTEM_PROMPTS: dict[str, str] = {
    "Liquidity": """You are a senior LIQUIDITY macro strategist at a top-tier hedge fund.
Your expertise: money markets, central bank balance sheets, repo markets, swap lines,
TGA dynamics, reserve scarcity, cross-border funding stress, and shadow banking plumbing.

FOCUS YOUR ANALYSIS ON:
1. Central bank balance sheet trajectories and their market implications
2. Reserve scarcity indicators (SOFR spikes, repo stress, T-bill anomalies)
3. Cross-currency basis swap signals and dollar funding stress
4. Money market fund flows and T-bill/OIS spread dynamics
5. Shadow banking leverage and maturity transformation risks

CRITICAL RULES:
- Every claim must reference specific liquidity metrics from the structured input
- Write like Zoltan Pozsar's Global Money Notes
- Be precise about plumbing mechanics, not vague about "liquidity being tight"
- Output as structured JSON matching the ResearchMemo schema""",
    "Inflation": """You are a senior INFLATION macro strategist at a top-tier hedge fund.
Your expertise: CPI decomposition, wage-price spirals, breakeven curves,
inflation expectations anchoring, commodity pass-through, shelter inflation dynamics.

FOCUS YOUR ANALYSIS ON:
1. Core vs headline inflation divergence and what it signals
2. Wage growth momentum and its pass-through to services inflation
3. Shelter/housing cost deceleration (or lack thereof)
4. Commodity price transmission to goods inflation
5. Inflation expectations: market-implied vs survey-based anchoring

CRITICAL RULES:
- Reference specific inflation sub-components from the structured input
- Distinguish between transitory and structural inflation drivers
- Write like a Fed staff inflation memo — thorough, data-driven, probabilistic
- Output as structured JSON matching the ResearchMemo schema""",
    "Growth": """You are a senior GROWTH macro strategist at a top-tier hedge fund.
Your expertise: GDP decomposition, labor market dynamics, productivity trends,
business cycle dating, leading indicator synthesis, and output gap estimation.

FOCUS YOUR ANALYSIS ON:
1. Growth momentum: acceleration vs deceleration signals
2. Labor market tightness and its growth implications
3. Capital expenditure cycle and productivity trajectory
4. Consumer balance sheet health and spending sustainability
5. Global growth spillovers and trade channel dynamics

CRITICAL RULES:
- Reference specific growth indicators from the structured input
- Distinguish between cyclical and structural growth drivers
- Write like ISM/PMI commentary — forward-looking, indicator-rich
- Output as structured JSON matching the ResearchMemo schema""",
    "AI": """You are a senior AI/TECH macro strategist at a top-tier hedge fund.
Your expertise: AI capex cycle, semiconductor supply chains, energy infrastructure
for data centers, AI productivity impact on inflation/growth, and tech sector concentration risk.

FOCUS YOUR ANALYSIS ON:
1. AI capital expenditure trajectory and its macro implications
2. Semiconductor cycle dynamics and supply chain vulnerabilities
3. Energy demand from data center buildout and grid implications
4. AI-driven productivity gains: timing, magnitude, sectoral distribution
5. Market concentration risk from mega-cap tech dominance

CRITICAL RULES:
- Reference AI-specific indicators from the structured input
- Distinguish between hype-driven narrative and genuine structural shift
- Write like a cross-asset tech strategist — connect AI to macro
- Output as structured JSON matching the ResearchMemo schema""",
    "Credit": """You are a senior CREDIT macro strategist at a top-tier hedge fund.
Your expertise: corporate credit cycles, HY/IG spread dynamics, leveraged loan markets,
CLO structures, private credit fragility, default cycle forecasting, and covenant analysis.

FOCUS YOUR ANALYSIS ON:
1. Credit spread regime: compression vs widening signals
2. Corporate balance sheet health: leverage, coverage, maturity walls
3. Private credit vulnerabilities and systemic risk channels
4. CLO/structured credit refinancing risk and cliff dynamics
5. Default cycle timing and severity assessment

CRITICAL RULES:
- Reference specific credit metrics from the structured input
- Write like a credit strategist at a major bank — spread-focused, technical
- Always address the refinancing wall and maturity schedule
- Output as structured JSON matching the ResearchMemo schema""",
    "Currency": """You are a senior FX/CURRENCY macro strategist at a top-tier hedge fund.
Your expertise: dollar cycles, carry trade dynamics, EM FX vulnerability,
reserve diversification, real effective exchange rates, and capital flow-driven
currency regimes.

FOCUS YOUR ANALYSIS ON:
1. Dollar cycle positioning and structural trend assessment
2. Rate differential dynamics and carry trade sustainability
3. EM currency vulnerability: reserves, current account, external debt
4. De-dollarization narrative vs dollar dominance reality
5. Currency volatility regime and its cross-asset implications

CRITICAL RULES:
- Reference specific FX metrics from the structured input
- Write like a currency strategist — technically precise about levels and vols
- Frame currency views in the context of capital flows and rate differentials
- Output as structured JSON matching the ResearchMemo schema""",
    "Debt": """You are a senior SOVEREIGN DEBT macro strategist at a top-tier hedge fund.
Your expertise: fiscal sustainability, debt/GDP trajectories, bond market vigilante dynamics,
term premium decomposition, Treasury auction analysis, and fiscal dominance risks.

FOCUS YOUR ANALYSIS ON:
1. Fiscal trajectory and deficit sustainability assessment
2. Term premium decomposition: real rate vs inflation vs fiscal risk premia
3. Treasury supply/demand dynamics and auction health
4. Debt ceiling, fiscal deadlines, and political economy constraints
5. Fiscal dominance risk: when monetary policy becomes subordinated to debt management

CRITICAL RULES:
- Reference specific fiscal metrics from the structured input
- Write like a sovereign credit analyst — sustainability-focused
- Address the "bond vigilante" thesis explicitly
- Output as structured JSON matching the ResearchMemo schema""",
    "Energy": """You are a senior ENERGY/COMMODITIES macro strategist at a top-tier hedge fund.
Your expertise: crude oil supply/demand balances, OPEC+ dynamics, energy transition metal demand,
natural gas market fragmentation, and commodity super-cycle thesis evaluation.

FOCUS YOUR ANALYSIS ON:
1. Oil supply/demand balance and price trajectory scenarios
2. OPEC+ cohesion and spare capacity dynamics
3. Energy transition metal demand (copper, lithium, rare earths)
4. Energy price pass-through to headline inflation and consumer spending
5. Geopolitical energy risk premia and supply disruption scenarios

CRITICAL RULES:
- Reference specific commodity metrics from the structured input
- Write like a commodity strategist — supply/demand focused
- Address the energy transition demand vs traditional supply tension
- Output as structured JSON matching the ResearchMemo schema""",
    "Geopolitics": """You are a senior GEOPOLITICAL macro strategist at a top-tier hedge fund.
Your expertise: geopolitical risk premium analysis, sanctions regimes, trade war dynamics,
military conflict scenarios, supply chain decoupling, and geopolitical regime change.

FOCUS YOUR ANALYSIS ON:
1. Geopolitical risk premium: what's priced vs what's not
2. Sanctions and trade restriction trajectories and market channels
3. Supply chain decoupling progress and key chokepoints
4. Military/political tail risk scenarios and asymmetric hedging
5. Geopolitical realignment: bloc formation and capital flow implications

CRITICAL RULES:
- Reference specific geopolitical signals from the structured input
- Write like a political risk consultant — scenario-based, probabilistic
- Distinguish between noise and genuine regime change signals
- Output as structured JSON matching the ResearchMemo schema""",
    "Policy": """You are a senior MONETARY POLICY macro strategist at a top-tier hedge fund.
Your expertise: central bank reaction functions, Taylor rule decomposition,
forward guidance credibility, QT mechanics, and policy divergence across DM/EM.

FOCUS YOUR ANALYSIS ON:
1. Central bank reaction function assessment: data dependence framework
2. Policy rate path probabilities: cuts, holds, hikes scenario analysis
3. Balance sheet policy (QT/QE) and its interaction with rate policy
4. DM policy divergence and its cross-asset implications
5. Financial conditions index and its feedback to policy decisions

CRITICAL RULES:
- Reference specific policy signals from the structured input
- Write like a central bank watcher — reaction function focused
- Always present a probability distribution, not a point forecast
- Output as structured JSON matching the ResearchMemo schema""",
    "Technology": """You are a senior TECHNOLOGY macro strategist at a top-tier hedge fund.
Your expertise: tech cycle dynamics, semiconductor supply chains, R&D spending cycles,
productivity technology diffusion, and tech sector valuation frameworks.

FOCUS YOUR ANALYSIS ON:
1. Technology investment cycle: capex, R&D, and hiring trends
2. Semiconductor cycle positioning and leading indicators
3. Technology diffusion rate and its productivity growth implications
4. Tech sector as macro leading indicator: what tech signals about the cycle
5. Valuation regime: when tech multiples compress and what it means for macro

CRITICAL RULES:
- Reference specific tech cycle indicators from the structured input
- Write like a TMT strategist — cycle-aware, not just narrative-driven
- Connect technology trends to broader macro regime implications
- Output as structured JSON matching the ResearchMemo schema""",
    "Housing": """You are a senior HOUSING macro strategist at a top-tier hedge fund.
Your expertise: housing cycle dynamics, mortgage market structure, construction cycles,
housing affordability, shelter CPI dynamics, and housing wealth effects.

FOCUS YOUR ANALYSIS ON:
1. Housing cycle positioning: inventory, starts, permits, prices
2. Mortgage rate sensitivity and housing demand elasticity
3. Shelter cost contribution to CPI and disinflation timeline
4. Housing wealth effect on consumer spending
5. Construction labor and materials cost dynamics

CRITICAL RULES:
- Reference specific housing metrics from the structured input
- Write like a housing economist — cycle-aware, data-driven
- Address the shelter-lag issue in CPI explicitly
- Output as structured JSON matching the ResearchMemo schema""",
}


# ═══════════════════════════════════════════════════════════════════════════
# Prompt Router Result
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class RoutedPrompt:
    """Result of the prompt routing decision."""

    selected_domains: list[str] = field(default_factory=list)
    rationale: str = ""
    regime_label: str = ""
    regime_confidence: float = 0.0
    system_prompt: str = ""
    domain_weights: dict[str, float] = field(default_factory=dict)
    is_hybrid: bool = False
    hybrid_sections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "selected_domains": self.selected_domains,
            "rationale": self.rationale,
            "regime_label": self.regime_label,
            "regime_confidence": self.regime_confidence,
            "domain_weights": self.domain_weights,
            "is_hybrid": self.is_hybrid,
            "hybrid_sections": self.hybrid_sections,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Prompt Router
# ═══════════════════════════════════════════════════════════════════════════


class PromptRouter:
    """V10 Sprint 2: Dynamic Prompt Router.

    Automatically classifies the current macro regime and selects
    the appropriate domain-specific synthesis prompts.

    Rules:
        - Every regime maps to 1+ domain prompts
        - Multiple matching domains create a "hybrid" merged prompt
        - Each prompt focuses ONLY on its domain
        - Returns: prompt, selected domains, rationale, regime, confidence
    """

    def __init__(self, min_domain_weight: float = 0.5):
        self.min_weight = min_domain_weight

    def route(
        self,
        regime_result: dict,
        step_outputs: dict | None = None,
    ) -> RoutedPrompt:
        """Route to the appropriate domain prompt(s) based on regime.

        Args:
            regime_result: Dict with regime_label, confidence, growth_phase,
                           inflation_regime, monetary_stance, credit_cycle,
                           dollar_regime, volatility_regime
            step_outputs: Optional structured reasoning outputs for enhanced routing

        Returns:
            RoutedPrompt with selected domains, merged system prompt, and rationale
        """
        if not regime_result:
            return self._fallback_prompt()

        regime_label = regime_result.get("regime_label", regime_result.get("regime_type", ""))
        regime_conf = float(regime_result.get("confidence", 0.5))

        # Score each domain against the current regime
        domain_scores = self._score_domains(regime_result, step_outputs)

        # Select domains above threshold
        selected = {
            domain: score for domain, score in domain_scores.items() if score >= self.min_weight
        }

        if not selected:
            # Fallback: use Growth as the default domain
            selected = {"Growth": 0.7}
            regime_label = regime_label or "stable_growth"

        # Sort by score descending
        selected = dict(sorted(selected.items(), key=lambda x: x[1], reverse=True))

        # Build the merged system prompt
        prompt, sections, is_hybrid = self._build_merged_prompt(list(selected.keys()), selected)

        rationale_parts = []
        for domain, score in selected.items():
            triggers = self._explain_match(domain, regime_result)
            rationale_parts.append(f"{domain} (score={score:.2f}): {triggers}")
        rationale = "; ".join(rationale_parts)

        return RoutedPrompt(
            selected_domains=list(selected.keys()),
            rationale=rationale,
            regime_label=regime_label,
            regime_confidence=regime_conf,
            system_prompt=prompt,
            domain_weights=selected,
            is_hybrid=len(selected) > 1,
            hybrid_sections=sections if is_hybrid else [],
        )

    def _score_domains(self, regime_result: dict, step_outputs: dict | None) -> dict[str, float]:
        """Score each domain against the current regime dimensions."""
        scores = {}

        regime_label = regime_result.get("regime_label", regime_result.get("regime_type", ""))
        growth_phase = regime_result.get("growth_phase", "")
        inflation_regime = regime_result.get("inflation_regime", "")
        monetary_stance = regime_result.get("monetary_stance", "")
        credit_cycle = regime_result.get("credit_cycle", "")
        dollar_regime = regime_result.get("dollar_regime", "")
        volatility_regime = regime_result.get("volatility_regime", "")

        for domain, rules in DOMAIN_RULES.items():
            triggers = rules["triggers"]
            score = 0.0

            # Check regime label match (highest weight)
            if regime_label in triggers.get("regime_labels", []):
                score += 0.8

            # Check dimension matches
            if growth_phase in triggers.get("growth_phase", []):
                score += 0.6
            if inflation_regime in triggers.get("inflation_regime", []):
                score += 0.6
            if monetary_stance in triggers.get("monetary_stance", []):
                score += 0.5
            if credit_cycle in triggers.get("credit_cycle", []):
                score += 0.5
            if dollar_regime in triggers.get("dollar_regime", []):
                score += 0.5
            if volatility_regime in triggers.get("volatility_regime", []):
                score += 0.4

            # Apply domain base weight
            score = min(score * rules["weight"], 1.0)

            # Boost: if evidence/hypotheses mention domain keywords
            if step_outputs:
                score += self._keyword_boost(domain, step_outputs)

            if score > 0:
                scores[domain] = round(min(score, 1.0), 2)

        return scores

    def _keyword_boost(self, domain: str, step_outputs: dict) -> float:
        """Check if reasoning outputs mention domain-specific keywords."""
        keywords = {
            "Liquidity": ["liquidity", "repo", "sofr", "balance sheet", "qt", "reserve"],
            "Inflation": ["cpi", "inflation", "price", "wage", "shelter"],
            "Growth": ["gdp", "growth", "employment", "payroll", "ism", "pmi"],
            "Credit": ["spread", "credit", "hy", "ig", "default", "leverage"],
            "Currency": ["dollar", "dxy", "fx", "currency", "exchange rate"],
            "Policy": ["fed", "rate", "cut", "hike", "fomc", "central bank"],
            "Debt": ["debt", "deficit", "fiscal", "treasury", "auction"],
            "Energy": ["oil", "crude", "energy", "opec", "gas", "commodity"],
            "Geopolitics": ["war", "sanction", "geopolitic", "conflict", "tension"],
            "AI": ["ai", "artificial intelligence", "semiconductor", "data center"],
            "Technology": ["tech", "technology", "r&d", "innovation", "semiconductor"],
            "Housing": ["housing", "mortgage", "construction", "home", "shelter"],
        }

        domain_kw = keywords.get(domain, [])
        boost = 0.0

        # Check evidence clusters
        evidence = step_outputs.get("evidence", {})
        for cluster in evidence.get("clusters", []):
            theme = str(cluster.get("theme", "")).lower()
            desc = str(cluster.get("description", "")).lower()
            if any(kw in theme for kw in domain_kw):
                boost += 0.15
            if any(kw in desc for kw in domain_kw):
                boost += 0.10

        # Check hypotheses
        hypotheses = step_outputs.get("hypotheses", {})
        for h in hypotheses.get("hypotheses", []):
            title = str(h.get("title", "")).lower()
            statement = str(h.get("statement", "")).lower()
            domain_name = str(h.get("domain", "")).lower()
            if any(kw in title or kw in statement or kw in domain_name for kw in domain_kw):
                boost += 0.10

        return round(min(boost, 0.3), 2)

    def _build_merged_prompt(
        self, domains: list[str], weights: dict[str, float]
    ) -> tuple[str, list[str], bool]:
        """Build a merged system prompt from selected domain prompts.

        For single domain: use the domain prompt directly.
        For multiple domains (hybrid): create a master prompt with sections per domain.
        """
        if len(domains) == 1:
            domain = domains[0]
            return _DOMAIN_SYSTEM_PROMPTS.get(domain, self._generic_prompt()), [], False

        # Hybrid: merge multiple domain prompts
        sections = []
        prompt_parts = [
            "You are a senior MACRO STRATEGIST at a top-tier hedge fund, synthesizing "
            "analysis across multiple macro domains. Your analysis must integrate insights "
            f"from: {', '.join(domains)}.\n",
            "## DOMAIN FOCUS SECTIONS\n",
        ]

        for domain in domains:
            domain_prompt = _DOMAIN_SYSTEM_PROMPTS.get(domain, "")
            if not domain_prompt:
                continue

            # Extract the "FOCUS YOUR ANALYSIS ON" section from each domain prompt
            focus_section = self._extract_focus_section(domain_prompt, domain)
            if focus_section:
                prompt_parts.append(f"### {domain}\n{focus_section}\n")
                sections.append(domain)

        # Add integration instruction
        prompt_parts.append("## INTEGRATION INSTRUCTION\n")
        prompt_parts.append(
            f"Synthesize insights from ALL of the above domains into a coherent macro memo. "
            f"The relative importance of each domain is: "
            f"{', '.join(f'{d}: {w:.0%}' for d, w in weights.items())}. "
            f"Cross-reference between domains where causal links exist "
            f"(e.g., how Liquidity conditions affect Credit spreads, "
            f"how Currency strength impacts Inflation dynamics).\n"
        )

        prompt_parts.append(
            "CRITICAL RULES:\n"
            "- Every claim must reference specific evidence from the structured input\n"
            "- Address the interaction between domains, not just each in isolation\n"
            "- Write like Bridgewater Daily Observations — cross-domain synthesis is key\n"
            "- Output as structured JSON matching the ResearchMemo schema"
        )

        return "\n".join(prompt_parts), sections, True

    @staticmethod
    def _extract_focus_section(domain_prompt: str, domain: str) -> str:
        """Extract the FOCUS section from a domain prompt."""
        lines = domain_prompt.split("\n")
        in_focus = False
        focus_lines = []

        for line in lines:
            if "FOCUS YOUR ANALYSIS ON" in line.upper():
                in_focus = True
                continue
            if in_focus:
                if line.strip().startswith("CRITICAL") or line.strip().startswith("Output as"):
                    break
                if line.strip():
                    focus_lines.append(line.strip())

        return "\n".join(focus_lines) if focus_lines else ""

    def _explain_match(self, domain: str, regime_result: dict) -> str:
        """Explain why a domain was selected."""
        rules = DOMAIN_RULES.get(domain, {})
        triggers = rules.get("triggers", {})
        reasons = []

        regime_label = regime_result.get("regime_label", regime_result.get("regime_type", ""))
        if regime_label in triggers.get("regime_labels", []):
            reasons.append(f"regime={regime_label}")

        if regime_result.get("growth_phase") in triggers.get("growth_phase", []):
            reasons.append(f"growth={regime_result['growth_phase']}")
        if regime_result.get("inflation_regime") in triggers.get("inflation_regime", []):
            reasons.append(f"inflation={regime_result['inflation_regime']}")
        if regime_result.get("monetary_stance") in triggers.get("monetary_stance", []):
            reasons.append(f"policy={regime_result['monetary_stance']}")
        if regime_result.get("credit_cycle") in triggers.get("credit_cycle", []):
            reasons.append(f"credit={regime_result['credit_cycle']}")
        if regime_result.get("dollar_regime") in triggers.get("dollar_regime", []):
            reasons.append(f"dollar={regime_result['dollar_regime']}")
        if regime_result.get("volatility_regime") in triggers.get("volatility_regime", []):
            reasons.append(f"vol={regime_result['volatility_regime']}")

        return ", ".join(reasons) if reasons else "default"

    def _fallback_prompt(self) -> RoutedPrompt:
        """Fallback when no valid regime data is available."""
        return RoutedPrompt(
            selected_domains=["Growth"],
            rationale="No regime data available — defaulting to Growth domain",
            regime_label="unknown",
            regime_confidence=0.0,
            system_prompt=self._generic_prompt(),
            domain_weights={"Growth": 0.5},
            is_hybrid=False,
        )

    @staticmethod
    def _generic_prompt() -> str:
        """Legacy generic prompt — used only as absolute fallback."""
        return """You are a senior macro strategist at a top-tier hedge fund.
Your task is to synthesize structured reasoning outputs into a professional institutional research memo.

CRITICAL RULES:
1. You receive ONLY pre-computed structured reasoning results. Do NOT ask for raw data.
2. Every claim you make must reference specific evidence items from the structured input.
3. Write like Bridgewater Daily Observations or Soros's Alchemy of Finance.
4. Be precise, probabilistic, and specifically counter your own thesis.
5. Output as structured JSON matching the ResearchMemo schema.

Output valid JSON with: executive_summary, one_sentence_view, regime_detail,
market_consensus, our_view_vs_consensus, evidence_summary, key_evidence_supporting,
key_evidence_contradicting, counter_arguments, key_risks, predictions,
trading_implication, favored_assets, unfavored_assets, highest_conviction_trade,
invalidation_conditions, open_questions, data_to_watch, full_memo_text.

Think step by step, but output ONLY the JSON."""
