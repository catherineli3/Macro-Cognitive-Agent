"""Hypothesis domain concepts — status classification.

Sprint 6 defines the lifecycle states of a Hypothesis.
A Hypothesis moves through these states as it is reasoned, reflected upon,
and validated:

    ACTIVE    → currently under consideration (freshly generated)
    CONFIRMED → supported by strong, consistent evidence
    REFUTED   → contradicted by evidence or broken assumptions
    STALE     → expired; data has moved, needs regeneration
"""

from enum import Enum


class HypothesisStatus(str, Enum):
    """Lifecycle status of a macro research hypothesis.

    ACTIVE:     Freshly generated, awaiting Reflection (Sprint 7).
                All hypotheses produced by HypothesisEngine start here.
    CONFIRMED:  Reflection found no contradictions; evidence is consistent.
                Set by Reflection Engine (Sprint 7).
    REFUTED:    Contradicting evidence outweighs supporting evidence,
                or a core assumption is broken. Set by Reflection Engine.
    STALE:      Underlying data is outdated. Triggered by Memory (Sprint 8)
                or a scheduler-based freshness check.
    """

    ACTIVE = "active"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    STALE = "stale"
