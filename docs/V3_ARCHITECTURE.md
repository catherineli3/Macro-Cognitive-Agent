# V3 Architecture Freeze — Adaptive Research Agent

> **Document Type**: Architecture Design Document (Pre-Code Freeze)
> **Version**: 2.2 — Final Freeze
> **Date**: July 2026
> **Status**: Proposed — Awaiting Architecture Review
> **Supersedes**: V3_ARCHITECTURE.md v2.1 (added: Learning Unit, Belief Versioning, Multi-Prediction, Hypothesis Library)

---

## Strategic Reframe (v2.2 — Final)

### The Core Insight

V3 is no longer an engineering project. It is a **Research System** — a system whose primary asset is not code but **accumulated knowledge** about macro-financial causality.

The most common failure mode of research systems: **all modules exist, but no one defined what the system is actually learning.**

### v2.2 Final Freeze Items

In addition to v2.1's six DDRs, four critical design decisions are frozen:

| # | Freeze Item | Core Question Answered |
|---|------------|----------------------|
| 1 | **Learning Unit** | What exactly can the Learning Engine modify? |
| 2 | **Belief Versioning** | How do we trace knowledge evolution? |
| 3 | **Multi-Prediction Model** | Does a hypothesis fail as a whole, or do specific transmission channels fail? |
| 4 | **Hypothesis Library & Score** | What is the long-term asset the system is building? |

With these four, V3 has a complete definition of its **learning object**.

### The System's True Asset

```
Hypothesis Library
       │
       ├── Belief Graph (versioned, weighted, conditional)
       ├── Learning Log (every error, diagnosis, action)
       ├── Error Taxonomy (what fails, how often, why)
       └── Hypothesis Scores (which beliefs are reliable)
```

**Prediction is just the validator. The Hypothesis Library is what grows.**

---

## 1. Architecture Decisions (DDR-V3 v2.2)

Ten DDRs define V3. Six from v2.1 (revised), four new in v2.2.

### DDR-V3-001: Hypothesis-First Architecture (v2.1)

**Decision**: The Hypothesis Generator is V3's optimization target. Prediction is a mandatory validation instrument — not the deliverable. Every hypothesis must produce falsifiable predictions; every prediction must trace back to a hypothesis.

**Rationale**: A system optimizing for prediction accuracy learns to make easy predictions. A system optimizing for hypothesis quality learns to form better causal models.

**Consequences**: PredictionEngine mandatory but subordinate. Every `Prediction` carries non-nullable `source_hypothesis_id`.

### DDR-V3-002: Diagnosis Before Learning (v2.1)

**Decision**: A Diagnosis Engine must classify **why** a prediction failed before any learning action. 6 error categories: `SIGNAL_ERR`, `HYP_ERR`, `EVID_MISSING`, `TIMING_ERR`, `EVENT_ERR`, `WEIGHT_ERR`.

**Rationale**: Without diagnosis, Learning Engine cannot distinguish "fundamentally wrong hypothesis" from "unpredictable event."

**Consequences**: New `DiagnosisEngine` between Outcome and Learning. Learning input is `DiagnosisReport`, not `EvaluationReport`.

### DDR-V3-003: Incremental Belief Evolution (v2.1, extended in v2.2)

**Decision**: The Learning Engine does NOT directly modify rules or replace knowledge. It maintains **five defined properties** on each Belief (see §8: Learning Unit). Updates are progressive, not revolutionary. All Beliefs are **versioned** (see DDR-V3-008).

**Rationale**: Real belief evolution is gradual. "Replace belief" discards partially correct knowledge.

**Consequences**: `AdaptiveBelief` with weight, confidence, preconditions, time horizon, supporting evidence. Learning actions are additive only. Deprecation (not deletion) is strongest action.

### DDR-V3-004: Four-Component KPI System (v2.1)

**Decision**: Four equally-weighted KPIs on rolling 30d/90d/all-time windows: Hypothesis Accuracy, Prediction Error, Confidence Calibration, Learning Speed.

**Rationale**: Single-metric optimization creates perverse incentives. Four KPIs ensure balanced improvement.

### DDR-V3-005: Error Taxonomy as First-Class Knowledge (v2.1)

**Decision**: Every error classified into exactly one taxonomy category. Persisted as append-only `LearningLog`. Minimum 200 entries before PatternLearner activates.

### DDR-V3-006: Diagnosis as the Bridge to Learning (v2.1)

**Decision**: Diagnosis Engine is the only path from Outcome to Learning. No outcome bypasses diagnosis. Diagnosis failure → no learning (safe default).

### DDR-V3-007: Learning Unit — Five Modifiable Attributes ★ NEW v2.2

**Decision**: The Learning Engine is constrained to modify exactly five types of attributes on any Belief. It cannot create, delete, or rewrite rules — only adjust these properties within bounded ranges.

| # | Attribute | What It Means | Example Modification |
|---|-----------|---------------|---------------------|
| 1 | **Weight** | How much to trust this belief (0~1) | 0.85 → 0.81 |
| 2 | **Confidence** | How sure we are about the weight itself | 0.90 → 0.72 |
| 3 | **Preconditions** | When this belief is applicable | Add: `core_cpi > 3%` |
| 4 | **Valid Time Horizon** | How long predictions from this belief remain valid | "3d" → "10d" |
| 5 | **Supporting Evidence** | Which evidence items anchor this belief | Add/remove evidence references |

**Rationale**: Without a bounded Learning Unit, the Learning Engine is a black box. "Update Belief" is too abstract — it allows arbitrary modification. By constraining to exactly 5 attribute types, every learning action is auditable, reversible, and versioned. The system cannot accidentally delete good knowledge.

**Consequences**: Every `LearningAction` must specify which of the 5 attributes it modifies. Any action attempting modification outside these 5 is rejected at the schema level. Learning Engine internals can only call `WeightUpdater`, `ConditionNarrower`, `HorizonAdjuster`, `EvidenceManager`, and `ConfidenceManager` — no other modification paths exist.

### DDR-V3-008: Belief Versioning ★ NEW v2.2

**Decision**: Every Belief carries a monotonic version number and retains its full version history. Learning actions produce new versions; old versions are immutable and queryable.

