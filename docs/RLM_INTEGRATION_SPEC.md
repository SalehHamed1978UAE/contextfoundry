# Context Foundry × Recursive Language Models (RLM) Integration Spec

> **Purpose**: Enhance Context Foundry's query/reasoning pipeline with RLM principles
> **Status**: Approved for implementation
> **Date**: January 2026

---

## Executive Summary

This spec proposes integrating Recursive Language Model (RLM) principles into Context Foundry's existing tri-memory architecture. The core insight from the RLM paper (Zhang et al., MIT CSAIL, Dec 2025): **treat long contexts as part of an external environment** that LLMs can programmatically interact with, rather than stuffing everything into the context window.

Context Foundry already implements a version of this philosophy with its tri-memory separation. RLM enhancement would allow cognitive agents to **write code to navigate memory** and **recursively sub-query for verification** — dramatically improving performance on complex multi-hop queries across ADQ's 50+ portfolio companies.

**Model Strategy**: The architecture is model-agnostic, supporting both Anthropic (Claude 4.5 family) and OpenAI (GPT-5 family). Recommended default: Claude Sonnet 4.5 for root orchestration + Claude Haiku 4.5 for sub-queries.

---

## Design Decisions (Resolved)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| STAGING visibility | **Option B**: Show both STAGING and TRUSTED with `lifecycle_state` field | LLM can weigh confidence accordingly; hiding STAGING loses recent data |
| Circuit breaker | Progress = new entities OR new relationships discovered | Simple, measurable, prevents cost runaway |
| Entity ID stability | Live data + `StaleEntityError` if ID disappears | Gardener runs every 5 min; unlikely but handle gracefully |

---

## Current Architecture (Baseline)

```
User Query
    │
    ▼
┌─────────────────┐
│ QueryClassifier │  Classify intent, check data sufficiency
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ EntityResolver  │  3-stage: exact → semantic → fuzzy
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ RetrievalAgent  │  Query all 3 memory layers
│                 │  Build ContextBundle
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ReasoningAgent  │  LLM reasoning with full context
│                 │  3-phase confidence calibration
└────────┬────────┘
         │
         ▼
    Response
```

**Limitation**: RetrievalAgent assembles a static ContextBundle before reasoning. The LLM cannot adaptively explore memory based on intermediate findings.

---

## Proposed RLM-Enhanced Architecture

```
User Query
    │
    ▼
┌─────────────────┐
│ QueryClassifier │  Classify intent, estimate complexity
│                 │  Route: SIMPLE → standard | COMPLEX → RLM
└────────┬────────┘
         │
         ▼ (COMPLEX queries)
┌─────────────────────────────────────────────────────────────────┐
│                     RLM EXECUTION ENVIRONMENT                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    MEMORY INTERFACE                        │  │
│  │                                                            │  │
│  │  semantic = SemanticMemoryAPI(tenant_id)                   │  │
│  │  episodic = EpisodicMemoryAPI(tenant_id)                   │  │
│  │  symbolic = SymbolicMemoryAPI(tenant_id)                   │  │
│  │  llm_query = SubQueryAPI(budget_remaining)                 │  │
│  │                                                            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────▼───────────────────────────────┐  │
│  │                    REPL EXECUTOR                           │  │
│  │                                                            │  │
│  │  - Sandboxed Python execution                              │  │
│  │  - Memory APIs exposed as queryable objects                │  │
│  │  - Iteration limit: 10 turns                               │  │
│  │  - Token budget: configurable per query complexity         │  │
│  │                                                            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────▼───────────────────────────────┐  │
│  │                    ROOT LLM                                │  │
│  │                                                            │  │
│  │  Writes code to:                                           │  │
│  │  - Probe memory layers based on query understanding        │  │
│  │  - Traverse relationships in symbolic memory               │  │
│  │  - Verify findings with recursive sub-queries              │  │
│  │  - Aggregate evidence into final answer                    │  │
│  │                                                            │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│ ValidationAgent │  Check against symbolic rules
└────────┬────────┘
         │
         ▼
    Response with:
    - answer_text
    - response_mode
    - confidence
    - evidence_chain
    - execution_trace (NEW: for debugging/audit)
```

---

## Configuration

```yaml
rlm:
  enabled: true
  
  routing:
    min_complexity_score: 3
    always_rlm_patterns:
      - "which .* are affected by"
      - "trace .* through"
      - "compare .* across"
      - "aggregate .* from"
  
  execution:
    max_iterations: 10
    iteration_timeout_seconds: 30
    total_timeout_seconds: 120
  
  sub_queries:
    provider: "anthropic"
    model: "claude-haiku-4-5-20251001"
    base_budget_tokens: 5000
    max_budget_tokens: 20000
    max_calls: 20
  
  root_llm:
    provider: "anthropic"
    model: "claude-sonnet-4-5-20250929"
    temperature: 0.1
    max_tokens: 2000
  
  presets:
    anthropic_recommended:
      root: "claude-sonnet-4-5-20250929"
      sub: "claude-haiku-4-5-20251001"
    anthropic_max:
      root: "claude-opus-4-5-20251101"
      sub: "claude-sonnet-4-5-20250929"
    openai_paper_validated:
      root: "gpt-5"
      sub: "gpt-5-mini"
  
  sandbox:
    allowed_imports: []
    max_output_length: 10000
    restricted_apis: ["os", "sys", "subprocess", "eval", "exec"]
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Runaway costs from sub-queries | Hard budget limits, circuit breakers, cost alerts |
| Infinite loops in REPL | Iteration limits, timeout per iteration |
| Code injection | Sandboxed execution, no imports, restricted builtins |
| Poor routing decisions | A/B testing, gradual rollout, fallback to standard |
| Latency increase | Async execution where possible, caching, timeout limits |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Complex query accuracy | +20% vs standard pipeline | A/B test on multi-hop queries |
| Response completeness | +15% evidence citation | Automated citation counting |
| Cost per query (complex) | <$0.50 average | Cost tracking |
| Latency (complex queries) | <30s p95 | Latency monitoring |

---

## Implementation Phases

### Phase 1: Memory APIs (Week 1-2)
- Implement SemanticMemoryAPI wrapper
- Implement EpisodicMemoryAPI wrapper  
- Implement SymbolicMemoryAPI wrapper
- Unit tests for each API
- Documentation

### Phase 2: REPL Executor (Week 3-4)
- Sandboxed Python execution environment
- Iteration loop with state management
- Output capture and truncation
- Budget tracking
- Execution trace logging

### Phase 3: Sub-Query API (Week 5)
- SubQueryAPI with budget management
- Specialized verify/summarize methods
- Rate limiting and circuit breakers
- Cost tracking integration with MeteringService

### Phase 4: Query Router (Week 6)
- Complexity classification
- Routing logic
- Configuration system
- A/B testing framework (RLM vs standard)

### Phase 5: Integration & Testing (Week 7-8)
- Integration with existing Brain service
- End-to-end testing
- Performance benchmarking
- Cost analysis
- Documentation and runbooks

---

## References

- Zhang, A.L., Kraska, T., & Khattab, O. (2025). Recursive Language Models. arXiv:2512.24601
- Context Foundry Architecture Doc (ARCHITECTURE.md)
- Memory API Schemas (RLM_MEMORY_API_SCHEMAS.md)
