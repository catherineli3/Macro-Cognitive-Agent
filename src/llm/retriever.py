"""HistoryRetriever — keyword-overlap retrieval for RAG without vector DB.

Design contract (Phase 3):
  - Zero new heavy dependencies — no Pinecone / Milvus / pgvector / Chroma.
  - Retrieval: Jaccard similarity × time decay, top-K candidates.
  - Tokenization: English split by whitespace; Chinese split by bigram.
  - Token budget: chars ÷ 1.5; single entry ≤ 300 chars; history ≤ 1050 chars.
  - Time decay: 0.95^days_ago.

Integration:
  - Called from LLMNarrativeEngine.generate() before LLM prompt assembly.
  - Silently degrades to empty history on any failure.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Optional

from src.memory.store import BeliefMemoryStore
from src.shared.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Tokenization — English whitespace + Chinese character bigram
# ---------------------------------------------------------------------------

# Minimal stopword list: common English function words + generic Chinese tokens
_STOPWORDS: frozenset[str] = frozenset(
    [
        # English
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "can", "shall",
        "and", "or", "but", "not", "no", "if", "then", "else",
        "at", "by", "for", "from", "in", "of", "on", "to", "with",
        "this", "that", "these", "those", "it", "its", "they", "their",
        "we", "us", "our", "you", "your", "he", "she", "him", "her",
        "about", "above", "after", "again", "all", "also", "as",
        "just", "more", "most", "only", "other", "over", "same",
        "some", "such", "than", "very", "well", "when", "which",
        "while", "who", "whom", "why", "how", "up", "down", "out",
        # Chinese
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
        "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
        "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
        "它", "们", "那", "些", "什么", "吗", "吧", "呢", "啊",
    ]
)

_CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


def _tokenize(text: str) -> set[str]:
    r"""Tokenize text into a set of tokens.

    English: split by whitespace, lowercase, strip punctuation.
    Chinese: character-level bigrams (overlapping 2-char windows).

    Both filtered through minimal stopword list.
    """
    tokens: set[str] = set()

    # --- English tokens: split on whitespace & punctuation ---
    # Collapse non-alpha-non-chinese chars to spaces for English splitting.
    cleaned = re.sub(r"[^\u4e00-\u9fffa-zA-Z0-9]+", " ", text.lower())
    for word in cleaned.split():
        word = word.strip()
        if word and word not in _STOPWORDS and len(word) >= 2:
            tokens.add(word)

    # --- Chinese bigrams ---
    chinese_chars = _CHINESE_CHAR_RE.findall(text)
    for i in range(len(chinese_chars) - 1):
        bigram = chinese_chars[i] + chinese_chars[i + 1]
        if bigram not in _STOPWORDS:
            tokens.add(bigram)

    return tokens


# ---------------------------------------------------------------------------
# Token estimation — chars ÷ 1.5 per spec
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    """Estimated token count using char ÷ 1.5 rule."""
    return max(1, int(len(text) / 1.5))


def _truncate_to_chars(text: str, max_chars: int) -> str:
    """Truncate text to at most max_chars, trying to break at sentence boundary."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    # Try to break at last sentence-ending char
    for sep in ("。", ". ", ".\n", ". ", "\n", " ", "；", "; "):
        last = truncated.rfind(sep)
        if last > max_chars // 2:
            return truncated[: last + len(sep.rstrip())]  # noqa: ASYNC911
    return truncated


# ---------------------------------------------------------------------------
# HistoryRecord — lightweight container for retrieved history
# ---------------------------------------------------------------------------

class HistoryRecord:
    """A single retrieved history item for prompt injection."""

    __slots__ = ("date", "dimension", "text", "score")

    def __init__(self, date: str, dimension: str, text: str, score: float) -> None:
        self.date = date
        self.dimension = dimension
        self.text = text
        self.score = score

    def to_prompt_entry(self, index: int, max_chars: int = 300) -> str:
        """Format for injection into user prompt, truncated to max_chars."""
        body = _truncate_to_chars(self.text, max_chars)
        return f"[{index}] {self.date} | {self.dimension} | {body}"

    def __repr__(self) -> str:
        return (
            f"<HistoryRecord {self.date} {self.dimension} "
            f"score={self.score:.3f}>"
        )


# ---------------------------------------------------------------------------
# HistoryRetriever
# ---------------------------------------------------------------------------