```
Belief "Higher Yield → Dollar Up"
  v1 (2026-07-01): weight=0.85, horizon=5d, precondition=none
  v2 (2026-07-15): weight=0.81, horizon=5d, precondition=none
       └── Reason: TIMING_ERR × 2, weight reduced
  v3 (2026-08-01): weight=0.83, horizon=10d, precondition=none
       └── Reason: Correct after horizon extension, weight recovered
  v4 (2026-08-20): weight=0.83, horizon=10d, precondition="core_cpi > 3%"
       └── Reason: EVID_MISSING during low-inflation regime
```

**Rationale**: A research system must be able to answer "why do I believe this today?" Without versioning, belief evolution is lost — the system can only report its current state, not its reasoning journey. Versioning enables: (a) audit trails for every belief change, (b) rollback if learning degrades performance, (c) comparing belief trajectories across different market regimes, and (d) V4's "explain your reasoning" feature.

**Consequences**: `BeliefVersion` schema: `version_number`, `created_at`, `change_reason`, `diagnosis_report_id` (which diagnosis triggered this), `before_snapshot`, `after_snapshot`. `AdaptiveBelief.current_version` → `BeliefVersion`. `AdaptiveBelief.version_history: list[BeliefVersion]`. Immutable — old versions never modified.

### DDR-V3-009: Multi-Prediction Model ★ NEW v2.2

**Decision**: One Hypothesis generates multiple predictions across related assets — not just one. Outcomes and Diagnosis are evaluated **per individual prediction**, not at the hypothesis level. A hypothesis is not "right" or "wrong" — specific transmission channels within it succeed or fail.

```
Hypothesis: "Liquidity Tightening"
  ├── Prediction 1 (Primary):   NASDAQ ↓   →  ✓  Direction correct
  ├── Prediction 2 (Secondary): USD ↑      →  ✗  Direction wrong
  └── Prediction 3 (Tertiary):  Gold ↓     →  ✓  Direction correct

Learning insight: The hypothesis is partially valid. 
The Dollar transmission channel failed — investigate why.
Not: "The entire hypothesis is wrong."
```

**Rationale**: Macro hypotheses naturally affect multiple assets. A single-prediction model conflates "hypothesis quality" with "specific transmission channel reliability." If a Liquidity Tightening hypothesis correctly predicts Nasdaq and Gold moves but misses Dollar, the correct learning action is "narrow the Dollar transmission condition" — not "reduce the entire hypothesis weight."

**Consequences**: `Prediction` schema extended with `prediction_tier: "primary" | "secondary" | "tertiary"` and `transmission_channel: str` (e.g., "liquidity→equity", "liquidity→fx"). `PredictionBatch` groups by `source_hypothesis_id`. `EvaluationReport.accuracy_by_hypothesis` complemented by `accuracy_by_channel`. Learning actions operate per-transmission-channel, not per-hypothesis.

### DDR-V3-010: Hypothesis Library & Score ★ NEW v2.2

**Decision**: A new `HypothesisLibrary` module maintains every hypothesis with a composite `HypothesisScore` that aggregates five dimensions. This is the system's long-term intellectual asset — the Agent's goal is to maximize Hypothesis Library quality, not prediction count.

```
HypothesisScore = f(
    Prediction Accuracy,    # How often are this hypothesis's predictions correct?
    Evidence Quality,       # How strong is the evidence anchoring it?
    Calibration,            # How well-calibrated are its confidence estimates?
    Consistency,            # How stable is its accuracy across cycles?
    Learning History        # Has it improved over time?
)
```

**Rationale**: Without a Hypothesis Library, the system is stateless between runs — every pipeline execution starts from scratch with V2 rules and weights. With a Library, the Agent accumulates knowledge: hypotheses that prove reliable across many cycles earn high scores; hypotheses that consistently fail are deprecated. The Library is what makes the Agent actually "learn" over weeks and months, not just adjust weights within a single session.

**Consequences**: New `HypothesisLibrary` module with CRUD for scored hypotheses. `HypothesisScore` schema with 5 sub-scores. KPI-1 (Hypothesis Accuracy) directly derived from Library scores. Library persisted to `data/hypothesis_library/`. Hypothesis Generator queries Library before forming new hypotheses — reuses high-score beliefs, avoids deprecated ones.

---

### DDR Consistency with V2

| V3 DDR | V2 Precedent | Relationship |
|--------|-------------|--------------|
| V3-001: Hypothesis-First | DDR-010 (Schema First) | Hypothesis quality is the schema of research output |
| V3-002: Diagnosis Before Learning | DDR-v2.2 (EMA Update) | Replaces blind EMA with diagnosis-gated update |
| V3-003: Incremental Belief | DDR-v2.2 (EMA Update) | Extends EMA to 5 Learning Unit attributes |
| V3-004: 4-KPI System | DDR-009 (Outcome Tracking) | Upgrades from 1 metric to 4-KPI dashboard |
| V3-005: Error Taxonomy | DDR-010 (Schema First) | Error classes are first-class schemas |
| V3-006: Diagnosis Bridge | DDR-v2.5 (Graceful Degradation) | Diagnosis failure = no learning |
| V3-007: Learning Unit | DDR-003 (Incremental Belief) | Defines the atom of learning |
| V3-008: Belief Versioning | DDR-v2.1 (Outcome Tracking) | Extends persistence to belief history |
| V3-009: Multi-Prediction | DDR-001 (Layering) | Extends layering to transmission channels |
| V3-010: Hypothesis Library | DDR-009 (Outcome→Learning) | Upgrades from tracking to knowledge accumulation |

---

## 2. Module 0: The Hypothesis Generator (V2 → V3 Target)

### 2.1 What V3 Optimizes

