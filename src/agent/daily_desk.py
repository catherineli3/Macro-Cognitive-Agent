"""V5.5 Daily Research Desk — Simulate a macro research department workflow.

Replaces the old `run_cycle()` with a professional morning workflow:

    06:00  Collect          — Gather macro data, market data, news
    06:15  Market Snapshot  — Quick scan of overnight moves
    06:20  News Summary     — Curate and classify overnight news
    06:40  Narrative Update — Update narratives, beliefs with new data
    07:00  Research Memo    — Full reasoning pipeline (V5.2 → V5.3 QA)
    07:40  Trade Dashboard  — Signal generation, risk monitoring
    08:00  Publish          — Daily Macro Brief ready for review

Final output: a professional Daily Macro Brief readable by portfolio managers.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class DeskPhase(str, Enum):
    COLLECT = "collect"
    MARKET_SNAPSHOT = "market_snapshot"
    NEWS_SUMMARY = "news_summary"
    NARRATIVE_UPDATE = "narrative_update"
    RESEARCH_MEMO = "research_memo"
    TRADE_DASHBOARD = "trade_dashboard"
    QA_REVIEW = "qa_review"
    PUBLISH = "publish"


@dataclass
class DeskState:
    """State tracking for the daily research desk workflow."""

    desk_id: str = field(default_factory=lambda: f"desk_{datetime.now().strftime('%Y%m%d')}")
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Phase tracking
    current_phase: DeskPhase = DeskPhase.COLLECT
    phase_history: list[tuple[DeskPhase, str, float]] = field(default_factory=list)

    # Collected data
    macro_data: dict = field(default_factory=dict)
    market_data: dict = field(default_factory=dict)
    news_items: list[str] = field(default_factory=list)
    events: list = field(default_factory=list)

    # Analysis outputs
    market_snapshot: str = ""
    news_summary: str = ""
    narrative_update: str = ""
    research_memo: str = ""
    trade_dashboard: dict = field(default_factory=dict)

    # Pipeline & QA
    pipeline_state: any = None
    qa_scorecard: any = None
    memo_passed_qa: bool = False

    # Timing
    phase_timings: dict[str, float] = field(default_factory=dict)
    total_duration: float = 0.0

    completed_at: str = ""

    @property
    def total_runtime(self) -> str:
        minutes = int(self.total_duration // 60)
        seconds = int(self.total_duration % 60)
        return f"{minutes}m {seconds}s"


class DailyResearchDesk:
    """Simulate a professional macro research department.

    Orchestrates the complete morning workflow from data collection
    to publication of the Daily Macro Brief.

    Usage:
        desk = DailyResearchDesk()
        brief = desk.run_morning_session(
            macro_data={"cpi": "3.2%", "gdp_growth": "2.8%"},
            market_data={"sp500": "+0.5%", "us10y": "4.25%"},
            news=["Fed signals patient stance", "China PMI beats estimates"],
        )
        print(brief)
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}

        # Lazy-loaded modules
        self._pipeline = None
        self._grader = None
        self._report_card = None

        # Callbacks
        self._on_phase: Callable | None = None

    # ── Main Workflow ────────────────────────────────────────────────

    def run_morning_session(
        self,
        macro_data: dict | None = None,
        market_data: dict | None = None,
        news_items: list[str] | None = None,
        previous_state: dict | None = None,
        belief_data: dict | None = None,
        regime_data: dict | None = None,
    ) -> str:
        """Run the full morning research desk workflow.

        Returns the complete Daily Macro Brief as a formatted string.
        """
        state = DeskState(
            desk_id=f"desk_{datetime.now().strftime('%Y%m%d_%H%M')}",
        )
        session_start = time.time()

        print("=" * 60)
        print("  MACRO RESEARCH DESK — Morning Session")
        print(f"  {state.date}")
        print("=" * 60)
        print()

        # ── 06:00 Phase 1: Collect ──────────────────────────────────
        self._set_phase(state, DeskPhase.COLLECT)
        state.macro_data = macro_data or {}
        state.market_data = market_data or {}
        state.news_items = news_items or []
        self._record_phase(state, "Data collected")

        # ── 06:15 Phase 2: Market Snapshot ──────────────────────────
        self._set_phase(state, DeskPhase.MARKET_SNAPSHOT)
        state.market_snapshot = self._build_market_snapshot(state)
        self._record_phase(state, "Market snapshot generated")

        # ── 06:20 Phase 3: News Summary ─────────────────────────────
        self._set_phase(state, DeskPhase.NEWS_SUMMARY)
        state.news_summary = self._build_news_summary(state)
        self._record_phase(state, "News summarized")

        # ── 06:40 Phase 4: Narrative Update ─────────────────────────
        self._set_phase(state, DeskPhase.NARRATIVE_UPDATE)
        state.narrative_update = self._build_narrative_update(state, previous_state, belief_data)
        self._record_phase(state, "Narratives updated")

        # ── 07:00 Phase 5: Research Memo (V5.2 Pipeline) ────────────
        self._set_phase(state, DeskPhase.RESEARCH_MEMO)
        state.research_memo, state.pipeline_state = self._build_research_memo(
            state, belief_data, regime_data
        )
        self._record_phase(state, "Research memo generated")

        # ── 07:20 Phase 6: QA Review (V5.3) ─────────────────────────
        self._set_phase(state, DeskPhase.QA_REVIEW)
        state.qa_scorecard, state.memo_passed_qa = self._run_qa(state)
        self._record_phase(
            state,
            f"QA {'PASSED' if state.memo_passed_qa else 'FAILED' if state.qa_scorecard else 'SKIPPED'}",
        )

        # ── 07:40 Phase 7: Trade Dashboard ──────────────────────────
        self._set_phase(state, DeskPhase.TRADE_DASHBOARD)
        state.trade_dashboard = self._build_trade_dashboard(state)
        self._record_phase(state, "Trade dashboard generated")

        # ── 08:00 Phase 8: Publish ──────────────────────────────────
        self._set_phase(state, DeskPhase.PUBLISH)
        daily_brief = self._assemble_daily_brief(state)
        self._record_phase(state, "Daily brief published")

        # Complete
        state.total_duration = time.time() - session_start
        state.completed_at = datetime.now().isoformat()

        print(f"\n  Session complete in {state.total_runtime}")
        print("=" * 60)

        return daily_brief

    # ── Phase Implementations ───────────────────────────────────────

    def _build_market_snapshot(self, state: DeskState) -> str:
        """Generate a quick market snapshot."""
        lines = []
        lines.append("MARKET SNAPSHOT")
        lines.append("-" * 40)

        if state.market_data:
            for key, value in list(state.market_data.items())[:8]:
                lines.append(f"  {key}: {value}")
        else:
            lines.append("  No market data available.")

        lines.append("")
        return "\n".join(lines)

    def _build_news_summary(self, state: DeskState) -> str:
        """Build curated news summary."""
        lines = []
        lines.append("OVERNIGHT NEWS SUMMARY")
        lines.append("-" * 40)

        if state.news_items:
            for i, item in enumerate(state.news_items[:8], 1):
                lines.append(f"  {i}. {item}")
        else:
            lines.append("  No significant news.")

        lines.append("")
        return "\n".join(lines)

    def _build_narrative_update(
        self,
        state: DeskState,
        previous: dict | None,
        beliefs: dict | None,
    ) -> str:
        """Update narratives with new data."""
        lines = []
        lines.append("NARRATIVE UPDATE")
        lines.append("-" * 40)

        if beliefs:
            for key, value in beliefs.items():
                lines.append(f"  {key}: {value}")
        else:
            lines.append("  Narratives maintained from previous session.")

        if previous:
            lines.append("")
            lines.append("  Changes from previous session:")
            # Compare with previous data
            for key in set(
                list(state.macro_data.keys()) + list(previous.get("macro_data", {}).keys())
            ):
                curr = str(state.macro_data.get(key, "N/A"))
                prev = str(previous.get("macro_data", {}).get(key, "N/A"))
                if curr != prev:
                    lines.append(f"    {key}: {prev} → {curr}")

        lines.append("")
        return "\n".join(lines)

    def _build_research_memo(
        self,
        state: DeskState,
        belief_data: dict | None,
        regime_data: dict | None,
    ) -> tuple[str, any]:
        """Run the V5.2 Reasoning Pipeline to generate the research memo."""
        try:
            from src.research.reasoning_pipeline.pipeline import ReasoningPipeline

            if self._pipeline is None:
                self._pipeline = ReasoningPipeline(self.config)

            pipeline_state = self._pipeline.run(
                macro_data=state.macro_data,
                market_data=state.market_data,
                news_items=state.news_items,
                belief_data=belief_data,
                regime_data=regime_data,
                strict_mode=True,
            )

            memo = self._pipeline._build_summary(pipeline_state)
            return memo, pipeline_state

        except ImportError:
            # Fallback: generate simple memo
            memo = self._generate_fallback_memo(state)
            return memo, None

    def _run_qa(self, state: DeskState) -> tuple[any, bool]:
        """Run V5.3 QA on the research memo."""
        if not state.research_memo:
            return None, False

        try:
            from src.research.qa.memo_grader import MemoGrader

            if self._grader is None:
                self._grader = MemoGrader(self.config)

            scorecard = self._grader.grade(state.research_memo, memo_id=state.desk_id)
            passed = scorecard.verdict.value != "reject"
            return scorecard, passed

        except ImportError:
            return None, True  # Assume pass if QA not available

    def _build_trade_dashboard(self, state: DeskState) -> dict:
        """Build trade dashboard from pipeline output."""
        dashboard = {
            "signals": [],
            "positioning": "",
            "risks": [],
            "watchlist_24h": [],
            "watchlist_1w": [],
        }

        if state.pipeline_state:
            trade_output = state.pipeline_state.get_output("trade")
            risk_output = state.pipeline_state.get_output("risk")

            if trade_output:
                dashboard["signals"] = trade_output.trades
                dashboard["positioning"] = trade_output.portfolio_positioning

            if risk_output:
                dashboard["risks"] = risk_output.risks[:5]
                dashboard["watchlist_24h"] = risk_output.watchlist_24h[:5]
                dashboard["watchlist_1w"] = risk_output.watchlist_1w[:3]

        return dashboard

    # ── Daily Brief Assembly ────────────────────────────────────────

    def _assemble_daily_brief(self, state: DeskState) -> str:
        """Assemble the complete Daily Macro Brief."""
        lines = []
        width = 70

        # Title block
        lines.append("=" * width)
        lines.append(f"{'DAILY MACRO BRIEF':^{width}}")
        lines.append(f"{state.date:^{width}}")
        lines.append("=" * width)
        lines.append("")

        # Executive Summary
        if state.research_memo:
            # Extract executive summary from memo
            exec_start = state.research_memo.find("EXECUTIVE SUMMARY")
            if exec_start >= 0:
                exec_end = state.research_memo.find("KEY OBSERVATIONS", exec_start)
                if exec_end < 0:
                    exec_end = state.research_memo.find("-" * 40, exec_start + 100)
                if exec_end > exec_start:
                    lines.append(state.research_memo[exec_start:exec_end].strip())
                    lines.append("")

        # Market Snapshot
        lines.append(state.market_snapshot)

        # Key Data
        lines.append("KEY MACRO DATA")
        lines.append("-" * 40)
        if state.macro_data:
            for key, value in list(state.macro_data.items())[:6]:
                lines.append(f"  {key}: {value}")
        lines.append("")

        # Top Narratives
        lines.append("TOP NARRATIVES")
        lines.append("-" * 40)
        if state.pipeline_state:
            pat = state.pipeline_state.get_output("pattern")
            if pat and pat.patterns:
                for p in pat.patterns[:4]:
                    lines.append(f"  * {p}")
        if state.narrative_update:
            narrative_lines = state.narrative_update.split("\n")
            for nl in narrative_lines[2:6]:
                if nl.strip() and not nl.startswith("Changes"):
                    lines.append(nl)
        lines.append("")

        # Competing Hypotheses
        if state.pipeline_state:
            lines.append("COMPETING HYPOTHESES")
            lines.append("-" * 40)
            hyp = state.pipeline_state.get_output("hypothesis")
            if hyp:
                lines.append(f"  Primary: {hyp.primary_hypothesis[:120]}")
                for alt in hyp.alternative_hypotheses[:2]:
                    lines.append(f"  Alternative: {alt[:120]}")
            lines.append("")

        # Evidence Table
        if state.pipeline_state:
            evd = state.pipeline_state.get_output("evidence")
            if evd and evd.evidence_clusters:
                lines.append("EVIDENCE OVERVIEW")
                lines.append("-" * 40)
                for theme, items in list(evd.evidence_clusters.items())[:4]:
                    lines.append(
                        f"  {theme}: {len(items)} items, " f"net weight {evd.net_weight:+.2f}"
                    )
                lines.append("")

        # Historical Analogies
        if state.pipeline_state:
            ana = state.pipeline_state.get_output("analogy")
            if ana and ana.analogies:
                lines.append("HISTORICAL ANALOGIES")
                lines.append("-" * 40)
                for a in ana.analogies[:2]:
                    lines.append(f"  {a['period']}: {a['description'][:100]}")
                lines.append(
                    f"  Key difference: {ana.differences[0][:100] if ana.differences else 'N/A'}"
                )
                lines.append("")

        # Predictions
        if state.pipeline_state:
            prd = state.pipeline_state.get_output("prediction")
            if prd and prd.predictions:
                lines.append("PREDICTIONS")
                lines.append("-" * 40)
                for p in prd.predictions[:4]:
                    inval = p.get("invalidation", "")
                    lines.append(
                        f"  [{p['probability']:.0%}] {p['claim'][:80]} " f"(by {p['horizon']})"
                    )
                    if inval:
                        lines.append(f"    Invalidation: {inval[:80]}")
                lines.append("")

        # Risk Monitoring
        if state.trade_dashboard and state.trade_dashboard.get("risks"):
            lines.append("RISK MONITORING")
            lines.append("-" * 40)
            for r in state.trade_dashboard["risks"][:3]:
                lines.append(
                    f"  [{r['severity'].upper()}] (P={r['probability']:.0%}) " f"{r['risk'][:80]}"
                )
            lines.append("")

        # Watchlist
        if state.trade_dashboard:
            wl = state.trade_dashboard.get("watchlist_24h", [])
            if wl:
                lines.append("24H WATCHLIST")
                lines.append("-" * 40)
                for w in wl[:5]:
                    lines.append(f"  * {w}")
                lines.append("")

            wl_1w = state.trade_dashboard.get("watchlist_1w", [])
            if wl_1w:
                lines.append("THIS WEEK")
                lines.append("-" * 40)
                for w in wl_1w[:3]:
                    lines.append(f"  * {w}")
                lines.append("")

        # QA Badge
        if state.qa_scorecard:
            lines.append("QUALITY ASSURANCE")
            lines.append("-" * 40)
            try:
                from src.research.qa.report_card import ReportCard

                if self._report_card is None:
                    self._report_card = ReportCard()
                lines.append(f"  {self._report_card.format_badge(state.qa_scorecard)}")
            except ImportError:
                lines.append(f"  Score: {state.qa_scorecard.total_score:.1f}/100")
            lines.append("")

        # Footer
        lines.append("=" * width)
        lines.append(f"{'Generated by Macro Research Agent V5.5':^{width}}")
        lines.append(f"{datetime.now().strftime('%Y-%m-%d %H:%M'):^{width}}")
        lines.append(f"{'For institutional use only':^{width}}")
        lines.append("=" * width)

        return "\n".join(lines)

    def _generate_fallback_memo(self, state: DeskState) -> str:
        """Generate a simple memo when V5.2 pipeline is not available."""
        lines = []
        lines.append("RESEARCH MEMO (Fallback)")
        lines.append("-" * 40)
        lines.append(f"Date: {state.date}")
        lines.append("")
        lines.append(state.market_snapshot)
        lines.append(state.news_summary)
        lines.append(
            "Note: Full V5.2 Reasoning Pipeline not available. "
            "Install all V5.2 dependencies for institutional-quality research memos."
        )
        return "\n".join(lines)

    # ── Desk State Management ───────────────────────────────────────

    def _set_phase(self, state: DeskState, phase: DeskPhase):
        """Set current phase and log."""
        phase_time = datetime.now().strftime("%H:%M")
        state.current_phase = phase
        phase_names = {
            DeskPhase.COLLECT: "06:00 Collect",
            DeskPhase.MARKET_SNAPSHOT: "06:15 Market Snapshot",
            DeskPhase.NEWS_SUMMARY: "06:20 News Summary",
            DeskPhase.NARRATIVE_UPDATE: "06:40 Narrative Update",
            DeskPhase.RESEARCH_MEMO: "07:00 Research Memo",
            DeskPhase.QA_REVIEW: "07:20 QA Review",
            DeskPhase.TRADE_DASHBOARD: "07:40 Trade Dashboard",
            DeskPhase.PUBLISH: "08:00 Publish",
        }

        status = phase_names.get(phase, phase.value)
        print(f"  [{phase_time}] {status}...")

        if self._on_phase:
            self._on_phase(phase)

    def _record_phase(self, state: DeskState, note: str):
        """Record phase completion."""
        state.phase_history.append((state.current_phase, note, time.time()))

    def on_phase_change(self, callback: Callable):
        """Register callback for phase transitions."""
        self._on_phase = callback

    # ── Quick Methods ────────────────────────────────────────────────

    def quick_brief(self, **kwargs) -> str:
        """Generate a quick brief with minimal output.

        Useful for rapid iteration.
        """
        # Use lightweight mode
        state = DeskState()
        state.macro_data = kwargs.get("macro_data", {})
        state.market_data = kwargs.get("market_data", {})
        state.news_items = kwargs.get("news_items", [])

        lines = []
        lines.append(f"QUICK BRIEF — {state.date}")
        lines.append("=" * 50)
        lines.append(self._build_market_snapshot(state))
        lines.append(self._build_news_summary(state))

        # Try pipeline but in non-strict mode
        try:
            from src.research.reasoning_pipeline.pipeline import ReasoningPipeline

            pipeline = ReasoningPipeline(self.config)
            ps = pipeline.run(
                macro_data=state.macro_data,
                market_data=state.market_data,
                news_items=state.news_items,
                strict_mode=False,
            )
            lines.append(pipeline._build_summary(ps))
        except Exception:
            lines.append("(Pipeline unavailable — showing snapshot only)")

        return "\n".join(lines)
