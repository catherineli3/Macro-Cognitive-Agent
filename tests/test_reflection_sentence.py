"""Tests for dynamic reflection sentence and smart truncation (issue fixes)."""

from types import SimpleNamespace

from src.narrative.engine import _reflection_sentence, _smart_truncate


def _refs(confirmed=0, refuted=0, uncertain=0):
    return SimpleNamespace(
        confirmed=[object()] * confirmed,
        refuted=[object()] * refuted,
        uncertain=[object()] * uncertain,
        count=confirmed + refuted + uncertain,
    )


class TestReflectionSentence:
    def test_refuted_majority_says_challenges(self):
        s = _reflection_sentence(_refs(confirmed=0, refuted=2, uncertain=1))
        assert "challenges" in s
        assert "0 confirmed" in s and "2 refuted" in s
        # Regression: must never claim confirmation when none happened
        assert "confirms the majority" not in s

    def test_confirmed_majority_says_supports(self):
        s = _reflection_sentence(_refs(confirmed=3, refuted=1))
        assert "supports" in s and "3 confirmed" in s

    def test_no_reviews(self):
        s = _reflection_sentence(_refs())
        assert "No belief-review data" in s

    def test_split(self):
        s = _reflection_sentence(_refs(confirmed=1, refuted=1))
        assert "split" in s


class TestSmartTruncate:
    def test_short_text_unchanged(self):
        assert _smart_truncate("short text", 100) == "short text"

    def test_cuts_at_sentence_boundary(self):
        text = "First sentence here. " * 10
        out = _smart_truncate(text, 120)
        assert out.endswith(".")
        assert len(out) <= 120

    def test_no_midword_cut(self):
        text = "word " * 60  # no sentence boundary
        out = _smart_truncate(text, 100)
        assert not out.rstrip("…").endswith("wor")  # no partial word
        assert out.endswith("…")
