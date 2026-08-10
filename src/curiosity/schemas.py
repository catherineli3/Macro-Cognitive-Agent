"""V3.5 Curiosity Engine — Research Curiosity & Autonomous Question Generator.

The agent shouldn't just analyze the known — it should ask:
    "What don't I understand that matters?"

Architecture:
    Current Beliefs → Uncertainty Map → Unknown Important Variables
    → Research Question Generator → Data Acquisition → New Belief Update

This mirrors how top macro researchers work: they constantly identify
what they DON'T know that could change their thesis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class UncertaintyNode:
    """A knowledge gap — something the agent doesn't understand well enough."""
    topic: str = ""
    domain: str = ""
    current_confidence: float = 0.5
    importance: float = 0.0       # How important is knowing this? (0-1)
    uncertainty: float = 0.0       # How uncertain are we? (0-1)
    curiosity_score: float = 0.0   # importance * uncertainty — what to research
    related_beliefs: list[str] = field(default_factory=list)
    existing_knowledge: str = ""
    unknown_aspects: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "domain": self.domain,
            "importance": self.importance,
            "uncertainty": self.uncertainty,
            "curiosity_score": self.curiosity_score,
            "unknown_aspects": self.unknown_aspects,
        }


@dataclass
class ResearchQuestion:
    """A specific, actionable research question generated from uncertainty."""
    question_id: str = ""
    question: str = ""
    domain: str = ""
    priority: float = 0.0          # 0-1, how urgently should this be researched?
    hypothesis: str = ""            # What do we currently think?
    what_would_change_mind: str = ""  # What evidence would flip our hypothesis?
    data_needed: list[str] = field(default_factory=list)
    status: str = "open"            # "open", "researching", "answered"
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "domain": self.domain,
            "priority": self.priority,
            "hypothesis": self.hypothesis,
            "what_would_change_mind": self.what_would_change_mind,
            "data_needed": self.data_needed,
            "status": self.status,
        }


@dataclass
class CuriosityReport:
    """Complete curiosity engine output."""
    report_id: str = ""
    date: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Uncertainty map
    uncertainty_nodes: list[UncertaintyNode] = field(default_factory=list)
    top_unknowns: list[UncertaintyNode] = field(default_factory=list)

    # Research agenda
    research_questions: list[ResearchQuestion] = field(default_factory=list)
    priority_questions: list[ResearchQuestion] = field(default_factory=list)

    # Summary
    most_important_unknown: str = ""
    recommended_research_agenda: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "date": self.date,
            "top_unknowns": [u.to_dict() for u in self.top_unknowns[:5]],
            "priority_questions": [rq.to_dict() for rq in self.priority_questions[:5]],
            "most_important_unknown": self.most_important_unknown,
            "recommended_research_agenda": self.recommended_research_agenda,
        }
