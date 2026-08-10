"""Comprehensive tests for Milestone D: Autonomous Research Cycle.

Tests cover:
    D2: ResearchThesis & MacroSnapshot schemas
    D3: FrameworkSelector (framework activation)
    D4: ThesisGenerator (hypothesis→thesis upgrade)
    D5: ResearchMemory (persistent history)
    D6.1: OutcomeTracker (outcome detection)
    D6.2: Postmortem (root cause analysis)
    D1: ResearchCycleEngine (full cycle integration)
"""

import pytest
import json
import tempfile
import os
from datetime import datetime, timezone
from pathlib import Path

# ── Imports ────────────────────────────────────────────────────────────────

from src.schemas.macro_snapshot import MacroSnapshot, MarketSnapshot
from src.schemas.research_thesis import (
    ResearchThesis, ThesisStatus, ThesisOutcome,
)
from src.research.evolution.regime_gate import RegimeSnapshot
from src.research_cycle.framework_selector import (
    FrameworkSelector, FrameworkSelection,
)
from src.research_cycle.thesis_generator import ThesisGenerator
from src.research_cycle.research_memory import (
    ResearchMemory, ResearchMemoryEntry, PostmortemReport,
)
from src.research_cycle.outcome_tracker import (
    OutcomeTracker, PendingThesis,
)
from src.research_cycle.postmortem import Postmortem
from src.research_cycle.cycle_engine import (
    ResearchCycleEngine, CycleResult,
)


# ═══════════════════════════════════════════════════════════════════════════════
# D2: Schema Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestResearchThesis:
    """Test ResearchThesis schema creation and lifecycle."""

    def test_create_thesis(self):
        thesis = ResearchThesis(
            title="Liquidity Expansion Drives Long Duration Assets",
            core_belief="Fed liquidity dominates earnings slowdown.",
            transmission_chain=[
                "Fed Balance Sheet +",
                "USD Liquidity +",
                "Credit Spread Compression",
                "Long Duration Equities +"
            ],
            evidence=["DXY declining", "HYG outperforming", "Financial conditions easing"],
            counter_arguments=["Inflation rebound could invalidate"],
            invalidation_conditions=["10Y > 5%", "Credit spread widening"],
            confidence=0.72,
            expected_window="30-90 days",
        )
        assert thesis.thesis_id.startswith("thesis-")
        assert thesis.is_well_formed
        assert thesis.status == ThesisStatus.DRAFT
        assert thesis.chain_depth == 4
        assert thesis.evidence_count == 3

    def test_thesis_lifecycle(self):
        thesis = ResearchThesis(
            title="Test",
            core_belief="Test belief",
            transmission_chain=["A", "B"],
            evidence=["E1", "E2"],
            invalidation_conditions=["C1"],
            confidence=0.5,
        )
        assert thesis.status == ThesisStatus.DRAFT

        thesis.activate()
        assert thesis.status == ThesisStatus.ACTIVE
        assert thesis.activated_at is not None

        thesis.validate(ThesisOutcome(verified=True))
        assert thesis.status == ThesisStatus.VALIDATED

    def test_thesis_invalidation(self):
        thesis = ResearchThesis(
            title="Test",
            core_belief="Test",
            transmission_chain=["A", "B"],
            evidence=["E1", "E2"],
            invalidation_conditions=["C1"],
            confidence=0.5,
        )
        thesis.invalidate("10Y > 5%")
        assert thesis.status == ThesisStatus.INVALIDATED
        assert thesis.outcome.invalidation_triggered == "10Y > 5%"
        assert not thesis.outcome.verified

    def test_thesis_well_formed_check(self):
        # Missing components
        bad_thesis = ResearchThesis()
        assert not bad_thesis.is_well_formed

        # Minimum viable thesis
        minimal = ResearchThesis(
            title="T",
            core_belief="X",
            transmission_chain=["A", "B"],
            evidence=["E1", "E2"],
            invalidation_conditions=["C1"],
            confidence=0.1,
        )
        assert minimal.is_well_formed

    def test_thesis_serialization(self):
        thesis = ResearchThesis(
            title="Test Serialization",
            core_belief="Core belief",
            transmission_chain=["A", "B"],
            evidence=["E1", "E2"],
            invalidation_conditions=["C1"],
            confidence=0.65,
            expected_window="30-90 days",
            framework_used=["fw-1"],
        )
        data = thesis.to_dict()
        assert data["title"] == "Test Serialization"
        assert data["confidence"] == 0.65

        # Roundtrip
        rebuilt = ResearchThesis.from_dict(data)
        assert rebuilt.thesis_id == thesis.thesis_id
        assert rebuilt.confidence == thesis.confidence

    def test_thesis_format(self):
        thesis = ResearchThesis(
            title="Format Test",
            core_belief="A causes B",
            transmission_chain=["Step 1", "Step 2"],
            evidence=["Evidence 1"],
            counter_arguments=["Counter 1"],
            invalidation_conditions=["Condition 1"],
            confidence=0.7,
        )
        formatted = thesis.format()
        assert "FORMAT TEST" in formatted.upper()
        assert "CORE BELIEF" in formatted
        assert "TRANSMISSION" in formatted
        assert "EVIDENCE" in formatted
        assert "COUNTER" in formatted
        assert "INVALIDATION" in formatted


