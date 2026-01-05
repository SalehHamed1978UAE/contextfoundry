# RLM Memory API Response Schemas

> **Addendum to**: RLM Integration Spec  
> **Purpose**: Define concrete data shapes for Memory APIs so LLM can generate valid code  
> **Status**: Draft for Replit review  
> **Date**: January 2026

---

## Design Decisions (Resolved)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| STAGING visibility | **Option B**: Show both STAGING and TRUSTED with `lifecycle_state` field | LLM can weigh confidence accordingly; hiding STAGING loses recent data |
| Circuit breaker | Progress = new entities OR new relationships discovered | Simple, measurable, prevents cost runaway |
| Entity ID stability | Live data + `StaleEntityError` if ID disappears | Gardener runs every 5 min; unlikely but handle gracefully |

---

## Core Data Types

### Common Types

```python
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class LifecycleState(str, Enum):
    STAGING = "STAGING"
    TRUSTED = "TRUSTED"
    ARCHIVED = "ARCHIVED"

class EntityType(str, Enum):
    """From domain_schema.yaml - extend as needed"""
    PERSON = "PERSON"
    SERVICE = "SERVICE"
    INCIDENT = "INCIDENT"
    TEAM = "TEAM"
    SYSTEM = "SYSTEM"
    DOCUMENT = "DOCUMENT"
    METRIC = "METRIC"
    # ... domain-specific types

class RelationshipType(str, Enum):
    """From domain_schema.yaml - extend as needed"""
    MANAGES = "MANAGES"
    USES = "USES"
    TRIGGERED_BY = "TRIGGERED_BY"
    AFFECTS = "AFFECTS"
    OWNS = "OWNS"
    MEMBER_OF = "MEMBER_OF"
    DEPENDS_ON = "DEPENDS_ON"
    # ... domain-specific types
```

---

## Semantic Memory API Responses

### EntitySummary
Lightweight representation for list operations. Does NOT include embeddings.

```python
class EntitySummary(BaseModel):
    """Returned by find_entities(), find_similar(), find_by_property()"""
    id: str                          # UUID
    name: str                        # Display name
    entity_type: EntityType          # PERSON, SERVICE, etc.
    confidence: float                # 0.0-1.0
    lifecycle_state: LifecycleState  # STAGING, TRUSTED, ARCHIVED
    created_at: datetime
    updated_at: datetime
    
    # Flattened key properties for quick access (subset of full properties)
    primary_property: Optional[str]  # Most important property value
    property_count: int              # How many properties exist
    relationship_count: int          # How many relationships exist

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Network Monitoring Service",
                "entity_type": "SERVICE",
                "confidence": 0.89,
                "lifecycle_state": "TRUSTED",
                "created_at": "2024-11-15T10:30:00Z",
                "updated_at": "2024-12-20T14:22:00Z",
                "primary_property": "status: active",
                "property_count": 8,
                "relationship_count": 12
            }
        }
```

### EntityDetail
Full entity data for get_entity() calls.

```python
class EntityDetail(BaseModel):
    """Returned by get_entity()"""
    id: str
    name: str
    entity_type: EntityType
    confidence: float
    lifecycle_state: LifecycleState
    created_at: datetime
    updated_at: datetime
    
    # Full properties as flat dict
    properties: Dict[str, Any]
    
    # Aliases for entity resolution
    aliases: List[str]
    
    # Source tracking
    source_document_ids: List[str]
    extraction_method: str  # "llm_extraction", "bulk_load", "manual"
    
    # Governance metadata
    corroboration_count: int  # How many sources confirm this entity
    last_verified_at: Optional[datetime]
    promoted_at: Optional[datetime]  # When moved to TRUSTED

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Network Monitoring Service",
                "entity_type": "SERVICE",
                "confidence": 0.89,
                "lifecycle_state": "TRUSTED",
                "created_at": "2024-11-15T10:30:00Z",
                "updated_at": "2024-12-20T14:22:00Z",
                "properties": {
                    "status": "active",
                    "owner_team": "Infrastructure",
                    "criticality": "high",
                    "port": 8080,
                    "version": "2.4.1"
                },
                "aliases": ["NetMon", "NMS", "Network Monitor"],
                "source_document_ids": ["doc-123", "doc-456"],
                "extraction_method": "llm_extraction",
                "corroboration_count": 3,
                "last_verified_at": "2024-12-18T09:00:00Z",
                "promoted_at": "2024-11-16T08:00:00Z"
            }
        }
```

