"""(Unit) LLMNarrativeEngine: markdown code fence stripping + degradation paths."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.llm.client import LLMClient, LLMError
from src.llm.narrative import LLMNarrativeData, LLMNarrativeEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scenario(name: str, probability: float, rationale: str) -> MagicMock:
    """Create a mock scenario with explicit attributes; avoids MagicMock(name=...)
    collision where 'name' is reserved as _mock_name."""
    s = MagicMock()
    s.name = name
    s.probability = probability
    s.rationale = rationale
    return s


def _make_belief_change(
    hypothesis_statement: str,
    previous_confidence: float,
    current_confidence: float,
    direction: str,
) -> MagicMock:
    """Create a mock belief change with explicit non-reserved attributes."""
    b = MagicMock()
    b.hypothesis_statement = hypothesis_statement
    b.previous_confidence = previous_confidence
    b.current_confidence = current_confidence
    b.direction = direction
    return b


def _mock_narrative() -> MagicMock:
    """Return a MagicMock MacroNarrative with pure JSON-serializable fields.

    All leaf attributes resolve to str / float / list[str] so that
    _build_input() can safely json.dumps() the result without hitting
    "Object of type MagicMock is not JSON serializable".
    """
    n = MagicMock()
    n.summary = "macro overview"
    n.macro_story = "risk-on story"
    n.today_key_changes = "no major changes"
    n.liquidity.summary = "neutral"
    n.liquidity.analysis = "balanced"
    n.liquidity.confidence = 0.7
    n.credit.summary = "stable"
    n.credit.analysis = "credit spreads tight"
    n.credit.confidence = 0.65
    n.growth.summary = "moderate"
    n.growth.analysis = "GDP near trend"
    n.growth.confidence = 0.6
    n.inflation.summary = "sticky"
    n.inflation.analysis = "core CPI elevated"
    n.inflation.confidence = 0.55
    n.risk_appetite_analysis = "balanced risk"
    n.scenario_analysis = [
        _make_scenario("soft landing", 0.5, "data consistent"),
        _make_scenario("recession", 0.25, "yield curve"),
        _make_scenario("reflation", 0.25, "fiscal policy"),
    ]
    n.belief_changes = [
        _make_belief_change("inflation will ease", 0.3, 0.6, "strengthened"),
    ]
    n.key_risks = ["geopolitical risk", "policy error"]
    n.action_items = ["monitor CPI", "hedge tail risk"]
    n.confidence_level.value = "medium"
    n.confidence_score = 0.72
    return n


# ---------------------------------------------------------------------------
# Test: _parse_json strips markdown code fences
# ---------------------------------------------------------------------------


class TestJsonFenceStripping:
    """Model output wrapped in ```json ... ``` should parse correctly."""

    VALID_PAYLOAD = {
        "executive_summary": "sum",
        "scenario_analysis": "sca",
        "action_recommendations": ["a", "b"],
        "belief_revision": "blf",
    }

    @pytest.mark.parametrize(
        "raw_input",
        [
            # Plain JSON — no fence
            json.dumps(VALID_PAYLOAD),
            # ```json wrapper with leading/trailing whitespace
            "```json\n" + json.dumps(VALID_PAYLOAD, indent=2) + "\n```",
            # ``` (no language hint) wrapper
            "```\n" + json.dumps(VALID_PAYLOAD) + "\n```",
            # leading text + fence
            "Here is the report:\n```json\n" + json.dumps(VALID_PAYLOAD) + "\n```",
            # extra newlines around fence
            "```json\n\n" + json.dumps(VALID_PAYLOAD) + "\n\n```",
        ],
    )
    def test_fenced_json_parses(self, raw_input: str) -> None:
        """All fenced variants should parse to valid LLMNarrativeData."""
        result = LLMNarrativeEngine._validate(raw_input)
        assert isinstance(result, LLMNarrativeData)
        assert result.executive_summary == "sum"
        assert result.scenario_analysis == "sca"
        assert result.action_recommendations == ["a", "b"]
        assert result.belief_revision == "blf"

    def test_invalid_json_still_raises(self) -> None:
        """Non-JSON (even after stripping) should still raise."""
        with pytest.raises(json.JSONDecodeError):
            LLMNarrativeEngine._validate("not json at all")

    def test_empty_fence_not_json(self) -> None:
        """Empty fence with nothing parseable inside raises."""
        with pytest.raises(json.JSONDecodeError):
            LLMNarrativeEngine._validate("```json\n\n```")


# ---------------------------------------------------------------------------
# Test: degradation on LLM failure
# ---------------------------------------------------------------------------


class TestDegradationPaths:
    """Engine returns degraded=True + template fallback on any LLM failure."""

    def test_degraded_when_llm_unreachable(self) -> None:
        """LLM call fails -> degraded=True, template data used."""
        engine = LLMNarrativeEngine()
        engine._call_llm = MagicMock(side_effect=LLMError("unreachable"))

        result = engine.generate(_mock_narrative())

        assert result.degraded is True
        assert "unreachable" in (result.error or "")
        assert result.data.executive_summary == "macro overview"
        assert isinstance(result.data, LLMNarrativeData)

    def test_degraded_when_llm_returns_invalid_json(self) -> None:
        """LLM returns unparseable text -> degraded."""
        engine = LLMNarrativeEngine()
        engine._call_llm = MagicMock(return_value="not json at all")

        result = engine.generate(_mock_narrative())

        assert result.degraded is True

    def test_degraded_when_schema_validation_fails(self) -> None:
        """LLM returns valid JSON but missing required structure -> degraded."""
        engine = LLMNarrativeEngine()
        engine._call_llm = MagicMock(side_effect=LLMError("schema validation failed"))

        result = engine.generate(_mock_narrative())

        assert result.degraded is True

    def test_success_path(self) -> None:
        """Normal LLM response -> degraded=False, raw response captured."""
        engine = LLMNarrativeEngine()
        payload = json.dumps({
            "executive_summary": "sum",
            "scenario_analysis": "sca",
            "action_recommendations": ["x"],
            "belief_revision": "blf",
        })
        engine._call_llm = MagicMock(return_value=payload)

        result = engine.generate(_mock_narrative())

        assert result.degraded is False
        assert result.error is None
        assert result.raw_llm_response == payload
        assert result.data.executive_summary == "sum"
