"""Research Findings Engine — Milestone B.5 (Migrated to research/findings/).

Produces structured research findings from accumulated transmission history.

Four finding categories:
    F1: Reliability Ranking — most/least reliable transmissions now
    F2: Failure Warning — transmissions starting to fail (early warning)
    F3: Failure Event Correlation — what conditions break each transmission
    F4: Regime Similarity — when did the graph last look like this?

Migration: src/transmission/research_findings.py → src/research/findings/engine.py
"""

from __future__ import annotations

from collections import Counter, defaultdict

from src.research.findings.note_generator import ResearchNoteGenerator
from src.schemas.transmission_v3_1 import (
    BreakpointDiagnosis,
    FindingConfidence,
    ResearchFinding,
    ResearchFindingsReport,
    ResearchNote,
    TransmissionEdge,
)
from src.shared.logging import get_logger
from src.transmission.transmission_graph import TransmissionGraph

logger = get_logger(__name__)


class ResearchFindingsEngine:
    """Produces structured research findings from transmission history.

    Milestone B.5: The engine that transforms the agent from "I found 3 breakpoints"
    to "My research shows that under current conditions, the liquidity→credit
    channel is the most reliable transmission, while credit→risk_appetite has
    begun to fail — consistent with the 2018 tightening episode."

    This is what makes the agent grow like a researcher, not an optimizer.
    """

    def __init__(self, graph: TransmissionGraph) -> None:
        self._graph = graph
        self._note_gen = ResearchNoteGenerator(graph)
        self._diagnosis_history: list[BreakpointDiagnosis] = []
        self._note_history: list[ResearchNote] = []
        self._context_history: list[str] = []
        self._regime_snapshots: list[dict] = []

    # ── Main Entry ───────────────────────────────────────────────────────

    def analyze(
        self,
        diagnoses: list[BreakpointDiagnosis],
        context_key: str = "",
        cycle_number: int = 0,
    ) -> ResearchFindingsReport:
        """Run full research analysis on a cycle's transmission results."""
        self._diagnosis_history.extend(diagnoses)
        self._context_history.append(context_key)

        if cycle_number % 25 == 0 or len(self._regime_snapshots) == 0:
            self._regime_snapshots.append(self._snapshot_graph(context_key, cycle_number))

        notes = self._note_gen.generate_batch(diagnoses, context_key)
        self._note_history.extend(notes)

        f1 = self._find_most_reliable(context_key)
        f2 = self._find_failing_warnings(context_key)
        f3 = self._find_failure_correlations(context_key)
        f4 = self._find_regime_similarities(context_key)

        summary = self._build_summary(f1, f2, f3, f4, context_key)

        return ResearchFindingsReport(
            context_key=context_key,
            cycle_number=cycle_number,
            reliability_ranking=f1,
            failure_warnings=f2,
            failure_event_correlations=f3,
            regime_similarities=f4,
            research_notes=notes,
            summary=summary,
        )

    # ── F1: Reliability Ranking ──────────────────────────────────────────

    def _find_most_reliable(self, ctx: str) -> list[ResearchFinding]:
        findings: list[ResearchFinding] = []

        for rank, edge in enumerate(self._graph.top_edges(n=5, context_key=ctx), 1):
            cr = edge.reliability_in_context(ctx) if ctx else edge.reliability_default
            desc = (
                f"{edge.segment_id}: rel={cr:.1%}, str={edge.edge_strength:.2f}, "
                f"latency={edge.latency_days}d, evidence={edge.observation_count} obs. "
                f"Quality score: {edge.quality_score():.3f}."
            )
            if edge.named_failure_modes:
                desc += f" Failure modes: {', '.join(edge.named_failure_modes[:3])}."

            findings.append(
                ResearchFinding(
                    category="reliability_ranking",
                    title=f"#{rank} Most Reliable: {edge.segment_id} (q={edge.quality_score():.3f})",
                    description=desc,
                    evidence={
                        "rank": rank,
                        "reliability": cr,
                        "strength": edge.edge_strength,
                        "quality": edge.quality_score(),
                        "observations": edge.observation_count,
                    },
                    relevance_score=round(edge.quality_score(), 3),
                    confidence=self._obs_conf(edge.observation_count),
                    source_edges=[edge.segment_id],
                    context_key=ctx,
                )
            )

        for edge in self._graph.weakest_edges(n=3):
            if edge.reliability_default < 0.40:
                desc = (
                    f"WARNING: {edge.segment_id} reliability only {edge.reliability_default:.1%}. "
                    f"Break rate {edge.break_rate:.0%} ({edge.break_count}/{edge.observation_count}). "
                    f"Strength {edge.edge_strength:.2f}. This edge is structurally unreliable."
                )
                findings.append(
                    ResearchFinding(
                        category="reliability_ranking",
                        title=f"Weak: {edge.segment_id} (rel={edge.reliability_default:.1%})",
                        description=desc,
                        evidence={
                            "reliability": edge.reliability_default,
                            "break_rate": edge.break_rate,
                            "strength": edge.edge_strength,
                        },
                        relevance_score=round(1.0 - edge.reliability_default, 3),
                        confidence=self._obs_conf(edge.observation_count),
                        source_edges=[edge.segment_id],
                        context_key=ctx,
                    )
                )

        return findings

    # ── F2: Failure Warning ──────────────────────────────────────────────

    def _find_failing_warnings(self, ctx: str) -> list[ResearchFinding]:
        findings: list[ResearchFinding] = []
        recent = [d for d in self._diagnosis_history[-20:] if d.breakpoint_found]

        if recent:
            break_counts: Counter = Counter()
            for d in recent:
                break_counts[d.breakpoint_segment] += 1

            for seg_id, count in break_counts.most_common(5):
                if count >= 2:
                    edge = self._find_edge_by_segment(seg_id)
                    rel = edge.reliability_default if edge else 0.50
                    obs = edge.observation_count if edge else 0

                    desc = (
                        f"{seg_id} has broken {count} times in recent cycles. "
                        f"Current reliability: {rel:.1%}. "
                        f"This transmission is showing signs of degradation."
                    )
                    if edge and edge.dominant_failure_mode:
                        desc += f" Primary failure: {edge.dominant_failure_mode.name}."

                    findings.append(
                        ResearchFinding(
                            category="failure_warning",
                            title=f"Failing: {seg_id} ({count} recent breaks)",
                            description=desc,
                            evidence={
                                "recent_breaks": count,
                                "reliability": rel,
                                "observations": obs,
                            },
                            relevance_score=min(0.95, count / 10),
                            confidence=self._obs_conf(obs),
                            source_edges=[seg_id],
                            context_key=ctx,
                        )
                    )

        for edge in self._graph.all_edges():
            if edge.observation_count >= 10 and edge.break_rate > 0.15:
                if not any(
                    f.title.startswith("Failing:") and edge.segment_id in f.title for f in findings
                ):
                    desc = (
                        f"{edge.segment_id} has elevated break rate: {edge.break_rate:.1%} "
                        f"({edge.break_count}/{edge.observation_count}). "
                        f"Reliability: {edge.reliability_default:.1%}, "
                        f"Strength: {edge.edge_strength:.2f}."
                    )
                    findings.append(
                        ResearchFinding(
                            category="failure_warning",
                            title=f"Elevated breaks: {edge.segment_id} ({edge.break_rate:.0%} rate)",
                            description=desc,
                            evidence={
                                "break_rate": edge.break_rate,
                                "break_count": edge.break_count,
                                "observations": edge.observation_count,
                            },
                            relevance_score=round(edge.break_rate, 3),
                            confidence=self._obs_conf(edge.observation_count),
                            source_edges=[edge.segment_id],
                            context_key=ctx,
                        )
                    )

        return findings

    # ── F3: Failure Event Correlation ────────────────────────────────────

    def _find_failure_correlations(self, ctx: str) -> list[ResearchFinding]:
        findings: list[ResearchFinding] = []
        fm_by_edge: dict[str, list] = defaultdict(list)
        for edge in self._graph.all_edges():
            for fm in edge.failure_modes:
                fm_by_edge[edge.segment_id].append(fm)

        for seg_id, fms in fm_by_edge.items():
            if len(fms) < 3:
                continue
            edge = self._find_edge_by_segment(seg_id)
            if not edge:
                continue

            names = [fm.name for fm in fms if fm.name]
            cats = Counter(fm.category.value for fm in fms)

            if names:
                desc = (
                    f"{seg_id} most commonly fails due to: {', '.join(names[:3])}. "
                    f"Failure categories: {dict(cats.most_common(3))}. "
                    f"Edge reliability: {edge.reliability_default:.1%} "
                    f"({edge.observation_count} obs)."
                )
                findings.append(
                    ResearchFinding(
                        category="failure_event_correlation",
                        title=f"Failure pattern: {seg_id} → {names[0]}",
                        description=desc,
                        evidence={
                            "failure_modes": names[:5],
                            "categories": dict(cats.most_common(5)),
                            "total_failures": len(fms),
                        },
                        relevance_score=min(0.9, len(fms) / 20),
                        confidence=self._obs_conf(edge.observation_count),
                        source_edges=[seg_id],
                        context_key=ctx,
                    )
                )

        return findings

    # ── F4: Regime Similarity ────────────────────────────────────────────

    def _find_regime_similarities(self, ctx: str) -> list[ResearchFinding]:
        findings: list[ResearchFinding] = []

        if len(self._regime_snapshots) < 2:
            if self._diagnosis_history:
                findings.append(
                    ResearchFinding(
                        category="regime_similarity",
                        title="Building transmission history baseline",
                        description=f"Accumulated {len(self._diagnosis_history)} diagnoses. "
                        f"Regime comparison requires multiple cycles to "
                        f"establish baselines for similarity analysis.",
                        relevance_score=0.3,
                        confidence=FindingConfidence.PRELIMINARY,
                        context_key=ctx,
                    )
                )
            return findings

        current = self._snapshot_graph(ctx, -1)
        if not current:
            return findings

        similarities = []
        for snap in self._regime_snapshots[:-1]:
            score = self._regime_similarity_score(current, snap)
            similarities.append((score, snap))

        similarities.sort(key=lambda x: x[0], reverse=True)

        for score, snap in similarities[:3]:
            if score < 0.3:
                continue
            snap_ctx = snap.get("context", "unknown")
            snap_cycle = snap.get("cycle", 0)
            desc = (
                f"Current transmission graph resembles the state at cycle "
                f"{snap_cycle} ({snap_ctx}), similarity={score:.1%}. "
                f"At that time, the dominant pattern was similar edge "
                f"reliability distribution."
            )
            findings.append(
                ResearchFinding(
                    category="regime_similarity",
                    title=f"Similar to cycle #{snap_cycle} ({snap_ctx}) — score {score:.0%}",
                    description=desc,
                    evidence={
                        "similarity_score": score,
                        "matched_cycle": snap_cycle,
                        "matched_context": snap_ctx,
                    },
                    relevance_score=round(score, 3),
                    confidence=(
                        FindingConfidence.OBSERVED if score > 0.6 else FindingConfidence.PRELIMINARY
                    ),
                    context_key=ctx,
                )
            )

        return findings

    # ── Helpers ──────────────────────────────────────────────────────────

    def _snapshot_graph(self, ctx: str, cycle: int) -> dict:
        edges_summary = {}
        for edge in self._graph.all_edges():
            if edge.observation_count >= 5:
                edges_summary[edge.segment_id] = {
                    "reliability": edge.reliability_default,
                    "strength": edge.edge_strength,
                    "observation_count": edge.observation_count,
                    "break_rate": edge.break_rate,
                }
        return {
            "context": ctx,
            "cycle": cycle,
            "edge_count": len(edges_summary),
            "edges": edges_summary,
            "stability": self._graph.reliability_stability(),
        }

    @staticmethod
    def _regime_similarity_score(current: dict, historical: dict) -> float:
        cur_edges = current.get("edges", {})
        hist_edges = historical.get("edges", {})
        common = set(cur_edges) & set(hist_edges)
        if not common:
            return 0.0
        total_diff = 0.0
        for seg_id in common:
            cur_rel = cur_edges[seg_id].get("reliability", 0.5)
            hist_rel = hist_edges[seg_id].get("reliability", 0.5)
            total_diff += abs(cur_rel - hist_rel)
        avg_diff = total_diff / len(common)
        return round(max(0.0, 1.0 - avg_diff), 4)

    def _build_summary(self, f1, f2, f3, f4, ctx: str) -> str:
        parts = [f"Research Findings Summary [{ctx or 'default'}]:"]
        parts.append(f"  Most reliable: {f1[0].title if f1 else 'insufficient data'}")
        if f2:
            parts.append(f"  Warnings: {len(f2)} transmissions showing stress")
        else:
            parts.append("  Warnings: none — all transmissions within normal range")
        if f3:
            parts.append(f"  Failure patterns: {len(f3)} identified")
        if f4:
            parts.append(f"  Regime comparison: {f4[0].title if f4 else 'baseline'}")
        parts.append(
            f"  Total evidence: {self._graph.total_observations} observations "
            f"across {self._graph.edge_count} edges"
        )
        return "\n".join(parts)

    def _find_edge_by_segment(self, seg_id: str) -> TransmissionEdge | None:
        for e in self._graph.all_edges():
            if e.segment_id == seg_id:
                return e
        return None

    @staticmethod
    def _obs_conf(obs: int) -> FindingConfidence:
        if obs >= 100:
            return FindingConfidence.ROBUST
        if obs >= 50:
            return FindingConfidence.ESTABLISHED
        if obs >= 20:
            return FindingConfidence.OBSERVED
        return FindingConfidence.PRELIMINARY

    @property
    def total_diagnoses(self) -> int:
        return len(self._diagnosis_history)

    @property
    def total_notes(self) -> int:
        return len(self._note_history)
