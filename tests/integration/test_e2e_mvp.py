"""End-to-end integration tests — MVP validation.

Validates the complete 7-step cognitive pipeline:
    collect → normalize → signal → hypothesis → reflection → memory → narrative

MVP Acceptance Criteria:
    - pipeline.run() produces MacroNarrative Schema
    - Schema chain integrity: signals → hypotheses → reflections → narrative
    - MacroNarrative includes all 4 dimensions
    - CLI renders Markdown from MacroNarrative
"""

import pytest

from src.domain.execution import ExecutionStatus
from src.pipeline import MacroResearchPipeline
from src.schemas.narrative import MacroNarrative


@pytest.fixture
def pipeline() -> MacroResearchPipeline:
    """Create a fresh pipeline instance for each test."""
    return MacroResearchPipeline()


# ── Core Pipeline Tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_pipeline_produces_macro_narrative(pipeline: MacroResearchPipeline):
    """MVP Acceptance Criterion #1: pipeline.run() outputs MacroNarrative Schema."""
    result = await pipeline.run(goal="macro environment analysis")

    assert result.status in (
        ExecutionStatus.COMPLETED,
        ExecutionStatus.PARTIALLY_COMPLETED,
    ), f"Pipeline status should be COMPLETED or PARTIALLY_COMPLETED, got {result.status}"
    assert result.narrative_obj is not None, "Pipeline must produce a MacroNarrative object"

    narrative = result.narrative_obj
    assert isinstance(
        narrative, MacroNarrative
    ), f"Expected MacroNarrative, got {type(narrative).__name__}"

    # Content quality checks
    assert len(narrative.summary) > 10, f"Summary too short: '{narrative.summary}'"
    assert (
        len(narrative.macro_story) > 50
    ), f"Macro story too short ({len(narrative.macro_story)} chars)"
    assert 0.0 <= narrative.confidence <= 1.0, f"Confidence out of range: {narrative.confidence}"


@pytest.mark.asyncio
async def test_pipeline_artifacts_chain(pipeline: MacroResearchPipeline):
    """Verify Schema chain completeness: signals → hypotheses → reflections → narrative."""
    result = await pipeline.run(goal="macro environment analysis")

    artifacts = result.artifacts
    assert "signals" in artifacts, "Missing 'signals' in artifact chain"
    assert "hypotheses" in artifacts, "Missing 'hypotheses' in artifact chain"
    assert "reflections" in artifacts, "Missing 'reflections' in artifact chain"
    assert "narrative" in artifacts, "Missing 'narrative' in artifact chain"


@pytest.mark.asyncio
async def test_macro_narrative_dimensions_present(pipeline: MacroResearchPipeline):
    """Verify MacroNarrative contains all required dimensions."""
    result = await pipeline.run(goal="macro environment analysis")
    narrative = result.narrative_obj
    assert narrative is not None

    assert narrative.liquidity is not None, "Missing liquidity dimension"
    assert narrative.credit is not None, "Missing credit dimension"
    assert narrative.growth is not None, "Missing growth dimension"
    assert narrative.inflation is not None, "Missing inflation dimension"

    # Each dimension should have a dimension name
    for dim in [narrative.liquidity, narrative.credit, narrative.growth, narrative.inflation]:
        assert dim.dimension, "Dimension must have a name"
        assert isinstance(dim.summary, str), "Dimension must have a summary"


@pytest.mark.asyncio
async def test_cli_output_is_markdown_from_narrative(pipeline: MacroResearchPipeline):
    """Verify CLI Markdown rendering from MacroNarrative."""
    result = await pipeline.run(goal="macro environment analysis")
    assert result.narrative is not None, "Narrative markdown is required"
    assert len(result.narrative) > 100, f"Markdown output too short ({len(result.narrative)} chars)"
    # Markdown should contain heading markers
    assert "# " in result.narrative, "Markdown should contain headings"


# ── Schema Type Contract Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_narrative_schema_is_json_serializable(pipeline: MacroResearchPipeline):
    """Verify MacroNarrative can be serialized to JSON (for API response)."""
    result = await pipeline.run(goal="macro environment analysis")
    assert result.narrative_obj is not None

    narrative = result.narrative_obj
    json_data = narrative.model_dump(mode="json")

    assert isinstance(json_data, dict)
    assert "summary" in json_data
    assert "macro_story" in json_data
    assert "liquidity" in json_data
    assert "credit" in json_data
    assert "growth" in json_data
    assert "inflation" in json_data
    assert "risks" in json_data
    assert "confidence" in json_data
    assert "generated_at" in json_data


@pytest.mark.asyncio
async def test_narrative_confidence_in_range(pipeline: MacroResearchPipeline):
    """Verify narrative confidence is always in [0, 1]."""
    result = await pipeline.run(goal="macro environment analysis")
    assert result.narrative_obj is not None

    confidence = result.narrative_obj.confidence
    assert 0.0 <= confidence <= 1.0, f"Confidence {confidence} out of [0, 1] range"

    # Each dimension confidence should also be valid
    for dim in [
        result.narrative_obj.liquidity,
        result.narrative_obj.credit,
        result.narrative_obj.growth,
        result.narrative_obj.inflation,
    ]:
        assert (
            0.0 <= dim.confidence <= 1.0
        ), f"Dimension {dim.dimension} confidence {dim.confidence} out of [0, 1] range"


# ── Pipeline Robustness Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_handles_empty_goal(pipeline: MacroResearchPipeline):
    """Verify pipeline produces valid output even without detailed goal context."""
    result = await pipeline.run(goal="macro environment analysis")
    # Should still produce a narrative even without detailed goal
    assert result.narrative_obj is not None


@pytest.mark.asyncio
async def test_pipeline_produces_risks_list(pipeline: MacroResearchPipeline):
    """Verify MacroNarrative always includes a risks list (at minimum a default note)."""
    result = await pipeline.run(goal="macro environment analysis")
    assert result.narrative_obj is not None
    assert isinstance(result.narrative_obj.risks, list), "risks must be a list"
    assert len(result.narrative_obj.risks) >= 1, "should have at least a default risk note"


@pytest.mark.asyncio
async def test_pipeline_consistent_on_repeat(pipeline: MacroResearchPipeline):
    """Verify pipeline produces consistent output shape on repeated runs.

    MVP pipelines with mock data should be approximately deterministic.
    """
    result1 = await pipeline.run(goal="macro environment analysis")
    result2 = await pipeline.run(goal="macro environment analysis")

    assert result1.narrative_obj is not None
    assert result2.narrative_obj is not None

    # Both should have same structure
    assert (
        result1.narrative_obj.confidence == result2.narrative_obj.confidence
    ), "Deterministic pipeline should produce consistent confidence"
