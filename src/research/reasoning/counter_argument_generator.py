"""CounterArgumentGenerator — Produce structured falsification arguments.

Quality principle: Professional researchers argue against themselves.
Every hypothesis MUST have a counter-argument. This is what separates
institutional research from echo-chamber analysis.

For each hypothesis, generates:
    1. Why the hypothesis could be wrong
    2. What the market is missing
    3. Trigger conditions for the counter-case
    4. Historical precedent for the counter-case
    5. Severity (fatal / major / minor)
"""

from __future__ import annotations

import uuid

from src.research.reasoning.schemas import CounterArgument, Hypothesis


class CounterArgumentGenerator:
    """Generate counter-arguments for each hypothesis.

    The goal: force the research to confront what could go wrong.
    """

    # Framework: Dalio-style "what don't I see?" questions
    COUNTER_FRAMEWORKS = {
        "growth_momentum": [
            "Are leading indicators giving false positives due to statistical noise?",
            "Is consumer spending masking underlying business investment weakness?",
            "Could inventory restocking be misinterpreted as final demand?",
            "Is growth merely a base-effect recovery, not structural expansion?",
        ],
        "inflation_dynamics": [
            "Is disinflation concentrated in goods while services remain sticky?",
            "Could shelter/OER measurement lags mask true inflation?",
            "Are commodity price declines temporary and reversing?",
            "Is deglobalization structurally inflationary despite cyclical easing?",
        ],
        "labor_market": [
            "Could declining participation mask genuine labor weakness?",
            "Is wage growth sustainable or pulling forward from future gains?",
            "Are gig-economy workers counted accurately in employment data?",
            "Could immigration restrictions create artificial tightness?",
        ],
        "monetary_policy": [
            "Is the market pricing the wrong terminal rate?",
            "Could fiscal dominance force the central bank into a corner?",
            "Are financial conditions indices distorted by equity valuations?",
            "Does the long-and-variable-lag problem make policy timing impossible?",
        ],
        "capital_flows": [
            "Are flows driven by mechanical rebalancing rather than conviction?",
            "Could crowded positioning create a sharp reversal risk?",
            "Is the flow data lagged, reflecting last week's not today's positioning?",
            "Are retail flows counter-signaling institutional distribution?",
        ],
        "credit_conditions": [
            "Is credit tightening concentrated in CRE while other sectors are fine?",
            "Could shadow banking growth offset traditional bank tightening?",
            "Are default fears priced or still ahead of us?",
        ],
        "currency_markets": [
            "Is dollar strength driven by rate differentials or safe-haven flows?",
            "Could intervention risk cap further moves?",
            "Is carry trade positioning excessively crowded?",
        ],
    }

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def generate(
        self,
        hypotheses: list[Hypothesis],
        evidence_clusters: list = None,
        regime_result: dict | None = None,
    ) -> tuple[list[CounterArgument], list[str], dict[str, str]]:
        """Generate counter-arguments for ALL hypotheses AND eliminate weak ones.

        Returns:
            counters: list of CounterArgument objects
            eliminated_ids: list of hypothesis_ids that should be eliminated
            elimination_reasons: dict of {hypothesis_id: reason_why_eliminated}

        Elimination rules:
            - Any hypothesis with a "fatal" counter (probability > 0.5) is eliminated.
            - If no fatal counter is found but we have 2+ hypotheses, the weakest
              (lowest confidence * evidence_weight) is eliminated.
            - At least 1 weak hypothesis is always eliminated when count > 1.
        """
        counters = []
        eliminated_ids: list[str] = []
        elimination_reasons: dict[str, str] = {}

        for hyp in hypotheses:
            c = self._counter_for_hypothesis(hyp, regime_result)
            if c:
                counters.append(c)

        # ── Elimination logic ──
        # Rule 1: Fatal counters → eliminate immediately
        for c in counters:
            if c.severity == "fatal" and c.probability > 0.5:
                eliminated_ids.append(c.target_hypothesis_id)
                elimination_reasons[c.target_hypothesis_id] = (
                    f"Fatal counter-argument (probability {c.probability:.0%}): {c.title}"
                )

        # Rule 2: If no fatal elimination and we have 2+ hypotheses, eliminate the weakest
        if not eliminated_ids and len(hypotheses) > 1:
            # Compute a composite weakness score (lower = weaker)
            weakest_hyp = min(
                hypotheses,
                key=lambda h: (
                    h.confidence * max(h.evidence_weight, 0.01) * 0.5 + (1 - h.confidence) * 0.5
                ),
            )
            eliminated_ids.append(weakest_hyp.hypothesis_id)
            elimination_reasons[weakest_hyp.hypothesis_id] = (
                f"Weakest hypothesis eliminated: confidence={weakest_hyp.confidence:.0%}, "
                f"evidence_weight={weakest_hyp.evidence_weight:.2f}, "
                f"domain={weakest_hyp.domain}"
            )

        return counters, eliminated_ids, elimination_reasons

    def generate_for_hypothesis(
        self, hypothesis: Hypothesis, regime_result: dict | None = None
    ) -> CounterArgument:
        """Generate a counter-argument for a single hypothesis."""
        return self._counter_for_hypothesis(hypothesis, regime_result)

    # ── Internal ──

    def _counter_for_hypothesis(self, hyp: Hypothesis, regime: dict | None) -> CounterArgument:
        c_id = f"COUNTER_{str(uuid.uuid4())[:8]}"

        # Get domain-specific counter questions
        questions = self.COUNTER_FRAMEWORKS.get(
            hyp.domain,
            self.COUNTER_FRAMEWORKS.get("growth_momentum", []),
        )

        # Select relevant counter based on hypothesis confidence
        if hyp.confidence > 0.7:
            # High confidence → need strongest counter
            counter_questions = questions[:2]
            severity = "major" if hyp.confidence > 0.8 else "major"
        elif hyp.confidence > 0.5:
            counter_questions = questions[1:3]
            severity = "major"
        else:
            counter_questions = questions[-2:]
            severity = "minor"

        # Build the counter argument
        counter_evidence = []
        for item in hyp.contradicting_evidence[:3]:
            counter_evidence.append(
                {
                    "description": item.get("description", "Contradicting signal"),
                    "source": item.get("source", "evidence_cluster"),
                    "strength": item.get("strength", 0.5),
                }
            )

        # If no contradicting evidence in hypothesis, generate from framework
        if not counter_evidence:
            for q in questions[:2]:
                counter_evidence.append(
                    {
                        "description": q,
                        "source": "counter_framework",
                        "strength": 0.3,
                    }
                )

        # Build the argument text
        argument = self._build_argument(hyp, counter_questions, severity)

        # Title
        title = f"Counter: {hyp.title}"

        # Why the hypothesis could be wrong
        why_wrong = self._why_wrong(hyp, counter_questions)

        # What the market is missing
        what_missing = self._what_missing(hyp)

        # Trigger conditions
        triggers = self._extract_triggers(hyp, counter_questions)

        # Historical precedent
        precedent = self._find_precedent(hyp)

        return CounterArgument(
            counter_id=c_id,
            target_hypothesis_id=hyp.hypothesis_id,
            title=title,
            argument=argument,
            probability=round(1 - hyp.confidence, 2),
            severity=severity,
            why_the_hypothesis_could_be_wrong=why_wrong,
            what_the_market_is_missing=what_missing,
            counter_evidence=counter_evidence,
            trigger_conditions=triggers,
            historical_precedent=precedent,
        )

    def _build_argument(self, hyp, questions, severity):
        """Build the full counter-argument text."""
        parts = [f"The hypothesis that '{hyp.title}' may be incorrect for the following reasons:"]
        for i, q in enumerate(questions[:2]):
            parts.append(f"{i + 1}. {q}")
        if severity == "fatal":
            parts.append(
                "This counter-argument, if realized, would fundamentally invalidate the hypothesis."
            )
        elif severity == "major":
            parts.append(
                "These questions represent material risks to the hypothesis, though not fatal ones."
            )
        else:
            parts.append(
                "These are minor concerns that should be monitored but do not threaten the core thesis."
            )
        return "\n\n".join(parts)

    def _why_wrong(self, hyp, questions):
        """Explain why the hypothesis could be wrong."""
        reasons = []
        base = f"The {hyp.domain.replace('_', ' ')} data may be misleading because:"
        reasons.append(base)
        for q in questions[:2]:
            reasons.append(f"- {q}")
        if hyp.evidence_weight < 0.3:
            reasons.append("- Evidence weight is low, increasing model risk")
        if hyp.confidence < 0.5:
            reasons.append("- Confidence is below 50%, suggesting internal signal weakness")
        return "\n".join(reasons)

    def _what_missing(self, hyp):
        """What the market/consensus might be missing about this counter."""
        misses = {
            "growth_momentum": "The market may be over-extrapolating recent strength and ignoring mean-reversion dynamics in the business cycle.",
            "inflation_dynamics": "Markets tend to price the last 3 months of data, not the structural shift in inflation regime that may be underway.",
            "labor_market": "Headline payroll numbers mask compositional shifts — quality of jobs matters as much as quantity.",
            "monetary_policy": "Markets consistently underestimate the long-and-variable-lag problem in monetary transmission.",
            "capital_flows": "Flow-following is the most consensus strategy — consensus has a poor track record at turning points.",
            "macro_regime": "Historical analogs are imperfect guides — structural differences always exist.",
        }
        return misses.get(
            hyp.domain,
            f"The consensus view on {hyp.domain} may overlook structural changes that invalidate the base case.",
        )

    def _extract_triggers(self, hyp, questions):
        """Extract or generate trigger conditions."""
        triggers = []
        # Use existing falsification conditions
        for fc in hyp.falsification_conditions[:2]:
            triggers.append(fc.get("condition", ""))
        # If not enough, add generic ones
        while len(triggers) < 2:
            triggers.append(
                f"If data on {hyp.domain} reverses, the counter-case becomes the base case"
            )
        return triggers[:3]

    def _find_precedent(self, hyp):
        """Find historical precedent for the counter-argument."""
        precedents = {
            "growth_momentum": "2011: Post-GFC recovery was widely believed durable, then sovereign debt crisis triggered double-dip fears.",
            "inflation_dynamics": "1970s: Inflation was repeatedly declared 'transitory' over a decade of structural price increases.",
            "labor_market": "2019: Record-low unemployment masked growing gig-economy precarity and wage stagnation for bottom quintiles.",
            "monetary_policy": "2008: Markets priced 50bp of additional hikes in summer 2008 — actual path was zero rates and QE.",
            "capital_flows": "2022: Record ETF inflows into tech in 2021 were followed by the sharpest drawdown in a decade.",
            "credit_conditions": "2007: Credit markets showed no stress in Q1 2007, three months before the Bear Stearns hedge fund blowup.",
            "macro_regime": "2018 Q4: Powell pivot from 'a long way from neutral' to 'just below neutral' in 6 weeks — regime shifts can be abrupt.",
        }
        return precedents.get(
            hyp.domain, "Historical precedent exists for abrupt reversals in consensus macro views."
        )
