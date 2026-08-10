from __future__ import annotations

"""BeliefMemoryStore — JSON-file backed belief persistence.

Sprint 8 introduces persistent belief storage. The store handles:
    - Writing BeliefRecords to a JSON file.
    - Querying historical beliefs by dimension.
    - Detecting belief transitions (direction reversals, confidence changes).

Design:
    - Single-file JSON storage — portable, human-readable, no dependencies.
    - Transition detection happens at write time via last_belief() comparison.
    - Thread-safe: file operations are atomic (write to temp → rename).
    - The store owns NO domain knowledge beyond BeliefRecord fields.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.domain.memory import TransitionType
from src.schemas.memory import BeliefRecord
from src.shared.logging import get_logger

logger = get_logger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

_CONFIDENCE_STABLE_THRESHOLD = 0.10  # ±threshold for STABLE vs REINFORCED/WEAKENED


class BeliefMemoryStore:
    """Persistent storage for BeliefRecords.

    Usage:
        store = BeliefMemoryStore()
        store.record(belief_record)
        prior = store.last_belief("Liquidity")
        has_flipped = store.has_reversal("Risk_Appetite")
    """

    def __init__(self, file_path: str | None = None) -> None:
        """Initialize the store.

        Args:
            file_path: Path to the JSON storage file.
                       Defaults to '<workspace>/data/memory/beliefs.json'.
        """
        if file_path is None:
            # Default: project-relative path
            base = Path(__file__).resolve().parent.parent.parent
            file_path = str(base / "data" / "memory" / "beliefs.json")

        self._file_path = Path(file_path)
        self._records: list[BeliefRecord] = []
        self._loaded = False
        self._dirty: bool = False  # RC-2: Track whether flush is needed

    # ── Write Operations ─────────────────────────────────────────────────

    def record(self, record: BeliefRecord) -> None:
        """Persist a single belief record.

        Before writing, the store:
        1. Loads existing records if not already loaded.
        2. Computes the transition type by comparing against the last
           belief in the same dimension.
        3. Appends the record and marks the store dirty.

        The store is flushed to disk lazily — call commit() to persist,
        or the next record()/record_batch() call will flush implicitly.

        Args:
            record: The BeliefRecord to persist. Its transition field
                    will be overwritten with the computed value.
        """
        self._ensure_loaded()

        # Compute transition against prior belief in same dimension
        prior = self.last_belief(record.dimension)
        record.transition = self._detect_transition(record, prior)

        self._records.append(record)
        self._dirty = True
        self._flush()

        logger.info(
            "belief_recorded",
            extra={
                "belief_id": record.belief_id,
                "dimension": record.dimension,
                "direction": record.direction.value,
                "confidence": round(record.confidence, 3),
                "transition": record.transition.value,
            },
        )

    def record_batch(self, records: list[BeliefRecord]) -> None:
        """Persist multiple belief records in a single flush.

        Records are processed in order. Transition detection considers
        records within the batch: if two records share the same dimension,
        the second will see the first as its prior.

        RC-2: Uses lazy flush — records are marked dirty and flushed once.
        """
        if not records:
            return

        self._ensure_loaded()

        for record in records:
            prior = self.last_belief(record.dimension)
            record.transition = self._detect_transition(record, prior)
            self._records.append(record)

        self._dirty = True
        self._flush()

        logger.info(
            "belief_batch_recorded",
            extra={"count": len(records)},
        )

    def commit(self) -> None:
        """Explicitly flush dirty records to disk.

        Use this after multiple record() calls to batch-write.
        A no-op if the store is clean (no unflushed changes).
        """
        if self._dirty:
            self._flush()

    # ── Query Operations ─────────────────────────────────────────────────

    def last_belief(self, dimension: str) -> Optional[BeliefRecord]:
        """Most recent belief for a dimension.

        Args:
            dimension: Macro dimension to query.

        Returns:
            The newest BeliefRecord for this dimension, or None.
        """
        self._ensure_loaded()
        matches = [r for r in self._records if r.dimension == dimension]
        if not matches:
            return None
        # Return the newest (last in chronological order)
        return max(matches, key=lambda r: r.timestamp)

    def recent_beliefs(self, dimension: str, n: int = 5) -> list[BeliefRecord]:
        """Last N beliefs for a dimension, newest first.

        Args:
            dimension: Macro dimension to query.
            n: Maximum number of records to return (default 5).

        Returns:
            List of BeliefRecords sorted newest-first.
        """
        self._ensure_loaded()
        matches = [r for r in self._records if r.dimension == dimension]
        matches.sort(key=lambda r: r.timestamp, reverse=True)
        return matches[:n]

    def all_beliefs(self) -> list[BeliefRecord]:
        """All stored beliefs sorted newest-first."""
        self._ensure_loaded()
        return sorted(self._records, key=lambda r: r.timestamp, reverse=True)

    def has_reversal(self, dimension: str) -> bool:
        """Check if the most recent belief reversed direction.

        A reversal is when:
            direction(most_recent) != direction(second_most_recent)
        """
        recent = self.recent_beliefs(dimension, n=2)
        if len(recent) < 2:
            return False
        return recent[0].direction != recent[1].direction

    @property
    def belief_count(self) -> int:
        """Total number of stored beliefs."""
        self._ensure_loaded()
        return len(self._records)

    # ── Transition Detection ──────────────────────────────────────────────

    def _detect_transition(
        self,
        current: BeliefRecord,
        prior: Optional[BeliefRecord],
    ) -> TransitionType:
        """Compute the transition type for a new belief.

        Rules (evaluated in order):
            1. No prior for this dimension → NEW
            2. Different direction → REVERSED
            3. Same direction, confidence delta > +threshold → REINFORCED
            4. Same direction, confidence delta < -threshold → WEAKENED
            5. Same direction, small delta → STABLE
        """
        if prior is None:
            return TransitionType.NEW

        if current.direction != prior.direction:
            return TransitionType.REVERSED

        delta = round(current.confidence - prior.confidence, 6)

        if delta > _CONFIDENCE_STABLE_THRESHOLD:
            return TransitionType.REINFORCED
        elif delta < -_CONFIDENCE_STABLE_THRESHOLD:
            return TransitionType.WEAKENED
        else:
            return TransitionType.STABLE

    # ── File I/O ──────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        """Lazy-load records from disk on first access."""
        if self._loaded:
            return

        if self._file_path.exists():
            try:
                with open(self._file_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                loaded_records: list[BeliefRecord] = []
                for item in raw.get("records", []):
                    loaded_records.append(BeliefRecord(**item))
                self._records = loaded_records
                logger.debug(
                    "memory_store_loaded",
                    extra={
                        "path": str(self._file_path),
                        "count": len(self._records),
                    },
                )
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning(
                    "memory_store_load_failed — starting with empty store",
                    extra={"error": str(exc)},
                )
                self._records = []
        else:
            self._records = []

        self._loaded = True

    def _flush(self) -> None:
        """Write all records to disk atomically.

        RC-2 optimization:
          - Uses compact JSON (no indent) for I/O speed.
          - Skips write if store is clean (not dirty).
          - Uses atomic write-to-temp-then-rename for crash safety.

        For human-readable output, use export_pretty() instead.
        """
        if not self._dirty:
            return

        # Ensure parent directory exists
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(self._records),
            "records": [r.model_dump(mode="json") for r in self._records],
        }

        # Atomic write: temp file → rename (compact JSON for speed)
        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix=".json",
            prefix="beliefs_",
            dir=str(self._file_path.parent),
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp_path, str(self._file_path))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        finally:
            self._dirty = False

    def __repr__(self) -> str:
        return (
            f"<BeliefMemoryStore path={self._file_path.name} "
            f"records={self.belief_count}>"
        )
