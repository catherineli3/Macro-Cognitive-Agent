"""Memory domain concepts — Belief tracking enums.

Sprint 8 introduces the Belief Memory System. These enums define
what a Belief IS in the Memory layer, independent of Reflection's
internal classification.

Key design:
    - BeliefStatus: Memory's own verdict, NOT a re-export of ReflectionVerdict.
      This decouples Memory from Reflection internals.
    - TransitionType: Describes how a belief changed from the previous record.
      Detected by BeliefMemoryStore, not by Reflection.
"""

from enum import Enum


class BeliefStatus(str, Enum):
    """Memory-level classification of a stored belief.

    This is Memory's own verdict — it maps FROM ReflectionVerdict
    but lives in the Memory domain so Reflection can evolve independently.

    States:
        HELD        — Belief is currently held (maps from CONFIRMED).
        IN_DOUBT    — Belief is uncertain (maps from UNCERTAIN).
        ABANDONED   — Belief has been refuted (maps from REFUTED).
    """

    HELD = "held"
    """Evidence supports this belief. The agent currently holds it as its
    working model of reality."""

    IN_DOUBT = "in_doubt"
    """Evidence is insufficient or mixed. The agent is uncertain about
    whether to maintain this belief."""

    ABANDONED = "abandoned"
    """Evidence contradicts this belief. The agent has discarded it."""


class TransitionType(str, Enum):
    """How a belief changed relative to the previous belief in the same dimension.

    Computed by BeliefMemoryStore during record() — NOT by Reflection.
    A Transition is a Memory-level concept: it describes the relationship
    between two adjacent BeliefRecords in the same dimension.

    States:
        NEW         — First belief ever recorded for this dimension.
        STABLE      — Same direction, confidence change is small (±0.10).
        REINFORCED  — Same direction, confidence increased significantly (> +0.10).
        WEAKENED    — Same direction, confidence decreased significantly (> -0.10).
        REVERSED    — Direction changed (bullish → bearish or vice versa).
    """

    NEW = "new"
    """First time this dimension has been recorded."""

    STABLE = "stable"
    """Direction unchanged, confidence within ±0.10 of prior."""

    REINFORCED = "reinforced"
    """Same direction, confidence rose > 0.10 — evidence is strengthening."""

    WEAKENED = "weakened"
    """Same direction, confidence fell > 0.10 — evidence is weakening."""

    REVERSED = "reversed"
    """Direction flipped — the agent now believes the opposite."""
