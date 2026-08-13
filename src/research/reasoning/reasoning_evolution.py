"""V10 Sprint 4.5 — Task 3: Reasoning Evolution.

NOT: Learning → Update Belief
BUT: Learning → Update Reasoning Template

Core insight: True learning isn't about updating belief confidence.
It's about updating HOW you reason. The reasoning template itself should evolve.

Architecture:
    Prediction Error
        ↓
    Capture: Old Reasoning + Mistake Context + Correction
        ↓
    Store: ReasoningCase → ReasoningLibrary
        ↓
    Future: Pre-Synthesis Retrieval → Inject Past Failures into Context
        ↓
    Result: "I've seen this pattern before and here's what went wrong"

This creates a REASONING LIBRARY — a growing collection of reasoning cases
that serve as "memory of mistakes" for the system.

Key components:
    1. ReasoningCase      — Old reasoning → Mistake → New reasoning
    2. ReasoningLibrary   — Persistent store of reasoning cases
    3. ReasoningEvolution — Engine that processes outcomes into cases
    4. CaseRetriever      — Retrieves relevant past cases for new reasoning
    5. ReasoningTemplate  — Evolves from patterns across cases
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.shared.logging import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ReasoningCase:
    """A single reasoning case: Old → Mistake → New.

    This is the atomic unit of the Reasoning Library.
    Each case captures what went wrong and how to fix it.
    """

    case_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    # Context
    date: str = ""  # When the original reasoning was done
    regime_label: str = ""
    domains: list[str] = field(default_factory=list)
    prediction_id: str = ""

    # Old reasoning (what we thought)
    old_reasoning: str = ""  # The original reasoning chain / hypothesis
    old_direction: str = ""  # bullish / bearish / neutral
    old_confidence: float = 0.0
    old_key_assumptions: list[str] = field(default_factory=list)
    old_evidence_used: list[str] = field(default_factory=list)

    # What happened (the mistake)
    mistake_type: str = (
        ""  # wrong_direction / wrong_magnitude / wrong_timing / missed_risk / false_analogy
    )
    mistake_description: str = ""
    actual_outcome: str = ""
    actual_direction: str = ""
    error_magnitude: float = 0.0  # How big was the error
    root_cause: str = ""  # Why we got it wrong
    surprise_factor: float = 0.0  # How surprising was the outcome (0-1)

    # New reasoning (correction)
    new_reasoning: str = ""  # The corrected reasoning
    what_should_have_done: str = ""  # What the reasoning SHOULD have been
    missing_evidence: list[str] = field(default_factory=list)
    missing_counterarguments: list[str] = field(default_factory=list)
    missed_risks: list[str] = field(default_factory=list)

    # Evolution meta
    pattern_label: str = ""  # Classified pattern for retrieval
    embedding_keywords: list[str] = field(default_factory=list)
    severity: str = ""  # "minor" / "moderate" / "major" / "catastrophic"
    lessons_learned: list[str] = field(default_factory=list)
    reuse_count: int = 0  # How many times this case has been retrieved

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "date": self.date,
            "regime_label": self.regime_label,
            "domains": self.domains,
            "mistake_type": self.mistake_type,
            "root_cause": self.root_cause,
            "severity": self.severity,
            "old_reasoning": self.old_reasoning[:300],
            "new_reasoning": self.new_reasoning[:300],
            "lessons_learned": self.lessons_learned,
            "pattern_label": self.pattern_label,
            "embedding_keywords": self.embedding_keywords,
            "reuse_count": self.reuse_count,
        }


@dataclass
class RetrievalResult:
    """Result of retrieving relevant past cases."""

    query_context: str = ""  # What we're trying to reason about now
    matched_cases: list[ReasoningCase] = field(default_factory=list)
    similarity_scores: list[float] = field(default_factory=list)
    total_matches: int = 0
    relevant_lessons: list[str] = field(default_factory=list)
    retrieval_context: str = ""  # Injected context for the reasoning step


@dataclass
class ReasoningTemplate:
    """An evolved reasoning template built from patterns in the library.

    This is the output of reasoning evolution — a template that incorporates
    past mistakes into structured guidance for future reasoning.
    """

    template_id: str = ""
    template_name: str = ""
    version: int = 1
    last_updated: str = ""
    based_on_cases: int = 0  # How many cases formed this template

    # Template sections
    domain: str = ""  # Which domain this template applies to
    regime_patterns: list[str] = field(default_factory=list)
    common_mistakes: list[str] = field(default_factory=list)
    must_check_evidence: list[str] = field(default_factory=list)
    must_consider_counterarguments: list[str] = field(default_factory=list)
    critical_assumptions_to_test: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)  # Patterns that led to past failures

    # Meta-template (how to use this template)
    reasoning_guidance: str = ""

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "template_name": self.template_name,
            "version": self.version,
            "domain": self.domain,
            "common_mistakes": self.common_mistakes,
            "must_check_evidence": self.must_check_evidence,
            "red_flags": self.red_flags,
            "reasoning_guidance": self.reasoning_guidance[:500],
        }


@dataclass
class EvolutionReport:
    """Report produced by reasoning evolution cycle."""

    cases_created: int = 0
    templates_updated: int = 0
    library_size: int = 0
    patterns_discovered: list[str] = field(default_factory=list)
    top_lessons: list[str] = field(default_factory=list)
    new_cases: list[ReasoningCase] = field(default_factory=list)
    updated_templates: list[ReasoningTemplate] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "cases_created": self.cases_created,
            "templates_updated": self.templates_updated,
            "library_size": self.library_size,
            "patterns_discovered": self.patterns_discovered,
            "top_lessons": self.top_lessons[:5],
        }


# ═══════════════════════════════════════════════════════════════════════════
# Mistake Pattern Classifier
# ═══════════════════════════════════════════════════════════════════════════

_MISTAKE_PATTERNS = {
    "wrong_direction": {
        "keywords": [
            "direction",
            "bullish",
            "bearish",
            "went up",
            "fell",
            "rallied",
            "sold off",
            "opposite",
            "reversed",
            "wrong way",
        ],
        "severity": "major",
    },
    "wrong_magnitude": {
        "keywords": [
            "magnitude",
            "underestimated",
            "overestimated",
            "much more",
            "much less",
            "smaller than",
            "larger than",
            "size",
            "scale",
        ],
        "severity": "moderate",
    },
    "wrong_timing": {
        "keywords": [
            "too early",
            "too late",
            "timing",
            "already moved",
            "before",
            "after",
            "patience",
            "premature",
        ],
        "severity": "moderate",
    },
    "missed_risk": {
        "keywords": [
            "didn't consider",
            "overlooked",
            "missed",
            "black swan",
            "tail event",
            "unexpected",
            "shock",
            "surprise",
            "did not foresee",
        ],
        "severity": "major",
    },
    "false_analogy": {
        "keywords": [
            "similar to",
            "like last time",
            "history repeats",
            "analog",
            "just like",
            "same as",
            "historical pattern",
            "this time is different",
        ],
        "severity": "major",
    },
    "overconfidence": {
        "keywords": [
            "too confident",
            "overconfident",
            "high conviction wrong",
            "too certain",
            "dismissive of",
            "ignored",
        ],
        "severity": "major",
    },
    "missing_evidence": {
        "keywords": [
            "didn't have",
            "missing data",
            "incomplete information",
            "unaware of",
            "new data",
            "revised",
            "data was wrong",
        ],
        "severity": "moderate",
    },
    "recency_bias": {
        "keywords": [
            "extrapolate",
            "recent trend",
            "momentum",
            "trend following",
            "assumed continuation",
            "extrapolating",
        ],
        "severity": "minor",
    },
    "narrative_capture": {
        "keywords": [
            "believed the story",
            "narrative",
            "convinced by",
            "sold on",
            "bought into",
            "consensus narrative",
            "popular view",
        ],
        "severity": "moderate",
    },
    "correlation_breakdown": {
        "keywords": [
            "correlation broke",
            "decoupled",
            "diverged",
            "no longer correlated",
            "relationship changed",
            "regime change",
        ],
        "severity": "major",
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# Keyword-Based Similarity Engine (deterministic, no embeddings needed)
# ═══════════════════════════════════════════════════════════════════════════


class CaseRetriever:
    """Retrieve relevant past reasoning cases using keyword similarity.

    This is a deterministic retrieval engine. It uses keyword overlap
    between the current reasoning context and past cases' embedding_keywords.
    No vector database needed — pure computation.

    For production, this can be swapped with a vector-embedding retriever
    while keeping the same interface.
    """

    def retrieve(
        self,
        library: ReasoningLibrary,
        query_context: str,
        current_domains: list[str],
        current_regime: str = "",
        max_cases: int = 5,
        min_similarity: float = 0.15,
    ) -> RetrievalResult:
        """Retrieve most relevant past reasoning cases.

        Args:
            library: The reasoning library to search.
            query_context: Current reasoning context text.
            current_domains: Current domain tags.
            current_regime: Current regime label.
            max_cases: Maximum cases to return.
            min_similarity: Minimum similarity threshold.

        Returns:
            RetrievalResult with matched cases and lessons.
        """
        # Extract query keywords
        query_keywords = self._extract_keywords(query_context, current_domains, current_regime)

        # Score each case
        scored = []
        for case in library.cases:
            similarity = self._calculate_similarity(query_keywords, case)
            if similarity >= min_similarity:
                scored.append((similarity, case))

        # Sort by similarity descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Take top N
        top = scored[:max_cases]

        matched_cases = [case for _, case in top]
        similarity_scores = [score for score, _ in top]

        # Extract lessons
        relevant_lessons = []
        for case in matched_cases:
            for lesson in case.lessons_learned:
                if lesson not in relevant_lessons:
                    relevant_lessons.append(lesson)

        # Build retrieval context for injection
        retrieval_context = self._build_retrieval_context(matched_cases)

        return RetrievalResult(
            query_context=query_context[:500],
            matched_cases=matched_cases,
            similarity_scores=similarity_scores,
            total_matches=len(matched_cases),
            relevant_lessons=relevant_lessons[:10],
            retrieval_context=retrieval_context,
        )

    def _extract_keywords(self, query: str, domains: list[str], regime: str) -> list[str]:
        """Extract meaningful keywords from query context."""
        keywords = []

        # Domain words
        keywords.extend(domains)

        # Regime
        if regime:
            keywords.extend(regime.replace("_", " ").split())

        # Extract meaningful words (4+ chars, skip stopwords)
        stopwords = {
            "this",
            "that",
            "the",
            "and",
            "for",
            "with",
            "from",
            "have",
            "been",
            "what",
            "when",
            "where",
            "which",
            "would",
            "could",
            "should",
            "about",
            "their",
            "there",
            "being",
            "also",
            "will",
            "into",
            "over",
            "more",
            "some",
            "such",
            "than",
            "then",
            "they",
        }

        words = re.findall(r"\b[a-z]{4,}\b", query.lower())
        for w in words:
            if w not in stopwords and w not in keywords:
                keywords.append(w)

        return keywords[:30]  # Cap at 30 keywords

    def _calculate_similarity(self, query_keywords: list[str], case: ReasoningCase) -> float:
        """Calculate similarity between query and a reasoning case."""
        if not query_keywords:
            return 0.0

        # Build case keyword set
        case_keywords = set(case.embedding_keywords)
        case_keywords.update(k.lower() for k in case.domains)
        case_keywords.update(k.lower() for k in case.mistake_type.split("_"))
        if case.regime_label:
            case_keywords.update(case.regime_label.replace("_", " ").split())
        if case.pattern_label:
            case_keywords.add(case.pattern_label.lower())

        # Tokenize old reasoning for additional keywords
        extra_keywords = re.findall(r"\b[a-z]{4,}\b", case.old_reasoning.lower()[:500])
        case_keywords.update(extra_keywords[:15])

        # Intersection / Union (Jaccard-like)
        query_set = set(query_keywords)
        intersection = query_set & case_keywords

        if not intersection:
            return 0.0

        jaccard = len(intersection) / min(len(query_set), len(case_keywords))

        # Boost for domain match
        domain_overlap = set(d.lower() for d in case.domains) & query_set
        domain_boost = min(len(domain_overlap) * 0.1, 0.3)

        # Boost for same mistake type mentioned in query
        mistake_words = set(case.mistake_type.split("_"))
        if mistake_words & query_set:
            domain_boost += 0.1

        # Recency boost — more recent cases get slightly higher weight
        recency_boost = min(case.reuse_count * 0.02, 0.1)

        return min(jaccard + domain_boost + recency_boost, 1.0)

    def _build_retrieval_context(self, cases: list[ReasoningCase]) -> str:
        """Build context to inject into the reasoning step."""
        if not cases:
            return ""

        parts = [
            "=== REASONING LIBRARY: PAST FAILURES RELEVANT TO CURRENT CONTEXT ===",
            f"Retrieved {len(cases)} past reasoning failure(s):",
            "",
        ]

        for i, case in enumerate(cases):
            parts.append(f"[Case {i + 1}] Pattern: {case.pattern_label or case.mistake_type}")
            parts.append(f"  Regime: {case.regime_label} | Domain: {', '.join(case.domains)}")
            parts.append(f"  What we thought: {case.old_reasoning[:200]}...")
            parts.append(f"  What happened: {case.mistake_description[:200]}")
            parts.append(f"  What we should have done: {case.what_should_have_done[:200]}")
            parts.append(f"  Lessons: {'; '.join(case.lessons_learned[:3])}")
            parts.append("")

        parts.append(
            "CRITICAL: Do NOT repeat these mistakes. Check your reasoning against these patterns."
        )
        parts.append(
            "For each claim you make, ask: 'Am I making the same mistake as Case X above?'"
        )

        return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# Reasoning Library
# ═══════════════════════════════════════════════════════════════════════════


class ReasoningLibrary:
    """Persistent library of reasoning cases.

    Stores and organizes reasoning cases — the "memory of mistakes."
    Supports keyword-based retrieval for injection into future reasoning.
    """

    def __init__(self, max_cases: int = 1000):
        self.cases: list[ReasoningCase] = []
        self.max_cases = max_cases
        self._retriever = CaseRetriever()

    def add_case(self, case: ReasoningCase) -> None:
        """Add a new reasoning case to the library."""
        if not case.case_id:
            case.case_id = self._generate_case_id(case)

        # Don't add duplicates
        if any(c.case_id == case.case_id for c in self.cases):
            logger.debug("Duplicate reasoning case: %s", case.case_id)
            return

        self.cases.append(case)

        # Evict oldest if over capacity
        if len(self.cases) > self.max_cases:
            self.cases.sort(key=lambda c: (c.reuse_count, c.timestamp))
            self.cases = self.cases[-self.max_cases :]

        logger.info(
            "ReasoningLibrary: added case %s [%s/%s], library size=%d",
            case.case_id,
            case.mistake_type,
            case.pattern_label,
            len(self.cases),
        )

    def retrieve_relevant(
        self,
        query_context: str,
        domains: list[str],
        regime: str = "",
        max_cases: int = 5,
    ) -> RetrievalResult:
        """Retrieve cases relevant to current reasoning context."""
        result = self._retriever.retrieve(
            self,
            query_context,
            domains,
            regime,
            max_cases,
        )

        # Increment reuse count
        for case in result.matched_cases:
            case.reuse_count += 1

        logger.info(
            "Retrieval: %d relevant cases found (query domains=%s, regime=%s)",
            result.total_matches,
            domains,
            regime,
        )

        return result

    def get_by_mistake_type(self, mistake_type: str) -> list[ReasoningCase]:
        """Get all cases of a specific mistake type."""
        return [c for c in self.cases if c.mistake_type == mistake_type]

    def get_by_domain(self, domain: str) -> list[ReasoningCase]:
        """Get all cases for a specific domain."""
        return [c for c in self.cases if domain in c.domains]

    def get_by_regime(self, regime: str) -> list[ReasoningCase]:
        """Get all cases for a specific regime."""
        return [c for c in self.cases if c.regime_label == regime]

    def get_statistics(self) -> dict:
        """Get library statistics."""
        if not self.cases:
            return {"total_cases": 0, "mistake_types": {}, "domains": {}, "avg_severity": "N/A"}

        mistake_counts = {}
        domain_counts = {}
        severities = []

        for case in self.cases:
            mt = case.mistake_type or "unknown"
            mistake_counts[mt] = mistake_counts.get(mt, 0) + 1

            for d in case.domains:
                domain_counts[d] = domain_counts.get(d, 0) + 1

            severities.append(case.severity)

        severity_order = {"catastrophic": 4, "major": 3, "moderate": 2, "minor": 1}
        avg_sev_num = sum(severity_order.get(s, 0) for s in severities) / len(severities)
        avg_sev = {4: "catastrophic", 3: "major", 2: "moderate", 1: "minor"}.get(
            round(avg_sev_num), "moderate"
        )

        return {
            "total_cases": len(self.cases),
            "mistake_types": mistake_counts,
            "domains": domain_counts,
            "avg_severity": avg_sev,
            "most_common_mistake": (
                max(mistake_counts, key=mistake_counts.get) if mistake_counts else "N/A"
            ),
        }

    def to_dict(self) -> dict:
        return {
            "total_cases": len(self.cases),
            "cases": [c.to_dict() for c in self.cases],
            "statistics": self.get_statistics(),
        }

    def _generate_case_id(self, case: ReasoningCase) -> str:
        """Generate a unique case ID."""
        content = (
            f"{case.date}_{case.mistake_type}_{case.regime_label}_" f"{'|'.join(case.domains)}"
        )
        hash_id = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"RC-{case.date}-{hash_id}"


# ═══════════════════════════════════════════════════════════════════════════
# Reasoning Evolution Engine
# ═══════════════════════════════════════════════════════════════════════════


class ReasoningEvolution:
    """V10 Sprint 4.5: Evolution engine for reasoning templates.

    Takes prediction outcomes, identifies what went wrong in the REASONING
    (not just the prediction), and creates new ReasoningCases that become
    part of the Reasoning Library.

    Unlike belief updates (which just adjust confidence), this creates
    REUSABLE REASONING PATTERNS — "I should check X before concluding Y"
    — that get injected into future reasoning contexts.
    """

    def __init__(self, library: ReasoningLibrary | None = None):
        self.library = library or ReasoningLibrary()
        self._case_counter: dict[str, int] = {}

    def evolve(
        self,
        prediction: dict,
        outcome: dict,
        old_memo_text: str = "",
        old_hypotheses: list | None = None,
        old_evidence: dict | None = None,
        regime_label: str = "",
        domains: list[str] | None = None,
    ) -> ReasoningCase:
        """Create a reasoning case from a prediction-outcome pair.

        This is the core engine: take what happened, diagnose the reasoning
        error, and create a case for future retrieval.

        Args:
            prediction: Prediction dict (direction, confidence, statement, etc.)
            outcome: Outcome dict (actual_direction, was_correct, actual_pct, etc.)
            old_memo_text: The original memo that contained the prediction.
            old_hypotheses: The hypotheses that led to the prediction.
            old_evidence: The evidence clusters used.
            regime_label: The regime at prediction time.
            domains: The domains in play.

        Returns:
            ReasoningCase ready to add to the Reasoning Library.
        """
        date = prediction.get("timestamp", prediction.get("date", ""))[:10]
        pred_direction = prediction.get(
            "predicted_direction", prediction.get("direction", "unknown")
        )
        pred_confidence = float(prediction.get("confidence", 0.5))
        pred_statement = prediction.get("prediction_statement", prediction.get("statement", ""))
        was_correct = outcome.get("was_correct", False)
        actual_direction = outcome.get("actual_direction", outcome.get("direction", "unknown"))
        actual_pct = float(outcome.get("actual_change_pct", 0.0))

        # Don't create cases for correct predictions
        if was_correct:
            return ReasoningCase(
                case_id=f"RC-CORRECT-{date}",
                date=date,
                regime_label=regime_label,
                domains=domains or [],
                old_reasoning=pred_statement[:500],
                old_direction=pred_direction,
                old_confidence=pred_confidence,
                mistake_type="no_error",
                mistake_description="Prediction was correct — no reasoning error to capture.",
                severity="minor",
                lessons_learned=["Good call: reasoning was sound."],
            )

        # 1. Classify the mistake
        mistake_type, severity = self._classify_mistake(
            pred_direction,
            actual_direction,
            pred_confidence,
            old_memo_text,
            outcome,
        )

        # 2. Extract old reasoning components
        old_assumptions = self._extract_assumptions(old_memo_text, old_hypotheses)
        old_evidence_used = self._extract_evidence(old_evidence)
        old_key_risks = self._extract_risks(old_memo_text)

        # 3. Analyze what went wrong
        mistake_description = self._describe_mistake(
            mistake_type,
            pred_statement,
            pred_direction,
            actual_direction,
            actual_pct,
        )

        # 4. Determine root cause
        root_cause = self._determine_root_cause(
            mistake_type,
            old_assumptions,
            old_evidence_used,
            old_memo_text,
        )

        # 5. Generate new/corrected reasoning
        new_reasoning = self._generate_corrected_reasoning(
            mistake_type,
            pred_statement,
            old_memo_text,
            actual_direction,
            actual_pct,
        )

        # 6. What should have been done
        what_should_have_done = self._generate_should_have_done(
            mistake_type,
            old_memo_text,
        )

        # 7. Missing elements
        missing_evidence = self._find_missing_evidence(old_evidence, mistake_type)
        missing_counter = self._generate_counterarguments(old_memo_text, mistake_type)
        missed_risks = [r for r in old_key_risks if r not in str(mistake_description)]

        # 8. Generate lessons
        lessons = self._generate_lessons(
            mistake_type,
            pred_direction,
            actual_direction,
            root_cause,
            old_assumptions,
        )

        # 9. Pattern label and embedding keywords
        pattern_label = self._generate_pattern_label(
            mistake_type,
            regime_label,
            pred_direction,
            actual_direction,
        )
        embedding_keywords = self._generate_embedding_keywords(
            mistake_type,
            regime_label,
            domains or [],
            old_memo_text,
            pred_statement,
            root_cause,
        )

        # 10. Surprise factor
        surprise = self._calculate_surprise(pred_confidence, was_correct, actual_pct)

        case = ReasoningCase(
            date=date,
            regime_label=regime_label,
            domains=domains or [],
            prediction_id=str(prediction.get("prediction_id", "")),
            old_reasoning=pred_statement[:1000],
            old_direction=pred_direction,
            old_confidence=pred_confidence,
            old_key_assumptions=old_assumptions[:10],
            old_evidence_used=old_evidence_used[:10],
            mistake_type=mistake_type,
            mistake_description=mistake_description[:500],
            actual_outcome=f"Direction: {actual_direction}, Change: {actual_pct:+.1f}%",
            actual_direction=actual_direction,
            error_magnitude=round(abs(actual_pct), 1),
            root_cause=root_cause[:300],
            surprise_factor=round(surprise, 2),
            new_reasoning=new_reasoning[:1000],
            what_should_have_done=what_should_have_done[:500],
            missing_evidence=missing_evidence[:5],
            missing_counterarguments=missing_counter[:5],
            missed_risks=missed_risks[:5],
            pattern_label=pattern_label,
            embedding_keywords=embedding_keywords[:20],
            severity=severity,
            lessons_learned=lessons[:5],
        )

        # Add to library
        self.library.add_case(case)

        logger.info(
            "ReasoningEvolution: created case %s [%s] — " "pred was %s, actual %s, root cause: %s",
            case.case_id,
            case.pattern_label,
            pred_direction,
            actual_direction,
            root_cause[:60],
        )

        return case

    def evolve_from_pipeline(
        self,
        pipeline_result: Any,
        outcome: dict,
        prediction: dict,
    ) -> ReasoningCase:
        """Create a reasoning case from a full pipeline result.

        Extracts all context from the pipeline result for richer cases.

        Args:
            pipeline_result: PipelineResult from a previous run.
            outcome: Outcome data.
            prediction: Prediction data.

        Returns:
            ReasoningCase.
        """
        memo = ""
        hypotheses = None
        evidence = None
        regime = ""
        domains = []

        if pipeline_result:
            memo = getattr(pipeline_result, "memo_text", "")
            regime = (
                pipeline_result.step_llm_synthesis.structured_json.get("_prompt_routing", {}).get(
                    "regime_label", ""
                )
                if hasattr(pipeline_result, "step_llm_synthesis")
                else ""
            )
            domains = getattr(pipeline_result, "selected_domains", [])
            evidence = (
                pipeline_result.step_evidence.structured_json
                if hasattr(pipeline_result, "step_evidence")
                else None
            )
            hypotheses = (
                pipeline_result.step_hypothesis.structured_json.get("hypotheses", [])
                if hasattr(pipeline_result, "step_hypothesis")
                else None
            )

        return self.evolve(
            prediction=prediction,
            outcome=outcome,
            old_memo_text=memo,
            old_hypotheses=hypotheses,
            old_evidence=evidence,
            regime_label=regime,
            domains=domains,
        )

    # ── Mistake Classification ─────────────────────────────────────────

    def _classify_mistake(
        self,
        pred_dir: str,
        actual_dir: str,
        confidence: float,
        memo_text: str,
        outcome: dict,
    ) -> tuple[str, str]:
        """Classify the type of reasoning mistake.

        Returns (mistake_type, severity).
        """
        text_lower = memo_text.lower()

        # Direction wrong = wrong_direction
        if pred_dir != actual_dir and pred_dir != "unknown" and actual_dir != "unknown":
            # Check for overconfidence
            if confidence > 0.8:
                return "overconfidence", "major"
            return "wrong_direction", "major"

        # Same direction but check magnitude
        actual_pct = abs(float(outcome.get("actual_change_pct", 0)))
        if pred_dir == actual_dir:
            if actual_pct < 1.0:
                # Moved right direction but tiny — could be timing issue
                return "wrong_timing", "moderate"
            elif actual_pct > 10.0:
                # Massive move but we only got direction right
                return "wrong_magnitude", "moderate"
            else:
                return "wrong_magnitude", "minor"

        # Check for narrative capture
        narrative_capture_signals = [
            "consensus",
            "everyone",
            "widely expected",
            "obvious",
            "no-brainer",
            "sure thing",
        ]
        if any(s in text_lower for s in narrative_capture_signals):
            return "narrative_capture", "moderate"

        # Check for false analogy
        analogy_signals = [
            "similar to",
            "like the",
            "just like",
            "parallels",
            "reminds me of",
            "history shows",
            "last time",
        ]
        if any(s in text_lower for s in analogy_signals):
            return "false_analogy", "major"

        # Check for recency bias
        recency_signals = [
            "momentum",
            "trend",
            "continuing",
            "extrapolating",
            "will keep",
            "maintain",
            "sustained",
        ]
        if any(s in text_lower for s in recency_signals) and confidence > 0.6:
            return "recency_bias", "minor"

        # Default
        return "missed_risk", "major"

    # ── Evidence & Assumption Extraction ───────────────────────────────

    def _extract_assumptions(self, memo_text: str, hypotheses: list | None) -> list[str]:
        """Extract assumptions from memo and hypotheses."""
        assumptions = []

        # From memo text
        assumption_markers = [
            r"(?:assuming|assume[sd]?\s+that|if\s+we\s+assume|based\s+on\s+the\s+assumption)\s+(.{10,120}?)(?:[.;]|$)",
            r"(?:premise\s+(?:is|that)|our\s+base\s+case\s+(?:is|assumes))\s+(.{10,120}?)(?:[.;]|$)",
        ]
        for pattern in assumption_markers:
            matches = re.findall(pattern, memo_text[:3000])
            for m in matches:
                assumptions.append(str(m).strip())

        # From hypotheses
        if hypotheses:
            for h in hypotheses:
                if isinstance(h, dict):
                    statement = h.get("statement", "")
                    if statement and len(statement) > 10:
                        assumptions.append(statement[:150])

        return assumptions

    def _extract_evidence(self, evidence: dict | None) -> list[str]:
        """Extract evidence items from structured evidence."""
        items = []
        if not evidence:
            return items

        for cluster in evidence.get("clusters", []):
            if isinstance(cluster, dict):
                theme = cluster.get("theme", "")
                description = cluster.get("description", "")
                if theme:
                    items.append(f"{theme}: {str(description)[:100]}")
                elif description:
                    items.append(str(description)[:100])

        return items

    def _extract_risks(self, memo_text: str) -> list[str]:
        """Extract risk mentions from memo."""
        risks = []

        risk_section = re.search(
            r"(?:key\s+risks?|risk\s+factors?|risks?\s+and\s+challenges?)(?:[\s:]*)(.{10,800}?)(?:\n\n|\n#|$)",
            memo_text[:4000],
            re.IGNORECASE | re.DOTALL,
        )

        if risk_section:
            risk_items = re.findall(r"[\d.]+[\s)]*([^.\n]{20,150})", risk_section.group(1))
            risks.extend(r.strip() for r in risk_items)

        return risks

    # ── Root Cause Analysis ────────────────────────────────────────────

    def _describe_mistake(
        self,
        mistake_type: str,
        pred_statement: str,
        pred_dir: str,
        actual_dir: str,
        actual_pct: float,
    ) -> str:
        """Describe the mistake in natural language."""
        descriptions = {
            "wrong_direction": (
                f"Predicted {pred_dir} but market went {actual_dir} "
                f"(moved {actual_pct:+.1f}%). The direction call was completely inverted."
            ),
            "overconfidence": (
                f"Predicted {pred_dir} with very high conviction but market went {actual_dir}. "
                f"Overconfidence prevented consideration of alternatives."
            ),
            "wrong_magnitude": (
                f"Predicted {pred_dir} but underestimated magnitude. "
                f"Market moved {actual_pct:+.1f}%, far beyond expected range."
            ),
            "wrong_timing": (
                "Direction was eventually correct but timing was off. "
                "The trade thesis was premature — entered too early."
            ),
            "missed_risk": (
                "Did not foresee a key risk that materialized. "
                "The reasoning framework was incomplete — missing critical tail events."
            ),
            "false_analogy": (
                "Drew an inappropriate historical parallel. "
                "The analogy didn't capture structural differences in this regime."
            ),
            "narrative_capture": (
                "Captured by consensus narrative. "
                "Reasoning was influenced by the dominant macro story rather than evidence."
            ),
            "recency_bias": (
                "Over-extrapolated recent trends. "
                "Assumed momentum would continue without considering mean reversion."
            ),
            "missing_evidence": (
                "Key evidence was missing from the analysis. "
                "Would have changed the conclusion if considered."
            ),
            "correlation_breakdown": (
                "Relied on a correlation that broke. "
                "The assumed relationship between assets decoupled in this regime."
            ),
        }
        return descriptions.get(mistake_type, f"Reasoning error: {mistake_type}")

    def _determine_root_cause(
        self,
        mistake_type: str,
        assumptions: list[str],
        evidence: list[str],
        memo_text: str,
    ) -> str:
        """Determine the fundamental root cause of the mistake."""
        root_causes = {
            "wrong_direction": (
                "Epistemological error: the causal model was inverted. "
                "The relationship between variables moved in the opposite direction "
                "from what the reasoning assumed. Check: is the sign of the causal "
                "relationship correct and stable in this regime?"
            ),
            "overconfidence": (
                "Calibration error: confidence was too high relative to actual predictive power. "
                "High-conviction calls require a falsification test. "
                "Check: 'What would prove me wrong?' was never adequately asked."
            ),
            "wrong_magnitude": (
                "Scaling error: got direction right but underestimated non-linearity. "
                "Positioning/crowding/exhaustion can create extreme moves. "
                "Check: is there a reflexivity or feedback loop amplifying the move?"
            ),
            "wrong_timing": (
                "Temporal error: the causal chain was correct but the timeline was wrong. "
                "Catalysts were further in the future than anticipated. "
                "Check: patience — not every thesis trades immediately."
            ),
            "missed_risk": (
                "Completeness error: the risk framework was incomplete. "
                "Tail risks and Black Swan events were not adequately considered. "
                "Check: what's the worst case? What's the second-order risk?"
            ),
            "false_analogy": (
                "Pattern-matching error: historical analogy was superficially similar "
                "but structurally different. The narrative of 'this time is like X' "
                "obscured key differences. Check: how is this time ACTUALLY different?"
            ),
            "narrative_capture": (
                "Social proof error: reasoning was influenced by consensus rather than evidence. "
                "When a narrative becomes dominant, counter-evidence gets discounted. "
                "Check: am I reasoning independently or just echoing the crowd?"
            ),
            "recency_bias": (
                "Extrapolation error: projected recent trend into the future. "
                "Markets are mean-reverting over long horizons. "
                "Check: is the trend structure justified or just momentum-chasing?"
            ),
            "missing_evidence": (
                "Information error: decision was made with incomplete data. "
                "Some evidence was unavailable or overlooked. "
                "Check: what don't I know? What data would change my mind?"
            ),
            "correlation_breakdown": (
                "Regime-change error: relied on a stable correlation that broke. "
                "Correlations are regime-dependent and can invert. "
                "Check: is this correlation stable in the current regime?"
            ),
        }
        return root_causes.get(
            mistake_type, f"Undiagnosed root cause for {mistake_type}. Further analysis needed."
        )

    # ── Corrected Reasoning Generation ─────────────────────────────────

    def _generate_corrected_reasoning(
        self,
        mistake_type: str,
        original_statement: str,
        memo_text: str,
        actual_direction: str,
        actual_pct: float,
    ) -> str:
        """Generate corrected reasoning based on what actually happened."""
        corrections = {
            "wrong_direction": (
                f"The original thesis ({original_statement[:100]}) was directionally wrong. "
                f"The market actually went {actual_direction} ({actual_pct:+.1f}%). "
                f"Revised reasoning must account for the missing drivers that caused "
                f"this outcome. Key question: what causal force was stronger than "
                f"the one we identified? What was the market ACTUALLY responding to?"
            ),
            "overconfidence": (
                f"High-conviction call ({original_statement[:100]}) was wrong. "
                f"Revised reasoning must explicitly quantify uncertainty and include "
                f"a falsification test: 'I will be wrong if X happens. X just happened.' "
                f"Future reasoning must cap confidence to actual predictive accuracy."
            ),
            "wrong_magnitude": (
                f"Direction was correct but magnitude was underestimated. "
                f"The market moved {actual_pct:+.1f}% — far more than expected. "
                f"Revised reasoning must incorporate non-linearity: feedback loops, "
                f"positioning effects, and reflexivity that can amplify moves."
            ),
            "wrong_timing": (
                "Direction call was directionally correct but poorly timed. "
                "Revised reasoning must separate 'what will happen' from 'when it will happen.' "
                "Add catalyst analysis and timeline sensitivity."
            ),
            "missed_risk": (
                "A critical risk went unidentified. Revised reasoning must include "
                "a structured risk framework with second-order and tail-risk analysis. "
                "Ask: 'What haven't I considered? What's the most dangerous assumption here?'"
            ),
            "false_analogy": (
                "Historical analogy was misleading. Revised reasoning must verify: "
                "(1) Are the structural conditions truly comparable? "
                "(2) What's different this time? "
                "(3) Is the causal mechanism the same or just the surface pattern?"
            ),
            "narrative_capture": (
                "Consensus narrative was wrong. Revised reasoning must independently "
                "verify claims against evidence rather than against other narratives. "
                "Deliberately seek disconfirming evidence for every claim."
            ),
            "recency_bias": (
                "Extrapolation of recent trends was incorrect. Revised reasoning must "
                "incorporate mean-reversion analysis: is this trend sustainable or "
                "is it borrowing from future returns? Consider counter-cyclical forces."
            ),
            "correlation_breakdown": (
                "Assumed correlation broke in this regime. Revised reasoning must "
                "regime-condition all relationships: 'Is this correlation stable in "
                "the current regime? What would break it?'"
            ),
        }
        return corrections.get(
            mistake_type, "Revised reasoning: original thesis was flawed. Requires re-analysis."
        )

    def _generate_should_have_done(self, mistake_type: str, memo_text: str) -> str:
        """Generate 'what the reasoning should have been' based on mistake type."""
        should_have = {
            "wrong_direction": (
                "Should have: (1) Stress-tested the direction call with a sign check: "
                "'Would a net increase in X really cause Y to go up?' "
                "(2) Searched for counter-evidence more aggressively. "
                "(3) Considered the possibility that the causal relationship was inverted."
            ),
            "overconfidence": (
                "Should have: (1) Explicitly stated the falsification condition. "
                "(2) Assigned probability to alternative scenarios. "
                "(3) Calibrated confidence to match the evidence strength."
            ),
            "wrong_magnitude": (
                "Should have: (1) Modeled non-linear scenarios. "
                "(2) Accounted for positioning crowding/amplification. "
                "(3) Included a 'worst case' scenario in the analysis."
            ),
            "wrong_timing": (
                "Should have: (1) Separated conviction on direction from conviction on timing. "
                "(2) Mapped specific catalysts to timeline. "
                "(3) Considered 'what would delay this thesis?'"
            ),
            "missed_risk": (
                "Should have: (1) Run a comprehensive risk identification process. "
                "(2) Explicitly listed 'what could go wrong' before 'what will go right.' "
                "(3) Included second-order/tail risks."
            ),
            "false_analogy": (
                "Should have: (1) Verified structural similarity, not surface similarity. "
                "(2) Identified 3+ ways this time IS different. "
                "(3) Used analogies as hypothesis generators, not conclusions."
            ),
            "narrative_capture": (
                "Should have: (1) Deliberately sought the counter-narrative. "
                "(2) Checked evidence independently rather than through the narrative lens. "
                "(3) Asked: 'If the narrative is wrong, what would the evidence look like?'"
            ),
            "recency_bias": (
                "Should have: (1) Tested trend sustainability with structural analysis. "
                "(2) Considered the long-term mean and reversion forces. "
                "(3) Asked: 'What would cause this trend to reverse?'"
            ),
            "correlation_breakdown": (
                "Should have: (1) Regime-conditioned all correlation assumptions. "
                "(2) Tested correlation stability in different macro regimes. "
                "(3) Identified what could cause decoupling."
            ),
        }
        return should_have.get(
            mistake_type, "Should have: Taken a more rigorous approach to the reasoning process."
        )

    # ── Missing Elements ───────────────────────────────────────────────

    def _find_missing_evidence(self, evidence: dict | None, mistake_type: str) -> list[str]:
        """Identify evidence that was missing from the analysis."""
        missing = []

        evidence_themes = set()
        if evidence:
            for c in evidence.get("clusters", []):
                theme = c.get("theme", "")
                if theme:
                    evidence_themes.add(theme.lower())

        # Standard checks by mistake type
        if mistake_type == "wrong_direction":
            if "positioning" not in evidence_themes and "flow" not in evidence_themes:
                missing.append("Positioning/flow data was missing from analysis")
            if "sentiment" not in evidence_themes:
                missing.append("Sentiment indicators were not considered")

        elif mistake_type == "missed_risk":
            missing.append("Tail-risk scenario analysis was insufficient")
            missing.append("Second-order effects were not mapped")

        elif mistake_type == "narrative_capture":
            missing.append("Counter-narrative evidence was not examined")
            missing.append("Independent data verification was bypassed in favor of narrative")

        elif mistake_type == "false_analogy":
            missing.append("Structural difference analysis was skipped")
            missing.append("Current-regime-specific evidence was insufficient")

        return missing

    def _generate_counterarguments(self, memo_text: str, mistake_type: str) -> list[str]:
        """Generate counterarguments that should have been considered."""
        counterarguments = []

        if mistake_type == "wrong_direction":
            counterarguments.append("The causal relationship could be inverted in this regime")
            counterarguments.append(
                "A stronger countervailing force may dominate the identified driver"
            )
        elif mistake_type == "overconfidence":
            counterarguments.append("Historical accuracy of similar high-conviction calls is low")
        elif mistake_type == "narrative_capture":
            counterarguments.append(
                "The narrative is consensus — if everyone believes it, it's likely "
                "already priced in, and the contrarian view has higher alpha potential"
            )
        elif mistake_type == "false_analogy":
            counterarguments.append(
                "Structural conditions are different: regime, policy, liquidity are not comparable"
            )

        return counterarguments

    # ── Lessons & Pattern Generation ───────────────────────────────────

    def _generate_lessons(
        self,
        mistake_type: str,
        pred_dir: str,
        actual_dir: str,
        root_cause: str,
        assumptions: list[str],
    ) -> list[str]:
        """Generate actionable lessons from this case."""
        lessons = []

        if mistake_type == "wrong_direction":
            lessons.append(
                f"Direction check: Before concluding {pred_dir}, actively search for "
                f"evidence supporting {actual_dir} — then weigh the two."
            )
        elif mistake_type == "overconfidence":
            lessons.append(
                "Calibration rule: Never exceed 80% confidence without an explicit, "
                "observable falsification condition."
            )
        elif mistake_type == "wrong_magnitude":
            lessons.append(
                "Always model non-linear scenarios — linear extrapolation fails "
                "at extremes when positioning and reflexivity amplify moves."
            )
        elif mistake_type == "wrong_timing":
            lessons.append(
                "Separate the thesis from the timing. A correct direction call "
                "can lose money if entered at the wrong time."
            )
        elif mistake_type == "missed_risk":
            lessons.append(
                "Risk-first reasoning: Map all risks BEFORE building the positive case. "
                "What you don't consider WILL hurt you."
            )
        elif mistake_type == "false_analogy":
            lessons.append(
                "Analogy discipline: For every historical parallel, identify at least "
                "3 structural differences. Analogies generate hypotheses, not conclusions."
            )
        elif mistake_type == "narrative_capture":
            lessons.append(
                "Narrative independence: Verify claims against evidence, not against the narrative. "
                "If a narrative is consensus, the alpha is in challenging it."
            )
        elif mistake_type == "recency_bias":
            lessons.append(
                "Trend skepticism: Every trend has a counter-force. Always ask: "
                "'What would reverse this trend?' before assuming continuation."
            )
        elif mistake_type == "correlation_breakdown":
            lessons.append(
                "Correlation is regime-dependent. Regime-condition every assumed relationship. "
                "A correlation that held for 5 years can break in 5 days."
            )

        # Add assumption-based lessons
        if assumptions:
            lessons.append(
                f"Assumption audit: Key assumptions must be explicitly tested, not implicitly accepted. "
                f"Assumption in question: '{assumptions[0][:100]}'"
            )

        if not lessons:
            lessons.append(f"Root cause: {root_cause[:150]}")

        return lessons

    def _generate_pattern_label(
        self,
        mistake_type: str,
        regime: str,
        pred_dir: str,
        actual_dir: str,
    ) -> str:
        """Generate a pattern label for retrieval."""
        parts = [mistake_type]

        # Add directional context
        if pred_dir == "bullish" and actual_dir == "bearish":
            parts.append("bull_flip")
        elif pred_dir == "bearish" and actual_dir == "bullish":
            parts.append("bear_flip")

        # Add regime context if available
        if regime:
            parts.append(regime)

        return "|".join(parts)

    def _generate_embedding_keywords(
        self,
        mistake_type: str,
        regime: str,
        domains: list[str],
        memo_text: str,
        pred_statement: str,
        root_cause: str,
    ) -> list[str]:
        """Generate keywords for similarity retrieval."""
        keywords = set()

        # Mistake type keywords
        if mistake_type in _MISTAKE_PATTERNS:
            keywords.update(_MISTAKE_PATTERNS[mistake_type]["keywords"][:10])

        # Domain tags
        keywords.update(d.lower() for d in domains)

        # Regime words
        if regime:
            keywords.update(regime.replace("_", " ").split())

        # Extract key terms from memo text
        memo_words = re.findall(r"\b[a-z]{4,}\b", memo_text[:2000].lower())
        # Filter stopwords
        stopwords = {
            "this",
            "that",
            "the",
            "and",
            "for",
            "with",
            "from",
            "have",
            "been",
            "what",
            "when",
            "where",
            "which",
            "would",
            "could",
            "should",
            "about",
            "their",
            "there",
            "being",
            "also",
            "will",
            "into",
            "over",
            "more",
            "some",
            "such",
            "than",
            "then",
            "they",
        }
        keywords.update(w for w in memo_words if w not in stopwords)

        # Root cause keywords
        keywords.update(re.findall(r"\b[a-z]{4,}\b", root_cause.lower()))

        return list(keywords)[:30]

    def _calculate_surprise(self, confidence: float, was_correct: bool, actual_pct: float) -> float:
        """Calculate how surprising the outcome was."""
        # High confidence + wrong = very surprising
        if not was_correct:
            surprise = confidence * 0.7  # Base: higher confidence = more surprising

            # Magnitude amplifies surprise
            if abs(actual_pct) > 10:
                surprise += 0.2
            elif abs(actual_pct) > 5:
                surprise += 0.1

            return min(surprise, 1.0)

        return 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Reasoning Template Evolver
# ═══════════════════════════════════════════════════════════════════════════


class ReasoningTemplateEvolver:
    """Evolve reasoning templates from the reasoning library.

    When enough cases accumulate for a specific pattern/domain/regime,
    this synthesizes them into an evolved reasoning template.

    The template becomes the "reasoning SOP" for that domain — it encodes
    all the lessons learned, checks that must be performed, and red flags.
    """

    def evolve_templates(self, library: ReasoningLibrary) -> list[ReasoningTemplate]:
        """Evolve reasoning templates from library cases.

        Returns list of new or updated ReasoningTemplate objects.
        """
        if not library.cases:
            return []

        templates = []

        # Group by mistake_type for pattern templates
        by_mistake = self._group_by_mistake(library.cases)
        for mistake_type, cases in by_mistake.items():
            if len(cases) >= 2:  # Need at least 2 cases to form a template
                template = self._build_template_from_cases(
                    mistake_type, cases, f"Pattern: {mistake_type}"
                )
                templates.append(template)

        # Group by domain
        by_domain = self._group_by_domain(library.cases)
        for domain, cases in by_domain.items():
            if len(cases) >= 3:
                template = self._build_template_from_cases(domain, cases, f"Domain: {domain}")
                templates.append(template)

        return templates

    def _group_by_mistake(self, cases: list[ReasoningCase]) -> dict[str, list[ReasoningCase]]:
        groups = {}
        for c in cases:
            mt = c.mistake_type or "unknown"
            groups.setdefault(mt, []).append(c)
        return groups

    def _group_by_domain(self, cases: list[ReasoningCase]) -> dict[str, list[ReasoningCase]]:
        groups = {}
        for c in cases:
            for d in c.domains:
                groups.setdefault(d, []).append(c)
        return groups

    def _build_template_from_cases(
        self, key: str, cases: list[ReasoningCase], template_name: str
    ) -> ReasoningTemplate:
        """Build a reasoning template from a group of cases."""
        # Collect common mistakes
        common_mistakes = []
        for c in cases:
            mistake_summary = (
                f"[{c.mistake_type}] In {c.regime_label}: {c.mistake_description[:150]}"
            )
            if mistake_summary not in common_mistakes:
                common_mistakes.append(mistake_summary)

        # Collect must-check evidence
        must_check = set()
        for c in cases:
            for e in c.old_evidence_used:
                must_check.add(e)
            for e in c.missing_evidence:
                must_check.add(e)

        # Collect counterarguments
        counterarguments = set()
        for c in cases:
            for ca in c.missing_counterarguments:
                counterarguments.add(ca)

        # Collect red flags
        red_flags = set()
        for c in cases:
            red_flags.add(f"[{c.mistake_type}] {c.mistake_description[:120]}")
            for assumption in c.old_key_assumptions[:2]:
                red_flags.add(f"Assumption: {assumption[:100]}")

        # Collect lessons
        all_lessons = []
        for c in cases:
            all_lessons.extend(c.lessons_learned)

        # Build reasoning guidance
        guidance = self._build_guidance(key, cases, all_lessons)

        return ReasoningTemplate(
            template_id=f"TPL-{hashlib.md5(key.encode()).hexdigest()[:8]}",
            template_name=template_name,
            version=len(cases),
            last_updated=datetime.now(UTC).isoformat(),
            based_on_cases=len(cases),
            domain=key,
            regime_patterns=list(set(c.regime_label for c in cases if c.regime_label)),
            common_mistakes=common_mistakes[:5],
            must_check_evidence=list(must_check)[:8],
            must_consider_counterarguments=list(counterarguments)[:5],
            critical_assumptions_to_test=[
                f"From Case [{c.case_id}]: {a[:100]}"
                for c in cases
                for a in c.old_key_assumptions[:2]
            ][:5],
            red_flags=list(red_flags)[:8],
            reasoning_guidance=guidance,
        )

    def _build_guidance(self, key: str, cases: list[ReasoningCase], lessons: list[str]) -> str:
        """Build reasoning guidance from cases and lessons."""
        unique_lessons = list(dict.fromkeys(lessons))[:5]

        severity_order = {"catastrophic": 4, "major": 3, "moderate": 2, "minor": 1}
        avg_sev = sum(severity_order.get(c.severity, 0) for c in cases) / max(len(cases), 1)

        severity_msg = {
            4: "CRITICAL — these patterns have caused catastrophic failures. MUST be checked.",
            3: "HIGH — these patterns have caused major losses. Strongly recommend checking.",
            2: "MODERATE — these patterns have caused moderate errors. Worth reviewing.",
            1: "LOW — these patterns are minor but should be noted.",
        }.get(round(avg_sev), "Review these patterns.")

        guidance_parts = [
            f"### Reasoning Guidance for {key}",
            f"Based on {len(cases)} past failures. Average severity: {severity_msg}",
            "",
            "#### CRITICAL CHECKS (before publishing any reasoning in this domain):",
        ]

        for i, lesson in enumerate(unique_lessons):
            guidance_parts.append(f"{i + 1}. {lesson}")

        guidance_parts.append("")
        guidance_parts.append("#### RED FLAGS (if you see these, STOP and re-evaluate):")

        red_flags = set()
        for c in cases:
            for a in c.old_key_assumptions[:2]:
                red_flags.add(f"- Assumption '{a[:80]}' — previously caused {c.mistake_type}")
        guidance_parts.extend(list(red_flags)[:5] or ["- No red flags configured"])

        return "\n".join(guidance_parts)


# ═══════════════════════════════════════════════════════════════════════════
# Top-Level Evolution Engine
# ═══════════════════════════════════════════════════════════════════════════


class ReasoningEvolutionEngine:
    """V10 Sprint 4.5: Complete reasoning evolution engine.

    Orchestrates the full learning cycle:
        Prediction → Outcome → ReasoningCase → ReasoningLibrary → ReasoningTemplate
    """

    def __init__(self):
        self.library = ReasoningLibrary()
        self.evolution = ReasoningEvolution(library=self.library)
        self.template_evolver = ReasoningTemplateEvolver()

    def process_outcome(
        self,
        prediction: dict,
        outcome: dict,
        memo_text: str = "",
        pipeline_result: Any | None = None,
        regime_label: str = "",
        domains: list[str] | None = None,
    ) -> ReasoningCase:
        """Process a single prediction outcome into a reasoning case."""
        if pipeline_result:
            return self.evolution.evolve_from_pipeline(
                pipeline_result,
                outcome,
                prediction,
            )
        return self.evolution.evolve(
            prediction=prediction,
            outcome=outcome,
            old_memo_text=memo_text,
            regime_label=regime_label,
            domains=domains,
        )

    def process_batch(
        self,
        predictions: list[dict],
        outcomes: list[dict],
        pipeline_results: list | None = None,
    ) -> EvolutionReport:
        """Process a batch of outcomes into reasoning cases and templates."""
        cases_created = 0

        # Create cases
        outcome_map = {o.get("prediction_id", ""): o for o in outcomes}
        new_cases = []

        for i, pred in enumerate(predictions):
            pid = pred.get("prediction_id", "")
            outcome = outcome_map.get(pid, outcomes[i] if i < len(outcomes) else None)
            if not outcome:
                continue

            pipeline_result = (
                pipeline_results[i] if pipeline_results and i < len(pipeline_results) else None
            )
            case = self.process_outcome(
                prediction=pred,
                outcome=outcome,
                pipeline_result=pipeline_result,
            )
            if case.mistake_type != "no_error":
                new_cases.append(case)
                cases_created += 1

        # Evolve templates
        updated_templates = self.template_evolver.evolve_templates(self.library)

        # Discover patterns
        patterns = self._discover_patterns(new_cases)

        # Top lessons
        top_lessons = list(dict.fromkeys(lesson for c in new_cases for lesson in c.lessons_learned))

        return EvolutionReport(
            cases_created=cases_created,
            templates_updated=len(updated_templates),
            library_size=len(self.library.cases),
            patterns_discovered=patterns,
            top_lessons=top_lessons[:10],
            new_cases=new_cases,
            updated_templates=updated_templates,
        )

    def retrieve_for_reasoning(
        self,
        query_context: str,
        domains: list[str],
        regime: str = "",
    ) -> RetrievalResult:
        """Retrieve relevant past cases before a new reasoning step.

        This should be called BEFORE Step 7 (LLM Synthesis) to inject
        past failure context into the reasoning process.
        """
        return self.library.retrieve_relevant(query_context, domains, regime)

    def get_library_stats(self) -> dict:
        """Get reasoning library statistics."""
        return self.library.get_statistics()

    def _discover_patterns(self, cases: list[ReasoningCase]) -> list[str]:
        """Discover emerging patterns from new cases."""
        patterns = []

        # Group by mistake type
        by_type = {}
        for c in cases:
            by_type.setdefault(c.mistake_type, []).append(c)

        for mt, mt_cases in by_type.items():
            if len(mt_cases) >= 2:
                # Check for regime concentration
                regimes = [c.regime_label for c in mt_cases if c.regime_label]
                if len(set(regimes)) <= 2 and len(regimes) >= 2:
                    patterns.append(f"Pattern '{mt}' clusters in regimes: {list(set(regimes))}")

                # Check for domain concentration
                all_domains = [d for c in mt_cases for d in c.domains]
                domain_counts = {}
                for d in all_domains:
                    domain_counts[d] = domain_counts.get(d, 0) + 1
                concentrated_domains = [d for d, count in domain_counts.items() if count >= 2]
                if concentrated_domains:
                    patterns.append(
                        f"Pattern '{mt}' is concentrated in domains: {concentrated_domains}"
                    )

        return patterns
