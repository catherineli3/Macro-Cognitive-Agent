"""V10.1 — Evidence Gap Analyzer & Source Planner.

EvidenceGapAnalyzer:
    Given current hypotheses + evidence assessment, identifies which
    coverage dimensions and evidence sources are missing.

SourcePlanner:
    Given missing evidence gaps, plans the next round of source collection.
    Prioritizes by: (1) hypothesis domain relevance, (2) source priority,
    (3) coverage gap size. Never repeats already-visited sources.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.research.reasoning.evidence_source_registry import (
    EvidenceSource,
    EVIDENCE_SOURCES,
    COVERAGE_DIMENSIONS,
    get_sources_by_coverage,
    SourceCategory,
)


# ═══════════════════════════════════════════════════════════════════
# Evidence Gap Analyzer
# ═══════════════════════════════════════════════════════════════════


@dataclass
class EvidenceGap:
    """A single gap: one coverage dimension with insufficient evidence."""

    dimension: str                          # e.g. "positioning", "policy"
    current_coverage_pct: float = 0.0       # 0-100: how covered is this dimension?
    needed_by_hypotheses: list[str] = field(default_factory=list)  # Which hypothesis_ids need this?
    recommended_sources: list[str] = field(default_factory=list)   # Source names to fill this gap

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "current_coverage_pct": self.current_coverage_pct,
            "needed_by_hypotheses": self.needed_by_hypotheses,
            "recommended_sources": self.recommended_sources,
        }


class EvidenceGapAnalyzer:
    """Analyzes gaps between hypothesis needs and current evidence coverage.

    Input:
        - hypotheses_json: list of hypothesis dicts with domain and statement
        - evidence_assessment: dict with clusters and visited_sources
        - visited_sources: set of source names already collected

    Output:
        - list of EvidenceGap objects, one per under-covered dimension
    """

    # Domain → required coverage dimensions
    DOMAIN_COVERAGE_MAP: dict[str, list[str]] = {
        "growth": ["macro", "valuation", "sentiment"],
        "inflation": ["macro", "policy", "positioning"],
        "monetary": ["policy", "liquidity", "macro"],
        "fiscal": ["macro", "liquidity", "policy"],
        "external": ["macro", "flow", "positioning"],
        "financial": ["liquidity", "positioning", "sentiment"],
        "labor": ["macro", "sentiment"],
        "housing": ["macro", "valuation"],
        "corporate": ["valuation", "sentiment", "flow"],
        "commodity": ["macro", "positioning", "flow"],
        "fx": ["macro", "policy", "flow", "positioning"],
        "credit": ["liquidity", "valuation", "sentiment"],
        "equity": ["valuation", "flow", "sentiment", "macro"],
        "rate": ["policy", "liquidity", "macro"],
        "geopolitical": ["sentiment", "flow"],
    }

    # Minimum coverage threshold per dimension
    COVERAGE_THRESHOLD = 0.6  # 60% per dimension = covered

    @classmethod
    def analyze(
        cls,
        hypotheses_json: dict,
        evidence_assessment: dict,
        visited_sources: set,
    ) -> list[EvidenceGap]:
        """Identify evidence gaps by comparing hypothesis needs against current coverage.

        Returns list of EvidenceGap, sorted by severity (least covered first).
        """
        # Step 1: Determine which dimensions are needed
        needed_dims: set[str] = set()
        dim_to_hypotheses: dict[str, list[str]] = {}

        for hyp in hypotheses_json.get("hypotheses", []):
            domain = hyp.get("domain", "growth")
            hyp_id = hyp.get("hypothesis_id", "")
            for dim in cls.DOMAIN_COVERAGE_MAP.get(domain, ["macro", "sentiment"]):
                needed_dims.add(dim)
                dim_to_hypotheses.setdefault(dim, []).append(hyp_id)

        # Step 2: Estimate current coverage per dimension from evidence clusters
        current_coverage = cls._estimate_coverage(evidence_assessment, visited_sources)

        # Step 3: Identify gaps
        gaps: list[EvidenceGap] = []
        for dim in sorted(needed_dims):
            coverage_pct = current_coverage.get(dim, 0.0)
            if coverage_pct < cls.COVERAGE_THRESHOLD:
                # Recommend sources for this dimension, excluding visited
                all_sources = get_sources_by_coverage(dim)
                recommended = [
                    s.name for s in all_sources
                    if s.name not in visited_sources
                ]
                recommended.sort(
                    key=lambda name: EVIDENCE_SOURCES[name].priority,
                    reverse=True,
                )
                gaps.append(EvidenceGap(
                    dimension=dim,
                    current_coverage_pct=round(coverage_pct * 100, 1),
                    needed_by_hypotheses=dim_to_hypotheses.get(dim, []),
                    recommended_sources=recommended[:4],  # Top 4 per gap
                ))

        # Sort: least covered first
        gaps.sort(key=lambda g: g.current_coverage_pct)
        return gaps

    @classmethod
    def _estimate_coverage(
        cls,
        evidence: dict,
        visited_sources: set,
    ) -> dict[str, float]:
        """Estimate per-dimension coverage from existing evidence + source metadata.

        Coverage = f(clusters_in_dimension, sources_covering_dim, evidence_completeness)
        """
        # Count clusters by their likely dimension mapping
        clusters = evidence.get("clusters", [])
        dim_hits: dict[str, int] = {d: 0 for d in COVERAGE_DIMENSIONS}

        for c in clusters:
            theme = c.get("theme", "") if isinstance(c, dict) else getattr(c, "theme", "")
            dim = cls._theme_to_dimension(theme)
            dim_hits[dim] = dim_hits.get(dim, 0) + 1

        # Estimate coverage: each dimension needs ~2 clusters for "covered"
        coverage = {}
        for dim in COVERAGE_DIMENSIONS:
            cluster_weight = min(dim_hits.get(dim, 0) / 2.0, 1.0) * 0.7
            # Source presence weight
            source_weight = cls._source_dim_coverage(visited_sources, dim) * 0.3
            coverage[dim] = cluster_weight + source_weight

        return coverage

    @classmethod
    def _theme_to_dimension(cls, theme: str) -> str:
        """Map evidence cluster theme → coverage dimension."""
        theme_l = theme.lower()
        mapping = [
            (["growth", "gdp", "pmi", "industrial", "output"], "macro"),
            (["inflation", "cpi", "ppi", "price", "deflator"], "macro"),
            (["labor", "employment", "unemployment", "payroll", "wage"], "macro"),
            (["trade", "export", "import"], "macro"),
            (["monetary", "fed", "fomc", "rate", "central bank"], "policy"),
            (["fiscal", "deficit", "stimulus", "spending"], "policy"),
            (["positioning", "cot", "cftc", "exposure"], "positioning"),
            (["flow", "etf", "allocation", "fund"], "flow"),
            (["credit", "spread", "default", "bond"], "liquidity"),
            (["liquidity", "auction", "repo", "reserve"], "liquidity"),
            (["sentiment", "survey", "confidence", "fear"], "sentiment"),
            (["earnings", "profit", "margin", "valuation", "pe", "guidance"], "valuation"),
        ]
        for keywords, dim in mapping:
            if any(k in theme_l for k in keywords):
                return dim
        return "macro"  # default

    @classmethod
    def _source_dim_coverage(cls, visited: set, dim: str) -> float:
        """Fraction of dimension covered by visited sources (0-1)."""
        relevant = get_sources_by_coverage(dim)
        if not relevant:
            return 0.0
        covered = sum(1 for s in relevant if s.name in visited)
        return min(covered / max(len(relevant), 1), 1.0)


# ═══════════════════════════════════════════════════════════════════
# Source Planner
# ═══════════════════════════════════════════════════════════════════


@dataclass
class SourcePlan:
    """A plan item: one source to collect, with rationale."""

    source_name: str
    category: str
    priority: int
    fills_gap: str           # Which dimension this source fills
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "source_name": self.source_name,
            "category": self.category,
            "priority": self.priority,
            "fills_gap": self.fills_gap,
            "rationale": self.rationale,
        }


class SourcePlanner:
    """Plans evidence collection based on gap analysis.

    Priority rules:
        1. Gaps needed by more hypotheses → higher priority
        2. Source priority (from registry) → tiebreaker
        3. Never repeat visited sources
        4. Cap at reasonable number of new sources per round
    """

    MAX_SOURCES_PER_PLAN = 5

    @classmethod
    def plan(
        cls,
        gaps: list[EvidenceGap],
        visited_sources: set,
        max_new: int = 5,
    ) -> list[SourcePlan]:
        """Build a prioritized collection plan from identified gaps.

        Args:
            gaps: Gap analysis results (sorted by severity)
            visited_sources: Already-collected source names
            max_new: Maximum new sources to plan per round

        Returns:
            Prioritized list of SourcePlan items
        """
        plans: list[SourcePlan] = []
        planned_sources: set = set()

        # Sort gaps: more hypotheses needing + lower coverage first
        for gap in sorted(gaps, key=lambda g: (
            -len(g.needed_by_hypotheses),
            g.current_coverage_pct,
        )):
            for src_name in gap.recommended_sources:
                if src_name in visited_sources:
                    continue
                if src_name in planned_sources:
                    continue
                if len(plans) >= max_new:
                    break

                src = EVIDENCE_SOURCES.get(src_name)
                if src is None:
                    continue

                plans.append(SourcePlan(
                    source_name=src.name,
                    category=src.category,
                    priority=src.priority,
                    fills_gap=gap.dimension,
                    rationale=(
                        f"Hypothesis domain requires {gap.dimension} coverage "
                        f"({gap.current_coverage_pct:.0f}%); "
                        f"{src.name} (priority={src.priority}) fills this gap"
                    ),
                ))
                planned_sources.add(src_name)

            if len(plans) >= max_new:
                break

        # Sort final plan by priority descending
        plans.sort(key=lambda p: p.priority, reverse=True)
        return plans[:max_new]
