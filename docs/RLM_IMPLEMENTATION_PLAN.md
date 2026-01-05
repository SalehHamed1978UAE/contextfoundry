# RLM Integration - Detailed Implementation & Testing Plan

> **Purpose**: Step-by-step implementation guide for RLM integration
> **Date**: January 2026

---

## Overview

This document provides detailed implementation instructions for each phase of the RLM integration. Each task includes:
- Acceptance criteria
- Key implementation details
- Test requirements
- Dependencies

---

## Phase 1: Memory APIs (Week 1-2)

### Task 1.1: Create RLM Pydantic Schemas

**File**: `src/context_foundry/rlm/schemas.py`

**Implementation**:
```python
# All data types from RLM_MEMORY_API_SCHEMAS.md
# - EntitySummary, EntityDetail, EntityMatch
# - ChunkSummary, ChunkDetail, ChunkMatch
# - Relationship, Path, PathStep, SubGraph
# - VerificationResult
# - REPLExecutionResult, ProgressTracker
# - ExecutionTrace, ExecutionTraceEntry, SubQueryLog
# - Error types: RLMError, StaleEntityError, BudgetExhaustedError, etc.
```

**Acceptance Criteria**:
- [ ] All Pydantic models validate correctly
- [ ] JSON serialization/deserialization works
- [ ] Examples in docstrings for each model

**Test File**: `tests/rlm/test_schemas.py`
- Validate model instantiation
- Test JSON round-trip
- Test error messages

---

### Task 1.2: Implement SemanticMemoryAPI

**File**: `src/context_foundry/rlm/memory_apis/semantic.py`

**Methods**:
| Method | Description | DB Query |
|--------|-------------|----------|
| `find_entities()` | List entities by type | `entities` table filtered |
| `find_similar()` | Semantic search | pgvector cosine similarity |
| `get_entity()` | Full entity details | Join with properties |
| `find_by_property()` | Property-based search | JSONB query |

**Key Implementation Details**:
- Wrap existing `SemanticMemory` class
- Add `include_staging` parameter to all methods
- Track accessed entity IDs for progress tracking
- Raise `StaleEntityError` when entity not found

**Acceptance Criteria**:
- [ ] All 4 methods implemented
- [ ] Tenant isolation enforced
- [ ] Returns correct Pydantic types
- [ ] Handles missing entities gracefully

**Test File**: `tests/rlm/test_semantic_memory_api.py`
- Test with known entities in test tenant
- Test `include_staging` filtering
- Test entity not found scenario

---

### Task 1.3: Implement EpisodicMemoryAPI

**File**: `src/context_foundry/rlm/memory_apis/episodic.py`

**Methods**:
| Method | Description | DB Query |
|--------|-------------|----------|
| `search()` | Semantic search over chunks | pgvector on embeddings |
| `get_chunk()` | Full chunk content | `document_chunks` table |
| `get_document_chunks()` | All chunks from document | Filter by document_id |
| `get_provenance()` | Source tracking | Join with documents |

**Key Implementation Details**:
- Wrap existing `EpisodicMemory` class
- Add `document_type` filter to search
- Build provenance chain from document metadata

**Acceptance Criteria**:
- [ ] All 4 methods implemented
- [ ] Tenant isolation via document ownership
- [ ] Content properly escaped for REPL display

**Test File**: `tests/rlm/test_episodic_memory_api.py`
- Test search with known document content
- Test provenance retrieval
- Test chunk content matches source

---

### Task 1.4: Implement SymbolicMemoryAPI

**File**: `src/context_foundry/rlm/memory_apis/symbolic.py`

**Methods**:
| Method | Description | DB Query |
|--------|-------------|----------|
| `get_relationships()` | Entity relationships | `facts` table filtered |
| `find_path()` | BFS path finding | Recursive CTE |
| `get_related_entities()` | Related by type | Join facts → entities |
| `traverse()` | Graph traversal | Recursive with depth limit |

**Key Implementation Details**:
- Wrap existing `SymbolicMemory` class
- `find_path()` uses BFS with max_depth limit
- `traverse()` returns SubGraph with truncation flag
- Track discovered relationships for progress

**Acceptance Criteria**:
- [ ] All 4 methods implemented
- [ ] Path finding handles cycles
- [ ] Traversal respects max_entities limit

**Test File**: `tests/rlm/test_symbolic_memory_api.py`
- Test relationship retrieval (both directions)
- Test path finding between connected entities
- Test traverse with depth limits

---

