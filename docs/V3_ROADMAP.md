# V3 Roadmap — Macro Research Intelligence

> **Document Type**: Strategic Roadmap  
> **Version**: 1.0  
> **Date**: July 2026  
> **Status**: Draft — Pending Architecture Review  
> **Target Audience**: System architects, technical leads, product owners

---

## Executive Summary

V2 has delivered a complete **Macro Cognitive Agent** with a 10-engine closed loop (maturity: 9.3/10). However, it remains a **Rule-based Cognitive Agent**:

```
Data → Rule → Template → Report
```

V3's goal is to transform it into a **Macro Research Intelligence** — an Agent that can think, reason about what to study, build knowledge graphs, challenge its own reasoning, and recall analogous research cases.

This roadmap defines **5 new capabilities** (research intelligence) and **2 engineering upgrades** (platform readiness), organized by priority and dependency.

---

## Strategic Shift: From Module Stacking to Cognitive Depth

| V1-V2 Approach | V3 Approach |
|----------------|-------------|
| Add more modules | Add thinking capabilities |
| Fixed DAG pipeline | Dynamic research planning |
| Flat evidence lists | Structured knowledge graph |
| Simple belief review | Critical research evaluation |
| Belief memory | Long-term case memory |
| Pre-configured data sources | Dynamic tool selection |

---

## The 5 Capabilities (Research Intelligence)

### Priority Matrix

```
Capability          Priority   Dependency         Effort    Impact
──────────────────────────────────────────────────────────
1. Research Planner   P0        None               High      ★★★★★
2. Tool Reasoning     P0        Research Planner   High      ★★★★★
3. Evidence Graph     P1        None               Medium    ★★★★
4. Research Critic    P1        Evidence Graph     Medium    ★★★★
5. Long-Term Memory   P2        1, 2, 3, 4         High      ★★★★★
```

---

## Capability 1: Research Planner (P0 — Foundational)

### Current State
```
User Goal → RuleBasedPlanner → Fixed DAG
```

### Target State
```
User Goal
    │
    ▼
Research Planner
    │
    ├── What should I study today?
    ├── What indicators are relevant?
    ├── What hypotheses should I test?
    └── What's the research plan?
    │
    ▼
Dynamic Research Plan (not fixed DAG)
```

### Behavior Example

**Input**: "Why did gold rally today?"

**Current (V2)**: Runs fixed macro_environment DAG — collects DXY, US10Y, VIX, etc., generates standard signal/hypothesis/reflection pipeline regardless of the question.

**Target (V3)**: Planner determines the relevant research path:

```
Research Plan: "Gold Rally Analysis"
├── Step 1: Collect Gold (XAU/USD) price + volume
├── Step 2: Collect DXY (inverse correlation check)
├── Step 3: Collect Real Yields (TIPS)
├── Step 4: Collect Treasury Auction results (supply shock?)
├── Step 5: Collect Fed Speakers today (policy signal?)
├── Step 6: Collect Geopolitical News (safe haven?)
├── Step 7: Generate Hypotheses for each potential driver
├── Step 8: Cross-validate with Evidence Graph
├── Step 9: Reflection + Critic review
└── Step 10: Report with causal narrative
```

### Design Considerations

| Aspect | Approach |
|--------|----------|
| **Planning Strategy** | Decompose goal → identify relevant domains → select indicators → generate plan |
| **LLM Role** | Optional: LLM can suggest exploration paths; rules validate and constrain |
| **Plan Validation** | Plans must pass domain-relevance checks (no suggesting "Apple stock" for "gold analysis") |
| **Existing DAG** | V2's RuleBasedPlanner becomes a fallback/default for generic "macro environment" goals |
| **Memory Integration** | Planner should consult Long-Term Memory for similar past research questions |

### Key Deliverables

