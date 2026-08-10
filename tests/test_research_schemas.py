"""Tests for Milestone C Research Evolution Schemas.

Validates the four-level cognitive hierarchy data structures.
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.schemas.research import (
    ResearchPrinciple, ResearchFramework, FrameworkSet,
    CompetingPrinciple, ConflictRecord, ConflictResolution,
    FindingLifecycle, FindingTTLStatus,
    PrincipleEvidence, PrincipleStrength, PrincipleStatus,
    FrameworkStatus, FrameworkExplainability,
    SynthesisStrategy,
)


# ═══════════════════════════════════════════════════════════════════════════════
# ResearchPrinciple tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestResearchPrinciple:
    def test_create_principle_with_granularity(self):
        """GR-1: Single causal edge — one directed relationship."""
        p = ResearchPrinciple(
            name="VIX Threshold",
            statement="When VIX > 30, credit→SPX transmission breaks",
            domain="credit→SPX",
            strength=PrincipleStrength.VALIDATED,
        )
        assert p.is_atomic  # GR-4: atomic domain
        assert p.strength == PrincipleStrength.VALIDATED
        assert p.status == PrincipleStatus.ACTIVE

    def test_principle_strength_progression(self):
        p = ResearchPrinciple(name="Test", domain="liquidity", statement="x → y")
        p.evidence.total_observations = 100
        p.evidence.accuracy = 1.0
        p.evidence.regimes_count = 5
        p.evidence.sustained_cycles = 200
        score = p.strength_score()
        assert score > 0.7

    def test_principle_competition(self):
        p = ResearchPrinciple(
            name="Compete A", domain="liquidity",
            statement="Liquidity easing → Gold rises",
            strength=PrincipleStrength.VALIDATED,
            status=PrincipleStatus.ACTIVE_COMPETITION,
            competes_with=["pr-other"],
        )
        assert p.is_competition_active
        assert p.competes_with == ["pr-other"]


class TestResearchFramework:
    def test_framework_explainability(self):
        p1 = ResearchPrinciple(
            principle_id="p1", name="P1", domain="monetary",
            statement="test", strength=PrincipleStrength.MATURE,
        )
        p1.evidence.total_observations = 80
        p1.evidence.accuracy = 0.85

        fw = ResearchFramework(
            framework_id="fw-test",
            name="Monetary Framework",
            thesis="Monetary policy is the primary driver of asset prices in "
                   "this regime. Rate decisions ripple through credit markets "
                   "and equity valuations via the discount rate channel.",
            status=FrameworkStatus.ACTIVE,
            principles=["p1"],
            accuracy_trajectory=[0.75, 0.80, 0.78, 0.82, 0.79],
        )

        explain = fw.compute_explainability({"p1": p1})
        assert explain.name == "Monetary Framework"
        assert len(explain.thesis) >= 100
        assert explain.supporting_principles_count == 1
        assert explain.historical_win_rate > 0

    def test_framework_confidence_computation(self):
        p1 = ResearchPrinciple(
            principle_id="p1", name="P1", domain="monetary",
            statement="test", strength=PrincipleStrength.MATURE,
        )
        p1.evidence.total_observations = 100
        p1.evidence.accuracy = 0.90

        fw = ResearchFramework(
            name="Test FW",
            thesis="A framework thesis that explains the macro worldview in "
                   "adequate detail for confidence computation purposes here.",
            principles=["p1"],
            accuracy_trajectory=[0.70, 0.72, 0.71, 0.73],
        )
        conf = fw.compute_confidence({"p1": p1})
        assert 0 <= conf <= 1


class TestFrameworkSet:
    def test_add_framework(self):
        fs = FrameworkSet()
        assert fs.add_framework("fw-a") is True
        assert fs.active_count == 1
        assert "fw-a" in fs.framework_weights

    def test_capacity_limit(self):
        fs = FrameworkSet(max_active=3)
        fs.add_framework("fw-a")
        fs.add_framework("fw-b")
        fs.add_framework("fw-c")
        assert fs.is_at_capacity
        assert fs.add_framework("fw-d") is False  # No room

    def test_replace_weakest(self):
        fs = FrameworkSet(max_active=3)
        fs.add_framework("fw-a")
        fs.add_framework("fw-b")
        fs.add_framework("fw-c")
        result = fs.replace_weakest("fw-d", 0.3, "fw-c")
        assert result is True
        assert "fw-c" in fs.retired_frameworks
        assert "fw-d" in fs.active_frameworks

    def test_min_active_guard(self):
        fs = FrameworkSet(max_active=3, min_active=1)
        fs.add_framework("fw-a")
        result = fs.retire_framework("fw-a")  # Cannot retire last framework
        assert result is False


class TestCompetingPrinciple:
    def test_competition_creation(self):
        cp = CompetingPrinciple(
            principle_a_id="pr-a", principle_b_id="pr-b",
            domain="liquidity",
        )
        assert cp.status == "competing"
        assert cp.a_win_rate == 0.5

    def test_decisive_resolution(self):
        cp = CompetingPrinciple(principle_a_id="pr-a", principle_b_id="pr-b")
        for _ in range(30):
            cp.record_evidence(for_a=True)
            cp.advance_cycle()
        assert cp.is_decisive
        assert cp.a_win_rate >= 0.70

    def test_stalemate(self):
        cp = CompetingPrinciple(principle_a_id="pr-a", principle_b_id="pr-b")
        for i in range(50):
            cp.record_evidence(for_a=(i % 2 == 0))
            cp.advance_cycle()
        assert cp.is_stalemate
        assert not cp.is_decisive


class TestFindingLifecycle:
    def test_default_ttl(self):
        fl = FindingLifecycle(finding_id="test")
        assert fl.status == FindingTTLStatus.ACTIVE
        assert fl.ttl_days == 90
        assert not fl.is_expired

    def test_expiry(self):
        fl = FindingLifecycle(
            finding_id="test",
            created_at=datetime.now(timezone.utc) - timedelta(days=91),
        )
        fl.expires_at = fl.created_at + timedelta(days=fl.ttl_days)
        assert fl.is_expired

    def test_freeze_unfreeze(self):
        fl = FindingLifecycle(finding_id="test")
        remaining_before = fl.days_remaining
        fl.freeze("conflict-1")
        assert fl.status == FindingTTLStatus.FROZEN
        assert fl.days_remaining == -1  # Indefinite
        fl.unfreeze()
        assert fl.status == FindingTTLStatus.ACTIVE
        assert fl.days_remaining >= 0

    def test_promotion_immune_to_ttl(self):
        fl = FindingLifecycle(
            finding_id="test",
            created_at=datetime.now(timezone.utc) - timedelta(days=200),
        )
        fl.expires_at = fl.created_at + timedelta(days=fl.ttl_days)
        fl.promote("pr-1")
        assert fl.status == FindingTTLStatus.PROMOTED
        assert not fl.is_expired  # Immune to TTL

    def test_ttl_by_confidence(self):
        fl = FindingLifecycle(finding_id="test")
        fl.set_ttl("robust")
        assert fl.ttl_days == 180
        fl.set_ttl("preliminary")
        assert fl.ttl_days == 45
        fl.set_ttl("observed")
        assert fl.ttl_days == 90


class TestPrincipleEvidence:
    def test_strength_score(self):
        pe = PrincipleEvidence(
            total_observations=100,
            accuracy=0.85,
            regimes_count=3,
            sustained_cycles=150,
        )
        assert pe.strength_score > 0.5


class TestConflictResolution:
    def test_all_options(self):
        assert ConflictResolution.A_WINS.value == "a_wins"
        assert ConflictResolution.UNRESOLVED.value == "unresolved"
        assert ConflictResolution.ARCHIVED_REGIME.value == "archived_regime"


class TestFrameworkExplainability:
    def test_full_output(self):
        fe = FrameworkExplainability(
            name="Test FW",
            thesis="A sufficiently detailed thesis that explains the worldview "
                   "in adequate detail to serve as a proper framework explanation.",
            confidence=0.71,
            supporting_principles_count=17,
            contradicting_principles_count=3,
            historical_win_rate=0.74,
            activated_since_cycle=100,
            parent_framework="fw-old",
            competing_frameworks=["fw-compete-1"],
        )
        desc = fe.describe()
        assert "Test FW" in desc
        assert "0.71" in desc
        assert "17" in desc
        assert "3" in desc
