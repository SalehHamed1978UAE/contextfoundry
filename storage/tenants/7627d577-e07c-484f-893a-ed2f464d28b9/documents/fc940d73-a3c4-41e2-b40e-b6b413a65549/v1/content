# Context Foundry Enhancement: Relationship Context Metadata

**Author**: Claude (Architect)  
**Date**: January 2026  
**Status**: Specification  
**Priority**: High — Core to CF's value proposition

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

## Current State

### What We Store Now

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

### Option A: Add Columns to Relationships Table

```sql
ALTER TABLE relationships ADD COLUMN context JSONB DEFAULT '{}';
ALTER TABLE relationships ADD COLUMN provenance_text TEXT;
ALTER TABLE relationships ADD COLUMN source_document_id UUID REFERENCES documents(id);
ALTER TABLE relationships ADD COLUMN source_location VARCHAR(100);  -- "line 47" or "paragraph 3"
ALTER TABLE relationships ADD COLUMN temporal_start TIMESTAMP;
ALTER TABLE relationships ADD COLUMN temporal_end TIMESTAMP;  -- NULL = still valid
ALTER TABLE relationships ADD COLUMN description TEXT;
ALTER TABLE relationships ADD COLUMN embedding VECTOR(1536);  -- For semantic search
ALTER TABLE relationships ADD COLUMN extraction_method VARCHAR(50);  -- 'llm', 'rule', 'manual'
ALTER TABLE relationships ADD COLUMN qualifiers JSONB DEFAULT '[]';
```

### Option B: Separate Relationship Context Table (Recommended)

More flexible, preserves existing table, allows multiple contexts per relationship.

```sql
CREATE TABLE relationship_contexts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    relationship_id UUID NOT NULL REFERENCES relationships(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL,
    
    -- Provenance
    source_document_id UUID REFERENCES documents(id),
    source_chunk_id UUID,  -- Which chunk contained this
    provenance_text TEXT,  -- Exact sentence(s) that support this relationship
    source_location VARCHAR(100),  -- "section 3.2" or "line 47-52"
    
    -- Temporal
    temporal_start TIMESTAMP,  -- When relationship became true
    temporal_end TIMESTAMP,  -- When relationship ended (NULL = current)
    temporal_granularity VARCHAR(20),  -- 'exact', 'approximate', 'unknown'
    
    -- Description
    description TEXT,  -- Natural language explanation of the relationship
    qualifiers JSONB DEFAULT '[]',  -- Conditions, exceptions, modifiers
    
    -- Semantic
    embedding VECTOR(1536),  -- Embedding of provenance_text + description
    
    -- Extraction metadata
    extraction_method VARCHAR(50),  -- 'llm_extraction', 'rule_based', 'manual', 'inferred'
    extraction_model VARCHAR(100),  -- 'claude-3-sonnet', 'gpt-4', etc.
    extraction_prompt_version VARCHAR(50),
    raw_extraction JSONB,  -- Original LLM output for debugging
    
    -- Confidence breakdown
    confidence_source FLOAT,  -- Confidence in the source document
    confidence_extraction FLOAT,  -- Confidence in the extraction
    confidence_combined FLOAT,  -- Overall confidence
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_context_per_relationship UNIQUE(relationship_id, source_document_id)
);

-- Index for fast lookup
CREATE INDEX idx_rel_context_relationship ON relationship_contexts(relationship_id);
CREATE INDEX idx_rel_context_tenant ON relationship_contexts(tenant_id);
CREATE INDEX idx_rel_context_document ON relationship_contexts(source_document_id);

-- Semantic search index
CREATE INDEX idx_rel_context_embedding ON relationship_contexts 
    USING ivfflat (embedding vector_cosine_ops);

-- RLS policy
ALTER TABLE relationship_contexts ENABLE ROW LEVEL SECURITY;

CREATE POLICY rel_context_tenant_isolation ON relationship_contexts
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

---

## Context Types (Based on Research)

### 1. Provenance Context

Where did this relationship come from?

```json
{
  "source_document": "architecture_overview.md",
  "source_location": "section 3.2, paragraph 1",
  "provenance_text": "The Auth Service depends on the Users Database for credential storage and validation.",
  "extraction_date": "2026-01-06T10:30:00Z"
}
```

### 2. Temporal Context

When is/was this relationship valid?

```json
{
  "temporal_start": "2024-01-01",
  "temporal_end": null,  // Still valid
  "temporal_granularity": "approximate",
  "temporal_source": "Document mentions 'current architecture'"
}
```

**Examples:**
- "Steve Jobs was chairman of Apple" — temporal_end: 2011
- "Auth Service depends on Users Database" — temporal_end: null (current)

### 3. Descriptive Context

What does this relationship actually mean?

```json
{
  "description": "Auth Service queries Users Database to validate user credentials during login",
  "purpose": "credential_storage",
  "direction": "read",
  "frequency": "per_request"
}
```

### 4. Qualifier Context

Conditions or exceptions to the relationship.

```json
{
  "qualifiers": [
    {
      "type": "condition",
      "text": "Only during authentication flows",
      "scope": "limited"
    },
    {
      "type": "exception",
      "text": "Cached credentials bypass database for 5 minutes",
      "scope": "partial"
    }
  ]
}
```

### 5. Confidence Context

Why do we trust this relationship?

```json
{
  "confidence_combined": 0.95,
  "confidence_breakdown": {
    "source_reliability": 0.98,  // Official architecture doc
    "extraction_confidence": 0.95,  // Clear statement
    "recency": 0.90  // Document is 2 months old
  },
  "evidence_type": "explicit_statement",  // vs 'inferred', 'implicit'
  "corroborating_sources": 2  // Found in 2 documents
}
```

---

## Extraction Enhancement

### Current Extraction Prompt (Simplified)

```
Extract relationships from this document:
- Return: (source_entity, relationship_type, target_entity)
```

### Enhanced Extraction Prompt

```
Extract relationships from this document with full context.

