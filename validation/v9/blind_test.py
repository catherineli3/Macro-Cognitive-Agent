# =============================================================================
# V9 Blind Research Test — Run Agent Against History Without Knowing Outcomes
# =============================================================================
# Core workflow:
#   1. Take historical case at date T (only give data available at T)
#   2. Agent produces: regime, narrative, beliefs, prediction, risk, invalidation, asset
#   3. Score against actual outcome using 5-dimension 100-point framework
#   4. Aggregate across many cases for capability assessment
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from validation.v9.historical_cases import HistoricalCase, CASES, _ensure_loaded
from validation.v9.scoring_engine import (
    MacroUnderstandingScorer,
    BlindTestResult,
    DimensionScore,
)


@dataclass
class BlindTestCase:
    """A single blind test case: agent sees only date + conditions, not outcome."""
    case: HistoricalCase

    @property
    def blind_prompt(self) -> dict:
        """What agent sees — no outcome, no expert view."""
        return {
            "date": self.case.date,
            "title": self.case.title,
            "macro_regime": self.case.macro_regime,
            "starting_conditions": self.case.starting_conditions,
            "market_beliefs_at_time": self.case.market_beliefs,
            # Agent does NOT see: dominant_narrative, expert_view, actual_outcome, asset_reaction
        }


@dataclass
class BlindTestSuite:
    """Collection of blind test cases with aggregate results."""
    name: str
    cases: list[BlindTestCase] = field(default_factory=list)
    results: list[BlindTestResult] = field(default_factory=list)

    def add_cases(self, historical_cases: list[HistoricalCase]):
        for c in historical_cases:
            self.cases.append(BlindTestCase(case=c))

    @property
    def total_tests(self) -> int:
        return len(self.results)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.passed) / len(self.results)

    @property
    def average_score(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.total_score for r in self.results) / len(self.results)

    @property
    def dimension_averages(self) -> dict:
        """Average score per dimension across all tests."""
        if not self.results:
            return {}
        n = len(self.results)
        return {
            "regime_recognition": sum(r.regime_recognition.score for r in self.results) / n,
            "narrative_identification": sum(r.narrative_identification.score for r in self.results) / n,
            "causal_reasoning": sum(r.causal_reasoning.score for r in self.results) / n,
            "prediction_accuracy": sum(r.prediction_accuracy.score for r in self.results) / n,
            "risk_awareness": sum(r.risk_awareness.score for r in self.results) / n,
        }

    @property
    def grade_distribution(self) -> dict:
        """Count of results by grade."""
        dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        for r in self.results:
            dist[r.grade] += 1
        return dist

    def summary(self) -> str:
        """One-page summary of blind test suite results."""
        dims = self.dimension_averages
        grades = self.grade_distribution
        lines = [
            f"Blind Test Suite: {self.name}",
            f"{'─'*60}",
            f"Total Tests: {self.total_tests}",
            f"Average Score: {self.average_score:.1f}/100",
            f"Pass Rate (≥70): {self.pass_rate:.1%}",
            f"",
            f"Dimension Averages:",
            f"  Regime Recognition:      {dims.get('regime_recognition', 0):.1f}/20",
            f"  Narrative Identification: {dims.get('narrative_identification', 0):.1f}/20",
            f"  Causal Reasoning:        {dims.get('causal_reasoning', 0):.1f}/20",
            f"  Prediction Accuracy:     {dims.get('prediction_accuracy', 0):.1f}/20",
            f"  Risk Awareness:          {dims.get('risk_awareness', 0):.1f}/20",
            f"",
            f"Grade Distribution:",
            f"  A (90-100): {grades['A']} | B (80-89): {grades['B']}",
            f"  C (70-79):  {grades['C']} | D (60-69): {grades['D']}",
            f"  F (<60):    {grades['F']}",
            f"",
            f"V9 Target: ≥70 average | Current: {'PASS' if self.average_score >= 70 else 'FAIL'}",
        ]
        return "\n".join(lines)


