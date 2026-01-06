# RLM Answer Generation Fix — Instructions for Replit

> **Goal**: Make RLM produce measurable value by generating grounded answers, not just exploring
> **Priority**: High — this is blocking demonstration of RLM value
> **Estimated Effort**: 2-3 hours

---

## Problem Statement

RLM is successfully finding entities (20) and relationships (15), but hitting circuit breaker without producing an answer. Returns "Unable to find relevant information" despite having relevant data.

**Current behavior**:
```
Iteration 1: Find 8 entities ✅
Iteration 2: Find 5 more entities, 10 relationships ✅
Iteration 3: Find 7 more entities, 5 relationships ✅
Iteration 4-6: Verify/explore more, no new discoveries
→ Circuit breaker trips
→ Returns "Unable to find relevant information" ❌
```

**Desired behavior**:
```
Iteration 1-3: Explore and discover entities/relationships ✅
Iteration 4: Recognize sufficient data, call FINAL() with synthesized answer ✅
→ Returns grounded answer citing specific entities/relationships ✅
```

---

## Fix 1: Update RLM System Prompt

**File**: `src/context_foundry/rlm/executor.py` (or wherever system prompt is defined)

Add these directives to the system prompt:

```python
RLM_SYSTEM_PROMPT_ADDITIONS = """
## CRITICAL: Answer Generation Rules

1. **Finalize Early**: After 3 iterations of exploration, you MUST attempt to answer.
   - Do NOT keep exploring indefinitely
   - If you have found relevant entities and relationships, synthesize an answer
   - Use FINAL(your_answer) to provide your response

2. **Progress Check**: At each iteration, ask yourself:
   - "Do I have enough information to answer the original query?"
   - If YES → Call FINAL() immediately
   - If NO → Continue ONE more exploration step, then reassess

3. **Answer Structure**: Your final answer should:
   - Name specific entities you found (by name, not ID)
   - Describe the relationships between them
   - Directly address the original query
   - Cite confidence based on evidence found

4. **When to Stop Exploring**:
   - You found entities matching the query subject ✓
   - You found relationships connecting them ✓
   - Additional searches return entities you've already seen ✓
   → STOP and synthesize answer

5. **No Data Found**: If after 3 iterations you genuinely found nothing relevant:
   - Call FINAL("No relevant information found in the knowledge base for: [query]")
   - Do NOT keep searching hoping something appears

## Example Good Behavior

Query: "What services depend on Checkout Service?"

Iteration 1:
```python
checkout = semantic.find_similar("Checkout Service", k=5, entity_type="SERVICE")
print(f"Found: {[e.name for e in checkout]}")
# Found: ['Checkout Service', 'Checkout API', ...]
```

Iteration 2:
```python
# Get the main entity
checkout_svc = checkout[0]
deps = symbolic.get_relationships(checkout_svc.id, direction="incoming", relationship_type="DEPENDS_ON")
print(f"Services depending on Checkout: {[r.source_entity_name for r in deps]}")
# Services depending on Checkout: ['Payment Gateway', 'Order Service', 'Cart Service']
```

Iteration 3:
```python
# I have the answer! Finalize now.
dependent_services = [r.source_entity_name for r in deps]
FINAL(f"The following services depend on Checkout Service: {', '.join(dependent_services)}")
```

## Example Bad Behavior (DO NOT DO THIS)

Iteration 3: Found 3 dependent services
Iteration 4: Search for more services just in case...
Iteration 5: Verify each service exists...
Iteration 6: Search for related incidents...
→ Circuit breaker, no answer provided

The problem: You had the answer at iteration 3 but kept exploring!
"""
```

---

## Fix 2: Improve Circuit Breaker Logic

**File**: `src/context_foundry/rlm/executor.py`

Current logic trips breaker after N iterations with no new discoveries. This is wrong because:
- LLM might have enough data but is "verifying"
- Should trip only if no progress AND no FINAL() call attempted

**Change**:

