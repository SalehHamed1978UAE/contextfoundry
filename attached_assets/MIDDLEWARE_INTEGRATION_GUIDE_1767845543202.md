# Precedent Middleware Integration Guide

## What This Is

The **Precedent Middleware** completes the Context Graph by adding "look before you leap" behavior to all agent decisions. This is the missing piece that turns DTL from a logging system into a learning system.

## Files to Upload

1. `precedent_middleware.py` - The middleware module
2. `test_precedent_middleware.py` - Tests for the middleware
3. `test_dtl_e2e.py` - End-to-end DTL tests (if not already uploaded)

## Installation

1. Upload `precedent_middleware.py` to `src/decision_trace_layer/`
2. Upload test files to `tests/` or project root

## Usage Options

### Option 1: Convenience Function (Simplest)

For one-off decisions:

```python
from src.decision_trace_layer.precedent_middleware import decide_with_context

result = decide_with_context(
    tenant_id="your-tenant-id",
    decision_maker_id="your-agent-id",
    situation="Customer Acme wants 25% discount, ARR $350K, high churn risk",
    decision_type="discount_approval",
    default_decision=lambda: {
        "choice": {"approved": True, "discount": 20},
        "rationale": "Default policy: max 20% without precedent"
    },
    adapt_from_precedent=lambda p: {
        "choice": p.choice,  # Use the precedent's choice
        "rationale": f"Following precedent: {p.summary}"
    }
)

print(f"Decision: {result.choice}")
print(f"Followed precedent: {result.precedent_followed}")
```

### Option 2: Middleware Instance (More Control)

For repeated decisions:

```python
from src.decision_trace_layer.precedent_middleware import PrecedentMiddleware

middleware = PrecedentMiddleware(
    tenant_id="your-tenant-id",
    decision_maker_id="your-agent-id"
)

def my_decide_fn(precedents):
    if precedents and precedents[0].score > 0.7:
        return {
            "choice": precedents[0].choice,
            "rationale": f"Following: {precedents[0].summary}",
            "followed_precedent_id": precedents[0].decision_id
        }
    else:
        return {
            "choice": {"my": "decision"},
            "rationale": "No strong precedent",
            "deviated_from_id": precedents[0].decision_id if precedents else None,
            "deviation_reason": "Score below threshold"
        }

result = middleware.decide_with_precedents(
    situation="Description of current situation",
    decision_type="my_decision_type",
    decide_fn=my_decide_fn
)
```

### Option 3: Decorator Pattern (Cleanest)

For functions that make decisions:

```python
from src.decision_trace_layer.precedent_middleware import PrecedentMiddleware

middleware = PrecedentMiddleware(tenant_id, decision_maker_id)

@middleware.with_precedents(decision_type="query_routing")
def route_query(query: str, *, precedents, context):
    """
    precedents: List[Precedent] - automatically injected
    context: DecisionContext - for tracking
    """
    
    if precedents and precedents[0].score > 0.7:
        # Follow precedent
        middleware.follow(
            precedent_id=precedents[0].decision_id,
            choice={"tier": precedents[0].choice.get("tier")},
            rationale=f"Following precedent for similar query"
        )
        return precedents[0].choice.get("tier")
    else:
        # Make own decision
        tier = "TIER1_SIMPLE" if len(query) < 50 else "TIER2_RLM"
        middleware.deviate(
            precedent_id=precedents[0].decision_id if precedents else None,
            reason="No strong match",
            choice={"tier": tier},
            rationale="Using complexity heuristic"
        )
        return tier

# Usage - precedents automatically queried and decision logged
tier = route_query("What services depend on Auth?")
```

## Integration Points in CF

Here's where to add precedent checks in the existing CF agent flow:

### 1. Query Router (`src/agents/query_router.py` or similar)

```python
# BEFORE (current)
def route_query(query: str) -> str:
    complexity = calculate_complexity(query)
    return "TIER2_RLM" if complexity > 0.5 else "TIER1_SIMPLE"

# AFTER (with precedents)
@middleware.with_precedents(decision_type="query_routing")
def route_query(query: str, *, precedents, context) -> str:
    if precedents and precedents[0].score > 0.7:
        middleware.follow(precedents[0].decision_id, 
                         precedents[0].choice, 
                         f"Following: {precedents[0].summary}")
        return precedents[0].choice.get("tier", "TIER1_SIMPLE")
    
    complexity = calculate_complexity(query)
    tier = "TIER2_RLM" if complexity > 0.5 else "TIER1_SIMPLE"
    middleware.deviate(precedents[0].decision_id if precedents else None,
                      "Low similarity score",
                      {"tier": tier}, 
                      f"Complexity: {complexity}")
    return tier
```

### 2. Entity Resolution

```python
@middleware.with_precedents(decision_type="entity_resolution")
def resolve_entity(name: str, candidates: list, *, precedents, context):
    # Check if we've resolved this ambiguity before
    if precedents and precedents[0].score > 0.8:
        return precedents[0].choice.get("resolved_entity")
    
    # Normal resolution logic
    best = max(candidates, key=lambda c: c.similarity)
    middleware.deviate(None, "Novel resolution", 
                      {"resolved_entity": best.id}, 
                      f"Best match: {best.similarity}")
    return best.id
```

### 3. Sufficiency Assessment

```python
@middleware.with_precedents(decision_type="sufficiency_assessment")
def assess_sufficiency(query: str, context: str, *, precedents, context):
    if precedents and precedents[0].score > 0.75:
        return precedents[0].choice.get("sufficiency")
    
    # Normal assessment
    ...
```

## Running Tests

```bash
# Set environment
export CF_API_KEY="your-api-key"
export DTL_BASE_URL="http://localhost:5000"

# Run middleware tests
python test_precedent_middleware.py

# Run full DTL tests
python test_dtl_e2e.py
```

## Expected Test Output

```
PRECEDENT MIDDLEWARE TEST SUITE
============================================================
TEST: 1. Middleware Creation
============================================================
✅ PASS: Middleware created successfully

TEST: 2. Retrieve Precedents
============================================================
ℹ️  Found 5 precedents
ℹ️    1. Approved 25% discount for Enterprise customer... (score: 0.823)
✅ PASS: Precedent retrieval works

... more tests ...

Results: 8 passed, 0 failed

🎉 ALL MIDDLEWARE TESTS PASSED!

The 'look before you leap' pattern is working.
Agents can now query precedents before making decisions.
```

## What Success Looks Like

After integration:

1. **Every decision queries precedents first**
2. **Strong matches are followed** (or explicitly deviated with reason)
3. **All decisions are logged with citations**
4. **The system learns from itself** - new decisions become precedents for future decisions

## Monitoring

Track these metrics to verify value:

| Metric | What It Tells You |
|--------|-------------------|
| Precedent query rate | Are agents actually checking? |
| Strong match rate (>0.7) | Is the system finding relevant precedents? |
| Follow rate | How often are precedents being followed? |
| Deviation reasons | Why are agents deviating? |

Query example:
```sql
SELECT 
    decision_type,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE context_snapshot->>'precedent_followed' = 'true') as followed,
    COUNT(*) FILTER (WHERE context_snapshot->>'deviated_from' IS NOT NULL) as deviated
FROM decision_traces
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY decision_type;
```
