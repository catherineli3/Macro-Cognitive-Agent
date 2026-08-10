"""Tests for BeliefScorer — confidence adjustment."""

from typing import Optional

import pytest

from src.domain.reflection import FindingSeverity, ReflectionVerdict
from src.domain.signal import SignalDirection
from src.schemas.hypothesis import HypothesisEvidence, HypothesisSchema, HypothesisSet
from src.schemas.reflection import ReflectionFinding, ReflectionReport
from src.critic.scorer import BeliefScorer
from src.critic.engine import ReflectionEngine


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_evidence(
    indicator: str = "DXY",
    contribution: float = 0.8,
) -> HypothesisEvidence:
    return HypothesisEvidence(
        indicator=indicator,
        signal_id=f"s_{indicator}",
        observation=f"{indicator}=100",
        interpretation=f"{indicator} interpretation",
        contribution=contribution,
    )


def _make_hypothesis(
    hypothesis_id: str = "h1",
    statement: str = "Test",
    supporting: Optional[list] = None,
    contradicting: Optional[list] = None,
    confidence: float = 0.8,
) -> HypothesisSchema:
    return HypothesisSchema(
        hypothesis_id=hypothesis_id,
        statement=statement,
        dimension="Liquidity",
        direction=SignalDirection.BEARISH,
        confidence=confidence,
        supporting_evidence=supporting or [],
        contradicting_evidence=contradicting or [],
        assumptions=["Test assumption"],
    )


# ── Fixture ─────────────────────────────────────────────────────────────────


@pytest.fixture
def scorer():
    return BeliefScorer()


# ── Basic Scoring ───────────────────────────────────────────────────────────


class TestBasicScoring:
    def test_perfect_report_no_change(self, scorer):
        """High sufficiency + consistent + no findings → confidence maintained."""
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.8,
            evidence_sufficiency="high",
            evidence_consistency="consistent",
            findings=[],
        )
        updated = scorer.score(report, 0.8)
        assert updated == pytest.approx(0.8)

    def test_medium_sufficiency_reduces(self, scorer):
        """Medium sufficiency → 0.90 multiplier."""
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.8,
            evidence_sufficiency="medium",
            evidence_consistency="consistent",
            findings=[],
        )
        updated = scorer.score(report, 0.8)
        assert updated == pytest.approx(0.8 * 0.90)

    def test_low_sufficiency_reduces(self, scorer):
        """Low sufficiency → 0.75 multiplier."""
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.8,
            evidence_sufficiency="low",
            evidence_consistency="consistent",
            findings=[],
        )
        updated = scorer.score(report, 0.8)
        assert updated == pytest.approx(0.8 * 0.75)

    def test_mixed_consistency_reduces(self, scorer):
        """Mixed consistency → 0.85 multiplier."""
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.8,
            evidence_sufficiency="high",
            evidence_consistency="mixed",
            findings=[],
        )
        updated = scorer.score(report, 0.8)
        assert updated == pytest.approx(0.8 * 0.85)

    def test_conflicting_consistency_reduces(self, scorer):
        """Conflicting → 0.65 multiplier."""
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.8,
            evidence_sufficiency="high",
            evidence_consistency="conflicting",
            findings=[],
        )
        updated = scorer.score(report, 0.8)
        assert updated == pytest.approx(0.8 * 0.65)


# ── Finding Penalties ───────────────────────────────────────────────────────


class TestFindingPenalties:
    def test_critical_penalty(self, scorer):
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.8,
            evidence_sufficiency="high",
            evidence_consistency="consistent",
            findings=[
                ReflectionFinding(
                    type="conflicting_evidence",
                    severity=FindingSeverity.CRITICAL,
                    description="Major conflict.",
                )
            ],
        )
        updated = scorer.score(report, 0.8)
        expected = 0.8 * 1.0 * 1.0 * 0.75  # sufficiency * consistency * critical
        assert updated == pytest.approx(expected)

    def test_major_penalty(self, scorer):
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.8,
            evidence_sufficiency="high",
            evidence_consistency="consistent",
            findings=[
                ReflectionFinding(
                    type="evidence_insufficient",
                    severity=FindingSeverity.MAJOR,
                    description="Not enough.",
                )
            ],
        )
        updated = scorer.score(report, 0.8)
        expected = 0.8 * 1.0 * 1.0 * 0.90
        assert updated == pytest.approx(expected)

    def test_minor_penalty(self, scorer):
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.8,
            evidence_sufficiency="high",
            evidence_consistency="consistent",
            findings=[
                ReflectionFinding(
                    type="evidence_insufficient",
                    severity=FindingSeverity.MINOR,
                    description="Minor issue.",
                )
            ],
        )
        updated = scorer.score(report, 0.8)
        expected = 0.8 * 1.0 * 1.0 * 0.97
        assert updated == pytest.approx(expected)

    def test_cumulative_penalties_compound(self, scorer):
        """Two findings → compound multipliers."""
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.8,
            evidence_sufficiency="high",
            evidence_consistency="consistent",
            findings=[
                ReflectionFinding(
                    type="evidence_insufficient",
                    severity=FindingSeverity.MAJOR,
                    description="Insufficient.",
                ),
                ReflectionFinding(
                    type="evidence_quality_low",
                    severity=FindingSeverity.MAJOR,
                    description="Low quality.",
                ),
            ],
        )
        updated = scorer.score(report, 0.8)
        # 1.0 * 1.0 * 0.90 * 0.90 = 0.81
        expected = 0.8 * 0.90 * 0.90
        assert updated == pytest.approx(expected)

    def test_confidence_cannot_go_below_zero(self, scorer):
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.1,
            evidence_sufficiency="low",
            evidence_consistency="conflicting",
            findings=[
                ReflectionFinding(
                    type="conflicting_evidence",
                    severity=FindingSeverity.CRITICAL,
                    description="Critical.",
                )
            ],
        )
        updated = scorer.score(report, 0.1)
        assert updated >= 0.0

    def test_confidence_cannot_exceed_one(self, scorer):
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.99,
            evidence_sufficiency="high",
            evidence_consistency="consistent",
            findings=[],
        )
        updated = scorer.score(report, 0.99)
        assert updated <= 1.0

    def test_zero_confidence_stays_zero(self, scorer):
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.0,
            evidence_sufficiency="low",
            evidence_consistency="conflicting",
        )
        updated = scorer.score(report, 0.0)
        assert updated == 0.0


