# =============================================================================
# V9 Research Report Benchmark — Compare Agent Memos vs Institutional Reports
# =============================================================================
# Scores agent memos against Bridgewater, JPMorgan, Goldman, Morgan Stanley.
# Dimensions: Insight, Evidence, Causality, Originality, Risk, Actionability.
# Target: ≥80% of institutional research quality.
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ResearchQualityDimensions:
    """Six dimensions of research report quality."""
    insight: float = 0.0        # Depth of original insight (0-100)
    evidence: float = 0.0       # Quality and breadth of supporting evidence
    causality: float = 0.0      # Logical chain from data to conclusion
    originality: float = 0.0    # Unique perspective vs consensus
    risk_analysis: float = 0.0  # Thoroughness of risk and alternative scenarios
    actionability: float = 0.0  # Clear implications for investors

    @property
    def total(self) -> float:
        return (self.insight + self.evidence + self.causality +
                self.originality + self.risk_analysis + self.actionability) / 6

    @property
    def grade(self) -> str:
        t = self.total
        if t >= 90: return "A"
        if t >= 80: return "B"
        if t >= 70: return "C"
        if t >= 60: return "D"
        return "F"


@dataclass
class MemoComparisonResult:
    """Agent memo compared against institutional benchmark."""
    case_id: str = ""
    case_title: str = ""

    # Agent's quality scores
    agent_quality: ResearchQualityDimensions = field(default_factory=ResearchQualityDimensions)

    # Benchmark (institutional average)
    benchmark_quality: ResearchQualityDimensions = field(default_factory=ResearchQualityDimensions)

    # Agent relative to benchmark
    relative_scores: dict = field(default_factory=dict)  # dimension->percentage

    # Word count
    agent_word_count: int = 0
    benchmark_min_words: int = 2500

    # Overall
    agent_vs_benchmark_pct: float = 0.0  # agent_total / benchmark_total

    # Gap analysis
    biggest_strength: str = ""
    biggest_weakness: str = ""
    improvement_recommendations: list[str] = field(default_factory=list)

    @property
    def meets_target(self) -> bool:
        return self.agent_vs_benchmark_pct >= 0.80  # ≥80% of institutional level

    @property
    def passed(self) -> bool:
        return self.agent_quality.total >= 85  # V9 target: ≥85/100


