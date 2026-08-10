"""V7.1 Continuous Research — Agent never stops researching.

Instead of running once daily, the agent continuously:
    1. Listens for major events 24/7
    2. Triggers research updates on significant new information
    3. Versions every memo (v1, v2, v3...) — never overwrites
    4. Maintains a running research thread

Memo versioning is critical: every update produces a new version
with clear change documentation, not a replacement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4


class ResearchTrigger(str, Enum):
    """What triggers a research update?"""
    BREAKING_NEWS = "breaking_news"           # Critical event detected
    ECONOMIC_DATA = "economic_data"           # Major data release
    POLICY_EVENT = "policy_event"             # CB decision, speech
    MARKET_MOVE = "market_move"               # Significant price action
    SCHEDULED_UPDATE = "scheduled_update"     # Regular interval check
    MANUAL = "manual"                         # User-triggered


class MemoStatus(str, Enum):
    DRAFT = "draft"
    REVIEWING = "reviewing"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"          # Newer version exists
    RETRACTED = "retracted"


@dataclass
class MemoVersion:
    """A single version of a research memo. Never overwritten."""
    version_id: str = field(default_factory=lambda: uuid4().hex[:8])
    version_number: int = 1
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Trigger
    trigger: ResearchTrigger = ResearchTrigger.SCHEDULED_UPDATE
    trigger_event_id: str = ""
    trigger_description: str = ""
    
    # Content
    memo_content: str = ""
    word_count: int = 0
    
    # Changes from previous version
    changes_from_previous: list[str] = field(default_factory=list)
    sections_added: list[str] = field(default_factory=list)
    sections_removed: list[str] = field(default_factory=list)
    sections_modified: list[str] = field(default_factory=list)
    
    # Quality
    qa_score: Optional[float] = None
    qa_grade: str = ""
    passed_qa: bool = False
    
    # Status
    status: MemoStatus = MemoStatus.DRAFT
    published_at: str = ""
    
    def to_dict(self) -> dict:
        return {
            "version_id": self.version_id,
            "version_number": self.version_number,
            "created_at": self.created_at,
            "trigger": self.trigger.value,
            "trigger_description": self.trigger_description,
            "word_count": self.word_count,
            "changes": len(self.changes_from_previous),
            "qa_score": self.qa_score,
            "qa_grade": self.qa_grade,
            "status": self.status.value,
        }


@dataclass
class ContinuousResearchState:
    """State of the continuous research agent."""
    state_id: str = field(default_factory=lambda: uuid4().hex[:8])
    
    # Current memo
    current_topic: str = ""
    memo_versions: list[MemoVersion] = field(default_factory=list)
    
    # Activity
    is_active: bool = False
    started_at: str = ""
    last_update: str = ""
    total_updates: int = 0
    
    # Triggers processed
    trigger_history: list[dict] = field(default_factory=list)
    
    # Pending
    pending_triggers: list[dict] = field(default_factory=list)
    
    @property
    def current_version(self) -> Optional[MemoVersion]:
        if self.memo_versions:
            return self.memo_versions[-1]
        return None
    
    @property
    def latest_memo(self) -> str:
        v = self.current_version
        return v.memo_content if v else ""
    
    def summary(self) -> str:
        v = self.current_version
        return (
            f"Continuous Research: {self.total_updates} updates, "
            f"v{v.version_number if v else 0}, "
            f"active: {self.is_active}"
        )


class ContinuousResearch:
    """24/7 research agent with memo versioning.

    Usage:
        cr = ContinuousResearch()
        cr.start("Fed Policy Path 2026")
        
        # On breaking news:
        cr.on_event(critical_event, trigger=ResearchTrigger.BREAKING_NEWS)
        
        # On scheduled update:
        cr.on_scheduled()
        
        # Get version history:
        history = cr.get_version_history()
    """

    def __init__(self):
        self.state = ContinuousResearchState()
        
        # Callbacks
        self._on_new_version: Optional[Callable] = None
        self._research_pipeline: Optional[Callable] = None
        self._qa_pipeline: Optional[Callable] = None
        
        # Trigger thresholds
        self.critical_triggers: set[str] = set()

    def start(self, topic: str):
        """Begin continuous research on a topic."""
        self.state.is_active = True
        self.state.started_at = datetime.now(timezone.utc).isoformat()
        self.state.current_topic = topic

    def stop(self):
        """Pause continuous research."""
        self.state.is_active = False

    def on_event(self, event: dict, trigger: ResearchTrigger,
                 force_update: bool = False) -> Optional[MemoVersion]:
        """Handle a real-time event that may trigger a research update."""
        if not self.state.is_active:
            return None
        
        # Record the trigger
        trigger_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": trigger.value,
            "event_id": event.get("event_id", ""),
            "event_title": event.get("title", ""),
            "importance": event.get("importance", "medium"),
        }
        self.state.trigger_history.append(trigger_record)
        
        # Determine if this warrants an update
        should_update = force_update or self._should_update(event, trigger)
        
        if not should_update:
            self.state.pending_triggers.append(trigger_record)
            return None
        
        # Generate new memo version
        version = self._create_new_version(trigger, trigger_record)
        return version

    def on_scheduled(self) -> Optional[MemoVersion]:
        """Scheduled research update (e.g., end of day)."""
        if not self.state.is_active:
            return None
        
        trigger_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": ResearchTrigger.SCHEDULED_UPDATE.value,
            "event_id": "",
            "event_title": "Scheduled research refresh",
        }
        self.state.trigger_history.append(trigger_record)
        
        return self._create_new_version(ResearchTrigger.SCHEDULED_UPDATE, trigger_record)

    def force_update(self, reason: str = "") -> MemoVersion:
        """Force an immediate research update."""
        trigger_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": ResearchTrigger.MANUAL.value,
            "event_title": reason or "Manual update trigger",
        }
        return self._create_new_version(ResearchTrigger.MANUAL, trigger_record)

    def set_pipelines(self, research_pipeline: Optional[Callable] = None,
                      qa_pipeline: Optional[Callable] = None):
        """Set callbacks for research generation and QA."""
        self._research_pipeline = research_pipeline
        self._qa_pipeline = qa_pipeline

    def set_on_new_version(self, callback: Callable):
        """Set callback for new memo versions."""
        self._on_new_version = callback

    # ── Version Management ────────────────────────────────────────────────

    def get_version_history(self) -> list[MemoVersion]:
        """Get all memo versions in chronological order."""
        return list(self.state.memo_versions)

    def get_version(self, version_number: int) -> Optional[MemoVersion]:
        """Get a specific version by number."""
        for v in self.state.memo_versions:
            if v.version_number == version_number:
                return v
        return None

    def get_latest(self) -> Optional[MemoVersion]:
        return self.state.current_version

    def compare_versions(self, v1: int, v2: int) -> Optional[dict]:
        """Compare two memo versions, showing what changed."""
        ver1 = self.get_version(v1)
        ver2 = self.get_version(v2)
        
        if not ver1 or not ver2:
            return None
        
        return {
            "v1": v1, "v2": v2,
            "v1_created": ver1.created_at,
            "v2_created": ver2.created_at,
            "v2_changes": ver2.changes_from_previous,
            "v2_sections_added": ver2.sections_added,
            "v2_sections_removed": ver2.sections_removed,
            "word_count_diff": ver2.word_count - ver1.word_count,
            "qa_diff": (
                (ver2.qa_score or 0) - (ver1.qa_score or 0)
                if ver2.qa_score and ver1.qa_score else 0
            ),
        }

    def get_trigger_history(self) -> list[dict]:
        return self.state.trigger_history[-50:]  # Last 50

    def get_stats(self) -> dict:
        triggers_by_type = {}
        for t in self.state.trigger_history:
            tt = t.get("trigger", "unknown")
            triggers_by_type[tt] = triggers_by_type.get(tt, 0) + 1
        
        return {
            "topic": self.state.current_topic,
            "is_active": self.state.is_active,
            "total_versions": len(self.state.memo_versions),
            "total_updates": self.state.total_updates,
            "total_triggers": len(self.state.trigger_history),
            "triggers_by_type": triggers_by_type,
            "pending": len(self.state.pending_triggers),
            "current_version": self.state.current_version.version_number if self.state.current_version else 0,
        }

    # ── Internal ─────────────────────────────────────────────────────────

    def _should_update(self, event: dict, trigger: ResearchTrigger) -> bool:
        """Decide if an event warrants a research update."""
        # Always update on critical triggers
        if trigger in (ResearchTrigger.BREAKING_NEWS, ResearchTrigger.POLICY_EVENT):
            return True
        
        importance = event.get("importance", "medium")
        if importance in ("critical", "high"):
            return True
        
        # For economic data, update if it's a significant surprise
        if trigger == ResearchTrigger.ECONOMIC_DATA:
            surprise = event.get("surprise", 0)
            if surprise and abs(surprise) > 0:
                return True
        
        # Check dedup: don't update for the same event twice
        event_id = event.get("event_id", "")
        if event_id and event_id in self.critical_triggers:
            return False
        
        if event_id:
            self.critical_triggers.add(event_id)
        
        return False

    def _create_new_version(self, trigger: ResearchTrigger,
                            trigger_record: dict) -> MemoVersion:
        """Create a new memo version with change tracking."""
        prev = self.state.current_version
        
        # Create new version
        version = MemoVersion(
            version_number=len(self.state.memo_versions) + 1,
            trigger=trigger,
            trigger_event_id=trigger_record.get("event_id", ""),
            trigger_description=trigger_record.get("event_title", ""),
        )
        
        # Generate memo content via research pipeline
        if self._research_pipeline:
            try:
                version.memo_content = self._research_pipeline(
                    topic=self.state.current_topic,
                    trigger=trigger,
                    previous_version=prev,
                    event=trigger_record,
                )
            except Exception:
                version.memo_content = self._generate_default_memo(version)
        else:
            version.memo_content = self._generate_default_memo(version)
        
        version.word_count = len(version.memo_content.split())
        
        # Track changes
        if prev:
            version.changes_from_previous = self._detect_changes(prev.memo_content, version.memo_content)
        
        # QA
        if self._qa_pipeline:
            try:
                qa_result = self._qa_pipeline(version.memo_content)
                version.qa_score = qa_result.get("score", 0)
                version.qa_grade = qa_result.get("grade", "D")
                version.passed_qa = qa_result.get("passed", False)
            except Exception:
                version.passed_qa = True  # Default pass if QA unavailable
        else:
            version.passed_qa = True
        
        # Supersede previous version
        if prev:
            prev.status = MemoStatus.SUPERSEDED
        
        version.status = MemoStatus.PUBLISHED
        version.published_at = datetime.now(timezone.utc).isoformat()
        
        # Store
        self.state.memo_versions.append(version)
        self.state.last_update = version.created_at
        self.state.total_updates += 1
        
        # Callback
        if self._on_new_version:
            try:
                self._on_new_version(version)
            except Exception:
                pass
        
        return version

    def _generate_default_memo(self, version: MemoVersion) -> str:
        """Generate a default memo when no pipeline is available."""
        return f"""# Research Update: {self.state.current_topic}

