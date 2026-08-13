"""Tests for Hypothesis domain + schema models (Sprint 6).

Covers:
    - HypothesisStatus enum values
    - HypothesisEvidence creation and validation
    - HypothesisSchema creation, properties, direction, evidence
    - HypothesisSet creation, filtering, highest-confidence lookup
"""

import pytest

from src.domain.hypothesis import HypothesisStatus
from src.schemas.hypothesis import HypothesisEvidence, HypothesisSchema, HypothesisSet
from src.schemas.signal import SignalDirection

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def sample_supporting() -> list[HypothesisEvidence]:
    return [
        HypothesisEvidence(
            indicator="DXY",
            signal_id="s1",
            observation="DXY at 106.5 (condition: value > 105.0)",
            interpretation="Dollar strengthening — liquidity tightening",
            contribution=0.64,
            alignment="supporting",
        ),
        HypothesisEvidence(
            indicator="US10Y",
            signal_id="s2",
            observation="US10Y at 5.2 (condition: value > 5.0)",
            interpretation="Long-end rates elevated — restrictive monetary",
            contribution=0.68,
            alignment="supporting",
        ),
    ]


@pytest.fixture
def sample_contradicting() -> list[HypothesisEvidence]:
    return [
        HypothesisEvidence(
            indicator="HG=F",
            signal_id="s5",
            observation="Copper at 4.8 (condition: value > 4.5)",
            interpretation="Industrial demand strong — growth signal",
            contribution=0.385,
            alignment="contradicting",
        ),
    ]


@pytest.fixture
def sample_hypothesis(sample_supporting, sample_contradicting) -> HypothesisSchema:
    return HypothesisSchema(
        statement="Global financial conditions are tightening.",
        dimension="Liquidity",
        direction=SignalDirection.BEARISH,
        confidence=0.82,
        supporting_evidence=sample_supporting,
        contradicting_evidence=sample_contradicting,
        assumptions=[
            "Dollar strength represents tighter global liquidity",
            "Rising bond yields are liquidity-driven not growth-driven",
        ],
    )


# ── HypothesisStatus Enum ─────────────────────────────────────────────────


class TestHypothesisStatus:
    def test_values_exist(self):
        assert HypothesisStatus.ACTIVE.value == "active"
        assert HypothesisStatus.CONFIRMED.value == "confirmed"
        assert HypothesisStatus.REFUTED.value == "refuted"
        assert HypothesisStatus.STALE.value == "stale"

    def test_default_is_active(self):
        h = HypothesisSchema(
            statement="Test",
            dimension="Liquidity",
        )
        assert h.status == HypothesisStatus.ACTIVE

    def test_str_equals_value(self):
        assert HypothesisStatus.ACTIVE.value == "active"


# ── HypothesisEvidence ────────────────────────────────────────────────────


class TestHypothesisEvidence:
    def test_create_supporting(self):
        ev = HypothesisEvidence(
            indicator="DXY",
            signal_id="s1",
            observation="DXY at 106.5",
            interpretation="Dollar strengthening",
            contribution=0.64,
            alignment="supporting",
        )
        assert ev.indicator == "DXY"
        assert ev.signal_id == "s1"
        assert ev.alignment == "supporting"
        assert ev.contribution == 0.64

    def test_create_contradicting(self):
        ev = HypothesisEvidence(
            indicator="HG=F",
            signal_id="s5",
            observation="Copper at 4.8",
            interpretation="Industrial demand strong",
            contribution=0.385,
            alignment="contradicting",
        )
        assert ev.alignment == "contradicting"

    def test_default_contribution(self):
        ev = HypothesisEvidence(
            indicator="DXY",
            signal_id="s1",
            observation="DXY at 106",
            interpretation="Test",
        )
        assert ev.contribution == 0.5

    def test_default_alignment(self):
        ev = HypothesisEvidence(
            indicator="DXY",
            signal_id="s1",
            observation="DXY at 106",
            interpretation="Test",
        )
        assert ev.alignment == "supporting"

    def test_contribution_range(self):
        ev = HypothesisEvidence(
            indicator="DXY",
            signal_id="s1",
            observation="DXY at 106",
            interpretation="Test",
            contribution=0.75,
        )
        assert 0.0 <= ev.contribution <= 1.0

    def test_contribution_boundary_min(self):
        ev = HypothesisEvidence(
            indicator="DXY",
            signal_id="s1",
            observation="DXY at 106",
            interpretation="Test",
            contribution=0.0,
        )
        assert ev.contribution == 0.0

    def test_contribution_boundary_max(self):
        ev = HypothesisEvidence(
            indicator="DXY",
            signal_id="s1",
            observation="DXY at 106",
            interpretation="Test",
            contribution=1.0,
        )
        assert ev.contribution == 1.0


# ── HypothesisSchema ──────────────────────────────────────────────────────


