"""Evidence Weight — weighted evidence scoring for Beta-Bayesian belief updating.

Computes an evidence weight (0–1) that determines how much a piece of evidence
should move a ResearchBelief's Beta distribution.

Weight = source_base × min(confidence, 1.0) × recency_discount × corroboration_bonus
          clamped to [0.05, 1.0]

Evidence Sources (base_weights reflect epistemic reliability):
    MACRO_DATA      = 0.85   — Economic releases, policy data (high reliability)
    MARKET_DATA     = 0.90   — Price/volume/spreads (highest reliability)
    NEWS            = 0.40   — Headlines, sentiment (noisy)
    COMPANY         = 0.55   — Earnings, guidance (medium reliability)
    HISTORY         = 0.60   — Historical analogs, backtest results
    INFERENCE       = 0.50   — Model-derived conclusions (unverified)
"""

from __future__ import annotations

from src.research.beliefs.schemas import EvidenceSource

# ── Base Weights by Evidence Source ──────────────────────────────────────────
# These reflect the inherent epistemic reliability of each source type.
# MARKET_DATA > MACRO_DATA > HISTORY > COMPANY > INFERENCE > NEWS

EVIDENCE_BASE_WEIGHTS: dict[str, float] = {
    "macro_data": 0.85,
    "market_data": 0.90,
    "news": 0.40,
    "company": 0.55,
    "history": 0.60,
    "inference": 0.50,
}


# ── Recency Discount Parameters ──────────────────────────────────────────────
# Evidence older than HALF_LIFE_DAYS loses half its weight.
# Evidence older than MAX_AGE_DAYS is clamped to floor weight.

_HALF_LIFE_DAYS: float = 30.0
_MAX_AGE_DAYS: float = 365.0
_FLOOR_WEIGHT: float = 0.10


def compute_evidence_weight(
    source: EvidenceSource,
    confidence: float = 0.7,
    recency_days: float = 0.0,
    corroboration_count: int = 0,
) -> float:
    """Compute evidence weight for Beta-Bayesian belief updating.

    Args:
        source: Evidence source type (from 6-source classification).
        confidence: Source-specific confidence 0–1.
        recency_days: Days since evidence was observed (0 = fresh).
        corroboration_count: Total number of existing evidence items on this
                             belief. More evidence → diminishing returns bonus.

    Returns:
        Weight float in [0.05, 1.0], used as α-increment or β-increment.

    Weight Formula:
        base = EVIDENCE_BASE_WEIGHTS[source]
        recency = 2^(-recency_days / HALF_LIFE)  clamped to [FLOOR, 1.0]
        corroboration = min(1.0 + 0.02 * corroboration_count, 1.15)
        weight = base × min(confidence, 1.0) × recency × corroboration
        return clamp(weight, 0.05, 1.0)
    """
    # Base source weight
    source_key = source.value if isinstance(source, EvidenceSource) else str(source)
    base = EVIDENCE_BASE_WEIGHTS.get(source_key, 0.5)

    # Recency discount: exponential decay with half-life
    if recency_days <= 0:
        recency_discount = 1.0
    else:
        recency_discount = 2.0 ** (-recency_days / _HALF_LIFE_DAYS)
        recency_discount = max(_FLOOR_WEIGHT, min(1.0, recency_discount))

    # Corroboration bonus: more supporting evidence = slightly higher weight
    # Diminishing returns: capped at 1.15x
    corroboration_bonus = min(1.0 + 0.02 * corroboration_count, 1.15)

    # Clamp confidence
    conf = max(0.0, min(1.0, confidence))

    # Compute final weight
    weight = base * conf * recency_discount * corroboration_bonus

    return round(max(0.05, min(1.0, weight)), 4)


