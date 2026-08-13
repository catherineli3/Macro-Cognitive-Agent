"""V6.3 Research Session — Persistent research workflow management.

A Research Session represents a continuous research thread.
The agent doesn't start fresh each day — it continues from yesterday's session.

Session lifecycle:
    Start → Read → Question → Hypothesis → Counter → Rewrite → Prediction → Publish

Sessions are persisted and can span multiple days.
The agent picks up where it left off.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4


class SessionPhase(str, Enum):
    """Phases within a research session."""

    START = "start"
    READ = "read"  # Gathering information
    QUESTION = "question"  # Formulating research questions
    HYPOTHESIS = "hypothesis"  # Developing thesis
    COUNTER = "counter"  # Challenging thesis
    REWRITE = "rewrite"  # Refining based on counter
    PREDICTION = "prediction"  # Making forecasts
    PUBLISH = "publish"  # Finalizing memo
    PAUSED = "paused"
    CLOSED = "closed"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class SessionEntry:
    """A single entry in a research session — captures one thinking step."""

    entry_id: str = field(default_factory=lambda: uuid4().hex[:8])
    phase: SessionPhase = SessionPhase.READ
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    content: str = ""  # What was done/thought
    input_data: dict = field(default_factory=dict)  # What was consumed
    output_data: dict = field(default_factory=dict)  # What was produced
    decisions: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "phase": self.phase.value,
            "timestamp": self.timestamp,
            "content_summary": self.content[:200],
            "decisions": self.decisions,
            "questions": self.questions,
            "insights": self.insights,
        }


@dataclass
class ResearchSession:
    """A continuous research thread that persists across days.

    Not a daily run — a session that evolves as new information arrives.
    """

    session_id: str = field(default_factory=lambda: uuid4().hex[:12])
    title: str = ""  # Research topic
    description: str = ""  # What are we investigating?

    # Status
    status: SessionStatus = SessionStatus.ACTIVE
    current_phase: SessionPhase = SessionPhase.START

    # Timeline
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str = ""

    # Content
    entries: list[SessionEntry] = field(default_factory=list)

    # Research artifacts (built up over time)
    observations: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    hypotheses: list[dict] = field(default_factory=list)
    counter_arguments: list[dict] = field(default_factory=list)
    predictions: list[dict] = field(default_factory=list)
    evidence_collected: list[str] = field(default_factory=list)

    # Final output
    final_memo: str = ""
    memo_versions: list[dict] = field(default_factory=list)

    # Meta
    tags: list[str] = field(default_factory=list)
    related_sessions: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def duration_hours(self) -> float:
        if not self.entries:
            return 0
        try:
            first = datetime.fromisoformat(self.entries[0].timestamp.replace("Z", "+00:00"))
            last = datetime.fromisoformat(self.entries[-1].timestamp.replace("Z", "+00:00"))
            return (last - first).total_seconds() / 3600
        except (ValueError, TypeError, IndexError):
            return 0

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "status": self.status.value,
            "current_phase": self.current_phase.value,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "entries": len(self.entries),
            "hypotheses": len(self.hypotheses),
            "predictions": len(self.predictions),
            "memo_versions": len(self.memo_versions),
            "has_final_memo": bool(self.final_memo),
        }

    def summary(self) -> str:
        return (
            f"Session: {self.title} [{self.status.value}] — "
            f"{self.entry_count} entries, {len(self.hypotheses)} hypotheses, "
            f"{len(self.predictions)} predictions, "
            f"{len(self.memo_versions)} memo versions"
        )


class SessionManager:
    """Manage multiple research sessions with persistence.

    A researcher might have several active sessions:
    - "Fed Policy Path 2026"
    - "China Reflation Thesis"
    - "AI Capex Cycle"
    - "Global Liquidity Regime"

    Each session is independent but can reference others.
    """

    def __init__(self):
        self.sessions: dict[str, ResearchSession] = {}
        self.active_session_id: str | None = None

    def create_session(
        self, title: str, description: str = "", tags: list[str] | None = None
    ) -> ResearchSession:
        """Start a new research session."""
        session = ResearchSession(
            title=title,
            description=description,
            tags=tags or [],
        )
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> ResearchSession | None:
        return self.sessions.get(session_id)

    def get_active_session(self) -> ResearchSession | None:
        if self.active_session_id:
            return self.sessions.get(self.active_session_id)
        return None

    def set_active(self, session_id: str) -> bool:
        if session_id in self.sessions:
            self.active_session_id = session_id
            return True
        return False

    def add_entry(
        self,
        session_id: str,
        phase: SessionPhase,
        content: str,
        input_data: dict | None = None,
        output_data: dict | None = None,
        decisions: list[str] | None = None,
        questions: list[str] | None = None,
        insights: list[str] | None = None,
    ) -> SessionEntry | None:
        """Add a thinking entry to a session."""
        session = self.sessions.get(session_id)
        if not session:
            return None

        entry = SessionEntry(
            phase=phase,
            content=content,
            input_data=input_data or {},
            output_data=output_data or {},
            decisions=decisions or [],
            questions=questions or [],
            insights=insights or [],
        )

        session.entries.append(entry)
        session.current_phase = phase
        session.last_updated = datetime.now(UTC).isoformat()

        # Accumulate artifacts
        if questions:
            session.questions.extend(questions)
        if insights:
            session.observations.extend(insights)

        return entry

    def add_hypothesis(
        self,
        session_id: str,
        hypothesis: str,
        confidence: float = 0.5,
        evidence: list[str] | None = None,
    ) -> bool:
        """Add a hypothesis to the session."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.hypotheses.append(
            {
                "text": hypothesis,
                "confidence": confidence,
                "evidence": evidence or [],
                "timestamp": datetime.now(UTC).isoformat(),
                "status": "active",
            }
        )
        session.last_updated = datetime.now(UTC).isoformat()
        return True

    def add_counter_argument(
        self,
        session_id: str,
        argument: str,
        against_hypothesis_index: int = 0,
        strength: float = 0.5,
    ) -> bool:
        """Add a counter-argument challenging a hypothesis."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.counter_arguments.append(
            {
                "text": argument,
                "against_hypothesis": against_hypothesis_index,
                "strength": strength,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        session.last_updated = datetime.now(UTC).isoformat()
        return True

    def add_prediction(
        self,
        session_id: str,
        prediction: str,
        probability: float = 0.5,
        invalidation_condition: str = "",
        time_horizon: str = "",
    ) -> bool:
        """Add a prediction to the session."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.predictions.append(
            {
                "text": prediction,
                "probability": probability,
                "invalidation_condition": invalidation_condition,
                "time_horizon": time_horizon,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        session.last_updated = datetime.now(UTC).isoformat()
        return True

    def publish_memo(self, session_id: str, memo: str) -> bool:
        """Publish a memo version for this session."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        version = len(session.memo_versions) + 1
        session.memo_versions.append(
            {
                "version": version,
                "memo": memo,
                "published_at": datetime.now(UTC).isoformat(),
            }
        )
        session.final_memo = memo
        session.current_phase = SessionPhase.PUBLISH
        session.last_updated = datetime.now(UTC).isoformat()
        return True

    def close_session(self, session_id: str) -> bool:
        """Close a completed session."""
        session = self.sessions.get(session_id)
        if not session:
            return False
        session.status = SessionStatus.COMPLETED
        session.completed_at = datetime.now(UTC).isoformat()
        session.last_updated = datetime.now(UTC).isoformat()
        return True

    def pause_session(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False
        session.status = SessionStatus.PAUSED
        session.current_phase = SessionPhase.PAUSED
        session.last_updated = datetime.now(UTC).isoformat()
        return True

    def resume_session(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False
        session.status = SessionStatus.ACTIVE
        session.current_phase = SessionPhase.START
        session.last_updated = datetime.now(UTC).isoformat()
        return True

    def get_session_history(self, session_id: str) -> list[dict]:
        """Get the full entry history for a session."""
        session = self.sessions.get(session_id)
        if not session:
            return []
        return [e.to_dict() for e in session.entries]

    def get_session_timeline(self, session_id: str) -> list[dict]:
        """Get a timeline of all activities in a session."""
        session = self.sessions.get(session_id)
        if not session:
            return []

        timeline = []
        for entry in session.entries:
            timeline.append(
                {
                    "timestamp": entry.timestamp,
                    "phase": entry.phase.value,
                    "summary": entry.content[:150],
                }
            )
        return timeline

    def list_sessions(self, status: SessionStatus | None = None) -> list[dict]:
        """List all sessions, optionally filtered by status."""
        result = []
        for sid, session in self.sessions.items():
            if status and session.status != status:
                continue
            result.append(session.to_dict())
        return sorted(result, key=lambda x: x["last_updated"], reverse=True)

    def get_stats(self) -> dict:
        total = len(self.sessions)
        active = sum(1 for s in self.sessions.values() if s.status == SessionStatus.ACTIVE)
        completed = sum(1 for s in self.sessions.values() if s.status == SessionStatus.COMPLETED)

        return {
            "total_sessions": total,
            "active_sessions": active,
            "completed_sessions": completed,
            "total_entries": sum(s.entry_count for s in self.sessions.values()),
            "total_predictions": sum(len(s.predictions) for s in self.sessions.values()),
            "total_hypotheses": sum(len(s.hypotheses) for s in self.sessions.values()),
        }

    def export_session(self, session_id: str) -> dict | None:
        """Export a full session for persistence."""
        session = self.sessions.get(session_id)
        if not session:
            return None

        return {
            "session": session.to_dict(),
            "entries": [e.to_dict() for e in session.entries],
            "hypotheses": session.hypotheses,
            "counter_arguments": session.counter_arguments,
            "predictions": session.predictions,
            "observations": session.observations,
            "memo_versions": [
                {
                    "version": mv["version"],
                    "published_at": mv["published_at"],
                    "length": len(mv["memo"]),
                }
                for mv in session.memo_versions
            ],
        }