class TestThesisOutcome:
    """Test ThesisOutcome."""

    def test_outcome_success(self):
        outcome = ThesisOutcome(verified=True)
        assert outcome.is_success

    def test_outcome_failure(self):
        outcome = ThesisOutcome(verified=False, invalidation_triggered="VIX > 30")
        assert not outcome.is_success
        assert "INVALIDATED" in outcome.describe().upper()

    def test_outcome_describe(self):
        outcome = ThesisOutcome(verified=True, realized_return=0.05)
        assert "+5.00%" in outcome.describe()


class TestMacroSnapshot:
    """Test MacroSnapshot schema."""

    def test_create_snapshot(self):
        regime = RegimeSnapshot(
            monetary_policy="easing",
            fiscal_stance="neutral",
            volatility="low",
            growth="accelerating",
            inflation="stable",
        )
        market = MarketSnapshot(indicators={
            "spx": 5200, "vix": 15.3, "dxy": 104.2, "us10y": 4.25,
        })
        snapshot = MacroSnapshot(regime=regime, market=market)
        assert snapshot.regime_label == "Early Easing / Growth"
        assert snapshot.signal_count == 0

    def test_regime_labels(self):
        # Early Easing / Growth
        r1 = RegimeSnapshot(monetary_policy="easing", growth="accelerating")
        assert MacroSnapshot(regime=r1).regime_label == "Early Easing / Growth"

        # Tightening / Inflation Fight
        r2 = RegimeSnapshot(monetary_policy="tightening", inflation="rising")
        assert "Tightening" in MacroSnapshot(regime=r2).regime_label

        # Goldilocks
        r3 = RegimeSnapshot(growth="accelerating", inflation="stable", monetary_policy="neutral")
        assert "Goldilocks" in MacroSnapshot(regime=r3).regime_label

        # High Vol
        r4 = RegimeSnapshot(volatility="high")
        assert "High Volatility" in MacroSnapshot(regime=r4).regime_label

    def test_from_regime_factory(self):
        regime = RegimeSnapshot(monetary_policy="easing")
        snapshot = MacroSnapshot.from_regime(regime, market_data={"spx": 5000})
        assert snapshot.regime_label == "Early Easing / Growth"
        assert snapshot.market.get("spx") == 5000

    def test_market_snapshot(self):
        market = MarketSnapshot(indicators={"vix": 20, "dxy": 105})
        assert market.count == 2
        assert market.get("vix") == 20
        assert market.get("non_existent", 0.0) == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# D3: FrameworkSelector Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFrameworkSelector:
    """Test FrameworkSelector behavior."""

    def test_select_no_frameworks(self):
        fs = FrameworkSelector()
        snapshot = MacroSnapshot(
            regime=RegimeSnapshot(monetary_policy="easing"),
        )
        selection = fs.select(snapshot)
        assert selection.regime_label != ""
        assert not selection.has_selection

    def test_select_empty_snapshot(self):
        fs = FrameworkSelector()
        selection = fs.select(MacroSnapshot())
        assert not selection.has_selection
        assert "No active frameworks" in selection.selection_rationale

    def test_selection_describe_empty(self):
        selection = FrameworkSelection()
        desc = selection.describe()
        assert desc != ""

    def test_selection_describe_with_framework(self):
        from src.schemas.research import ResearchFramework
        fw = ResearchFramework(name="Test FW")
        selection = FrameworkSelection(
            primary_framework=fw,
            ranked=[(fw, 0.8)],
            regime_label="Test Regime",
            activation_scores={fw.framework_id: 0.8},
            selection_rationale="Test rationale",
        )
        assert selection.has_selection
        assert selection.top_framework_id == fw.framework_id
        desc = selection.describe()
        assert "Test FW" in desc

    def test_regime_match_methods(self):
        fs = FrameworkSelector()
        assert fs._monetary_policy_match("easing") > fs._monetary_policy_match("tightening")
        assert fs._growth_match("accelerating") > fs._growth_match("contracting")
        assert fs._inflation_match("stable") > fs._inflation_match("rising")


