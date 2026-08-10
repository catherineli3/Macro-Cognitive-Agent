# =============================================================================
# V9 Phase 5: LLM Reasoning Optimization Loop
# =============================================================================
# NOT about adding more prompts.
# About: discovering WHERE the agent thinks wrong, then fixing it.
#
# The Loop:
#   Research Output → Human/Expert Score → Error Analysis
#   → Prompt Update → Reasoning Style Update → New Version
#
# Tracks why each version improved (or didn't).
# =============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from validation.v9.historical_cases import HistoricalCase, CASES, build_all_cases
from validation.v9.scoring_engine import BlindTestResult, DimensionScore


# ══════════════════════════════════════════════════════════════════════
# Core Data Types
# ══════════════════════════════════════════════════════════════════════


@dataclass
class ReasoningError:
    """A specific error in the agent's reasoning process."""
    error_id: str
    error_type: str  # One of: regime_misread, narrative_miss, causality_error,
                     #   evidence_weak, timing_wrong, framework_misapplication,
                     #   overconfidence, data_ignorance, anchoring, confirmation
    description: str
    case_id: str
    agent_wrong_thought: str  # What the agent thought
    correct_thought: str      # What it should have thought
    severity: float = 0.5     # 0-1, how bad was the error
    frequency: int = 1        # How often this pattern appears
    root_cause: str = ""      # Why the agent made this error
    suggested_fix: str = ""   # How to fix the reasoning pattern


@dataclass
class ReasoningStyle:
    """The agent's reasoning approach / style."""
    version: str  # e.g., "v1", "v2", "v3"
    name: str     # Human-readable name
    description: str
    prompts: dict[str, str] = field(default_factory=dict)
    focus_areas: list[str] = field(default_factory=list)
    known_weaknesses: list[str] = field(default_factory=list)
    improvements_over_previous: list[str] = field(default_factory=list)
    score_improvement: float = 0.0  # Points improvement from previous version


@dataclass
class ImprovementIteration:
    """One iteration of the reasoning improvement loop."""
    iteration: int
    reasoning_style: ReasoningStyle
    average_score: float
    error_catalog: list[ReasoningError] = field(default_factory=list)
    dimension_scores: dict[str, float] = field(default_factory=dict)
    what_worked: list[str] = field(default_factory=list)
    what_didnt_work: list[str] = field(default_factory=list)
    next_focus: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ══════════════════════════════════════════════════════════════════════
# Error Pattern Catalog
# ══════════════════════════════════════════════════════════════════════

# Pre-built catalog of common macro reasoning errors
# These are templates that get instantiated when the agent makes these mistakes

