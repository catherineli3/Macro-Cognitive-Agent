# Developer Guide — Macro Research Agent v2.0

> **Document Type**: Developer Guide  
> **Version**: 1.0  
> **Date**: July 2026  
> **Target Audience**: Developers extending the Macro Research Agent

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Architecture Overview (Quick Recap)](#2-architecture-overview-quick-recap)
3. [Adding a New Data Source](#3-adding-a-new-data-source)
4. [Adding a New Tool](#4-adding-a-new-tool)
5. [Adding a New Signal Rule](#5-adding-a-new-signal-rule)
6. [Adding a New Hypothesis Template](#6-adding-a-new-hypothesis-template)
7. [Adding a New Macro Theme](#7-adding-a-new-macro-theme)
8. [Adding a New Cognitive Handler](#8-adding-a-new-cognitive-handler)
9. [Extending the Pipeline](#9-extending-the-pipeline)
10. [Adding a New API Endpoint](#10-adding-a-new-api-endpoint)
11. [Working with Schemas](#11-working-with-schemas)
12. [Testing Patterns](#12-testing-patterns)
13. [Common Pitfalls](#13-common-pitfalls)

---

## 1. Getting Started

### 1.1 Prerequisites

```bash
# Python 3.11+
python --version

# Install in development mode
cd macro-research-agent
pip install -e ".[dev]"

# Verify
python -c "from src.pipeline import MacroResearchPipeline; print('OK')"

# Run all tests
pytest
```

### 1.2 Key Files to Know

| File | Purpose | When to touch |
|------|---------|---------------|
| `src/pipeline.py` | System entry point | Adding new engines/handlers |
| `configs/signal_rules.yaml` | Threshold rules | Adding/changing signal rules |
| `configs/planning_rules.yaml` | DAG decomposition | Adding new task types |
| `src/schemas/` | All data contracts | Adding new schema types |
| `src/handlers/` | Task implementations | Adding new pipeline steps |
| `src/domain/` | Business enums | Adding new enum values |
| `tests/conftest.py` | Shared fixtures | Adding test utilities |

### 1.3 Architecture Rules (DO NOT VIOLATE)

1. **Schema First**: All inter-module data uses typed Pydantic schemas. NO `dict`, `tuple`, or `list[Any]` across boundaries.
2. **No Business Logic in `shared/`**: Only types, logging, config, utilities.
3. **Handlers are Stateless**: Read from context, write artifacts, return results.
4. **Pipeline owns everything**: Consumers never see Planner/Executor/Handler internals.
5. **Graceful Degradation**: New engines in try/except; failure logs warning, doesn't crash.
6. **Deterministic**: Cognitive engines are deterministic. Same input = same output.

---

## 2. Architecture Overview (Quick Recap)

```
MacroResearchPipeline.run(goal)
    │
    ├── Planner: goal → ExecutionPlan (fixed DAG)
    ├── Executor: DAG → handlers → artifacts
    │
    ├── v1.0 Cognitive Pipeline:
    │   Collect → Normalize → Signal → Hypothesis → Reflection → Memory → Narrative
    │
    └── v2.0 Post-Execution Loop:
        Outcome Tracking → Learning → Calibration → Composite Signals
```

**Schema Chain**:
```
MacroDataSchema → SignalSnapshot → HypothesisSet → ReflectionSet → BeliefRecord[] → MacroNarrative
```

---

## 3. Adding a New Data Source

### 3.1 Step-by-Step

To add a new data source (e.g., FRED, Bloomberg, SEC EDGAR):

**Step 1: Create a new Tool**

```python
# src/tools/fred_tool.py
from src.tools.base import BaseTool
from src.schemas.macro_data import MacroDataSchema
from src.schemas.tool import ToolResult, ToolResultStatus

class FredMacroTool(BaseTool):
    @property
    def tool_name(self) -> str:
        return "fred_macro"

    @property
    def capability(self) -> str:
        return "macro.fred"

    async def execute(self, input_data: dict) -> ToolResult:
        """Fetch data from FRED API and translate to MacroDataSchema."""
        try:
            symbol = input_data["symbol"]
            # 1. Call FRED API (httpx or fredapi library)
            # raw_data = await self._fetch_from_fred(symbol)

            # 2. Translate to MacroDataSchema (Canonical Data Layer)
            # schema = MacroDataSchema(
            #     indicator=...,
            #     value=...,
            #     timestamp=...,
            #     source="FRED",
            # )

            # 3. Return ToolResult
            # return ToolResult(status=ToolResultStatus.SUCCESS, data=schema)
            ...
        except Exception as e:
            return ToolResult(status=ToolResultStatus.FAILED, error=str(e))
```

**Step 2: Register the Tool**

```python
# In src/pipeline.py, _ensure_handlers() or wherever tools are initialized:
from src.tools.manager import ToolManager
from src.tools.fred_tool import FredMacroTool

manager = ToolManager.get_instance()
manager.register(FredMacroTool())
```

**Step 3: (Optional) Create a Handler that uses the Tool**

```python
# src/handlers/fred_handler.py
from src.handlers import TaskHandlerInterface
from src.tools.manager import ToolManager

class FredDataHandler(TaskHandlerInterface):
    @property
    def capability(self) -> str:
        return "macro.fred_data"

    async def execute(self, task, context):
        manager = ToolManager.get_instance()
        result = await manager.execute("macro.fred", {"symbol": task.config["symbol"]})
        if result.success:
            context.set_artifact("fred_data", result.data)
        return result
```

### 3.2 Key Principle: Canonical Data Layer

Every Tool must translate vendor-specific responses into `MacroDataSchema` BEFORE returning. The rest of the system should never see raw FRED/Bloomberg/Yahoo data formats.

---

## 4. Adding a New Tool

Tools follow the `BaseTool` ABC:

```python
# src/tools/base.py
class BaseTool(ABC):
    @property
    @abstractmethod
    def tool_name(self) -> str: ...

    @property
    @abstractmethod
    def capability(self) -> str: ...

    @abstractmethod
    async def execute(self, input_data: dict) -> ToolResult: ...
```

### 4.1 Tool Contract

| Requirement | Description |
|-------------|-------------|
| `tool_name` | Unique identifier string |
| `capability` | Matches handler capability strings for routing |
| `execute(input_data)` | Async, returns `ToolResult` (never raises) |
| Canonical Data Layer | Output must be `MacroDataSchema` or domain schema |

### 4.2 Tool Registration

```python
from src.tools.registry import ToolRegistry
from src.tools.manager import ToolManager

# Option A: Direct registration
registry = ToolRegistry()
registry.register("macro.fred", FredMacroTool())

# Option B: Via manager (recommended — single entry point)
manager = ToolManager.get_instance()
manager.register(FredMacroTool())
```

### 4.3 Tool Usage (from Handler)

```python
# Handlers always go through ToolManager — never import Tools directly
manager = ToolManager.get_instance()
result = await manager.execute("macro.yahoo", {"symbols": ["DXY", "US10Y"]})
```

---

## 5. Adding a New Signal Rule

Signal rules are defined declaratively in YAML — no Python code changes needed.

### 5.1 Rule Schema

```yaml
# configs/signal_rules.yaml (add a new entry)

rules:
  - id: "new_rule_id"              # Unique identifier
    indicator: "VIX"               # Must match MacroIndicator name
    dimension: "risk_appetite"     # liquidity | credit | growth | risk_appetite | inflation
    rule_type: "threshold"         # Currently only threshold supported
    condition:
      operator: "gt"               # gt | lt | gte | lte
      value: 30.0                  # Threshold value
    signal:
      direction: "bearish"         # bullish | bearish
      strength: "strong"           # strong | moderate | weak
      confidence: 0.85             # 0.0 - 1.0
    interpretation: "VIX above 30 indicates extreme risk aversion"
```

### 5.2 Supported Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `gt` | Greater than | `value > 30.0` |
| `lt` | Less than | `value < 15.0` |
| `gte` | Greater than or equal | `value >= 30.0` |
| `lte` | Less than or equal | `value <= 15.0` |

### 5.3 Rule Engine Internals (for reference)

```python
# src/signal/rule_engine.py — how rules are evaluated
class RuleEngine:
    def evaluate(self, indicator, current_value, rules) -> list[RuleEvaluation]:
        results = []
        for rule_def in rules:
            if self._matches(indicator, rule_def):
                triggered = self._check_threshold(current_value, rule_def)
                if triggered:
                    results.append(RuleEvaluation(rule=rule_def, triggered=True, ...))
        return results
```

---

## 6. Adding a New Hypothesis Template

Hypothesis templates define how signal patterns map to explanatory statements.

### 6.1 Template Structure

```python
# In src/hypothesis/generator.py — add a new template

# Existing templates: tightening, easing, risk_off, risk_on, divergence

# Add a new template (e.g., "stagflation"):
_stagflation_template = NarrativeTemplate(
    name="stagflation",
    condition=lambda signals: (
        signals.get("inflation", {}).get("direction") == "bullish"
        and signals.get("growth", {}).get("direction") == "bearish"
    ),
    statement_template=(
        "Stagflationary pressures are emerging: {inflation_detail} while {growth_detail}. "
        "This challenging combination constrains policy options."
    ),
    dimension="inflation",  # primary dimension
    assumptions=[
        "Rising inflation coupled with slowing growth indicates supply-side constraints",
        "Traditional monetary policy faces a trade-off between inflation and growth",
    ],
)
```

### 6.2 Template Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Unique template identifier |
| `condition` | `Callable[[dict], bool]` | Lambda function: does this template apply? |
| `statement_template` | `str` | Format string with `{dimension_detail}` placeholders |
| `dimension` | `str` | Primary macro dimension |
| `assumptions` | `List[str]` | Explicit assumptions for Reflection to review later |

### 6.3 Registering the Template

```python
# In HypothesisGenerator.__init__()
self._templates = [
    _tightening_template,
    _easing_template,
    _risk_off_template,
    _risk_on_template,
    _divergence_template,
    _stagflation_template,  # ← ADD HERE
]
```

### 6.4 How Templates Generate Hypotheses

```python
# generator.py — internal flow
def generate(self, signals_by_dimension):
    hypotheses = []
    for template in self._templates:
        if template.condition(signals_by_dimension):
            # Format the statement with actual signal values
            statement = template.statement_template.format(
                inflation_detail=self._describe_signals(signals_by_dimension, "inflation"),
                growth_detail=self._describe_signals(signals_by_dimension, "growth"),
            )
            hypotheses.append(HypothesisSchema(
                statement=statement,
                dimension=template.dimension,
                assumptions=template.assumptions,
                ...
            ))
    return hypotheses
```

---

## 7. Adding a New Macro Theme

MacroThemes are defined in `CompositeSignalGenerator` (v2.0).

### 7.1 Theme Definition

```python
# In src/signal/composite_signal_generator.py

# Add to _THEME_DEFINITIONS list:
{
    "name": "Stagflation Risk",         # Theme name
    "description": "Stagflationary conditions: rising inflation + falling growth",
    "conditions": {                      # dimension: required direction
        "inflation": "bullish",
        "growth": "bearish",
    },
    "min_signals": 2,                    # Minimum dimensions that must match
}

# Example of an existing theme:
{
    "name": "Liquidity Tightening",
    "description": "Dollar strength and rising yields signal tightening financial conditions",
    "conditions": {
        "liquidity": "bullish",
        "credit": "bearish",
    },
    "min_signals": 2,
}
```

### 7.2 Theme Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Short theme name |
| `description` | `str` | Human-readable description |
| `conditions` | `dict[str, str]` | dimension → required direction (bullish/bearish) |
| `min_signals` | `int` | Minimum dimensions that must match (typically 2) |

### 7.3 How Themes are Matched

```python
# composite_signal_generator.py — internal matching logic
def _match_themes(self, signal_snapshot):
    active_themes = []
    for theme_def in self._THEME_DEFINITIONS:
        matches = 0
        for dim, required_dir in theme_def["conditions"].items():
            signals_in_dim = signal_snapshot.get_by_dimension(dim)
            if any(s.direction.value == required_dir for s in signals_in_dim):
                matches += 1
        if matches >= theme_def["min_signals"]:
            active_themes.append(MacroTheme(name=theme_def["name"], ...))
    return active_themes
```

---

## 8. Adding a New Cognitive Handler

Handlers are the bridge between the Executor (orchestration) and the cognitive engines (business logic).

### 8.1 Handler Interface

```python
# src/interfaces/task_handler.py
class TaskHandlerInterface(ABC):
    @property
    @abstractmethod
    def capability(self) -> str: ...

    @abstractmethod
    async def execute(self, task: Task, context: ExecutionContext) -> TaskResult: ...
```

### 8.2 Creating a New Handler

```python
# src/handlers/new_feature_handler.py
from src.handlers import TaskHandlerInterface
from src.schemas.execution import TaskResult, TaskResultStatus

class NewFeatureHandler(TaskHandlerInterface):
    """Handler for a new cognitive capability."""

    @property
    def capability(self) -> str:
        return "macro.new_feature"  # Must be unique

    async def execute(self, task, context) -> TaskResult:
        try:
            # 1. Read input artifacts from context
            input_data = context.get_artifact("some_artifact_key")

            # 2. Call your engine
            # engine = NewFeatureEngine()
            # result = engine.process(input_data)

            # 3. Write output artifact to context
            # context.set_artifact("new_feature_output", result)

            return TaskResult(
                task_id=task.id,
                status=TaskResultStatus.COMPLETED,
                artifacts={"new_feature_output": result},
            )
        except Exception as e:
            return TaskResult(
                task_id=task.id,
                status=TaskResultStatus.FAILED,
                error=str(e),
            )
```

### 8.3 Registering the Handler

```python
# In src/pipeline.py, _ensure_handlers():
from src.handlers.new_feature_handler import NewFeatureHandler

self._executor.register(NewFeatureHandler())
```

### 8.4 Adding to Planning Rules

```yaml
# configs/planning_rules.yaml — add task to the DAG
planning_rules:
  - id: "macro_with_new_feature"
    triggers: ["new feature analysis"]  # keyword match
    tasks:
      - id: "collect"
        type: "retrieve"
        config:
          capability: "simple.retrieve"
      # ... existing tasks ...
      - id: "new_feature"
        type: "analyze"
        config:
          capability: "macro.new_feature"
        dependencies: ["signal"]  # depends on signal completion
```

---

## 9. Extending the Pipeline

### 9.1 Adding a New Post-Execution Step

v2.0 pattern: add new engine to `_ensure_v2_engines()` and wrap execution in try/except.

```python
# In src/pipeline.py

class MacroResearchPipeline:
    def __init__(self):
        # ... existing engines ...
        self._new_engine = None  # ADD

    def _ensure_v2_engines(self):
        # ... existing lazy-init ...
        if self._new_engine is None:
            from src.new_module.engine import NewEngine
            self._new_engine = NewEngine()

    async def run(self, goal, indicators=None):
        # ... existing v1.0 flow ...

        # ── NEW ENGINE (v2.1) ──────────────────────────────────
        new_result = None
        try:
            new_result = self._new_engine.process(some_input)
            logger.info("new_engine_complete", extra={"result": new_result})
        except Exception as e:
            logger.warning("new_engine_skipped: %s", str(e))

        # Add new_result to PipelineResult
        result = PipelineResult(
            # ... existing fields ...
            new_result=new_result,  # ADD to PipelineResult dataclass too
        )
        return result
```

### 9.2 Extending PipelineResult

```python
@dataclass
class PipelineResult:
    # ... existing fields ...

    # ── v2.1 fields ──────────────────────────────────────────
    new_result: Optional[Any] = None
```

### 9.3 Extending the Narrative

```python
# In src/narrative/engine.py — add new section
def narrate(self, ..., new_result=None):
    narrative = MacroNarrative(...)

    # New section — only if data available
    if new_result:
        narrative.metadata["new_section"] = self._render_new_section(new_result)

    return narrative
```

---

## 10. Adding a New API Endpoint

### 10.1 FastAPI Route

```python
# src/api/new_routes.py
from fastapi import APIRouter

router = APIRouter(prefix="/v2.1", tags=["v2.1"])

@router.get("/new-feature")
async def get_new_feature():
    """Get new feature data."""
    result = _new_engine.get_data()
    return {"status": "ok", "data": result}
```

### 10.2 Register in Main App

```python
# src/api/main.py
from src.api.new_routes import router as new_router

app.include_router(new_router)
```

### 10.3 API Design Principles

1. **GET for read, POST for mutation** — minimal write endpoints
2. **Schema as response model** — always return typed Pydantic, never raw dict
3. **Health check for new components** — add to `/health` response

---

## 11. Working with Schemas

### 11.1 Creating a New Schema

```python
# src/schemas/new_feature.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class NewFeatureInput(BaseModel):
    """Input contract for NewFeatureEngine."""
    source_data_id: str
    parameters: dict[str, float]
    timestamp: datetime

class NewFeatureOutput(BaseModel):
    """Output contract for NewFeatureEngine."""
    result_id: str
    score: float
    confidence: float
    rationale: str
    generated_at: datetime
```

### 11.2 Schema File Organization

| File | Contains |
|------|----------|
| `macro_data.py` | `MacroDataSchema`, `QualityScore` |
| `signal.py` | `MacroSignalSchema`, `SignalSnapshot`, `CompositeSignal`, `MacroTheme` |
| `hypothesis.py` | `HypothesisEvidence`, `HypothesisSchema`, `HypothesisSet` |
| `reflection.py` | `ReflectionFinding`, `ReflectionReport`, `ReflectionSet` |
| `narrative.py` | `MacroNarrative`, `DimensionNarrative`, `ScenarioProbability` |
| `memory.py` | `BeliefRecord` |
| `planning.py` | `Task`, `ExecutionPlan` |
| `execution.py` | `TaskResult`, `ExecutionResult` |
| `outcome.py` | `OutcomeRecord`, `PredictionOutcome`, `OutcomeSummary` |
| `learning.py` | `BeliefWeight`, `LearningSummary` |
| `calibration.py` | `ConfidenceCalibration`, `CalibratedConfidenceSet` |
| `tool.py` | `ToolResult` |

### 11.3 Domain Enums

Domain enums define the controlled vocabulary of the system:

```python
# src/domain/signal.py — example
from enum import Enum

class SignalDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"

class SignalStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
```

**Rule**: Add new enum values to existing enums only if backward-compatible. Otherwise, create new enum.

---

## 12. Testing Patterns

### 12.1 Unit Test for a New Engine

```python
# tests/unit/test_new_feature.py
import pytest
from src.new_module.engine import NewEngine

def test_new_engine_basic():
    engine = NewEngine()
    result = engine.process(test_input)
    assert result.score > 0
    assert 0 <= result.confidence <= 1

def test_new_engine_edge_cases():
    engine = NewEngine()
    # Test with empty input
    result = engine.process({})
    assert result.score == 0  # graceful handling
```

### 12.2 Integration Test with Pipeline

```python
# tests/integration/test_new_feature_e2e.py
import pytest
from src.pipeline import MacroResearchPipeline

@pytest.mark.asyncio
async def test_pipeline_with_new_feature():
    pipeline = MacroResearchPipeline()
    result = await pipeline.run(goal="new feature analysis")

    assert result.status.value != "FAILED"
    assert result.new_result is not None  # v2.1 field populated
```

### 12.3 Test Fixture Patterns

```python
# tests/conftest.py — add shared fixtures
import tempfile
import pytest

@pytest.fixture
def isolated_store():
    """Provide an isolated BeliefMemoryStore for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = BeliefMemoryStore(file_path=f"{tmpdir}/test_beliefs.json")
        yield store
```

---

## 13. Common Pitfalls

### 13.1 DO NOT: Dict Across Boundaries

```python
# ❌ BAD: Passing raw dict between modules
def signal_handler(task, context):
    data = {"direction": "bullish", "strength": 0.8}
    context.set_artifact("signals", data)  # dict!

# ✅ GOOD: Use Schema
def signal_handler(task, context):
    signal = MacroSignalSchema(direction="bullish", strength=0.8)
    context.set_artifact("signal_snapshot", SignalSnapshot(signals=[signal]))
```

### 13.2 DO NOT: Business Logic in `shared/`

```python
# ❌ BAD: src/shared/ has macro-specific logic
# src/shared/utils.py
def calculate_liquidity_score(dxy, us10y):  # This belongs in signal/ or hypothesis/
    ...

# ✅ GOOD: shared/ is purely technical
# src/shared/utils.py
def safe_divide(a: float, b: float) -> float:  # Generic utility
    return a / b if b != 0 else 0.0
```

### 13.3 DO NOT: Skip Schema Validation

```python
# ❌ BAD: Creating objects without validation
signal = {"direction": "BULLSH", "strength": 999}  # Typo + out of range

# ✅ GOOD: Pydantic catches errors
signal = MacroSignalSchema(direction="bullish", strength=0.8)
# Wrong direction → ValidationError with clear message
```

### 13.4 DO NOT: Hardcode Rules in Python

```python
# ❌ BAD: Threshold in code
if dxy_value > 105:
    direction = "bullish"

# ✅ GOOD: Threshold in config
# configs/signal_rules.yaml:
#   - indicator: "DXY"
#     condition: {operator: "gt", value: 105}
```

### 13.5 DO NOT: Forget Graceful Degradation

```python
# ❌ BAD: New engine crash kills entire pipeline
new_result = self._new_engine.process(data)  # no try/except

# ✅ GOOD: Graceful degradation
try:
    new_result = self._new_engine.process(data)
except Exception as e:
    logger.warning("new_engine_skipped: %s", e)
    new_result = None
```

### 13.6 DO NOT: Direct Module Coupling

```python
# ❌ BAD: Handler directly instantiates engine
class MyHandler:
    async def execute(self, task, context):
        engine = LearningEngine()  # hard dependency
        ...

# ✅ GOOD: Dependencies injected via constructor or pipeline
class MyHandler:
    def __init__(self, engine=None):
        self._engine = engine

# Better: Pipeline owns engine lifecycle; handler reads from context
```

---

## Quick Reference

| Task | Key File | What to Do |
|------|----------|------------|
| New data source | `src/tools/` | Create new `BaseTool` subclass, register |
| New signal rule | `configs/signal_rules.yaml` | Add YAML rule entry |
| New hypothesis template | `src/hypothesis/generator.py` | Add template + add to `_templates` list |
| New macro theme | `src/signal/composite_signal_generator.py` | Add to `_THEME_DEFINITIONS` list |
| New handler | `src/handlers/` + `src/pipeline.py` | Create handler, register in pipeline |
| New pipeline step | `src/pipeline.py` | Add to `_ensure_v2_engines()` + run() |
| New API endpoint | `src/api/` | Create route file, register in `main.py` |
| New schema | `src/schemas/` | Add Pydantic model file |
| New domain enum | `src/domain/` | Add to existing or create new file |

---

> **Document Status**: FINAL v1.0  
> **Related**: `ARCHITECTURE_WHITEPAPER.md`, `ddr/ARCHITECTURE_DECISIONS.md`
