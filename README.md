# Macro Research Agent v3.0 — Macro Cognitive Agent

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/architecture-9.3%2F10-brightgreen.svg)](docs/ARCHITECTURE_WHITEPAPER.md)

> **Version**: 3.0.0 | **Status**: Portfolio Release | Python 3.11+
> **Architecture Maturity**: 9.3/10 | **Tests**: 93 files, 148+ test cases | **DDRs**: 27 ratified

## What is this?

A **Macro Cognitive Agent** — not a demo, not a script, not an LLM wrapper. It's an enterprise-grade AI system with a defined cognitive architecture that performs automated macroeconomic research through a **10-engine closed loop**:

```
Data → Signal → Hypothesis → Reflection → Memory → Outcome → Learning → Calibration → Narrative
```

It generates professional **MacroNarrative** reports with scenario analysis, confidence assessment, belief change tracking, learning insights, and action recommendations — all from market data, with zero LLM dependency.

---

## 5-Minute Setup

```bash
# 1. Clone & enter
cd macro-research-agent

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 3. Install
pip install -e ".[dev]"

# 4. Verify
python -c "from src.pipeline import MacroResearchPipeline; print('OK')"
```

## 5-Minute First Run

```bash
# Generate a macro research report
macro-agent analyze --goal "macro environment analysis"

# See JSON output
macro-agent analyze --goal "liquidity analysis" --format json

# List available commands
macro-agent --help
```

**Expected output**: A Markdown report with sections including Executive Summary, Scenario Analysis, Confidence Assessment, What We Learned, Prediction Accuracy, and Action Items.

---

## Architecture at a Glance

### Cognitive Closed Loop (v2.0)

```
Observation → Signal → Hypothesis → Reflection → Memory
                                                │
                ┌───────────────────────────────┤
                ↓                               ↓
          Outcome Tracking               Composite Signals
                │                               │
                ↓                               ↓
          Learning Engine                MacroThemes
                │                               │
                ↓                               │
       Confidence Calibration                   │
                │                               │
                └───────────┬───────────────────┘
                            ↓
                  Narrative Engine v2
             (含 What We Learned /
              Prediction Accuracy /
              Confidence Calibration 章节)
```

### 10 Cognitive Engines

| Engine | Role | Version |
|--------|------|---------|
| **Signal Engine** | Threshold rules → structured signals | v1.0 |
| **Hypothesis Engine** | Template-based reasoning → explanations | v1.0 |
| **Reflection Engine** | 3-question belief review | v1.0 |
| **Belief Memory** | Persistent belief state + transition tracking | v1.0 |
| **Narrative Engine** | Synthesize full cognitive chain → MacroNarrative | v2.0 |
| **Outcome Tracking** | Prediction vs actual evaluation (Hit Rate, Brier Score) | v2.0 |
| **Learning Engine** | EMA weight updates + Pattern Mining | v2.0 |
| **Confidence Calibrator** | Weighted blend: raw×0.50 + historical×0.30 + weight×0.20 | v2.0 |
| **Composite Signals** | Cross-indicator reasoning → 8 MacroThemes | v2.0 |
| **Tool Layer** | Unified abstraction for all external data sources | v1.0 |

### Key Design Principles

1. **Schema First**: All modules communicate via typed Pydantic Schemas — no `dict`, `Any`, or raw strings cross module boundaries (DDR-010)
2. **Deterministic**: All cognitive engines produce identical output for identical input — no LLM, no randomness
3. **Graceful Degradation**: v2.0 engines wrapped in try/except; single failure never crashes the pipeline
4. **Pipeline owns everything**: `MacroResearchPipeline.run()` is the only entry point

---

## Documentation Map

| Document | Purpose |
|----------|---------|
| **[Architecture Whitepaper](docs/ARCHITECTURE_WHITEPAPER.md)** ★ | Formal V2 seal — full system architecture, cognitive model, design decisions |
| **[V3 Architecture Freeze](docs/V3_ARCHITECTURE.md)** ★ | V3 v2.2 Final: 10 DDRs, Learning Unit, Belief Versioning, Multi-Prediction, Hypothesis Library & Score; 4-KPI |
| **[Architecture Decisions](docs/ddr/ARCHITECTURE_DECISIONS.md)** | Consolidated 27 DDRs (17 ratified + 10 V3 v2.2 proposed) |
| **[Developer Guide](docs/DEVELOPER_GUIDE.md)** | How to extend: data sources, tools, handlers, engines, pipeline, API |
| **[V3 Roadmap](docs/V3_ROADMAP.md)** | 5 research intelligence capabilities + 2 engineering upgrades |
| [Architecture History](docs/architecture.md) | Sprint-by-sprint architecture evolution (S0–S8) |
| [Release Roadmap](docs/roadmap.md) | MVP → V1 → V2 delivery history |
| [v2.0 DDR Details](docs/ddr_v2.md) | Detailed v2.0 design decision records |

---

## Quick Reference

### CLI Commands

| Command | Purpose |
|---------|---------|
| `macro-agent analyze --goal <goal>` | Run full pipeline |
| `macro-agent latest` | Show latest report |
| `macro-agent beliefs` | View belief memory |
| `uvicorn src.api.main:app` | Start API server |
| `python run_daily_memo.py` | Generate daily macro memo |

### API Endpoints

**v1.0:**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | System health |
| POST | `/api/analyze` | Run analysis |
| GET | `/api/signals/snapshot` | Signal snapshot |
| GET | `/api/beliefs` | Belief memory |

**v2.0:**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/v2/beliefs` | Belief weights per dimension |
| GET | `/v2/learning` | Learning summary + patterns |
| GET | `/v2/outcomes` | Outcome history |
| GET | `/v2/accuracy` | Hit rate, Brier Score |
| GET | `/v2/confidence` | Calibrated confidence |
| POST | `/v2/relearn` | Manual learning cycle |

### Configuration

| File | Purpose |
|------|---------|
| `configs/signal_rules.yaml` | 12 threshold signal rules (4 dimensions) |
| `configs/planning_rules.yaml` | 6 DAG decomposition rules |
| `configs/settings.yaml` | App configuration |
| `configs/prompts.yaml` | LLM prompt templates (future use) |

---

## Testing

```bash
# All tests (148 total: 86 v1.0 + 62 v2.0)
pytest

# v2.0 suite only
pytest tests/unit/test_outcome.py tests/unit/test_learning.py -v

# E2E cognitive loop
pytest tests/integration/test_v2_e2e_learning.py -v

# With coverage
pytest --cov=src --cov-report=term -q
```

---

## Tech Stack

| Category | Choice |
|----------|--------|
| Web Framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| Validation | Pydantic v2 |
| Data | pandas, yfinance, httpx |
| Config | YAML (PyYAML) |
| Testing | pytest + pytest-asyncio |
| Code Quality | Ruff + Black + MyPy (strict) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Container | Docker + Compose |

---

> **V3 Architecture** | July 2026 | **Core Documentation**: [Architecture Whitepaper](docs/ARCHITECTURE_WHITEPAPER.md)
