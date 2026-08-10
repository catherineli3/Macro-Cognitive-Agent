# Design Decision Records — Macro Research Agent

> **Document Type**: Architecture Decision Records (ADR)  
> **Version**: 1.0 (consolidated)  
> **Date**: July 2026  
> **Status**: All decisions ratified; v2.0 decisions implemented

---

## Overview

This document consolidates all architecture design decisions (DDRs) made during the development of the Macro Research Agent, from Sprint 0 through v2.0.

**17 decisions total**: 10 foundational (DDR-001 through DDR-010) + 7 v2.0 (DDR-v2.1 through DDR-v2.7) + 10 V3 proposed (DDR-V3-001 through DDR-V3-010).

---

## DDR Index

| # | Decision | Phase | Status | Impact |
|---|----------|-------|--------|--------|
| DDR-001 | Observation → Signal → Hypothesis Layering | S6 | Approved (reserved for V1) | Architecture |
| DDR-002 | Reflection as Belief Review, Not Challenge | S7 | Approved | Cognitive Model |
| DDR-003 | Narrative Engine as MVP Priority | S7-S8 | Approved | Output Contract |
| DDR-004 | MacroResearchPipeline as Unified Entry Point | S8 | Active | System Design |
| DDR-005 | Planner = Fixed DAG Only | S8 | Active (frozen) | Scope |
| DDR-006 | Analyzer Module Deprecated | S8 | Ratified | Module Lifecycle |
| DDR-007 | Observation Layer → V1 | S8 | Approved | Roadmap |
| DDR-008 | State Manager, Scheduler, Monitoring → V2 | S8 | Approved | Roadmap |
| DDR-009 | Outcome Tracking → Learning | S8 → v2.0 | ✅ Implemented | Continuous Learning |
| DDR-010 | Schema First Architecture | S8 | Active (enforced) | System-Wide Contract |
| DDR-v2.1 | Outcome Tracking as Separate Domain | v2.0 | ✅ Implemented | Module Boundary |
| DDR-v2.2 | Learning Engine as EMA Belief Update | v2.0 | ✅ Implemented | Algorithm |
| DDR-v2.3 | Confidence Calibration as Weighted Blend | v2.0 | ✅ Implemented | Calibration |
| DDR-v2.4 | Composite Signals as Deterministic Pattern Matching | v2.0 | ✅ Implemented | Signal Engine |
| DDR-v2.5 | Pipeline Integration — Graceful Degradation | v2.0 | ✅ Implemented | Reliability |
| DDR-v2.6 | Narrative Engine v2 — Source-Anchored Learning | v2.0 | ✅ Implemented | Narrative |
| DDR-v2.7 | API v2 Endpoints — Read-Only Observation | v2.0 | ✅ Implemented | API Design |

---

## Foundational Decisions (DDR-001 ~ DDR-010)

---

### DDR-001: Observation → Signal → Hypothesis Layering

**Date**: 2026-07-15 | **Phase**: Sprint 6 | **Status**: Approved (reserved for V1)

**Context**: At Sprint 6, the Signal Engine reads raw data directly from the Data Pipeline. This couples Signal to data format details. A formal Observation Layer (statistical description of data before signal generation) would improve separation of concerns.

**Decision**: Architecture reserves a formal Observation Layer between Data Pipeline and Signal Engine for a future release. The three layers form a progressive abstraction chain:

```
Raw Data → Observation → Signal → Hypothesis → Reflection
```

**Rationale**:
- Today: Signal Engine reads data directly — works but couples to format
- Future: Signal Engine will consume `Observation[]` instead of `MacroDataSchema`
- Hypothesis Engine's contract (`Signal[]` → `Hypothesis[]`) remains unchanged
- Designed for natural evolution, not a rewrite

**Consequences**:
- Sprint 9/10: Introduce `ObservationLayer`. Signal Engine interface signature changes.
- **No Hypothesis refactor needed** — its contract is stable.

---

### DDR-002: Reflection as Belief Review, Not Challenge

**Date**: 2026-07-15 | **Phase**: Sprint 7 | **Status**: Approved

**Context**: During Reflection Engine design, two approaches were considered: (a) a "challenger" that attacks hypotheses to find weaknesses, or (b) a "reviewer" that evaluates whether to maintain belief.

**Decision**: Reflection Engine is designed as a **Belief Review Engine**. It answers exactly three questions:
1. Is evidence sufficient?
2. Is evidence internally consistent?
3. Should we still believe?

