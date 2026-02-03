# Tree-Based Retrieval - Usage Guide

## Overview

Tree-based retrieval extends relationship-first retrieval (currently role-only) to **ALL query types** by treating the knowledge graph as a hierarchical tree rooted at the anchor organization.

**Key Principle:** Answers are ranked by **graph proximity** to the anchor, not just semantic similarity.

---

## Quick Start

### 1. Enable the Feature

Set the environment variable:

```bash
export CF_TREE_BASED_RETRIEVAL=true
```

Or add to your `.env` file:
```
CF_TREE_BASED_RETRIEVAL=true
```

### 2. Use in Code

```python
from src.context_foundry.retrieval import TreeBasedRetriever
from sqlalchemy.orm import Session

# Create retriever
retriever = TreeBasedRetriever(session, tenant_id="your-vault-id")

# Retrieve for any query type
result = retriever.retrieve(
    query="What is the FY2026 capital expenditure?",
    query_type="METRIC",
    max_depth=3
)

# Access results
if result.confidence in ['high', 'medium']:
    for entity in result.entities:
        print(f"{entity['name']} ({entity['entity_type']})")
```

---

## How It Works

### 1. Anchor Identification

The system identifies an anchor entity for every query:

```python
Query: "Who is the CFO?"
→ Anchor: Nexus Industries (vault primary org)

Query: "What is the budget for Falcon X?"
→ Anchor: Falcon X (project entity)

Query: "Revenue of Aerospace Division?"
→ Anchor: Aerospace Division (division entity)
```

### 2. Graph Traversal (BFS)

Starting from the anchor, traverse the graph up to `max_depth` hops:

```
Depth 0: Nexus Industries (anchor)
Depth 1: Michael Chang (CFO), Falcon X (project), Aerospace Division
Depth 2: Financial reports, Toyota JV, CyberShield product
Depth 3: Supplier relationships, specifications
```

### 3. Intent Matching

Filter entities by query intent:

- **Entity type**: PERSON, METRIC, PROJECT, etc.
- **Properties**: fiscal_year=2026, role=CFO
- **Keywords**: budget, revenue, capacity

### 4. Ranking

Results are ranked by combined score:

```
Score = (graph_proximity * 0.7) + (semantic_similarity * 0.3)

Graph proximity:
- Depth 1: 1.0 (direct connection)
- Depth 2: 0.75
- Depth 3: 0.5
```

---

## API Reference

### TreeBasedRetriever

```python
class TreeBasedRetriever:
    def __init__(self, session: Session, tenant_id: str):
        """Initialize with database session and vault ID."""

    def retrieve(
        self,
        query: str,
        query_type: str = "UNKNOWN",
        max_depth: int = 3
    ) -> RetrievalResult:
        """
        Main retrieval method.

        Args:
            query: Natural language question
            query_type: ROLE, METRIC, PROJECT, AGGREGATION, etc.
            max_depth: Maximum graph traversal depth (1-5)

        Returns:
            RetrievalResult with entities, relationships, confidence
        """
```

### RetrievalResult

```python
@dataclass
class RetrievalResult:
    entities: List[Dict[str, Any]]          # Retrieved entities
    relationships: List[Dict[str, Any]]     # Relationships between entities
    confidence: str                         # 'high', 'medium', 'low', 'none'
    method: str                             # 'tree_traversal' or 'semantic_fallback'
    anchor: Optional[Dict[str, Any]]        # Anchor entity used
    max_depth_reached: int                  # Deepest entity found
    total_traversed: int                    # Total entities visited
```

---

## Query Type Examples

### Role Queries

```python
result = retriever.retrieve("Who is the CFO?", query_type="ROLE")
# Returns: Michael Chang (depth 1 from Nexus)
```

### Metric Queries

```python
result = retriever.retrieve(
    "What is the FY2026 capital expenditure?",
    query_type="METRIC"
)
# Traverses: Nexus → Divisions → Budgets → FY2026 capex
```

### Project Queries

```python
result = retriever.retrieve(
    "When is Falcon X launching?",
    query_type="PROJECT"
)
# Anchor: Falcon X project
# Returns: Launch milestones
```

### Aggregation Queries

```python
result = retriever.retrieve(
    "How many employees?",
    query_type="AGGREGATION"
)
# Traverses: Nexus → EMPLOYS → all people → COUNT
```

---

## Configuration

### Feature Flag

```python
from src.context_foundry.config.feature_flags import is_tree_based_retrieval_enabled

if is_tree_based_retrieval_enabled():
    # Use tree-based retrieval
    result = tree_retriever.retrieve(query)
else:
    # Use semantic search
    result = semantic_retriever.retrieve(query)
```

### Traversal Depth

Control how deep the graph traversal goes:

```python
# Shallow (fast, high precision)
result = retriever.retrieve(query, max_depth=1)

# Medium (balanced)
result = retriever.retrieve(query, max_depth=2)

# Deep (comprehensive, slower)
result = retriever.retrieve(query, max_depth=4)
```

**Recommendation:** Start with depth=3 for most queries.

---

## Testing

### Run Unit Tests

```bash
pytest tests/unit/test_tree_retriever.py -v
```

### Run Integration Tests

```bash
# Test on real vault
python -m src.test_runner.runner \
  --vault-id <your-vault-id> \
  --questions src/test_questions/nexus_100q.json
```

### Compare with Baseline

```bash
# Disable tree-based retrieval
export CF_TREE_BASED_RETRIEVAL=false
python -m src.test_runner.runner --vault-id <vault-id> --questions nexus_100q.json

# Enable tree-based retrieval
export CF_TREE_BASED_RETRIEVAL=true
python -m src.test_runner.runner --vault-id <vault-id> --questions nexus_100q.json --force

# Compare results
```

---

## Performance

### Latency

| Depth | Avg Latency | Notes |
|-------|-------------|-------|
| 1 | <100ms | Direct connections only |
| 2 | 100-300ms | Most queries |
| 3 | 200-500ms | Comprehensive |
| 4+ | 500ms-2s | Use sparingly |

### Accuracy Improvement (Expected)

| Query Type | Before | After | Improvement |
|------------|--------|-------|-------------|
| Role | 85% | 98%+ | +13% |
| Metric | 75% | 95%+ | +20% |
| Relationship | 70% | 90%+ | +20% |
| Overall | 87% | 96-100% | +9-13% |

---

## Troubleshooting

### No Results Returned

**Problem:** `result.entities == []`

**Solutions:**
1. Check if anchor was identified: `result.anchor`
2. Increase max_depth: `max_depth=4`
3. Check entity types in intent: Use `'*'` for any type
4. Verify entities exist in database for this tenant

### Low Confidence Results

**Problem:** `result.confidence == 'low'`

**Causes:**
- Only deep results found (depth 3+)
- Low semantic similarity scores
- Anchor not connected to answer

**Solutions:**
1. Review query phrasing
2. Check if data exists in KG
3. Try semantic fallback

### Wrong Anchor Selected

**Problem:** Query uses wrong anchor organization

**Solutions:**
1. Make organization explicit in query: "CFO of Nexus Industries"
2. Check vault primary organization setting
3. Review anchor detection patterns

---

## Best Practices

### 1. Always Set Anchor Context

Encourage users to be explicit:
- ❌ "What is the revenue?"
- ✅ "What is Nexus Industries' revenue?"

### 2. Use Appropriate Depth

- **Depth 1:** Direct connections (roles, immediate properties)
- **Depth 2:** Standard queries (most use cases)
- **Depth 3:** Complex queries (multi-hop relationships)
- **Depth 4+:** Rare (very deep analysis)

### 3. Monitor Performance

Log retrieval metrics:
```python
logger.info(f"[TREE] Query: {query}")
logger.info(f"[TREE] Anchor: {result.anchor['name']}")
logger.info(f"[TREE] Depth reached: {result.max_depth_reached}")
logger.info(f"[TREE] Entities found: {len(result.entities)}")
logger.info(f"[TREE] Confidence: {result.confidence}")
```

### 4. Fallback Gracefully

```python
result = tree_retriever.retrieve(query)

if result.confidence == 'none':
    # Fall back to semantic search
    result = semantic_retriever.retrieve(query)
```

---

## Migration Path

### Phase 1: Shadow Mode (Week 1)

Run both retrievers in parallel, compare:
```python
tree_result = tree_retriever.retrieve(query)
semantic_result = semantic_retriever.retrieve(query)

log_comparison(tree_result, semantic_result)
return tree_result  # Use tree-based
```

### Phase 2: Gradual Rollout (Week 2-3)

Enable for specific query types:
```python
if query_type in ['ROLE', 'METRIC', 'RELATIONSHIP']:
    return tree_retriever.retrieve(query)
else:
    return semantic_retriever.retrieve(query)
```

### Phase 3: Full Rollout (Week 4)

Enable for all vaults:
```bash
export CF_TREE_BASED_RETRIEVAL=true
```

---

## See Also

- [Tree-Based Retrieval Spec](TREE_BASED_RETRIEVAL_SPEC.md) - Full specification
- [Anchor Resolver](../src/context_foundry/retrieval/anchor_resolver.py) - Anchor detection code
- [Intent Extractor](../src/context_foundry/retrieval/intent_extractor.py) - Query intent extraction

---

**Questions?** Check the spec document or review test cases for examples.