class TestHypothesisSchema:
    def test_create_minimal(self):
        h = HypothesisSchema(
            statement="Liquidity tightening.",
            dimension="Liquidity",
        )
        assert h.statement == "Liquidity tightening."
        assert h.dimension == "Liquidity"
        assert h.status == HypothesisStatus.ACTIVE
        assert h.direction == SignalDirection.NEUTRAL
        assert h.confidence == 0.5
        assert h.supporting_evidence == []
        assert h.contradicting_evidence == []
        assert h.assumptions == []
        assert h.hypothesis_id  # auto-generated

    def test_create_full(self, sample_hypothesis):
        assert sample_hypothesis.statement.startswith("Global financial conditions")
        assert sample_hypothesis.dimension == "Liquidity"
        assert sample_hypothesis.direction == SignalDirection.BEARISH
        assert sample_hypothesis.confidence == 0.82
        assert len(sample_hypothesis.supporting_evidence) == 2
        assert len(sample_hypothesis.contradicting_evidence) == 1
        assert len(sample_hypothesis.assumptions) == 2

    def test_evidence_count_property(self, sample_hypothesis):
        assert sample_hypothesis.evidence_count == 3  # 2 + 1

    def test_evidence_count_zero(self):
        h = HypothesisSchema(statement="Test", dimension="Liquidity")
        assert h.evidence_count == 0

    def test_has_contradictions_true(self, sample_hypothesis):
        assert sample_hypothesis.has_contradictions is True

    def test_has_contradictions_false(self):
        h = HypothesisSchema(
            statement="Test",
            dimension="Liquidity",
            supporting_evidence=[
                HypothesisEvidence(
                    indicator="DXY",
                    signal_id="s1",
                    observation="DXY at 106",
                    interpretation="Test",
                    alignment="supporting",
                )
            ],
        )
        assert h.has_contradictions is False

    def test_supporting_ratio(self, sample_hypothesis):
        assert sample_hypothesis.supporting_ratio == pytest.approx(2 / 3)

    def test_supporting_ratio_empty(self):
        h = HypothesisSchema(statement="Test", dimension="Liquidity")
        assert h.supporting_ratio == 0.0

    def test_supporting_ratio_all_supporting(self):
        h = HypothesisSchema(
            statement="Test",
            dimension="Liquidity",
            supporting_evidence=[
                HypothesisEvidence(
                    indicator="DXY",
                    signal_id="s1",
                    observation="DXY at 106",
                    interpretation="Test",
                    alignment="supporting",
                )
            ],
        )
        assert h.supporting_ratio == 1.0

    def test_unique_ids(self):
        h1 = HypothesisSchema(statement="A", dimension="Liquidity")
        h2 = HypothesisSchema(statement="B", dimension="Credit")
        assert h1.hypothesis_id != h2.hypothesis_id

    def test_repr(self, sample_hypothesis):
        r = repr(sample_hypothesis)
        assert "Hypothesis" in r
        assert "Liquidity" in r
        assert "bearish" in r

    def test_timestamp_is_utc(self):
        h = HypothesisSchema(statement="Test", dimension="Liquidity")
        assert h.generated_at.tzinfo is not None


# ── HypothesisSet ─────────────────────────────────────────────────────────


class TestHypothesisSet:
    def test_create_empty(self):
        hs = HypothesisSet()
        assert hs.count == 0
        assert hs.hypotheses == []
        assert hs.dimensions_covered == []

    def test_create_with_hypotheses(self, sample_hypothesis):
        h2 = HypothesisSchema(
            statement="Growth accelerating.",
            dimension="Growth",
            direction=SignalDirection.BULLISH,
        )
        hs = HypothesisSet(
            hypotheses=[sample_hypothesis, h2],
            dimensions_covered=["Liquidity", "Growth"],
            summary="Two competing narratives.",
        )
        assert hs.count == 2
        assert hs.dimensions_covered == ["Liquidity", "Growth"]
        assert hs.summary == "Two competing narratives."

    def test_get_by_dimension(self, sample_hypothesis):
        h2 = HypothesisSchema(
            statement="Credit improving.",
            dimension="Credit",
            direction=SignalDirection.BULLISH,
        )
        hs = HypothesisSet(
            hypotheses=[sample_hypothesis, h2],
            dimensions_covered=["Liquidity", "Credit"],
        )
        liquidity = hs.get_by_dimension("Liquidity")
        assert len(liquidity) == 1
        assert liquidity[0] is sample_hypothesis

    def test_get_by_dimension_nonexistent(self, sample_hypothesis):
        hs = HypothesisSet(hypotheses=[sample_hypothesis])
        result = hs.get_by_dimension("Inflation")
        assert result == []

    def test_get_highest_confidence(self):
        h1 = HypothesisSchema(
            statement="Low confidence.",
            dimension="Liquidity",
            confidence=0.3,
        )
        h2 = HypothesisSchema(
            statement="High confidence.",
            dimension="Credit",
            confidence=0.9,
        )
        hs = HypothesisSet(hypotheses=[h1, h2])
        best = hs.get_highest_confidence()
        assert best is h2

    def test_get_highest_confidence_empty(self):
        hs = HypothesisSet()
        assert hs.get_highest_confidence() is None

    def test_generated_at_is_set(self):
        hs = HypothesisSet()
        assert hs.generated_at.tzinfo is not None

    def test_repr(self, sample_hypothesis):
        hs = HypothesisSet(
            hypotheses=[sample_hypothesis],
            dimensions_covered=["Liquidity"],
        )
        r = repr(hs)
        assert "HypothesisSet" in r
        assert "1" in r  # hypothesis count
