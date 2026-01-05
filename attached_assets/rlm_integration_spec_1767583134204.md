# Context Foundry × Recursive Language Models (RLM) Integration Spec

> **Purpose**: Enhance Context Foundry's query/reasoning pipeline with RLM principles
> **Status**: Draft for architectural review
> **Date**: January 2026

---

## Executive Summary

This spec proposes integrating Recursive Language Model (RLM) principles into Context Foundry's existing tri-memory architecture. The core insight from the RLM paper (Zhang et al., MIT CSAIL, Dec 2025): **treat long contexts as part of an external environment** that LLMs can programmatically interact with, rather than stuffing everything into the context window.

Context Foundry already implements a version of this philosophy with its tri-memory separation. RLM enhancement would allow cognitive agents to **write code to navigate memory** and **recursively sub-query for verification** — dramatically improving performance on complex multi-hop queries across ADQ's 50+ portfolio companies.

**Model Strategy**: The architecture is model-agnostic, supporting both Anthropic (Claude 4.5 family) and OpenAI (GPT-5 family). Recommended default: Claude Sonnet 4.5 for root orchestration + Claude Haiku 4.5 for sub-queries, maintaining consistency with CF's existing use of Claude for vision tasks.

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

## Memory Interface APIs

### SemanticMemoryAPI

```python
class SemanticMemoryAPI:
    """Exposes semantic memory operations to RLM REPL environment."""
    
    def __init__(self, tenant_id: str, memory: SemanticMemory):
        self.tenant_id = tenant_id
        self.memory = memory
    
    def find_entities(self, entity_type: str = None, limit: int = 50) -> List[EntitySummary]:
        """List entities, optionally filtered by type."""
        # Returns lightweight summaries, not full embeddings
        pass
    
    def find_similar(self, query: str, k: int = 10, 
                     entity_type: str = None) -> List[EntityMatch]:
        """Semantic search for entities matching query."""
        # Embeds query, searches pgvector
        pass
    
    def get_entity(self, entity_id: str) -> EntityDetail:
        """Get full entity details including properties."""
        pass
    
    def find_by_property(self, property_name: str, 
                         property_value: str) -> List[EntitySummary]:
        """Find entities with matching property values."""
        pass
    
    def get_lifecycle_state(self, entity_id: str) -> str:
        """Returns STAGING, TRUSTED, or ARCHIVED."""
        pass
```

### EpisodicMemoryAPI

```python
class EpisodicMemoryAPI:
    """Exposes episodic memory (document chunks) to RLM REPL environment."""
    
    def __init__(self, tenant_id: str, memory: EpisodicMemory):
        self.tenant_id = tenant_id
        self.memory = memory
    
    def search(self, query: str, k: int = 5) -> List[ChunkMatch]:
        """Semantic search over document chunks."""
        pass
    
    def get_chunk(self, chunk_id: str) -> ChunkDetail:
        """Get full chunk content with provenance."""
        pass
    
    def get_document_chunks(self, document_id: str) -> List[ChunkSummary]:
        """Get all chunks from a specific document."""
        pass
    
    def get_provenance(self, chunk_id: str) -> ProvenanceInfo:
        """Get source document, upload date, etc."""
        pass
    
    def search_by_document_type(self, doc_type: str, 
                                 query: str, k: int = 5) -> List[ChunkMatch]:
        """Search within specific document types."""
        pass
```

### SymbolicMemoryAPI

```python
class SymbolicMemoryAPI:
    """Exposes symbolic memory (relationships, rules) to RLM REPL environment."""
    
    def __init__(self, tenant_id: str, memory: SymbolicMemory):
        self.tenant_id = tenant_id
        self.memory = memory
    
    def get_relationships(self, entity_id: str, 
                          direction: str = "both") -> List[Relationship]:
        """Get relationships for an entity (outgoing, incoming, or both)."""
        pass
    
    def find_path(self, source_id: str, target_id: str, 
                  max_depth: int = 3) -> List[Path]:
        """Find relationship paths between two entities."""
        pass
    
    def get_related_entities(self, entity_id: str, 
                              relationship_type: str) -> List[EntitySummary]:
        """Get entities connected by specific relationship type."""
        pass
    
    def traverse(self, start_id: str, relationship_types: List[str], 
                 depth: int = 2) -> SubGraph:
        """Traverse graph from starting entity."""
        pass
    
    def get_rules_for_entity(self, entity_id: str) -> List[ValidationRule]:
        """Get applicable validation rules."""
        pass
```

