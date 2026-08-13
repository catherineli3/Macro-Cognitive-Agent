"""Prediction Registry — SQLite-backed prediction tracking (Milestone E, Task 2).

Every prediction the agent makes is registered here. The OutcomeScheduler
periodically checks for expired predictions and evaluates them.

This is the system of record for:
    - What the agent predicted
    - When the prediction was made
    - Whether it was correct
    - The actual outcome

No new intelligence — pure storage + query.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from pathlib import Path
from typing import Any

from src.shared.logging import get_logger

logger = get_logger(__name__)

# ── Schema ────────────────────────────────────────────────────────────────

DDL = """
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id   TEXT PRIMARY KEY,
    thesis_id       TEXT NOT NULL,
    date            TEXT NOT NULL,          -- YYYY-MM-DD
    direction       TEXT,                   -- UP / DOWN / FLAT
    asset           TEXT,                   -- e.g. SPX, US10Y, VIX
    channel         TEXT,                   -- transmission channel name
    confidence      REAL,                   -- 0.0 - 1.0
    horizon_days    INTEGER,                -- expected duration in days
    expected_date   TEXT,                   -- YYYY-MM-DD
    status          TEXT DEFAULT 'pending', -- pending / success / failed / invalidated
    actual_value    REAL,
    actual_date     TEXT,
    evaluation      TEXT,                   -- human-readable outcome notes
    thesis_title    TEXT,                   -- cached thesis title for queries
    created_at      TEXT DEFAULT (datetime('now')),
    evaluated_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_pred_date ON predictions(date);