```python
class RLMExecutor:
    def __init__(self, ...):
        self.max_iterations = 10  # Hard limit
        self.max_no_progress_iterations = 3  # Soft limit for no new discoveries
        self.min_iterations_before_breaker = 3  # Don't trip before this
    
    def _should_trip_breaker(self, progress_tracker, iteration: int) -> bool:
        """Decide if circuit breaker should trip."""
        # Never trip before minimum iterations
        if iteration < self.min_iterations_before_breaker:
            return False
        
        # Trip if no progress for N consecutive iterations
        if progress_tracker.iterations_without_progress >= self.max_no_progress_iterations:
            return True
        
        return False
    
    def _handle_circuit_breaker(self, result: RLMExecutionResult) -> dict:
        """When breaker trips, synthesize answer from discovered data instead of failing."""
        
        if result.entities_discovered or result.relationships_discovered:
            # We have data! Synthesize an answer instead of returning "unable to find"
            return self._synthesize_answer_from_discoveries(result)
        else:
            # Genuinely found nothing
            return {
                "answer": "No relevant information found in the knowledge base.",
                "confidence": 0.0,
                "response_mode": "NOT_FOUND"
            }
    
    def _synthesize_answer_from_discoveries(self, result: RLMExecutionResult) -> dict:
        """Use sub-query to synthesize answer from discovered entities/relationships."""
        
        # Build context from discoveries
        entity_summary = "\n".join([
            f"- {e.name} ({e.entity_type})" 
            for e in result.entities_discovered[:20]  # Limit for context
        ])
        
        relationship_summary = "\n".join([
            f"- {r.source_entity_name} --[{r.relationship_type}]--> {r.target_entity_name}"
            for r in result.relationships_discovered[:20]
        ])
        
        synthesis_prompt = f"""Based on the following discovered entities and relationships, 
answer the original query: "{result.original_query}"

ENTITIES FOUND:
{entity_summary}

RELATIONSHIPS FOUND:
{relationship_summary}

Provide a concise answer that:
1. Directly addresses the query
2. References specific entities by name
3. Explains the relationships between them
4. Acknowledges if the information is incomplete

Answer:"""
        
        # Use sub-query API to synthesize
        synthesized_answer = self.sub_query_api.query(synthesis_prompt, max_tokens=500)
        
        return {
            "answer": synthesized_answer,
            "confidence": 0.7,  # Medium confidence for synthesized answers
            "response_mode": "PARTIAL_ANSWER",
            "synthesis_note": "Answer synthesized from discovered entities after circuit breaker"
        }
```

---

## Fix 3: Add Iteration Limit Warning to LLM

**File**: `src/context_foundry/rlm/executor.py`

Inject a warning into the LLM context as iterations approach limit:

```python
def _build_iteration_context(self, iteration: int, max_iterations: int) -> str:
    """Build context string warning LLM about iteration limits."""
    
    remaining = max_iterations - iteration
    
    if remaining <= 2:
        return f"""
⚠️ WARNING: You have {remaining} iteration(s) remaining before automatic timeout.
You MUST call FINAL() with your answer in the next iteration.
If you have found relevant entities/relationships, synthesize your answer NOW.
"""
    elif remaining <= 4:
        return f"""
Note: {remaining} iterations remaining. Consider finalizing soon if you have sufficient data.
"""
    else:
        return ""
```

Inject this into each iteration's prompt.

---

## Fix 4: Lower Router Threshold

**File**: `src/context_foundry/rlm/router.py`

Current threshold (0.19) is too high — complex queries like "Which services are affected by incidents triggered by X" only score 0.1.

**Change**:

```python
class QueryComplexityRouter:
    # Lower threshold to catch more complex queries
    COMPLEXITY_THRESHOLD = 0.10  # Was 0.19
    
    # Add explicit pattern matches that force RLM routing
    FORCE_RLM_PATTERNS = [
        r"affected by.*triggered",
        r"triggered by.*affected",
        r"depend(?:s|ing)? on.*and",
        r"trace.*from.*to",
        r"chain.*from.*to",
        r"what.*incidents.*services",
        r"which.*services.*incidents",
        r"compare.*across",
        r"all.*that.*have",
    ]
    
    def route(self, query: str) -> QueryRoute:
        # Check forced patterns first
        query_lower = query.lower()
        for pattern in self.FORCE_RLM_PATTERNS:
            if re.search(pattern, query_lower):
                return QueryRoute(tier="tier2", reason=f"Matched pattern: {pattern}")
        
        # Fall back to complexity scoring
        score = self._calculate_complexity(query)
        if score >= self.COMPLEXITY_THRESHOLD:
            return QueryRoute(tier="tier2", reason=f"Complexity score: {score}")
        
        return QueryRoute(tier="tier1", reason=f"Simple query (score: {score})")
```

---

## Testing Plan

### Test 1: Basic RLM Answer Generation

