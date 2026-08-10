from __future__ import annotations

"""Analyze API routes — Beta endpoints for macro research execution.

POST /api/analyze      — Execute a full macro research pipeline run.
GET  /api/report/{id}  — Retrieve a persisted MacroNarrative by ID.
GET  /api/reports/latest — Get the most recent analysis report.
GET  /api/beliefs       — Get current belief state from memory.
"""

from fastapi import APIRouter, HTTPException

from src.pipeline import MacroResearchPipeline
from src.schemas.narrative import MacroNarrative
from src.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["analyze"])


# ── Request/Response Schemas ───────────────────────────────────────────────

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request body for POST /api/analyze."""

    goal: str = Field(
        default="macro environment analysis",
        min_length=1,
        max_length=512,
        description="Research goal (e.g., 'liquidity analysis', 'risk assessment')",
    )
    indicators: list[str] | None = Field(
        default=None,
        description="Optional list of specific indicators to focus on",
    )


class AnalyzeResponse(BaseModel):
    """Response body for POST /api/analyze."""

    status: str = Field(..., description="Execution status: completed | partially_completed | failed")
    message: str = Field(default="", description="Human-readable status message")
    report_id: str = Field(default="", description="Unique report identifier")
    narrative: dict | None = Field(default=None, description="MacroNarrative serialized as dict")
    narrative_markdown: str | None = Field(default=None, description="Markdown rendered report (Beta)")
    confidence_score: float | None = Field(default=None, description="Numeric confidence (0-1)")
    confidence_level: str | None = Field(default=None, description="HIGH | MEDIUM | LOW")
    risk_count: int = Field(default=0, description="Number of risks identified")
    scenario_count: int = Field(default=0, description="Number of scenarios generated")
    artifacts_summary: dict = Field(default_factory=dict, description="Summary of intermediate artifacts")


class BeliefItem(BaseModel):
    """A single belief entry for GET /beliefs."""

    dimension: str
    statement: str
    direction: str
    confidence: float
    status: str
    transition: str
    timestamp: str


class BeliefsResponse(BaseModel):
    """Response body for GET /api/beliefs."""

    beliefs: list[BeliefItem] = Field(default_factory=list)
    count: int = 0
    last_updated: str | None = None


# ── In-memory report cache (Beta: replaces placeholder with actual storage) ──

_report_cache: dict[str, MacroNarrative] = {}
_latest_report_id: str | None = None

import uuid


def _cache_report(narrative: MacroNarrative) -> str:
    """Cache a generated narrative and return its report ID."""
    global _latest_report_id
    report_id = uuid.uuid4().hex[:12]
    _report_cache[report_id] = narrative
    _latest_report_id = report_id
    return report_id


# ── POST /analyze ──────────────────────────────────────────────────────────


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Execute a full macro research pipeline run.

    This is the primary endpoint. It runs the complete 7-step
    cognitive pipeline (collect → normalize → signal → hypothesis →
    reflection → memory → narrative) and returns a structured
    MacroNarrative.

    Beta: Also caches reports for retrieval via /reports/latest.
    """
    logger.info(
        "api_analyze_request",
        extra={"goal": request.goal, "indicators": request.indicators},
    )

    pipeline = MacroResearchPipeline()
    result = await pipeline.run(
        goal=request.goal,
        indicators=request.indicators,
    )

    if result.narrative_obj is None:
        error_msg = result.error or "Pipeline produced no narrative."
        logger.error("api_analyze_failed", extra={"error": error_msg})
        return AnalyzeResponse(
            status=result.status.value,
            message=error_msg,
            narrative=None,
            narrative_markdown=None,
            confidence_score=None,
            confidence_level=None,
            risk_count=0,
            scenario_count=0,
            artifacts_summary=_summarize_artifacts(result.artifacts),
        )

    narrative_obj: MacroNarrative = result.narrative_obj

    # Cache for later retrieval
    report_id = _cache_report(narrative_obj)

    logger.info(
        "api_analyze_completed",
        extra={
            "report_id": report_id,
            "status": result.status.value,
            "confidence": narrative_obj.confidence_score,
            "confidence_level": narrative_obj.confidence_level.value,
            "risk_count": len(narrative_obj.risks),
            "scenario_count": len(narrative_obj.scenario_analysis),
        },
    )

    return AnalyzeResponse(
        status=result.status.value,
        message=f"Analysis completed with {narrative_obj.confidence_score:.0%} confidence ({narrative_obj.confidence_level.value}).",
        report_id=report_id,
        narrative=narrative_obj.model_dump(mode="json"),
        narrative_markdown=result.narrative,
        confidence_score=narrative_obj.confidence_score,
        confidence_level=narrative_obj.confidence_level.value,
        risk_count=len(narrative_obj.risks),
        scenario_count=len(narrative_obj.scenario_analysis),
        artifacts_summary=_summarize_artifacts(result.artifacts),
    )


