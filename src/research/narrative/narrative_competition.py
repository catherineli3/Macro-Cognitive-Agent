"""Narrative Competition Engine (V3.2).

For the same market state, generates multiple competing narratives with
probability-weighted scoring — enabling multi-hypothesis competition
instead of single-narrative determinism.

Philosophy:
    "Not one narrative → competing narratives → Hypothesis Engine"

Example:
    Input: DXY↑, 10Y↑, HYG↓, Gold↑
    Output:
        Narrative A: "Inflation shock" — P=0.35
        Narrative B: "Debt credibility" — P=0.25
        Narrative C: "Fed tightening" — P=0.40
"""

from __future__ import annotations

from typing import Any, Optional

from src.research.narrative.schemas import (
    Narrative,
    NarrativeObject,
    NarrativeCompetitionResult,
)
from src.research.narrative.narrative_reasoner import NarrativeReasoner
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Competing narrative templates: each market signal → competing interpretations ─

COMPETITION_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    # DXY and yields rising together:
    #   Could be: hawkish Fed, inflation shock, or US exceptionalism
    "usd_yields_up": [
        {
            "title": "Fed tightening is driving USD and yields higher",
            "description": (
                "Hawkish Fed stance and rate hike expectations push DXY and Treasury "
                "yields higher. This is a monetary policy-driven tightening cycle."
            ),
            "category": "monetary",
            "base_probability": 0.40,
            "theme": "tightening",
        },
        {
            "title": "Inflation shock is forcing yields up and strengthening USD",
            "description": (
                "Persistent inflation surprises force the bond market to reprice, "
                "driving real yields higher. DXY strengthens on rate differentials, "
                "not just policy — this is an inflation cycle, not just a Fed cycle."
            ),
            "category": "inflation",
            "base_probability": 0.35,
            "theme": "elevated",
        },
        {
            "title": "US exceptionalism: capital inflows drive USD and yields",
            "description": (
                "Global capital flows into US assets on growth divergence. DXY and "
                "yields rise together because the US is the best house in a bad "
                "neighborhood — not because of Fed policy or inflation."
            ),
            "category": "growth",
            "base_probability": 0.25,
            "theme": "acceleration",
        },
    ],
    # Risk-off with gold up:
    #   Could be: geopolitical risk, stagflation, or dollar credibility
    "risk_off_gold_up": [
        {
            "title": "Geopolitical risk premium drives safe-haven demand",
            "description": (
                "Elevated geopolitical uncertainty triggers flight to safety. Gold "
                "benefits as the ultimate safe haven, while equities sell off on "
                "uncertainty premium. This is a transient risk event."
            ),
            "category": "risk_appetite",
            "base_probability": 0.35,
            "theme": "risk_off",
        },
        {
            "title": "Stagflation risk: growth fears meet persistent inflation",
            "description": (
                "Gold rising while equities fall signals stagflation alarm. Growth "
                "is slowing but inflation remains sticky — the worst of both worlds "
                "for risk assets. This is structural, not transitory."
            ),
            "category": "inflation",
            "base_probability": 0.40,
            "theme": "elevated",
        },
        {
            "title": "Dollar credibility crisis: de-dollarization bid for gold",
            "description": (
                "Central bank gold buying and BRICS de-dollarization efforts signal "
                "a structural shift in reserve currency demand. Gold rises on monetary "
                "system concerns, not just risk-off flows."
            ),
            "category": "dollar",
            "base_probability": 0.25,
            "theme": "weak",
        },
    ],
    # Tech selloff with rates stable:
    #   Could be: AI bubble, earnings risk, rotation
    "tech_selloff_stable_rates": [
        {
            "title": "AI bubble risk: speculative excess unwinding",
            "description": (
                "AI-related valuations have detached from fundamentals. The selloff "
                "reflects a bubble deflation, not a macro shock. Tech corrects as "
                "speculative positioning unwinds."
            ),
            "category": "ai_capex",
            "base_probability": 0.40,
            "theme": "bubble",
        },
        {
            "title": "Earnings disappointment signals growth peak",
            "description": (
                "Tech earnings are disappointing relative to elevated expectations. "
                "This signals that growth has peaked and the AI spending cycle may "
                "not deliver the ROI markets have priced in."
            ),
            "category": "growth",
            "base_probability": 0.35,
            "theme": "slowdown",
        },
        {
            "title": "Sector rotation: rebalancing from growth to value",
            "description": (
                "Markets are rotating from extended growth/tech positions into value "
                "and cyclicals. This is a healthy rotation, not a crisis — rates "
                "stable confirms this is positioning-driven."
            ),
            "category": "risk_appetite",
            "base_probability": 0.25,
            "theme": "neutral",
        },
    ],
    # Credit spreads widening:
    #   Could be: recession signal, liquidity stress, idiosyncratic
    "credit_spreads_wider": [
        {
            "title": "Recession signal: credit markets pricing downturn",
            "description": (
                "Widening credit spreads are the market's leading recession indicator. "
                "Corporate bond investors are pricing higher default risk, signaling "
                "economic deterioration ahead."
            ),
            "category": "growth",
            "base_probability": 0.40,
            "theme": "recession",
        },
        {
            "title": "Liquidity stress: funding markets under pressure",
            "description": (
                "Credit spread widening reflects liquidity conditions, not default "
                "risk. Funding markets are tightening, forcing de-leveraging — this "
                "is a plumbing issue, not a solvency issue."
            ),
            "category": "liquidity",
            "base_probability": 0.35,
            "theme": "tight",
        },
        {
            "title": "Idiosyncratic credit events, not systemic risk",
            "description": (
                "Specific credit events (single names, sectors) are driving spreads "
                "wider. This is contained, not systemic — the broader credit market "
                "remains healthy."
            ),
            "category": "credit",
            "base_probability": 0.25,
            "theme": "stress",
        },
    ],
    # Yield curve steepening:
    #   Could be: soft landing, fiscal risk, inflation expectations
    "curve_steepening": [
        {
            "title": "Soft landing: curve normalizes on growth optimism",
            "description": (
                "Yield curve steepening from inversion signals the market pricing "
                "a soft landing. Long-end yields rise on growth expectations, while "
                "the front end stabilizes on rate cut hopes."
            ),
            "category": "growth",
            "base_probability": 0.40,
            "theme": "acceleration",
        },
        {
            "title": "Fiscal sustainability concerns drive term premium",
            "description": (
                "Long-end yields rising on fiscal sustainability concerns, not growth. "
                "Rising debt/GDP, deficits, and supply pressure are pushing the term "
                "premium higher — a fiscal risk signal."
            ),
            "category": "liquidity",
            "base_probability": 0.35,
            "theme": "tight",
        },
        {
            "title": "Inflation expectations de-anchoring at the long end",
            "description": (
                "Steepening driven by rising inflation expectations embedded in "
                "long-end yields. The market is pricing a higher inflation regime, "
                "not just a growth recovery."
            ),
            "category": "inflation",
            "base_probability": 0.25,
            "theme": "elevated",
        },
    ],
    # Commodities rally:
    #   Could be: supply shock, demand recovery, dollar weakness
    "commodities_rally": [
        {
            "title": "Supply constraints driving commodity super-cycle",
            "description": (
                "Structural under-investment in commodity supply is creating a "
                "super-cycle. Prices rise on supply scarcity, not demand — this "
                "is secular, not cyclical."
            ),
            "category": "inflation",
            "base_probability": 0.40,
            "theme": "elevated",
        },
        {
            "title": "Global demand recovery boosting commodities",
            "description": (
                "Synchronized global growth recovery is driving commodity demand. "
                "China re-opening, EM industrialization, and infrastructure spending "
                "create a cyclical demand tailwind."
            ),
            "category": "growth",
            "base_probability": 0.35,
            "theme": "acceleration",
        },
        {
            "title": "Dollar weakness inflating commodity prices",
            "description": (
                "Commodity prices are rising primarily due to USD depreciation. "
                "This is a currency effect, not a fundamental supply-demand shift. "
                "Real commodity demand is unchanged."
            ),
            "category": "dollar",
            "base_probability": 0.25,
            "theme": "weak",
        },
    ],
    # VIX elevated, everything selling off:
    #   Could be: deleveraging cascade, regime change, margin call
    "broad_selloff": [
        {
            "title": "Systematic deleveraging cascade underway",
            "description": (
                "Elevated VIX triggers systematic strategy de-risking (risk parity, "
                "CTAs, vol-targeting). The selloff is mechanical, not fundamental — "
                "forced selling begets more selling."
            ),
            "category": "risk_appetite",
            "base_probability": 0.40,
            "theme": "risk_off",
        },
        {
            "title": "Regime change: markets pricing structural shift",
            "description": (
                "This is not a pullback but a regime change. Markets are repricing "
                "for a higher-rate, higher-vol, lower-growth world. The old playbook "
                "no longer works."
            ),
            "category": "monetary",
            "base_probability": 0.35,
            "theme": "tightening",
        },
        {
            "title": "Margin call / liquidation event",
            "description": (
                "Leveraged positions being force-liquidated across asset classes. "
                "This is a technical event driven by positioning extremes — once "
                "liquidation completes, markets stabilize."
            ),
            "category": "liquidity",
            "base_probability": 0.25,
            "theme": "tight",
        },
    ],
}


