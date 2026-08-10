# Contributing to Macro Research Agent

Welcome! This document guides you through contributing to the Macro Cognitive Agent.

## Project Philosophy

This is a **cognitive architecture agent**, not an LLM wrapper. Read the [Architecture Whitepaper](docs/ARCHITECTURE_WHITEPAPER.md) before contributing. Core design principles:

1. **Schema-First** — All inter-module communication uses typed Pydantic schemas. No raw dicts.
2. **Falsifiable Judgments** — Every model conclusion must state "what would prove me wrong."
3. **Confidence Calibration** — Confidence scores are computed, not asserted — see the `_compute_confidence()` formula.
4. **Closed-Loop Learning** — Market → Signal → Hypothesis → Prediction → Outcome → Diagnosis → Calibration → Library.

## Quick Start

```bash
# Clone & install
git clone <repo-url>
cd macro-research-agent
pip install -e ".[dev]"

# Generate a daily memo
python run_daily_memo.py

# Run tests
python -m pytest tests/ -v
```

## Project Structure

```
macro-research-agent/
├── src/
│   ├── research/          # Mental models, frameworks, hypothesis library
│   ├── research_cycle/    # Cycle engine (10 cognitive steps)
│   ├── narrative/         # Narrative detection & reasoning
│   ├── collector/         # Data collectors (Sina, Yahoo, FRED)
│   ├── data_pipeline/     # M1/M2 pipeline
│   ├── schemas/           # Pydantic models (26 schema files)
│   ├── shared/            # Logging, exceptions, utilities
│   └── interfaces/        # Abstract base classes
├── tests/                 # Test suite
├── docs/                  # Architecture docs & DDRs
└── validation/            # Validation protocols
```

## How to Add a New Mental Model

1. Create `src/research/models/<your_model>.py` extending `MentalModel` base class
2. Define monitored indicators in `build_default_registry()` in `model_registry.py`
3. Implement `evaluate(context)` → `ResearchConclusion`
4. Add test cases in `tests/`
5. Run `python run_daily_memo.py` to verify integration

## Testing Standards

- Unit tests in `tests/` root
- Integration tests in `tests/integration/`
- Run before PR: `python -m pytest tests/`
- Model tests must verify confidence calibration formula

## Commit Convention

```
<type>: <short description>

- feat: New feature
- fix: Bug fix  
- refactor: Code restructuring
- docs: Documentation
- test: Test additions/changes
- chore: Build/tooling
```

## Code Style

- Type hints required on all public APIs
- Docstrings in Google-style format
- `from __future__ import annotations` at top of all files
- Logging via `get_logger(__name__)` with structured key=value format

## Pull Request Process

1. Fork and create a feature branch
2. Add/update tests
3. Run `python -m pytest tests/` — all tests must pass
4. Update docs if behavior changes
5. Open PR with description of change + motivation

## Questions?

Open a GitHub Issue or refer to the [Architecture Whitepaper](docs/ARCHITECTURE_WHITEPAPER.md).
