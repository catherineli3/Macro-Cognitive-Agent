# Research Principles — The Agent's Research Methodology

> **Document Type**: Methodology Definition (Not Code Documentation)
> **Version**: 1.0
> **Date**: July 2026
> **Status**: Architecture Freeze
> **Purpose**: Defines the four-level cognitive hierarchy that forms the agent's research methodology

---

## The Four-Level Hierarchy

The agent's knowledge is organized in a strict four-level hierarchy. Each level has a distinct responsibility, lifecycle, and relationship to the levels above and below it.

```
                        ┌──────────────────────────────────────┐
                        │           RESEARCH FRAMEWORK          │
                        │  "How I understand the macro world"   │
                        │                                      │
                        │  The organizing lens through which    │
                        │  all other levels are interpreted.    │
                        │  Evolves slowly — over 100+ cycles.   │
                        └────────────────┬─────────────────────┘
                                         │ composed of
                                         ▼
                        ┌──────────────────────────────────────┐
                        │           BELIEF                      │
                        │  "What I believe about specific       │
                        │   causal relationships"               │
                        │                                      │
                        │  Weighted, context-conditional,       │
                        │  versioned. Six-stage lifecycle.      │
                        └────────────────┬─────────────────────┘
                                         │ derived from
                                         ▼
                        ┌──────────────────────────────────────┐
                        │           RESEARCH PRINCIPLE          │
                        │  "What the data has taught me about   │
                        │   how markets actually work"          │
                        │                                      │
                        │  Validated patterns. Cross-regime.    │
                        │  Permanent (until retired).           │
                        └────────────────┬─────────────────────┘
                                         │ abstracted from
                                         ▼
                        ┌──────────────────────────────────────┐
                        │           RESEARCH FINDING            │
                        │  "What I observed in the last cycle"  │
                        │                                      │
                        │  Per-cycle observations. Raw output   │
                        │  of Diagnosis + Transmission Analysis.│
                        │  Most are temporary. Few become       │
                        │  Principles.                          │
                        └──────────────────────────────────────┘
```

---

## Level 1: Research Finding

### Definition

A Research Finding is a **single-cycle observation** produced by the B.5 Research Findings Engine. It is the raw output of comparing a prediction's transmission chain against actual market outcomes.

### What It Is

```
Finding: "In cycle #187, under high_vix regime,
          the credit→SPX transmission broke.
          Root cause: VIX spike suppressed risk appetite
          despite credit conditions being favorable."
```

### What It Is NOT

- NOT a permanent truth
- NOT a validated pattern
- NOT a belief modification instruction
- NOT a principle candidate (until it accumulates evidence)

### Responsibilities

| Responsibility | How Fulfilled |
|----------------|--------------|
| Record what happened | Per-cycle transmission analysis output |
| Propose potential cause | Root cause analysis from Breakpoint Diagnosis |
| Associate with context | Always tagged with regime + market conditions |
| Accumulate for pattern detection | Stored in Finding Accumulator |

### Lifecycle

```
Created ──► Accumulated ──► Pattern Detected
    │                           │
    │                           ├──► Promoted to Principle (if P1-P5 met)
    │                           │    Status: PROMOTED, immune to TTL
    │                           │
    │                           └──► Archived as context (if pattern not significant)
    │                                Status: ARCHIVED, read-only
    │
    ├──► Entered Conflict Queue
    │    TTL frozen while conflict active. Finding persists until resolution.
    │
    ├──► Cited by active Principle/Belief
    │    TTL extended +30 days per citation
    │
    └──► EXPIRED (90-day TTL elapsed)
         No promotion, no citation, no conflict.
         Auto-archived. Excluded from Finding Accumulator.
```

### Time-To-Live (TTL)

| Condition | TTL |
|-----------|-----|
| Default new finding | 90 days |
| Cited by ongoing conflict | Frozen until conflict resolved |
| Cited by active Principle | Principle's sustained_validity_cycles / 2 |
| Confidence: ESTABLISHED or ROBUST | 180 days |
| Confidence: PRELIMINARY | 45 days |
| Promoted to Principle | Permanent (as evidence record) |

**Key rule**: Findings are observations, not permanent knowledge. They expire unless they earn the right to persist through promotion, citation, or conflict participation.

### Key Properties

```python
class ResearchFinding:
    finding_id: str
    category: str                   # F1/F2/F3/F4
    headline: str
    narrative: str                  # Researcher-prose explanation
    key_numbers: dict               # reliability, latency, strength, etc.
    confidence: FindingConfidence   # PRELIMINARY | OBSERVED | ESTABLISHED | ROBUST
    source_diagnosis_id: str
    transmission_channel: str
    context_key: str                # Regime + conditions
    cycle_number: int
    evidence_count: int
    recommendation: str
```