CREATE INDEX IF NOT EXISTS idx_pred_status ON predictions(status);
CREATE INDEX IF NOT EXISTS idx_pred_thesis ON predictions(thesis_id);
CREATE INDEX IF NOT EXISTS idx_pred_expected ON predictions(expected_date);
"""


@dataclass
class PredictionRecord:
    """In-memory representation of one prediction row."""

    prediction_id: str
    thesis_id: str = ""
    date: str = ""  # YYYY-MM-DD
    direction: str = ""  # UP / DOWN / FLAT
    asset: str = ""  # SPX, US10Y, etc.
    channel: str = ""  # transmission channel
    confidence: float = 0.0
    horizon_days: int = 30
    expected_date: str = ""  # YYYY-MM-DD
    status: str = "pending"
    actual_value: float | None = None
    actual_date: str = ""
    evaluation: str = ""
    thesis_title: str = ""
    created_at: str = ""
    evaluated_at: str = ""

    @property
    def is_pending(self) -> bool:
        return self.status == "pending"

    @property
    def is_success(self) -> bool:
        return self.status == "success"

    @property
    def is_due(self) -> bool:
        """Is this prediction past its expected date?"""
        if not self.expected_date:
            return False
        try:
            due = datetime.strptime(self.expected_date, "%Y-%m-%d").date()
            return due <= date_type.today()
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> dict:
        return {
            "prediction_id": self.prediction_id,
            "thesis_id": self.thesis_id,
            "date": self.date,
            "direction": self.direction,
            "asset": self.asset,
            "channel": self.channel,
            "confidence": self.confidence,
            "horizon_days": self.horizon_days,
            "expected_date": self.expected_date,
            "status": self.status,
            "actual_value": self.actual_value,
            "actual_date": self.actual_date,
            "evaluation": self.evaluation,
            "thesis_title": self.thesis_title,
            "created_at": self.created_at,
            "evaluated_at": self.evaluated_at,
        }

    @classmethod
    def from_row(cls, row: dict | tuple) -> PredictionRecord:
        """Create from a sqlite3.Row (converted to dict) or tuple."""
        if isinstance(row, dict):
            d = dict(row)
        else:
            cols = [
                "prediction_id",
                "thesis_id",
                "date",
                "direction",
                "asset",
                "channel",
                "confidence",
                "horizon_days",
                "expected_date",
                "status",
                "actual_value",
                "actual_date",
                "evaluation",
                "thesis_title",
                "created_at",
                "evaluated_at",
            ]
            d = dict(zip(cols, row))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class PredictionRegistry:
    """SQLite-backed persistent prediction tracker.

    Usage:
        registry = PredictionRegistry()
        registry.register_predictions(thesis, prediction_list)
        due = registry.get_due_predictions(date.today())
        registry.mark_outcome(pred_id, success=True, actual_value=5300)
    """

    DEFAULT_PATH = "data/predictions.db"

    def __init__(self, db_path: str | None = None):
        self._path = Path(db_path or self.DEFAULT_PATH)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.executescript(DDL)
        self._conn.commit()

    # ── Registration ────────────────────────────────────────────────────

    def register_predictions(
        self,
        thesis: Any,  # ResearchThesis
        predictions: Any | None,  # PredictionBatch or list
        date_str: str | None = None,
    ) -> int:
        """Register all predictions from a thesis for a given date.

        Args:
            thesis: ResearchThesis object
            predictions: PredictionBatch or list of Prediction objects
            date_str: Override date (YYYY-MM-DD). Default: today.

        Returns:
            Number of predictions registered.
        """
        if predictions is None:
            logger.info(
                "No predictions to register for thesis '%s'", getattr(thesis, "title", "unknown")
            )
            return 0

        today = date_str or date_type.today().isoformat()
        thesis_id = getattr(thesis, "thesis_id", "unknown")
        thesis_title = getattr(thesis, "title", "")[:200]
        count = 0

        # Unwrap batch if needed
        pred_list = predictions
        if hasattr(predictions, "predictions"):
            pred_list = predictions.predictions
        if not isinstance(pred_list, (list, tuple)):
            logger.warning("Unsupported prediction type: %s", type(predictions))
            return 0

        for p in pred_list:
            rec = self._prediction_to_record(p, thesis_id, thesis_title, today)
            if rec.prediction_id:  # Skip invalid
                self._insert_record(rec)
                count += 1

        self._conn.commit()
        logger.info(
            "Registered %d predictions for thesis '%s' on %s", count, thesis_title[:60], today
        )
        return count

    @staticmethod
    def _prediction_to_record(
        pred: Any,
        thesis_id: str,
        thesis_title: str,
        date_str: str,
    ) -> PredictionRecord:
        """Convert a prediction object to a PredictionRecord."""
        pred_id = getattr(pred, "prediction_id", "")
        if not pred_id:
            # Generate one
            import uuid

            pred_id = f"pred-{uuid.uuid4().hex[:12]}"

        direction = str(getattr(pred, "direction", ""))
        asset = getattr(pred, "asset", "") or getattr(pred, "indicator", "")
        channel = getattr(pred, "transmission_channel", "") or getattr(pred, "channel", "")
        confidence = float(getattr(pred, "confidence", 0.0) or 0.0)
        horizon_raw = getattr(pred, "horizon", 30) or 30
        # Horizon may be string like "5d", "21d" or int
        if isinstance(horizon_raw, str):
            horizon_raw = horizon_raw.rstrip("dD")
        horizon = int(horizon_raw)

        # Compute expected date
        try:
            expected = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=horizon)
            expected_str = expected.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            expected_str = ""

        return PredictionRecord(
            prediction_id=pred_id,
            thesis_id=thesis_id,
            date=date_str,
            direction=direction.upper() if direction else "",
            asset=str(asset),
            channel=str(channel),
            confidence=confidence,
            horizon_days=horizon,
            expected_date=expected_str,
            status="pending",
            thesis_title=thesis_title,
            created_at=datetime.now(UTC).isoformat(),
        )

    def _insert_record(self, rec: PredictionRecord) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO predictions
               (prediction_id, thesis_id, date, direction, asset, channel,
                confidence, horizon_days, expected_date, status,
                thesis_title, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rec.prediction_id,
                rec.thesis_id,
                rec.date,
                rec.direction,
                rec.asset,
                rec.channel,
                rec.confidence,
                rec.horizon_days,
                rec.expected_date,
                rec.status,
                rec.thesis_title,
                rec.created_at,
            ),
        )

    # ── Query ───────────────────────────────────────────────────────────

    def get_due_predictions(self, as_of: str | None = None) -> list[PredictionRecord]:
        """Get all pending predictions whose expected_date <= as_of.

        Args:
            as_of: Date string YYYY-MM-DD. Default: today.
        """
        as_of = as_of or date_type.today().isoformat()
        rows = self._conn.execute(
            """SELECT * FROM predictions
               WHERE status = 'pending'
                 AND expected_date <= ?
               ORDER BY expected_date ASC""",
            (as_of,),
        ).fetchall()
        return [PredictionRecord.from_row(dict(r)) for r in rows]

    def get_pending(self) -> list[PredictionRecord]:
        """Get all pending predictions regardless of due date."""
        rows = self._conn.execute(
            "SELECT * FROM predictions WHERE status = 'pending' ORDER BY date DESC",
        ).fetchall()
        return [PredictionRecord.from_row(dict(r)) for r in rows]

    def get_by_thesis(self, thesis_id: str) -> list[PredictionRecord]:
        """Get all predictions for a given thesis."""
        rows = self._conn.execute(
            "SELECT * FROM predictions WHERE thesis_id = ? ORDER BY date ASC",
            (thesis_id,),
        ).fetchall()
        return [PredictionRecord.from_row(dict(r)) for r in rows]

    def get_by_date(self, date_str: str) -> list[PredictionRecord]:
        """Get all predictions made on a specific date."""
        rows = self._conn.execute(
            "SELECT * FROM predictions WHERE date = ? ORDER BY confidence DESC",
            (date_str,),
        ).fetchall()
        return [PredictionRecord.from_row(dict(r)) for r in rows]

    def get_recently_evaluated(self, days: int = 7) -> list[PredictionRecord]:
        """Get predictions that were evaluated in the last N days.

        Returns only evaluated predictions (status = 'success' or 'failed')
        with an actual_date within the window.
        """
        cutoff = (date_type.today() - timedelta(days=days)).isoformat()
        rows = self._conn.execute(
            """SELECT * FROM predictions
               WHERE status IN ('success', 'failed')
                 AND actual_date >= ?
               ORDER BY actual_date DESC""",
            (cutoff,),
        ).fetchall()
        return [PredictionRecord.from_row(dict(r)) for r in rows]

    def get_recently_invalidated(self, days: int = 7) -> list[PredictionRecord]:
        """Get predictions that were invalidated in the last N days."""
        cutoff = (date_type.today() - timedelta(days=days)).isoformat()
        rows = self._conn.execute(
            """SELECT * FROM predictions
               WHERE status = 'invalidated'
                 AND evaluated_at >= ?
               ORDER BY evaluated_at DESC""",
            (cutoff,),
        ).fetchall()
        return [PredictionRecord.from_row(dict(r)) for r in rows]

    def get_history(self, days: int = 30) -> list[PredictionRecord]:
        """Get predictions from the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = self._conn.execute(
            "SELECT * FROM predictions WHERE date >= ? ORDER BY date DESC",
            (cutoff,),
        ).fetchall()
        return [PredictionRecord.from_row(dict(r)) for r in rows]

    # ── Update ──────────────────────────────────────────────────────────

    def mark_outcome(
        self,
        prediction_id: str,
        success: bool,
        actual_value: float | None = None,
        evaluation: str = "",
        actual_date: str | None = None,
    ) -> None:
        """Mark a prediction as evaluated.

        Args:
            prediction_id: The prediction to mark
            success: True if prediction was correct
            actual_value: The actual market value observed
            evaluation: Human-readable evaluation notes
            actual_date: When the evaluation occurred (default: today)
        """
        status = "success" if success else "failed"
        actual_date = actual_date or date_type.today().isoformat()
        evaluated_at = datetime.now(UTC).isoformat()

        self._conn.execute(
            """UPDATE predictions
               SET status = ?, actual_value = ?, actual_date = ?,
                   evaluation = ?, evaluated_at = ?
               WHERE prediction_id = ?""",
            (status, actual_value, actual_date, evaluation, evaluated_at, prediction_id),
        )
        self._conn.commit()
        logger.info("Prediction %s marked as %s", prediction_id, status)

    def mark_invalidated(self, prediction_id: str, reason: str = "") -> None:
        """Mark a prediction as invalidated (thesis was invalidated)."""
        self._conn.execute(
            """UPDATE predictions
               SET status = 'invalidated', evaluation = ?, evaluated_at = ?
               WHERE prediction_id = ?""",
            (reason, datetime.now(UTC).isoformat(), prediction_id),
        )
        self._conn.commit()

    def invalidate_by_thesis(self, thesis_id: str, reason: str = "") -> int:
        """Mark all predictions for a thesis as invalidated."""
        cursor = self._conn.execute(
            """UPDATE predictions
               SET status = 'invalidated', evaluation = ?, evaluated_at = ?
               WHERE thesis_id = ? AND status = 'pending'""",
            (reason, datetime.now(UTC).isoformat(), thesis_id),
        )
        self._conn.commit()
        count = cursor.rowcount
        logger.info("Invalidated %d predictions for thesis %s", count, thesis_id)
        return count

    # ── Statistics ──────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Comprehensive prediction statistics."""
        row = self._conn.execute("SELECT COUNT(*) as total FROM predictions").fetchone()
        total = row["total"] if row else 0

        pending_row = self._conn.execute(
            "SELECT COUNT(*) as c FROM predictions WHERE status = 'pending'"
        ).fetchone()
        pending = pending_row["c"] if pending_row else 0

        success_row = self._conn.execute(
            "SELECT COUNT(*) as c FROM predictions WHERE status = 'success'"
        ).fetchone()
        success = success_row["c"] if success_row else 0

        failed_row = self._conn.execute(
            "SELECT COUNT(*) as c FROM predictions WHERE status = 'failed'"
        ).fetchone()
        failed = failed_row["c"] if failed_row else 0

        evaluated = success + failed
        hit_rate = success / evaluated if evaluated > 0 else 0.0

        # Average confidence of correct vs wrong predictions
        conf_row = self._conn.execute(
            """SELECT
                 AVG(CASE WHEN status='success' THEN confidence END) as avg_success_conf,
                 AVG(CASE WHEN status='failed' THEN confidence END) as avg_failed_conf
               FROM predictions WHERE status IN ('success', 'failed')"""
        ).fetchone()

        return {
            "total": total,
            "pending": pending,
            "success": success,
            "failed": failed,
            "invalidated": total - pending - success - failed,
            "evaluated": evaluated,
            "hit_rate": round(hit_rate, 4),
            "avg_confidence_success": round(conf_row["avg_success_conf"] or 0, 4),
            "avg_confidence_failed": round(conf_row["avg_failed_conf"] or 0, 4),
        }

    def hit_rate_by_horizon(self) -> dict[str, float]:
        """Hit rate broken down by horizon buckets."""
        rows = self._conn.execute(
            """SELECT
                 CASE
                   WHEN horizon_days <= 7  THEN '0-7d'
                   WHEN horizon_days <= 14 THEN '8-14d'
                   WHEN horizon_days <= 30 THEN '15-30d'
                   WHEN horizon_days <= 60 THEN '31-60d'
                   ELSE '60d+'
                 END as bucket,
                 COUNT(*) as total,
                 SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as wins
               FROM predictions
               WHERE status IN ('success', 'failed')
               GROUP BY bucket
               ORDER BY bucket"""
        ).fetchall()

        result = {}
        for r in rows:
            total = r["total"]
            wins = r["wins"]
            result[r["bucket"]] = round(wins / total, 4) if total > 0 else 0.0
        return result

    def summary(self) -> str:
        """Human-readable summary."""
        s = self.stats()
        lines = [
            f"Prediction Registry: {s['total']} total, {s['pending']} pending",
            f"  Hit rate: {s['hit_rate']:.1%} ({s['success']}/{s['evaluated']})",
            f"  Avg confidence (correct): {s['avg_confidence_success']:.0%}",
            f"  Avg confidence (wrong):   {s['avg_confidence_failed']:.0%}",
        ]
        by_horizon = self.hit_rate_by_horizon()
        if by_horizon:
            horizon_str = ", ".join(f"{k}: {v:.0%}" for k, v in by_horizon.items())
            lines.append(f"  Hit rate by horizon: {horizon_str}")
        return "\n".join(lines)

    # ── Lifecycle ───────────────────────────────────────────────────────

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