ERROR_PATTERNS = {
    "wrong_regime": {
        "root_cause": "Failing to correctly identify the macro regime context",
        "fix": "Always ask: what monetary regime, what growth regime, what inflation regime BEFORE predicting",
        "examples": [
            "Calling 'tightening' when policy is still accommodative",
            "Calling 'expansion' when leading indicators are rolling over",
            "Calling 'disinflation done' when shelter CPI still 5%",
        ],
    },
    "wrong_narrative": {
        "root_cause": "Missing or misunderstanding the dominant market narrative",
        "fix": "Identify the story the market is currently pricing, then test against data",
        "examples": [
            "Focusing on micro when macro narrative is dominant",
            "Trading old narrative when market has moved on",
            "Missing the 'soft landing' story during disinflation",
        ],
    },
    "wrong_causality": {
        "root_cause": "Incorrect cause-effect reasoning or reversed causality",
        "fix": "Trace each link in the chain: A→B→C. Verify direction with data.",
        "examples": [
            "Bond yields rising→recession (wrong: yields can rise on growth)",
            "QE→inflation (wrong in deflationary environment)",
            "Rate cuts→equities rally (wrong if cuts signal recession)",
        ],
    },
    "wrong_timing": {
        "root_cause": "Correct direction but wrong timing",
        "fix": "Add time window to every prediction. Specify: what needs to happen for this?",
        "examples": [
            "Correctly predicting recession but 2 years too early",
            "Calling dollar top correctly but 6 months before it happens",
            "Right on inflation peaking but wrong on how fast it falls",
        ],
    },
    "wrong_data": {
        "root_cause": "Used incorrect, incomplete, or misleading data",
        "fix": "Verify data sources. Cross-check with multiple indicators before concluding.",
        "examples": [
            "Using nominal data when real data reveals different picture",
            "Over-indexing on single data point without broader context",
            "Using lagging indicators to predict turning points",
        ],
    },
    "black_swan": {
        "root_cause": "Unpredictable exogenous event outside the model's scope",
        "fix": "Always consider tail risk scenarios. Use 'unknown unknowns' section.",
        "examples": [
            "COVID-19 or similar pandemic shocks",
            "Geopolitical events (wars, sanctions)",
            "Natural disasters with macro impact",
        ],
    },
    "correct": {
        "root_cause": "N/A — prediction was correct",
        "fix": "No fix needed. Analyze what went right.",
        "examples": [],
    },
    # Legacy aliases (used by _analyze_dimensions -> _create_error)
    "regime_misread": {
        "root_cause": "Failing to correctly identify the macro regime context",
        "fix": "Always ask: what monetary regime, what growth regime, what inflation regime BEFORE predicting",
        "examples": ["Calling 'tightening' when policy is still accommodative"],
    },
    "narrative_miss": {
        "root_cause": "Missing or misunderstanding the dominant market narrative",
        "fix": "Identify the story the market is currently pricing, then test against data",
        "examples": ["Focusing on micro when macro narrative is dominant"],
    },
    "causality_error": {
        "root_cause": "Incorrect cause-effect reasoning or reversed causality",
        "fix": "Trace each link in the chain: A→B→C. Verify direction with data.",
        "examples": ["Bond yields rising→recession (wrong: yields can rise on growth)"],
    },
    "evidence_weak": {
        "root_cause": "Conclusion not supported by sufficient data",
        "fix": "Each prediction must cite specific data points. No hand-waving.",
        "examples": [
            "Predicting recession because 'cycle is old' (not a data point)",
            "Calling bubble because 'prices are high' (need overvaluation evidence)",
            "Predicting currency move without rate differential analysis",
        ],
    },
    "timing_wrong": {
        "root_cause": "Correct direction but wrong timing",
        "fix": "Add time window to every prediction. Specify: what needs to happen for this?",
        "examples": [
            "Correctly predicting recession but 2 years too early",
            "Calling dollar top correctly but 6 months before it happens",
            "Right on inflation peaking but wrong on how fast it falls",
        ],
    },
    "framework_misapplication": {
        "root_cause": "Applying the wrong analytical framework to the situation",
        "fix": "Ask: what type of regime is this? Does the framework apply?",
        "examples": [
            "Using normal-cycle framework during structural regime change",
            "Applying DM framework to EM crisis",
            "Using valuation framework during liquidity-driven moves",
        ],
    },
    "overconfidence": {
        "root_cause": "Too certain about a single path when multiple are possible",
        "fix": "Force alternate scenario: 'What if I'm wrong?' Must list invalidation conditions.",
        "examples": [
            "95% confidence on a single outcome",
            "No alternative scenario listed",
            "Dismissing tail risks as impossible",
        ],
    },
    "data_ignorance": {
        "root_cause": "Ignoring or dismissing data that contradicts the narrative",
        "fix": "Must engage with contradictory data. Write 'the case against my view' section.",
        "examples": [
            "Ignoring rising initial claims because 'labor market is strong'",
            "Dismissing yield curve inversion because 'this time is different'",
            "Ignoring credit stress because 'equities are at ATH'",
        ],
    },
    "anchoring": {
        "root_cause": "Anchored to recent levels or previous predictions",
        "fix": "Re-evaluate from first principles each time. Forget prior view.",
        "examples": [
            "Still bullish because was bullish 6 months ago despite data change",
            "Expecting rates to stay low because they've been low for decade",
            "Anchored to CPI 2% when it's clearly going to 5%",
        ],
    },
    "confirmation": {
        "root_cause": "Seeking only confirming evidence, ignoring disconfirming",
        "fix": "For each prediction, actively search for evidence against it.",
        "examples": [
            "Only reading bullish analysts when long",
            "Dismissing contrary data as noise",
            "Fitting all data points into existing thesis",
        ],
    },
}


# ══════════════════════════════════════════════════════════════════════
# Reasoning Optimizer
# ══════════════════════════════════════════════════════════════════════


