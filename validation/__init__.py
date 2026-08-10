"""Validation Layer — Read-Only Analysis.

Validation Isolation Principle:
    Validation must NEVER modify Agent state.
    All modules in this package are read-only.
    They read from: data/ (JSON, SQLite, snapshots)
    They write to: validation/output/ (charts, logs)
    They write to: docs/ (reports)

No src.* imports allowed — to guarantee zero side effects on Agent.
"""

__all__ = [
    "readiness_checker",
    "metric_calculator",
    "statistics_engine",
    "curve_generator",
    "report_builder",
]