### SubQueryAPI

```python
class SubQueryAPI:
    """Allows recursive LLM sub-queries with budget tracking."""
    
    def __init__(self, budget_tokens: int, 
                 provider: str = "anthropic",
                 model: str = "claude-haiku-4-5-20251001"):
        self.budget_remaining = budget_tokens
        self.provider = provider
        self.model = model
        self.call_count = 0
        self.max_calls = 20  # Hard limit
    
    def query(self, prompt: str, max_tokens: int = 500) -> str:
        """Execute a sub-LLM query, deducting from budget."""
        if self.call_count >= self.max_calls:
            raise BudgetExhaustedError("Max sub-query calls reached")
        if self.budget_remaining < max_tokens:
            raise BudgetExhaustedError("Token budget exhausted")
        
        # Execute query
        response = self._call_llm(prompt, max_tokens)
        
        # Track usage
        self.budget_remaining -= response.usage.total_tokens
        self.call_count += 1
        
        return response.content
    
    def verify(self, claim: str, evidence: str) -> VerificationResult:
        """Specialized verification sub-query."""
        prompt = f"""Verify if the following claim is supported by the evidence.
        
Claim: {claim}

Evidence: {evidence}

Respond with:
- supported: true/false
- confidence: 0.0-1.0
- reasoning: brief explanation
"""
        return self._parse_verification(self.query(prompt))
    
    def summarize(self, content: str, focus: str = None) -> str:
        """Specialized summarization sub-query."""
        pass
```

---

## RLM Executor

```python
class RLMExecutor:
    """Executes RLM-style iterative reasoning over tri-memory."""
    
    def __init__(self, tenant_id: str, tri_memory: TriMemory, config: RLMConfig):
        self.tenant_id = tenant_id
        self.config = config
        
        # Initialize memory APIs
        self.semantic = SemanticMemoryAPI(tenant_id, tri_memory.semantic)
        self.episodic = EpisodicMemoryAPI(tenant_id, tri_memory.episodic)
        self.symbolic = SymbolicMemoryAPI(tenant_id, tri_memory.symbolic)
        
        # Initialize sub-query API with budget
        self.llm_query = SubQueryAPI(
            budget_tokens=config.sub_query_budget,
            model=config.sub_query_model
        )
        
        # Execution state
        self.execution_trace = []
        self.iteration_count = 0
    
    def execute(self, query: str, context_hint: str = None) -> RLMResult:
        """Execute RLM reasoning loop."""
        
        # Build system prompt with memory interface documentation
        system_prompt = self._build_system_prompt(query, context_hint)
        
        # Initialize REPL environment
        repl_env = self._create_sandbox()
        
        # Iterative execution loop
        while self.iteration_count < self.config.max_iterations:
            # Get next action from root LLM
            action = self._get_next_action(system_prompt, self.execution_trace)
            
            if action.type == "FINAL":
                return self._finalize(action.content)
            
            if action.type == "FINAL_VAR":
                return self._finalize_var(action.variable_name, repl_env)
            
            if action.type == "CODE":
                # Execute code in sandbox
                result = self._execute_code(action.code, repl_env)
                self.execution_trace.append({
                    "iteration": self.iteration_count,
                    "code": action.code,
                    "result": result,
                    "budget_remaining": self.llm_query.budget_remaining
                })
            
            self.iteration_count += 1
        
        # Max iterations reached - return best effort
        return self._finalize_timeout()
    
    def _create_sandbox(self) -> dict:
        """Create sandboxed execution environment with memory APIs."""
        return {
            "semantic": self.semantic,
            "episodic": self.episodic,
            "symbolic": self.symbolic,
            "llm_query": self.llm_query.query,
            "llm_verify": self.llm_query.verify,
            "llm_summarize": self.llm_query.summarize,
            # Safe builtins only
            "print": self._capture_print,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "list": list,
            "dict": dict,
            "set": set,
            "sorted": sorted,
            "enumerate": enumerate,
            "zip": zip,
            "range": range,
            "min": min,
            "max": max,
            "sum": sum,
            "any": any,
            "all": all,
        }
    
    def _build_system_prompt(self, query: str, context_hint: str) -> str:
        """Build system prompt with memory interface documentation."""
        return f"""You are a reasoning agent with access to a tri-memory knowledge system.
Your task is to answer the following query by exploring the memory layers.

QUERY: {query}

{f"HINT: {context_hint}" if context_hint else ""}

## Available Memory Interfaces

You have access to three memory layers as Python objects:

### semantic - Entity Memory
- semantic.find_entities(entity_type=None, limit=50) → List of entity summaries
- semantic.find_similar(query, k=10, entity_type=None) → Semantic search for entities
- semantic.get_entity(entity_id) → Full entity details
- semantic.find_by_property(property_name, property_value) → Property-based search

### episodic - Document Memory  
- episodic.search(query, k=5) → Semantic search over document chunks
- episodic.get_chunk(chunk_id) → Full chunk content with provenance
- episodic.get_document_chunks(document_id) → All chunks from a document
- episodic.get_provenance(chunk_id) → Source tracking

### symbolic - Relationship Memory
- symbolic.get_relationships(entity_id, direction="both") → Entity relationships
- symbolic.find_path(source_id, target_id, max_depth=3) → Path between entities
- symbolic.get_related_entities(entity_id, relationship_type) → Related entities
- symbolic.traverse(start_id, relationship_types, depth=2) → Graph traversal

### llm_query - Recursive Sub-Queries
- llm_query(prompt) → Query a sub-LLM for analysis/verification
- llm_verify(claim, evidence) → Verify a claim against evidence
- llm_summarize(content, focus=None) → Summarize content

## Execution Rules

1. Write Python code in ```repl blocks to explore memory
2. Use print() to observe results and continue reasoning
3. Use llm_query() for semantic analysis that code can't handle
4. Budget your sub-queries - you have limited calls
5. When ready, use FINAL(answer) or FINAL_VAR(variable_name)