- `src/planning/research_planner.py` — Goal → ResearchPlan (dynamic)
- `ResearchPlan` schema — Task graph with rationale per step
- `ResearchPlannerInterface` — ABC for future LLM/RL planners
- Integration with Tool Reasoning for step execution

---

## Capability 2: Tool Reasoning (P0 — Enables Planner)

### Current State
```
Pipeline: fixed collect → normalize flow (always Yahoo)
```

### Target State
```
Question: "Why did gold rally?"
    │
    ▼
Need data? → Yes → Which source?
    │
    ├── FRED for real yields?
    ├── SEC for treasury auction?
    ├── News API for Fed speeches?
    ├── Twitter for market sentiment?
    └── Bloomberg for professional flow data?
    │
    ▼
Execute tools → Collect → Canonicalize → Continue reasoning
```

### Design Considerations

| Aspect | Approach |
|--------|----------|
| **Tool Discovery** | ToolRegistry already exists; extend with metadata (data domains, freshness, cost) |
| **Selection Logic** | Planner maps question domains → required data types → matching tools |
| **Canonical Layer** | All tools already emit `MacroDataSchema` — this is the key enabler |
| **Fallback Chain** | If Bloomberg API fails → try Yahoo → try cached data → warn user |
| **Cost Awareness** | Premium tools (Bloomberg) vs free tools (FRED, Yahoo); plan accordingly |

### Key Deliverables

- Extended `ToolRegistry` with metadata: `data_domains`, `cost_tier`, `freshness`
- `ToolReasoner` class: Question → Required Data Types → Tool Selection
- Multi-source data aggregation (merge FRED + Yahoo + News into unified signal)
- Fallback chain logic

---

## Capability 3: Evidence Graph (P1 — Structural Upgrade)

### Current State
```python
# Evidence is a flat list
hypothesis.evidence = [
    Evidence(source="DXY", direction="bullish", strength=0.8),
    Evidence(source="US10Y", direction="bullish", strength=0.7),
]
```

### Target State
```
Evidence Graph
    │
    ├── Node: DXY↑ (value: 105.2, timestamp: ..., source: Yahoo)
    │   ├── supports: Liquidity Tightening (weight: 0.8)
    │   └── conflicts with: Risk-On sentiment
    │
    ├── Node: US10Y↑ (value: 4.85%, timestamp: ..., source: FRED)
    │   ├── supports: Liquidity Tightening (weight: 0.9)
    │   └── supports: Inflation Expectations (weight: 0.6)
    │
    └── Edge: DXY↑ ←correlates_with→ US10Y↑ (ρ=0.72, window=30d)
```

### Graph Properties

| Property | Value |
|----------|-------|
| **Nodes** | Evidence items (signals, data points, external events) |
| **Edges** | Relationships: supports, contradicts, correlates, causes, precedes |
| **Weights** | Confidence/strength of relationship |
| **Temporality** | All nodes and edges are timestamped |
| **Provenance** | Every node has a source (tool + timestamp) |

### Design Considerations

| Aspect | Approach |
|--------|----------|
| **Storage** | NetworkX in-memory for active session; SQLite/Neo4j for persistence |
| **Query Patterns** | "What evidence supports X?" "What contradicts Y?" "What correlates with Z?" |
| **Graph Construction** | HypothesisEngine constructs graph during reasoning (replaces flat evidence lists) |
| **Graph Pruning** | Stale evidence decays; contradictory edges flagged for Critic review |
| **Narrative Integration** | Graph visualization data embedded in MacroNarrative metadata |

### Key Deliverables

- `src/evidence_graph/` module
- `EvidenceNode`, `EvidenceEdge`, `EvidenceGraph` schemas
- Graph construction during HypothesisEngine.reason()
- Graph query API for Reflection + Critic + Narrative

---

## Capability 4: Research Critic (P1 — Quality Upgrade)

### Current State
```
Reflection: 3-question belief review
  → Is evidence sufficient?
  → Is evidence consistent?
  → Should we still believe?
```