# ── GET /report/{report_id} ────────────────────────────────────────────────


@router.get("/report/{report_id}")
async def get_report(report_id: str) -> dict:
    """Retrieve a previously generated MacroNarrative by report ID.

    Beta: Reads from in-memory report cache.
    """
    logger.info("api_get_report_request", extra={"report_id": report_id})

    narrative = _report_cache.get(report_id)
    if narrative is None:
        raise HTTPException(
            status_code=404,
            detail=f"Report '{report_id}' not found. Generate one via POST /api/analyze.",
        )

    from src.renderer.markdown import MarkdownRenderer

    markdown = MarkdownRenderer().render(narrative)

    return {
        "report_id": report_id,
        "confidence_score": narrative.confidence_score,
        "confidence_level": narrative.confidence_level.value,
        "generated_at": narrative.generated_at.isoformat(),
        "narrative": narrative.model_dump(mode="json"),
        "markdown": markdown,
    }


# ── GET /reports/latest ────────────────────────────────────────────────────


@router.get("/reports/latest")
async def get_latest_report() -> dict:
    """Get the most recently generated analysis report.

    Beta: Returns cached latest report if available.
    """
    global _latest_report_id

    if _latest_report_id is None or _latest_report_id not in _report_cache:
        raise HTTPException(
            status_code=404,
            detail="No reports have been generated yet. Run POST /api/analyze first.",
        )

    narrative = _report_cache[_latest_report_id]
    from src.renderer.markdown import MarkdownRenderer

    markdown = MarkdownRenderer().render(narrative)

    return {
        "report_id": _latest_report_id,
        "confidence_score": narrative.confidence_score,
        "confidence_level": narrative.confidence_level.value,
        "generated_at": narrative.generated_at.isoformat(),
        "summary": narrative.summary,
        "narrative": narrative.model_dump(mode="json"),
        "markdown": markdown,
        "scenario_count": len(narrative.scenario_analysis),
        "risk_count": len(narrative.risks),
        "action_items": narrative.action_items,
    }


# ── GET /beliefs ───────────────────────────────────────────────────────────


@router.get("/beliefs", response_model=BeliefsResponse)
async def get_beliefs() -> BeliefsResponse:
    """Get current belief state from memory store.

    Returns all stored beliefs with their transitions.
    """
    try:
        from src.memory.store import BeliefMemoryStore

        store = BeliefMemoryStore()
        all_beliefs = store.all_beliefs()

        if not all_beliefs:
            return BeliefsResponse(
                beliefs=[],
                count=0,
                last_updated=None,
            )

        items = [
            BeliefItem(
                dimension=b.dimension,
                statement=b.statement[:200],
                direction=b.direction.value,
                confidence=b.confidence,
                status=b.status.value,
                transition=b.transition.value,
                timestamp=b.timestamp.isoformat(),
            )
            for b in all_beliefs[:50]  # Limit to 50 most recent
        ]

        last_updated = max(b.timestamp for b in all_beliefs).isoformat()

        return BeliefsResponse(
            beliefs=items,
            count=len(items),
            last_updated=last_updated,
        )

    except Exception as e:
        logger.error("api_beliefs_failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to retrieve beliefs: {str(e)}")


# ── Helpers ────────────────────────────────────────────────────────────────


def _summarize_artifacts(artifacts: dict) -> dict:
    """Build a summary of intermediate artifacts for observability."""
    summary: dict = {}
    for key, value in artifacts.items():
        if value is None:
            summary[key] = "none"
        elif hasattr(value, "count"):
            summary[key] = f"{value.count} items"
        elif isinstance(value, list):
            summary[key] = f"{len(value)} items"
        elif isinstance(value, dict):
            summary[key] = f"{len(value)} keys"
        else:
            summary[key] = type(value).__name__
    return summary