## Phase 2: REPL Executor (Week 3-4)

### Task 2.1: Create Sandbox Execution Environment

**File**: `src/context_foundry/rlm/sandbox.py`

**Implementation**:
```python
class REPLSandbox:
    def __init__(self, memory_apis: dict, llm_apis: dict):
        self.globals = self._create_safe_globals(memory_apis, llm_apis)
        self.locals = {}
        self.output_buffer = []
    
    def execute(self, code: str, timeout_seconds: int = 30) -> REPLExecutionResult:
        # 1. Validate code (no imports, restricted builtins)
        # 2. Execute with timeout
        # 3. Capture stdout to output_buffer
        # 4. Track accessed entities/relationships
        # 5. Return structured result
```

**Safe Builtins**:
```python
SAFE_BUILTINS = {
    "print": self._capture_print,
    "len", "str", "int", "float", "list", "dict", "set",
    "sorted", "enumerate", "zip", "range", "min", "max",
    "sum", "any", "all", "True", "False", "None"
}
```

**Restricted Patterns** (reject code containing):
- `import`, `__import__`
- `eval`, `exec`, `compile`
- `open`, `file`
- `os.`, `sys.`, `subprocess`
- `__builtins__`, `__class__`, `__bases__`

**Acceptance Criteria**:
- [ ] Code executes in isolated namespace
- [ ] Timeout enforced
- [ ] stdout captured correctly
- [ ] Dangerous operations rejected
- [ ] Memory APIs accessible

**Test File**: `tests/rlm/test_sandbox.py`
- Test safe code execution
- Test import rejection
- Test timeout handling
- Test output capture

---

### Task 2.2: Implement Progress Tracker

**File**: `src/context_foundry/rlm/progress.py`

**Implementation**:
```python
class ProgressTracker:
    def __init__(self):
        self.entities_discovered: Set[str] = set()
        self.relationships_discovered: Set[str] = set()
        self.iteration = 0
        self.iterations_without_progress = 0
    
    def record_iteration(self, result: REPLExecutionResult) -> bool:
        # Returns True if progress was made
        pass
    
    def should_trip_breaker(self, threshold: int = 3) -> bool:
        return self.iterations_without_progress >= threshold
```

**Acceptance Criteria**:
- [ ] Correctly tracks new vs. seen entities
- [ ] Circuit breaker trips after 3 no-progress iterations
- [ ] Resets progress counter on discovery

**Test File**: `tests/rlm/test_progress.py`
- Test progress detection
- Test circuit breaker logic
- Test edge cases (empty results, duplicates)

---

### Task 2.3: Implement Retry Hint Generator

**File**: `src/context_foundry/rlm/hints.py`

**Implementation**:
```python
def generate_retry_hint(error: Exception, code: str) -> Optional[str]:
    error_type = type(error).__name__
    
    if error_type == "AttributeError":
        return f"Object doesn't have attribute '{extract_attr(error)}'. Check schema: EntitySummary has id, name, entity_type, confidence, lifecycle_state"
    
    if error_type == "KeyError":
        return f"Key '{error.args[0]}' not found. Available keys: {extract_available_keys(code)}"
    
    # ... more patterns
```

**Error Patterns**:
| Error Type | Hint Template |
|------------|---------------|
| AttributeError | Show valid attributes for the type |
| KeyError | Show available keys |
| TypeError | Show expected types |
| StaleEntityError | Suggest re-search |
| BudgetExhaustedError | Suggest finalize |

**Acceptance Criteria**:
- [ ] Covers common error types
- [ ] Hints are actionable
- [ ] Returns None for unknown errors

---

### Task 2.4: Implement RLM Executor Core

**File**: `src/context_foundry/rlm/executor.py`

**Implementation**:
```python
class RLMExecutor:
    def __init__(self, tenant_id: str, config: RLMConfig):
        self.tenant_id = tenant_id
        self.config = config
        self.progress = ProgressTracker()
        self.trace = ExecutionTrace(...)
        
        # Initialize memory APIs
        self.semantic = SemanticMemoryAPI(tenant_id, db_session)
        self.episodic = EpisodicMemoryAPI(tenant_id, db_session)
        self.symbolic = SymbolicMemoryAPI(tenant_id, db_session)
        self.sub_query = SubQueryAPI(config.sub_query_budget)
        
        # Create sandbox
        self.sandbox = REPLSandbox(
            memory_apis={"semantic": self.semantic, "episodic": self.episodic, "symbolic": self.symbolic},
            llm_apis={"llm_query": self.sub_query.query, "llm_verify": self.sub_query.verify}
        )
    
    def execute(self, query: str, context_hint: str = None) -> RLMResult:
        # Main loop
        while self.progress.iteration < self.config.max_iterations:
            # 1. Get next action from root LLM
            action = self._get_next_action()
            
            # 2. Handle action type
            if action.type == "FINAL":
                return self._finalize(action.content)
            
            if action.type == "CODE":
                result = self.sandbox.execute(action.code)
                self._record_iteration(result)
            
            # 3. Check circuit breaker
            if self.progress.should_trip_breaker():
                return self._fallback_to_standard()
```