### Relationship to Higher Levels

```
Finding → (Accumulation + P1-P5 Gate) → Principle
Finding → (Failed Gate) → Archived as context
Finding → (Single Event) → Temporary Event Layer
```

---

## Level 2: Research Principle

### Definition

A Research Principle is a **validated, cross-regime pattern** that has been abstracted from multiple consistent Research Findings. It represents durable knowledge about how macro-financial causality works.

### What It Is

```
Principle: "Transmission from credit conditions to equity markets
           (credit→SPX) breaks reliably when VIX exceeds 30.
           Validated in 3 distinct regimes (easing, tightening, neutral)
           across 48 observations. Sustained validity: 20 cycles."
```

### What It Is NOT

- NOT a single observation
- NOT a regime-specific rule
- NOT directly actionable as a prediction (that's the Belief's job)
- NOT immutable — it can be retired if evidence shifts
- NOT a causal chain — one Principle = one causal edge (see Granularity Rules)

### Granularity Rules

A Principle is the **minimum indivisible learning unit**. Every Principle must satisfy:

| Rule | Definition | Violation |
|------|-----------|-----------|
| **GR-1** | Single causal edge (exactly two nodes, one direction) | "Liquidity → Risk Asset" (causal chain) |
| **GR-2** | Independently falsifiable by a single observation in principle | "Liquidity matters" (unfalsifiable) |
| **GR-3** | At most one compound precondition (single condition domain) | "When VIX>30 OR GDP<0 OR inflation>5%" |
| **GR-4** | Operates within one transmission dimension | "Liquidity affects rates AND equities" |
| **GR-5** | If splittable into two independently true principles, MUST be split | "Fed eases → Dollar falls AND Gold rises" |

**Principle composition**: Principles form causal chains through `prerequisite_principles` and `implies_principles` relationships, not through aggregation. "Liquidity → Real Yield → Valuation → Risk Asset" is three Principles, not one.

### Competing Principles

Two Principles may make contradictory claims about the same relationship. This is legitimate. They enter `ACTIVE_COMPETITION`:

- Both remain active (strength ≥ "validated" preserved)
- All Beliefs citing either are weight-penalized (×0.5)
- Competition resolved by cumulative evidence, not forced merge
- If one wins ≥ 70% of next 30 cycles → opponent enters WEAKENING
- If neither dominates after 50 cycles → both archived as "unresolved regime-dependent"

### Responsibilities

| Responsibility | How Fulfilled |
|----------------|--------------|
| Distill durable causal knowledge | Abstracted from ≥ 5 consistent findings |
| Define applicability boundaries | Explicit regime + condition preconditions |
| Serve as evidence for Beliefs | Beliefs cite Principles as their foundation |
| Track sustained validity | Continuously monitored against new findings |
| Self-retire when obsolete | If contradicted ≥ 10 times, enters retirement review |

### Admission Criteria (from Architecture Q1)

| # | Criterion | Threshold |
|---|-----------|-----------|
| P1 | Cross-Regime Validation | ≥ 2 distinct regimes |
| P2 | Repetition Count | ≥ 5 independent observations |
| P3 | Minimum Evidence | ≥ 30 edge-level observations |
| P4 | Sustained Validity | No contradiction in last 20 cycles |
| P5 | Generality | Applies to ≥ 2 transmission channels |

### Principle Strength Levels

```
Candidate ──► Validated ──► Mature ──► Foundational
   │              │            │            │
   │              │            │            └── ≥ 100 observations,
   │              │            │                ≥ 5 regimes,
   │              │            │                0 contradictions
   │              │            │
   │              │            └── ≥ 50 observations,
   │              │                ≥ 3 regimes,
   │              │                ≤ 2 contradictions in 30 cycles
   │              │
   │              └── P1-P5 all met,
   │                  ≥ 30 observations
   │
   └── P2-P4 met, but P1 pending
       (cross-regime validation in progress)
```

### Key Properties

```python
class ResearchPrinciple:
    principle_id: str
    name: str                       # "VIX Threshold Effect on Credit-Equity Transmission"
    statement: str                  # Declarative: "When VIX > 30, credit→SPX transmission breaks"
    strength: str                   # "candidate" | "validated" | "mature" | "foundational"
    domain: str                     # Transmission channel or dimension
    preconditions: dict             # When this principle applies
    evidence: PrincipleEvidence
    source_findings: list[str]      # Finding IDs that led to this principle
    regimes_validated: list[str]    # Which regimes has it been observed in?
    contradiction_count: int
    created_from_conflict: Optional[str]

class PrincipleEvidence:
    total_observations: int
    correct_in_scope: int
    accuracy: float
    regimes_count: int
    last_validated_cycle: int
    sustained_cycles: int           # Consecutive cycles without contradiction
```

