"""V7.3 Live Narrative Tracking — Daily narrative intelligence.

Every day, output the current narrative landscape:
    - Top 3 narratives driving markets
    - Emerging narratives on the horizon
    - Fading narratives losing relevance
    - Broken narratives (definitively disproven)

For each narrative, explain WHY it's ranked where it is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class NarrativeStatus(str, Enum):
    DOMINANT = "dominant"        # Top narrative driving markets
    STRONG = "strong"           # Widely held, significant impact
    ACTIVE = "active"           # Relevant but not dominant
    EMERGING = "emerging"       # New, gaining traction
    FADING = "fading"           # Losing relevance
    BROKEN = "broken"           # Definively disproven
    DORMANT = "dormant"         # Inactive, could return


@dataclass
class NarrativeEntry:
    """A single narrative being tracked."""
    narrative_id: str = field(default_factory=lambda: uuid4().hex[:8])
    name: str = ""
    description: str = ""
    
    # Status
    status: NarrativeStatus = NarrativeStatus.ACTIVE
    rank: int = 0                    # 1 = most important
    previous_rank: int = 0
    
    # Metrics
    strength: float = 0.5           # 0–1: current conviction
    momentum: float = 0.0           # Positive = strengthening, Negative = fading
    evidence_count: int = 0
    supporting_evidence: int = 0
    contradicting_evidence: int = 0
    
    # Market impact
    market_impact: str = "neutral"   # bullish, bearish, neutral
    assets_affected: list[str] = field(default_factory=list)
    
    # Meta
    first_observed: str = ""
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evolution_notes: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.narrative_id,
            "name": self.name,
            "status": self.status.value,
            "rank": self.rank,
            "strength": round(self.strength, 3),
            "momentum": round(self.momentum, 3),
            "evidence": f"{self.supporting_evidence}/{self.evidence_count}",
            "impact": self.market_impact,
        }


@dataclass
class NarrativeRanking:
    """Daily narrative ranking output."""
    date: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d'))
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    top_narratives: list[NarrativeEntry] = field(default_factory=list)
    emerging: list[NarrativeEntry] = field(default_factory=list)
    fading: list[NarrativeEntry] = field(default_factory=list)
    broken: list[NarrativeEntry] = field(default_factory=list)
    dormant: list[NarrativeEntry] = field(default_factory=list)
    
    total_tracked: int = 0
    
    def summary(self) -> str:
        lines = [f"# Narrative Ranking — {self.date}", ""]
        
        if self.top_narratives:
            lines.append("## Top Narratives")
            for i, n in enumerate(self.top_narratives[:3]):
                lines.append(f"### {i+1}. {n.name}")
                lines.append(f"- Strength: {n.strength:.2f} | Momentum: {n.momentum:+.2f}")
                lines.append(f"- Status: {n.status.value} | Impact: {n.market_impact}")
                lines.append(f"- Evidence: {n.supporting_evidence}/{n.evidence_count} supporting")
                lines.append("")
        
        if self.emerging:
            lines.append("## Emerging Narratives")
            for n in self.emerging[:3]:
                lines.append(f"- **{n.name}** (strength: {n.strength:.2f}) — {n.description[:100]}")
            lines.append("")
        
        if self.fading:
            lines.append("## Fading Narratives")
            for n in self.fading[:3]:
                lines.append(f"- **{n.name}** — was rank {n.previous_rank}, now fading")
            lines.append("")
        
        if self.broken:
            lines.append("## Broken Narratives")
            for n in self.broken[:3]:
                lines.append(f"- ~~{n.name}~~ — definitively disproven")
            lines.append("")
        
        return "\n".join(lines)


class NarrativeTracker:
    """Track and rank narratives in real-time.

    Narratives compete for dominance. The tracker:
    1. Ranks narratives by strength, momentum, and evidence
    2. Detects emerging narratives before they become consensus
    3. Identifies fading narratives before they fully die
    4. Marks narratives as broken when definitively disproven
    """

    def __init__(self):
        self.narratives: dict[str, NarrativeEntry] = {}
        self._ranking_history: list[NarrativeRanking] = []
        self._recent_changes: list[dict] = []

    def register(self, name: str, description: str = "",
                 strength: float = 0.5, status: NarrativeStatus = NarrativeStatus.ACTIVE,
                 market_impact: str = "neutral") -> NarrativeEntry:
        """Register a new narrative to track."""
        entry = NarrativeEntry(
            name=name,
            description=description,
            status=status,
            strength=strength,
            market_impact=market_impact,
            first_observed=datetime.now(timezone.utc).isoformat(),
        )
        self.narratives[entry.narrative_id] = entry
        
        # Update rankings
        self._rerank()
        
        return entry

    def update(self, narrative_id: str, 
               strength: Optional[float] = None,
               momentum: Optional[float] = None,
               evidence_delta: Optional[dict] = None,
               status: Optional[NarrativeStatus] = None,
               note: str = "") -> Optional[NarrativeEntry]:
        """Update a narrative's metrics."""
        entry = self.narratives.get(narrative_id)
        if not entry:
            return None
        
        if strength is not None:
            entry.strength = max(0.0, min(1.0, strength))
        if momentum is not None:
            entry.momentum = momentum
        if status is not None:
            entry.status = status
        
        if evidence_delta:
            entry.supporting_evidence += evidence_delta.get("supporting", 0)
            entry.contradicting_evidence += evidence_delta.get("contradicting", 0)
            entry.evidence_count = entry.supporting_evidence + entry.contradicting_evidence
        
        if note:
            entry.evolution_notes.append(
                f"[{datetime.now().strftime('%Y-%m-%d')}] {note}"
            )
        
        entry.last_updated = datetime.now(timezone.utc).isoformat()
        
        # Auto-detect status changes
        self._auto_detect_status(entry)
        
        # Rerank
        self._rerank()
        
        return entry

    def get_ranking(self) -> NarrativeRanking:
        """Get the current narrative ranking."""
        return self._build_ranking()

    def get_daily_ranking(self) -> NarrativeRanking:
        """Get today's ranking, generating it if needed."""
        ranking = self._build_ranking()
        self._ranking_history.append(ranking)
        return ranking

    def get_narrative(self, narrative_id: str) -> Optional[NarrativeEntry]:
        return self.narratives.get(narrative_id)

    def find_by_name(self, name: str) -> Optional[NarrativeEntry]:
        """Find a narrative by name (fuzzy)."""
        name_lower = name.lower()
        for entry in self.narratives.values():
            if name_lower in entry.name.lower():
                return entry
        return None

    def mark_broken(self, narrative_id: str, reason: str = "") -> bool:
        """Mark a narrative as definitively broken."""
        entry = self.narratives.get(narrative_id)
        if not entry:
            return False
        
        entry.status = NarrativeStatus.BROKEN
        entry.strength = 0.0
        entry.momentum = -1.0
        entry.evolution_notes.append(
            f"[{datetime.now().strftime('%Y-%m-%d')}] BROKEN: {reason}"
        )
        entry.last_updated = datetime.now(timezone.utc).isoformat()
        
        self._recent_changes.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "broken",
            "narrative": entry.name,
            "reason": reason,
        })
        
        self._rerank()
        return True

    def mark_emerging(self, narrative_id: str) -> bool:
        """Promote a narrative to emerging status."""
        entry = self.narratives.get(narrative_id)
        if not entry:
            return False
        entry.status = NarrativeStatus.EMERGING
        entry.evolution_notes.append(
            f"[{datetime.now().strftime('%Y-%m-%d')}] Emerging — gaining traction"
        )
        entry.last_updated = datetime.now(timezone.utc).isoformat()
        self._rerank()
        return True

    def get_history(self, limit: int = 10) -> list[NarrativeRanking]:
        """Get ranking history."""
        return self._ranking_history[-limit:]

    def get_narrative_evolution(self, narrative_id: str) -> Optional[list[str]]:
        """Get the evolution notes for a narrative."""
        entry = self.narratives.get(narrative_id)
        if not entry:
            return None
        return entry.evolution_notes

    def get_recent_changes(self, limit: int = 20) -> list[dict]:
        return self._recent_changes[-limit:]

    def get_stats(self) -> dict:
        statuses = {}
        for n in self.narratives.values():
            s = n.status.value
            statuses[s] = statuses.get(s, 0) + 1
        
        ranking = self._build_ranking()
        
        return {
            "total_narratives": len(self.narratives),
            "status_distribution": statuses,
            "rankings_stored": len(self._ranking_history),
            "current_top3": [n.name for n in ranking.top_narratives[:3]],
            "emerging_count": len(ranking.emerging),
            "fading_count": len(ranking.fading),
            "broken_count": len(ranking.broken),
        }

    # ── Internal ─────────────────────────────────────────────────────────

    def _rerank(self):
        """Re-rank all active narratives."""
        active = [n for n in self.narratives.values() 
                  if n.status not in (NarrativeStatus.BROKEN, NarrativeStatus.DORMANT)]
        
        # Rank by: strength (0.5) + momentum (0.3) + evidence_support (0.2)
        def rank_score(n: NarrativeEntry) -> float:
            evidence_ratio = (
                n.supporting_evidence / max(n.evidence_count, 1)
                if n.evidence_count > 0 else 0.5
            )
            return n.strength * 0.5 + (n.momentum + 1) / 2 * 0.3 + evidence_ratio * 0.2
        
        sorted_narratives = sorted(active, key=rank_score, reverse=True)
        
        for i, n in enumerate(sorted_narratives):
            n.previous_rank = n.rank
            n.rank = i + 1

    def _build_ranking(self) -> NarrativeRanking:
        ranking = NarrativeRanking(total_tracked=len(self.narratives))
        
        for n in self.narratives.values():
            # Status-based checks first (BROKEN/DORMANT take priority over rank)
            if n.status == NarrativeStatus.BROKEN:
                ranking.broken.append(n)
            elif n.status == NarrativeStatus.DORMANT:
                ranking.dormant.append(n)
            elif n.status == NarrativeStatus.DOMINANT or n.rank <= 3:
                ranking.top_narratives.append(n)
            elif n.status == NarrativeStatus.EMERGING:
                ranking.emerging.append(n)
            elif n.status == NarrativeStatus.FADING:
                ranking.fading.append(n)
            # ACTIVE and STRONG with rank > 3 are tracked but not top-ranked
        
        # Sort each category by rank
        ranking.top_narratives.sort(key=lambda n: n.rank)
        ranking.emerging.sort(key=lambda n: n.strength, reverse=True)
        ranking.fading.sort(key=lambda n: n.momentum)
        
        return ranking

    def _auto_detect_status(self, entry: NarrativeEntry):
        """Auto-detect narrative status changes based on metrics."""
        if entry.status in (NarrativeStatus.BROKEN, NarrativeStatus.DORMANT):
            return
        
        # Strong momentum + high strength → DOMINANT
        if entry.strength > 0.8 and entry.momentum > 0.2:
            entry.status = NarrativeStatus.DOMINANT
        # Good strength, positive momentum → STRONG
        elif entry.strength > 0.6 and entry.momentum > 0:
            entry.status = NarrativeStatus.STRONG
        # Declining strength → FADING
        elif entry.momentum < -0.3 and entry.strength < 0.4:
            if entry.status not in (NarrativeStatus.EMERGING,):
                entry.status = NarrativeStatus.FADING
        
        # Track significant changes
        self._recent_changes.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "status_change",
            "narrative": entry.name,
            "new_status": entry.status.value,
            "strength": entry.strength,
            "momentum": entry.momentum,
        })
