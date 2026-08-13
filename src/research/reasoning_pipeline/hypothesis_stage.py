"""V5.2 Stage 5: Hypothesis — Form causal hypotheses based on evidence.

This is the core intellectual act of macro research:
    "Given what we observe, what is the causal mechanism driving outcomes?"

Key discipline:
    - Not just "X correlates with Y"
    - Must explain WHY — the causal chain
    - Must acknowledge alternative hypotheses
    - Must explain why we prefer our hypothesis over alternatives
"""

from __future__ import annotations

from datetime import datetime

from src.research.reasoning_pipeline.schemas import (
    AnalogyOutput,
    EvidenceOutput,
    HypothesisOutput,
    ObservationOutput,
    PatternOutput,
    StageStatus,
)


class HypothesisStage:
    """Stage 5: Causal hypothesis generation."""

    CAUSAL_FRAMEWORKS = [
        "monetary_policy_transmission",  # Rate changes → financial conditions → economy
        "fiscal_dominance",  # Fiscal expansion drives inflation/growth
        "credit_cycle",  # Credit expansion → asset boom → credit contraction → bust
        "balance_sheet_recession",  # Private sector deleveraging → persistent weak demand
        "supply_side_shock",  # Supply disruption → stagflation or disinflation
        "liquidity_driven",  # Central bank liquidity → asset prices
        "expectations_channel",  # Forward guidance → market pricing
        "portfolio_balance_channel",  # QE → portfolio rebalancing → risk assets
        "exchange_rate_channel",  # Currency moves → trade/inflation passthrough
        "wealth_effect",  # Asset prices → consumer spending
        "financial_accelerator",  # Collateral values → credit → spending
        "secular_stagnation",  # Demographics + technology → low r* → policy challenges
    ]

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def execute(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
        pattern: PatternOutput,
        analogy: AnalogyOutput,
        belief_data: dict | None = None,
    ) -> HypothesisOutput:
        """Execute hypothesis generation.

        Args:
            observation: Stage 1
            evidence: Stage 2
            pattern: Stage 3
            analogy: Stage 4
            belief_data: Existing belief states

        Returns:
            HypothesisOutput with primary and alternative hypotheses
        """
        output = HypothesisOutput(
            timestamp=datetime.now().isoformat(),
            status=StageStatus.IN_PROGRESS,
        )

        # 1. Build primary hypothesis
        output.primary_hypothesis = self._build_primary(observation, evidence, pattern, analogy)

        # 2. Identify causal mechanism
        output.causal_mechanism = self._identify_mechanism(evidence, pattern)

        # 3. Build logic chain
        output.logic_chain = self._build_logic_chain(observation, evidence, pattern)

        # 4. Generate alternatives
        output.alternative_hypotheses = self._generate_alternatives(evidence, pattern)

        # 5. Explain preference
        output.preference_rationale = self._explain_preference(output, evidence)

        # 6. Calibrate confidence
        output.hypothesis_confidence = self._calibrate(output, evidence, belief_data)

        # 7. Generate trace
        output.reasoning_trace = self._generate_trace(output)
        output.status = StageStatus.COMPLETED

        return output

    def _build_primary(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
        pattern: PatternOutput,
        analogy: AnalogyOutput,
    ) -> str:
        """Build the primary causal hypothesis."""
        parts = []

        # What regime are we in?
        if pattern.regime_diagnosis:
            parts.append(f"In a {pattern.regime_diagnosis}")

        # What is the primary causal driver?
        dominant_themes = sorted(
            evidence.evidence_clusters.keys(),
            key=lambda k: len(evidence.evidence_clusters[k]),
            reverse=True,
        )
        if dominant_themes:
            top_theme = dominant_themes[0]
            parts.append(f"driven primarily by {top_theme} dynamics")

        # What is the expected outcome?
        if analogy.best_analogy:
            parts.append(f"analogous to {analogy.best_analogy}")

        # Synthesize
        if len(parts) >= 2:
            return ", ".join(parts) + "."
        return "Hypothesis: " + " ".join(parts) + "."

    def _identify_mechanism(
        self,
        evidence: EvidenceOutput,
        pattern: PatternOutput,
    ) -> str:
        """Identify the causal mechanism at work."""
        clusters = evidence.evidence_clusters

        mechanism_scores = {}

        # Monetary policy transmission
        if "monetary_policy" in clusters:
            mechanism_scores["monetary_policy_transmission"] = len(
                clusters["monetary_policy"]
            ) * 2 + len(clusters.get("financial_conditions", []))

        # Credit cycle
        if "credit_markets" in clusters:
            mechanism_scores["credit_cycle"] = len(clusters["credit_markets"]) * 2 + len(
                clusters.get("housing", [])
            )

        # Supply side
        if "commodity_markets" in clusters or "global_trade" in clusters:
            mechanism_scores["supply_side_shock"] = len(
                clusters.get("commodity_markets", [])
            ) + len(clusters.get("global_trade", []))

        # Fiscal dominance
        if "fiscal_policy" in clusters:
            mechanism_scores["fiscal_dominance"] = len(clusters["fiscal_policy"]) * 2

        # Liquidity driven
        if "financial_conditions" in clusters:
            mechanism_scores["liquidity_driven"] = len(clusters["financial_conditions"])

        # Default: expectations channel
        mechanism_scores.setdefault("expectations_channel", 1)

        best = max(mechanism_scores, key=mechanism_scores.get)
        mechanism_descriptions = {
            "monetary_policy_transmission": "Monetary policy transmission — rate changes flowing through financial conditions to the real economy",
            "credit_cycle": "Credit cycle dynamics — credit expansion/contraction driving asset prices and economic activity",
            "supply_side_shock": "Supply-side shock — disruptions in production/supply chains driving price and output dynamics",
            "fiscal_dominance": "Fiscal dominance — government spending/deficits as the primary macro driver",
            "liquidity_driven": "Liquidity-driven — central bank balance sheet and market liquidity as primary drivers",
            "expectations_channel": "Expectations channel — forward guidance and market expectations driving outcomes",
        }
        return mechanism_descriptions.get(best, best)

    def _build_logic_chain(
        self,
        observation: ObservationOutput,
        evidence: EvidenceOutput,
        pattern: PatternOutput,
    ) -> list[str]:
        """Build step-by-step logic chain."""
        chain = []

        # Step 1: What we observe
        if observation.data_surprises:
            chain.append(f"1. Data shows: {'; '.join(observation.data_surprises[:2])}")
        else:
            chain.append("1. Current macro data is in line with expectations")

        # Step 2: What this means for the economy
        if pattern.patterns:
            chain.append(f"2. This is consistent with a {pattern.patterns[0]} environment")

        # Step 3: Policy response
        if "monetary_policy" in evidence.evidence_clusters:
            policy_items = evidence.evidence_clusters["monetary_policy"]
            chain.append(f"3. Policy stance: {'; '.join(policy_items[:2])}")

        # Step 4: Market implications
        if observation.market_moves:
            chain.append(f"4. Markets are pricing: {'; '.join(observation.market_moves[:2])}")

        # Step 5: Expected evolution
        chain.append(
            "5. Forward expectation: This configuration should persist until "
            "a material shift in the underlying drivers occurs"
        )

        return chain

    def _generate_alternatives(
        self,
        evidence: EvidenceOutput,
        pattern: PatternOutput,
    ) -> list[str]:
        """Generate alternative hypotheses."""
        alternatives = []

        # Opposite regime
        if "risk-on" in " ".join(pattern.patterns):
            alternatives.append(
                "Risk-off scenario: Current risk appetite is fragile; "
                "a negative shock could trigger rapid risk aversion"
            )

        if "hawkish" in " ".join(pattern.patterns):
            alternatives.append(
                "Policy pivot scenario: Economic data could deteriorate faster than expected, "
                "forcing central banks to reverse tightening"
            )

        # Structural alternative
        alternatives.append(
            "Structural change scenario: Current patterns may represent a structural break "
            "rather than a cyclical phase, invalidating historical analogies"
        )

        # Consensus alternative
        alternatives.append(
            "Consensus is correct: The market consensus view accurately prices the outlook; "
            "no alpha from contrarian positioning"
        )

        return alternatives[:3]

    def _explain_preference(
        self,
        output: HypothesisOutput,
        evidence: EvidenceOutput,
    ) -> str:
        """Explain why primary hypothesis is preferred over alternatives."""
        supporting = len(evidence.supporting_evidence)
        contradicting = len(evidence.contradicting_evidence)

        if supporting > contradicting * 2:
            return (
                f"Primary hypothesis is strongly supported by evidence "
                f"({supporting} supporting vs {contradicting} contradicting data points). "
                f"Alternative hypotheses lack equivalent evidence backing."
            )
        elif supporting > contradicting:
            return (
                f"Primary hypothesis has moderate evidence support "
                f"({supporting} vs {contradicting}). "
                f"Alternatives are plausible but less consistent with the full evidence set."
            )
        else:
            return (
                "Evidence is mixed; primary hypothesis is preferred based on "
                "causal coherence and historical precedent, but conviction is tempered."
            )

    def _calibrate(
        self,
        output: HypothesisOutput,
        evidence: EvidenceOutput,
        belief_data: dict | None,
    ) -> float:
        """Calibrate hypothesis confidence."""
        base = 0.6

        # Evidence weight adjustment
        base += evidence.net_weight * 0.2

        # Penalty for no alternatives
        if not output.alternative_hypotheses:
            base -= 0.1

        # Penalty for no causal mechanism
        if not output.causal_mechanism:
            base -= 0.15

        return min(max(base, 0.1), 0.9)

    def _generate_trace(self, output: HypothesisOutput) -> str:
        """Generate reasoning trace."""
        trace = []
        trace.append("=== Stage 5: Hypothesis ===")
        trace.append(f"Primary: {output.primary_hypothesis[:100]}...")
        trace.append(f"Mechanism: {output.causal_mechanism}")
        trace.append(f"Logic chain: {len(output.logic_chain)} steps")
        trace.append(f"Alternatives: {len(output.alternative_hypotheses)}")
        trace.append(f"Confidence: {output.hypothesis_confidence:.2f}")
        return "\n".join(trace)