### Target State
```
Research Critic (in addition to belief review):
  → What alternative explanations have we not considered?
  → Are we suffering from survivorship bias?
  → Are there counter-examples in historical data?
  → Does our evidence graph have structural gaps?
  → Would a different analytical framework yield different conclusions?
```

### Critic vs Reflection

| Aspect | Reflection (v2.0) | Critic (v3.0) |
|--------|-------------------|---------------|
| **Question** | "Should we still believe?" | "What are we missing?" |
| **Scope** | Reviews current evidence | Searches for missing evidence |
| **Posture** | Evaluative | Investigative |
| **Output** | CONFIRMED / REFUTED / UNCERTAIN | Missing explanations, biases, blind spots |
| **Data** | Hypothesis + evidence only | Evidence graph + historical cases + external knowledge |

### Behavior Example

**Hypothesis**: "Gold rallied because USD weakened."

**Critic**:
1. Checks historical cases: "In Case #47 (March 2024), gold also rallied while USD *strengthened*. The USD-weakness explanation is insufficient."
2. Identifies missing dimension: "You haven't analyzed real yields. TIPS data shows real yields dropped 15bp today — that's a stronger gold driver than USD."
3. Flags bias: "3 of your last 4 gold analyses used USD-weakness as the primary explanation. Consider alternative frameworks."

### Design Considerations

| Aspect | Approach |
|--------|----------|
| **LLM Role** | LLM is highly suitable for open-ended critique (more than for deterministic signal generation) |
| **Guardrails** | Critic suggests, doesn't decide. Final hypothesis weight is still determined by the Reflection Engine |
| **Historical Checks** | Critic queries Long-Term Memory for similar past cases with different outcomes |
| **Framework Diversity** | Critic maintains a catalog of analytical frameworks and rotates through them |

### Key Deliverables

- `src/critic/research_critic.py` — ResearchCritic (new, alongside ReflectionEngine)
- Integration with Evidence Graph for gap detection
- Integration with Long-Term Memory for historical case comparison
- CriticReport schema: missing_explanations, biases_identified, framework_suggestions

---

## Capability 5: Long-Term Memory (P2 — Enables All Others)

### Current State
```python
# Memory stores beliefs, not cases
BeliefRecord(dimension="liquidity", direction="bullish", confidence=0.8)
```

### Target State
```python
# Memory stores research cases with full context
ResearchCase(
    case_id="148",
    question="Why did gold rally on July 15?",
    context={
        "event": "Treasury auction tailed 3bp",
        "market_state": "DXY 104.2, US10Y 4.35%, VIX 18",
    },
    hypotheses_generated=["Liquidity tightening", "Safe haven demand"],
    outcome="Gold +2.1%, DXY -0.3%, Yields -5bp",
    lessons=["Auction tails drive gold more than USD moves in current regime"],
    tags=["gold", "treasury_auction", "safe_haven", "yields"],
)

# Later: new Treasury auction happens
similarity = memory.find_similar(query="Treasury auction tail", top_k=3)
# Returns: Case #148 (similarity 89%), Case #312 (similarity 74%), ...
```

### Memory Architecture

```
Long-Term Memory
    │
    ├── Research Cases         ← Structured past analyses
    │   ├── Case embedding     ← for semantic similarity search
    │   ├── Case metadata      ← tags, dates, outcomes
    │   └── Case lessons       ← extracted patterns
    │
    ├── Belief History         ← v2.0 BeliefMemoryStore (keep)
    │
    └── Causal Patterns        ← Learned correlations
        ├── "Treasury auction → Gold" (confidence 0.85)
        ├── "Fed hawkish → DXY" (confidence 0.92)
        └── "VIX spike → HYG selloff" (confidence 0.78)
```

### Design Considerations

