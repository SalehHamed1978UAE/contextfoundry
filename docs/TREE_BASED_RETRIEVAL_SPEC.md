# Tree-Based Retrieval: Complete Specification

**Version:** 1.0.0
**Date:** February 4, 2026
**Status:** Design Specification
**Target:** Post Phase 3 Ontology Integration

---

## Executive Summary

**Problem:** Current retrieval uses flat semantic search that often prioritizes document text over knowledge graph relationships, causing wrong entities to be selected even when correct data exists in the KG.

**Solution:** Extend relationship-first retrieval (currently role-only) to ALL query types by treating the knowledge graph as a hierarchical tree rooted at the anchor organization, with retrieval prioritizing graph proximity over semantic similarity.

**Expected Impact:** +8-12 percentage points accuracy (88% → 96-100%)

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Core Concept](#2-core-concept)
3. [Architecture](#3-architecture)
4. [Implementation Plan](#4-implementation-plan)
5. [Query Type Coverage](#5-query-type-coverage)
6. [Ranking Algorithm](#6-ranking-algorithm)
7. [Integration Points](#7-integration-points)
8. [Testing & Validation](#8-testing--validation)
9. [Rollout Strategy](#9-rollout-strategy)
10. [Success Criteria](#10-success-criteria)

---

## 1. Problem Statement

### Current Behavior (Flat Semantic Search)

```
Query: "What is the FY2026 capex?"

Current Flow:
1. Embed query → vector(1536)
2. Search document_chunks by cosine similarity
3. Retrieve top-K chunks (regardless of relevance to anchor org)
4. LLM generates answer from chunks
5. Problem: Wrong fiscal year data or wrong organization data retrieved
```

**Root Causes (from 87% failure analysis):**

| Issue | Description | Example Failures |
|-------|-------------|------------------|
| **Retrieval Ranking** | Correct data exists but wrong entities selected | Q66 (capex), Q79 (revenue target) |
| **Document > KG** | Document text preferred over graph relationships | Q45 (CEO appointment date) |
| **Semantic Collapse** | Similar text scores equally despite org mismatch | Q14 (wrong Robert Kim), Q32 (wrong CEO) |

### What's Already Built

✅ **AnchorResolver** - Detects primary organization via graph centrality
✅ **RelationshipFirstRetriever** - Traverses from anchor for **role queries only**
❌ **Tree-based retrieval for ALL query types** - NOT IMPLEMENTED

---

## 2. Core Concept

### Hierarchical Graph Traversal

**Treat the KG as a tree, not a flat property store.**

```
                    Nexus Industries (Anchor)
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
    [PEOPLE]          [PROJECTS]         [DIVISIONS]
        │                  │                  │
   Michael Chang      Falcon X UAV      Aerospace Division
   (CFO - depth 1)   (budget - depth 1)  (revenue - depth 1)
        │                  │                  │
   [REPORTS]          [PARTNERS]         [PRODUCTS]
        │                  │                  │
   Financial Docs     Toyota JV          CyberShield
   (depth 2)         (depth 2)          (depth 2)
```

**Key Principle:** Answers are ranked by **graph distance from anchor**, not just semantic similarity.

---

## 3. Architecture

### Three-Tier Retrieval System

```python
class TreeBasedRetriever:
    """
    Hierarchical retrieval prioritizing graph proximity over semantics.

    Retrieval tiers (in priority order):
    1. GRAPH_TIER: Entities/relationships reachable from anchor (depth 1-3)
    2. HYBRID_TIER: Graph + semantic fusion for complex queries
    3. FALLBACK_TIER: Pure semantic search with low confidence marker
    """
```

### Retrieval Priority

```
Priority 1: Direct connections (depth 1)
  anchor → LEADS → person
  anchor → HAS_PROJECT → project
  anchor → HAS_DIVISION → division

Priority 2: Two-hop connections (depth 2)
  anchor → HAS_DIVISION → division → HAS_REVENUE → metric
  anchor → HAS_PROJECT → project → PARTNERED_WITH → company

Priority 3: Three-hop connections (depth 3)
  anchor → HAS_DIVISION → division → HAS_PRODUCT → product → HAS_SPEC → spec

Priority 4: Semantic search (fallback)
  - Use ONLY if graph traversal returns no results
  - Mark answer as LOW CONFIDENCE
  - Route through Data Gate
```

---

## 4. Implementation Plan

### Step 1: Extend AnchorResolver (Week 1)

**Current:** Only used for role queries
**Target:** Used for ALL queries

```python
class AnchorResolver:
    """Enhanced to support all query types."""

    def identify_anchor_for_any_query(self, query: str, query_type: str) -> Dict:
        """
        Identify anchor for any query type, not just roles.

        Examples:
        - "What is Nexus's revenue?" → explicit anchor (Nexus)
        - "How many employees?" → vault primary org (implicit)
        - "What is the budget for Falcon X?" → scoped to Falcon X entity
        """
        # Check for explicit org mention
        explicit_org = self._extract_organization_from_query(query)
        if explicit_org:
            return self._find_entity_by_name(explicit_org)

        # Check for entity-scoped query (e.g., "budget for Falcon X")
        entity_mention = self._extract_entity_from_query(query)
        if entity_mention:
            entity = self._find_entity_by_name(entity_mention)
            if entity and entity['entity_type'] in ['PROJECT', 'PRODUCT', 'DIVISION']:
                return entity  # Use this as traversal starting point

        # Default to vault primary org
        return self.get_primary_organization()
```

**New Methods:**

```python
def _extract_entity_from_query(self, query: str) -> Optional[str]:
    """
    Extract any named entity from query, not just organizations.

    Patterns:
    - "budget for Falcon X"
    - "CEO of Toyota JV"
    - "supplier for GreenHydrogen"
    """
    patterns = [
        r"(?:for|of|in)\s+([A-Z][A-Za-z\s]+?)(?:\?|$|,)",
        r"([A-Z][A-Za-z\s]+?)'s\s+(?:budget|revenue|CEO|capacity)",
    ]
    # ... implementation
```

---

### Step 2: Create TreeBasedRetriever (Week 1-2)

**New File:** `src/context_foundry/retrieval/tree_retriever.py`

```python
class TreeBasedRetriever:
    """
    Hierarchical entity retrieval via graph traversal.

    Extends RelationshipFirstRetriever to support all query types.
    """

    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.anchor_resolver = AnchorResolver(session, tenant_id)

    def retrieve(
        self,
        query: str,
        query_type: str,
        max_depth: int = 3
    ) -> RetrievalResult:
        """
        Main retrieval method for all query types.

        Args:
            query: User question
            query_type: ROLE, METRIC, RELATIONSHIP, AGGREGATION, etc.
            max_depth: Maximum graph traversal depth (default 3)

        Returns:
            RetrievalResult with entities, relationships, confidence
        """
        # Step 1: Identify anchor
        anchor = self.anchor_resolver.identify_anchor_for_any_query(query, query_type)
        if not anchor:
            return self._fallback_semantic_search(query)

        # Step 2: Extract query intent (what are we looking for?)
        intent = self._extract_query_intent(query, query_type)

        # Step 3: Traverse graph from anchor
        results = self._traverse_from_anchor(
            anchor=anchor,
            intent=intent,
            max_depth=max_depth
        )

        # Step 4: Rank by graph proximity + semantic relevance
        ranked = self._rank_results(results, query)

        # Step 5: Return with confidence
        if ranked:
            return RetrievalResult(
                entities=ranked,
                confidence="high" if ranked[0]['depth'] <= 2 else "medium",
                method="tree_traversal",
                anchor=anchor
            )

        # Fallback to semantic search
        return self._fallback_semantic_search(query)
```

**Core Traversal Logic:**

```python
def _traverse_from_anchor(
    self,
    anchor: Dict,
    intent: QueryIntent,
    max_depth: int
) -> List[Dict]:
    """
    BFS traversal from anchor entity.

    Returns all entities reachable within max_depth hops,
    filtered by intent (entity type, relationship type, properties).
    """
    visited = set()
    queue = [(anchor['id'], 0)]  # (entity_id, depth)
    results = []

    while queue:
        entity_id, depth = queue.pop(0)

        if entity_id in visited or depth > max_depth:
            continue

        visited.add(entity_id)

        # Get entity details
        entity = self._get_entity_details(entity_id)

        # Check if entity matches intent
        if self._matches_intent(entity, intent, depth):
            results.append({
                'entity': entity,
                'depth': depth,
                'path': []  # TODO: track path for provenance
            })

        # Get connected entities (only if depth < max_depth)
        if depth < max_depth:
            connected = self._get_connected_entities(
                entity_id,
                intent.relationship_types
            )
            for conn in connected:
                queue.append((conn['id'], depth + 1))

    return results
```

---

### Step 3: Query Intent Extraction (Week 2)

**New Class:** `QueryIntent`

```python
@dataclass
class QueryIntent:
    """Structured representation of what the query is asking for."""

    # What type of entity are we looking for?
    target_entity_types: List[str]  # ['PERSON', 'METRIC', 'PROJECT']

    # What relationships should we traverse?
    relationship_types: List[str]  # ['HAS_REVENUE', 'HAS_BUDGET', 'LEADS']

    # What properties should entities have?
    property_filters: Dict[str, Any]  # {'fiscal_year': '2026', 'metric_type': 'revenue'}

    # What's the question type?
    question_type: str  # 'who', 'what', 'when', 'how_many', 'which'

    # Semantic context for ranking
    semantic_keywords: List[str]  # ['revenue', 'FY2026', 'target']
```

**Intent Extractor:**

```python
class IntentExtractor:
    """Extract structured intent from natural language queries."""

    QUERY_TYPE_PATTERNS = {
        'ROLE': {
            'patterns': [r'who is the', r'who (?:leads|manages|heads)', r'name of the'],
            'entity_types': ['PERSON'],
            'relationship_types': ['LEADS', 'MANAGES', 'HAS_ROLE', 'HOLDS_POSITION']
        },
        'METRIC': {
            'patterns': [r'what is the (?:revenue|budget|capacity|cost)', r'how much'],
            'entity_types': ['METRIC', 'FINANCIAL_DATA', 'SPECIFICATION'],
            'relationship_types': ['HAS_REVENUE', 'HAS_BUDGET', 'HAS_METRIC', 'HAS_SPEC']
        },
        'PROJECT': {
            'patterns': [r'when is .* launching', r'what is the .* project'],
            'entity_types': ['PROJECT', 'INITIATIVE', 'PROGRAM'],
            'relationship_types': ['HAS_PROJECT', 'MANAGES', 'WORKS_ON']
        },
        'AGGREGATION': {
            'patterns': [r'how many', r'total (?:value|count)', r'which has the (?:most|largest|highest)'],
            'entity_types': ['*'],  # Any type
            'relationship_types': ['*'],
            'requires_aggregation': True
        }
    }

    def extract(self, query: str, query_type: str) -> QueryIntent:
        """Extract intent from query."""
        # Get base patterns for query type
        patterns = self.QUERY_TYPE_PATTERNS.get(query_type, {})

        # Extract entity types to look for
        target_entity_types = patterns.get('entity_types', ['*'])

        # Extract relationship types to traverse
        relationship_types = patterns.get('relationship_types', [])

        # Extract property filters (fiscal year, metric type, etc.)
        property_filters = self._extract_property_filters(query)

        # Extract question type
        question_type = self._extract_question_type(query)

        # Extract semantic keywords for ranking
        semantic_keywords = self._extract_keywords(query)

        return QueryIntent(
            target_entity_types=target_entity_types,
            relationship_types=relationship_types,
            property_filters=property_filters,
            question_type=question_type,
            semantic_keywords=semantic_keywords
        )
```

---

### Step 4: Ranking Algorithm (Week 2-3)

**Hybrid Ranking:** Graph proximity + Semantic relevance

```python
def _rank_results(
    self,
    results: List[Dict],
    query: str
) -> List[Dict]:
    """
    Rank results by graph proximity and semantic relevance.

    Score = (graph_score * 0.7) + (semantic_score * 0.3)

    Graph Score:
    - Depth 1: 1.0
    - Depth 2: 0.75
    - Depth 3: 0.5

    Semantic Score:
    - Cosine similarity of entity embedding vs query embedding
    """
    query_embedding = self._get_embedding(query)

    for result in results:
        entity = result['entity']
        depth = result['depth']

        # Graph proximity score (higher is better, closer to anchor)
        graph_score = 1.0 - (depth * 0.25)  # Depth 1=1.0, 2=0.75, 3=0.5

        # Semantic similarity score
        entity_embedding = entity.get('embedding')
        semantic_score = self._cosine_similarity(query_embedding, entity_embedding)

        # Combined score (graph weighted higher)
        combined_score = (graph_score * 0.7) + (semantic_score * 0.3)

        result['graph_score'] = graph_score
        result['semantic_score'] = semantic_score
        result['combined_score'] = combined_score

    # Sort by combined score (descending)
    results.sort(key=lambda x: x['combined_score'], reverse=True)

    return results
```

---

## 5. Query Type Coverage

### Mapping Query Types to Traversal Strategies

| Query Type | Example | Anchor | Traversal Path | Target Entity |
|------------|---------|--------|----------------|---------------|
| **ROLE** | Who is the CFO? | Nexus Industries | anchor → LEADS → person | PERSON |
| **METRIC** | What is FY2026 revenue? | Nexus Industries | anchor → HAS_REVENUE → metric | METRIC |
| **PROJECT** | When is Falcon X launching? | Falcon X | project → HAS_MILESTONE → date | PROJECT |
| **RELATIONSHIP** | Who supplies electrolyzers? | GreenHydrogen | project → SUPPLIER_OF → company | ORGANIZATION |
| **AGGREGATION** | How many employees? | Nexus Industries | anchor → EMPLOYS → person → COUNT | PERSON |
| **COMPARISON** | Which division has highest revenue? | Nexus Industries | anchor → HAS_DIVISION → division → HAS_REVENUE → MAX | DIVISION |
| **TEMPORAL** | When did Victoria Chen become CEO? | Victoria Chen | person → HOLDS_POSITION → role → temporal_start | RELATIONSHIP |

---

## 6. Integration Points

### 6.1 Query Pipeline Integration

**Current Flow:**
```
Query → QueryClassifier → RetrievalRouter → retrieve() → LLM → Answer
```

**Enhanced Flow:**
```
Query → QueryClassifier → RetrievalRouter → TreeBasedRetriever.retrieve() → LLM → Answer
                                                      ↓
                                            [GRAPH_TIER: depth 1-3]
                                                      ↓
                                            [FALLBACK: semantic if empty]
```

**File:** `src/context_foundry/agents/retrieval_router.py`

```python
class RetrievalRouter:
    """Enhanced to use tree-based retrieval by default."""

    def route(self, query: str, query_type: str) -> RetrievalResult:
        # NEW: Always try tree-based retrieval first
        if self.config.use_tree_based_retrieval:  # Feature flag
            tree_retriever = TreeBasedRetriever(self.session, self.tenant_id)
            result = tree_retriever.retrieve(query, query_type)

            if result.confidence in ['high', 'medium']:
                return result

        # FALLBACK: Old semantic search
        return self._semantic_search(query)
```

---

### 6.2 ToolAgent Integration

**File:** `src/context_foundry/agents/tool_agent.py`

Add new tree-based retrieval tool:

```python
{
    "name": "traverse_from_entity",
    "description": "Traverse the knowledge graph from a specific entity to find connected information",
    "parameters": {
        "entity_name": "Name of the entity to start from",
        "relationship_types": "List of relationship types to follow",
        "max_depth": "Maximum traversal depth (default 3)"
    }
}
```

---

## 7. Testing & Validation

### 7.1 Unit Tests

**File:** `tests/unit/test_tree_retriever.py`

```python
def test_depth_1_retrieval():
    """Test direct connections are retrieved correctly."""
    retriever = TreeBasedRetriever(session, vault_id)
    anchor = {"id": "nexus-id", "name": "Nexus Industries"}

    # Query: "Who is the CFO?"
    intent = QueryIntent(
        target_entity_types=['PERSON'],
        relationship_types=['LEADS', 'HAS_EXECUTIVE'],
        property_filters={'role': 'CFO'}
    )

    results = retriever._traverse_from_anchor(anchor, intent, max_depth=1)

    assert len(results) > 0
    assert results[0]['entity']['name'] == 'Michael Chang'
    assert results[0]['depth'] == 1

def test_depth_2_retrieval():
    """Test two-hop connections."""
    # Query: "What is the Aerospace Division revenue?"
    # Path: Nexus → HAS_DIVISION → Aerospace → HAS_REVENUE → $XX

def test_fallback_to_semantic():
    """Test semantic search fallback when graph has no answer."""
    # Query about entity not in graph
    # Should fall back to document search with low confidence

def test_ranking_prioritizes_depth():
    """Test that depth 1 results rank higher than depth 3."""
```

---

### 7.2 Integration Tests

**File:** `tests/integration/test_tree_based_pipeline.py`

```python
def test_end_to_end_role_query():
    """Test full pipeline for role query."""
    query = "Who is the CFO of Nexus Industries?"
    answer = query_pipeline.answer(query, vault_id)

    assert answer.confidence == "high"
    assert answer.method == "tree_traversal"
    assert "Michael Chang" in answer.text

def test_end_to_end_metric_query():
    """Test full pipeline for metric query."""
    query = "What is the FY2026 capital expenditure plan?"
    answer = query_pipeline.answer(query, vault_id)

    assert answer.confidence in ["high", "medium"]
    assert answer.method == "tree_traversal"
    # Should return correct FY2026 value, not FY2025
```

---

### 7.3 Regression Testing

**Run full 100-question test suite:**

```bash
python -m src.test_runner.runner \
  --vault-id <vault_id> \
  --questions src/test_questions/nexus_100q.json \
  --force
```

**Expected Results:**

| Metric | Before (87%) | After (Target) | Improvement |
|--------|--------------|----------------|-------------|
| Overall Accuracy | 87% | 96-100% | +9-13 points |
| Role Query Accuracy | 85% | 98-100% | +13-15 points |
| Metric Query Accuracy | 75% | 95-100% | +20-25 points |
| Graph Traversal Used | 20% | 80%+ | +60 points |
| MISMATCH Failures | 9 | 0-2 | -7-9 |
| NOT_FOUND Failures | 4 | 0-2 | -2-4 |

---

## 8. Rollout Strategy

### Phase 1: Feature Flag (Week 3)

Add configuration flag to enable/disable tree-based retrieval:

```python
# config/app_config.py
TREE_BASED_RETRIEVAL_ENABLED = os.getenv('TREE_BASED_RETRIEVAL', 'false').lower() == 'true'
```

**Benefit:** Can A/B test tree vs semantic retrieval

---

### Phase 2: Shadow Mode (Week 4)

Run both retrievers in parallel, compare results:

```python
def retrieve_with_comparison(query, query_type):
    # Run both
    tree_result = tree_retriever.retrieve(query, query_type)
    semantic_result = semantic_retriever.retrieve(query)

    # Log differences
    log_retrieval_comparison(tree_result, semantic_result)

    # Use tree result
    return tree_result
```

---

### Phase 3: Full Rollout (Week 5)

Make tree-based retrieval the default for all vaults.

---

## 9. Success Criteria

### Must-Have (P0)

- ✅ All 13 failing questions from 87% baseline now pass
- ✅ Zero MISMATCH failures (wrong entity selected)
- ✅ 95%+ accuracy on 100-question test
- ✅ Graph traversal used for 80%+ of queries
- ✅ No regression on currently passing questions

### Nice-to-Have (P1)

- Trace logs show graph paths for provenance
- Sub-second latency for depth 1-2 queries
- Automatic anchor detection for 95%+ of queries
- Support for multi-anchor queries

### Future (P2)

- Path visualization in UI
- Query-time graph expansion (fetch missing edges)
- Cross-vault traversal (federated queries)

---

## 10. Open Questions

1. **How to handle temporal queries?**
   - "Who was the former CEO?" (need historical relationships)
   - Solution: Add `valid_from` / `valid_to` to relationships

2. **How to handle negation?**
   - "Which divisions do NOT have safety incidents?"
   - Solution: Traverse all divisions, filter out those with incident relationships

3. **How to handle multi-anchor queries?**
   - "Compare Nexus revenue to Boeing revenue"
   - Solution: Detect multiple orgs, run parallel traversals, merge results

4. **How to optimize performance for deep traversals?**
   - Depth 3+ can be expensive
   - Solution: Implement query plan optimizer, cache subgraph patterns

---

## Appendix A: File Checklist

**New Files:**
- [ ] `src/context_foundry/retrieval/tree_retriever.py` - Main tree retrieval logic
- [ ] `src/context_foundry/retrieval/intent_extractor.py` - Query intent extraction
- [ ] `tests/unit/test_tree_retriever.py` - Unit tests
- [ ] `tests/integration/test_tree_based_pipeline.py` - Integration tests

**Modified Files:**
- [ ] `src/context_foundry/retrieval/anchor_resolver.py` - Extend for all query types
- [ ] `src/context_foundry/agents/retrieval_router.py` - Add tree-based routing
- [ ] `src/context_foundry/agents/tool_agent.py` - Add traversal tool
- [ ] `config/app_config.py` - Add feature flag

---

## Appendix B: Database Schema Changes

**Add relationship temporal support (optional for Phase 1):**

```sql
ALTER TABLE relationships
ADD COLUMN valid_from TIMESTAMP,
ADD COLUMN valid_to TIMESTAMP;

-- Index for temporal queries
CREATE INDEX idx_relationships_temporal
ON relationships(source_id, relationship_type, valid_from, valid_to)
WHERE valid_to IS NULL OR valid_to > NOW();
```

---

## Appendix C: References

- **Relationship-First Retrieval Spec:** `attached_assets/Pasted-Relationship-First-Retrieval-Complete-Implementation-Sp_1769440132804.txt`
- **Anchor Resolver Code:** `src/context_foundry/retrieval/anchor_resolver.py`
- **Failure Analysis:** `docs/ACCURACY_FAILURES_87.md`
- **Master Reference:** `docs/CF_MASTER_REFERENCE.md`

---

**End of Specification**

*"The graph is not a database. It's a world model. Traverse it like you're exploring a territory, not querying a table."*