**Rationale**:
- Autonomous reasoning agent should *review* beliefs, not attack them
- "Challenge" implies adversarial posture; "Review" implies measured evaluation
- 3-question framework prevents scope creep into rule engine territory
- No individual assumption review — the review target is the Belief, not its components

**Rejected Alternatives**:
- AssumptionChallenger (adversarial, over-engineered for MVP)
- LogicIssue enumeration (creates rule catalog, violates YAGNI)
- Alternative explanation generation (requires LLM-level reasoning)

**Consequences**:
- Sprint 8 (Memory): `ReflectionReport` is self-contained, ready for serialization
- Future LLM Sprint: Alternative explanation generation can be added as separate step

---

### DDR-003: Narrative Engine as MVP Priority

**Date**: 2026-07-15 | **Phase**: Sprint 7-8 | **Status**: Approved

**Context**: At the end of Sprint 7 (Reflection), the cognitive pipeline produced `ReflectionSet`. The system needed an output layer to make results consumable.

**Decision**: Narrative Engine is the MVP's highest-priority deliverable. It outputs `MacroNarrative` Schema — NOT Markdown strings.

**Rationale**:
- MVP goal: complete pipeline from data to actionable output
- Narrative Engine is the ONLY user-visible deliverable
- `MacroNarrative` as Schema: CLI/API/Dashboard each render their own format
- Avoids coupling presentation format to cognitive engine output
- Future LLM, Template, HTML, PDF all replaceable without touching Narrative

**Consequences**:
- CLI renders `MacroNarrative` → Markdown
- API serializes `MacroNarrative` → JSON
- Future Dashboard reads `MacroNarrative` → UI components

---

### DDR-004: MacroResearchPipeline as Unified Entry Point

**Date**: 2026-07-15 | **Phase**: Sprint 8 | **Status**: Active

**Context**: Multiple entry points (CLI, API, future Scheduler) needed a single, consistent way to trigger macro research execution.

**Decision**: `MacroResearchPipeline.run()` is the system's ONLY unified entry point.

```python
pipeline = MacroResearchPipeline()
result = await pipeline.run(goal="macro environment")
```

**Architecture**:
```
CLI ──► MacroResearchPipeline.run() ◄── API
                 │
                 ▼
        Planner → Executor → Handlers → MacroNarrative
```

**Rationale**:
- Single entry = single place for lifecycle management, error handling, logging
- Pipeline encapsulates Planner, Executor, Handler registration
- Consumers never see internal wiring
- Named "Pipeline" (doer), not "Builder" (constructor) — reflects API semantics

---

### DDR-005: Planner = Fixed DAG Only

**Date**: 2026-07-15 | **Phase**: Sprint 8 | **Status**: Active (Frozen)

**Context**: Should the Planner evolve to support autonomous planning (LLM task decomposition, dynamic re-planning)?

**Decision**: **No.** Planner is frozen as a fixed DAG orchestrator. It will NOT be extended for any version (MVP, V1, V2).

**Rationale**:
- Macro research workflow is highly structured — fixed DAG covers all needs
- Autonomous planning belongs to a fundamentally different architecture (V3: Research Planner)
- Keeping Planner frozen prevents scope creep and over-engineering
- The PlannerInterface ABC exists for future Research Planner but current impl is final

---

### DDR-006: Analyzer Module Deprecated

**Date**: 2026-07-15 | **Phase**: Sprint 8 | **Status**: Ratified

**Context**: `src/analyzer/` was originally designed to "analyze macro data." Its responsibilities were vague and overlapped with other modules.

**Decision**: `src/analyzer/` is formally deprecated. Its analysis capabilities are split across:
- **Observation Layer (V1)**: Statistical description (percentile, rate of change, history)
- **Signal Engine**: Threshold judgment and signal classification
- **Hypothesis Engine**: Cross-signal causal reasoning and hypothesis formation

**Rationale**: "Analyze data" is too broad — violates Single Responsibility Principle. The three replacement modules each have precise, bounded responsibilities.

---

### DDR-007: Observation Layer → V1

**Date**: 2026-07-15 | **Phase**: Sprint 8 | **Status**: Approved

**Context**: Should the Observation Layer be built in MVP or deferred?

**Decision**: Observation Layer is deferred to V1 (after MVP). MVP's Signal Engine continues consuming data directly from the Normalizer.

