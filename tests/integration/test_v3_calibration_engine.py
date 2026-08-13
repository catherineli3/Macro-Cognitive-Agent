"""V3 Calibration Engine & Belief Store tests — Milestone F (Release 3.2).

Covers:
    - evidence_weight.py: compute_evidence_weight, classify_evidence
    - belief_store.py: BeliefStore CRUD, query, persistence, history
    - calibration_engine.py: CalibrationEngine curve building, health, evolution
"""

from __future__ import annotations

from src.calibration.calibration_engine import CalibrationEngine
from src.domain.signal import SignalDirection
from src.learning.learning_engine import LearningEngine
from src.research.beliefs.belief_store import BeliefStore
from src.research.beliefs.evidence_weight import (
    EVIDENCE_BASE_WEIGHTS,
    classify_evidence,
    compute_evidence_batch,
    compute_evidence_weight,
    get_source_reliability,
)
from src.research.beliefs.schemas import (
    BeliefDomain,
    BeliefStage,
    EvidenceSource,
    ResearchBelief,
)
from src.schemas.calibration import ConfidenceCalibration
from src.schemas.hypothesis import HypothesisSchema
from src.schemas.outcome import (
    OutcomeDirection,
    OutcomeRecord,
    OutcomeVerdict,
    PredictionOutcome,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Evidence Weight Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEvidenceWeight:
    """Tests for evidence_weight.py — weight computation and classification."""

    def test_compute_fresh_high_confidence_market(self):
        """Fresh market data with high confidence → near-base weight."""
        w = compute_evidence_weight(
            source=EvidenceSource.MARKET_DATA,
            confidence=0.95,
            recency_days=0,
            corroboration_count=0,
        )
        assert 0.80 <= w <= 0.95

    def test_compute_old_news_low_weight(self):
        """Old news with low confidence → low weight."""
        w = compute_evidence_weight(
            source=EvidenceSource.NEWS,
            confidence=0.5,
            recency_days=60,
            corroboration_count=0,
        )
        assert w <= 0.15

    def test_corroboration_bonus_capped(self):
        """Many corroborations → bonus capped at 1.15x."""
        w_none = compute_evidence_weight(
            EvidenceSource.MACRO_DATA,
            confidence=0.8,
            recency_days=0,
            corroboration_count=0,
        )
        w_many = compute_evidence_weight(
            EvidenceSource.MACRO_DATA,
            confidence=0.8,
            recency_days=0,
            corroboration_count=100,
        )
        ratio = w_many / w_none
        assert 1.0 <= ratio <= 1.15

    def test_recency_decay_halflife(self):
        """At half-life (30 days), weight ~50% of fresh."""
        w_fresh = compute_evidence_weight(
            EvidenceSource.MACRO_DATA,
            0.8,
            0,
            0,
        )
        w_old = compute_evidence_weight(
            EvidenceSource.MACRO_DATA,
            0.8,
            30,
            0,
        )
        ratio = w_old / w_fresh
        assert 0.45 <= ratio <= 0.55

    def test_floor_weight(self):
        """Weight never below 0.05."""
        w = compute_evidence_weight(
            EvidenceSource.NEWS,
            0.01,
            365,
            0,
        )
        assert w >= 0.05

    def test_ceiling_weight(self):
        """Weight never above 1.0."""
        w = compute_evidence_weight(
            EvidenceSource.MARKET_DATA,
            1.0,
            0,
            0,
        )
        assert w <= 1.0

    def test_weight_is_float_in_range(self):
        """Weight is float in [0.05, 1.0]."""
        w = compute_evidence_weight(EvidenceSource.INFERENCE)
        assert isinstance(w, float)
        assert 0.05 <= w <= 1.0

    def test_classify_market_keywords(self):
        assert classify_evidence("DXY broke above 106 resistance") == EvidenceSource.MARKET_DATA
        assert classify_evidence("Treasury yield spiked to 4.5%") == EvidenceSource.MARKET_DATA

    def test_classify_macro_keywords(self):
        assert classify_evidence("Fed raised rates by 25bp") == EvidenceSource.MACRO_DATA
        assert classify_evidence("CPI came in above expectations") == EvidenceSource.MACRO_DATA

    def test_classify_company_keywords(self):
        assert classify_evidence("Apple earnings beat estimates") == EvidenceSource.COMPANY

    def test_classify_history_keywords(self):
        assert (
            classify_evidence("Historically this pattern precedes recessions")
            == EvidenceSource.HISTORY
        )

    def test_classify_default_inference(self):
        assert classify_evidence("Model suggests continued expansion") == EvidenceSource.INFERENCE

    def test_classify_direct_type_strings(self):
        assert classify_evidence("market_data") == EvidenceSource.MARKET_DATA
        assert classify_evidence("macro_data") == EvidenceSource.MACRO_DATA

    def test_all_base_weights_defined(self):
        for source in EvidenceSource:
            assert source.value in EVIDENCE_BASE_WEIGHTS
            assert 0.0 < EVIDENCE_BASE_WEIGHTS[source.value] <= 1.0

    def test_source_reliability_all_sources(self):
        for source in EvidenceSource:
            profile = get_source_reliability(source)
            for key in ("source", "base_weight", "reliability_tier", "description"):
                assert key in profile

    def test_batch_computation(self):
        sources = [EvidenceSource.MARKET_DATA, EvidenceSource.NEWS, EvidenceSource.MACRO_DATA]
        confs = [0.9, 0.5, 0.8]
        recs = [0, 10, 5]
        corrs = [0, 2, 5]
        weights = compute_evidence_batch(sources, confs, recs, corrs)
        assert len(weights) == 3
        assert all(0.05 <= w <= 1.0 for w in weights)
        assert weights[0] > weights[1]  # market > news


# ═══════════════════════════════════════════════════════════════════════════════
# Belief Store Tests
# ═══════════════════════════════════════════════════════════════════════════════


def _belief(
    bid: str, title: str = "Test", domain=BeliefDomain.LIQUIDITY, stage=BeliefStage.HYPOTHESIS
) -> ResearchBelief:
    b = ResearchBelief(id=bid, title=title, description=title, domain=domain, stage=stage)
    return b


class TestBeliefStore:
    """Tests for belief_store.py — CRUD, query, persistence, history."""

    def test_add_and_get(self):
        store = BeliefStore()
        b = _belief("b1", "USD bullish trend")
        store.add(b)
        assert store.get("b1") is not None
        assert store.get("b1").title == "USD bullish trend"
        assert store.count() == 1

    def test_get_nonexistent(self):
        assert BeliefStore().get("noexist") is None

    def test_get_many_skips_missing(self):
        store = BeliefStore()
        store.add(_belief("b1"))
        store.add(_belief("b2"))
        results = store.get_many(["b1", "b3", "b2"])
        assert len(results) == 2

    def test_update_existing(self):
        store = BeliefStore()
        store.add(_belief("b1", stage=BeliefStage.HYPOTHESIS))
        b = store.get("b1")
        b.title = "Updated"
        b.advance_stage(BeliefStage.CONFIRMATION, "evidence strong")
        assert store.update(b) is True
        assert store.get("b1").title == "Updated"
        assert store.get("b1").stage == BeliefStage.CONFIRMATION

    def test_update_missing(self):
        store = BeliefStore()
        assert store.update(_belief("noexist")) is False

    def test_retire(self):
        store = BeliefStore()
        store.add(_belief("b1", stage=BeliefStage.CONSOLIDATION))
        assert store.retire("b1", "outdated") is True
        assert store.count() == 0
        retired = store.get("b1")
        assert retired is not None
        assert retired.stage == BeliefStage.RETIRED

    def test_retire_missing(self):
        assert BeliefStore().retire("noexist") is False

    def test_query_by_domain(self):
        store = BeliefStore()
        store.add(_belief("b1", domain=BeliefDomain.LIQUIDITY))
        store.add(_belief("b2", domain=BeliefDomain.CREDIT))
        store.add(_belief("b3", domain=BeliefDomain.LIQUIDITY))

        liq = store.query_by_domain(BeliefDomain.LIQUIDITY)
        assert len(liq) == 2
        assert {b.id for b in liq} == {"b1", "b3"}

    def test_query_by_stage(self):
        store = BeliefStore()
        store.add(_belief("b1", stage=BeliefStage.HYPOTHESIS))
        store.add(_belief("b2", stage=BeliefStage.CONFIRMATION))
        store.add(_belief("b3", stage=BeliefStage.CONSOLIDATION))

        conf = store.query_by_stage(BeliefStage.CONFIRMATION)
        assert len(conf) == 1
        assert conf[0].id == "b2"

    def test_query_by_stage_string(self):
        store = BeliefStore()
        store.add(_belief("b1", stage=BeliefStage.CONSOLIDATION))
        results = store.query_by_stage("consolidation")
        assert len(results) == 1

    def test_query_active(self):
        store = BeliefStore()
        store.add(_belief("b1", stage=BeliefStage.HYPOTHESIS))
        store.add(_belief("b2", stage=BeliefStage.CONSOLIDATION))
        store.retire("b1")
        active = store.query_active()
        assert len(active) == 1
        assert active[0].id == "b2"

    def test_query_validated(self):
        store = BeliefStore()
        store.add(_belief("b1", stage=BeliefStage.HYPOTHESIS))
        store.add(_belief("b2", stage=BeliefStage.CONFIRMATION))
        store.add(_belief("b3", stage=BeliefStage.CONSOLIDATION))
        validated = store.query_validated()
        assert len(validated) == 2

    def test_query_dominant(self):
        store = BeliefStore()
        store.add(_belief("b1", stage=BeliefStage.CONSOLIDATION))
        store.add(_belief("b2", stage=BeliefStage.CONFIRMATION))
        dom = store.query_dominant()
        assert len(dom) == 1
        assert dom[0].id == "b1"

    def test_save_and_load_latest(self):
        store = BeliefStore()
        store.save([_belief("b1")], "2026-01-01")
        store.save([_belief("b1"), _belief("b2")], "2026-01-02")
        latest = store.load_latest()
        assert len(latest) == 2

    def test_load_by_date(self):
        store = BeliefStore()
        store.save([_belief("b1")], "2026-01-01")
        store.save([_belief("b1"), _belief("b2")], "2026-01-02")
        assert len(store.load_by_date("2026-01-01")) == 1
        assert len(store.load_by_date("2026-01-02")) == 2
        assert store.load_by_date("2099-01-01") == []

    def test_save_auto_date_returns_valid_date(self):
        store = BeliefStore()
        date = store.save([_belief("b1")])
        assert len(date) == 10  # YYYY-MM-DD
        assert store.load_latest() is not None

    def test_history_dates_sorted(self):
        store = BeliefStore()
        store.save([_belief("b1")], "2026-01-03")
        store.save([_belief("b2")], "2026-01-01")
        store.save([_belief("b3")], "2026-01-02")
        assert store.history_dates() == ["2026-01-01", "2026-01-02", "2026-01-03"]
        assert store.snapshot_count() == 3

    def test_diff_added_removed_modified(self):
        store = BeliefStore()
        store.save([_belief("b1", "Belief 1"), _belief("b2", "Belief 2")], "2026-01-01")
        store.save([_belief("b1", "Belief 1 v2"), _belief("b3", "Belief 3")], "2026-01-02")
        diff = store.diff("2026-01-01", "2026-01-02")
        assert len(diff["added"]) == 1
        assert len(diff["removed"]) == 1
        assert len(diff["modified"]) == 1
        assert diff["added"][0].id == "b3"
        assert diff["removed"][0].id == "b2"
        assert diff["modified"][0].id == "b1"

    def test_summary(self):
        store = BeliefStore()
        store.add(_belief("b1", stage=BeliefStage.HYPOTHESIS, domain=BeliefDomain.LIQUIDITY))
        store.add(_belief("b2", stage=BeliefStage.CONFIRMATION, domain=BeliefDomain.CREDIT))
        # Snapshots are separate from active store; save persists current state
        store.save(
            [
                _belief("b1", domain=BeliefDomain.LIQUIDITY, stage=BeliefStage.HYPOTHESIS),
                _belief("b2", domain=BeliefDomain.CREDIT, stage=BeliefStage.CONFIRMATION),
            ]
        )
        s = store.summary()
        assert s["total_active"] == 2
        assert s["total_snapshots"] >= 1
        assert "hypothesis" in s["by_stage"]
        assert "Liquidity" in s["by_domain"]

    def test_all_beliefs(self):
        store = BeliefStore()
        store.add(_belief("b1"))
        store.add(_belief("b2"))
        assert len(store.all_beliefs()) == 2

    def test_auto_generate_id_prefix(self):
        store = BeliefStore()
        b = ResearchBelief(id="", title="Auto ID")
        bid = store.add(b)
        assert bid.startswith("BLF-")
        assert len(bid) == 12

    def test_clear(self):
        store = BeliefStore()
        store.add(_belief("b1"))
        store.save([_belief("b1")], "2026-01-01")
        store.clear()
        assert store.count() == 0
        assert store.snapshot_count() == 0

    def test_domain_index_updated_on_update(self):
        store = BeliefStore()
        store.add(_belief("b1", domain=BeliefDomain.LIQUIDITY))
        b = store.get("b1")
        b.domain = BeliefDomain.CREDIT
        store.update(b)
        assert store.query_by_domain(BeliefDomain.LIQUIDITY) == []
        assert len(store.query_by_domain(BeliefDomain.CREDIT)) == 1

    def test_stage_index_updated_on_update(self):
        store = BeliefStore()
        store.add(_belief("b1", stage=BeliefStage.HYPOTHESIS))
        b = store.get("b1")
        b.advance_stage(BeliefStage.CONFIRMATION, "test")
        store.update(b)
        assert store.query_by_stage(BeliefStage.HYPOTHESIS) == []
        assert len(store.query_by_stage(BeliefStage.CONFIRMATION)) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Calibration Engine Tests
# ═══════════════════════════════════════════════════════════════════════════════


def _po(
    hid: str, dim: str = "Liquidity", conf: float = 0.8, correct: bool = True
) -> PredictionOutcome:
    return PredictionOutcome(
        hypothesis_id=hid,
        dimension=dim,
        predicted_statement=f"Prediction {hid}",
        predicted_direction=SignalDirection.BULLISH,
        predicted_confidence=conf,
        verdict=OutcomeVerdict.CORRECT if correct else OutcomeVerdict.INCORRECT,
        observed_direction=OutcomeDirection.UP if correct else OutcomeDirection.DOWN,
    )


class TestCalibrationEngine:
    """Tests for calibration_engine.py — curve building, health, evolution."""

    def test_empty_curve(self):
        engine = CalibrationEngine()
        result = engine.build_calibration_curve([])
        assert result["total_outcomes"] == 0
        assert result["ece"] == 0.0

    def test_curve_structure(self):
        engine = CalibrationEngine()
        outcomes = [_po(f"h{i}") for i in range(20)]
        result = engine.build_calibration_curve(outcomes)
        assert result["total_outcomes"] == 20
        assert "buckets" in result
        assert len(result["buckets"]) == 5
        # All correct → accuracy=1.0, ECE should exist (prediction~0.8)
        assert result["ece"] > 0.0

    def test_ece_mce_set_after_build(self):
        engine = CalibrationEngine()
        engine.build_calibration_curve([_po(f"h{i}") for i in range(20)])
        assert engine.ece > 0.0
        assert engine.mce > 0.0

    def test_health_excellent(self):
        """Well-calibrated predictions → excellent/good health (low ECE)."""
        engine = CalibrationEngine()
        outcomes = []
        # 25 × 0.55 confidence, 50% correct → accuracy ≈ 0.5, error small
        for i in range(25):
            outcomes.append(_po(f"a{i}", conf=0.55, correct=(i < 13)))
        # 20 × 0.85 confidence, 80% correct → accuracy ≈ 0.8, error small
        for i in range(20):
            outcomes.append(_po(f"b{i}", conf=0.85, correct=(i < 16)))

        engine.build_calibration_curve(outcomes)
        health = engine.get_calibration_health()
        assert health["health_status"] in ("excellent", "good", "fair")

    def test_health_poor_with_wrong_predictions(self):
        engine = CalibrationEngine()
        outcomes = []
        for i in range(50):
            outcomes.append(_po(f"h{i}", conf=0.9, correct=(i < 5)))
        engine.build_calibration_curve(outcomes)
        health = engine.get_calibration_health()
        assert health["ece"] > 0.1

    def test_overconfidence_recommendations(self):
        engine = CalibrationEngine()
        outcomes = [_po(f"h{i}", conf=0.9, correct=False) for i in range(30)]
        engine.build_calibration_curve(outcomes)
        health = engine.get_calibration_health()
        assert len(health["recommendations"]) > 0

    def test_evolve_curves(self):
        engine = CalibrationEngine()
        bad = [_po(f"b{i}", conf=0.9, correct=False) for i in range(20)]
        engine.build_calibration_curve(bad)

        good = [_po(f"g{i}", conf=0.7, correct=True) for i in range(30)]
        health = engine.evolve_curves(good, alpha=0.5)
        assert "ece" in health

    def test_platt_scale_with_curve(self):
        engine = CalibrationEngine()
        engine.build_calibration_curve(
            [_po(f"h{i}", conf=0.8, correct=(i < 15)) for i in range(20)]
        )
        scaled = engine.platt_scale(0.85)
        assert 0.0 <= scaled <= 1.0

    def test_platt_scale_without_curve_returns_raw(self):
        engine = CalibrationEngine()
        assert engine.platt_scale(0.75) == 0.75

    def test_is_calibrated_false_when_empty(self):
        assert CalibrationEngine().is_calibrated is False

    def test_delegation_to_confidence_calibrator(self):
        engine = CalibrationEngine()
        hyp = HypothesisSchema(
            hypothesis_id="h1",
            statement="Liquidity bullish",
            dimension="Liquidity",
            direction=SignalDirection.BULLISH,
            confidence=0.75,
            supporting_evidence=[],
            contradicting_evidence=[],
        )
        cal = engine.calibrate_hypothesis(hyp, 0.75)
        assert isinstance(cal, ConfidenceCalibration)
        assert cal.hypothesis_id == "h1"
        assert 0.0 <= cal.calibrated_confidence <= 1.0

    def test_get_curve_5_buckets(self):
        engine = CalibrationEngine()
        engine.build_calibration_curve([_po(f"h{i}") for i in range(10)])
        curve = engine.get_curve()
        assert len(curve) == 5
        for data in curve.values():
            assert "range" in data
            assert "observed_accuracy" in data
            assert "count" in data

    def test_multi_dimension_accuracy(self):
        engine = CalibrationEngine()
        outcomes = []
        for i in range(10):
            outcomes.append(_po(f"l{i}", dim="Liquidity", conf=0.8, correct=True))
        for i in range(10):
            outcomes.append(_po(f"g{i}", dim="Growth", conf=0.8, correct=(i < 3)))
        engine.build_calibration_curve(outcomes)
        health = engine.get_calibration_health()
        dim_acc = health.get("dim_accuracy", {})
        assert "Liquidity" in dim_acc
        assert "Growth" in dim_acc
        assert dim_acc["Liquidity"] > dim_acc["Growth"]

    def test_set_learning_engine_propagates(self):
        le = LearningEngine()
        engine = CalibrationEngine()
        engine.set_learning_engine(le)

        # Feed learning engine with data
        records = []
        for i in range(10):
            records.append(
                OutcomeRecord(
                    run_id=f"r{i}",
                    outcome=_po(f"h{i}"),
                )
            )
        from src.outcome.engine import OutcomeMetrics

        summary = OutcomeMetrics.compute_summary(records)
        le.learn(summary, records)

        hyp = HypothesisSchema(
            hypothesis_id="h_new",
            statement="Test",
            dimension="Liquidity",
            direction=SignalDirection.BULLISH,
            confidence=0.82,
            supporting_evidence=[],
            contradicting_evidence=[],
        )
        cal = engine.calibrate_hypothesis(hyp, 0.82)
        assert cal.calibrated_confidence >= 0.55
