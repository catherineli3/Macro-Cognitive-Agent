"""V8.4 Self Challenge — The agent challenges its own research.

The agent must automatically ask:
    - Why am I wrong?
    - What's missing from my analysis?
    - What evidence contradicts my thesis?
    - What would Dalio disagree with?
    - What would PTJ trade instead?
    - What would invalidate everything?

After the self-challenge, the agent REWRITES the memo incorporating
the strongest counter-arguments and refined perspectives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


@dataclass
class Challenge:
    """A single challenge to the current thesis."""
    challenge_id: str = field(default_factory=lambda: uuid4().hex[:8])
    question: str = ""                    # The challenging question
    challenger_perspective: str = ""       # Whose perspective?
    answer: str = ""                      # Honest answer
    severity: float = 0.5                # 0–1: how damaging is this challenge?
    is_valid: bool = True                # Is this a real concern?
    evidence_contradicting: list[str] = field(default_factory=list)
    implication: str = ""                # What if this challenge is correct?


@dataclass
class SelfChallengeResult:
    """Complete self-challenge analysis."""
    challenge_id: str = field(default_factory=lambda: uuid4().hex[:8])
    topic: str = ""
    original_thesis: str = ""
    date: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d'))
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # The challenges
    challenges: list[Challenge] = field(default_factory=list)
    
    # Overall assessment
    vulnerability_score: float = 0.0      # 0–100: how vulnerable is the thesis?
    strongest_challenge: str = ""
    strongest_severity: float = 0.0
    
    # Key gaps
    missing_evidence: list[str] = field(default_factory=list)
    blind_spots: list[str] = field(default_factory=list)
    assumptions_unverified: list[str] = field(default_factory=list)
    
    # Investment implications
    if_wrong_impact: str = ""             # What's the P&L impact if wrong?
    hedge_recommendation: str = ""
    
    # Revised thesis
    revised_thesis: str = ""              # After incorporating challenges
    confidence_adjustment: float = 0.0    # How much did confidence change?
    
    def render(self) -> str:
        lines = [
            f"# Self-Challenge Analysis",
            f"**Topic**: {self.topic}",
            f"**Date**: {self.date}",
            "",
            "---",
            "",
            f"## Original Thesis",
            self.original_thesis,
            "",
            f"## Vulnerability Score: {self.vulnerability_score:.0f}/100",
            f"{'⚠️ HIGH VULNERABILITY — thesis needs significant revision' if self.vulnerability_score > 70 else 'Thesis reasonably robust after challenge.'}",
            "",
            "---",
            "",
            "## Challenges",
            "",
        ]
        
        for i, c in enumerate(self.challenges):
            lines.extend([
                f"### Challenge {i+1}: {c.question}",
                f"**Perspective**: {c.challenger_perspective}",
                f"**Severity**: {c.severity:.0%} | **Valid**: {'Yes' if c.is_valid else 'No'}",
                "",
                f"**Honest Answer**: {c.answer}",
                "",
            ])
            if c.evidence_contradicting:
                lines.append(f"**Contradicting Evidence**: {', '.join(c.evidence_contradicting)}")
            if c.implication:
                lines.append(f"**If Correct**: {c.implication}")
            lines.append("")
        
        lines.extend([
            "---",
            "",
            "## Key Gaps Identified",
            "",
        ])
        for g in self.blind_spots:
            lines.append(f"- **Blind Spot**: {g}")
        for a in self.assumptions_unverified:
            lines.append(f"- **Unverified Assumption**: {a}")
        for e in self.missing_evidence:
            lines.append(f"- **Missing Evidence**: {e}")
        
        lines.extend([
            "",
            "## Investment Implications if Wrong",
            self.if_wrong_impact or "No material impact assessed.",
            f"**Hedge**: {self.hedge_recommendation or 'None recommended.'}",
            "",
            "---",
            "",
            "## Revised Thesis",
            self.revised_thesis or self.original_thesis,
            "",
            f"**Confidence Adjustment**: {self.confidence_adjustment:+.0%}",
            "",
            f"**Strongest Challenge**: {self.strongest_challenge} (severity: {self.strongest_severity:.0%})",
            "",
            "---",
            "*Self-Challenge Analysis by Macro Research Agent V8.4*",
        ])
        
        return "\n".join(lines)


class SelfChallenger:
    """Automatically challenge the agent's own research.

    The hardest thing for any analyst: admitting they might be wrong.
    This module forces the agent to confront its own biases, assumptions,
    and blind spots before publishing any research.
    """

    # Standard challenge questions from different perspectives
    CHALLENGE_QUESTIONS = [
        {
            "question": "Why am I wrong?",
            "perspective": "Internal Skeptic",
            "approach": "Honestly list the top 3 reasons this thesis could fail.",
        },
        {
            "question": "What's missing from my analysis?",
            "perspective": "Completeness Check",
            "approach": "Identify data, frameworks, or perspectives not considered.",
        },
        {
            "question": "What evidence contradicts my thesis?",
            "perspective": "Evidence Audit",
            "approach": "Search for data points that point in the opposite direction.",
        },
        {
            "question": "What would Dalio disagree with?",
            "perspective": "Dalio Systematic",
            "approach": "Apply long-term debt cycle and productivity framework.",
        },
        {
            "question": "What would PTJ trade instead?",
            "perspective": "PTJ Macro Trader",
            "approach": "Focus on momentum, positioning, and asymmetric payoff.",
        },
        {
            "question": "What would Soros say about reflexivity here?",
            "perspective": "Soros Reflexivity",
            "approach": "Are market prices affecting fundamentals? Is this a boom-bust?",
        },
        {
            "question": "What would invalidate everything?",
            "perspective": "Null Hypothesis",
            "approach": "What single data point or event would completely reverse the thesis?",
        },
        {
            "question": "Is this just recency bias?",
            "perspective": "Cognitive Bias Check",
            "approach": "Are we overweighting recent data and ignoring long-term trends?",
        },
        {
            "question": "What's the consensus view, and why would it be wrong?",
            "perspective": "Consensus Challenge",
            "approach": "If everyone thinks this, what's the contrarian case?",
        },
        {
            "question": "What scenario has the highest P&L impact?",
            "perspective": "Risk Manager",
            "approach": "Which tail scenario causes the most damage, and is it priced?",
        },
    ]

    def __init__(self):
        self._results: dict[str, SelfChallengeResult] = {}

    def challenge(self, topic: str, thesis: str,
                  evidence: Optional[list[str]] = None,
                  beliefs: Optional[list[dict]] = None,
                  narratives: Optional[list[str]] = None,
                  risks: Optional[list[dict]] = None) -> SelfChallengeResult:
        """Run complete self-challenge on a research thesis."""
        
        result = SelfChallengeResult(
            topic=topic,
            original_thesis=thesis,
        )
        
        # Generate challenges
        for cq in self.CHALLENGE_QUESTIONS:
            challenge = self._generate_challenge(
                cq, thesis, evidence, beliefs, narratives, risks
            )
            result.challenges.append(challenge)
        
        # Assess overall vulnerability
        result.vulnerability_score = self._calculate_vulnerability(result.challenges)
        
        # Find strongest challenge
        strongest = max(result.challenges, key=lambda c: c.severity)
        result.strongest_challenge = strongest.question
        result.strongest_severity = strongest.severity
        
        # Identify gaps
        result.blind_spots = self._identify_blind_spots(result.challenges)
        result.assumptions_unverified = self._identify_assumptions(thesis)
        result.missing_evidence = self._identify_missing_evidence(thesis, evidence)
        
        # Investment implications
        result.if_wrong_impact = self._assess_if_wrong_impact(thesis, result.vulnerability_score)
        result.hedge_recommendation = self._recommend_hedge(result.vulnerability_score)
        
        # Revise thesis
        result.revised_thesis = self._revise_thesis(thesis, result)
        result.confidence_adjustment = -min(result.vulnerability_score / 100 * 0.3, 0.3)
        
        self._results[result.challenge_id] = result
        return result

    def get_result(self, challenge_id: str) -> Optional[SelfChallengeResult]:
        return self._results.get(challenge_id)

    def get_stats(self) -> dict:
        if not self._results:
            return {"total_challenges": 0}
        
        return {
            "total_challenges": len(self._results),
            "avg_vulnerability": (
                sum(r.vulnerability_score for r in self._results.values()) / 
                len(self._results)
            ),
            "avg_confidence_adjustment": (
                sum(r.confidence_adjustment for r in self._results.values()) / 
                len(self._results)
            ),
        }

    # ── Internal ─────────────────────────────────────────────────────────

    def _generate_challenge(self, cq: dict, thesis: str,
                            evidence: Optional[list[str]],
                            beliefs: Optional[list[dict]],
                            narratives: Optional[list[str]],
                            risks: Optional[list[dict]]) -> Challenge:
        """Generate a specific challenge."""
        
        question = cq["question"]
        perspective = cq["perspective"]
        
        # Generate answer based on perspective
        if "Dalio" in perspective:
            answer = (
                f"Dalio would ask: where are we in the long-term debt cycle? "
                f"The current thesis may not account for structural forces like "
                f"debt monetization, productivity trends, and political dynamics. "
                f"The biggest risk is being right about the direction but wrong "
                f"about the structural regime."
            )
        elif "PTJ" in perspective:
            answer = (
                f"PTJ would focus on positioning and momentum. The thesis may be "
                f"fundamentally correct but poorly timed. He would say: 'The last "
                f"20% of a move is the hardest.' He would look for the asymmetric "
                f"trade — where is the 5:1 risk/reward that disagrees with consensus?"
            )
        elif "Soros" in perspective:
            answer = (
                f"Soros would examine whether market prices are affecting the "
                f"fundamentals this thesis relies on. If so, the feedback loop "
                f"could drive things far from equilibrium. The thesis might be "
                f"correct about the direction but wrong about the stability."
            )
        elif "Consensus" in perspective:
            answer = (
                f"If this is the consensus view, it's already priced in. The "
                f"marginal trade is on the other side. The question is not whether "
                f"the thesis is correct, but whether it's more correct than the "
                f"market already expects."
            )
        elif "Null Hypothesis" in perspective:
            answer = (
                f"Complete invalidation requires: (1) a regime change that makes "
                f"the current framework irrelevant, (2) a policy shock that reverses "
                f"the fundamental trend, or (3) a financial accident that breaks "
                f"correlation assumptions. Probability is low but impact is extreme."
            )
        elif "Bias" in perspective:
            answer = (
                f"Recency bias is a real risk. The last 6-12 months of data may be "
                f"dominating the analysis while ignoring structural trends that play "
                f"out over years. We should test the thesis against data from "
                f"different regimes and time periods."
            )
        else:
            answer = f"Challenging question that requires deeper analysis of the thesis assumptions and evidence base."
        
        # Estimate severity
        severity = 0.3
        if "Null" in perspective or "invalidate" in question.lower():
            severity = 0.8
        elif "Dalio" in perspective or "Soros" in perspective:
            severity = 0.6
        elif "PTJ" in perspective or "Consensus" in perspective:
            severity = 0.5
        elif "evidence" in question.lower():
            evidence_count = len(evidence) if evidence else 0
            severity = max(0.3, 0.7 - evidence_count * 0.1)
        
        challenge = Challenge(
            question=question,
            challenger_perspective=perspective,
            answer=answer,
            severity=severity,
            is_valid=severity > 0.3,
            evidence_contradicting=[],
            implication=f"If {question.lower()}: the thesis confidence should decrease by ~{severity:.0%}.",
        )
        
        return challenge

    def _calculate_vulnerability(self, challenges: list[Challenge]) -> float:
        if not challenges:
            return 0.0
        return min(sum(c.severity for c in challenges) / len(challenges) * 100, 100.0)

    def _identify_blind_spots(self, challenges: list[Challenge]) -> list[str]:
        blind_spots = []
        
        high_severity = [c for c in challenges if c.severity > 0.5]
        for c in high_severity[:3]:
            blind_spots.append(f"Blind spot related to: {c.question}")
        
        if not blind_spots:
            blind_spots = [
                "Potential confirmation bias in evidence selection",
                "Limited consideration of tail risk scenarios",
                "Assumption that current regime persists",
            ]
        
        return blind_spots

    def _identify_assumptions(self, thesis: str) -> list[str]:
        assumptions = [
            "Current macro regime continues without structural break",
            "Central bank reaction function remains consistent",
            "Market correlations remain stable during stress",
            "No exogenous geopolitical or financial shock",
        ]
        
        thesis_lower = thesis.lower()
        if "inflation" in thesis_lower:
            assumptions.append("Inflation dynamics follow historical patterns")
        if "growth" in thesis_lower or "gdp" in thesis_lower:
            assumptions.append("Productivity trends continue at current pace")
        if "rate" in thesis_lower or "fed" in thesis_lower:
            assumptions.append("Fed maintains data-dependent framework")
        
        return assumptions[:5]

    def _identify_missing_evidence(self, thesis: str,
                                    evidence: Optional[list[str]]) -> list[str]:
        missing = []
        
        if not evidence or len(evidence) < 3:
            missing.append("Limited evidence base — need more data points")
        
        thesis_lower = thesis.lower()
        if "inflation" in thesis_lower:
            missing.append("Leading inflation indicators (supply chain, wages, rents)")
            missing.append("Global inflation comparison across regimes")
        if "growth" in thesis_lower:
            missing.append("Leading economic indicators (PMI, LEI, yield curve)")
            missing.append("Labor market depth analysis")
        if "rate" in thesis_lower or "monetary" in thesis_lower:
            missing.append("Central bank reaction function analysis")
            missing.append("Market-implied vs dot plot comparison")
        
        if not missing:
            missing = [
                "Contrarian data points that would challenge the thesis",
                "Long-term historical comparison data",
                "Cross-asset correlation analysis",
            ]
        
        return missing[:4]

    def _assess_if_wrong_impact(self, thesis: str, 
                                 vulnerability: float) -> str:
        if vulnerability > 70:
            return (
                "If the thesis is wrong, the P&L impact would be SEVERE. "
                "Positions aligned with this thesis would likely suffer "
                "significant mark-to-market losses. Hedging is essential."
            )
        elif vulnerability > 40:
            return (
                "If wrong, moderate P&L impact expected. Core thesis is "
                "likely directionally correct even if timing/sizing is off. "
                "Tactical hedges recommended."
            )
        return (
            "If wrong, limited P&L impact. Thesis has multiple support points "
            "and even partial invalidation would leave some framework intact."
        )

    def _recommend_hedge(self, vulnerability: float) -> str:
        if vulnerability > 70:
            return (
                "Consider explicit hedges: OTM put options, variance swaps, "
                "or long vol strategies. Size hedges for the tail scenario."
            )
        elif vulnerability > 40:
            return (
                "Use tactical hedges: diversify across uncorrelated positions, "
                "maintain dry powder, set stop-loss levels."
            )
        return "No specific hedge needed. Diversification is sufficient."

    def _revise_thesis(self, thesis: str, 
                       result: SelfChallengeResult) -> str:
        if result.vulnerability_score > 70:
            return (
                f"{thesis}\n\n"
                f"**Caveat**: This thesis has HIGH vulnerability to challenge. "
                f"Key risks: {result.strongest_challenge}. "
                f"Confidence should be materially discounted. "
                f"Position sizing should reflect asymmetric downside risk."
            )
        elif result.vulnerability_score > 40:
            return (
                f"{thesis}\n\n"
                f"**Note**: While the core thesis remains intact, "
                f"the self-challenge identified meaningful risks. "
                f"Primary concern: {result.strongest_challenge}. "
                f"Monitor invalidation conditions closely."
            )
        return thesis