class BlindTestRunner:
    """Runs agent through historical cases without revealing outcomes.

    This is the core V9 validation: can agent reason from first principles
    about a historical moment, matching or exceeding expert analysis?
    """

    def __init__(self, agent_fn: Optional[Callable] = None):
        """Initialize with optional agent research function.

        agent_fn(dict) -> dict with keys: regime, narrative, beliefs,
        prediction, risk, invalidation, asset_implication
        """
        self.agent_fn = agent_fn
        self.scorer = MacroUnderstandingScorer()

    def run_single(self, test_case: BlindTestCase,
                   agent_output: Optional[dict] = None) -> BlindTestResult:
        """Run a single blind test case."""
        if agent_output is None and self.agent_fn:
            agent_output = self.agent_fn(test_case.blind_prompt)
        elif agent_output is None:
            agent_output = {}  # Empty output for scoring

        # Build expert ground truth from case
        expert = {
            "regime": self._build_expert_regime(test_case.case),
            "regime_description": test_case.case.macro_regime.get("description", ""),
            "dominant_narrative": test_case.case.dominant_narrative,
            "competing_narratives": test_case.case.competing_narratives,
            "market_beliefs": test_case.case.market_beliefs,
            "causal_chain": test_case.case.causal_chain,
            "actual_outcome": test_case.case.actual_outcome,
            "asset_reaction": test_case.case.asset_reaction,
            "key_risks": test_case.case.key_risks,
            "unknowns": test_case.case.unknowns,
        }

        return self.scorer.score_full(
            case_id=test_case.case.case_id,
            case_date=test_case.case.date,
            case_title=test_case.case.title,
            agent_output=agent_output,
            expert_ground_truth=expert,
        )

    def run_suite(self, suite: BlindTestSuite,
                  agent_outputs: Optional[list[dict]] = None) -> BlindTestSuite:
        """Run all cases in a test suite."""
        results = []
        for i, tc in enumerate(suite.cases):
            ao = agent_outputs[i] if agent_outputs and i < len(agent_outputs) else None
            result = self.run_single(tc, agent_output=ao)
            results.append(result)
        suite.results = results
        return suite

    @staticmethod
    def build_turning_point_suite() -> BlindTestSuite:
        """Build suite of regime-change / turning point cases."""
        _ensure_loaded()
        tc_cases = [c for c in CASES if c.is_turning_point]
        suite = BlindTestSuite(name="Turning Points (Regime Change)")
        suite.add_cases(tc_cases)
        return suite

    @staticmethod
    def build_cycle_suite(cycle_name: str) -> BlindTestSuite:
        """Build suite for a specific macro cycle."""
        _ensure_loaded()
        from validation.v9.historical_cases import MacroCycle
        cycle = MacroCycle(cycle_name)
        cases = [c for c in CASES if c.cycle == cycle]
        suite = BlindTestSuite(name=f"{cycle_name.upper()} Cycle")
        suite.add_cases(cases)
        return suite

    @staticmethod
    def build_difficulty_suite(difficulty: str) -> BlindTestSuite:
        """Build suite filtered by difficulty level."""
        _ensure_loaded()
        cases = [c for c in CASES if c.difficulty == difficulty]
        suite = BlindTestSuite(name=f"{difficulty.upper()} Cases")
        suite.add_cases(cases)
        return suite

    @staticmethod
    def build_full_suite() -> BlindTestSuite:
        """Build suite with ALL 100+ cases."""
        _ensure_loaded()
        suite = BlindTestSuite(name="Full 100+ Case Benchmark")
        suite.add_cases(CASES)
        return suite

    def _build_expert_regime(self, case: HistoricalCase) -> dict:
        """Convert case regime to expert format for scoring."""
        return {
            "monetary": case.macro_regime.get("monetary", ""),
            "fiscal": case.macro_regime.get("fiscal", ""),
            "growth": case.macro_regime.get("growth", ""),
            "inflation": case.macro_regime.get("inflation", ""),
            "volatility": case.macro_regime.get("volatility", ""),
            "description": case.macro_regime.get("description", ""),
            "narrative": case.dominant_narrative,
        }


# ── V10 Real Agent Adapter — Replaces simulate_agent_research ────────
# Connects the V9 blind test framework to the real ResearchReasoningAgent
# with full LLM reasoning. Falls back to rule-based reasoning when LLM unavailable.