### Relationship to Other Levels

```
Finding ──► (Admission Gate) ──► Principle
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
              Belief A            Belief B           Belief C
          (cites Principle)  (cites Principle)  (cites Principle)

Principle ──► (Conflict) ──► Resolution
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
            Principle stays  Principle      Principle
                           narrowed       retired

Principle ──► (Clustering) ──► Framework
```

---

## Level 3: Belief

### Definition

A Belief is the agent's **actionable conviction** about a specific causal relationship, expressed as a weighted, context-conditional, versioned proposition. Beliefs are what the Hypothesis Generator uses to form predictions.

### What It Is

```
Belief: "Liquidity easing → NASDAQ rises"
    In context "fed_active_easing": weight=0.85, confidence=0.78
    In context "fed_passive_easing": weight=0.42, confidence=0.35
    Founded on: Principle "Liquidity→Equity under active monetary easing"
    Lifecycle stage: MATURE
    Version: 12 (evolved from v1 weight=0.60 across 80 cycles)
```

### What It Is NOT

- NOT a raw finding (that's Level 1)
- NOT a validated principle (that's Level 2)
- NOT a framework (that's Level 4)
- NOT static — evolves with lifecycle stages

### Responsibilities

| Responsibility | How Fulfilled |
|----------------|--------------|
| Encode actionable conviction | Weight + confidence per context |
| Be the Hypothesis Generator's input | Generator queries active, mature beliefs |
| Track its own reasoning history | Version history with trigger + evidence per version |
| Maintain context boundaries | Active/inactive transmission segments per context |
| Self-assess reliability | Confidence meta-parameter |
| Derive weight from principles | weight = f(underlying_principle.strength, recent_performance) |

### Six-Stage Lifecycle

```
CREATED → VALIDATED → MATURE → WEAKENING → RETIRED → ARCHIVED
   ↑                                                    │
   └──────────────────── REVIVAL ───────────────────────┘
        (only if regime matches validated conditions)
```

| Stage | Entry Condition | Exit Condition | Hypothesis Generator Uses? |
|-------|----------------|----------------|---------------------------|
| CREATED | New belief formed | ≥5 correct + ≥10 obs | Yes, low weight |
| VALIDATED | Entry threshold met | ≥20 correct + ≥65% accuracy | Yes, moderate weight |
| MATURE | Stable, high accuracy | ≥3 failures in 10 OR regime shift | Yes, full weight |
| WEAKENING | Accuracy declining | ≥10 failures OR 30 cycles without recovery | Yes, reduced weight |
| RETIRED | Failure threshold met | 50 cycles + no revival | No |
| ARCHIVED | Historical artifact | — | No |

### Key Properties

```python
class AdaptiveBelief:
    belief_id: str
    dimension: str
    transmission_channel: str
    lifecycle_stage: BeliefLifecycleStage

    # Per-context state
    contexts: dict[str, ContextProfile]

    # Foundation
    founded_on_principles: list[str]     # Principle IDs
    founded_on_findings: list[str]       # Finding IDs

    # Evolution
    current_version: int
    version_history: list[BeliefVersion]

    # Performance
    total_predictions: int
    correct_predictions: int
    streak: int                         # Consecutive correct/incorrect

    # Derived
    overall_confidence: float           # Meta-confidence across all contexts
```

### Relationship to Other Levels

```
Principle ──► (Informs) ──► Belief
                                  │
                                  ▼
                          Hypothesis Generator
                                  │
                                  ▼
                          Prediction

Belief ──► (Clustered with other beliefs) ──► Framework
Belief ──► (Lifecycle transition) ──► Retired/Archived
```

**Critical Rule**: Belief weight is **derived** from Principles, not independent. When a Principle's strength changes, all Beliefs founded on it automatically recalculate.

```
belief.weight[context] = f(
    principle.strength_score,        # 0.0-1.0
    principle.accuracy_in_context,
    belief.recent_performance,        # Streak effect
    belief.meta_confidence            # How sure are we about this weight?
)
```

---

## Level 4: Research Framework

### Definition

A Research Framework is the agent's **highest-level organizing worldview**. It is a coherent cluster of Principles and Beliefs that together define how the agent interprets the macro environment. Framework evolution is the ultimate measure of the agent's research maturity.

### What It Is

```
Framework: "Monetary-Fiscal Interaction"

    Thesis: "Asset prices in the current era are driven by the net
            interaction of fiscal supply (Treasury issuance, TGA) and
            monetary demand (Fed balance sheet, RRP), not by either alone.
            The traditional 'Fed Dominates' framework no longer adequately
            explains market behavior."

    Composed of Principles:
        - "Net Liquidity (TGA + RRP + Fed) → Risk Assets" (mature)
        - "Treasury Supply → Term Premium → Dollar" (validated)
        - "Fed Rate Path → Front-End Yields Only" (validated)
        - "Credit→Equity Breaks Above VIX 30" (foundational)

    Accuracy: 0.71 over last 50 cycles
    Status: ACTIVE
    Evolved from: "Fed Dominates" (retired, Cycle 142)
```

### What It Is NOT

- NOT a prediction model
- NOT a rule set
- NOT a score or ranking
- NOT a fixed template — frameworks evolve, split, and retire
- NOT a black-box label — every Framework MUST be explainable

### Framework Explainability (Mandatory)

A Framework that cannot explain itself is architecturally invalid. Every Framework must produce:

| Field | Content |
|-------|---------|
| `name` | Human-readable identifier (e.g., "Fiscal-Monetary Interaction") |
| `thesis` | ≥ 100 character paragraph explaining the causal worldview |
| `confidence` | 0.0-1.0, computed from principle consensus + accuracy |
| `supporting_principles_count` | How many principles back this framework |
| `contradicting_principles_count` | How many principles challenge it |
| `historical_win_rate` | Regime classification accuracy over lookback |
| `activated_since` | When the framework became active |
| `parent_framework` | Framework lineage (which framework did this evolve from) |
| `competing_frameworks` | Other active frameworks with overlapping domains |

Confidence is computed, not labeled:
```
confidence = 0.4 × mean(supporting_principle_strength)
           + 0.2 × (1 - mean(contradicting_principle_strength))
           + 0.3 × historical_win_rate
           + 0.1 × supporting_ratio
```

### Framework Set: Multi-Framework Coexistence

The agent does NOT have one framework. It has a **Framework Set** — multiple active frameworks, each interpreting the world through a different lens:

```python
class FrameworkSet:
    active_frameworks: list[str]     # Ordered by confidence, max 5
    framework_weights: dict          # Derived weights, sum = 1.0
    domain_assignment: dict          # Each framework may specialize
    synthesis_strategy: str          # "weighted_average" | "domain_partition" | "best_framework"
    retired_frameworks: list[str]    # Archived for historical reference
```

**Why multi-framework matters**:
- A single framework failure ≠ agent failure
- The agent can hold conflicting views simultaneously (like a real researcher)
- Regime shifts may deactivate one framework while others survive
- Internal disagreement IS insight: "Framework A is bullish, B is cautious → neutral-positive"

### Responsibilities

| Responsibility | How Fulfilled |
|----------------|--------------|
| Define the agent's interpretive lens | Thesis statement + principle cluster |
| Organize knowledge hierarchically | Groups related principles under a coherent theme |
| Detect worldview shifts | Framework upgrade/retirement triggers |
| Explain WHY the agent thinks what it thinks | Framework thesis + parent-child lineage |
| Enable V4 interaction | User asks: "How do you see the macro world?" → Framework answer |

### Framework Formation

```
Step 1: Principle Clustering
    When ≥ 5 principles consistently co-activate under similar conditions
    → Candidate framework detected

Step 2: Thesis Formation
    The agent extracts the common causal theme:
    What do these principles collectively assert about how markets work?

Step 3: Validation
    Candidate framework tested: ≥ 70% regime classification accuracy over 30 cycles
    → Promoted to ACTIVE

Step 4: Active Framework lifecycle
    Accuracy monitored
    Principles added/removed as they mature/retire
    May split if internal tension detected
```

### Framework Lifecycle

```
Candidate ──► Active ──► Under Review ──► Retired
    │            │             │              │
    │            │             │              └── Replaced by
    │            │             │                  successor framework
    │            │             │
    │            │             └── Accuracy declining
    │            │                 or contradictory principles detected
    │            │
    │            └── ≥ 70% accuracy over 30 cycles
    │
    └── Principle cluster ≥ 5, thesis formed
```

### Framework Evolution Example

```
Cycle 0-50:
    Framework: "Fed Dominates" (ACTIVE)
        Thesis: "Monetary policy is the primary driver of all assets"
        Top Principles: Liquidity→Risk, Rate→Dollar, Fed→Volatility
        Accuracy: 0.78

Cycle 51-120:
    Framework: "Fed Dominates" (UNDER REVIEW)
        Accuracy declining: 0.52
        New findings consistently contradict:
            "Liquidity easing → NASDAQ" fails in fiscal-dominant context
            "Rate path → Dollar" fails when term premium dominates
        → Framework tension detected

Cycle 121:
    Framework: "Fed Dominates" → RETIRED
    Framework: "Fiscal-Monetary Interaction" → ACTIVE (CANDIDATE → ACTIVE)
        Thesis: "Net liquidity = monetary + fiscal, not either alone"
        Accuracy over next 30: 0.74

Cycle 200+:
    Framework: "Fiscal-Monetary Interaction" (MATURE)
        Accuracy: 0.71, stable
        Lineage traceable: "Evolved from Fed Dominates (retired cycle 121)"
```

### Key Properties

```python
class ResearchFramework:
    framework_id: str
    name: str
    thesis: str                         # 1-3 paragraph explanation
    status: str                         # "candidate" | "active" | "under_review" | "retired"
    principles: list[str]               # Principle IDs
    principle_weights: dict[str, float] # Relative importance
    accuracy_trajectory: list[float]
    parent_framework: Optional[str]     # Framework lineage
    created_at_cycle: int
    created_from: str                   # "principle_cluster" | "framework_conflict"
    retired_at_cycle: Optional[int]
    retirement_reason: Optional[str]
```

---

## Cross-Level Dynamics

### How Information Flows Upward

```
Finding
    │
    │ (Accumulation → Pattern detection → Admission Gate)
    ▼
Principle
    │
    │ (Informs weight calculation → Cited as foundation)
    ▼
Belief
    │
    │ (Clustered with related beliefs → Common thesis)
    ▼
Framework
```

### How Influence Flows Downward

```
Framework Set
    │
    │ (Multiple frameworks weighted by domain + confidence)
    │ (Framework A: monetary domain, weight 0.5)
    │ (Framework B: fiscal domain, weight 0.3)
    │ (Framework C: external domain, weight 0.2)
    ▼
Principle
    │
    │ (Principles may be competing — both active, beliefs penalized)
    │ (Competing: weight × 0.5 until resolved by evidence)
    │ (Principle strength determines belief base weight)
    ▼
Belief
    │
    │ (Belief weight determines hypothesis confidence)
    │ (Beliefs may cite competing principles → double penalty applied)
    ▼
Hypothesis → Prediction
```

### The Key Invariants

```
Invariant 1: Belief.weight ≠ independent parameter
    Belief.weight = f(Principle.strength) + f(recent_performance)
    When a Principle is retired → all Beliefs founded on it are
    automatically re-evaluated.

Invariant 2: Principle is the minimum indivisible learning unit
    One Principle = one causal edge. Independently falsifiable.
    No aggregation. Chains via composition, not inside one Principle.

Invariant 3: Competing Principles coexist
    Two contradictory principles remain active simultaneously.
    Resolved by evidence, not forced merge.
    Weight penalty applied to beliefs until competition resolved.

Invariant 4: Framework is a Set, not a Singleton
    Multiple frameworks operate concurrently.
    Domain-weighted synthesis determines hypothesis generation.

Invariant 5: Finding has finite TTL
    Default 90 days. Expiry → auto-archive.
    Only promotion, conflict, or citation pauses the clock.

Invariant 6: Four Layers Are Independent
    Research Findings are observations.
    Research Principles are reusable knowledge.
    Beliefs are decision weights.
    Frameworks are organizing worldviews.
    The system must never collapse these four layers into one.
    No cross-layer direct modification.

This is the "researcher's knowledge cascade" —
discovering that a causal relationship is broken changes ALL
judgments that depended on it.

---

## The Agent's Research Methodology — Summary

```
The Agent's worldview at any point in time:

    I believe [Framework.thesis]
    because these principles are well-established [Principle₁, Principle₂, ...]
    which manifest in these specific actionable beliefs [Belief₁, Belief₂, ...]
    which were derived from thousands of cycle observations [Finding₁..N]

The Agent's evolution over time:

    I used to believe [Retired Framework]
    but my findings [Key Finding₁, Key Finding₂]
    led me to form new principles [New Principle₁]
    which shifted my worldview to [Current Framework]
    my old framework is archived for when conditions change.
```

This is what makes the agent a **researcher**, not a model.

---

> **Document Status**: ARCHITECTURE FREEZE
> **Related**: `RESEARCH_EVOLUTION_ARCHITECTURE.md` (technical architecture), `RESEARCH_EVOLUTION_REVIEW.md` (review)
> **Next**: Architecture review → Milestone C implementation
