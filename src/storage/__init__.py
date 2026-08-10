"""Storage module — Database, cache, and vector store management.

Responsibilities:
    - Database persistence (SQLAlchemy ORM + async engine)
    - Cache layer (future: Redis integration)
    - Vector store (future: Chroma / Qdrant)

Sprint 1:
    SqlMacroRepository — Repository pattern for macro observations

NOT managed by this module:
    - Agent memory → memory/
"""

from src.storage.engine import check_db_health, dispose_engine, get_engine, get_session_factory
from src.storage.models import Base, MacroObservation
from src.storage.repository import SqlMacroRepository

__all__ = [
    # Repository
    "SqlMacroRepository",
    # Models
    "Base",
    "MacroObservation",
    # Engine
    "get_engine",
    "get_session_factory",
    "check_db_health",
    "dispose_engine",
]
