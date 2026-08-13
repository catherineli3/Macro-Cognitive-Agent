"""ReviewQueue — Human review workflow for Agent outputs.

Quality: The agent is a research assistant, not the final decision maker.
Human researchers must be able to Accept, Reject, or Edit agent outputs.

Human edits become learning signals that improve future outputs.

Workflow:
    1. Agent produces research outputs (beliefs, narratives, hypotheses, memo, predictions)
    2. Outputs go into review queue
    3. Human accepts/rejects/edits
    4. Edits feed back into learning system (feedback loop)
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class ReviewStatus(str, Enum):
    """Status of an item in the review queue."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EDITED = "edited"
    SKIPPED = "skipped"


class ReviewableType(str, Enum):
    """Types of items that can be reviewed."""

    BELIEF = "belief"
    NARRATIVE = "narrative"
    HYPOTHESIS = "hypothesis"
    COUNTER_ARGUMENT = "counter_argument"
    RESEARCH_MEMO = "research_memo"
    PREDICTION = "prediction"
    REGIME_CLASSIFICATION = "regime_classification"
    CAPITAL_FLOW = "capital_flow"


@dataclass
class ReviewableItem:
    """An item awaiting human review."""

    item_id: str = ""
    item_type: ReviewableType = ReviewableType.BELIEF
    content: dict = field(default_factory=dict)
    original_content: dict = field(default_factory=dict)  # Before any edits
    status: ReviewStatus = ReviewStatus.PENDING

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    reviewed_at: str | None = None
    reviewer: str = ""

    # Review outcome
    reviewer_notes: str = ""
    edited_fields: list[str] = field(default_factory=list)  # Which fields were changed?

    # Learning signal
    learning_signal: dict = field(default_factory=dict)
    # {action: "accept"|"reject"|"edit", feedback_type: "reinforcement"|"correction",
    #  lessons: [...], confidence_impact: float}

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "item_type": (
                self.item_type.value
                if isinstance(self.item_type, ReviewableType)
                else str(self.item_type)
            ),
            "status": (
                self.status.value if isinstance(self.status, ReviewStatus) else str(self.status)
            ),
            "content_preview": str(self.content)[:100],
            "created_at": self.created_at,
            "reviewed_at": self.reviewed_at,
            "reviewer": self.reviewer,
            "reviewer_notes": self.reviewer_notes,
        }


@dataclass
class ReviewSession:
    """A review session — one sitting of reviewing agent outputs."""

    session_id: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    ended_at: str | None = None
    reviewer: str = ""

    items: list[ReviewableItem] = field(default_factory=list)
    total_items: int = 0
    accepted: int = 0
    rejected: int = 0
    edited: int = 0
    skipped: int = 0

    # Learning
    learning_signals: list[dict] = field(default_factory=list)

    def acceptance_rate(self) -> float:
        """% of items accepted (including edited)."""
        total_decided = self.accepted + self.rejected + self.edited
        if total_decided == 0:
            return 0.0
        return (self.accepted + self.edited) / total_decided

    def summary(self) -> str:
        return (
            f"Review Summary: {self.total_items} items reviewed — "
            f"{self.accepted} accepted, {self.rejected} rejected, "
            f"{self.edited} edited, {self.skipped} skipped. "
            f"Acceptance rate: {self.acceptance_rate():.0%}"
        )


