"""Transmission Graph Engine — Competition-aware directed graph with 5-attribute edges.

Milestone B.5: Transmission Reasoning + Competition + Research Findings.

Five attributes per edge:
    Reliability | Latency | Strength | Failure Modes | Evidence Count

Competition:
    Multiple mechanism-edges between same source→target.
    e.g. Dollar→Gold: "real_yield_channel" vs "liquidity_channel"
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.schemas.transmission_v3_1 import (
    BreakpointDiagnosis, BreakpointSeverity, FailureMode, FailureModeCategory,
    SegmentDiagnosis, TransmissionAction, TransmissionEdge, TransmissionUpdateRecord,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)

_INITIAL_EDGES: list[tuple] = [
    ("liquidity", "NASDAQ", "+", "direct", 5, 0.60),
    ("liquidity", "USD", "-", "direct", 7, 0.45),
    ("liquidity", "Gold", "-", "direct", 7, 0.40),
    ("credit", "HYG", "+", "direct", 3, 0.70),
    ("credit", "SPX", "+", "direct", 5, 0.55),
    ("growth", "SPX", "+", "direct", 10, 0.55),
    ("growth", "US10Y", "+", "direct", 10, 0.50),
    ("growth", "DXY", "+", "direct", 10, 0.40),
    ("risk_appetite", "SPX", "+", "direct", 3, 0.65),
    ("risk_appetite", "VIX", "-", "direct", 1, 0.75),
    ("risk_appetite", "HYG", "+", "direct", 3, 0.60),
    ("inflation", "TIPS", "-", "direct", 10, 0.50),
    ("inflation", "Gold", "+", "direct", 10, 0.55),
    ("inflation", "US10Y", "+", "direct", 10, 0.60),
]

_INTER_EDGES: list[tuple] = [
    ("liquidity", "credit", "+", "credit_channel", 7, 0.65),
    ("credit", "risk_appetite", "+", "sentiment_channel", 3, 0.60),
    ("liquidity", "risk_appetite", "+", "direct_risk_channel", 7, 0.50),
    ("growth", "credit", "+", "fundamental_channel", 10, 0.55),
    ("inflation", "growth", "-", "stagflation_channel", 14, 0.40),
    ("liquidity", "inflation", "+", "monetary_channel", 14, 0.35),
    ("risk_appetite", "credit", "+", "feedback_loop", 1, 0.45),
]

_CROSS_ASSET: list[tuple] = [
    ("USD", "Gold", "-", "dollar_peg", 1, 0.70),
    ("US10Y", "NASDAQ", "-", "discount_rate", 3, 0.60),
    ("VIX", "SPX", "-", "fear_index", 1, 0.80),
    ("SPX", "VIX", "-", "fear_index_reverse", 1, 0.70),
    ("DXY", "NASDAQ", "-", "dollar_equity", 3, 0.55),
    ("HYG", "SPX", "+", "credit_equity", 2, 0.65),
    ("TIPS", "Gold", "-", "real_yield_gold", 5, 0.60),
    ("US10Y", "Gold", "-", "nominal_yield_gold", 3, 0.55),
]

_COMPETING_EDGES: list[tuple] = [
    ("USD", "Gold", "-", "real_yield_channel", 3, 0.55),
    ("USD", "Gold", "-", "liquidity_channel", 5, 0.45),
    ("liquidity", "NASDAQ", "+", "credit_risk_channel", 7, 0.55),
    ("liquidity", "NASDAQ", "+", "discount_rate_channel", 5, 0.45),
    ("credit", "SPX", "+", "capex_channel", 10, 0.50),
    ("credit", "SPX", "+", "risk_appetite_channel", 3, 0.55),
]


@dataclass
class CompetitionResult:
    source: str
    target: str
    context_key: str
    mechanisms: list = field(default_factory=list)
    winner: Optional[TransmissionEdge] = None
    margin: float = 0.0
    analysis: str = ""
    winner_quality: float = 0.0
    runner_up_quality: float = 0.0

    @property
    def is_conclusive(self) -> bool:
        return self.margin > 0.08

    def __repr__(self) -> str:
        w = self.winner.segment_id if self.winner else "none"
        return f"<Competition {self.source}→{self.target} winner={w} margin={self.margin:.3f}>"


class TransmissionGraph:
    """Competition-aware graph with 5-attribute edges."""

    def __init__(self) -> None:
        self._edges: dict[str, TransmissionEdge] = {}            # edge_id → edge
        self._pair_index: dict[tuple, list[str]] = defaultdict(list)  # (s,t) → [edge_id]
        self._outgoing: dict[str, list[str]] = defaultdict(list)
        self._incoming: dict[str, list[str]] = defaultdict(list)
        self._total_updates: int = 0
        self._total_competitions_resolved: int = 0
        self._initialize_graph()

    def _initialize_graph(self) -> None:
        all_tuples = _INITIAL_EDGES + _INTER_EDGES + _CROSS_ASSET + _COMPETING_EDGES
        for src, tgt, d, m, lat, s in all_tuples:
            self.add_edge(source=src, target=tgt, direction=d, mechanism=m,
                          latency_days=lat, edge_strength=s)
        comps = sum(1 for p, ids in self._pair_index.items() if len(ids) > 1)
        logger.info("graph_init edges=%d nodes=%d competitions=%d",
                     len(self._edges), len(self._outgoing), comps)

    @staticmethod
    def _default_conditions(source: str, target: str) -> list[str]:
        c = []
        if "VIX" in (source, target) or "risk_appetite" in (source, target):
            c.append("VIX < 25")
        if "inflation" in (source, target):
            c.append("inflation trend stable")
        if "liquidity" in (source, target):
            c.append("Fed not in emergency mode")
        return c

    # ── Edge Management ──────────────────────────────────────────────────

    def add_edge(self, source: str, target: str, direction: str = "+",
                 mechanism: str = "", latency_days: int = 5,
                 edge_strength: float = 0.50, reliability: float = 0.50,
                 ) -> TransmissionEdge:
        eid = f"te-{uuid4().hex[:8]}"
        edge = TransmissionEdge(
            edge_id=eid, source=source, target=target, direction=direction,
            mechanism=mechanism, latency_days=latency_days, edge_strength=edge_strength,
            reliability_default=reliability,
            conditions_for_validity=self._default_conditions(source, target),
        )
        self._edges[eid] = edge
        self._pair_index[(source, target)].append(eid)
        if target not in self._outgoing[source]:
            self._outgoing[source].append(target)
        if source not in self._incoming[target]:
            self._incoming[target].append(source)
        return edge

    def get_edge(self, source: str, target: str, mechanism: str = "") -> Optional[TransmissionEdge]:
        eids = self._pair_index.get((source, target), [])
        if not eids:
            return None
        if mechanism:
            for eid in eids:
                e = self._edges.get(eid)
                if e and e.mechanism == mechanism:
                    return e
            return None
        for eid in eids:
            e = self._edges.get(eid)
            if e and not e.mechanism:
                return e
        return self._edges.get(eids[0]) if eids else None

    def get_edges_between(self, source: str, target: str) -> list[TransmissionEdge]:
        eids = self._pair_index.get((source, target), [])
        return [self._edges[eid] for eid in eids if eid in self._edges]

    def has_edge(self, source: str, target: str, mechanism: str = "") -> bool:
        return self.get_edge(source, target, mechanism) is not None

    def has_competition(self, source: str, target: str) -> bool:
        return len(self._pair_index.get((source, target), [])) > 1

    def all_edges(self) -> list[TransmissionEdge]:
        return list(self._edges.values())

    def active_edges(self, min_observation: int = 10) -> list[TransmissionEdge]:
        return [e for e in self._edges.values() if e.observation_count >= min_observation]

    def competing_pairs(self) -> list[tuple]:
        return [(s, t) for (s, t), ids in self._pair_index.items() if len(ids) > 1]

    # ── Competition Resolution ───────────────────────────────────────────

    def dominant_mechanism(self, source: str, target: str,
                           context_key: str = "") -> Optional[TransmissionEdge]:
        edges = self.get_edges_between(source, target)
        if not edges:
            return None
        if len(edges) == 1:
            return edges[0]
        scored = [(e.quality_score(), e) for e in edges]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def resolve_competition(self, source: str, target: str,
                            context_key: str = "") -> CompetitionResult:
        edges = self.get_edges_between(source, target)
        if len(edges) < 2:
            w = edges[0] if edges else None
            return CompetitionResult(source=source, target=target, context_key=context_key,
                                     mechanisms=edges, winner=w, margin=1.0 if w else 0.0,
                                     analysis=f"Single mechanism: {w.segment_id if w else 'none'}",
                                     winner_quality=w.quality_score() if w else 0.0)
        scored = [(e.quality_score(), e) for e in edges]
        scored.sort(key=lambda x: x[0], reverse=True)
        winner, rup = scored[0][1], scored[1][1] if len(scored) > 1 else None
        w_s, r_s = scored[0][0], scored[1][0] if len(scored) > 1 else 0.0
        margin = w_s - r_s

        lines = [f"Competition: {source}→{target} ({len(edges)} mechanisms)"]
        for q, e in scored:
            cr = e.reliability_in_context(context_key) if context_key else e.reliability_default
            lines.append(f"  [{e.mechanism or 'default'}]: quality={q:.3f} rel={cr:.2f} "
                         f"str={e.edge_strength:.2f} obs={e.observation_count}")
        if margin > 0.10:
            lines.append(f"Result: {winner.mechanism} CLEARLY dominates (margin={margin:.3f})")
        elif margin > 0.03:
            lines.append(f"Result: {winner.mechanism} slightly preferred (margin={margin:.3f})")
        else:
            lines.append(f"Result: Too close to call ({margin:.3f})")
        self._total_competitions_resolved += 1

        return CompetitionResult(source=source, target=target, context_key=context_key,
                                 mechanisms=edges, winner=winner, margin=margin,
                                 analysis="\n".join(lines), winner_quality=w_s, runner_up_quality=r_s)

    def promote_mechanism(self, source: str, target: str, mechanism: str,
                          context_key: str = "", boost: float = 0.03) -> TransmissionUpdateRecord:
        e = self.get_edge(source, target, mechanism)
        if not e:
            return TransmissionUpdateRecord(action=TransmissionAction.NO_CHANGE)
        u = TransmissionUpdateRecord(segment_id=e.segment_id, source=source, target=target,
                                     mechanism=mechanism, action=TransmissionAction.PROMOTE_MECHANISM,
                                     context_key=context_key, reliability_delta=boost,
                                     competition_delta=boost * 1.5,
                                     reason=f"Won competition: {source}→{target}[{mechanism}]")
        self.apply_update(u)
        return u

    def demote_mechanism(self, source: str, target: str, mechanism: str,
                         context_key: str = "", penalty: float = -0.04) -> TransmissionUpdateRecord:
        e = self.get_edge(source, target, mechanism)
        if not e:
            return TransmissionUpdateRecord(action=TransmissionAction.NO_CHANGE)
        u = TransmissionUpdateRecord(segment_id=e.segment_id, source=source, target=target,
                                     mechanism=mechanism, action=TransmissionAction.DEMOTE_MECHANISM,
                                     context_key=context_key, reliability_delta=penalty,
                                     competition_delta=penalty,
                                     reason=f"Lost competition: {source}→{target}[{mechanism}]")
        self.apply_update(u)
        return u

    # ── Path Finding ─────────────────────────────────────────────────────

    def trace_paths(self, source: str, target: str, max_depth: int = 5) -> list[list[str]]:
        if source == target:
            return [[source]]
        paths: list[list[str]] = []
        queue: deque[tuple[str, list[str]]] = deque([(source, [source])])
        while queue:
            node, path = queue.popleft()
            if len(path) > max_depth:
                continue
            for nb in self._outgoing.get(node, []):
                if nb in path:
                    continue
                np = path + [nb]
                if nb == target:
                    paths.append(np)
                else:
                    queue.append((nb, np))
        return paths

    def mechanism_paths(self, source: str, target: str,
                        max_depth: int = 5) -> list[list[TransmissionEdge]]:
        node_paths = self.trace_paths(source, target, max_depth)
        edge_paths: list[list[TransmissionEdge]] = []

        for np in node_paths:
            step_edges: list[list[TransmissionEdge]] = []
            for i in range(len(np) - 1):
                es = self.get_edges_between(np[i], np[i + 1])
                step_edges.append(es if es else [])
            if not step_edges:
                continue

            def _combine(idx: int, cur: list[TransmissionEdge]):
                if idx == len(step_edges):
                    edge_paths.append(list(cur))
                    return
                for e in step_edges[idx]:
                    cur.append(e)
                    _combine(idx + 1, cur)
                    cur.pop()
            _combine(0, [])
        return edge_paths

    def edges_on_path(self, path: list[str]) -> list[TransmissionEdge]:
        es = []
        for i in range(len(path) - 1):
            e = self.dominant_mechanism(path[i], path[i + 1])
            if e:
                es.append(e)
        return es

    def path_reliability(self, path: list[str], context_key: str = "") -> float:
        es = self.edges_on_path(path)
        if not es:
            return 0.0
        rels = [e.reliability_in_context(context_key) if context_key else e.reliability_default for e in es]
        prod = 1.0
        for r in rels:
            prod *= max(r, 0.01)
        gm = prod ** (1.0 / len(rels))
        lp = max(0.6, 1.0 - (len(es) - 1) * 0.03)
        return round(gm * lp, 4)

    def strongest_path(self, source: str, target: str, context_key: str = "",
                       max_depth: int = 5) -> Optional[tuple[list[str], float]]:
        ps = self.trace_paths(source, target, max_depth)
        if not ps:
            return None
        scored = [(p, self.path_reliability(p, context_key)) for p in ps]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0]

    def compare_paths(self, pa: list[str], pb: list[str],
                      context_key: str = "") -> dict:
        ra = self.path_reliability(pa, context_key)
        rb = self.path_reliability(pb, context_key)
        d = ra - rb
        w = "tie" if abs(d) < 0.03 else ("a" if d > 0 else "b")
        a_text = f"Path A ({'→'.join(pa)}) reliability={ra:.3f}"
        b_text = f"Path B ({'→'.join(pb)}) reliability={rb:.3f}"
        return {"winner": w, "reliability_diff": d, "path_a_reliability": ra,
                "path_b_reliability": rb, "path_a_length": len(pa) - 1,
                "path_b_length": len(pb) - 1,
                "analysis": f"{a_text} vs {b_text}: {'tie' if w=='tie' else w+' wins'}"}

    # ── Breakpoint Detection ─────────────────────────────────────────────

    def find_breakpoint(self, expected_chain: list[str],
                        actual_segment_states: dict[str, bool],
                        context_key: str = "") -> BreakpointDiagnosis:
        d = BreakpointDiagnosis(expected_chain=expected_chain)
        if len(expected_chain) < 2:
            d.all_segments_healthy = True
            return d

        sds: list[SegmentDiagnosis] = []
        bf = False
        ah = True

        for i in range(len(expected_chain) - 1):
            src = expected_chain[i]
            tgt = expected_chain[i + 1]
            sid = f"{src}→{tgt}"

            edge = self.dominant_mechanism(src, tgt, context_key)
            if not edge:
                edge = self.get_edge(src, tgt)

            ok = actual_segment_states.get(sid, False)
            edir = edge.direction if edge else "+"
            rel = (edge.reliability_in_context(context_key)
                   if edge and context_key else (edge.reliability_default if edge else 0.50))
            mech = edge.mechanism if edge else ""
            is_bp = False
            sev = None
            mf = None
            rat = ""

            if ok:
                rat = f"{sid}: transmitted correctly ({edir})"
            else:
                ah = False
                if not bf:
                    is_bp = True
                    bf = True
                    if rel > 0.70:
                        sev = BreakpointSeverity.SIGNIFICANT
                        rat = f"{sid}: BROKEN — reliable edge ({rel:.2f}) failed unexpectedly"
                    elif rel > 0.40:
                        sev = BreakpointSeverity.SIGNIFICANT
                        rat = f"{sid}: BROKEN — moderate reliability ({rel:.2f})"
                    else:
                        sev = BreakpointSeverity.MINOR
                        rat = f"{sid}: BROKEN — low reliability ({rel:.2f}), not surprising"
                    if edge and edge.failure_modes:
                        for fm in edge.failure_modes:
                            if fm.condition and all(context_key == k for k in fm.condition.get("context_keys", [])):
                                mf = fm.mode_id
                                break
                else:
                    rat = f"{sid}: NOT transmitted (downstream of {d.breakpoint_segment})"

            sd = SegmentDiagnosis(
                segment_id=sid, source=src, target=tgt, mechanism=mech,
                expected_direction=edir,
                actual_direction="unknown" if not ok else edir,
                transmitted_correctly=ok, is_breakpoint=is_bp,
                breakpoint_severity=sev, matched_failure_mode=mf,
                evidence={"reliability": rel, "context": context_key,
                          "observations": edge.observation_count if edge else 0,
                          "strength": edge.edge_strength if edge else 0.0,
                          "latency_days": edge.latency_days if edge else 0},
                diagnosis_rationale=rat,
            )
            sds.append(sd)

        d.segment_diagnoses = sds
        d.all_segments_healthy = ah

        if bf:
            bp = next((sd for sd in sds if sd.is_breakpoint), None)
            if bp:
                d.breakpoint_found = True
                d.breakpoint_segment = bp.segment_id
                edge = self.get_edge(bp.source, bp.target, bp.mechanism)
                if edge:
                    rel = (edge.reliability_in_context(context_key)
                           if context_key else edge.reliability_default)
                    if rel > 0.65:
                        d.root_cause_category = FailureModeCategory.EVENT_OVERRIDE
                        d.root_cause_description = f"High-reliability edge ({rel:.2f}) broke → external event in '{context_key}'"
                        d.suggested_action = TransmissionAction.REGISTER_FAILURE
                    elif rel > 0.35:
                        d.root_cause_category = FailureModeCategory.REGIME_INCOMPATIBLE
                        d.root_cause_description = f"Moderate-reliability edge ({rel:.2f}) broke → regime incompatibility"
                        d.suggested_action = TransmissionAction.WEAKEN
                    else:
                        d.root_cause_category = FailureModeCategory.THRESHOLD_NONLINEAR
                        d.root_cause_description = f"Low-reliability edge ({rel:.2f}) broke → structurally unreliable"
                        d.suggested_action = TransmissionAction.WEAKEN
                else:
                    d.root_cause_category = FailureModeCategory.STRUCTURAL_BREAK
                    d.suggested_action = TransmissionAction.REGISTER_FAILURE

                if d.suggested_action == TransmissionAction.REGISTER_FAILURE:
                    d.new_failure_mode = FailureMode(
                        category=d.root_cause_category,
                        condition={"context_key": context_key} if context_key else {},
                        description=d.root_cause_description, occurrence_count=1,
                        first_observed=datetime.now(timezone.utc),
                        last_observed=datetime.now(timezone.utc),
                    )

        return d

    # ── Update Operations ─────────────────────────────────────────────────

    def apply_update(self, update: TransmissionUpdateRecord) -> TransmissionEdge:
        sid = update.segment_id
        # Locate edge — try by edge_id first, then segment_id matching
        edge = None
        if hasattr(update, 'edge_id') and update.edge_id:
            edge = self._edges.get(update.edge_id)
        if not edge and sid:
            for e in self._edges.values():
                if e.segment_id == sid:
                    edge = e
                    break

        if not edge and update.source and update.target:
            edge = self.get_edge(update.source, update.target, update.mechanism)
            if not edge:
                edge = self.add_edge(update.source, update.target, mechanism=update.mechanism)

        if not edge:
            raise ValueError(f"Cannot locate edge for update: {update}")

        edge.observation_count += 1
        if update.action == TransmissionAction.REINFORCE:
            edge.success_count += 1
        elif update.action in (TransmissionAction.WEAKEN, TransmissionAction.DEMOTE_MECHANISM):
            edge.break_count += 1

        edge.reliability_default = max(0.05, min(0.95, edge.reliability_default + update.reliability_delta))

        if update.context_key and update.context_reliability_delta != 0:
            cur = edge.reliability_by_context.get(update.context_key, edge.reliability_default)
            edge.reliability_by_context[update.context_key] = max(0.05, min(0.95, cur + update.context_reliability_delta))

        if update.strength_delta != 0:
            edge.edge_strength = max(0.05, min(0.95, edge.edge_strength + update.strength_delta))

        if update.action == TransmissionAction.REGISTER_FAILURE and update.failure_category:
            fm = FailureMode(
                category=update.failure_category,
                condition={"context_key": update.context_key} if update.context_key else {},
                description=update.failure_description, occurrence_count=1,
                first_observed=datetime.now(timezone.utc), last_observed=datetime.now(timezone.utc),
            )
            edge.failure_modes.append(fm)

        if update.action == TransmissionAction.ADD_CONDITION and update.failure_description:
            if update.failure_description not in edge.conditions_for_validity:
                edge.conditions_for_validity.append(update.failure_description)

        edge.last_updated = datetime.now(timezone.utc)
        update.new_reliability = edge.reliability_default
        self._total_updates += 1
        return edge

    def reinforce_edge(self, source: str, target: str, context_key: str = "",
                       amount: float = 0.02, reason: str = "",
                       mechanism: str = "") -> TransmissionUpdateRecord:
        edge = self.get_edge(source, target, mechanism)
        if not edge:
            self.add_edge(source, target, mechanism=mechanism)
        u = TransmissionUpdateRecord(
            segment_id=f"{source}→{target}" + (f"[{mechanism}]" if mechanism else ""),
            source=source, target=target, mechanism=mechanism,
            action=TransmissionAction.REINFORCE, context_key=context_key,
            reliability_delta=amount,
            context_reliability_delta=amount * 0.8 if context_key else 0.0,
            reason=reason or f"Transmission confirmed: {source}→{target}",
        )
        self.apply_update(u)
        return u

    def weaken_edge(self, source: str, target: str, context_key: str = "",
                    amount: float = -0.06, reason: str = "",
                    mechanism: str = "") -> TransmissionUpdateRecord:
        edge = self.get_edge(source, target, mechanism)
        if not edge:
            self.add_edge(source, target, mechanism=mechanism)
        u = TransmissionUpdateRecord(
            segment_id=f"{source}→{target}" + (f"[{mechanism}]" if mechanism else ""),
            source=source, target=target, mechanism=mechanism,
            action=TransmissionAction.WEAKEN, context_key=context_key,
            reliability_delta=amount,
            context_reliability_delta=amount * 1.2 if context_key else 0.0,
            reason=reason or f"Transmission broken: {source}→{target}",
        )
        self.apply_update(u)
        return u

    # ── Statistics ───────────────────────────────────────────────────────

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def node_count(self) -> int:
        ns = set()
        for e in self._edges.values():
            ns.add(e.source); ns.add(e.target)
        return len(ns)

    @property
    def total_observations(self) -> int:
        return sum(e.observation_count for e in self._edges.values())

    @property
    def competition_count(self) -> int:
        return len(self.competing_pairs())

    def reliability_stability(self, window: int = 20) -> float:
        active = [e for e in self._edges.values() if e.observation_count >= window]
        if not active:
            return 0.0
        return sum(1 for e in active if e.is_stable(window)) / len(active)

    def top_edges(self, n: int = 5, context_key: str = "") -> list[TransmissionEdge]:
        """Top N edges by quality score."""
        scored = [(e.quality_score(), e) for e in self._edges.values()
                  if e.observation_count >= 3]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:n]]

    def weakest_edges(self, n: int = 5) -> list[TransmissionEdge]:
        """Weakest N edges by reliability (with enough data)."""
        active = [e for e in self._edges.values() if e.observation_count >= 5]
        active.sort(key=lambda e: e.reliability_default)
        return active[:n]

    def summary(self) -> str:
        active = self.active_edges(min_observation=5)
        lines = [
            f"TransmissionGraph: {self.edge_count} edges, {self.node_count} nodes",
            f"  Competitions: {self.competition_count}",
            f"  Total observations: {self.total_observations}",
            f"  Active edges (>=5 obs): {len(active)}",
            f"  Stability: {self.reliability_stability():.1%}",
        ]
        top = self.top_edges(5)
        if top:
            lines.append("  Top edges:")
            for e in top:
                lines.append(f"    {e.describe()}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"<TransmissionGraph edges={self.edge_count} nodes={self.node_count} comps={self.competition_count}>"
