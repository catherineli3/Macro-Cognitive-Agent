# Macro Research Agent — 规则驱动的宏观研究流水线

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **Version**: 3.5 | Python 3.11+
> **Tests**: 821 用例 | 93 测试文件

## 项目定位

一个规则驱动的宏观研究流水线实验项目。用确定性引擎（阈值规则、模板推理、回测校准）处理数据与计算，保证结果可复现、可验证；LLM 层负责表达与历史判断关联。

本项目是作者探索 AI 系统工程化的练习作品：核心架构与引擎设计由作者主导，部分实现由 AI 编程工具辅助生成。

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

## Quick Start

```bash
# Generate a macro research report
macro-agent analyze --goal "macro environment analysis"

# Generate daily CIO macro brief (V11 summary engine)
python run_daily_memo.py

# See JSON output
macro-agent analyze --goal "liquidity analysis" --format json

# List available commands
macro-agent --help
```

**Expected output**: A Markdown report with Executive Summary, Scenario Analysis, Confidence Assessment, Belief Changes, Learning Insights, and Action Recommendations.

---

## Architecture at a Glance

### Cognitive Closed Loop

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
```

### Core Engines

| Engine | Role |
|--------|------|
| **Signal Engine** | Threshold rules → structured signals |
| **Hypothesis Engine** | Template-based reasoning → explanations |
| **Reflection Engine** | Belief review via 3-question framework |
| **Belief Memory** | Persistent belief state + transition tracking |
| **Narrative Engine** | Synthesize cognitive chain → MacroNarrative |
| **Outcome Tracking** | Prediction vs actual evaluation |
| **Learning Engine** | EMA weight updates + Pattern Mining |
| **Confidence Calibrator** | Weighted blend confidence scoring |
| **Composite Signals** | Cross-indicator reasoning → MacroThemes |

### V11 Summary Engine (Daily CIO Brief)

| Phase | Module | Purpose |
|-------|--------|---------|
| Phase 1 | `MacroStateLayer` | Build 5-dimension macro state (growth, inflation, liquidity, credit, risk) |
| Phase 2 | `ChangeDetector` | Detect momentum, divergence, regime shifts |
| Phase 3 | `NarrativeGenerator` | Generate dominant narrative with supporting/contradicting evidence |
| Phase 4 | `CIOBriefGenerator` | Produce 7-section CIO Macro Brief |
| Phase 5 | `SummaryEvaluator` | 5-dimension quality scoring (target >85/100) |

### Key Design Principles

1. **Schema First**: All modules communicate via typed Pydantic schemas — no `dict`, `Any`, or raw strings cross module boundaries
2. **Deterministic**: Core engines produce identical output for identical input — no LLM, no randomness
3. **Graceful Degradation**: Engines wrapped in try/except; single failure never crashes the pipeline
4. **Pipeline owns everything**: `MacroResearchPipeline.run()` is the only entry point

---

## Documentation Map

| Document | Purpose |
|----------|---------|
| **[Architecture Whitepaper](docs/ARCHITECTURE_WHITEPAPER.md)** | Full system architecture, cognitive model, design decisions |
| **[V3 Architecture](docs/V3_ARCHITECTURE.md)** | DDR documentation, Learning Unit, Belief Versioning |
| **[Architecture Decisions](docs/ddr/ARCHITECTURE_DECISIONS.md)** | Consolidated DDRs |
| **[Developer Guide](docs/DEVELOPER_GUIDE.md)** | How to extend: data sources, tools, handlers, engines, pipeline, API |
| **[V3 Roadmap](docs/V3_ROADMAP.md)** | Research intelligence capability roadmap |
| [Architecture History](docs/architecture.md) | Sprint-by-sprint architecture evolution |
| [Release Roadmap](docs/roadmap.md) | MVP → V1 → V2 delivery history |
| [Archive Reports](docs/archive/) | Historical milestone reports (V3.3, V3.4, V3.5) |

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
| `configs/signal_rules.yaml` | Threshold signal rules (4 dimensions) |
| `configs/planning_rules.yaml` | DAG decomposition rules |
| `configs/settings.yaml` | App configuration |
| `configs/prompts.yaml` | LLM prompt templates |

---

## Testing

```bash
# All tests (821 collected)
pytest

# With coverage
pytest --cov=src --cov-report=term -q
```

**Known issue**: `tests/planning/test_planner.py::TestMultiRuleMerging::test_multi_match_merges` — test expects task ID `retrieve_market_data` but planning rule uses `collect_market_data` (naming mismatch after rule rename). All other tests pass.

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

> **July 2026** | Core Documentation: [Architecture Whitepaper](docs/ARCHITECTURE_WHITEPAPER.md)
