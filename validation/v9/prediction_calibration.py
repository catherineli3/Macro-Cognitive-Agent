# =============================================================================
# V9 Enhanced Prediction Ledger — Error Diagnosis & Calibration v2
# =============================================================================
# Extends V5.1/V3.4 PredictionRegistry.
# Every prediction → saved → timed → evaluated → error diagnosed → learned.
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import json
import os


class ErrorType(str, Enum):
    WRONG_DATA = "wrong_data"           # Used incorrect/incomplete data
    WRONG_REGIME = "wrong_regime"        # Misidentified macro regime
    WRONG_NARRATIVE = "wrong_narrative"  # Wrong dominant narrative
    WRONG_CAUSALITY = "wrong_causality"  # Incorrect cause→effect chain
    WRONG_TIMING = "wrong_timing"        # Right direction, wrong timing
    BLACK_SWAN = "black_swan"            # Unpredictable exogenous event
    OVERCONFIDENCE = "overconfidence"    # Confidence too high
    UNDERCONFIDENCE = "underconfidence"  # Confidence too low
    CORRECT = "correct"                  # Prediction was right


class PredictionStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIAL = "partial"


@dataclass
class ErrorDiagnosis:
    """Root cause analysis of prediction error."""
    prediction_id: str = ""
    error_types: list[ErrorType] = field(default_factory=list)
    primary_error: ErrorType = ErrorType.CORRECT

    # What went wrong
    reasoning_flaw: str = ""      # Specific flaw in reasoning
    narrative_error: str = ""     # Wrong narrative interpretation
    belief_error: str = ""        # Which belief was wrong
    evidence_error: str = ""      # Missing or misinterpreted evidence
    regime_error: str = ""        # Regime misidentification
    timing_error: str = ""        # Why timing was off

    # What should have been different
    corrective_action: str = ""   # How to fix this type of error
    learning_priority: str = "medium"  # high / medium / low

    diagnosis_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class PredictionRecord:
    """A single prediction with full lifecycle tracking."""
    prediction_id: str
    timestamp: str                  # When prediction was made
    belief_name: str                # Which belief drove this
    confidence: float               # 0-1
    expected_outcome: str           # What was expected
    time_window: str                # e.g. "30d", "90d", "6m"
    expiration_date: str            # When to evaluate

    # Supporting reasoning
    causal_chain: list[str] = field(default_factory=list)
    key_assumptions: list[str] = field(default_factory=list)

    # Outcome
    status: PredictionStatus = PredictionStatus.PENDING
    actual_result: str = ""         # What actually happened
    was_correct: Optional[bool] = None
    error_diagnosis: Optional[ErrorDiagnosis] = None

    # Calibration
    brier_score: float = 0.0        # (confidence - outcome)^2
    surprise_measure: float = 0.0   # How surprising was outcome vs confidence


