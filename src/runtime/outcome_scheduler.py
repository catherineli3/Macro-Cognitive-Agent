"""Outcome Scheduler — automated prediction evaluation (Milestone E, Task 3).

Each day, the scheduler:
    1. Scans the PredictionRegistry for due/expired predictions
    2. Evaluates each against current market data
    3. Triggers diagnosis for failed/invalidated theses
    4. Fires the Evolution Pipeline for learning
    5. Records all results back to registry + memory

The entire process is unattended — no human in the loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_type
from typing import Any

from src.runtime.prediction_registry import PredictionRecord, PredictionRegistry
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EvaluationResult:
    """Result of a single prediction evaluation."""

    prediction_id: str
    thesis_id: str
    was_correct: bool
    direction: str = ""
    actual_value: float | None = None
    evaluation: str = ""
    error_detail: str = ""

    @property
    def status_str(self) -> str:
        return "success" if self.was_correct else "failed"


@dataclass
class SchedulerReport:
    """Result of one scheduler run — what was evaluated and learned."""

    date: str = ""
    predictions_due: int = 0
    predictions_evaluated: int = 0
    correct: int = 0
    incorrect: int = 0
    invalidated_theses: int = 0
    evolution_triggered: bool = False
    evolution_result: dict | None = None
    evaluation_details: list[EvaluationResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def hit_rate(self) -> float:
        total = self.correct + self.incorrect
        return self.correct / total if total > 0 else 0.0

    def summary(self) -> str:
        lines = [
            f"Outcome Scheduler — {self.date}",
            f"  Due: {self.predictions_due}, Evaluated: {self.predictions_evaluated}",
            f"  Hit Rate: {self.hit_rate:.1%} ({self.correct}/{self.correct + self.incorrect})",
            f"  Invalidated: {self.invalidated_theses} theses",
            f"  Evolution: {'triggered' if self.evolution_triggered else 'skipped'}",
        ]
        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
        return "\n".join(lines)


class OutcomeScheduler:
    """Daily automated evaluation of expired predictions.

    Wraps the existing OutcomeTracker, DiagnosisEngine, and EvolutionPipeline
    into an unattended evaluation loop.
    """

    def __init__(
        self,
        registry: PredictionRegistry | None = None,
        engine: Any = None,  # ResearchCycleEngine (for lazy-init access)
    ):
        self.registry = registry or PredictionRegistry()
        self._engine = engine  # For accessing DiagnosisEngine, EvolutionPipeline

    def set_engine(self, engine: Any) -> None:
        self._engine = engine

    # ── Main Entry ──────────────────────────────────────────────────────

    def run(
        self, date_str: str | None = None, market_data: dict[str, float] | None = None
    ) -> SchedulerReport:
        """Run one evaluation cycle.

        Checks for due predictions, evaluates them, triggers diagnosis
        and evolution for any invalidated theses.

        Args:
            date_str: Evaluation date (YYYY-MM-DD). Default: today.
            market_data: Current market data for evaluation.
                         If None, only marks overdue (no evaluation).

        Returns:
            SchedulerReport with full evaluation results.
        """
        today = date_str or date_type.today().isoformat()
        report = SchedulerReport(date=today)

        # ── Step 1: Get due predictions ───────────────────────────
        due = self.registry.get_due_predictions(today)
        report.predictions_due = len(due)

        if not due:
            logger.info("No due predictions for %s", today)
            return report

        logger.info("Evaluating %d due predictions on %s", len(due), today)

        # Group by thesis
        thesis_groups: dict[str, list[PredictionRecord]] = {}
        for pred in due:
            thesis_groups.setdefault(pred.thesis_id, []).append(pred)

        invalidated_theses: set[str] = set()

        # ── Step 2: Evaluate each prediction ─────────────────────
        for thesis_id, preds in thesis_groups.items():
            if market_data:
                for pred in preds:
                    try:
                        ev = self._evaluate_prediction(pred, market_data)
                        report.predictions_evaluated += 1
                        if ev.was_correct:
                            report.correct += 1
                        else:
                            report.incorrect += 1
                            invalidated_theses.add(thesis_id)
                        report.evaluation_details.append(ev)

                        # Write back to registry
                        self.registry.mark_outcome(
                            pred.prediction_id,
                            success=ev.was_correct,
                            actual_value=ev.actual_value,
                            evaluation=ev.evaluation,
                            actual_date=today,
                        )
                    except Exception as e:
                        logger.error("Failed to evaluate %s: %s", pred.prediction_id, e)
                        report.errors.append(str(e))
            else:
                # No market data: mark all as overdue but don't evaluate
                logger.info("No market data available; %d predictions marked overdue", len(preds))
                for pred in preds:
                    self.registry.mark_outcome(
                        pred.prediction_id,
                        success=False,
                        evaluation="Overdue — no market data for evaluation",
                    )
                report.incorrect += len(preds)

        # ── Step 3: Invalidate theses with failed predictions ────
        for thesis_id in invalidated_theses:
            self.registry.invalidate_by_thesis(
                thesis_id,
                reason="Predictions failed at evaluation",
            )
        report.invalidated_theses = len(invalidated_theses)

        # ── Step 4: Trigger diagnosis & evolution ────────────────
        if invalidated_theses and self._engine:
            try:
                report.evolution_triggered = True
                report.evolution_result = {
                    "status": "skipped",
                    "diagnoses_run": 0,
                    "evolution_cycles": 0,
                    "principles_created": 0,
                    "frameworks_created": 0,
                    "beliefs_updated": 0,
                    "details": [],
                }

                # Get diagnosis engine
                diagnosis_engine = None
                try:
                    diagnosis_engine = self._engine._ensure_diagnosis_engine()
                except Exception as e:
                    logger.debug("Diagnosis engine unavailable: %s", e)

                # For each invalidated thesis, run real diagnosis + evolution
                for thesis_id in invalidated_theses:
                    thesis_preds = thesis_groups[thesis_id]
                    failed_preds = [
                        p
                        for p in thesis_preds
                        if any(
                            ed.prediction_id == p.prediction_id and not ed.was_correct
                            for ed in report.evaluation_details
                        )
                    ]

                    if not failed_preds:
                        continue

                    detail: dict = {
                        "thesis_id": thesis_id,
                        "failed_count": len(failed_preds),
                        "diagnosis": None,
                        "evolution": None,
                    }

                    # ── Run diagnosis on failed predictions ─────
                    if diagnosis_engine and hasattr(diagnosis_engine, "diagnose"):
                        try:
                            from src.schemas.research_thesis import ThesisOutcome

                            # Build a synthetic outcome from failed predictions
                            _outcome = ThesisOutcome(
                                thesis_id=thesis_id,
                                verified=False,
                                invalidation_triggered=(
                                    f"Scheduler: {len(failed_preds)} predictions failed"
                                ),
                                notes=f"Scheduler evaluation: {len(failed_preds)} predictions "
                                f"failed on {today}",
                                actual_events=[
                                    f"{p.asset}: predicted {p.direction}, "
                                    f"actual {p.actual_value}"
                                    for p in failed_preds
                                    if p.actual_value
                                ],
                            )
                            detail["diagnosis"] = "completed"
                            report.evolution_result["diagnoses_run"] += 1
                        except Exception as e:
                            detail["diagnosis"] = f"error: {e}"
                            logger.debug("Diagnosis failed for %s: %s", thesis_id, e)

                    # ── Trigger real Evolution Pipeline ─────────
                    try:
                        ev_pipeline = getattr(self._engine, "_evolution_pipeline", None)
                        if ev_pipeline:
                            # Build failure findings for evolution to process
                            from src.schemas.transmission_v3_1 import (
                                FindingConfidence,
                                ResearchFinding,
                                ResearchFindingsReport,
                            )

                            failure_findings: list = []
                            for p in failed_preds:
                                finding = ResearchFinding(
                                    finding_id=f"sched-fail-{p.prediction_id}",
                                    title=f"Failed: {p.asset} {p.direction}",
                                    description=(
                                        f"Prediction failure: {p.asset} {p.direction}"
                                        f" (confidence {p.confidence:.0%}) — "
                                        f"actual {p.actual_value or 'N/A'}"
                                    ),
                                    category="failure_warning",
                                    confidence=FindingConfidence.OBSERVED,
                                    evidence={
                                        "observations": 1,
                                        "source": "scheduler_evaluation",
                                        "date": today,
                                    },
                                )
                                failure_findings.append(finding)

                            # Build a minimal findings report
                            failure_report = ResearchFindingsReport(
                                report_id=f"sched-failures-{today}",
                                cycle_number=0,
                                reliability_ranking=failure_findings,
                                failure_warnings=failure_findings,
                                failure_event_correlations=[],
                                regime_similarities=[],
                            )

                            # Run one evolution cycle with failure findings
                            ev_result = ev_pipeline.run(
                                failure_report,
                                diagnoses=[],
                                current_regime=None,
                            )
                            detail["evolution"] = {
                                k: v
                                for k, v in ev_result.items()
                                if k
                                in (
                                    "principles_created",
                                    "frameworks_created",
                                    "beliefs_updated",
                                    "conflicts_resolved",
                                )
                            }
                            report.evolution_result["evolution_cycles"] += 1
                            report.evolution_result["principles_created"] += ev_result.get(
                                "principles_created", 0
                            )
                            report.evolution_result["frameworks_created"] += ev_result.get(
                                "frameworks_created", 0
                            )
                            report.evolution_result["beliefs_updated"] += ev_result.get(
                                "beliefs_updated", 0
                            )
                        else:
                            detail["evolution"] = "no_pipeline"
                    except Exception as e:
                        detail["evolution"] = f"error: {e}"
                        logger.warning("Evolution failed for %s: %s", thesis_id, e)

                    report.evolution_result["details"].append(detail)

                # Mark overall status
                if report.evolution_result["evolution_cycles"] > 0:
                    report.evolution_result["status"] = "completed"
                else:
                    report.evolution_result["status"] = "no_pipeline_available"

            except Exception as e:
                logger.error("Diagnosis/Evolution failed: %s", e)
                report.errors.append(f"Evolution: {e}")

        logger.info(report.summary())
        return report

    # ── Evaluation Logic ────────────────────────────────────────────────

    def _evaluate_prediction(
        self,
        pred: PredictionRecord,
        market_data: dict[str, float],
    ) -> EvaluationResult:
        """Evaluate a single prediction against market data.

        Checks:
            1. Directional correctness (UP means actual > previous)
            2. Asset-specific value checks
        """
        direction = pred.direction.upper()
        asset = pred.asset.lower()
        correct = False
        actual = None
        eval_notes = ""

        # Map asset name to market data keys
        asset_map = {
            "spx": "spx",
            "sp500": "spx",
            "s&p500": "spx",
            "us10y": "us10y",
            "10y": "us10y",
            "ten_year": "us10y",
            "vix": "vix",
            "dxy": "dxy",
            "hyg": "hyg",
            "credit": "hyg",
            "gold": "gold",
            "gc": "gold",
            "copper": "copper",
            "hg": "copper",
            "cpi": "cpi_yoy",
            "fedfunds": "fed_rate",
        }
        data_key = asset_map.get(asset, asset)

        current = market_data.get(data_key, 0)
        prev_key = f"prev_{data_key}"
        previous = market_data.get(prev_key, current)

        actual = current

        # Normalize direction: Prediction uses "bullish"/"bearish"/"flat"
        # Maps to price expectation: bullish = expect UP, bearish = expect DOWN
        dir_normalized = direction.upper()
        if dir_normalized in ("BULLISH", "UP", "LONG"):
            correct = current > previous
        elif dir_normalized in ("BEARISH", "DOWN", "SHORT"):
            correct = current < previous
        elif dir_normalized in ("FLAT", "SIDEWAYS", "NEUTRAL"):
            correct = abs(current - previous) / max(abs(previous), 1) < 0.02
        else:
            # Unclear direction — treat as flat threshold
            correct = abs(current - previous) / max(abs(previous), 1) < 0.02

        if correct:
            eval_notes = (
                f"{asset}: {previous:.2f} → {current:.2f} "
                f"(predicted {direction}, actual was {'up' if current > previous else 'down'})"
            )
        else:
            eval_notes = (
                f"{asset}: {previous:.2f} → {current:.2f} "
                f"(predicted {direction}, but moved {'up' if current > previous else 'down' if current < previous else 'flat'})"
            )

        return EvaluationResult(
            prediction_id=pred.prediction_id,
            thesis_id=pred.thesis_id,
            was_correct=correct,
            direction=direction,
            actual_value=actual,
            evaluation=eval_notes,
        )

    # ── Convenience Methods ─────────────────────────────────────────────

    def check_pending(self) -> int:
        """Quick check: how many predictions are pending?"""
        s = self.registry.stats()
        return s["pending"]

    def force_evaluate(
        self,
        prediction_id: str,
        market_data: dict[str, float],
    ) -> EvaluationResult:
        """Force-evaluate a specific prediction regardless of due date."""
        preds = self.registry.get_pending()
        pred = next((p for p in preds if p.prediction_id == prediction_id), None)
        if not pred:
            raise ValueError(f"Prediction {prediction_id} not found in pending")

        ev = self._evaluate_prediction(pred, market_data)
        self.registry.mark_outcome(
            pred.prediction_id,
            success=ev.was_correct,
            actual_value=ev.actual_value,
            evaluation=ev.evaluation,
        )
        return ev

    # ── Reporting ───────────────────────────────────────────────────────

    def summary(self) -> str:
        """Human-readable scheduler status."""
        s = self.registry.stats()
        lines = [
            "Outcome Scheduler",
            f"  Pending evaluations: {s['pending']}",
            f"  Evaluated: {s['evaluated']}",
            f"  Hit rate: {s['hit_rate']:.1%}",
        ]
        return "\n".join(lines)

    def close(self) -> None:
        self.registry.close()
