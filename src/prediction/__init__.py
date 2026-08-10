"""Multi-Prediction Engine — 1 Hypothesis → N Predictions (DDR-V3-009).

Generates multiple predictions per hypothesis across transmission channels.
Each prediction targets a specific asset class via a transmission_channel.
Prediction tiers: primary, secondary, tertiary.

Mapping rules define which assets respond to which macro dimensions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.schemas.hypothesis import HypothesisSchema, HypothesisSet
from src.schemas.hypothesis_library import HypothesisLibraryEntry
from src.schemas.prediction_v3 import (
    Prediction,
    PredictionBatch,
    PredictionStatus,
    PredictionTier,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Prediction Mapping Rules ─────────────────────────────────────────────────


# DDR-V3-009: Macro dimension → asset class predictions
# Each hypothesis dimension maps to 1-3 asset-level predictions
PREDICTION_MAPPING: dict[str, list[dict]] = {
    "liquidity": [
        {"indicator": "NASDAQ", "direction": None, "tier": "primary", "channel": "liquidity→equity"},
        {"indicator": "USD", "direction": None, "tier": "secondary", "channel": "liquidity→fx"},
        {"indicator": "Gold", "direction": None, "tier": "tertiary", "channel": "liquidity→commodity"},
    ],
    "credit": [
        {"indicator": "HYG", "direction": None, "tier": "primary", "channel": "credit→credit"},
        {"indicator": "SPX", "direction": None, "tier": "secondary", "channel": "credit→equity"},
    ],
    "growth": [
        {"indicator": "SPX", "direction": None, "tier": "primary", "channel": "growth→equity"},
        {"indicator": "US10Y", "direction": None, "tier": "secondary", "channel": "growth→rates"},
        {"indicator": "DXY", "direction": None, "tier": "tertiary", "channel": "growth→fx"},
    ],
    "risk_appetite": [
        {"indicator": "SPX", "direction": None, "tier": "primary", "channel": "risk_appetite→equity"},
        {"indicator": "VIX", "direction": None, "tier": "secondary", "channel": "risk_appetite→volatility"},
        {"indicator": "HYG", "direction": None, "tier": "tertiary", "channel": "risk_appetite→credit"},
    ],
    "inflation": [
        {"indicator": "TIPS", "direction": None, "tier": "primary", "channel": "inflation→bonds"},
        {"indicator": "Gold", "direction": None, "tier": "secondary", "channel": "inflation→commodity"},
        {"indicator": "US10Y", "direction": None, "tier": "tertiary", "channel": "inflation→rates"},
    ],
}

# Direction mapping based on hypothesis direction
DIRECTION_MAP = {
    # liquidity
    ("liquidity", "bullish"): {"NASDAQ": "bullish", "USD": "bullish", "Gold": "bearish"},
    ("liquidity", "bearish"): {"NASDAQ": "bearish", "USD": "bearish", "Gold": "bullish"},
    # credit
    ("credit", "bullish"): {"HYG": "bullish", "SPX": "bullish"},
    ("credit", "bearish"): {"HYG": "bearish", "SPX": "bearish"},
    # growth
    ("growth", "bullish"): {"SPX": "bullish", "US10Y": "bullish", "DXY": "bullish"},
    ("growth", "bearish"): {"SPX": "bearish", "US10Y": "bearish", "DXY": "bearish"},
    # risk_appetite
    ("risk_appetite", "bullish"): {"SPX": "bullish", "VIX": "bearish", "HYG": "bullish"},
    ("risk_appetite", "bearish"): {"SPX": "bearish", "VIX": "bullish", "HYG": "bearish"},
    # inflation
    ("inflation", "bullish"): {"TIPS": "bearish", "Gold": "bullish", "US10Y": "bullish"},
    ("inflation", "bearish"): {"TIPS": "bullish", "Gold": "bearish", "US10Y": "bearish"},
}

# Default horizon per dimension
DEFAULT_HORIZONS: dict[str, str] = {
    "liquidity": "5d",
    "credit": "5d",
    "growth": "10d",
    "risk_appetite": "3d",
    "inflation": "10d",
}


class PredictionMapper:
    """Maps hypothesis dimensions/directions to multi-asset predictions."""

    def get_mappings(self, dimension: str) -> list[dict]:
        """Get prediction mappings for a dimension."""
        dim_key = dimension.lower().replace(" ", "_")
        return PREDICTION_MAPPING.get(dim_key, [
            {"indicator": dimension, "direction": None, "tier": "primary", "channel": f"{dim_key}→general"},
        ])

    def get_direction(
        self, dimension: str, hypothesis_direction: str, indicator: str
    ) -> str:
        """Get the predicted direction for a specific indicator."""
        dim_key = dimension.lower().replace(" ", "_")
        h_dir = hypothesis_direction.lower()
        key = (dim_key, h_dir)
        mapping = DIRECTION_MAP.get(key, {})
        return mapping.get(indicator, h_dir)

    def get_default_horizon(self, dimension: str) -> str:
        """Get default evaluation horizon for a dimension."""
        dim_key = dimension.lower().replace(" ", "_")
        return DEFAULT_HORIZONS.get(dim_key, "5d")


# ── Multi-Prediction Engine ──────────────────────────────────────────────────


class MultiPredictionEngine:
    """V3 Prediction Engine — generates multi-asset predictions per hypothesis.

    DDR-V3-001: Predictions are validation instruments for hypotheses.
    DDR-V3-009: Each hypothesis generates 1-N predictions across channels.
    """

    def __init__(self) -> None:
        self._mapper = PredictionMapper()

    async def generate_predictions(
        self,
        hypothesis_set: HypothesisSet,
        run_id: str,
        hypothesis_library_entries: Optional[list[HypothesisLibraryEntry]] = None,
    ) -> PredictionBatch:
        """Generate multi-asset predictions for all hypotheses.

        Each hypothesis → N predictions (primary, secondary, tertiary).
        Predictions reference their source hypothesis (DDR-V3-001).
        Confidence is calibrated based on hypothesis confidence and prior track record.
        """
        batch_id = f"batch-{uuid4().hex[:8]}"
        predictions: list[Prediction] = []

        # Build a lookup from library for prior scores
        lib_scores: dict[str, float] = {}
        if hypothesis_library_entries:
            for entry in hypothesis_library_entries:
                lib_scores[entry.hypothesis_id] = entry.current_score.total_score

        for hypothesis in hypothesis_set.hypotheses:
            dim = hypothesis.dimension.lower().replace(" ", "_")
            mappings = self._mapper.get_mappings(dim)

            # Base confidence from hypothesis, moderated by Library score
            base_confidence = hypothesis.confidence
            lib_score = lib_scores.get(hypothesis.hypothesis_id, 0.5)
            # Blend: 60% hypothesis confidence + 40% library track record
            calibrated_confidence = 0.6 * base_confidence + 0.4 * lib_score

            for i, mapping in enumerate(mappings):
                indicator = mapping["indicator"]
                channel = mapping["channel"]
                tier_str = mapping["tier"]

                # Determine direction
                direction = self._mapper.get_direction(
                    dim, hypothesis.direction.value, indicator,
                )

                # Determine horizon
                horizon = self._mapper.get_default_horizon(dim)

                # Adjust confidence by tier (secondary/tertiary slightly lower)
                tier_confidence = calibrated_confidence
                if tier_str == "secondary":
                    tier_confidence *= 0.95
                elif tier_str == "tertiary":
                    tier_confidence *= 0.90

                prediction = Prediction(
                    prediction_id=f"pred-{uuid4().hex[:10]}",
                    run_id=run_id,
                    dimension=dim,
                    indicator=indicator,
                    direction=direction,
                    prediction_tier=PredictionTier(tier_str),
                    transmission_channel=channel,
                    horizon=horizon,
                    source_hypothesis_id=hypothesis.hypothesis_id,
                    source_evidence_ids=[
                        e.signal_id for e in hypothesis.supporting_evidence
                    ],
                    confidence=round(tier_confidence, 4),
                    rationale=f"Derived from: {hypothesis.statement[:200]}",
                    status=PredictionStatus.PENDING,
                )
                predictions.append(prediction)

        required_predictions = len(predictions)
        batch = PredictionBatch(
            batch_id=batch_id,
            run_id=run_id,
            predictions=predictions,
        )

        logger.info(
            "predictions_generated batch=%s total=%d hypotheses=%d channels=%d",
            batch_id, required_predictions, batch.hypothesis_count, batch.channel_count,
        )
        return batch

    def predict(
        self,
        hypothesis_set: HypothesisSet,
        run_id: str | None = None,
        hypothesis_library_entries: list[HypothesisLibraryEntry] | None = None,
    ) -> PredictionBatch:
        """Sync wrapper for generate_predictions. Compatible with cycle_engine.

        Bridges the async generate_predictions into a synchronous interface
        by running the coroutine in a dedicated event loop.
        """
        import asyncio
        import signal as _signal_mod

        if run_id is None:
            run_id = f"run-{uuid4().hex[:8]}"

        async def _generate():
            return await self.generate_predictions(
                hypothesis_set, run_id, hypothesis_library_entries,
            )

        # Windows: monkey-patch signal.set_wakeup_fd to avoid crash
        if not hasattr(_signal_mod, 'set_wakeup_fd'):
            _signal_mod.set_wakeup_fd = lambda fd: None  # type: ignore

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_generate())
        finally:
            try:
                loop.close()
            except Exception:
                pass

    async def get_predictions_by_hypothesis(
        self, batch: PredictionBatch, hypothesis_id: str
    ) -> list[Prediction]:
        """Get all predictions for a specific hypothesis from a batch."""
        return batch.by_hypothesis.get(hypothesis_id, [])

    async def get_predictions_by_channel(
        self, batch: PredictionBatch, channel: str
    ) -> list[Prediction]:
        """Get all predictions for a specific transmission channel."""
        return batch.by_channel.get(channel, [])

    def get_channel_accuracy(
        self, predictions: list[Prediction]
    ) -> dict[str, float]:
        """Compute accuracy per transmission channel from a set of evaluated predictions."""
        channel_correct: dict[str, int] = {}
        channel_total: dict[str, int] = {}

        for p in predictions:
            if p.status != PredictionStatus.EVALUATED:
                continue
            outcome = getattr(p, "outcome", None)
            if outcome is None:
                continue
            channel = p.transmission_channel
            channel_total[channel] = channel_total.get(channel, 0) + 1
            if getattr(outcome, "correct", False):
                channel_correct[channel] = channel_correct.get(channel, 0) + 1

        accuracy: dict[str, float] = {}
        for ch in channel_total:
            accuracy[ch] = channel_correct.get(ch, 0) / channel_total[ch]
        return accuracy
