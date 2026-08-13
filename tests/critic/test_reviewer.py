"""Tests for HypothesisReviewer — the 3-question belief reviewer."""

import pytest

from src.critic.reviewer import HypothesisReviewer
from src.domain.reflection import ReflectionVerdict
from src.domain.signal import SignalDirection
from src.schemas.hypothesis import HypothesisEvidence, HypothesisSchema
from src.schemas.reflection import ReflectionReport

# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_evidence(
    indicator: str = "DXY",
    signal_id: str = "s1",
    contribution: float = 0.8,
) -> HypothesisEvidence:
    return HypothesisEvidence(
        indicator=indicator,
        signal_id=signal_id,
        observation=f"{indicator}=100",
        interpretation=f"{indicator} interpretation",
        contribution=contribution,
    )


def _make_hypothesis(
    hypothesis_id: str = "h1",
    statement: str = "Test hypothesis",
    supporting: list | None = None,
    contradicting: list | None = None,
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
def reviewer():
    return HypothesisReviewer()


# ── Question 1: Evidence Sufficiency ────────────────────────────────────────


class TestEvidenceSufficiency:
    def test_high_sufficiency(self, reviewer):
        """4+ evidence items across 3+ indicators → high."""
        h = _make_hypothesis(
            supporting=[
                _make_evidence("DXY", "s1"),
                _make_evidence("US10Y", "s2"),
                _make_evidence("UST2Y", "s3"),
                _make_evidence("MOVE", "s4"),
            ],
        )
        assert reviewer._assess_sufficiency(h) == "high"

    def test_medium_sufficiency(self, reviewer):
        """2+ items across 2+ indicators → medium."""
        h = _make_hypothesis(
            supporting=[
                _make_evidence("DXY", "s1"),
                _make_evidence("US10Y", "s2"),
            ],
        )
        assert reviewer._assess_sufficiency(h) == "medium"

    def test_low_sufficiency_single_item(self, reviewer):
        """1 item → low."""
        h = _make_hypothesis(
            supporting=[_make_evidence("DXY", "s1")],
        )
        assert reviewer._assess_sufficiency(h) == "low"

    def test_low_sufficiency_empty(self, reviewer):
        """0 items → low."""
        h = _make_hypothesis()
        assert reviewer._assess_sufficiency(h) == "low"

    def test_medium_with_contradicting_items(self, reviewer):
        """2 supporting + 1 contradicting across 3 indicators → medium."""
        h = _make_hypothesis(
            supporting=[
                _make_evidence("DXY", "s1"),
                _make_evidence("US10Y", "s2"),
            ],
            contradicting=[
                _make_evidence("HYG", "s3"),
            ],
        )
        assert reviewer._assess_sufficiency(h) == "medium"

    def test_high_counts_unique_indicators(self, reviewer):
        """Multiple items but all same indicator → not high."""
        h = _make_hypothesis(
            supporting=[
                _make_evidence("DXY", "s1"),
                _make_evidence("DXY", "s2"),
                _make_evidence("DXY", "s3"),
                _make_evidence("DXY", "s4"),
            ],
        )
        # 4 items but only 1 unique indicator → low
        assert reviewer._assess_sufficiency(h) == "low"


# ── Question 2: Evidence Consistency ────────────────────────────────────────


class TestEvidenceConsistency:
    def test_consistent_no_contradicting(self, reviewer):
        h = _make_hypothesis(
            supporting=[_make_evidence("DXY", "s1")],
        )
        assert reviewer._assess_consistency(h) == "consistent"

    def test_consistent_low_contradiction(self, reviewer):
        """Small contradicing contribution → still consistent."""
        h = _make_hypothesis(
            supporting=[_make_evidence("DXY", "s1", contribution=0.9)],
            contradicting=[_make_evidence("US10Y", "s2", contribution=0.1)],
        )
        # contra ratio: 0.1 / 1.0 = 0.1 (below 0.15)
        assert reviewer._assess_consistency(h) == "consistent"

    def test_mixed_moderate_contradiction(self, reviewer):
        h = _make_hypothesis(
            supporting=[_make_evidence("DXY", "s1", contribution=0.7)],
            contradicting=[_make_evidence("US10Y", "s2", contribution=0.3)],
        )
        # contra ratio: 0.3 / 1.0 = 0.3
        assert reviewer._assess_consistency(h) == "mixed"

    def test_conflicting_strong_contradiction(self, reviewer):
        h = _make_hypothesis(
            supporting=[_make_evidence("DXY", "s1", contribution=0.5)],
            contradicting=[_make_evidence("US10Y", "s2", contribution=0.5)],
        )
        # contra ratio: 0.5 / 1.0 = 0.5
        assert reviewer._assess_consistency(h) == "conflicting"

    def test_consistent_zero_total(self, reviewer):
        """All zero contributions → consistent."""
        h = _make_hypothesis(
            supporting=[_make_evidence("DXY", "s1", contribution=0.0)],
            contradicting=[_make_evidence("US10Y", "s2", contribution=0.0)],
        )
        assert reviewer._assess_consistency(h) == "consistent"


# ── Question 3: Verdict ─────────────────────────────────────────────────────


class TestVerdict:
    def test_empty_hypothesis_uncertain(self, reviewer):
        h = _make_hypothesis()
        report = reviewer.review(h)
        assert report.verdict == ReflectionVerdict.UNCERTAIN

    def test_clean_evidence_confirmed(self, reviewer):
        """Strong, consistent evidence → CONFIRMED."""
        h = _make_hypothesis(
            supporting=[
                _make_evidence("DXY", "s1"),
                _make_evidence("US10Y", "s2"),
                _make_evidence("UST2Y", "s3"),
                _make_evidence("MOVE", "s4"),
            ],
        )
        report = reviewer.review(h)
        assert report.verdict == ReflectionVerdict.CONFIRMED
        assert report.evidence_sufficiency == "high"
        assert report.evidence_consistency == "consistent"

    def test_conflicting_refuted(self, reviewer):
        """Strong contradictions → REFUTED."""
        h = _make_hypothesis(
            supporting=[_make_evidence("DXY", "s1", contribution=0.5)],
            contradicting=[
                _make_evidence("US10Y", "s2", contribution=0.5),
            ],
        )
        report = reviewer.review(h)
        assert report.verdict == ReflectionVerdict.REFUTED

    def test_medium_evidence_confirmed(self, reviewer):
        """2 items, consistent → maybe CONFIRMED."""
        h = _make_hypothesis(
            supporting=[
                _make_evidence("DXY", "s1"),
                _make_evidence("US10Y", "s2"),
            ],
        )
        report = reviewer.review(h)
        # Medium sufficiency gets a finding, but may still be confirmed
        assert report.evidence_sufficiency == "medium"
        assert report.evidence_consistency == "consistent"

    def test_single_indicator_multiple_items(self, reviewer):
        """Multiple items from same indicator → single_source_risk finding."""
        h = _make_hypothesis(
            supporting=[
                _make_evidence("DXY", "s1", contribution=0.8),
                _make_evidence("DXY", "s2", contribution=0.7),
            ],
        )
        report = reviewer.review(h)
        finding_types = {f.type for f in report.findings}
        assert "single_source_risk" in finding_types


# ── Full Review Pipeline ────────────────────────────────────────────────────


class TestFullReview:
    def test_review_returns_report(self, reviewer):
        h = _make_hypothesis(
            supporting=[
                _make_evidence("DXY", "s1"),
                _make_evidence("US10Y", "s2"),
            ],
        )
        report = reviewer.review(h)
        assert isinstance(report, ReflectionReport)
        assert report.hypothesis_id == h.hypothesis_id
        assert report.statement == h.statement
        assert report.original_confidence == h.confidence

    def test_review_preserves_original_confidence(self, reviewer):
        """Reviewer should not modify confidence (scorer does that)."""
        h = _make_hypothesis(
            supporting=[_make_evidence("DXY", "s1")],
            confidence=0.75,
        )
        report = reviewer.review(h)
        assert report.original_confidence == 0.75
        # Reviewer leaves updated == original (scorer adjusts later)
        assert report.updated_confidence == 0.75

    def test_all_three_questions_in_report(self, reviewer):
        h = _make_hypothesis(
            supporting=[
                _make_evidence("DXY", "s1"),
                _make_evidence("US10Y", "s2"),
                _make_evidence("UST2Y", "s3"),
                _make_evidence("MOVE", "s4"),
            ],
        )
        report = reviewer.review(h)
        # All three answers must be present
        assert report.evidence_sufficiency in ("high", "medium", "low")
        assert report.evidence_consistency in ("consistent", "mixed", "conflicting")
        assert report.verdict in ReflectionVerdict.__members__.values()
        assert isinstance(report.review_summary, str)
        assert len(report.review_summary) > 0

    def test_review_summary_not_empty(self, reviewer):
        h = _make_hypothesis(
            supporting=[_make_evidence("DXY", "s1")],
        )
        report = reviewer.review(h)
        assert len(report.review_summary) > 0