_V10_AGENT_INSTANCE = None
_V10_AGENT_AVAILABLE = None


def _get_v10_agent():
    """Lazy-initialize the V10 research agent (ResearchReasoningAgent)."""
    global _V10_AGENT_INSTANCE, _V10_AGENT_AVAILABLE
    if _V10_AGENT_INSTANCE is not None:
        return _V10_AGENT_INSTANCE, _V10_AGENT_AVAILABLE

    try:
        from src.research.llm_brain.research_reasoning_agent import (
            ResearchReasoningAgent,
            ReasoningInput,
        )
        from src.research.llm_brain.prompts import PromptArchitecture

        # Use V10 professional prompts
        prompts = PromptArchitecture()

        agent = ResearchReasoningAgent(
            model="gpt-4o",
            temperature=0.3,
            max_tokens=4096,
            reasoning_mode="llm",
            prompt_architecture=prompts,
        )
        _V10_AGENT_INSTANCE = agent
        _V10_AGENT_AVAILABLE = agent.llm_available
        return agent, agent.llm_available
    except Exception as e:
        import sys
        print(f"[V10] ResearchReasoningAgent init failed: {e}", file=sys.stderr)
        _V10_AGENT_INSTANCE = None
        _V10_AGENT_AVAILABLE = False
        return None, False


def _blind_prompt_to_reasoning_input(blind_input: dict) -> "ReasoningInput":
    """Convert V9 blind_test prompt dict to V3.4 ReasoningInput for LLM agent."""
    from src.research.llm_brain.research_reasoning_agent import ReasoningInput

    date = blind_input.get("date", "")
    title = blind_input.get("title", "")
    regime = blind_input.get("macro_regime", {})
    conditions = blind_input.get("starting_conditions", {})
    beliefs_text = blind_input.get("market_beliefs_at_time", "")

    # Map regime codes to descriptors
    regime_label = _decode_regime(regime)

    # Build market summary from conditions
    market_parts = []
    for k, v in conditions.items():
        market_parts.append(f"  {k}: {v}")
    market_summary = "\n".join(market_parts)

    # Extract beliefs as list
    core_beliefs = [b.strip() for b in beliefs_text.split(".") if b.strip()] if beliefs_text else []

    return ReasoningInput(
        regime_label=regime_label,
        regime_confidence=0.7,
        regime_dimensions={
            "monetary": regime.get("monetary", ""),
            "fiscal": regime.get("fiscal", ""),
            "growth": regime.get("growth", ""),
            "inflation": regime.get("inflation", ""),
            "volatility": regime.get("volatility", ""),
        },
        market_indicators=conditions,
        market_summary=market_summary,
        dominant_narrative=beliefs_text[:200],
        narrative_confidence=0.6,
        narrative_stage="unknown",
        competing_narratives=[],
        core_beliefs=core_beliefs,
        belief_confidence=0.6,
        active_mental_models=["Dalio Economic Machine", "Bridgewater All-Weather", "Soros Reflexivity", "PTJ Positioning"],
        judgment_text=f"Blind historical analysis at {date}: {title}",
        judgment_confidence=0.5,
        falsification_conditions=[],
        timestamp=date,
        case_id=f"v10_blind_{date}",
        historical_context=f"Historical case study — analyze as if you are at {date} with only data available at that time. {title}",
        recent_events=[],
        blind_test_date=date,
        blind_test_title=title,
    )


def _decode_regime(regime: dict) -> str:
    """Decode single-letter regime codes into human-readable label."""
    codes = {
        "monetary": {"T": "Tightening", "N": "Neutral", "E": "Easing", "X": "Extreme Easing"},
        "fiscal": {"N": "Neutral", "E": "Expansionary", "X": "Extreme Expansionary", "A": "Austerity"},
        "growth": {"S": "Strong", "N": "Normal", "D": "Decelerating", "R": "Recession", "A": "Accelerating"},
        "inflation": {"H": "High", "N": "Normal", "L": "Low", "R": "Rising", "F": "Falling"},
        "volatility": {"H": "High", "M": "Medium", "L": "Low"},
    }
    parts = []
    for dim, code_map in codes.items():
        code = regime.get(dim, "")
        label = code_map.get(code, code)
        parts.append(f"{dim}={label}")
    return " / ".join(parts)