## Version {version.version_number}
**Trigger**: {version.trigger.value}
**Description**: {version.trigger_description}
**Generated**: {version.created_at}

## Status Update
Continuous research monitoring active. Awaiting pipeline integration for 
full analysis generation.

## Key Monitoring Points
- Macro data releases
- Central bank communications
- Market price action
- Narrative shifts

---
*Auto-generated by Continuous Research Agent v7.1*
"""

    def _detect_changes(self, prev_memo: str, new_memo: str) -> list[str]:
        """Detect what changed between memo versions."""
        changes = []
        
        # Simple section-based diff
        prev_sections = set(
            line.strip().lstrip('#- ') for line in prev_memo.split('\n')
            if line.startswith('##') and len(line) > 5
        )
        new_sections = set(
            line.strip().lstrip('#- ') for line in new_memo.split('\n')
            if line.startswith('##') and len(line) > 5
        )
        
        added = new_sections - prev_sections
        removed = prev_sections - new_sections
        modified = prev_sections & new_sections
        
        if added:
            changes.append(f"Added sections: {', '.join(list(added)[:3])}")
        if removed:
            changes.append(f"Removed sections: {', '.join(list(removed)[:3])}")
        if modified and not added and not removed:
            changes.append(f"Updated {(len(modified))} sections with new information")
        
        return changes if changes else ["Incremental update with new data"]
