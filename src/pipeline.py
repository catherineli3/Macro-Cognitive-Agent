from __future__ import annotations

"""MacroResearchPipeline — The single entry point for all macro research runs.

v2.0 Upgrade:
    Full cognitive loop: Observation → Signal → Hypothesis → Reflection →
    Memory → Outcome Tracking → Learning → Confidence Calibration → Narrative.

CLI, API, and future Scheduler all call:
    pipeline = MacroResearchPipeline()
    result = await pipeline.run(goal="macro environment")
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.domain.execution import ExecutionStatus
from src.executor.context import ExecutionContext
from src.executor.executor import AgentExecutor
from src.handlers import (
    HypothesisHandler,
    MemoryHandler,
    ReflectionHandler,
    SignalHandler,
)
from src.handlers.simple import (
    SimpleAnalyzeHandler,
    SimpleGenerateHandler,
    SimpleProcessHandler,
    SimpleRetrieveHandler,
    SimpleValidateHandler,
)
from src.planning.planner import RuleBasedPlanner
from src.schemas.planning import ExecutionPlan
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Pipeline Result ────────────────────────────────────────────────────────


@dataclass
class PipelineResult:
    """The unified output of a pipeline run.

    v2.0: Adds learning_summary, calibrated_confidence, composite_signals, outcome_summary.
    v3.0: Adds prediction_batch, evaluation_report, diagnosis_report, kpi_report.
    """

    status: ExecutionStatus
    narrative: Optional[str] = None
    narrative_obj: Optional["MacroNarrative"] = None  # type: ignore[name-defined]
    narrative_json: Optional[str] = None
    artifacts: dict = field(default_factory=dict)
    error: Optional[str] = None

    # ── v2.0 fields ──────────────────────────────────────────────────────
    learning_summary: Optional[Any] = None        # LearningSummary
    calibrated_confidence: Optional[Any] = None   # CalibratedConfidenceSet
    composite_signals: Optional[Any] = None       # CompositeSignalSnapshot
    outcome_summary: Optional[Any] = None         # OutcomeSummary

    # ── v3.0 fields ──────────────────────────────────────────────────────
    prediction_batch: Optional[Any] = None        # PredictionBatch
    evaluation_report: Optional[Any] = None       # EvaluationReport
    diagnosis_report: Optional[Any] = None        # DiagnosisReport
    kpi_report: Optional[Any] = None              # FourKPIReport

    # ── v3.5 LLM fields ──────────────────────────────────────────────────
    llm_narrative_result: Optional[Any] = None    # LLMNarrativeResult


# ── Pipeline ───────────────────────────────────────────────────────────────


class MacroResearchPipeline:
    """The single entry point for all macro research execution.

    v2.0: Integrates OutcomeEngine, LearningEngine, ConfidenceCalibrator,
    and CompositeSignalGenerator into the execution loop.

    External consumers (CLI, API, Scheduler) always call:
        pipeline = MacroResearchPipeline()
        result = await pipeline.run(goal=...)

    Internal Builder logic is encapsulated — consumers never see
    Planner, Executor, or Handler registration details.

    RC-2: Reuses BeliefMemoryStore across runs to reduce disk I/O.
    v2.0: Reuses v2.0 engines across runs for continuous learning.
    """

    def __init__(self) -> None:
        self._planner = RuleBasedPlanner()
        self._executor = AgentExecutor()
        self._handlers_registered = False
        self._memory_store: Any = None  # RC-2: Reuse store across runs

        # ── v2.0 engines (lazy-init, reused across runs) ─────────────────
        self._outcome_engine: Any = None
        self._learning_engine: Any = None
        self._confidence_calibrator: Any = None
        self._composite_generator: Any = None

        # ── v3.0 engines (lazy-init, reused across runs) ─────────────────
        self._hypothesis_library: Any = None
        self._belief_version_manager: Any = None
        self._prediction_engine: Any = None
        self._v3_evaluation_engine: Any = None
        self._diagnosis_engine: Any = None
        self._learning_log: Any = None
        self._kpi_metrics: Any = None

    def _ensure_handlers(self) -> None:
        """Lazy registration of all handlers (DDR-004: pipeline is the owner)."""
        if self._handlers_registered:
            return

        # Simple mock handlers — keep as fallback for collect/normalize
        self._executor.register(SimpleRetrieveHandler())
        self._executor.register(SimpleProcessHandler())
        self._executor.register(SimpleAnalyzeHandler())
        self._executor.register(SimpleGenerateHandler())
        self._executor.register(SimpleValidateHandler())

        # Real cognitive handlers
        self._executor.register(SignalHandler())
        self._executor.register(HypothesisHandler())
        self._executor.register(ReflectionHandler())
        # MemoryHandler — RC-2: reuses store to avoid redundant file I/O
        from src.memory.store import BeliefMemoryStore

        if self._memory_store is None:
            self._memory_store = BeliefMemoryStore()
        self._executor.register(MemoryHandler(store=self._memory_store))

        # NarrativeHandler — synthesizes full cognitive chain → MacroNarrative
        from src.handlers.narrative_handler import NarrativeHandler

        self._executor.register(NarrativeHandler())

        self._handlers_registered = True

    def _ensure_v2_engines(self) -> None:
        """Lazy initialization of v2.0 engines (reused across runs)."""
        if self._outcome_engine is None:
            from src.outcome.engine import OutcomeEngine
            self._outcome_engine = OutcomeEngine()

        if self._learning_engine is None:
            from src.learning.learning_engine import LearningEngine
            self._learning_engine = LearningEngine()

        if self._confidence_calibrator is None:
            from src.calibration.confidence_calibrator import ConfidenceCalibrator
            self._confidence_calibrator = ConfidenceCalibrator(
                learning_engine=self._learning_engine,
            )

        if self._composite_generator is None:
            from src.signal.composite_signal_generator import CompositeSignalGenerator
            self._composite_generator = CompositeSignalGenerator()

    def _ensure_v3_engines(self) -> None:
        """Lazy initialization of v3.0 engines (reused across runs)."""
        if self._hypothesis_library is None:
            from src.hypothesis_library import HypothesisLibrary
            self._hypothesis_library = HypothesisLibrary()

        if self._belief_version_manager is None:
            from src.belief_versioning import BeliefVersionManager
            self._belief_version_manager = BeliefVersionManager()

        if self._prediction_engine is None:
            from src.prediction import MultiPredictionEngine
            self._prediction_engine = MultiPredictionEngine()

        if self._v3_evaluation_engine is None:
            from src.evaluation import OutcomeEvaluationEngine
            self._v3_evaluation_engine = OutcomeEvaluationEngine()

        if self._diagnosis_engine is None:
            from src.diagnosis import DiagnosisEngine
            self._diagnosis_engine = DiagnosisEngine()

        if self._learning_log is None:
            from src.learning_log import LearningLogRepository
            self._learning_log = LearningLogRepository()

        if self._kpi_metrics is None:
            from src.metrics import KPIMetricsEngine
            self._kpi_metrics = KPIMetricsEngine()

    async def run(
        self,
        goal: str = "macro environment analysis",
        indicators: list[str] | None = None,
        use_llm: bool = False,
    ) -> PipelineResult:
        """Execute a full macro research cycle.

        v1.0 Flow: Plan → Execute (7-step DAG) → Extract Narrative → Render
        v2.0 Flow: Same + Outcome Tracking → Learning → Calibration → Composite Signals
        v3.5: + optional LLM narrative (use_llm=True, reads settings.yaml llm.enabled)

        Args:
            goal: Natural language goal (e.g., "liquidity analysis").
            indicators: Optional list of indicators to focus on.
            use_llm: Enable LLM-powered narrative generation. Defaults to value
                     from settings.yaml (llm.enabled).

        Returns:
            PipelineResult with status, MacroNarrative, learning data, and v2.0 artifacts.
        """
        # Resolve use_llm from settings if not explicitly set
        if not use_llm:
            try:
                from src.shared.config import get_settings
                settings = get_settings()
                use_llm = bool(settings.get("llm", {}).get("enabled", False))
            except Exception:
                use_llm = False
        try:
            self._ensure_handlers()
            self._ensure_v2_engines()

            # 1. Plan — decompose goal into DAG
            plan: ExecutionPlan = await self._planner.create_plan(goal)

            logger.info(
                "pipeline_run_starting_v2",
                extra={"plan_id": plan.plan_id, "goal": goal, "task_count": plan.task_count},
            )

            # 2. Execute the DAG
            exec_result = await self._executor.execute(plan)

            # 3. Extract v1.0 artifacts
            narrative_obj = exec_result.artifacts.get("narrative")
            signal_snapshot = exec_result.artifacts.get("signal_snapshot")
            hypothesis_set = exec_result.artifacts.get("hypothesis_set")
            reflection_set = exec_result.artifacts.get("reflection_set")

            # ═══════════════════════════════════════════════════════════════
            # v2.0 POST-EXECUTION: Outcome → Learning → Calibration → Composite
            # ═══════════════════════════════════════════════════════════════

            # 4. Outcome Tracking — create pending outcomes from beliefs
            outcome_summary = None
            try:
                beliefs = self._memory_store.get_all() if self._memory_store else []
                new_beliefs = [b for b in beliefs if b.run_id == plan.plan_id]
                for belief in new_beliefs:
                    outcome = self._outcome_engine.create_outcome(
                        belief=belief,
                        run_id=plan.plan_id,
                        observation_window_days=7,
                    )
                    self._outcome_engine.persist(outcome, plan.plan_id)

                # Evaluate any previously pending outcomes (using available beliefs as proxy)
                # In production, this would pull real market data
                pending = self._outcome_engine._tracker.get_pending()
                if pending:
                    # Use belief direction trends as rough outcome evaluation
                    observed_map: dict[str, Any] = {}
                    for dim in ["liquidity", "credit", "growth", "risk_appetite", "inflation"]:
                        dim_beliefs = [
                            b for b in beliefs
                            if b.dimension.lower() == dim and b.confidence > 0.5
                        ]
                        if dim_beliefs:
                            latest = max(dim_beliefs, key=lambda b: b.timestamp)
                            from src.schemas.outcome import OutcomeDirection
                            map_dir = {
                                "bullish": OutcomeDirection.UP,
                                "bearish": OutcomeDirection.DOWN,
                            }
                            observed_map[dim] = map_dir.get(
                                latest.direction.value, OutcomeDirection.FLAT,
                            )
                    self._outcome_engine.evaluate_pending(observed_map)

                outcome_summary = self._outcome_engine.summary()
                logger.info(
                    "outcome_tracking_complete",
                    extra={"total": outcome_summary.total_predictions, "hit_rate": outcome_summary.hit_rate},
                )
            except Exception as e:
                logger.warning("outcome_tracking_skipped: %s", str(e))

            # 5. Learning — update belief weights from outcomes
            learning_summary = None
            try:
                if outcome_summary and outcome_summary.total_predictions > 0:
                    all_records = self._outcome_engine._tracker.get_all()
                    learning_summary = self._learning_engine.learn(
                        outcome_summary=outcome_summary,
                        outcome_records=all_records,
                    )
                    logger.info(
                        "learning_complete",
                        extra={
                            "best_dim": learning_summary.best_dimension,
                            "patterns": len(learning_summary.learned_patterns),
                        },
                    )
            except Exception as e:
                logger.warning("learning_skipped: %s", str(e))

            # 6. Confidence Calibration — calibrate hypothesis confidences
            calibrated_set = None
            try:
                if hypothesis_set and reflection_set and self._learning_engine:
                    # Ensure calibrator has learning engine
                    self._confidence_calibrator.set_learning_engine(self._learning_engine)
                    calibrated_set = self._confidence_calibrator.calibrate_set(
                        hypotheses=hypothesis_set,
                        reflections=reflection_set,
                        run_id=plan.plan_id,
                    )
                    logger.info(
                        "calibration_complete",
                        extra={"avg_raw": calibrated_set.average_raw, "avg_cal": calibrated_set.average_calibrated},
                    )
            except Exception as e:
                logger.warning("calibration_skipped: %s", str(e))

            # 7. Composite Signal Generation — cross-indicator reasoning
            composite_snapshot = None
            try:
                if signal_snapshot:
                    composite_snapshot = self._composite_generator.generate_snapshot(signal_snapshot)
                    logger.info(
                        "composite_signals_generated",
                        extra={
                            "composites": len(composite_snapshot.composite_signals),
                            "themes": len(composite_snapshot.macro_themes),
                            "dominant": composite_snapshot.dominant_theme,
                        },
                    )
            except Exception as e:
                logger.warning("composite_signals_skipped: %s", str(e))

            # 8. Render to Markdown / JSON
            rendered: Optional[str] = None
            rendered_json: Optional[str] = None
            if narrative_obj is not None:
                from src.renderer.markdown import MarkdownRenderer
                from src.renderer.json_renderer import JsonRenderer

                md_renderer = MarkdownRenderer()
                json_renderer = JsonRenderer()
                rendered = md_renderer.render(narrative_obj)
                rendered_json = json_renderer.render(narrative_obj)

            # ── v3.5: LLM Narrative Generation ──────────────────────────
            llm_narrative = None
            if use_llm:
                try:
                    from src.llm.narrative import LLMNarrativeEngine
                    llm_engine = LLMNarrativeEngine()
                    llm_narrative = llm_engine.generate(narrative=narrative_obj)
                    logger.info(
                        "LLM narrative generated, degraded=%s",
                        llm_narrative.degraded,
                    )
                except Exception as exc:
                    logger.warning("LLM narrative engine failed: %s", exc)
                    llm_narrative = None

            result = PipelineResult(
                status=exec_result.status,
                narrative=rendered,
                narrative_obj=narrative_obj,
                narrative_json=rendered_json,
                artifacts=exec_result.artifacts,
                # v2.0
                learning_summary=learning_summary,
                calibrated_confidence=calibrated_set,
                composite_signals=composite_snapshot,
                outcome_summary=outcome_summary,
                # v3.5 LLM
                llm_narrative_result=llm_narrative,
            )

            logger.info(
                "pipeline_run_completed_v2",
                extra={
                    "plan_id": plan.plan_id,
                    "status": exec_result.status.value,
                    "has_narrative": narrative_obj is not None,
                    "total_ms": exec_result.total_time_ms,
                    "outcomes_tracked": outcome_summary.total_predictions if outcome_summary else 0,
                },
            )

            return result

        except Exception as e:
            logger.error("pipeline_run_failed error=%s", str(e))
            return PipelineResult(
                status=ExecutionStatus.FAILED,
                error=str(e),
            )

    async def run_once(self, goal: str) -> PipelineResult:
        """Alias for run() — single execution."""
        return await self.run(goal=goal)

    async def analyze(self, goal: str) -> PipelineResult:
        """Simplified analysis entry point."""
        return await self.run(goal=goal)

    # ═══════════════════════════════════════════════════════════════════════════
    # V3: Full Adaptive Loop
    # ═══════════════════════════════════════════════════════════════════════════

    async def run_with_prediction(
        self,
        goal: str = "macro environment analysis",
        indicators: list[str] | None = None,
        actual_data: dict[str, tuple[float, float]] | None = None,
    ) -> PipelineResult:
        """Execute a full V3 research cycle with prediction and evaluation.

        V3 Flow: Plan → Execute (V2) → Hypothesis Library query →
            Multi-Prediction → Outcome Evaluation → Diagnosis →
            Learning Log → KPI computation.

        Args:
            goal: Natural language goal.
            indicators: Optional indicators to focus on.
            actual_data: {indicator: (current_value, previous_value)} for evaluation.
                         If None, predictions are generated but not evaluated.

        Returns:
            PipelineResult with V3 artifacts (prediction_batch, evaluation_report,
            diagnosis_report, kpi_report).
        """
        try:
            self._ensure_handlers()
            self._ensure_v2_engines()
            self._ensure_v3_engines()

            # 1. Run standard V2 pipeline first
            plan: ExecutionPlan = await self._planner.create_plan(goal)
            logger.info("v3_pipeline_start plan_id=%s goal=%s", plan.plan_id, goal)

            exec_result = await self._executor.execute(plan)

            # Extract V2 artifacts
            hypothesis_set = exec_result.artifacts.get("hypothesis_set")
            narrative_obj = exec_result.artifacts.get("narrative")
            signal_snapshot = exec_result.artifacts.get("signal_snapshot")
            reflection_set = exec_result.artifacts.get("reflection_set")

            # ═══════════════════════════════════════════════════════════════
            # V3 STEP 1: Register hypotheses in Library (if not already)
            # ═══════════════════════════════════════════════════════════════
            if hypothesis_set:
                for h in hypothesis_set.hypotheses:
                    existing = await self._hypothesis_library.get(h.hypothesis_id)
                    if existing is None:
                        await self._hypothesis_library.register(
                            hypothesis_id=h.hypothesis_id,
                            dimension=h.dimension,
                            statement=h.statement,
                            direction=h.direction.value,
                        )

            # ═══════════════════════════════════════════════════════════════
            # V3 STEP 2: Get prior beliefs from Library
            # ═══════════════════════════════════════════════════════════════
            library_entries = await self._hypothesis_library.get_all_active()

            # ═══════════════════════════════════════════════════════════════
            # V3 STEP 3: Multi-Prediction Generation
            # ═══════════════════════════════════════════════════════════════
            prediction_batch = None
            evaluation_report = None
            diagnosis_report = None
            kpi_report = None

            if hypothesis_set and hypothesis_set.count > 0:
                prediction_batch = await self._prediction_engine.generate_predictions(
                    hypothesis_set=hypothesis_set,
                    run_id=plan.plan_id,
                    hypothesis_library_entries=library_entries,
                )
                logger.info(
                    "v3_predictions_generated total=%d hypotheses=%d channels=%d",
                    prediction_batch.total_predictions,
                    prediction_batch.hypothesis_count,
                    prediction_batch.channel_count,
                )

                # ═══════════════════════════════════════════════════════════
                # V3 STEP 4: Outcome Evaluation (if actual_data provided)
                # ═══════════════════════════════════════════════════════════
                if actual_data:
                    evaluation_report = await self._v3_evaluation_engine.evaluate_batch(
                        batch=prediction_batch,
                        actual_data=actual_data,
                    )
                    logger.info(
                        "v3_evaluation_complete da=%.1f%% channels=%d",
                        evaluation_report.directional_accuracy * 100,
                        len(evaluation_report.accuracy_by_channel),
                    )

                    # ═══════════════════════════════════════════════════════
                    # V3 STEP 5: Diagnosis (Passive in 3.0)
                    # ═══════════════════════════════════════════════════════
                    diagnosis_report = await self._diagnosis_engine.diagnose_batch(
                        evaluation_report=evaluation_report,
                    )

                    # ═══════════════════════════════════════════════════════
                    # V3 STEP 6: Learning Log (record all chains)
                    # ═══════════════════════════════════════════════════════
                    from src.schemas.learning_log import LearningLogEntry
                    log_entries: list[LearningLogEntry] = []
                    for outcome, classification in zip(
                        evaluation_report.outcomes,
                        diagnosis_report.classifications,
                    ):
                        # Find the matching prediction
                        pred = next(
                            (p for p in prediction_batch.predictions
                             if p.prediction_id == outcome.prediction_id),
                            None,
                        )
                        if pred:
                            entry = LearningLogEntry(
                                run_id=plan.plan_id,
                                prediction_id=pred.prediction_id,
                                hypothesis_id=pred.source_hypothesis_id,
                                dimension=pred.dimension,
                                transmission_channel=pred.transmission_channel,
                                prediction_tier=pred.prediction_tier.value,
                                predicted_direction=pred.direction,
                                predicted_confidence=pred.confidence,
                                horizon=pred.horizon,
                                was_correct=outcome.correct,
                                actual_direction=outcome.actual_direction,
                                error_magnitude=outcome.error_magnitude,
                                error_category=classification.error_category.value if classification.error_category else None,
                                diagnosis_confidence=classification.diagnosis_confidence,
                                diagnosis_rationale=classification.diagnosis_rationale,
                                predicted_at=pred.created_at,
                                evaluated_at=outcome.evaluated_at,
                            )
                            log_entries.append(entry)

                    if log_entries:
                        await self._learning_log.append_batch(log_entries)
                        logger.info("v3_learning_logged entries=%d", len(log_entries))

                    # ═══════════════════════════════════════════════════════
                    # V3 STEP 7: KPI Computation
                    # ═══════════════════════════════════════════════════════
                    lib_avg = await self._hypothesis_library.get_library_avg_score()

                    kpi1 = await self._kpi_metrics.compute_kpi1(
                        library_avg_score=lib_avg,
                        active_hypotheses=len(library_entries),
                        total_hypotheses=len(await self._hypothesis_library.get_all_active()),
                    )
                    kpi2 = await self._kpi_metrics.compute_kpi2(
                        directional_accuracy=evaluation_report.directional_accuracy,
                        mae=evaluation_report.mean_absolute_error,
                        rmse=evaluation_report.rmse,
                        total_predictions=evaluation_report.total_outcomes,
                        correct_predictions=evaluation_report.total_correct,
                        primary_accuracy=evaluation_report.accuracy_by_tier.get("primary", 0.5),
                        secondary_accuracy=evaluation_report.accuracy_by_tier.get("secondary", 0.5),
                    )
                    kpi3 = await self._kpi_metrics.compute_kpi3(
                        ece=0.25,  # Placeholder until empirical calibration
                        brier_score=evaluation_report.brier_score,
                    )
                    log_count = await self._learning_log.count()
                    kpi4 = await self._kpi_metrics.compute_kpi4(
                        total_errors_classified=log_count,
                    )

                    from src.schemas.kpi import WindowPeriod
                    kpi_report = await self._kpi_metrics.compute_full_report(
                        window=WindowPeriod.D30,
                        kpi1=kpi1, kpi2=kpi2, kpi3=kpi3, kpi4=kpi4,
                    )

                    # Set baseline on first KPI report
                    if self._kpi_metrics._baseline is None:
                        await self._kpi_metrics.set_baseline(kpi_report)

                    logger.info(
                        "v3_kpi_computed overall=%.3f kpi1=%.3f kpi2=%.3f kpi3=%.3f kpi4=%.3f",
                        kpi_report.overall_score,
                        kpi1.composite_score, kpi2.composite_score,
                        kpi3.composite_score, kpi4.composite_score,
                    )

            # ═══════════════════════════════════════════════════════════════
            # Assemble result
            # ═══════════════════════════════════════════════════════════════
            result = PipelineResult(
                status=exec_result.status,
                narrative_obj=narrative_obj,
                artifacts=exec_result.artifacts,
                prediction_batch=prediction_batch,
                evaluation_report=evaluation_report,
                diagnosis_report=diagnosis_report,
                kpi_report=kpi_report,
            )

            logger.info(
                "v3_pipeline_complete plan_id=%s has_prediction=%s has_eval=%s has_diag=%s has_kpi=%s",
                plan.plan_id,
                prediction_batch is not None,
                evaluation_report is not None,
                diagnosis_report is not None,
                kpi_report is not None,
            )

            return result

        except Exception as e:
            logger.error("v3_pipeline_failed error=%s", str(e))
            return PipelineResult(
                status=ExecutionStatus.FAILED,
                error=str(e),
            )