# ═══════════════════════════════════════════════════════════════════════════════
# D4: ThesisGenerator Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestThesisGenerator:
    """Test ThesisGenerator — hypothesis→thesis upgrade."""

    def test_generate_basic_thesis(self):
        tg = ThesisGenerator()
        snapshot = MacroSnapshot(
            regime=RegimeSnapshot(monetary_policy="easing", growth="stable"),
            market=MarketSnapshot(indicators={"spx": 5200, "vix": 15}),
        )
        selection = FrameworkSelection(regime_label="Early Easing")

        thesis = tg.generate(selection, snapshot)
        assert thesis.title != ""
        assert thesis.core_belief != ""
        assert len(thesis.evidence) > 0
        assert len(thesis.invalidation_conditions) > 0
        assert thesis.confidence > 0
        assert thesis.regime_label == "Early Easing / Growth"

    def test_generate_with_market_data_conditions(self):
        tg = ThesisGenerator()
        snapshot = MacroSnapshot(
            regime=RegimeSnapshot(monetary_policy="easing", volatility="low"),
            market=MarketSnapshot(indicators={
                "us10y": 4.25, "vix": 15.3, "spx": 5200, "dxy": 104.2,
            }),
        )
        selection = FrameworkSelection(regime_label="Test")
        thesis = tg.generate(selection, snapshot)

        # Should have invalidation conditions based on market data
        assert thesis.confidence > 0
        assert len(thesis.invalidation_conditions) >= 1

    def test_generate_empty_inputs(self):
        tg = ThesisGenerator()
        thesis = tg.generate(FrameworkSelection(), MacroSnapshot())
        assert thesis is not None
        assert thesis.status == ThesisStatus.DRAFT

    def test_infer_asset_impact(self):
        tg = ThesisGenerator()
        # Easing + accelerating
        s1 = MacroSnapshot(regime=RegimeSnapshot(monetary_policy="easing", growth="accelerating"))
        impact = tg._infer_asset_impact(s1)
        assert "risk assets" in impact.lower()

        # Tightening + rising inflation
        s2 = MacroSnapshot(regime=RegimeSnapshot(monetary_policy="tightening", inflation="rising"))
        impact = tg._infer_asset_impact(s2)
        assert len(impact) > 0

    def test_determine_window(self):
        tg = ThesisGenerator()
        # High vol = shorter
        s1 = MacroSnapshot(regime=RegimeSnapshot(volatility="high"))
        w1 = tg._determine_window(FrameworkSelection(), s1)
        assert "14" in w1 or "45" in w1

        # Normal
        s2 = MacroSnapshot(regime=RegimeSnapshot(monetary_policy="easing"))
        w2 = tg._determine_window(FrameworkSelection(), s2)
        assert w2 == "30-90 days"


