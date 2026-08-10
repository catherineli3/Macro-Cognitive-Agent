"""Hypothesis Library — V3's Long-Term Knowledge Asset (DDR-V3-010).

The Hypothesis Library is the persistent store of all hypotheses the Agent has
ever formed, each with a composite HypothesisScore. This makes the Agent a
research system rather than a prediction pipeline.

Score computation aggregates 5 dimensions:
    1. Prediction Accuracy    (0.30)
    2. Evidence Quality        (0.25)
    3. Calibration             (0.20)
    4. Consistency             (0.15)
    5. Learning History        (0.10)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from src.schemas.belief_version import AdaptiveBelief
from src.schemas.hypothesis_library import HypothesisLibraryEntry, HypothesisScore
from src.schemas.prediction_v3 import Prediction
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Score Computer ───────────────────────────────────────────────────────────


class ScoreComputer:
    """Computes HypothesisScore from accumulated prediction and belief data."""

    @staticmethod
    def compute_prediction_accuracy(predictions: list[Prediction]) -> float:
        """Sub-score 1: Directional accuracy of predictions."""
        evaluated = [p for p in predictions if hasattr(p, "status") and p.status.value == "evaluated"]
        if not evaluated:
            return 0.5  # Neutral for unproven hypotheses
        correct = sum(1 for p in evaluated if getattr(getattr(p, "outcome", None), "correct", False))
        return correct / len(evaluated)

    @staticmethod
    def compute_evidence_quality(
        evidence_ids: list[str], evidence_freshness_days: float = 30.0
    ) -> tuple[float, int, float]:
        """Sub-score 2: Evidence quality based on count and freshness."""
        evidence_count = len(evidence_ids)
        if evidence_count == 0:
            return 0.3, 0, 30.0  # Low score for no evidence
        # Quality: count factor * freshness factor
        count_score = min(evidence_count / 5.0, 1.0)  # Max at 5+ evidence items
        freshness_score = max(0.0, 1.0 - evidence_freshness_days / 90.0)  # Decay over 90 days
        quality = 0.6 * count_score + 0.4 * freshness_score
        return quality, evidence_count, evidence_freshness_days

    @staticmethod
    def compute_calibration_score(predictions: list[Prediction]) -> tuple[float, float]:
        """Sub-score 3: Calibration — 1.0 - ECE."""
        evaluated = [p for p in predictions if hasattr(p, "status") and p.status.value == "evaluated"]
        if not evaluated:
            return 0.5, 0.25  # Default for unproven
        # Simple ECE: average |confidence - accuracy| per prediction
        ece_sum = 0.0
        for p in evaluated:
            pred_conf = p.confidence
            outcome = getattr(p, "outcome", None)
            was_correct = 1.0 if (outcome and getattr(outcome, "correct", False)) else 0.0
            ece_sum += abs(pred_conf - was_correct)
        ece = ece_sum / len(evaluated)
        return 1.0 - ece, ece

    @staticmethod
    def compute_consistency(predictions: list[Prediction], cycle_count: int) -> tuple[float, float]:
        """Sub-score 4: Consistency — stability across cycles."""
        if cycle_count < 2:
            return 0.5, 0.0  # Not enough data for consistency assessment
        evaluated = [p for p in predictions if hasattr(p, "status") and p.status.value == "evaluated"]
        if len(evaluated) < 5:
            return 0.5, 0.0
        accuracies = [1.0 if getattr(getattr(p, "outcome", None), "correct", False) else 0.0 for p in evaluated]
        mean = sum(accuracies) / len(accuracies)
        variance = sum((a - mean) ** 2 for a in accuracies) / len(accuracies)
        consistency = 1.0 - min(variance * 4, 1.0)  # Scale variance to 0-1
        return consistency, variance

    @staticmethod
    def compute_learning_history(belief: Optional[AdaptiveBelief]) -> tuple[float, float, int]:
        """Sub-score 5: Has accuracy improved over time?"""
        if belief is None:
            return 0.5, 0.0, 1
        slope = belief.get_accuracy_trajectory_slope()
        version_count = belief.current_version
        if version_count < 2:
            return 0.5, slope, version_count
        # Positive slope = improving, score > 0.5
        # Slope sigmoid: maps [-0.1, 0.1] to [0.1, 0.9]
        import math
        sigmoid_val = 1.0 / (1.0 + math.exp(-slope * 20))
        learning_score = max(0.1, min(0.9, sigmoid_val))
        return learning_score, slope, version_count

    def compute(
        self,
        hypothesis_id: str,
        predictions: list[Prediction],
        evidence_ids: list[str],
        evidence_freshness_days: float = 30.0,
        belief: Optional[AdaptiveBelief] = None,
    ) -> HypothesisScore:
        """Compute composite HypothesisScore from all 5 sub-scores."""
        # Sub-score 1
        pred_acc = self.compute_prediction_accuracy(predictions)

        # Sub-score 2
        ev_quality, ev_count, ev_fresh = self.compute_evidence_quality(
            evidence_ids, evidence_freshness_days,
        )

        # Sub-score 3
        cal_score, ece = self.compute_calibration_score(predictions)

        # Sub-score 4
        cycle_count = belief.cycle_count if belief else 0
        consistency, variance = self.compute_consistency(predictions, cycle_count)

        # Sub-score 5
        learning_score, slope, v_count = self.compute_learning_history(belief)

        # Composite
        total = (
            0.30 * pred_acc +
            0.25 * ev_quality +
            0.20 * cal_score +
            0.15 * consistency +
            0.10 * learning_score
        )

        return HypothesisScore(
            hypothesis_id=hypothesis_id,
            total_score=round(total, 4),
            prediction_accuracy=round(pred_acc, 4),
            predictions_evaluated=len([p for p in predictions if getattr(p, "status", None) and p.status.value == "evaluated"]),
            evidence_quality=round(ev_quality, 4),
            evidence_count=ev_count,
            evidence_freshness_days=ev_fresh,
            calibration_score=round(cal_score, 4),
            ece=round(ece, 4),
            consistency_score=round(consistency, 4),
            accuracy_variance=round(variance, 6),
            cycle_count=cycle_count,
            learning_history_score=round(learning_score, 4),
            accuracy_trajectory_slope=round(slope, 6),
            version_count=v_count,
            computed_at=datetime.now(timezone.utc),
        )


# ── Hypothesis Library ───────────────────────────────────────────────────────


class HypothesisLibrary:
    """Persistent store of scored hypotheses — the Agent's knowledge base.

    DDR-V3-010: The Library IS the Agent's intelligence.
    Hypothesis Generator queries it for prior beliefs with scores.
    """

    def __init__(self, storage_dir: str | Path = "data/hypothesis_library") -> None:
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, HypothesisLibraryEntry] = {}
        self._score_computer = ScoreComputer()
        self._loaded = False

    # ── CRUD ────────────────────────────────────────────────────────────

    async def register(
        self,
        hypothesis_id: str,
        dimension: str,
        statement: str = "",
        direction: str = "neutral",
        initial_score: Optional[HypothesisScore] = None,
    ) -> str:
        """Register a new hypothesis in the Library."""
        await self._ensure_loaded()

        if hypothesis_id in self._entries:
            logger.warning("hypothesis_already_registered id=%s", hypothesis_id)
            return hypothesis_id

        score = initial_score or HypothesisScore(hypothesis_id=hypothesis_id)
        entry = HypothesisLibraryEntry(
            hypothesis_id=hypothesis_id,
            dimension=dimension,
            statement=statement,
            direction=direction,
            current_score=score,
            score_history=[score],
            registered_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc),
            status="active",
        )
        self._entries[hypothesis_id] = entry
        await self._persist()
        logger.info("hypothesis_registered id=%s dim=%s score=%.3f", hypothesis_id, dimension, score.total_score)
        return hypothesis_id

    async def update_score(
        self,
        hypothesis_id: str,
        predictions: list[Prediction],
        evidence_ids: list[str] | None = None,
        belief: Optional[AdaptiveBelief] = None,
    ) -> Optional[HypothesisScore]:
        """Recompute score after new prediction outcomes."""
        await self._ensure_loaded()
        entry = self._entries.get(hypothesis_id)
        if entry is None:
            logger.warning("hypothesis_not_found id=%s", hypothesis_id)
            return None

        ev_ids = evidence_ids or []
        new_score = self._score_computer.compute(
            hypothesis_id=hypothesis_id,
            predictions=predictions,
            evidence_ids=ev_ids,
            belief=belief,
        )

        entry.current_score = new_score
        entry.score_history.append(new_score)
        entry.last_updated = datetime.now(timezone.utc)

        # Auto-deprecate if score drops too low
        if new_score.total_score < 0.30 and entry.status == "active":
            entry.status = "deprecated"
            logger.info("hypothesis_deprecated id=%s score=%.3f", hypothesis_id, new_score.total_score)

        await self._persist()
        return new_score

    async def get(self, hypothesis_id: str) -> Optional[HypothesisLibraryEntry]:
        """Retrieve a hypothesis entry."""
        await self._ensure_loaded()
        return self._entries.get(hypothesis_id)

    async def get_top(
        self,
        dimension: Optional[str] = None,
        min_score: float = 0.6,
        limit: int = 10,
    ) -> list[HypothesisLibraryEntry]:
        """Get top-scoring active hypotheses, optionally filtered by dimension."""
        await self._ensure_loaded()
        active = [
            e for e in self._entries.values()
            if e.is_active and e.current_score.total_score >= min_score
        ]
        if dimension:
            active = [e for e in active if e.dimension.lower() == dimension.lower()]
        active.sort(key=lambda e: e.current_score.total_score, reverse=True)
        return active[:limit]

    async def get_deprecated(self, dimension: Optional[str] = None) -> list[HypothesisLibraryEntry]:
        """Get all deprecated hypotheses."""
        await self._ensure_loaded()
        deprecated = [e for e in self._entries.values() if e.status == "deprecated"]
        if dimension:
            deprecated = [e for e in deprecated if e.dimension.lower() == dimension.lower()]
        return deprecated

    async def get_all_active(self) -> list[HypothesisLibraryEntry]:
        """Get all active hypotheses."""
        await self._ensure_loaded()
        return [e for e in self._entries.values() if e.is_active]

    async def get_active_belief_ids(
        self, dimension: str, min_score: float = 0.5
    ) -> list[str]:
        """Get belief IDs from active, well-scored hypotheses in a dimension."""
        entries = await self.get_top(dimension=dimension, min_score=min_score, limit=100)
        belief_ids: list[str] = []
        for e in entries:
            belief_ids.extend(e.belief_ids)
        return list(set(belief_ids))

    async def get_library_avg_score(self) -> float:
        """Average score across all active hypotheses (KPI-1 input)."""
        await self._ensure_loaded()
        active = [e for e in self._entries.values() if e.is_active]
        if not active:
            return 0.5
        return sum(e.current_score.total_score for e in active) / len(active)

    async def get_score_history(self, hypothesis_id: str) -> list[HypothesisScore]:
        """Get score trajectory for a hypothesis."""
        await self._ensure_loaded()
        entry = self._entries.get(hypothesis_id)
        if entry is None:
            return []
        return entry.score_history

    async def find_similar(
        self, dimension: str, direction: str, threshold: float = 0.7
    ) -> list[HypothesisLibraryEntry]:
        """Find active hypotheses with similar dimension and direction."""
        await self._ensure_loaded()
        similar = [
            e for e in self._entries.values()
            if e.is_active
            and e.dimension.lower() == dimension.lower()
            and e.direction.lower() == direction.lower()
            and e.current_score.total_score >= threshold
        ]
        return similar

    async def deprecate(self, hypothesis_id: str) -> bool:
        """Manually mark a hypothesis as deprecated."""
        await self._ensure_loaded()
        entry = self._entries.get(hypothesis_id)
        if entry is None:
            return False
        entry.status = "deprecated"
        entry.last_updated = datetime.now(timezone.utc)
        await self._persist()
        logger.info("hypothesis_manually_deprecated id=%s", hypothesis_id)
        return True

    # ── Persistence ─────────────────────────────────────────────────────

    async def _ensure_loaded(self) -> None:
        """Lazy-load entries from disk."""
        if self._loaded:
            return
        index_path = self._storage_dir / "library_index.json"
        if index_path.exists():
            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))
                for entry_data in data.get("entries", []):
                    entry = HypothesisLibraryEntry.model_validate(entry_data)
                    self._entries[entry.hypothesis_id] = entry
                logger.info("library_loaded entries=%d", len(self._entries))
            except Exception as e:
                logger.warning("library_load_failed: %s", e)
        self._loaded = True

    async def _persist(self) -> None:
        """Persist library to disk."""
        index_path = self._storage_dir / "library_index.json"
        entries_data = [e.model_dump(mode="json") for e in self._entries.values()]
        data = {
            "entries": entries_data,
            "total": len(entries_data),
            "active": sum(1 for e in self._entries.values() if e.is_active),
            "persisted_at": datetime.now(timezone.utc).isoformat(),
        }
        index_path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