**Rationale**:
- MVP goal: end-to-end functionality. Observation Layer doesn't block this.
- Signal Engine works correctly with direct data consumption.
- V1 introduces Observation Layer by upgrading Signal Engine interface only.
- Hypothesis and Reflection need zero changes.

---

### DDR-008: State Manager, Scheduler, Monitoring → V2

**Date**: 2026-07-15 | **Phase**: Sprint 8 | **Status**: Approved

**Context**: Production systems need state management (LangGraph), periodic scheduling, and monitoring/observability.

**Decision**: All three defer to V2 (platform reliability release).

**Rationale**:
- MVP's `ExecutionContext` manages execution state adequately
- Periodic execution is a production need; MVP uses CLI/API triggers
- Monitoring is operational, not functional

**Note**: v2.0 implemented continuous learning engines but NOT state management/scheduling/monitoring. These remain V2 (infrastructure) scope, separate from v2.0 (cognitive) scope.

---

### DDR-009: Outcome Tracking → Learning

**Date**: 2026-07-15 | **Phase**: Sprint 8 → v2.0 | **Status**: ✅ Implemented

**Context**: The Agent generates predictions but never checks if they were correct. Without outcome tracking, there's no feedback loop for improvement.

**Decision**: Outcome Tracking → Learning implemented in v2.0. Core mechanism:
1. Track predictions as `PredictionOutcome` records (PENDING → CORRECT/INCORRECT)
2. Compute hit rate, Brier Score, per-dimension accuracy
3. Use EMA to update belief weights based on track record
4. Calibrate hypothesis confidence using historical accuracy

**v2.0 Implementation** (July 2026):
- `src/outcome/engine.py` — OutcomeEvaluator, OutcomeMetrics, OutcomeTracker
- `src/learning/learning_engine.py` — BeliefUpdater, ConfidenceDecay, PatternMiner
- `src/calibration/confidence_calibrator.py` — Weighted blend calibrator
- 62 tests, all passing
- Full integration with pipeline and narrative

---

### DDR-010: Schema First Architecture

**Date**: 2026-07-15 | **Phase**: Sprint 8 | **Status**: Active (Enforced)

**Context**: Without explicit data contracts, modules communicate via ad-hoc dicts, tuples, and lists — leading to silent breakage and unclear boundaries.

**Decision**: ALL cognitive modules communicate exclusively through typed Pydantic Schemas.

**Schema Chain**:
```
MacroDataSchema → SignalSnapshot → HypothesisSet → ReflectionSet → BeliefRecord[] → MacroNarrative
```

**Enforced Rules**:
- ❌ `dict` must not cross module boundaries
- ❌ `tuple` must not cross module boundaries
- ❌ `list[Any]` must not cross module boundaries
- ✅ Every module's input → output types are explicitly declared in Schema layer
- ✅ Internal implementations can change; contracts cannot

**Rationale**:
- Schema is the API of an AI Agent — like protobuf/OpenAPI for microservices
- Typed contracts eliminate implicit conventions
- Reduces risk of handler artifact key typos
- All future modules (Observation, new data sources) must comply

---

## v2.0 Decisions (DDR-v2.1 ~ DDR-v2.7)

*Full details in [docs/ddr_v2.md](ddr_v2.md)*

---

### DDR-v2.1: Outcome Tracking as Separate Domain

**Decision**: Outcome Tracking is a standalone engine (`src/outcome/`), NOT embedded in Memory or Reflection. JSON-file persistence, no DB dependency.

**Why separate**: Memory stores beliefs; Outcomes track what happened. Different lifecycles, different query patterns.

---

### DDR-v2.2: Learning Engine as EMA Belief Update

**Decision**: Belief weight updates use Exponential Moving Average:
```
new_weight = old_weight * (1 - 0.1) + accuracy * 0.1
```

**Why EMA**: Simple, explainable, no black-box ML. All dimensions start at 0.5 (neutral). 14-day half-life decay for stale dimensions.

---

### DDR-v2.3: Confidence Calibration as Weighted Blend

**Decision**: Calibrated confidence uses:
```
calibrated = raw * 0.50 + historical_accuracy * 0.30 + dimension_weight * 0.20
```

**Key constraint**: calibrated ≤ raw always. Calibrator can only reduce confidence, not inflate.

---

### DDR-v2.4: Composite Signals as Deterministic Pattern Matching

**Decision**: 8 hardcoded MacroTheme definitions with deterministic rule matching. No LLM, no ML.