def _match_market_pattern(
    state_vector: dict[str, Any],
) -> Optional[str]:
    """Match current market state to a known competition template pattern.

    Returns the template key (e.g. "usd_yields_up") or None.
    """
    if not state_vector:
        return None

    # Extract directional signals
    dv = _extract_directions(state_vector)

    has_risk_off = dv.get("risk_appetite") == "risk_off"
    has_gold_up = dv.get("gold") == "positive" or dv.get("commodities") == "positive"
    has_yields_up = dv.get("rates") == "rising"
    has_dxy_up = dv.get("dollar") == "strong"
    has_credit_wide = dv.get("credit") == "tightening"
    has_tech_down = dv.get("tech") == "negative"
    has_rates_stable = dv.get("rates") in ("stable", "neutral")
    has_curve_steep = dv.get("curve") == "steepening"
    has_commodities_up = dv.get("commodities") == "positive"

    # Pattern: DXY↑ + Yields↑
    if has_dxy_up and has_yields_up:
        return "usd_yields_up"

    # Pattern: Risk-off + Gold up
    if has_risk_off and has_gold_up:
        return "risk_off_gold_up"

    # Pattern: Tech selloff + Stable rates
    if has_tech_down and has_rates_stable:
        return "tech_selloff_stable_rates"

    # Pattern: Credit spreads wider
    if has_credit_wide:
        return "credit_spreads_wider"

    # Pattern: Yield curve steepening
    if has_curve_steep:
        return "curve_steepening"

    # Pattern: Commodities rally
    if has_commodities_up:
        return "commodities_rally"

    # Pattern: Broad selloff (VIX elevated)
    vix_up = dv.get("volatility") == "elevated" or dv.get("risk_appetite") == "risk_off"
    broad_risk_off = has_risk_off and not has_gold_up
    if vix_up or broad_risk_off:
        return "broad_selloff"

    return None


