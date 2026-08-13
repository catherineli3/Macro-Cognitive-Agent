"""V5.2 Reasoning Pipeline Schemas — Typed outputs for each reasoning stage.

Every stage in the 10-step pipeline produces a structured output object.
This enforces reasoning discipline — no skipping, no jumping to conclusions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# ── Stage Status ──────────────────────────────────────────────────────


class StageStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ── Stage Output Objects ──────────────────────────────────────────────


@dataclass
class ObservationOutput:
    """Stage 1: What do we observe in the macro data and market today?"""

    stage_id: str = field(default_factory=lambda: f"obs_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Key observations ranked by importance
    observations: list[str] = field(default_factory=list)

    # Data points that stand out (surprises, deviations from trend)
    data_surprises: list[str] = field(default_factory=list)

    # Market moves that stand out
    market_moves: list[str] = field(default_factory=list)

    # News items of significance
    significant_news: list[str] = field(default_factory=list)

    # Overall macro snapshot summary (2-3 sentences)
    macro_snapshot: str = ""

    # Data sources referenced
    sources: list[str] = field(default_factory=list)

    status: StageStatus = StageStatus.PENDING
    reasoning_trace: str = ""


@dataclass
class EvidenceOutput:
    """Stage 2: What evidence supports or contradicts our observations?"""

    stage_id: str = field(default_factory=lambda: f"evd_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Evidence clusters by theme
    evidence_clusters: dict[str, list[str]] = field(default_factory=dict)

    # Supporting evidence (confirms the observation narrative)
    supporting_evidence: list[str] = field(default_factory=list)

    # Contradicting evidence (challenges the observation narrative)
    contradicting_evidence: list[str] = field(default_factory=list)

    # Neutral / ambiguous evidence
    neutral_evidence: list[str] = field(default_factory=list)

    # Net evidence weight (+1 strongly supports, -1 strongly contradicts)
    net_weight: float = 0.0

    # Evidence gaps — what data is missing?
    evidence_gaps: list[str] = field(default_factory=list)

    status: StageStatus = StageStatus.PENDING
    reasoning_trace: str = ""


@dataclass
class PatternOutput:
    """Stage 3: What patterns or regime signals do we see?"""

    stage_id: str = field(default_factory=lambda: f"pat_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Identified patterns (e.g., "reflation", "stagflation", "goldilocks")
    patterns: list[str] = field(default_factory=list)

    # Current macro regime diagnosis
    regime_diagnosis: str = ""

    # Regime transition signals
    regime_transition_signals: list[str] = field(default_factory=list)

    # Pattern strength (0-1)
    pattern_confidence: float = 0.0

    # What patterns are NOT present (negative patterns)
    absent_patterns: list[str] = field(default_factory=list)

    status: StageStatus = StageStatus.PENDING
    reasoning_trace: str = ""


@dataclass
class AnalogyOutput:
    """Stage 4: What does history tell us about similar situations?"""

    stage_id: str = field(default_factory=lambda: f"ana_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Historical analogies with year/period
    analogies: list[dict[str, str]] = field(default_factory=list)
    # Each analogy: {"period": "1994-1995", "description": "...", "similarity": "high/medium/low"}

    # Key lessons from each analogy
    lessons: list[str] = field(default_factory=list)

    # How is today different from the analogies?
    differences: list[str] = field(default_factory=list)

    # Best-fit analogy
    best_analogy: str = ""

    # Analogy confidence
    analogy_confidence: float = 0.0

    status: StageStatus = StageStatus.PENDING
    reasoning_trace: str = ""


@dataclass
class HypothesisOutput:
    """Stage 5: What is our causal hypothesis?"""

    stage_id: str = field(default_factory=lambda: f"hyp_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Primary hypothesis (causal chain: "Because X → Y → Z")
    primary_hypothesis: str = ""

    # Causal mechanism (the "why" — not just correlation)
    causal_mechanism: str = ""

    # Supporting logic chain (step by step)
    logic_chain: list[str] = field(default_factory=list)

    # Alternative hypotheses considered
    alternative_hypotheses: list[str] = field(default_factory=list)

    # Why primary is preferred over alternatives
    preference_rationale: str = ""

    # Confidence in hypothesis (0-1, calibrated)
    hypothesis_confidence: float = 0.0

    status: StageStatus = StageStatus.PENDING
    reasoning_trace: str = ""


@dataclass
class CounterOutput:
    """Stage 6: What could prove our hypothesis wrong?"""

    stage_id: str = field(default_factory=lambda: f"cnt_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Primary counterargument
    primary_counter: str = ""

    # Counter with supporting reasoning
    counter_arguments: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"claim": "", "evidence": [], "severity": "fatal/major/minor", "probability": 0.0}

    # What evidence would invalidate our hypothesis?
    invalidation_conditions: list[str] = field(default_factory=list)

    # Which counters are we most worried about?
    most_concerning_counter: str = ""

    # Why we still prefer our hypothesis despite these counters
    why_still_preferred: str = ""

    status: StageStatus = StageStatus.PENDING
    reasoning_trace: str = ""


@dataclass
class PredictionOutput:
    """Stage 7: What do we forecast?"""

    stage_id: str = field(default_factory=lambda: f"prd_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Predictions with probability and time horizon
    predictions: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"claim": "", "probability": 0.0, "horizon": "", "conditions": [], "invalidation": ""}

    # Probability calibration notes
    calibration_notes: str = ""

    # Confidence intervals where applicable
    confidence_intervals: dict[str, tuple[float, float]] = field(default_factory=dict)

    # What would change our forecast?
    forecast_dependencies: list[str] = field(default_factory=list)

    status: StageStatus = StageStatus.PENDING
    reasoning_trace: str = ""


@dataclass
class TradeOutput:
    """Stage 8: How do we express this view in markets?"""

    stage_id: str = field(default_factory=lambda: f"trd_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Trade expressions (can be multiple for different horizons/convictions)
    trades: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"description": "", "direction": "", "instrument": "",
    #         "size_hint": "", "entry": "", "stop": "", "target": "",
    #         "conviction": 0.0, "horizon": ""}

    # Portfolio-level positioning (not individual trades)
    portfolio_positioning: str = ""

    # Key trades to avoid
    trades_to_avoid: list[str] = field(default_factory=list)

    # Execution considerations
    execution_notes: str = ""

    status: StageStatus = StageStatus.PENDING
    reasoning_trace: str = ""


@dataclass
class RiskOutput:
    """Stage 9: What are the risks and what do we monitor?"""

    stage_id: str = field(default_factory=lambda: f"rsk_{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Key risks ranked by severity × probability
    risks: list[dict[str, Any]] = field(default_factory=list)
    # Each: {"risk": "", "severity": "fatal/major/minor", "probability": 0.0,
    #         "impact": "", "hedge": "", "monitor": ""}

    # Tail risks (low probability, high impact)
    tail_risks: list[str] = field(default_factory=list)

    # Correlation risks (what correlations might break?)
    correlation_risks: list[str] = field(default_factory=list)

    # Watchlist for next 24 hours
    watchlist_24h: list[str] = field(default_factory=list)

    # Watchlist for next week
    watchlist_1w: list[str] = field(default_factory=list)

    # Key data releases to watch
    key_data_releases: list[str] = field(default_factory=list)

    status: StageStatus = StageStatus.PENDING
    reasoning_trace: str = ""


# ── Pipeline State ────────────────────────────────────────────────────


@dataclass
class StageResult:
    """Container for a single stage's execution result."""

    stage_name: str
    status: StageStatus
    output: Any = None
    error: str = ""
    duration_seconds: float = 0.0
    started_at: str = ""
    completed_at: str = ""