def classify_evidence(
    description_or_type: str,
) -> EvidenceSource:
    """Classify a raw evidence description into its EvidenceSource type.

    Uses keyword-based heuristics to map free-text descriptions or type
    identifiers to the 6-source classification system.

    Args:
        description_or_type: A text description or source type string.

    Returns:
        The best-matching EvidenceSource enum value (defaults to INFERENCE).

    Examples:
        >>> classify_evidence("market_data")
        EvidenceSource.MARKET_DATA
        >>> classify_evidence("DXY broke above 106 resistance")
        EvidenceSource.MARKET_DATA
        >>> classify_evidence("Fed raised rates by 25bp")
        EvidenceSource.MACRO_DATA
        >>> classify_evidence("Goldman Sachs upgrades XYZ to Buy")
        EvidenceSource.INFERENCE
    """
    text = description_or_type.lower().strip()

    # Direct type matching
    type_map = {
        "macro_data": EvidenceSource.MACRO_DATA,
        "market_data": EvidenceSource.MARKET_DATA,
        "market data": EvidenceSource.MARKET_DATA,
        "news": EvidenceSource.NEWS,
        "company": EvidenceSource.COMPANY,
        "history": EvidenceSource.HISTORY,
        "inference": EvidenceSource.INFERENCE,
    }

    if text in type_map:
        return type_map[text]

    # Keyword-based classification — check most-specific categories first.
    # Macro keywords are checked before market because terms like "fed", "cpi"
    # are more specific indicators of macro data than generic "rate" or "yield".

    macro_keywords = [
        "fed",
        "ecb",
        "pce",
        "cpi",
        "ppi",
        "gdp",
        "nfp",
        "nonfarm",
        "unemployment",
        "ism",
        "pmi",
        "inflation",
        "policy",
        "rate hike",
        "rate cut",
        "fomc",
        "central bank",
        "balance sheet",
        "fiscal",
        "deficit",
        "trade",
        "interest rate",
        "basis point",
        "bps",
        "tightening",
        "qe",
        "quantitative",
    ]

    company_keywords = [
        "earnings",
        "revenue",
        "guidance",
        "ceo",
        "quarterly",
        "annual report",
        "eps",
        "beat",
        "miss",
    ]

    news_keywords = [
        "headline",
        "breaking",
        "reported",
        "according to",
        "sources say",
        "exclusive",
        "interview",
    ]

    market_keywords = [
        "price",
        "volume",
        "spread",
        "yield",
        "dxy",
        "s&p",
        "spx",
        "nasdaq",
        "vix",
        "treasury",
        "bond",
        "equity",
        "index",
        "resistance",
        "support",
        "breakout",
        "broke above",
        "broke below",
        "rallied",
        "sold off",
        "spike",
        "crash",
        "surged",
    ]

    history_keywords = [
        "historically",
        "backtest",
        "analog",
        "precedent",
        "prior cycle",
        "past",
        "previously",
        "historical",
    ]

    for kw in macro_keywords:
        if kw in text:
            return EvidenceSource.MACRO_DATA

    for kw in company_keywords:
        if kw in text:
            return EvidenceSource.COMPANY

    for kw in news_keywords:
        if kw in text:
            return EvidenceSource.NEWS

    for kw in market_keywords:
        if kw in text:
            return EvidenceSource.MARKET_DATA

    for kw in history_keywords:
        if kw in text:
            return EvidenceSource.HISTORY

    # Default: inference (model/conclusion-derived)
    return EvidenceSource.INFERENCE


def compute_evidence_batch(
    sources: list[EvidenceSource],
    confidences: list[float],
    recency_days_list: list[float],
    corroboration_counts: list[int],
) -> list[float]:
    """Compute weights for a batch of evidence items.

    Args:
        sources: Evidence source types.
        confidences: Source-specific confidences.
        recency_days_list: Days since each evidence was observed.
        corroboration_counts: Corroboration counts for each item.

    Returns:
        List of weights in [0.05, 1.0].
    """
    return [
        compute_evidence_weight(s, c, r, corr)
        for s, c, r, corr in zip(
            sources,
            confidences,
            recency_days_list,
            corroboration_counts,
        )
    ]


def get_source_reliability(source: EvidenceSource) -> dict:
    """Get the reliability profile for an evidence source.

    Returns:
        Dict with base_weight, reliability_tier, and description.
    """
    source_key = source.value
    base = EVIDENCE_BASE_WEIGHTS.get(source_key, 0.5)

    if base >= 0.85:
        tier = "A — Highly Reliable"
    elif base >= 0.60:
        tier = "B — Moderately Reliable"
    elif base >= 0.50:
        tier = "C — Somewhat Reliable"
    else:
        tier = "D — Low Reliability"

    descriptions = {
        "macro_data": "Official economic releases and policy announcements",
        "market_data": "Real-time price, volume, and spread data",
        "news": "News headlines and sentiment signals",
        "company": "Corporate earnings, guidance, and filings",
        "history": "Historical analogs and backtest results",
        "inference": "Model-derived conclusions and internal reasoning",
    }

    return {
        "source": source_key,
        "base_weight": base,
        "reliability_tier": tier,
        "description": descriptions.get(source_key, "Unknown source type"),
    }
