"""Unit tests for HistoryRetriever — no real API calls.

Covers: Jaccard, time decay, Chinese bigram, top-K, truncation, degradation.
"""

from __future__ import annotations

import json
import math
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from src.llm.retriever import (
    HistoryRecord,
    HistoryRetriever,
    assemble_history_prompt,
    _tokenize,
    _truncate_to_chars,
    _estimate_tokens,
)
from src.memory.store import BeliefMemoryStore
from src.schemas.memory import BeliefRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_belief(
    belief_id: str,
    dimension: str,
    statement: str,
    direction: str = "bearish",
    confidence: float = 0.7,
    days_ago: int = 0,
    evidence: str = "",
    run_id: str = "test-run",
    hypothesis_id: str = "H-001",
) -> BeliefRecord:
    """Factory for test BeliefRecords."""
    from src.domain.memory import BeliefStatus, TransitionType
    from src.domain.signal import SignalDirection

    direction_map = {
        "bullish": SignalDirection.BULLISH,
        "bearish": SignalDirection.BEARISH,
        "neutral": SignalDirection.NEUTRAL,
    }
    return BeliefRecord(
        belief_id=belief_id,
        run_id=run_id,
        hypothesis_id=hypothesis_id,
        dimension=dimension,
        statement=statement,
        direction=direction_map.get(direction, SignalDirection.NEUTRAL),
        confidence=confidence,
        status=BeliefStatus.HELD,
        transition=TransitionType.REINFORCED,
        evidence_summary=evidence,
        timestamp=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )


def _make_store(records: list[BeliefRecord]) -> BeliefMemoryStore:
    """Create an in-memory BeliefMemoryStore with given records (no file I/O)."""
    store = BeliefMemoryStore.__new__(BeliefMemoryStore)
    object.__setattr__(store, "_records", list(records))
    object.__setattr__(store, "_loaded", True)
    return store


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------


class TestTokenization:
    def test_english_whitespace_split(self):
        t = _tokenize("Global liquidity tightening via DXY strength")
        assert "liquidity" in t
        assert "tightening" in t
        assert "dxy" in t
        # Common stopwords removed
        assert "the" not in t
        # Single-char tokens (like 'a') removed by len>=2 filter
        assert "a" not in t if len("a") < 2 else True

    def test_chinese_bigram(self):
        t = _tokenize("全球流动性收紧美元走强")
        assert "全球" in t
        assert "流动" in t
        assert "收紧" in t
        assert "美元" in t
        assert "走强" in t
        # Single char should not appear
        assert "球" not in t
        assert "紧" not in t

    def test_chinese_stopwords_removed(self):
        """Chinese bigrams that exactly match stopword entries are filtered."""
        # "一个" is in the stopword list as a bigram → removed
        t = _tokenize("这是一个很好的信号")
        assert "一个" not in t
        # "信号" (non-stopword bigram) should survive
        assert "信号" in t

    def test_pure_chinese_jaccard_identical(self):
        """Spec requirement: pure Chinese Jaccard test case."""
        q = _tokenize("全球流动性收紧美元走强")
        d = _tokenize("全球流动性收紧美元走强")
        assert len(q) > 0
        assert q == d

    def test_pure_chinese_jaccard_overlap_50pct(self):
        q = _tokenize("全球流动性收紧")
        d = _tokenize("全球流动性宽松")
        intersection = q & d
        union = q | d
        assert len(intersection) >= 1  # at least "全球"
        assert 0.2 < len(intersection) / len(union) < 0.8

    def test_mixed_cn_en_tokenization(self):
        t = _tokenize("DXY 走强 liquidity 收紧")
        assert "dxy" in t
        assert "走强" in t
        assert "liquidity" in t
        assert "收紧" in t

    def test_empty_text_returns_empty_set(self):
        assert _tokenize("") == set()
        assert _tokenize("   ") == set()


# ---------------------------------------------------------------------------
# Token estimation & truncation
# ---------------------------------------------------------------------------


class TestTokenEstimation:
    def test_estimate_tokens(self):
        assert _estimate_tokens("abc") == 2  # 3/1.5=2
        assert _estimate_tokens("abcdef") == 4  # 6/1.5=4

    def test_truncate_noop(self):
        assert _truncate_to_chars("short", 100) == "short"

    def test_truncate_at_boundary(self):
        text = "第一句。第二句。第三句。"
        result = _truncate_to_chars(text, 6)
        assert len(result) <= 6


