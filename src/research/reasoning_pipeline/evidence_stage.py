"""V5.2 Stage 2: Evidence — Cluster and evaluate all evidence systematically.

Every hypothesis must be built on evidence. This stage:
    1. Clusters observations into thematic groups
    2. Evaluates each piece of evidence for direction (support/contradict/neutral)
    3. Computes net evidence weight per theme
    4. Identifies evidence gaps

Cannot skip: observations without evidence are just anecdotes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.research.reasoning_pipeline.schemas import (
    ObservationOutput,
    EvidenceOutput,
    StageStatus,
)


class EvidenceStage:
    """Stage 2: Systematic evidence clustering and evaluation."""

    EVIDENCE_THEMES = [
        "growth", "inflation", "labor_market", "monetary_policy",
        "fiscal_policy", "financial_conditions", "global_trade",
        "corporate_health", "consumer_health", "housing",
        "credit_markets", "currency_markets", "commodity_markets",
        "geopolitical_risk", "sentiment",
    ]

    THEME_KEYWORDS: dict[str, list[str]] = {
        "growth": ["gdp", "growth", "recession", "expansion", "slowdown", "output"],
        "inflation": ["cpi", "pce", "inflation", "deflation", "price", "ppi"],
        "labor_market": ["employment", "unemployment", "payroll", "wage", "jolts", "job"],
        "monetary_policy": ["fed", "rate", "hawkish", "dovish", "taper", "qe", "tightening", "easing"],
        "fiscal_policy": ["fiscal", "deficit", "spending", "tax", "stimulus", "budget"],
        "financial_conditions": ["credit", "spread", "liquidity", "financing", "lending"],
        "global_trade": ["trade", "export", "import", "tariff", "supply chain"],
        "corporate_health": ["earnings", "revenue", "margin", "corporate", "profit"],
        "consumer_health": ["consumer", "retail", "sentiment", "spending", "confidence"],
        "housing": ["housing", "home", "mortgage", "construction", "real estate"],
        "credit_markets": ["hy", "ig", "high yield", "investment grade", "default"],
        "currency_markets": ["dollar", "eur", "yen", "fx", "currency", "dxy"],
        "commodity_markets": ["oil", "gold", "copper", "commodity", "energy", "metal"],
        "geopolitical_risk": ["geopolitical", "conflict", "war", "sanction", "tension"],
        "sentiment": ["sentiment", "positioning", "flows", "survey", "aaII"],
    }

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}

    def execute(
        self,
        observation: ObservationOutput,
        belief_data: dict | None = None,
        fusion_data: dict | None = None,
    ) -> EvidenceOutput:
        """Execute evidence evaluation.

        Args:
            observation: Output from Stage 1 (Observation)
            belief_data: Current belief states and weights
            fusion_data: Unified evidence graph from V5.3 Fusion Engine

        Returns:
            EvidenceOutput with clustered, evaluated evidence
        """
        output = EvidenceOutput(
            timestamp=datetime.now().isoformat(),
            status=StageStatus.IN_PROGRESS,
        )

        # Collect all raw evidence
        all_evidence = (
            observation.observations +
            observation.data_surprises +
            observation.market_moves +
            observation.significant_news
        )

        # Add fusion data if available
        if fusion_data:
            all_evidence.extend(fusion_data.get("evidence", []))

        # 1. Cluster evidence by theme
        output.evidence_clusters = self._cluster_by_theme(all_evidence)

        # 2. Evaluate each evidence piece
        output.supporting_evidence, \
        output.contradicting_evidence, \
        output.neutral_evidence = self._evaluate_evidence(all_evidence, belief_data)

        # 3. Compute net weight
        output.net_weight = self._compute_net_weight(output)

        # 4. Identify gaps
        output.evidence_gaps = self._identify_gaps(output)

        # 5. Generate trace
        output.reasoning_trace = self._generate_trace(output)
        output.status = StageStatus.COMPLETED

        return output

    # ── Clustering ──────────────────────────────────────────────────

    def _cluster_by_theme(self, evidence: list[str]) -> dict[str, list[str]]:
        """Cluster evidence items by thematic keywords."""
        clusters: dict[str, list[str]] = {theme: [] for theme in self.EVIDENCE_THEMES}

        for item in evidence:
            item_lower = item.lower()
            matched = False
            for theme, keywords in self.THEME_KEYWORDS.items():
                if any(kw in item_lower for kw in keywords):
                    clusters[theme].append(item)
                    matched = True
            if not matched:
                clusters.setdefault("other", []).append(item)

        # Only return non-empty clusters
        return {k: v for k, v in clusters.items() if v}

    # ── Evaluation ──────────────────────────────────────────────────

    def _evaluate_evidence(
        self,
        evidence: list[str],
        belief_data: dict | None,
    ) -> tuple[list[str], list[str], list[str]]:
        """Evaluate each evidence piece for direction."""
        supporting = []
        contradicting = []
        neutral = []

        # Bullish / hawkish keywords
        bullish = [
            "strong", "beat", "above", "surge", "rally", "upgrade",
            "expansion", "growth", "improve", "positive", "hawkish",
            "tightening", "hike", "increase", "rise", "higher",
        ]

        # Bearish / dovish keywords
        bearish = [
            "weak", "miss", "below", "plunge", "selloff", "downgrade",
            "contraction", "recession", "decline", "negative", "dovish",
            "easing", "cut", "decrease", "fall", "lower",
        ]

        for item in evidence:
            item_lower = item.lower()
            bull_count = sum(1 for kw in bullish if kw in item_lower)
            bear_count = sum(1 for kw in bearish if kw in item_lower)

            if bull_count > bear_count + 1:
                supporting.append(item)
            elif bear_count > bull_count + 1:
                contradicting.append(item)
            else:
                neutral.append(item)

        return supporting, contradicting, neutral

    def _compute_net_weight(self, output: EvidenceOutput) -> float:
        """Compute net evidence weight (-1 to +1)."""
        total = (
            len(output.supporting_evidence) +
            len(output.contradicting_evidence) +
            len(output.neutral_evidence)
        )
        if total == 0:
            return 0.0

        support_weight = len(output.supporting_evidence)
        contradict_weight = len(output.contradicting_evidence)

        net = (support_weight - contradict_weight) / total
        return round(net, 3)

    def _identify_gaps(self, output: EvidenceOutput) -> list[str]:
        """Identify themes with no evidence — what are we missing?"""
        gaps = []
        covered_themes = set(output.evidence_clusters.keys())

        for theme in self.EVIDENCE_THEMES:
            if theme not in covered_themes:
                gaps.append(f"No evidence on {theme}")

        return gaps

    def _generate_trace(self, output: EvidenceOutput) -> str:
        """Generate reasoning trace."""
        trace = []
        trace.append("=== Stage 2: Evidence ===")
        trace.append(f"Themes covered: {list(output.evidence_clusters.keys())}")
        trace.append(f"Supporting: {len(output.supporting_evidence)} items")
        trace.append(f"Contradicting: {len(output.contradicting_evidence)} items")
        trace.append(f"Neutral: {len(output.neutral_evidence)} items")
        trace.append(f"Net weight: {output.net_weight:+.3f}")
        if output.evidence_gaps:
            trace.append(f"Gaps: {output.evidence_gaps}")
        return "\n".join(trace)