| Aspect | Approach |
|--------|----------|
| **Storage** | SQLite for structured data; optional vector DB (ChromaDB/Qdrant) for embeddings |
| **Similarity** | Tag-based + optional embedding-based (LLM embedding model) |
| **Case Creation** | Automatic: every pipeline run produces a ResearchCase |
| **Case Retrieval** | Query by tags, time range, dimension, or natural language (embedding search) |
| **Lesson Extraction** | PatternMiner (v2.0) extended to extract cross-case patterns |
| **Memory Decay** | Older cases have lower retrieval weight (configurable half-life) |

### Key Deliverables

- `src/memory/long_term.py` — LongTermMemoryStore
- `ResearchCase` schema
- `CaseIndex` with tag-based + embedding-based search
- Automatic case creation in pipeline post-execution
- Integration with Planner (similar case lookup), Critic (historical checks), Narrative (case references)

---

## Engineering Upgrades (Cross-Cutting)

### E1: Scheduler + State Manager

| Component | Current | Target |
|-----------|---------|--------|
| **Scheduler** | Manual CLI/API trigger only | Scheduled daily/weekly research cycles |
| **State Manager** | Simple ExecutionContext | LangGraph state machine with checkpointing |

### E2: Observability & Monitoring

| Component | Current | Target |
|-----------|---------|--------|
| **Logging** | Structured logging via logger | + Metrics (Prometheus), traces (OpenTelemetry) |
| **Alerting** | None | Pipeline failure alerts, accuracy degradation alerts |
| **Dashboard** | None | Web dashboard: belief state, accuracy trends, active themes |

---

## V3 Delivery Phases

```
Phase 1: Foundation (Capabilities 1 + 2)
    Research Planner + Tool Reasoning
    → Agent can now decide WHAT to study and HOW to get data
    Duration: ~4-6 weeks

Phase 2: Structure (Capability 3)
    Evidence Graph
    → Evidence becomes graph-structured, enabling richer reasoning
    Duration: ~3-4 weeks

Phase 3: Quality (Capability 4)
    Research Critic
    → Agent challenges its own reasoning, searches for blind spots
    Duration: ~3-4 weeks

Phase 4: Memory (Capability 5)
    Long-Term Memory
    → Agent recalls past research, builds case library, learns patterns
    Duration: ~4-6 weeks

Phase 5: Platform (Engineering E1 + E2)
    Scheduler + State Manager + Observability
    → Production-grade reliability
    Duration: ~3-4 weeks
```

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Planner over-generates irrelevant steps | Medium | Domain guardrails; human-in-the-loop for plan review |
| LLM dependency for Critic reduces determinism | Medium | Critic output is advisory only; Reflection is the final arbiter |
| Evidence Graph complexity explodes | Low | Pruning by staleness + relevance; configurable max graph size |
| Long-Term Memory storage grows unbounded | Low | Decay + archiving; case compression for old entries |
| V2 → V3 migration breaks existing pipeline | Low | Graceful degradation pattern already proven in v2.0 |
| Performance: dynamic planning slower than fixed DAG | Medium | Cache common plans; async tool execution |

---

## Success Criteria for V3

1. **Research Planner**: Agent can decompose a natural language question into a relevant, executable research plan without human guidance
2. **Tool Reasoning**: Agent selects appropriate data sources based on the question, not a pre-configured list
3. **Evidence Graph**: Evidence relationships are graph-structured and queryable, replacing flat lists
4. **Research Critic**: Critic identifies at least one missing explanation or bias in >50% of research runs
5. **Long-Term Memory**: Agent retrieves relevant past cases and lessons for >80% of research questions
6. **No Regression**: All 148 v2.0 tests continue to pass

---

> **Document Status**: Draft v1.0 — Strategic Roadmap  
> **Related**: `ARCHITECTURE_WHITEPAPER.md` (V2 seal), `ddr/ARCHITECTURE_DECISIONS.md` (decision history)  
> **Next Step**: Architecture review → detailed technical specifications for Phase 1