class ReviewQueue:
    """Manage the human review workflow for agent outputs.

    Responsibilities:
    1. Enqueue agent outputs for review
    2. Track review status
    3. Accept/reject/edit items
    4. Convert human edits into learning signals for feedback loop

    The review queue is the bridge between agent automation and
    human judgment.
    """

    def __init__(self):
        self.queue: list[ReviewableItem] = []
        self.sessions: list[ReviewSession] = []
        self.current_session: ReviewSession | None = None
        self._on_learning_signal: Callable | None = None

    def start_session(self, reviewer: str = "") -> ReviewSession:
        """Start a new review session."""
        session = ReviewSession(
            session_id=f"REV_{str(uuid.uuid4())[:8]}",
            reviewer=reviewer,
        )
        self.current_session = session
        self.sessions.append(session)
        return session

    def end_session(self) -> ReviewSession | None:
        """End the current review session and compile learning signals."""
        if not self.current_session:
            return None

        self.current_session.ended_at = datetime.now(UTC).isoformat()

        # Compile learning signals
        for item in self.current_session.items:
            if item.learning_signal:
                self.current_session.learning_signals.append(item.learning_signal)

        session = self.current_session
        self.current_session = None
        return session

    def enqueue(
        self,
        content: dict,
        item_type: ReviewableType,
        original_content: dict | None = None,
    ) -> ReviewableItem:
        """Add an item to the review queue.

        Args:
            content: The item content to review
            item_type: Type of item (belief, hypothesis, memo, etc.)
            original_content: Original before any automated processing

        Returns:
            ReviewableItem in the queue
        """
        item = ReviewableItem(
            item_id=f"REVITEM_{str(uuid.uuid4())[:8]}",
            item_type=item_type,
            content=content,
            original_content=original_content or dict(content),
        )

        self.queue.append(item)

        if self.current_session:
            self.current_session.items.append(item)
            self.current_session.total_items = len(self.current_session.items)

        return item

    def enqueue_batch(
        self,
        items: list[dict],
        item_type: ReviewableType,
    ) -> list[ReviewableItem]:
        """Enqueue multiple items of the same type."""
        return [self.enqueue(content=item, item_type=item_type) for item in items]

    def accept(self, item_id: str, notes: str = "") -> ReviewableItem | None:
        """Accept an item — it passes review unchanged."""
        item = self._find_item(item_id)
        if not item:
            return None

        item.status = ReviewStatus.ACCEPTED
        item.reviewed_at = datetime.now(UTC).isoformat()
        item.reviewer_notes = notes

        item.learning_signal = {
            "action": "accept",
            "feedback_type": "reinforcement",
            "item_type": (
                item.item_type.value
                if isinstance(item.item_type, ReviewableType)
                else str(item.item_type)
            ),
            "lessons": ["Output quality met human standards — reinforce this pattern"],
            "confidence_impact": 0.05,
        }

        if self.current_session:
            self.current_session.accepted += 1

        self._emit_learning_signal(item.learning_signal)
        return item

    def reject(self, item_id: str, reason: str = "") -> ReviewableItem | None:
        """Reject an item — it does not pass review."""
        item = self._find_item(item_id)
        if not item:
            return None

        item.status = ReviewStatus.REJECTED
        item.reviewed_at = datetime.now(UTC).isoformat()
        item.reviewer_notes = reason

        item.learning_signal = {
            "action": "reject",
            "feedback_type": "correction",
            "item_type": (
                item.item_type.value
                if isinstance(item.item_type, ReviewableType)
                else str(item.item_type)
            ),
            "lessons": [f"Rejected because: {reason}"],
            "rejection_reason": reason,
            "confidence_impact": -0.1,
        }

        if self.current_session:
            self.current_session.rejected += 1

        self._emit_learning_signal(item.learning_signal)
        return item

    def edit(self, item_id: str, edits: dict, notes: str = "") -> ReviewableItem | None:
        """Edit an item — modify and accept.

        Args:
            item_id: Item to edit
            edits: Dict of field_name → new_value
            notes: Reviewer notes on the edit

        Returns:
            Updated ReviewableItem
        """
        item = self._find_item(item_id)
        if not item:
            return None

        # Track which fields were edited
        item.edited_fields = list(edits.keys())

        # Apply edits
        for field_name, new_value in edits.items():
            item.content[field_name] = new_value

        item.status = ReviewStatus.EDITED
        item.reviewed_at = datetime.now(UTC).isoformat()
        item.reviewer_notes = notes

        item.learning_signal = {
            "action": "edit",
            "feedback_type": "correction",
            "item_type": (
                item.item_type.value
                if isinstance(item.item_type, ReviewableType)
                else str(item.item_type)
            ),
            "edited_fields": item.edited_fields,
            "lessons": [
                f"Fields edited: {', '.join(item.edited_fields)}",
                "Agent output needed human refinement — improve prompts for this pattern",
            ],
            "confidence_impact": -0.05,
        }

        if self.current_session:
            self.current_session.edited += 1

        self._emit_learning_signal(item.learning_signal)
        return item

    def skip(self, item_id: str, notes: str = "") -> ReviewableItem | None:
        """Skip an item for later review."""
        item = self._find_item(item_id)
        if not item:
            return None

        item.status = ReviewStatus.SKIPPED
        item.reviewer_notes = notes or "Skipped for later review"

        if self.current_session:
            self.current_session.skipped += 1

        return item

    def get_pending(self) -> list[ReviewableItem]:
        """Get all items awaiting review."""
        return [item for item in self.queue if item.status == ReviewStatus.PENDING]

    def get_by_type(self, item_type: ReviewableType) -> list[ReviewableItem]:
        """Get all items of a specific type."""
        return [item for item in self.queue if item.item_type == item_type]

    def get_by_status(self, status: ReviewStatus) -> list[ReviewableItem]:
        """Get all items with a specific status."""
        return [item for item in self.queue if item.status == status]

    def get_learning_signals(self) -> list[dict]:
        """Get all learning signals from reviewed items.

        These feed into: PromptOptimizer, ConfidenceOptimizer, Belief system.
        """
        signals = []
        for item in self.queue:
            if item.learning_signal:
                signals.append(item.learning_signal)
        for session in self.sessions:
            signals.extend(session.learning_signals)
        return signals

    def statistics(self) -> dict:
        """Get review queue statistics."""
        total = len(self.queue)
        accepted = len(self.get_by_status(ReviewStatus.ACCEPTED))
        rejected = len(self.get_by_status(ReviewStatus.REJECTED))
        edited = len(self.get_by_status(ReviewStatus.EDITED))
        pending = len(self.get_pending())
        skipped = len(self.get_by_status(ReviewStatus.SKIPPED))

        decided = accepted + rejected + edited
        acceptance_rate = (accepted + edited) / decided if decided > 0 else 0.0

        # By type
        by_type = {}
        for item_type in ReviewableType:
            items = self.get_by_type(item_type)
            if items:
                by_type[item_type.value] = {
                    "total": len(items),
                    "accepted": sum(1 for i in items if i.status == ReviewStatus.ACCEPTED),
                    "rejected": sum(1 for i in items if i.status == ReviewStatus.REJECTED),
                    "edited": sum(1 for i in items if i.status == ReviewStatus.EDITED),
                }

        return {
            "total_items": total,
            "pending": pending,
            "accepted": accepted,
            "rejected": rejected,
            "edited": edited,
            "skipped": skipped,
            "acceptance_rate": round(acceptance_rate, 2),
            "total_signals": len(self.get_learning_signals()),
            "by_type": by_type,
        }

    def clear_reviewed(self):
        """Remove accepted/rejected items from queue, keeping pending."""
        self.queue = [
            item
            for item in self.queue
            if item.status in (ReviewStatus.PENDING, ReviewStatus.SKIPPED)
        ]

    def set_learning_callback(self, callback: Callable):
        """Set callback for learning signals.

        The callback receives learning signals as they are generated
        and can feed them into: PromptOptimizer, ConfidenceOptimizer, etc.
        """
        self._on_learning_signal = callback

    # ── Internal ──

    def _find_item(self, item_id: str) -> ReviewableItem | None:
        """Find an item by ID."""
        for item in self.queue:
            if item.item_id == item_id:
                return item
        return None

    def _emit_learning_signal(self, signal: dict):
        """Emit a learning signal to the callback."""
        if self._on_learning_signal:
            try:
                self._on_learning_signal(signal)
            except Exception:
                pass  # Don't let callback errors break the queue