**Acceptance Criteria**:
- [ ] Iteration loop works correctly
- [ ] FINAL action terminates cleanly
- [ ] CODE action executes in sandbox
- [ ] Circuit breaker triggers correctly
- [ ] Execution trace captured

**Test File**: `tests/rlm/test_executor.py`
- Test simple query execution
- Test iteration limits
- Test circuit breaker
- Test trace generation

---

## Phase 3: Sub-Query API (Week 5)

### Task 3.1: Implement SubQueryAPI

**File**: `src/context_foundry/rlm/sub_query.py`

**Implementation**:
```python
class SubQueryAPI:
    def __init__(self, budget_tokens: int, provider: str = "anthropic", 
                 model: str = "claude-haiku-4-5-20251001"):
        self.budget_remaining = budget_tokens
        self.call_count = 0
        self.max_calls = 20
        self.client = self._init_client(provider)
    
    def query(self, prompt: str, max_tokens: int = 500) -> str:
        self._check_budget(max_tokens)
        response = self._call_llm(prompt, max_tokens)
        self._deduct_usage(response)
        return response.content
    
    def verify(self, claim: str, evidence: str) -> VerificationResult:
        prompt = self._build_verify_prompt(claim, evidence)
        response = self.query(prompt)
        return self._parse_verification(response)
    
    def summarize(self, content: str, focus: str = None) -> str:
        prompt = self._build_summarize_prompt(content, focus)
        return self.query(prompt)
```

**Acceptance Criteria**:
- [ ] Budget tracking works
- [ ] BudgetExhaustedError raised correctly
- [ ] verify() returns structured result
- [ ] Supports both Anthropic and OpenAI

**Test File**: `tests/rlm/test_sub_query.py`
- Test budget deduction
- Test budget exhaustion
- Test verify parsing
- Test provider switching (mock)

---

### Task 3.2: Add Cost Tracking Integration

**File**: Update `src/platform_foundation/services/metering.py`

**Add**:
```python
def record_rlm_usage(self, tenant_id: str, query_id: str, 
                      tokens_used: int, sub_queries: int, cost_usd: float):
    # Record RLM-specific usage for billing
```

**Acceptance Criteria**:
- [ ] RLM queries metered separately
- [ ] Cost breakdowns visible in dashboard
- [ ] Alerts for high-cost queries

---

## Phase 4: Query Router (Week 6)

### Task 4.1: Implement Complexity Classifier

**File**: `src/context_foundry/rlm/router.py`

**Implementation**:
```python
class QueryComplexityClassifier:
    COMPLEXITY_WEIGHTS = {
        "entity_mentions": 1,      # Per entity beyond 2
        "multi_hop": 3,            # Requires traversal
        "aggregation": 2,          # "all", "every", "sum of"
        "comparison": 2,           # "compare", "vs", "difference"
        "temporal": 1,             # Time-based reasoning
    }
    
    def classify(self, query: str) -> ComplexityResult:
        score = 0
        reasons = []
        
        # Count entity mentions
        entities = self._extract_entity_mentions(query)
        if len(entities) > 2:
            score += (len(entities) - 2) * self.COMPLEXITY_WEIGHTS["entity_mentions"]
            reasons.append(f"{len(entities)} entities mentioned")
        
        # Check for multi-hop patterns
        if self._is_multi_hop(query):
            score += self.COMPLEXITY_WEIGHTS["multi_hop"]
            reasons.append("Multi-hop traversal required")
        
        # ... more checks
        
        return ComplexityResult(
            score=score,
            route="RLM" if score >= 3 else "STANDARD",
            reasons=reasons
        )
```

**Patterns for RLM**:
- "which X are affected by Y"
- "trace X through Y"
- "compare X across Y"
- "aggregate X from Y"
- "all X that relate to Y"

