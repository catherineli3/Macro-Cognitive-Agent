"""HypothesisBuilder — Causal hypotheses from observations.

Professional researchers don't describe events — they build causal models.
Every hypothesis has: causal chain, assumptions, falsification conditions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from src.research.reasoning.schemas import Hypothesis, EvidenceCluster


class HypothesisBuilder:
    """Generate causal hypotheses from evidence clusters and beliefs."""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def build_hypotheses(
        self,
        evidence_clusters: list[EvidenceCluster],
        beliefs: list = None,
        regime_result: Optional[dict] = None,
        narrative: Optional[str] = None,
    ) -> list[Hypothesis]:
        """Generate ranked hypotheses from current evidence landscape."""
        beliefs = beliefs or []
        hypotheses = []

        for cluster in evidence_clusters:
            if cluster.weight_score < 0.3:
                continue
            h = self._from_cluster(cluster, regime_result)
            if h:
                hypotheses.append(h)

        for belief in beliefs:
            bd = self._to_dict(belief)
            if bd:
                h = self._from_belief(bd, evidence_clusters)
                if h:
                    hypotheses.append(h)

        if regime_result:
            h = self._from_regime(regime_result, evidence_clusters)
            if h:
                hypotheses.append(h)

        hypotheses = self._deduplicate(hypotheses)
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        return hypotheses

    def _from_cluster(self, cluster: EvidenceCluster, regime: Optional[dict]) -> Optional[Hypothesis]:
        h_id = f"HYP_{str(uuid.uuid4())[:8]}"
        theme, direction = cluster.theme, cluster.net_direction

        causal = self._causal(theme, direction, cluster)
        statement = self._statement(theme, direction, cluster)
        structural, cyclical = self._factor_split(theme)

        supporting = [i for i in cluster.evidence_items if i["direction"] == "bullish"]
        contradicting = [i for i in cluster.evidence_items if i["direction"] == "bearish"]
        ew = cluster.weight_score * (1 if direction == "supporting_bullish" else -1)

        conf = min(0.85, cluster.weight_score * 0.5 + cluster.quality_score * 0.3 + cluster.recency_score * 0.2)

        return Hypothesis(
            hypothesis_id=h_id,
            title=self._title(theme, direction),
            statement=statement,
            domain=theme,
            causal_chain=causal,
            key_assumptions=self._assumptions(theme),
            structural_factors=structural,
            cyclical_factors=cyclical,
            supporting_evidence=supporting[:5],
            contradicting_evidence=contradicting[:3],
            evidence_weight=round(ew, 2),
            confidence=round(conf, 2),
            confidence_breakdown={
                "causal_logic": min(0.7, cluster.weight_score + 0.2),
                "data_quality": cluster.quality_score,
                "timing": cluster.recency_score,
                "historical_consistency": 0.6,
            },
            falsification_conditions=self._falsify(theme, direction),
            if_true_implication=self._implication(theme, direction),
            asset_impact=self._impact(theme, direction),
            source=f"evidence_cluster:{cluster.cluster_id}",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _from_belief(self, bd: dict, clusters: list[EvidenceCluster]) -> Optional[Hypothesis]:
        name = bd.get("name", bd.get("label", ""))
        if not name:
            return None

        confidence = bd.get("confidence", bd.get("prior_mean", 0.5))
        direction = bd.get("direction", "neutral")

        supports = [c for c in clusters if c.net_direction == "supporting_bullish"]
        contradicts = [c for c in clusters if c.net_direction == "supporting_bearish"]
        evidence_weight = len(supports) - len(contradicts)
        final_conf = round(float(confidence) * 0.6 + min(0.9, max(0.1, 0.5 + evidence_weight * 0.1)) * 0.4, 2)

        return Hypothesis(
            hypothesis_id=f"HYP_{str(uuid.uuid4())[:8]}",
            title=f"Belief: {name} — {self._dir_label(direction)}",
            statement=f"Research belief '{name}' is {'supported' if evidence_weight >= 0 else 'challenged'} "
                      f"by current evidence (net: {evidence_weight:+d} clusters)",
            domain="macro_view",
            causal_chain=[f"Belief: {name}", f"Evidence alignment: {evidence_weight:+d}"],
            key_assumptions=["Belief model is well-specified"],
            structural_factors=[],
            cyclical_factors=[],
            supporting_evidence=[],
            contradicting_evidence=[],
            evidence_weight=round(evidence_weight / max(len(clusters), 1), 2),
            confidence=final_conf,
            confidence_breakdown={"causal_logic": 0.6, "data_quality": 0.5, "timing": 0.7, "historical_consistency": 0.5},
            falsification_conditions=[{"condition": "Evidence direction reverses", "if_triggered": "Invert belief", "probability": 0.3, "timeline": "1-2 weeks"}],
            if_true_implication="Confirms existing research direction",
            asset_impact=[],
            source="belief_driven",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _from_regime(self, rr: dict, clusters: list[EvidenceCluster]) -> Optional[Hypothesis]:
        rl = rr.get("regime_label", rr.get("regime_type", ""))
        if not rl:
            return None

        trans = rr.get("transition", {})
        tr = trans.get("probability", trans.get("risk", 0.3)) if isinstance(trans, dict) else 0.3
        rc = rr.get("confidence", 0.6)
        stable = tr < 0.4

        causal = [f"Regime: {rl} (conf: {rc:.0%})", f"Transition risk: {tr:.0%}"]
        analog = rr.get("historical_analog", rr.get("analog", {}))
        if analog and isinstance(analog, dict) and analog.get("period"):
            causal.append(f"Analog: {analog['period']} ({analog.get('label', '')})")

        return Hypothesis(
            hypothesis_id=f"HYP_REGIME_{str(uuid.uuid4())[:8]}",
            title=f"Regime: {rl} {'Stable' if stable else 'In Transition'}",
            statement=f"Macro regime is {rl} with {tr:.0%} transition risk. "
                      f"{'Stable favors directional views.' if stable else 'Elevated risk argues caution.'}",
            domain="macro_regime",
            causal_chain=causal,
            key_assumptions=["Regime classifier is calibrated", "Historical analogs apply"],
            structural_factors=[rl],
            cyclical_factors=[f"Transition prob: {tr:.0%}"],
            supporting_evidence=[], contradicting_evidence=[],
            evidence_weight=0.0,
            confidence=round(rc * (1 - tr * 0.5), 2),
            confidence_breakdown={"causal_logic": 0.8, "data_quality": 0.6, "timing": 0.7, "historical_consistency": 0.5},
            falsification_conditions=[{"condition": "Key regime indicator breaks trend", "if_triggered": "Re-classify regime", "probability": tr, "timeline": "1-4 weeks"}],
            if_true_implication=f"Maintain {rl}-appropriate allocation",
            asset_impact=[],
            source="regime_driven",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    # ── Helpers ──

    def _causal(self, theme, direction, cluster):
        maps = {
            "growth_momentum": ["Activity indicators shifting", f"Direction: {direction}", "Transmission → earnings (1-2Q lag)", "Policy response contingent on persistence"],
            "inflation_dynamics": ["Price signals across baskets", f"Direction: {direction}", "Core/headline divergence = signal quality", "CB reaction function at thresholds"],
            "labor_market": ["Labor tightness evolving", f"Direction: {direction}", "Wage pressure → services inflation channel", "Employment → consumption → growth"],
            "monetary_policy": ["Policy stance identified", "Rate path expectations forming", "Financial conditions transmission", "Lag effects: 12-18 months to real economy"],
            "capital_flows": ["Flow direction established", f"Direction: {direction}", "Institutional positioning confirms/diverges", "Cross-asset ripple effects"],
            "credit_conditions": ["Credit impulse direction", f"Spreads: {direction}", "Bank lending standards = leading indicator", "Corporate refinancing wall approaching"],
        }
        return maps.get(theme, [f"{theme} evolving", f"Direction: {direction}", "Impact assessment pending"])

    def _statement(self, theme, direction, cluster):
        templates = {
            "growth_momentum": f"Growth momentum is {self._dir_label(direction)} based on {len(cluster.evidence_items)} data points. The signal quality is {cluster.quality_score:.0%}.",
            "inflation_dynamics": f"Inflation trajectory appears {self._dir_label(direction)}. Evidence quality {cluster.quality_score:.0%}, recency {cluster.recency_score:.0%}.",
            "monetary_policy": f"Monetary policy stance is assessed as {self._dir_label(direction)} with weight score {cluster.weight_score:.2f}.",
            "capital_flows": f"Capital flows signal {self._dir_label(direction)} positioning. Cluster weight: {cluster.weight_score:.2f}.",
        }
        return templates.get(theme, f"Evidence on {theme} points {self._dir_label(direction)} (weight: {cluster.weight_score:.2f}, quality: {cluster.quality_score:.0%}).")

    @staticmethod
    def _title(theme, direction):
        labels = {
            "growth_momentum": f"Growth: {direction}", "inflation_dynamics": f"Inflation: {direction}",
            "labor_market": f"Labor: {direction}", "monetary_policy": f"Policy: {direction}",
            "capital_flows": f"Flows: {direction}", "credit_conditions": f"Credit: {direction}",
            "fiscal_policy": f"Fiscal: {direction}", "geopolitical_risk": f"Geopolitics",
            "currency_markets": f"FX: {direction}", "commodity_markets": f"Commodities: {direction}",
        }
        base = labels.get(theme, f"{theme.replace('_', ' ').title()}: {direction}")
        return base

    @staticmethod
    def _assumptions(theme):
        maps = {
            "growth_momentum": ["Data accurately reflects real activity", "No structural break in leading indicators"],
            "inflation_dynamics": ["Supply-side normalization continues", "Shelter/OER lag is well-modeled"],
            "labor_market": ["Participation rate stable", "Immigration policy unchanged"],
            "monetary_policy": ["Fed reaction function unchanged", "Data-dependent framework holds"],
        }
        return maps.get(theme, ["Underlying relationships are stable", "No regime change imminent"])

    @staticmethod
    def _factor_split(theme):
        splits = {
            "growth_momentum": (["Productivity trend", "Demographics"], ["Inventory cycle", "Consumer confidence"]),
            "inflation_dynamics": (["Deglobalization", "Energy transition cost"], ["Base effects", "Commodity prices"]),
            "labor_market": (["Aging workforce", "Skills mismatch"], ["Hiring/firing cycle", "Seasonal patterns"]),
            "monetary_policy": (["Natural rate (r*)", "Neutral rate debate"], ["Meeting-by-meeting data", "Hawk/dove rotation"]),
        }
        return splits.get(theme, ([], []))

    @staticmethod
    def _falsify(theme, direction):
        defaults = [{"condition": "Key data reverses direction", "if_triggered": "Abandon hypothesis", "probability": 0.25, "timeline": "2-4 weeks"}]
        specifics = {
            "growth_momentum": [{"condition": "Two consecutive negative PMI prints", "if_triggered": "Growth hypothesis falsified", "probability": 0.3, "timeline": "1-2 months"}],
            "inflation_dynamics": [{"condition": "Core CPI MoM exceeds 0.3% for 3 months", "if_triggered": "Disinflation thesis invalidated", "probability": 0.25, "timeline": "3 months"}],
            "monetary_policy": [{"condition": "FOMC surprises markets with opposite action", "if_triggered": "Policy path hypothesis wrong", "probability": 0.15, "timeline": "Next FOMC"}],
        }
        return specifics.get(theme, defaults)

    @staticmethod
    def _implication(theme, direction):
        maps = {
            "growth_momentum": f"{'Risk-on positioning warranted' if 'supporting_bullish' in direction else 'Defensive rotation advisable'}",
            "inflation_dynamics": f"{'Duration risk acceptable' if 'supporting_bullish' in direction else 'Shorten duration, add real assets'}",
            "monetary_policy": f"{'Maintain risk exposure' if 'supporting_bullish' in direction else 'Reduce leverage, increase cash'}",
            "capital_flows": f"{'Follow the flow, momentum supportive' if 'supporting_bullish' in direction else 'Fade the flow, contrarian opportunity'}",
        }
        return maps.get(theme, f"Directional trade in favor of {direction}")

    def _impact(self, theme, direction):
        impacts = {
            "growth_momentum": [{"asset": "Equities", "direction": "long" if "bullish" in direction else "short", "conviction": "medium"}],
            "inflation_dynamics": [{"asset": "Bonds", "direction": "long" if "bullish" not in direction else "short", "conviction": "medium"}],
            "monetary_policy": [{"asset": "USD", "direction": "long" if "bullish" not in direction else "short", "conviction": "low"}],
        }
        return impacts.get(theme, [])

    @staticmethod
    def _deduplicate(hypotheses):
        seen_titles = set()
        unique = []
        for h in hypotheses:
            key = h.title.lower().strip()
            if key not in seen_titles:
                seen_titles.add(key)
                unique.append(h)
        return unique

    @staticmethod
    def _dir_label(direction):
        return {"supporting_bullish": "bullish", "supporting_bearish": "bearish", "mixed": "mixed", "neutral": "neutral"}.get(direction, str(direction))

    @staticmethod
    def _to_dict(obj):
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        return {}
