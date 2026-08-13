"""Tests for Sprint 7 — Reflection domain enums and schemas."""

from datetime import UTC, datetime

import pytest

from src.domain.reflection import FindingSeverity, ReflectionVerdict
from src.schemas.reflection import ReflectionFinding, ReflectionReport, ReflectionSet

# ── Domain Enums ────────────────────────────────────────────────────────────


class TestReflectionVerdict:
    def test_confirmed_value(self):
        assert ReflectionVerdict.CONFIRMED.value == "confirmed"

    def test_refuted_value(self):
        assert ReflectionVerdict.REFUTED.value == "refuted"

    def test_uncertain_value(self):
        assert ReflectionVerdict.UNCERTAIN.value == "uncertain"

    def test_all_members_present(self):
        members = set(ReflectionVerdict.__members__.keys())
        assert members == {"CONFIRMED", "REFUTED", "UNCERTAIN"}

    def test_value_equals_string(self):
        assert ReflectionVerdict.CONFIRMED.value == "confirmed"


class TestFindingSeverity:
    def test_critical_value(self):
        assert FindingSeverity.CRITICAL.value == "critical"

    def test_major_value(self):
        assert FindingSeverity.MAJOR.value == "major"

    def test_minor_value(self):
        assert FindingSeverity.MINOR.value == "minor"

    def test_all_members_present(self):
        members = set(FindingSeverity.__members__.keys())
        assert members == {"CRITICAL", "MAJOR", "MINOR"}

    def test_ordering(self):
        """Severity should be comparable by intuition."""
        severities = [FindingSeverity.MINOR, FindingSeverity.MAJOR, FindingSeverity.CRITICAL]
        # All three must be distinct
        assert len(set(severities)) == 3


# ── ReflectionFinding ───────────────────────────────────────────────────────


class TestReflectionFinding:
    def test_minimal_construction(self):
        f = ReflectionFinding(
            type="evidence_insufficient",
            description="Not enough data.",
        )
        assert f.type == "evidence_insufficient"
        assert f.severity == FindingSeverity.MAJOR  # default
        assert "Not enough" in f.description

    def test_all_types(self):
        for t in [
            "evidence_insufficient",
            "conflicting_evidence",
            "evidence_quality_low",
            "single_source_risk",
        ]:
            f = ReflectionFinding(type=t, description=f"Test {t}")
            assert f.type == t

    def test_with_explicit_severity(self):
        f = ReflectionFinding(
            type="conflicting_evidence",
            severity=FindingSeverity.CRITICAL,
            description="Evidence contradicts.",
        )
        assert f.severity == FindingSeverity.CRITICAL

    def test_type_too_long(self):
        with pytest.raises(ValueError):
            ReflectionFinding(type="x" * 41, description="valid")

    def test_description_too_long(self):
        with pytest.raises(ValueError):
            ReflectionFinding(type="valid", description="d" * 513)

    def test_type_empty(self):
        with pytest.raises(ValueError):
            ReflectionFinding(type="", description="valid")

    def test_description_empty(self):
        with pytest.raises(ValueError):
            ReflectionFinding(type="valid", description="")


# ── ReflectionReport ────────────────────────────────────────────────────────


