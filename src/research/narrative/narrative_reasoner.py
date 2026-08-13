"""NarrativeReasoner — from Signal Detection to Narrative Reasoning (V3.2).

Transforms flat Narrative (V3.0 signal detection) into rich NarrativeObject (V3.2)
with causal chain reasoning, evidence classification, asset impact analysis,
and regime awareness.

Core capability: "解释世界" (explain the world), not just "读取世界" (read the world).
"""

from __future__ import annotations

from typing import Any

from src.research.narrative.schemas import Narrative, NarrativeObject
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Causal chain templates by category ─────────────────────────────────────
# Each maps a trigger phrase → ordered chain of causal steps

CAUSAL_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "monetary": {
        "tightening": [
            "DXY↑ + Real Yield↑",
            "→ Financial Conditions Tighten",
            "→ Risk Appetite Declines",
            "→ Equity Multiple Compression",
            "→ Risk Assets Underperform",
        ],
        "easing": [
            "DXY↓ + Real Yield↓",
            "→ Financial Conditions Ease",
            "→ Liquidity Expands",
            "→ Risk Appetite Improves",
            "→ Risk Assets Rally",
        ],
        "hawkish": [
            "Fed Hawkish Stance → Rate Expectations Rise",
            "→ Bond Yields Rise (2Y/10Y Bear Flattening)",
            "→ USD Strengthens",
            "→ EM/Commodities Under Pressure",
        ],
        "dovish": [
            "Fed Dovish Pivot → Rate Expectations Fall",
            "→ Bond Yields Decline (Bull Steepening)",
            "→ USD Weakens",
            "→ EM/Commodities Benefit",
        ],
        "default": [
            "Monetary Policy Shift → Rate Expectations Adjust",
            "→ Financial Conditions Change",
            "→ Asset Prices Re-rate",
        ],
    },
    "inflation": {
        "elevated": [
            "CPI/PCE Above Target → Inflation Expectations De-anchor",
            "→ Real Yields Rise → Bond Selloff",
            "→ Discount Rates Increase",
            "→ Growth/Momentum Multiple Compression",
            "→ Value/Cyclical Rotation",
        ],
        "moderating": [
            "Inflation Moderating → Expectations Re-anchor",
            "→ Real Yields Stabilize/Decline",
            "→ Fed Hiking Cycle Nears End",
            "→ Rate-Sensitive Sectors Recover",
        ],
        "shock": [
            "Supply Shock → Input Costs Surge",
            "→ Margin Compression → Earnings Risk",
            "→ Defensive Rotation → Quality Premium",
        ],
        "default": [
            "Inflation Dynamics → Monetary Policy Response",
            "→ Rate Expectations Adjust",
            "→ Sector/Asset Re-pricing",
        ],
    },
    "growth": {
        "slowdown": [
            "Leading Indicators Weaken → Growth Concerns Rise",
            "→ Earnings Estimates Cut",
            "→ Defensive Rotation → Bond Bid",
            "→ Cyclical Underperformance",
        ],
        "acceleration": [
            "Activity Data Surprises → Growth Optimism",
            "→ Earnings Upgrades → Cyclical Bid",
            "→ Rotation from Defensives to Cyclicals",
            "→ Value/Cyclical Leadership",
        ],
        "recession": [
            "Inversion Deepens / Data Deteriorates → Recession Fear",
            "→ Flight to Safety → Treasury Bid",
            "→ Credit Spreads Widen → HY Underperform",
            "→ Risk-Off Across Assets",
        ],
        "default": [
            "Growth Signals → Macro Outlook Adjustment",
            "→ Sector Rotation → Asset Allocation Shift",
        ],
    },
    "liquidity": {
        "tight": [
            "Liquidity Conditions Tighten → Funding Stress",
            "→ Credit Spreads Widen",
            "→ Risk Appetite Declines",
            "→ Volatility Rises → De-risking",
        ],
        "ample": [
            "Liquidity Abundant → Funding Conditions Easy",
            "→ Carry/Spread Compression",
            "→ Risk Appetite Elevated",
            "→ Leverage Builds → Fragility Risk",
        ],
        "default": [
            "Liquidity Dynamics → Funding Conditions Shift",
            "→ Credit Market Response → Risk Repricing",
        ],
    },
    "dollar": {
        "strong": [
            "DXY Strengthens → USD Funding Tightens",
            "→ EM FX Pressure → Capital Outflows",
            "→ Commodities Under Pressure (USD-denominated)",
            "→ S&P 500 Multinational Headwinds",
        ],
        "weak": [
            "DXY Weakens → USD Funding Eases",
            "→ EM FX Relief → Capital Inflows",
            "→ Commodities Rally (USD-denominated)",
            "→ S&P 500 Multinational Tailwinds",
        ],
        "default": [
            "DXY Movement → USD Funding Conditions Shift",
            "→ Cross-Border Flow Adjustment",
            "→ EM/Commodity Repricing",
        ],
    },
    "risk_appetite": {
        "risk_on": [
            "VIX Declines → Risk Appetite Expands",
            "→ Cyclical/High Beta Outperform",
            "→ Credit Spreads Tighten",
            "→ Leverage/Positioning Increases",
        ],
        "risk_off": [
            "VIX Spikes → Risk Appetite Collapses",
            "→ Flight to Quality → UST Bid",
            "→ Credit Spreads Widen → HY Underperform",
            "→ De-leveraging Cascade",
        ],
        "default": [
            "Sentiment Shift → Risk Appetite Adjusts",
            "→ Positioning Changes → Asset Re-pricing",
        ],
    },
    "credit": {
        "stress": [
            "Credit Spreads Widen → Funding Stress Signal",
            "→ Corporate Borrowing Costs Rise",
            "→ Capex/Hiring Pullback → Growth Headwind",
            "→ HY/IG Divergence → Risk-Off Signal",
        ],
        "benign": [
            "Credit Spreads Tight → Funding Conditions Benign",
            "→ Corporate Access to Capital → Growth Support",
            "→ M&A / Buyback Activity → Equity Support",
        ],
        "default": [
            "Credit Conditions → Corporate Health Signal",
            "→ Growth/Macro Implications",
        ],
    },
    "ai_capex": {
        "boom": [
            "AI Capex Surge → Semiconductor/Infra Demand",
            "→ Productivity Expectations Rise",
            "→ Growth/Momentum Premium → Tech Leadership",
            "→ Concentration Risk → Fragility Signal",
        ],
        "bubble": [
            "AI Capex Unsustainable → ROI Concerns",
            "→ Valuation Peak → Multiple Compression Risk",
            "→ Rotation from AI Winners → Broad Market",
        ],
        "default": [
            "AI Capex Trend → Tech/Growth Impact",
            "→ Market Structure Implications",
        ],
    },
}

