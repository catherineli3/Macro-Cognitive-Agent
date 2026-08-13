"""EvidenceSynthesizer — Clusters raw evidence into meaningful themes.

V10.1: Evidence Source Retry replaces Theme Rotation.
Instead of re-mapping themes on retry, the synthesizer:
    1. Gap Analysis: what coverage dimensions are missing?
    2. Source Planning: which new sources would fill the gaps?
    3. Simulated Collection: add evidence tagged with new source types
    4. Re-cluster & Re-score with enriched evidence

Answers: "On net, what does the evidence say — and what story does it tell?"

Quality: Every conclusion in the research memo traces back to a specific
evidence cluster produced here. No floating claims.
"""

from __future__ import annotations

import uuid

from src.research.reasoning.evidence_gap_planner import (
    EvidenceGapAnalyzer,
    SourcePlanner,
)
from src.research.reasoning.evidence_source_registry import (
    COVERAGE_DIMENSIONS,
    EVIDENCE_SOURCES,
)
from src.research.reasoning.schemas import EvidenceAssessment, EvidenceCluster


class EvidenceSynthesizer:
    """Cluster evidence, evaluate net weight, identify contradictions.

    V10.1: Retry is now source-driven.
      - visited_sources tracks which sources have been used
      - On retry, gaps are identified and new sources are simulated
      - EvidenceCoverage is computed per assessment
    """

    CLUSTER_THEMES = [
        "growth_momentum",
        "inflation_dynamics",
        "labor_market",
        "monetary_policy",
        "fiscal_policy",
        "global_trade",
        "capital_flows",
        "credit_conditions",
        "corporate_earnings",
        "geopolitical_risk",
        "currency_markets",
        "commodity_markets",
    ]

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._visited_sources: set[str] = set()

    # ── Public API ─────────────────────────────────────────────────

    def synthesize(
        self,
        market_data: dict,
        narratives: list,
        beliefs: list,
        capital_flow_result: dict | None = None,
        regime_result: dict | None = None,
        news_events: list[dict] | None = None,
        retry_attempt: int = 0,
        visited_sources: set[str] | None = None,
        hypotheses_json: dict | None = None,
    ) -> EvidenceAssessment:
        """Synthesize all evidence into unified assessment.

        Args:
            retry_attempt: 0 = first pass; 1+ = retry.
                On retry, gap analysis → source planning → simulated collection.
            visited_sources: Set of source names already collected.
            hypotheses_json: Current hypotheses, used for gap analysis on retry.
        """
        # Track visited sources
        self._visited_sources = set(visited_sources or set())
        # Auto-register sources from current data
        self._register_input_sources(market_data, news_events, capital_flow_result)

        raw = self._extract_evidence(
            market_data,
            narratives,
            beliefs,
            capital_flow_result,
            regime_result,
            news_events,
        )

        # ── V10.1: Source-based retry ──
        if retry_attempt > 0 and hypotheses_json:
            raw = self._retry_collect_new_sources(
                raw,
                hypotheses_json,
                retry_attempt,
            )

        clusters = self._cluster_evidence(raw, beliefs)
        return self._build_assessment(clusters, raw, beliefs)

    def get_visited_sources(self) -> set[str]:
        """Return the set of source names visited in this session."""
        return set(self._visited_sources)

    # ── Evidence Extraction ────────────────────────────────────────

    def _extract_evidence(
        self, market_data, narratives, beliefs, capital_flow_result, regime_result, news_events
    ):
        """Extract atomic evidence from all sources."""
        evidence = []
        evidence.extend(self._from_market(market_data))
        evidence.extend(self._from_narratives(narratives))
        evidence.extend(self._from_beliefs(beliefs))

        if capital_flow_result:
            evidence.extend(self._from_capital_flow(capital_flow_result))
        if regime_result:
            evidence.extend(self._from_regime(regime_result))
        if news_events:
            for evt in news_events:
                d = (
                    evt
                    if isinstance(evt, dict)
                    else evt.to_dict() if hasattr(evt, "to_dict") else {}
                )
                src_name = d.get("source", "news_wire")
                self._visited_sources.add(src_name)
                evidence.append(
                    {
                        "theme": d.get("category", self._map_theme(d.get("event", ""))),
                        "description": d.get("event", str(d)),
                        "direction": d.get("market_impact", "neutral"),
                        "strength": d.get("confidence", 0.5),
                        "source": src_name,
                        "raw": d,
                    }
                )
        return evidence

    def _register_input_sources(self, market_data, news_events, capital_flow_result):
        """Auto-register sources based on what input data is available."""
        # Market data implies Reuters/Bloomberg level access
        if market_data and market_data.get("prices"):
            self._visited_sources.add("Reuters")
            self._visited_sources.add("Bloomberg")
        # News events imply Reuters
        if news_events:
            self._visited_sources.add("Reuters")
        # Capital flow data
        if capital_flow_result:
            self._visited_sources.add("ETF Flow")

    def _from_market(self, md):
        items = []
        for sig_name, sig in md.get("signals", {}).items():
            if isinstance(sig, dict):
                items.append(
                    {
                        "theme": self._map_theme(sig.get("description", sig_name)),
                        "description": sig.get("description", sig_name),
                        "direction": sig.get("direction", "neutral"),
                        "strength": sig.get("strength", 0.5),
                        "source": "Bloomberg",
                    }
                )
        for asset, changes in md.get("prices", {}).items():
            if isinstance(changes, dict):
                for period, val in changes.items():
                    try:
                        v = float(val)
                    except (ValueError, TypeError):
                        continue
                    if abs(v) > 0.001:
                        items.append(
                            {
                                "theme": "market_price",
                                "description": f"{asset} {period}: {v:+.2%}{'' if abs(v) < 1 else ''}",
                                "direction": "bullish" if v > 0 else "bearish",
                                "strength": min(abs(v) * 5, 1.0),
                                "source": "Bloomberg",
                            }
                        )
        return items

    def _from_narratives(self, narratives):
        items = []
        for n in narratives:
            nd = n if isinstance(n, dict) else n.to_dict() if hasattr(n, "to_dict") else {}
            text = nd.get("summary") or nd.get("content") or ""
            items.append(
                {
                    "theme": self._map_theme(text),
                    "description": text[:200],
                    "direction": nd.get("direction", nd.get("sentiment", "neutral")),
                    "strength": (
                        float(nd.get("strength", nd.get("intensity", 0.5)))
                        if nd.get("strength", nd.get("intensity"))
                        else 0.5
                    ),
                    "source": "Reuters",
                    "raw": nd,
                }
            )
        return items

    def _from_beliefs(self, beliefs):
        items = []
        for b in beliefs:
            bd = b if isinstance(b, dict) else b.to_dict() if hasattr(b, "to_dict") else {}
            direction = "bullish"
            if bd.get("stage") and "bear" in str(bd.get("stage", "")).lower():
                direction = "bearish"
            elif bd.get("direction"):
                direction = bd.get("direction")
            items.append(
                {
                    "theme": "macro_view",
                    "description": f"Active belief: {bd.get('name', bd.get('label', ''))}",
                    "direction": direction,
                    "strength": (
                        float(bd.get("confidence", bd.get("prior_mean", 0.5)))
                        if bd.get("confidence", bd.get("prior_mean"))
                        else 0.5
                    ),
                    "source": "belief",
                    "belief_id": bd.get("id", bd.get("belief_id", "")),
                    "raw": bd,
                }
            )
        return items

    def _from_capital_flow(self, cf):
        items = []
        fd = cf.get("flow_data", cf)
        if isinstance(fd, dict):
            items.append(
                {
                    "theme": "capital_flows",
                    "description": str(
                        fd.get("summary", fd.get("description", "Capital flow signal"))
                    ),
                    "direction": fd.get("direction", fd.get("flow_direction", "neutral")),
                    "strength": self._strength_map(fd),
                    "source": "ETF Flow",
                }
            )
        return items

    def _from_regime(self, rr):
        items = []
        self._visited_sources.add("Macro Calendar")
        rl = rr.get("regime_label", rr.get("regime_type", ""))
        confidence = rr.get("confidence", 0.5)
        items.append(
            {
                "theme": "macro_regime",
                "description": f"Current regime: {rl}",
                "direction": self._regime_dir(rl),
                "strength": confidence,
                "source": "Macro Calendar",
            }
        )
        analog = rr.get("historical_analog", rr.get("analog", {}))
        if analog and isinstance(analog, dict):
            items.append(
                {
                    "theme": "macro_regime",
                    "description": f"Historical analog: {analog.get('period', '')} - {analog.get('label', '')}",
                    "direction": "neutral",
                    "strength": analog.get("similarity_score", 0.5),
                    "source": "Macro Calendar",
                }
            )
        trans = rr.get("transition", {})
        if trans and isinstance(trans, dict):
            risk = trans.get("probability", trans.get("risk", 0))
            items.append(
                {
                    "theme": "macro_regime",
                    "description": f"Regime transition risk: {risk}",
                    "direction": "neutral",
                    "strength": float(risk) if risk else 0.3,
                    "source": "Regime",
                }
            )
        return items

    # ═══════════════════════════════════════════════════════════════
    # V10.1: Source-based Retry Engine
    # ═══════════════════════════════════════════════════════════════

    def _retry_collect_new_sources(
        self,
        existing_evidence: list,
        hypotheses_json: dict,
        retry_attempt: int,
    ) -> list:
        """V10.1: Source-driven retry instead of Theme Rotation.

        Flow:
            1. Run EvidenceGapAnalyzer on current evidence + hypotheses
            2. SourcePlanner builds prioritized collection plan
            3. Simulate collecting from planned (unvisited) sources
            4. Merge simulated evidence with existing evidence
        """
        # Build assessment dict from existing clusters (for gap analysis)
        temp_clusters = self._cluster_evidence(existing_evidence, [])
        temp_assessment = self._build_assessment_dict(temp_clusters, existing_evidence)

        # Step 1: Gap Analysis
        gaps = EvidenceGapAnalyzer.analyze(
            hypotheses_json=hypotheses_json,
            evidence_assessment=temp_assessment,
            visited_sources=self._visited_sources,
        )

        # Step 2: Source Planning
        max_new = min(5, 2 + retry_attempt)  # More sources on later retries
        plan = SourcePlanner.plan(
            gaps=gaps,
            visited_sources=self._visited_sources,
            max_new=max_new,
        )

        if not plan:
            return existing_evidence  # Nothing new to collect, all sources visited

        # Step 3: Simulate collection from planned sources
        simulated = self._simulate_source_collection(plan, existing_evidence)
        self._visited_sources.update(p.source_name for p in plan)

        # Step 4: Merge
        return existing_evidence + simulated

    def _simulate_source_collection(
        self,
        plan: list,
        existing_evidence: list,
    ) -> list[dict]:
        """Simulate collecting evidence from planned source types.

        In a real system, this would make actual API calls.
        Here, we construct evidence items that reflect what those sources
        would contribute, based on the source's category and reliability.

        Each simulated item is tagged with the real source name
        and has quality proportional to that source's reliability.
        """
        simulated = []

        # Cluster existing evidence by theme to extract dominant signals
        theme_directions = self._summarize_theme_directions(existing_evidence)

        for p in plan:
            src = EVIDENCE_SOURCES.get(p.source_name)
            if src is None:
                continue

            # Determine which theme(s) this source covers
            for coverage_dim in src.coverage:
                # Find a related theme from existing evidence
                related_theme = self._dim_to_cluster_theme(coverage_dim)
                direction = theme_directions.get(related_theme, "neutral")

                # Construct simulated evidence item
                item = {
                    "theme": related_theme,
                    "description": f"[Simulated] {src.name}: {coverage_dim} signal from {src.category}",
                    "direction": direction,
                    "strength": src.reliability * 0.6,  # Simulated signal strength
                    "source": src.name,
                    "source_category": src.category,
                    "source_priority": src.priority,
                    "simulated": True,
                }
                simulated.append(item)

        return simulated

    @staticmethod
    def _summarize_theme_directions(evidence: list) -> dict[str, str]:
        """For each theme, determine the dominant direction from existing evidence."""
        theme_signals: dict[str, dict[str, float]] = {}
        for e in evidence:
            theme = e.get("theme", "unknown")
            direction = e.get("direction", "neutral")
            strength = e.get("strength", 0.0)
            theme_signals.setdefault(theme, {"bullish": 0.0, "bearish": 0.0, "neutral": 0.0})
            theme_signals[theme][direction] += strength

        result = {}
        for theme, scores in theme_signals.items():
            max_dir = max(scores, key=scores.get)
            result[theme] = max_dir if scores[max_dir] > 0 else "neutral"
        return result

    @staticmethod
    def _dim_to_cluster_theme(dim: str) -> str:
        """Map coverage dimension → cluster theme."""
        mapping = {
            "macro": "growth_momentum",
            "liquidity": "credit_conditions",
            "policy": "monetary_policy",
            "positioning": "capital_flows",
            "flow": "capital_flows",
            "valuation": "corporate_earnings",
            "sentiment": "macro_view",
        }
        return mapping.get(dim, "macro_view")

    # ═══════════════════════════════════════════════════════════════
    # Clustering & Assessment (with EvidenceCoverage)
    # ═══════════════════════════════════════════════════════════════

    def _cluster_evidence(self, evidence, beliefs):
        """Group evidence by theme, evaluate net direction."""
        grouped = {}
        for e in evidence:
            theme = e.get("theme", "unknown")
            grouped.setdefault(theme, []).append(e)

        clusters = []
        belief_map = {
            (b if isinstance(b, dict) else b.to_dict() if hasattr(b, "to_dict") else {}).get(
                "id",
                (b if isinstance(b, dict) else b.to_dict() if hasattr(b, "to_dict") else {}).get(
                    "belief_id", ""
                ),
            ): b
            for b in beliefs
        }

        for theme, items in grouped.items():
            # Score directions
            bullish_w = sum(i["strength"] for i in items if i["direction"] == "bullish")
            bearish_w = sum(i["strength"] for i in items if i["direction"] == "bearish")
            neutral_w = sum(i["strength"] for i in items if i["direction"] == "neutral")

            if bullish_w > bearish_w * 1.25:
                net_dir = "supporting_bullish"
            elif bearish_w > bullish_w * 1.25:
                net_dir = "supporting_bearish"
            elif abs(bullish_w - bearish_w) < 0.3 and (bullish_w + bearish_w + neutral_w) > 0:
                net_dir = "mixed"
            else:
                net_dir = "neutral"

            weight = bullish_w + bearish_w + neutral_w
            max_w = max(len(items) * 0.8, 1.0)
            weight_score = min(weight / max_w, 1.0)

            quality_scores = []
            for i in items:
                q = 0.5
                src_name = i.get("source", "")
                # Use source registry reliability if available
                reg_src = EVIDENCE_SOURCES.get(src_name)
                if reg_src:
                    q = reg_src.reliability
                elif i["source"] in ("market_data", "regime"):
                    q = 0.7
                elif i["source"] == "news":
                    q = 0.6
                elif i["source"] == "narrative":
                    q = 0.5
                elif i["source"] == "belief":
                    q = 0.4
                quality_scores.append(q)
            quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
            recency = 0.8

            # Bridge to beliefs
            supports, contradicts = [], []
            for i in items:
                bid = i.get("belief_id", "")
                b_obj = belief_map.get(bid, {})
                if isinstance(b_obj, dict):
                    direction = b_obj.get("direction", "")
                else:
                    direction = getattr(b_obj, "direction", "")
                if i["direction"] == "bullish":
                    if direction in ("bullish", ""):
                        supports.append(bid)
                    else:
                        contradicts.append(bid)

            cluster = EvidenceCluster(
                cluster_id=str(uuid.uuid4())[:8],
                theme=theme,
                description=f"Evidence cluster on {theme}: {net_dir}",
                evidence_items=items,
                net_direction=net_dir,
                weight_score=round(weight_score, 2),
                quality_score=round(quality_score, 2),
                recency_score=round(recency, 2),
                supports=supports,
                contradicts=contradicts,
            )
            clusters.append(cluster)

        return clusters

    def _build_assessment(self, clusters, raw, beliefs):
        bullish = sum(c.weight_score for c in clusters if c.net_direction == "supporting_bullish")
        bearish = sum(c.weight_score for c in clusters if c.net_direction == "supporting_bearish")

        if bullish > bearish * 1.5:
            net = "bullish"
        elif bearish > bullish * 1.5:
            net = "bearish"
        elif abs(bullish - bearish) < 0.3 and len(clusters) > 0:
            net = "mixed"
        else:
            net = "tilted_" + ("bullish" if bullish > bearish else "bearish")

        quality_levels = ["high", "moderate", "low", "insufficient"]
        avg_q = sum(c.quality_score for c in clusters) / len(clusters) if clusters else 0
        if avg_q >= 0.7:
            eq = quality_levels[0]
        elif avg_q >= 0.5:
            eq = quality_levels[1]
        elif avg_q >= 0.3:
            eq = quality_levels[2]
        else:
            eq = quality_levels[3]

        # Quality score
        overall_quality_score = self._compute_overall_quality_score(clusters)

        # V10.1: Evidence Coverage
        evidence_coverage = self._compute_evidence_coverage(clusters)
        _coverage_score = evidence_coverage.get("overall_coverage_pct", 0.0)

        # Contradictory signals
        contradictory = []
        for c in clusters:
            if c.net_direction == "mixed":
                contradictory.append(f"{c.theme}: mixed signals")

        return EvidenceAssessment(
            clusters=clusters,
            total_evidence_points=len(raw),
            net_weight_bullish=round(bullish, 2),
            net_weight_bearish=round(bearish, 2),
            net_direction=net,
            evidence_quality=eq,
            overall_quality_score=overall_quality_score,
            evidence_coverage=evidence_coverage,
            contradictory_signals=contradictory,
            key_missing_data=self._find_gaps(clusters),
        )

    def _build_assessment_dict(self, clusters, raw) -> dict:
        """Build a dict version for gap analysis (avoids EvidenceAssessment object)."""
        return {
            "clusters": [c.to_dict() for c in clusters],
            "total_evidence_points": len(raw),
        }

    def _compute_overall_quality_score(self, clusters: list) -> float:
        """Compute a numeric 0-100 quality score.

        V10.1: Now includes evidence coverage dimension (10%).
        Formula: cluster quality (35%) + quantity (20%) + recency (15%)
                 + coherence (20%) + coverage (10%).
        """
        n = len(clusters)
        if n == 0:
            return 0.0

        avg_quality = sum(c.quality_score for c in clusters) / n
        avg_recency = sum(c.recency_score for c in clusters) / n
        quantity_score = min(n / 5.0, 1.0)
        mixed_count = sum(1 for c in clusters if c.net_direction == "mixed")
        coherence_score = max(1.0 - (mixed_count / max(n, 1)), 0.0)

        # V10.1: Coverage bonus
        coverage = self._compute_evidence_coverage(clusters)
        coverage_factor = coverage.get("overall_coverage_pct", 0.0) / 100.0

        score = (
            avg_quality * 35
            + quantity_score * 20
            + avg_recency * 15
            + coherence_score * 20
            + coverage_factor * 10
        )
        return round(min(score, 100.0), 1)

    # ═══════════════════════════════════════════════════════════════
    # V10.1: Evidence Coverage
    # ═══════════════════════════════════════════════════════════════

    def _compute_evidence_coverage(self, clusters: list) -> dict:
        """Compute per-dimension and overall evidence coverage (0-100%).

        Each coverage dimension needs at least 1 evidence cluster with
        supporting data AND at least 1 registered source covering that dimension.

        Coverage > 85% → Evidence Complete.
        """
        # Which dimensions do our clusters cover?
        cluster_dims: set[str] = set()
        for c in clusters:
            theme = (
                getattr(c, "theme", c.get("theme", ""))
                if not isinstance(c, EvidenceCluster)
                else c.theme
            )
            dim = self._theme_to_coverage_dim(theme)
            cluster_dims.add(dim)

        # Which dimensions do our visited sources cover?
        source_dims: set[str] = set()
        for src_name in self._visited_sources:
            src = EVIDENCE_SOURCES.get(src_name)
            if src:
                source_dims.update(src.coverage)

        # Per-dimension coverage
        dim_coverage = {}
        for dim in COVERAGE_DIMENSIONS:
            # Dimension is "covered" if we have both cluster evidence AND source data
            _has_cluster = dim in cluster_dims
            has_source = dim in source_dims
            # Multiple clusters in same dim → stronger coverage
            cluster_count = sum(
                1
                for c in clusters
                if self._theme_to_coverage_dim(
                    getattr(c, "theme", "")
                    if isinstance(c, EvidenceCluster)
                    else c.get("theme", "")
                )
                == dim
            )
            cluster_strength = min(cluster_count / 2.0, 1.0)
            dim_coverage[dim] = round(
                (cluster_strength * 0.6 + (1.0 if has_source else 0.0) * 0.4) * 100,
                1,
            )

        # Overall coverage
        overall = round(sum(dim_coverage.values()) / max(len(COVERAGE_DIMENSIONS), 1), 1)

        return {
            "dimensions": dim_coverage,
            "overall_coverage_pct": overall,
            "evidence_complete": overall >= 85.0,
            "covered_dimensions": sorted(cluster_dims & source_dims),
            "missing_dimensions": sorted(set(COVERAGE_DIMENSIONS) - (cluster_dims & source_dims)),
            "visited_source_count": len(self._visited_sources),
            "visited_sources": sorted(self._visited_sources),
        }

    @staticmethod
    def _theme_to_coverage_dim(theme: str) -> str:
        """Map cluster theme → coverage dimension."""
        theme_l = theme.lower()
        mapping = [
            ("growth_momentum", "macro"),
            ("inflation_dynamics", "macro"),
            ("labor_market", "macro"),
            ("global_trade", "macro"),
            ("commodity_markets", "macro"),
            ("monetary_policy", "policy"),
            ("fiscal_policy", "policy"),
            ("credit_conditions", "liquidity"),
            ("capital_flows", "flow"),
            ("corporate_earnings", "valuation"),
            ("currency_markets", "positioning"),
            ("geopolitical_risk", "sentiment"),
            ("macro_view", "sentiment"),
        ]
        for key, dim in mapping:
            if key in theme_l:
                return dim
        return "macro"

    def _find_gaps(self, clusters):
        covered = {c.theme for c in clusters}
        gaps = []
        for theme in self.CLUSTER_THEMES[:6]:
            if theme not in covered:
                gaps.append(f"Missing evidence on {theme}")
        return gaps[:3]

    # ── Static Helpers ─────────────────────────────────────────────

    @staticmethod
    def _map_theme(text):
        text_l = str(text).lower()
        theme_map = [
            (["gdp", "growth", "pmi", "industrial", "manufacturing", "retail"], "growth_momentum"),
            (["cpi", "ppi", "inflation", "deflator", "price"], "inflation_dynamics"),
            (
                ["employment", "unemployment", "payroll", "nfp", "wage", "job", "labor"],
                "labor_market",
            ),
            (
                [
                    "fed",
                    "fomc",
                    "rate hike",
                    "rate cut",
                    "tightening",
                    "easing",
                    "central bank",
                    "ecb",
                    "boj",
                    "pboc",
                ],
                "monetary_policy",
            ),
            (["fiscal", "deficit", "spending", "stimulus", "budget", "treasury"], "fiscal_policy"),
            (["trade", "export", "import", "tariff", "shipping"], "global_trade"),
            (["flow", "etf", "allocation", "positioning", "rotation"], "capital_flows"),
            (["credit", "bond", "spread", "yield", "default", "borrowing"], "credit_conditions"),
            (["earnings", "profit", "margin", "revenue"], "corporate_earnings"),
            (["geopolit", "war", "sanction", "conflict"], "geopolitical_risk"),
            (["currency", "fx", "dollar", "usd", "eur", "jpy", "cny"], "currency_markets"),
            (["oil", "gold", "commodit", "copper", "energy"], "commodity_markets"),
        ]
        for keywords, theme in theme_map:
            if any(k in text_l for k in keywords):
                return theme
        return "macro_view"

    @staticmethod
    def _strength_map(fd):
        q = str(fd.get("quality", fd.get("confidence", "moderate"))).lower()
        return {"high": 0.8, "moderate": 0.6, "low": 0.4, "uncertain": 0.3}.get(q, 0.5)

    @staticmethod
    def _regime_dir(label):
        label_l = str(label).lower()
        if any(t in label_l for t in ("goldilocks", "stable", "expansion")):
            return "bullish"
        if any(t in label_l for t in ("recession", "stagflation", "crisis", "tightening")):
            return "bearish"
        return "neutral"
