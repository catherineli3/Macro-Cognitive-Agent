"""V8.5 Long-term Learning — Reasoning evolution, not just confidence calibration.

When predictions are wrong, the agent doesn't just:
    confidence -= 0.1

Instead it diagnoses ROOT CAUSE:
    Prediction Wrong
    ↓
    Root Cause
    ↓
    Reasoning Error
    ↓
    Narrative Error
    ↓
    Belief Error
    ↓
    Evidence Error
    ↓
    Regime Error
    ↓
    Prompt Update
    ↓
    Reasoning Style Update

The agent's reasoning STYLE must evolve over time, not just its confidence levels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class ErrorRootCause(str, Enum):
    """Root causes of prediction/reasoning errors."""
    EVIDENCE_WRONG = "evidence_wrong"              # Key data was misinterpreted
    EVIDENCE_INSUFFICIENT = "evidence_insufficient" # Not enough data
    NARRATIVE_WRONG = "narrative_wrong"            # Wrong story framework
    BELIEF_WRONG = "belief_wrong"                  # Core belief was incorrect
    REGIME_MISJUDGED = "regime_misjudged"          # Wrong regime assumption
    COUNTER_IGNORED = "counter_ignored"            # Valid counter was dismissed
    TIMING_WRONG = "timing_wrong"                  # Right direction, wrong timing
    MAGNITUDE_WRONG = "magnitude_wrong"            # Right direction, wrong size
    CORRELATION_BREAK = "correlation_break"        # Historical relationships broke
    EXOGENOUS_SHOCK = "exogenous_shock"             # Unpredictable event
    MODEL_ERROR = "model_error"                    # Framework limitation
    UNKNOWN = "unknown"                             # Cannot determine


class LearningType(str, Enum):
    """Types of learning that modify the agent's behavior."""
    PROMPT_UPDATE = "prompt_update"                # Change how we ask LLM
    REASONING_STYLE = "reasoning_style"             # Change reasoning approach
    BELIEF_UPDATE = "belief_update"                 # Update belief parameters
    NARRATIVE_UPDATE = "narrative_update"           # Update narrative framework
    EVIDENCE_WEIGHT = "evidence_weight"             # Change evidence weighting
    REGIME_RECLASSIFY = "regime_reclassify"         # Reclassify regime
    CORRELATION_UPDATE = "correlation_update"       # Update correlation assumptions
    PROCESS_CHANGE = "process_change"               # Change research workflow


@dataclass
class DiagnosisPath:
    """Step-by-step root cause diagnosis."""
    step: int = 0
    hypothesis: str = ""                # What we think went wrong
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    confidence: float = 0.5
    is_root_cause: bool = False