# ── Asset mapping by category ──────────────────────────────────────────

ASSET_MAP: dict[str, list[str]] = {
    "monetary": ["NASDAQ", "SPX", "UST10Y", "DXY", "Gold", "HYG"],
    "inflation": ["TIPS", "Gold", "UST10Y", "Commodities", "SPX", "XLE"],
    "growth": ["SPX", "XLI", "XLY", "UST10Y", "HYG", "IWM"],
    "liquidity": ["HYG", "IG", "SPX", "VIX", "Gold", "NASDAQ"],
    "dollar": ["DXY", "EM_ETF", "Gold", "Copper", "Oil", "SPX"],
    "risk_appetite": ["VIX", "SPX", "HYG", "UST10Y", "NASDAQ", "IWM"],
    "credit": ["HYG", "IG", "SPX", "CDX", "UST10Y"],
    "ai_capex": ["NASDAQ", "NVDA", "SOX", "SPX", "QQQ"],
}

# ── By-direction asset direction hints ────────────────────────────────

ASSET_DIRECTION: dict[str, dict[str, list[str]]] = {
    "tightening": {
        "positive": ["DXY", "UST10Y", "VIX"],
        "negative": ["NASDAQ", "HYG", "SPX", "Gold", "Copper"],
    },
    "easing": {"positive": ["NASDAQ", "HYG", "SPX", "Gold"], "negative": ["DXY", "UST10Y", "VIX"]},
    "elevated": {
        "positive": ["Gold", "TIPS", "XLE", "Commodities"],
        "negative": ["UST10Y_price", "NASDAQ", "SPX"],
    },
    "slowdown": {"positive": ["UST10Y", "Gold", "VIX"], "negative": ["SPX", "XLI", "XLY", "IWM"]},
    "risk_off": {
        "positive": ["UST10Y", "VIX", "Gold", "DXY"],
        "negative": ["SPX", "NASDAQ", "HYG", "IWM"],
    },
    "risk_on": {"positive": ["SPX", "NASDAQ", "HYG", "IWM"], "negative": ["UST10Y", "VIX", "DXY"]},
    "strong": {"positive": ["DXY"], "negative": ["Gold", "Copper", "EM_ETF", "Oil", "XLE"]},
    "weak": {"positive": ["Gold", "Copper", "EM_ETF", "Oil"], "negative": ["DXY"]},
}


