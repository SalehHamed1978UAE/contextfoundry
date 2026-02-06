# Research LLM Response Analysis & Implementation Roadmap

## Executive Summary

The deep reasoning LLM provided a **comprehensive, research-backed solution** with concrete implementations. The response validates our diagnosis but provides significantly more sophisticated approaches than our original plan.

**Key Innovation:** Query-time conflict resolution with functional dependency detection, NOT graph cleaning.

**Projected Impact:** 74% → 88-93% in 4 weeks (first week alone: 74% → 81%)

---

## Novel Insights We Hadn't Considered

### 1. **Functional Dependency Detection via Cardinality Registry**

**What we had:** Simple evidence counting (evidence_count * 0.4 + confidence * 0.3...)

**What LLM suggests:** CRDL framework (Peng et al., MDPI 2024) - classify relations by cardinality (1-to-1, 1-to-N, N-to-N) to enable automatic conflict detection with 56.4% improvement in recall.

**Why it's better:**
- "President of Digital Solutions" is 1-to-1 → automatic conflict detection when 2 people claim it
- No manual tuning of weights needed
- Mathematically grounded in database functional dependencies

**Implementation:**
```python
RELATION_CARDINALITY = {
    "PRESIDENT_OF": "1-to-1",  # One president per org at a time
    "HAS_ROLE": "N-to-1",       # Person has one role per org
    "HAS_ENERGY_DENSITY": "1-to-1",  # One target per product+period
    "HAS_CUSTOMER": "1-to-N",   # Org can have many customers
}
```

### 2. **SOURCE_TRUST Hierarchy (Document Authority)**

**What we had:** All documents treated equally

**What LLM suggests:** Explicit trust weights by document type:

```python
SOURCE_TRUST = {
    "annual_report": 0.95,
    "strategic_plan": 0.90,
    "organizational_chart": 0.95,
    "meeting_notes": 0.60,
    "extraction_run": 0.50,  # Generic re-extraction gets lowest trust
}
```

**Why it's critical:** Solves the Kevin Chang (email) vs Robert Kim (org chart) problem! Org chart automatically wins due to source_trust = 0.95 vs 0.60.

### 3. **SkewRoute - Graph Reliability Detection via Entropy**

**What we had:** No mechanism to detect when graph is unreliable

**What LLM suggests:** Normalized entropy of score distribution (Wang et al., May 2025):

```python
def assess_graph_reliability(graph_results):
    scores = [r.score for r in graph_results]
    entropy = -sum(p * log(p) for p in probs) / log(len(probs))

    if entropy > 0.7 or conflicts_exist:
        return "UNRELIABLE"  # Fall back to documents
    elif entropy > 0.5:
        return "UNCERTAIN"   # Run hybrid (graph + docs)
    else:
        return "RELIABLE"    # Trust graph
```

**Why it's brilliant:** Automatic detection of noisy KG regions without manual configuration. High entropy = diffuse scores = unreliable graph.

### 4. **Reified Metric Observation Pattern**

**What we had:** Metrics as edge properties (HAS_REVENUE edge with value in properties)

**What LLM suggests:** Metrics as FIRST-CLASS NODES (FinKario 2025, Bloomberg KG pattern):

```python
@dataclass
class MetricObservation:
    metric_type: str  # "revenue", "employee_count"
    value: float
    unit: str  # "USD", "Wh/kg", "count"
    observation_type: str  # "actual" | "target" | "forecast"
    period_label: str  # "FY2025", "Q1 2025"
    confidence: float
    source_sentence: str  # Verbatim for provenance
    supersedes: Optional[str]  # Never delete, always chain
```

