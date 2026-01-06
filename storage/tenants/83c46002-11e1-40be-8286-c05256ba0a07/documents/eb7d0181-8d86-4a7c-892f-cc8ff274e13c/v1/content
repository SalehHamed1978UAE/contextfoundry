# Context Foundry Enhancement: Relationship Context Metadata (v2)

**Author**: Claude (Architect)  
**Date**: January 2026  
**Status**: Specification  
**Version**: 2.0 — Updated to reflect 3-step pipeline architecture

---

## Executive Summary

Context Foundry currently stores relationships as bare triples:
```
(Auth Service) -[DEPENDS_ON]-> (Users Database)
```

This loses the **contextual information** that makes relationships meaningful and trustworthy. Based on research in Context Graphs (Xu et al., 2024), we should enrich relationships with metadata that enables:

1. **Richer answers** — "Auth Service depends on Users Database *for credential storage*"
2. **Temporal awareness** — "This was true as of December 2025"
3. **Provenance** — "According to architecture_overview.md, line 47"
4. **Confidence with evidence** — "95% confident based on explicit statement"
5. **Query-relevant filtering** — Return only relationships relevant to the question

---

## Current Architecture (Post 3-Step Pipeline)

### What We Have Now

**Query Pipeline:**
```
User Query → QueryInterpreter → DirectedGraphRetriever → AnswerSynthesizer
                   ↓                      ↓                      ↓
             QueryIntent            Graph Traversal         Natural Language
             (structured)           (with cascade)            Response
```

**QueryIntent Schema:**
```python
class QueryIntent:
    entity: str                    # "API Gateway"
    direction: str                 # "inbound" | "outbound" | "both"
    relationship_types: list       # ["DEPENDS_ON", "CALLS"]
    depth: int                     # Cascade depth (1 = direct only)
    target_entity_type: str | None # Dynamic from tenant schema
```

**Relationships Table:**
```sql
CREATE TABLE relationships (
    id UUID PRIMARY KEY,
    source_entity_id UUID,
    target_entity_id UUID,
    relationship_type VARCHAR(100),
    tenant_id UUID,
    lifecycle_state VARCHAR(50),
    confidence FLOAT,  -- Only metadata we have
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### What's Missing

| Missing Context | Why It Matters |
|-----------------|----------------|
| **Provenance sentence** | Can't cite source for the relationship |
| **Document source** | Don't know where relationship came from |
| **Temporal validity** | Don't know if relationship is current |
| **Relationship description** | Can't explain *why* entities are related |
| **Semantic embedding** | Can't filter relationships by query relevance |
| **Extraction method** | Don't know if LLM extracted or rule-based |
| **Qualifiers** | Can't capture conditions like "during business hours" |

---

## Proposed Schema

### Relationship Context Table

```sql
CREATE TABLE relationship_contexts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    relationship_id UUID NOT NULL REFERENCES relationships(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL,
    
    -- Provenance
    source_document_id UUID REFERENCES documents(id),
    source_chunk_id UUID,
    provenance_text TEXT,           -- Exact sentence(s) supporting this relationship
    source_location VARCHAR(100),   -- "section 3.2" or "line 47-52"
    
    -- Temporal
    temporal_start TIMESTAMP,
    temporal_end TIMESTAMP,         -- NULL = current
    temporal_granularity VARCHAR(20), -- 'exact', 'approximate', 'unknown'
    
    -- Description
    description TEXT,               -- Natural language explanation
    qualifiers JSONB DEFAULT '[]',  -- Conditions, exceptions, modifiers
    
    -- Semantic
    embedding VECTOR(1536),         -- For query-relevant filtering
    
    -- Extraction metadata
    extraction_method VARCHAR(50),  -- 'llm_extraction', 'rule_based', 'manual'
    extraction_model VARCHAR(100),
    extraction_prompt_version VARCHAR(50),
    raw_extraction JSONB,
    
    -- Confidence breakdown
    confidence_source FLOAT,
    confidence_extraction FLOAT,
    confidence_combined FLOAT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_context_per_relationship UNIQUE(relationship_id, source_document_id)
);

-- Indexes
CREATE INDEX idx_rel_context_relationship ON relationship_contexts(relationship_id);
CREATE INDEX idx_rel_context_tenant ON relationship_contexts(tenant_id);
CREATE INDEX idx_rel_context_document ON relationship_contexts(source_document_id);
CREATE INDEX idx_rel_context_embedding ON relationship_contexts 
    USING ivfflat (embedding vector_cosine_ops);

