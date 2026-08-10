# Architecture — Macro Research Agent

## 1. Overview

Macro Research Agent is an enterprise-grade AI system designed for automated macroeconomic
research. It follows a modular, layered architecture with strict separation of concerns.

### Guiding Principles

| Principle | Implementation |
|-----------|---------------|
| Single Responsibility | Each module has exactly one reason to change |
| Loose Coupling | Modules communicate via Schemas and Interfaces only |
| High Cohesion | Related logic stays within one module boundary |
| Dependency Injection | Dependencies are injected, not imported directly |
| Open/Closed | Extension via interfaces; modification is prohibited |

---

## 2. Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│                     API Layer                        │
│                  (FastAPI + routes)                  │
├─────────────────────────────────────────────────────┤
│                   State Layer                        │
│               (MacroAgentState)                      │
├──────┬──────┬──────┬──────┬──────┬──────┬───────────┤
│ Coll │ Norm │Analy │ Hypo │Critic│Report│ Scheduler │
│ ector│alizer│  zer │thesis│      │      │           │
├──────┴──────┴──────┴──────┴──────┴──────┴───────────┤
│                  Domain Layer                        │
│     (Hypothesis, Evidence, MacroState, ...)          │
├─────────────────────────────────────────────────────┤
│                 Schema Layer                         │
│     (CollectorInput, AnalyzerOutput, ...)            │
├─────────────────────────────────────────────────────┤
│               Interfaces Layer                       │
│     (Protocol/ABC for all modules)                   │
├─────────────────────────────────────────────────────┤
│              Infrastructure Layer                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │  Memory  │  │ Storage  │  │    Shared         │   │
│  │ (Agent   │  │(DB/Cache │  │ (types, utils,    │   │
│  │ Memory)  │  │ /Vector) │  │  errors, config)  │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 3. Module Responsibilities

### 3.1 Business Modules

| Module | Responsibility | Status |
|--------|---------------|--------|
| `collector` | Fetch raw macro data from external sources (APIs, scrapers) | ✅ |
| `normalizer` | Clean, standardize, and transform raw data into structured form | ✅ |
| `signal` | Generate structured macro signals via Rule Engine + Signal Generator | ✅ |
| `hypothesis` | Generate macro hypotheses (explanations) from analyzed signals | ✅ |
| `critic` | Reflection Engine — belief review: evaluate hypotheses, produce ReflectionReport. **Must NOT modify Hypothesis.** | ✅ |
| `narrative` ★ | Narrative Engine — synthesize Signal + Hypothesis + Reflection into structured research reports | 🔴 MVP |
| `observer` | Observation Layer — statistical description of data before signal generation | 🟡 V1 |
| `scheduler` | Orchestrate periodic execution of research workflows | ⚪ V2 |

> ~~`analyzer`~~ 已废弃，职责由 Observation + Signal + Hypothesis 覆盖。

### 3.2 Infrastructure Modules

| Module | Responsibility | Notes |
|--------|---------------|-------|
| `memory` | **Agent Memory only**: conversation context, short-term/long-term agent memory | Does NOT handle DB persistence |
| `storage` | Database persistence, cache layer, vector store | SQLAlchemy + Alembic migrations |
| `shared` | Types, exceptions, utility functions, config infrastructure | **NO business logic allowed** |
| `api` | FastAPI application, route definitions, middleware | Only depends on Schemas + Domain |

### 3.3 Core Layers

| Layer | Responsibility |
|-------|---------------|
| `domain` | All core business objects: `Hypothesis`, `Evidence`, `MacroState`, `MacroIndicator`, `ReportSection` |
| `schemas` | All inter-module data exchange contracts. **Direct `dict` or `DataFrame` transfer is prohibited.** |
| `interfaces` | Abstract Protocols/ABCs defining module contracts |
| `state` | `MacroAgentState` — all LangGraph nodes **read/write only through State**. No direct module coupling. |

---

## 4. Data Flow (Final — Architecture Freeze)

```
Collector ──(raw data)──► Normalizer ──(structured data)──► Signal Engine
                                                               │
                                                               ▼
                                                          Hypothesis Engine
                                                         (explanation)
                                                               │
                                                               ▼
                                                          Reflection Engine
                                                         (belief review)
                                                               │
                                                               ▼
                                                          Narrative Engine ★
                                                         (structured report)
```

> **MVP 流程**: Collector → Normalizer → Signal → Hypothesis → Reflection → Narrative
> **V1 流程**: Collector → Normalizer → **Observation** → Signal → Hypothesis → Reflection → Narrative
> ~~**Analyzer**~~ 模块已废弃，职责由 Observation (V1) + Signal + Hypothesis 覆盖。

### Critical Constraint: Reflection Engine

The Reflection Engine:
- ✅ Reviews beliefs and produces **ReflectionReport** (verdict, findings, confidence adjustment)
- ✅ May recommend **CONFIRMED / REFUTED / UNCERTAIN**
- ❌ **Must NOT modify**, rewrite, or alter the Hypothesis object
- ❌ Must NOT have write access to the Hypothesis store

---

## 5. Domain Model

All core business objects live in `src/domain/`. They are Pydantic models:

```
Hypothesis
├── id
├── statement
├── evidence: list[Evidence]
├── confidence: float | None
├── status: HypothesisStatus (PENDING | CONFIRMED | REJECTED)
└── created_at

Evidence
├── id
├── source
├── description
├── strength: float
└── type: EvidenceType (SUPPORTING | COUNTER)

MacroState
├── timestamp
├── indicators: list[MacroIndicator]
└── metadata

MacroIndicator
├── name
├── value
├── unit
├── source
└── timestamp
```

---

## 6. Schema Layer

All inter-module communication uses Schema objects (Pydantic models). Examples:

```python
class CollectorInput(BaseModel): ...
class NormalizerOutput(BaseModel): ...
class AnalyzerInput(BaseModel): ...
class AnalyzerOutput(BaseModel): ...
class HypothesisInput(BaseModel): ...
class HypothesisOutput(BaseModel): ...
class CriticInput(BaseModel): ...
class CriticOutput(BaseModel): ...  # contains counter_evidence, confidence only
class ReportInput(BaseModel): ...
class ReportOutput(BaseModel): ...
```

**Rule**: Dict and DataFrame must never cross module boundaries directly.

---

## 7. Agent State

`MacroAgentState` is the single source of truth for LangGraph orchestration:

```python
class MacroAgentState(TypedDict):
    raw_data: list[RawDataEntry]
    normalized_data: list[NormalizedEntry]
    analysis_result: AnalyzerOutput | None
    hypotheses: list[Hypothesis]
    critic_results: list[CriticOutput]
    report: ReportOutput | None
    memory_context: AgentMemoryContext
```

All LangGraph nodes:
- Read only from `MacroAgentState`
- Write only into `MacroAgentState`
- Never couple directly to other modules

---

## 8. shared/ Rules

**Allowed**: types, exceptions/errors, utility functions, config models, constants, logging setup.

**Prohibited**: any business logic, any module-specific logic, any domain model logic.

---

## 9. Directory Structure

```
macro-research-agent/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── requirements.txt              # pip freeze lock file
├── pyproject.toml                # sole source of truth for deps + tool config
├── .pre-commit-config.yaml
│
├── .github/
│   └── workflows/
│       └── ci.yml
│
├── docs/
│   ├── architecture.md
│   ├── prd.md
│   ├── workflow.md
│   ├── roadmap.md
│   ├── engineering_principles.md
│   ├── coding_standard.md
│   └── api_spec.md
│
├── configs/
│   ├── settings.yaml
│   ├── logging.yaml
│   ├── sources.yaml
│   └── prompts.yaml
│
├── src/
│   ├── collector/
│   ├── normalizer/
│   ├── analyzer/
│   ├── hypothesis/
│   ├── critic/
│   ├── report/
│   ├── memory/
│   ├── storage/
│   ├── scheduler/
│   ├── domain/
│   ├── schemas/
│   ├── interfaces/
│   ├── state/
│   ├── shared/
│   ├── api/
│   └── migrations/
│
├── tests/
│   ├── collector/
│   ├── normalizer/
│   ├── analyzer/
│   ├── hypothesis/
│   ├── critic/
│   ├── report/
│   ├── memory/
│   ├── storage/
│   ├── domain/
│   ├── integration/
│   └── fixtures/
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── scripts/
├── logs/
└── data/
    ├── raw/
    ├── processed/
    ├── cache/
    └── snapshot/
```

---

## 10. Technology Stack

| Category | Choice | Purpose |
|----------|--------|---------|
| Web Framework | FastAPI | Async API server |
| ORM | SQLAlchemy 2.0 (async) | Database access |
| Migrations | Alembic | Schema versioning |
| Validation | Pydantic v2 | Domain, Schema, Config |
| Agent Framework | LangGraph | Workflow orchestration |
| LLM | LangChain | LLM integration |
| HTTP Client | httpx (async) | External API calls |
| Data Processing | pandas | Tabular data manipulation |
| Testing | pytest + pytest-asyncio | Unit & integration tests |
| Linting | Ruff | Fast Python linter |
| Formatting | Black | Code formatter |
| Type Checking | MyPy (strict) | Static type checking |
| CI/CD | GitHub Actions | Lint, Test, Build |
| Container | Docker + Compose | Deployment |

---

## 11. Known Architecture Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| LangGraph/LangChain API instability | Medium | Locked minor versions; test suite covers breaking changes |
| Critic-Hypothesis boundary violation | Low | Critic output schema enforces Counter Evidence + Confidence only |
| shared/ becoming a dumping ground | Medium | Lint rule + code review; clear forbidden list in coding_standard.md |
| Async DB driver mismatch with FastAPI | Low | Explicit async driver dependencies (asyncpg, aiosqlite) |

---

## 12. Sprint 1 — Data Pipeline Architecture

### 12.1 Data Flow

```
                    ┌──────────────────────┐
                    │   Yahoo Finance API    │
                    │   (yfinance lib)       │
                    └──────────┬───────────┘
                               │ raw JSON / DataFrame
                               ▼
                    ┌──────────────────────┐
                    │   YahooCollector      │  ← implements CollectorInterface
                    │   src/collector/      │     Single responsibility: API → Schema
                    └──────────┬───────────┘
                               │ MacroDataSchema
                               ▼
                    ┌──────────────────────┐
                    │   DataValidator       │  ← src/validation/ (shared capability)
                    │   (value range,       │     Independent of any specific Collector
                    │    timestamp, nulls,  │
                    │    quality scoring)   │
                    └──────────┬───────────┘
                               │ MacroDataSchema (validated) or ValidationError
                               ▼
                    ┌──────────────────────┐
                    │   DataNormalizer      │  ← src/normalizer/
                    │   (canonicalization   │     ONLY: format, unit, timezone.
                    │    only — NO business │     NO semantic transformations.
                    │    logic)             │
                    └──────────┬───────────┘
                               │ MacroDataSchema (canonicalized)
                               ▼
                    ┌──────────────────────┐
                    │   MacroRepository     │  ← src/storage/ (depends on StorageInterface)
                    │   (Collector never    │     Swappable backend: PG / SQLite / DuckDB
                    │    touches DB directly)│
                    └──────────┬───────────┘
                               │ SQL INSERT
                               ▼
                    ┌──────────────────────┐
                    │   PostgreSQL / SQLite │
                    │   (Alembic managed)   │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Pipeline Health API │
                    │   GET /health         │
                    │   → source_status     │
                    │   → db_status         │
                    │   → last_updated      │
                    │   → component_latency │
                    └──────────────────────┘
```

### 12.2 Data Contract (Task 0)

`MacroDataSchema` is the **single data contract** for the entire pipeline.
All modules communicate exclusively through it. dict, JSON, and DataFrame
transfer across module boundaries is PROHIBITED.

### 12.3 New Modules (Sprint 1)

