"""Outcome Tracker — tracks predictions and links outcomes to theses (Milestone D, D6.1).

Responsibilities:
    1. Record predictions made during a cycle
    2. Check outcomes against actual market data
    3. Detect which invalidation conditions have been triggered
    4. Link outcomes back to theses for the postmortem
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.schemas.research_thesis import ResearchThesis, ThesisOutcome
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PendingThesis:
    """A thesis awaiting market validation."""

    thesis_id: str
    thesis_title: str
    invalidation_conditions: list[str] = field(default_factory=list)
    expected_window: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    prediction_count: int = 0
    predictions: list = field(default_factory=list)

    @property
    def is_overdue(self) -> bool:
        """Check if expected window has passed (simple heuristic)."""
        elapsed = (datetime.now(UTC) - self.created_at).days
        # Parse window like "30-90 days"
        window = self.expected_window.lower().replace("days", "").strip()
        try:
            parts = window.split("-")
            max_days = int(parts[-1].strip())
            return elapsed > max_days
        except (ValueError, IndexError):
            return elapsed > 90  # Default: 90 days


class OutcomeTracker:
    """Tracks thesis outcomes and invalidation condition checks.

    Works alongside the prediction engine — registers predictions as they
    are made, then checks outcomes when market data arrives.
    """

    def __init__(self):
        self._pending: dict[str, PendingThesis] = {}
        self._completed: dict[str, ThesisOutcome] = {}
        self._history: list[tuple[str, ThesisOutcome]] = []

    # ── Registration ────────────────────────────────────────────────────

    def register_thesis(
        self, thesis: ResearchThesis, predictions: list | None = None
    ) -> PendingThesis:
        """Register a thesis for outcome tracking.

        Args:
            thesis: The thesis to track
            predictions: Optional prediction batch from the prediction engine

        Returns:
            PendingThesis tracking object
        """
        # Unwrap PredictionBatch if needed (it stores predictions in .predictions list)
        pred_list = predictions
        if pred_list is not None and hasattr(pred_list, "predictions"):
            pred_list = pred_list.predictions

        pending = PendingThesis(
            thesis_id=thesis.thesis_id,
            thesis_title=thesis.title,
            invalidation_conditions=list(thesis.invalidation_conditions),
            expected_window=thesis.expected_window,
            prediction_count=len(pred_list) if pred_list else 0,
            predictions=list(pred_list) if pred_list else [],
        )
        self._pending[thesis.thesis_id] = pending
        logger.info(
            "Tracking thesis '%s' (%d predictions, %d conditions)",
            thesis.title[:60],
            pending.prediction_count,
            len(pending.invalidation_conditions),
        )
        return pending

    def record_prediction_outcome(self, thesis_id: str, prediction_id: str, correct: bool) -> None:
        """Record the outcome of a single prediction linked to a thesis."""
        pending = self._pending.get(thesis_id)
        if pending:
            for p in pending.predictions:
                if hasattr(p, "prediction_id") and p.prediction_id == prediction_id:
                    setattr(p, "_correct", correct)
                    break

    # ── Outcome Determination ───────────────────────────────────────────

    def determine_outcome(
        self,
        thesis: ResearchThesis,
        actual_data: dict[str, float],
        diagnosis_notes: str = "",
    ) -> ThesisOutcome:
        """Determine the outcome of a thesis based on actual market data.

        Checks:
            1. Did any invalidation condition trigger?
            2. Did the market move in the thesis direction?
            3. Is the thesis window expired?

        Args:
            thesis: The thesis being evaluated
            actual_data: Dict of indicator → actual value
            diagnosis_notes: Optional notes from the diagnosis engine

        Returns:
            ThesisOutcome with verification status
        """
        triggered = self.check_invalidation(thesis.thesis_id, actual_data)

        if triggered:
            outcome = ThesisOutcome(
                thesis_id=thesis.thesis_id,
                verified=False,
                invalidation_triggered=triggered,
                actual_events=[f"Invalidation condition triggered: {triggered}"],
                notes=diagnosis_notes or f"Thesis invalidated by {triggered}",
            )
            thesis.invalidate(triggered, outcome)
            logger.info("Thesis %s INVALIDATED: %s", thesis.thesis_id, triggered)
        else:
            # Check if thesis was directionally correct
            directional_correct = self._check_direction(thesis, actual_data)

            outcome = ThesisOutcome(
                thesis_id=thesis.thesis_id,
                verified=directional_correct,
                invalidation_triggered=None,
                transmission_verified=None,  # Postmortem will determine
                timing_correct=None,
                notes=diagnosis_notes
                or (
                    "Thesis validated: market moved in expected direction."
                    if directional_correct
                    else "Thesis not invalidated but directional outcome unclear."
                ),
            )
            if directional_correct:
                thesis.validate(outcome)
                logger.info("Thesis %s VALIDATED", thesis.thesis_id)
            else:
                thesis.invalidate("directional outcome not met", outcome)
                logger.info(
                    "Thesis %s: no invalidation triggered, but direction wrong", thesis.thesis_id
                )

        # Move from pending to completed
        self._completed[thesis.thesis_id] = outcome
        self._history.append((thesis.thesis_id, outcome))
        self._pending.pop(thesis.thesis_id, None)

        return outcome

    def check_invalidation(self, thesis_id: str, actual_data: dict[str, float]) -> str | None:
        """Check if any invalidation condition has been triggered.

        Parses conditions like:
            - "10Y Treasury yield exceeds 4.75%"
            - "S&P 500 drops below 4680"
            - "VIX spikes above 30"

        Args:
            thesis_id: The thesis ID to check
            actual_data: Dict of indicator → current value

        Returns:
            The triggered condition string, or None if none triggered
        """
        pending = self._pending.get(thesis_id)
        if not pending:
            logger.debug("No pending thesis found for %s", thesis_id)
            return None

        for condition in pending.invalidation_conditions:
            if self._condition_triggered(condition, actual_data):
                logger.info("Invalidation condition triggered: '%s'", condition)
                return condition

        return None

    def _condition_triggered(self, condition: str, actual_data: dict[str, float]) -> bool:
        """Check if a specific condition is met by actual data.

        Parses natural language conditions against data.
        """
        cond_lower = condition.lower()

        # 10Y yield
        if "10y" in cond_lower or "treasury yield" in cond_lower:
            us10y = actual_data.get("us10y", 0)
            if us10y and "exceeds" in cond_lower:
                threshold = self._extract_number(condition)
                if threshold and us10y > threshold:
                    return True

        # S&P 500 / SPX
        if "s&p" in cond_lower or "spx" in cond_lower or "sp500" in cond_lower:
            spx = actual_data.get("spx", 0)
            if spx and "drops below" in cond_lower or "below" in cond_lower:
                threshold = self._extract_number(condition)
                if threshold and spx < threshold:
                    return True

        # VIX
        if "vix" in cond_lower:
            vix = actual_data.get("vix", 0)
            if vix and ("spikes above" in cond_lower or "above" in cond_lower):
                threshold = self._extract_number(condition)
                if threshold and vix > threshold:
                    return True

        # DXY
        if "dxy" in cond_lower:
            dxy = actual_data.get("dxy", 0)
            if dxy and "breaks above" in cond_lower or "above" in cond_lower:
                threshold = self._extract_number(condition)
                if threshold and dxy > threshold:
                    return True

        # Credit spread
        if "credit spread" in cond_lower:
            hyg = actual_data.get("hyg", 0)
            if hyg:
                threshold = self._extract_number(condition)
                if threshold and hyg < threshold:
                    return True

        # CPI check
        if "cpi" in cond_lower:
            cpi = actual_data.get("cpi", actual_data.get("cpi_yoy", 0))
            if cpi:
                threshold = self._extract_number(condition)
                if "above" in cond_lower and threshold and cpi > threshold:
                    return True
                if "below" in cond_lower and threshold and cpi < threshold:
                    return True

        # Fed rate check
        if "rate hike" in cond_lower or "rate cut" in cond_lower or "fed" in cond_lower:
            fed_rate = actual_data.get("fed_rate", actual_data.get("fedfunds", 0))
            if fed_rate and "hike" in cond_lower:
                threshold = self._extract_number(condition)
                if threshold and fed_rate > threshold:
                    return True

        return False

    @staticmethod
    def _extract_number(text: str) -> float | None:
        """Extract a numeric threshold from a condition string.

        Heuristic: returns the LAST number that is not part of a bond
        maturity label (e.g. "10Y"). Thresholds tend to appear near the
        end of conditions ("S&P 500 drops below 4,680") while proper-name
        numbers ("S&P 500") appear earlier.
        """
        import re

        matches = re.findall(r"[\d,.]+", text)
        for m in reversed(matches):
            m_pos = text.find(m)
            after = text[m_pos + len(m) : m_pos + len(m) + 2].strip()
            if after.startswith("Y"):  # "10Y Treasury"
                continue
            cleaned = m.replace(",", "").replace("$", "")
            try:
                return float(cleaned)
            except ValueError:
                continue
        return None

    @staticmethod
    def _check_direction(thesis: ResearchThesis, actual_data: dict[str, float]) -> bool:
        """Check if market moved in the thesis direction based on core belief."""
        belief = thesis.core_belief.lower()

        # Growth acceleration thesis
        if "growth" in belief or "accelerating" in belief:
            gdp = actual_data.get("gdp", actual_data.get("gdp_qoq", 0))
            prev_gdp = actual_data.get("prev_gdp", 0)
            return gdp > prev_gdp

        # Liquidity / easing thesis: check if credit spreads tightened
        if "liquidity" in belief or "easing" in belief or "credit" in belief:
            hyg = actual_data.get("hyg", actual_data.get("credit", 0))
            prev_hyg = actual_data.get("prev_hyg", 0)
            if hyg and prev_hyg:
                return hyg > prev_hyg  # HYG up = spreads tightening

        # Risk-on thesis
        spx = actual_data.get("spx", 0)
        prev_spx = actual_data.get("prev_spx", 0)
        if spx and prev_spx:
            return spx > prev_spx

        # Default: unclear, assume neutral (not validated, not invalidated)
        return False

    # ── Query ───────────────────────────────────────────────────────────

    def get_pending_theses(self) -> list[str]:
        """Get IDs of theses still awaiting outcome."""
        return list(self._pending.keys())

    def get_completed_theses(self) -> list[str]:
        """Get IDs of theses with determined outcomes."""
        return list(self._completed.keys())

    def get_outcome(self, thesis_id: str) -> ThesisOutcome | None:
        return self._completed.get(thesis_id)

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    def summary(self) -> str:
        return f"OutcomeTracker: {self.pending_count} pending, " f"{self.completed_count} completed"