-- RLS
ALTER TABLE relationship_contexts ENABLE ROW LEVEL SECURITY;
CREATE POLICY rel_context_tenant_isolation ON relationship_contexts
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

---

## Context Types

### 1. Provenance Context
```json
{
  "source_document": "architecture_overview.md",
  "source_location": "section 3.2, paragraph 1",
  "provenance_text": "The Auth Service depends on the Users Database for credential storage.",
  "extraction_date": "2026-01-06T10:30:00Z"
}
```

### 2. Temporal Context
```json
{
  "temporal_start": "2024-01-01",
  "temporal_end": null,
  "temporal_granularity": "approximate",
  "temporal_source": "Document mentions 'current architecture'"
}
```

### 3. Descriptive Context
```json
{
  "description": "Auth Service queries Users Database to validate credentials during login",
  "purpose": "credential_storage",
  "direction": "read",
  "frequency": "per_request"
}
```

### 4. Qualifier Context
```json
{
  "qualifiers": [
    {"type": "condition", "text": "Only during authentication flows"},
    {"type": "exception", "text": "Cached credentials bypass database for 5 minutes"}
  ]
}
```

### 5. Confidence Context
```json
{
  "confidence_combined": 0.95,
  "confidence_breakdown": {
    "source_reliability": 0.98,
    "extraction_confidence": 0.95,
    "recency": 0.90
  },
  "evidence_type": "explicit_statement",
  "corroborating_sources": 2
}
```

---

## Integration with 3-Step Pipeline

### Current Flow (Without Context)

```
Step 1: QueryInterpreter
        Input:  "If Users Database fails, what services are affected?"
        Output: QueryIntent {
                  entity: "Users Database",
                  direction: "inbound",
                  relationship_types: ["DEPENDS_ON", "CALLS"],
                  depth: 3,
                  target_entity_type: "SERVICE"
                }

Step 2: DirectedGraphRetriever
        Input:  QueryIntent
        Output: RetrievalResult {
                  relationships: [...],
                  cascade_paths: [
                    "Users Database → Auth Service",
                    "Users Database → Auth Service → API Gateway"
                  ]
                }

Step 3: AnswerSynthesizer
        Input:  RetrievalResult
        Output: "Auth Service, API Gateway, ... are affected"
```

### Enhanced Flow (With Context)

```
Step 1: QueryInterpreter (unchanged)

Step 2: DirectedGraphRetriever (enhanced)
        Input:  QueryIntent
        Output: RetrievalResult {
                  relationships: [
                    {
                      source: "Auth Service",
                      target: "Users Database",
                      type: "DEPENDS_ON",
                      context: {
                        provenance: "architecture_overview.md, section 3.2",
                        description: "For credential storage and validation",
                        temporal: "current",
                        confidence: 0.95
                      }
                    }
                  ],
                  cascade_paths: [...]
                }

Step 3: AnswerSynthesizer (enhanced)
        Input:  RetrievalResult with context
        Output: "Auth Service depends on Users Database for credential storage
                 (source: architecture_overview.md, confidence: 0.95)"
```

---

## Graph Traversal Formulas

### Blast Radius (What breaks if X fails)

```
BR(X) = transitive closure of inbound DEPENDS_ON/CALLS from X
```

### Target Type Filtering

```
Let:
  X  = entity in question
  T  = target entity type (discovered from tenant schema)
  BR(X) = blast radius of X
  N_T(e) = neighbors of entity e that are of type T

Result = N_T(X) ∪ N_T(BR(X))
```

**Translation:** Entities of type T connected to X itself, PLUS entities of type T connected to anything in the blast radius.

### Cascade Path Tracking

```
Path = X → e₁ → e₂ → ... → eₙ

Where each edge (eᵢ, eᵢ₊₁) includes:
  - relationship_type
  - confidence
  - context (if available)
  - depth from X
```

---

## Dynamic Schema Discovery

Entity types are **not hardcoded**. They are discovered from tenant data:

```python
def get_tenant_entity_types(tenant_id: str) -> List[str]:
    """Query database to find all entity types for this tenant."""
    return session.execute(text("""
        SELECT DISTINCT entity_type 
        FROM entities 
        WHERE tenant_id = :tid
    """), {"tid": tenant_id}).scalars().all()
```

The QueryInterpreter prompt includes available types dynamically:

```
Available entity types in this tenant: {types}

Based on the user's question, determine which type they want:
- "Which teams..." → target_entity_type: "TEAM"
- "What databases..." → target_entity_type: "DATABASE"
- etc.
```

---

## Extraction Enhancement

### Current Prompt (Bare Triples)
```
Extract relationships from this document:
- Return: (source_entity, relationship_type, target_entity)
```