| Module | Location | Responsibility |
|--------|----------|---------------|
| **validation/** | `src/validation/` | Shared data validation engine. Value range, timestamp sanity, null checks, quality scoring. Independent of any single Collector. |
| **QualityScore** | `src/schemas/macro_data.py` | Composite quality score with factors: Completeness, Timeliness, Consistency, Outlier, Duplicate. Future: source reputation, historical consistency. |

### 12.4 Revised Module Boundaries

| Module | Sprint 0 (original) | Sprint 1 (revised) |
|--------|---------------------|-------------------|
| **collector/** | Fetch raw data, emit via Schema | Fetch raw data, output MacroDataSchema. No DB access. |
| **normalizer/** | Clean, standardize, validate | **Canonicalization only**: format, unit, timezone. NO business semantics. |
| **validation/** | (did not exist) | Independent shared engine. Value range, timestamp, nulls, quality score. |
| **storage/** | DB + cache + vector store | Repository Pattern. Depends on StorageInterface (not concrete DB). Future: PG, DuckDB, Redis, Qdrant. |

### 12.5 Domain Model Extensions

`MacroIndicator` now includes `hypothesis_dimension`:

| Dimension | Examples |
|-----------|----------|
| **Liquidity** | DXY, Fed Funds Rate |
| **Credit** | HYG, Investment Grade Spread |
| **Growth** | GDP, PMI, Industrial Production |
| **Risk Appetite** | VIX, Copper/Gold ratio |

This field eliminates hardcoded mappings in the Analyzer module (Sprint 3+).

### 12.6 Pipeline Health

`GET /health` returns component-level status:

```json
{
  "status": "healthy",
  "components": {
    "api": {"status": "healthy"},
    "collector": {"status": "healthy", "source": "Yahoo", "latency_ms": 245},
    "database": {"status": "healthy", "latency_ms": 12},
    "last_ingested": "2026-07-13T10:30:00Z"
  }
}
```

### 12.7 Design Principles (Sprint 1)

- **Single Responsibility**: Each module has exactly one reason to change
- **Data Contract First**: Schema before code; MacroDataSchema is the backbone
- **Collector Interface**: All collectors (Yahoo, FRED, Bloomberg) implement the same interface
- **Repository Pattern**: Collector never touches DB; Repository abstracts storage backend
- **Validation as Capability**: Shared across all collectors, not coupled to any single one

---

## 13. Sprint 2 — Signal Engine Architecture

### 13.1 Mission

Convert trusted macro data into structured macro signals.
Answers: **"What is happening?"** — NOT "Why?" or "What will happen?"

### 13.2 Data Flow

```
  Sprint 1 Output
       │
       │  (MacroIndicator, MacroDataSchema, history)
       │
       ▼
┌─────────────────────────┐    ┌───────────────────────────┐
│   Signal Generator       │◄───│   Rule Engine              │
│   src/signal/generator   │    │   src/signal/rule_engine   │
│                          │    │                            │
│   generate(indicator,    │    │   configs/signal_rules.yaml │
│    current, history)     │    │   Sprint 2: Threshold only  │
│        ↓                 │    │   Future: Trend/Momentum... │
│   MacroSignalSchema      │    └───────────────────────────┘
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│   Signal Repository      │  ← SqlSignalRepository
│   (SignalRepositoryIF)   │     Separate from MacroRepository
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│   signals table          │  ← Alembic migration 002
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│   GET /signals/snapshot  │  ← Latest signal per indicator
└─────────────────────────┘
```

### 13.3 New Modules

| Module | Location | Responsibility |
|--------|----------|---------------|
| **signal/** | `src/signal/` | Signal Engine: Rule Engine + Signal Generator |
| **SignalRepository** | `src/storage/signal_repository.py` | Signal persistence (separate from data repo) |
| **Signal API** | `src/api/signal_routes.py` | REST endpoint for signal queries |

### 13.4 Data Contracts

| Contract | Location | Purpose |
|----------|----------|---------|
| `MacroSignalSchema` | `src/schemas/signal.py` | Canonical signal format (all modules use this) |
| `SignalEvidence` | `src/schemas/signal.py` | Rule provenance + financial interpretation |
| `SignalSnapshot` | `src/schemas/signal.py` | Point-in-time macro signal picture |

### 13.5 Design Principles (Sprint 2)

- **Deterministic**: Same input → same signal. No randomness, no LLM.
- **Explainable**: Every signal carries full evidence chain (rule + value + interpretation).
- **Configurable**: All thresholds in `signal_rules.yaml`, NOT in Python code.
- **Single-Indicator Generator**: Generator handles one indicator at a time. Multi-indicator logic belongs to Rule Engine (future).
- **Historical Context**: Generator receives history for change detection (future rule types).
- **Threshold MVP**: Sprint 2 implements Threshold only. Architecture supports 6 rule types with zero refactoring.

---

## 14. Sprint 3 — Planner Agent Architecture

### 14.1 Mission

Decompose a user goal into a structured, validated ExecutionPlan.

Planner answers: **"What should we do?"** — NOT "How?", "Why?", or "What happened?"

### 14.2 Data Flow

```
User Goal (string)
     │
     ▼
┌─────────────────────────┐    ┌───────────────────────────────┐
│   RuleBasedPlanner       │◄───│   configs/planning_rules.yaml  │
│   src/planning/planner   │    │                                │
│                          │    │   Goal keywords →               │
│   create_plan(goal)      │    │   Abstract task templates       │
│        ↓                 │    │   (no specific tools/indicators) │
│   ExecutionPlan          │    └───────────────────────────────┘
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│   PlanValidator          │  ← Kahn topological sort + cycle detection
│   src/planning/validator │     Unique IDs + orphan dependency check
└─────────┬───────────────┘
          │
          ▼
   Executor (Sprint 4+) — NOT implemented in Sprint 3
```

### 14.3 Separation of Concerns

```
Planner          → ExecutionPlan   → Executor (future)
(pure planning)     (immutable)       (executes tasks)

Planner does NOT:
  ✗ Execute tasks
  ✗ Call tools
  ✗ Access database
  ✗ Use LLM (Sprint 3: rule-based only)
  ✗ Track execution status
```

### 14.4 New Modules

| Module | Location | Responsibility |
|--------|----------|---------------|
| **planning/** | `src/planning/` | Planner Engine + PlanValidator |
| **PlannerInterface** | `src/interfaces/planner.py` | Abstract contract (future LLMPlanner support) |
| **Planning Schemas** | `src/schemas/planning.py` | Task + ExecutionPlan data contracts |
| **Planning Rules** | `configs/planning_rules.yaml` | Goal → abstract task decomposition patterns |

### 14.5 TaskType — Generic Agent Capability Taxonomy

| Type | Value | Meaning |
|------|-------|---------|
| RETRIEVE | `retrieve` | Fetch data from sources |
| PROCESS | `process` | Transform, normalize, clean |
| ANALYZE | `analyze` | Examine patterns, signals |
| GENERATE | `generate` | Create new output content |
| VALIDATE | `validate` | Verify correctness/quality |
| DECIDE | `decide` | Choose among alternatives (future) |

### 14.6 Design Principles (Sprint 3)

- **Domain Agnostic**: Planner does not know about DXY, US10Y, or any macro-specific entity.
- **Abstract Tasks**: Tasks describe WHAT, not HOW. Executor maps to tools.
- **Immutable Plans**: ExecutionPlan is created once, never modified.
- **No Status Tracking**: Execution status belongs to Executor, not Planner.
- **Configurable Rules**: All task decomposition patterns in `planning_rules.yaml`.
- **LLM-Ready Interface**: `PlannerInterface` ABC enables drop-in LLMPlanner replacement.

---

## 15. Sprint 4 — Agent Executor Architecture

### 15.1 Mission

Execute an ExecutionPlan by dispatching each Task to a registered TaskHandler.
The Executor answers: **"Let's do it."** — NOT "What?", "Why?", or "How to do it?"

### 15.2 Data Flow

```
ExecutionPlan (Sprint 3)
        │
        ▼
┌──────────────────────────────────────────┐
│  AgentExecutor                            │
│  src/executor/executor.py                 │
│                                           │
│  execute(plan)                            │
│    ├── PlanValidator.validate(plan)       │  ← reuse Sprint 3
│    ├── _validate_handler_coverage(plan)   │  ← Sprint 4
│    ├── ExecutionContext(plan_id)          │
│    ├── LOOP:                              │
│    │    ├── _get_ready_tasks(plan, ctx)   │  ← private method
│    │    └── for task in ready:             │
│    │         ├── _get_handler(task)        │  ← private method
│    │         └── result = handler.execute()│
│    │              ├── ctx.record_result()  │
│    │              └── ctx.record_artifacts()│
│    └── ctx.to_execution_result(plan)      │
└──────────────┬───────────────────────────┘
               │
               ▼
        ExecutionResult
        ├── status (COMPLETED / PARTIALLY_COMPLETED / FAILED)
        ├── task_results (per-task status + timing)
        └── artifacts    (business data for Memory/Reflection/Report)
```

### 15.3 Separation of Concerns

```
Planner (Sprint 3)     → ExecutionPlan     → AgentExecutor (Sprint 4)
"what to do"              (immutable)         "execute the plan"

Executor does NOT:
  ○ Generate plans (Planner's job)
  ○ Contain business logic (Handler's job)
  ○ Call LLM
  ○ Access database
  ○ Know about macro entities (DXY, US10Y, signals)

Executor IS:
  ○ An orchestrator: plan → handler → context → result
```

### 15.4 Minimal Architecture (YAGNI + KISS)

Sprint 4 follows Minimal Agent Architecture. Components that would be
modules in a workflow engine are PRIVATE METHODS of AgentExecutor:

| Concept | Implementation | Why |
|---------|---------------|-----|
| Scheduler | `_get_ready_tasks()` private method | Dependency resolution is 10 lines |
| Dispatcher | `_get_handler()` private method | Capability lookup is a dict access |
| Registry | `self._handlers: dict[str, Handler]` | Simple dict, no abstraction needed |

### 15.5 New Modules

| Module | Location | Responsibility |
|--------|----------|---------------|
| **executor/** | `src/executor/` (2 files) | AgentExecutor + ExecutionContext |
| **handlers/** | `src/handlers/` (2 files) | Pluggable TaskHandler implementations |
| **TaskHandlerInterface** | `src/interfaces/task_handler.py` | Abstract contract for handlers |
| **Execution Schemas** | `src/schemas/execution.py` | TaskResult + ExecutionResult |
| **Execution Domain** | `src/domain/execution.py` | TaskResultStatus + ExecutionStatus enums |

### 15.6 Capability Routing

Task dispatch uses **capability strings** (not TaskType) for handler resolution:

```
Task.config["capability"]  →  AgentExecutor._get_handler()  →  TaskHandlerInterface
```

| Capability | Handler | Artifact Produced |
|-----------|---------|-------------------|
| `simple.retrieve` | SimpleRetrieveHandler | `raw_data` |
| `simple.process` | SimpleProcessHandler | `processed_data` |
| `simple.analyze` | SimpleAnalyzeHandler | `analysis` |
| `simple.generate` | SimpleGenerateHandler | `output` |
| `simple.validate` | SimpleValidateHandler | `validation` |

Future Sprints replace `simple.*` with real capabilities:
`macro.yahoo`, `macro.signal`, `macro.hypothesis`, etc.

### 15.7 Artifacts (Primary Data Carrier)

ExecutionContext uses **artifacts** as the primary business data interface:

```
TaskHandler returns TaskResult.artifacts  ← named business outputs
        ↓
Executor merges into context._artifacts
        ↓
Future components (Memory, Reflection, Report) read context.artifacts
```

TaskResult is kept for execution observability (status, timing, errors) — 
NOT as the primary data carrier.

### 15.8 Failure Mode — Strict

One task fails → all downstream tasks (dependent on the failed task) are BLOCKED.
Status becomes `PARTIALLY_COMPLETED` if some tasks succeeded, `FAILED` if none.

### 15.9 Design Principles (Sprint 4)

- **YAGNI**: No Scheduler/Dispatcher/Registry classes — private methods only.
- **KISS**: 2 files in executor/, 2 files in handlers/.
- **First Principles**: execute(plan) → ExecutionResult. That's the whole API.
- **Capability Routing**: TaskType describes WHAT, capability routes to WHO.
- **Artifacts over TaskResults**: Business data flows through artifacts.
- **Strict Dependencies**: Failure blocks downstream (no best-effort mode).
- **Pluggable Handlers**: `register(handler)` extends the executor.
- **Zero Business Logic**: Executor knows nothing about macro research.

---

## 16. Sprint 5 — Tool Layer Architecture

### 16.1 Mission

Build the Tool Layer — a unified abstraction for all external capabilities.
After Sprint 5, every external data source must be accessed through a Tool.

### 16.2 Architecture

```
Handler → ToolManager → ToolRegistry → BaseTool → External System
                           ↓
                     ToolResult (Canonical Data Layer)
                           ↓
                  ExecutionContext.artifacts
```

### 16.3 Key Design Decisions

- **Canonical Data Layer**: Every Tool translates vendor-specific responses into `MacroDataSchema` before returning. The Agent never sees raw API responses.
- **ToolManager is the ONLY entry point**: Handlers never instantiate or import Tools directly.
- **Exceptions never leak**: Tool failures are caught and returned as `ToolResult(FAILED)`, never raised.

### 16.4 New Modules

| Module | Location | Responsibility |
|--------|----------|---------------|
| **tools/base.py** | `src/tools/` | `BaseTool` ABC — async tool contract |
| **tools/registry.py** | `src/tools/` | `ToolRegistry` — capability → tool mapping |
| **tools/manager.py** | `src/tools/` | `ToolManager` — sole entry point for handlers |
| **tools/yahoo_tool.py** | `src/tools/` | `YahooMacroTool` — real yfinance implementation |
| **schemas/tool.py** | `src/schemas/` | `ToolResult` — unified tool output contract |
| **domain/tool.py** | `src/domain/` | `ToolResultStatus` enum |

---

## 17. Sprint 6 — Reasoning Engine (Hypothesis) Architecture

### 17.1 Mission

Transform structured Signals into structured Hypotheses.
A Hypothesis is an **explanation of reality**, not a signal aggregation.

### 17.2 Conceptual Model

```
Observations → Signals → Reasoning → Hypotheses
                              ↑
                         Assumptions
```

### 17.3 Data Flow

```
MacroSignal[] (from Signal Engine / ExecutionContext.artifacts)
        │
        ▼
┌──────────────────────────────────────────┐
│  HypothesisEngine                         │
│  src/hypothesis/engine.py                 │
│                                           │
│  reason(signals)                          │
│    ├── HypothesisGenerator               │
│    │     └── generate explanations        │
│    ├── EvidenceAggregator                 │
│    │     └── classify supporting/         │
│    │         contradicting evidence        │
│    └── ConfidenceCalculator               │
│          └── compute belief confidence    │
└──────────────┬───────────────────────────┘
               │
               ▼
        HypothesisSet
        ├── hypotheses (HypothesisSchema[])
        │     ├── statement (explanation)
        │     ├── confidence (belief)
        │     ├── supporting_evidence (first-class)
        │     ├── contradicting_evidence (first-class)
        │     └── assumptions (basis of reasoning)
        ├── dimensions_covered
        └── summary
```

### 17.4 Key Architecture Decisions

1. **Hypothesis = Explanation, NOT Aggregation**. Each Hypothesis represents one
   explanatory statement (e.g., "Global liquidity is tightening") — NOT a dimension
   group. Dimension is metadata only.

2. **Evidence as First-Class Objects**. Supporting and contradicting evidence are
   stored as `HypothesisEvidence` objects, not bare signal_ids. Reflection (Sprint 7)
   consumes these directly without re-querying Signals.

3. **Assumptions Enable Reflection**. Every Hypothesis carries explicit assumptions
   (e.g., "Dollar strength represents tighter liquidity"). Without assumptions,
   the Agent cannot later challenge its own reasoning.

4. **Confidence = Belief, NOT Agreement**. Confidence measures how strongly the
   Agent believes the explanation — not the proportion of agreeing signals.
   The MVP formula uses signal metrics as a proxy, but the semantic distinction
   is preserved for future refinement.

5. **Rule-Based MVP (No LLM)**. Hypothesis generation uses template-based
   deterministic rules. Templates produce financial English explanations
   from signal patterns.

6. **Public API Expresses Reasoning**: `engine.reason(signals)` — not `generate()`.
   The API reflects cognition, not data transformation.

### 17.5 New Modules

| Module | Location | Responsibility |
|--------|----------|---------------|
| **domain/hypothesis.py** | `src/domain/` | `HypothesisStatus` enum |
| **schemas/hypothesis.py** | `src/schemas/` | `HypothesisEvidence`, `HypothesisSchema`, `HypothesisSet` |
| **hypothesis/engine.py** | `src/hypothesis/` | `HypothesisEngine.reason()` — orchestrator |
| **hypothesis/generator.py** | `src/hypothesis/` | `HypothesisGenerator` — template-based explanation generation |
| **hypothesis/aggregator.py** | `src/hypothesis/` | `EvidenceAggregator` — evidence classification |
| **hypothesis/confidence.py** | `src/hypothesis/` | `ConfidenceCalculator` — belief confidence |
| **handlers/hypothesis_handler.py** | `src/handlers/` | `HypothesisHandler` — Executor integration |

---

## 18. Design Decision Records (DDR)

### DDR-001: Observation → Signal → Hypothesis Layering

**Date**: 2026-07-15

**Decision**: The Agent will introduce a formal Observation Layer in a future Sprint
(Sprint 9 or 10). Signal will be scoped to interpret Observation, and Hypothesis
will interpret Signal. The three layers form a progressive abstraction chain:

```
Raw Data → Observation → Signal → Hypothesis → Reflection
```

**Rationale**:

- Today (Sprint 6): Signal Engine reads raw data directly. This couples Signal
  to data format details that should belong to an Observation Layer.
- The current Hypothesis implementation treats Signal as its input boundary.
  When Observation Layer is introduced, Hypothesis will NOT need to change — it
  will still consume Signal.
- This is designed for natural evolution, not a rewrite.

**Future Impact**:

- **Sprint 9/10**: Introduce `ObservationLayer` between Data Pipeline and Signal Engine.
  Signal Engine will consume `Observation[]` instead of `MacroDataSchema`.
- **No Hypothesis Refactor**: Hypothesis Engine's contract (`Signal[]` → `Hypothesis[]`)
  remains unchanged.

**Status**: Approved. Architecture reserves this layering without implementing it yet.

---

## 19. Sprint 7 — Reflection Engine (Belief Review) Architecture

### 19.1 Mission

Critically evaluate whether the agent should **still believe** its generated hypotheses.
Reflection is a **Belief Review Engine**, not a challenger or rule engine.

### 19.2 Conceptual Model

```
HypothesisSet
     │
     ▼
ReflectionEngine.review(hypothesis_set)
     │
     ├── HypothesisReviewer
     │      └── Answers 3 questions:
     │           1. Is the evidence sufficient?
     │           2. Is the evidence internally consistent?
     │           3. Should we still believe this hypothesis?
     │
     └── BeliefScorer
            └── Adjusts confidence based on review findings
     │
     ▼
ReflectionSet
├── reports (ReflectionReport[])
│     ├── original_confidence → updated_confidence
│     ├── verdict (CONFIRMED / REFUTED / UNCERTAIN)
│     ├── findings (ReflectionFinding[])
│     ├── evidence_sufficiency (high / medium / low)
│     ├── evidence_consistency (consistent / mixed / conflicting)
│     └── review_summary
└── summary
```

### 19.3 Key Architecture Decisions

1. **Reflection = Belief Review, NOT Challenge**. The engine reviews belief, it does not
   intentionally challenge or attack hypotheses. Output is "should we still believe?"
   rather than "here are problems with your thinking."

2. **Three Questions Only**. The Reviewer answers exactly three questions:
   evidence sufficiency, internal consistency, and belief verdict.
   No rule engine, no causation analysis, no individual assumption review.

3. **Finding-based, Not Rule-based**. Issues discovered during review are expressed
   as typed `ReflectionFindings` (evidence_insufficient, conflicting_evidence,
   evidence_quality_low, single_source_risk). Severity (CRITICAL/MAJOR/MINOR)
   determines impact on confidence.

4. **BeliefScorer for Confidence Adjustment**. Confidence is adjusted multiplicatively
   based on sufficiency factor, consistency factor, and cumulative finding penalties.
   This is belief adjustment, not a new confidence formula.

5. **Stateless + Deterministic**. No LLM, no memory, no external data access.
   Input: HypothesisSet → Output: ReflectionSet. Pure function.

6. **No Mutation of Hypothesis**. ReflectionReport is a standalone object.
   Original HypothesisSchema objects are never modified.

### 19.4 Public API

```python
engine = ReflectionEngine()
reflection_set = engine.review(hypothesis_set)
```

The API expresses belief review: `review()` — not `critique()` or `challenge()`.

### 19.5 New Modules

| Module | Location | Responsibility |
|--------|----------|---------------|
| **domain/reflection.py** | `src/domain/` | `ReflectionVerdict`, `FindingSeverity` enums |
| **schemas/reflection.py** | `src/schemas/` | `ReflectionFinding`, `ReflectionReport`, `ReflectionSet` |
| **critic/engine.py** | `src/critic/` | `ReflectionEngine.review()` — orchestrator |
| **critic/reviewer.py** | `src/critic/` | `HypothesisReviewer` — 3-question belief review |
| **critic/scorer.py** | `src/critic/` | `BeliefScorer` — confidence adjustment |
| **handlers/reflection_handler.py** | `src/handlers/` | `ReflectionHandler` (capability: `macro.reflection`) |

### 19.6 Handler Integration

```python
executor.register(ReflectionHandler())

# In execution plan:
Task(
    id="t3",
    type=TaskType.VALIDATE,
    config={"capability": "macro.reflection"},
    dependencies=["t2"],  # t2 = hypothesis.generate
)
```

### 19.7 Agent Responsibility Boundaries

| Component | Responsibility |
|-----------|---------------|
| Planner | What to do |
| Executor | How to execute |
| Hypothesis | What we currently believe |
| **Reflection** | **Whether we should still believe it** |

---

## 20. Design Decision Records (DDR)

### DDR-002: Reflection as Belief Review, Not Challenge

**Date**: 2026-07-15

**Decision**: Reflection Engine is designed as a **Belief Review Engine**, not a
Challenger or Rule Engine. It answers three questions only: (1) Is evidence sufficient?
(2) Is evidence internally consistent? (3) Should we still believe?

**Rationale**:

- An autonomous reasoning agent should review its own beliefs, not attack them.
  "Challenge" implies adversarial posture; "Review" implies measured evaluation.
- The 3-question framework prevents scope creep into rule engine territory.
- No individual assumption review — the review target is the Belief (the whole
  hypothesis), not its component assumptions.
- This keeps the architecture aligned with an autonomous reasoning agent rather
  than a report generator.

**Rejected Alternatives**:

- AssumptionChallenger (adversarial posture, over-engineered for MVP)
- LogicIssue enumeration (creates a rule catalog, violates YAGNI)
- Alternative explanation generation (requires LLM-level reasoning)

**Future Impact**:

- Sprint 8 (Memory): ReflectionReport is a self-contained serializable object
  ready for persistence without modification.
- Future LLM Sprint: Alternative explanation generation can be added as a
  separate pipeline step without changing the current Reflection contract.

**Status**: Approved.

---

## 21. Architecture Freeze — Final Architecture (2026-07-15, Revision 2)

> Sprint S0–S8 完成。架构冻结，后续按 Release Roadmap (MVP → V1 → V2) 开发。

### 21.1 Schema Chain (DDR-010: Schema First Architecture)

所有认知模块仅通过类型化 Pydantic Schema 交换数据。内部实现可变，契约不可变。

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
Narrative Engine → MacroNarrative
```

**强制规则**: 禁止 `dict | tuple | list[Any]` 跨越模块边界传递。

### 21.2 Final Cognitive Pipeline

```
Collector ──► Normalizer ──► [Observation V1] ──► Signal Engine
                                                       │
                                                       ▼
                                                  Hypothesis Engine
                                                       │
                                                       ▼
                                                  Reflection Engine
                                                       │
                                                       ▼
                                                   Belief Memory
                                                       │
                                                       ▼
                                                  Narrative Engine ★
                                                       │
                                                       ▼
                                                  MacroNarrative
                                                 (结构化 Schema)
                                               ┌───┼───┐
                                               ▼   ▼   ▼
                                              CLI API Dashboard
                                          (各自渲染 Markdown/JSON/HTML)
```

- **MVP**: Observation Layer 跳过；Signal Engine 直接从 Normalizer 消费数据。
- **V1**: Observation Layer 插入，Signal Engine 接口升级为消费 `Observation[]`。
- **MVP 核心创新**: `MacroNarrative` 是 Agent 与所有 presentation 层的唯一契约。
  CLI/API/Dashboard 消费 `MacroNarrative`，各自渲染展示格式，不直接消费 Markdown。

### 21.3 Final Module Responsibilities

| 模块 | 路径 | 状态 | 职责 |
|------|------|------|------|
| `collector` | `src/collector/` | ✅ 完成 | 从外部源获取原始宏观数据 |
| `normalizer` | `src/normalizer/` | ✅ 完成 | 清洗、标准化、验证数据 |
| `signal` | `src/signal/` | ✅ 完成 | 阈值规则引擎 + 信号生成器 |
| `hypothesis` | `src/hypothesis/` | ✅ 完成 | 从信号推理宏观假设 |
| `critic` | `src/critic/` | ✅ 完成 | Reflection Engine — 信念审查 |
| `memory` | `src/memory/` | ✅ 完成 | 信念记忆存储 |
| `narrative` ★ | `src/narrative/` | ✅ 完成 (v2.0) | 消费完整认知链 → 输出 `MacroNarrative` Schema（v2.0 含学习章节） |
| `pipeline` | `src/pipeline.py` | ✅ 完成 (v2.0) | `MacroResearchPipeline.run()` — 系统唯一统一入口（v2.0 含 4 新引擎） |
| `outcome` | `src/outcome/` | ✅ v2.0 | Outcome Tracking — 预测 vs 实际评估 |
| `learning` | `src/learning/` | ✅ v2.0 | Learning Engine — EMA 权重更新 + Pattern Mining |
| `calibration` | `src/calibration/` | ✅ v2.0 | Confidence Calibrator — 加权混合校准 |
| `tools` | `src/tools/` | ✅ 完成 | 工具层抽象 + YahooMacroTool |
| `planning` | `src/planning/` | ✅ 完成 | 固定 DAG 任务编排器（不扩展） |
| `executor` | `src/executor/` | ✅ 完成 | 任务执行器 + ExecutionContext |
| `handlers` | `src/handlers/` | 🟡 缺 NarrativeHandler | 可插拔任务处理器 |
| `api` | `src/api/` | 🟡 需扩展 | FastAPI 路由（缺 POST /analyze, GET /report） |
| `cli` | `src/cli/` | 🔴 **MVP** | 命令行入口，消费 `MacroNarrative` 渲染 Markdown |
| `storage` | `src/storage/` | ✅ 完成 | Repository Pattern 持久化 |
| `observer` | `src/observer/` | 🟡 **V1** | Observation Layer |
| `state` | `src/state/` | ⚪ **V2** | LangGraph 状态管理 |
| `scheduler` | `src/scheduler/` | ⚪ **V2** | 定时任务调度 |
| ~~`analyzer`~~ | `src/analyzer/` | ❌ 废弃 | 职责由 Observation + Signal 覆盖 |

### 21.4 MacroNarrative Schema（唯一输出契约）

```python
class MacroNarrative(BaseModel):
    """Agent 与所有 presentation 层的唯一契约。
    CLI/API/Dashboard/PDF 全部消费此 Schema，不直接消费 Markdown。
    """
    summary: str                     # 一句话宏观判断
    macro_story: str                 # 宏观叙事（2-3 段结构化文本）
    liquidity: DimensionNarrative    # 流动性维度
    credit: DimensionNarrative       # 信用维度
    growth: DimensionNarrative       # 增长维度
    inflation: DimensionNarrative    # 通胀维度
    belief_changes: list[BeliefChangeNote]  # 信念变化追踪（与上次 Memory 对比）
    risks: list[RiskItem]            # 风险提示列表
    action_items: list[str]          # 待关注事项
    confidence: float                # 综合置信度 0–1
    generated_at: datetime
```

Presentation 层各取所需：
- CLI → 从 `MacroNarrative` 渲染 Markdown
- API → 序列化 `MacroNarrative` 为 JSON
- Future Dashboard → 从 `MacroNarrative` 填充 UI 组件
- Future PDF → 从 `MacroNarrative` 排版

### 21.5 Key Architecture Decisions

#### DDR-003: Narrative Engine as MVP Priority

**Decision**: Narrative Engine（原 Report 模块）是 MVP 最高优先级交付物。
输出 `MacroNarrative` Schema，而非 Markdown 字符串。

**Rationale**:
- MVP 目标：从数据输入到结构化宏观叙事的完整链路。
- Narrative Engine 是用户可见的唯一交付物。
- `MacroNarrative` 作为结构化 Schema，CLI/API/Dashboard 各自消费渲染。
  避免将 Markdown 字符串作为模块间协议。
- 未来 LLM、Template、HTML、PDF 等所有 presentation 层均可替换，不需重构 Report。

#### DDR-004: MacroResearchPipeline as Unified Entry Point

**Decision**: `MacroResearchPipeline.run()` 是系统唯一统一入口。
命名上明确这是实干对象（Pipeline），而非构造器（Builder）。

**Architecture**:
```
CLI ──► MacroResearchPipeline.run() ◄── API
                    │
                    ▼
           Planner (固定 DAG) → Executor → Handlers → MacroNarrative
```

**API Surface**:
```python
pipeline = MacroResearchPipeline()
result = pipeline.run(goal="macro environment")  # → PipelineResult
# Future:
# pipeline.run_once()   — 单次执行
# pipeline.analyze()    — 简化分析入口
```

`Builder` 是内部构造细节，外部消费者永远只看到 `pipeline.run()`。

#### DDR-005: Planner = Fixed DAG Only

**Decision**: Planner 不再扩展，仅作为固定 DAG 的任务编排器。
不为任何版本增加自主规划能力（LLM task decomposition, dynamic re-planning 等）。

**Rationale**: 宏观研究流程高度结构化，固定 DAG 足够覆盖 MVP–V2 需求。

#### DDR-006: Analyzer Module Deprecated

**Decision**: `src/analyzer/` 正式废弃。分析与解读能力分别由以下模块覆盖：
- **Observation Layer (V1)**: 数据统计描述（百分位、变化率、历史对比）
- **Signal Engine**: 阈值判断和信号分类
- **Hypothesis Engine**: 跨信号的因果推理和假设形成

Analyzer 的模糊定位（"分析数据"）违反了 Single Responsibility 原则。

#### DDR-007: Observation Layer → V1

**Decision**: Observation Layer 从 MVP 调整到 V1，作为 Signal Engine 的质量增强。

**Rationale**:
- MVP 目标是端到端可用，Observation Layer 不阻塞此目标。
- 当前 Signal Engine 直接消费 Normalizer 输出，可以正常工作。
- V1 引入 Observation Layer 时，只需升级 Signal Engine 接口签名，Hypothesis 和 Reflection 不需要改动。

#### DDR-008: State Manager, Scheduler, Monitoring → V2

**Decision**: LangGraph State Manager、Scheduler、Monitoring 全部放入 V2。

**Rationale**:
- MVP 的 ExecutionContext 已足够管理执行状态。
- 定时任务是生产环境需求，MVP 可通过 CLI/API 手动触发。
- Monitoring 是运维需求，非功能需求。

#### DDR-009: Outcome Tracking → Learning (Implemented in v2.0 ✅)

**Decision**: Outcome Tracking → Learning 在 v2.0 中实现。核心思路：追踪报告预测 vs 实际宏观结果，建立反馈闭环，实现信念校准和长期学习。

**v2.0 Implementation** (July 2026):
- `src/outcome/` — OutcomeEvaluator, OutcomeMetrics, OutcomeTracker
- `src/learning/` — BeliefUpdater (EMA), ConfidenceDecay, PatternMiner, LearningEngine
- `src/calibration/` — ConfidenceCalibrator (weighted blend formula)
- `src/signal/composite_signal_generator.py` — Cross-indicator reasoning → MacroThemes
- Pipeline integrated with graceful degradation
- Narrative Engine v2 with learning sections
- API v2 endpoints for beliefs, accuracy, calibration
- 62 tests, all passing

详见 [docs/ddr_v2.md](ddr_v2.md)。

#### DDR-010: Schema First Architecture

**Decision**: 所有认知模块仅通过类型化 Pydantic Schema 交换数据。
内部实现可变，契约不可变。

```
MacroDataSchema → SignalSnapshot → HypothesisSet → ReflectionSet → BeliefRecord[] → MacroNarrative
```

**强制规则**:
- 禁止 `dict` 跨模块边界传递
- 禁止 `tuple` 跨模块边界传递
- 禁止 `list[Any]` 跨模块边界传递
- 每个模块的 `input → output` 类型在 Schema 层显式声明

**Rationale**:
- Schema 是 AI Agent 的 API — 类似于微服务之间的 protobuf/OpenAPI。
- 类型化契约消除隐式约定，降低 Handler 间 artifact key 拼写错误风险。
- 未来 Observation、Outcome、Learning 等所有新模块全部遵守此规则。
- 这是将 Agent 从 "脚本" 升级为 "系统" 的关键架构决策。

### 21.6 Updated Directory Structure

```
src/
├── collector/          # ✅ 完成
├── normalizer/         # ✅ 完成
├── signal/             # ✅ 完成
├── hypothesis/         # ✅ 完成
├── critic/             # ✅ 完成 (Reflection Engine)
├── memory/             # ✅ 完成
├── narrative/          # 🔴 MVP — Narrative Engine → MacroNarrative
├── observer/           # 🟡 V1 — Observation Layer
├── planning/           # ✅ 完成 (固定 DAG)
├── executor/           # ✅ 完成
├── handlers/           # 🟡 缺 NarrativeHandler + SignalHandler
├── tools/              # ✅ 完成
├── storage/            # ✅ 完成
├── domain/             # ✅ 完成
├── schemas/            # 🟡 缺 narrative.py (MacroNarrative, etc.)
├── interfaces/         # ✅ 完成
├── shared/             # ✅ 完成
├── api/                # 🟡 需扩展路由
├── cli/                # 🔴 MVP
├── state/              # ⚪ V2
├── scheduler/          # ⚪ V2
├── pipeline.py         # 🔴 MVP — MacroResearchPipeline
├── analyzer/           # ❌ 废弃
└── migrations/         # ✅ 完成
```

---

## 22. v2.0 — Continuous Learning Architecture

> **Status**: ✅ Implemented (July 2026)  
> **Tests**: 62 passing (v2.0 suite), 86 v1.0 regression tests unaffected  
> **DDR**: [docs/ddr_v2.md](ddr_v2.md)

v2.0 将 Agent 从 "一次性分析器" 升级为 "持续学习研究者"。在 v1.0 的 7 步认知流水线基础上，增加 4 个新引擎，形成完整的认知闭环。

### 22.1 New v2.0 Modules

| 模块 | 路径 | 职责 |
|------|------|------|
| **Outcome Tracking** | `src/outcome/` | 追踪预测 vs 实际结果。计算 hit rate、Brier Score、per-dimension 准确度。 |
| **Learning Engine** | `src/learning/` | 基于历史准确度更新维度信念权重 (EMA)。含衰退、pattern mining。 |
| **Confidence Calibration** | `src/calibration/` | 校准置信度 = raw*0.50 + historical*0.30 + weight*0.20，不超过原始值。 |
| **Composite Signals** | `src/signal/composite_signal_generator.py` | 组合信号 → 宏观主题。8 个预定义主题（Liquidity Tightening/Easing 等）。 |

### 22.2 New v2.0 Schemas

| Schema | 路径 | 用途 |
|--------|------|------|
| `OutcomeRecord` / `PredictionOutcome` / `OutcomeSummary` | `src/schemas/outcome.py` | 结局追踪 |
| `BeliefWeight` / `LearningSummary` | `src/schemas/learning.py` | 信念学习 |
| `ConfidenceCalibration` / `CalibratedConfidenceSet` | `src/schemas/calibration.py` | 置信度校准 |
| `CompositeSignal` / `MacroTheme` / `CompositeSignalSnapshot` | `src/schemas/signal.py` (扩展) | 组合信号 |

### 22.3 Pipeline v2.0 Integration

```
MacroResearchPipeline.run(goal, indicators)
    │
    ├── 1. Signal Generation (v1.0)
    ├── 2. Hypothesis Generation (v1.0)
    ├── 3. Reflection (v1.0)
    ├── 4. Memory Persistence (v1.0)
    ├── 5. Narrative Generation (v1.0)
    │
    └── 6. v2.0 Post-Execution (graceful degradation)
         ├── Outcome Tracking    (try/except → log warning)
         ├── Learning Update     (try/except → log warning)
         ├── Confidence Calib.   (try/except → log warning)
         └── Composite Signals   (try/except → log warning)
```

所有 v2.0 步骤由 try/except 包裹，单个引擎失败不影响整体产出。

### 22.4 API v2 Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | /v2/beliefs | Current belief weights per dimension |
| GET | /v2/learning | Learning summary with patterns |
| GET | /v2/outcomes | Outcome history (filterable) |
| GET | /v2/accuracy | Hit rate, Brier, per-dimension |
| GET | /v2/confidence | Calibrated confidence data |
| POST | /v2/relearn | Manual learning cycle trigger |

### 22.5 Updated Directory Structure

```
src/
├── outcome/            # ✅ v2.0 — Outcome Tracking Engine
├── learning/           # ✅ v2.0 — Learning Engine (EMA + decay + pattern mining)
├── calibration/        # ✅ v2.0 — Confidence Calibrator
├── signal/
│   └── composite_signal_generator.py  # ✅ v2.0 — Cross-indicator reasoning
├── [...]               # (v1.0 modules unchanged)
└── pipeline.py         # ✅ v2.0 — Integrated with 4 new engines
```