**Acceptance Criteria**:
- [ ] Correctly scores simple queries < 3
- [ ] Correctly scores complex queries >= 3
- [ ] Pattern matching for forced-RLM queries
- [ ] Reasons logged for debugging

**Test File**: `tests/rlm/test_router.py`
- Test simple query classification
- Test complex query classification
- Test pattern matching
- Test edge cases

---

### Task 4.2: Integrate Router with Brain Service

**File**: Update `src/context_foundry/brain/query_handler.py`

**Changes**:
```python
async def handle_query(self, query: str, tenant_id: str) -> QueryResponse:
    # 1. Classify complexity
    complexity = self.router.classify(query)
    
    # 2. Route based on complexity
    if complexity.route == "RLM":
        return await self._handle_rlm(query, tenant_id, complexity)
    else:
        return await self._handle_standard(query, tenant_id)
```

**Acceptance Criteria**:
- [ ] Simple queries use standard pipeline
- [ ] Complex queries use RLM pipeline
- [ ] Fallback to standard on RLM failure
- [ ] Response format consistent

---

## Phase 5: Integration & Testing (Week 7-8)

### Task 5.1: End-to-End Integration Tests

**File**: `tests/rlm/test_e2e.py`

**Test Scenarios**:

| Scenario | Query | Expected Behavior |
|----------|-------|-------------------|
| Simple entity lookup | "What is API Gateway?" | Standard pipeline, 1 entity |
| Multi-hop traversal | "Which services are affected by incidents triggered by Network Monitoring?" | RLM pipeline, 2+ hops |
| Aggregation | "How many incidents occurred in Q4?" | RLM pipeline, count aggregation |
| Comparison | "Compare uptime between Auth Service and API Gateway" | RLM pipeline, 2 entities |
| Timeout | Very complex query | Circuit breaker or timeout |

**Acceptance Criteria**:
- [ ] All scenarios pass
- [ ] Latency within targets
- [ ] Correct response modes

---

### Task 5.2: Performance Benchmarks

**File**: `benchmarks/rlm_benchmark.py`

**Metrics**:
- P50/P95/P99 latency
- Token usage per query
- Cost per query
- Iteration count distribution
- Circuit breaker trigger rate

**Benchmark Set**: 50 queries of varying complexity

**Acceptance Criteria**:
- [ ] P95 latency < 30s for complex queries
- [ ] Average cost < $0.50 per complex query
- [ ] Circuit breaker < 10% of queries

---

### Task 5.3: A/B Test Framework

**File**: `src/context_foundry/rlm/ab_test.py`

**Implementation**:
```python
class RLMABTest:
    def __init__(self, rlm_percentage: float = 0.1):
        self.rlm_percentage = rlm_percentage
    
    def route(self, query: str, tenant_id: str) -> str:
        # Hash-based routing for consistency
        if self._should_use_rlm(tenant_id, query):
            return "RLM"
        return "STANDARD"
    
    def record_result(self, route: str, query: str, 
                      accuracy: float, latency_ms: int):
        # Log for analysis
```

**Acceptance Criteria**:
- [ ] Consistent routing per tenant
- [ ] Configurable percentage
- [ ] Results logged for analysis

---

## Test Data Requirements

### Seed Data for Testing

Create test fixtures in `tests/fixtures/rlm_test_data.py`:

1. **10 entities** of various types (SERVICE, INCIDENT, PERSON, TEAM)
2. **20 relationships** connecting them (multi-hop paths available)
3. **5 documents** with chunks containing references to entities
4. **Known paths** for path-finding tests

---

## Configuration Files

### `config/rlm_config.yaml`

```yaml
rlm:
  enabled: true
  routing:
    min_complexity_score: 3
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
  sandbox:
    max_output_length: 10000
```

---

## Rollout Plan

### Week 1-2: Memory APIs
- Deploy to dev
- Unit test coverage > 90%

### Week 3-4: REPL Executor
- Deploy to dev
- Integration tests passing

### Week 5: Sub-Query API
- Cost monitoring in place
- Budget alerts configured

### Week 6: Query Router
- Deploy to staging
- A/B test at 10%

### Week 7-8: Production Rollout
- Gradual rollout 10% → 50% → 100%
- Monitor metrics
- Runbook for issues

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Complex query accuracy | +20% vs standard | Manual eval on 50 queries |
| Evidence citation rate | +15% | Automated citation counting |
| Cost per complex query | < $0.50 | Metering data |
| P95 latency (complex) | < 30s | APM monitoring |
| Circuit breaker rate | < 10% | Execution traces |
