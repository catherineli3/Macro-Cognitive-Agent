# Changelog

All notable changes to the Macro Research Agent.

---

## [3.0.0] — 2026-07-30

### Portfolio Release (First Public)

This release marks the transition from internal prototype to portfolio-grade open-source project.

**Architecture:**
- 10-Engine Cognitive Closed Loop (Market → Signal → Hypothesis → Multi-Prediction → Outcome → Diagnosis → Learning → Calibration → Library)
- 7 Mental Models with unified ResearchConclusion output format
- Schema-First design: 26 Pydantic schema files, zero raw dict communication
- Narrative Detection → Belief Engine → Falsifiable Judgment pipeline

**Fixes (from audit):**
- Fixed NarrativeDetector bypass: MentalModel outputs now properly feed into narrative pipeline
- Fixed ResearchConclusion parameter: `dimension=` → `domain=` in cycle engine
- Lowered Framework MIN_CLUSTER_SIZE from 5 to 3 (fixes empty framework formations)
- Added proper test import path handling in `tests/conftest.py`
- Removed `.env` from repo, kept `.env.example` as template
- Unified version string to 3.0.0 (was inconsistent 2.0.0/V3 across files)

**Data:**
- Sina Finance collector for real-time US market prices (free, works from China)
- Daily/Weekly change comparison with local snapshot history
- Synthetic data fallback for macroeconomic indicators (GDP, CPI, etc.)

**Documentation:**
- Cleaned docs from 49 to 13 core files
- Added CONTRIBUTING.md
- Added CHANGELOG.md
- Architecture whitepaper remains as authoritative reference

**Known Limitations:**
- FRED/WorldBank collectors disabled pending API key configuration
- Yahoo Finance rate-limited in many network environments
- Macroeconomic indicators (CPI/GDP/unemployment) use research-grade estimates
- Test suite requires `pip install -e ".[dev]"` for imports to resolve

---

## [2.0.0] — 2026-06

### Closed-Loop Architecture

- Mental Model framework with confidence calibration formula
- Hypothesis generator and library
- Research cycle engine with multi-step cognitive pipeline
- Belief versioning and outcome diagnosis

---

## [1.0.0] — 2026-05

### Initial Framework

- M1/M2 data pipeline
- Basic state vector computation
- Regime detector
- Early narrative engine