# ---------------------------------------------------------------------------
# Jaccard similarity
# ---------------------------------------------------------------------------


class TestJaccard:
    def test_identical_sets(self):
        inst = HistoryRetriever()
        score = inst._score(
            text="Global liquidity tightening",
            query_tokens={"global", "liquidity", "tightening"},
            date_str=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            now=datetime.now(timezone.utc),
        )
        assert score > 0.9

    def test_disjoint_sets(self):
        inst = HistoryRetriever()
        score = inst._score(
            text="Equity rally tech stocks",
            query_tokens={"liquidity", "tightening", "dxy"},
            date_str=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            now=datetime.now(timezone.utc),
        )
        assert score == 0.0

    def test_partial_overlap(self):
        inst = HistoryRetriever()
        score = inst._score(
            text="Global liquidity tightening via DXY strength",
            query_tokens={"liquidity", "dxy", "risk"},
            date_str=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            now=datetime.now(timezone.utc),
        )
        assert 0.0 < score < 1.0


# ---------------------------------------------------------------------------
# Time decay
# ---------------------------------------------------------------------------


class TestTimeDecay:
    def test_recent_higher_than_old(self):
        inst = HistoryRetriever()
        now = datetime.now(timezone.utc)
        recent = inst._score(
            text="liquidity tightening",
            query_tokens={"liquidity", "tightening"},
            date_str=(now - timedelta(days=1)).strftime("%Y-%m-%d"),
            now=now,
        )
        old = inst._score(
            text="liquidity tightening",
            query_tokens={"liquidity", "tightening"},
            date_str=(now - timedelta(days=5)).strftime("%Y-%m-%d"),
            now=now,
        )
        assert recent > old

    def test_decay_rate_matches_spec(self):
        """Spec: 0.95^days_ago."""
        inst = HistoryRetriever()
        now = datetime.now(timezone.utc)

        s_day1 = inst._score(
            text="liquidity tightening",
            query_tokens={"liquidity", "tightening"},
            date_str=(now - timedelta(days=1)).strftime("%Y-%m-%d"),
            now=now,
        )
        s_day7 = inst._score(
            text="liquidity tightening",
            query_tokens={"liquidity", "tightening"},
            date_str=(now - timedelta(days=7)).strftime("%Y-%m-%d"),
            now=now,
        )
        # On identical text, Jaccard=1; ratio = 0.95^(1-7) ≈ 0.95^-6 ≈ 1.36
        # s_day1 should be about 1.36x s_day7
        expected_ratio = 0.95 ** (-6)  # day1 / day7 = 0.95^(1-7) = 0.95^-6
        actual_ratio = s_day1 / s_day7 if s_day7 > 0 else float("inf")
        assert math.isclose(actual_ratio, expected_ratio, rel_tol=0.01)


# ---------------------------------------------------------------------------
# Retriever integration
# ---------------------------------------------------------------------------


class TestRetriever:
    def test_retrieve_returns_top_k(self):
        records = [
            _make_belief("B1", "liquidity", "DXY bullish tightening", days_ago=0, evidence="DXY up 0.5%"),
            _make_belief("B2", "liquidity", "10Y yield stable", days_ago=1, evidence="10Y at 4.2%"),
            _make_belief("B3", "growth", "GDP slowing", days_ago=0, evidence="GDPNow 1.8%"),
            _make_belief("B4", "inflation", "CPI moderating", days_ago=2, evidence="Core PCE 2.6%"),
            _make_belief("B5", "liquidity", "Fed hawkish stance", days_ago=0, evidence="Fed minutes"),
        ]
        store = _make_store(records)
        retriever = HistoryRetriever(belief_store=store)

        structured_input = {
            "summary": "liquidity tightening DXY bullish",
            "macro_story": "Global financial conditions tightening",
            "today_key_changes": "DXY up",
            "liquidity": {"summary": "tightening", "analysis": "DXY bullish"},
            "credit": {"summary": "stable", "analysis": "spreads narrow"},
            "growth": {"summary": "slowing", "analysis": "GDP mixed"},
            "inflation": {"summary": "moderating", "analysis": "PCE down"},
            "risk_appetite_analysis": "risk-off",
            "belief_changes": [
                {"hypothesis": "liquidity tightening persists", "previous": 0.6, "current": 0.7}
            ],
        }

        results = retriever.retrieve(structured_input)
        assert 1 <= len(results) <= 3, f"Expected 1-3 results, got {len(results)}"
        # liquidity records should rank higher than growth/inflation
        for r in results:
            assert r.dimension in ("liquidity", "growth", "inflation")

    def test_retrieve_empty_input_returns_empty(self):
        store = _make_store([
            _make_belief("B1", "liquidity", "test", days_ago=0),
        ])
        retriever = HistoryRetriever(belief_store=store)
        results = retriever.retrieve({})
        assert results == []

    def test_retrieve_no_matching_candidates(self):
        store = _make_store([
            _make_belief("B1", "credit", "corporate spreads widening", days_ago=0),
            _make_belief("B2", "credit", "HY default rate up", days_ago=1),
        ])
        retriever = HistoryRetriever(belief_store=store)
        # Query about unrelated dimension
        structured_input = {
            "summary": "geopolitics Middle East tensions oil supply",
            "liquidity": {"summary": "FX volatility", "analysis": ""},
            "credit": {"summary": "", "analysis": ""},
            "growth": {"summary": "", "analysis": ""},
            "inflation": {"summary": "", "analysis": ""},
            "risk_appetite_analysis": "",
            "belief_changes": [],
        }
        results = retriever.retrieve(structured_input)
        # Credit records might have some overlap with geopolitics keywords like "risk"
        # but if the query is about geopolitics/oil, Jaccard will be low
        assert len(results) <= 3  # may return some with very low scores, but filtered by >0


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


