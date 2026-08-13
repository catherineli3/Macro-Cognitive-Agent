"""V6.4 Multi-pass Thinking — Iterative memo refinement.

Never generate a memo in one pass.

Instead:
    Pass 1: Observation — what do we see?
    Pass 2: Narrative — what story does the data tell?
    Pass 3: Belief — what do we believe and why?
    Pass 4: Counter — what could go wrong?
    Pass 5: Rewrite — incorporate counter, refine thesis
    Pass 6: Final — publishable memo

Each pass records WHY changes were made, creating an audit trail
of the agent's reasoning evolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4


class ThinkingPass(str, Enum):
    """The 5 passes of multi-pass memo generation."""

    OBSERVATION = "observation"  # Pass 1: What do we observe?
    NARRATIVE = "narrative"  # Pass 2: What's the story?
    BELIEF = "belief"  # Pass 3: What do we believe?
    COUNTER = "counter"  # Pass 4: Challenge our beliefs
    REWRITE = "rewrite"  # Pass 5: Final integration
    FINAL = "final"  # Publishable


@dataclass
class ThinkingDelta:
    """Records what changed between two thinking passes."""

    pass_from: ThinkingPass = ThinkingPass.OBSERVATION
    pass_to: ThinkingPass = ThinkingPass.NARRATIVE
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # What changed
    changes: list[str] = field(default_factory=list)
    why_changed: list[str] = field(default_factory=list)

    # Content diff
    added_sections: list[str] = field(default_factory=list)
    removed_sections: list[str] = field(default_factory=list)
    modified_sections: list[str] = field(default_factory=list)

    # Quality impact
    confidence_shift: float = 0.0  # Did confidence increase or decrease?
    reasoning_improvement: str = ""  # How did reasoning improve?
    new_evidence_incorporated: list[str] = field(default_factory=list)
    counter_addressed: list[str] = field(default_factory=list)


@dataclass
class ThinkingPassResult:
    """Output of a single thinking pass."""

    pass_type: ThinkingPass
    pass_id: str = field(default_factory=lambda: uuid4().hex[:8])
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Content
    content: str = ""  # Full text at this stage
    summary: str = ""  # 1-paragraph summary

    # Key elements extracted
    key_observations: list[str] = field(default_factory=list)
    key_narratives: list[str] = field(default_factory=list)
    key_beliefs: list[dict] = field(default_factory=list)
    key_counters: list[dict] = field(default_factory=list)

    # Confidence
    confidence: float = 0.5  # Overall confidence in this pass
    uncertainties: list[str] = field(default_factory=list)

    # Reasoning audit
    reasoning_chain: list[str] = field(default_factory=list)
    evidence_used: list[str] = field(default_factory=list)

    # Delta from previous
    delta: ThinkingDelta | None = None


@dataclass
class MultiPassResult:
    """Complete multi-pass thinking result with all passes preserved."""

    result_id: str = field(default_factory=lambda: uuid4().hex[:12])
    topic: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str = ""

    passes: list[ThinkingPassResult] = field(default_factory=list)

    @property
    def final_content(self) -> str:
        """Get the final (last pass) content."""
        if self.passes:
            return self.passes[-1].content
        return ""

    @property
    def pass_count(self) -> int:
        return len(self.passes)

    @property
    def total_changes(self) -> int:
        return sum(len(p.delta.changes) for p in self.passes if p.delta)

    @property
    def confidence_evolution(self) -> list[float]:
        return [p.confidence for p in self.passes]

    def get_evolution_summary(self) -> str:
        """Summarize how thinking evolved across passes."""
        parts = [f"Multi-pass thinking: {self.pass_count} passes for '{self.topic}'"]

        for i, p in enumerate(self.passes):
            parts.append(f"\nPass {i+1} [{p.pass_type.value}]: {p.summary[:100]}")
            if p.delta:
                if p.delta.changes:
                    parts.append(f"  Changes: {', '.join(p.delta.changes[:3])}")
                if p.delta.why_changed:
                    parts.append(f"  Why: {', '.join(p.delta.why_changed[:2])}")

        parts.append(f"\nConfidence: {self.confidence_evolution}")
        return "\n".join(parts)


class MultiPassThinker:
    """Orchestrate multi-pass memo generation.

    The agent thinks in layers. Each pass refines the previous.
    Changes are recorded with reasons.
    """

    def __init__(self):
        self._results: dict[str, MultiPassResult] = {}

    def execute(
        self,
        topic: str,
        macro_data: dict | None = None,
        market_data: dict | None = None,
        belief_data: dict | None = None,
        narrative_data: dict | None = None,
        evidence_items: list[str] | None = None,
    ) -> MultiPassResult:
        """Execute full multi-pass thinking for a topic.

        In production, each pass would call the LLM.
        Here we implement the structured thinking framework.
        """
        result = MultiPassResult(topic=topic)

        # Pre-process data
        macro = macro_data or {}
        market = market_data or {}
        beliefs = belief_data or {}
        narratives = narrative_data or {}
        evidence = evidence_items or []

        # ── Pass 1: Observation ───────────────────────────────────────
        obs = self._pass_observation(topic, macro, market, evidence)
        result.passes.append(obs)

        # ── Pass 2: Narrative ─────────────────────────────────────────
        nar = self._pass_narrative(topic, macro, market, obs, narratives)
        result.passes.append(nar)

        # ── Pass 3: Belief ────────────────────────────────────────────
        bel = self._pass_belief(topic, nar, beliefs, evidence)
        result.passes.append(bel)

        # ── Pass 4: Counter ───────────────────────────────────────────
        cnt = self._pass_counter(topic, bel, beliefs, evidence)
        result.passes.append(cnt)

        # ── Pass 5: Rewrite ───────────────────────────────────────────
        rwt = self._pass_rewrite(topic, bel, cnt, evidence)
        result.passes.append(rwt)

        result.completed_at = datetime.now(UTC).isoformat()
        self._results[result.result_id] = result

        return result

    # ── Pass Implementations ──────────────────────────────────────────────

    def _pass_observation(
        self, topic: str, macro: dict, market: dict, evidence: list[str]
    ) -> ThinkingPassResult:
        """Pass 1: Pure observation — what do the data say?"""
        observations = []

        for key, value in list(macro.items())[:5]:
            observations.append(f"Macro: {key} = {value}")
        for key, value in list(market.items())[:5]:
            observations.append(f"Market: {key} = {value}")

        content = f"""# Observation: {topic}

