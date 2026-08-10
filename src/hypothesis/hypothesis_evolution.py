"""Hypothesis Evolution Orchestrator — Milestone A Pipeline.

Wires together:
    Signal Engine → Candidate Generator → Historical Retriever
    → Competition Engine → Hypothesis Selector

This is the single entry point for Milestone A:
producing Top-5 hypotheses from a macro snapshot.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.hypothesis.candidate_generator import CandidateGenerator
from src.hypothesis.competition_engine import CompetitionEngine
from src.hypothesis.retriever import HistoricalRetriever
from src.hypothesis.selector import HypothesisSelector
from src.hypothesis.signal_engine import SignalEngine, SignalReport
from src.schemas.hypothesis_library import HypothesisLibraryEntry
from src.schemas.hypothesis_v3_1 import (
    HypothesisEvolutionResult,
    SelectedHypothesis,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)


class HypothesisEvolution:
    """Orchestrates the full Hypothesis Evolution pipeline.

    Usage:
        evolution = HypothesisEvolution(library_entries)
        result = evolution.evolve(
            indicators={"DXY": 102.5, "US02Y": 3.45, ...},
            regime="easing",
        )
        for h in result.selected_hypotheses:
            print(f"#{h.rank}: {h.thesis} [{h.confidence:.0%}]")
    """

    def __init__(
        self,
        library_entries: Optional[list[HypothesisLibraryEntry]] = None,
    ) -> None:
        self._signal_engine = SignalEngine()
        self._generator = CandidateGenerator()
        self._retriever = HistoricalRetriever()
        self._competition = CompetitionEngine()
        self._selector = HypothesisSelector(max_selection=5, min_dimensions_covered=3)

        self._library = library_entries or []

    def evolve(
        self,
        indicators: dict[str, float],
        regime: str = "unknown",
        library_entries: Optional[list[HypothesisLibraryEntry]] = None,
    ) -> HypothesisEvolutionResult:
        """Run the complete Hypothesis Evolution pipeline.

        Args:
            indicators: Current macro indicator values {name: value}
            regime: Known macro regime ("easing", "tightening", "neutral", "unknown")
            library_entries: Optional override for library entries

        Returns:
            HypothesisEvolutionResult with selected Top-5 + full pipeline stats
        """
        lib = library_entries if library_entries is not None else self._library

        # Step 1: Signal Engine — detect what's unusual
        signal_report = self._signal_engine.process(indicators, regime)

        # Step 2: Candidate Generator — produce ~30 candidate hypotheses
        candidates = self._generator.generate(signal_report)

        # Step 3: Historical Retriever — find similar past hypotheses
        retrieval_report = self._retriever.retrieve(candidates, lib, signal_report)

        # Step 4: Competition Engine — let hypotheses fight
        competition_round = self._competition.compete(candidates, retrieval_report)

        # Step 5: Selector — produce Top-5
        survivors = [
            c for c in candidates
            if c.candidate_id in competition_round.survivors
        ]
        selected = self._selector.select(survivors, retrieval_report, competition_round)

        # Build result
        return HypothesisEvolutionResult(
            regime=signal_report.regime,
            snapshot_summary=signal_report.summary,
            signals_detected=len(signal_report.anomalies),
            themes_identified=len(signal_report.themes),
            candidates_generated=len(candidates),
            historical_matches=retrieval_report.total_matches,
            competition_round=competition_round,
            selected_hypotheses=selected,
        )

    def describe(self, result: HypothesisEvolutionResult) -> str:
        """Generate a human-readable summary of the evolution result."""
        lines = []
        lines.append(f"══════ Hypothesis Evolution Report ══════")
        lines.append(f"Regime: {result.regime}")
        lines.append(f"Signals detected: {result.signals_detected}")
        lines.append(f"Themes identified: {result.themes_identified}")
        lines.append(f"Candidates generated: {result.candidates_generated}")
        lines.append(f"Historical matches: {result.historical_matches}")

        if result.competition_round:
            cr = result.competition_round
            lines.append(f"Competition: {cr.candidates_before} → {cr.candidates_after}")
            lines.append(f"  Contradictions found: {len(cr.contradictions_found)}")
            lines.append(f"  Eliminated: {len(cr.eliminated)}")
            for e in cr.eliminated[:5]:
                lines.append(f"    [ELIM] {e.candidate_id}: {e.reason.value} ({e.detail[:80]}...)")

        lines.append(f"")
        lines.append(f"Top-5 Selected Hypotheses:")
        for h in result.selected_hypotheses:
            lines.append(
                f"  #{h.rank} [{h.dimension}] {h.direction} "
                f"({h.confidence:.0%}): {h.thesis}"
            )
            if h.historical_backing and "no direct" not in h.historical_backing.lower():
                lines.append(f"      History: {h.historical_backing[:100]}...")

        return "\n".join(lines)

    def update_library(self, entries: list[HypothesisLibraryEntry]) -> None:
        """Update the library entries used for historical retrieval."""
        self._library = entries

    @property
    def library_size(self) -> int:
        return len(self._library)