### Enhanced Prompt (With Context)
```
Extract relationships with full context.

For each relationship, provide:
1. source_entity
2. relationship_type
3. target_entity
4. provenance_text: Exact sentence(s) stating this relationship
5. description: Brief explanation of what this relationship means
6. temporal_validity: current | historical | time-bounded
7. qualifiers: Conditions, exceptions, or modifiers
8. confidence: 0.0-1.0 with reasoning

Return JSON:
{
  "relationships": [
    {
      "source_entity": "Auth Service",
      "relationship_type": "DEPENDS_ON",
      "target_entity": "Users Database",
      "provenance_text": "Auth Service depends on Users Database for credential storage",
      "description": "Queries user credentials during authentication",
      "temporal_validity": {"status": "current"},
      "qualifiers": [{"type": "purpose", "text": "credential storage"}],
      "confidence": 0.95,
      "confidence_reasoning": "Explicit statement in architecture document"
    }
  ]
}
```

---

## Example Response: Before vs After

### Query: "If Users Database fails, what's affected and why?"

### Before (Current)
```
**Directly Affected (Depth 1):**
- Auth Service via DEPENDS_ON (confidence: 0.95)
- Notification Service via DEPENDS_ON (confidence: 0.87)

**Indirectly Affected (Depth 2+):**
- API Gateway via chain: Auth Service → API Gateway

**Summary:** 3 services affected.
```

### After (With Context)
```
**Directly Affected (Depth 1):**

1. Auth Service (confidence: 0.95)
   - Relationship: DEPENDS_ON
   - Why: "Auth Service queries Users Database for credential storage"
   - Impact: All authentication fails
   - Source: architecture_overview.md, section 3.2

2. Notification Service (confidence: 0.87)
   - Relationship: DEPENDS_ON
   - Why: "Reads user preferences for notification routing"
   - Impact: Notifications use defaults
   - Source: architecture_overview.md, section 5.1

**Indirectly Affected (Depth 2+):**

3. API Gateway (via Auth Service)
   - Chain: Users Database → Auth Service → API Gateway
   - Impact: All authenticated requests fail
   - Source: Inferred from dependency chain

**Knowledge Gaps:**
- Session Cache behavior during outage not documented
- Recovery time objectives not found
- Fallback mechanisms not specified

**Sources:**
- architecture_overview.md (primary)
- Last verified: December 2025
```

---

## Implementation Plan

### Phase 1: Schema & Migration (1 day)
1. Create `relationship_contexts` table
2. Add RLS policy
3. Create indexes
4. Test with existing data

### Phase 2: Extraction Enhancement (2 days)
1. Update extraction prompt
2. Modify GraphBuilder to store context
3. Add embedding generation for provenance
4. Test extraction quality

### Phase 3: Pipeline Integration (2 days)
1. Update DirectedGraphRetriever to fetch context
2. Update RetrievalResult to include context
3. Update AnswerSynthesizer to render context
4. Test end-to-end

### Phase 4: Backfill (1 day)
1. Re-process demo tenant documents
2. Generate embeddings
3. Verify quality

### Phase 5: Testing (1 day)
1. Run A/B comparison
2. Measure answer quality improvement
3. Document results

---

## Expected Benefits

| Metric | Before | After |
|--------|--------|-------|
| Answer citations | None | "According to [source]" |
| Relationship explanation | None | "For credential storage" |
| Temporal awareness | None | "Current" / "As of 2024" |
| Confidence transparency | Single number | Breakdown with reasoning |
| Debug-ability | Hard | Full extraction trace |
| Trust | "Says who?" | Cited sources |

---

## Research References

1. **Context Graph** (Xu et al., 2024) — Entity and relation contexts
2. **Contextual Graph Transformer** (Reddy & Pal, 2025) — Semantic similarity edges
3. **Semantic-Aware Relational Message Passing** (Wen et al., 2025) — Top-K selection

---

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Schema approach | Separate table (Option B) | More flexible, preserves existing data |
| Type discovery | Dynamic from tenant data | Domain-agnostic, no hardcoding |
| Cascade tracking | Depth + paths | Shows "why" not just "what" |
| Target type filtering | N_T(X) ∪ N_T(BR(X)) | Includes direct + blast radius connections |

---

## Next Steps

1. Review and approve this spec
2. Create database migration
3. Update extraction prompt
4. Integrate with 3-step pipeline
5. Test with demo tenant
6. Run A/B evaluation

---

**This completes CF's "refuses to hallucinate" promise — every answer has provenance, every relationship has context.**