**Why deterministic**: Every theme has clear, auditable conditions. No hallucination risk. Extensible by adding entries to theme definition list.

---

### DDR-v2.5: Pipeline Integration — Graceful Degradation

**Decision**: Every v2.0 pipeline step is wrapped in `try/except`. Failure of any single engine produces a warning log and continues.

**Why**: Core function (signal → hypothesis → narrative) must never depend on v2.0 engines. Users can deploy engines incrementally.

---

### DDR-v2.6: Narrative Engine v2 — Source-Anchored Learning

**Decision**: v2.0 narrative adds 3 structured sections sourced from engine outputs:
1. What We Learned (PatternMiner output)
2. Prediction Accuracy (OutcomeMetrics)
3. Confidence Calibration (CalibratedConfidenceSet)

**Why source-anchored**: Every sentence maps to a deterministic field. No free-text generation. Graceful absence: first run shows "Insufficient data."

---

### DDR-v2.7: API v2 Endpoints — Read-Only Observation

**Decision**: 6 read-heavy endpoints, 1 mutating (`POST /v2/relearn`). Module-level singletons for engine reuse.

**Why read-heavy**: Users inspect learning state without side effects. Only explicit POST triggers state change.

---

## Decision Impact Matrix

```
                     MVP     V1      V2     v2.0    V3
DDR-001  Layering    ─       ✦       ─      ─      ─
DDR-002  Reflection  ✦       ─       ─      ─      ✦(Critic)
DDR-003  Narrative   ✦       ─       ─      ✦      ─
DDR-004  Pipeline    ✦       ─       ─      ─      ─
DDR-005  Planner     ✦(frozen)─       ─      ─      ✦(Replaced)
DDR-006  Analyzer    ✦       ─       ─      ─      ─
DDR-007  Observation ─       ✦       ─      ─      ─
DDR-008  Infra       ─       ─       ✦      ─      ─
DDR-009  Outcome     ─       ─       ─      ✦      ─
DDR-010  Schema      ✦       ─       ─      ─      ─
DDR-v2.1 Outcome    ─       ─       ─      ✦      ─
DDR-v2.2 Learning   ─       ─       ─      ✦      ─
DDR-v2.3 Calibration─       ─       ─      ✦      ─
DDR-v2.4 Composite  ─       ─       ─      ✦      ─
DDR-v2.5 Degradation─       ─       ─      ✦      ─
DDR-v2.6 NarrativeV2─       ─       ─      ✦      ─
DDR-v2.7 API v2     ─       ─       ─      ✦      ─
```

> ✦ = decision impacts this phase | ─ = no impact (already implemented or not reached)

---

## Decision Principles (Retrospective)

Looking back at all 17 decisions, three meta-principles emerge:

1. **Determinism First**: Every cognitive engine (Signal, Hypothesis, Reflection, Learning, Calibration) is deterministic. Rules and templates produce identical output for identical input. This gives the system auditability that LLM-based agents lack.

2. **Scope Discipline**: When a capability is within reach but not essential, it gets reserved (→ future phase) rather than half-implemented. Observation Layer, State Manager, Scheduler — all deferred cleanly.

3. **Schema as Architecture**: DDR-010 is the most impactful single decision. Typed schemas transform the Agent from a script with implicit data-flow assumptions into a system with explicit, enforceable contracts. Every subsequent module was built on this foundation.

---

## V3 Decisions (DDR-V3-001 ~ DDR-V3-010)

*Full detail in [docs/V3_ARCHITECTURE.md](../V3_ARCHITECTURE.md)*

> **V3 Architecture Freeze v2.2 (Final)** — V3 从"工程项目"正式定义为**研究系统（Research System）**。
> 核心目标：持续提升 Hypothesis Generator 质量。Prediction 是验证手段。
> 新增：Diagnosis Engine、Learning Unit（5 属性约束）、Belief Versioning、Multi-Prediction Model、Hypothesis Library & Score。
> Conversation/Session/Workspace/Chat UI 全部推迟到 V4。

Ten DDRs define the V3 Adaptive Research architecture. Core closed loop: **Market → Data → Observation → Signal → Hypothesis → Multi-Prediction → Outcome → Diagnosis → Learning (5 LU attrs, versioned) → Calibration → Hypothesis Library → Better Hypotheses**.

---

### DDR-V3-001: Hypothesis-First Architecture (Revised v2.1)

**Date**: 2026-07-15 | **Phase**: V3 Architecture Freeze v2.2 | **Status**: Proposed