def _memo_to_agent_output(memo) -> dict:
    """Convert ResearchMemo to the 7-field dict expected by blind test scorer."""
    # Extract beliefs from belief synthesis
    beliefs = []
    if memo.belief.core_belief:
        beliefs.append(memo.belief.core_belief)
    if memo.belief.highest_conviction_view:
        beliefs.append(memo.belief.highest_conviction_view)

    # Build regime string
    r = memo.regime
    regime_str = (
        f"Regime: {r.regime_label} (confidence: {r.regime_confidence:.2f}). "
        f"Growth: {r.growth_assessment}, Inflation: {r.inflation_assessment}, "
        f"Monetary: {r.monetary_assessment}. Transition risk: {r.regime_transition_risk:.2f}"
    )

    # Build prediction from assets + belief
    prediction = memo.one_sentence_view or memo.executive_summary[:300]
    if memo.assets.highest_conviction_trades:
        prediction += f" | Highest conviction: {memo.assets.highest_conviction_trades[0]}"

    # Build risk from tail risk + falsification
    risks = []
    if memo.falsification.falsification_conditions:
        for fc in memo.falsification.falsification_conditions[:3]:
            cond = fc.get("condition", str(fc))
            risks.append(cond)
    if memo.tail_risk.tail_risks:
        for tr in memo.tail_risk.tail_risks[:2]:
            risk_desc = tr.get("risk", str(tr))
            risks.append(risk_desc)
    risk_str = "; ".join(risks) if risks else memo.tail_risk.fat_tail_assessment

    # Build invalidation conditions
    invalidation = memo.falsification.base_case_if_wrong or ""
    if not invalidation and memo.falsification.falsification_conditions:
        invalidation = " | ".join(
            fc.get("condition", str(fc))
            for fc in memo.falsification.falsification_conditions[:3]
        )

    # Asset implication
    asset_parts = []
    if memo.assets.regime_favored_assets:
        asset_parts.append(f"Favored: {', '.join(memo.assets.regime_favored_assets[:5])}")
    if memo.assets.regime_unfavored_assets:
        asset_parts.append(f"Unfavored: {', '.join(memo.assets.regime_unfavored_assets[:5])}")
    asset_str = "; ".join(asset_parts) if asset_parts else memo.assets.portfolio_positioning

    return {
        "regime": regime_str,
        "narrative": memo.narrative.dominant_narrative[:500] if memo.narrative.dominant_narrative else memo.executive_summary[:300],
        "beliefs": beliefs if beliefs else ["Analysis from first principles"],
        "prediction": prediction,
        "risk": risk_str,
        "invalidation": invalidation,
        "asset_implication": asset_str,
        "confidence": memo.confidence.overall_confidence,
        "conviction_level": memo.conviction_level,
        "executive_summary": memo.executive_summary,
        "reasoning_mode": memo.reasoning_mode,
        "llm_model": memo.llm_model,
    }


# ══════════════════════════════════════════════════════════════════════
# V10 Agent Research — Real LLM reasoning, replaces simulate_agent_research
# ══════════════════════════════════════════════════════════════════════

