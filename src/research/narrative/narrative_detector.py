"""NarrativeDetector — detects active market narratives from macro state.

Input:
    MacroStateVector  +  ResearchConclusion[]  +  CompositeSignal

Output:
    Narrative[]

Architecture:
    1. Template-based detection ← pre-defined narrative patterns
    2. Conclusion-driven detection ← from mental model conclusions
    3. Anomaly-driven detection ← from contradictions in signals
    4. Merge & deduplicate ← combine all sources
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.research.models.mental_model import ResearchConclusion
from src.research.narrative.schemas import (
    Narrative,
    NarrativeCategory,
    NarrativeSignal,
    NarrativeTemplate,
    NarrativeTimeHorizon,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Narrative Templates ──────────────────────────────────────────────────────


_NARRATIVE_TEMPLATES: list[NarrativeTemplate] = [
    # ── Liquidity narratives ─────────────────────────────────────────────
    NarrativeTemplate(
        title_template="Liquidity Tightening",
        description_template="Financial conditions are tightening: USD strength, rising real yields, and Fed balance sheet reduction are draining global liquidity.",
        category=NarrativeCategory.MONETARY,
        time_horizon=NarrativeTimeHorizon.MEDIUM,
        required_dimensions=["Liquidity"],
        required_directions=["tightening"],
        affected_assets=["SP500", "Nasdaq", "EM_Equities", "Gold"],
        base_confidence=0.75,
    ),
    NarrativeTemplate(
        title_template="Liquidity Easing",
        description_template="Financial conditions are easing: USD weakness, falling yields, and potential Fed pivot are boosting liquidity.",
        category=NarrativeCategory.MONETARY,
        time_horizon=NarrativeTimeHorizon.MEDIUM,
        required_dimensions=["Liquidity"],
        required_directions=["easing"],
        affected_assets=["SP500", "Nasdaq", "EM_Equities", "Gold", "HYG"],
        base_confidence=0.75,
    ),
    # ── Rates / Policy narratives ────────────────────────────────────────
    NarrativeTemplate(
        title_template="Higher for Longer",
        description_template="The Fed maintains a hawkish stance; rates will stay elevated for an extended period, pressuring long-duration assets.",
        category=NarrativeCategory.MONETARY,
        time_horizon=NarrativeTimeHorizon.LONG,
        required_dimensions=["Policy", "Liquidity"],
        required_directions=["hawkish", "tightening"],
        affected_assets=["SP500", "Nasdaq", "US10Y", "US2Y"],
        base_confidence=0.70,
    ),
    NarrativeTemplate(
        title_template="Fed Pivot / Dovish Shift",
        description_template="Expectations are building for a Fed pivot: inflation cooling, growth slowing — markets pricing in rate cuts.",
        category=NarrativeCategory.MONETARY,
        time_horizon=NarrativeTimeHorizon.MEDIUM,
        required_dimensions=["Policy", "Inflation"],
        required_directions=["dovish", "cooling"],
        affected_assets=["SP500", "Nasdaq", "Bonds", "Gold", "HYG"],
        base_confidence=0.65,
    ),
    # ── Growth narratives ────────────────────────────────────────────────
    NarrativeTemplate(
        title_template="Soft Landing",
        description_template="The economy is slowing gently without entering recession: inflation cools while growth remains positive.",
        category=NarrativeCategory.GROWTH,
        time_horizon=NarrativeTimeHorizon.MEDIUM,
        required_dimensions=["Growth", "Inflation"],
        required_directions=["expansion", "cooling"],
        affected_assets=["SP500", "Russell", "HYG", "Copper"],
        base_confidence=0.70,
    ),
    NarrativeTemplate(
        title_template="Growth Scare",
        description_template="Growth indicators are deteriorating sharply: recession fears rising, risk-off sentiment building.",
        category=NarrativeCategory.GROWTH,
        time_horizon=NarrativeTimeHorizon.SHORT,
        required_dimensions=["Growth", "Risk_Appetite"],
        required_directions=["contraction", "risk_off"],
        affected_assets=["SP500", "Russell", "Copper", "Oil"],
        base_confidence=0.80,
    ),
    NarrativeTemplate(
        title_template="Growth Resilience",
        description_template="Despite headwinds, growth indicators remain surprisingly strong: employment holds, consumer spending robust.",
        category=NarrativeCategory.GROWTH,
        time_horizon=NarrativeTimeHorizon.MEDIUM,
        required_dimensions=["Growth"],
        required_directions=["expansion"],
        affected_assets=["SP500", "Russell", "Copper", "Oil"],
        base_confidence=0.65,
    ),
    # ── Inflation narratives ─────────────────────────────────────────────
    NarrativeTemplate(
        title_template="Inflation Reacceleration",
        description_template="Inflation is rising again: commodity prices surging, wage growth persistent, shelter costs sticky.",
        category=NarrativeCategory.INFLATION,
        time_horizon=NarrativeTimeHorizon.MEDIUM,
        required_dimensions=["Inflation"],
        required_directions=["rising"],
        affected_assets=["Gold", "Oil", "TIPS", "US10Y"],
        base_confidence=0.75,
    ),
    NarrativeTemplate(
        title_template="Disinflation Trend",
        description_template="Inflation is cooling across categories: goods deflation, shelter moderating, services slowing.",
        category=NarrativeCategory.INFLATION,
        time_horizon=NarrativeTimeHorizon.MEDIUM,
        required_dimensions=["Inflation"],
        required_directions=["cooling"],
        affected_assets=["Nasdaq", "Bonds", "SP500"],
        base_confidence=0.70,
    ),
    # ── Risk narratives ──────────────────────────────────────────────────
    NarrativeTemplate(
        title_template="Risk-On Rally",
        description_template="Risk appetite is surging: VIX low, credit spreads tight, equities rallying — broad bullish sentiment.",
        category=NarrativeCategory.RISK,
        time_horizon=NarrativeTimeHorizon.SHORT,
        required_dimensions=["Risk_Appetite", "Credit"],
        required_directions=["risk_on", "expansion"],
        affected_assets=["SP500", "Nasdaq", "Russell", "HYG"],
        base_confidence=0.70,
    ),
    NarrativeTemplate(
        title_template="Risk-Off / Flight to Safety",
        description_template="Risk appetite has collapsed: VIX spiking, credit spreads widening, safe-haven demand surging.",
        category=NarrativeCategory.RISK,
        time_horizon=NarrativeTimeHorizon.SHORT,
        required_dimensions=["Risk_Appetite"],
        required_directions=["risk_off"],
        affected_assets=["Gold", "US10Y", "VIX", "USD"],
        base_confidence=0.80,
    ),
    # ── Dollar narratives ────────────────────────────────────────────────
    NarrativeTemplate(
        title_template="Dollar Strength Regime",
        description_template="USD is strengthening broadly: rate differentials favor USD, capital flows into US assets, EM under pressure.",
        category=NarrativeCategory.MONETARY,
        time_horizon=NarrativeTimeHorizon.MEDIUM,
        required_dimensions=["Dollar"],
        required_directions=["strengthening"],
        affected_assets=["DXY", "EM_Equities", "Gold", "Commodities"],
        base_confidence=0.75,
    ),
    NarrativeTemplate(
        title_template="Dollar Weakness / EM Revival",
        description_template="USD weakening: rate differentials narrowing, capital flowing to EM, commodity prices rising in USD terms.",
        category=NarrativeCategory.MONETARY,
        time_horizon=NarrativeTimeHorizon.MEDIUM,
        required_dimensions=["Dollar"],
        required_directions=["weakening"],
        affected_assets=["EM_Equities", "Gold", "Copper", "Oil"],
        base_confidence=0.70,
    ),
    # ── Credit narratives ────────────────────────────────────────────────
    NarrativeTemplate(
        title_template="Credit Expansion",
        description_template="Credit conditions are easing: spreads tightening, banks lending, corporate borrowing strong.",
        category=NarrativeCategory.CREDIT,
        time_horizon=NarrativeTimeHorizon.MEDIUM,
        required_dimensions=["Credit"],
        required_directions=["expansion"],
        affected_assets=["HYG", "LQD", "SP500", "Russell"],
        base_confidence=0.70,
    ),
    NarrativeTemplate(
        title_template="Credit Stress Building",
        description_template="Credit conditions are deteriorating: spreads widening, HY underperformance, lending standards tightening.",
        category=NarrativeCategory.CREDIT,
        time_horizon=NarrativeTimeHorizon.SHORT,
        required_dimensions=["Credit", "Risk_Appetite"],
        required_directions=["contraction", "risk_off"],
        affected_assets=["HYG", "LQD", "SP500", "VIX"],
        base_confidence=0.75,
    ),
    # ── AI / Tech narratives ─────────────────────────────────────────────
    NarrativeTemplate(
        title_template="AI Capex Still Strong",
        description_template="AI investment cycle remains robust: semiconductor demand high, hyperscaler capex growing, AI supply chain healthy.",
        category=NarrativeCategory.SECTORAL,
        time_horizon=NarrativeTimeHorizon.MEDIUM,
        required_dimensions=["AI_Capex"],
        required_directions=["expansion"],
        affected_assets=["NVDA", "SMH", "ASML", "Nasdaq"],
        base_confidence=0.70,
    ),
    NarrativeTemplate(
        title_template="AI Capex Peak / Pullback",
        description_template="AI investment cycle showing signs of peaking: semiconductor orders slowing, hyperscaler capex moderating.",
        category=NarrativeCategory.SECTORAL,
        time_horizon=NarrativeTimeHorizon.SHORT,
        required_dimensions=["AI_Capex"],
        required_directions=["contraction"],
        affected_assets=["NVDA", "SMH", "ASML", "Nasdaq"],
        base_confidence=0.70,
    ),
    # ── Employment narratives ────────────────────────────────────────────
    NarrativeTemplate(
        title_template="Labor Market Strength",
        description_template="Employment remains robust: low claims, strong payrolls, wage growth steady — supporting consumer spending.",
        category=NarrativeCategory.GROWTH,
        time_horizon=NarrativeTimeHorizon.MEDIUM,
        required_dimensions=["Employment"],
        required_directions=["expansion"],
        affected_assets=["SP500", "Russell", "USD"],
        base_confidence=0.65,
    ),
    # ── Contradiction / special narratives ───────────────────────────────
    NarrativeTemplate(
        title_template="Stagflation Risk",
        description_template="Rare combination: inflation rising while growth slowing — policy dilemma for central banks.",
        category=NarrativeCategory.GROWTH,
        time_horizon=NarrativeTimeHorizon.MEDIUM,
        required_dimensions=["Inflation", "Growth"],
        required_directions=["rising", "contraction"],
        affected_assets=["Gold", "Oil", "TIPS", "SP500"],
        base_confidence=0.85,
    ),
    NarrativeTemplate(
        title_template="Goldilocks",
        description_template="Perfect macro environment: growth solid, inflation moderate, policy neutral — ideal for risk assets.",
        category=NarrativeCategory.GROWTH,
        time_horizon=NarrativeTimeHorizon.SHORT,
        required_dimensions=["Growth", "Inflation", "Risk_Appetite"],
        required_directions=["expansion", "cooling", "risk_on"],
        affected_assets=["SP500", "Nasdaq", "Russell", "HYG"],
        base_confidence=0.75,
    ),
]


# ── Detector ─────────────────────────────────────────────────────────────────


class NarrativeDetector:
    """Detects active market narratives from macro state and model conclusions.

    Three detection methods:
        1. Template-based: match pre-defined patterns against state vector
        2. Conclusion-driven: derive narratives from mental model conclusions
        3. Anomaly-driven: detect contradictions between signals

    Usage:
        detector = NarrativeDetector()
        narratives = detector.detect(
            state_vector=m1_snapshot["state_vector"],
            conclusions=registry.evaluate_all(m1_snapshot),
            feature_summary=m1_snapshot.get("feature_summary", {}),
        )
    """

    def __init__(self) -> None:
        self._templates = list(_NARRATIVE_TEMPLATES)
        self._previous_narratives: dict[str, Narrative] = {}

    def register_template(self, template: NarrativeTemplate) -> None:
        """Register a custom narrative template."""
        self._templates.append(template)

    def detect(
        self,
        state_vector: dict,
        conclusions: list[ResearchConclusion],
        feature_summary: dict | None = None,
    ) -> list[Narrative]:
        """Detect all active narratives.

        Args:
            state_vector: M1 state_vector dict {dim: {score, direction, drivers, ...}}
            conclusions: M2 ResearchConclusion list from mental models
            feature_summary: Optional feature data for signal extraction

        Returns:
            Detected Narrative list, sorted by composite score descending.
        """
        narratives: list[Narrative] = []

        # ── Method 1: Template-based detection ───────────────────────────
        template_narratives = self._detect_from_templates(state_vector, conclusions)
        narratives.extend(template_narratives)

        # ── Method 2: Conclusion-driven ──────────────────────────────────
        conclusion_narratives = self._detect_from_conclusions(conclusions, state_vector)
        narratives.extend(conclusion_narratives)

        # ── Method 3: Anomaly-driven ─────────────────────────────────────
        if feature_summary:
            anomaly_narratives = self._detect_anomalies(state_vector, feature_summary)
            narratives.extend(anomaly_narratives)

        # ── Deduplicate & compute scores ─────────────────────────────────
        narratives = self._deduplicate(narratives)
        for n in narratives:
            n.compute_composite_score()

        # ── Update novelty vs previous run ───────────────────────────────
        self._compute_novelty(narratives)

        # ── Store for next comparison ────────────────────────────────────
        self._previous_narratives = {n.title: n for n in narratives}

        # ── Sort by composite score ──────────────────────────────────────
        narratives.sort(key=lambda n: n.composite_score, reverse=True)

        logger.info(
            "narrative_detection_complete | total=%d active=%d",
            len(narratives),
            sum(1 for n in narratives if n.is_active),
        )
        return narratives

    # ── Template Detection ───────────────────────────────────────────────────

    def _detect_from_templates(
        self,
        state_vector: dict,
        conclusions: list[ResearchConclusion],
    ) -> list[Narrative]:
        """Match pre-defined narrative templates against current state."""
        narratives: list[Narrative] = []

        for template in self._templates:
            match_score = template.match(state_vector, conclusions)

            if match_score >= 0.5:  # Minimum threshold
                # Build narrative from template
                narrative = Narrative(
                    title=template.title_template,
                    description=template.description_template,
                    score=min(1.0, template.base_confidence * match_score),
                    category=(
                        template.category.value
                        if hasattr(template.category, "value")
                        else str(template.category)
                    ),
                    strength=match_score,
                    time_horizon=(
                        template.time_horizon.value
                        if hasattr(template.time_horizon, "value")
                        else str(template.time_horizon)
                    ),
                    affected_assets=list(template.affected_assets),
                    source_list=["template_matcher"],
                    market_consensus=0.5 + 0.3 * (0.5 - abs(0.5 - match_score)),
                )

                # Attach signals from state vector
                for dim in template.required_dimensions:
                    dim_data = state_vector.get(dim, {})
                    if dim_data:
                        narrative.supporting_signals.append(
                            NarrativeSignal(
                                source=dim,
                                value=dim_data.get("score", 0.5),
                                direction="supporting",
                                interpretation=f"{dim}: {dim_data.get('direction', 'neutral')} (score={dim_data.get('score', 0.5):.2f})",
                            )
                        )

                # Attach model conclusions
                for c in conclusions:
                    if c.domain == template.category.value or any(
                        dim.lower() == c.domain.lower() for dim in template.required_dimensions
                    ):
                        if c.confidence >= 0.5:
                            narrative.supporting_models.append(c.model_name)
                        else:
                            narrative.contradicting_models.append(c.model_name)

                narratives.append(narrative)

        return narratives

    # ── Conclusion-Driven Detection ──────────────────────────────────────────

    def _detect_from_conclusions(
        self,
        conclusions: list[ResearchConclusion],
        state_vector: dict,
    ) -> list[Narrative]:
        """Derive narratives directly from mental model conclusions.

        High-confidence conclusions (>0.7) become standalone narratives.
        """
        narratives: list[Narrative] = []

        for c in conclusions:
            if c.confidence < 0.6:
                continue  # Skip low-confidence conclusions

            category_map = {
                "Liquidity": NarrativeCategory.MONETARY,
                "Credit": NarrativeCategory.CREDIT,
                "Inflation": NarrativeCategory.INFLATION,
                "Growth": NarrativeCategory.GROWTH,
                "Policy": NarrativeCategory.MONETARY,
                "Dollar": NarrativeCategory.MONETARY,
                "AI_Capex": NarrativeCategory.SECTORAL,
                "Risk_Appetite": NarrativeCategory.RISK,
                "Employment": NarrativeCategory.GROWTH,
            }

            narrative = Narrative(
                title=f"{c.domain}: {c.direction.replace('_', ' ').title()}",
                description=c.conclusion,
                score=c.confidence,
                strength=c.confidence,
                category=(
                    category_map.get(c.domain, NarrativeCategory.MONETARY).value
                    if hasattr(category_map.get(c.domain, NarrativeCategory.MONETARY), "value")
                    else str(category_map.get(c.domain, NarrativeCategory.MONETARY))
                ),
                time_horizon=(
                    NarrativeTimeHorizon.MEDIUM.value
                    if hasattr(NarrativeTimeHorizon.MEDIUM, "value")
                    else str(NarrativeTimeHorizon.MEDIUM)
                ),
                source_list=["mental_model"],
            )

            # Extract signals from supporting evidence
            for ev in c.supporting_evidence:
                narrative.supporting_signals.append(
                    NarrativeSignal(
                        source=ev.get("indicator", c.domain),
                        value=ev.get("value", 0),
                        direction="supporting",
                        interpretation=ev.get("text", ""),
                    )
                )

            # Extract from contradicting evidence
            for ev in c.contradicting_evidence:
                narrative.supporting_signals.append(
                    NarrativeSignal(
                        source=ev.get("indicator", c.domain),
                        value=ev.get("value", 0),
                        direction="contradicting",
                        interpretation=ev.get("text", ""),
                    )
                )

            narratives.append(narrative)

        return narratives

    # ── Anomaly Detection ────────────────────────────────────────────────────

    def _detect_anomalies(
        self,
        state_vector: dict,
        feature_summary: dict,
    ) -> list[Narrative]:
        """Detect narratives from anomalous signal combinations.

        E.g., Gold up + Dollar up + Bonds up = something unusual is happening.
        """
        anomalies: list[Narrative] = []

        indicators = feature_summary.get("indicators", {})

        # Pattern 1: Divergence between Gold and Dollar (both rising)
        gold_data = indicators.get("GOLD", {})
        dxy_data = indicators.get("DXY", {})

        gold_trend = self._get_trend(gold_data)
        dxy_trend = self._get_trend(dxy_data)

        if gold_trend == "up" and dxy_trend == "up":
            anomalies.append(
                Narrative(
                    title="Decoupling: Gold + DXY Both Rising",
                    description="Gold and USD are both strengthening — a rare divergence suggesting geopolitical risk premium and/or de-dollarization flows simultaneously with US exceptionalism.",
                    confidence=0.65,
                    strength=0.70,
                    novelty_score=0.85,
                    market_consensus=0.3,  # Contrarian
                    category=NarrativeCategory.GEOPOLITICAL,
                    time_horizon=NarrativeTimeHorizon.SHORT,
                    affected_assets=["Gold", "DXY", "EM_Equities"],
                    source_list=["anomaly_detector"],
                    supporting_signals=[
                        NarrativeSignal(
                            source="GOLD",
                            value=gold_data.get("raw_value", 0),
                            direction="supporting",
                            interpretation="Gold rising",
                        ),
                        NarrativeSignal(
                            source="DXY",
                            value=dxy_data.get("raw_value", 0),
                            direction="supporting",
                            interpretation="DXY rising",
                        ),
                    ],
                )
            )

        # Pattern 2: VIX low but HYG also low (complacency vs credit stress)
        vix_data = indicators.get("VIX", {})
        hyg_data = indicators.get("HYG", {})

        vix_val = vix_data.get("raw_value", 0)
        hyg_val = hyg_data.get("raw_value", 0)

        if 0 < vix_val < 15 and self._get_trend(hyg_data) == "down":
            anomalies.append(
                Narrative(
                    title="Complacency Trap: Low VIX, Weak Credit",
                    description="VIX is extremely low but credit markets are weak — a warning sign that risk is mispriced in equity vol.",
                    confidence=0.60,
                    strength=0.65,
                    novelty_score=0.90,
                    market_consensus=0.25,
                    category=NarrativeCategory.RISK,
                    time_horizon=NarrativeTimeHorizon.SHORT,
                    affected_assets=["VIX", "HYG", "SP500"],
                    source_list=["anomaly_detector"],
                    supporting_signals=[
                        NarrativeSignal(
                            source="VIX",
                            value=vix_val,
                            direction="contradicting",
                            interpretation="VIX extremely low (complacency)",
                        ),
                        NarrativeSignal(
                            source="HYG",
                            value=hyg_val,
                            direction="supporting",
                            interpretation="HYG weakening (credit stress)",
                        ),
                    ],
                )
            )

        # Pattern 3: Oil surging + bonds selling off (inflation fear)
        oil_data = indicators.get("OIL", {})
        us10y_data = indicators.get("US10Y", {})

        if self._get_trend(oil_data) == "up" and self._get_trend(us10y_data) == "up":
            anomalies.append(
                Narrative(
                    title="Oil-Driven Inflation Scare",
                    description="Oil prices rising alongside bond yields — markets pricing in supply-side inflation risk that could delay rate cuts.",
                    confidence=0.70,
                    strength=0.75,
                    novelty_score=0.60,
                    market_consensus=0.55,
                    category=NarrativeCategory.INFLATION,
                    time_horizon=NarrativeTimeHorizon.MEDIUM,
                    affected_assets=["Oil", "US10Y", "SP500", "TIPS"],
                    source_list=["anomaly_detector"],
                    supporting_signals=[
                        NarrativeSignal(
                            source="OIL",
                            value=oil_data.get("raw_value", 0),
                            direction="supporting",
                            interpretation="Oil rising",
                        ),
                        NarrativeSignal(
                            source="US10Y",
                            value=us10y_data.get("raw_value", 0),
                            direction="supporting",
                            interpretation="Yields rising",
                        ),
                    ],
                )
            )

        return anomalies

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _deduplicate(self, narratives: list[Narrative]) -> list[Narrative]:
        """Merge duplicate narratives by title (keep highest confidence)."""
        seen: dict[str, Narrative] = {}
        for n in narratives:
            key = n.title.lower().strip()
            if key in seen:
                # Merge: keep the higher confidence, combine signals
                existing = seen[key]
                existing.supporting_signals.extend(n.supporting_signals)
                existing.supporting_models = list(
                    set(existing.supporting_models + n.supporting_models)
                )
                existing.contradicting_models = list(
                    set(existing.contradicting_models + n.contradicting_models)
                )
                existing.source_list = list(set(existing.source_list + n.source_list))
                existing.confidence = max(existing.confidence, n.confidence)
                existing.updated_at = datetime.now(UTC)
                existing.version += 1
            else:
                seen[key] = n
        return list(seen.values())

    def _compute_novelty(self, narratives: list[Narrative]) -> None:
        """Compare current narratives to previous run to compute novelty."""
        for n in narratives:
            prev = self._previous_narratives.get(n.title)
            if prev is None:
                # Brand new narrative — high novelty
                n.novelty_score = max(n.novelty_score, 0.80)
            else:
                # Existing narrative — check if changed significantly
                confidence_delta = abs(n.confidence - prev.confidence)
                if confidence_delta > 0.20:
                    n.novelty_score = max(n.novelty_score, 0.60)
                else:
                    n.novelty_score = max(n.novelty_score, 0.15)

    @staticmethod
    def _get_trend(indicator_data: dict) -> str:
        """Extract trend direction from feature data."""
        features = indicator_data.get("features", [])
        for f in features:
            if isinstance(f, dict) and f.get("label", "").endswith("uptrend"):
                return "up"
            if isinstance(f, dict) and f.get("label", "").endswith("downtrend"):
                return "down"
        # Fallback: check 5d change
        for f in features:
            if isinstance(f, dict) and "5d_up" in f.get("label", ""):
                return "up"
            if isinstance(f, dict) and "5d_down" in f.get("label", ""):
                return "down"
        return "flat"