**Decision**: The Hypothesis Generator is V3's optimization target. Prediction is a mandatory validation instrument — not the deliverable. Every hypothesis must produce falsifiable predictions; every prediction must trace back to a hypothesis.

**Rationale**: A system optimizing for prediction accuracy learns to make easy predictions. A system optimizing for hypothesis quality learns to form better causal models. The former is a parlor trick; the latter is research.

**Consequences**: Hypothesis quality metrics equal-weight to prediction metrics. Every `Prediction` carries non-nullable `source_hypothesis_id`.

---

### DDR-V3-002: Diagnosis Before Learning (Revised v2.1)

**Date**: 2026-07-15 | **Phase**: V3 Architecture Freeze v2.2 | **Status**: Proposed

**Decision**: A Diagnosis Engine classifies **why** a prediction failed before any learning action. 6 error categories: `SIGNAL_ERR`, `HYP_ERR`, `EVID_MISSING`, `TIMING_ERR`, `EVENT_ERR`, `WEIGHT_ERR`.

**Rationale**: Without diagnosis, Learning cannot distinguish "fundamentally wrong hypothesis" from "unpredictable event."

**Consequences**: New `DiagnosisEngine` between Outcome and Learning. Learning input is `DiagnosisReport`, not `EvaluationReport`.

---

### DDR-V3-003: Incremental Belief Evolution (Revised v2.1, extended v2.2)

**Date**: 2026-07-15 | **Phase**: V3 Architecture Freeze v2.2 | **Status**: Proposed

**Decision**: The Learning Engine does NOT modify rules or replace knowledge. It maintains exactly five defined properties per Belief (see DDR-V3-007). Updates are progressive and versioned (see DDR-V3-008). Deprecation (not deletion) is the strongest action.

**Rationale**: "Replace belief" discards partially correct knowledge. Additive actions preserve what was learned while correcting what was wrong.

**Consequences**: `AdaptiveBelief` with 5 Learning Unit attributes. Actions: `WEIGHT_ADJUST`, `CONDITION_NARROW`, `HORIZON_ADJUST`, `EVIDENCE_ADD/DEPRECATE`, `CONFIDENCE_DECAY`, `DEPRECATE`.

---

### DDR-V3-004: Four-Component KPI System (Revised v2.1)

**Date**: 2026-07-15 | **Phase**: V3 Architecture Freeze v2.2 | **Status**: Proposed

**Decision**: Four equally-weighted KPIs on rolling windows: (1) Hypothesis Accuracy (via Library scores), (2) Prediction Error, (3) Confidence Calibration, (4) Learning Speed.

**Consequences**: `KPIMetricsEngine` computes weekly. Regression gate blocks degradation. KPI-1 source: Hypothesis Library average score.

---

### DDR-V3-005: Error Taxonomy as First-Class Knowledge (v2.1)

**Date**: 2026-07-15 | **Phase**: V3 Architecture Freeze v2.2 | **Status**: Proposed

**Decision**: Every error classified into exactly one taxonomy category. Persisted as append-only `LearningLog`. Minimum 200 entries before PatternLearner activates.

---

### DDR-V3-006: Diagnosis as the Bridge to Learning (v2.1)

**Date**: 2026-07-15 | **Phase**: V3 Architecture Freeze v2.2 | **Status**: Proposed

**Decision**: Diagnosis Engine is the only path from Outcome to Learning. No outcome bypasses diagnosis. Safe default: no diagnosis = no learning.

---

### DDR-V3-007: Learning Unit — Five Modifiable Attributes ★ NEW v2.2

**Date**: 2026-07-15 | **Phase**: V3 Architecture Freeze v2.2 | **Status**: Proposed

**Decision**: The Learning Engine is constrained to modify exactly five attribute types on any Belief. It cannot create, delete, or rewrite rules.

| # | Attribute | Meaning | Example |
|---|-----------|---------|---------|
| 1 | **Weight** | How much to trust (0~1) | 0.85 → 0.81 |
| 2 | **Confidence** | How sure about the weight | 0.90 → 0.72 |
| 3 | **Preconditions** | When this belief applies | Add: `core_cpi > 3%` |
| 4 | **Valid Time Horizon** | Prediction validity window | "3d" → "10d" |
| 5 | **Supporting Evidence** | Evidence anchoring this belief | Add/deprecate references |