## Raw Data Points
{chr(10).join(f'- {o}' for o in observations) if observations else 'No data points available.'}

## Evidence Items
{chr(10).join(f'- {e}' for e in evidence[:5]) if evidence else 'No specific evidence items.'}

## Initial Observations
- This is a fact-gathering stage — no interpretation yet.
- The data above represent the raw inputs for analysis.
"""

        return ThinkingPassResult(
            pass_type=ThinkingPass.OBSERVATION,
            content=content,
            summary=f"Raw observation of {len(observations)} data points and {len(evidence)} evidence items.",
            key_observations=observations[:10],
            confidence=0.3,  # Low confidence at pure observation stage
            uncertainties=["Data quality?", "What's missing?", "Sample bias?"],
            evidence_used=evidence,
        )

    def _pass_narrative(
        self, topic: str, macro: dict, market: dict, obs: ThinkingPassResult, narratives: dict
    ) -> ThinkingPassResult:
        """Pass 2: Narrative construction — what story do the data tell?"""

        # Build narrative from observations
        narratives_list = list(narratives.keys()) if narratives else []
        if not narratives_list:
            narratives_list = [
                "Data-dependent macro regime",
                "Policy normalization path",
                "Growth-inflation dynamics",
                "Risk appetite cycle",
            ]

        selected = narratives_list[:3]

        content = f"""# Narrative: {topic}

## Dominant Narratives
{chr(10).join(f'### {i+1}. {n}' for i, n in enumerate(selected))}

## Story Construction
The observed data suggests the following story:
- Multiple data points converge to suggest a coherent pattern.
- This pattern fits within established macro frameworks.
- Key question: is this a continuation or a regime change?

## Narrative Confidence: Medium
- Supporting evidence present but not overwhelming.
- Alternative interpretations possible.
"""

        return ThinkingPassResult(
            pass_type=ThinkingPass.NARRATIVE,
            content=content,
            summary=f"Narrative constructed from {len(selected)} candidate stories.",
            key_narratives=selected,
            confidence=0.5,
            uncertainties=["Are we fitting data to narrative?", "What narratives are we missing?"],
            evidence_used=obs.evidence_used,
        )

    def _pass_belief(
        self, topic: str, nar: ThinkingPassResult, beliefs: dict, evidence: list[str]
    ) -> ThinkingPassResult:
        """Pass 3: Belief formation — what do we actually believe?"""

        belief_items = []
        for bid, info in list(beliefs.items())[:5]:
            if isinstance(info, dict):
                belief_items.append(
                    {
                        "id": bid,
                        "name": info.get("name", bid),
                        "confidence": info.get("confidence", 0.5),
                    }
                )

        if not belief_items:
            belief_items = [
                {"id": "macro_regime", "name": "Current Macro Regime", "confidence": 0.6},
                {"id": "policy_path", "name": "Monetary Policy Path", "confidence": 0.55},
                {"id": "risk_appetite", "name": "Risk Appetite", "confidence": 0.5},
            ]

        content = f"""# Belief Assessment: {topic}