For each relationship, provide:
1. source_entity: The entity that has the relationship
2. relationship_type: DEPENDS_ON, MANAGES, AFFECTS, etc.
3. target_entity: The entity being related to
4. provenance_text: The exact sentence(s) that state this relationship
5. description: A brief explanation of what this relationship means
6. temporal_validity: Is this current, historical, or time-bounded?
7. qualifiers: Any conditions, exceptions, or modifiers
8. confidence: How certain are you (0.0-1.0) with reasoning

Return JSON:
{
  "relationships": [
    {
      "source_entity": "Auth Service",
      "relationship_type": "DEPENDS_ON",
      "target_entity": "Users Database",
      "provenance_text": "Auth Service depends on Users Database for credential storage",
      "description": "Auth Service queries user credentials during authentication",
      "temporal_validity": {
        "status": "current",
        "start": null,
        "end": null
      },
      "qualifiers": [
        {"type": "purpose", "text": "credential storage and validation"}
      ],
      "confidence": 0.95,
      "confidence_reasoning": "Explicit dependency statement in architecture document"
    }
  ]
}
```

---

## Query Enhancement

### Current Query Response

```
Q: "What does Auth Service depend on?"
A: "Auth Service depends on Users Database, Session Cache"
   Confidence: 0.85
```

### Enhanced Query Response

```
Q: "What does Auth Service depend on?"
A: "Auth Service depends on:
   
   1. Users Database (confidence: 0.95)
      Purpose: Credential storage and validation
      Source: architecture_overview.md, section 3.2
      Status: Current
   
   2. Session Cache (confidence: 0.90)
      Purpose: Active session data storage
      Source: architecture_overview.md, section 4.1
      Status: Current
      Note: Fallback to database if cache unavailable"
   
   Overall confidence: 0.92
   Sources: 1 document
```

### Semantic Filtering

When answering queries, filter relationships by relevance:

```python
def get_relevant_relationships(
    entity_id: str,
    query: str,
    tenant_id: str,
    top_k: int = 10
) -> List[RelationshipWithContext]:
    """
    Get relationships relevant to a specific query.
    
    Instead of returning ALL relationships for an entity,
    return only those semantically relevant to the query.
    """
    
    # Get query embedding
    query_embedding = embed(query)
    
    # Find relationships with context embeddings similar to query
    results = session.execute(text("""
        SELECT r.*, rc.*,
               1 - (rc.embedding <=> :query_emb) as relevance_score
        FROM relationships r
        JOIN relationship_contexts rc ON r.id = rc.relationship_id
        WHERE r.source_entity_id = :entity_id
        AND r.tenant_id = :tid
        AND r.lifecycle_state = 'TRUSTED'
        ORDER BY relevance_score DESC
        LIMIT :top_k
    """), {
        "entity_id": entity_id,
        "query_emb": query_embedding,
        "tid": tenant_id,
        "top_k": top_k
    }).fetchall()
    
    return results
