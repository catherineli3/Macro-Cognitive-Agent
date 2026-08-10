# Workflow Design — Macro Research Agent

> Status: Draft | Sprint 0

## 1. Workflow Overview

The core research workflow is a LangGraph state machine:

```
START → Collector → Normalizer → Analyzer → Hypothesis → Critic → Report → END
```

## 2. Node Details

| Node | Input | Output | Description |
|------|-------|--------|-------------|
| Collector | Schedule trigger | RawDataEntry[] | Fetch macro data from configured sources |
| Normalizer | RawDataEntry[] | NormalizedEntry[] | Clean and standardize |
| Analyzer | NormalizedEntry[] | AnalyzerOutput | Statistical analysis |
| Hypothesis | AnalyzerOutput | Hypothesis[] | Generate research hypotheses |
| Critic | Hypothesis[] | CriticOutput[] | Counter-evidence + confidence |
| Report | All upstream | ReportOutput | Final structured report |

## 3. State

All nodes read/write exclusively through `MacroAgentState` (TypedDict).
Direct module coupling is prohibited.

## 4. Critic Constraint

The Critic node:
- Reads hypotheses from state
- Outputs `CriticOutput` (counter_evidence, confidence only)
- Does NOT modify Hypothesis objects