### EntityMatch
Returned by semantic search with similarity score.

```python
class EntityMatch(BaseModel):
    """Returned by find_similar()"""
    entity: EntitySummary
    similarity_score: float  # 0.0-1.0, from pgvector cosine similarity
    match_type: str          # "exact", "semantic", "fuzzy"

    class Config:
        json_schema_extra = {
            "example": {
                "entity": {"id": "...", "name": "Network Monitoring Service", "...": "..."},
                "similarity_score": 0.92,
                "match_type": "semantic"
            }
        }
```

---

## Episodic Memory API Responses

### ChunkSummary
Lightweight chunk reference.

```python
class ChunkSummary(BaseModel):
    """Returned by get_document_chunks()"""
    id: str                    # UUID
    document_id: str           # Parent document UUID
    chunk_index: int           # Position in document (0-indexed)
    token_count: int           # Approximate tokens
    preview: str               # First 200 chars of content
    created_at: datetime
```

### ChunkDetail
Full chunk content with provenance.

```python
class ChunkDetail(BaseModel):
    """Returned by get_chunk()"""
    id: str
    document_id: str
    chunk_index: int
    content: str               # Full chunk text
    token_count: int
    created_at: datetime
    
    # Provenance
    document_name: str         # Original filename
    document_type: str         # "pdf", "docx", "txt", etc.
    upload_date: datetime
    page_numbers: Optional[List[int]]  # For PDFs

    class Config:
        json_schema_extra = {
            "example": {
                "id": "chunk-789",
                "document_id": "doc-123",
                "chunk_index": 4,
                "content": "The Network Monitoring Service detected an anomaly in traffic patterns at 14:32 UTC. The incident was automatically escalated to the Infrastructure team...",
                "token_count": 487,
                "created_at": "2024-12-01T10:00:00Z",
                "document_name": "Incident_Report_2024_Q4.pdf",
                "document_type": "pdf",
                "upload_date": "2024-12-01T09:45:00Z",
                "page_numbers": [12, 13]
            }
        }
```

### ChunkMatch
Returned by semantic search.

```python
class ChunkMatch(BaseModel):
    """Returned by episodic.search()"""
    chunk: ChunkDetail
    similarity_score: float    # 0.0-1.0
    highlight: Optional[str]   # Relevant snippet with query terms highlighted

    class Config:
        json_schema_extra = {
            "example": {
                "chunk": {"id": "chunk-789", "...": "..."},
                "similarity_score": 0.87,
                "highlight": "...the **Network Monitoring Service** detected an **anomaly**..."
            }
        }
```

### ProvenanceInfo
Detailed source tracking.

```python
class ProvenanceInfo(BaseModel):
    """Returned by get_provenance()"""
    chunk_id: str
    document_id: str
    document_name: str
    document_type: str
    upload_date: datetime
    uploaded_by: Optional[str]  # User ID if available
    page_numbers: Optional[List[int]]
    section_title: Optional[str]
    
    # Chain of custody
    processing_steps: List[str]  # ["pdf_extraction", "chunking", "embedding"]
```

---

## Symbolic Memory API Responses

### Relationship
Single relationship between entities.

```python
class Relationship(BaseModel):
    """Returned by get_relationships()"""
    id: str
    source_entity_id: str
    source_entity_name: str    # Denormalized for convenience
    target_entity_id: str
    target_entity_name: str    # Denormalized for convenience
    relationship_type: RelationshipType
    confidence: float
    lifecycle_state: LifecycleState
    properties: Dict[str, Any]  # Relationship-specific properties
    created_at: datetime
    
    # Source tracking
    source_document_ids: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "id": "rel-001",
                "source_entity_id": "entity-nms",
                "source_entity_name": "Network Monitoring Service",
                "target_entity_id": "entity-inc-142",
                "target_entity_name": "INC-2024-0142",
                "relationship_type": "TRIGGERED_BY",
                "confidence": 0.85,
                "lifecycle_state": "TRUSTED",
                "properties": {"trigger_time": "2024-12-15T14:32:00Z"},
                "created_at": "2024-12-15T15:00:00Z",
                "source_document_ids": ["doc-123"]
            }
        }
```

