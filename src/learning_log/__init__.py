"""Learning Log Repository — Append-Only Error & Learning Record (DDR-V3-005).

Stores every (prediction → outcome → diagnosis → learning action) chain
as an append-only LearningLogEntry. This is the raw data for PatternLearner
to identify systematic weaknesses.

Minimum 200 entries before PatternLearner activates (DDR-V3-005).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from src.schemas.learning_log import LearningLogEntry
from src.shared.logging import get_logger

logger = get_logger(__name__)


class LearningLogRepository:
    """Append-only store of LearningLogEntry records.

    DDR-V3-005: Persistent, queryable long-term learning dataset.
    Grows in value with every prediction cycle.
    """

    def __init__(self, storage_dir: str | Path = "data/learning_log") -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._entries: list[LearningLogEntry] = []
        self._loaded = False

    # ── CRUD ────────────────────────────────────────────────────────────

    async def append(self, entry: LearningLogEntry) -> str:
        """Append a single entry (immutable, append-only)."""
        await self._ensure_loaded()
        if not entry.entry_id:
            entry.entry_id = f"log-{uuid4().hex[:8]}"
        entry.logged_at = datetime.now(UTC)
        self._entries.append(entry)
        await self._persist_incremental(entry)
        return entry.entry_id

    async def append_batch(self, entries: list[LearningLogEntry]) -> int:
        """Append multiple entries."""
        count = 0
        for entry in entries:
            await self.append(entry)
            count += 1
        logger.info("log_batch_appended count=%d total=%d", count, await self.count())
        return count

    async def get_all(self) -> list[LearningLogEntry]:
        """Get all log entries."""
        await self._ensure_loaded()
        return list(self._entries)

    async def count(self) -> int:
        """Total number of entries."""
        await self._ensure_loaded()
        return len(self._entries)

    async def is_pattern_learner_ready(self) -> bool:
        """Check if ≥200 entries exist for PatternLearner activation (DDR-V3-005)."""
        return await self.count() >= 200

    # ── Query ───────────────────────────────────────────────────────────

    async def query_by_hypothesis(self, hypothesis_id: str) -> list[LearningLogEntry]:
        """Get all entries for a specific hypothesis."""
        await self._ensure_loaded()
        return [e for e in self._entries if e.hypothesis_id == hypothesis_id]

    async def query_by_error_category(self, error_category: str) -> list[LearningLogEntry]:
        """Get all entries with a specific error category."""
        await self._ensure_loaded()
        return [e for e in self._entries if e.error_category == error_category]

    async def query_by_channel(self, channel: str) -> list[LearningLogEntry]:
        """Get all entries for a specific transmission channel."""
        await self._ensure_loaded()
        return [e for e in self._entries if e.transmission_channel == channel]

    async def query_by_dimension(self, dimension: str) -> list[LearningLogEntry]:
        """Get all entries for a macro dimension."""
        await self._ensure_loaded()
        return [e for e in self._entries if e.dimension.lower() == dimension.lower()]

    async def get_error_distribution(
        self,
        window_days: int | None = None,
        channel: str | None = None,
    ) -> dict[str, int]:
        """Get error category distribution, optionally filtered."""
        await self._ensure_loaded()
        entries = self._entries
        if channel:
            entries = [e for e in entries if e.transmission_channel == channel]
        if window_days:
            cutoff = datetime.now(UTC)
            entries = [e for e in entries if (cutoff - e.logged_at).days <= window_days]

        dist: dict[str, int] = {}
        for e in entries:
            if e.error_category and not e.was_correct:
                dist[e.error_category] = dist.get(e.error_category, 0) + 1
        return dist

    async def get_entries_since(self, since: datetime) -> list[LearningLogEntry]:
        """Get all entries logged since a timestamp."""
        await self._ensure_loaded()
        return [e for e in self._entries if e.logged_at >= since]

    async def get_recent(self, n: int = 50) -> list[LearningLogEntry]:
        """Get the N most recent entries."""
        await self._ensure_loaded()
        return self._entries[-n:]

    # ── Persistence ─────────────────────────────────────────────────────

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        index_path = self._storage_dir / "log_index.json"
        if index_path.exists():
            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))
                for entry_data in data.get("entries", []):
                    entry = LearningLogEntry.model_validate(entry_data)
                    self._entries.append(entry)
                logger.info("learning_log_loaded entries=%d", len(self._entries))
            except Exception as e:
                logger.warning("learning_log_load_failed: %s", e)
        self._loaded = True

    async def _persist_incremental(self, entry: LearningLogEntry) -> None:
        """Append a single entry to the log file (append-only)."""
        log_path = self._storage_dir / "log_entries.jsonl"
        line = json.dumps(entry.model_dump(mode="json"), ensure_ascii=False, default=str)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    async def _persist_full(self) -> None:
        """Full re-persist (used for migration)."""
        index_path = self._storage_dir / "log_index.json"
        data = {
            "entries": [e.model_dump(mode="json") for e in self._entries],
            "total": len(self._entries),
            "persisted_at": datetime.now(UTC).isoformat(),
        }
        index_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
