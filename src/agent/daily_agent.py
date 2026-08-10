"""DailyMacroAgent — V10 production daily research loop.

Orchestrates the full pipeline: Regime → Reflexivity → CapitalFlow →
ExpertDebate → Learning → Curiosity → ReasoningPipeline → ResearchMemo.

V10 Change: Step 7 uses ReasoningPipeline (8 steps: 6 deterministic + LLM synthesis + quality review)
instead of the old single-pass LLM call.
"""

from __future__ import annotations
import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Optional
from src.agent.schemas import DailyRunReport


class DailyMacroAgent:
    """Complete V3.5 daily macro research agent."""

    def __init__(self, use_llm: bool = False, verbosity: int = 1):
        self.use_llm = use_llm
        self.verbosity = verbosity
        self._run_history: list[DailyRunReport] = []
        self._belief_state: list[Any] = []
        self._model_weights: dict[str, float] = {}

        # Lazy-init engines
        self._engines: dict[str, Any] = {}

    def _get_engine(self, name: str) -> Any:
        if name not in self._engines:
            if name == "regime_classifier":
                from src.regime import RegimeClassifier
                self._engines[name] = RegimeClassifier()
            elif name == "regime_transition":
                from src.regime import RegimeTransitionDetector
                self._engines[name] = RegimeTransitionDetector()
            elif name == "historical_similarity":
                from src.regime import HistoricalSimilarity
                self._engines[name] = HistoricalSimilarity()
            elif name == "capital_rotation":
                from src.capital_flow import CapitalRotation
                self._engines[name] = CapitalRotation()
            elif name == "reflexivity":
                from src.research.reflexivity import ReflexivityCycleDetector
                self._engines[name] = ReflexivityCycleDetector()
            elif name == "outcome_collector":
                from src.learning import OutcomeCollector
                self._engines[name] = OutcomeCollector()
            elif name == "prediction_scorer":
                from src.learning import PredictionScorer
                self._engines[name] = PredictionScorer()
            elif name == "belief_calibration":
                from src.learning import BeliefCalibration
                self._engines[name] = BeliefCalibration()
            elif name == "weight_optimizer":
                from src.learning import ModelWeightOptimizer
                self._engines[name] = ModelWeightOptimizer()
            elif name == "curiosity":
                from src.curiosity import CuriosityEngine
                self._engines[name] = CuriosityEngine()
            elif name == "reasoning":
                from src.research.llm_brain import ResearchReasoningAgent
                self._engines[name] = ResearchReasoningAgent(reasoning_mode="rule")
            elif name == "reasoning_pipeline":
                from src.research.reasoning.reasoning_pipeline import ReasoningPipeline
                self._engines[name] = ReasoningPipeline()
            elif name == "expert_debate":
                from src.research.expert_debate import ExpertDebate
                self._engines[name] = ExpertDebate(debate_mode="rule")
        return self._engines[name]

    def run_daily(
        self,
        date: Optional[str] = None,
        market_data: Optional[dict] = None,
        mental_models: Optional[dict] = None,
        beliefs: Optional[list[Any]] = None,
        narratives: Optional[list[Any]] = None,
    ) -> DailyRunReport:
        """Execute the complete 10-step daily research pipeline."""
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        run_id = hashlib.md5(f"daily_{date}".encode()).hexdigest()[:12]
        t0 = time.time()
        market = market_data or {}
        mental = mental_models or {}
        belief_list = beliefs or self._belief_state or []

        report = DailyRunReport(run_id=run_id, date=date)
        executed, failed, errors = [], [], []

        def log(msg, level=1):
            if self.verbosity >= level:
                print(f"  [{date}] {msg}")

        # Step 1: Regime Classification
        log("Step 1/9: Classifying macro regime...")
        try:
            rc = self._get_engine("regime_classifier")
            regime = rc.classify(mental_models=mental, market_data=market)
            trans = self._get_engine("regime_transition").estimate_transition(regime, market_data=market)
            analogs = self._get_engine("historical_similarity").find_analogs(regime, top_n=3)
            report.regime_classification = regime
            report.regime_transition = trans
            report.historical_analogs = analogs
            executed.append("regime")
            top_a = analogs[0].period_name if analogs else "none"
            log(f"  Regime: {regime.regime_label} (conf={regime.confidence:.0%}), top analog: {top_a}")
        except Exception as e:
            failed.append("regime"); errors.append(f"Regime: {e}")

        # Step 2: Reflexivity Detection
        log("Step 2/9: Detecting reflexivity...")
        try:
            dom_nar = ""
            if narratives and isinstance(narratives, list) and len(narratives) > 0:
                dom_nar = getattr(narratives[0], "title", "") or str(narratives[0])
            refl = self._get_engine("reflexivity").detect(
                market_data=market,
                dominant_narrative=dom_nar,
                narrative_objects=narratives,
            )
            report.reflexivity_report = refl
            executed.append("reflexivity")
            cycles_n = len(getattr(refl, "active_cycles", [])) if refl else 0
            log(f"  Reflexivity: {cycles_n} active cycle(s)")
        except Exception as e:
            failed.append("reflexivity"); errors.append(f"Reflexivity: {e}")

        # Step 3: Capital Flow
        log("Step 3/9: Analyzing capital flows...")
        try:
            refl_data = {"active_cycles": getattr(report.reflexivity_report, "active_cycles", [])} if report.reflexivity_report else {}
            flow = self._get_engine("capital_rotation").detect_regime(date=date, reflexivity_data=refl_data)
            report.capital_flow_report = flow
            executed.append("capital_flow")
            log(f"  Capital Flow: {flow.regime.regime_label}, net {flow.regime.net_flow_bn:+.1f}B")
        except Exception as e:
            failed.append("capital_flow"); errors.append(f"CapitalFlow: {e}")

        # Step 4: Expert Debate
        log("Step 4/9: Running expert debate...")
        try:
            regime_label = getattr(report.regime_classification, "regime_label", "") if report.regime_classification else ""
            dom_narrative = ""
            if narratives:
                for n in (narratives if isinstance(narratives, list) else []):
                    if hasattr(n, "title"):
                        dom_narrative = n.title
                        break
            debate = self._get_engine("expert_debate").debate(
                market_data=market,
                regime_label=regime_label,
                dominant_narrative=dom_narrative,
            )
            report.expert_debate_report = debate
            executed.append("expert_debate")
            cs = getattr(debate, "consensus_score", 0)
            log(f"  Expert Debate: consensus={cs:.2f}")
        except Exception as e:
            failed.append("expert_debate"); errors.append(f"ExpertDebate: {e}")

        # Step 5: Learning Loop
        log("Step 5/9: Learning — resolving predictions...")
        try:
            outcomes = self._get_engine("outcome_collector").collect_outcomes(beliefs=belief_list, market_data=market)
            scored = self._get_engine("prediction_scorer").score_batch(outcomes)
            metrics = self._get_engine("prediction_scorer").compute_batch_metrics(scored)
            calibrations = self._get_engine("belief_calibration").calibrate_all(belief_list, scored)
            cal_sum = self._get_engine("belief_calibration").get_calibration_summary(calibrations)
            from src.learning import LearningReport
            learning = LearningReport(
                report_id=f"lr_{date}", date=date,
                predictions_resolved=len(outcomes),
                predictions_pending=self._get_engine("outcome_collector").get_pending_count(belief_list),
                overall_accuracy=metrics.get("accuracy", 0),
                overall_brier_score=metrics.get("avg_brier", 0),
                beliefs_calibrated=cal_sum.get("calibratable_beliefs", 0),
                overconfident_beliefs=cal_sum.get("overconfident", 0),
                underconfident_beliefs=cal_sum.get("underconfident", 0),
            )
            report.learning_report = learning
            executed.append("learning")
            log(f"  Learning: {len(outcomes)} resolved, accuracy {metrics.get('accuracy', 0):.0%}")
        except Exception as e:
            failed.append("learning"); errors.append(f"Learning: {e}")

        # Step 6: Curiosity
        log("Step 6/9: Generating research questions...")
        try:
            cur = self._get_engine("curiosity").generate_questions(beliefs=belief_list, mental_models=mental, learning_report=report.learning_report, date=date)
            report.curiosity_report = cur
            executed.append("curiosity")
            log(f"  Curiosity: {len(cur.priority_questions)} priority questions")
        except Exception as e:
            failed.append("curiosity"); errors.append(f"Curiosity: {e}")

        # Step 7: Research Memo via V10 ReasoningPipeline
        #     Observation → [6 deterministic steps] → LLM Synthesis → Quality Review
        log("Step 7/9: Running V10 ReasoningPipeline (8-step: evidence→hypo→counter→reflexivity→history→portfolio→LLM→quality)...")
        try:
            regime_label = getattr(report.regime_classification, "regime_label", "unknown") if report.regime_classification else "unknown"
            regime_conf = getattr(report.regime_classification, "confidence", 0.5) if report.regime_classification else 0.5
            dims = {}
            if report.regime_classification:
                for d in ("growth_phase", "inflation_regime", "monetary_stance"):
                    dims[d] = getattr(report.regime_classification, d, "")

            # Build regime_result dict for the pipeline
            regime_result = {
                "regime_label": regime_label,
                "regime_type": regime_label,
                "confidence": regime_conf,
                "dimensions": dims,
            }

            # Build narrative list
            narrative_list = []
            if narratives:
                narrative_list = list(narratives) if isinstance(narratives, (list, tuple)) else [narratives]

            # Capital flow result
            capital_flow_result = {}
            if report.capital_flow_report:
                cf = report.capital_flow_report
                capital_flow_result = {
                    "regime_label": getattr(cf.regime, "regime_label", "") if hasattr(cf, "regime") else "",
                    "net_flow_bn": getattr(cf.regime, "net_flow_bn", 0) if hasattr(cf, "regime") else 0,
                    "reflexivity_warning": getattr(cf, "reflexivity_warning", False),
                }

            pipeline = self._get_engine("reasoning_pipeline")
            pipe_result = pipeline.execute(
                market_data=market,
                narratives=narrative_list,
                beliefs=belief_list,
                regime_result=regime_result,
                capital_flow_result=capital_flow_result,
                news_events=[],
                date_str=date,
                old_beliefs=self._belief_state if self._belief_state else None,
            )

            # Store pipeline result on report
            report.research_memo = pipe_result.memo_text or pipe_result.step_llm_synthesis.summary
            report._pipeline_result = pipe_result

            executed.append("research_memo")
            log(f"  V10 Pipeline: {pipe_result.total_elapsed_ms:.0f}ms, "
                f"quality={pipe_result.memo_quality_score:.0f}, "
                f"llm_calls={pipe_result.llm_call_count}, "
                f"errs={len(pipe_result.errors)}")
        except Exception as e:
            failed.append("research_memo"); errors.append(f"ResearchMemo: {e}")
            log(f"  Research Memo FAILED: {e}, falling back to legacy reasoner")
            # Fallback to old ResearchReasoningAgent
            try:
                regime_label = getattr(report.regime_classification, "regime_label", "unknown") if report.regime_classification else "unknown"
                regime_conf = getattr(report.regime_classification, "confidence", 0.5) if report.regime_classification else 0.5
                dims = {}
                if report.regime_classification:
                    for d in ("growth_phase", "inflation_regime", "monetary_stance"):
                        dims[d] = getattr(report.regime_classification, d, "")
                b_titles = [getattr(b, "title", "") for b in belief_list] if belief_list else []

                from src.research.llm_brain.research_reasoning_agent import ReasoningInput
                ri = ReasoningInput(
                    regime_label=regime_label,
                    regime_confidence=regime_conf,
                    regime_dimensions=dims,
                    market_indicators=market,
                    case_id=f"daily_{date}",
                    core_beliefs=b_titles[:5],
                )
                memo = self._get_engine("reasoning").reason(ri)
                report.research_memo = memo
                executed.append("research_memo")
            except Exception as e2:
                log(f"  Legacy reasoner also FAILED: {e2}")

        # Step 8: Compose summary
        sentiment, conviction, headline, risks, opps = self._compose_summary(report, market)
        report.summary_headline = headline
        report.key_risks = risks
        report.key_opportunities = opps
        report.sentiment = sentiment
        report.conviction = conviction
        report.pipeline_duration_seconds = round(time.time() - t0, 1)
        report.modules_executed = executed
        report.modules_failed = failed
        report.errors = errors

        self._run_history.append(report)
        return report

    def _compose_summary(self, report: DailyRunReport, market: dict) -> tuple:
        """Synthesize cross-module insights into summary."""
        regime = report.regime_classification
        flow = report.capital_flow_report
        refl = report.reflexivity_report

        # Sentiment from multiple sources
        risk_signals = 0
        if regime:
            if regime.volatility_regime in ("high_vol", "crisis"):
                risk_signals += 3
            if regime.credit_cycle in ("contraction",):
                risk_signals += 2
            if regime.monetary_stance == "tightening":
                risk_signals += 1
            if regime.transition_probability > 0.5:
                risk_signals += 1

        if flow:
            if flow.regime.regime_label.startswith("risk_off"):
                risk_signals += 2
            if flow.reflexivity_warning:
                risk_signals += 2

        if risk_signals <= 2:
            sentiment, conviction = "constructive", 0.65
            headline = f"Macro regime: {getattr(regime, 'regime_label', '')} — constructive outlook with manageable risks"
        elif risk_signals <= 5:
            sentiment, conviction = "cautious", 0.50
            headline = f"Macro regime: {getattr(regime, 'regime_label', '')} — caution warranted, multiple stress signals"
        else:
            sentiment, conviction = "defensive", 0.70
            headline = f"Macro regime: {getattr(regime, 'regime_label', '')} — defensive posture, elevated risk environment"

        # Risks
        risks = []
        if regime:
            for w in regime.early_warning_signals[:3]:
                risks.append(w)
        if flow and flow.reflexivity_warning:
            risks.append("Active reflexivity feedback loop detected")

        # Opportunities
        opps = []
        if regime and regime.growth_phase == "accelerating":
            opps.append("Growth acceleration supports risk assets")
        if flow and flow.regime.net_flow_bn > 2:
            opps.append("Capital inflows providing liquidity support")

        return sentiment, conviction, headline, risks[:5], opps[:3]

    def get_run_history(self) -> list[dict]:
        return [r.to_dict() for r in self._run_history]

    def get_last_run(self) -> Optional[DailyRunReport]:
        return self._run_history[-1] if self._run_history else None

    # ═══════════════════════════════════════════════════════════════════
    # V10 Sprint 4: Continuous Learning After Benchmark
    # ═══════════════════════════════════════════════════════════════════

    def run_benchmark_learning(
        self,
        predictions: list,
        outcomes: list,
    ) -> Optional[Any]:
        """After a benchmark cycle, run the continuous learning loop.

        Thread: Prediction → Outcome → Root Cause → Belief/Prompt/Reasoning Update.

        Args:
            predictions: List of PredictionRecord objects.
            outcomes: List of OutcomeRecord objects.

        Returns:
            LearningReport with diagnosis, belief/prompt/reasoning diffs.
        """
        if not predictions:
            return None

        # Get pipeline result from the last run for domain information
        last_run = self.get_last_run()
        pipeline_result = getattr(last_run, "_pipeline_result", None) if last_run else None

        # Use the pipeline's learning cycle
        if pipeline_result and hasattr(pipeline_result, "_pipeline_result"):
            from src.research.reasoning.reasoning_pipeline import ReasoningPipeline
            # If the agent has the pipeline engine, use it
            pass

        # Preferred path: use the standalone ContinuousLearningLoop
        from src.research.reasoning.continuous_learning import ContinuousLearningLoop

        used_domains = []
        if pipeline_result and hasattr(pipeline_result, "selected_domains"):
            used_domains = pipeline_result.selected_domains
        if not used_domains:
            used_domains = ["Growth"]

        loop = ContinuousLearningLoop()
        report = loop.run_cycle(
            predictions=predictions,
            outcomes=outcomes,
            beliefs=self._belief_state,
            used_domains=used_domains,
        )

        # Store learning report in run history
        if last_run:
            last_run._learning_report = report

        return report

    def get_learning_history(self) -> list[dict]:
        """Get all learning reports from history."""
        reports = []
        for run in self._run_history:
            lr = getattr(run, "_learning_report", None)
            if lr:
                reports.append(lr.to_dict())
        return reports

    def get_improvement_trend(self) -> dict:
        """Get accuracy improvement trend across all learning cycles."""
        from src.research.reasoning.continuous_learning import ContinuousLearningLoop

        loop = ContinuousLearningLoop()
        # Replay all stored learning reports
        for run in self._run_history:
            lr = getattr(run, "_learning_report", None)
            if lr:
                loop._cycle_history.append(lr)

        return loop.get_improvement_trend()
