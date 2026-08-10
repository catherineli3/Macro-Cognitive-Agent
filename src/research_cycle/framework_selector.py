"""Framework Selector — maps MacroSnapshot to active frameworks (Milestone D, D3).

Algorithm:
    1. Regime Match: Compare snapshot regime with each framework's regime coverage
    2. Confidence: Framework confidence scores from evaluator
    3. Recency: How recently was the framework used successfully
    4. Composite Score: 0.5 * regime_match + 0.3 * confidence + 0.2 * recency
    5. Return top-N weighted frameworks
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.schemas.research import ResearchFramework, ResearchPrinciple
from src.schemas.macro_snapshot import MacroSnapshot
from src.research.evolution.regime_gate import RegimeSnapshot
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FrameworkSelection:
    """Result of the framework selection step."""

    primary_framework: ResearchFramework | None = None
    ranked: list[tuple[ResearchFramework, float]] = field(default_factory=list)
    regime_label: str = ""
    activation_scores: dict[str, float] = field(default_factory=dict)
    selection_rationale: str = ""

    @property
    def has_selection(self) -> bool:
        return self.primary_framework is not None and len(self.ranked) > 0

    @property
    def top_framework_id(self) -> str:
        if self.primary_framework:
            return self.primary_framework.framework_id
        return ""

    @property
    def ranked_ids(self) -> list[str]:
        return [fw.framework_id for fw, _ in self.ranked]

    def weight_for(self, framework_id: str) -> float:
        return self.activation_scores.get(framework_id, 0.0)

    def describe(self) -> str:
        if not self.has_selection:
            return f"FrameworkSelection: No active frameworks match regime '{self.regime_label}'"

        lines = [
            f"FrameworkSelection for regime '{self.regime_label}':",
            f"  Primary: {self.primary_framework.name} ({self.activation_scores.get(self.primary_framework.framework_id, 0):.0%})",
        ]
        for fw, score in self.ranked[:5]:
            lines.append(f"  [{score:.0%}] {fw.name}")
        return "\n".join(lines)


class FrameworkSelector:
    """Maps a MacroSnapshot to the most relevant active frameworks.

    Receives an EvolutionPipeline (from Milestone C) to access
    the current FrameworkSet and active frameworks.

    Design constraint: No new tools. Uses only existing data from C.
    """

    def __init__(self, evolution_pipeline=None):
        """Initialize with an optional EvolutionPipeline reference.

        The evolution_pipeline provides access to:
            - get_active_frameworks() → list[ResearchFramework]
            - get_framework_set() → FrameworkSet
            - get_active_principles() → list[ResearchPrinciple]
        """
        self._evolution = evolution_pipeline
        self._selection_history: list[FrameworkSelection] = []

    def set_evolution_pipeline(self, pipeline) -> None:
        """Set or update the evolution pipeline reference (lazy binding)."""
        self._evolution = pipeline

    # ── Main Entry ──────────────────────────────────────────────────────

    def select(self, macro_snapshot: MacroSnapshot) -> FrameworkSelection:
        """Select and rank active frameworks for the current macro snapshot.

        Args:
            macro_snapshot: Current market state including regime and signals

        Returns:
            FrameworkSelection with ranked frameworks and rationale
        """
        regime = macro_snapshot.regime
        regime_label = macro_snapshot.regime_label

        # Get active frameworks from evolution pipeline
        active_frameworks = self._get_active_frameworks()

        if not active_frameworks:
            return FrameworkSelection(
                regime_label=regime_label,
                selection_rationale="No active frameworks available. "
                                   "Agent has not yet developed any research frameworks.",
            )

        # Compute activation scores
        scores: dict[str, float] = {}
        for fw in active_frameworks:
            regime_match = self._compute_regime_match(fw, regime)
            confidence = self._get_framework_confidence(fw)
            recency = self._compute_recency(fw)
            scores[fw.framework_id] = (
                0.5 * regime_match + 0.3 * confidence + 0.2 * recency
            )

        # Rank and select primary
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        fw_map = {fw.framework_id: fw for fw in active_frameworks}

        ranked_frameworks = [(fw_map[fid], score) for fid, score in ranked if fid in fw_map]

        primary = ranked_frameworks[0][0] if ranked_frameworks else None
        top_score = ranked_frameworks[0][1] if ranked_frameworks else 0.0

        # Build rationale
        rationale_parts = [f"Regime: {regime_label}"]
        if primary:
            rationale_parts.append(
                f"Primary framework '{primary.name}' selected "
                f"(activation_score={top_score:.3f})"
            )
            rationale_parts.append(f"  - Regime match: {self._compute_regime_match(primary, regime):.2f}")
            rationale_parts.append(f"  - Confidence: {self._get_framework_confidence(primary):.2f}")
            rationale_parts.append(f"  - Recency: {self._compute_recency(primary):.2f}")
            # Secondary frameworks
            if len(ranked_frameworks) > 1:
                secondaries = [
                    f"{fw.name}({score:.2f})"
                    for fw, score in ranked_frameworks[1:4]
                ]
                rationale_parts.append(f"  Secondaries: {', '.join(secondaries)}")
        else:
            rationale_parts.append("No framework matched current regime.")

        selection = FrameworkSelection(
            primary_framework=primary,
            ranked=ranked_frameworks,
            regime_label=regime_label,
            activation_scores=scores,
            selection_rationale=" | ".join(rationale_parts),
        )

        self._selection_history.append(selection)
        return selection

    # ── Scoring Components ──────────────────────────────────────────────

    def _compute_regime_match(self, framework: ResearchFramework,
                               regime: RegimeSnapshot | None) -> float:
        """Score how well a framework matches the current regime.

        Checks:
            1. Framework's historical regime coverage vs current regime
            2. Domain coverage matches regime characteristics
            3. Framework was validated in similar regimes
        """
        if regime is None:
            return 0.3  # Neutral when no regime info

        score = 0.0
        checks = 0

        # Check domain coverage vs regime
        domains = framework.domain_coverage or {}

        # Liquidity frameworks match monetary policy regimes
        if "liquidity" in domains:
            score += self._monetary_policy_match(regime.monetary_policy)
            checks += 1

        # Growth frameworks match growth regimes
        if "growth" in domains:
            score += self._growth_match(regime.growth)
            checks += 1

        # Inflation frameworks match inflation regimes
        if "inflation" in domains:
            score += self._inflation_match(regime.inflation)
            checks += 1

        # Framework accuracy trajectory — higher accuracy = better regime fit
        acc = framework.accuracy_trajectory
        if acc:
            recent_acc = sum(acc[-5:]) / min(len(acc), 5) if acc else 0.0
            score += recent_acc
            checks += 1

        # Number of principles validated in this framework
        p_count = min(1.0, len(framework.principles) / 10)
        score += p_count
        checks += 1

        return score / max(checks, 1)

    @staticmethod
    def _monetary_policy_match(policy: str) -> float:
        """Map monetary policy to framework relevance."""
        if policy == "easing":
            return 0.9  # Liquidity frameworks highly relevant
        elif policy == "tightening":
            return 0.7
        else:
            return 0.5

    @staticmethod
    def _growth_match(growth: str) -> float:
        if growth in ("accelerating", "stable"):
            return 0.8
        elif growth == "decelerating":
            return 0.6
        else:
            return 0.3

    @staticmethod
    def _inflation_match(inflation: str) -> float:
        if inflation == "stable":
            return 0.8
        elif inflation == "falling":
            return 0.6
        else:
            return 0.5

    @staticmethod
    def _get_framework_confidence(framework: ResearchFramework) -> float:
        """Get framework confidence from its evaluator history."""
        acc = framework.accuracy_trajectory
        if not acc:
            return 0.5  # Default for new frameworks
        recent = sum(acc[-10:]) / min(len(acc), 10)
        return max(0.0, min(1.0, recent))

    @staticmethod
    def _compute_recency(framework: ResearchFramework) -> float:
        """Score how recently the framework was active/successful."""
        # Frameworks that were recently evaluated get higher recency
        acc = framework.accuracy_trajectory
        if not acc:
            return 0.3
        # Count how many recent evaluations; more recent = higher
        n = min(len(acc), 20)
        recency_weight = n / 20  # 20+ evaluations = full recency
        # Recent trend: improving = better
        if len(acc) >= 3:
            trend = acc[-1] - acc[-3] if len(acc) >= 3 else 0
            recency_weight += 0.2 * min(1.0, max(-1.0, trend))
        return max(0.0, min(1.0, recency_weight))

    # ── Helpers ─────────────────────────────────────────────────────────

    def _get_active_frameworks(self) -> list[ResearchFramework]:
        """Get active frameworks from the evolution pipeline."""
        if self._evolution:
            try:
                return self._evolution.get_active_frameworks()
            except Exception:
                pass
        return []

    @property
    def history(self) -> list[FrameworkSelection]:
        return list(self._selection_history)

    def summary(self) -> str:
        if not self._selection_history:
            return "FrameworkSelector: No selections made yet."
        last = self._selection_history[-1]
        return f"FrameworkSelector: Last selection — {last.describe()}"
