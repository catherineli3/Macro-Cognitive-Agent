"""V10 Sprint 4 — Continuous Learning Loop.

After every benchmark cycle, the agent must evolve:
    Prediction → Outcome → Root Cause → Belief Update → Prompt Update 
    → Reasoning Update → Memory Update → Next Benchmark

Key principle: Never simply decrease confidence. Always diagnose WHY.

Root Cause Diagnosis:
    Wrong Data | Wrong Narrative | Wrong Regime | Wrong Timing |
    Wrong Causality | Wrong Probability | Black Swan |
    Overconfidence | Underconfidence | Missing Evidence

Output:
    LearningReport, PromptDiff, BeliefDiff, ReasoningDiff, PerformanceDiff
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Prediction Record
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class PredictionRecord:
    """A prediction made by the agent, to be evaluated later."""
    prediction_id: str = ""
    timestamp: str = ""
    regime_label: str = ""
    prediction_statement: str = ""
    predicted_direction: str = ""  # bullish/bearish/neutral
    confidence: float = 0.0  # 0-1
    time_horizon: str = ""  # 1w/1m/3m/6m
    asset_class: str = ""
    specific_asset: str = ""
    catalyst: str = ""


@dataclass
class OutcomeRecord:
    """The actual outcome for a prediction."""
    prediction_id: str = ""
    outcome_timestamp: str = ""
    actual_direction: str = ""  # bullish/bearish/neutral
    actual_change_pct: float = 0.0
    was_correct: bool = False
    error_magnitude: float = 0.0  # |predicted - actual|
    notes: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# Root Cause Diagnosis
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class RootCauseDiagnosis:
    """Automated root cause analysis of prediction errors."""
    prediction_id: str = ""
    primary_cause: str = ""  # One of the 10 categories
    secondary_causes: list[str] = field(default_factory=list)
    confidence_adjustment: float = 0.0  # How much to adjust confidence
    reasoning_flaw: str = ""
    evidence_for_diagnosis: list[str] = field(default_factory=list)
    correction_strategy: str = ""


class RootCauseDiagnostician:
    """Analyzes why predictions were wrong — never just decreases confidence.

    Diagnoses 10 root cause categories:
        1. Wrong Data — used incorrect or stale data
        2. Wrong Narrative — interpreted data through wrong narrative lens
        3. Wrong Regime — misclassified the macro regime
        4. Wrong Timing — correct direction, wrong timeframe
        5. Wrong Causality — misidentified the causal mechanism
        6. Wrong Probability — over/underestimated tail risk
        7. Black Swan — genuinely unpredictable external shock
        8. Overconfidence — confidence too high relative to uncertainty
        9. Underconfidence — confidence too low (missed a clear signal)
        10. Missing Evidence — failed to incorporate key data
    """

    CAUSE_CATEGORIES = [
        "Wrong Data",
        "Wrong Narrative",
        "Wrong Regime",
        "Wrong Timing",
        "Wrong Causality",
        "Wrong Probability",
        "Black Swan",
        "Overconfidence",
        "Underconfidence",
        "Missing Evidence",
    ]

    def diagnose(
        self,
        prediction: PredictionRecord,
        outcome: OutcomeRecord,
        regime_at_prediction: Optional[dict] = None,
        regime_at_outcome: Optional[dict] = None,
        evidence_used: Optional[list] = None,
    ) -> RootCauseDiagnosis:
        """Diagnose why a prediction was wrong.

        Args:
            prediction: The original prediction.
            outcome: The actual outcome.
            regime_at_prediction: Regime when prediction was made.
            regime_at_outcome: Regime when outcome was evaluated.
            evidence_used: What evidence was available and used.

        Returns:
            RootCauseDiagnosis with primary cause and correction strategy.
        """
        if outcome.was_correct:
            return RootCauseDiagnosis(
                prediction_id=prediction.prediction_id,
                primary_cause="Correct Prediction",
                reasoning_flaw="None — prediction was accurate",
                correction_strategy="Maintain current reasoning approach; minor calibration only",
            )

        causes = []

        # 1. Check Timing — was direction correct but wrong timeframe?
        timing_wrong = self._check_timing(prediction, outcome)
        if timing_wrong:
            causes.append(("Wrong Timing", timing_wrong))

        # 2. Check Regime — did regime change between prediction and outcome?
        regime_wrong = self._check_regime_change(
            regime_at_prediction, regime_at_outcome
        )
        if regime_wrong:
            causes.append(("Wrong Regime", regime_wrong))

        # 3. Check for Black Swan
        if abs(outcome.actual_change_pct) > 5.0:
            causes.append(
                ("Black Swan", "Outcome magnitude >5% suggests external shock")
            )

        # 4. Check Confidence calibration
        conf_diag = self._check_confidence(prediction, outcome)
        if conf_diag:
            causes.append(conf_diag)

        # 5. Check Causality
        if prediction.predicted_direction != outcome.actual_direction:
            causes.append(
                ("Wrong Causality",
                 f"Predicted {prediction.predicted_direction} but "
                 f"outcome was {outcome.actual_direction} — "
                 f"causal mechanism was incorrectly identified")
            )

        # 6. Check if missing key evidence
        if evidence_used and len(evidence_used) < 3:
            causes.append(
                ("Missing Evidence",
                 f"Only {len(evidence_used)} evidence items used — "
                 f"likely insufficient for reliable prediction")
            )

        # 7. Check Narrative
        if not causes:
            causes.append(
                ("Wrong Narrative",
                 "No specific technical failure detected — "
                 "likely the overall narrative lens was wrong")
            )

        # Sort causes: most impactful first
        cause_priority = {c: i for i, c in enumerate(self.CAUSE_CATEGORIES)}
        causes.sort(key=lambda x: cause_priority.get(x[0], 99))

        primary = causes[0]
        secondary = [c[0] for c in causes[1:4]]

        # Generate correction strategy
        strategy = self._generate_strategy(primary[0], primary[1], prediction, outcome)

        # Calculate confidence adjustment
        conf_adjust = self._calculate_confidence_adjustment(causes, prediction)

        return RootCauseDiagnosis(
            prediction_id=prediction.prediction_id,
            primary_cause=primary[0],
            secondary_causes=secondary,
            confidence_adjustment=conf_adjust,
            reasoning_flaw=primary[1],
            evidence_for_diagnosis=[c[1] for c in causes],
            correction_strategy=strategy,
        )

    def _check_timing(
        self, prediction: PredictionRecord, outcome: OutcomeRecord
    ) -> Optional[str]:
        """Check if timing was the issue (right direction, wrong time)."""
        if prediction.predicted_direction == outcome.actual_direction:
            return (
                f"Direction was correct ({prediction.predicted_direction}), "
                f"but may have been early/late. Adjust time horizon calibration."
            )
        return None

    def _check_regime_change(
        self,
        regime_before: Optional[dict],
        regime_after: Optional[dict],
    ) -> Optional[str]:
        """Check if regime shifted between prediction and outcome."""
        if not regime_before or not regime_after:
            return None

        before_label = regime_before.get("regime_label", "")
        after_label = regime_after.get("regime_label", "")

        if before_label != after_label:
            return (
                f"Regime shifted from '{before_label}' to '{after_label}'. "
                f"Prediction was made for the wrong regime."
            )
        return None

    def _check_confidence(
        self, prediction: PredictionRecord, outcome: OutcomeRecord
    ) -> Optional[tuple]:
        """Check if confidence was miscalibrated."""
        if outcome.was_correct:
            return None

        if prediction.confidence > 0.8:
            return (
                "Overconfidence",
                f"Confidence was {prediction.confidence:.0%} but prediction "
                f"was wrong. Evidence did not justify this high confidence."
            )
        elif prediction.confidence < 0.3:
            return (
                "Underconfidence",
                f"Confidence was only {prediction.confidence:.0%} but "
                f"outcome was {outcome.actual_change_pct:+.1%}. "
                f"Should have been more confident in the correct signal."
            )
        return None

    @staticmethod
    def _generate_strategy(
        primary_cause: str,
        detail: str,
        prediction: PredictionRecord,
        outcome: OutcomeRecord,
    ) -> str:
        """Generate a specific correction strategy for each cause type."""
        strategies = {
            "Wrong Data": (
                "Expand data source checklist. Verify data freshness before "
                "making predictions. Cross-reference with alternative sources."
            ),
            "Wrong Narrative": (
                "Run counter-narrative analysis before finalizing predictions. "
                "Generate at least 2 alternative narratives and evaluate each."
            ),
            "Wrong Regime": (
                "Increase regime classification confidence threshold. "
                "Add regime transition probability to every prediction. "
                "Consider both current and adjacent regime scenarios."
            ),
            "Wrong Timing": (
                "Add time horizon probability bands. Instead of 'X will happen', "
                "predict 'X has P% chance within 1m, Q% within 3m, R% within 6m'. "
                "Calibrate time horizon estimates using historical analogs."
            ),
            "Wrong Causality": (
                "Strengthen causal chain verification. Each prediction must have "
                "a explicit causal mechanism with falsifiable conditions. "
                "Use historical analog testing to verify causal logic."
            ),
            "Wrong Probability": (
                "Implement proper probability scoring. Add tail-risk scenarios "
                "to every prediction. Use historical distribution to calibrate "
                "probability estimates — not subjective confidence."
            ),
            "Black Swan": (
                "Black swans cannot be predicted, but vulnerability can be managed. "
                "Increase tail-risk hedging recommendations. Stress-test portfolio "
                "for extreme scenarios. Accept this as irreducible uncertainty."
            ),
            "Overconfidence": (
                "Reduce confidence by {:.0f}% on similar predictions. ".format(
                    100 * max(0, prediction.confidence - 0.7)
                ) +
                "Implement forced calibration: if confidence >70%, must list "
                "3 specific reasons why you could be wrong."
            ),
            "Underconfidence": (
                "Increase confidence floor to 30% when evidence is clear. "
                "Review what evidence you had that you failed to weight properly. "
                "List the signals you had but dismissed."
            ),
            "Missing Evidence": (
                "Create mandatory evidence checklist per regime type. "
                "Minimum 5 evidence items required before making any prediction. "
                "Track evidence completeness as an explicit quality metric."
            ),
        }

        return strategies.get(primary_cause, "Review and recalibrate the full reasoning chain.")

    @staticmethod
    def _calculate_confidence_adjustment(
        causes: list[tuple[str, str]], prediction: PredictionRecord
    ) -> float:
        """Calculate the appropriate confidence adjustment."""
        adjustments = {
            "Overconfidence": -0.15,
            "Underconfidence": +0.10,
            "Wrong Causality": -0.10,
            "Wrong Regime": -0.12,
            "Wrong Narrative": -0.08,
            "Wrong Timing": -0.05,
            "Wrong Data": -0.10,
            "Black Swan": 0.0,  # Don't adjust for unpredictable events
            "Missing Evidence": -0.08,
            "Wrong Probability": -0.05,
        }

        total = 0.0
        for cause_name, _ in causes[:3]:
            total += adjustments.get(cause_name, -0.05)

        return round(max(-0.3, min(0.15, total)), 2)


# ═══════════════════════════════════════════════════════════════════════════
# Belief Updater
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class BeliefUpdate:
    """Result of a belief update operation."""
    belief_id: str = ""
    belief_name: str = ""
    old_confidence: float = 0.0
    new_confidence: float = 0.0
    reason: str = ""
    was_updated: bool = False


@dataclass
class BeliefDiff:
    """Aggregate belief changes across all updated beliefs."""
    updates: list[BeliefUpdate] = field(default_factory=list)
    total_confidence_shift: float = 0.0
    beliefs_updated: int = 0
    beliefs_unchanged: int = 0
    summary: str = ""


class BeliefUpdater:
    """Updates agent beliefs based on prediction outcomes and root causes.

    Never simply decreases confidence — always has a reason tied to diagnosis.
    """

    def update(
        self,
        beliefs: list[dict],
        predictions: list[PredictionRecord],
        outcomes: list[OutcomeRecord],
        diagnoses: list[RootCauseDiagnosis],
    ) -> BeliefDiff:
        """Update beliefs based on prediction outcomes.

        Args:
            beliefs: Current belief list.
            predictions: Predictions made.
            outcomes: Actual outcomes.
            diagnoses: Root cause diagnoses.

        Returns:
            BeliefDiff with all changes.
        """
        updates = []

        # Build prediction→diagnosis→outcome lookup
        diag_lookup = {d.prediction_id: d for d in diagnoses}
        outcome_lookup = {o.prediction_id: o for o in outcomes}

        for pred in predictions:
            diagnosis = diag_lookup.get(pred.prediction_id)
            outcome = outcome_lookup.get(pred.prediction_id)

            if not diagnosis or not outcome:
                continue

            # Find matching beliefs
            for belief in beliefs:
                relevance = self._belief_relevance(belief, pred)
                if relevance < 0.3:
                    continue

                old_conf = float(belief.get("confidence", 0.5))
                adjustment = diagnosis.confidence_adjustment * relevance

                # Cap adjustment
                new_conf = max(0.1, min(0.95, old_conf + adjustment))

                if abs(new_conf - old_conf) > 0.01:
                    updates.append(BeliefUpdate(
                        belief_id=str(belief.get("id", belief.get("name", ""))),
                        belief_name=str(belief.get("name", "unknown")),
                        old_confidence=old_conf,
                        new_confidence=new_conf,
                        reason=f"{diagnosis.primary_cause}: {diagnosis.reasoning_flaw}",
                        was_updated=True,
                    ))
                    # Update in-place
                    belief["confidence"] = new_conf
                    belief["confidence"] = new_conf

                    # Store diagnosis info
                    belief["last_diagnosis"] = diagnosis.primary_cause
                    belief["last_updated"] = datetime.now(timezone.utc).isoformat()

        unchanged = len(beliefs) - len(updates)
        total_shift = sum(u.new_confidence - u.old_confidence for u in updates)

        return BeliefDiff(
            updates=updates,
            total_confidence_shift=round(total_shift, 2),
            beliefs_updated=len(updates),
            beliefs_unchanged=max(0, unchanged),
            summary=self._summarize(updates),
        )

    @staticmethod
    def _belief_relevance(belief: dict, prediction: PredictionRecord) -> float:
        """How relevant is this belief to this prediction? 0-1."""
        belief_text = (
            str(belief.get("name", "")) + " " + str(belief.get("title", ""))
        ).lower()

        pred_text = (
            prediction.prediction_statement + " " + prediction.catalyst
        ).lower()

        score = 0.0

        # Asset class match
        if prediction.asset_class.lower() in belief_text:
            score += 0.3

        # Direction consistency
        belief_dir = str(belief.get("direction", "")).lower()
        if belief_dir and prediction.predicted_direction.lower() in belief_dir:
            score += 0.2

        # Keyword overlap
        belief_words = set(belief_text.split())
        pred_words = set(pred_text.split())
        if belief_words and pred_words:
            overlap = len(belief_words & pred_words) / min(len(belief_words), len(pred_words))
            score += overlap * 0.3

        return min(1.0, round(score, 2))

    @staticmethod
    def _summarize(updates: list[BeliefUpdate]) -> str:
        if not updates:
            return "No beliefs updated — all predictions aligned with existing beliefs."
        increased = [u for u in updates if u.new_confidence > u.old_confidence]
        decreased = [u for u in updates if u.new_confidence < u.old_confidence]

        parts = []
        if increased:
            parts.append(f"{len(increased)} beliefs strengthened")
        if decreased:
            parts.append(f"{len(decreased)} beliefs weakened")
        return "; ".join(parts) + " based on prediction outcomes."


# ═══════════════════════════════════════════════════════════════════════════
# Prompt Updater
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class PromptUpdate:
    """Record of a prompt modification."""
    domain: str = ""
    change_type: str = ""  # "addition", "modification", "weight_change"
    before: str = ""
    after: str = ""
    reason: str = ""


@dataclass
class PromptDiff:
    """Aggregate changes to the prompt system."""
    updates: list[PromptUpdate] = field(default_factory=list)
    domains_affected: list[str] = field(default_factory=list)
    summary: str = ""


class PromptUpdater:
    """V10 Sprint 4: Learns from outcomes to improve prompt templates.

    Based on root cause diagnosis, adjusts domain prompts:
    - If Wrong Narrative: add more explicit alternative narrative instructions
    - If Wrong Causality: strengthen causal chain requirements
    - If Overconfidence: add calibration instructions
    - If Missing Evidence: add evidence requirement checklists
    """

    def update(
        self,
        diagnoses: list[RootCauseDiagnosis],
        used_domains: list[str],
        current_prompts: Optional[dict[str, str]] = None,
    ) -> PromptDiff:
        """Generate prompt improvements based on diagnosis patterns.

        Args:
            diagnoses: Root cause analyses from this cycle.
            used_domains: Which domain prompts were used.
            current_prompts: Current domain-specific prompts (optional).

        Returns:
            PromptDiff with suggested prompt changes.
        """
        updates = []
        affected_domains = set()

        # Aggregate diagnosis patterns
        cause_counts = {}
        for d in diagnoses:
            cause_counts[d.primary_cause] = cause_counts.get(d.primary_cause, 0) + 1

        # Generate updates for each pattern
        for cause, count in cause_counts.items():
            if count < 1:
                continue

            for domain in used_domains:
                update = self._cause_to_prompt_update(cause, domain, count)
                if update:
                    updates.append(update)
                    affected_domains.add(domain)

        return PromptDiff(
            updates=updates,
            domains_affected=list(affected_domains),
            summary=self._summarize_diff(updates, diagnoses),
        )

    def _cause_to_prompt_update(
        self, cause: str, domain: str, frequency: int
    ) -> Optional[PromptUpdate]:
        """Map a root cause to a specific prompt improvement."""
        mappings = {
            "Wrong Narrative": PromptUpdate(
                domain=domain,
                change_type="addition",
                before="",
                after=f"ADD: Before finalizing, generate 2 alternative narratives "
                      f"that contradict your thesis. Evaluate each seriously.",
                reason=f"Wrong Narrative detected ({frequency}x) — "
                       f"prompt needs counter-narrative requirement",
            ),
            "Wrong Causality": PromptUpdate(
                domain=domain,
                change_type="addition",
                before="",
                after=f"ADD: For each key claim, explicitly state: "
                      f"'IF [mechanism] THEN [outcome] BECAUSE [causal chain]'. "
                      f"List the invalidation condition for each causal claim.",
                reason=f"Wrong Causality detected ({frequency}x) — "
                       f"prompt needs explicit causal chain requirement",
            ),
            "Overconfidence": PromptUpdate(
                domain=domain,
                change_type="addition",
                before="",
                after=f"ADD: If confidence in any prediction exceeds 70%, "
                      f"you MUST list 3 specific reasons why you could be wrong. "
                      f"Each reason must reference concrete evidence.",
                reason=f"Overconfidence detected ({frequency}x) — "
                       f"prompt needs calibration requirement",
            ),
            "Missing Evidence": PromptUpdate(
                domain=domain,
                change_type="addition",
                before="",
                after=f"ADD: MINIMUM EVIDENCE REQUIREMENT: Before making any claim, "
                      f"verify you have at least 3 specific pieces of evidence "
                      f"from the structured input supporting it.",
                reason=f"Missing Evidence ({frequency}x) — "
                       f"prompt needs evidence sufficiency check",
            ),
            "Wrong Regime": PromptUpdate(
                domain=domain,
                change_type="addition",
                before="",
                after=f"ADD: Begin analysis with explicit regime confirmation: "
                      f"'Current regime is [X] with {frequency} confidence. "
                      f"If the regime were instead [Y], the analysis would change as follows...'",
                reason=f"Wrong Regime detected ({frequency}x) — "
                       f"prompt needs regime-awareness requirement",
            ),
        }

        return mappings.get(cause)

    @staticmethod
    def _summarize_diff(
        updates: list[PromptUpdate], diagnoses: list[RootCauseDiagnosis]
    ) -> str:
        if not updates:
            return "No prompt updates needed — predictions well-calibrated."

        cause_summary = {}
        for d in diagnoses:
            cause_summary[d.primary_cause] = cause_summary.get(d.primary_cause, 0) + 1

        parts = [f"{len(updates)} prompt improvement(s) generated:"]
        for update in updates:
            parts.append(f"  • {update.domain}: {update.reason}")
        return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# Reasoning Template Updater
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ReasoningUpdate:
    """Record of a reasoning process change."""
    step: str = ""
    change_type: str = ""
    description: str = ""


@dataclass
class ReasoningDiff:
    """Aggregate reasoning process changes."""
    updates: list[ReasoningUpdate] = field(default_factory=list)
    summary: str = ""


class ReasoningUpdater:
    """Improves the reasoning process based on diagnosis patterns.

    Adjusts step weights, adds verification steps, modifies threshold values.
    """

    _STEP_MAP = {
        "Wrong Data": "Evidence",
        "Missing Evidence": "Evidence",
        "Wrong Narrative": "Hypothesis",
        "Wrong Causality": "Hypothesis",
        "Wrong Regime": "Reflexivity",
        "Overconfidence": "Quality",
        "Underconfidence": "Quality",
        "Wrong Probability": "CounterArgument",
        "Wrong Timing": "Historical",
    }

    def update(self, diagnoses: list[RootCauseDiagnosis]) -> ReasoningDiff:
        """Generate reasoning process improvements."""
        updates = []
        cause_counts = {}
        for d in diagnoses:
            cause_counts[d.primary_cause] = cause_counts.get(d.primary_cause, 0) + 1

        for cause, count in cause_counts.items():
            step = self._STEP_MAP.get(cause, "Synthesis")
            rec = self._get_recommendation(cause, count)
            if rec:
                updates.append(ReasoningUpdate(
                    step=step,
                    change_type="enhancement",
                    description=rec,
                ))

        return ReasoningDiff(
            updates=updates,
            summary=(
                f"{len(updates)} reasoning step(s) enhanced based on "
                f"{len(diagnoses)} diagnosis results."
            ) if updates else "No reasoning changes needed.",
        )

    @staticmethod
    def _get_recommendation(cause: str, frequency: int) -> str:
        """Get specific reasoning improvement recommendation."""
        recs = {
            "Wrong Data": (
                f"Evidence step: Add data freshness validation. "
                f"All data points must include timestamp. "
                f"Stale data (>7 days) must be flagged."
            ),
            "Wrong Narrative": (
                f"Hypothesis step: Increase minimum hypothesis count to 5. "
                f"Require at least 2 alternative hypotheses per observation. "
                f"Score hypotheses by falsifiability."
            ),
            "Wrong Regime": (
                f"Reflexivity step: Expand regime transition probability analysis. "
                f"Add adjacent-regime scenario to every prediction. "
                f"Increase regime confidence threshold."
            ),
            "Missing Evidence": (
                f"Evidence step: Enforce minimum 5 evidence items per analysis. "
                f"Track evidence coverage ratio as quality metric. "
                f"Flag under-evidenced claims for review."
            ),
            "Overconfidence": (
                f"Quality step: Add calibration checker. "
                f"When confidence > 70%, require explicit invalidation conditions. "
                f"Compare claim confidence against historical accuracy baseline."
            ),
        }
        return recs.get(cause, f"Review {cause.lower()} pattern ({frequency}x) — adjust step accordingly.")


# ═══════════════════════════════════════════════════════════════════════════
# Learning Report
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class LearningReport:
    """Complete learning report after a benchmark cycle."""
    cycle_id: str = ""
    timestamp: str = ""
    total_predictions: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.0
    diagnoses: list[RootCauseDiagnosis] = field(default_factory=list)
    belief_diff: Optional[BeliefDiff] = None
    prompt_diff: Optional[PromptDiff] = None
    reasoning_diff: Optional[ReasoningDiff] = None
    performance_change: float = 0.0  # Delta from previous cycle
    key_improvements: list[str] = field(default_factory=list)
    cause_distribution: dict[str, int] = field(default_factory=dict)
    ece: float = 0.0  # Expected Calibration Error
    expert_similarity_change: float = 0.0
    memo_quality_change: float = 0.0

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "accuracy": self.accuracy,
            "cause_distribution": self.cause_distribution,
            "belief_diff": self.belief_diff.summary if self.belief_diff else "",
            "prompt_diff": self.prompt_diff.summary if self.prompt_diff else "",
            "reasoning_diff": self.reasoning_diff.summary if self.reasoning_diff else "",
            "performance_change": self.performance_change,
            "ece": self.ece,
            "expert_similarity_change": self.expert_similarity_change,
            "memo_quality_change": self.memo_quality_change,
            "key_improvements": self.key_improvements,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Continuous Learning Loop — Main Orchestrator
# ═══════════════════════════════════════════════════════════════════════════


class ContinuousLearningLoop:
    """V10 Sprint 4: Continuous Learning Loop.

    After every benchmark cycle:
        Predictions + Outcomes → Diagnose → Update Beliefs → Update Prompts 
        → Update Reasoning → Generate Report → Next Benchmark
    """

    def __init__(self):
        self._diagnostician = RootCauseDiagnostician()
        self._belief_updater = BeliefUpdater()
        self._prompt_updater = PromptUpdater()
        self._reasoning_updater = ReasoningUpdater()
        self._cycle_history: list[LearningReport] = []
        self._all_diagnoses: list[RootCauseDiagnosis] = []

    def run_cycle(
        self,
        predictions: list[PredictionRecord],
        outcomes: list[OutcomeRecord],
        beliefs: list[dict],
        used_domains: list[str],
        regime_records: Optional[dict] = None,
        previous_metrics: Optional[dict] = None,
    ) -> LearningReport:
        """Execute a full learning cycle.

        Args:
            predictions: All predictions made in the benchmark.
            outcomes: Actual outcomes for those predictions.
            beliefs: Current belief state (mutated in-place).
            used_domains: Which domain prompts were used.
            regime_records: Dict of prediction_id → (regime_at_pred, regime_at_outcome).
            previous_metrics: Previous cycle metrics to compute deltas.

        Returns:
            LearningReport summarizing all changes.
        """
        t0 = time.time()
        cycle_id = hashlib.md5(
            str(time.time()).encode()
        ).hexdigest()[:12]

        # ── Step 1: Diagnose every prediction ──
        diagnoses = []
        for pred in predictions:
            outcome = next(
                (o for o in outcomes if o.prediction_id == pred.prediction_id), None
            )
            if not outcome:
                continue

            regimes = None
            if regime_records:
                regimes = regime_records.get(pred.prediction_id)

            diagnosis = self._diagnostician.diagnose(
                prediction=pred,
                outcome=outcome,
                regime_at_prediction=regimes[0] if regimes else None,
                regime_at_outcome=regimes[1] if regimes else None,
            )
            diagnoses.append(diagnosis)

        self._all_diagnoses.extend(diagnoses)

        # ── Step 2: Update Beliefs ──
        error_diagnoses = [d for d in diagnoses if d.primary_cause != "Correct Prediction"]
        belief_diff = self._belief_updater.update(
            beliefs=beliefs,
            predictions=predictions,
            outcomes=outcomes,
            diagnoses=error_diagnoses,
        )

        # ── Step 3: Update Prompts ──
        prompt_diff = self._prompt_updater.update(
            diagnoses=error_diagnoses,
            used_domains=used_domains,
        )

        # ── Step 4: Update Reasoning ──
        reasoning_diff = self._reasoning_updater.update(
            diagnoses=error_diagnoses,
        )

        # ── Step 5: Compute Metrics ──
        total = len(predictions)
        correct = sum(1 for o in outcomes if o.was_correct)
        accuracy = round(correct / max(total, 1), 3)

        # ECE (Expected Calibration Error) — simplified
        ece = self._compute_ece(predictions, outcomes)

        # Performance change
        perf_change = 0.0
        if previous_metrics:
            prev_acc = previous_metrics.get("accuracy", accuracy)
            perf_change = round(accuracy - prev_acc, 3)

        # Cause distribution
        cause_dist = {}
        for d in diagnoses:
            cause_dist[d.primary_cause] = cause_dist.get(d.primary_cause, 0) + 1

        # Key improvements
        key_improvements = self._identify_key_improvements(
            diagnoses, belief_diff, prompt_diff, reasoning_diff
        )

        elapsed = (time.time() - t0) * 1000
        logger.info(
            "Learning cycle %s complete: acc=%.1f%%, ECE=%.3f, "
            "%d diagnoses, %d beliefs updated, %.0fms",
            cycle_id, accuracy * 100, ece,
            len(error_diagnoses), belief_diff.beliefs_updated, elapsed,
        )

        report = LearningReport(
            cycle_id=cycle_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_predictions=total,
            correct_predictions=correct,
            accuracy=accuracy,
            diagnoses=diagnoses,
            belief_diff=belief_diff,
            prompt_diff=prompt_diff,
            reasoning_diff=reasoning_diff,
            performance_change=perf_change,
            key_improvements=key_improvements,
            cause_distribution=cause_dist,
            ece=ece,
        )

        self._cycle_history.append(report)
        return report

    @staticmethod
    def _compute_ece(
        predictions: list[PredictionRecord], outcomes: list[OutcomeRecord]
    ) -> float:
        """Compute Expected Calibration Error."""
        outcome_lookup = {o.prediction_id: o for o in outcomes}

        bins = [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]
        ece = 0.0

        for low, high in bins:
            bin_preds = [p for p in predictions if low <= p.confidence < high]
            if not bin_preds:
                continue

            bin_correct = sum(
                1 for p in bin_preds
                if outcome_lookup.get(p.prediction_id)
                and outcome_lookup[p.prediction_id].was_correct
            )
            bin_accuracy = bin_correct / len(bin_preds)
            bin_confidence = (low + high) / 2

            ece += (len(bin_preds) / len(predictions)) * abs(bin_accuracy - bin_confidence)

        return round(ece, 4) if predictions else 0.0

    @staticmethod
    def _identify_key_improvements(
        diagnoses: list[RootCauseDiagnosis],
        belief_diff: Optional[BeliefDiff],
        prompt_diff: Optional[PromptDiff],
        reasoning_diff: Optional[ReasoningDiff],
    ) -> list[str]:
        """Identify the most important improvements from this cycle."""
        improvements = []

        if belief_diff and belief_diff.beliefs_updated > 0:
            improvements.append(
                f"Updated {belief_diff.beliefs_updated} beliefs: {belief_diff.summary}"
            )

        if prompt_diff and prompt_diff.updates:
            improvements.append(
                f"Enhanced {len(prompt_diff.domains_affected)} prompt domains: "
                f"{', '.join(prompt_diff.domains_affected[:3])}"
            )

        if reasoning_diff and reasoning_diff.updates:
            improvements.append(
                f"Improved reasoning steps: "
                f"{', '.join(u.step for u in reasoning_diff.updates[:3])}"
            )

        cause_dist = {}
        for d in diagnoses:
            if d.primary_cause != "Correct Prediction":
                cause_dist[d.primary_cause] = cause_dist.get(d.primary_cause, 0) + 1

        if cause_dist:
            top_cause = max(cause_dist, key=cause_dist.get)
            improvements.append(
                f"Primary failure mode: {top_cause} ({cause_dist[top_cause]}x)"
            )

        return improvements

    def get_history(self) -> list[LearningReport]:
        """Get all cycle reports."""
        return list(self._cycle_history)

    def get_latest_report(self) -> Optional[LearningReport]:
        """Get the most recent learning report."""
        return self._cycle_history[-1] if self._cycle_history else None

    def get_improvement_trend(self) -> dict:
        """Track accuracy improvement over cycles."""
        if not self._cycle_history:
            return {"cycles": 0, "initial_accuracy": 0, "current_accuracy": 0, "trend": "flat"}

        initial = self._cycle_history[0].accuracy
        current = self._cycle_history[-1].accuracy

        if current > initial + 0.03:
            trend = "improving"
        elif current < initial - 0.03:
            trend = "declining"
        else:
            trend = "flat"

        return {
            "cycles": len(self._cycle_history),
            "initial_accuracy": initial,
            "current_accuracy": current,
            "trend": trend,
            "delta": round(current - initial, 3),
        }
