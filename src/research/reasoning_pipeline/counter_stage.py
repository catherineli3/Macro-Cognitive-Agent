"""V5.2 Stage 6: Counter — Rigorously challenge our own hypothesis.

This is what separates professional from amateur research.

Amateurs: "Here's our view and why we're right."
Professionals: "Here's our view, here's every reason it could be wrong,
                and here's why we still hold it."

Self-criticism is not optional in macro research.
"""

from __future__ import annotations

from datetime import datetime

from src.research.reasoning_pipeline.schemas import (
    CounterOutput,
    EvidenceOutput,
    HypothesisOutput,
    ObservationOutput,
    StageStatus,
)


class CounterStage:
    """Stage 6: Mandatory counterargument generation."""

    COUNTER_DIMENSIONS = [
        "data_quality",  # Could the data be wrong/misleading?
        "model_risk",  # Is our framework appropriate?
        "regime_change",  # Are we in a new regime where history doesn't apply?
        "policy_error",  # Could policymakers make the wrong call?
        "exogenous_shock",  # What external shocks could hit?
        "market_positioning",  # Is consensus too one-sided?
        "correlation_breakdown",  # Could assumed correlations break?
        "liquidity_event",  # Could liquidity suddenly dry up?
        "geopolitical_tail",  # What geopolitical events could disrupt?
        "measurement_error",  # Are our indicators measuring what we think?
    ]

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def execute(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
        hypothesis: HypothesisOutput,
    ) -> CounterOutput:
        """Execute counterargument generation.

        This is MANDATORY. The pipeline cannot skip this stage.

        Args:
            observation: Stage 1
            evidence: Stage 2
            hypothesis: Stage 5

        Returns:
            CounterOutput with structured counterarguments
        """
        output = CounterOutput(
            timestamp=datetime.now().isoformat(),
            status=StageStatus.IN_PROGRESS,
        )

        # 1. Generate counterarguments from each dimension
        output.counter_arguments = self._generate_counters(observation, evidence, hypothesis)

        # 2. Select primary counter
        if output.counter_arguments:
            # Most severe/fatal counter
            fatal_counters = [c for c in output.counter_arguments if c.get("severity") == "fatal"]
            if fatal_counters:
                output.primary_counter = fatal_counters[0]["claim"]
                output.most_concerning_counter = fatal_counters[0]["claim"]
            else:
                output.primary_counter = output.counter_arguments[0]["claim"]
                output.most_concerning_counter = max(
                    output.counter_arguments, key=lambda c: c.get("probability", 0)
                )["claim"]

        # 3. Define invalidation conditions
        output.invalidation_conditions = self._define_invalidation(observation, hypothesis)

        # 4. Explain why we still prefer our hypothesis
        output.why_still_preferred = self._explain_preference(output, evidence, hypothesis)

        # 5. Generate trace
        output.reasoning_trace = self._generate_trace(output)
        output.status = StageStatus.COMPLETED

        return output

    def _generate_counters(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
        hypothesis: HypothesisOutput,
    ) -> list[dict]:
        """Generate counterarguments from each dimension."""
        counters = []

        # 1. Data quality
        if observation.data_surprises:
            counters.append(
                {
                    "claim": (
                        "Data quality risk: Recent data surprises may reflect "
                        "measurement noise or seasonal distortions rather than "
                        "genuine economic shifts. Revision risk is elevated."
                    ),
                    "evidence": observation.data_surprises[:2],
                    "severity": "minor",
                    "probability": 0.3,
                }
            )

        # 2. Contradicting evidence
        if evidence.contradicting_evidence:
            counters.append(
                {
                    "claim": (
                        f"Contradicting evidence exists: "
                        f"{evidence.contradicting_evidence[0][:100]}"
                    ),
                    "evidence": evidence.contradicting_evidence[:2],
                    "severity": "major" if len(evidence.contradicting_evidence) > 2 else "minor",
                    "probability": min(
                        0.5,
                        len(evidence.contradicting_evidence)
                        / max(len(evidence.supporting_evidence), 1),
                    ),
                }
            )

        # 3. Regime change risk
        counters.append(
            {
                "claim": (
                    "Regime change risk: We may be observing a structural break "
                    "rather than a cyclical pattern. Post-COVID, post-QE, post-globalization "
                    "dynamics may make historical analogies unreliable."
                ),
                "evidence": ["Structural shifts in inflation dynamics", "Deglobalization trends"],
                "severity": "fatal",
                "probability": 0.25,
            }
        )

        # 4. Policy error
        counters.append(
            {
                "claim": (
                    "Policy error risk: Central banks could over-tighten (causing recession) "
                    "or under-tighten (allowing inflation to re-accelerate). The path to "
                    "a perfect soft landing is narrow."
                ),
                "evidence": ["Historical precedent of policy errors"],
                "severity": "major",
                "probability": 0.3,
            }
        )

        # 5. Market positioning / consensus risk
        counters.append(
            {
                "claim": (
                    "Consensus crowding risk: If the market is already positioned "
                    "for this scenario, even a correct call may not generate alpha. "
                    "The trade is consensus; the surprise would be the opposite."
                ),
                "evidence": [],
                "severity": "minor" if hypothesis.hypothesis_confidence > 0.6 else "major",
                "probability": 0.35,
            }
        )

        # 6. Exogenous shock
        counters.append(
            {
                "claim": (
                    "Exogenous shock risk: Geopolitical events, natural disasters, "
                    "or financial accidents could override the macro picture entirely."
                ),
                "evidence": ["Geopolitical uncertainty", "Cyber risk", "Pandemic risk"],
                "severity": "major",
                "probability": 0.15,
            }
        )

        return counters

    def _define_invalidation(
        self,
        observation: ObservationOutput,
        hypothesis: HypothesisOutput,
    ) -> list[str]:
        """Define specific, observable conditions that would invalidate our hypothesis."""
        conditions = []

        # Data-driven invalidation
        conditions.append(
            "If the next 2-3 data releases consistently contradict "
            "the current trend direction, the hypothesis should be revisited."
        )

        # Policy-driven invalidation
        conditions.append(
            "If the central bank explicitly signals a different path than "
            "what our hypothesis assumes, conviction must be reduced."
        )

        # Market-driven invalidation
        conditions.append(
            "If key market indicators (yield curve, credit spreads, VIX) "
            "move in the opposite direction from what our hypothesis implies, "
            "this is an early warning."
        )

        # Time-based invalidation
        conditions.append(
            "If the predicted outcomes do not materialize within the expected "
            "timeframe (allowing for a 50% buffer), the hypothesis has failed."
        )

        return conditions

    def _explain_preference(
        self,
        output: CounterOutput,
        evidence: EvidenceOutput,
        hypothesis: HypothesisOutput,
    ) -> str:
        """Explain why, despite counterarguments, we still prefer our hypothesis."""
        net = evidence.net_weight
        confident = hypothesis.hypothesis_confidence

        if net > 0.3 and confident > 0.7:
            return (
                "Despite valid counterarguments, the evidence base strongly supports "
                "our primary hypothesis. The identified risks are monitored but do not "
                "reach the threshold to overturn our central case. We maintain our view "
                "with the stated invalidation conditions as our exit criteria."
            )
        elif net > 0:
            return (
                "We acknowledge meaningful counterarguments, particularly regarding "
                f"{output.most_concerning_counter[:80]}... However, the balance of "
                "evidence continues to favor our central case. Position sizing should "
                "reflect this uncertainty."
            )
        else:
            return (
                "Evidence is conflicted and counterarguments are strong. "
                "We hold our hypothesis as a working framework but with low conviction. "
                "This is a high-uncertainty environment where thesis maintenance requires "
                "continuous validation against incoming data."
            )

    def _generate_trace(self, output: CounterOutput) -> str:
        """Generate reasoning trace."""
        trace = []
        trace.append("=== Stage 6: Counter ===")
        trace.append(f"Counterarguments: {len(output.counter_arguments)}")
        trace.append(f"Most concerning: {output.most_concerning_counter[:80]}...")
        trace.append(f"Invalidation conditions: {len(output.invalidation_conditions)}")
        fatal_count = sum(1 for c in output.counter_arguments if c.get("severity") == "fatal")
        trace.append(f"Fatal counters: {fatal_count}")
        return "\n".join(trace)