def v10_agent_research(blind_input: dict) -> dict:
    """Real agent research using LLM reasoning via ResearchReasoningAgent.

    This REPLACES simulate_agent_research with actual LLM-powered analysis.
    Falls back to rule-based reasoning when LLM is unavailable.

    Args:
        blind_input: dict with date, title, macro_regime, starting_conditions,
                     market_beliefs_at_time — only data available at historical moment.

    Returns:
        dict with regime, narrative, beliefs, prediction, risk, invalidation,
        asset_implication, confidence, conviction_level, executive_summary,
        reasoning_mode, llm_model.
    """
    agent, llm_available = _get_v10_agent()

    # Build ReasoningInput from blind prompt
    try:
        reasoning_input = _blind_prompt_to_reasoning_input(blind_input)
    except Exception as e:
        import sys
        print(f"[V10] Failed to build ReasoningInput: {e}", file=sys.stderr)
        return _v10_fallback_output(blind_input, f"input_build_error: {e}")

    # If agent is available, use real reasoning
    if agent is not None:
        try:
            memo = agent.reason(reasoning_input)
            output = _memo_to_agent_output(memo)
            return output
        except Exception as e:
            import sys
            print(f"[V10] LLM reasoning failed, using rule-based fallback: {e}", file=sys.stderr)
            # Fall through to rule-based
            try:
                from src.research.llm_brain.research_reasoning_agent import _rule_based_memo
                memo = _rule_based_memo(reasoning_input)
                return _memo_to_agent_output(memo)
            except Exception:
                return _v10_fallback_output(blind_input, f"llm_error: {e}")
    else:
        # No agent available — use rule-based or minimal fallback
        try:
            from src.research.llm_brain.research_reasoning_agent import _rule_based_memo
            reasoning_input = _blind_prompt_to_reasoning_input(blind_input)
            memo = _rule_based_memo(reasoning_input)
            return _memo_to_agent_output(memo)
        except Exception:
            return _v10_fallback_output(blind_input, "agent_unavailable")


def _v10_fallback_output(blind_input: dict, reason: str = "") -> dict:
    """Minimal fallback when all reasoning paths fail."""
    regime = blind_input.get("macro_regime", {})
    conditions = blind_input.get("starting_conditions", {})
    beliefs = blind_input.get("market_beliefs_at_time", "")
    return {
        "regime": f"Monetary: {regime.get('monetary','?')}, Fiscal: {regime.get('fiscal','?')}, Growth: {regime.get('growth','?')}, Inflation: {regime.get('inflation','?')}",
        "narrative": beliefs[:200] if beliefs else "Insufficient data for narrative identification",
        "beliefs": ["Analysis requires LLM reasoning — minimal fallback output"],
        "prediction": "Unable to generate prediction without reasoning engine",
        "risk": "Risk assessment unavailable",
        "invalidation": "N/A — minimal fallback",
        "asset_implication": "N/A — minimal fallback",
        "confidence": 0.3,
        "conviction_level": "low",
        "executive_summary": f"MINIMAL FALLBACK — {reason}",
        "reasoning_mode": "fallback",
        "llm_model": "none",
    }


# ── Backward-compatible alias — remove once all callers use v10_agent_research ──
def simulate_agent_research(blind_input: dict) -> dict:
    """DEPRECATED: Use v10_agent_research instead.
    Kept for backward compatibility — delegates to real agent.
    """
    try:
        return v10_agent_research(blind_input)
    except Exception:
        # Absolute last resort: return old-style simulated output
        regime = blind_input.get("macro_regime", {})
        conditions = blind_input.get("starting_conditions", {})
        beliefs = blind_input.get("market_beliefs_at_time", "")
        monetary = regime.get("monetary", "")
        growth = regime.get("growth", "")
        inflation = regime.get("inflation", "")
        vol = regime.get("volatility", "")
        return {
            "regime": f"Monetary: {monetary}, Fiscal: {regime.get('fiscal', '')}, Growth: {growth}, Inflation: {inflation}, Volatility: {vol}",
            "narrative": beliefs[:120] if beliefs else "Narrative not clearly identified",
            "beliefs": [
                f"Monetary policy is {monetary}",
                f"Economic growth is {growth}",
                f"Inflation trend is {inflation}",
                f"Market volatility is {vol}",
            ],
            "prediction": f"Based on current conditions, expect continued {growth} growth with {inflation} inflation pressure",
            "risk": f"Key risk: regime shift if {monetary} policy changes or {growth} trend reverses",
            "invalidation": f"Thesis invalid if {growth} turns sharply or {inflation} spikes unexpectedly",
            "asset_implication": f"Prefer assets aligned with {monetary} policy and {growth} growth",
            "confidence": 0.4,
            "conviction_level": "low",
            "executive_summary": "LEGACY SIMULATED OUTPUT",
            "reasoning_mode": "simulated (V10 fallback)",
            "llm_model": "none",
        }
