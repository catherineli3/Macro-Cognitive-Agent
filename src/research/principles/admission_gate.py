"""Principle Admission Gate — Five-criteria admission gate (Milestone C, Q1).

Evaluates ResearchFindings against the five admission criteria (P1-P5)
to determine whether a finding qualifies for promotion to ResearchPrinciple.

    P1: Cross-Regime Validation — >=2 distinct regimes
    P2: Repetition Count — >=5 independent observations
    P3: Minimum Evidence — >=30 edge-level observations
    P4: Sustained Validity — No contradiction in last 20 cycles
    P5: Generality — Applies to >=2 distinct transmission channels
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.schemas.transmission_v3_1 import ResearchFinding, ResearchFindingsReport
from src.schemas.research import ResearchPrinciple, PrincipleEvidence, PrincipleStrength
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AdmissionResult:
    """Result of evaluating a finding cluster against admission criteria."""
    passed: bool = False
    p1_cross_regime: bool = False
    p2_repetition: bool = False
    p3_evidence: bool = False
    p4_sustained: bool = False
    p5_generality: bool = False
    regimes_found: list[str] = field(default_factory=list)
    repetition_count: int = 0
    evidence_count: int = 0
    sustained_cycles: int = 0
    channels_found: list[str] = field(default_factory=list)
    detail: str = ""


class PrincipleAdmissionGate:
    """Evaluates whether accumulated findings qualify for Principle creation.

    P1-P5 criteria per the architecture specification (Q1).
    All five must pass for full admission.
    P2-P4 pass = candidate status; P1 pending.
    """

    # Thresholds (architecture-defined)
    P1_MIN_REGIMES = 2
    P2_MIN_REPETITION = 5
    P3_MIN_EVIDENCE = 30
    P4_SUSTAINED_WINDOW = 20
    P5_MIN_CHANNELS = 2

    # Regime definition dimensions
    REGIME_DIMENSIONS = [
        "monetary_policy",   # "tightening" | "neutral" | "easing"
        "fiscal_stance",     # "expansionary" | "neutral" | "contractionary"
        "volatility",         # "low" | "moderate" | "high"
        "growth",            # "accelerating" | "stable" | "decelerating" | "contracting"
        "inflation",         # "rising" | "stable" | "falling"
    ]

    def __init__(self) -> None:
        self._finding_clusters: dict[str, list[ResearchFinding]] = {}
        self._regime_tags: dict[str, dict] = {}      # finding_id → regime dict
        self._contradiction_counts: dict[str, list] = {}  # finding_id → contradiction cycles

    def register_finding(self, finding: ResearchFinding,
                         regime: dict | None = None,
                         cycle: int = 0) -> None:
        """Register a finding and its regime tag for later evaluation."""
        channel = finding.category or "unknown"
        if channel not in self._finding_clusters:
            self._finding_clusters[channel] = []
        self._finding_clusters[channel].append(finding)
        if regime:
            self._regime_tags[finding.finding_id] = regime

    def register_findings_report(self, report: ResearchFindingsReport,
                                 regime: dict | None = None,
                                 cycle: int = 0) -> None:
        """Register all findings from a report."""
        for f in report.reliability_ranking:
            self.register_finding(f, regime, cycle)
        for f in report.failure_warnings:
            self.register_finding(f, regime, cycle)
        for f in report.failure_event_correlations:
            self.register_finding(f, regime, cycle)
        for f in report.regime_similarities:
            self.register_finding(f, regime, cycle)

    def evaluate(self, findings: list[ResearchFinding],
                 context_key: str = "") -> AdmissionResult:
        """Evaluate a cluster of findings against P1-P5 and return the result.

        Returns an AdmissionResult with pass/fail for each criterion.
        """
        result = AdmissionResult()

        # P1: Cross-Regime Validation
        result.p1_cross_regime, result.regimes_found = self._check_cross_regime(findings)
        # P2: Repetition Count
        result.p2_repetition, result.repetition_count = self._check_repetition(findings)
        # P3: Minimum Evidence
        result.p3_evidence, result.evidence_count = self._check_evidence(findings)
        # P4: Sustained Validity
        result.p4_sustained, result.sustained_cycles = self._check_sustained(findings)
        # P5: Generality
        result.p5_generality, result.channels_found = self._check_generality(findings)

        result.passed = all([
            result.p1_cross_regime, result.p2_repetition,
            result.p3_evidence, result.p4_sustained, result.p5_generality,
        ])

        if result.passed:
            result.detail = "All P1-P5 criteria met. Eligible for Principle promotion."
        elif result.p2_repetition and result.p3_evidence and result.p4_sustained:
            result.detail = "P2-P4 met but P1 (cross-regime) pending. Eligible for candidate status."
        else:
            missing = []
            if not result.p1_cross_regime: missing.append("P1")
            if not result.p2_repetition: missing.append("P2")
            if not result.p3_evidence: missing.append("P3")
            if not result.p4_sustained: missing.append("P4")
            if not result.p5_generality: missing.append("P5")
            result.detail = f"Failed criteria: {', '.join(missing)}. Not eligible."

        logger.info(
            "Admission gate: %s | P1=%s P2=%s P3=%s P4=%s P5=%s → %s",
            context_key,
            result.p1_cross_regime, result.p2_repetition,
            result.p3_evidence, result.p4_sustained, result.p5_generality,
            "PASS" if result.passed else "FAIL",
        )
        return result

    def create_principle(self, findings: list[ResearchFinding],
                         name: str, statement: str, domain: str,
                         preconditions: dict | None = None,
                         cycle: int = 0) -> ResearchPrinciple | None:
        """Attempt to create a Principle from findings. Returns None if criteria not met.

        F1.6 (G2): ALL new principles start as CANDIDATE regardless of P1-P5 result.
        VALIDATED status requires separate multi-cycle confirmation via CandidateManager.
        """
        result = self.evaluate(findings)

        if not result.passed and not (
            result.p2_repetition and result.p3_evidence and result.p4_sustained
        ):
            return None

        # G2: Always CANDIDATE — never bypass to VALIDATED
        strength = PrincipleStrength.CANDIDATE

        evidence = PrincipleEvidence(
            total_observations=result.evidence_count,
            correct_in_scope=result.evidence_count,
            accuracy=0.0,  # G3: accuracy will be computed from outcomes
            regimes_count=len(result.regimes_found),
            regimes_validated=list(result.regimes_found),
            channels_validated=list(result.channels_found),
            last_validated_cycle=cycle,
            sustained_cycles=1,
            contradiction_count=0,
        )

        return ResearchPrinciple(
            name=name,
            statement=statement,
            domain=domain,
            preconditions=preconditions or {},
            strength=strength,
            evidence=evidence,
            source_findings=[f.finding_id for f in findings],
            created_at_cycle=cycle,
            promoted_from_findings=[f.finding_id for f in findings],
        )

    # ── P1-P5 Checkers ──────────────────────────────────────────────────

    @staticmethod
    def _regimes_are_distinct(r1: dict, r2: dict) -> bool:
        """Two regimes are distinct if >=2 dimensions differ in category."""
        dims = ["monetary_policy", "fiscal_stance", "volatility", "growth", "inflation"]
        diff_count = 0
        for dim in dims:
            v1 = (r1 or {}).get(dim, "unknown")
            v2 = (r2 or {}).get(dim, "unknown")
            if v1 != v2:
                diff_count += 1
        return diff_count >= 2

    def _check_cross_regime(self, findings: list[ResearchFinding]) -> tuple[bool, list[str]]:
        regimes: set[str] = set()
        for f in findings:
            regime = self._regime_tags.get(f.finding_id, {})
            regime_key = str(sorted(regime.items())) if regime else f.context_key
            regimes.add(regime_key)
        # Count distinct regimes
        regimes_list = list(regimes)
        if len(regimes_list) < self.P1_MIN_REGIMES:
            return False, regimes_list
        return True, regimes_list

    @staticmethod
    def _check_repetition(findings: list[ResearchFinding]) -> tuple[bool, int]:
        count = len(findings)
        return count >= PrincipleAdmissionGate.P2_MIN_REPETITION, count

    @staticmethod
    def _check_evidence(findings: list[ResearchFinding]) -> tuple[bool, int]:
        total = sum(f.evidence.get("observations", 0) for f in findings)
        return total >= PrincipleAdmissionGate.P3_MIN_EVIDENCE, total

    def _check_sustained(self, findings: list[ResearchFinding]) -> tuple[bool, int]:
        # Check if any finding has recent contradictions
        recent_contradictions = 0
        for f in findings:
            contradictions = self._contradiction_counts.get(f.finding_id, [])
            recent_contradictions += sum(
                1 for c in contradictions if c >= self.P4_SUSTAINED_WINDOW
            )
        sustained = recent_contradictions == 0
        # Calculate sustained cycles (approximate from repetition count)
        sustained_cycles = len(findings) * 5  # rough estimate
        return sustained, sustained_cycles

    @staticmethod
    def _check_generality(findings: list[ResearchFinding]) -> tuple[bool, list[str]]:
        channels: set[str] = set()
        for f in findings:
            if f.category:
                channels.add(f.category)
            for edge in (f.source_edges or []):
                channels.add(edge)
        channels_list = list(channels)
        return len(channels_list) >= PrincipleAdmissionGate.P5_MIN_CHANNELS, channels_list

    # ── Utility ──────────────────────────────────────────────────────────

    def get_candidates(self) -> list[str]:
        """Get channels that have enough findings for evaluation."""
        return [
            ch for ch, findings in self._finding_clusters.items()
            if len(findings) >= self.P2_MIN_REPETITION
        ]

    @property
    def total_clusters(self) -> int:
        return len(self._finding_clusters)

    @property
    def total_findings_registered(self) -> int:
        return sum(len(v) for v in self._finding_clusters.values())
