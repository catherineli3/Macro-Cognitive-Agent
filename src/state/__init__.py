"""State module — MacroAgentState definition.

MacroAgentState is the single source of truth for LangGraph orchestration.
All LangGraph nodes:
- Read ONLY from MacroAgentState
- Write ONLY into MacroAgentState
- NEVER couple directly to other modules

This ensures clean separation between workflow orchestration
and business logic implementation.
"""
