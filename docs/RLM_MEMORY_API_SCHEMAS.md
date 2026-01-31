# RLM Memory API Response Schemas

> **Addendum to**: RLM Integration Spec  
> **Purpose**: Define concrete data shapes for Memory APIs so LLM can generate valid code  
> **Status**: Approved for implementation  
> **Date**: January 2026

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
```

---

## Semantic Memory API Responses

### EntitySummary
```python
class EntitySummary(BaseModel):
    id: str
    name: str
    entity_type: str
    confidence: float
    lifecycle_state: LifecycleState
    created_at: datetime
    updated_at: datetime
    primary_property: Optional[str]
    property_count: int
    relationship_count: int
```

### EntityDetail
```python
class EntityDetail(BaseModel):
    id: str
    name: str
    entity_type: str
    confidence: float
    lifecycle_state: LifecycleState
    created_at: datetime
    updated_at: datetime
    properties: Dict[str, Any]
    aliases: List[str]
    source_document_ids: List[str]
    extraction_method: str
    corroboration_count: int
    last_verified_at: Optional[datetime]
    promoted_at: Optional[datetime]
```

### EntityMatch
```python
class EntityMatch(BaseModel):
    entity: EntitySummary
    similarity_score: float
    match_type: str  # "exact", "semantic", "fuzzy"
```

---

## Episodic Memory API Responses

### ChunkSummary
```python
class ChunkSummary(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    token_count: int
    preview: str
    created_at: datetime
```

### ChunkDetail
```python
class ChunkDetail(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    content: str
    token_count: int
    created_at: datetime
    document_name: str
    document_type: str
    upload_date: datetime
    page_numbers: Optional[List[int]]
```

### ChunkMatch
```python
class ChunkMatch(BaseModel):
    chunk: ChunkDetail
    similarity_score: float
    highlight: Optional[str]
```

---

## Symbolic Memory API Responses

### Relationship
```python
class Relationship(BaseModel):
    id: str
    source_entity_id: str
    source_entity_name: str
    target_entity_id: str
    target_entity_name: str
    relationship_type: str
    confidence: float
    lifecycle_state: LifecycleState
    properties: Dict[str, Any]
    created_at: datetime
    source_document_ids: List[str]
```

### Path
```python
class PathStep(BaseModel):
    entity_id: str
    entity_name: str
    entity_type: str
    relationship_type: str
    relationship_id: str

class Path(BaseModel):
    source_entity_id: str
    source_entity_name: str
    target_entity_id: str
    target_entity_name: str
    steps: List[PathStep]
    total_hops: int
    min_confidence: float
```

### SubGraph
```python
class SubGraph(BaseModel):
    root_entity_id: str
    root_entity_name: str
    entities: List[EntitySummary]
    relationships: List[Relationship]
    depth_reached: int
    truncated: bool
```

---

## Sub-Query API Responses

### VerificationResult
```python
class VerificationResult(BaseModel):
    supported: bool
    confidence: float
    reasoning: str
    evidence_quotes: List[str]
```

---

## Error Types

```python
class RLMError(Exception):
    pass

class StaleEntityError(RLMError):
    def __init__(self, entity_id: str):
        self.entity_id = entity_id
        super().__init__(f"Entity {entity_id} no longer exists")

class BudgetExhaustedError(RLMError):
    def __init__(self, budget_type: str, limit: int):
        self.budget_type = budget_type
        self.limit = limit
        super().__init__(f"{budget_type} budget exhausted (limit: {limit})")

class REPLExecutionError(RLMError):
    def __init__(self, code: str, error: str, retry_hint: Optional[str] = None):
        self.code = code
        self.error = error
        self.retry_hint = retry_hint
        super().__init__(f"REPL execution failed: {error}")

class CircuitBreakerTripped(RLMError):
    def __init__(self, iterations_without_progress: int):
        self.iterations = iterations_without_progress
        super().__init__(f"No progress after {iterations_without_progress} iterations")
```

---

## REPL Execution Types

### REPLExecutionResult
```python
class REPLExecutionResult(BaseModel):
    success: bool
    output: str
    error: Optional[str]
    retry_hint: Optional[str]
    execution_time_ms: int
    new_entities_discovered: List[str]
    new_relationships_discovered: List[str]
```

### ProgressTracker
```python
class ProgressTracker(BaseModel):
    iteration: int
    entities_discovered: set[str]
    relationships_discovered: set[str]
    iterations_without_progress: int
    
    def record_iteration(self, result: REPLExecutionResult) -> bool:
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
        return self.iterations_without_progress >= threshold
```

---

## Execution Trace Schema

```python
class SubQueryLog(BaseModel):
    query_type: str
    prompt_preview: str
    response_preview: str
    tokens_used: int
    duration_ms: int

class ExecutionTraceEntry(BaseModel):
    iteration: int
    timestamp: datetime
    code: str
    result: REPLExecutionResult
    sub_queries: List[SubQueryLog]
    budget_remaining: int
    cumulative_entities: int
    cumulative_relationships: int

class ExecutionTrace(BaseModel):
    query_id: str
    tenant_id: str
    original_query: str
    started_at: datetime
    completed_at: datetime
    total_iterations: int
    final_status: str  # "completed", "timeout", "budget_exhausted", "circuit_breaker"
    entries: List[ExecutionTraceEntry]
    total_tokens_used: int
    total_sub_queries: int
    total_entities_discovered: int
    total_relationships_discovered: int
    estimated_cost_usd: float
```

---

## API Method Signatures

```python
class SemanticMemoryAPI:
    def find_entities(self, entity_type: str = None, 
                      limit: int = 50,
                      include_staging: bool = True) -> List[EntitySummary]: ...
    
    def find_similar(self, query: str, k: int = 10,
                     entity_type: str = None,
                     min_confidence: float = 0.0,
                     include_staging: bool = True) -> List[EntityMatch]: ...
    
    def get_entity(self, entity_id: str) -> EntityDetail: ...
    
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
                          include_staging: bool = True) -> List[Relationship]: ...
    
    def find_path(self, source_id: str, target_id: str,
                  max_depth: int = 3) -> List[Path]: ...
    
    def get_related_entities(self, entity_id: str,
                             relationship_type: str,
                             include_staging: bool = True) -> List[EntitySummary]: ...
    
    def traverse(self, start_id: str,
                 relationship_types: List[str] = None,
                 depth: int = 2,
                 max_entities: int = 100) -> SubGraph: ...


class SubQueryAPI:
    def query(self, prompt: str, max_tokens: int = 500) -> str: ...
    def verify(self, claim: str, evidence: str) -> VerificationResult: ...
    def summarize(self, content: str, focus: str = None) -> str: ...
```

---

## Retry Hint Generation

```python
COMMON_ERROR_HINTS = {
    "AttributeError": lambda e: f"Object doesn't have that attribute. Check the schema.",
    "KeyError": lambda e: f"Key not found. Check available keys.",
    "TypeError": lambda e: f"Type mismatch. Check expected types.",
    "StaleEntityError": lambda e: f"Entity was archived. Search for it again.",
    "BudgetExhaustedError": lambda e: "Budget exhausted. Provide final answer now.",
}
```

---

## LLM Quick Reference

For the system prompt:

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