# ═══════════════════════════════════════════════════════════════════════════════
# D5: ResearchMemory Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestResearchMemory:
    """Test ResearchMemory persistence and queries."""

    @pytest.fixture
    def memory(self, tmp_path):
        path = str(tmp_path / "test_memory.json")
        mem = ResearchMemory(path)
        yield mem
        # Cleanup
        mem.clear()

    def test_record_and_retrieve(self, memory):
        entry = ResearchMemoryEntry(
            cycle_number=1,
            regime_label="Early Easing",
            framework_used=["fw-1"],
            learning_note="Liquidity thesis validated",
        )
        eid = memory.record_entry(entry)
        assert eid != ""

        retrieved = memory.get_entry(eid)
        assert retrieved is not None
        assert retrieved.cycle_number == 1
        assert retrieved.regime_label == "Early Easing"

    def test_get_recent(self, memory):
        for i in range(5):
            entry = ResearchMemoryEntry(cycle_number=i + 1)
            memory.record_entry(entry)

        recent = memory.get_recent(3)
        assert len(recent) == 3
        # Most recent first (reversed)
        assert recent[0].cycle_number > recent[-1].cycle_number

    def test_query_by_regime(self, memory):
        for i, label in enumerate(["Early Easing", "Tightening", "Early Easing"]):
            entry = ResearchMemoryEntry(cycle_number=i + 1, regime_label=label)
            memory.record_entry(entry)

        results = memory.query_by_regime("Easing")
        assert len(results) >= 2

    def test_query_by_framework(self, memory):
        for i in range(3):
            entry = ResearchMemoryEntry(cycle_number=i + 1, framework_used=["fw-a"])
            memory.record_entry(entry)
        entry = ResearchMemoryEntry(cycle_number=4, framework_used=["fw-b"])
        memory.record_entry(entry)

        results_a = memory.query_by_framework("fw-a")
        assert len(results_a) == 3

        results_b = memory.query_by_framework("fw-b")
        assert len(results_b) == 1

    def test_success_rate(self, memory):
        # Add validated
        e1 = ResearchMemoryEntry(cycle_number=1, thesis=ResearchThesis(
            title="T1", core_belief="B1", transmission_chain=["A","B"],
            evidence=["E1","E2"], invalidation_conditions=["C1"], confidence=0.5,
        ))
        e1.outcome = ThesisOutcome(verified=True)
        memory.record_entry(e1)

        # Add invalidated
        e2 = ResearchMemoryEntry(cycle_number=2)
        e2.outcome = ThesisOutcome(verified=False)
        memory.record_entry(e2)

        assert memory.total_entries == 2
        assert memory.success_rate == 0.5

    def test_export(self, memory, tmp_path):
        entry = ResearchMemoryEntry(cycle_number=1)
        memory.record_entry(entry)

        export_path = str(tmp_path / "export.json")
        result = memory.export(export_path)
        assert os.path.exists(result)

    def test_summary(self, memory):
        entry = ResearchMemoryEntry(cycle_number=1, regime_label="Test", learning_note="Learned something")
        memory.record_entry(entry)
        summary = memory.summary()
        assert "Research Memory" in summary
        assert "Test" in summary


# ═══════════════════════════════════════════════════════════════════════════════
# D6.1: OutcomeTracker Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOutcomeTracker:
    """Test OutcomeTracker behavior."""

    def test_register_thesis(self):
        tracker = OutcomeTracker()
        thesis = ResearchThesis(
            title="Test",
            core_belief="Belief",
            transmission_chain=["A", "B"],
            evidence=["E1", "E2"],
            invalidation_conditions=["10Y > 5%"],
            confidence=0.6,
        )
        pending = tracker.register_thesis(thesis)
        assert tracker.pending_count == 1
        assert pending.invalidation_conditions == ["10Y > 5%"]

    def test_determine_outcome_no_trigger(self):
        tracker = OutcomeTracker()
        thesis = ResearchThesis(
            title="Test",
            core_belief="Risk-on environment",
            transmission_chain=["A", "B"],
            evidence=["E1", "E2"],
            invalidation_conditions=["10Y > 5%"],
            confidence=0.6,
        )
        tracker.register_thesis(thesis)

        actual = {"spx": 5300, "prev_spx": 5000}  # Market up = risk-on validated
        outcome = tracker.determine_outcome(thesis, actual)
        assert outcome.verified

    def test_determine_outcome_triggered(self):
        tracker = OutcomeTracker()
        thesis = ResearchThesis(
            title="Test",
            core_belief="Belief",
            transmission_chain=["A", "B"],
            evidence=["E1", "E2"],
            invalidation_conditions=["10Y Treasury yield exceeds 4.75%"],
            confidence=0.6,
        )
        tracker.register_thesis(thesis)

        actual = {"us10y": 4.80}  # Triggers the condition
        triggered = tracker.check_invalidation(thesis.thesis_id, actual)
        assert triggered is not None
        assert "4.75" in triggered

    def test_vix_trigger(self):
        tracker = OutcomeTracker()
        thesis = ResearchThesis(
            title="Test",
            core_belief="B",
            transmission_chain=["A", "B"],
            evidence=["E1", "E2"],
            invalidation_conditions=["VIX spikes above 30"],
            confidence=0.6,
        )
        tracker.register_thesis(thesis)
        actual = {"vix": 35}
        triggered = tracker.check_invalidation(thesis.thesis_id, actual)
        assert triggered is not None

    def test_pending_list(self):
        tracker = OutcomeTracker()
        thesis1 = ResearchThesis(
            title="T1", core_belief="B", transmission_chain=["A","B"],
            evidence=["E1","E2"], invalidation_conditions=["C1"], confidence=0.5,
        )
        thesis2 = ResearchThesis(
            title="T2", core_belief="B", transmission_chain=["A","B"],
            evidence=["E1","E2"], invalidation_conditions=["C1"], confidence=0.5,
        )
        tracker.register_thesis(thesis1)
        tracker.register_thesis(thesis2)

        pending = tracker.get_pending_theses()
        assert len(pending) == 2
        assert thesis1.thesis_id in pending
        assert thesis2.thesis_id in pending

    def test_extract_number(self):
        tracker = OutcomeTracker()
        assert tracker._extract_number("10Y Treasury yield exceeds 4.75%") == 4.75
        assert tracker._extract_number("S&P 500 drops below 4,680") == 4680.0
        assert tracker._extract_number("VIX spikes above 30") == 30.0
        assert tracker._extract_number("no numbers here") is None


