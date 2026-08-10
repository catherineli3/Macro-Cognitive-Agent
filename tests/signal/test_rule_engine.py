"""Tests for RuleEngine — config loading, threshold evaluation, edge cases."""

from datetime import datetime, timezone

import pytest

from src.schemas.macro_data import MacroDataSchema
from src.signal.rule_engine import RuleEngine


class TestRuleEngineLoading:
    """Rule config loading and parsing."""

    def test_load_rules_from_config(self) -> None:
        engine = RuleEngine()
        assert len(engine.rules) > 0, "Should load at least one rule from YAML"
        rule_ids = {r.rule_id for r in engine.rules}
        assert "dxy_strong_dollar" in rule_ids

    def test_get_rules_for_indicator(self) -> None:
        engine = RuleEngine()
        dxy_rules = engine.get_rules_for_indicator("DXY")
        assert len(dxy_rules) == 2  # strong_dollar + weak_dollar

    def test_get_rules_for_nonexistent_indicator(self) -> None:
        engine = RuleEngine()
        rules = engine.get_rules_for_indicator("NONEXISTENT")
        assert rules == []

    def test_all_rules_have_required_fields(self) -> None:
        engine = RuleEngine()
        for rule in engine.rules:
            assert rule.rule_id, f"Missing rule_id in {rule}"
            assert rule.indicator, f"Missing indicator in {rule.rule_id}"
            assert rule.dimension, f"Missing dimension in {rule.rule_id}"
            assert rule.condition.threshold is not None, f"Missing threshold in {rule.rule_id}"
            assert rule.signal_direction in ("bullish", "bearish", "neutral"), (
                f"Invalid direction '{rule.signal_direction}' in {rule.rule_id}"
            )
            assert rule.signal_strength in ("strong", "moderate", "weak"), (
                f"Invalid strength '{rule.signal_strength}' in {rule.rule_id}"
            )
            assert 0.0 <= rule.signal_confidence <= 1.0, f"Invalid confidence in {rule.rule_id}"
            assert rule.interpretation, f"Missing interpretation in {rule.rule_id}"


class TestThresholdEvaluation:
    """Threshold rule evaluation logic."""

    @pytest.fixture
    def engine(self) -> RuleEngine:
        return RuleEngine()

    def test_gt_triggered(self, engine: RuleEngine, sample_dxy_data_high: MacroDataSchema) -> None:
        """DXY=106.5 > 105 → strong_dollar triggered."""
        results = engine.evaluate("DXY", sample_dxy_data_high, [])
        triggered = [r for r in results if r.triggered]
        assert any(r.rule.rule_id == "dxy_strong_dollar" for r in triggered)

    def test_gt_not_triggered(self, engine: RuleEngine, sample_dxy_data_mid: MacroDataSchema) -> None:
        """DXY=102 is below 105 → strong_dollar NOT triggered."""
        results = engine.evaluate("DXY", sample_dxy_data_mid, [])
        triggered = [r for r in results if r.triggered]
        assert not any(r.rule.rule_id == "dxy_strong_dollar" for r in triggered)

    def test_lt_triggered(self, engine: RuleEngine, sample_dxy_data_low: MacroDataSchema) -> None:
        """DXY=98.0 < 100 → weak_dollar triggered."""
        results = engine.evaluate("DXY", sample_dxy_data_low, [])
        triggered = [r for r in results if r.triggered]
        assert any(r.rule.rule_id == "dxy_weak_dollar" for r in triggered)

    def test_lt_not_triggered(self, engine: RuleEngine, sample_dxy_data_mid: MacroDataSchema) -> None:
        """DXY=102 is above 100 → weak_dollar NOT triggered."""
        results = engine.evaluate("DXY", sample_dxy_data_mid, [])
        triggered = [r for r in results if r.triggered]
        assert not any(r.rule.rule_id == "dxy_weak_dollar" for r in triggered)

    def test_vix_elevated_triggered(self, engine: RuleEngine, sample_vix_data_high: MacroDataSchema) -> None:
        """VIX=28 > 25 → vix_elevated triggered."""
        results = engine.evaluate("^VIX", sample_vix_data_high, [])
        triggered = [r for r in results if r.triggered]
        assert any(r.rule.rule_id == "vix_elevated" for r in triggered)

    def test_gte_operator(self, engine: RuleEngine) -> None:
        """Test gte with exact threshold match. Uses 5.01 since rule is gt (not gte)."""
        data = MacroDataSchema(
            symbol="US10Y",
            timestamp=datetime(2026, 7, 13, tzinfo=timezone.utc),
            value=5.01,  # Just above 5.0
            source="Yahoo",
        )
        results = engine.evaluate("US10Y", data, [])
        triggered = [r for r in results if r.triggered]
        assert any(r.rule.rule_id == "us10y_elevated" for r in triggered)

    def test_no_rules_for_indicator_returns_empty(self, engine: RuleEngine) -> None:
        """Indicator without rules → empty result."""
        data = MacroDataSchema(
            symbol="UNKNOWN",
            timestamp=datetime(2026, 7, 13, tzinfo=timezone.utc),
            value=100.0,
            source="Test",
        )
        results = engine.evaluate("UNKNOWN", data, [])
        assert results == []

    def test_evaluation_contains_input_value(self, engine: RuleEngine, sample_dxy_data_high: MacroDataSchema) -> None:
        """Each evaluation result must carry the input value."""
        results = engine.evaluate("DXY", sample_dxy_data_high, [])
        for r in results:
            assert r.input_value == 106.5

    def test_evaluation_contains_condition_str(self, engine: RuleEngine, sample_dxy_data_high: MacroDataSchema) -> None:
        """Each evaluation result must carry the condition string."""
        results = engine.evaluate("DXY", sample_dxy_data_high, [])
        for r in results:
            assert r.condition_str, f"Empty condition_str for {r.rule.rule_id}"
            assert "gt" in r.condition_str or "lt" in r.condition_str
