"""Planning domain concepts — Task type classification.

Sprint 3 defines generic Agent capability types. These are NOT
macro-specific — they describe what kind of work a task represents,
regardless of domain.

The six capability types form a complete Agent action taxonomy:
    RETRIEVE → fetch data from external sources
    PROCESS  → transform, normalize, or clean data
    ANALYZE  → examine data for patterns, signals, insights
    GENERATE → produce output (hypothesis, report, plan)
    VALIDATE → verify correctness, consistency, or quality
    DECIDE   → make a choice among alternatives (future)
"""

from enum import Enum


class TaskType(str, Enum):
    """Generic Agent capability types — domain-agnostic task classification.

    Sprint 3 uses these to categorize abstract tasks. The Executor
    (future Sprint) maps each type to concrete tool invocations.
    """

    RETRIEVE = "retrieve"  # Fetch data from external/internal sources
    PROCESS = "process"  # Transform, normalize, filter data
    ANALYZE = "analyze"  # Examine data for patterns, signals, anomalies
    GENERATE = "generate"  # Create new content (hypothesis, report, plan)
    VALIDATE = "validate"  # Verify correctness, consistency, quality
    DECIDE = "decide"  # Choose among alternatives (future capability)