# ═══════════════════════════════════════════════════════════════════════════════
# D6.2: Postmortem Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPostmortem:
    """Test Postmortem analysis."""

    def test_analyze_success(self):
        pm = Postmortem()
        thesis = ResearchThesis(
            title="Liquidity Thesis",
            core_belief="Liquidity expansion drives risk assets",
            transmission_chain=["Fed easing", "Liquidity increases", "Risk assets rise"],
            evidence=["DXY down", "Credit spreads tightening"],
            invalidation_conditions=["Fed hikes unexpectedly"],
            confidence=0.7,
        )
        outcome = ThesisOutcome(verified=True)
        report = pm.analyze(thesis, outcome)
        assert report.thesis_validated
        assert "appropriate" in report.framework_assessment.lower() or "Framework" in report.framework_assessment

    def test_analyze_failure(self):
        pm = Postmortem()
        thesis = ResearchThesis(
            title="Growth Thesis",
            core_belief="AI capex drives semiconductor rally",
            transmission_chain=["AI demand", "Chip orders", "Semis rally"],
            evidence=["Nvidia guidance strong"],
            invalidation_conditions=["Nvidia guidance cut"],
            confidence=0.65,
        )
        outcome = ThesisOutcome(
            verified=False,
            invalidation_triggered="Nvidia guidance cut",
        )
        report = pm.analyze(thesis, outcome, diagnosis_notes="Transmission broke at chip orders")
        assert not report.thesis_validated
        assert report.root_cause != ""
        assert report.learning != ""

    def test_classify_failure(self):
        pm = Postmortem()
        thesis = ResearchThesis(
            title="T", core_belief="B",
            transmission_chain=["A", "B"], evidence=["E1", "E2"],
            invalidation_conditions=["C1"], confidence=0.5,
        )
        outcome = ThesisOutcome(verified=False)
        # Transmission notes
        cat1 = pm._classify_failure(thesis, outcome, "Credit transmission broke")
        assert "credit" in cat1

        # Unknown
        cat2 = pm._classify_failure(thesis, outcome, "")
        assert cat2 == "framework_wrong"

    def test_report_collection(self):
        pm = Postmortem()
        thesis = ResearchThesis(
            title="T", core_belief="B",
            transmission_chain=["A", "B"], evidence=["E1", "E2"],
            invalidation_conditions=["C1"], confidence=0.5,
        )

        pm.analyze(thesis, ThesisOutcome(verified=True))
        pm.analyze(thesis, ThesisOutcome(verified=False))
        assert pm.report_count == 2

    def test_success_rate(self):
        pm = Postmortem()
        thesis = ResearchThesis(
            title="T", core_belief="B",
            transmission_chain=["A", "B"], evidence=["E1", "E2"],
            invalidation_conditions=["C1"], confidence=0.5,
        )
        pm.analyze(thesis, ThesisOutcome(verified=True))
        pm.analyze(thesis, ThesisOutcome(verified=False))
        assert pm.success_rate == 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# D1: ResearchCycleEngine Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCycleEngine:
    """Test the ResearchCycleEngine orchestration."""

    def test_engine_initialization(self, tmp_path):
        path = str(tmp_path / "memory.json")
        engine = ResearchCycleEngine(memory_path=path)
        assert engine.cycle_count == 0
        assert engine.memory.total_entries == 0

    def test_run_basic_cycle(self, tmp_path):
        """Run a complete cycle with minimal inputs."""
        path = str(tmp_path / "memory.json")
        engine = ResearchCycleEngine(memory_path=path)

        snapshot = MacroSnapshot(
            regime=RegimeSnapshot(
                monetary_policy="easing",
                fiscal_stance="neutral",
                volatility="low",
                growth="stable",
                inflation="stable",
            ),
            market=MarketSnapshot(indicators={
                "spx": 5200, "vix": 15.3, "dxy": 104.2, "us10y": 4.25,
            }),
        )

        result = engine.run_cycle(snapshot, skip_evolution=True)
        assert result.cycle_number == 1
        assert result.status == "completed"
        assert result.thesis is not None
        assert result.thesis.title != ""
        assert engine.memory.total_entries == 1

    def test_run_multiple_cycles(self, tmp_path):
        """Run two cycles and verify memory accumulates."""
        path = str(tmp_path / "memory.json")
        engine = ResearchCycleEngine(memory_path=path)

        for i in range(2):
            snapshot = MacroSnapshot(
                regime=RegimeSnapshot(monetary_policy="easing"),
            )
            result = engine.run_cycle(snapshot, skip_evolution=True)
            assert result.status == "completed"

        assert engine.cycle_count == 2
        assert engine.memory.total_entries == 2

    def test_run_cycle_with_previous_outcome(self, tmp_path):
        """Test running a cycle with previous outcome data."""
        path = str(tmp_path / "memory.json")
        engine = ResearchCycleEngine(memory_path=path)

        # First cycle
        snapshot = MacroSnapshot(regime=RegimeSnapshot(monetary_policy="easing"))
        result1 = engine.run_cycle(snapshot, skip_evolution=True)
        assert result1.status == "completed"
        thesis_id = result1.thesis.thesis_id

        # Second cycle with outcome from first
        snapshot2 = MacroSnapshot(regime=RegimeSnapshot(monetary_policy="easing"))
        previous_outcomes = {
            thesis_id: ({"spx": 5300, "prev_spx": 5200}, "Bullish outcome"),
        }
        result2 = engine.run_cycle(snapshot2, previous_outcomes=previous_outcomes, skip_evolution=True)
        assert result2.status == "completed"
        assert engine.memory.total_entries == 2

    def test_engine_summary(self, tmp_path):
        path = str(tmp_path / "memory.json")
        engine = ResearchCycleEngine(memory_path=path)

        snapshot = MacroSnapshot(regime=RegimeSnapshot(monetary_policy="easing"))
        engine.run_cycle(snapshot, skip_evolution=True)

        summary = engine.summary()
        assert "ResearchCycleEngine" in summary
        assert str(engine.cycle_count) in summary

    def test_cycle_result_summary(self):
        result = CycleResult(cycle_id="test-1", cycle_number=1)
        result.thesis = ResearchThesis(
            title="Test Thesis", core_belief="B",
            transmission_chain=["A", "B"], evidence=["E1", "E2"],
            invalidation_conditions=["C1"], confidence=0.7,
        )
        summary = result.summary()
        assert "Test Thesis" in summary


