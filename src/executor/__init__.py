"""Executor module — Agent Executor + ExecutionContext.

Sprint 4 implements the execution chain:
    ExecutionPlan → AgentExecutor → TaskHandler → ExecutionResult

Key principles:
    - AgentExecutor contains zero business logic
    - Scheduler/Dispatcher/Registry are PRIVATE methods, not independent modules
    - ExecutionContext is the single shared runtime state
    - Artifacts are the primary data carrier (consumed by Memory/Reflection/Report)
"""

from src.executor.context import ExecutionContext
from src.executor.executor import AgentExecutor

__all__ = [
    "AgentExecutor",
    "ExecutionContext",
]
