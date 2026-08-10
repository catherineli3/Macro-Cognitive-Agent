"""M1+M2 Daily Runner — Macro Data Pipeline + Mental Models + Research Cycle.

This is the NEW entry point for the Macro Research Agent.

Flow:
    1. MacroPipeline.build_daily_macro_snapshot()  → real data from Yahoo Finance
    2. SnapshotBuilder → enhanced MacroSnapshot dict
    3. Bridge → convert to existing MacroSnapshot schema
    4. MentalModel Library → ResearchConclusions
    5. ResearchCycleEngine.run_cycle() → autonomous research
    6. Output → daily report

No synthetic data. All data from real sources.

Usage:
    cd macro-research-agent
    python scripts/run_m1_daily.py                    # Single run (today)
    python scripts/run_m1_daily.py --dimension Liquidity  # Filter by domain
    python scripts/run_m1_daily.py --no-research      # Data pipeline only
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Inject project root ───────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_pipeline.macro_pipeline import MacroPipeline
from src.data_pipeline.feature_engine import FeatureSnapshot
from src.data_pipeline.state_vector import MacroStateVector, StateVectorDimension
from src.research.evolution.regime_gate import RegimeSnapshot
from src.research.models.mental_model import ResearchConclusion
from src.research.models.model_registry import build_default_registry
from src.schemas.macro_snapshot import MacroSnapshot, MarketSnapshot
from src.schemas.signal import (
    MacroSignalSchema,
    SignalDirection,
    SignalStrength,
    SignalEvidence,
)
from src.research_cycle.cycle_engine import ResearchCycleEngine
from src.shared.logging import get_logger

logger = get_logger(__name__)

OUTPUT_DIR = PROJECT_ROOT / "snapshot"


# ═══════════════════════════════════════════════════════════════════════════════
# Bridge: M1 Pipeline Dict → MacroSnapshot Schema
# ═══════════════════════════════════════════════════════════════════════════════


def bridge_m1_to_macro_snapshot(
    m1_snapshot: dict,
    cycle_id: str = "",
) -> MacroSnapshot:
    """Convert M1 pipeline enhanced snapshot dict to existing MacroSnapshot schema.

    This bridge preserves backward compatibility with ResearchCycleEngine
    while adding the full M1 state vector and feature data.

    Mapping:
        M1 state_vector.Liquidity → regime.monetary_policy
        M1 state_vector.Growth → regime.growth
        M1 state_vector.Inflation → regime.inflation
        M1 state_vector.Risk_Appetite → regime.volatility
        M1 feature_summary.indicators.*.raw_value → market.indicators
        M1 state_vector → signals (derived from dimension scores)
    """
    sv = m1_snapshot.get("state_vector", {})
    features = m1_snapshot.get("feature_summary", {})

    # ── Build RegimeSnapshot from state vector ────────────────────────────
    liquidity = sv.get("Liquidity", {})
    growth = sv.get("Growth", {})
    inflation = sv.get("Inflation", {})
    risk = sv.get("Risk_Appetite", {})

    def _map_direction(dim_data: dict, default: str = "neutral") -> str:
        direction = dim_data.get("direction", default)
        # Map M1 directions to regime-compatible names
        mapping = {
            "tightening": "tightening",
            "easing": "easing",
            "expansion": "accelerating",
            "contraction": "decelerating",
            "rising": "rising",
            "cooling": "falling",
            "risk_on": "low",
            "risk_off": "high",
            "caution": "elevated",
            "neutral": "stable",
        }
        return mapping.get(direction, default)

    regime = RegimeSnapshot(
        monetary_policy=_map_direction(liquidity, "neutral"),
        growth=_map_direction(growth, "stable"),
        inflation=_map_direction(inflation, "stable"),
        volatility=_map_direction(risk, "moderate"),
        fiscal_stance="neutral",
    )

    # ── Build MarketSnapshot from feature indicators ─────────────────────
    market_data: dict[str, float] = {}
    indicators = features.get("indicators", {})
    for name, ind_data in indicators.items():
        raw = ind_data.get("raw_value", 0)
        if raw is not None:
            market_data[name.lower()] = float(raw)

    market = MarketSnapshot(indicators=market_data)

    # ── Build Signals from state vector dimensions ───────────────────────
    signals = _build_signals_from_state_vector(sv, market_data)

    # ── Build Composite (theme/summary) ──────────────────────────────────
    from dataclasses import dataclass

    @dataclass
    class CompositeSignalSnapshot:
        dominant_theme: str = ""
        risk_appetite: str = "neutral"

    composite = CompositeSignalSnapshot(
        dominant_theme=m1_snapshot.get("meta", {}).get("dominant_theme", ""),
        risk_appetite=m1_snapshot.get("meta", {}).get("risk_regime", "normal"),
    )

    return MacroSnapshot(
        cycle_id=cycle_id or f"m1-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        regime=regime,
        market=market,
        signals=signals,
        composite=composite,
    )


def _build_signals_from_state_vector(
    sv: dict,
    market_data: dict[str, float],
) -> list[MacroSignalSchema]:
    """Derive MacroSignalSchema list from M1 state vector dimensions."""
    signals = []

    for dim_name, dim_data in sv.items():
        score = dim_data.get("score", 0.5)
        direction = dim_data.get("direction", "neutral")
        confidence = dim_data.get("confidence", 0.5)
        drivers = dim_data.get("drivers", [])

        # Map direction to SignalDirection
        bearish_directions = {"tightening", "strengthening", "rising", "hawkish", "contraction", "risk_off"}
        bullish_directions = {"easing", "weakening", "cooling", "dovish", "expansion", "risk_on"}

        if direction in bearish_directions:
            sig_dir = SignalDirection.BEARISH
        elif direction in bullish_directions:
            sig_dir = SignalDirection.BULLISH
        else:
            sig_dir = SignalDirection.NEUTRAL

        # Determine strength from score distance from neutral
        distance = abs(score - 0.5)
        if distance > 0.3:
            sig_strength = SignalStrength.STRONG
        elif distance > 0.15:
            sig_strength = SignalStrength.MODERATE
        else:
            sig_strength = SignalStrength.WEAK

        # Build evidence from drivers
        evidence_list = []
        for driver in drivers:
            driver_val = market_data.get(driver.lower(), 0)
            evidence_list.append(SignalEvidence(
                rule_id=f"m1_state_vector_{dim_name}_{driver}",
                rule_description=f"{dim_name} dimension driven by {driver}",
                input_value=driver_val,
                condition=f"{driver}: {driver_val:.2f}, direction: {direction}",
                interpretation=f"{dim_name}: {direction} (score={score:.2f}, conf={confidence:.2f})",
            ))

        signal = MacroSignalSchema(
            indicator=dim_name.upper(),
            dimension=dim_name,
            direction=sig_dir,
            strength=sig_strength,
            confidence=min(float(confidence), 0.95),
            evidence=evidence_list,
            metadata={
                "raw_score": score,
                "drivers": drivers,
                "m1_version": "1.0",
            },
        )
        signals.append(signal)

    return signals


# ═══════════════════════════════════════════════════════════════════════════════
# M1 Daily Runner
# ═══════════════════════════════════════════════════════════════════════════════


class M1DailyRunner:
    """Runs the complete M1 + M2 pipeline: Data → Models → Research.

    Usage:
        runner = M1DailyRunner()
        report = runner.run()
    """

    def __init__(self, run_research: bool = True):
        self.pipeline = MacroPipeline()
        self.registry = build_default_registry()
        self.run_research = run_research
        self.engine: ResearchCycleEngine | None = None
        self.m1_snapshot: dict = {}
        self.macro_snapshot: MacroSnapshot | None = None
        self.conclusions: list[ResearchConclusion] = []

    def run(self, for_dimension: str | None = None) -> dict:
        """Execute the full M1 + M2 daily pipeline.

        Args:
            for_dimension: Optional filter for single macro dimension.

        Returns:
            Complete daily report dict.
        """
        logger.info("=" * 70)
        logger.info("M1+M2 Daily Runner — Macro Data + Mental Models + Research")
        logger.info("=" * 70)

        # ── Stage 1: M1 Data Pipeline ──────────────────────────────────
        logger.info("Stage 1: Running M1 Macro Data Pipeline...")
        try:
            self.m1_snapshot = self.pipeline.build_daily_macro_snapshot(
                for_dimension=for_dimension,
                persist=True,
            )
            logger.info(
                "M1 pipeline complete: %d indicators, theme=%s, regime=%s",
                len(self.m1_snapshot.get("feature_summary", {}).get("indicators", {})),
                self.m1_snapshot.get("meta", {}).get("dominant_theme", "?"),
                self.m1_snapshot.get("meta", {}).get("risk_regime", "?"),
            )
        except Exception as e:
            logger.error("M1 pipeline failed: %s", e)
            return {"status": "failed", "stage": "m1_pipeline", "error": str(e)}

        # ── Stage 2: Bridge to MacroSnapshot ───────────────────────────
        logger.info("Stage 2: Building MacroSnapshot from M1 data...")
        self.macro_snapshot = bridge_m1_to_macro_snapshot(self.m1_snapshot)
        logger.info("MacroSnapshot built: regime=%s", self.macro_snapshot.regime_label)

        # ── Stage 3: Mental Model Evaluation ───────────────────────────
        logger.info("Stage 3: Running %d mental models...", len(self.registry))
        self.conclusions = self.registry.evaluate_all(self.m1_snapshot)
        logger.info(
            "Mental models complete: %d conclusions from %d models",
            len(self.conclusions),
            len(self.registry),
        )

        # ── Stage 4: Research Cycle (optional) ─────────────────────────
        cycle_result = None
        if self.run_research:
            logger.info("Stage 4: Running Research Cycle Engine...")
            self.engine = ResearchCycleEngine()
            cycle_result = self.engine.run_cycle(
                macro_snapshot=self.macro_snapshot,
            )
            logger.info(
                "Research cycle complete: status=%s thesis=%s",
                cycle_result.status,
                cycle_result.thesis.title[:80] if cycle_result.thesis else "N/A",
            )

        # ── Stage 5: Build Report ──────────────────────────────────────
        report = self._build_report(cycle_result)
        self._save_report(report)

        return report

    def _build_report(self, cycle_result: Any = None) -> dict:
        """Build the final daily report."""
        sv = self.m1_snapshot.get("state_vector", {})
        meta = self.m1_snapshot.get("meta", {})

        return {
            "report_type": "M1+M2 Daily Macro Intelligence",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pipeline_version": "M1",

            # ── Section 1: Macro State ────────────────────────────────
            "macro_state": {
                "risk_regime": meta.get("risk_regime", "unknown"),
                "dominant_theme": meta.get("dominant_theme", "unknown"),
                "aggregate_score": meta.get("aggregate_score", 0.5),
                "summary": self.m1_snapshot.get("summary", ""),
            },

            # ── Section 2: Dimension Scores ───────────────────────────
            "dimensions": {
                dim_name: {
                    "score": dim_data.get("score", 0.5),
                    "confidence": dim_data.get("confidence", 0.0),
                    "direction": dim_data.get("direction", "neutral"),
                    "drivers": dim_data.get("drivers", []),
                    "narrative_seeds": dim_data.get("narrative_seeds", []),
                }
                for dim_name, dim_data in sv.items()
            },

            # ── Section 3: Research Conclusions ───────────────────────
            "research_conclusions": [
                {
                    "model": c.model_name,
                    "domain": c.domain,
                    "conclusion": c.conclusion,
                    "confidence": c.confidence,
                    "direction": c.direction,
                    "narrative_seeds": c.narrative_seeds,
                    "supporting_count": len(c.supporting_evidence),
                    "contradicting_count": len(c.contradicting_evidence),
                }
                for c in self.conclusions
            ],

            # ── Section 4: Research Cycle Output ──────────────────────
            "research_cycle": (
                {
                    "status": cycle_result.status,
                    "thesis": (
                        {
                            "title": cycle_result.thesis.title,
                            "confidence": cycle_result.thesis.confidence,
                            "direction": cycle_result.thesis.direction,
                        }
                        if cycle_result and cycle_result.thesis else None
                    ),
                    "framework": (
                        cycle_result.framework_selection.top_framework_id
                        if cycle_result and cycle_result.framework_selection else None
                    ),
                    # V3.1: Narrative + Belief outputs
                    "narratives_count": (
                        len(cycle_result.narratives) if cycle_result else 0
                    ),
                    "narratives": (
                        [
                            {
                                "title": getattr(n, 'title', ''),
                                "category": str(getattr(n, 'category', '')),
                                "confidence": getattr(n, 'confidence', 0),
                                "composite_score": getattr(n, 'composite_score', 0),
                            }
                            for n in cycle_result.narratives
                        ]
                        if cycle_result and getattr(cycle_result, 'narratives', None)
                        else []
                    ),
                    "beliefs_count": (
                        len(cycle_result.beliefs) if cycle_result else 0
                    ),
                    "beliefs": (
                        [
                            {
                                "title": getattr(b, 'title', '') or getattr(b, 'belief_title', ''),
                                "domain": str(getattr(b, 'domain', '')),
                                "confidence": getattr(b, 'confidence', 0),
                                "stage": str(getattr(b, 'stage', '')),
                            }
                            for b in cycle_result.beliefs
                        ]
                        if cycle_result and getattr(cycle_result, 'beliefs', None)
                        else []
                    ),
                }
                if cycle_result else {"status": "skipped"}
            ),

            # ── Section 5: Quality Report ─────────────────────────────
            "quality": self.m1_snapshot.get("quality_report", {}),
            "sources": self.m1_snapshot.get("source_report", {}),
        }

    def _save_report(self, report: dict) -> str:
        """Save report to JSON file."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = OUTPUT_DIR / f"daily_report_{date_str}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        logger.info("Daily report saved: %s", path)
        return str(path)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def print_report(report: dict) -> None:
    """Pretty-print the daily report to console."""
    ms = report["macro_state"]
    dims = report["dimensions"]
    conclusions = report["research_conclusions"]
    quality = report.get("quality", {})
    cycle = report.get("research_cycle", {})

    width = 70
    print()
    print("=" * width)
    print("  MACRO INTELLIGENCE DAILY REPORT")
    print(f"  {report['generated_at'][:19]}")
    print("=" * width)

    # Section 1: Macro State
    print(f"\n{'─' * width}")
    print("  1. MACRO STATE")
    print(f"{'─' * width}")
    print(f"  Risk Regime:    {ms['risk_regime'].upper()}")
    print(f"  Dominant Theme: {ms['dominant_theme']}")
    print(f"  Aggregate Score: {ms['aggregate_score']:.2f}")

    # Section 2: Dimensions
    print(f"\n{'─' * width}")
    print("  2. DIMENSION SCORES")
    print(f"{'─' * width}")
    for dim, data in dims.items():
        bar = "█" * int(data["score"] * 20) + "░" * (20 - int(data["score"] * 20))
        print(f"  {dim:<15} [{bar}] {data['score']:.2f}  {data['direction']}")
        if data["drivers"]:
            print(f"  {'':15} Drivers: {', '.join(data['drivers'])}")

    # Section 3: Research Conclusions
    print(f"\n{'─' * width}")
    print("  3. RESEARCH CONCLUSIONS (Mental Models)")
    print(f"{'─' * width}")
    for i, c in enumerate(conclusions, 1):
        conf_bar = "★" * int(c["confidence"] * 5) + "☆" * (5 - int(c["confidence"] * 5))
        print(f"\n  {i}. [{c['domain']}] {conf_bar} ({c['confidence']:.2f})")
        print(f"     {c['conclusion'][:120]}")
        if c["narrative_seeds"]:
            print(f"     Possible narratives:")
            for seed in c["narrative_seeds"][:2]:
                print(f"       → {seed}")

    # Section 4: Research Cycle
    if cycle.get("status") != "skipped":
        print(f"\n{'─' * width}")
        print("  4. RESEARCH CYCLE")
        print(f"{'─' * width}")
        print(f"  Status:    {cycle.get('status', 'N/A')}")
        thesis = cycle.get("thesis")
        if thesis:
            print(f"  Thesis:    {thesis['title'][:100]}")
            print(f"  Confidence: {thesis['confidence']:.0%}")
            print(f"  Direction:  {thesis['direction']}")
        print(f"  Framework:  {cycle.get('framework', 'none')}")

    # Section 5: Quality
    print(f"\n{'─' * width}")
    print("  5. DATA QUALITY")
    print(f"{'─' * width}")
    print(f"  Indicators: {quality.get('total_indicators', 0)}")
    print(f"  Valid:      {quality.get('valid', 0)}")
    print(f"  Degraded:   {quality.get('degraded', 0)}")
    print(f"  Failed:     {quality.get('failed', 0)}")
    print(f"  Pass Rate:  {quality.get('pass_rate', 0):.0%}")

    print(f"\n{'=' * width}")
    print("  REPORT COMPLETE")
    print(f"{'=' * width}\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="M1+M2 Daily Macro Research Runner")
    parser.add_argument(
        "--dimension", type=str, default=None,
        help="Filter to a single macro dimension (e.g., Liquidity)"
    )
    parser.add_argument(
        "--no-research", action="store_true",
        help="Skip ResearchCycleEngine (data + models only)"
    )
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  M1+M2 MACRO RESEARCH AGENT — DAILY RUNNER")
    print(f"  Project: {PROJECT_ROOT}")
    print(f"  Date:    {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*70}\n")

    runner = M1DailyRunner(run_research=not args.no_research)

    try:
        report = runner.run(for_dimension=args.dimension)
        print_report(report)
    except Exception as e:
        logger.exception("Fatal error in M1 runner")
        print(f"\nFATAL ERROR: {e}")
        sys.exit(1)
