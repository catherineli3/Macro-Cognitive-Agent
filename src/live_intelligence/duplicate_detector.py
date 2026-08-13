"""V6.1 Duplicate Detector — Advanced event deduplication.

Builds on V4 NewsDeduplicator with additional capabilities:
- Cross-source dedup (Reuters + Bloomberg reporting same event)
- Temporal clustering (events at different times, same topic)
- Semantic similarity beyond exact matching
- Merge multiple raw events into one NormalizedEvent
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher

from src.live_intelligence.schemas import NormalizedEvent


@dataclass
class DuplicateReport:
    """Result of duplicate detection pass."""

    total_input: int = 0
    unique_count: int = 0
    duplicate_count: int = 0
    merged_count: int = 0

    duplicates: list[tuple[str, str, float]] = field(default_factory=list)
    # (event_id_kept, event_id_discarded, similarity)

    clusters: list[list[str]] = field(default_factory=list)
    # Groups of event_ids that were clustered together

    def summary(self) -> str:
        return (
            f"Dedup: {self.total_input} → {self.unique_count} unique "
            f"({self.duplicate_count} dupes, {self.merged_count} merged)"
        )


class DuplicateDetector:
    """Detect and merge duplicate events across sources.

    Strategy:
    1. Exact title match → duplicate
    2. High keyword overlap + same entities → duplicate
    3. Temporal proximity + semantic similarity → likely duplicate
    4. Same source reporting same story → merge
    """

    def __init__(
        self,
        title_similarity_threshold: float = 0.75,
        keyword_overlap_threshold: float = 0.6,
        temporal_window_minutes: int = 30,
        max_events_buffer: int = 5000,
    ):

        self.title_threshold = title_similarity_threshold
        self.keyword_threshold = keyword_overlap_threshold
        self.temporal_window = temporal_window_minutes
        self.max_buffer = max_events_buffer

        # Rolling buffer of recent events for dedup
        self._recent_events: dict[str, NormalizedEvent] = {}
        self._seen_hashes: set[str] = set()

        # Stats
        self.total_processed = 0
        self.total_duplicates_found = 0

    def deduplicate(
        self, events: list[NormalizedEvent]
    ) -> tuple[list[NormalizedEvent], DuplicateReport]:
        """Process a batch of events, removing duplicates."""
        report = DuplicateReport(total_input=len(events))
        unique = []

        for event in events:
            # Check against recent buffer first
            duplicate_of = self._find_duplicate(event)

            if duplicate_of:
                report.duplicate_count += 1
                report.duplicates.append(
                    (duplicate_of.event_id, event.event_id, self._similarity(duplicate_of, event))
                )
                # Merge raw_ids into the kept event
                duplicate_of.raw_ids.extend(event.raw_ids)
                duplicate_of.raw_ids = list(set(duplicate_of.raw_ids))
                duplicate_of.sources = list(set(duplicate_of.sources + event.sources))
                report.merged_count += 1
                event.is_duplicate = True
            else:
                report.unique_count += 1
                unique.append(event)
                self._add_to_buffer(event)

        # Cluster similar events
        report.clusters = self._cluster_events(unique)

        # Prune old events from buffer
        self._prune_buffer()

        self.total_processed += len(events)
        self.total_duplicates_found += report.duplicate_count

        return unique, report

    def is_duplicate_of(
        self, new_event: NormalizedEvent, existing: NormalizedEvent
    ) -> tuple[bool, float]:
        """Check if new_event is a duplicate of existing event."""
        sim = self._similarity(new_event, existing)
        return sim >= self.title_threshold, sim

    # ── Internal ──────────────────────────────────────────────────────────

    def _add_to_buffer(self, event: NormalizedEvent):
        key = self._event_key(event)
        self._recent_events[key] = event

        # Content hash for exact duplicate detection
        content_hash = hashlib.md5((event.title + event.summary).encode()).hexdigest()
        self._seen_hashes.add(content_hash)

    def _find_duplicate(self, event: NormalizedEvent) -> NormalizedEvent | None:
        """Find if event matches any in the buffer."""
        # Quick check: exact content hash
        content_hash = hashlib.md5((event.title + event.summary).encode()).hexdigest()
        if content_hash in self._seen_hashes:
            return self._recent_events.get(self._event_key(event))

        # Check against recent events within time window
        best_match = None
        best_score = 0.0

        for existing in self._recent_events.values():
            # Skip if too far apart in time
            if not self._within_temporal_window(event, existing):
                continue

            score = self._similarity(event, existing)
            if score >= self.title_threshold and score > best_score:
                best_match = existing
                best_score = score

        return best_match

    def _similarity(self, a: NormalizedEvent, b: NormalizedEvent) -> float:
        """Compute similarity between two events (0–1)."""
        scores = []

        # 1. Title similarity (weight: 0.4)
        title_sim = SequenceMatcher(None, a.title.lower(), b.title.lower()).ratio()
        scores.append(title_sim * 0.4)

        # 2. Keyword overlap (weight: 0.3)
        keywords_a = self._extract_keywords(a.title + " " + a.summary)
        keywords_b = self._extract_keywords(b.title + " " + b.summary)
        if keywords_a and keywords_b:
            overlap = len(keywords_a & keywords_b) / max(len(keywords_a | keywords_b), 1)
        else:
            overlap = 0.0
        scores.append(overlap * 0.3)

        # 3. Category match (weight: 0.15)
        if a.category == b.category and a.category:
            scores.append(0.15)
        else:
            scores.append(0.0)

        # 4. Country/entity overlap (weight: 0.15)
        entities_a = set(a.entities + a.countries)
        entities_b = set(b.entities + b.countries)
        if entities_a and entities_b:
            entity_overlap = len(entities_a & entities_b) / max(len(entities_a | entities_b), 1)
        else:
            entity_overlap = 0.0
        scores.append(entity_overlap * 0.15)

        return sum(scores)

    def _within_temporal_window(self, a: NormalizedEvent, b: NormalizedEvent) -> bool:
        """Check if two events are close enough in time to be duplicates."""
        try:
            t_a = (
                datetime.fromisoformat(a.occurred_at.replace("Z", "+00:00"))
                if a.occurred_at
                else datetime.fromisoformat(a.ingested_at.replace("Z", "+00:00"))
            )
            t_b = (
                datetime.fromisoformat(b.occurred_at.replace("Z", "+00:00"))
                if b.occurred_at
                else datetime.fromisoformat(b.ingested_at.replace("Z", "+00:00"))
            )
            return abs((t_a - t_b).total_seconds()) < self.temporal_window * 60
        except (ValueError, TypeError):
            return True  # If we can't parse times, assume close enough

    def _cluster_events(self, events: list[NormalizedEvent]) -> list[list[str]]:
        """Group related events into clusters (not strict duplicates but related)."""
        if len(events) < 2:
            return []

        clusters = []
        used = set()

        for i, e1 in enumerate(events):
            if e1.event_id in used:
                continue
            cluster = [e1.event_id]
            used.add(e1.event_id)

            for j, e2 in enumerate(events):
                if e2.event_id in used:
                    continue
                if (
                    e1.category == e2.category
                    and self._similarity(e1, e2) >= self.keyword_threshold
                ):
                    cluster.append(e2.event_id)
                    used.add(e2.event_id)

            if len(cluster) > 1:
                clusters.append(cluster)

        return clusters

    @staticmethod
    def _extract_keywords(text: str) -> set[str]:
        """Extract key terms for comparison."""
        if not text:
            return set()
        # Simple tokenization: lowercase, remove punctuation, get unique words > 3 chars
        words = re.findall(r"\b[a-z]{4,}\b", text.lower())
        # Remove stop words
        stop_words = {
            "this",
            "that",
            "with",
            "from",
            "have",
            "been",
            "were",
            "will",
            "they",
            "their",
            "about",
            "which",
            "would",
            "could",
            "should",
            "after",
            "before",
            "there",
            "where",
            "what",
            "when",
        }
        return set(w for w in words if w not in stop_words)

    @staticmethod
    def _event_key(event: NormalizedEvent) -> str:
        """Generate a unique key for buffer storage."""
        return f"{event.category}:{event.event_id}"

    def _prune_buffer(self):
        """Remove old events from the buffer."""
        if len(self._recent_events) > self.max_buffer:
            # Keep most recent half
            sorted_events = sorted(
                self._recent_events.values(), key=lambda e: e.ingested_at, reverse=True
            )
            keep = sorted_events[: self.max_buffer // 2]
            self._recent_events = {self._event_key(e): e for e in keep}

    def get_stats(self) -> dict:
        return {
            "total_processed": self.total_processed,
            "total_duplicates": self.total_duplicates_found,
            "duplicate_rate": (self.total_duplicates_found / max(self.total_processed, 1)),
            "buffer_size": len(self._recent_events),
            "seen_hashes": len(self._seen_hashes),
        }

    def reset(self):
        """Reset all state."""
        self._recent_events.clear()
        self._seen_hashes.clear()