**Rationale**: "Update Belief" is too abstract — it allows arbitrary modification. By constraining to exactly 5 attribute types, every learning action is auditable, reversible, and versioned. The system cannot accidentally delete good knowledge.

**Consequences**: `LearningUnit` schema validates all modifications. Prohibited: delete belief, rewrite causal rule, modify weight by >±0.15/cycle, remove preconditions. Learning Engine internals limited to 5 managers: WeightUpdater, ConditionNarrower, HorizonAdjuster, EvidenceManager, ConfidenceManager.

---

### DDR-V3-008: Belief Versioning ★ NEW v2.2

**Date**: 2026-07-15 | **Phase**: V3 Architecture Freeze v2.2 | **Status**: Proposed

**Decision**: Every Belief carries a monotonic version number and retains immutable version history. Every learning action creates a new version. The system can answer "why do I believe this today?" by tracing the belief's evolution.

```
Belief "Higher Yield → Dollar Up"
  v1: weight=0.85, horizon=5d, preconditions={}
  v2: weight=0.81  ← TIMING_ERR × 2
  v3: weight=0.83, horizon=10d  ← correct after extension
  v4: weight=0.83, preconditions={"core_cpi": ">3%"}  ← EVID_MISSING
```

**Rationale**: Without versioning, belief evolution is lost — the system only reports current state, not its reasoning journey. Versioning enables audit trails, rollback, regime comparison, and V4's "explain your reasoning."

**Consequences**: `BeliefVersion` schema: version_number, created_at, change_reason, diagnosis_report_id, before/after snapshots. `AdaptiveBelief.version_history: list[BeliefVersion]`. Old versions immutable. Rollback supported as emergency mechanism.

---

### DDR-V3-009: Multi-Prediction Model ★ NEW v2.2

**Date**: 2026-07-15 | **Phase**: V3 Architecture Freeze v2.2 | **Status**: Proposed

**Decision**: One Hypothesis generates multiple predictions across related assets (primary/secondary/tertiary). Outcomes and Diagnosis evaluated **per individual prediction**, not at hypothesis level. A hypothesis is not "right/wrong" — specific transmission channels succeed or fail.

```
Hypothesis: "Liquidity Tightening"
  ├── NASDAQ ↓  ✓  (liquidity→equity)
  ├── USD ↑     ✗  (liquidity→fx)      ← This channel failed, not the hypothesis
  └── Gold ↓    ✓  (liquidity→commodity)
```

**Rationale**: Macro hypotheses naturally affect multiple assets. Single-prediction conflates "hypothesis quality" with "specific channel reliability." Per-channel evaluation enables precise learning: narrow the failing channel's conditions, don't reduce the entire hypothesis weight.

**Consequences**: `Prediction` extended with `prediction_tier` and `transmission_channel`. `EvaluationReport.accuracy_by_channel`. Diagnosis per-prediction. Learning actions operate per-channel.

---

### DDR-V3-010: Hypothesis Library & Score ★ NEW v2.2

**Date**: 2026-07-15 | **Phase**: V3 Architecture Freeze v2.2 | **Status**: Proposed

**Decision**: A `HypothesisLibrary` maintains every hypothesis with a composite `HypothesisScore` (5 sub-scores). This is the system's long-term intellectual asset — the Agent's goal is to maximize Library quality, not prediction count.

```
HypothesisScore = f(
    Prediction Accuracy (0.30),
    Evidence Quality    (0.25),
    Calibration         (0.20),
    Consistency         (0.15),
    Learning History    (0.10)
)
```

**Rationale**: Without a Library, the system is stateless between runs — every pipeline starts from scratch. With a Library, the Agent accumulates knowledge: high-score hypotheses drive predictions; deprecated ones are avoided. The Library IS the Agent's intelligence.

**Consequences**: New `HypothesisLibrary` module. `HypothesisScore` schema with 5 sub-scores. KPI-1 derived from Library scores. Hypothesis Generator queries Library for prior beliefs. Library persisted to `data/hypothesis_library/`.

---

### V3 v2.2 Impact Matrix

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

> ✦ = decision impacts this phase | ─ = no impact

---

> **Document Status**: FINAL — 27 DDRs total: V1-V2 (17) + V3 v2.2 proposed (10)  
> **Related**: `docs/V3_ARCHITECTURE.md` for full V3 design (v2.2 — Adaptive Research Agent, Final Freeze)  
> **Next Step**: Architecture review → approval → DDR-V3-001~010 ratified
