# Engineering Principles — Macro Research Agent

> Status: Active | Sprint 0

## Core Principles

### 1. Single Responsibility Principle
Each module has exactly one reason to change. If a module handles both data collection
and data normalization, it must be split.

### 2. Loose Coupling
Modules communicate exclusively through:
- **Interfaces** (Protocol/ABC) — define contracts
- **Schemas** (Pydantic models) — define data shapes

Direct imports between business modules are prohibited.

### 3. High Cohesion
Related logic lives together. Do not scatter collection logic across analyzer or report.

### 4. Dependency Injection
Dependencies are injected via constructor parameters or FastAPI `Depends()`.
Never instantiate dependencies inside business logic.

```python
# ✅ Good
class Analyzer:
    def __init__(self, normalizer: NormalizerProtocol):
        self.normalizer = normalizer

# ❌ Bad
class Analyzer:
    def __init__(self):
        self.normalizer = Normalizer()
```

### 5. Open/Closed Principle
Modules are open for extension (via interfaces) but closed for modification.
To add a new data source, implement `CollectorProtocol` — do not modify `Collector`.

### 6. Explicit over Implicit
All data shapes, error types, and configuration must be explicit (typed).

### 7. Fail Fast
Validate inputs at module boundaries. Use Pydantic validation on all inbound data.

## Anti-Patterns (Prohibited)

- Passing `dict` or `DataFrame` across module boundaries
- Business logic in `shared/`
- Direct coupling between `hypothesis` and `critic`
- Synchronous blocking calls in async context
