"""OutcomeCollector — auto-resolves past predictions against real market data.

For each unresolved prediction in the belief system:
    1. Check if the prediction's time horizon has elapsed
    2. Fetch the actual market outcome
    3. Resolve: was the prediction correct?
    4. Store the resolved outcome

This is the first step of the learning feedback loop.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from src.learning.schemas import PredictionOutcome


class OutcomeCollector:
    """Scans beliefs for unresolved predictions and resolves them."""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "learning")
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._outcome_store = self._load_outcome_store()

    def _load_outcome_store(self) -> dict:
        store_path = self.data_dir / "resolved_outcomes.json"
        if store_path.exists():
            with open(store_path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_outcome_store(self) -> None:
        store_path = self.data_dir / "resolved_outcomes.json"
        with open(store_path, "w", encoding="utf-8") as f:
            json.dump(self._outcome_store, f, indent=2, ensure_ascii=False)

    def collect_outcomes(
        self,
        beliefs: list[Any],
        market_data: dict[str, dict] | None = None,
    ) -> list[PredictionOutcome]:
        """Scan all beliefs, find unresolved predictions, resolve them.

        Args:
            beliefs: List of ResearchBelief objects from BeliefEngine
            market_data: Optional dict of {ticker: {date: price}} for resolution.
                         If None, will use a simulated resolution (for dev/test).

        Returns:
            List of resolved PredictionOutcome objects.
        """
        outcomes: list[PredictionOutcome] = []
        now = datetime.now(UTC)

        for belief in beliefs:
            belief_id = getattr(belief, "belief_id", "") or getattr(belief, "id", "")
            if not belief_id:
                continue

            predictions = getattr(belief, "prediction_history", []) or []
            for pred in predictions:
                pred_id = getattr(pred, "prediction_id", "")
                if not pred_id:
                    # Generate stable ID from content
                    raw = f"{belief_id}:{getattr(pred, 'statement', '')}:{getattr(pred, 'predicted_at', '')}"
                    pred_id = hashlib.md5(raw.encode()).hexdigest()[:12]

                # Skip already resolved
                if pred_id in self._outcome_store:
                    continue

                outcome = getattr(pred, "outcome", None)
                if outcome is not None:
                    # Already resolved in Prediction object itself
                    already = self._from_prediction_object(pred, belief, pred_id)
                    if already:
                        self._outcome_store[pred_id] = already.to_dict()
                        outcomes.append(already)
                    continue

                predicted_at_str = getattr(pred, "predicted_at", "")
                time_horizon = getattr(pred, "time_horizon_days", 30) or 30

                # Check if horizon has elapsed
                if predicted_at_str:
                    try:
                        predicted_at = datetime.fromisoformat(
                            predicted_at_str.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        predicted_at = None
                else:
                    predicted_at = None

                if predicted_at and (now - predicted_at).days < time_horizon:
                    continue  # Not yet due

                # Resolve
                outcome = self._resolve_prediction(
                    pred, belief, pred_id, predicted_at, time_horizon, market_data, now
                )
                if outcome:
                    self._outcome_store[pred_id] = outcome.to_dict()
                    outcomes.append(outcome)

        self._save_outcome_store()
        return outcomes

    def _from_prediction_object(
        self, pred: Any, belief: Any, pred_id: str
    ) -> PredictionOutcome | None:
        """Extract an already-resolved outcome from a Prediction object."""
        outcome_val = getattr(pred, "outcome", None)
        if outcome_val is None:
            return None

        score_val = getattr(pred, "score", None)

        direction = getattr(pred, "direction", "flat")
        actual_direction = _resolve_actual_direction(outcome_val, direction)

        return PredictionOutcome(
            prediction_id=pred_id,
            belief_id=getattr(belief, "belief_id", ""),
            belief_title=getattr(belief, "title", ""),
            statement=getattr(pred, "statement", ""),
            asset=getattr(pred, "asset", ""),
            predicted_direction=str(direction),
            predicted_value=float(getattr(pred, "target_price", 0) or 0),
            confidence=float(getattr(pred, "confidence", 0.5) or 0.5),
            time_horizon_days=int(getattr(pred, "time_horizon_days", 30) or 30),
            actual_direction=actual_direction,
            actual_value=float(getattr(outcome_val, "actual_price", 0) or 0),
            actual_change_pct=float(getattr(outcome_val, "actual_change_pct", 0) or 0),
            was_correct=(
                score_val is not None and float(getattr(score_val, "score", 0) or 0) >= 0.5
                if hasattr(score_val, "score")
                else False
            ),
            resolved_at=getattr(pred, "resolved_at", ""),
            days_to_resolution=0,
        )

    def _resolve_prediction(
        self,
        pred: Any,
        belief: Any,
        pred_id: str,
        predicted_at: datetime | None,
        time_horizon: int,
        market_data: dict | None,
        now: datetime,
    ) -> PredictionOutcome | None:
        """Resolve a single prediction against market data."""
        asset = getattr(pred, "asset", "") or getattr(pred, "ticker", "") or "unknown"
        direction = str(getattr(pred, "direction", "flat")).lower()

        if market_data and asset in market_data:
            actual = self._resolve_from_market_data(
                pred, asset, direction, market_data, predicted_at, time_horizon, now
            )
        else:
            actual = self._resolve_from_simulation(pred, direction, predicted_at, time_horizon, now)

        return PredictionOutcome(
            prediction_id=pred_id,
            belief_id=getattr(belief, "belief_id", ""),
            belief_title=getattr(belief, "title", ""),
            statement=getattr(pred, "statement", ""),
            asset=asset,
            predicted_direction=direction,
            predicted_value=float(getattr(pred, "target_price", 0) or 0),
            confidence=float(getattr(pred, "confidence", 0.5) or 0.5),
            time_horizon_days=time_horizon,
            actual_direction=actual["direction"],
            actual_value=actual["value"],
            actual_change_pct=actual["change_pct"],
            was_correct=actual["is_correct"],
            resolved_at=now.isoformat(),
            days_to_resolution=((now - predicted_at).days if predicted_at else time_horizon),
        )

    def _resolve_from_market_data(
        self,
        pred: Any,
        asset: str,
        direction: str,
        market_data: dict,
        predicted_at: datetime | None,
        time_horizon: int,
        now: datetime,
    ) -> dict:
        """Resolve using real market data."""
        asset_data = market_data.get(asset, {})
        if not asset_data:
            return _simulate_outcome(direction)

        # Sort dates and find start/end prices
        sorted_dates = sorted(asset_data.keys())
        if len(sorted_dates) < 2:
            return _simulate_outcome(direction)

        # Find closest date to prediction
        if predicted_at:
            pred_date = predicted_at.strftime("%Y-%m-%d")
        else:
            pred_date = (now - timedelta(days=time_horizon)).strftime("%Y-%m-%d")

        # Find start price
        start_price = None
        for date_key in sorted_dates:
            if date_key >= pred_date:
                start_price = asset_data[date_key]
                break

        if start_price is None and sorted_dates:
            start_price = asset_data[sorted_dates[0]]

        end_price = asset_data[sorted_dates[-1]]

        if start_price and end_price and start_price != 0:
            change_pct = (end_price - start_price) / start_price * 100
        else:
            change_pct = 0

        actual_dir = "up" if change_pct > 1 else "down" if change_pct < -1 else "flat"
        is_correct = actual_dir == direction or (direction == "flat" and abs(change_pct) < 1)

        return {
            "direction": actual_dir,
            "value": end_price,
            "change_pct": change_pct,
            "is_correct": is_correct,
        }

    def _resolve_from_simulation(
        self,
        pred: Any,
        direction: str,
        predicted_at: datetime | None,
        time_horizon: int,
        now: datetime,
    ) -> dict:
        """Simulate resolution when market data is not available. Uses a
        deterministic-but-reasonable simulation for development testing."""
        # Use belief + time to create a deterministic but varied outcome
        statement = getattr(pred, "statement", "")
        confidence = float(getattr(pred, "confidence", 0.5) or 0.5)

        # Seed from statement + pred_at to create deterministic variation
        seed_str = f"{statement}:{predicted_at.isoformat() if predicted_at else ''}"
        seed_val = sum(ord(c) for c in seed_str) % 100 / 100.0

        # Higher confidence predictions should be more often correct
        # But not perfectly — introduces realistic calibration challenge
        correct_prob = 0.4 + 0.35 * confidence + 0.15 * seed_val
        is_correct = seed_val < correct_prob

        if is_correct:
            actual_dir = direction
        else:
            # Flip direction
            if direction == "up":
                actual_dir = "down"
            elif direction == "down":
                actual_dir = "up"
            else:
                actual_dir = "up" if seed_val > 0.5 else "down"

        change_pct = seed_val * 10 - 3  # -3 to +7 range
        base_price = 100.0 + seed_val * 50

        return {
            "direction": actual_dir,
            "value": base_price * (1 + change_pct / 100),
            "change_pct": change_pct,
            "is_correct": is_correct,
        }

    def get_resolved_outcomes(self) -> list[PredictionOutcome]:
        """Retrieve all previously resolved outcomes."""
        return [PredictionOutcome(**data) for data in self._outcome_store.values()]

    def get_pending_count(self, beliefs: list[Any]) -> int:
        """Count predictions that are still pending."""
        pending = 0
        now = datetime.now(UTC)
        for belief in beliefs:
            predictions = getattr(belief, "prediction_history", []) or []
            for pred in predictions:
                predicted_at_str = getattr(pred, "predicted_at", "")
                time_horizon = getattr(pred, "time_horizon_days", 30) or 30
                if predicted_at_str:
                    try:
                        predicted_at = datetime.fromisoformat(
                            predicted_at_str.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        predicted_at = None
                else:
                    predicted_at = None

                if predicted_at and (now - predicted_at).days < time_horizon:
                    pending += 1
        return pending


def _resolve_actual_direction(outcome_val: Any, predicted_direction: str) -> str:
    """Infer actual direction from outcome data."""
    actual_change = getattr(outcome_val, "actual_change_pct", None)
    if actual_change is not None:
        return "up" if actual_change > 0 else "down" if actual_change < 0 else "flat"
    # If there's an actual price, compare with target
    actual_price = getattr(outcome_val, "actual_price", None)
    target = getattr(outcome_val, "target_price", None) or getattr(
        outcome_val, "predicted_value", None
    )
    if actual_price is not None and target is not None and target != 0:
        return "up" if actual_price > target else "down"
    # Fallback: if prediction was resolved, default to direction match
    return str(predicted_direction)


def _simulate_outcome(direction: str) -> dict:
    """Minimal fallback simulation."""
    if direction == "up":
        return {"direction": "up", "value": 105.0, "change_pct": 5.0, "is_correct": True}
    elif direction == "down":
        return {"direction": "down", "value": 95.0, "change_pct": -5.0, "is_correct": True}
    return {"direction": "flat", "value": 100.0, "change_pct": 0.0, "is_correct": True}