# ═══════════════════════════════════════════════════════════════════════════════
# Stage G: Full Loop Integration Test
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullResearchCycle:
    """End-to-end test of a complete research cycle."""

    def test_full_cycle_lifecycle(self, tmp_path):
        """Simulate a complete: Input→Thesis→Outcome→Postmortem→Memory cycle."""
        path = str(tmp_path / "memory.json")
        engine = ResearchCycleEngine(memory_path=path)

        # ── Morning: Create snapshot ──────────────────────────────────
        snapshot = MacroSnapshot(
            regime=RegimeSnapshot(
                monetary_policy="easing",
                fiscal_stance="expansionary",
                volatility="low",
                growth="accelerating",
                inflation="stable",
            ),
            market=MarketSnapshot(indicators={
                "spx": 5200, "vix": 14, "dxy": 103,
                "us10y": 4.2, "hyg": 78,
            }),
        )

        # ── Run cycle ─────────────────────────────────────────────────
        result = engine.run_cycle(snapshot, skip_evolution=True)
        assert result.status == "completed"
        assert result.thesis is not None

        # ── Verify thesis structure ───────────────────────────────────
        thesis = result.thesis
        assert thesis.title != ""
        assert thesis.core_belief != ""
        assert len(thesis.evidence) > 0
        assert len(thesis.invalidation_conditions) > 0
        assert thesis.confidence > 0
        assert thesis.expected_window != ""
        assert thesis.status == ThesisStatus.ACTIVE

        # ── Verify memory entry ───────────────────────────────────────
        assert engine.memory.total_entries == 1
        entry = engine.memory.get_entry(result.memory_entry_id)
        assert entry is not None
        assert entry.cycle_number == 1
        assert entry.regime_label != ""

        # ── Simulate outcome ─────────────────────────────────────────
        actual_data = {"spx": 5350, "prev_spx": 5200, "vix": 13}
        outcome = ThesisOutcome(verified=True, realized_return=0.029)
        thesis.validate(outcome)

        # ── Run postmortem ───────────────────────────────────────────
        pm = engine.postmortem
        report = pm.analyze(thesis, outcome)
        assert report.thesis_validated
        assert report.root_cause != ""

        # ── Verify everything recorded ───────────────────────────────
        assert engine.memory.total_entries == 1
        assert engine.cycle_count == 1
        assert pm.report_count == 1

    def test_framework_selection_in_cycle(self, tmp_path):
        """Verify framework selection is made during cycle even without frameworks."""
        path = str(tmp_path / "memory.json")
        engine = ResearchCycleEngine(memory_path=path)

        snapshot = MacroSnapshot(
            regime=RegimeSnapshot(
                monetary_policy="tightening",
                growth="decelerating",
                inflation="rising",
            ),
        )

        result = engine.run_cycle(snapshot, skip_evolution=True)
        assert result.framework_selection is not None
        assert result.framework_selection.regime_label != ""

    def test_error_handling(self, tmp_path):
        """Cycle should handle errors gracefully without crashing."""
        path = str(tmp_path / "memory.json")
        engine = ResearchCycleEngine(memory_path=path)

        # Empty snapshot should still work (degraded)
        result = engine.run_cycle(MacroSnapshot(), skip_evolution=True)
        assert result.status == "completed"  # Should complete with whatever it can


