"""MacroReasoner — The V4 reasoning orchestrator.

Core function: Observation → Evidence clustering → Hypothesis → Counter →
    Confidence calibration → Investment implication → Research memo.

This is NOT a template engine. LLM performs the reasoning, informed by:
    - Structured evidence from EvidenceSynthesizer
    - Causal hypotheses from HypothesisBuilder
    - Falsification from CounterArgumentGenerator
    - Professional writing from MemoWriter

Quality principle: Every output must be traceable to specific evidence.
No floating claims, no unreferenced assertions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from src.research.reasoning.counter_argument_generator import CounterArgumentGenerator
from src.research.reasoning.evidence_synthesizer import EvidenceSynthesizer
from src.research.reasoning.hypothesis_builder import HypothesisBuilder
from src.research.reasoning.memo_writer import MemoWriter
from src.research.reasoning.schemas import (
    CounterArgument,
    EvidenceAssessment,
    Hypothesis,
    ReasoningChain,
    ResearchMemo,
)


class MacroReasoner:
    """Orchestrate the full V4 reasoning pipeline.

    Input: Macro context (market data, narratives, beliefs, regime,
           capital flows, news)
    Process: 7-step reasoning chain
    Output: Professional ResearchMemo

    The pipeline:
        1. Extract evidence from all sources
        2. Cluster evidence by theme
        3. Generate causal hypotheses
        4. Generate counter-arguments
        5. Calibrate confidence
        6. Derive investment implications
        7. Write professional research memo
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.synthesizer = EvidenceSynthesizer(config)
        self.hypothesis_builder = HypothesisBuilder(config)
        self.counter_generator = CounterArgumentGenerator(config)
        self.memo_writer = MemoWriter(config)

    def reason(
        self,
        market_data: dict,
        narratives: list = None,
        beliefs: list = None,
        regime_result: dict | None = None,
        capital_flow_result: dict | None = None,
        news_events: list | None = None,
        date_str: str | None = None,
    ) -> ResearchMemo:
        """Execute the full reasoning pipeline.

        This is the primary V4 API. Everything flows through here.

        Args:
            market_data: Market data with signals and prices
            narratives: Active market narratives
            beliefs: Active research beliefs
            regime_result: Current regime classification
            capital_flow_result: Capital flow analysis
            news_events: News/research events
            date_str: Date string for memo

        Returns:
            ResearchMemo — the final institutional research memo
        """
        narratives = narratives or []
        beliefs = beliefs or []
        date_str = date_str or datetime.now(UTC).strftime("%Y-%m-%d")

        # ── Step 1: Evidence Synthesis ──
        evidence_assessment = self.synthesizer.synthesize(
            market_data=market_data,
            narratives=narratives,
            beliefs=beliefs,
            capital_flow_result=capital_flow_result,
            regime_result=regime_result,
            news_events=news_events,
        )

        # ── Step 2: Hypothesis Generation ──
        hypotheses = self.hypothesis_builder.build_hypotheses(
            evidence_clusters=evidence_assessment.clusters,
            beliefs=beliefs,
            regime_result=regime_result,
            narrative=self._extract_narrative_text(narratives),
        )

        # ── Step 3: Counter-Argument Generation ──
        counter_arguments = self.counter_generator.generate(
            hypotheses=hypotheses,
            evidence_clusters=evidence_assessment.clusters,
            regime_result=regime_result,
        )

        # ── Step 4: Confidence Calibration ──
        hypotheses = self._calibrate_confidence(hypotheses, counter_arguments, evidence_assessment)

        # ── Step 5: Reasoning Chain ──
        _chain = self._build_reasoning_chain(evidence_assessment, hypotheses, counter_arguments)

        # ── Step 6: Write Research Memo ──
        memo = self.memo_writer.write_memo(
            evidence_assessment=evidence_assessment,
            hypotheses=hypotheses,
            counter_arguments=counter_arguments,
            regime_result=regime_result,
            beliefs=beliefs,
            capital_flow_result=capital_flow_result,
            narrative=self._extract_narrative_text(narratives),
            date_str=date_str,
        )

        return memo

    def reason_quick(
        self,
        market_data: dict,
        beliefs: list = None,
        regime_result: dict | None = None,
    ) -> ResearchMemo:
        """Fast reasoning with only essential inputs.

        For when you want a quick research memo without full pipeline.
        """
        return self.reason(
            market_data=market_data,
            narratives=[],
            beliefs=beliefs or [],
            regime_result=regime_result,
            capital_flow_result=None,
            news_events=None,
        )

    def reason_with_news(
        self,
        market_data: dict,
        news_events: list,
        beliefs: list = None,
        regime_result: dict | None = None,
    ) -> ResearchMemo:
        """Reasoning with news integration as primary input."""
        return self.reason(
            market_data=market_data,
            narratives=[],
            beliefs=beliefs or [],
            regime_result=regime_result,
            capital_flow_result=None,
            news_events=news_events,
        )

    # ── Internal Methods ──

    def _calibrate_confidence(
        self,
        hypotheses: list[Hypothesis],
        counter_arguments: list[CounterArgument],
        evidence: EvidenceAssessment,
    ) -> list[Hypothesis]:
        """Calibrate hypothesis confidence after counter-argument review.

        Counter-arguments should reduce confidence proportionally
        to their severity and probability.
        """
        ca_map = {ca.target_hypothesis_id: ca for ca in counter_arguments}

        for hyp in hypotheses:
            ca = ca_map.get(hyp.hypothesis_id)
            if not ca:
                continue

            # Severity discount
            severity_map = {"fatal": 0.4, "major": 0.7, "minor": 0.9}
            severity_discount = severity_map.get(ca.severity, 0.8)

            # If confidence is very high and counter has counter-evidence,
            # discount less; if no counter-evidence against the counter, discount more
            if ca.counter_evidence:
                # Counter has its own supporting evidence
                severity_discount *= 0.8

            # Adjust
            hyp.confidence = round(hyp.confidence * severity_discount, 2)

            # Update confidence breakdown
            if hasattr(hyp, "confidence_breakdown") and hyp.confidence_breakdown:
                for key in hyp.confidence_breakdown:
                    hyp.confidence_breakdown[key] = round(
                        hyp.confidence_breakdown[key] * severity_discount, 2
                    )

        return hypotheses

    def _build_reasoning_chain(
        self,
        evidence: EvidenceAssessment,
        hypotheses: list[Hypothesis],
        counters: list[CounterArgument],
    ) -> ReasoningChain:
        """Build the traceable reasoning chain."""
        observations = []
        for c in evidence.clusters[:5]:
            observations.append(f"{c.theme}: {c.net_direction} (weight: {c.weight_score:.2f})")

        inferences = []
        for hyp in hypotheses[:3]:
            if hyp.causal_chain:
                inferences.append(hyp.causal_chain[0])

        deductions = []
        for hyp in hypotheses[:3]:
            if len(hyp.causal_chain) > 1:
                deductions.append(hyp.causal_chain[-1])

        conclusions = [hyp.statement[:100] for hyp in hypotheses[:3]]

        assumptions = []
        for hyp in hypotheses[:3]:
            assumptions.extend(hyp.key_assumptions[:1])

        weakest = []
        for hyp in hypotheses:
            if hyp.confidence < 0.5:
                weakest.append(f"{hyp.title} (confidence: {hyp.confidence:.0%})")

        # Logic strength based on evidence quality and counter coverage
        quality_map = {"high": 0.8, "moderate": 0.6, "low": 0.4, "insufficient": 0.2}
        logic = quality_map.get(evidence.evidence_quality, 0.5)
        if counters:
            logic *= 0.9  # Discount slightly for having identified counters

        return ReasoningChain(
            chain_id=f"CHAIN_{str(uuid.uuid4())[:8]}",
            observations=observations,
            inferences=inferences,
            deductions=deductions,
            conclusions=conclusions,
            explicit_assumptions=assumptions,
            implicit_assumptions=["Markets are not perfectly efficient in the short run"],
            weakest_links=weakest[:3] if weakest else ["All hypotheses above 50% confidence"],
            overall_logic_strength=round(logic, 2),
            weakest_link_probability=min(h.confidence for h in hypotheses) if hypotheses else 0.5,
        )

    @staticmethod
    def _extract_narrative_text(narratives: list) -> str | None:
        """Extract dominant narrative text from narrative objects."""
        for n in narratives:
            nd = n if isinstance(n, dict) else n.to_dict() if hasattr(n, "to_dict") else {}
            text = nd.get("content") or nd.get("summary") or nd.get("name") or ""
            if text:
                return text
        return None
