# =============================================================================
# V3.3 Benchmark Runner — runs the full Agent pipeline against historical cases
# =============================================================================
# For each HistoricalCase:
#   1. Construct MacroSnapshot from case data
#   2. Run: NarrativeDetector -> NarrativeReasoner -> NarrativeCompetition
#   3. Run: BeliefEngine -> BeliefGraph -> ResearchJudgmentEngine
#   4. Save: agent_output.json with all intermediate outputs
# =============================================================================

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.research.evolution.regime_gate import RegimeSnapshot
from src.schemas.macro_snapshot import MacroSnapshot, MarketSnapshot
from src.shared.logging import get_logger

from validation.macro_benchmark.historical_cases import (
    CASES, HistoricalCase, get_cases_by_tag, get_cases_by_difficulty,
)

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Output Data Structures
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CaseResult:
    """Output for a single benchmark case."""
    case_id: str
    case_title: str
    status: str = "pending"  # pending | running | completed | skipped | error
    elapsed_ms: float = 0.0
    error: str = ""

    # Input
    macro_snapshot_summary: dict = field(default_factory=dict)

    # Stage 1: Narrative Detection
    narratives_detected: int = 0
    narrative_titles: list[str] = field(default_factory=list)

    # Stage 2: Narrative Reasoning (V3.2)
    narrative_objects_count: int = 0
    narrative_object_titles: list[str] = field(default_factory=list)
    causal_depths: list[int] = field(default_factory=list)

    # Stage 3: Narrative Competition (V3.2)
    competition_narratives: int = 0
    dominant_narrative_title: str = ""
    narrative_probabilities: dict[str, float] = field(default_factory=dict)

    # Stage 4: Belief Generation
    beliefs_count: int = 0
    belief_titles: list[str] = field(default_factory=list)
    belief_graph_relations: int = 0
    belief_graph_clusters: int = 0

    # Stage 5: Research Judgment (V3.2)
    judgments_count: int = 0
    judgments_falsifiable: int = 0
    judgment_convictions: list[str] = field(default_factory=list)
    macro_stance: str = ""

    # Raw outputs (for detailed analysis)
    raw_narratives: list[dict] = field(default_factory=list)
    raw_beliefs: list[dict] = field(default_factory=list)
    raw_judgments: list[dict] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    """Aggregate benchmark result for all cases."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_cases: int = 0
    completed: int = 0
    skipped: int = 0
    errors: int = 0
    total_elapsed_ms: float = 0.0
    case_results: list[CaseResult] = field(default_factory=list)

    # Aggregate metrics
    narrative_detection_rate: float = 0.0
    narrative_reasoning_rate: float = 0.0
    narrative_to_belief_rate: float = 0.0
    competition_existence_rate: float = 0.0
    falsifiability_rate: float = 0.0
    avg_judgment_confidence: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Snapshot Builder
# ═══════════════════════════════════════════════════════════════════════════

def build_macro_snapshot(case: HistoricalCase, cycle_id: str = "") -> MacroSnapshot:
    """Build a MacroSnapshot from historical case data.

    Converts the case's macro_regime into RegimeSnapshot and input_data
    into MarketSnapshot, then generates basic signals from input data.
    """
    regime = RegimeSnapshot(
        regime_id=f"regime-{case.case_id}",
        monetary_policy=case.macro_regime.get("monetary_policy", "neutral"),
        fiscal_stance=case.macro_regime.get("fiscal_stance", "neutral"),
        volatility=case.macro_regime.get("volatility", "moderate"),
        growth=case.macro_regime.get("growth", "stable"),
        inflation=case.macro_regime.get("inflation", "stable"),
    )

    # Extract numeric indicators from input_data
    indicators = {}
    for k, v in case.input_data.items():
        if isinstance(v, (int, float)) and k != "event":
            indicators[k] = float(v)

    market = MarketSnapshot(
        timestamp=datetime.now(timezone.utc),
        indicators=indicators,
    )

    # Generate basic signals from market data
    signals = _generate_signals_from_data(case.input_data)

    return MacroSnapshot(
        cycle_id=cycle_id or f"bench-{case.case_id}",
        regime=regime,
        market=market,
        signals=signals,
    )


def _generate_signals_from_data(data: dict) -> list:
    """Generate simple MacroSignal-like objects from input data."""
    signals = []

    # VIX signal
    vix = data.get("vix", 0)
    if vix > 40:
        signals.append({"name": "VIX_extreme", "value": vix, "category": "risk",
                        "direction": "bearish", "strength": min(vix / 80, 1.0)})
    elif vix > 25:
        signals.append({"name": "VIX_elevated", "value": vix, "category": "risk",
                        "direction": "bearish", "strength": 0.6})

    # Rate signal  
    us10y = data.get("us10y", 0)
    us2y = data.get("us2y", 0)
    if us2y and us10y:
        spread = us10y - us2y
        if spread < -0.5:
            signals.append({"name": "curve_inversion", "value": spread, "category": "rates",
                            "direction": "bearish", "strength": min(abs(spread) / 2, 1.0)})
        elif spread < 0:
            signals.append({"name": "curve_flat", "value": spread, "category": "rates",
                            "direction": "neutral", "strength": 0.5})

    # Credit spread signal
    hyg_spread = data.get("hyg_spread", 0)
    if hyg_spread > 800:
        signals.append({"name": "credit_stress_extreme", "value": hyg_spread, "category": "credit",
                        "direction": "bearish", "strength": 0.9})
    elif hyg_spread > 500:
        signals.append({"name": "credit_stress", "value": hyg_spread, "category": "credit",
                        "direction": "bearish", "strength": 0.6})

    # Oil signal
    oil = data.get("oil", 0)
    if oil < 40:
        signals.append({"name": "oil_depressed", "value": oil, "category": "commodities",
                        "direction": "bearish", "strength": 0.7})
    elif oil > 100:
        signals.append({"name": "oil_elevated", "value": oil, "category": "commodities",
                        "direction": "inflationary", "strength": 0.7})

    # DXY signal
    dxy = data.get("dxy", 0)
    if dxy > 105:
        signals.append({"name": "dollar_strong", "value": dxy, "category": "fx",
                        "direction": "hawkish", "strength": 0.7})
    elif dxy < 85:
        signals.append({"name": "dollar_weak", "value": dxy, "category": "fx",
                        "direction": "dovish", "strength": 0.7})

    # Gold signal (safe haven)
    gold = data.get("gold", 0)
    if gold > 2000:
        signals.append({"name": "gold_elevated", "value": gold, "category": "safe_haven",
                        "direction": "risk_off", "strength": 0.6})

    # Unemployment
    ue = data.get("unemployment", 0)
    if ue > 8:
        signals.append({"name": "labor_stress", "value": ue, "category": "growth",
                        "direction": "bearish", "strength": 0.8})
    elif ue < 4:
        signals.append({"name": "labor_tight", "value": ue, "category": "growth",
                        "direction": "hawkish", "strength": 0.6})

    return signals


# ═══════════════════════════════════════════════════════════════════════════
# State Vector Converter: raw data -> dimensional state_vector
# ═══════════════════════════════════════════════════════════════════════════

def _build_dim_state_vector(raw_data: dict) -> dict[str, dict]:
    """Convert raw market indicators to dimensional state_vector for engines.

    The narrative engines expect a state_vector like:
      {"rates": {"direction": "rising", "score": 0.8}, ...}
    Not raw values like {"us10y": 4.5, "dxy": 105}
    """
    sv = {}

    vix = raw_data.get("vix", 0)
    if vix > 40:
        sv["risk_appetite"] = {"direction": "extreme_fear", "score": 0.9}
    elif vix > 25:
        sv["risk_appetite"] = {"direction": "risk_off", "score": 0.7}
    elif vix < 15:
        sv["risk_appetite"] = {"direction": "risk_on", "score": 0.7}
    else:
        sv["risk_appetite"] = {"direction": "neutral", "score": 0.5}

    dxy = raw_data.get("dxy", 0)
    if dxy > 105:
        sv["dollar"] = {"direction": "strong", "score": 0.8}
    elif dxy > 100:
        sv["dollar"] = {"direction": "moderately_strong", "score": 0.65}
    elif dxy < 85:
        sv["dollar"] = {"direction": "weak", "score": 0.8}
    else:
        sv["dollar"] = {"direction": "neutral", "score": 0.5}

    us10y = raw_data.get("us10y", 0)
    if us10y > 4.5:
        sv["rates"] = {"direction": "rising", "score": 0.85}
    elif us10y > 3.0:
        sv["rates"] = {"direction": "moderately_rising", "score": 0.65}
    elif us10y < 1.0:
        sv["rates"] = {"direction": "falling", "score": 0.8}
    else:
        sv["rates"] = {"direction": "neutral", "score": 0.5}

    hyg = raw_data.get("hyg_spread", 0)
    if hyg > 800:
        sv["credit"] = {"direction": "tightening", "score": 0.9}
    elif hyg > 500:
        sv["credit"] = {"direction": "tightening", "score": 0.7}
    elif hyg < 300:
        sv["credit"] = {"direction": "easing", "score": 0.7}
    else:
        sv["credit"] = {"direction": "neutral", "score": 0.5}

    gold = raw_data.get("gold", 0)
    if gold > 2000:
        sv["gold"] = {"direction": "positive", "score": 0.8}
    elif gold > 1800:
        sv["gold"] = {"direction": "moderately_positive", "score": 0.65}
    elif gold < 1200:
        sv["gold"] = {"direction": "negative", "score": 0.7}
    else:
        sv["gold"] = {"direction": "neutral", "score": 0.5}

    oil = raw_data.get("oil", 0)
    if oil > 100:
        sv["commodities"] = {"direction": "positive", "score": 0.8}
    elif oil < 40:
        sv["commodities"] = {"direction": "negative", "score": 0.7}
    else:
        sv["commodities"] = {"direction": "neutral", "score": 0.5}

    # Tech sentiment from spx relative levels
    spx = raw_data.get("spx", 0)
    nasdaq = raw_data.get("nasdaq_ytd", 0)
    if nasdaq:
        sv["tech"] = {"direction": "negative" if nasdaq < 0 else "positive",
                      "score": min(abs(nasdaq) / 40, 1.0)}

    # Yield curve
    us2y = raw_data.get("us2y", 0)
    if us10y and us2y:
        spread = us10y - us2y
        if spread < -0.5:
            sv["curve"] = {"direction": "inverting", "score": 0.8}
        elif spread < 0:
            sv["curve"] = {"direction": "flat", "score": 0.6}
        elif spread > 1.5:
            sv["curve"] = {"direction": "steepening", "score": 0.8}
        else:
            sv["curve"] = {"direction": "normal", "score": 0.5}

    # Inflation
    cpi = raw_data.get("cpi_yoy", 0)
    if cpi > 7:
        sv["inflation"] = {"direction": "extreme", "score": 0.9}
    elif cpi > 4:
        sv["inflation"] = {"direction": "high", "score": 0.75}
    elif cpi < 2:
        sv["inflation"] = {"direction": "low", "score": 0.7}
    else:
        sv["inflation"] = {"direction": "moderate", "score": 0.5}

    return sv


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline Runner
# ═══════════════════════════════════════════════════════════════════════════

class BenchmarkRunner:
    """Runs the full Agent pipeline against historical cases."""

    def __init__(self, output_dir: str = "validation/macro_benchmark/output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # Lazy-initialized components
        self._narrative_detector = None
        self._narrative_reasoner = None
        self._narrative_competition = None
        self._belief_engine = None
        self._judgment_engine = None

    # ── Component lazy-init ─────────────────────────────────────────

    def _get_narrative_detector(self):
        if self._narrative_detector is not None:
            return self._narrative_detector
        try:
            from src.research.narrative.narrative_detector import NarrativeDetector
            self._narrative_detector = NarrativeDetector()
        except Exception as e:
            logger.warning("NarrativeDetector init failed: %s", e)
            self._narrative_detector = False
        return self._narrative_detector

    def _get_narrative_reasoner(self):
        if self._narrative_reasoner is not None:
            return self._narrative_reasoner
        try:
            from src.research.narrative.narrative_reasoner import NarrativeReasoner
            self._narrative_reasoner = NarrativeReasoner()
        except Exception as e:
            logger.warning("NarrativeReasoner init failed: %s", e)
            self._narrative_reasoner = False
        return self._narrative_reasoner

    def _get_narrative_competition(self):
        if self._narrative_competition is not None:
            return self._narrative_competition
        try:
            from src.research.narrative.narrative_competition import NarrativeCompetition
            reasoner = self._get_narrative_reasoner()
            self._narrative_competition = NarrativeCompetition(reasoner=reasoner)
        except Exception as e:
            logger.warning("NarrativeCompetition init failed: %s", e)
            self._narrative_competition = False
        return self._narrative_competition

    def _get_belief_engine(self):
        if self._belief_engine is not None:
            return self._belief_engine
        try:
            from src.research.beliefs.belief_engine import BeliefEngine
            self._belief_engine = BeliefEngine()
        except Exception as e:
            logger.warning("BeliefEngine init failed: %s", e)
            self._belief_engine = False
        return self._belief_engine

    def _get_judgment_engine(self):
        if self._judgment_engine is not None:
            return self._judgment_engine
        try:
            from src.research.judgment.research_judgment import ResearchJudgmentEngine
            self._judgment_engine = ResearchJudgmentEngine()
        except Exception as e:
            logger.warning("ResearchJudgmentEngine init failed: %s", e)
            self._judgment_engine = False
        return self._judgment_engine

    # ── Main run ────────────────────────────────────────────────────

    def run_all(self, cases: list[HistoricalCase] | None = None,
                skip_reasoner: bool = False, skip_competition: bool = False,
                skip_judgment: bool = False) -> BenchmarkResult:
        """Run the full pipeline on all cases.

        Args:
            cases: Cases to run (default: all CASES)
            skip_reasoner: Skip V3.2 narrative reasoning
            skip_competition: Skip V3.2 narrative competition
            skip_judgment: Skip V3.2 research judgment
        """
        if cases is None:
            cases = CASES

        result = BenchmarkResult(total_cases=len(cases))
        t_start = time.time()

        for i, case in enumerate(cases):
            logger.info("[%d/%d] Running %s: %s", i + 1, len(cases), case.case_id, case.title[:60])
            case_result = self._run_case(
                case, skip_reasoner, skip_competition, skip_judgment
            )
            result.case_results.append(case_result)

            if case_result.status == "completed":
                result.completed += 1
            elif case_result.status == "skipped":
                result.skipped += 1
            else:
                result.errors += 1

        result.total_elapsed_ms = (time.time() - t_start) * 1000
        self._compute_aggregate_metrics(result)
        self._save_results(result)
        return result

    def _run_case(self, case: HistoricalCase,
                  skip_reasoner: bool, skip_competition: bool,
                  skip_judgment: bool) -> CaseResult:
        """Run pipeline on a single case."""
        cr = CaseResult(case_id=case.case_id, case_title=case.title)
        t0 = time.time()

        try:
            # Step 1: Build macro snapshot
            snapshot = build_macro_snapshot(case)
            cr.macro_snapshot_summary = {
                "regime": case.macro_regime,
                "indicators_count": len(case.input_data),
                "signals_count": snapshot.signal_count,
            }

            # Step 2: Narrative Detection (V3.0) — try template-based first
            narratives = self._detect_narratives(snapshot)
            cr.narratives_detected = len(narratives)
            cr.narrative_titles = [getattr(n, 'title', str(n)[:50]) for n in narratives]
            cr.raw_narratives = [self._narrative_to_dict(n) for n in narratives]

            # Step 3: Narrative Competition (V3.2) — generates narratives from state_vector
            # Always run competition as fallback narrative generator
            narrative_objects = []
            if not skip_competition:
                comp_result = self._compete_narratives(snapshot)
                if comp_result:
                    narrative_objects = getattr(comp_result, 'narratives', [])
                    cr.competition_narratives = len(narrative_objects)
                    cr.narrative_object_titles = [getattr(n, 'title', '') for n in narrative_objects]
                    cr.causal_depths = [getattr(n, 'causal_depth', 0) for n in narrative_objects
                                        if hasattr(n, 'causal_depth')]
                    cr.narrative_probabilities = self._extract_probabilities(comp_result)
                    dominant = getattr(comp_result, 'dominant', None)
                    if dominant:
                        cr.dominant_narrative_title = getattr(dominant, 'title', '')

            # If competition generated no narratives, use detection results
            if not narrative_objects and narratives:
                narrative_objects = narratives

            # Step 3b: Narrative Reasoning (V3.2) — enrich with causal chains
            if not skip_reasoner and narrative_objects:
                reasoned = self._reason_narratives(narrative_objects, snapshot)
                if reasoned:
                    cr.narrative_objects_count = len(reasoned)
                    cr.causal_depths = [getattr(n, 'causal_depth', 0) for n in reasoned]
                    narrative_objects = reasoned

            if not narrative_objects:
                cr.status = "completed"
                cr.elapsed_ms = (time.time() - t0) * 1000
                return cr

            # Step 4: Belief Generation (V3.2)
            beliefs = self._generate_beliefs(narrative_objects, snapshot)
            cr.beliefs_count = len(beliefs)
            cr.belief_titles = [getattr(b, 'title', '') or getattr(b, 'belief_title', '') for b in beliefs]
            cr.raw_beliefs = [self._belief_to_dict(b) for b in beliefs]

            # Get graph stats
            belief_engine = self._get_belief_engine()
            if belief_engine and hasattr(belief_engine, 'graph'):
                stats = belief_engine.graph.get_graph_stats()
                cr.belief_graph_relations = stats.get("relation_count", 0)
                cr.belief_graph_clusters = stats.get("competition_clusters", 0)

            # Step 6: Research Judgment (V3.2)
            if not skip_judgment and beliefs:
                judgment_output = self._judge_beliefs(beliefs, narrative_objects)
                if judgment_output:
                    cr.judgments_count = getattr(judgment_output, 'count', 0)
                    cr.judgments_falsifiable = getattr(judgment_output, 'falsifiable_count', 0)
                    cr.macro_stance = getattr(judgment_output, 'macro_stance', '')
                    cr.raw_judgments = self._judgments_to_dict(judgment_output)
                    for j in getattr(judgment_output, 'judgments', [])[:3]:
                        conv = getattr(j, 'conviction_statement', '')
                        if conv:
                            cr.judgment_convictions.append(conv[:100])

            cr.status = "completed"

        except Exception as e:
            cr.status = "error"
            cr.error = str(e)
            logger.error("Case %s failed: %s", case.case_id, e)

        cr.elapsed_ms = (time.time() - t0) * 1000
        return cr

    # ── Pipeline stages ─────────────────────────────────────────────

    def _detect_narratives(self, snapshot: MacroSnapshot) -> list:
        """Stage 1: Run NarrativeDetector."""
        detector = self._get_narrative_detector()
        if not detector:
            return []

        try:
            # Build state_vector from market indicators
            state_vector = {}
            if snapshot.market and snapshot.market.indicators:
                state_vector = snapshot.market.indicators

            # detector.detect(state_vector, conclusions) — conclusions optional
            return detector.detect(state_vector, conclusions=[])
        except Exception as e:
            logger.warning("Narrative detection failed: %s", e)
            return []

    def _reason_narratives(self, narratives: list, snapshot: MacroSnapshot) -> list:
        """Stage 2b: Run NarrativeReasoner (V3.2)."""
        reasoner = self._get_narrative_reasoner()
        if not reasoner:
            return []

        try:
            from src.research.narrative.schemas import Narrative
            v3_narratives = [n for n in narratives if isinstance(n, Narrative) and
                             not hasattr(n, 'causal_chain')]

            raw_data = {}
            if snapshot.market and snapshot.market.indicators:
                raw_data = snapshot.market.indicators
            dim_sv = _build_dim_state_vector(raw_data)

            regime = snapshot.regime_label

            return reasoner.reason_batch(
                v3_narratives or narratives,
                state_vector=dim_sv,
                regime=regime,
            )
        except Exception as e:
            logger.warning("Narrative reasoning failed: %s", e)
            return []

    def _compete_narratives(self, snapshot: MacroSnapshot) -> Any:
        """Stage 3: Run NarrativeCompetition (V3.2)."""
        competition = self._get_narrative_competition()
        if not competition:
            return None

        try:
            # Build dimensional state_vector from raw indicators
            raw_data = {}
            if snapshot.market and snapshot.market.indicators:
                raw_data = snapshot.market.indicators
            dim_sv = _build_dim_state_vector(raw_data)

            regime = snapshot.regime_label

            return competition.compete(
                state_vector=dim_sv,
                regime=regime,
            )
        except Exception as e:
            logger.warning("Narrative competition failed: %s", e)
            return None

    def _generate_beliefs(self, narratives: list, snapshot: MacroSnapshot) -> list:
        """Stage 4: Run BeliefEngine."""
        engine = self._get_belief_engine()
        if not engine:
            return []

        try:
            # Build dimensional state_vector
            raw_data = {}
            if snapshot.market and snapshot.market.indicators:
                raw_data = snapshot.market.indicators
            dim_sv = _build_dim_state_vector(raw_data)

            return engine.generate_from_narratives(narratives, dim_sv)
        except Exception as e:
            logger.warning("Belief generation failed: %s", e)
            return []

    def _judge_beliefs(self, beliefs: list, narrative_objects: list) -> Any:
        """Stage 5: Run ResearchJudgmentEngine (V3.2)."""
        judge = self._get_judgment_engine()
        if not judge:
            return None

        try:
            return judge.judge(
                beliefs=beliefs,
                graph=getattr(self._get_belief_engine(), 'graph', None) if self._get_belief_engine() else None,
                narrative_objects=narrative_objects,
            )
        except Exception as e:
            logger.warning("Research judgment failed: %s", e)
            return None

    # ── Serialization helpers ───────────────────────────────────────

    def _narrative_to_dict(self, narrative) -> dict:
        try:
            return {
                "id": getattr(narrative, 'id', ''),
                "title": getattr(narrative, 'title', ''),
                "description": getattr(narrative, 'description', '')[:200],
                "score": getattr(narrative, 'score', 0),
                "category": getattr(narrative, 'category', ''),
            }
        except Exception:
            return {"error": str(narrative)[:100]}

    def _belief_to_dict(self, belief) -> dict:
        try:
            return {
                "id": getattr(belief, 'id', ''),
                "title": getattr(belief, 'title', '') or getattr(belief, 'belief_title', ''),
                "domain": str(getattr(belief, 'domain', '')),
                "confidence": getattr(belief, 'confidence', 0),
                "evidence_count": len(getattr(belief, 'evidence', [])),
                "narratives": getattr(belief, 'source_narratives', [])[:3],
            }
        except Exception:
            return {"error": str(belief)[:100]}

    def _judgments_to_dict(self, judgment_output) -> list[dict]:
        try:
            judgments = getattr(judgment_output, 'judgments', [])
            result = []
            for j in judgments:
                result.append({
                    "belief_title": getattr(j, 'belief_title', ''),
                    "conviction": getattr(j, 'conviction_statement', '')[:150],
                    "confidence": getattr(j, 'confidence', 0),
                    "reasoning": getattr(j, 'reasoning_chain', [])[:3],
                    "falsification": getattr(j, 'falsification_conditions', [])[:3],
                    "competing": getattr(j, 'competing_beliefs', [])[:3],
                    "contradicting": getattr(j, 'contradicting_beliefs', [])[:3],
                })
            return result
        except Exception:
            return []

    def _extract_probabilities(self, comp_result) -> dict[str, float]:
        try:
            narratives = getattr(comp_result, 'narratives', [])
            return {getattr(n, 'title', f'n{i}'): getattr(n, 'probability', 0.5)
                    for i, n in enumerate(narratives)}
        except Exception:
            return {}

    # ── Aggregate metrics ───────────────────────────────────────────

    def _compute_aggregate_metrics(self, result: BenchmarkResult):
        completed = [c for c in result.case_results if c.status == "completed"]
        n = len(completed)
        if n == 0:
            return

        result.narrative_detection_rate = sum(1 for c in completed if c.narratives_detected > 0) / n
        result.narrative_reasoning_rate = sum(1 for c in completed if c.narrative_objects_count > 0) / n
        result.narrative_to_belief_rate = sum(
            1 for c in completed
            if c.narratives_detected > 0 and c.beliefs_count >= c.narratives_detected
        ) / n
        result.competition_existence_rate = sum(1 for c in completed if c.competition_narratives >= 2) / n
        result.falsifiability_rate = sum(
            1 for c in completed
            if c.judgments_count > 0 and c.judgments_falsifiable > 0
        ) / max(sum(1 for c in completed if c.judgments_count > 0), 1)

        confidences = []
        for c in completed:
            for j_dict in c.raw_judgments:
                conf = j_dict.get("confidence", 0)
                if conf:
                    confidences.append(conf)
        result.avg_judgment_confidence = sum(confidences) / len(confidences) if confidences else 0

    def _save_results(self, result: BenchmarkResult):
        """Save benchmark results to JSON."""
        output = {
            "benchmark_version": "V3.3",
            "timestamp": result.timestamp,
            "summary": {
                "total_cases": result.total_cases,
                "completed": result.completed,
                "skipped": result.skipped,
                "errors": result.errors,
                "total_elapsed_ms": result.total_elapsed_ms,
            },
            "aggregate_metrics": {
                "narrative_detection_rate": round(result.narrative_detection_rate, 3),
                "narrative_reasoning_rate": round(result.narrative_reasoning_rate, 3),
                "narrative_to_belief_rate": round(result.narrative_to_belief_rate, 3),
                "competition_existence_rate": round(result.competition_existence_rate, 3),
                "falsifiability_rate": round(result.falsifiability_rate, 3),
                "avg_judgment_confidence": round(result.avg_judgment_confidence, 3),
            },
            "case_results": [],
        }

        for cr in result.case_results:
            output["case_results"].append({
                "case_id": cr.case_id,
                "case_title": cr.case_title[:80],
                "status": cr.status,
                "elapsed_ms": round(cr.elapsed_ms, 1),
                "error": cr.error[:200] if cr.error else "",
                "narratives_detected": cr.narratives_detected,
                "narrative_objects": cr.narrative_objects_count,
                "competition_narratives": cr.competition_narratives,
                "dominant_narrative": cr.dominant_narrative_title[:80],
                "beliefs_count": cr.beliefs_count,
                "belief_graph_relations": cr.belief_graph_relations,
                "belief_graph_clusters": cr.belief_graph_clusters,
                "judgments_count": cr.judgments_count,
                "judgments_falsifiable": cr.judgments_falsifiable,
                "macro_stance": cr.macro_stance,
                "judgment_convictions": cr.judgment_convictions[:2],
                "narrative_titles": cr.narrative_titles[:3],
                "belief_titles": cr.belief_titles[:3],
            })

        # Save summary
        summary_path = os.path.join(self.output_dir, "benchmark_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(output["summary"], f, indent=2, ensure_ascii=False, default=str)

        # Save full results
        full_path = os.path.join(self.output_dir, "agent_output.json")
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)

        # Save per-case detailed outputs
        cases_dir = os.path.join(self.output_dir, "cases")
        os.makedirs(cases_dir, exist_ok=True)
        for cr in result.case_results:
            case_output = {
                "case_id": cr.case_id,
                "title": cr.case_title,
                "status": cr.status,
                "narratives": cr.raw_narratives,
                "beliefs": cr.raw_beliefs,
                "judgments": cr.raw_judgments,
                "narrative_probabilities": cr.narrative_probabilities,
                "dominant_narrative": cr.dominant_narrative_title,
                "macro_stance": cr.macro_stance,
            }
            case_path = os.path.join(cases_dir, f"{cr.case_id}.json")
            with open(case_path, "w", encoding="utf-8") as f:
                json.dump(case_output, f, indent=2, ensure_ascii=False, default=str)

        logger.info("Benchmark results saved to %s", self.output_dir)
        logger.info("  summary: %s", summary_path)
        logger.info("  full: %s", full_path)
        logger.info("  per-case: %s/*.json", cases_dir)


# ═══════════════════════════════════════════════════════════════════════════
# Quick CLI
# ═══════════════════════════════════════════════════════════════════════════

def run_benchmark(
    tags: list[str] | None = None,
    difficulty: str | None = None,
    max_cases: int = 0,
    output_dir: str = "validation/macro_benchmark/output",
) -> BenchmarkResult:
    """Run the benchmark with optional filters.

    Args:
        tags: Filter cases by tags (e.g., ["inflation", "fed"])
        difficulty: Filter by difficulty ("easy", "medium", "hard")
        max_cases: Limit to N cases (0 = all)
        output_dir: Output directory for results
    """
    cases = list(CASES)  # copy

    if tags:
        filtered = set()
        for tag in tags:
            filtered.update(get_cases_by_tag(tag))
        cases = [c for c in cases if c in filtered]

    if difficulty:
        cases = get_cases_by_difficulty(difficulty)

    if max_cases > 0:
        cases = cases[:max_cases]

    logger.info("Running benchmark: %d cases (tags=%s, difficulty=%s)",
                len(cases), tags, difficulty)

    runner = BenchmarkRunner(output_dir=output_dir)
    return runner.run_all(cases)


if __name__ == "__main__":
    import sys
    result = run_benchmark(max_cases=5)
    print(f"\nBenchmark complete: {result.completed}/{result.total_cases} completed")
    print(f"Narrative detection rate: {result.narrative_detection_rate:.1%}")
    print(f"Narrative reasoning rate: {result.narrative_reasoning_rate:.1%}")
    print(f"Narrative->Belief rate: {result.narrative_to_belief_rate:.1%}")
    print(f"Competition existence: {result.competition_existence_rate:.1%}")
    print(f"Falsifiability rate: {result.falsifiability_rate:.1%}")
    print(f"Results saved to: validation/macro_benchmark/output/")