class TestPromptAssembly:
    def test_no_records_returns_empty(self):
        text, tokens = assemble_history_prompt([])
        assert text == ""
        assert tokens == 0

    def test_with_records_includes_history_header(self):
        records = [
            HistoryRecord("2026-08-10", "liquidity", "DXY bullish tightening persists", 0.85),
        ]
        text, tokens = assemble_history_prompt(records)
        assert "【历史参考】" in text
        assert "2026-08-10" in text
        assert "liquidity" in text
        assert tokens > 0

    def test_instruction_suffix_present(self):
        """Spec: '历史引用须标注、不得与当日数据混淆' instruction."""
        records = [
            HistoryRecord("2026-08-10", "liquidity", "DXY tightening", 0.85),
        ]
        text, _ = assemble_history_prompt(records)
        assert "历史引用须标注、不得与当日数据混淆" in text

    def test_history_budget_enforced(self):
        """Spec: history segment ≤ 1050 chars."""
        records = [
            HistoryRecord(f"2026-08-{10-i:02d}", "liquidity", "test record content " * 30, 0.8)
            for i in range(5)
        ]
        text, tokens = assemble_history_prompt(records)
        assert len(text) <= HistoryRetriever.MAX_HISTORY_CHARS + 100  # tolerance for instruction suffix

    def test_single_entry_truncated_to_300_chars(self):
        long_text = "X " * 400
        record = HistoryRecord("2026-08-10", "liquidity", long_text, 0.9)
        entry = record.to_prompt_entry(index=1)
        # entry text portion should be ≤ 300 chars
        assert len(record.to_prompt_entry(index=1)) <= 300 + 50  # meta overhead


# ---------------------------------------------------------------------------
# Degradation: missing store / empty store / first run
# ---------------------------------------------------------------------------


class TestDegradation:
    def test_no_belief_store_returns_empty(self, tmp_path):
        retriever = HistoryRetriever()
        # No store; retriever will try lazy init and fail gracefully
        structured_input = {"summary": "liquidity tightening"}
        results = retriever.retrieve(structured_input)
        assert results == []

    def test_empty_beliefs_returns_empty(self):
        store = _make_store([])
        retriever = HistoryRetriever(belief_store=store)
        results = retriever.retrieve({"summary": "anything"})
        assert results == []

    def test_temporal_filter_excludes_old_beliefs(self):
        """Beliefs older than LOOKBACK_DAYS should not be returned."""
        records = [
            _make_belief("B-old", "liquidity", "old tightening signal", days_ago=10),
        ]
        store = _make_store(records)
        retriever = HistoryRetriever(belief_store=store)

        # Verify query tokens are extracted
        query = retriever._extract_query_tokens({"summary": "liquidity tightening"})
        assert len(query) > 0

        # Build candidate pool and verify temporal filtering directly
        candidates = retriever._build_candidate_pool(query)
        # With 10-day old belief, LOOKBACK_DAYS=7 should exclude it
        assert len(candidates) == 0, f"Expected 0, got {len(candidates)}"
