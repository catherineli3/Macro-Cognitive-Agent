"""Principle Extractor — Pattern extraction from finding clusters (Milestone C).

Discovers recurring patterns in accumulated research findings and proposes
candidate principles. Implements GR-1~5 granularity rules to ensure each
extracted principle is a single causal edge.

F1.6 (G1): Adds semantic deduplication — new findings that match existing
principles update the existing record rather than creating a duplicate.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from difflib import SequenceMatcher

from src.schemas.transmission_v3_1 import ResearchFinding
from src.schemas.research import ResearchPrinciple, PrincipleStrength
from src.research.principles.admission_gate import PrincipleAdmissionGate
from src.shared.logging import get_logger

logger = get_logger(__name__)

# G1: Similarity threshold for considering two principles as identical
SIMILARITY_THRESHOLD = 0.65


class PrincipleExtractor:
    """Extracts candidate principles from accumulated finding clusters.

    Implements the Granularity Rules (GR-1~5):
        GR-1: Single causal edge — one directed relationship
        GR-2: Independently falsifiable
        GR-3: Single condition domain
        GR-4: Atomic domain — one transmission dimension
        GR-5: Must be split if splittable

    F1.6 (G1): Deduplication — before creating a new principle, checks
    existing principles for semantic similarity. If a match is found,
    updates the existing principle instead of creating a duplicate.
    """

    def __init__(self, admission_gate: PrincipleAdmissionGate | None = None) -> None:
        self._gate = admission_gate or PrincipleAdmissionGate()
        self._extracted_principles: list[ResearchPrinciple] = []
        self._domain_findings: dict[str, list[ResearchFinding]] = defaultdict(list)
        self._principle_store = None  # G1: set via set_store()

    def add_findings(self, findings: list[ResearchFinding]) -> None:
        """Feed new findings into the extractor."""
        for f in findings:
            domain = self._infer_domain(f)
            self._domain_findings[domain].append(f)

    # ── G1: Deduplication ──────────────────────────────────────────────

    def set_store(self, store) -> None:
        """G1: Bind PrincipleStore for deduplication lookups."""
        self._principle_store = store

    def _find_matching_principle(
        self, name: str, statement: str, domain: str,
        findings: list[ResearchFinding],
    ) -> ResearchPrinciple | None:
        """G1: Check if a proposed principle already exists in store.

        Uses multi-dimension semantic matching:
          1. Statement similarity (SequenceMatcher)
          2. Domain match
          3. Causal edge overlap
          4. Transmission path similarity

        Returns existing principle if similarity > threshold, else None.
        """
        if self._principle_store is None:
            return None

        existing = self._principle_store.get_all()
        if not existing:
            return None

        # Gather source edges from new findings for comparison
        new_edges: set[str] = set()
        for f in findings:
            new_edges.update(f.source_edges or [])

        best_score = 0.0
        best_match: ResearchPrinciple | None = None

        for p in existing:
            score = self._compute_similarity(
                name, statement, domain, new_edges,
                p.name, p.statement, p.domain,
                set(p.evidence.channels_validated or []),
            )
            if score > best_score:
                best_score = score
                best_match = p

        if best_score >= SIMILARITY_THRESHOLD and best_match is not None:
            logger.info(
                "G1 Dedup: matched new '%s' → existing '%s' (score=%.2f)",
                name[:40], best_match.name[:40], best_score,
            )
            return best_match

        return None

    @staticmethod
    def _compute_similarity(
        new_name: str, new_stmt: str, new_domain: str, new_edges: set[str],
        exist_name: str, exist_stmt: str, exist_domain: str, exist_edges: set[str],
    ) -> float:
        """G1: Compute multi-dimension similarity score (0.0-1.0).

        Weights:
            - Statement similarity: 0.45  (primary signal)
            - Domain match:         0.25  (same transmission domain)
            - Edge overlap:         0.20  (causal edges)
            - Name similarity:      0.10  (weakest signal)
        """
        # Statement similarity
        stmt_sim = SequenceMatcher(None, new_stmt.lower(), exist_stmt.lower()).ratio()

        # Domain match
        domain_sim = 1.0 if new_domain == exist_domain else (
            0.5 if new_domain.split("_")[0] == exist_domain.split("_")[0] else 0.0
        )

        # Edge overlap (Jaccard)
        if new_edges or exist_edges:
            intersection = len(new_edges & exist_edges)
            union = len(new_edges | exist_edges)
            edge_sim = intersection / max(union, 1)
        else:
            edge_sim = 0.0

        # Name similarity
        name_sim = SequenceMatcher(None, new_name.lower(), exist_name.lower()).ratio()

        score = 0.45 * stmt_sim + 0.25 * domain_sim + 0.20 * edge_sim + 0.10 * name_sim
        return round(score, 4)

    def _update_existing_principle(
        self, existing: ResearchPrinciple, findings: list[ResearchFinding],
        domain: str, cycle: int,
    ) -> ResearchPrinciple:
        """G1: Update an existing principle with new evidence.

        Increments observation count, adds new finding IDs, updates
        regimes/channels, and bumps sustained_cycles.
        Returns the existing principle (mutated in-place).
        """
        total_obs = sum(f.evidence.get("observations", 0) for f in findings)
        channels = set(existing.evidence.channels_validated or [])
        for f in findings:
            channels.update(f.source_edges or [])

        # Merge new findings
        new_finding_ids = [f.finding_id for f in findings]
        for fid in new_finding_ids:
            if fid not in existing.source_findings:
                existing.source_findings.append(fid)

        # Update evidence
        existing.evidence.total_observations += total_obs
        existing.evidence.channels_validated = list(channels)
        existing.evidence.sustained_cycles += 1
        existing.evidence.last_validated_cycle = cycle

        # Merge promoted_from_findings
        for fid in new_finding_ids:
            if fid not in existing.promoted_from_findings:
                existing.promoted_from_findings.append(fid)

        # Merge preconditions
        for f in findings:
            evidence = f.evidence or {}
            for key in ["regime", "vix_level", "context"]:
                if key in evidence and key not in existing.preconditions:
                    existing.preconditions[key] = evidence[key]
            if f.context_key and "context_key" not in existing.preconditions:
                existing.preconditions["context_key"] = f.context_key

        logger.info(
            "G1: Updated existing principle '%s': +%d obs, total=%d, sustained=%d",
            existing.name[:40], total_obs,
            existing.evidence.total_observations,
            existing.evidence.sustained_cycles,
        )
        return existing

    def extract_candidates(self,
                           min_cluster_size: int = 5,
                           cycle: int = 0) -> list[ResearchPrinciple]:
        """Extract candidate principles from accumulated findings.

        F1.6 (G1): Before creating a new principle, checks existing store
        for semantic matches. If match found, updates existing principle.
        F1.6 (G2): All new principles start as CANDIDATE (never VALIDATED directly).

        Returns a list of principles (new candidates + updated existing).
        """
        candidates: list[ResearchPrinciple] = []

        for domain, findings in self._domain_findings.items():
            if len(findings) < min_cluster_size:
                continue

            # Cluster findings by patterns within domain
            clusters = self._cluster_by_pattern(findings, domain)
            for cluster_name, cluster_findings in clusters.items():
                if len(cluster_findings) < min_cluster_size:
                    continue

                # Check GR-5: Can this be split?
                sub_clusters = self._try_split(cluster_findings)
                target_clusters = sub_clusters if len(sub_clusters) > 1 else {cluster_name: cluster_findings}

                for sub_name, sub_findings in target_clusters.items():
                    result = self._extract_or_update(sub_name, sub_findings, domain, cycle)
                    if result is not None:
                        if result not in candidates:
                            candidates.append(result)

        self._extracted_principles.extend(candidates)
        logger.info("Extracted %d candidate principles from %d domains (cycle %d)",
                     len(candidates), len(self._domain_findings), cycle)
        return candidates

    def _extract_or_update(self, name: str, findings: list[ResearchFinding],
                           domain: str, cycle: int) -> ResearchPrinciple | None:
        """G1+G2: Either update existing matching principle, or create new CANDIDATE.

        Flow:
            1. Check semantic match against existing principles (G1)
            2. If match found → update existing (return it)
            3. If no match → create new CANDIDATE (G2: never VALIDATED directly)
            4. If below minimum threshold → return None
        """
        if len(findings) < self._gate.P2_MIN_REPETITION:
            return None

        # Build statement
        statement = self._build_statement(findings, domain)

        # G1: Check for existing match first
        existing = self._find_matching_principle(name, statement, domain, findings)
        if existing is not None:
            return self._update_existing_principle(existing, findings, domain, cycle)

        # G2: Create new principle — ALWAYS as CANDIDATE
        return self._extract_single(name, findings, domain, cycle)

    # ── Internal ─────────────────────────────────────────────────────────

    def _infer_domain(self, finding: ResearchFinding) -> str:
        """Infer the transmission domain from a finding."""
        if finding.source_edges:
            edge = finding.source_edges[0]
            if "→" in edge:
                return edge.split("→")[0].strip()
        return finding.category or "unknown"

    def _cluster_by_pattern(self, findings: list[ResearchFinding],
                            domain: str) -> dict[str, list[ResearchFinding]]:
        """Group findings by recurring patterns extracted from titles."""
        clusters: dict[str, list[ResearchFinding]] = defaultdict(list)

        for f in findings:
            # Use title pattern as cluster key (simplified name extraction)
            title = f.title or ""
            # Extract key phrases
            if "Most Reliable" in title and ":" in title:
                key = title.split(":", 1)[1].split("(")[0].strip()
            elif "Failing" in title and ":" in title:
                key = title.split(":", 1)[1].split("(")[0].strip()
            elif "Failure pattern" in title:
                key = title.split("→")[1].strip() if "→" in title else title
            elif "Similar to" in title:
                key = "regime_similarity"
            else:
                key = title[:50]

            if key:
                clusters[key].append(f)

        return dict(clusters)

    def _try_split(self, findings: list[ResearchFinding]) -> dict[str, list[ResearchFinding]]:
        """GR-5: Check if a cluster can be split into simpler principles.

        If the cluster covers multiple distinct edges or conditions,
        try to split into sub-clusters by edge segment.
        """
        if len(findings) < 10:
            return {}  # Not enough data to warrant splitting

        # Group by source edge
        by_edge: dict[str, list[ResearchFinding]] = defaultdict(list)
        for f in findings:
            for edge in (f.source_edges or [""]):
                by_edge[edge].append(f)

        # Only split if we get meaningful sub-groups
        meaningful = {
            k: v for k, v in by_edge.items()
            if len(v) >= 5 and k
        }

        if len(meaningful) > 1:
            return meaningful
        return {}

    def _extract_single(self, name: str, findings: list[ResearchFinding],
                        domain: str, cycle: int) -> ResearchPrinciple | None:
        """G2: Create a NEW principle — ALWAYS as CANDIDATE.

        Admission to VALIDATED requires separate multi-cycle confirmation
        (handled by CandidateManager). No direct VALIDATED creation.
        """
        if len(findings) < self._gate.P2_MIN_REPETITION:
            return None

        # Build statement from finding evidence
        statement = self._build_statement(findings, domain)

        # Extract preconditions (GR-3: single condition domain)
        preconditions = self._extract_preconditions(findings)

        # Build evidence
        total_obs = sum(f.evidence.get("observations", 0) for f in findings)
        channels = set()
        for f in findings:
            channels.update(f.source_edges or [])

        # G2: Always start as CANDIDATE — no direct VALIDATED
        strength = PrincipleStrength.CANDIDATE

        principle = ResearchPrinciple(
            name=name,
            statement=statement,
            domain=domain,
            preconditions=preconditions,
            strength=strength,
            source_findings=[f.finding_id for f in findings],
            created_at_cycle=cycle,
            promoted_from_findings=[f.finding_id for f in findings],
        )
        principle.evidence.total_observations = total_obs
        principle.evidence.channels_validated = list(channels)
        principle.evidence.sustained_cycles = 1
        principle.evidence.last_validated_cycle = cycle

        return principle

    def _build_statement(self, findings: list[ResearchFinding], domain: str) -> str:
        """Build a declarative causal statement from findings."""
        # Extract common themes from finding titles and descriptions
        titles = [f.title for f in findings if f.title]
        descriptions = [f.description for f in findings if f.description]

        # Detect direction patterns
        direction_words = {"increases": 0, "decreases": 0, "breaks": 0,
                           "transmits": 0, "reinforces": 0, "weakens": 0}
        for desc in descriptions:
            desc_lower = desc.lower()
            for word in direction_words:
                if word in desc_lower:
                    direction_words[word] += 1

        dominant = max(direction_words, key=direction_words.get)

        if dominant == "breaks":
            avg_rel = sum(
                f.evidence.get("reliability", 0.5) for f in findings
            ) / max(len(findings), 1)
            condition = list(self._extract_preconditions(findings).keys())[:1]
            cond_str = f" when {condition[0]}" if condition else ""
            return f"Transmission in {domain}{cond_str} is unreliable (avg {avg_rel:.0%})"
        else:
            return f"{domain.replace('_', ' ').title()} signal consistently transmits to markets"

    @staticmethod
    def _extract_preconditions(findings: list[ResearchFinding]) -> dict:
        """Extract common preconditions from findings (GR-3: single domain)."""
        preconditions: dict = {}
        for f in findings:
            evidence = f.evidence or {}
            for key in ["regime", "vix_level", "context"]:
                if key in evidence and key not in preconditions:
                    preconditions[key] = evidence[key]
            # Extract from context
            if f.context_key and "context_key" not in preconditions:
                preconditions["context_key"] = f.context_key
        return preconditions

    @property
    def total_extracted(self) -> int:
        return len(self._extracted_principles)

    @property
    def total_domains(self) -> int:
        return len(self._domain_findings)