```python
from context_foundry.core import ContextFoundry

cf = ContextFoundry(tenant_id="f3dd3201-7225-4a55-9264-445f99d0eba3")

# Force RLM
result = cf.query(
    "What services depend on Checkout Service?",
    force_tier="tier2"
)

# Assertions
assert result["answer"] != "Unable to find relevant information"
assert "Checkout" in result["answer"] or len(result.get("entities_discovered", [])) > 0
assert result.get("confidence", 0) > 0
print(f"✅ Answer: {result['answer']}")
print(f"✅ Entities: {len(result.get('entities_discovered', []))}")
print(f"✅ Relationships: {len(result.get('relationships_discovered', []))}")
```

### Test 2: Auto-Routing Complex Query

```python
# This should auto-route to RLM with the new patterns
result = cf.query(
    "Which services are affected by incidents triggered by Network Monitoring Service?"
)

assert result.get("tier") == "tier2_rlm", f"Expected tier2, got {result.get('tier')}"
assert result["answer"] != "Unable to find relevant information"
print(f"✅ Routed to: {result.get('tier')}")
print(f"✅ Answer: {result['answer']}")
```

### Test 3: Synthesized Answer on Circuit Breaker

```python
# Query that might hit circuit breaker but should still produce answer
result = cf.query(
    "List all the relationships for Payment Gateway service",
    force_tier="tier2"
)

# Even if circuit breaker trips, should have synthesized answer
assert "Payment" in result["answer"] or result.get("synthesis_note") is not None
print(f"✅ Status: {result.get('status')}")
print(f"✅ Answer: {result['answer']}")
```

### Test 4: Tier 1 vs Tier 2 Comparison

```python
query = "What services are connected to the Database Cluster?"

tier1 = cf.query(query, force_tier="tier1")
tier2 = cf.query(query, force_tier="tier2")

print("=== TIER 1 (Standard) ===")
print(f"Answer: {tier1['answer']}")
print(f"Confidence: {tier1.get('confidence')}")

print("\n=== TIER 2 (RLM) ===")
print(f"Answer: {tier2['answer']}")
print(f"Confidence: {tier2.get('confidence')}")
print(f"Entities discovered: {len(tier2.get('entities_discovered', []))}")
print(f"Relationships discovered: {len(tier2.get('relationships_discovered', []))}")

# RLM should provide more grounded answer
print("\n✅ Compare answers manually for quality difference")
```

---

## Success Criteria

| Metric | Before | After |
|--------|--------|-------|
| RLM produces answer | ❌ "Unable to find" | ✅ Grounded answer |
| Complex queries route to RLM | ❌ Score too low | ✅ Pattern matching works |
| Circuit breaker with data | ❌ Returns failure | ✅ Synthesizes answer |
| Entities cited in answer | ❌ None | ✅ Specific names mentioned |
| Confidence > 0 | ❌ 0.0 | ✅ 0.5-0.9 based on evidence |

---

## Files to Modify

1. `src/context_foundry/rlm/executor.py`
   - Update system prompt
   - Add iteration limit warning
   - Add `_handle_circuit_breaker()` with synthesis
   - Add `_synthesize_answer_from_discoveries()`

2. `src/context_foundry/rlm/router.py`
   - Lower threshold to 0.10
   - Add `FORCE_RLM_PATTERNS` list
   - Update `route()` to check patterns first

3. `tests/rlm/test_integration.py`
   - Add tests from Testing Plan above

---

## After Implementation

Run the full test suite:
```bash
pytest tests/rlm/ -v
```

Then run the demo comparison:
```python
# Full comparison script
python -c "
from context_foundry.core import ContextFoundry
cf = ContextFoundry(tenant_id='f3dd3201-7225-4a55-9264-445f99d0eba3')

queries = [
    'What services depend on Checkout Service?',
    'Which services are affected by incidents triggered by Network Monitoring?',
    'Trace dependencies from Database Cluster to frontend services',
]

for q in queries:
    print(f'\n=== Query: {q} ===')
    r = cf.query(q, force_tier='tier2')
    print(f'Answer: {r[\"answer\"][:200]}...')
    print(f'Entities: {len(r.get(\"entities_discovered\", []))}')
    print(f'Relationships: {len(r.get(\"relationships_discovered\", []))}')
    print(f'Confidence: {r.get(\"confidence\")}')
"
```

---

## Questions for Saleh (if any blockers)

1. Should synthesized answers have lower confidence ceiling (e.g., max 0.7)?
2. For pattern matching, should "incidents" always force RLM regardless of other words?
3. Acceptable cost per RLM query? Current: ~$0.23 with 6 iterations.