class EnhancedPredictionLedger:
    """V9 prediction ledger with full error diagnosis and calibration."""

    def __init__(self, storage_dir: str = "data/predictions"):
        self.storage_dir = storage_dir
        self.records: dict[str, PredictionRecord] = {}
        self._ensure_storage()

    def _ensure_storage(self):
        os.makedirs(self.storage_dir, exist_ok=True)

    # ── Record Management ────────────────────────────────────────────

    def record(self, prediction_id: str, belief_name: str, confidence: float,
               expected_outcome: str, time_window: str, causal_chain: list[str] = None,
               key_assumptions: list[str] = None) -> PredictionRecord:
        """Create a new prediction record."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)

        # Calculate expiration
        unit = time_window[-1] if time_window else "d"
        amount = int(time_window[:-1]) if len(time_window) > 1 else 30
        if unit == "d":
            delta = timedelta(days=amount)
        elif unit == "m":
            delta = timedelta(days=amount * 30)
        elif unit == "y":
            delta = timedelta(days=amount * 365)
        else:
            delta = timedelta(days=30)

        record = PredictionRecord(
            prediction_id=prediction_id,
            timestamp=now.isoformat(),
            belief_name=belief_name,
            confidence=min(max(confidence, 0.0), 1.0),
            expected_outcome=expected_outcome,
            time_window=time_window,
            expiration_date=(now + delta).isoformat(),
            causal_chain=causal_chain or [],
            key_assumptions=key_assumptions or [],
        )
        self.records[prediction_id] = record
        return record

    def evaluate(self, prediction_id: str, actual_result: str,
                 was_correct: Optional[bool] = None) -> Optional[ErrorDiagnosis]:
        """Evaluate a prediction against actual outcome."""
        record = self.records.get(prediction_id)
        if not record:
            return None

        record.actual_result = actual_result

        # Determine correctness
        if was_correct is None:
            was_correct = self._auto_determine_correctness(record.expected_outcome, actual_result)

        record.was_correct = was_correct
        record.status = PredictionStatus.CORRECT if was_correct else PredictionStatus.INCORRECT

        # Calculate calibration metrics
        outcome_binary = 1.0 if was_correct else 0.0
        record.brier_score = (record.confidence - outcome_binary) ** 2
        record.surprise_measure = abs(record.confidence - outcome_binary)

        # Diagnose errors
        if not was_correct:
            record.error_diagnosis = self.diagnose_error(record, actual_result)

        return record.error_diagnosis

    def diagnose_error(self, record: PredictionRecord, actual_result: str) -> ErrorDiagnosis:
        """Diagnose root cause of prediction error."""
        diag = ErrorDiagnosis(prediction_id=record.prediction_id)

        # Rule-based error classification
        actual_lower = actual_result.lower()
        expected_lower = record.expected_outcome.lower()

        # 1. Check if right direction but wrong timing
        if self._same_direction(expected_lower, actual_lower):
            diag.error_types.append(ErrorType.WRONG_TIMING)
            diag.timing_error = "Direction correct but timing off"
            diag.primary_error = ErrorType.WRONG_TIMING
        else:
            # 2. Check for black swan (exogenous shock)
            black_swan_signals = ["unexpected", "surprise", "exogenous", "shock", "pandemic", "war", "earthquake"]
            if any(w in actual_lower for w in black_swan_signals):
                diag.error_types.append(ErrorType.BLACK_SWAN)
                diag.primary_error = ErrorType.BLACK_SWAN
            else:
                # 3. Regime or narrative error
                diag.error_types.append(ErrorType.WRONG_NARRATIVE)
                diag.narrative_error = "Narrative diverged from reality"
                diag.primary_error = ErrorType.WRONG_NARRATIVE

        # 4. Check overconfidence
        if record.confidence > 0.8:
            diag.error_types.append(ErrorType.OVERCONFIDENCE)
            diag.reasoning_flaw = f"Confidence {record.confidence:.0%} too high for accuracy"

        # Build corrective action
        diag.corrective_action = self._suggest_correction(diag)
        diag.learning_priority = "high" if record.confidence > 0.7 else "medium"

        return diag

    # ── Calibration Metrics ──────────────────────────────────────────

    @property
    def calibration_stats(self) -> dict:
        """Overall calibration statistics."""
        evaluated = [r for r in self.records.values() if r.was_correct is not None]
        if not evaluated:
            return {"count": 0, "accuracy": 0, "ece": 0, "brier": 0}

        n = len(evaluated)
        accuracy = sum(1 for r in evaluated if r.was_correct) / n
        avg_brier = sum(r.brier_score for r in evaluated) / n

        # Expected Calibration Error (ECE)
        ece = self._calculate_ece(evaluated)

        return {
            "total_predictions": len(self.records),
            "evaluated": n,
            "pending": len(self.records) - n,
            "accuracy": round(accuracy, 3),
            "brier_score": round(avg_brier, 4),
            "ece": round(ece, 4),
        }

    def _calculate_ece(self, records: list[PredictionRecord]) -> float:
        """Calculate Expected Calibration Error (ECE)."""
        bins = [0.0, 0.5, 0.7, 0.85, 1.01]
        ece = 0.0
        n = len(records)

        for i in range(len(bins) - 1):
            bin_records = [r for r in records if bins[i] <= r.confidence < bins[i + 1]]
            if bin_records:
                bin_accuracy = sum(1 for r in bin_records if r.was_correct) / len(bin_records)
                bin_confidence = sum(r.confidence for r in bin_records) / len(bin_records)
                weight = len(bin_records) / n
                ece += weight * abs(bin_accuracy - bin_confidence)

        return ece

    @property
    def error_distribution(self) -> dict:
        """Distribution of error types."""
        dist = {e.value: 0 for e in ErrorType}
        for r in self.records.values():
            if r.error_diagnosis:
                for et in r.error_diagnosis.error_types:
                    dist[et.value] += 1
        return dist

    @property
    def learning_insights(self) -> list[str]:
        """Extract learning insights from error patterns."""
        insights = []

        # Overconfidence pattern
        wrong_high_conf = [r for r in self.records.values()
                          if r.was_correct is False and r.confidence > 0.8]
        if wrong_high_conf and len(wrong_high_conf) >= 2:
            insights.append(f"Overconfidence pattern: {len(wrong_high_conf)} wrong predictions with >80% confidence")

        # Timing error pattern
        timing_errors = [r for r in self.records.values()
                        if r.error_diagnosis and ErrorType.WRONG_TIMING in r.error_diagnosis.error_types]
        if timing_errors and len(timing_errors) >= 2:
            insights.append(f"Timing error pattern: {len(timing_errors)} predictions had right direction, wrong timing")

        # Regime errors
        regime_errors = [r for r in self.records.values()
                        if r.error_diagnosis and ErrorType.WRONG_REGIME in r.error_diagnosis.error_types]
        if regime_errors:
            insights.append(f"Regime misidentification: {len(regime_errors)} times agent got regime wrong")

        return insights

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _auto_determine_correctness(expected: str, actual: str) -> bool:
        """Simple heuristic to determine if prediction was correct."""
        exp_l = expected.lower()
        act_l = actual.lower()
        # Check overlap of key words
        exp_words = set(exp_l.split()) - {"the", "a", "an", "is", "was", "will", "should"}
        act_words = set(act_l.split()) - {"the", "a", "an", "is", "was", "will", "should"}
        overlap = len(exp_words.intersection(act_words))
        total = max(len(exp_words), 1)
        return overlap / total > 0.3

    @staticmethod
    def _same_direction(expected: str, actual: str) -> bool:
        """Check if both predict same direction."""
        bull_words = ["bullish", "rally", "up", "rise", "growth", "positive", "recovery", "gain"]
        bear_words = ["bearish", "decline", "down", "fall", "negative", "recession", "crash", "selloff"]

        exp_bull = any(w in expected for w in bull_words)
        exp_bear = any(w in expected for w in bear_words)
        act_bull = any(w in actual for w in bull_words)
        act_bear = any(w in actual for w in bear_words)

        return (exp_bull == act_bull) and (exp_bear == act_bear)

    @staticmethod
    def _suggest_correction(diagnosis: ErrorDiagnosis) -> str:
        """Suggest how to correct this type of error."""
        suggestions = {
            ErrorType.WRONG_TIMING: "Wait for confirming data points before committing. Use momentum indicators.",
            ErrorType.WRONG_REGIME: "Review regime detection rules. Check monetary + fiscal + growth + inflation alignment.",
            ErrorType.WRONG_NARRATIVE: "Chart narrative competition: which narrative has more supporting evidence?",
            ErrorType.WRONG_CAUSALITY: "Trace cause→effect chain. Look for correlation vs causation traps.",
            ErrorType.OVERCONFIDENCE: "Reduce confidence by 10-20%. Acknowledge tail risks explicitly.",
            ErrorType.BLACK_SWAN: "No correction needed for black swans. Add tail hedge awareness.",
            ErrorType.WRONG_DATA: "Verify data sources. Check for revisions, seasonal adjustments.",
        }
        primary = diagnosis.primary_error
        return suggestions.get(primary, "Review entire reasoning chain for systematic bias")

    # ── Persistence ──────────────────────────────────────────────────

    def save(self, filename: str = "prediction_ledger.json"):
        path = os.path.join(self.storage_dir, filename)
        data = {
            pid: {
                "prediction_id": r.prediction_id,
                "timestamp": r.timestamp,
                "belief_name": r.belief_name,
                "confidence": r.confidence,
                "expected_outcome": r.expected_outcome,
                "time_window": r.time_window,
                "expiration_date": r.expiration_date,
                "status": r.status.value,
                "actual_result": r.actual_result,
                "was_correct": r.was_correct,
                "brier_score": r.brier_score,
                "error_types": [e.value for e in r.error_diagnosis.error_types] if r.error_diagnosis else [],
            }
            for pid, r in self.records.items()
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, filename: str = "prediction_ledger.json"):
        path = os.path.join(self.storage_dir, filename)
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for pid, d in data.items():
            r = PredictionRecord(
                prediction_id=d["prediction_id"],
                timestamp=d["timestamp"],
                belief_name=d["belief_name"],
                confidence=d["confidence"],
                expected_outcome=d["expected_outcome"],
                time_window=d["time_window"],
                expiration_date=d["expiration_date"],
                status=PredictionStatus(d["status"]),
                actual_result=d.get("actual_result", ""),
                was_correct=d.get("was_correct"),
                brier_score=d.get("brier_score", 0),
            )
            self.records[pid] = r
