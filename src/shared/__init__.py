"""Shared module — Infrastructure code.

ALLOWED content:
    - Type aliases and base types
    - Custom exception/error classes
    - Utility/pure functions (no side effects)
    - Configuration models and loaders
    - Logging setup helpers
    - Reliability utilities (timeout, retry, metrics)
    - Constants and enums

PROHIBITED content:
    - Any business logic
    - Module-specific logic
    - Domain model definitions
    - Cross-module data exchange (use schemas/)
"""

from src.shared.config import get_database_url, get_settings, load_yaml
from src.shared.exceptions import (
    CollectionError,
    ConfigurationError,
    ExecutionError,
    HypothesisError,
    MacroAgentError,
    NormalizationError,
    PipelineError,
    PlanCreationError,
    PlanValidationError,
    ReflectionError,
    RepositoryError,
    SignalGenerationError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
)
from src.shared.logging import (
    configure_logging,
    get_logger,
    pipeline_step,
    pipeline_step_sync,
    with_retry,
)
from src.shared.reliability import (
    ExecutionMetrics,
    TaskTimeoutError,
    execute_with_timeout,
    with_async_retry,
)

__all__ = [
    # Config
    "load_yaml",
    "get_database_url",
    "get_settings",
    # Exceptions
    "MacroAgentError",
    "ConfigurationError",
    "CollectionError",
    "NormalizationError",
    "RepositoryError",
    "PipelineError",
    "SignalGenerationError",
    "PlanCreationError",
    "PlanValidationError",
    "ExecutionError",
    "ToolError",
    "ToolNotFoundError",
    "ToolExecutionError",
    "HypothesisError",
    "ReflectionError",
    # Logging
    "get_logger",
    "configure_logging",
    "pipeline_step",
    "pipeline_step_sync",
    "with_retry",
    # Reliability (RC-1)
    "execute_with_timeout",
    "TaskTimeoutError",
    "with_async_retry",
    "ExecutionMetrics",
]
