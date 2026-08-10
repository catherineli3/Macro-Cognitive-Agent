# Architecture Whitepaper v1.0

## Macro Research Agent — A Cognitive Architecture for Automated Macroeconomic Research

> **Document Type**: Architecture Whitepaper  
> **Version**: 1.0  
> **Date**: July 2026  
> **Status**: V2 Formal Seal — Architecture Freeze  
> **Author**: Macro Research Agent Team  
> **Target Audience**: System architects, core developers, technical evaluators

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Philosophy](#2-system-philosophy)
3. [Architecture Overview](#3-architecture-overview)
4. [Cognitive Architecture — The Core Innovation](#4-cognitive-architecture--the-core-innovation)
5. [Layer-by-Layer Architecture](#5-layer-by-layer-architecture)
6. [Module Deep Dives](#6-module-deep-dives)
7. [Data Contract Chain](#7-data-contract-chain)
8. [Cognitive Closed Loop v2.0](#8-cognitive-closed-loop-v20)
9. [Execution Model](#9-execution-model)
10. [API & Integration Surface](#10-api--integration-surface)
11. [Design Decision Records](#11-design-decision-records)
12. [Testing Strategy](#12-testing-strategy)
13. [Technology Stack Rationale](#13-technology-stack-rationale)
14. [Maturity Assessment v2.0](#14-maturity-assessment-v20)
15. [Current Limitations & Known Gaps](#15-current-limitations--known-gaps)
16. [Evolution Path to V3](#16-evolution-path-to-v3)

---

## 1. Executive Summary

### 1.1 What We Built

The **Macro Research Agent** is not a demo, not a script, and not a thin LLM wrapper. It is a **Macro Cognitive Agent** — a system with a defined cognitive architecture that performs automated macroeconomic research through a principled pipeline of:

```
Data → Signal → Hypothesis → Reflection → Memory → Outcome → Learning → Calibration → Narrative
```

At v2.0, the system has achieved a **complete cognitive closed loop**: it observes market data, forms structured hypotheses about the macro environment, critically reviews its own beliefs, tracks prediction outcomes, learns from track record, calibrates confidence, and produces professional research narratives.

### 1.2 What Makes It Different

Most "AI agents" in 2026 follow the pattern:
```
User Prompt → LLM → Tool Calls → LLM → Output
```

This Agent follows a fundamentally different paradigm:
```
Data → Deterministic Signal Rules → Template-Based Reasoning → Belief Review → Continuous Learning
```

It is **deterministic, explainable, auditable, and continuously improving** — without depending on LLM black-box reasoning.

### 1.3 Key Metrics

| Metric | v2.0 |
|--------|------|
| **Cognitive Modules** | 10 (Collector, Normalizer, Signal, Hypothesis, Reflection, Memory, Narrative, Outcome, Learning, Calibration) |
| **Schema Contracts** | 12+ typed Pydantic schemas |
| **Test Suite** | 148 tests (86 v1.0 + 62 v2.0) |
| **Architecture Maturity** | 9.3/10 (per external review) |
| **LLM Dependency** | Zero (pure rule-based cognitive engine) |
| **Production Readiness** | Graceful degradation on all v2.0 steps |

---

## 2. System Philosophy

### 2.1 Core Beliefs

The architecture is founded on six principles that govern every design decision:

| Principle | Manifestation |
|-----------|---------------|
| **Cognitive Transparency** | Every decision traceable to deterministic rules and explicit evidence |
| **Schema as Contract** | All inter-module communication via typed Pydantic schemas; no `dict`, `tuple`, or `list[Any]` across boundaries |
| **Separation of Concerns** | Each module has exactly one reason to change; cognitive layers are strictly separated |
| **Explanation over Aggregation** | A hypothesis is an *explanation of reality*, not a statistical summary of signals |
| **Progressive Disclosure** | Architecture reserves future layers (Observation) without implementing them yet |
| **Graceful Degradation** | New engines wrap in try/except; single failure never crashes the pipeline |

### 2.2 What We Deliberately Avoided

- **LLM as core reasoning engine**: Deterministic rules produce explainable, auditable outputs
- **Black-box pipelines**: Every intermediate artifact is a typed schema, inspectable and testable
- **Premature abstraction**: YAGNI applied aggressively; Scheduler, Dispatcher, Registry remain private methods until the use case demands otherwise
- **Report-first design**: The system produces structured cognitive output (`MacroNarrative` Schema), not Markdown strings

### 2.3 System Identity

The Agent is designed as a **Research Assistant with Memory**, not a Chatbot. It:

- Remembers its past beliefs and tracks transitions
- Learns from prediction accuracy over time
- Can tell you *why* it believes something, with full evidence chain
- Knows what it doesn't know (confidence calibration)
- Produces professional-grade structured narratives

---

## 3. Architecture Overview

### 3.1 Four-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                            │
│  CLI (Typer)  │  FastAPI Routes  │  Future: Dashboard, PDF       │
│       All consume MacroNarrative Schema, not raw Markdown        │
├─────────────────────────────────────────────────────────────────┤
│                    ORCHESTRATION LAYER                           │
│  MacroResearchPipeline (single entry) → Planner → Executor       │
│  Fixed DAG: collect → normalize → signal → hypothesis →          │
│              reflection → memory → narrative                     │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│  Signal  │Hypothesis│Reflection│Memory    │ Narrative Engine     │
│  Engine  │ Engine   │ Engine   │ Builder  │ (v2.0 with Learning) │
├──────────┼──────────┼──────────┼──────────┼─────────────────────┤
│ Outcome  │ Learning │Calibration│Composite │                     │
│ Tracking │ Engine   │ Engine    │ Signals  │  ← v2.0 Additions   │
├──────────┴──────────┴──────────┴──────────┴─────────────────────┤
│                    COGNITIVE LAYER (Domain + Schemas)             │
│  All state is typed Pydantic model; all transitions are explicit │
├─────────────────────────────────────────────────────────────────┤
│                    INFRASTRUCTURE LAYER                           │
│  Tools (Yahoo, future: FRED, Bloomberg)                          │
│  Storage (Repository Pattern, SQLite/PostgreSQL)                 │
│  Config (YAML-driven: rules, settings, prompts)                  │
│  Shared (logging, exceptions, utilities — NO business logic)     │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Module Map

```
src/
├── pipeline.py              ★ Single entry point for all execution
│
├── collector/               Data ingestion from external sources
├── normalizer/              Canonicalization: format, unit, timezone
│
├── signal/                  Signal Engine + Composite Signal Generator (v2.0)
│   ├── generator.py         ThresholdSignalGenerator
│   ├── rule_engine.py       YAML-driven threshold rules
│   └── composite_signal_generator.py  Cross-indicator reasoning (v2.0)
│
├── hypothesis/              Reasoning Engine
│   ├── engine.py            HypothesisEngine.reason(signals)
│   ├── generator.py         Template-based hypothesis generation
│   ├── aggregator.py        Evidence classification (supporting/contradicting)
│   └── confidence.py        Multi-factor confidence calculator
│
├── critic/                  Reflection Engine (Belief Review)
│   ├── engine.py            ReflectionEngine.review(hypotheses)
│   ├── reviewer.py          3-question belief review
│   └── scorer.py            Confidence adjustment from findings
│
├── memory/                  Belief Memory System
│   ├── builder.py           BeliefRecordBuilder (HypothesisSet → BeliefRecord[])
│   └── store.py             JSON-file persistence with atomic writes
│
├── narrative/               Narrative Engine ★
│   └── engine.py            Synthesizes full cognitive chain → MacroNarrative
│
├── outcome/        v2.0      Outcome Tracking Engine
│   └── engine.py            OutcomeEvaluator, OutcomeMetrics, OutcomeTracker
│
├── learning/       v2.0      Learning Engine
│   └── learning_engine.py   BeliefUpdater (EMA), ConfidenceDecay, PatternMiner
│
├── calibration/    v2.0      Confidence Calibrator
│   └── confidence_calibrator.py  Weighted blend formula
│
├── planning/                 RuleBasedPlanner (Fixed DAG only)
├── executor/                 AgentExecutor + ExecutionContext
├── handlers/                 Pluggable TaskHandler implementations
├── tools/                    Tool Layer (BaseTool, Registry, Manager)
│
├── domain/                   Pydantic enums and pure business objects
├── schemas/                  All inter-module data exchange contracts
├── interfaces/               Abstract Protocols/ABCs
├── storage/                  Repository Pattern persistence
├── shared/                   Types, logging, config, errors (NO business logic)
│
├── api/                      FastAPI server + routes (v1.0 + v2.0)
├── cli/                      CLI entry point (Typer)
└── renderer/                 Markdown + JSON renderers for MacroNarrative
```

---

## 4. Cognitive Architecture — The Core Innovation

### 4.1 The Cognitive Model

The Agent's cognitive model is a **progressive abstraction chain**:

```
RAW DATA            "DXY = 105.2, US10Y = 4.85%"
    │
    ▼
SIGNAL              "DXY: Strong (bullish, confidence 0.85)"
    │                "US10Y: Elevated (bullish, confidence 0.90)"
    │
    ▼
HYPOTHESIS          "Global liquidity is tightening.
    │                 USD strength and rising yields signal
    │                 reduced dollar availability."
    │
    ▼
REFLECTION          "Evidence is sufficient, internally consistent.
    │                 Should we still believe? → CONFIRMED."
    │
    ▼
MEMORY              BeliefRecord stored: dimension=liquidity,
    │                 direction=bullish, confidence=0.82
    │
    ▼
OUTCOME (v2.0)      "Prediction created. Evaluate in 7 days."
    │
    ▼
LEARNING (v2.0)     "Liquidity predictions: 80% accurate → weight ↑ 0.58"
    │
    ▼
CALIBRATION (v2.0)  "Confidence adjusted: 0.85 → 0.79 (weighted blend)"
    │
    ▼
NARRATIVE           Structured report with all cognitive layers,
                     including What We Learned and Prediction Accuracy
```

Each layer adds **semantic depth** without losing provenance:
- **Signal** answers: "What is happening?"
- **Hypothesis** answers: "Why is it happening?"
- **Reflection** answers: "Should we trust this explanation?"
- **Memory** answers: "What did we believe before?"
- **Outcome** answers: "Were we right?"
- **Learning** answers: "How can we improve?"
- **Narrative** answers: "What's the complete story?"

### 4.2 Why This Architecture Wins

**Deterministic → Explainable**: Every output has a deterministic origin traceable to a rule or template. No black-box generation.

**Layered → Auditable**: Each cognitive step produces a typed Schema artifact. You can inspect `SignalSnapshot`, `HypothesisSet`, or `ReflectionSet` independently.

**Persistent → Learning**: BeliefMemoryStore and OutcomeTracker enable the Agent to improve over time. Track record is not advisory — it directly feeds into confidence calibration.

**Contract-First → Stable**: All 12+ Schema contracts are explicitly defined. Internal implementations can be completely rewritten without affecting downstream consumers.

---

## 5. Layer-by-Layer Architecture

### 5.1 Infrastructure Layer

**Purpose**: Provide capabilities that all business modules consume without knowing implementation details.

| Component | Location | Responsibility |
|-----------|----------|---------------|
| **Tools** | `src/tools/` | Unified abstraction for all external capabilities. `BaseTool` ABC → `ToolRegistry` → `ToolManager`. Canonical Data Layer: every Tool translates vendor-specific responses into `MacroDataSchema`. |
| **Storage** | `src/storage/` | Repository Pattern persistence. `SqlMacroRepository` (observations) + `SqlSignalRepository` (signals). Async SQLAlchemy 2.0 backend: SQLite for dev, PostgreSQL for production. |
| **Config** | `configs/` | YAML-driven configuration. `settings.yaml` (app), `signal_rules.yaml` (12 threshold rules), `planning_rules.yaml` (6 DAG decomposition rules), `prompts.yaml` (LLM templates for future use). |
| **Shared** | `src/shared/` | Types, logging, exceptions, config infrastructure. **Zero business logic. Zero module-specific logic.** |

### 5.2 Cognitive Layer (Domain + Schemas)

**Purpose**: Define the ontology of macro research — what objects exist, what they mean, how they relate.

| Component | Location | Content |
|-----------|----------|---------|
| **Domain** | `src/domain/` | Pure Pydantic enums: `HypothesisStatus`, `ReflectionVerdict`, `SignalDirection`, `SignalStrength`, `RuleType`, `TaskType`, `BeliefStatus`, `TransitionType`, `ConfidenceLevel`, `RiskLevel`, `ExecutionStatus` |
| **Schemas** | `src/schemas/` | Typed data contracts: `MacroDataSchema`, `MacroSignalSchema`, `SignalSnapshot`, `HypothesisSchema`, `HypothesisSet`, `ReflectionReport`, `ReflectionSet`, `BeliefRecord`, `MacroNarrative`, `OutcomeRecord`, `LearningSummary`, `CalibratedConfidenceSet`, `CompositeSignal`, `MacroTheme` |

### 5.3 Cognitive Modules Layer

See [Section 6](#6-module-deep-dives) for detailed descriptions of each module.

### 5.4 Orchestration Layer

**Purpose**: Assemble cognitive modules into executable research runs.

| Component | Location | Responsibility |
|-----------|----------|---------------|
| **MacroResearchPipeline** | `src/pipeline.py` | **Single unified entry point.** `run(goal)` → `PipelineResult`. CLI, API, and future Scheduler all call this. Encapsulates Planner, Executor, Handler registration, and v2.0 engine lifecycle. |
| **RuleBasedPlanner** | `src/planning/` | Goal → `ExecutionPlan` (fixed DAG). Keyword-matches goal against `planning_rules.yaml` to select task decomposition. Output: immutable `ExecutionPlan`. |
| **AgentExecutor** | `src/executor/` | ExecutionPlan → `ExecutionResult`. Dispatches tasks to registered handlers via capability strings. Respects DAG dependencies. Tracks execution context and artifacts. |
| **Handlers** | `src/handlers/` | Pluggable task implementations: `SignalHandler`, `HypothesisHandler`, `ReflectionHandler`, `MemoryHandler`, `NarrativeHandler`. Each implements `TaskHandlerInterface` with a `capability` string. |

### 5.5 Presentation Layer

**Purpose**: Consume `MacroNarrative` Schema and render it in different formats.

| Component | Location | Format |
|-----------|----------|--------|
| **CLI** | `src/cli/main.py` | Renders `MacroNarrative` → Markdown to terminal |
| **API** | `src/api/` | Serializes `MacroNarrative` → JSON + v2.0 learning endpoints |
| **Renderer** | `src/renderer/` | `MarkdownRenderer` + `JsonRenderer` — separate rendering from narrative engine |

> **Critical**: CLI/API/Dashboard consume `MacroNarrative` Schema. They never consume raw Markdown strings. This allows future presentation formats (HTML dashboard, PDF report) to be added without touching the cognitive pipeline.

---

## 6. Module Deep Dives

### 6.1 Collector + Normalizer

```
Yahoo Finance API (yfinance)
        │
        ▼
YahooCollector       ← implements CollectorInterface
        │
        ▼
DataValidator        ← shared validation engine (range, timestamp, nulls, quality)
        │
        ▼
DataNormalizer       ← canonicalization only: format, unit, timezone. NO business logic.
        │
        ▼
MacroRepository      ← Repository Pattern (collector never touches DB)
```

**Key Decisions**:
- Collector emits `MacroDataSchema` only — never raw DataFrames
- Normalizer is purely technical (canonicalization), NOT semantic (no signal generation)
- Repository Pattern isolates storage backend; swap SQLite→PostgreSQL without changing any business code

### 6.2 Signal Engine

```
MacroIndicator + MacroDataSchema + history
        │
        ▼
RuleEngine.evaluate()              ← loads configs/signal_rules.yaml
        │                             (12 threshold rules across 4 dimensions)
        ▼
ThresholdSignalGenerator.generate() ← single-indicator: one signal per call
        │
        ▼
MacroSignalSchema                   ← direction + strength + confidence + evidence
        │
        ▼
SignalSnapshot                      ← point-in-time macro signal picture
```

**12 Signal Rules** (configs/signal_rules.yaml):

| Dimension | Indicator | Threshold | Signal |
|-----------|-----------|-----------|--------|
| Liquidity | DXY | > 105 | Strong Bullish |
| Liquidity | DXY | < 100 | Bearish |
| Liquidity | US10Y | > 5.0% | Strong Bullish |
| Liquidity | US10Y | < 3.0% | Bearish |
| Liquidity | US2Y | > 5.5% | Bullish |
| Credit | HYG | < 70 | Bearish |
| Credit | HYG | > 78 | Bullish |
| Risk Appetite | VIX | > 25 | Risk-Off |
| Risk Appetite | VIX | < 12 | Risk-On |
| Risk Appetite | Gold | > 2500 | Risk-Off |
| Growth | Copper | > 4.5 | Bullish |
| Growth | Copper | < 3.5 | Bearish |

**Signal Aggregation Logic**:
- Direction: conservative bias — bullish+bearish conflict → bearish wins
- Strength: max triggered rule strength
- Confidence: max triggered rule confidence; no triggers → 0.3

**Design Principles**:
- **Deterministic**: Same input → same signal. No randomness, no LLM.
- **Explainable**: Every signal carries full evidence chain (rule + value + interpretation).
- **Configurable**: All thresholds in YAML, not Python code.
- **Single-Indicator**: Generator handles one indicator at a time. Multi-indicator logic → CompositeSignalGenerator (v2.0).

### 6.3 Hypothesis Engine

```
MacroSignal[] (from SignalSnapshot)
        │
        ▼
HypothesisEngine.reason(signals)
        │
        ├── HypothesisGenerator        ← 5 narrative templates
        │      tightening / easing / risk_off / risk_on / divergence
        │
        ├── EvidenceAggregator         ← classify supporting/contradicting
        │
        └── ConfidenceCalculator       ← 35% consistency + 35% strength + 30% coverage
        │
        ▼
HypothesisSet
```

**5 Narrative Templates**:

| Template | Trigger Condition | Example Statement |
|----------|-------------------|-------------------|
| `tightening` | liquidity: bullish + credit: bearish | "Global liquidity is tightening as USD strengthens and credit spreads widen." |
| `easing` | liquidity: bearish + credit: bullish | "Liquidity conditions are easing, supporting risk assets." |
| `risk_off` | risk_appetite: bearish + liquidity: bullish | "Risk-off sentiment dominates as safe-haven demand rises." |
| `risk_on` | risk_appetite: bullish + credit: bullish | "Risk appetite is recovering, driving credit and equity demand." |
| `divergence` | conflicting signals across dimensions | "Divergent signals: liquidity tightening while growth remains resilient." |

**Key Architecture Decisions**:
1. **Hypothesis = Explanation, NOT Aggregation**: Each Hypothesis represents one explanatory statement, not a dimension group. Dimension is metadata only.
2. **Evidence as First-Class Objects**: Supporting and contradicting evidence are `HypothesisEvidence` objects, not bare signal_ids. Reflection consumes these directly.
3. **Assumptions Enable Reflection**: Every Hypothesis carries explicit assumptions (e.g., "Dollar strength represents tighter liquidity"). Without assumptions, the Agent cannot later challenge its own reasoning.
4. **Rule-Based MVP (No LLM)**: Template-based deterministic rules produce financial English explanations from signal patterns.

### 6.4 Reflection Engine

```
HypothesisSet
        │
        ▼
ReflectionEngine.review(hypothesis_set)
        │
        ├── HypothesisReviewer        ← 3 questions:
        │      1. Is evidence sufficient?
        │      2. Is evidence internally consistent?
        │      3. Should we still believe?
        │
        └── BeliefScorer              ← Confidence adjustment
              sufficiency factor * consistency factor * finding penalties
        │
        ▼
ReflectionSet
```

**Finding Types**: `evidence_insufficient`, `conflicting_evidence`, `evidence_quality_low`, `single_source_risk`

**Severity → Impact**: CRITICAL (×0.5), MAJOR (×0.7), MINOR (×0.9)

**Key Decisions**:
- **Reflection = Belief Review, NOT Challenge**: The engine reviews belief; it does not attack hypotheses. "Should we still believe?" not "Here are problems with your thinking."
- **No Mutation of Hypothesis**: `ReflectionReport` is standalone. Original `HypothesisSchema` objects are never modified.
- **Stateless + Deterministic**: No LLM, no memory, no external data. Pure function: `HypothesisSet → ReflectionSet`.

### 6.5 Belief Memory

```
HypothesisSet + ReflectionSet
        │
        ▼
BeliefRecordBuilder             ← maps ReflectionVerdict → BeliefStatus
  CONFIRMED → HELD
  REFUTED → ABANDONED
  UNCERTAIN → IN_DOUBT
        │
        ▼
BeliefMemoryStore               ← JSON-file persistence
  • record() / record_batch()   ← auto-detects TransitionType
  • last_belief(dimension)      ← latest belief per dimension
  • recent_beliefs(dimension,n) ← historical beliefs
  • has_reversal(dimension)     ← direction flip detection
```

**TransitionType**: NEW / STABLE / REINFORCED / WEAKENED / REVERSED

**Persistence**: Atomic writes (temp file → `os.replace`), lazy writes (`_dirty` flag), JSON file at `data/memory/beliefs.json`.

### 6.6 Narrative Engine (v2.0)

```
Inputs (all optional, graceful degradation):
  signals: SignalSnapshot
  hypotheses: HypothesisSet
  reflections: ReflectionSet
  belief_records: list[BeliefRecord]
  learning_summary: LearningSummary           ← v2.0
  calibrated_confidence: CalibratedConfidenceSet  ← v2.0
  outcome_summary: OutcomeSummary             ← v2.0
        │
        ▼
NarrativeEngine.narrate(...)
        │
        ▼
MacroNarrative                                 ← ONLY contract with presentation layers
  ├── summary                   (one-sentence macro judgment)
  ├── macro_story               (2-4 paragraph macro narrative)
  ├── today_key_changes         (belief change tracking)
  ├── liquidity / credit / growth / inflation narratives
  ├── scenario_analysis         (5 scenarios: Soft Landing, Hard Landing, etc.)
  ├── belief_changes            (tracked transitions)
  ├── risks + action_items
  ├── confidence                (raw + calibrated blend)
  └── v2.0 sections             (What We Learned, Prediction Accuracy, Calibration)
```

**5 Scenario Templates**:
| Scenario | Conditions | Base Probability |
|----------|------------|-----------------|
| Soft Landing | growth: stable + inflation: benign | 0.30 |
| Hard Landing | growth: bearish + credit: bearish | 0.10 |
| Inflation Re-acceleration | inflation: bullish + growth: bullish | 0.20 |
| Dollar Strength | liquidity: bullish | 0.25 |
| Risk-On | risk_appetite: bullish + credit: bullish | 0.15 |

### 6.7 Outcome Tracking Engine (v2.0)

```
BeliefRecord → create_outcome() → PENDING PredictionOutcome
        │
        ▼
evaluate(observed_direction) → CORRECT / INCORRECT / PARTIALLY_CORRECT / PENDING
        │
        ▼
OutcomeMetrics.compute_summary() → OutcomeSummary
  • Hit Rate: correct / total_evaluated
  • Brier Score: (1/N) * Σ(p_i - o_i)²
  • Directional Accuracy: bullish/bearish predictions only
  • Per-Dimension Accuracy: liquidity/credit/growth/risk_appetite/inflation
```

**Persistence**: JSON file at `data/memory/outcomes.json`. Separate from BeliefMemoryStore — different lifecycle and query patterns.

### 6.8 Learning Engine (v2.0)

```
OutcomeSummary + OutcomeRecords
        │
        ▼
LearningEngine.learn()
        ├── BeliefUpdater: new_weight = old_weight*(1-lr) + accuracy*lr
        ├── ConfidenceDecay: 14-day half-life for stale dimensions
        └── PatternMiner: best/worst dimensions, directional bias, overconfidence
        │
        ▼
LearningSummary
  ├── dimension_weights
  ├── best_dimension / worst_dimension
  ├── learned_patterns    (human-readable: "Bullish predictions 80% accurate")
  └── decay_applied
```

**Core Algorithm** (EMA):
```
new_weight = old_weight * (1 - 0.1) + dimension_accuracy * 0.1
```

All dimensions initialize at 0.5 (neutral), accumulate evidence over time.

### 6.9 Confidence Calibrator (v2.0)

```
HypothesisSet + ReflectionSet + LearningEngine
        │
        ▼
ConfidenceCalibrator.calibrate_set()
        │
calibrated = raw_confidence * 0.50 + historical_accuracy * 0.30 + dimension_weight * 0.20
        │
        ▼
CalibratedConfidenceSet
  ├── per_hypothesis calibration (raw → calibrated delta)
  ├── average_raw / average_calibrated
  └── rationale (traceable component contributions)
```

**Key Constraint**: Calibrated confidence **NEVER exceeds** raw confidence. The calibrator can only maintain or reduce; it cannot inflate.

### 6.10 Composite Signals (v2.0)

```
SignalSnapshot
        │
        ▼
CompositeSignalGenerator.generate_snapshot()
        │
        ├── Group signals by dimension → CompositeSignal (≥2 indicators agree)
        └── Cross-dimension patterns → MacroTheme (8 predefined themes)
        │
        ▼
CompositeSignalSnapshot
```

**8 MacroThemes**:
| Theme | Conditions |
|-------|-----------|
| Liquidity Tightening | liquidity: bullish + credit: bearish |
| Liquidity Easing | liquidity: bearish + credit: bullish |
| Credit Stress | credit: bearish + risk_appetite: bearish |
| Growth Recovery | growth: bullish + risk_appetite: bullish |
| Growth Slowdown | growth: bearish + liquidity: bullish |
| Inflation Resurgence | inflation: bullish + growth: bullish |
| Risk-On | risk_appetite: bullish + credit: bullish |
| Risk-Off | risk_appetite: bearish + liquidity: bullish |

---

## 7. Data Contract Chain

### 7.1 The Schema Chain (DDR-010)

All cognitive modules communicate exclusively through typed Pydantic Schemas:

```
Collector        → MacroDataSchema
    ↓
Normalizer       → MacroDataSchema (canonicalized)
    ↓
Signal Engine    → SignalSnapshot
    ↓
HypothesisEngine → HypothesisSet
    ↓
ReflectionEngine → ReflectionSet
    ↓
BeliefMemory     → BeliefRecord[]
    ↓
OutcomeTracker   → OutcomeRecord[]     ← v2.0
    ↓
LearningEngine   → LearningSummary     ← v2.0
    ↓
Calibrator       → CalibratedConfidenceSet ← v2.0
    ↓
NarrativeEngine  → MacroNarrative
```

### 7.2 Mandatory Rules

- ❌ `dict` must not cross module boundaries
- ❌ `tuple` must not cross module boundaries
- ❌ `list[Any]` must not cross module boundaries
- ❌ `DataFrame` must not cross module boundaries
- ✅ Every module's `input → output` types are explicitly declared in the Schema layer
- ✅ Internal implementations can change; contracts cannot

---

## 8. Cognitive Closed Loop v2.0

### 8.1 The Complete Loop

```
                    ┌─────────────────────────────────────────┐
                    │         v2.0 Cognitive Closed Loop        │
                    │                                           │
    Observation ──→ Signal ──→ Hypothesis ──→ Reflection       │
         ↑                                       │              │
         │                                       ↓              │
         │                          ┌─────── Memory ──────┐     │
         │                          │  BeliefRecord(s)    │     │
         │                          └────────┬────────────┘     │
         │                                   │                  │
         │                    ┌──────────────┼──────────────┐   │
         │                    ↓              ↓              ↓   │
         │              Outcome        Learning       Composite │
         │              Tracking       Engine          Signals  │
         │                    │              │              │   │
         │                    ↓              ↓              │   │
         │              OutcomeSummary  LearningSummary      │   │
         │                    │              │              │   │
         │                    └──────┬───────┘              │   │
         │                           ↓                      │   │
         │                    Confidence                   │   │
         │                    Calibrator                   │   │
         │                           │                      │   │
         │                           ↓                      ↓   │
         │                    ┌──────────────────────────────┐   │
         │                    │     Narrative Engine v2      │   │
         │                    │  ┌─────────────────────────┐ │   │
         │                    │  │ What We Learned         │ │   │
         │                    │  │ Prediction Accuracy     │ │   │
         │                    │  │ Confidence Calibration  │ │   │
         │                    │  │ Composite Themes        │ │   │
         │                    │  └─────────────────────────┘ │   │
         │                    └──────────────────────────────┘   │
         │                                                       │
         └─────────────────── Narrative ─────────────────────────┘
```

### 8.2 Loop Dynamics

1. **Data → Signal**: Threshold rules convert numeric indicators to directional signals with confidence
2. **Signal → Hypothesis**: Template-based reasoning generates explanatory hypotheses with evidence
3. **Hypothesis → Reflection**: 3-question belief review evaluates sufficiency, consistency, and belief status
4. **Reflection → Memory**: BeliefRecordBuilder maps verdicts to persistent belief state with transition tracking
5. **Memory → Outcome**: Each BeliefRecord creates a pending PredictionOutcome for future evaluation
6. **Outcome → Learning**: EMA weight updates adjust dimension reliability based on track record
7. **Learning → Calibration**: Weighted blend formula adjusts hypothesis confidence downward if track record is poor
8. **Calibration → Narrative**: All cognitive artifacts synthesized into professional MacroNarrative

---

## 9. Execution Model

### 9.1 Pipeline Flow

```
                    User Goal (string)
                         │
                         ▼
                MacroResearchPipeline.run()
                         │
                    ┌────┴────┐
                    ▼         ▼
            RuleBasedPlanner  AgentExecutor
            (goal → DAG)      (DAG → handlers)
                    │              │
                    └──────┬───────┘
                           ▼
                   7-Step Cognitive DAG
                   
  [1] SimpleRetrieveHandler → raw_data
  [2] SimpleProcessHandler  → processed_data
  [3] SignalHandler         → SignalSnapshot
  [4] HypothesisHandler     → HypothesisSet
  [5] ReflectionHandler     → ReflectionSet
  [6] MemoryHandler         → BeliefRecord[]
  [7] NarrativeHandler      → MacroNarrative
                           │
                           ▼
                   v2.0 Post-Execution
  [8] OutcomeEngine         → OutcomeSummary       (try/except)
  [9] LearningEngine        → LearningSummary      (try/except)
  [10] ConfidenceCalibrator → CalibratedConfidenceSet (try/except)
  [11] CompositeSignalGen   → CompositeSignalSnapshot (try/except)
                           │
                           ▼
                   Render (Markdown + JSON)
                           │
                           ▼
                     PipelineResult
```

### 9.2 Graceful Degradation

All v2.0 steps are wrapped in try/except. If all v2.0 engines fail:
- Pipeline produces a valid v1.0-compatible result
- Narrative omits learning sections or shows "Insufficient data."
- 86 v1.0 regression tests continue to pass alongside 62 v2.0 tests

### 9.3 Handler Dispatch

Tasks are dispatched via **capability strings**:

| Capability | Handler | Artifact Produced | Version |
|-----------|---------|-------------------|---------|
| `simple.retrieve` | SimpleRetrieveHandler | `raw_data` | v1.0 |
| `simple.process` | SimpleProcessHandler | `processed_data` | v1.0 |
| `macro.signal` | SignalHandler | `signal_snapshot` | v1.0 |
| `macro.hypothesis` | HypothesisHandler | `hypothesis_set` | v1.0 |
| `macro.reflection` | ReflectionHandler | `reflection_set` | v1.0 |
| `macro.memory` | MemoryHandler | `memory_records` | v1.0 |
| `macro.narrative` | NarrativeHandler | `narrative` | v1.0 |

---

## 10. API & Integration Surface

### 10.1 v1.0 Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | System health (DB, collector, latency) |
| GET | `/` | API info and version |
| POST | `/api/analyze` | Trigger full pipeline execution |
| GET | `/api/report/{id}` | Retrieve report by ID |
| GET | `/api/reports/latest` | Latest report |
| GET | `/api/beliefs` | Current belief state |
| GET | `/signals/snapshot` | Latest signal snapshot |

### 10.2 v2.0 Endpoints (Read-Heavy Observation)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/v2/beliefs` | Current belief weights per dimension |
| GET | `/v2/learning` | Learning summary with patterns |
| GET | `/v2/outcomes` | Outcome history (filterable) |
| GET | `/v2/accuracy` | Hit rate, Brier Score, per-dimension accuracy |
| GET | `/v2/confidence` | Calibrated confidence data |
| POST | `/v2/relearn` | Manual learning cycle trigger |

### 10.3 CLI Interface

```bash
macro-agent analyze "macro environment analysis"     # Full pipeline
macro-agent analyze "liquidity analysis" --format json
macro-agent health                                   # System check
macro-agent signals                                  # Signal snapshot
macro-agent memory                                   # Belief memory
```

---

## 11. Design Decision Records

### DDR Index

| # | Decision | Date | Status |
|---|----------|------|--------|
| DDR-001 | Observation → Signal → Hypothesis Layering (reserved for V1) | 2026-07 | Approved |
| DDR-002 | Reflection as Belief Review, Not Challenge | 2026-07 | Approved |
| DDR-003 | Narrative Engine as MVP Priority (MacroNarrative Schema, not Markdown) | 2026-07 | Approved |
| DDR-004 | MacroResearchPipeline as Unified Entry Point | 2026-07 | Approved |
| DDR-005 | Planner = Fixed DAG Only (no autonomous planning) | 2026-07 | Approved |
| DDR-006 | Analyzer Module Deprecated (split into Observation + Signal + Hypothesis) | 2026-07 | Approved |
| DDR-007 | Observation Layer → V1 (MVP skips it; Signal reads data directly) | 2026-07 | Approved |
| DDR-008 | State Manager, Scheduler, Monitoring → V2 | 2026-07 | Approved |
| DDR-009 | Outcome Tracking → Learning (Implemented in v2.0) | 2026-07 | ✅ Implemented |
| DDR-010 | Schema First Architecture | 2026-07 | Active |
| DDR-v2.1 | Outcome Tracking as Separate Domain | 2026-07 | ✅ Implemented |
| DDR-v2.2 | Learning Engine as EMA Belief Update | 2026-07 | ✅ Implemented |
| DDR-v2.3 | Confidence Calibration as Weighted Blend (never exceeds raw) | 2026-07 | ✅ Implemented |
| DDR-v2.4 | Composite Signals as Deterministic Rule-Based Pattern Matching | 2026-07 | ✅ Implemented |
| DDR-v2.5 | Pipeline Integration — Graceful Degradation | 2026-07 | ✅ Implemented |
| DDR-v2.6 | Narrative Engine v2 — Source-Anchored Learning Sections | 2026-07 | ✅ Implemented |
| DDR-v2.7 | API v2 Endpoints — Read-Only Observation | 2026-07 | ✅ Implemented |

### Key Decision: Deterministic Over LLM

The most consequential architectural decision: **the entire cognitive pipeline is deterministic**.

- Signal Engine: hardcoded threshold rules (YAML-configurable)
- Hypothesis Engine: template-based generation (5 narrative patterns)
- Reflection Engine: 3-question rule-based review
- Learning Engine: EMA formula (no ML)
- Calibrator: fixed weight blend (0.50/0.30/0.20)
- Composite Signals: 8 hardcoded theme definitions

**Rationale**: For a system that professional analysts must trust, explainability and auditability outweigh the flexibility of black-box LLM generation. The architecture reserves LLM integration as an *optional quality enhancement* to existing deterministic modules — not as a replacement.

---

## 12. Testing Strategy

### 12.1 Test Distribution

| Suite | Count | Scope |
|-------|-------|-------|
| **v1.0 Core** | 86 | Collector, Normalizer, Signal, Hypothesis, Reflection, Memory, Pipeline, API, CLI |
| **v2.0 Additions** | 62 | Outcome (26), Learning (17), Calibration (6), Composite (9), E2E Loop (4) |
| **Total** | **148** | Full regression suite |

### 12.2 Test Principles

- **Isolation**: Each cognitive module tested independently with mock inputs
- **Determinism**: All tests produce identical results on every run (no randomness, no external APIs)
- **Schema Validation**: Every test validates that outputs conform to Schema contracts
- **E2E Closed Loop**: Integration tests verify the full cognitive loop (Signal → ... → Learning → Narrative)
- **Graceful Degradation**: Tests verify that v2.0 engine failures don't crash the pipeline

### 12.3 Test Architecture

```
tests/
├── unit/              # Per-module unit tests
│   ├── test_signal.py
│   ├── test_hypothesis.py
│   ├── test_reflection.py
│   ├── test_memory.py
│   ├── test_outcome.py       ← v2.0 (26 tests)
│   ├── test_learning.py      ← v2.0 (17 tests)
│   ├── test_calibration.py   ← v2.0 (6 tests)
│   └── test_composite.py     ← v2.0 (9 tests)
├── integration/
│   ├── test_v2_e2e_learning.py  ← v2.0 (4 tests)
│   └── conftest.py              ← overrides DB init for integration tests
└── conftest.py                   ← shared fixtures
```

---

## 13. Technology Stack Rationale

| Technology | Choice | Rationale |
|-----------|--------|-----------|
| **FastAPI** | Web framework | Native async, Pydantic integration, OpenAPI auto-generation |
| **SQLAlchemy 2.0** | ORM | Async support, mature migration tooling (Alembic) |
| **Pydantic v2** | Validation | Schema-first architecture backbone; all domain objects and contracts |
| **yfinance** | Data source | Free, no API key, covers all needed macro indicators |
| **PyYAML** | Configuration | Human-readable rules, no code changes needed for threshold adjustments |
| **pytest + pytest-asyncio** | Testing | Industry standard, async-native test execution |
| **Typer** | CLI | Type-hint-driven CLI generation, integrates with FastAPI patterns |
| **Ruff + Black + MyPy** | Code quality | Fast linting, consistent formatting, strict type checking |
| **aiosqlite / asyncpg** | Database drivers | SQLite for dev, PostgreSQL for production — same async interface |
| **httpx** | HTTP client | Async HTTP, used for future API data sources |

---

## 14. Maturity Assessment v2.0

### 14.1 Module Maturity (External Review)

| Module | Score | Notes |
|--------|-------|-------|
| Data Pipeline | 10/10 | Robust collector, normalizer, validator, repository pattern |
| Signal Engine | 9/10 | Deterministic, explainable, YAML-configurable |
| Hypothesis Engine | 10/10 | Clean separation: Generator → Aggregator → Confidence |
| Reflection Engine | 10/10 | Minimal, focused 3-question belief review |
| Belief Memory | 10/10 | Atomic writes, transition tracking, lazy persistence |
| Narrative Engine | 9/10 | Rich output, v2.0 learning sections, graceful degradation |
| Outcome Tracking | 9/10 | Hit rate + Brier Score + per-dimension accuracy |
| Learning Engine | 9/10 | EMA + decay + pattern mining; simple and explainable |
| Calibration | 9/10 | Weighted blend, never exceeds raw, traceable provenance |
| API | 8/10 | v1 + v2 endpoints; read-heavy observation pattern |
| CLI | 8/10 | Clean Typer interface; consumes MacroNarrative |
| Scheduler | 7/10 | Basic; deferred to future versions |
| **Overall** | **9.3/10** | Complete cognitive Agent, not a demo |

### 14.2 What v2.0 Achieved

- ✅ Complete cognitive closed loop (10 engines)
- ✅ Continuous learning from prediction track record
- ✅ Confidence calibration with downward-only constraint
- ✅ Cross-indicator composite signals and macro themes
- ✅ Narrative enriched with learning insights
- ✅ API observability for learning state
- ✅ Graceful degradation on all v2.0 steps
- ✅ 148 tests, all passing

---

## 15. Current Limitations & Known Gaps

### 15.1 Cognitive Limitations

**The Agent does not truly "think."** It remains a Rule-based Cognitive Agent:

```
Data → Rule → Template → Report
```

This is not a criticism — it's the deliberately chosen architecture for v1.0–v2.0. But it means:

1. **No autonomous research planning**: The Planner uses a fixed DAG. It cannot decide "today I should investigate X because Y changed."

2. **No evidence graph**: Evidence is stored as flat lists (supporting/contradicting). There's no graph structure connecting evidence across hypotheses, time, and sources.

3. **No research critic**: Reflection asks "should we still believe?" but never asks "what alternative explanations are we missing?" or "are we suffering from survivorship bias?"

4. **No long-term research memory**: Memory stores beliefs, not research cases. When a new Treasury auction happens, the Agent cannot recall "last time this happened, gold rallied 2%."

5. **No tool reasoning**: The pipeline is fixed. The Agent cannot dynamically decide which data sources to query based on the question at hand.

### 15.2 Engineering Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| **No Scheduler** | Medium | All runs triggered manually via CLI/API |
| **No LangGraph State Manager** | Medium | ExecutionContext is simple but limited; no state machine persistence |
| **No Monitoring/Observability** | Medium | No metrics, alerts, or execution tracing beyond logging |
| **No Observation Layer** | Low | Signal Engine reads data directly; reserved for V1 but deferred |
| **Python 3.11 Requirement** | Low | `pyproject.toml` declares 3.11+; CI should enforce this |
| **No Web Dashboard** | Low | All interaction via CLI and API JSON |

---

## 16. Evolution Path to V3

### 16.1 The Next Leap

v2.0 is a complete **Macro Cognitive Agent**. v3.0 should become a **Macro Research Intelligence**.

The difference:

| v2.0 (Current) | v3.0 (Target) |
|----------------|---------------|
| Fixed DAG planning | **Research Planner**: Agent decides what to study |
| Flat evidence lists | **Evidence Graph**: Knowledge graph with weights, sources, time |
| 3-question belief review | **Research Critic**: Searches for missing explanations, biases, counter-examples |
| Belief memory | **Long-Term Research Memory**: Stores cases, analogies, lessons |
| Fixed data pipeline | **Tool Reasoning**: Agent decides which data sources to query dynamically |

### 16.2 V3 Target Architecture

```
                    User Goal
                         │
                         ▼
                Research Planner       ← "What should I study today?"
                         │
        ┌────────────────┼───────────────┐
        ▼                ▼               ▼
  Tool Reasoner     Evidence Graph   Memory Recall
  (dynamic source   (knowledge       (case-based
   selection)        graph)           analogies)
        │                │               │
        └────────────┬───┴───────────────┘
                     ▼
              Hypothesis Engine
                     ▼
             Reflection + Critic    ← "What am I missing?"
                     ▼
             Learning Engine
                     ▼
              Confidence Update
                     ▼
               Narrative Engine
```

### 16.3 Recommended Path Forward

1. ✅ **Architecture Whitepaper v1.0** (this document) — formal V2 seal
2. 📋 **ADR/DDR consolidation** — all 17 decisions organized and traceable
3. 📋 **Developer Guide** — extension patterns for new data sources, tools, handlers
4. 📋 **V3 Roadmap** — research intelligence capabilities separated from engineering upgrades
5. 🔮 **V3 Development** — 5 capabilities executed in dependency order:
   - Research Planner (foundational)
   - Tool Reasoning (enables Planner)
   - Evidence Graph (structural upgrade)
   - Research Critic (quality upgrade)
   - Long-Term Memory (case-based learning)

---

## Appendix A: Directory Structure (v2.0)

```
macro-research-agent/
├── README.md
├── pyproject.toml                    # Sole source of truth for deps + config
├── configs/
│   ├── settings.yaml                 # App configuration
│   ├── signal_rules.yaml             # 12 threshold signal rules
│   ├── planning_rules.yaml           # 6 DAG decomposition rules
│   └── prompts.yaml                  # LLM templates (future)
├── src/
│   ├── pipeline.py                   # ★ MacroResearchPipeline.run()
│   ├── collector/yahoo.py            # Data ingestion
│   ├── normalizer/                   # Canonicalization
│   ├── signal/                       # Signal + Composite (v2.0)
│   ├── hypothesis/                   # Reasoning Engine
│   ├── critic/                       # Reflection Engine
│   ├── memory/                       # Belief Memory
│   ├── narrative/                    # Narrative Engine (v2.0)
│   ├── outcome/                      # Outcome Tracking (v2.0)
│   ├── learning/                     # Learning Engine (v2.0)
│   ├── calibration/                  # Confidence Calibrator (v2.0)
│   ├── planning/                     # RuleBasedPlanner
│   ├── executor/                     # AgentExecutor
│   ├── handlers/                     # 5 cognitive + 5 simple handlers
│   ├── tools/                        # Tool abstraction layer
│   ├── storage/                      # Repository Pattern
│   ├── domain/                       # Pydantic enums
│   ├── schemas/                      # All data contracts
│   ├── interfaces/                   # Abstract Protocols
│   ├── shared/                       # Utilities (no business logic)
│   ├── api/                          # FastAPI (v1.0 + v2.0 routes)
│   ├── cli/                          # Typer CLI
│   └── renderer/                     # Markdown + JSON renderers
├── tests/
│   ├── unit/                         # Per-module unit tests
│   ├── integration/                  # E2E cognitive loop tests
│   └── conftest.py                   # Shared fixtures
├── docs/
│   ├── ARCHITECTURE_WHITEPAPER.md    # ★ This document
│   ├── architecture.md               # Sprint-by-sprint architecture history
│   ├── roadmap.md                    # Release roadmap (MVP → V1 → V2)
│   ├── ddr_v2.md                     # v2.0 Design Decision Records
│   ├── DEVELOPER_GUIDE.md            # Extension guide
│   └── V3_ROADMAP.md                 # V3 research intelligence roadmap
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── data/
│   ├── raw/
│   ├── processed/
│   ├── cache/
│   └── memory/                       # Belief + Outcome persistence
└── scripts/
```

---

## Appendix B: Glossary

| Term | Definition |
|------|-----------|
| **MacroNarrative** | The structured Schema that is the ONLY contract between the Agent and all presentation layers. Contains summary, dimension narratives, scenario analysis, belief changes, risks, and v2.0 learning sections. |
| **BeliefRecord** | A persisted snapshot of what the Agent believes about a macro dimension at a point in time. Includes direction, confidence, status, and transition type. |
| **Cognitive Closed Loop** | The full cycle: Data → Signal → Hypothesis → Reflection → Memory → Outcome → Learning → Calibration → Narrative. Each run feeds the next via persistent state. |
| **Schema-First** | Architecture principle (DDR-010): all inter-module data exchange uses typed Pydantic Schemas. No dict, tuple, or list[Any] crosses module boundaries. |
| **Graceful Degradation** | v2.0 design pattern: each new engine is wrapped in try/except. If it fails, the pipeline continues with degraded (but valid) output. |
| **EMA (Exponential Moving Average)** | Learning algorithm: `new_weight = old_weight * (1 - lr) + accuracy * lr`. Simple, explainable weight update. |
| **Brier Score** | Probabilistic calibration metric: `(1/N) * Σ(p_i - o_i)²`. Lower = better calibrated. |
| **Deterministic Engine** | A module whose output is completely determined by its input. No randomness, no LLM, no external state. All v1.0–v2.0 cognitive engines are deterministic. |

---

> **Document Status**: FINAL — V2 Architecture Seal  
> **Next Milestone**: V3 Roadmap definition  
> **Contact**: For architecture questions, refer to `docs/architecture.md` for sprint history, `docs/ddr_v2.md` for v2.0 decisions, and `docs/DEVELOPER_GUIDE.md` for extension patterns.