class ReportBenchmark:
    """Benchmark agent research memos against institutional standards.

    Institutional benchmarks (approximate levels):
        Bridgewater DO: ~92/100 — deepest causal reasoning
        JPM Macro Strategy: ~88/100 — comprehensive evidence, actionable
        Goldman Outlook: ~85/100 — sharp insight, institutional polish
        Morgan Stanley Strategy: ~82/100 — strong risk analysis
    """

    # Institutional benchmark average scores
    INSTITUTIONAL_BENCHMARK = ResearchQualityDimensions(
        insight=85, evidence=90, causality=88,
        originality=80, risk_analysis=85, actionability=82,
    )

    def __init__(self):
        self.results: list[MemoComparisonResult] = []

    def evaluate_memo(self, case_id: str, case_title: str,
                      memo_content: str, memo_sections: dict) -> MemoComparisonResult:
        """Evaluate agent memo against institutional benchmark."""

        agent = self._score_memo_quality(memo_content, memo_sections)
        benchmark = self.INSTITUTIONAL_BENCHMARK

        # Calculate relative scores
        relative = {
            "insight": (agent.insight / benchmark.insight * 100) if benchmark.insight else 0,
            "evidence": (agent.evidence / benchmark.evidence * 100) if benchmark.evidence else 0,
            "causality": (agent.causality / benchmark.causality * 100) if benchmark.causality else 0,
            "originality": (agent.originality / benchmark.originality * 100) if benchmark.originality else 0,
            "risk_analysis": (agent.risk_analysis / benchmark.risk_analysis * 100) if benchmark.risk_analysis else 0,
            "actionability": (agent.actionability / benchmark.actionability * 100) if benchmark.actionability else 0,
        }

        result = MemoComparisonResult(
            case_id=case_id,
            case_title=case_title,
            agent_quality=agent,
            benchmark_quality=benchmark,
            relative_scores=relative,
            agent_word_count=len(memo_content.split()),
            agent_vs_benchmark_pct=agent.total / benchmark.total * 100 if benchmark.total else 0,
        )

        # Gap analysis
        dims = {"insight": agent.insight, "evidence": agent.evidence,
                "causality": agent.causality, "originality": agent.originality,
                "risk_analysis": agent.risk_analysis, "actionability": agent.actionability}

        result.biggest_strength = max(dims, key=dims.get)
        result.biggest_weakness = min(dims, key=dims.get)

        # Recommendations
        if result.biggest_weakness == "evidence":
            result.improvement_recommendations.append(
                "Add more data points, charts, and specific numbers to support claims")
        elif result.biggest_weakness == "originality":
            result.improvement_recommendations.append(
                "Develop unique analytical frameworks; avoid consensus-repeating")
        elif result.biggest_weakness == "causality":
            result.improvement_recommendations.append(
                "Strengthen cause→effect chains; show mechanisms not just correlations")

        self.results.append(result)
        return result

    def _score_memo_quality(self, content: str, sections: dict) -> ResearchQualityDimensions:
        """Score agent memo content quality."""
        quality = ResearchQualityDimensions()
        content_lower = content.lower()
        word_count = len(content.split())

        # Insight (depth): checks for analytical depth markers
        insight_signals = ["because", "therefore", "implies", "suggests", "indicates",
                          "mechanism", "transmission", "channel", "why"]
        insight_count = sum(1 for s in insight_signals if s in content_lower)
        sections_count = len(sections)
        quality.insight = min(insight_count * 5 + sections_count * 5, 100)

        # Evidence: checks for data, numbers, and references
        import re
        numbers = len(re.findall(r'\d+\.?\d*%?', content))
        quality.evidence = min(numbers * 2 + sections_count * 3, 100)

        # Causality: checks for cause-effect construction
        causal_signals = ["causes", "leads to", "results in", "drives", "because",
                         "therefore", "hence", "as a result", "mechanism"]
        causal_count = sum(1 for s in causal_signals if s in content_lower)
        quality.causality = min(causal_count * 5 + 20, 100)

        # Originality: checks for unique perspectives
        originality_signals = ["contrary to", "unlike", "whereas", "however",
                              "this differs from", "unique", "unprecedented", "novel"]
        orig_count = sum(1 for s in originality_signals if s in content_lower)
        quality.originality = min(orig_count * 8 + 20, 100)

        # Risk analysis: checks for risk and alternative scenarios
        risk_signals = ["risk", "if", "unless", "however", "downside", "tail",
                       "alternative scenario", "bear case", "counter", "worst case"]
        risk_count = sum(1 for s in risk_signals if s in content_lower)
        quality.risk_analysis = min(risk_count * 4 + len(sections.get("risk", "").split()) * 0.5, 100)

        # Actionability: checks for investment implications
        action_signals = ["implication", "position", "trade", "invest", "recommend",
                         "prefer", "avoid", "overweight", "underweight", "allocation"]
        action_count = sum(1 for s in action_signals if s in content_lower)
        quality.actionability = min(action_count * 5 + 20, 100)

        return quality

    @property
    def overall_stats(self) -> dict:
        """Aggregate stats across all evaluations."""
        if not self.results:
            return {"count": 0, "avg_score": 0, "pass_rate": 0, "benchmark_pct": 0}

        n = len(self.results)
        avg_score = sum(r.agent_quality.total for r in self.results) / n
        pass_rate = sum(1 for r in self.results if r.passed) / n
        benchmark_pct = sum(r.agent_vs_benchmark_pct for r in self.results) / n

        return {
            "count": n,
            "avg_quality_score": round(avg_score, 1),
            "pass_rate_85plus": round(pass_rate, 2),
            "avg_vs_institutional_pct": round(benchmark_pct, 1),
            "meets_80pct_target": benchmark_pct >= 80,
        }

    def summary(self) -> str:
        stats = self.overall_stats
        lines = [
            "Research Report Quality Benchmark",
            f"{'─'*50}",
            f"Reports Evaluated: {stats['count']}",
            f"Avg Quality Score: {stats['avg_quality_score']:.1f}/100",
            f"Pass Rate (≥85): {stats['pass_rate_85plus']:.1%}",
            f"Avg vs Institutional: {stats['avg_vs_institutional_pct']:.1f}%",
            f"80% Target Met: {'YES' if stats['meets_80pct_target'] else 'NO'}",
        ]
        if self.results:
            last = self.results[-1]
            lines.append("")
            lines.append(f"Last Report — {last.case_title}")
            lines.append(f"  Insight: {last.agent_quality.insight:.0f} | Evidence: {last.agent_quality.evidence:.0f}")
            lines.append(f"  Causality: {last.agent_quality.causality:.0f} | Originality: {last.agent_quality.originality:.0f}")
            lines.append(f"  Risk: {last.agent_quality.risk_analysis:.0f} | Actionability: {last.agent_quality.actionability:.0f}")
            lines.append(f"  Biggest Gap: {last.biggest_weakness.replace('_', ' ').title()}")
        return "\n".join(lines)