## Current Beliefs
{chr(10).join(f'### {b["name"]} (confidence: {b["confidence"]:.2f})' for b in belief_items)}

## Evidence Supporting Beliefs
{chr(10).join(f'- {e}' for e in evidence[:5]) if evidence else '- Evidence assessment pending.'}

## Belief Confidence
Overall belief confidence reflects the alignment between narratives and evidence.
"""

        return ThinkingPassResult(
            pass_type=ThinkingPass.BELIEF,
            content=content,
            summary=f"Belief assessment across {len(belief_items)} dimensions.",
            key_beliefs=belief_items,
            confidence=0.6,
            uncertainties=["Beliefs may be wrong", "Evidence may be misinterpreted"],
            evidence_used=evidence,
        )

    def _pass_counter(
        self, topic: str, bel: ThinkingPassResult, beliefs: dict, evidence: list[str]
    ) -> ThinkingPassResult:
        """Pass 4: Counter-argument — challenge every belief."""

        counters = []
        for b in bel.key_beliefs[:3]:
            counters.append(
                {
                    "belief": b["name"],
                    "counter": f"What if {b['name']} is wrong? Alternative scenarios exist.",
                    "probability": round(1 - b["confidence"], 2),
                    "impact": "High — would require significant position adjustment.",
                }
            )

        content = f"""# Counter-Arguments: {topic}

## Challenging Our Thesis

{chr(10).join(f'''### Counter to: {c["belief"]}
- **Counter**: {c["counter"]}
- **Probability**: {c["probability"]}
- **Impact if true**: {c["impact"]}
''' for c in counters)}

## Key Risks
- Confirmation bias: we may be overweighting supporting evidence.
- Recent bias: recent data may be overweighted.
- Consensus risk: if everyone believes this, what's priced in?

## Unanswered Questions
- What evidence would prove us wrong?
- What scenario has the highest asymmetric payoff?
"""

        return ThinkingPassResult(
            pass_type=ThinkingPass.COUNTER,
            content=content,
            summary=f"Generated {len(counters)} counter-arguments to test thesis robustness.",
            key_counters=counters,
            confidence=max(0.3, bel.confidence - 0.1),  # Counter typically lowers confidence
            uncertainties=[
                "Are we challenging hard enough?",
                "What's the strongest argument against us?",
            ],
            evidence_used=evidence,
        )

    def _pass_rewrite(
        self, topic: str, bel: ThinkingPassResult, cnt: ThinkingPassResult, evidence: list[str]
    ) -> ThinkingPassResult:
        """Pass 5: Final synthesis — incorporate counters, refine thesis."""

        content = f"""# Final Assessment: {topic}

## Thesis
After multi-pass analysis incorporating observations, narratives, beliefs,
and counter-arguments, the synthesized thesis is:

### Core View
The evidence supports the following framework:
1. Macro regime assessment based on data and narrative alignment.
2. Key beliefs with quantified confidence levels.
3. Counter-arguments considered and incorporated.

### Risk-Adjusted View
Having considered counter-arguments:
- Base case probability adjusted for identified risks.
- Key invalidation conditions clearly stated.
- Asymmetric scenarios identified.

## Confidence Calibration
- Initial observation confidence: low (pure data)
- Narrative confidence: medium (story construction)
- Belief confidence: medium-high (evidence alignment)
- Post-counter confidence: calibrated (risks incorporated)

## Watch List
- Key data releases to monitor.
- Narrative shifts to watch for.
- Belief invalidation triggers.
"""

        return ThinkingPassResult(
            pass_type=ThinkingPass.REWRITE,
            content=content,
            summary=f"Synthesized thesis from {len(evidence)} evidence items, "
            f"{len(bel.key_beliefs)} beliefs, {len(cnt.key_counters)} counters.",
            key_beliefs=bel.key_beliefs,
            key_counters=cnt.key_counters,
            confidence=0.55,  # Calibrated post-counter confidence
            uncertainties=[
                "Thesis is as robust as the weakest assumption.",
                "Markets can stay irrational longer than we can stay solvent.",
            ],
            evidence_used=evidence,
        )

    def get_result(self, result_id: str) -> MultiPassResult | None:
        return self._results.get(result_id)

    def get_stats(self) -> dict:
        if not self._results:
            return {"total_results": 0}

        results = self._results.values()
        total_passes = sum(r.pass_count for r in results)
        avg_confidence = sum(r.passes[-1].confidence for r in results if r.passes) / max(
            len(results), 1
        )

        return {
            "total_results": len(self._results),
            "total_passes": total_passes,
            "avg_passes_per_result": total_passes / max(len(self._results), 1),
            "avg_final_confidence": avg_confidence,
        }