@dataclass
class RootCauseDiagnosis:
    """Complete root cause analysis of a failed prediction."""
    diagnosis_id: str = field(default_factory=lambda: uuid4().hex[:8])
    
    # What went wrong
    original_prediction: str = ""
    original_probability: float = 0.5
    actual_outcome: str = ""
    was_correct: bool = False
    error_magnitude: float = 0.0           # How wrong (0-1)
    
    # Diagnosis
    root_cause: ErrorRootCause = ErrorRootCause.UNKNOWN
    root_cause_confidence: float = 0.5
    diagnosis_path: list[DiagnosisPath] = field(default_factory=list)
    
    # Alternative explanations
    alternative_causes: list[dict] = field(default_factory=list)
    # [{cause, probability, evidence}]
    
    # Impact
    what_should_have_been_different: str = ""
    key_lesson: str = ""
    
    # Learning
    learning_type: LearningType = LearningType.BELIEF_UPDATE
    learning_specifics: dict = field(default_factory=dict)
    
    date: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d'))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ReasoningEvolution:
    """Tracks how the agent's reasoning has evolved over time."""
    evolution_id: str = field(default_factory=lambda: uuid4().hex[:8])
    learning_type: LearningType = LearningType.BELIEF_UPDATE
    
    # What changed
    change_description: str = ""
    trigger_diagnosis_id: str = ""
    
    # Before/After
    before_state: dict = field(default_factory=dict)
    after_state: dict = field(default_factory=dict)
    
    # Impact tracking
    expected_improvement: str = ""
    
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DeepLearningEngine:
    """Long-term learning that evolves the agent's reasoning style.

    Not just Bayesian updating — true reasoning evolution:
    1. Diagnose root cause of every error
    2. Map error to specific learning action
    3. Modify reasoning approach
    4. Track improvement over time
    """

    def __init__(self):
        self.diagnoses: dict[str, RootCauseDiagnosis] = {}
        self.evolutions: list[ReasoningEvolution] = []
        
        # Learning history
        self.error_patterns: dict[ErrorRootCause, int] = {
            cause: 0 for cause in ErrorRootCause
        }
        self.learning_applied: dict[LearningType, int] = {
            lt: 0 for lt in LearningType
        }
        
        # Track improvement
        self.accuracy_before_learning: float = 0.5
        self.accuracy_after_learning: float = 0.5
        
        # Reasoning style version
        self.reasoning_version: int = 1
        self.reasoning_patches: list[dict] = []

    def diagnose_error(self, prediction: str, probability: float,
                       actual_outcome: str, was_correct: bool,
                       context: Optional[dict] = None) -> RootCauseDiagnosis:
        """Diagnose why a prediction was wrong."""
        
        diagnosis = RootCauseDiagnosis(
            original_prediction=prediction,
            original_probability=probability,
            actual_outcome=actual_outcome,
            was_correct=was_correct,
            error_magnitude=abs(probability - (1.0 if was_correct else 0.0)),
        )
        
        if was_correct:
            diagnosis.root_cause = ErrorRootCause.UNKNOWN  # No error to diagnose
            diagnosis.key_lesson = "Prediction was correct — validate what worked."
            diagnosis.what_should_have_been_different = "Nothing — prediction was accurate."
        else:
            # Walk through diagnostic tree
            diagnosis.diagnosis_path = self._walk_diagnosis_tree(prediction, context)
            diagnosis.root_cause = self._identify_root_cause(diagnosis.diagnosis_path)
            diagnosis.root_cause_confidence = self._root_cause_confidence(diagnosis.diagnosis_path)
            diagnosis.alternative_causes = self._generate_alternatives(prediction, context)
            diagnosis.key_lesson = self._generate_lesson(diagnosis)
            diagnosis.what_should_have_been_different = self._what_should_have_been(
                diagnosis
            )
            
            # Determine learning type
            diagnosis.learning_type = self._map_to_learning(diagnosis.root_cause)
            diagnosis.learning_specifics = self._generate_learning_specifics(diagnosis)
            
            # Apply learning
            self._apply_learning(diagnosis)
        
        self.diagnoses[diagnosis.diagnosis_id] = diagnosis
        self.error_patterns[diagnosis.root_cause] += 1
        
        return diagnosis

    def apply_learning(self, diagnosis: RootCauseDiagnosis) -> ReasoningEvolution:
        """Apply the learning from a diagnosis to evolve reasoning."""
        
        evolution = ReasoningEvolution(
            learning_type=diagnosis.learning_type,
            change_description=diagnosis.key_lesson,
            trigger_diagnosis_id=diagnosis.diagnosis_id,
            before_state={"reasoning_version": self.reasoning_version},
            expected_improvement=f"Reduce {diagnosis.root_cause.value} errors",
        )
        
        # Apply the actual change
        if diagnosis.learning_type == LearningType.REASONING_STYLE:
            self.reasoning_version += 1
            self.reasoning_patches.append({
                "version": self.reasoning_version,
                "change": diagnosis.key_lesson,
                "root_cause": diagnosis.root_cause.value,
                "timestamp": diagnosis.timestamp,
            })
            evolution.after_state = {
                "reasoning_version": self.reasoning_version,
                "patches_applied": len(self.reasoning_patches),
            }
        elif diagnosis.learning_type == LearningType.PROMPT_UPDATE:
            evolution.after_state = {
                "prompt_modified": diagnosis.learning_specifics.get("prompt_change", ""),
            }
        elif diagnosis.learning_type == LearningType.BELIEF_UPDATE:
            evolution.after_state = {
                "belief_updated": diagnosis.learning_specifics.get("belief_update", ""),
            }
        
        self.evolutions.append(evolution)
        self.learning_applied[diagnosis.learning_type] += 1
        
        return evolution

    def get_evolution_history(self) -> list[ReasoningEvolution]:
        return list(self.evolutions)

    def get_error_patterns(self) -> dict[str, int]:
        return {
            cause.value: count 
            for cause, count in self.error_patterns.items()
        }

    def get_most_common_error(self) -> tuple[ErrorRootCause, int]:
        if not self.error_patterns:
            return ErrorRootCause.UNKNOWN, 0
        return max(self.error_patterns.items(), key=lambda x: x[1])

    def get_reasoning_version(self) -> dict:
        return {
            "version": self.reasoning_version,
            "patches": self.reasoning_patches,
            "total_evolutions": len(self.evolutions),
            "total_diagnoses": len(self.diagnoses),
        }

    def get_accuracy_improvement(self) -> dict:
        return {
            "before_learning": self.accuracy_before_learning,
            "after_learning": self.accuracy_after_learning,
            "improvement": self.accuracy_after_learning - self.accuracy_before_learning,
            "total_learning_events": sum(self.learning_applied.values()),
        }

    def get_stats(self) -> dict:
        correct_diagnoses = sum(
            1 for d in self.diagnoses.values() if d.was_correct
        )
        total = max(len(self.diagnoses), 1)
        
        return {
            "total_diagnoses": len(self.diagnoses),
            "accuracy": correct_diagnoses / total,
            "error_patterns": self.get_error_patterns(),
            "most_common_error": self.get_most_common_error()[0].value,
            "learning_applied": {
                lt.value: count for lt, count in self.learning_applied.items()
            },
            "reasoning_version": self.reasoning_version,
            "total_evolutions": len(self.evolutions),
            "accuracy_improvement": self.get_accuracy_improvement(),
        }

    def generate_learning_report(self) -> str:
        """Generate a comprehensive learning report."""
        stats = self.get_stats()
        
        lines = [
            "# Long-term Learning Report",
            "",
            f"## Accuracy",
            f"- Current: {stats['accuracy']:.1%}",
            f"- Total predictions tracked: {stats['total_diagnoses']}",
            "",
            f"## Error Patterns",
        ]
        
        for cause, count in sorted(
            self.get_error_patterns().items(), key=lambda x: x[1], reverse=True
        ):
            if count > 0:
                lines.append(f"- **{cause}**: {count} occurrences")
        
        lines.extend([
            "",
            "## Learning Applied",
        ])
        for lt, count in self.learning_applied.items():
            if count > 0:
                lines.append(f"- **{lt}**: {count} updates")
        
        lines.extend([
            "",
            f"## Reasoning Evolution",
            f"- Current version: v{self.reasoning_version}",
            f"- Total patches: {len(self.reasoning_patches)}",
        ])
        
        if self.reasoning_patches:
            lines.append("", "### Patch History")
            for p in self.reasoning_patches[-5:]:
                lines.append(f"- **v{p['version']}**: {p['change'][:100]} ({p['root_cause']})")
        
        return "\n".join(lines)

    # ── Internal Diagnostic Tree ─────────────────────────────────────────

    def _walk_diagnosis_tree(self, prediction: str,
                             context: Optional[dict]) -> list[DiagnosisPath]:
        """Walk through the diagnostic tree to find root cause."""
        path = []
        
        # Step 1: Check evidence
        path.append(DiagnosisPath(
            step=1,
            hypothesis="Evidence was wrong or insufficient",
            evidence_for=["Data may have been misinterpreted"],
            evidence_against=["Data quality may be adequate"],
            confidence=0.4,
        ))
        
        # Step 2: Check narrative
        path.append(DiagnosisPath(
            step=2,
            hypothesis="Wrong narrative framework was applied",
            evidence_for=["Narrative may have driven conclusion rather than data"],
            evidence_against=["Narrative was reasonable given available data"],
            confidence=0.35,
        ))
        
        # Step 3: Check belief
        path.append(DiagnosisPath(
            step=3,
            hypothesis="Core belief was incorrect",
            evidence_for=["Belief may have been too strong given evidence"],
            evidence_against=["Multiple beliefs converged on same conclusion"],
            confidence=0.3,
        ))
        
        # Step 4: Check regime
        path.append(DiagnosisPath(
            step=4,
            hypothesis="Macro regime was misclassified",
            evidence_for=["Regime transition may have been underway"],
            evidence_against=["Regime appeared stable at time of prediction"],
            confidence=0.25,
        ))
        
        # Step 5: Check counter
        path.append(DiagnosisPath(
            step=5,
            hypothesis="Valid counter-arguments were ignored",
            evidence_for=["Counter-arguments existed but were dismissed"],
            evidence_against=["Counter-arguments were weak or improbable"],
            confidence=0.2,
        ))
        
        return path

    def _identify_root_cause(self, path: list[DiagnosisPath]) -> ErrorRootCause:
        """Identify the most likely root cause from the diagnosis path."""
        if not path:
            return ErrorRootCause.UNKNOWN
        
        # Highest confidence diagnosis that hasn't been ruled out
        for p in sorted(path, key=lambda x: x.confidence, reverse=True):
            evidence_ratio = len(p.evidence_for) / max(len(p.evidence_for) + len(p.evidence_against), 1)
            if evidence_ratio > 0.5:
                # Map to root cause
                step_map = {
                    1: ErrorRootCause.EVIDENCE_INSUFFICIENT,
                    2: ErrorRootCause.NARRATIVE_WRONG,
                    3: ErrorRootCause.BELIEF_WRONG,
                    4: ErrorRootCause.REGIME_MISJUDGED,
                    5: ErrorRootCause.COUNTER_IGNORED,
                }
                return step_map.get(p.step, ErrorRootCause.UNKNOWN)
        
        return ErrorRootCause.UNKNOWN

    def _root_cause_confidence(self, path: list[DiagnosisPath]) -> float:
        best = max(path, key=lambda p: p.confidence) if path else None
        return best.confidence if best else 0.3

    def _generate_alternatives(self, prediction: str,
                               context: Optional[dict]) -> list[dict]:
        return [
            {"cause": "Timing was the only error", "probability": 0.3,
             "evidence": "Direction was correct but magnitude/timing off."},
            {"cause": "Exogenous shock", "probability": 0.15,
             "evidence": "Unpredictable event intervened."},
            {"cause": "Model limitation", "probability": 0.1,
             "evidence": "Framework couldn't capture this scenario."},
        ]

    def _generate_lesson(self, diagnosis: RootCauseDiagnosis) -> str:
        lessons = {
            ErrorRootCause.EVIDENCE_WRONG: (
                "Verify evidence quality and triangulate across multiple sources "
                "before forming a strong view. Correlation is not causation."
            ),
            ErrorRootCause.EVIDENCE_INSUFFICIENT: (
                "Delay high-conviction calls until sufficient evidence accumulates. "
                "Low conviction should mean small position size."
            ),
            ErrorRootCause.NARRATIVE_WRONG: (
                "Challenge the narrative before committing. Ask: what story would "
                "I tell if the data were different? Avoid narrative-first analysis."
            ),
            ErrorRootCause.BELIEF_WRONG: (
                "Beliefs should have explicit invalidation conditions. When evidence "
                "contradicts, reduce confidence immediately. Strong beliefs, weakly held."
            ),
            ErrorRootCause.REGIME_MISJUDGED: (
                "Regime classification needs continuous updating. Look for early "
                "signals of regime transition. Don't fight the regime."
            ),
            ErrorRootCause.COUNTER_IGNORED: (
                "Always give the counter-argument its strongest form before dismissing. "
                "If you can't articulate the bear case convincingly, you don't understand the thesis."
            ),
            ErrorRootCause.TIMING_WRONG: (
                "Being right too early is indistinguishable from being wrong. "
                "Use catalysts and technical levels for timing, not just fundamentals."
            ),
            ErrorRootCause.CORRELATION_BREAK: (
                "Historical correlations are unreliable in regime transitions. "
                "Stress-test assumptions under multiple correlation scenarios."
            ),
            ErrorRootCause.EXOGENOUS_SHOCK: (
                "Black swans happen. Maintain tail hedges. Don't overfit to "
                "the unpredictable — but be prepared for it."
            ),
            ErrorRootCause.UNKNOWN: (
                "When root cause is unclear, reduce position size and gather "
                "more evidence. Uncertainty should reduce conviction."
            ),
        }
        
        return lessons.get(diagnosis.root_cause, 
                          "Learn from the error and adjust the reasoning process.")

    def _what_should_have_been(self, diagnosis: RootCauseDiagnosis) -> str:
        return (
            f"Based on diagnosis ({diagnosis.root_cause.value}): "
            f"the agent should have recognized {diagnosis.root_cause.value} "
            f"earlier and adjusted confidence/probability accordingly."
        )

    def _map_to_learning(self, root_cause: ErrorRootCause) -> LearningType:
        learning_map = {
            ErrorRootCause.EVIDENCE_WRONG: LearningType.EVIDENCE_WEIGHT,
            ErrorRootCause.EVIDENCE_INSUFFICIENT: LearningType.PROCESS_CHANGE,
            ErrorRootCause.NARRATIVE_WRONG: LearningType.NARRATIVE_UPDATE,
            ErrorRootCause.BELIEF_WRONG: LearningType.BELIEF_UPDATE,
            ErrorRootCause.REGIME_MISJUDGED: LearningType.REGIME_RECLASSIFY,
            ErrorRootCause.COUNTER_IGNORED: LearningType.REASONING_STYLE,
            ErrorRootCause.TIMING_WRONG: LearningType.REASONING_STYLE,
            ErrorRootCause.CORRELATION_BREAK: LearningType.CORRELATION_UPDATE,
            ErrorRootCause.MODEL_ERROR: LearningType.PROMPT_UPDATE,
            ErrorRootCause.UNKNOWN: LearningType.PROCESS_CHANGE,
        }
        return learning_map.get(root_cause, LearningType.BELIEF_UPDATE)

    def _generate_learning_specifics(self, 
                                      diagnosis: RootCauseDiagnosis) -> dict:
        return {
            "root_cause": diagnosis.root_cause.value,
            "lesson": diagnosis.key_lesson,
            "learning_type": diagnosis.learning_type.value,
            "should_modify": diagnosis.root_cause != ErrorRootCause.UNKNOWN,
            "priority": "high" if diagnosis.error_magnitude > 0.5 else "medium",
        }

    def _apply_learning(self, diagnosis: RootCauseDiagnosis):
        """Apply the learning — modify agent behavior."""
        # In production, this would update:
        # - Prompt templates
        # - Reasoning pipeline rules
        # - Belief update parameters
        # - Evidence weighting
        # - Narrative tracking sensitivity
        
        # For now, track the learning event
        pass