class ReasoningOptimizer:
    """Runs the reasoning improvement loop.

    NOT a prompt engineering tool. This is:
    1. Identify where agent thinks wrong
    2. Create targeted fix for that specific thinking error
    3. Test if fix improved score
    4. Track what worked
    """

    def __init__(self, history_dir: Optional[Path] = None):
        self.history_dir = history_dir or Path("validation/v9/optimization_history")
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.iterations: list[ImprovementIteration] = []
        self.styles: list[ReasoningStyle] = [
            self.default_style(),
            self.causal_heavy_style(),
        ]
        self.error_catalog: list[ReasoningError] = []
        self.current_style: Optional[ReasoningStyle] = None

    # ── Reasoning Styles ─────────────────────────────────────────────

    def default_style(self) -> ReasoningStyle:
        """Default v1 reasoning style — baseline macro framework."""
        return ReasoningStyle(
            version="v1",
            name="Standard Macro Analyst",
            description="Baseline multi-factor macro framework. "
                        "Analyzes monetary, fiscal, growth, inflation, "
                        "and positions within cycle framework.",
            prompts={
                "regime_prompt": (
                    "Identify the current macro regime. Consider:\n"
                    "1. Monetary policy stance (easing/tightening/neutral)\n"
                    "2. Growth trajectory (accelerating/decelerating/contracting)\n"
                    "3. Inflation dynamic (rising/falling/stable)\n"
                    "4. Fiscal impulse direction\n"
                    "5. Cross-asset signals"
                ),
                "narrative_prompt": (
                    "What is the dominant market narrative?\n"
                    "1. What story is driving asset prices right now?\n"
                    "2. What is the consensus view?\n"
                    "3. Is the narrative aligned with data or diverging?"
                ),
                "prediction_prompt": (
                    "Given the regime and narrative:\n"
                    "1. What is the most likely 3-6 month path?\n"
                    "2. What assets benefit? Which suffer?\n"
                    "3. What is the risk distribution (bull/bear/base)?\n"
                    "4. What specific data would invalidate this view?"
                ),
            },
            focus_areas=[
                "Monetary policy stance",
                "Growth momentum",
                "Inflation trajectory",
                "Market positioning",
            ],
            known_weaknesses=[
                "May over-weight recent data",
                "May miss narrative regime changes",
                "Timing precision needs improvement",
            ],
        )

    def causal_heavy_style(self) -> ReasoningStyle:
        """v2 — Emphasizes causal chain reasoning over description."""
        return ReasoningStyle(
            version="v2",
            name="Causal Chain Analyst",
            description="v2 improvement: Force agent to trace causal chains. "
                        "Every prediction must include A→B→C reasoning.",
            prompts={
                "regime_prompt": (
                    "Identify the macro regime by tracing the causal chain:\n"
                    "What caused current monetary policy stance?\n"
                    "What is causing the growth trajectory?\n"
                    "What is driving inflation?\n"
                    "Trace each from cause to effect."
                ),
                "narrative_prompt": (
                    "Identify the dominant market narrative by explaining:\n"
                    "What causal story is the market telling?\n"
                    "What evidence supports this story?\n"
                    "What evidence contradicts it?\n"
                    "How would the story change if key data shifts?"
                ),
                "prediction_prompt": (
                    "Make predictions by tracing causal chains:\n"
                    "1. If X happens → Y will happen → Z assets will respond\n"
                    "2. What is the probability of each link?\n"
                    "3. Where is the weakest link?\n"
                    "4. What alternative chain has highest probability?"
                ),
            },
            focus_areas=[
                "Causal chain identification",
                "Weakest-link analysis",
                "Contradictory evidence",  
                "Probability distribution over paths",
            ],
            known_weaknesses=[
                "May over-complicate simple situations",
                "Can get lost in chain complexity",
            ],
            improvements_over_previous=[
                "Adds explicit causal chain reasoning",
                "Forces identification of weakest link",
                "Requires alternative scenario",
            ],
            score_improvement=0.0,
        )

    def risk_aware_style(self) -> ReasoningStyle:
        """v3 — Emphasizes risk analysis and invalidation conditions."""
        return ReasoningStyle(
            version="v3",
            name="Risk-Aware Analyst",
            description="v3 improvement: Every view has explicit invalidation. "
                        "Force identification of what could go wrong.",
            prompts={
                "regime_prompt": (
                    "Identify the macro regime. For each assessment, answer:\n"
                    "1. What data supports this regime?\n"
                    "2. What data would indicate a DIFFERENT regime?\n"
                    "3. What is the regime CHANGE signal to watch?\n"
                    "4. How fast could regime change happen?"
                ),
                "narrative_prompt": (
                    "Identify the dominant narrative AND its vulnerability:\n"
                    "1. What story is priced in?\n"
                    "2. What would break this story?\n"
                    "3. What is the narrative transition signal?\n"
                    "4. What narrative is NOT being discussed (the blind spot)?"
                ),
                "prediction_prompt": (
                    "Make predictions with explicit risk bands:\n"
                    "1. Base case (60%): What happens if conditions continue\n"
                    "2. Bull case (20%): What positive surprise would do\n"
                    "3. Bear case (20%): What negative surprise would do\n"
                    "4. For EACH case: what specific trigger?\n"
                    "5. What is the invalidation condition for base case?"
                ),
            },
            focus_areas=[
                "Regime change signals",
                "Narrative vulnerability",
                "Explicit risk bands",
                "Invalidation conditions",
            ],
            known_weaknesses=[
                "Risk-analysis paralysis possible",
                "May overweight tail risks",
            ],
            improvements_over_previous=[
                "Adds mandatory invalidation conditions",
                "Forces bull/bear/base scenario framework",
                "Identifies narrative blind spots",
            ],
            score_improvement=0.0,
        )

    def v10_professional_style(self) -> ReasoningStyle:
        """V10 Professional Macro Researcher.
        
        The V10 style upgrade: 10-step mandatory reasoning chain,
        13-question methodology, professional sell-side writing standards,
        no generic explanations, no textbook answers, no simple summaries.
        
        This style targets the V10 acceptance criteria:
        - Blind Test >=80%
        - Expert Similarity >=85%
        - Memo Quality >=90/100
        - ECE < 0.10
        - Hallucination Rate <2%
        """
        return ReasoningStyle(
            version="v10",
            name="Professional Macro Researcher (V10)",
            description="V10 upgrade: 10-step mandatory reasoning chain, "
                        "13-question methodology, professional institutional writing. "
                        "No generic explanations, no textbook answers, no simple summaries. "
                        "Output comparable to sell-side macro research.",
            prompts={
                "research_methodology": (
                    "Answer these 13 questions in order — DO NOT skip any:\n"
                    "1. What happened? (objective data, no judgment)\n"
                    "2. Why? (first-layer causal chain)\n"
                    "3. Why now? (timing analysis)\n"
                    "4. Who benefits? (specific assets, sectors, investors)\n"
                    "5. Who loses? (specific losers and chain reactions)\n"
                    "6. Market expectation? (what's priced in vs your view)\n"
                    "7. Second-order effects? (A→B triggered what C?)\n"
                    "8. Third-order effects? (institutional/structural changes)\n"
                    "9. Consensus? (where is market consensus)\n"
                    "10. Crowded trade? (what positioning is consensus)\n"
                    "11. Catalysts? (what accelerates/reverses trend)\n"
                    "12. Tail risks? (extreme scenarios, both tails)\n"
                    "13. How can I be wrong? (most likely invalidation)"
                ),
                "writing_standards": (
                    "PROHIBITED:\n"
                    "- Generic explanations ('inflation is caused by supply and demand')\n"
                    "- Textbook answers ('monetary policy operates through interest rates')\n"
                    "- Simple summaries (just listing data without causal connections)\n\n"
                    "REQUIRED:\n"
                    "- Specific data citations with causal links\n"
                    "- Trader language (carry trade, pain trade, crowded positioning, gamma squeeze)\n"
                    "- Every judgment: direction + confidence + timeframe + stop-loss\n"
                    "- Counter-evidence for every major claim\n"
                    "- Probability table for scenarios"
                ),
                "output_standards": (
                    "Output must contain ALL 13 sections — no skipping:\n"
                    "1. Executive Summary (300 words, standalone readable)\n"
                    "2. One-Sentence Core View\n"
                    "3. Current Regime (classification + transition risk + historical analog)\n"
                    "4. Key Narratives (dominant + competing + stage + crowdedness)\n"
                    "5. Causal Chain (5-8 steps + second-order + third-order)\n"
                    "6. Evidence Assessment (supporting vs contradicting + net weight)\n"
                    "7. Counter Evidence (why I could be wrong)\n"
                    "8. Alternative Scenarios (probability distribution)\n"
                    "9. Historical Analogies (2-3 periods with similarity scores)\n"
                    "10. Portfolio/Trade Implications (direction + confidence + timeframe + stop)\n"
                    "11. Risk & Falsification (fatal/major/minor severities)\n"
                    "12. Unknowns (known unknowns + possible blind spots)\n"
                    "13. Probability Table (multi-scenario with key trigger conditions)"
                ),
            },
            focus_areas=[
                "10-step mandatory reasoning chain",
                "13-question professional methodology",
                "Institutional writing quality (Bridgewater/GS/MS)",
                "Counter-argument coverage 100%",
                "Historical analogies with similarity scores",
                "Actionable trade recommendations",
                "Probability-calibrated scenarios",
            ],
            known_weaknesses=[
                "May over-explain in straightforward situations",
                "Requires LLM with strong reasoning capabilities",
                "Trade recommendations may lack execution detail",
            ],
            improvements_over_previous=[
                "10-step mandatory reasoning chain (vs 3 styles)",
                "13-question methodology with no skip enforcement",
                "Professional writing: no generic/textbook/simple outputs",
                "100% counter-argument coverage requirement",
                "Historical analogy similarity scoring",
                "Probability table with key trigger conditions",
                "Trader/PM language requirements for actionable output",
            ],
            score_improvement=0.0,
        )

    # ── Auto-Improvement Loop (V10) ───────────────────────────────────
    
    def auto_improve(
        self,
        agent_fn,
        sample_cases: list,
        max_iterations: int = 3,
        target_score: float = 80.0,
    ) -> list[ImprovementIteration]:
        """V10: Automated reasoning improvement loop.
        
        Runs the reasoning optimizer against historical cases, analyzes
        failures, and iterates reasoning styles until target score reached
        or max iterations exhausted.
        
        This is Phase E: Benchmark Improvement Loop.
        
        Args:
            agent_fn: The agent research function (e.g. v10_agent_research)
            sample_cases: List of HistoricalCase for testing
            max_iterations: Max style iterations before stopping
            target_score: Stop when average score reaches this
            
        Returns:
            List of ImprovementIteration results
        """
        from validation.v9.blind_test import (
            BlindTestRunner, BlindTestSuite,
        )
        
        # Start with default style, then try upgrades
        styles = [
            self.default_style(),        # v1: baseline
            self.causal_heavy_style(),   # v2: causal chains
            self.risk_aware_style(),     # v3: risk + invalidation
            self.v10_professional_style(), # v10: professional
        ]
        
        results = []
        
        for style in styles:
            if len(results) >= max_iterations:
                break
            
            # Build test suite
            suite = BlindTestSuite(name=f"Iteration {len(results)+1}: {style.name}")
            from validation.v9.blind_test import BlindTestCase
            for case in sample_cases:
                suite.add_case(BlindTestCase(
                    case=case,
                    blind_prompt={
                        "date": case.date,
                        "title": case.title,
                        "macro_regime": {
                            "monetary": case.monetary,
                            "fiscal": case.fiscal,
                            "growth": case.growth,
                            "inflation": case.inflation,
                            "volatility": case.volatility,
                        },
                        "starting_conditions": case.starting_conditions,
                        "market_beliefs_at_time": case.market_beliefs_at_time,
                    },
                ))
            
            # Run agent
            agent_outputs = [agent_fn(tc.blind_prompt) for tc in suite.cases]
            
            # Score
            runner = BlindTestRunner(agent_fn=agent_fn)
            suite = runner.run_suite(suite, agent_outputs=agent_outputs)
            
            # Analyze
            iteration = self.run_iteration(
                style=style,
                agent_fn=agent_fn,
                test_results=suite.results,
                agent_outputs=agent_outputs,
                cases=[tc.case for tc in suite.cases],
            )
            
            results.append(iteration)
            
            # Check convergence
            if iteration.average_score >= target_score:
                break
        
        return results
    
    def convergence_report(self, iterations: list[ImprovementIteration]) -> str:
        """Generate a convergence report from improvement iterations."""
        if not iterations:
            return "No iterations to report."
        
        lines = [
            "=" * 60,
            "V10 Reasoning Improvement Convergence Report",
            "=" * 60,
            "",
        ]
        
        for it in iterations:
            score_str = f"{it.average_score:.1f}"
            status = "TARGET" if it.average_score >= 80 else "IMPROVING"
            lines.append(
                f"  v{it.iteration} [{it.reasoning_style.name}]: "
                f"{score_str}/100 [{status}]"
            )
            if it.what_worked:
                for w in it.what_worked[:2]:
                    lines.append(f"    + {w}")
            if it.what_didnt_work:
                for w in it.what_didnt_work[:2]:
                    lines.append(f"    - {w}")
        
        if iterations[-1].average_score >= 80:
            lines.append(f"\n  CONVERGED: Target >=80% reached at iteration {len(iterations)}")
        else:
            lines.append(f"\n  NO CONVERGENCE: Best score {iterations[-1].average_score:.1f}. Next: {iterations[-1].next_focus}")
        
        lines.append("")
        return "\n".join(lines)

    # ── Error Detection ──────────────────────────────────────────────

    def analyze_errors(
        self,
        agent_outputs: list[dict],
        test_results: list[BlindTestResult],
        cases: list[HistoricalCase],
    ) -> list[ReasoningError]:
        """Analyze agent outputs to find reasoning errors.

        Maps agent's wrong answers to specific error patterns.
        """
        errors = []

        for ao, tr, case in zip(agent_outputs, test_results, cases):
            # Skip high-scoring results
            if tr.total_score >= 85:
                continue

            # Check each dimension
            dim_errors = self._analyze_dimensions(tr, case, ao)
            errors.extend(dim_errors)

        # Aggregate similar errors
        aggregated = self._aggregate_errors(errors)
        self.error_catalog.extend(aggregated)
        return aggregated

    def _analyze_dimensions(
        self,
        result: BlindTestResult,
        case: HistoricalCase,
        ao: dict,
    ) -> list[ReasoningError]:
        """Analyze which dimensions had errors and classify them."""
        errors = []

        # BlindTestResult has individual dimension fields, not a dict
        dim_scores = {
            "regime_recognition": result.regime_recognition.score if hasattr(result, 'regime_recognition') else 10,
            "narrative_identification": result.narrative_identification.score if hasattr(result, 'narrative_identification') else 10,
            "causal_reasoning": result.causal_reasoning.score if hasattr(result, 'causal_reasoning') else 10,
            "prediction_accuracy": result.prediction_accuracy.score if hasattr(result, 'prediction_accuracy') else 10,
            "risk_awareness": result.risk_awareness.score if hasattr(result, 'risk_awareness') else 10,
        }

        dim_map = {
            "regime_recognition": "regime_misread",
            "narrative_identification": "narrative_miss",
            "causal_reasoning": "causality_error",
            "prediction_accuracy": "evidence_weak",
            "risk_awareness": "data_ignorance",
        }

        for dim_name, error_type in dim_map.items():
            dim_score = dim_scores.get(dim_name, 10)

            if dim_score < 12:  # Below 60% on this dimension = significant error
                error = self._create_error(
                    error_type=error_type,
                    case=case,
                    ao=ao,
                    dim_score=dim_score,
                )
                if error:
                    errors.append(error)

        # Check for overconfidence
        confidence_raw = ao.get("confidence", 0.5)
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.5

        if confidence > 0.9 and result.total_score < 70:
            errors.append(ReasoningError(
                error_id=f"err_{case.case_id}_overconfidence",
                error_type="overconfidence",
                description=f"Overconfident: {confidence:.0%} confidence but scored {result.total_score}",
                case_id=case.case_id,
                agent_wrong_thought=f"Was {confidence:.0%} confident in prediction",
                correct_thought="Should have assigned lower confidence given uncertainty",
                severity=min(0.8, confidence),
                root_cause=ERROR_PATTERNS["overconfidence"]["root_cause"],
                suggested_fix=ERROR_PATTERNS["overconfidence"]["fix"],
            ))

        return errors

    def _create_error(
        self,
        error_type: str,
        case: HistoricalCase,
        ao: dict,
        dim_score: float,
    ) -> Optional[ReasoningError]:
        """Create a reasoning error from pattern template."""
        pattern = ERROR_PATTERNS.get(error_type)
        if not pattern:
            return None

        severity = max(0.3, 1.0 - dim_score / 20.0)

        return ReasoningError(
            error_id=f"err_{case.case_id}_{error_type}",
            error_type=error_type,
            description=f"{error_type} on case {case.case_id}: {case.title[:80]}",
            case_id=case.case_id,
            agent_wrong_thought=ao.get("regime", ao.get("narrative", ""))[:100],
            correct_thought=case.expert_view[:200],
            severity=severity,
            root_cause=pattern["root_cause"],
            suggested_fix=pattern["fix"],
        )

    def _aggregate_errors(self, errors: list[ReasoningError]) -> list[ReasoningError]:
        """Aggregate similar errors by type."""
        from collections import Counter
        type_counter = Counter(e.error_type for e in errors)

        aggregated = []
        seen_types = set()
        for error in errors:
            error.frequency = type_counter[error.error_type]
            if error.error_type not in seen_types:
                seen_types.add(error.error_type)
                aggregated.append(error)
            else:
                # Add to existing aggregated entry
                for agg in aggregated:
                    if agg.error_type == error.error_type:
                        agg.severity = max(agg.severity, error.severity)
                        agg.frequency = type_counter[error.error_type]
                        break

        return aggregated

    # ── Improvement Loop ─────────────────────────────────────────────

    def run_iteration(
        self,
        style: ReasoningStyle,
        agent_fn,
        test_results: list[BlindTestResult],
        agent_outputs: list[dict],
        cases: list[HistoricalCase],
    ) -> ImprovementIteration:
        """Run one iteration of the reasoning improvement loop.

        1. Run test with current style
        2. Analyze errors  
        3. Generate improvement recommendations
        4. Track what changed
        """
        avg_score = sum(tr.total_score for tr in test_results) / len(test_results) if test_results else 0

        # Analyze errors
        errors = self.analyze_errors(agent_outputs, test_results, cases)

        # Extract dimension scores from individual fields
        dim_scores = {}
        if test_results:
            dim_fields = ["regime_recognition", "narrative_identification",
                         "causal_reasoning", "prediction_accuracy", "risk_awareness"]
            for field_name in dim_fields:
                scores = []
                for r in test_results:
                    dim_obj = getattr(r, field_name, None)
                    if dim_obj and hasattr(dim_obj, 'score'):
                        scores.append(dim_obj.score)
                dim_scores[field_name] = sum(scores) / len(scores) if scores else 0

        # Determine what worked
        prev_avg = self.iterations[-1].average_score if self.iterations else 0
        what_worked, what_didnt = self._evaluate_changes(style, avg_score, prev_avg, errors)

        # Determine next focus
        next_focus = self._determine_next_focus(errors, dim_scores)

        iteration = ImprovementIteration(
            iteration=len(self.iterations) + 1,
            reasoning_style=style,
            average_score=avg_score,
            error_catalog=errors,
            dimension_scores=dim_scores,
            what_worked=what_worked,
            what_didnt_work=what_didnt,
            next_focus=next_focus,
        )

        self.iterations.append(iteration)
        self.current_style = style
        return iteration

    def _evaluate_changes(
        self,
        style: ReasoningStyle,
        current_score: float,
        previous_score: float,
        errors: list[ReasoningError],
    ) -> tuple[list[str], list[str]]:
        """Evaluate what worked and what didn't in this iteration."""
        what_worked = []
        what_didnt = []

        if current_score > previous_score:
            improvement = current_score - previous_score
            what_worked.append(f"Score improved +{improvement:.1f} points with {style.name}")
            style.score_improvement = improvement

            if style.improvements_over_previous:
                what_worked.append(f"Key changes: {', '.join(style.improvements_over_previous)}")
        else:
            what_didnt.append(f"No improvement: {style.name} scored {current_score} vs previous {previous_score}")

        # Check if specific error types decreased
        if self.iterations:
            prev_errors = self.iterations[-1].error_catalog
            prev_types = {e.error_type for e in prev_errors}
            curr_types = {e.error_type for e in errors}
            resolved = prev_types - curr_types
            new = curr_types - prev_types

            if resolved:
                what_worked.append(f"Resolved error types: {', '.join(resolved)}")
            if new:
                what_didnt.append(f"New error types appeared: {', '.join(new)}")

        # Identify persistent errors
        persistent = [e for e in errors if e.frequency and e.frequency >= 3]
        if persistent:
            what_didnt.append(
                f"Persistent errors (>3 occurrences): {', '.join(e.error_type for e in persistent)}"
            )

        return what_worked, what_didnt

    def _determine_next_focus(
        self,
        errors: list[ReasoningError],
        dim_scores: dict[str, float],
    ) -> str:
        """Determine what to focus on in the next iteration."""
        if not errors and not dim_scores:
            return "Maintain: Continue testing and monitoring"

        # Find weakest dimension
        if dim_scores:
            weakest = min(dim_scores.items(), key=lambda x: x[1])
            weakest_name = weakest[0].replace("_", " ").title()
        else:
            weakest_name = None

        # Find most common error type
        from collections import Counter
        if errors:
            top_error = Counter(e.error_type for e in errors).most_common(1)[0][0]
        else:
            top_error = None

        parts = []
        if top_error:
            fix = ERROR_PATTERNS.get(top_error, {}).get("fix", "Target this error pattern")
            parts.append(f"Focus: {top_error} — {fix[:80]}")
        if weakest_name:
            parts.append(f"Weakest dimension: {weakest_name}")
        if not parts:
            parts.append("No clear weakness — refine edge cases")

        return " | ".join(parts)

    # ── History & Reporting ──────────────────────────────────────────

    def iteration_history(self) -> str:
        """Generate a history of all iterations with scores."""
        lines = [
            "Reasoning Optimization History",
            "===============================",
        ]
        for it in self.iterations:
            delta = ""
            if it.iteration > 1:
                prev = self.iterations[it.iteration - 2].average_score
                change = it.average_score - prev
                delta = f" ({'+' if change >=0 else ''}{change:.1f})"
            lines.append(
                f"  v{it.iteration} [{it.reasoning_style.name}] "
                f"Score: {it.average_score:.1f}{delta}"
            )
            for w in it.what_worked:
                lines.append(f"    ✓ {w}")
            for w in it.what_didnt_work:
                lines.append(f"    ✗ {w}")

        return "\n".join(lines)

    def error_summary(self) -> str:
        """Summarize all errors found across iterations."""
        if not self.error_catalog:
            return "No errors analyzed yet."

        lines = ["Error Pattern Summary", "===================="]
        from collections import Counter

        # Normalize error types: handle both ErrorDiagnosis (ErrorType enum) and ReasoningError (str)
        normalized = []
        for e in self.error_catalog:
            if hasattr(e, "primary_error"):
                # ErrorDiagnosis from prediction_calibration
                normalized.append(e.primary_error.value)
            elif hasattr(e, "error_type"):
                # ReasoningError from self._create_error
                et = e.error_type if isinstance(e.error_type, str) else getattr(e.error_type, "value", str(e.error_type))
                normalized.append(et)

        type_counts = Counter(normalized)

        for error_type, count in type_counts.most_common():
            pattern = ERROR_PATTERNS.get(error_type, {})
            lines.append(
                f"\n  {error_type} ({count} occurrences):\n"
                f"    Cause: {pattern.get('root_cause', 'N/A')[:100]}\n"
                f"    Fix:   {pattern.get('fix', 'N/A')[:100]}"
            )

        return "\n".join(lines)

    def generate_improvement_plan(self) -> str:
        """Generate the next improvement plan based on current state."""
        if not self.iterations:
            return "No iterations run yet. Start with default style."

        last = self.iterations[-1]
        lines = [
            "Next Improvement Plan",
            "====================",
            f"Current Style: {last.reasoning_style.name} (v{last.iteration})",
            f"Current Score: {last.average_score:.1f}",
            f"Next Focus: {last.next_focus}",
            "",
            "Recommended Changes:",
        ]

        for error in last.error_catalog[:5]:
            lines.append(f"  - Fix {error.error_type}: {error.suggested_fix}")

        return "\n".join(lines)

    def save_history(self):
        """Save optimization history to file."""
        import json

        def _safe_error_type(e):
            if hasattr(e, 'primary_error'):
                return e.primary_error.value
            if hasattr(e, 'error_type'):
                et = e.error_type
                return et if isinstance(et, str) else str(et)
            return str(e)

        def _safe_frequency(e):
            return getattr(e, 'frequency', 1)

        filepath = self.history_dir / f"optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data = {
            "styles": [{"version": s.version, "name": s.name, "description": s.description}
                      for s in self.styles],
            "iterations": [
                {
                    "iteration": it.iteration,
                    "style": it.reasoning_style.version,
                    "score": it.average_score,
                    "top_errors": [_safe_error_type(e) for e in it.error_catalog[:3]],
                    "focus": it.next_focus,
                }
                for it in self.iterations
            ],
            "error_summary": {_safe_error_type(e): _safe_frequency(e) for e in self.error_catalog},
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        return filepath


# ══════════════════════════════════════════════════════════════════════
# Version History Tracker
# ══════════════════════════════════════════════════════════════════════

VERSION_EVOLUTION = {
    "v1": "Standard Macro Analyst — baseline multi-factor framework",
    "v2": "Causal Chain Analyst — forces causal chain reasoning",
    "v3": "Risk-Aware Analyst — invalidation conditions, risk bands",
    "v10": "Professional Macro Researcher — 10-step chain, 13-question methodology, institutional quality",
}

# Usage pattern:
#
#   1. Start with v1 (default style)
#   2. Run blind test benchmark
#   3. Analyze errors → identify most common error pattern
#   4. Create v2 targeting that pattern
#   5. Repeat until score ≥ 75 on blind test
#
#   This is NOT prompt engineering — it's reasoning diagnosis.
#   Each version fixes specific thinking errors, not adds more instructions.
