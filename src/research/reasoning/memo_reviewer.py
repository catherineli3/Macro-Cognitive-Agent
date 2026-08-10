"""V10 Sprint 3 — Research Memo Self-Review Pipeline.

After MemoWriter produces a memo, this module applies a multi-stage
review → critic → rewrite → score loop until quality >= 90 or max 3 revisions.

Stages:
    1. MemoReviewer — Structured evaluation (Logic, Evidence, Counter, Risk, 
       Trade, Writing, Clarity, Hallucination)
    2. MemoCritic — Challenge assumptions, find missing evidence, broken chains
    3. Rewrite — Request LLM improvement based on reviewer + critic feedback
    4. Score — Generate quality score; loop if below threshold

Rules:
    - Reviewer and Critic are deterministic (rule-based + structured templates)
    - ONLY the Rewrite step uses LLM
    - Max 3 revision loops
    - Quality threshold: 90/100
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Review Result types
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ReviewDimensionScore:
    """Score for a single review dimension."""
    dimension: str = ""
    score: float = 0.0  # 0-100
    issues: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)


@dataclass
class ReviewResult:
    """Complete review output."""
    overall_score: float = 0.0  # 0-100
    grade: str = ""  # A/B/C/D/F
    dimensions: dict[str, ReviewDimensionScore] = field(default_factory=dict)
    critic_challenges: list[str] = field(default_factory=list)
    rewrite_instructions: str = ""
    passed: bool = False  # >= 90


@dataclass
class RevisionRecord:
    """Record of one revision cycle."""
    revision_number: int = 0
    before_score: float = 0.0
    after_score: float = 0.0
    critic_challenges: list[str] = field(default_factory=list)
    improvements_made: list[str] = field(default_factory=list)
    improvement_delta: float = 0.0


@dataclass
class SelfReviewResult:
    """Final output of the self-review pipeline."""
    final_memo_text: str = ""
    final_score: float = 0.0
    revisions: list[RevisionRecord] = field(default_factory=list)
    total_revisions: int = 0
    passed_threshold: bool = False
    elapsed_ms: float = 0.0
    llm_calls: int = 0
    initial_score: float = 0.0
    final_grade: str = ""
    overall_improvement: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Hallucination Detector (Deterministic)
# ═══════════════════════════════════════════════════════════════════════════


class HallucinationDetector:
    """Deterministic check: does the memo reference data/proof available in the
    structured reasoning inputs?"""

    def check(
        self, memo_text: str, step_outputs: dict
    ) -> tuple[float, list[str]]:
        """Check hallucination likelihood.

        Returns (confidence_that_all_claims_are_grounded, list_of_suspicious_claims).
        Higher score = fewer hallucinations detected.
        """
        issues = []

        # Extract numeric claims from memo
        numeric_pattern = re.findall(
            r"(\d+(?:\.\d+)?)\s*(%|bps|bp|percent|basis.points|trillion|billion|million)",
            memo_text, re.IGNORECASE,
        )
        # Extract named entity references
        entity_pattern = re.findall(
            r"\b(SPX|VIX|DXY|US10Y|US2Y|OIL|GOLD|BTC|CPI|GDP|UNEMP|FOMC|Fed|ECB|PBOC|BOJ)\b",
            memo_text,
        )

        # Collect all data available in step outputs
        available_data = self._collect_available_data(step_outputs)
        available_text = json.dumps(available_data).lower() if available_data else ""

        # Check if key numeric values appear in available data
        suspect_claims = 0
        total_claims = len(numeric_pattern) + len(entity_pattern)

        for value, unit in numeric_pattern:
            claim_str = f"{value}{unit}"
            if claim_str.lower() not in available_text and value not in available_text:
                suspect_claims += 1
                # Only flag if we have some reference data to check against
                if len(available_text) > 100:
                    issues.append(f"Suspicious value: {value} {unit} — not found in source data")

        # Check entity references
        for entity in entity_pattern:
            if entity.lower() not in available_text:
                # Allow these common entities
                if entity.upper() not in ("FED", "FOMC", "ECB", "PBOC", "BOJ"):
                    pass  # These are OK to mention without data

        if total_claims == 0:
            return 1.0, []  # No claims to check = no hallucinations found

        hallucination_rate = suspect_claims / max(total_claims, 1)
        score = 1.0 - min(hallucination_rate, 1.0)

        # Score 0-100
        return round(score * 100, 1), issues

    def _collect_available_data(self, step_outputs: dict) -> dict:
        """Collect all data points from structured reasoning outputs."""
        data = {}

        # From evidence
        evidence = step_outputs.get("evidence", {})
        for cluster in evidence.get("clusters", []):
            theme = cluster.get("theme", "")
            if theme:
                data[theme] = {
                    "net_direction": cluster.get("net_direction"),
                    "weight_score": cluster.get("weight_score"),
                }

        # From hypotheses
        hypotheses = step_outputs.get("hypotheses", {})
        data["hypothesis_count"] = len(hypotheses.get("hypotheses", []))

        # From history
        history = step_outputs.get("historical", {})
        for analog in history.get("analogs", []):
            period = analog.get("period", "")
            if period:
                data[f"analog_{period}"] = analog.get("similarity_score")

        # From portfolio
        portfolio = step_outputs.get("portfolio", {})
        for k, v in portfolio.items():
            if isinstance(v, (str, int, float, bool)):
                data[f"portfolio_{k}"] = v

        return data


# ═══════════════════════════════════════════════════════════════════════════
# Memo Reviewer (Deterministic structural evaluation)
# ═══════════════════════════════════════════════════════════════════════════


class MemoReviewer:
    """Deterministic reviewer: evaluates memo structure, completeness, and
    consistency against the structured reasoning outputs.

    Evaluates 8 dimensions:
        Logic, Evidence, CounterArguments, Risk, Trade,
        Writing, Clarity, Hallucination
    """

    DIMENSIONS = [
        "Logic",
        "Evidence",
        "CounterArguments",
        "Risk",
        "Trade",
        "Writing",
        "Clarity",
        "Hallucination",
    ]

    def __init__(self):
        self._hallucination = HallucinationDetector()

    def review(
        self, memo_text: str, step_outputs: dict, regime_result: Optional[dict] = None
    ) -> ReviewResult:
        """Perform a full structured review of the memo.

        Returns ReviewResult with dimension scores, critic challenges, and
        rewrite instructions.
        """
        dimensions = {}

        # 1. Logic — check for logical structure markers
        dimensions["Logic"] = self._score_logic(memo_text)

        # 2. Evidence — check for evidence references
        dimensions["Evidence"] = self._score_evidence(memo_text, step_outputs)

        # 3. CounterArguments — check for counter-argument coverage
        dimensions["CounterArguments"] = self._score_counter_arguments(
            memo_text, step_outputs
        )

        # 4. Risk — check for risk discussion
        dimensions["Risk"] = self._score_risk(memo_text)

        # 5. Trade — check for trading implications
        dimensions["Trade"] = self._score_trade(memo_text)

        # 6. Writing — check for professional writing quality
        dimensions["Writing"] = self._score_writing(memo_text)

        # 7. Clarity — check for clear, precise language
        dimensions["Clarity"] = self._score_clarity(memo_text)

        # 8. Hallucination — check claims against source data
        hallu_score, hallu_issues = self._hallucination.check(memo_text, step_outputs)
        dimensions["Hallucination"] = ReviewDimensionScore(
            dimension="Hallucination",
            score=hallu_score,
            issues=hallu_issues,
            strengths=["All claims appear grounded in source data"] if hallu_score >= 95 else [],
        )

        # Calculate overall score
        weights = {
            "Logic": 0.20,
            "Evidence": 0.20,
            "CounterArguments": 0.15,
            "Risk": 0.15,
            "Trade": 0.10,
            "Writing": 0.10,
            "Clarity": 0.05,
            "Hallucination": 0.05,
        }

        overall = round(
            sum(dimensions[d].score * weights[d] for d in self.DIMENSIONS), 1
        )

        # Grade
        grade = self._score_to_grade(overall)

        # Generate rewrite instructions
        instructions = self._generate_rewrite_instructions(dimensions, overall)

        return ReviewResult(
            overall_score=overall,
            grade=grade,
            dimensions=dimensions,
            critic_challenges=[],  # Filled by MemoCritic
            rewrite_instructions=instructions,
            passed=overall >= 90.0,
        )

    def _score_logic(self, text: str) -> ReviewDimensionScore:
        """Score logical structure."""
        score = 70.0  # Baseline
        issues = []
        strengths = []

        lower = text.lower()

        # Check for causal language
        causal_markers = ["because", "therefore", "as a result", "consequently",
                          "leads to", "drives", "causes", "implies"]
        causal_count = sum(1 for m in causal_markers if m in lower)
        if causal_count >= 5:
            score += 15
            strengths.append(f"Strong causal reasoning ({causal_count} causal markers)")
        elif causal_count >= 2:
            score += 5
        else:
            score -= 10
            issues.append("Insufficient causal reasoning — add more 'because/therefore' chains")

        # Check for probability language
        prob_markers = ["likely", "probability", "scenario", "tail risk",
                        "base case", "expected", "confidence"]
        prob_count = sum(1 for m in prob_markers if m in lower)
        if prob_count >= 4:
            score += 10
            strengths.append("Good use of probabilistic language")
        elif prob_count == 0:
            score -= 5
            issues.append("No probabilistic framing — add scenario analysis")

        # Check for conditional logic
        cond_markers = ["if", "unless", "depends on", "conditional on", "contingent"]
        cond_count = sum(1 for m in cond_markers if m in lower)
        if cond_count >= 3:
            score += 5
            strengths.append("Good use of conditional logic")

        return ReviewDimensionScore(
            dimension="Logic",
            score=max(0, min(100, score)),
            issues=issues,
            strengths=strengths,
        )

    def _score_evidence(self, text: str, step_outputs: dict) -> ReviewDimensionScore:
        """Score evidence integration."""
        score = 60.0
        issues = []
        strengths = []

        lower = text.lower()

        # Check for data references
        data_pattern = re.findall(r"\d+(?:\.\d+)?\s*%?", text)
        if len(data_pattern) >= 5:
            score += 15
            strengths.append(f"Rich data references ({len(data_pattern)} data points)")
        elif len(data_pattern) >= 2:
            score += 5
        else:
            score -= 15
            issues.append("Very few data references — needs more quantitative evidence")

        # Check if references evidence from source
        evidence_refs = ["evidence", "data shows", "indicator", "metric", "reading",
                         "print", "release", "survey", "index"]
        ref_count = sum(1 for m in evidence_refs if m in lower)
        if ref_count >= 4:
            score += 10
            strengths.append("Good source attribution")

        # Check support vs contradict
        if "support" in lower or "confirm" in lower:
            score += 5
        if "contradict" in lower or "counter" in lower or "challenge" in lower:
            score += 10
            strengths.append("Addresses contradictory evidence")

        return ReviewDimensionScore(
            dimension="Evidence",
            score=max(0, min(100, score)),
            issues=issues,
            strengths=strengths,
        )

    def _score_counter_arguments(self, text: str, step_outputs: dict) -> ReviewDimensionScore:
        """Score counter-argument coverage."""
        score = 50.0
        issues = []
        strengths = []

        lower = text.lower()

        # Count available counter-arguments from step outputs
        counter_data = step_outputs.get("counter", {})
        available_counters = len(counter_data.get("arguments", counter_data.get("counter_arguments", [])))

        # Check counter-argument language
        counter_markers = [
            "however", "on the other hand", "alternative view", "bear case",
            "conversely", "counter", "skeptics argue", "one risk is",
            "could go wrong", "what if", "might not", "despite",
        ]
        counter_count = sum(1 for m in counter_markers if m in lower)

        if counter_count >= 4:
            score += 25
            strengths.append(f"Strong counter-argument coverage ({counter_count} markers)")
        elif counter_count >= 2:
            score += 10
        else:
            score -= 20
            issues.append("No meaningful counter-arguments — memo is one-sided")

        # Check if specific counters from reasoning are referenced
        if available_counters > 0 and counter_count >= 2:
            score += 15
            strengths.append("References structured counter-arguments from reasoning")

        return ReviewDimensionScore(
            dimension="CounterArguments",
            score=max(0, min(100, score)),
            issues=issues,
            strengths=strengths,
        )

    def _score_risk(self, text: str) -> ReviewDimensionScore:
        """Score risk analysis."""
        score = 50.0
        issues = []
        strengths = []

        lower = text.lower()

        risk_markers = [
            "risk", "tail", "worst-case", "black swan", "drawdown",
            "vulnerability", "fragility", "exposure", "hedge", "invalidation",
            "could fail", "what breaks", "trigger",
        ]
        risk_count = sum(1 for m in risk_markers if m in lower)

        if risk_count >= 6:
            score += 30
            strengths.append(f"Excellent risk coverage ({risk_count} risk markers)")
        elif risk_count >= 3:
            score += 15
        else:
            score -= 25
            issues.append("Insufficient risk analysis — add invalidation conditions and tail risks")

        # Check for specific risk quantification
        if re.search(r"\d+%?\s*(probability|chance|likelihood)", lower):
            score += 10
            strengths.append("Quantified risk probabilities")

        return ReviewDimensionScore(
            dimension="Risk",
            score=max(0, min(100, score)),
            issues=issues,
            strengths=strengths,
        )

    def _score_trade(self, text: str) -> ReviewDimensionScore:
        """Score trading implications."""
        score = 50.0
        issues = []
        strengths = []

        lower = text.lower()

        trade_markers = [
            "trade", "position", "long", "short", "overweight", "underweight",
            "allocation", "portfolio", "asset", "exposure", "duration",
            "hedge", "option", "spread", "carry", "volatility",
        ]
        trade_count = sum(1 for m in trade_markers if m in lower)

        if trade_count >= 5:
            score += 30
            strengths.append(f"Concrete trade ideas ({trade_count} trade references)")
        elif trade_count >= 2:
            score += 10
        else:
            score -= 20
            issues.append("No trade ideas — add portfolio implications")

        # Check for highest conviction trade
        if "highest conviction" in lower or "best trade" in lower:
            score += 10
            strengths.append("Identifies highest conviction trade")

        return ReviewDimensionScore(
            dimension="Trade",
            score=max(0, min(100, score)),
            issues=issues,
            strengths=strengths,
        )

    def _score_writing(self, text: str) -> ReviewDimensionScore:
        """Score professional writing quality."""
        score = 70.0
        issues = []
        strengths = []

        # Check for structured sections
        section_markers = re.findall(
            r"(?:^|\n)(?:#+|[A-Z][\w\s]+:)(?:\s)", text
        )
        if len(section_markers) >= 4:
            score += 10
            strengths.append("Well-structured with clear sections")
        elif len(section_markers) >= 2:
            score += 5
        else:
            score -= 10
            issues.append("Lacks clear section structure")

        # Check paragraph length
        paras = [p for p in text.split("\n\n") if len(p.strip()) > 50]
        if 3 <= len(paras) <= 20:
            score += 5
            strengths.append("Good paragraph structure")
        elif len(paras) > 30:
            score -= 5
            issues.append("Too many paragraphs — consider consolidation")

        # Check for jargon balance
        jargon = ["alpha", "beta", "gamma", "delta", "vega", "theta",
                  "carry", "roll", "steepen", "flatten", "duration",
                  "convexity", "regime", "factor", "momentum", "value"]
        jargon_count = sum(1 for j in jargon if j in text.lower())
        if 3 <= jargon_count <= 10:
            score += 5
            strengths.append("Appropriate professional terminology")
        elif jargon_count == 0:
            score -= 5
        elif jargon_count > 15:
            score -= 5
            issues.append("Excessive jargon — may reduce clarity")

        return ReviewDimensionScore(
            dimension="Writing",
            score=max(0, min(100, score)),
            issues=issues,
            strengths=strengths,
        )

    def _score_clarity(self, text: str) -> ReviewDimensionScore:
        """Score clarity and precision."""
        score = 70.0
        issues = []
        strengths = []

        # Check for vague language
        vague = ["somewhat", "kind of", "sort of", "maybe", "probably maybe",
                 "could be", "might be", "various", "certain", "things"]
        vague_count = sum(1 for v in vague if v in text.lower())
        if vague_count <= 2:
            score += 10
            strengths.append("Minimal vague language")
        elif vague_count >= 6:
            score -= 15
            issues.append(f"Too much vague language ({vague_count} instances) — be more specific")

        # Check for explicit numbers
        num_pattern = re.findall(r"\b\d+(?:\.\d+)?\b", text)
        if len(num_pattern) >= 8:
            score += 10
            strengths.append("Good quantitative precision")
        elif len(num_pattern) >= 3:
            score += 5

        # Check one-sentence view
        one_sent = re.search(
            r"(?:one.sentence|one.sentence.view|in one sentence)[:\s]*(.+?)(?:\n|$)",
            text, re.IGNORECASE,
        )
        if one_sent:
            score += 5
            strengths.append("Has clear one-sentence view")

        return ReviewDimensionScore(
            dimension="Clarity",
            score=max(0, min(100, score)),
            issues=issues,
            strengths=strengths,
        )

    @staticmethod
    def _score_to_grade(score: float) -> str:
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        return "F"

    def _generate_rewrite_instructions(
        self, dimensions: dict[str, ReviewDimensionScore], overall: float
    ) -> str:
        """Generate specific rewrite instructions from review results."""
        instructions = []

        for dim_name, dim_score in dimensions.items():
            if dim_score.score < 75:
                for issue in dim_score.issues:
                    instructions.append(f"[{dim_name}] {issue}")

        if not instructions:
            return "Minor polish only — all dimensions are strong."

        # Sort by weakest dimensions
        sorted_dims = sorted(dimensions.items(), key=lambda x: x[1].score)
        weakest = sorted_dims[:3]

        header = (
            f"REWRITE INSTRUCTIONS (Current score: {overall:.0f}/100):\n\n"
            "Focus on these weakest dimensions:\n"
        )
        for dim_name, dim_score in weakest:
            header += f"  • {dim_name} ({dim_score.score:.0f}/100)\n"

        header += "\nSpecific improvements needed:\n"
        for inst in instructions:
            header += f"  - {inst}\n"

        return header


# ═══════════════════════════════════════════════════════════════════════════
# Memo Critic (Soros/Dalio challenges)
# ═══════════════════════════════════════════════════════════════════════════


class MemoCritic:
    """Challenges the memo from the perspective of Soros and Dalio.

    Asks:
        - What assumptions are weak?
        - Where is evidence missing?
        - Where is the causal chain broken?
        - Which section is repetitive?
        - What would Dalio criticize?
        - What would Soros criticize?
    """

    def challenge(
        self, memo_text: str, step_outputs: dict, review_result: ReviewResult
    ) -> list[str]:
        """Generate challenge questions and critiques from the trading legends.

        Returns a list of specific challenges that need to be addressed.
        """
        challenges = []

        # ── Assumption Analysis ──
        challenges.extend(self._find_weak_assumptions(memo_text))

        # ── Missing Evidence ──
        challenges.extend(self._find_missing_evidence(memo_text, step_outputs))

        # ── Broken Causal Chains ──
        challenges.extend(self._find_broken_causal_chains(memo_text))

        # ── Repetition Detection ──
        challenges.extend(self._find_repetition(memo_text))

        # ── Dalio Critique ──
        challenges.extend(self._dalio_critique(memo_text, step_outputs))

        # ── Soros Critique ──
        challenges.extend(self._soros_critique(memo_text, step_outputs))

        return challenges

    def _find_weak_assumptions(self, text: str) -> list[str]:
        """Identify weak/unstated assumptions."""
        challenges = []
        lower = text.lower()

        # Check for implicit assumptions
        assumption_triggers = [
            ("assume", "What assumptions underlie this claim? State them explicitly."),
            ("continue to", "Why will this trend continue? What could break it?"),
            ("should", "Who says this 'should' happen? Which model predicts this?"),
            ("always", "Is this phenomenon truly invariant? When has it failed to hold?"),
            ("never", "History suggests few things 'never' happen. What's the counter-case?"),
            ("obviously", "If it's 'obvious', it's likely priced in. What's NOT priced?"),
            ("everyone knows", "Consensus views are rarely profitable. What's the contrarian take?"),
        ]

        for trigger, challenge in assumption_triggers:
            if trigger in lower:
                challenges.append(f"[Weak Assumption] {challenge}")

        # Check if memo states its own assumptions
        if "assum" not in lower:
            challenges.append(
                "[Missing Assumptions] The memo does not explicitly state its key assumptions. "
                "List the top 3 assumptions that, if wrong, would invalidate the thesis."
            )

        return challenges

    def _find_missing_evidence(self, text: str, step_outputs: dict) -> list[str]:
        """Find claims that need evidence."""
        challenges = []
        lower = text.lower()

        # Strong claims without numbers
        strong_claims = [
            "significant", "substantial", "major", "dramatic", "massive",
            "critical", "historic", "unprecedented",
        ]
        for claim in strong_claims:
            # Check if claim is followed by specific data within 100 chars
            matches = [m.start() for m in re.finditer(re.escape(claim), lower)]
            for pos in matches:
                nearby = text[pos:pos + 150]
                if not re.search(r"\d+", nearby):
                    challenges.append(
                        f"[Missing Evidence] Claim '{claim}' near position {pos} "
                        f"lacks quantitative support."
                    )
                    break  # Only flag once per word

        return challenges[:3]  # Limit

    def _find_broken_causal_chains(self, text: str) -> list[str]:
        """Find incomplete causal reasoning."""
        challenges = []
        lower = text.lower()

        # Pattern: "X will cause Y" without explaining mechanism
        cause_patterns = [
            r"will (lead to|drive|cause|result in|trigger)",
            r"is (bullish|bearish) for",
            r"should (boost|support|weigh on|pressure)",
        ]

        for pattern in cause_patterns:
            matches = re.finditer(pattern, lower)
            for m in matches:
                # Check if "because" appears within 200 chars after
                after = text[m.start():m.start() + 200]
                if "because" not in after.lower() and "due to" not in after.lower():
                    challenges.append(
                        "[Broken Causal Chain] Statement at position ~"
                        f"{m.start()} asserts causality without explaining mechanism."
                    )
                    break  # Only flag first instance per pattern

        return challenges[:2]

    def _find_repetition(self, text: str) -> list[str]:
        """Detect repetitive sections."""
        challenges = []

        # Split into sentences and check for near-duplicates
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip().lower() for s in sentences if len(s.strip()) > 30]

        for i, s1 in enumerate(sentences):
            for j, s2 in enumerate(sentences):
                if j <= i:
                    continue
                # Simple similarity: common word ratio
                words1 = set(s1.split())
                words2 = set(s2.split())
                if words1 and words2:
                    common = words1 & words2
                    similarity = len(common) / min(len(words1), len(words2))
                    if similarity > 0.7:
                        challenges.append(
                            "[Repetition] Sentences "
                            f"'{sentences[i][:50]}...' and "
                            f"'{sentences[j][:50]}...' are highly similar "
                            f"({similarity:.0%} overlap). Consolidate."
                        )
                        break
            if len(challenges) >= 2:
                break

        return challenges

    def _dalio_critique(self, text: str, step_outputs: dict) -> list[str]:
        """What would Ray Dalio criticize?

        Dalio focuses on:
        - Debt cycles and long-term debt cycle positioning
        - Productivity growth as the ultimate driver
        - How the economic machine works (credit + productivity)
        - Political/social conflict cycles
        - Reserve currency dynamics
        """
        challenges = []
        lower = text.lower()

        dalio_checks = [
            ("debt cycle", "Where are we in the long-term debt cycle? This perspective is missing."),
            ("productivity", "How does productivity growth inform this view? Dalio would ask."),
            ("long-term debt", "No discussion of long-term debt cycle dynamics."),
            ("credit creation", "How is credit being created? By whom? For what purpose?"),
            ("reserve currency", "How does reserve currency status affect this analysis?"),
            ("social conflict", "Are there political/social dynamics that could override the economic view?"),
            ("beautiful deleveraging", "Is this a 'beautiful deleveraging' or an 'ugly' one?"),
            ("economic machine", "How does this fit into the economic machine framework?"),
        ]

        missing = [c for trigger, c in dalio_checks if trigger not in lower]
        if missing:
            selected = missing[:3]  # Pick top 3 missing Dalio perspectives
            for c in selected:
                challenges.append(f"[Dalio] {c}")

        return challenges

    def _soros_critique(self, text: str, step_outputs: dict) -> list[str]:
        """What would George Soros criticize?

        Soros focuses on:
        - Reflexivity (perception changes fundamentals)
        - Boom-bust sequences
        - Far-from-equilibrium conditions
        - Fallibility of participants
        - The Alchemy of Finance — markets shape reality
        """
        challenges = []
        lower = text.lower()

        soros_checks = [
            ("reflexiv", "No reflexivity analysis — how might market perception change the fundamentals?"),
            ("boom.bust", "Is this a boom-bust sequence? Soros would analyze the phases."),
            ("far.from.equilibrium", "Is the market near equilibrium or far from it? This distinction matters."),
            ("fallibil", "Soros emphasizes human fallibility. What cognitive biases are at play?"),
            ("self.reinforcing", "Is there a self-reinforcing feedback loop? The reflexive dimension is missing."),
            ("perception", "How does perception interact with reality here? Soros's key concern."),
            ("prevailing bias", "What is the prevailing bias — and when might it reverse?"),
        ]

        missing = [c for trigger, c in soros_checks if trigger not in lower]
        if missing:
            selected = missing[:3]
            for c in selected:
                challenges.append(f"[Soros] {c}")

        return challenges


# ═══════════════════════════════════════════════════════════════════════════
# Self-Review Pipeline
# ═══════════════════════════════════════════════════════════════════════════


class MemoSelfReviewPipeline:
    """V10 Sprint 3: Memo Self-Review & Improvement Loop.

    Pipeline:
        Memo → [Reviewer → Critic → Challenge → Rewrite → Score] → Final Memo

    Loops until quality >= 90 or max 3 revisions.
    Only the Rewrite step uses LLM.
    """

    MAX_REVISIONS = 3
    QUALITY_THRESHOLD = 90.0
    MIN_IMPROVEMENT = 3.0  # Minimum score improvement to continue

    def __init__(self, llm_client=None):
        self._reviewer = MemoReviewer()
        self._critic = MemoCritic()
        self._llm_client = llm_client

    def review_and_improve(
        self,
        memo_text: str,
        step_outputs: dict,
        regime_result: Optional[dict] = None,
        date_str: str = "",
    ) -> SelfReviewResult:
        """Run the full self-review pipeline.

        Args:
            memo_text: The initial memo text.
            step_outputs: Dict with keys: evidence, hypotheses, counter, reflexivity,
                          historical, portfolio (structured JSON from steps 1-6).
            regime_result: Regime classification result.
            date_str: Date string for context.

        Returns:
            SelfReviewResult with final memo, scores, and revision history.
        """
        t0 = time.time()
        revisions = []
        current_memo = memo_text
        llm_calls = 0

        # Initial review
        initial_review = self._reviewer.review(current_memo, step_outputs, regime_result)
        initial_score = initial_review.overall_score
        current_score = initial_score

        logger.info(
            "Self-review started: initial score=%.0f/100, grade=%s",
            initial_score, initial_review.grade,
        )

        for rev_num in range(1, self.MAX_REVISIONS + 1):
            if current_score >= self.QUALITY_THRESHOLD:
                logger.info("Quality threshold reached at revision %d", rev_num - 1)
                break

            # Critic challenges
            critic_challenges = self._critic.challenge(
                current_memo, step_outputs, initial_review
            )

            # Build rewrite prompt
            rewrite_prompt = self._build_rewrite_prompt(
                current_memo, initial_review, critic_challenges, rev_num
            )

            # Attempt LLM rewrite
            improved_memo = self._attempt_rewrite(rewrite_prompt)
            if improved_memo:
                llm_calls += 1
                current_memo = improved_memo
            else:
                # LLM unavailable — skip remaining revisions
                logger.warning("LLM rewrite unavailable at revision %d", rev_num)
                break

            # Re-score
            new_review = self._reviewer.review(current_memo, step_outputs, regime_result)
            new_score = new_review.overall_score
            improvement = new_score - current_score

            revisions.append(RevisionRecord(
                revision_number=rev_num,
                before_score=current_score,
                after_score=new_score,
                critic_challenges=critic_challenges,
                improvements_made=self._extract_improvements(
                    initial_review.dimensions, new_review.dimensions
                ),
                improvement_delta=round(improvement, 1),
            ))

            current_score = new_score
            initial_review = new_review

            logger.info(
                "Revision %d: %.0f -> %.0f (Δ%+.0f)",
                rev_num, revisions[-1].before_score, new_score, improvement,
            )

            # Stop if improvement is minimal
            if improvement < self.MIN_IMPROVEMENT and current_score < self.QUALITY_THRESHOLD:
                logger.info(
                    "Minimal improvement (Δ%+.1f < %.0f), stopping revisions",
                    improvement, self.MIN_IMPROVEMENT,
                )
                break

        elapsed = (time.time() - t0) * 1000

        return SelfReviewResult(
            final_memo_text=current_memo,
            final_score=current_score,
            revisions=revisions,
            total_revisions=len(revisions),
            passed_threshold=current_score >= self.QUALITY_THRESHOLD,
            elapsed_ms=elapsed,
            llm_calls=llm_calls,
            initial_score=initial_score,
            final_grade=self._reviewer._score_to_grade(current_score),
            overall_improvement=round(current_score - initial_score, 1),
        )

    def _build_rewrite_prompt(
        self,
        memo_text: str,
        review: ReviewResult,
        critic_challenges: list[str],
        revision_num: int,
    ) -> str:
        """Build a rewrite prompt incorporating reviewer + critic feedback."""
        parts = [
            f"## REVISION {revision_num} — MEMO REWRITE REQUEST\n",
            f"Current score: {review.overall_score:.0f}/100 (Grade: {review.grade})\n",
            "## CURRENT MEMO\n```\n" + memo_text + "\n```\n",
            "## REVIEWER FEEDBACK\n",
        ]

        # Dimension scores
        for dim_name, dim_score in review.dimensions.items():
            parts.append(f"### {dim_name}: {dim_score.score:.0f}/100")
            if dim_score.issues:
                for issue in dim_score.issues:
                    parts.append(f"  - ISSUE: {issue}")
            if dim_score.strengths:
                for strength in dim_score.strengths:
                    parts.append(f"  + STRENGTH: {strength}")
            parts.append("")

        # Critic challenges
        if critic_challenges:
            parts.append("## CRITIC CHALLENGES (Dalio/Soros perspective)\n")
            for challenge in critic_challenges:
                parts.append(f"  - {challenge}")
            parts.append("")

        # Rewrite instructions
        parts.append("## REWRITE INSTRUCTIONS\n")
        parts.append(review.rewrite_instructions)
        parts.append("\n")

        # Output format
        parts.append(
            "## REQUIRED OUTPUT\n"
            "Rewrite the full memo addressing ALL reviewer issues and critic challenges. "
            "Output ONLY the improved memo text. Do NOT include meta-commentary about "
            "the revision process. The memo must be complete and self-contained."
        )

        return "\n".join(parts)

    def _attempt_rewrite(self, rewrite_prompt: str) -> Optional[str]:
        """Attempt LLM-based rewrite. Returns None if LLM unavailable."""
        if not self._llm_client:
            return None

        try:
            response = self._llm_client.research_chat(
                system_prompt=(
                    "You are rewriting a professional macro research memo based on "
                    "structured reviewer feedback. Improve the memo while preserving "
                    "all correct analysis. Follow the rewrite instructions precisely. "
                    "Output ONLY the improved memo text."
                ),
                user_prompt=rewrite_prompt,
                temperature=0.3,
            )

            if response.success and response.content:
                return response.content.strip()
            return None
        except Exception as e:
            logger.warning("Rewrite attempt failed: %s", e)
            return None

    @staticmethod
    def _extract_improvements(
        before: dict[str, ReviewDimensionScore],
        after: dict[str, ReviewDimensionScore],
    ) -> list[str]:
        """Extract which dimensions improved."""
        improvements = []
        for dim_name in before:
            delta = after[dim_name].score - before[dim_name].score
            if delta >= 2:
                improvements.append(f"{dim_name}: +{delta:.0f}pts")
        return improvements


# ═══════════════════════════════════════════════════════════════════════════
# Convenience: review memo without LLM rewrite
# ═══════════════════════════════════════════════════════════════════════════


def review_memo(
    memo_text: str,
    step_outputs: dict,
    regime_result: Optional[dict] = None,
) -> ReviewResult:
    """Quick deterministic review without the rewrite loop."""
    reviewer = MemoReviewer()
    critic = MemoCritic()
    result = reviewer.review(memo_text, step_outputs, regime_result)
    result.critic_challenges = critic.challenge(memo_text, step_outputs, result)
    return result