### Path
Relationship path between two entities.

```python
class PathStep(BaseModel):
    """Single step in a path"""
    entity_id: str
    entity_name: str
    entity_type: EntityType
    relationship_type: RelationshipType  # Relationship TO this entity
    relationship_id: str

class Path(BaseModel):
    """Returned by find_path()"""
    source_entity_id: str
    source_entity_name: str
    target_entity_id: str
    target_entity_name: str
    steps: List[PathStep]
    total_hops: int
    min_confidence: float      # Lowest confidence in the path
    
    class Config:
        json_schema_extra = {
            "example": {
                "source_entity_id": "entity-nms",
                "source_entity_name": "Network Monitoring Service",
                "target_entity_id": "entity-email-gw",
                "target_entity_name": "Email Gateway",
                "steps": [
                    {"entity_id": "entity-inc-142", "entity_name": "INC-2024-0142", 
                     "entity_type": "INCIDENT", "relationship_type": "TRIGGERED_BY", "relationship_id": "rel-001"},
                    {"entity_id": "entity-email-gw", "entity_name": "Email Gateway",
                     "entity_type": "SERVICE", "relationship_type": "AFFECTS", "relationship_id": "rel-002"}
                ],
                "total_hops": 2,
                "min_confidence": 0.78
            }
        }
```

### SubGraph
Result of graph traversal.

```python
class SubGraph(BaseModel):
    """Returned by traverse()"""
    root_entity_id: str
    root_entity_name: str
    entities: List[EntitySummary]      # All discovered entities
    relationships: List[Relationship]  # All discovered relationships
    depth_reached: int                 # Actual depth traversed
    truncated: bool                    # True if hit limit before exhausting graph

    class Config:
        json_schema_extra = {
            "example": {
                "root_entity_id": "entity-nms",
                "root_entity_name": "Network Monitoring Service",
                "entities": ["...list of EntitySummary..."],
                "relationships": ["...list of Relationship..."],
                "depth_reached": 2,
                "truncated": False
            }
        }
```

---

## Sub-Query API Responses

### VerificationResult
Returned by llm_verify().

```python
class VerificationResult(BaseModel):
    """Returned by llm_verify(claim, evidence)"""
    supported: bool
    confidence: float          # 0.0-1.0
    reasoning: str             # Brief explanation
    evidence_quotes: List[str] # Specific quotes that support/refute
    
    class Config:
        json_schema_extra = {
            "example": {
                "supported": True,
                "confidence": 0.92,
                "reasoning": "The incident report explicitly states the Network Monitoring Service triggered alert INC-2024-0142",
                "evidence_quotes": ["NMS triggered automatic escalation at 14:32 UTC"]
            }
        }
```

---

## Error Types

```python
class RLMError(Exception):
    """Base error for RLM execution"""
    pass

class StaleEntityError(RLMError):
    """Entity ID no longer exists (Gardener archived/deleted it)"""
    def __init__(self, entity_id: str):
        self.entity_id = entity_id
        super().__init__(f"Entity {entity_id} no longer exists. It may have been archived by Gardener.")

class BudgetExhaustedError(RLMError):
    """Token or call budget exhausted"""
    def __init__(self, budget_type: str, limit: int):
        self.budget_type = budget_type
        self.limit = limit
        super().__init__(f"{budget_type} budget exhausted (limit: {limit})")

class REPLExecutionError(RLMError):
    """Code execution failed in sandbox"""
    def __init__(self, code: str, error: str, retry_hint: Optional[str] = None):
        self.code = code
        self.error = error
        self.retry_hint = retry_hint
        super().__init__(f"REPL execution failed: {error}")

class CircuitBreakerTripped(RLMError):
    """No progress detected, falling back to standard pipeline"""
    def __init__(self, iterations_without_progress: int):
        self.iterations = iterations_without_progress
        super().__init__(f"No progress after {iterations_without_progress} iterations")
```

---

## REPL Execution Types

### REPLExecutionResult