## Strategy Suggestions

- Start by probing semantic memory for relevant entities
- Use symbolic memory to find relationships between entities
- Verify findings with episodic memory (source documents)
- Use llm_verify() to check claims before finalizing
- Aggregate evidence before providing final answer

## Example

```repl
# Find entities related to query
entities = semantic.find_similar("quarterly revenue", k=5, entity_type="METRIC")
print(f"Found {{len(entities)}} relevant metrics")
for e in entities:
    print(f"  - {{e.name}} ({{e.entity_type}}): {{e.confidence}}")
```

Remember: Explore thoroughly, verify claims, and cite your sources.
"""
```

---

## Query Complexity Router

```python
class QueryComplexityRouter:
    """Routes queries to standard or RLM pipeline based on complexity."""
    
    COMPLEXITY_THRESHOLDS = {
        "entity_count": 3,      # Queries involving 3+ entities → RLM
        "hop_count": 2,         # Multi-hop queries → RLM
        "aggregation": True,    # Aggregation queries → RLM
        "comparison": True,     # Comparison queries → RLM
    }
    
    def __init__(self, classifier: QueryClassifier):
        self.classifier = classifier
    
    def route(self, query: str) -> QueryRoute:
        """Determine whether query should use standard or RLM pipeline."""
        
        # Classify query
        classification = self.classifier.classify(query)
        
        # Check complexity indicators
        complexity_score = 0
        
        if classification.entity_mentions >= self.COMPLEXITY_THRESHOLDS["entity_count"]:
            complexity_score += 2
        
        if classification.requires_multi_hop:
            complexity_score += 3
        
        if classification.is_aggregation:
            complexity_score += 2
        
        if classification.is_comparison:
            complexity_score += 2
        
        if classification.temporal_reasoning:
            complexity_score += 1
        
        # Route decision
        if complexity_score >= 3:
            return QueryRoute(
                pipeline="RLM",
                config=RLMConfig(
                    max_iterations=10,
                    sub_query_budget=self._calculate_budget(complexity_score),
                    root_provider="anthropic",
                    root_model="claude-sonnet-4-5-20250929",
                    sub_provider="anthropic",
                    sub_model="claude-haiku-4-5-20251001"
                ),
                reasoning=f"Complexity score {complexity_score}: {classification.summary}"
            )
        else:
            return QueryRoute(
                pipeline="STANDARD",
                config=None,
                reasoning=f"Simple query (score {complexity_score})"
            )
    
    def _calculate_budget(self, complexity_score: int) -> int:
        """Calculate sub-query token budget based on complexity."""
        base_budget = 5000
        return base_budget + (complexity_score * 2000)
```

---

## Example RLM Execution Trace

**Query**: "Which services in the IT Operations domain are affected by incidents that were triggered by the Network Monitoring service?"

**Iteration 1**: Probe for entities
```python
# Find the Network Monitoring service
network_mon = semantic.find_similar("Network Monitoring", k=3, entity_type="SERVICE")
print(f"Found services: {[e.name for e in network_mon]}")
# Output: Found services: ['Network Monitoring Service', 'Network Monitor Agent', 'NetMon Dashboard']
```

**Iteration 2**: Get relationships
```python
# Get the correct entity and find incidents it triggered
nms = semantic.get_entity(network_mon[0].id)
print(f"Entity: {nms.name} (confidence: {nms.confidence})")

# Find incidents triggered by this service
incidents = symbolic.get_related_entities(nms.id, "TRIGGERED_BY")
print(f"Triggered incidents: {len(incidents)}")
for inc in incidents:
    print(f"  - {inc.name}")
# Output: 
# Entity: Network Monitoring Service (confidence: 0.89)
# Triggered incidents: 4
#   - INC-2024-0142
#   - INC-2024-0156
#   - INC-2024-0189
#   - INC-2024-0201
```

**Iteration 3**: Find affected services
```python
# For each incident, find affected services
affected_services = set()
for inc in incidents:
    affected = symbolic.get_related_entities(inc.id, "AFFECTS")
    for svc in affected:
        affected_services.add((svc.id, svc.name))
        print(f"Incident {inc.name} affects: {svc.name}")

print(f"\nTotal unique affected services: {len(affected_services)}")
# Output:
# Incident INC-2024-0142 affects: Email Gateway
# Incident INC-2024-0142 affects: Authentication Service
# Incident INC-2024-0156 affects: Database Cluster
# ...
# Total unique affected services: 7
```

**Iteration 4**: Verify with episodic memory
```python
# Verify findings against source documents
verification_results = []
for svc_id, svc_name in list(affected_services)[:3]:  # Sample verification
    chunks = episodic.search(f"incident {svc_name} Network Monitoring", k=2)
    if chunks:
        verified = llm_verify(
            claim=f"{svc_name} was affected by an incident triggered by Network Monitoring",
            evidence=chunks[0].content
        )
        verification_results.append((svc_name, verified))
        print(f"Verified {svc_name}: {verified.supported} ({verified.confidence})")

# Output:
# Verified Email Gateway: True (0.92)
# Verified Authentication Service: True (0.87)
# Verified Database Cluster: True (0.78)
```

**Iteration 5**: Finalize
```python
# Build final answer
answer = {
    "affected_services": [name for _, name in affected_services],
    "source_service": "Network Monitoring Service",
    "incident_count": len(incidents),
    "verification_confidence": sum(v.confidence for _, v in verification_results) / len(verification_results)
}
print(f"Final answer prepared: {len(answer['affected_services'])} services affected")
```

**FINAL_VAR(answer)**

---

## Configuration

```yaml
# config/rlm_config.yaml

rlm:
  enabled: true
  
  # Complexity routing
  routing:
    min_complexity_score: 3
    always_rlm_patterns:
      - "which .* are affected by"
      - "trace .* through"
      - "compare .* across"
      - "aggregate .* from"
  
  # Execution limits
  execution:
    max_iterations: 10
    iteration_timeout_seconds: 30
    total_timeout_seconds: 120
  
  # Sub-query budget
  sub_queries:
    provider: "anthropic"  # or "openai"
    model: "claude-haiku-4-5-20251001"  # or "gpt-5-mini"
    base_budget_tokens: 5000
    max_budget_tokens: 20000
    max_calls: 20
  
  # Root LLM (orchestrates REPL reasoning)
  root_llm:
    provider: "anthropic"  # or "openai"
    model: "claude-sonnet-4-5-20250929"  # or "gpt-5"
    temperature: 0.1
    max_tokens: 2000
  
  # Model presets for easy switching
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
  
  # Safety
  sandbox:
    allowed_imports: []  # No imports allowed
    max_output_length: 10000
    restricted_apis: ["os", "sys", "subprocess", "eval", "exec"]
```

### Model Selection Rationale

| Configuration | Root LLM | Sub-Query LLM | Use Case |
|---------------|----------|---------------|----------|
| **anthropic_recommended** | Claude Sonnet 4.5 | Claude Haiku 4.5 | Default - balances capability and cost |
| **anthropic_max** | Claude Opus 4.5 | Claude Sonnet 4.5 | Complex multi-hop queries requiring deep reasoning |
| **openai_paper_validated** | GPT-5 | GPT-5-mini | Replicating MIT paper results for benchmarking |

**Recommendation**: Start with `anthropic_recommended` since CF already uses Claude Sonnet for complex PDF vision. This maintains ecosystem consistency and leverages Claude's strong code generation for REPL operations. Benchmark against `openai_paper_validated` to compare performance.

---

## Implementation Phases

### Phase 1: Memory APIs (Week 1-2)
- [ ] Implement SemanticMemoryAPI wrapper
- [ ] Implement EpisodicMemoryAPI wrapper  
- [ ] Implement SymbolicMemoryAPI wrapper
- [ ] Unit tests for each API
- [ ] Documentation

### Phase 2: REPL Executor (Week 3-4)
- [ ] Sandboxed Python execution environment
- [ ] Iteration loop with state management
- [ ] Output capture and truncation
- [ ] Budget tracking
- [ ] Execution trace logging

### Phase 3: Sub-Query API (Week 5)
- [ ] SubQueryAPI with budget management
- [ ] Specialized verify/summarize methods
- [ ] Rate limiting and circuit breakers
- [ ] Cost tracking integration with MeteringService

### Phase 4: Query Router (Week 6)
- [ ] Complexity classification
- [ ] Routing logic
- [ ] Configuration system
- [ ] A/B testing framework (RLM vs standard)

### Phase 5: Integration & Testing (Week 7-8)
- [ ] Integration with existing Brain service
- [ ] End-to-end testing
- [ ] Performance benchmarking
- [ ] Cost analysis
- [ ] Documentation and runbooks

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Runaway costs from sub-queries | Hard budget limits, circuit breakers, cost alerts |
| Infinite loops in REPL | Iteration limits, timeout per iteration |
| Code injection | Sandboxed execution, no imports, restricted builtins |
| Poor routing decisions | A/B testing, gradual rollout, fallback to standard |
| Latency increase | Async execution where possible, caching, timeout limits |
| Model capability gaps | Default to Claude Sonnet 4.5 for root; benchmark alternatives |
| Provider lock-in | Model-agnostic architecture supports Anthropic, OpenAI, others |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Complex query accuracy | +20% vs standard pipeline | A/B test on multi-hop queries |
| Response completeness | +15% evidence citation | Automated citation counting |
| Cost per query (complex) | <$0.50 average | Cost tracking |
| Latency (complex queries) | <30s p95 | Latency monitoring |
| User satisfaction | +10% on complex queries | Feedback collection |

---

## Open Questions for Discussion

1. **Model selection**: Should we default to Anthropic (Claude Sonnet 4.5 root + Haiku 4.5 sub) for ecosystem consistency, or benchmark against GPT-5 combo first? Paper validated with GPT-5, but CF already uses Claude for vision.

2. **Recursion depth**: Paper used depth=1 (sub-calls are plain LLMs). Should we allow RLM sub-calls (depth=2+) for very complex queries? Claude Opus 4.5 might handle deeper recursion better than alternatives.

3. **Caching**: Should we cache sub-query results? Could reduce costs but may return stale verification.

4. **Hybrid approach**: For queries right at the complexity threshold, should we run both pipelines and compare?

5. **Training data**: Should we collect RLM traces to potentially fine-tune a model specifically for CF's memory navigation?

6. **Extended thinking**: Claude 4.5 models support extended thinking. Should root LLM use this for complex orchestration decisions, or does it add too much latency?

---

## References

- Zhang, A.L., Kraska, T., & Khattab, O. (2025). Recursive Language Models. arXiv:2512.24601
- Context Foundry Architecture Doc (ARCHITECTURE.md)
- CF SavePoint Dec 15 (latest system state)
