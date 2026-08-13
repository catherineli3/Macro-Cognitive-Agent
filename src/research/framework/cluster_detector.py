"""Principle Cluster Detector — detects co-activation patterns among principles (Milestone C).

Identifies groups of principles that consistently co-activate under similar
macro conditions, signaling potential framework formation opportunities.
"""

from __future__ import annotations

from collections import defaultdict

from src.schemas.research import PrincipleStrength, ResearchPrinciple
from src.shared.logging import get_logger

logger = get_logger(__name__)


class PrincipleClusterDetector:
    """Detects principle co-activation clusters that may form frameworks.

    A Framework emerges when a group of principles consistently co-activate
    under similar conditions. This detector identifies these clusters.
    """

    MIN_CLUSTER_SIZE = 3  # Architecture-defined: >=3 principles (V3 lowered from 5)
    MIN_COACTIVATION_RATE = 0.6  # >=60% co-activation rate

    def __init__(self) -> None:
        self._coactivation_matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._activation_history: list[set[str]] = []  # List of activated principle sets per cycle
        self._total_cycles: int = 0

    def record_activation(self, active_principles: list[str], cycle: int = 0) -> None:
        """Record which principles were active this cycle."""
        active_set = set(active_principles)
        self._activation_history.append(active_set)
        self._total_cycles += 1

        # Update co-activation counts
        for pid_a in active_set:
            for pid_b in active_set:
                if pid_a < pid_b:  # Avoid double counting
                    self._coactivation_matrix[pid_a][pid_b] += 1
                    self._coactivation_matrix[pid_b][pid_a] += 1

    def detect_clusters(
        self,
        principles: dict[str, ResearchPrinciple],
        min_cluster_size: int | None = None,
        min_rate: float | None = None,
    ) -> list[list[str]]:
        """Detect principle clusters that may form candidate frameworks.

        Returns list of principle ID clusters.
        """
        min_size = min_cluster_size or self.MIN_CLUSTER_SIZE
        min_rate = min_rate or self.MIN_COACTIVATION_RATE

        if self._total_cycles < 5:
            logger.debug(
                "Insufficient history for cluster detection (%d cycles)", self._total_cycles
            )
            return []

        # Only consider validated+ principles
        eligible = {
            pid
            for pid, p in principles.items()
            if p.strength
            in (
                PrincipleStrength.VALIDATED,
                PrincipleStrength.MATURE,
                PrincipleStrength.FOUNDATIONAL,
            )
        }

        if len(eligible) < min_size:
            return []

        # Build adjacency graph based on co-activation rate
        adjacency: dict[str, set[str]] = defaultdict(set)
        for pid_a in eligible:
            for pid_b in eligible:
                if pid_a >= pid_b:
                    continue
                co_count = self._coactivation_matrix[pid_a].get(pid_b, 0)
                if self._total_cycles > 0:
                    rate = co_count / self._total_cycles
                    if rate >= min_rate:
                        adjacency[pid_a].add(pid_b)
                        adjacency[pid_b].add(pid_a)

        # Find connected components
        visited: set[str] = set()
        clusters: list[list[str]] = []

        for pid in eligible:
            if pid in visited:
                continue
            component = self._dfs(pid, adjacency, visited)
            if len(component) >= min_size:
                clusters.append(sorted(component))

        if clusters:
            logger.info(
                "Detected %d principle clusters (min_size=%d, min_rate=%.0f%%)",
                len(clusters),
                min_size,
                min_rate * 100,
            )

        return clusters

    def cluster_strength(
        self, cluster: list[str], principles: dict[str, ResearchPrinciple]
    ) -> float:
        """Calculate the overall strength of a principle cluster.

        Higher strength = more likely to form a valid framework.
        """
        if not cluster:
            return 0.0
        strengths = [
            principles[pid].evidence.strength_score for pid in cluster if pid in principles
        ]
        if not strengths:
            return 0.0
        # Mean strength * internal cohesion
        mean_strength = sum(strengths) / len(strengths)
        cohesion = self._cluster_cohesion(cluster)
        return round(0.6 * mean_strength + 0.4 * cohesion, 4)

    def _cluster_cohesion(self, cluster: list[str]) -> float:
        """Internal cohesion of a cluster (avg pairwise co-activation rate)."""
        if len(cluster) < 2 or self._total_cycles == 0:
            return 0.0
        total_rate = 0.0
        pairs = 0
        for i, pid_a in enumerate(cluster):
            for pid_b in cluster[i + 1 :]:
                co_count = self._coactivation_matrix[pid_a].get(pid_b, 0)
                total_rate += co_count / self._total_cycles
                pairs += 1
        return total_rate / max(pairs, 1)

    @staticmethod
    def _dfs(node: str, adjacency: dict[str, set[str]], visited: set[str]) -> list[str]:
        visited.add(node)
        component = [node]
        for neighbor in adjacency.get(node, set()):
            if neighbor not in visited:
                component.extend(PrincipleClusterDetector._dfs(neighbor, adjacency, visited))
        return component

    def get_most_coactivated(self, principle_id: str, top_n: int = 5) -> list[tuple[str, float]]:
        """Get the top N principles most co-activated with a given principle."""
        if principle_id not in self._coactivation_matrix:
            return []
        co_counts = self._coactivation_matrix[principle_id]
        if self._total_cycles == 0:
            return []
        scored = [(pid, count / self._total_cycles) for pid, count in co_counts.items()]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_n]

    @property
    def total_cycles_tracked(self) -> int:
        return self._total_cycles

    @property
    def total_coactivation_pairs(self) -> int:
        return sum(len(v) for v in self._coactivation_matrix.values()) // 2