**Why it's transformative:**
- Solves temporal conflicts (FY2024 revenue vs FY2025 revenue both exist)
- Enables aggregation WITHOUT LLM arithmetic
- Prevents re-extraction contamination (old doc can't overwrite new metric)

### 5. **Confidence Gating with "NULL is Better Than Wrong"**

**What we had:** Accept all extractions, resolve conflicts later

**What LLM suggests:** Unstract's LLMChallenge pattern - gate BEFORE ingestion:

```python
def gate_metric(new, existing):
    if new.confidence < 0.65:
        return "QUARANTINE"  # Don't pollute graph

    if existing.confidence > 0.85 and new.confidence <= existing.confidence:
        return "REJECT"  # Don't overwrite high-confidence with lower

    return "ACCEPT"
```

**Why it's crucial:** Prevents contamination at source. Bad extractions never reach the graph.

### 6. **Hierarchical Evidence Prioritization Rules**

**What we had:** Generic weighting formula

**What LLM suggests:** Query-type-specific evidence hierarchies:

- **Roles:** Tree > Graph > Documents (tree is authoritative for org structure)
- **Metrics:** Documents > Graph (documents have latest figures)
- **Technical specs:** Documents > Graph (specs rarely exist as edges)
- **Relationships:** Graph > Documents > Tree (graph captures multi-hop best)
- **Aggregations:** Structured compute > Documents > Graph (NEVER let LLM do arithmetic)

**Why it's powerful:** Different evidence sources have different authority for different query types.

---

## Novel Research Directions (Blind Spots Section)

The LLM identified **6 advanced techniques** we completely missed:

1. **Power of Noise (SIGIR 2024):** High-confidence-but-wrong facts are WORSE than random noise. Implication: dilute suspicious facts with document passages instead of discarding.

2. **IAR Semantics (Inconsistency-Tolerant Reasoning):** Return only facts consistent across ALL possible repairs. Ultra-conservative but eliminates MISMATCH entirely.

3. **RobustRAG Isolate-Then-Aggregate:** Generate answer from each passage independently, THEN aggregate. Prevents conflicting passages from confusing LLM.

4. **Graphiti Temporal Edge Invalidation:** Explicit validity periods on edges + hybrid search to detect supersession. Cleaner than soft-scoring.

5. **MEGA-RAG DISC Module:** When answers are contested, generate clarification sub-queries and do second retrieval pass. Breaks ties evidence-weighting can't.

6. **PaTeCon Automatic Constraint Mining (AAAI 2023):** Mine functional constraints from data patterns instead of hand-coding. Self-improving conflict detection.

---

## Comparison: Our Plan vs LLM Plan

| Aspect | Our Original Plan | LLM Research Plan | Winner |
|--------|------------------|-------------------|---------|
| **Conflict Detection** | Fuzzy name matching | Functional dependency via cardinality | **LLM** (mathematically grounded) |
| **Scoring Formula** | evidence_count * 0.4 + confidence * 0.3... | CRH composite with SOURCE_TRUST | **LLM** (document authority) |
| **Graph Reliability** | Not addressed | SkewRoute entropy-based detection | **LLM** (automatic detection) |
| **Metric Schema** | Add HAS_REVENUE edges | Reified MetricObservation nodes | **LLM** (temporal handling) |
| **Contamination Prevention** | Conflict resolution after ingestion | Confidence gating BEFORE ingestion | **LLM** (prevents pollution) |
| **Evidence Priority** | Generic formula | Query-type-specific hierarchies | **LLM** (nuanced) |
| **Implementation Time** | 6 hours | 4 weeks (phased) | **Ours** (faster) |
| **Expected Accuracy** | 77% → 80% | 74% → 88-93% | **LLM** (higher ceiling) |

---

## Implementation Roadmap (LLM's 4-Week Plan)

### Week 1: Conflict-Aware Retrieval (+7 questions → 81%)

**What to build:**
1. Cardinality registry in ontology YAML
2. Functional dependency conflict detector
3. CRH evidence-weighted scorer with SOURCE_TRUST
4. Integration: single function between retrieval and synthesis

**Files to modify:**
- `src/context_foundry/extraction/ontology_manager.py` (add cardinality field)
- `src/context_foundry/resolution/conflict_resolver.py` (NEW)
- `src/context_foundry/agents/tool_agent.py:1047` (insert conflict resolution)

**Expected fixes:** Q3, Q14, Q25, Q51, Q100 + 2 persistent MISMATCH failures

**Test plan:** Inject 2 conflicting facts with known metadata → verify scorer picks correct one

---

### Week 2: Query Routing with Graph Reliability (+6 questions → 87%)

**What to build:**
1. Feature-based query classifier (rule-driven, no training)
2. SkewRoute entropy-based reliability detector
3. Automatic fallback when graph is UNRELIABLE

**Files to create:**
- `src/context_foundry/routing/query_classifier.py` (NEW)
- `src/context_foundry/routing/graph_reliability.py` (NEW)

**Expected fixes:** NOT_FOUND failures (employee counts, division counts, CISO, operating temps) - metrics now routed to documents

**Test plan:** 20 queries (4 per type) → verify correct routing + fallback triggers

---

### Week 3: Metric Extraction with Typed Schemas (+5 questions → 92%)

**What to build:**
1. MetricObservation schema (first-class nodes)
2. Pydantic-enforced extraction schema
3. Confidence gating (QUARANTINE low-confidence extractions)
4. Temporal supersession chains

**Files to modify:**
- `src/context_foundry/models/schema.py` (add MetricObservation table)
- `src/context_foundry/extraction/metric_extractor.py` (NEW)
- `src/context_foundry/extraction/kg_ingestor.py` (add gating logic)

**Expected fixes:** FORMAT failures (revenue targets, backlog, dates, capex) + Q25 battery specs

**Test plan:** Golden tests for each FORMAT failure → verify typed extraction + gating

---

### Week 4: Hybrid Fusion and Answer Arbitration (+3 questions → 95%)

**What to build:**
1. Multi-path fusion (RRF when multiple paths run)
2. Answer arbitration (evidence coverage + self-consistency + path alignment)
3. Hierarchical evidence prioritization

**Files to create:**
- `src/context_foundry/fusion/answer_arbitrator.py` (NEW)

**Expected fixes:** Edge cases where no single path is correct but answer is available across paths

**Test plan:** Queries with close routing scores → verify fusion produces correct answer

---

## Concrete Data Structures (From LLM)

The LLM provided **production-ready Python code** for:

1. **EnrichedFact** - extends staging table with temporal validity, source_trust, conflict metadata
2. **ConflictGroup** - tracks detected conflicts and resolution status
3. **RoutingDecision** - records why each query was routed to specific path
4. **MetricObservation** - first-class metric nodes with full provenance

All integrate with existing staging/evidence tables - minimal schema changes.

---

## Priority Recommendation

### Option A: Full LLM Plan (4 weeks, 88-93% accuracy)

**Pros:**
- Research-backed, mathematically grounded
- Highest accuracy ceiling
- Novel techniques (SkewRoute, Reified Metrics, SOURCE_TRUST)
- Self-improving (graph gets better over time)

**Cons:**
- 4 weeks implementation
- Schema changes required (MetricObservation table)
- More complex (4 interlocking components)

### Option B: Hybrid (Week 1 only, then evaluate)

**Pros:**
- Fastest path to 81% (1 week)
- Validates core approach
- Minimal code changes (single function)
- Can decide on Weeks 2-4 based on results

**Cons:**
- Doesn't address NOT_FOUND failures (those need routing)
- Doesn't fix FORMAT failures (those need typed extraction)

### Option C: Cherry-Pick Best Ideas

**Pros:**
- Take LLM's innovations, keep our timeline
- SOURCE_TRUST + Cardinality Registry + SkewRoute entropy
- Skip schema changes (Reified Metrics)

**Cons:**
- May miss synergies between components
- Harder to validate (research papers assume full system)

---

## My Recommendation: **Option B (Week 1 + Evaluate)**

**Rationale:**
1. Week 1 conflict resolution has **highest ROI**: +7 questions, 1 week effort
2. Validates the entire approach with minimal risk
3. If we hit 81%, we prove query-time resolution works → commit to Weeks 2-4
4. If we only hit 77%, we know conflicts are solved but need routing/extraction

**Implementation Priority:**
1. ✅ Add SOURCE_TRUST hierarchy (1 hour) - **immediate impact**
2. ✅ Build cardinality registry (2 hours) - **enables functional dependency detection**
3. ✅ Implement CRH scorer (3 hours) - **composite evidence weighting**
4. ✅ Integrate at tool_agent.py:1047 (2 hours) - **single insertion point**
5. ✅ Test on Q3, Q14, Q25, Q51, Q100 (4 hours) - **validation**

**Total:** ~12 hours = 1.5 days = **Week 1 is actually achievable in 2 days**

---

## Next Steps

1. **Codex:** Review LLM response + this analysis
2. **Decision:** Commit to Week 1 implementation?
3. **If yes:** I start coding ConflictResolver with SOURCE_TRUST + Cardinality
4. **Test:** Run against Q3, Q14, Q25, Q51, Q100 specifically
5. **Measure:** Does accuracy improve to 77-81% as projected?
6. **If yes:** Commit to Weeks 2-4
7. **If no:** Debug and understand gap

**The research is done. The plan is concrete. Ready to implement.**
