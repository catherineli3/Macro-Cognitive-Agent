"""Shared exception hierarchy for the Macro Research Agent.

Design:
    - Single root: MacroAgentError
    - Domain-specific subclasses for each module/boundary
    - All exceptions carry optional 'details' dict for observability
"""

from typing import Any

# ── Root ───────────────────────────────────────────────────────────────────


class MacroAgentError(Exception):
    """Base class for all Macro Research Agent exceptions."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


# ── Sprint 1 — Data Pipeline ───────────────────────────────────────────────


class ConfigurationError(MacroAgentError):
    """Raised when agent configuration is invalid or missing."""


class CollectionError(MacroAgentError):
    """Raised when data collection fails."""


class NormalizationError(MacroAgentError):
    """Raised when data normalization fails."""


class RepositoryError(MacroAgentError):
    """Raised when data persistence fails."""


class PipelineError(MacroAgentError):
    """Raised when the data pipeline encounters an error."""


# ── Sprint 2 — Signal Engine ───────────────────────────────────────────────


class SignalGenerationError(MacroAgentError):
    """Raised when signal generation fails at the Signal Engine level."""


# ── Sprint 3 — Planner ─────────────────────────────────────────────────────


class PlanCreationError(MacroAgentError):
    """Raised when the Planner cannot create a valid ExecutionPlan."""


class PlanValidationError(MacroAgentError):
    """Raised when an ExecutionPlan fails structural validation."""


# ── Sprint 4 — Executor ────────────────────────────────────────────────────


class ExecutionError(MacroAgentError):
    """Raised when the Executor encounters a fatal error (no handler, invalid plan, etc.)."""


# ── Sprint 5 — Tool Layer ──────────────────────────────────────────────────


class ToolError(MacroAgentError):
    """Base exception for Tool Layer errors."""


class ToolNotFoundError(ToolError):
    """Raised when a capability has no registered tool."""


class ToolExecutionError(ToolError):
    """Raised when a tool fails during execution (before ToolResult wrapping)."""


# ── Sprint 6 — Reasoning Engine ────────────────────────────────────────────


class HypothesisError(MacroAgentError):
    """Raised when hypothesis generation or reasoning fails."""


# ── Sprint 7 — Reflection Engine ───────────────────────────────────────────


class ReflectionError(MacroAgentError):
    """Raised when belief review fails at the Reflection Engine level."""