```

**Example:**

Query: "What does Auth Service depend on for security?"

Without semantic filtering:
- Users Database
- Session Cache
- Config Service
- Monitoring Agent

With semantic filtering (relevance to "security"):
- Users Database (0.92) — credential storage
- Session Cache (0.85) — session tokens
- (Config Service filtered out — not security-related)

---

## Implementation Plan

### Phase 1: Schema & Migration (1 day)

1. Create `relationship_contexts` table
2. Add RLS policy
3. Create indexes
4. Test with existing data

### Phase 2: Extraction Enhancement (2 days)

1. Update extraction prompt to capture context
2. Modify GraphBuilder to store context
3. Add embedding generation for provenance text
4. Test extraction quality

### Phase 3: Query Enhancement (2 days)

1. Update relationship retrieval to include context
2. Add semantic filtering option
3. Update response formatting to show context
4. Test query quality improvement

### Phase 4: Backfill Existing Data (1 day)

1. Re-process documents with enhanced extraction
2. Generate embeddings for existing relationships
3. Verify data quality

### Phase 5: Testing & Validation (1 day)

1. Run demo queries with context
2. Compare answer quality before/after
3. Measure confidence improvement
4. Document improvements

---

## Expected Benefits

| Metric | Before | After |
|--------|--------|-------|
| Answer citations | None | "According to [source]" |
| Relationship explanation | None | "For credential storage" |
| Temporal awareness | None | "Current" / "As of 2024" |
| Query relevance | All relationships | Top-K relevant |
| Confidence transparency | Single number | Breakdown with reasoning |
| Debug-ability | Hard | Full extraction trace |

---

## Example: Full Context Response

**Query:** "If Users Database fails, what's affected and why?"

**Response with Context:**

```
## Impact Analysis: Users Database Failure

### Directly Affected Services

1. **Auth Service** (confidence: 0.95)
   - Relationship: DEPENDS_ON
   - Impact: "Auth Service cannot validate credentials without Users Database"
   - Source: architecture_overview.md, section 3.2
   - Severity: CRITICAL — All authentication fails
   
2. **Notification Service** (confidence: 0.87)
   - Relationship: DEPENDS_ON  
   - Impact: "Notification Service reads user preferences from Users Database"
   - Source: architecture_overview.md, section 5.1
   - Severity: DEGRADED — Notifications use defaults

### Cascade Effects

3. **API Gateway** (indirect, via Auth Service)
   - All authenticated requests fail
   - Source: Inferred from Auth Service dependency

### Knowledge Gaps

- Session Cache behavior during database outage not documented
- Retry/fallback mechanisms not specified
- Recovery time objectives not found

### Sources
- architecture_overview.md (primary)
- Last updated: December 2025
```

---

## Research References

1. **Context Graph** (Xu et al., 2024) — Entity and relation contexts
2. **Contextual Graph Transformer** (Reddy & Pal, 2025) — Semantic similarity edges
3. **Semantic-Aware Relational Message Passing** (Wen et al., 2025) — Top-K selection

---

## Decision Needed

1. **Option A** (columns on relationships) vs **Option B** (separate table)?
   - Recommend: Option B — more flexible, preserves existing data

2. **Backfill strategy** — Re-extract all documents or only new ones?
   - Recommend: Re-extract for demo tenant, new-only for production

3. **Embedding model** — Same as entity embeddings or separate?
   - Recommend: Same model for consistency

---

## Next Steps

1. Review and approve this spec
2. Create database migration
3. Update extraction prompt
4. Implement and test
5. Run enhanced demo

**This is the foundation for CF's "refuses to hallucinate" promise — every answer has provenance.**
