"""NewsDeduplicator — Merge duplicate stories into canonical events.

Quality: Multiple wire services report the same event. We need ONE canonical
ResearchEvent, not five copies. This prevents evidence double-counting and
narrative distortion in the Evidence Graph.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from src.news.schemas import ResearchEvent


class NewsDeduplicator:
    """Deduplicate news articles into canonical ResearchEvents.

    Strategy:
    1. Compute headline similarity matrix
    2. Cluster similar headlines
    3. Merge into single canonical event per cluster
    4. Preserve all source references for provenance
    """

    def __init__(self, similarity_threshold: float = 0.65):
        """
        Args:
            similarity_threshold: Headline similarity above which
                two articles are considered duplicates (0-1)
        """
        self.threshold = similarity_threshold

    def deduplicate(self, events: list[ResearchEvent]) -> list[ResearchEvent]:
        """Deduplicate a list of ResearchEvents.

        Groups similar events and produces canonical events with merged sources.
        """
        if len(events) <= 1:
            return events

        # 1. Build similarity matrix
        n = len(events)
        clusters = list(range(n))  # cluster[i] = cluster_id of event i

        for i in range(n):
            for j in range(i + 1, n):
                sim = self._similarity(events[i], events[j])
                if sim >= self.threshold:
                    # Merge clusters
                    old_cluster = clusters[j]
                    new_cluster = clusters[i]
                    for k in range(n):
                        if clusters[k] == old_cluster:
                            clusters[k] = new_cluster

        # 2. Group by cluster
        grouped = {}
        for i, c in enumerate(clusters):
            grouped.setdefault(c, []).append(i)

        # 3. Create canonical events
        canonical = []
        for c_id, indices in grouped.items():
            if len(indices) == 1:
                canonical.append(events[indices[0]])
            else:
                merged = self._merge_events([events[i] for i in indices])
                canonical.append(merged)

        return canonical

    def _similarity(self, e1: ResearchEvent, e2: ResearchEvent) -> float:
        """Compute similarity between two events (0-1)."""
        # If same category but different countries, they're probably different events
        if e1.country and e2.country and e1.country != e2.country:
            if e1.country != "US" and e2.country != "US":  # Allow US to be default
                return 0.0

        # Headline similarity
        t1 = self._normalize(e1.title)
        t2 = self._normalize(e2.title)
        headline_sim = SequenceMatcher(None, t1, t2).ratio() if t1 and t2 else 0.0

        # If headlines are very similar, high confidence
        if headline_sim > 0.85:
            return headline_sim

        # Check key_numbers overlap
        if e1.key_numbers and e2.key_numbers:
            shared_keys = set(e1.key_numbers.keys()) & set(e2.key_numbers.keys())
            if shared_keys:
                values_match = all(
                    e1.key_numbers.get(k) == e2.key_numbers.get(k) for k in shared_keys
                )
                if values_match:
                    return max(headline_sim, 0.7)

        # Same topic + same country = moderate similarity
        topic_match = e1.category == e2.category
        country_match = e1.country == e2.country
        if topic_match and country_match:
            return max(headline_sim, 0.5)

        return headline_sim

    def _merge_events(self, events: list[ResearchEvent]) -> ResearchEvent:
        """Merge multiple events into one canonical event."""
        if len(events) == 1:
            return events[0]

        # Use the most detailed event as the base
        base = max(events, key=lambda e: len(e.description) + len(e.entities) * 10)

        # Merge sources
        all_sources = []
        all_articles = []
        for e in events:
            all_sources.extend(e.sources)
            all_articles.extend(e.news_articles)

        # Merge entities
        all_entities = list(set(entity for e in events for entity in e.entities))

        # Merge countries
        all_countries = list(set(e.country for e in events if e.country))

        # Merge belief impacts
        merged_belief_impact = {}
        for e in events:
            for bid, bi in e.belief_impact.items():
                if bid in merged_belief_impact:
                    # Average the impact
                    existing = merged_belief_impact[bid]
                    existing["strength"] = max(existing.get("strength", 0), bi.get("strength", 0))
                else:
                    merged_belief_impact[bid] = dict(bi)

        # Pick highest severity
        severity_order = {"critical": 5, "high": 4, "medium": 3, "low": 2, "negligible": 1}
        max_severity = max(
            events,
            key=lambda e: severity_order.get(
                (
                    e.impact_severity.value
                    if hasattr(e.impact_severity, "value")
                    else str(e.impact_severity)
                ),
                3,
            ),
        )

        # Use key_numbers from the event with most data
        best_data = max(events, key=lambda e: len(e.key_numbers))

        return ResearchEvent(
            event_id=base.event_id,
            title=base.title,
            description=base.description,
            category=base.category,
            source_type=base.source_type,
            sources=all_sources,
            news_articles=all_articles,
            entities=all_entities,
            country=all_countries[0] if all_countries else base.country,
            countries_affected=all_countries,
            market_impact=base.market_impact,
            impact_severity=max_severity.impact_severity,
            impact_confidence=min(e.impact_confidence for e in events),  # Conservative
            belief_impact=merged_belief_impact,
            timestamp=base.timestamp,
            is_breaking=any(e.is_breaking for e in events),
            is_important=any(e.is_important for e in events),
            is_duplicate=True,
            key_numbers=best_data.key_numbers,
            consensus_expectation=best_data.consensus_expectation,
            actual_value=best_data.actual_value,
            surprise=best_data.surprise,
        )

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for comparison."""
        # Lower, strip punctuation, normalize whitespace
        text = text.lower().strip()
        import re

        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text