```python
class REPLExecutionResult(BaseModel):
    """Result of executing code in sandbox"""
    success: bool
    output: str                        # stdout capture
    error: Optional[str]               # stderr or exception message
    retry_hint: Optional[str]          # Suggestion for fixing code
    execution_time_ms: int
    
    # Progress tracking for circuit breaker
    new_entities_discovered: List[str]      # Entity IDs found this iteration
    new_relationships_discovered: List[str] # Relationship IDs found this iteration
    
    class Config:
        json_schema_extra = {
            "example_success": {
                "success": True,
                "output": "Found services: ['Network Monitoring Service', 'NetMon Agent']\n",
                "error": None,
                "retry_hint": None,
                "execution_time_ms": 245,
                "new_entities_discovered": ["entity-nms", "entity-nma"],
                "new_relationships_discovered": []
            },
            "example_error": {
                "success": False,
                "output": "",
                "error": "AttributeError: 'EntitySummary' object has no attribute 'full_name'",
                "retry_hint": "EntitySummary has 'name' not 'full_name'. Use entity.name instead.",
                "execution_time_ms": 12,
                "new_entities_discovered": [],
                "new_relationships_discovered": []
            }
        }
```

### ProgressTracker
For circuit breaker logic.

```python
class ProgressTracker(BaseModel):
    """Tracks progress for circuit breaker"""
    iteration: int
    entities_discovered: set[str]      # Cumulative entity IDs
    relationships_discovered: set[str] # Cumulative relationship IDs
    iterations_without_progress: int   # Consecutive iterations with no new discoveries
    
    def record_iteration(self, result: REPLExecutionResult) -> bool:
        """Returns True if progress was made"""
        new_entities = set(result.new_entities_discovered) - self.entities_discovered
        new_relationships = set(result.new_relationships_discovered) - self.relationships_discovered
        
        made_progress = len(new_entities) > 0 or len(new_relationships) > 0
        
        if made_progress:
            self.entities_discovered.update(new_entities)
            self.relationships_discovered.update(new_relationships)
            self.iterations_without_progress = 0
        else:
            self.iterations_without_progress += 1
        
        self.iteration += 1
        return made_progress
    
    def should_trip_breaker(self, threshold: int = 3) -> bool:
        """Trip circuit breaker if no progress for N iterations"""
        return self.iterations_without_progress >= threshold
```

---

## Execution Trace Schema

```python
class SubQueryLog(BaseModel):
    """Log entry for a sub-query call"""
    query_type: str            # "query", "verify", "summarize"
    prompt_preview: str        # First 200 chars of prompt
    response_preview: str      # First 200 chars of response
    tokens_used: int
    duration_ms: int

class ExecutionTraceEntry(BaseModel):
    """Single iteration in execution trace"""
    iteration: int
    timestamp: datetime
    code: str                  # Code executed
    result: REPLExecutionResult
    sub_queries: List[SubQueryLog]
    budget_remaining: int      # Tokens remaining after this iteration
    cumulative_entities: int   # Total unique entities discovered so far
    cumulative_relationships: int

class ExecutionTrace(BaseModel):
    """Full execution trace for audit/debugging"""
    query_id: str
    tenant_id: str
    original_query: str
    started_at: datetime
    completed_at: datetime
    total_iterations: int
    final_status: str          # "completed", "timeout", "budget_exhausted", "circuit_breaker"
    entries: List[ExecutionTraceEntry]
    
    # Summary stats
    total_tokens_used: int
    total_sub_queries: int
    total_entities_discovered: int
    total_relationships_discovered: int
    estimated_cost_usd: float
```

---

## API Method Signatures (Updated)

With concrete return types:

```python
class SemanticMemoryAPI:
    def find_entities(self, entity_type: str = None, 
                      limit: int = 50,
                      include_staging: bool = True) -> List[EntitySummary]: ...
    
    def find_similar(self, query: str, k: int = 10,
                     entity_type: str = None,
                     min_confidence: float = 0.0,
                     include_staging: bool = True) -> List[EntityMatch]: ...
    
    def get_entity(self, entity_id: str) -> EntityDetail: 
        """Raises StaleEntityError if entity no longer exists"""
        ...
    
    def find_by_property(self, property_name: str,
                         property_value: str,
                         include_staging: bool = True) -> List[EntitySummary]: ...


class EpisodicMemoryAPI:
    def search(self, query: str, k: int = 5,
               document_type: str = None) -> List[ChunkMatch]: ...
    
    def get_chunk(self, chunk_id: str) -> ChunkDetail: ...
    
    def get_document_chunks(self, document_id: str) -> List[ChunkSummary]: ...
    
    def get_provenance(self, chunk_id: str) -> ProvenanceInfo: ...


class SymbolicMemoryAPI:
    def get_relationships(self, entity_id: str,
                          direction: str = "both",
                          relationship_type: str = None,
                          include_staging: bool = True) -> List[Relationship]:
        """Raises StaleEntityError if entity no longer exists"""
        ...
    
    def find_path(self, source_id: str, target_id: str,
                  max_depth: int = 3) -> List[Path]:
        """Returns empty list if no path exists"""
        ...
    
    def get_related_entities(self, entity_id: str,
                             relationship_type: str,
                             include_staging: bool = True) -> List[EntitySummary]:
        """Raises StaleEntityError if entity no longer exists"""
        ...
    
    def traverse(self, start_id: str,
                 relationship_types: List[str] = None,
                 depth: int = 2,
                 max_entities: int = 100) -> SubGraph:
        """Raises StaleEntityError if start entity no longer exists"""
        ...


class SubQueryAPI:
    def query(self, prompt: str, max_tokens: int = 500) -> str:
        """Raises BudgetExhaustedError if budget exceeded"""
        ...
    
    def verify(self, claim: str, evidence: str) -> VerificationResult:
        """Raises BudgetExhaustedError if budget exceeded"""
        ...
    
    def summarize(self, content: str, focus: str = None) -> str:
        """Raises BudgetExhaustedError if budget exceeded"""
        ...
```

---

## REPL Error Handling Flow

```
Code Execution
     │
     ▼
┌─────────────────┐
│ Execute in      │
│ Sandbox         │
└────────┬────────┘
         │
    ┌────┴────┐
    │ Success? │
    └────┬────┘
         │
    Yes  │  No
    ─────┼─────
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Return result   │     │ Generate        │
│ Track progress  │     │ retry_hint      │
└─────────────────┘     └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │ Return error +  │
                        │ retry_hint      │
                        │ Count as        │
                        │ iteration       │
                        └─────────────────┘
```

### Retry Hint Generation

```python
COMMON_ERROR_HINTS = {
    "AttributeError": lambda e: f"Object doesn't have that attribute. Check the schema: {extract_valid_attrs(e)}",
    "KeyError": lambda e: f"Key not found. Available keys: {extract_available_keys(e)}",
    "TypeError": lambda e: f"Type mismatch. Expected types: {extract_expected_types(e)}",
    "StaleEntityError": lambda e: f"Entity was archived. Search for it again with semantic.find_similar()",
    "BudgetExhaustedError": lambda e: "Budget exhausted. Provide final answer with FINAL() using data collected so far.",
}
```

---

## Summary: What LLM Needs to Know

For the system prompt, this is what the LLM needs to understand about data shapes:

```
## Data Shapes Quick Reference

### Entities (semantic memory)
- EntitySummary: id, name, entity_type, confidence, lifecycle_state
- EntityDetail: + properties (dict), aliases (list), source_document_ids
- EntityMatch: entity (EntitySummary) + similarity_score, match_type

### Chunks (episodic memory)  
- ChunkSummary: id, document_id, chunk_index, preview
- ChunkDetail: + content (full text), document_name, page_numbers
- ChunkMatch: chunk (ChunkDetail) + similarity_score, highlight

### Relationships (symbolic memory)
- Relationship: source_entity_id/name, target_entity_id/name, relationship_type, confidence
- Path: steps (list of entities/relationships), total_hops, min_confidence
- SubGraph: entities (list), relationships (list), depth_reached

### Sub-queries
- llm_verify() returns: supported (bool), confidence (float), reasoning (str)

### Common patterns
- All entities have lifecycle_state: STAGING, TRUSTED, or ARCHIVED
- All confidence scores are 0.0-1.0
- StaleEntityError means entity was archived - search again
- BudgetExhaustedError means finish with what you have
```

---

## Next Steps

1. **Replit reviews** this schema document
2. **Merge into main spec** once approved
3. **Start Phase 1** - Implement Memory API wrappers returning these exact shapes
4. **Generate test fixtures** - Sample data matching these schemas for unit tests