# ── update_report_confidence ────────────────────────────────────────────────


class TestUpdateReportConfidence:
    def test_writes_updated_confidence(self, scorer):
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.8,
            evidence_sufficiency="medium",
            evidence_consistency="consistent",
            findings=[],
        )
        scorer.update_report_confidence(report)
        assert report.updated_confidence == pytest.approx(0.8 * 0.90)

    def test_returns_same_object(self, scorer):
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.7,
        )
        result = scorer.update_report_confidence(report)
        assert result is report


# ── Edge Cases ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_unknown_sufficiency_ignored(self, scorer):
        """Unknown sufficiency → factor 1.0 (no effect)."""
        # We bypass validation for this test by using model_construct
        report = ReflectionReport.model_construct(
            statement="Test",
            original_confidence=0.8,
            evidence_sufficiency="unknown",
            evidence_consistency="consistent",
            findings=[],
        )
        updated = scorer.score(report, 0.8)
        assert updated == pytest.approx(0.8)

    def test_combination_of_all_factors(self, scorer):
        """Low + conflicting + critical finding + major finding."""
        report = ReflectionReport(
            statement="Test",
            original_confidence=0.8,
            evidence_sufficiency="low",
            evidence_consistency="conflicting",
            findings=[
                ReflectionFinding(
                    type="conflicting_evidence",
                    severity=FindingSeverity.CRITICAL,
                    description="Conflict.",
                ),
                ReflectionFinding(
                    type="evidence_quality_low",
                    severity=FindingSeverity.MAJOR,
                    description="Low quality.",
                ),
            ],
        )
        updated = scorer.score(report, 0.8)
        # 0.8 * 0.75 * 0.65 * 0.75 * 0.90 = 0.26325
        expected = 0.8 * 0.75 * 0.65 * 0.75 * 0.90
        assert updated == pytest.approx(expected)


# ── ReflectionEngine Integration ────────────────────────────────────────────


class TestReflectionEngineIntegration:
    def test_engine_produces_reflection_set(self):
        engine = ReflectionEngine()
        h = _make_hypothesis(
            supporting=[
                _make_evidence("DXY"),
                _make_evidence("US10Y"),
            ],
            confidence=0.85,
        )
        hs = HypothesisSet(hypotheses=[h])
        result = engine.review(hs)
        assert result.count == 1
        # Medium sufficiency → confidence drops via sufficiency factor
        assert result.reports[0].updated_confidence != result.reports[0].original_confidence
        assert result.reports[0].updated_confidence < result.reports[0].original_confidence

    def test_engine_with_conflicting(self):
        engine = ReflectionEngine()
        h = _make_hypothesis(
            supporting=[_make_evidence("DXY", contribution=0.5)],
            contradicting=[_make_evidence("US10Y", contribution=0.5)],
            confidence=0.75,
        )
        hs = HypothesisSet(hypotheses=[h])
        result = engine.review(hs)
        assert result.reports[0].verdict == ReflectionVerdict.REFUTED
        assert result.reports[0].updated_confidence < result.reports[0].original_confidence

    def test_engine_with_weak_evidence(self):
        engine = ReflectionEngine()
        h = _make_hypothesis(
            supporting=[_make_evidence("DXY", contribution=0.3)],
            confidence=0.5,
        )
        hs = HypothesisSet(hypotheses=[h])
        result = engine.review(hs)
        report = result.reports[0]
        assert report.evidence_sufficiency == "low"

    def test_engine_empty_set(self):
        engine = ReflectionEngine()
        hs = HypothesisSet(hypotheses=[])
        result = engine.review(hs)
        assert result.count == 0
        assert "No hypotheses" in result.summary

    def test_engine_verdict_confidence_refuted(self):
        """If confidence drops below 0.25, verdict should be REFUTED."""
        engine = ReflectionEngine()
        h = _make_hypothesis(
            supporting=[_make_evidence("DXY", contribution=0.3)],
            contradicting=[_make_evidence("US10Y", contribution=0.8)],
            confidence=0.3,
        )
        hs = HypothesisSet(hypotheses=[h])
        result = engine.review(hs)
        assert result.reports[0].verdict == ReflectionVerdict.REFUTED