def _extract_directions(state_vector: dict[str, Any]) -> dict[str, str]:
    """Extract directional signals from state_vector."""
    directions: dict[str, str] = {}
    for dim, data in state_vector.items():
        if isinstance(data, dict):
            direction = data.get("direction", "")
            score = data.get("score", 0)
            if direction and abs(score) > 0.3:
                directions[dim.lower().replace(" ", "_")] = direction.lower()
    return directions


class NarrativeCompetition:
    """V3.2: Generate multiple competing narratives for the same market state.

    Instead of producing a single narrative, this engine generates 2-4 competing
    interpretations of the same data. Each narrative gets a probability weight,
    enabling the Hypothesis Engine to test multiple scenarios simultaneously.

    Usage:
        competition = NarrativeCompetition()
        result = competition.compete(state_vector, regime, existing_narratives)
        # result.narratives = [NarrativeA (0.40), NarrativeB (0.35), NarrativeC (0.25)]
    """

    def __init__(self, reasoner: NarrativeReasoner | None = None):
        self.reasoner = reasoner or NarrativeReasoner()
        self._competition_count = 0

    # ── Main API ─────────────────────────────────────────────────────

    def compete(
        self,
        state_vector: dict[str, Any],
        regime: str = "",
        existing_narratives: list[Narrative] | None = None,
        mental_model_outputs: list[dict] | None = None,
        min_narratives: int = 2,
        max_narratives: int = 4,
    ) -> NarrativeCompetitionResult:
        """Generate competing narratives for the current market state.

        Args:
            state_vector: Current macro state dimensions
            regime: Current regime label
            existing_narratives: Pre-detected narratives to reason about
            mental_model_outputs: Mental model analysis results
            min_narratives: Minimum competing narratives to generate
            max_narratives: Maximum competing narratives to generate

        Returns:
            NarrativeCompetitionResult with ordered narratives by probability.
        """
        self._competition_count += 1

        # Step 1: Match market pattern to competition template
        pattern_key = _match_market_pattern(state_vector)
        templates = COMPETITION_TEMPLATES.get(pattern_key, [])

        if not templates:
            # Fallback: create generic competition from existing narratives
            return self._fallback_compete(
                state_vector, regime, existing_narratives, mental_model_outputs
            )

        # Step 2: Build NarrativeObjects from templates, adjusted by state
        narrative_objects: list[NarrativeObject] = []

        for tpl in templates[:max_narratives]:
            # Create a minimal Narrative for the Reasoner
            narrative = Narrative(
                title=tpl["title"],
                description=tpl["description"],
                category=tpl.get("category", "monetary"),
                score=tpl.get("base_probability", 0.33),
                source_signals=self._extract_source_signals(state_vector, tpl),
            )

            # Reason → NarrativeObject
            nar_obj = self.reasoner.reason(
                narrative=narrative,
                state_vector=state_vector,
                regime=regime,
                mental_model_outputs=mental_model_outputs,
            )

            # Apply probability with regime adjustment
            nar_obj.probability = self._adjust_probability(
                tpl.get("base_probability", 0.33),
                nar_obj.regime_score,
                nar_obj.evidence_ratio,
            )

            narrative_objects.append(nar_obj)

        # Step 3: Normalize probabilities to sum to 1.0
        self._normalize_probabilities(narrative_objects)

        # Step 4: Sort by probability descending
        narrative_objects.sort(key=lambda n: n.probability, reverse=True)

        # Step 5: Set competing IDs
        all_ids = [n.id for n in narrative_objects]
        for n in narrative_objects:
            n.competing_narrative_ids = [i for i in all_ids if i != n.id]

        # Ensure minimum count
        if len(narrative_objects) < min_narratives:
            extra = self._generate_extra_narratives(
                state_vector, regime, narrative_objects, mental_model_outputs,
                needed=min_narratives - len(narrative_objects),
            )
            narrative_objects.extend(extra)
            self._normalize_probabilities(narrative_objects)
            narrative_objects.sort(key=lambda n: n.probability, reverse=True)

        # Trim to max
        narrative_objects = narrative_objects[:max_narratives]

        # Build summary
        state_summary = self._build_state_summary(state_vector, pattern_key)

        result = NarrativeCompetitionResult(
            market_state_summary=state_summary,
            regime=regime,
            narratives=narrative_objects,
        )

        logger.info(
            "Narrative competition: %d narratives for pattern '%s' "
            "(dominant: '%s', P=%.0f%%)",
            len(result.narratives), pattern_key or "auto",
            result.dominant.title if result.dominant else "none",
            result.dominant.probability * 100 if result.dominant else 0,
        )

        return result

    def _fallback_compete(
        self,
        state_vector: dict[str, Any],
        regime: str,
        existing_narratives: list[Narrative] | None,
        mental_model_outputs: list[dict] | None,
    ) -> NarrativeCompetitionResult:
        """Fallback competition when no pattern matches."""
        nar_objects: list[NarrativeObject] = []

        if existing_narratives:
            for n in existing_narratives[:3]:
                obj = self.reasoner.reason(
                    narrative=n,
                    state_vector=state_vector,
                    regime=regime,
                    mental_model_outputs=mental_model_outputs,
                )
                obj.probability = 1.0 / len(existing_narratives[:3])
                nar_objects.append(obj)
        else:
            # Create a single neutral narrative
            neutral = Narrative(
                title="Market in transition — no clear narrative dominance",
                description="Current signals are mixed with no single driver dominating.",
                category="neutral",
                score=0.5,
            )
            obj = self.reasoner.reason(
                narrative=neutral,
                state_vector=state_vector,
                regime=regime,
            )
            obj.probability = 1.0
            nar_objects.append(obj)

        self._normalize_probabilities(nar_objects)
        all_ids = [n.id for n in nar_objects]
        for n in nar_objects:
            n.competing_narrative_ids = [i for i in all_ids if i != n.id]

        return NarrativeCompetitionResult(
            market_state_summary=self._extract_state_summary(state_vector),
            regime=regime,
            narratives=nar_objects,
        )

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_source_signals(
        state_vector: dict[str, Any],
        template: dict[str, Any],
    ) -> list[str]:
        """Extract relevant signals from state_vector for a template."""
        signals: list[str] = []
        theme = template.get("theme", "")

        for dim, data in state_vector.items():
            if isinstance(data, dict):
                direction = data.get("direction", "")
                score = data.get("score", 0)
                if abs(score) > 0.2:
                    signals.append(f"{dim}: {direction} (score={score:.2f})")

        return signals[:8]

    @staticmethod
    def _adjust_probability(
        base_prob: float,
        regime_score: float,
        evidence_ratio: float,
    ) -> float:
        """Adjust base probability by regime fit and evidence balance.

        - Strong regime fit (>0.8) → +15% boost
        - Weak regime fit (<0.4) → -20% penalty
        - Strong evidence (>0.7 ratio) → +10% boost
        """
        adjusted = base_prob

        if regime_score > 0.8:
            adjusted *= 1.15
        elif regime_score < 0.4:
            adjusted *= 0.80

        if evidence_ratio > 0.7:
            adjusted *= 1.10
        elif evidence_ratio < 0.4:
            adjusted *= 0.85

        return max(0.05, min(adjusted, 0.95))

    @staticmethod
    def _normalize_probabilities(narratives: list[NarrativeObject]) -> None:
        """Normalize probabilities to sum to 1.0."""
        total = sum(n.probability for n in narratives)
        if total > 0:
            for n in narratives:
                n.probability = n.probability / total

    def _generate_extra_narratives(
        self,
        state_vector: dict[str, Any],
        regime: str,
        existing: list[NarrativeObject],
        mental_model_outputs: list[dict] | None,
        needed: int,
    ) -> list[NarrativeObject]:
        """Generate additional narratives to meet minimum count."""
        extras: list[NarrativeObject] = []
        existing_titles = {n.title for n in existing}

        # Try templates from other patterns
        for pattern, templates in COMPETITION_TEMPLATES.items():
            if len(extras) >= needed:
                break
            for tpl in templates:
                if len(extras) >= needed:
                    break
                if tpl["title"] in existing_titles:
                    continue

                narrative = Narrative(
                    title=tpl["title"],
                    description=tpl["description"],
                    category=tpl.get("category", "monetary"),
                    score=0.2,  # Lower base since not pattern-matched
                )
                obj = self.reasoner.reason(
                    narrative=narrative,
                    state_vector=state_vector,
                    regime=regime,
                    mental_model_outputs=mental_model_outputs,
                )
                obj.probability = 0.1  # Low probability for non-matched
                extras.append(obj)

        return extras

    @staticmethod
    def _extract_state_summary(state_vector: dict[str, Any]) -> str:
        """Build a text summary of the current market state."""
        parts: list[str] = []
        for dim, data in state_vector.items():
            if isinstance(data, dict):
                direction = data.get("direction", "")
                if direction:
                    parts.append(f"{dim}: {direction}")
        return "; ".join(parts) if parts else "Mixed signals"

    @staticmethod
    def _build_state_summary(
        state_vector: dict[str, Any],
        pattern_key: str | None,
    ) -> str:
        """Build a descriptive market state summary."""
        base = NarrativeCompetition._extract_state_summary(state_vector)
        if pattern_key:
            pattern_labels = {
                "usd_yields_up": "DXY and yields rising — USD tightening regime",
                "risk_off_gold_up": "Risk-off with gold bid — safe-haven flows dominant",
                "tech_selloff_stable_rates": "Tech under pressure with stable rates — sector-specific stress",
                "credit_spreads_wider": "Credit spreads widening — stress signal",
                "curve_steepening": "Yield curve steepening — term premium repricing",
                "commodities_rally": "Commodities rallying — supply/demand imbalance",
                "broad_selloff": "Broad-based selloff — systematic de-risking",
            }
            label = pattern_labels.get(pattern_key, pattern_key)
            return f"{label}\nSignals: {base}"

        return base

    # ── Query ─────────────────────────────────────────────────────────

    @property
    def competition_count(self) -> int:
        return self._competition_count

    @staticmethod
    def get_available_patterns() -> list[str]:
        """Return all available competition template patterns."""
        return list(COMPETITION_TEMPLATES.keys())