class TestReflectionReport:
    def test_minimal_construction(self):
        r = ReflectionReport(statement="A test hypothesis.")
        assert r.statement == "A test hypothesis."
        assert r.verdict == ReflectionVerdict.UNCERTAIN
        assert r.original_confidence == 0.5
        assert r.updated_confidence == 0.5
        assert r.findings == []
        assert r.evidence_sufficiency == "medium"
        assert r.evidence_consistency == "consistent"

    def test_full_construction(self):
        now = datetime.now(UTC)
        r = ReflectionReport(
            hypothesis_id="h1",
            statement="Liquidity is tightening.",
            original_confidence=0.8,
            updated_confidence=0.6,
            verdict=ReflectionVerdict.CONFIRMED,
            findings=[
                ReflectionFinding(
                    type="evidence_insufficient",
                    severity=FindingSeverity.MINOR,
                    description="Only 2 indicators.",
                )
            ],
            evidence_sufficiency="medium",
            evidence_consistency="mixed",
            review_summary="Belief mostly intact.",
            reviewed_at=now,
        )
        assert r.hypothesis_id == "h1"
        assert r.original_confidence == 0.8
        assert r.updated_confidence == 0.6
        assert r.verdict == ReflectionVerdict.CONFIRMED

    def test_confidence_delta(self):
        r = ReflectionReport(
            statement="Test",
            original_confidence=0.8,
            updated_confidence=0.5,
        )
        assert r.confidence_delta == pytest.approx(-0.3)

    def test_confidence_delta_positive(self):
        r = ReflectionReport(
            statement="Test",
            original_confidence=0.5,
            updated_confidence=0.7,
        )
        assert r.confidence_delta == pytest.approx(0.2)

    def test_has_critical_findings_true(self):
        r = ReflectionReport(
            statement="Test",
            findings=[
                ReflectionFinding(
                    type="conflicting_evidence",
                    severity=FindingSeverity.CRITICAL,
                    description="Conflict!",
                )
            ],
        )
        assert r.has_critical_findings is True

    def test_has_critical_findings_false(self):
        r = ReflectionReport(
            statement="Test",
            findings=[
                ReflectionFinding(
                    type="evidence_insufficient",
                    severity=FindingSeverity.MINOR,
                    description="Minor.",
                )
            ],
        )
        assert r.has_critical_findings is False

    def test_finding_count(self):
        r = ReflectionReport(statement="Test")
        assert r.finding_count == 0

        r = ReflectionReport(
            statement="Test",
            findings=[
                ReflectionFinding(type="a", description="1"),
                ReflectionFinding(type="b", description="2"),
                ReflectionFinding(type="c", description="3"),
            ],
        )
        assert r.finding_count == 3

    def test_invalid_sufficiency(self):
        with pytest.raises(ValueError):
            ReflectionReport(statement="Test", evidence_sufficiency="invalid")

    def test_invalid_consistency(self):
        with pytest.raises(ValueError):
            ReflectionReport(statement="Test", evidence_consistency="invalid")

    def test_statement_too_long(self):
        with pytest.raises(ValueError):
            ReflectionReport(statement="s" * 1025)

    def test_statement_empty(self):
        with pytest.raises(ValueError):
            ReflectionReport(statement="")

    def test_confidence_out_of_range_high(self):
        with pytest.raises(ValueError):
            ReflectionReport(statement="T", original_confidence=1.1)

    def test_confidence_out_of_range_low(self):
        with pytest.raises(ValueError):
            ReflectionReport(statement="T", updated_confidence=-0.1)


# ── ReflectionSet ───────────────────────────────────────────────────────────


class TestReflectionSet:
    def test_empty_construction(self):
        rs = ReflectionSet()
        assert rs.count == 0
        assert rs.confirmed == []
        assert rs.refuted == []
        assert rs.uncertain == []

    def test_with_reports(self):
        r1 = ReflectionReport(
            hypothesis_id="h1",
            statement="A",
            verdict=ReflectionVerdict.CONFIRMED,
            original_confidence=0.8,
            updated_confidence=0.75,
        )
        r2 = ReflectionReport(
            hypothesis_id="h2",
            statement="B",
            verdict=ReflectionVerdict.REFUTED,
            original_confidence=0.7,
            updated_confidence=0.2,
        )
        r3 = ReflectionReport(
            hypothesis_id="h3",
            statement="C",
            verdict=ReflectionVerdict.UNCERTAIN,
            original_confidence=0.5,
            updated_confidence=0.45,
        )
        rs = ReflectionSet(reports=[r1, r2, r3], summary="Mixed results.")
        assert rs.count == 3
        assert len(rs.confirmed) == 1
        assert len(rs.refuted) == 1
        assert len(rs.uncertain) == 1
        assert rs.confirmed[0].hypothesis_id == "h1"
        assert rs.refuted[0].hypothesis_id == "h2"
        assert rs.uncertain[0].hypothesis_id == "h3"

    def test_get_by_hypothesis_id(self):
        r = ReflectionReport(
            hypothesis_id="target-h",
            statement="Target",
            verdict=ReflectionVerdict.CONFIRMED,
        )
        rs = ReflectionSet(reports=[r])
        assert rs.get_by_hypothesis_id("target-h") is r
        assert rs.get_by_hypothesis_id("missing") is None