class NarrativeReasoner:
    """V3.2: Elevate Narrative from signal detection to narrative reasoning.

    For each detected Narrative (V3.0), produces a NarrativeObject (V3.2) with:
    1. Causal chain reasoning → answers "WHY this is happening"
    2. Supporting/contradicting evidence classification
    3. Affected assets with direction
    4. Regime fit score
    5. Source diversity assessment
    """

    def __init__(self):
        self._reasoning_count = 0

    # ── Main API ─────────────────────────────────────────────────────

    def reason(
        self,
        narrative: Narrative,
        state_vector: dict[str, Any] | None = None,
        regime: str = "",
        mental_model_outputs: list[dict] | None = None,
    ) -> NarrativeObject:
        """Transform a flat Narrative into a rich NarrativeObject.

        Args:
            narrative: Detected narrative (V3.0 signal detection output)
            state_vector: Current macro state {dim: {score, direction, ...}}
            regime: Current market regime label
            mental_model_outputs: Outputs from mental model analysis

        Returns:
            NarrativeObject with causal chain, evidence, asset impact.
        """
        self._reasoning_count += 1

        # 1. Determine the direction/theme from narrative content
        direction = self._infer_direction(narrative, state_vector)

        # 2. Build causal chain
        causal_chain = self._build_causal_chain(narrative, direction, state_vector)

        # 3. Classify evidence
        supporting, contradicting = self._classify_evidence(narrative, direction, state_vector)

        # 4. Determine affected assets
        affected_assets = self._determine_affected_assets(narrative, direction, state_vector)

        # 5. Assess regime fit
        regime_score = self._assess_regime_fit(narrative, regime, direction)

        # 6. Assess source diversity
        source_diversity = self._assess_source_diversity(narrative, mental_model_outputs)

        # 7. Build rich NarrativeObject
        obj = NarrativeObject(
            title=narrative.title,
            description=narrative.description,
            causal_chain=causal_chain,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            affected_assets=affected_assets,
            category=narrative.category or self._infer_category(narrative),
            regime=regime,
            regime_score=regime_score,
            confidence=narrative.score,
            source_diversity=source_diversity,
            derived_from=[narrative.id],
            mental_models_used=(
                [m.get("model_name", "") for m in mental_model_outputs]
                if mental_model_outputs
                else []
            ),
        )

        logger.debug(
            "Reasoned: %s (depth=%d, confidence=%.0f%%, regime_fit=%.0f%%)",
            obj.title,
            obj.causal_depth,
            obj.confidence * 100,
            obj.regime_score * 100,
        )

        return obj

    def reason_batch(
        self,
        narratives: list[Narrative],
        state_vector: dict[str, Any] | None = None,
        regime: str = "",
        mental_model_outputs: list[dict] | None = None,
    ) -> list[NarrativeObject]:
        """Transform a batch of Narratives into NarrativeObjects."""
        return [self.reason(n, state_vector, regime, mental_model_outputs) for n in narratives]

    # ── Internal Methods ──────────────────────────────────────────────

    @staticmethod
    def _infer_direction(
        narrative: Narrative,
        state_vector: dict[str, Any] | None = None,
    ) -> str:
        """Infer the directional theme from narrative content + state."""
        text = (narrative.title + " " + narrative.description).lower()

        # Check keywords
        direction_keywords = [
            "tightening",
            "tighten",
            "hawkish",
            "hawk",
            "easing",
            "ease",
            "dovish",
            "dove",
            "elevated",
            "rising",
            "surge",
            "shock",
            "moderating",
            "declining",
            "cooling",
            "slowdown",
            "slowing",
            "deceleration",
            "acceleration",
            "accelerating",
            "boom",
            "contraction",
            "recession",
            "risk_off",
            "risk_off",
            "risk-on",
            "stress",
            "distress",
            "strong",
            "strengthening",
            "weak",
            "weakening",
            "bubble",
            "overvalued",
        ]

        for kw in direction_keywords:
            if kw in text:
                return kw

        # Fallback: check category
        category = narrative.category.lower()
        if "tighten" in category or "hawk" in category:
            return "tightening"
        if "easing" in category or "dovish" in category:
            return "easing"

        return "neutral"

    @staticmethod
    def _build_causal_chain(
        narrative: Narrative,
        direction: str,
        state_vector: dict[str, Any] | None = None,
    ) -> list[str]:
        """Build ordered causal chain from category templates."""
        category = narrative.category.lower() if narrative.category else "monetary"

        # Normalize category
        cat_key = category
        for key in CAUSAL_TEMPLATES:
            if key in category:
                cat_key = key
                break

        templates = CAUSAL_TEMPLATES.get(cat_key, CAUSAL_TEMPLATES["monetary"])

        # Try exact direction match
        chain = templates.get(direction)
        if chain is None:
            # Try fuzzy match
            for dir_key, dir_chain in templates.items():
                if dir_key in direction or direction in dir_key:
                    chain = dir_chain
                    break

        if chain is None:
            chain = templates.get("default", CAUSAL_TEMPLATES["monetary"]["default"])

        return list(chain)  # Defensive copy

    @staticmethod
    def _classify_evidence(
        narrative: Narrative,
        direction: str,
        state_vector: dict[str, Any] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Classify evidence as supporting or contradicting based on direction."""
        supporting: list[str] = []
        contradicting: list[str] = []

        title = narrative.title or ""
        _description = narrative.description or ""

        # Narrative itself is supporting evidence
        supporting.append(f"Narrative signal: {title[:100]}")

        # Source signals as supporting evidence
        for sig in narrative.source_signals:
            supporting.append(f"Signal: {sig[:120]}")

        # Check state_vector for contradicting evidence
        if state_vector:
            for dim, data in state_vector.items():
                if not isinstance(data, dict):
                    continue
                dim_score = data.get("score", 0)
                dim_dir = data.get("direction", "")

                # Contradiction: opposite direction with significant score
                if dim_score > 0.4 and dim_dir:
                    if _directions_conflict(direction, dim_dir):
                        contradicting.append(
                            f"{dim}: {dim_dir} (score={dim_score:.2f}) — contradicts {direction}"
                        )
                    elif dim_score > 0.5:
                        supporting.append(
                            f"{dim}: {dim_dir} (score={dim_score:.2f}) — aligns with {direction}"
                        )

        return supporting, contradicting

    @staticmethod
    def _determine_affected_assets(
        narrative: Narrative,
        direction: str,
        state_vector: dict[str, Any] | None = None,
    ) -> list[str]:
        """Determine affected assets with direction tags."""
        category = narrative.category.lower() if narrative.category else "monetary"
        _cat_key = category

        # Get base assets for category
        assets = []
        for key in ASSET_MAP:
            if key in category:
                assets = ASSET_MAP[key]
                _cat_key = key
                break
        if not assets:
            assets = ASSET_MAP.get("monetary", ["NASDAQ", "SPX", "DXY"])

        # Get direction hints
        dir_hints: dict[str, list[str]] = {}
        for dir_key, hints in ASSET_DIRECTION.items():
            if dir_key in direction or direction in dir_key:
                dir_hints = hints
                break

        # Tag assets with direction
        result: list[str] = []
        positive_set = set(dir_hints.get("positive", []))
        negative_set = set(dir_hints.get("negative", []))

        for asset in assets:
            if asset in positive_set:
                result.append(f"{asset} (+)")
            elif asset in negative_set:
                result.append(f"{asset} (-)")
            else:
                result.append(f"{asset} (?)")

        return result

    @staticmethod
    def _assess_regime_fit(
        narrative: Narrative,
        regime: str,
        direction: str,
    ) -> float:
        """Assess how well the narrative fits the current regime. 0-1."""
        if not regime:
            return 0.5

        regime_lower = regime.lower()

        # Strong regime fits
        strong_fits = [
            ("tighten" in regime_lower and direction in ("tightening", "hawkish")),
            ("easing" in regime_lower and direction in ("easing", "dovish")),
            ("inflation" in regime_lower and direction in ("elevated", "shock", "moderating")),
            ("growth" in regime_lower and direction in ("acceleration", "slowdown", "recession")),
            ("vol" in regime_lower and direction in ("risk_off", "risk_on")),
            ("ai" in regime_lower and direction in ("boom", "bubble")),
        ]
        if any(strong_fits):
            return 0.85

        # Moderate fits: narrative category matches regime
        narrative_cat = (narrative.category or "").lower()
        if narrative_cat in regime_lower or any(w in regime_lower for w in narrative_cat.split()):
            return 0.65

        # Weak fit
        return 0.35

    @staticmethod
    def _assess_source_diversity(
        narrative: Narrative,
        mental_model_outputs: list[dict] | None = None,
    ) -> float:
        """Assess source diversity: 0-1, more independent sources → higher."""
        score = 0.0

        # Source signals each count as 0.2 diversity
        signal_count = len(narrative.source_signals)
        score += min(signal_count * 0.2, 0.5)

        # Mental models add 0.15 each
        if mental_model_outputs:
            score += min(len(mental_model_outputs) * 0.15, 0.3)

        # Narrative score itself adds
        score += narrative.score * 0.2

        return min(score, 1.0)

    @staticmethod
    def _infer_category(narrative: Narrative) -> str:
        """Infer narrative category from title/description."""
        text = (narrative.title + " " + narrative.description).lower()
        for cat in [
            "monetary",
            "inflation",
            "growth",
            "liquidity",
            "dollar",
            "credit",
            "risk_appetite",
            "ai_capex",
        ]:
            if cat in text:
                return cat
        return "monetary"

    # ── Query ─────────────────────────────────────────────────────────

    @property
    def reasoning_count(self) -> int:
        return self._reasoning_count


# ── Helpers ─────────────────────────────────────────────────────────────


def _directions_conflict(dir_a: str, dir_b: str) -> bool:
    """Check if two directions are in conflict."""
    conflicts: dict[str, set[str]] = {
        "tightening": {"easing", "dovish"},
        "easing": {"tightening", "hawkish"},
        "hawkish": {"easing", "dovish"},
        "dovish": {"tightening", "hawkish"},
        "elevated": {"declining", "moderating", "cooling"},
        "moderating": {"elevated", "rising", "surge"},
        "declining": {"elevated", "rising", "acceleration"},
        "slowdown": {"acceleration", "boom"},
        "acceleration": {"slowdown", "recession", "contraction"},
        "risk_on": {"risk_off"},
        "risk_off": {"risk_on"},
        "strong": {"weak", "weakening"},
        "weak": {"strong", "strengthening"},
        "boom": {"bubble", "recession"},
        "bubble": {"boom"},
    }

    conflict_set = conflicts.get(dir_a, set())
    return dir_b in conflict_set or any(c in dir_b for c in conflict_set)
