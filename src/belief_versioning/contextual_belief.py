"""Context-aware Belief Manager — Belief weight derived from transmission.

Milestone B: Transmission Reasoning.

V3.0 AdaptiveBelief:
    - Single global weight (updated via EMA)
    - No context awareness
    - Weight is an independent parameter

V3.1 ContextualBelief:
    - Multiple context profiles, each with independent weight
    - Weight = f(transmission segment reliabilities in context)
    - Context auto-discovery when sufficient data exists
    - When a transmission segment breaks, ALL beliefs depending on it
      in that context get their weight auto-adjusted (knowledge transfer)

This module provides:
    1. ContextualBeliefFactory: build from V3.0 AdaptiveBelief + hypothesis
    2. ContextSplitter: auto-discover context boundaries from performance data
    3. ContextualBeliefManager: manage lifecycle of contextual beliefs
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.schemas.transmission_v3_1 import (
    ContextProfile,
    ContextualBelief,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Context Key Builder ─────────────────────────────────────────────────────


class ContextKeyBuilder:
    """Build hashable context keys from macro conditions."""

    @staticmethod
    def from_regime(regime: str, conditions: dict = None) -> str:
        """Generate a context key from regime and optional conditions."""
        if not conditions:
            return regime or "default"

        parts = [regime or ""]
        for k in sorted(conditions.keys()):
            v = conditions[k]
            if isinstance(v, bool):
                parts.append(f"{k}={str(v).lower()}")
            elif isinstance(v, (int, float, str)):
                parts.append(f"{k}={v}")
        return "__".join(parts) if len(parts) > 1 else (regime or "default")

    @staticmethod
    def from_snapshot(regime: str, vix_level: str = "", event: str = "") -> str:
        """Build context key from common macro snapshot properties."""
        parts = [regime]
        if vix_level:
            parts.append(f"vix_{vix_level}")
        if event:
            parts.append(event.lower().replace(" ", "_"))
        return "__".join(parts)


# ── Contextual Belief Factory ───────────────────────────────────────────────


class ContextualBeliefFactory:
    """Build ContextualBelief from V3.0 AdaptiveBelief + transmission info."""

    def __init__(self) -> None:
        self._key_builder = ContextKeyBuilder()

    def from_hypothesis(
        self,
        belief_id: str,
        dimension: str,
        hypothesis_text: str,
        transmission_segments: list[str] = None,
        default_regime: str = "neutral",
    ) -> ContextualBelief:
        """Create a new contextual belief from a hypothesis.

        Args:
            belief_id: unique ID for this belief
            dimension: macro dimension (liquidity, credit, etc.)
            hypothesis_text: the belief statement
            transmission_segments: active segments for the default context
            default_regime: initial regime to create context profile for

        Returns:
            ContextualBelief with a default context profile
        """
        belief = ContextualBelief(
            belief_id=belief_id,
            dimension=dimension,
            hypothesis_text=hypothesis_text,
        )

        default_ctx = self._build_profile(
            belief_id=belief_id,
            context_key=default_regime,
            context_description=f"Default context: {default_regime}",
            regime=default_regime,
            segments=transmission_segments or [],
        )
        belief.contexts[default_regime] = default_ctx
        belief.default_context_key = default_regime

        return belief

    def from_v3_belief(
        self,
        v3_belief_id: str,
        dimension: str,
        hypothesis_text: str,
        v3_weight: float = 0.50,
        transmission_segments: list[str] = None,
        default_regime: str = "neutral",
    ) -> ContextualBelief:
        """Migrate a V3.0 AdaptiveBelief to V3.1 ContextualBelief."""
        belief = self.from_hypothesis(
            belief_id=v3_belief_id,
            dimension=dimension,
            hypothesis_text=hypothesis_text,
            transmission_segments=transmission_segments,
            default_regime=default_regime,
        )

        # Preserve the V3 weight as the initial derived weight
        if default_regime in belief.contexts:
            belief.contexts[default_regime].derived_weight = v3_weight
            belief.contexts[default_regime].derived_confidence = 0.40  # Low confidence initially

        return belief

    @staticmethod
    def _build_profile(
        belief_id: str,
        context_key: str,
        context_description: str,
        regime: str,
        segments: list[str],
    ) -> ContextProfile:
        return ContextProfile(
            context_id=f"{belief_id}:{context_key}",
            context_key=context_key,
            context_description=context_description,
            regime=regime,
            active_transmission_segments=list(segments),
        )


# ── Context Splitter ────────────────────────────────────────────────────────


class ContextSplitter:
    """Auto-discover context boundaries from belief performance data.

    When a belief has enough observations in a context AND performance varies
    significantly by some condition, the splitter creates a new context profile
    for the sub-condition.

    Example:
        Belief "liquidity easing → equities up" 
        Default context: "easing" with 30 observations, accuracy 0.65
        But when VIX > 25, accuracy drops to 0.38
        → Split: create "easing__vix_over_25" context with lower weight
    """

    def __init__(self) -> None:
        self._key_builder = ContextKeyBuilder()
        self._min_samples_for_split: int = 15
        self._min_accuracy_diff: float = 0.15  # Minimum % diff to justify split

    def analyze_and_split(
        self,
        belief: ContextualBelief,
        performance_by_condition: dict[str, dict],
        # ^ condition_key → {"sample_count": int, "accuracy": float}
    ) -> Optional[str]:
        """Check if a belief's context should be split.

        Returns the key of the newly created context, or None if no split needed.
        """
        if not belief.discovery_enabled:
            return None

        default_ctx = belief.contexts.get(belief.default_context_key)
        if not default_ctx or default_ctx.sample_count < self._min_samples_for_split:
            return None

        default_accuracy = default_ctx.historical_accuracy

        for cond_key, perf in performance_by_condition.items():
            if perf.get("sample_count", 0) < self._min_samples_for_split // 2:
                continue

            cond_accuracy = perf.get("accuracy", 0.0)
            if abs(cond_accuracy - default_accuracy) < self._min_accuracy_diff:
                continue

            # Create new context
            new_key = f"{belief.default_context_key}__{cond_key}"
            if new_key in belief.contexts:
                continue  # Already exists

            new_profile = ContextProfile(
                context_id=f"{belief.belief_id}:{new_key}",
                context_key=new_key,
                context_description=f"Split from {belief.default_context_key} by {cond_key}",
                regime=default_ctx.regime,
                conditions={cond_key: True},
                active_transmission_segments=list(default_ctx.active_transmission_segments),
                inactive_segments=[],
                derived_weight=max(0.10, cond_accuracy),  # Data-driven initial weight
                sample_count=perf.get("sample_count", 0),
                success_count=int(perf.get("sample_count", 0) * cond_accuracy),
                historical_accuracy=cond_accuracy,
            )
            belief.contexts[new_key] = new_profile

            logger.info(
                "context_split belief=%s from=%s to=%s default_acc=%.2f cond_acc=%.2f",
                belief.belief_id[:12],
                belief.default_context_key,
                new_key,
                default_accuracy,
                cond_accuracy,
            )

            return new_key

        return None


# ── Contextual Belief Manager ────────────────────────────────────────────────


class ContextualBeliefManager:
    """Manages the lifecycle of contextual beliefs.

    Bridge between:
        - Hypothesis Evolution (Milestone A) → hypothesis + transmission chains
        - Transmission Graph (Milestone B) → edge reliability data
        - Belief Versioning (V3.0) → historical belief records

    Responsibilities:
        1. Create beliefs from hypotheses + transmission chains
        2. Track belief performance per context
        3. Trigger context auto-splitting
        4. Provide active beliefs for prediction
    """

    def __init__(self) -> None:
        self._factory = ContextualBeliefFactory()
        self._splitter = ContextSplitter()
        self._beliefs: dict[str, ContextualBelief] = {}
        self._dimension_index: dict[str, list[str]] = defaultdict(list)
        # ^ dimension → [belief_id]

    # ── CRUD ──────────────────────────────────────────────────────────────

    def create(
        self,
        belief_id: str = "",
        dimension: str = "",
        hypothesis_text: str = "",
        transmission_segments: list[str] = None,
        default_regime: str = "neutral",
    ) -> ContextualBelief:
        """Create a new contextual belief."""
        if not belief_id:
            belief_id = f"cb-{uuid4().hex[:8]}"

        belief = self._factory.from_hypothesis(
            belief_id=belief_id,
            dimension=dimension,
            hypothesis_text=hypothesis_text,
            transmission_segments=transmission_segments or [],
            default_regime=default_regime,
        )
        self._beliefs[belief_id] = belief
        self._dimension_index[dimension].append(belief_id)

        return belief

    def migrate_from_v3(
        self,
        v3_belief_id: str,
        dimension: str,
        hypothesis_text: str,
        v3_weight: float = 0.50,
        transmission_segments: list[str] = None,
        default_regime: str = "neutral",
    ) -> ContextualBelief:
        """Migrate a V3.0 AdaptiveBelief."""
        belief = self._factory.from_v3_belief(
            v3_belief_id=v3_belief_id,
            dimension=dimension,
            hypothesis_text=hypothesis_text,
            v3_weight=v3_weight,
            transmission_segments=transmission_segments,
            default_regime=default_regime,
        )
        self._beliefs[v3_belief_id] = belief
        self._dimension_index[dimension].append(v3_belief_id)
        return belief

    def get(self, belief_id: str) -> Optional[ContextualBelief]:
        return self._beliefs.get(belief_id)

    def get_by_dimension(self, dimension: str) -> list[ContextualBelief]:
        ids = self._dimension_index.get(dimension, [])
        return [self._beliefs[bid] for bid in ids if bid in self._beliefs]

    def all_beliefs(self) -> list[ContextualBelief]:
        return list(self._beliefs.values())

    def active_beliefs(self, context_key: str = "") -> list[ContextualBelief]:
        """Get all beliefs that are active (non-zero weight) in given context."""
        active = []
        for b in self._beliefs.values():
            weight = b.active_weight(context_key or b.default_context_key)
            if weight > 0.10:  # Min activation threshold
                active.append(b)
        return active

    # ── Performance tracking ──────────────────────────────────────────────

    def record_outcome(
        self,
        belief_id: str,
        context_key: str,
        was_correct: bool,
    ) -> None:
        """Record a prediction outcome for a belief in a specific context."""
        belief = self._beliefs.get(belief_id)
        if not belief:
            return

        profile = belief.contexts.get(context_key)
        if not profile:
            # Auto-create context if it doesn't exist
            profile = ContextProfile(
                context_id=f"{belief_id}:{context_key}",
                context_key=context_key,
                context_description=f"Auto-created: {context_key}",
            )
            belief.contexts[context_key] = profile

        profile.sample_count += 1
        if was_correct:
            profile.success_count += 1

        if profile.sample_count > 0:
            profile.historical_accuracy = profile.success_count / profile.sample_count

        belief.last_updated = datetime.now(timezone.utc)

    # ── Context splitting ─────────────────────────────────────────────────

    def check_context_split(self, belief_id: str) -> Optional[str]:
        """Check if a belief needs context splitting. Returns new key or None."""
        belief = self._beliefs.get(belief_id)
        if not belief:
            return None

        # Build performance data for potential split conditions
        perf_data: dict[str, dict] = {}

        # Analyze by regime differences
        default_ctx = belief.contexts.get(belief.default_context_key)
        if default_ctx and default_ctx.sample_count >= self._splitter._min_samples_for_split:
            # Check each existing context for significant performance divergence
            for ctx_key, profile in belief.contexts.items():
                if ctx_key == belief.default_context_key:
                    continue
                if profile.sample_count < 5:
                    continue
                perf_data[ctx_key] = {
                    "sample_count": profile.sample_count,
                    "accuracy": profile.historical_accuracy,
                }

        return self._splitter.analyze_and_split(belief, perf_data)

    # ── Query ─────────────────────────────────────────────────────────────

    def get_weight(
        self,
        belief_id: str,
        context_key: str = "",
    ) -> float:
        """Get effective weight for a belief in a given context."""
        belief = self._beliefs.get(belief_id)
        if not belief:
            return 0.50
        return belief.active_weight(context_key or belief.default_context_key)

    def get_confidence(
        self,
        belief_id: str,
        context_key: str = "",
    ) -> float:
        """Get effective confidence."""
        belief = self._beliefs.get(belief_id)
        if not belief:
            return 0.30
        return belief.active_confidence(context_key or belief.default_context_key)

    def summary(self) -> str:
        """Human-readable summary of all beliefs."""
        lines = [f"ContextualBeliefManager: {len(self._beliefs)} beliefs"]

        dims = list(self._dimension_index.keys())
        lines.append(f"  Dimensions: {', '.join(dims)}")

        total_contexts = sum(len(b.contexts) for b in self._beliefs.values())
        total_samples = sum(b.total_samples for b in self._beliefs.values())
        lines.append(f"  Total contexts: {total_contexts}")
        lines.append(f"  Total observations: {total_samples}")

        lines.append("  Beliefs:")
        for b in sorted(self._beliefs.values(), key=lambda x: x.total_samples, reverse=True)[:8]:
            weight = b.active_weight(b.default_context_key)
            lines.append(
                f"    {b.belief_id[:12]} [{b.dimension}] "
                f"w={weight:.3f} ctx={len(b.contexts)} obs={b.total_samples}"
            )

        return "\n".join(lines)