@dataclass
class PipelineState:
    """Full pipeline execution state, tracking progress through all stages."""

    pipeline_id: str = field(default_factory=lambda: f"pp_{uuid.uuid4().hex[:8]}")
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Stage results in order
    observation: StageResult | None = None
    evidence: StageResult | None = None
    pattern: StageResult | None = None
    analogy: StageResult | None = None
    hypothesis: StageResult | None = None
    counter: StageResult | None = None
    prediction: StageResult | None = None
    trade: StageResult | None = None
    risk: StageResult | None = None

    # Pipeline metadata
    current_stage: int = 0
    total_stages: int = 9
    completed_at: str = ""
    total_duration_seconds: float = 0.0

    # Quality checks
    stage_validation_results: dict[str, bool] = field(default_factory=dict)

    def all_completed(self) -> bool:
        """Check if all stages completed successfully."""
        stages = [
            self.observation,
            self.evidence,
            self.pattern,
            self.analogy,
            self.hypothesis,
            self.counter,
            self.prediction,
            self.trade,
            self.risk,
        ]
        return all(s is not None and s.status == StageStatus.COMPLETED for s in stages)

    def get_output(self, stage_name: str) -> Any:
        """Get the output of a specific stage."""
        result = getattr(self, stage_name, None)
        return result.output if result else None

    def progress_pct(self) -> float:
        """Pipeline completion percentage."""
        completed = sum(
            1
            for s in [
                self.observation,
                self.evidence,
                self.pattern,
                self.analogy,
                self.hypothesis,
                self.counter,
                self.prediction,
                self.trade,
                self.risk,
            ]
            if s is not None and s.status == StageStatus.COMPLETED
        )
        return completed / self.total_stages * 100
