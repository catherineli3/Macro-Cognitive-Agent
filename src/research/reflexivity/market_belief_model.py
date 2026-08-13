"""MarketBeliefModel — Tracks formation and evolution of market beliefs.

Core concept (Soros): Market participants operate with imperfect knowledge.
Their collective beliefs form a "participant bias" that can become self-validating
when price action confirms the belief.

This module:
    1. Creates MarketBelief objects from market data and narratives
    2. Tracks belief evolution over time (strengthening, weakening, breaking)
    3. Detects when beliefs become "extreme" (crowded/consensus/fragile)
    4. Measures vulnerability to disconfirmation
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.research.reflexivity.schemas import MarketBelief
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Pre-defined belief archetypes ────────────────────────────────────────
# Each archetype has a reinforcement mechanism — how price confirms the belief

BELIEF_ARCHETYPES: dict[str, dict] = {
    "fed_cutting": {
        "category": "monetary",
        "reinforcement": "Bond prices rise (yields fall) → confirms rate cut expectation → more long positioning → yields fall further",
        "vulnerability": 0.7,  # Highly fragile to data
    },
    "fed_hiking": {
        "category": "monetary",
        "reinforcement": "Bond yields rise → confirms tightening expectation → short duration trade → yields rise further",
        "vulnerability": 0.5,
    },
    "soft_landing": {
        "category": "growth",
        "reinforcement": "Equity rallies → wealth effect → consumer spending → GDP grows → equity rallies more",
        "vulnerability": 0.6,
    },
    "hard_landing": {
        "category": "growth",
        "reinforcement": "Equity sells off → wealth destruction → spending cuts → GDP contracts → equity sells off more",
        "vulnerability": 0.4,
    },
    "inflation_persistent": {
        "category": "inflation",
        "reinforcement": "CPI above target → inflation expectations rise → wage demands → CPI stays high → expectations entrenched",
        "vulnerability": 0.3,
    },
    "inflation_transitory": {
        "category": "inflation",
        "reinforcement": "CPI moderates → inflation expectations fall → wage demands ease → CPI falls further",
        "vulnerability": 0.8,  # Very fragile — one hot CPI print kills it
    },
    "us_exceptionalism": {
        "category": "structural",
        "reinforcement": "DXY strengthens → capital flows to US → US outperforms → DXY strengthens more",
        "vulnerability": 0.5,
    },
    "dollar_decline": {
        "category": "structural",
        "reinforcement": "DXY weakens → EM benefits → capital flows out of US → DXY weakens more",
        "vulnerability": 0.6,
    },
    "ai_bubble": {
        "category": "structural",
        "reinforcement": "AI stocks rally → narrative of 'transformational tech' → retail/institutional FOMO → AI stocks rally more",
        "vulnerability": 0.75,  # Very fragile — any tech earnings miss
    },
    "commodity_supercycle": {
        "category": "growth",
        "reinforcement": "Commodities rally → inflation fears → real asset demand → commodities rally more",
        "vulnerability": 0.55,
    },
    "risk_on_everything": {
        "category": "risk",
        "reinforcement": "VIX falls → risk appetite rises → more buying → VIX falls further → 'TINA' narrative",
        "vulnerability": 0.65,
    },
    "risk_off_flight": {
        "category": "risk",
        "reinforcement": "VIX spikes → risk reduction → forced selling → VIX spikes more → margin calls",
        "vulnerability": 0.35,
    },
}

# ── Stage transition rules ────────────────────────────────────────────────


def _determine_belief_stage(consensus: float, evidence: float, vulnerability: float) -> str:
    """Determine belief lifecycle stage based on metrics."""
    if consensus < 0.2:
        return "forming"
    elif evidence < -0.3 and vulnerability > 0.6:
        return "challenged"
    elif consensus > 0.7 and vulnerability > 0.6:
        return "extreme"
    elif evidence < -0.5:
        return "broken"
    elif consensus > 0.5:
        return "consensus"
    else:
        return "forming"


# ═══════════════════════════════════════════════════════════════════════════
# MarketBeliefModel
# ═══════════════════════════════════════════════════════════════════════════


class MarketBeliefModel:
    """Tracks formation, evolution, and fragility of market beliefs.

    Usage:
        model = MarketBeliefModel()
        belief = model.identify_belief(market_data, narratives)
        updated = model.update_belief(belief, new_data)
        fragile = model.get_most_fragile_beliefs(beliefs, top_n=3)
    """

    def __init__(self):
        self._belief_history: dict[str, list[MarketBelief]] = {}

    # ── Public API ────────────────────────────────────────────────────

    def identify_beliefs(
        self,
        market_data: dict,
        dominant_narrative: str = "",
        narrative_objects: list = None,
    ) -> list[MarketBelief]:
        """Identify active market beliefs from current data.

        Matches market conditions against belief archetypes to detect
        which collective beliefs are currently active.

        Args:
            market_data: Dict of market indicators (vix, dxy, rates, etc.)
            dominant_narrative: The dominant narrative title/description
            narrative_objects: Optional narrative objects for belief grounding

        Returns:
            List of active MarketBelief objects
        """
        beliefs = []
        now = datetime.now(UTC).isoformat()
        narrative_text = (
            dominant_narrative + " " + " ".join(str(n) for n in (narrative_objects or [])[:3])
        ).lower()

        # ── Match monetary beliefs ──
        if (
            "hiking" in narrative_text
            or "tightening" in narrative_text
            or "hawkish" in narrative_text
        ):
            beliefs.append(self._build_belief("fed_hiking", market_data, now))
        if "cutting" in narrative_text or "easing" in narrative_text or "dovish" in narrative_text:
            beliefs.append(self._build_belief("fed_cutting", market_data, now))

        # ── Match growth beliefs ──
        vix = float(market_data.get("vix", 0))
        spx_ytd = float(market_data.get("spx_ytd", 0) or market_data.get("nasdaq_ytd", 0))
        _hyg = float(market_data.get("hyg_spread", 0))

        if spx_ytd > 15 and vix < 18:
            beliefs.append(self._build_belief("soft_landing", market_data, now))
        if spx_ytd < -10 or vix > 30:
            beliefs.append(self._build_belief("hard_landing", market_data, now))

        # ── Match inflation beliefs ──
        cpi = float(market_data.get("cpi_yoy", 0))
        if cpi > 4:
            beliefs.append(self._build_belief("inflation_persistent", market_data, now))
        elif cpi < 2.5:
            beliefs.append(self._build_belief("inflation_transitory", market_data, now))

        # ── Match dollar beliefs ──
        dxy = float(market_data.get("dxy", 0))
        if dxy > 103:
            beliefs.append(self._build_belief("us_exceptionalism", market_data, now))
        elif dxy < 95:
            beliefs.append(self._build_belief("dollar_decline", market_data, now))

        # ── Match risk beliefs ──
        if vix < 15 and spx_ytd > 0:
            beliefs.append(self._build_belief("risk_on_everything", market_data, now))
        elif vix > 25:
            beliefs.append(self._build_belief("risk_off_flight", market_data, now))

        # ── Match structural beliefs ──
        nasdaq_ytd = float(market_data.get("nasdaq_ytd", 0))
        if nasdaq_ytd > 30 and "ai" in narrative_text:
            beliefs.append(self._build_belief("ai_bubble", market_data, now))

        oil = float(market_data.get("oil", 0))
        gold = float(market_data.get("gold", 0))
        if oil > 90 or gold > 2000:
            beliefs.append(self._build_belief("commodity_supercycle", market_data, now))

        # ── Record history ──
        key = datetime.now(UTC).strftime("%Y%m%d")
        self._belief_history.setdefault(key, []).extend(beliefs)

        logger.info("Identified %d active market beliefs on %s", len(beliefs), key)
        return beliefs

    def _build_belief(self, archetype_key: str, market_data: dict, timestamp: str) -> MarketBelief:
        """Build a MarketBelief from an archetype template."""
        archetype = BELIEF_ARCHETYPES.get(archetype_key, {})

        # Compute evidence support from market data
        evidence = self._compute_evidence_support(archetype_key, market_data)

        # Compute consensus level
        vix = float(market_data.get("vix", 0))
        if vix < 15:
            consensus = 0.7  # Low vol = high consensus
        elif vix > 30:
            consensus = 0.3  # High vol = low consensus
        else:
            consensus = 0.5

        vulnerability = archetype.get("vulnerability", 0.5)
        stage = _determine_belief_stage(consensus, evidence, vulnerability)

        return MarketBelief(
            belief_id=f"{archetype_key}-{timestamp[:10]}",
            title=archetype_key.replace("_", " ").title(),
            description=archetype.get("reinforcement", "")[:200],
            category=archetype.get("category", ""),
            strength=max(0.1, evidence * 0.5 + consensus * 0.5),
            consensus_level=consensus,
            evidence_support=evidence,
            is_self_reinforcing=evidence > 0.3 and consensus > 0.4,
            reinforcement_mechanism=archetype.get("reinforcement", ""),
            vulnerability_to_disconfirmation=vulnerability,
            first_observed=timestamp,
            last_updated=timestamp,
            stage=stage,
            crowding_risk=0.7 if stage == "extreme" else (0.5 if stage == "consensus" else 0.2),
            reversal_magnitude_estimate=(
                "severe"
                if vulnerability > 0.7 and stage == "extreme"
                else ("moderate" if vulnerability > 0.4 else "small")
            ),
        )

    def update_belief(self, belief: MarketBelief, new_market_data: dict) -> MarketBelief:
        """Update belief metrics with new market data.

        Tracks belief evolution — strengthening or weakening over time.
        """
        now = datetime.now(UTC).isoformat()
        new_evidence = self._compute_evidence_support(
            belief.belief_id.split("-")[0], new_market_data
        )

        # Update
        updated = MarketBelief(
            belief_id=belief.belief_id,
            title=belief.title,
            description=belief.description,
            category=belief.category,
            strength=belief.strength * 0.7 + new_evidence * 0.3,
            consensus_level=belief.consensus_level,  # Would need external data
            evidence_support=new_evidence,
            is_self_reinforcing=new_evidence > 0.3 and belief.consensus_level > 0.4,
            reinforcement_mechanism=belief.reinforcement_mechanism,
            vulnerability_to_disconfirmation=belief.vulnerability_to_disconfirmation,
            first_observed=belief.first_observed,
            last_updated=now,
            stage=_determine_belief_stage(
                belief.consensus_level, new_evidence, belief.vulnerability_to_disconfirmation
            ),
            crowding_risk=belief.crowding_risk,
            reversal_magnitude_estimate=belief.reversal_magnitude_estimate,
        )

        return updated

    def get_most_fragile_beliefs(
        self, beliefs: list[MarketBelief], top_n: int = 3
    ) -> list[MarketBelief]:
        """Return beliefs most vulnerable to disconfirmation."""
        fragile = sorted(
            beliefs,
            key=lambda b: (b.vulnerability_to_disconfirmation * b.crowding_risk),
            reverse=True,
        )
        return fragile[:top_n]

    def detect_belief_break(
        self,
        old_belief: MarketBelief,
        new_evidence: float,
        threshold: float = -0.5,
    ) -> bool:
        """Check if a belief has been broken by new evidence."""
        return new_evidence < threshold and old_belief.vulnerability_to_disconfirmation > 0.5

    # ── Internal: Evidence computation ────────────────────────────────

    def _compute_evidence_support(self, archetype_key: str, market_data: dict) -> float:
        """Compute how well market data supports a given belief archetype.

        Returns:
            Score from -1 (strongly contradicted) to +1 (strongly supported)
        """
        signals = []

        vix = float(market_data.get("vix", 0))
        dxy = float(market_data.get("dxy", 0))
        us10y = float(market_data.get("us10y", 0))
        us2y = float(market_data.get("us2y", 0))
        spx_ytd = float(market_data.get("spx_ytd", 0) or market_data.get("nasdaq_ytd", 0))
        cpi = float(market_data.get("cpi_yoy", 0))
        hyg = float(market_data.get("hyg_spread", 0))
        gold = float(market_data.get("gold", 0))
        oil = float(market_data.get("oil", 0))

        if archetype_key == "fed_cutting":
            if us10y < us2y:
                signals.append(0.6)  # Inverted curve
            if cpi < 3:
                signals.append(0.8)
            if vix > 25:
                signals.append(0.4)  # Market stress = cut pressure
            if cpi > 5:
                signals.append(-0.7)
            if dxy > 105:
                signals.append(-0.3)

        elif archetype_key == "fed_hiking":
            if cpi > 4:
                signals.append(0.7)
            if dxy > 102:
                signals.append(0.5)
            if us10y > 4:
                signals.append(0.6)
            if vix > 30:
                signals.append(-0.4)  # Stress = pause
            if cpi < 2.5:
                signals.append(-0.6)

        elif archetype_key == "soft_landing":
            if spx_ytd > 10:
                signals.append(0.6)
            if vix < 18:
                signals.append(0.5)
            if cpi < 3.5:
                signals.append(0.7)
            if hyg < 400:
                signals.append(0.5)
            if spx_ytd < -5:
                signals.append(-0.6)
            if vix > 25:
                signals.append(-0.7)

        elif archetype_key == "hard_landing":
            if spx_ytd < -10:
                signals.append(0.6)
            if vix > 25:
                signals.append(0.7)
            if hyg > 500:
                signals.append(0.6)
            if spx_ytd > 15:
                signals.append(-0.7)
            if vix < 15:
                signals.append(-0.6)

        elif archetype_key == "inflation_persistent":
            if cpi > 5:
                signals.append(0.8)
            if oil > 80:
                signals.append(0.5)
            if gold > 1800:
                signals.append(0.4)
            if cpi < 3:
                signals.append(-0.8)
            if us10y < 3:
                signals.append(-0.5)

        elif archetype_key == "inflation_transitory":
            if cpi < 3.5:
                signals.append(0.7)
            if cpi > 5:
                signals.append(-0.9)
            if oil > 90:
                signals.append(-0.5)

        elif archetype_key == "us_exceptionalism":
            if dxy > 100:
                signals.append(0.5)
            if spx_ytd > 10:
                signals.append(0.5)
            if us10y > 3.5:
                signals.append(0.4)
            if dxy < 95:
                signals.append(-0.7)

        elif archetype_key == "dollar_decline":
            if dxy < 98:
                signals.append(0.6)
            if gold > 1800:
                signals.append(0.5)
            if dxy > 105:
                signals.append(-0.8)

        elif archetype_key == "ai_bubble":
            # Would need sector-specific data; approximate
            if spx_ytd > 25:
                signals.append(0.5)
            if vix < 15:
                signals.append(0.4)
            if vix > 25:
                signals.append(-0.5)

        elif archetype_key == "commodity_supercycle":
            if oil > 85:
                signals.append(0.6)
            if gold > 1900:
                signals.append(0.5)
            if cpi > 4:
                signals.append(0.5)
            if dxy > 105:
                signals.append(-0.4)

        elif archetype_key == "risk_on_everything":
            if vix < 15:
                signals.append(0.7)
            if spx_ytd > 15:
                signals.append(0.6)
            if hyg < 350:
                signals.append(0.5)
            if vix > 20:
                signals.append(-0.6)

        elif archetype_key == "risk_off_flight":
            if vix > 25:
                signals.append(0.7)
            if hyg > 500:
                signals.append(0.6)
            if spx_ytd < 0:
                signals.append(0.5)
            if vix < 15:
                signals.append(-0.7)

        if not signals:
            return 0.0
        return sum(signals) / len(signals)