class HistoryRetriever:
    r"""Retrieve relevant historical beliefs/evidence using keyword Jaccard.

    Usage:
        retriever = HistoryRetriever()
        records = retriever.retrieve(structured_input)
        # records is List[HistoryRecord], never raises.
    """

    # --- Tunable constants ---
    TOP_K: int = 3
    TIME_DECAY_RATE: float = 0.95  # 0.95^days_ago
    MAX_ENTRY_CHARS: int = 300      # single entry ≤ 300 chars
    MAX_HISTORY_CHARS: int = 1050   # history segment ≤ 1050 chars
    LOOKBACK_DAYS: int = 7          # beliefs within last 7 days
    SIGNAL_LOOKBACK_DAYS: int = 30  # signals within last 30 days

    def __init__(self, belief_store: BeliefMemoryStore | None = None) -> None:
        self._belief_store = belief_store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve(self, structured_input: dict) -> list[HistoryRecord]:
        """Retrieve top-K relevant history records for the given input.

        Args:
            structured_input: Dict from LLMNarrativeEngine._build_input().

        Returns:
            Up to TOP_K HistoryRecords sorted by score desc.  Empty list
            on any failure or when no history exists (silent degradation).
        """
        try:
            query_tokens = self._extract_query_tokens(structured_input)
            if not query_tokens:
                return []

            candidates = self._build_candidate_pool(query_tokens)
            if not candidates:
                return []

            now = datetime.now(timezone.utc)
            scored = []
            for record in candidates:
                score = self._score(record.text, query_tokens, record.date, now)
                if score > 0:
                    scored.append((score, record))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [r for _, r in scored[: self.TOP_K]]
        except Exception:
            logger.warning("history_retrieve_failed", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Internal — query token extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_query_tokens(structured_input: dict) -> set[str]:
        """Build query token set from structured input fields."""
        query_parts: list[str] = []

        # Core summary fields
        for key in ("summary", "macro_story", "today_key_changes"):
            val = structured_input.get(key, "")
            if isinstance(val, str) and val:
                query_parts.append(val)

        # Dimension summaries
        for dim in ("liquidity", "credit", "growth", "inflation"):
            dim_data = structured_input.get(dim, {})
            if isinstance(dim_data, dict):
                for sub in ("summary", "analysis"):
                    val = dim_data.get(sub, "")
                    if isinstance(val, str) and val:
                        query_parts.append(val)

        # Risk appetite
        ra = structured_input.get("risk_appetite_analysis", "")
        if isinstance(ra, str) and ra:
            query_parts.append(ra)

        # Belief changes
        for bc in structured_input.get("belief_changes", []) or []:
            if isinstance(bc, dict):
                hypothesis = bc.get("hypothesis", "")
                if isinstance(hypothesis, str):
                    query_parts.append(hypothesis)

        combined = " ".join(query_parts)
        return _tokenize(combined)

    # ------------------------------------------------------------------
    # Internal — candidate pool construction
    # ------------------------------------------------------------------

    def _build_candidate_pool(self, query_tokens: set[str]) -> list[HistoryRecord]:
        """Assemble candidates from belief store and signal evidence.

        Currently reads from BeliefMemoryStore.  Future: can extend to
        NarrativeStore / signals.evidence_json via SQLite.
        """
        candidates: list[HistoryRecord] = []

        store = self._belief_store
        if store is None:
            try:
                store = BeliefMemoryStore()
            except Exception:
                logger.warning("history_belief_store_unavailable")
                return candidates
            self._belief_store = store

        try:
            now = datetime.now(timezone.utc)
            all_beliefs = store.all_beliefs()
        except Exception:
            logger.warning("history_belief_load_failed", exc_info=True)
            return candidates

        for belief in all_beliefs:
            days_ago = (now - belief.timestamp).days
            if days_ago > self.LOOKBACK_DAYS:
                continue

            # Build a text representation for similarity matching
            text = self._belief_to_text(belief)
            if not text:
                continue

            date_str = belief.timestamp.strftime("%Y-%m-%d")
            candidates.append(
                HistoryRecord(
                    date=date_str,
                    dimension=belief.dimension,
                    text=text,
                    score=0.0,  # will be scored later
                )
            )

        return candidates

    # ------------------------------------------------------------------
    # Internal — scoring
    # ------------------------------------------------------------------

    def _score(
        self,
        text: str,
        query_tokens: set[str],
        date_str: str,
        now: datetime,
    ) -> float:
        """Compute retrieval score: Jaccard × time decay."""
        text_tokens = _tokenize(text)
        if not text_tokens or not query_tokens:
            return 0.0

        jaccard = len(query_tokens & text_tokens) / len(query_tokens | text_tokens)

        # Time decay
        try:
            record_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_ago = max(0, (now - record_date).days)
        except (ValueError, TypeError):
            days_ago = 0

        time_weight = self.TIME_DECAY_RATE ** days_ago
        return jaccard * time_weight

    # ------------------------------------------------------------------
    # Internal — text formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _belief_to_text(belief) -> str:
        """Convert a BeliefRecord into a compact text snippet for retrieval.

        Includes statement, direction, confidence, transition, evidence_summary.
        """
        parts: list[str] = []

        direction = getattr(belief.direction, "value", str(belief.direction))
        transition = getattr(belief.transition, "value", str(belief.transition))

        parts.append(f"假说: {belief.statement}")
        parts.append(f"方向: {direction} | 置信度: {belief.confidence:.0%} | 状态: {transition}")

        if getattr(belief, "evidence_summary", ""):
            parts.append(f"证据: {belief.evidence_summary}")
        if getattr(belief, "review_summary", ""):
            parts.append(f"反思: {belief.review_summary}")

        return "；".join(parts)


# ---------------------------------------------------------------------------
# Prompt assembly utility
# ---------------------------------------------------------------------------

def assemble_history_prompt(records: list[HistoryRecord]) -> tuple[str, int]:
    """Build the 【历史参考】prompt segment from retrieved records.

    Args:
        records: Retrieved HistoryRecord list from retriever.retrieve().

    Returns:
        (history_prompt_string, token_count_estimate)
        Empty string and 0 when records is empty.
    """
    if not records:
        return "", 0

    header = (
        f"【历史参考】\n"
        f"检索到 {len(records)} 条相关历史记录（最多 3 条，每条 ≤ 300 字符）：\n"
    )
    lines = [header]

    total_chars = len(header)
    kept = 0

    for record in records:
        entry = record.to_prompt_entry(index=kept + 1, max_chars=300)
        # separator
        sep = "---\n" if kept < len(records) - 1 else "\n"
        candidate_chars = len(entry) + len(sep)

        # Budget check: history segment ≤ MAX_HISTORY_CHARS chars
        if total_chars + candidate_chars > HistoryRetriever.MAX_HISTORY_CHARS:
            break

        lines.append(entry)
        lines.append(sep)
        total_chars += candidate_chars
        kept += 1

    # Instruction suffix
    lines.append("\n历史引用须标注、不得与当日数据混淆。\n")

    result = "".join(lines)
    token_estimate = _estimate_tokens(result)
    return result, token_estimate
