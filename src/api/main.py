"""FastAPI application — Macro Research Agent API.

Sprint 1: Pipeline Health API (GET /health)
Sprint 2: Signal API (GET /signals/snapshot)

Start with:
    uvicorn src.api.main:app --reload
"""

import time
from datetime import datetime, timezone

from fastapi import FastAPI

from src.api.analyze_routes import router as analyze_router
from src.api.signal_routes import router as signal_router
from src.shared.logging import configure_logging
from src.storage.engine import check_db_health

# ── Application ────────────────────────────────────────────────────────

app = FastAPI(
    title="Macro Research Agent",
    description="Enterprise-grade AI Macro Research Agent API — v2.0 with Continuous Learning",
    version="2.0.0",
)

# Register Sprint 2 routes
app.include_router(signal_router)

# Register MVP analyze routes
app.include_router(analyze_router)

# Register v2.0 routes (continuous learning)
from src.api.v2_routes import router as v2_router

app.include_router(v2_router)


@app.on_event("startup")
async def startup() -> None:
    """Initialize logging on application startup."""
    configure_logging(level="INFO")


# ── Pipeline Health ────────────────────────────────────────────────────


@app.get("/health")
async def health_check() -> dict:
    """Pipeline Health endpoint — component-level status.

    Returns:
        {
            "status": "healthy" | "degraded" | "unhealthy",
            "components": {
                "api": {"status": "healthy"},
                "collector": {"status": "healthy", "source": "Yahoo", "latency_ms": 245},
                "database": {"status": "healthy", "latency_ms": 12},
                "last_ingested": "2026-07-13T10:30:00Z"
            }
        }
    """
    components: dict = {
        "api": {"status": "healthy"},
    }

    # Check database
    db_start = time.perf_counter()
    db_ok = await check_db_health()
    db_latency = (time.perf_counter() - db_start) * 1000
    components["database"] = {
        "status": "healthy" if db_ok else "unhealthy",
        "latency_ms": round(db_latency, 2),
    }

    # Collector health — best-effort (depends on external API)
    collector_status = "unknown"
    collector_latency = None
    try:
        collector_start = time.perf_counter()
        from src.collector.yahoo import YahooCollector

        collector = YahooCollector()
        collector_ok = await collector.health_check()
        collector_latency = (time.perf_counter() - collector_start) * 1000
        collector_status = "healthy" if collector_ok else "unhealthy"
    except Exception:
        collector_status = "unhealthy"

    components["collector"] = {
        "status": collector_status,
        "source": "Yahoo",
    }
    if collector_latency is not None:
        components["collector"]["latency_ms"] = round(collector_latency, 2)

    # Last ingested — best-effort
    last_value: str = "unavailable"
    try:
        from src.storage.repository import SqlMacroRepository

        repo = SqlMacroRepository()
        latest = await repo.get_latest("DXY")
        if latest:
            last_value = latest.timestamp.isoformat()
        else:
            last_value = "never"
    except Exception:
        last_value = "unavailable"
    components["last_ingested"] = {"value": last_value}

    # Overall status — only check dict-type components with "status" key
    statuses = [
        c["status"]
        for c in components.values()
        if isinstance(c, dict) and "status" in c
    ]
    if "unhealthy" in statuses:
        overall = "degraded" if "healthy" in statuses else "unhealthy"
    else:
        overall = "healthy"

    return {"status": overall, "components": components, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/")
async def root() -> dict:
    """Root — API information."""
    return {
        "message": "Macro Research Agent API",
        "version": "0.1.0",
        "docs": "/docs",
    }
