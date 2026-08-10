# Coding Standard — Macro Research Agent

> Status: Active | Sprint 0

## 1. Tooling

| Tool | Purpose | Config |
|------|---------|--------|
| Black | Code formatting | `pyproject.toml` |
| Ruff | Linting + import sorting | `pyproject.toml` |
| MyPy | Static type checking (strict mode) | `pyproject.toml` |
| Pre-commit | Git hook automation | `.pre-commit-config.yaml` |

## 2. Style Rules

### Naming
- Modules/files: `snake_case` (e.g., `data_collector.py`)
- Classes: `PascalCase` (e.g., `FredCollector`)
- Functions/methods: `snake_case` (e.g., `fetch_indicators`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)
- Private members: `_leading_underscore`

### Type Annotations
All public functions MUST have complete type annotations. No exceptions.

```python
def calculate_gdp_growth(data: list[IndicatorRecord], window: int = 4) -> float:
    ...
```

### Docstrings
Google-style docstrings for all public modules, classes, and functions.

```python
def fetch_gdp_data(series_id: str, start_date: date) -> list[DataPoint]:
    """Fetch GDP time series data from FRED.

    Args:
        series_id: FRED series identifier (e.g., "GDP").
        start_date: Earliest date to fetch data from.

    Returns:
        List of DataPoint objects sorted by date ascending.

    Raises:
        DataSourceError: If the external API is unavailable.
    """
```

### Imports
- Standard library first
- Third-party second
- Local (`src.`) last
- Always use absolute imports: `from src.collector.fred import FredClient`

## 3. shared/ Rules

`src/shared/` MAY contain:
- Type aliases and base types
- Custom exception classes
- Utility/pure functions (no side effects, no business logic)
- Configuration models
- Logging setup

`src/shared/` MUST NOT contain:
- Any business logic
- Module-specific logic
- Domain model definitions (belongs in `domain/`)

## 4. Inter-Module Communication

- All cross-module data MUST use Schema objects (`src/schemas/`)
- `dict` and `DataFrame` MUST NOT cross module boundaries
- Use `Interface` (Protocol/ABC) for all module contracts

## 5. Testing

- Test file naming: `test_<module>.py`
- `pytest` with `pytest-asyncio` for async tests
- Minimum 80% coverage for business logic modules
- Fixtures in `tests/fixtures/`