The Hypothesis Generator (V2's `HypothesisEngine`) is the **only cognitive module V3 aims to improve**. All other V3 modules serve this goal. Its output feeds the Hypothesis Library.

```
Signal[] + Evidence[] + HypothesisLibrary ──► Hypothesis Generator ──► HypothesisSet
        (prior beliefs with scores)                    ▲
                                                       │
            ┌──────────────────────────────────────────┘
            │  Calibrated weights, narrowed preconditions,
            │  adjusted time horizons, updated evidence,
            │  versioned belief history
            │
    ┌───────┴────────┐
    │ LEARNING ENGINE │ (5 Learning Unit attributes only)
    └────────────────┘
```

### 2.2 Hypothesis Quality Dimensions

| Quality Dimension | How Measured | Target |
|-------------------|-------------|--------|
| **Validity** | % of predictions directionally correct | ↑ |
| **Precision** | MAE of predictions from this hypothesis | ↓ |
| **Stability** | Variance of accuracy across cycles | ↓ |
| **Calibration** | ECE of predictions from this hypothesis | ↓ |

---

## 3. Module 1: Multi-Prediction Engine ★ EXTENDED v2.2

### 3.1 Purpose

Transform each Hypothesis into a **set of predictions** across multiple correlated assets. One hypothesis = 1~N predictions. Each prediction tests a specific **transmission channel** — the causal mechanism by which the hypothesis affects a particular asset.

### 3.2 Key Principles

> **One hypothesis, multiple predictions, per-channel evaluation.**

> **A hypothesis is not judged as "right" or "wrong" — specific transmission channels within it are.**

### 3.3 Multi-Prediction Mapping Rules

| Hypothesis | Dimension | Direction | Primary | Secondary | Tertiary | Horizon |
|------------|-----------|-----------|---------|-----------|----------|---------|
| Liquidity Tightening | liquidity | tightening | NASDAQ ↓ | USD ↑ | Gold ↓ | 5d |
| Liquidity Easing | liquidity | easing | NASDAQ ↑ | USD ↓ | Gold ↑ | 5d |
| Credit Tightening | credit | tightening | HYG ↓ | SPX ↓ | — | 5d |
| Growth Accelerating | growth | accelerating | SPX ↑ | US10Y ↑ | DXY ↑ | 10d |
| Growth Decelerating | growth | decelerating | SPX ↓ | US10Y ↓ | DXY ↓ | 10d |
| Risk-On | risk_appetite | risk_on | SPX ↑ | VIX ↓ | HYG ↑ | 3d |
| Risk-Off | risk_appetite | risk_off | SPX ↓ | VIX ↑ | HYG ↓ | 3d |
| Inflation Rising | inflation | rising | TIPS ↓ | Gold ↑ | US10Y ↑ | 10d |
| Inflation Falling | inflation | falling | TIPS ↑ | Gold ↓ | US10Y ↓ | 10d |

### 3.4 Prediction Schema (Extended for Multi-Prediction)

```python
class Prediction(BaseModel):
    prediction_id: str
    run_id: str
    created_at: datetime
    # WHAT we predict
    dimension: str
    indicator: str
    direction: str              # "bullish" | "bearish" | "flat"
    prediction_tier: str        # "primary" | "secondary" | "tertiary"  ★ NEW v2.2
    transmission_channel: str   # "liquidity→equity" | "liquidity→fx"   ★ NEW v2.2
    target_range: tuple[float, float] | None
    horizon: str
    evaluate_at: datetime
    # WHY — all non-nullable
    source_hypothesis_id: str
    source_evidence_ids: list[str]
    confidence: float
    rationale: str
    # LIFECYCLE
    status: str = "pending"
    # OUTCOME
    outcome: PredictionOutcome | None = None
    # DIAGNOSIS
    diagnosis: ErrorClassification | None = None

class PredictionBatch(BaseModel):
    batch_id: str
    run_id: str
    predictions: list[Prediction]
    # Grouped views
    by_hypothesis: dict[str, list[Prediction]]    # hypothesis_id → predictions
    by_channel: dict[str, list[Prediction]]        # channel → predictions
```

### 3.5 Why Multi-Prediction Matters for Learning

```
Cycle 1 — Hypothesis "Liquidity Tightening":
  NASDAQ ↓  ✓    (liquidity→equity channel correct)
  USD ↑     ✗    (liquidity→fx channel failed)
  Gold ↓    ✓    (liquidity→commodity channel correct)

Diagnosis: WEIGHT_ERR on liquidity→fx channel
Learning:   Narrow precondition on USD prediction: "only when DXY < 105"
           (Not: reduce entire hypothesis weight)

Cycle 5 — Same hypothesis:
  NASDAQ ↓  ✓
  USD ↑     ✓    (precondition narrowed — now correct in this regime)
  Gold ↓    ✓

Hypothesis Score improves. Belief versioned with narrower, more precise conditions.
```

### 3.6 API

```python
class PredictionEngine:
    async def generate_predictions(
        self,
        hypothesis_set: HypothesisSet,
        calibrated_confidence: CalibratedConfidenceSet,
        evidence_items: list[MacroDataSchema],
        hypothesis_library: HypothesisLibrary,      # ★ NEW v2.2
        run_id: str,
    ) -> PredictionBatch: ...

    async def get_predictions_by_hypothesis(
        self, hypothesis_id: str
    ) -> list[Prediction]: ...

    async def get_channel_accuracy(
        self, channel: str, window_days: int = 90
    ) -> float: ...
```

---

## 4. Module 2: Outcome Evaluation

### 4.1 Purpose

Compare predictions against actual market data **at per-prediction granularity**. Each prediction is evaluated independently; hypothesis-level accuracy is a derived aggregate.

### 4.2 Per-Prediction Comparison Logic

```python
def compare(pred: Prediction, actual: float, prev_value: float) -> PredictionOutcome:
    pct_change = (actual - prev_value) / prev_value
    if pred.direction == "bullish":
        correct = pct_change > 0.001
    elif pred.direction == "bearish":
        correct = pct_change < -0.001
    else:
        correct = abs(pct_change) <= 0.005
    return PredictionOutcome(
        correct=correct,
        predicted_direction=pred.direction,
        actual_direction=_classify(pct_change),
        pct_change=round(pct_change, 6),
        error_magnitude=0.0 if correct else abs(pct_change),
    )
```

### 4.3 Metrics (Per-Channel + Per-Hypothesis)

| Metric | Granularity | Purpose |
|--------|------------|---------|
| Directional Accuracy | Per prediction / per channel / per hypothesis | KPI-2 |
| MAE / RMSE | Per channel / per hypothesis | KPI-2 |
| Brier Score | Per channel / per hypothesis | KPI-3 |
| Channel Accuracy | Per transmission channel | Identify weak channels |
| Hypothesis Accuracy | Aggregate of all predictions for that hypothesis | **KPI-1 input** |

### 4.4 Schema

```python
class PredictionOutcome(BaseModel):
    correct: bool
    predicted_direction: str
    actual_direction: str
    pct_change: float
    error_magnitude: float
    actual_value: float
    evaluated_at: datetime

class EvaluationReport(BaseModel):
    report_id: str
    batch_id: str
    evaluated_at: datetime
    outcomes: list[PredictionOutcome]
    # Aggregate
    directional_accuracy: float
    mean_absolute_error: float
    rmse: float
    brier_score: float
    # Breakdowns
    accuracy_by_dimension: dict[str, float]
    accuracy_by_horizon: dict[str, float]
    accuracy_by_hypothesis: dict[str, float]
    accuracy_by_channel: dict[str, float]          # ★ NEW v2.2
    accuracy_by_confidence_bucket: dict[str, float]
```

---

## 5. Module 3: Diagnosis Engine

### 5.1 Purpose

Diagnose **per prediction** — each prediction gets its own error classification. Hypothesis-level diagnosis patterns are derived, not first-class.

### 5.2 Error Taxonomy (6 categories, unchanged from v2.1)

| Category | Code | Learning Implication |
|----------|------|---------------------|
| Signal Error | `SIGNAL_ERR` | Improve signal quality |
| Hypothesis Error | `HYP_ERR` | Revise transmission channel |
| Evidence Missing | `EVID_MISSING` | Add data source |
| Timing Error | `TIMING_ERR` | Adjust horizon |
| Unexpected Event | `EVENT_ERR` | No weight change |
| Weight Error | `WEIGHT_ERR` | Adjust channel weight |

Correct predictions classified as `CORRECT_STRONG`, `CORRECT_WEAK`, or `CORRECT_LUCKY`.

### 5.3 Per-Prediction Diagnosis

Each error is diagnosed in context of its **transmission channel** — not the hypothesis as a whole. A `HYP_ERR` on `liquidity→fx` does not penalize `liquidity→equity`.

### 5.4 API (unchanged signature from v2.1)

```python
class DiagnosisEngine:
    async def diagnose_batch(
        self, evaluation_report: EvaluationReport
    ) -> DiagnosisReport: ...
    async def get_error_trend(
        self, hypothesis_id: str | None = None,
        channel: str | None = None,               # ★ NEW v2.2
        error_category: str | None = None,
        window_days: int = 90
    ) -> ErrorTrend: ...
```

---

## 6. Error Taxonomy & Learning Log (unchanged from v2.1)

Append-only store of all (prediction → outcome → diagnosis → learning action). Minimum 200 entries before PatternLearner activates. Query by hypothesis, error category, dimension, **transmission channel** (v2.2).

---

## 7. Learning Unit — The Atom of Learning ★ NEW v2.2

### 7.1 The Fundamental Question

> **What exactly can the Learning Engine modify?**

This is the most important architectural question for any research system. Without a bounded answer, "learning" is a black box — weights can change arbitrarily, rules can be rewritten, and no one can trace why.

### 7.2 The Five Learning Unit Attributes

The Learning Engine is permitted to modify **exactly five** attribute types on any Belief. No other modifications are allowed at the schema level.

```
                    ┌─────────────────────────┐
                    │      LEARNING ENGINE     │
                    │  (5 permitted operations) │
                    └───────────┬─────────────┘
                                │
        ┌───────────┬───────────┼───────────┬───────────┐
        ▼           ▼           ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
   │ WEIGHT  │ │CONFIDENCE│ │PRECOND- │ │  TIME   │ │SUPPORTING│
   │         │ │          │ │ITIONS   │ │ HORIZON │ │ EVIDENCE │
   └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
   How much    How sure    When to     How long    What data
   to trust?   about the   use this    is this     anchors
               weight?     belief?     valid?      this belief?
```

### 7.3 Detailed Attribute Definitions

#### Attribute 1: Weight

| Property | Value |
|----------|-------|
| **Type** | `float` (0.0 ~ 1.0) |
| **Meaning** | How much the Hypothesis Generator should trust this belief |
| **Modification** | ±δ per cycle, with δ bounded by diagnosis category |
| **Example** | `0.85 → 0.81` (TIMING_ERR, minor penalty) |

#### Attribute 2: Confidence (Meta-Confidence)

| Property | Value |
|----------|-------|
| **Type** | `float` (0.0 ~ 1.0) |
| **Meaning** | How sure we are about the weight itself |
| **Modification** | Decays on consecutive errors; strengthens on streaks |
| **Example** | `0.90 → 0.72` (3 consecutive prediction failures) |

#### Attribute 3: Preconditions

| Property | Value |
|----------|-------|
| **Type** | `dict[str, Any]` |
| **Meaning** | Conditions under which this belief is applicable |
| **Modification** | Additive only — preconditions can be added or narrowed, never removed |
| **Example** | `{} → {"core_cpi": ">3%", "vix_range": [10, 30]}` |

#### Attribute 4: Valid Time Horizon

| Property | Value |
|----------|-------|
| **Type** | `str` (enum: "1d" / "3d" / "5d" / "10d" / "21d") |
| **Meaning** | How long predictions derived from this belief remain valid |
| **Modification** | Extended or shortened based on TIMING_ERR patterns |
| **Example** | `"3d" → "10d"` (direction correct but materialized later) |

#### Attribute 5: Supporting Evidence

| Property | Value |
|----------|-------|
| **Type** | `list[EvidenceReference]` |
| **Meaning** | Which evidence items anchor this belief |
| **Modification** | Add new evidence; deprecate (not delete) old evidence |
| **Example** | Add `ev-tips-230` when new inflation data confirms the belief |

### 7.4 Prohibited Operations

The following are **architecturally forbidden** — enforced at schema validation:

- ❌ Delete a Belief
- ❌ Rewrite a Belief's causal rule
- ❌ Create a new Belief from scratch (only Hypothesis Generator does this)
- ❌ Modify any attribute not in the Learning Unit
- ❌ Modify weight by more than ±0.15 in a single cycle
- ❌ Remove a precondition (only add/narrow)

### 7.5 Schema

```python
class LearningUnit(BaseModel):
    """Defines what can be modified by Learning Engine."""
    belief_id: str
    
    # The 5 modifiable attributes (all optional — only changed fields present)
    weight_delta: float | None = None               # ± bounded
    confidence_delta: float | None = None
    precondition_change: PreconditionChange | None = None
    horizon_change: str | None = None                # New horizon value
    evidence_change: EvidenceChange | None = None
    
    # Validation
    def validate(self) -> bool:
        """At least one attribute must be changed, no forbidden changes."""
        ...

class PreconditionChange(BaseModel):
    action: str                     # "add" | "narrow" only (no "remove")
    key: str
    value: Any
    old_value: Any | None

class EvidenceChange(BaseModel):
    action: str                     # "add" | "deprecate"
    evidence_id: str
    reason: str
```

---

## 8. Module 4: Learning Engine (Revised for v2.2)

### 8.1 Reframed Purpose

> The Learning Engine modifies Beliefs via the 5 Learning Unit attributes only. Every modification produces a new Belief version.

### 8.2 Internal Components

| Component | Responsibility |
|-----------|---------------|
| **DiagnosisConsumer** | Reads DiagnosisReport; routes errors by channel |
| **WeightUpdater** | Adjusts belief weight (±δ) bounded by diagnosis category |
| **ConditionNarrower** | Adds/narrows preconditions when HYP_ERR or EVID_MISSING |
| **HorizonAdjuster** | Extends/shortens time horizon on TIMING_ERR |
| **EvidenceManager** | Adds/deprecates supporting evidence |
| **ConfidenceManager** | Adjusts meta-confidence on streaks/errors |
| **BeliefVersionManager** | Creates new Belief version on every modification ★ NEW v2.2 |
| **LearningLogWriter** | Persists every action as LearningLogEntry |
| **PatternLearner** | Mines LearningLog (activates after ≥200 entries) |

### 8.3 Belief Versioning Model ★ NEW v2.2

```python
class BeliefVersion(BaseModel):
    """Immutable snapshot of a belief at a point in time."""
    belief_id: str
    version_number: int                         # Monotonic: 1, 2, 3, ...
    created_at: datetime
    
    # Snapshot of Learning Unit attributes at this version
    weight: float
    confidence: float
    preconditions: dict[str, Any]
    valid_horizon: str
    supporting_evidence: list[str]
    
    # What triggered this version?
    trigger: str                                # "prediction_outcome" | "manual" | "deprecation"
    trigger_detail: str
    diagnosis_report_id: str | None             # Which diagnosis caused this change?
    
    # Diff from previous version (for v2+)
    changes_from_previous: LearningUnit | None

class AdaptiveBelief(BaseModel):
    """V3 belief: versioned, with 5 Learning Unit attributes."""
    belief_id: str
    dimension: str                              # "liquidity"
    transmission_channel: str                   # "liquidity→fx"  ★ NEW v2.2
    
    # Current state (derived from latest version)
    current_version: int
    weight: float
    confidence: float
    preconditions: dict[str, Any]
    valid_horizon: str
    supporting_evidence: list[str]
    
    # Full history
    version_history: list[BeliefVersion]        # Append-only, oldest first
    
    # Performance
    cycle_count: int
    correct_count: int
    streak: int
    status: str = "active"
    
    # Query helpers
    def get_version(self, v: int) -> BeliefVersion: ...
    def get_weight_trajectory(self) -> list[float]: ...
    def why_changed(self, v: int) -> str: ...    # Human-readable explanation
```

### 8.4 Learning Actions (Constrained by Learning Unit)

| Action | Attribute Modified | Trigger |
|--------|-------------------|---------|
| `WEIGHT_ADJUST` | Weight (±δ) | Any error except EVENT_ERR |
| `CONFIDENCE_DECAY` | Confidence | Consecutive errors |
| `CONDITION_ADD` | Preconditions | HYP_ERR or EVID_MISSING |
| `HORIZON_EXTEND` | Time Horizon | TIMING_ERR (direction eventually correct) |
| `HORIZON_SHORTEN` | Time Horizon | TIMING_ERR (direction wrong at current horizon) |
| `EVIDENCE_ADD` | Supporting Evidence | CORRECT_STRONG (reinforce with new data) |
| `EVIDENCE_DEPRECATE` | Supporting Evidence | SIGNAL_ERR (source data unreliable) |
| `MARK_EVENT` | None | EVENT_ERR (non-learnable) |
| `FLAG_FOR_REVIEW` | None | HYP_ERR × 3 within window |
| `DEPRECATE` | Status → "deprecated" | HYP_ERR × 10, no correct in last 20 |

### 8.5 Example: Belief Evolution Trace

```python
belief = AdaptiveBelief(
    belief_id="belief-liquidity-fx",
    dimension="liquidity",
    transmission_channel="liquidity→fx",
    version_history=[
        BeliefVersion(v=1, weight=0.85, preconditions={}, valid_horizon="5d",
                      trigger="initial", trigger_detail="Created by Hypothesis Generator"),
        BeliefVersion(v=2, weight=0.81, preconditions={}, valid_horizon="5d",
                      trigger="prediction_outcome", diagnosis_report_id="diag-042",
                      changes_from_previous=LearningUnit(weight_delta=-0.04)),
        BeliefVersion(v=3, weight=0.81, preconditions={"dxy_range": "<105"}, valid_horizon="5d",
                      trigger="prediction_outcome", diagnosis_report_id="diag-051",
                      changes_from_previous=LearningUnit(
                          precondition_change=PreconditionChange(
                              action="add", key="dxy_range", value="<105"))),
        BeliefVersion(v=4, weight=0.83, preconditions={"dxy_range": "<105"}, valid_horizon="10d",
                      trigger="prediction_outcome", diagnosis_report_id="diag-078",
                      changes_from_previous=LearningUnit(
                          weight_delta=+0.02, horizon_change="10d")),
    ]
)

# Query: "Why do I believe USD↑ when liquidity tightens today?"
belief.why_changed(4)
# → "v4: Weight increased to 0.83 because 3/3 recent predictions correct. 
#     Horizon extended to 10d because predictions materialized on day 7-9. 
#     Precondition: only applicable when DXY < 105."
```

### 8.6 API

```python
class LearningEngine:
    async def learn_from_diagnosis(
        self, diagnosis_report: DiagnosisReport
    ) -> LearningReport: ...

    async def update_belief(
        self, belief: AdaptiveBelief, unit: LearningUnit, diagnosis_id: str
    ) -> AdaptiveBelief: ...      # Returns belief with new version appended

    async def get_belief_history(
        self, belief_id: str
    ) -> list[BeliefVersion]: ...

    async def get_belief_trajectory(
        self, belief_id: str, attribute: str
    ) -> list[tuple[int, Any]]: ...  # [(v1, 0.85), (v2, 0.81), ...]

    async def rollback_belief(
        self, belief_id: str, target_version: int
    ) -> AdaptiveBelief: ...      # Emergency rollback to prior version
```

---

## 9. Module 5: Calibration Engine (unchanged from v2.1)

Tracks and optimizes calibration. ECE < 0.10 target. Hypothesis-specific calibration curves.

---

## 10. Hypothesis Library & Score ★ NEW v2.2

### 10.1 The System's Long-Term Asset

The Hypothesis Library is the persistent store of all hypotheses the Agent has ever formed, each with a composite score that reflects its accumulated track record. This is what makes the Agent a **research system** rather than a **prediction pipeline** — it builds knowledge over time.

### 10.2 HypothesisScore Composition

```python
class HypothesisScore(BaseModel):
    hypothesis_id: str
    computed_at: datetime
    
    # Composite score (0 ~ 1)
    total_score: float              # Weighted average of sub-scores
    
    # Sub-score 1: Prediction Accuracy (weight: 0.30)
    prediction_accuracy: float      # Directional accuracy of this hypothesis's predictions
    accuracy_trend: str             # "improving" | "stable" | "declining"
    
    # Sub-score 2: Evidence Quality (weight: 0.25)
    evidence_quality: float         # Average strength + recency of supporting evidence
    evidence_count: int
    evidence_freshness_days: float  # Avg age of evidence
    
    # Sub-score 3: Calibration (weight: 0.20)
    calibration_score: float        # 1.0 - ECE for this hypothesis
    ece: float
    
    # Sub-score 4: Consistency (weight: 0.15)
    consistency_score: float        # 1.0 - std_dev of accuracy across cycles
    accuracy_variance: float
    cycle_count: int
    
    # Sub-score 5: Learning History (weight: 0.10)
    learning_history_score: float   # Has accuracy improved over time?
    accuracy_trajectory_slope: float  # Positive = improving
    version_count: int              # More versions with improvement = higher score
```

### 10.3 Score Calculation

```python
def compute_hypothesis_score(
    predictions: list[Prediction],
    evidence: list[EvidenceItem],
    calibration_curve: CalibrationCurve,
    belief: AdaptiveBelief,
) -> HypothesisScore:
    
    accuracy = _directional_accuracy(predictions)
    evidence_q = _evidence_quality(evidence)
    calibration = 1.0 - _compute_ece(predictions, calibration_curve)
    consistency = 1.0 - _accuracy_variance_across_cycles(predictions)
    learning = _improvement_trajectory(
        belief.get_weight_trajectory(),
        belief.version_history,
    )
    
    total = (
        0.30 * accuracy +
        0.25 * evidence_q +
        0.20 * calibration +
        0.15 * consistency +
        0.10 * learning
    )
    
    return HypothesisScore(total_score=total, ...)
```

### 10.4 Hypothesis Library Operations

```python
class HypothesisLibrary:
    """The system's long-term knowledge asset."""
    
    async def register(
        self, hypothesis: Hypothesis, initial_score: HypothesisScore
    ) -> str: ...                   # Returns hypothesis_id
    
    async def update_score(
        self, hypothesis_id: str, new_predictions: list[Prediction]
    ) -> HypothesisScore: ...       # Recompute after new outcomes
    
    async def get_top(
        self, dimension: str | None = None, min_score: float = 0.6, limit: int = 10
    ) -> list[HypothesisWithScore]: ...
    
    async def get_deprecated(
        self, dimension: str | None = None
    ) -> list[HypothesisWithScore]: ...
    
    async def get_score_history(
        self, hypothesis_id: str
    ) -> list[HypothesisScore]: ...   # Score trajectory over time
    
    async def find_similar(
        self, hypothesis: Hypothesis, threshold: float = 0.7
    ) -> list[HypothesisWithScore]: ...
    
    # Used by Hypothesis Generator
    async def get_active_beliefs(
        self, dimension: str, min_score: float = 0.5
    ) -> list[AdaptiveBelief]: ...
```

### 10.5 Library as Hypothesis Generator Input

```
Before V3 (V2):    Hypothesis Generator uses fixed rule templates
After V3 (v2.2):   Hypothesis Generator queries Library for prior beliefs
                    → Reuses high-score beliefs
                    → Applies their learned preconditions
                    → Uses their calibrated confidence
                    → Avoids deprecated beliefs
```

The Library makes the Hypothesis Generator smarter with every cycle — not because its code changes, but because its knowledge base grows.

### 10.6 Example: Library Evolution

```
Week 1:  Library has 4 hypotheses, all score 0.50 (neutral)

Week 4:  "Liquidity Tightening → NASDAQ ↓"
         Score: 0.72 (3/4 predictions correct, good calibration)
         ↑ Reused with high confidence

Week 8:  "Growth Accelerating → SPX ↑"
         Score: 0.81 (consistent across 3 cycles)
         ↑ Now the most trusted growth hypothesis

Week 12: "Credit Tightening → HYG ↓"
         Score: 0.31 (mostly wrong, evidence stale)
         ↓ Deprecated — Hypothesis Generator no longer uses it

Week 16: Library has 12 hypotheses, avg score 0.65
         Top 3 hypotheses drive 80% of correct predictions
         The Library IS the Agent's intelligence
```

---

## 11. Four-Component KPI System (Frozen)

### 11.1 KPI-1: Hypothesis Accuracy (Source: Hypothesis Library)

| Metric | Formula | Target |
|--------|---------|--------|
| Library Average Score | mean(total_score) across all active hypotheses | > 0.65 (90d) |
| Top-3 Accuracy | mean accuracy of top 3 scored hypotheses | > 75% |
| Deprecation Rate | deprecated / total hypotheses | < 20% |
| Score Trajectory | slope of total_score over time | Positive |

### 11.2 KPI-2: Prediction Error

| Metric | Target |
|--------|--------|
| Directional Accuracy | > baseline + 8pp (90d) |
| MAE | < baseline × 0.85 |
| RMSE | < baseline × 0.85 |

### 11.3 KPI-3: Confidence Calibration

| Metric | Target |
|--------|--------|
| ECE | < 0.10 |
| Brier Score | < 0.15 |

### 11.4 KPI-4: Learning Speed

| Metric | Target |
|--------|--------|
| Error Recurrence Rate | Trend ↓ |
| Time-to-Correction | Trend ↓ |
| Pattern Fix Rate | > 50% |

---

## 12. Complete Feedback Loop (v2.2)

```
Research Pipeline Run (V2):
  Data → Signal → Hypothesis → Reflection → Narrative
                         │
                         ▼
                  ┌──────────────┐
                  │HYPOTHESIS     │
                  │LIBRARY        │ ← Query prior beliefs with scores
                  │(persistent)   │
                  └──────┬───────┘
                         │ Scored, preconditioned, versioned beliefs
                         ▼
                  ┌─────────────────┐
                  │ PREDICTION ENGINE│
                  │ 1 Hypothesis →   │
                  │ N Predictions    │  ← Multi-prediction per channel
                  │ Primary/2nd/3rd  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ PREDICTION STORE │
                  └────────┬────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
      ┌──────────────┐          ┌──────────────┐
      │ SCHEDULER     │          │ SCHEDULER     │
      └──────┬───────┘          └──────┬───────┘
             └──────────┬─────────────┘
                        ▼
              ┌─────────────────┐
              │ OUTCOME EVALUATION│
              │ Per-prediction   │
              │ Per-channel      │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ DIAGNOSIS ENGINE │
              │ Per-prediction   │
              │ Error taxonomy   │
              └────────┬────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ LEARNING │ │CALIBRATION│ │ LEARNING │
   │ ENGINE   │ │ ENGINE   │ │   LOG    │
   │ 5 LU     │ │ ECE      │ │ (append) │
   │ attrs    │ │ curve    │ │          │
   │ versioned│ │          │ │          │
   └────┬─────┘ └────┬─────┘ └──────────┘
        └────────────┼──────────────────┘
                     ▼
          ┌─────────────────────┐
          │ HYPOTHESIS LIBRARY  │
          │ Score recomputed    │
          │ Versions appended   │
          │ Deprecation checked │
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │ NEXT HYPOTHESIS     │
          │ GENERATOR CYCLE     │
          │ • High-score beliefs│
          │ • Narrowed preconds │
          │ • Calibrated conf   │
          │ → BETTER HYPOTHESES │
          └─────────────────────┘
```

---

## 13. Release Roadmap v2.2

```
Release 3.0 — Measurement Foundation     (Weeks 1-5)
Release 3.1 — Diagnosis & Learning        (Weeks 6-16)
Release 3.2 — Adaptive Maturity           (Weeks 17-26)
```

### 13.1 Release 3.0 — Measurement Foundation

**Theme**: Multi-prediction generation, outcome evaluation, 4-KPI baselines. Hypothesis Library created (passive). Diagnosis passive. Learning EMA-only. Belief Versioning records v1 of all beliefs.

**Deliverables**: Multi-PredictionEngine, OutcomeEvaluationEngine (per-channel), DiagnosisEngine (passive), MetricsEngine, HypothesisLibrary (initial), BeliefVersionManager (v1 only), LearningLog (accumulating), Scheduler.

**Exit Criteria**:
- ≥3 predictions per hypothesis (primary, secondary, tertiary where applicable)
- ≥100 predictions evaluated across all channels
- 4 KPI baselines computed
- Hypothesis Library: ≥10 registered hypotheses with initial scores
- All beliefs have v1 recorded
- All 148 V2 tests pass

### 13.2 Release 3.1 — Diagnosis & Learning

**Theme**: Diagnosis gates learning. 5 Learning Unit attributes activated. Belief Versioning active (v2+). Calibration empirical after ≥50 predictions. LearningLog reaches activation (≥200).

**Exit Criteria**:
- Hypothesis Library Avg Score > baseline + 0.05 (KPI-1)
- Directional Accuracy > baseline + 5pp (KPI-2)
- ECE < 0.15 (KPI-3)
- Error Recurrence Rate declining (KPI-4)
- ≥80% of beliefs have ≥2 versions
- PatternLearner detects ≥2 patterns
- No Learning Unit violation (all changes within 5 attributes)

### 13.3 Release 3.2 — Adaptive Maturity

**Theme**: Hypothesis Library is the Agent's core intelligence. Sustained KPI improvement. V4 ready.

**Exit Criteria**:
- Library Avg Score > 0.65 (KPI-1)
- Directional Accuracy > baseline + 8pp (KPI-2)
- ECE < 0.10 (KPI-3)
- Error Recurrence Rate < 20% (KPI-4)
- Top 3 hypotheses drive >50% of correct predictions
- Deprecation rate < 15%
- ≥8 weeks continuous operation, all KPIs stable or improving

---

## 14. V2 Compatibility

### 14.1 Core Principle

> **V3 adds versioned, diagnosis-gated feedback to V2's pipeline. V2 engines are untouched.**

### 14.2 Module Map

| V2 Module | V3 Strategy |
|-----------|------------|
| Pipeline | EXTENDED: + `run_with_prediction(goal)` |
| Signal Engine | REUSED |
| **Hypothesis Engine** | **OPTIMIZED: Queries Hypothesis Library for prior beliefs** |
| Reflection Engine | REUSED |
| Narrative Engine | REUSED: V3 data fed to v2.0 sections |
| Outcome Tracking | EXTENDED: per-channel evaluation |
| Learning Engine | REPLACED: 5 Learning Unit attributes, versioned |
| Calibration | REPLACED (after 50 preds): empirical |
| Belief Memory | REPLACED: AdaptiveBelief with versioning |
| Schemas | EXTENDED: +30 new schemas |
| API | EXTENDED: + /v3/* endpoints |
| CLI | EXTENDED: + predict, evaluate, diagnose, learn, metrics, library |

### 14.3 Directory Structure

```
src/
├── prediction/           NEW: MultiPredictionEngine, Mapper(per-channel), Horizon, Validator
├── evaluation/           NEW: OutcomeEvaluationEngine, PerChannelComparator
├── diagnosis/            NEW: DiagnosisEngine, ErrorClassifier, ContextAnalyzer
├── learning/             REPLACED: WeightUpdater, ConditionNarrower, HorizonAdjuster,
│                                    EvidenceManager, ConfidenceManager,
│                                    BeliefVersionManager, LearningLogWriter, PatternLearner
├── learning_log/         NEW: LearningLogRepository, LogQueryEngine
├── learning_unit/        NEW: LearningUnitValidator, AttributeConstraintChecker
├── belief_versioning/    NEW: BeliefVersionRepository, VersionDiffEngine, RollbackManager
├── hypothesis_library/   NEW: HypothesisLibrary, ScoreComputer, LibraryQueryEngine
├── calibration/          EXTENDED: + CalibrationEngine, CurveBuilder, HypothesisCalibration
├── metrics/              NEW: KPIMetricsEngine, FourKPIComputer, RegressionChecker
├── scheduler/            NEW: EvaluationScheduler, KPIReporter
├── schemas/              EXTENDED: + prediction_v3, evaluation_v3, diagnosis, learning_unit,
│                                    belief_version, hypothesis_library, learning_log, kpi
├── api/                  EXTENDED: + v3 routes
└── cli.py                EXTENDED: + predict, evaluate, diagnose, learn, metrics, library
```

---

## Appendix A: Schema Relationship Diagram (v2.2)

```
HypothesisLibrary ──► HypothesisSet ──► PredictionBatch (1:N per hypothesis)
                                             │
                                    ┌────────┼────────┐
                                    ▼        ▼        ▼
                              Prediction Prediction Prediction
                              (primary) (secondary)(tertiary)
                                    │
                                    ▼
                              PredictionOutcome (per-prediction)
                                    │
                                    ▼
                              ErrorClassification (per-prediction)
                                    │
                                    ▼
                              DiagnosisReport
                               │          │
                               ▼          ▼
                        LearningUnit   LearningLogEntry
                        (5 attrs max)  (append-only)
                               │
                               ▼
                        AdaptiveBelief
                        (new version created)
                               │
                               ▼
                        BeliefVersion (immutable)
                               │
                               ▼
                        HypothesisLibrary
                        (score recomputed)

CalibrationReport ◄── EvaluationReport + DiagnosisReport
```

## Appendix B: What Moves to V4

| Feature | V4 Target | Rationale |
|---------|-----------|-----------|
| Conversation Manager | 4.0 | Interaction layer |
| Session Manager | 4.0 | Session needs Workspace |
| Workspace | 4.1 | Richer with adaptive kernel |
| Chat UI / Timeline | 4.1 | Frontend |
| Agent Initiative | 4.2 | Calibrated self-knowledge |
| Evidence Graph | 4.1 | Flat sufficient for V3 |
| Human Review of FLAG_FOR_REVIEW | 4.0 | Needs interaction layer |

## Appendix C: DDR-V3 v2.2 Impact Matrix

```
                         V1-V2    v2.0    v2.1    v2.2
DDR-V3-001  Hypothesis-First  ─     ✦      ✦       ✦
DDR-V3-002  Diagnosis Gate    ─     ─      ✦       ✦
DDR-V3-003  Incremental Belief─     ✦      ✦       ✦(extended)
DDR-V3-004  4-KPI System      ─     ✦      ✦       ✦
DDR-V3-005  Error Taxonomy    ─     ─      ✦       ✦
DDR-V3-006  Diagnosis Bridge  ─     ─      ✦       ✦
DDR-V3-007  Learning Unit     ─     ─      ─       ✦(New)
DDR-V3-008  Belief Versioning ─     ─      ─       ✦(New)
DDR-V3-009  Multi-Prediction  ─     ─      ─       ✦(New)
DDR-V3-010  Hypothesis Library─     ─      ─       ✦(New)
```

## Appendix D: The Complete V3 Cognitive Chain

```
MARKET
  │
  ▼
DATA (yfinance, FRED, etc.)
  │
  ▼
OBSERVATION (statistical description)
  │
  ▼
SIGNAL (threshold classification)
  │
  ▼
HYPOTHESIS GENERATOR ◄─── Hypothesis Library (prior beliefs, scores)
  │
  ▼
MULTI-PREDICTION ENGINE (1 hypothesis → N predictions, per channel)
  │
  ▼
OUTCOME EVALUATION (per-prediction, per-channel)
  │
  ▼
DIAGNOSIS ENGINE (6 error categories, per-prediction)
  │
  ▼
LEARNING ENGINE (5 Learning Unit attributes, versioned beliefs)
  │
  ├──► Belief Versioning (v→v+1, immutable history)
  ├──► Learning Log (append-only)
  └──► Calibration Engine (ECE, empirical curves)
  │
  ▼
HYPOTHESIS LIBRARY (scores recomputed, knowledge accumulated)
  │
  └──► Next Cycle: Better Hypotheses
```

---

> **Document Status**: PROPOSED — V3 Architecture Freeze v2.2 (Final)
> **Related**: `ARCHITECTURE_WHITEPAPER.md` (V2), `ddr/ARCHITECTURE_DECISIONS.md` (DDRs)
> **Next Step**: Architecture review → approval → DDR-V3-001~010 ratified → Release 3.0