# ═══════════════════════════════════════════════════════════════════════════════
# Architecture Compliance
# ═══════════════════════════════════════════════════════════════════════════════


class TestArchitectureCompliance:
    """Verify architecture decisions are respected."""

    def test_no_ui_dependencies(self):
        """No UI imports anywhere in the cycle package."""
        import sys
        for name in sys.modules:
            if "research_cycle" in name:
                mod = sys.modules[name]
                source = mod.__file__ if hasattr(mod, '__file__') else ''
                if source and source.endswith('.py'):
                    with open(source) as f:
                        content = f.read()
                    # No flask, fastapi, streamlit, gradio
                    assert "flask" not in content.lower()
                    assert "fastapi" not in content.lower()
                    assert "streamlit" not in content.lower()
                    assert "gradio" not in content.lower()

    def test_d1_cycle_engine_exists(self):
        from src.research_cycle import ResearchCycleEngine
        engine = ResearchCycleEngine()
        assert hasattr(engine, 'run_cycle')

    def test_d2_thesis_schema_exists(self):
        from src.schemas.research_thesis import ResearchThesis
        thesis = ResearchThesis(
            title="T", core_belief="B",
            transmission_chain=["A","B"], evidence=["E1","E2"],
            invalidation_conditions=["C1"], confidence=0.5,
        )
        assert thesis.is_well_formed

    def test_d3_framework_selector_exists(self):
        from src.research_cycle import FrameworkSelector
        fs = FrameworkSelector()
        assert hasattr(fs, 'select')

    def test_d4_thesis_generator_exists(self):
        from src.research_cycle import ThesisGenerator
        tg = ThesisGenerator()
        assert hasattr(tg, 'generate')

    def test_d5_research_memory_exists(self):
        from src.research_cycle import ResearchMemory
        rm = ResearchMemory()
        assert hasattr(rm, 'record_entry')

    def test_d6_outcome_tracker_and_postmortem_exist(self):
        from src.research_cycle import OutcomeTracker, Postmortem
        assert hasattr(OutcomeTracker(), 'register_thesis')
        assert hasattr(Postmortem(), 'analyze')

    def test_schemas_exported(self):
        from src.schemas import (
            MacroSnapshot, MarketSnapshot,
            ResearchThesis, ThesisStatus, ThesisOutcome,
        )
        assert MacroSnapshot is not None
        assert ResearchThesis is not None
