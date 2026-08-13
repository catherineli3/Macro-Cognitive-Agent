"""FusionEngine — Unify data + news into a single Evidence Graph.

Quality: Professional researchers don't analyze data and news separately.
They ask: "Does today's CPI explain today's market?", not "CPI is 2.8%."

This engine:
    1. Takes ALL evidence sources (macro data, news, capital flow, beliefs,
       historical analog)
    2. Cross-references them — does the news confirm the data?
    3. Evaluates each piece of evidence against each belief
    4. Produces a Unified Evidence Graph with support/contradict/neutral/unknown
       labels for every belief-evidence pair

The Evidence Graph is the single source of truth for the reasoning pipeline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class EvidenceNode:
    """A single evidence node in the graph.

    Each node has:
    - Identity (what is it?)
    - Type (data, news, flow, belief, analog)
    - Impact vector (how does it affect each belief?)
    """

    node_id: str = ""
    title: str = ""
    description: str = ""
    source_type: str = ""  # "macro_data", "news", "capital_flow", "belief", "historical_analog"
    source_id: str = ""  # Reference to original source
    timestamp: str = ""

    # Impact on beliefs
    belief_impacts: dict = field(default_factory=dict)
    # {belief_id: {direction: "supports"|"contradicts"|"neutral"|"unknown", strength: 0-1}}

    # Data values
    quantitative_values: dict = field(default_factory=dict)

    # Quality
    confidence: float = 0.5
    recency: float = 0.5  # 0-1, how fresh?
    relevance: float = 0.5  # 0-1, how relevant to macro?

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "title": self.title,
            "source_type": self.source_type,
            "belief_impacts": self.belief_impacts,
            "confidence": self.confidence,
            "relevance": self.relevance,
        }


@dataclass
class EvidenceEdge:
    """Connection between two evidence nodes.

    Edges represent relationships:
    - confirms: Node A supports the same conclusion as Node B
    - contradicts: Node A contradicts Node B's implication
    - explains: Node A explains why Node B happened
    - relates_to: General relationship
    """

    edge_id: str = ""
    from_node: str = ""
    to_node: str = ""
    relationship: str = ""  # "confirms", "contradicts", "explains", "relates_to"
    strength: float = 0.5  # 0-1
    description: str = ""


@dataclass
class UnifiedEvidenceGraph:
    """The complete evidence graph — all evidence, all relationships.

    This is the master document for the reasoning pipeline.
    MemoWriter reads from here. HypothesisBuilder reads from here.
    """

    graph_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Nodes
    nodes: list[EvidenceNode] = field(default_factory=list)
    edges: list[EvidenceEdge] = field(default_factory=list)

    # Summary
    total_nodes: int = 0
    total_edges: int = 0
    data_node_count: int = 0
    news_node_count: int = 0
    flow_node_count: int = 0
    belief_node_count: int = 0
    analog_node_count: int = 0

    # Net assessment per belief
    belief_net_assessment: dict = field(default_factory=dict)
    # {belief_id: {support_count, contradict_count, net_direction, confidence}}

    def get_evidence_for_belief(self, belief_id: str) -> dict:
        """Get all evidence supporting/contradicting a specific belief."""
        result = {"supports": [], "contradicts": [], "neutral": [], "unknown": []}
        for node in self.nodes:
            bi = node.belief_impacts.get(belief_id, {})
            if bi:
                direction = bi.get("direction", "unknown")
                result.setdefault(direction, []).append(node.to_dict())
        return result

    def summary(self) -> str:
        """Text summary of the evidence graph."""
        parts = [f"Unified Evidence Graph: {self.total_nodes} nodes, {self.total_edges} edges"]
        parts.append(
            f"  Data: {self.data_node_count}, News: {self.news_node_count}, "
            f"Flows: {self.flow_node_count}, Beliefs: {self.belief_node_count}, "
            f"Analogs: {self.analog_node_count}"
        )
        for bid, assessment in self.belief_net_assessment.items():
            parts.append(
                f"  Belief {bid}: {assessment.get('net_direction', 'unknown')} "
                f"(supports: {assessment.get('support_count', 0)}, "
                f"contradicts: {assessment.get('contradict_count', 0)})"
            )
        return "\n".join(parts)


class FusionEngine:
    """Fuse all evidence sources into a Unified Evidence Graph.

    This is the bridge between raw inputs (data, news, etc.) and the
    reasoning pipeline (hypothesis builder, memo writer).

    Quality: Every conclusion in the final research memo traces back
    to a node in this graph. No floating claims.
    """

    def __init__(self):
        pass

    def fuse(
        self,
        market_data: dict,
        news_events: list[dict] = None,
        capital_flow_result: dict | None = None,
        beliefs: list = None,
        regime_result: dict | None = None,
    ) -> UnifiedEvidenceGraph:
        """Fuse all evidence sources into a unified graph.

        This is the primary API. Everything flows through here.

        Returns:
            Fully connected UnifiedEvidenceGraph
        """
        news_events = news_events or []
        beliefs = beliefs or []

        graph = UnifiedEvidenceGraph(
            graph_id=f"GRAP_{str(uuid.uuid4())[:8]}",
        )

        # 1. Create nodes from each source
        data_nodes = self._create_data_nodes(market_data)
        news_nodes = self._create_news_nodes(news_events)
        flow_nodes = self._create_flow_nodes(capital_flow_result)
        belief_nodes = self._create_belief_nodes(beliefs)
        analog_nodes = self._create_analog_nodes(regime_result)

        all_nodes = data_nodes + news_nodes + flow_nodes + belief_nodes + analog_nodes
        graph.nodes = all_nodes

        # 2. Evaluate each node against each belief
        for node in all_nodes:
            node.belief_impacts = self._evaluate_against_beliefs(node, beliefs)

        # 3. Create edges — cross-reference nodes
        graph.edges = self._create_edges(all_nodes)

        # 4. Compute summary statistics
        graph.total_nodes = len(all_nodes)
        graph.total_edges = len(graph.edges)
        graph.data_node_count = len(data_nodes)
        graph.news_node_count = len(news_nodes)
        graph.flow_node_count = len(flow_nodes)
        graph.belief_node_count = len(belief_nodes)
        graph.analog_node_count = len(analog_nodes)

        # 5. Net assessment per belief
        graph.belief_net_assessment = self._net_assessment(graph, beliefs)

        return graph

    # ── Node Creation ──

    def _create_data_nodes(self, market_data: dict) -> list[EvidenceNode]:
        """Create nodes from macro market data."""
        nodes = []
        signals = market_data.get("signals", {})
        for name, sig in signals.items():
            desc = sig.get("description", name) if isinstance(sig, dict) else str(sig)
            direction = sig.get("direction", "neutral") if isinstance(sig, dict) else "neutral"
            strength = sig.get("strength", 0.5) if isinstance(sig, dict) else 0.5

            nodes.append(
                EvidenceNode(
                    node_id=f"DATA_{str(uuid.uuid4())[:8]}",
                    title=f"Macro Signal: {name}",
                    description=desc,
                    source_type="macro_data",
                    source_id=name,
                    quantitative_values={"direction": direction, "strength": strength},
                    confidence=0.7,
                    recency=0.8,
                    relevance=0.7,
                )
            )

        # Price data
        prices = market_data.get("prices", {})
        for asset, changes in prices.items():
            if isinstance(changes, dict):
                for period, val in changes.items():
                    try:
                        v = float(val)
                    except (ValueError, TypeError):
                        continue
                    if abs(v) > 0.001:
                        nodes.append(
                            EvidenceNode(
                                node_id=f"PRICE_{str(uuid.uuid4())[:8]}",
                                title=f"Price: {asset} ({period})",
                                description=(
                                    f"{asset} price change {period}: {v:+.2%}"
                                    if abs(v) < 1
                                    else f"{asset} {period}: {v}"
                                ),
                                source_type="macro_data",
                                source_id=f"{asset}_{period}",
                                quantitative_values={"asset": asset, "period": period, "change": v},
                                confidence=0.9,
                                recency=0.9,
                                relevance=0.6,
                            )
                        )

        return nodes

    def _create_news_nodes(self, news_events: list[dict]) -> list[EvidenceNode]:
        """Create nodes from news events."""
        nodes = []
        for event in news_events:
            if isinstance(event, dict):
                title = event.get("title", event.get("event", ""))
                desc = event.get("description", event.get("event", ""))
            else:
                title = getattr(event, "title", str(event))
                desc = getattr(event, "description", str(event))

            nodes.append(
                EvidenceNode(
                    node_id=f"NEWS_{str(uuid.uuid4())[:8]}",
                    title=title[:100],
                    description=desc[:200],
                    source_type="news",
                    source_id=(
                        event.get("event_id", "")
                        if isinstance(event, dict)
                        else getattr(event, "event_id", "")
                    ),
                    confidence=(
                        event.get("impact_confidence", 0.6) if isinstance(event, dict) else 0.6
                    ),
                    recency=0.9,
                    relevance=0.6,
                )
            )

        return nodes

    def _create_flow_nodes(self, cf_result: dict | None) -> list[EvidenceNode]:
        """Create nodes from capital flow analysis."""
        if not cf_result:
            return []

        direction = cf_result.get("direction", cf_result.get("flow_direction", "neutral"))
        strength = cf_result.get("strength", cf_result.get("confidence", 0.5))

        return [
            EvidenceNode(
                node_id=f"FLOW_{str(uuid.uuid4())[:8]}",
                title=f"Capital Flow Signal: {direction}",
                description=str(
                    cf_result.get("summary", cf_result.get("description", "Capital flow analysis"))
                ),
                source_type="capital_flow",
                source_id="capital_flow_engine",
                quantitative_values={"direction": direction, "strength": strength},
                confidence=0.6,
                recency=0.7,
                relevance=0.7,
            )
        ]

    def _create_belief_nodes(self, beliefs: list) -> list[EvidenceNode]:
        """Create nodes from active beliefs (beliefs themselves are evidence about priors)."""
        nodes = []
        for b in beliefs:
            bd = b if isinstance(b, dict) else b.to_dict() if hasattr(b, "to_dict") else {}
            name = bd.get("name", bd.get("label", ""))
            stage = bd.get("stage", "")
            confidence = bd.get("confidence", bd.get("prior_mean", 0.5))

            nodes.append(
                EvidenceNode(
                    node_id=f"BEL_{str(uuid.uuid4())[:8]}",
                    title=f"Active Belief: {name}",
                    description=f"Belief in stage: {stage}, confidence: {confidence}",
                    source_type="belief",
                    source_id=bd.get("id", bd.get("belief_id", "")),
                    quantitative_values={"confidence": confidence},
                    confidence=confidence,
                    recency=0.5,
                    relevance=0.9,
                )
            )

        return nodes

    def _create_analog_nodes(self, regime_result: dict | None) -> list[EvidenceNode]:
        """Create nodes from historical analogs."""
        if not regime_result:
            return []

        nodes = []
        analog = regime_result.get("historical_analog", regime_result.get("analog", {}))
        if analog and isinstance(analog, dict) and analog.get("period"):
            nodes.append(
                EvidenceNode(
                    node_id=f"HIST_{str(uuid.uuid4())[:8]}",
                    title=f"Historical Analog: {analog.get('period')}",
                    description=f"Analog period: {analog.get('period')} — {analog.get('label', '')} "
                    f"(similarity: {analog.get('similarity_score', 'N/A')})",
                    source_type="historical_analog",
                    source_id=analog.get("period", ""),
                    quantitative_values={"similarity": analog.get("similarity_score", 0.5)},
                    confidence=analog.get("similarity_score", 0.5),
                    recency=0.3,
                    relevance=0.5,
                )
            )

        return nodes

    # ── Cross-Referencing ──

    def _evaluate_against_beliefs(self, node: EvidenceNode, beliefs: list) -> dict:
        """Evaluate how this evidence node affects each belief.

        Returns: {belief_id: {direction, strength}}

        This is the key quality function — it answers:
        "Does this piece of evidence support, contradict, or remain neutral
        to each of my active beliefs?"
        """
        impacts = {}

        for b in beliefs:
            bd = b if isinstance(b, dict) else b.to_dict() if hasattr(b, "to_dict") else {}
            bid = bd.get("id", bd.get("belief_id", ""))
            if not bid:
                continue

            belief_direction = bd.get("direction", "")
            belief_name = str(bd.get("name", bd.get("label", ""))).lower()

            # Evaluate compatibility
            node_text = (node.title + " " + node.description).lower()

            # Data nodes: check if the data direction aligns with belief
            if node.source_type == "macro_data":
                qv = node.quantitative_values
                data_dir = qv.get("direction", "")

                if data_dir == belief_direction:
                    impacts[bid] = {"direction": "supports", "strength": qv.get("strength", 0.5)}
                elif data_dir and belief_direction and data_dir != belief_direction:
                    impacts[bid] = {"direction": "contradicts", "strength": qv.get("strength", 0.5)}
                else:
                    impacts[bid] = {"direction": "neutral", "strength": 0.3}
            else:
                # Text-based matching for other node types
                if belief_name and belief_name in node_text:
                    impacts[bid] = {"direction": "supports", "strength": 0.6}
                else:
                    impacts[bid] = {"direction": "neutral", "strength": 0.3}

        return impacts

    def _create_edges(self, nodes: list[EvidenceNode]) -> list[EvidenceEdge]:
        """Create edges between related evidence nodes.

        Cross-references news ↔ data, flow ↔ data, belief ↔ everything.
        """
        edges = []
        data_nodes = [n for n in nodes if n.source_type == "macro_data"]
        news_nodes = [n for n in nodes if n.source_type == "news"]
        flow_nodes = [n for n in nodes if n.source_type == "capital_flow"]
        belief_nodes = [n for n in nodes if n.source_type == "belief"]

        # Data ↔ News: Does the news confirm or contradict the data signal?
        for dn in data_nodes:
            for nn in news_nodes:
                rel, strength = self._data_news_relationship(dn, nn)
                if rel != "unrelated":
                    edges.append(
                        EvidenceEdge(
                            edge_id=f"EDGE_{str(uuid.uuid4())[:8]}",
                            from_node=dn.node_id,
                            to_node=nn.node_id,
                            relationship=rel,
                            strength=strength,
                            description=f"Data '{dn.title}' {rel} news '{nn.title}'",
                        )
                    )

        # Flow ↔ Data
        for fn in flow_nodes:
            for dn in data_nodes[:5]:  # Limit connections
                edges.append(
                    EvidenceEdge(
                        edge_id=f"EDGE_{str(uuid.uuid4())[:8]}",
                        from_node=fn.node_id,
                        to_node=dn.node_id,
                        relationship="relates_to",
                        strength=0.5,
                        description="Flow signal relates to data signal",
                    )
                )

        # Belief ↔ Everything (beliefs are central nodes)
        for bn in belief_nodes:
            for node in data_nodes[:3] + news_nodes[:3] + flow_nodes:
                bi = node.belief_impacts.get(bn.source_id, {})
                if bi and bi.get("direction") in ("supports", "contradicts"):
                    edges.append(
                        EvidenceEdge(
                            edge_id=f"EDGE_{str(uuid.uuid4())[:8]}",
                            from_node=bn.node_id,
                            to_node=node.node_id,
                            relationship=bi["direction"] + "s",
                            strength=bi.get("strength", 0.5),
                            description=f"Belief {bi['direction']}ed by {node.title[:60]}",
                        )
                    )

        return edges

    def _data_news_relationship(
        self, data_node: EvidenceNode, news_node: EvidenceNode
    ) -> tuple[str, float]:
        """Determine if news confirms or contradicts data."""
        data_desc = data_node.description.lower()
        news_text = (news_node.title + " " + news_node.description).lower()

        # Keyword overlap = likely related
        data_words = set(data_desc.split())
        news_words = set(news_text.split())
        overlap = data_words & news_words

        if not overlap or len(overlap) < 2:
            return "unrelated", 0.0

        overlap_ratio = len(overlap) / min(len(data_words), 50)
        if overlap_ratio > 0.1:
            return "relates_to", 0.5

        return "unrelated", 0.0

    def _net_assessment(self, graph: UnifiedEvidenceGraph, beliefs: list) -> dict:
        """Compute net evidence assessment per belief."""
        assessment = {}

        for b in beliefs:
            bd = b if isinstance(b, dict) else b.to_dict() if hasattr(b, "to_dict") else {}
            bid = bd.get("id", bd.get("belief_id", ""))
            if not bid:
                continue

            support_count = 0
            contradict_count = 0
            total_confidence = 0.0

            for node in graph.nodes:
                bi = node.belief_impacts.get(bid, {})
                direction = bi.get("direction", "")
                if direction == "supports":
                    support_count += 1
                    total_confidence += bi.get("strength", 0.5)
                elif direction == "contradicts":
                    contradict_count += 1
                    total_confidence += bi.get("strength", 0.5)

            # Net direction
            if support_count > contradict_count * 1.5:
                net = "supported"
            elif contradict_count > support_count * 1.5:
                net = "contradicted"
            elif support_count == 0 and contradict_count == 0:
                net = "unknown"
            else:
                net = "mixed"

            total = support_count + contradict_count
            avg_confidence = total_confidence / total if total > 0 else 0.0

            assessment[bid] = {
                "support_count": support_count,
                "contradict_count": contradict_count,
                "net_direction": net,
                "confidence": round(avg_confidence, 2),
            }

        return assessment
