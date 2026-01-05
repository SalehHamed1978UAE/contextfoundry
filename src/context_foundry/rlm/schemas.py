"""
RLM Pydantic Schemas.

Defines all data types for the RLM Memory APIs, execution trace,
and error handling. These schemas ensure the LLM can generate valid code
against predictable data structures.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Set
from pydantic import BaseModel, Field


class LifecycleState(str, Enum):
    """Entity/relationship lifecycle states."""
    STAGING = "STAGING"
    TRUSTED = "TRUSTED"
    ARCHIVED = "ARCHIVED"


class EntitySummary(BaseModel):
    """
    Lightweight entity representation for list operations.
    
    Returned by: find_entities(), find_similar(), find_by_property(), get_related_entities()
    
    Example:
        {
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
    """
    id: str = Field(..., description="Entity UUID")
    name: str = Field(..., description="Display name")
    entity_type: str = Field(..., description="Entity type (PERSON, SERVICE, etc.)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    lifecycle_state: LifecycleState = Field(..., description="STAGING, TRUSTED, or ARCHIVED")
    created_at: datetime = Field(..., description="When entity was created")
    updated_at: datetime = Field(..., description="When entity was last updated")
    primary_property: Optional[str] = Field(None, description="Most important property value")
    property_count: int = Field(0, ge=0, description="Number of properties")
    relationship_count: int = Field(0, ge=0, description="Number of relationships")


class EntityDetail(BaseModel):
    """
    Full entity data including properties and provenance.
    
    Returned by: get_entity()
    
    Example:
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Network Monitoring Service",
            "entity_type": "SERVICE",
            "confidence": 0.89,
            "lifecycle_state": "TRUSTED",
            "properties": {"status": "active", "owner_team": "Infrastructure"},
            "aliases": ["NetMon", "NMS"],
            "source_document_ids": ["doc-123", "doc-456"],
            "extraction_method": "llm_extraction",
            "corroboration_count": 3
        }
    """
    id: str
    name: str
    entity_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    lifecycle_state: LifecycleState
    created_at: datetime
    updated_at: datetime
    properties: Dict[str, Any] = Field(default_factory=dict, description="Full properties dict")
    aliases: List[str] = Field(default_factory=list, description="Known aliases")
    source_document_ids: List[str] = Field(default_factory=list, description="Source documents")
    extraction_method: str = Field("unknown", description="How entity was extracted")
    corroboration_count: int = Field(0, ge=0, description="Number of confirming sources")
    last_verified_at: Optional[datetime] = Field(None, description="Last verification time")
    promoted_at: Optional[datetime] = Field(None, description="When promoted to TRUSTED")


class EntityMatch(BaseModel):
    """
    Entity with similarity score from semantic search.
    
    Returned by: find_similar()
    
    Example:
        {
            "entity": {...EntitySummary...},
            "similarity_score": 0.92,
            "match_type": "semantic"
        }
    """
    entity: EntitySummary
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")
    match_type: str = Field(..., description="exact, semantic, or fuzzy")


class ChunkSummary(BaseModel):
    """
    Lightweight chunk reference.
    
    Returned by: get_document_chunks()
    
    Example:
        {
            "id": "chunk-789",
            "document_id": "doc-123",
            "chunk_index": 4,
            "token_count": 487,
            "preview": "The Network Monitoring Service detected...",
            "created_at": "2024-12-01T10:00:00Z"
        }
    """
    id: str
    document_id: str
    chunk_index: int = Field(..., ge=0, description="Position in document (0-indexed)")
    token_count: int = Field(..., ge=0, description="Approximate token count")
    preview: str = Field(..., description="First 200 chars of content")
    created_at: datetime


class ChunkDetail(BaseModel):
    """
    Full chunk content with provenance.
    
    Returned by: get_chunk()
    
    Example:
        {
            "id": "chunk-789",
            "document_id": "doc-123",
            "chunk_index": 4,
            "content": "The Network Monitoring Service detected an anomaly...",
            "token_count": 487,
            "document_name": "Incident_Report_2024_Q4.pdf",
            "document_type": "pdf",
            "upload_date": "2024-12-01T09:45:00Z",
            "page_numbers": [12, 13]
        }
    """
    id: str
    document_id: str
    chunk_index: int = Field(..., ge=0)
    content: str = Field(..., description="Full chunk text")
    token_count: int = Field(..., ge=0)
    created_at: datetime
    document_name: str = Field(..., description="Original filename")
    document_type: str = Field(..., description="pdf, docx, txt, etc.")
    upload_date: datetime
    page_numbers: Optional[List[int]] = Field(None, description="Page numbers for PDFs")


class ChunkMatch(BaseModel):
    """
    Chunk with similarity score from semantic search.
    
    Returned by: episodic.search()
    
    Example:
        {
            "chunk": {...ChunkDetail...},
            "similarity_score": 0.87,
            "highlight": "...the **Network Monitoring Service** detected an **anomaly**..."
        }
    """
    chunk: ChunkDetail
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    highlight: Optional[str] = Field(None, description="Snippet with query terms highlighted")


class ProvenanceInfo(BaseModel):
    """
    Detailed source tracking for a chunk.
    
    Returned by: get_provenance()
    """
    chunk_id: str
    document_id: str
    document_name: str
    document_type: str
    upload_date: datetime
    uploaded_by: Optional[str] = Field(None, description="User ID if available")
    page_numbers: Optional[List[int]] = None
    section_title: Optional[str] = None
    processing_steps: List[str] = Field(
        default_factory=list, 
        description="Chain of custody: pdf_extraction, chunking, embedding, etc."
    )


class Relationship(BaseModel):
    """
    Single relationship between entities.
    
    Returned by: get_relationships()
    
    Example:
        {
            "id": "rel-001",
            "source_entity_id": "entity-nms",
            "source_entity_name": "Network Monitoring Service",
            "target_entity_id": "entity-inc-142",
            "target_entity_name": "INC-2024-0142",
            "relationship_type": "TRIGGERED_BY",
            "confidence": 0.85,
            "lifecycle_state": "TRUSTED",
            "properties": {"trigger_time": "2024-12-15T14:32:00Z"}
        }
    """
    id: str
    source_entity_id: str
    source_entity_name: str = Field(..., description="Denormalized for convenience")
    target_entity_id: str
    target_entity_name: str = Field(..., description="Denormalized for convenience")
    relationship_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    lifecycle_state: LifecycleState
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    source_document_ids: List[str] = Field(default_factory=list)


class PathStep(BaseModel):
    """Single step in a relationship path."""
    entity_id: str
    entity_name: str
    entity_type: str
    relationship_type: str = Field(..., description="Relationship TO this entity")
    relationship_id: str


class Path(BaseModel):
    """
    Relationship path between two entities.
    
    Returned by: find_path()
    
    Example:
        {
            "source_entity_id": "entity-nms",
            "source_entity_name": "Network Monitoring Service",
            "target_entity_id": "entity-email-gw",
            "target_entity_name": "Email Gateway",
            "steps": [...],
            "total_hops": 2,
            "min_confidence": 0.78
        }
    """
    source_entity_id: str
    source_entity_name: str
    target_entity_id: str
    target_entity_name: str
    steps: List[PathStep] = Field(default_factory=list)
    total_hops: int = Field(..., ge=0)
    min_confidence: float = Field(..., ge=0.0, le=1.0, description="Lowest confidence in path")


class SubGraph(BaseModel):
    """
    Result of graph traversal.
    
    Returned by: traverse()
    
    Example:
        {
            "root_entity_id": "entity-nms",
            "root_entity_name": "Network Monitoring Service",
            "entities": [...],
            "relationships": [...],
            "depth_reached": 2,
            "truncated": false
        }
    """
    root_entity_id: str
    root_entity_name: str
    entities: List[EntitySummary] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    depth_reached: int = Field(..., ge=0, description="Actual depth traversed")
    truncated: bool = Field(False, description="True if hit limit before exhausting graph")


class VerificationResult(BaseModel):
    """
    Result of llm_verify() sub-query.
    
    Example:
        {
            "supported": true,
            "confidence": 0.92,
            "reasoning": "The incident report explicitly states...",
            "evidence_quotes": ["NMS triggered automatic escalation at 14:32 UTC"]
        }
    """
    supported: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., description="Brief explanation")
    evidence_quotes: List[str] = Field(default_factory=list, description="Specific quotes")


class REPLExecutionResult(BaseModel):
    """
    Result of executing code in the sandbox.
    
    Example (success):
        {
            "success": true,
            "output": "Found services: ['Network Monitoring Service', 'NetMon Agent']",
            "error": null,
            "retry_hint": null,
            "execution_time_ms": 245,
            "new_entities_discovered": ["entity-nms", "entity-nma"],
            "new_relationships_discovered": []
        }
    
    Example (error):
        {
            "success": false,
            "output": "",
            "error": "AttributeError: 'EntitySummary' object has no attribute 'full_name'",
            "retry_hint": "EntitySummary has 'name' not 'full_name'. Use entity.name instead.",
            "execution_time_ms": 12,
            "new_entities_discovered": [],
            "new_relationships_discovered": []
        }
    """
    success: bool
    output: str = Field("", description="stdout capture")
    error: Optional[str] = Field(None, description="stderr or exception message")
    retry_hint: Optional[str] = Field(None, description="Suggestion for fixing code")
    execution_time_ms: int = Field(0, ge=0)
    new_entities_discovered: List[str] = Field(default_factory=list, description="Entity IDs")
    new_relationships_discovered: List[str] = Field(default_factory=list, description="Relationship IDs")


class ProgressTracker(BaseModel):
    """
    Tracks progress for circuit breaker logic.
    
    Progress = new entities OR new relationships discovered.
    Circuit breaker trips after 3 consecutive iterations without progress.
    """
    iteration: int = Field(0, ge=0)
    entities_discovered: Set[str] = Field(default_factory=set)
    relationships_discovered: Set[str] = Field(default_factory=set)
    iterations_without_progress: int = Field(0, ge=0)
    
    class Config:
        arbitrary_types_allowed = True
    
    def record_iteration(self, result: REPLExecutionResult) -> bool:
        """Returns True if progress was made."""
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
        """Trip circuit breaker if no progress for N iterations."""
        return self.iterations_without_progress >= threshold


class SubQueryLog(BaseModel):
    """Log entry for a sub-query call."""
    query_type: str = Field(..., description="query, verify, or summarize")
    prompt_preview: str = Field(..., description="First 200 chars of prompt")
    response_preview: str = Field(..., description="First 200 chars of response")
    tokens_used: int = Field(0, ge=0)
    duration_ms: int = Field(0, ge=0)


class ExecutionTraceEntry(BaseModel):
    """Single iteration in execution trace."""
    iteration: int
    timestamp: datetime
    code: str = Field(..., description="Code executed")
    result: REPLExecutionResult
    sub_queries: List[SubQueryLog] = Field(default_factory=list)
    budget_remaining: int = Field(..., ge=0, description="Tokens remaining after iteration")
    cumulative_entities: int = Field(0, ge=0, description="Total unique entities so far")
    cumulative_relationships: int = Field(0, ge=0, description="Total unique relationships so far")


class ExecutionTrace(BaseModel):
    """Full execution trace for audit/debugging."""
    query_id: str
    tenant_id: str
    original_query: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_iterations: int = Field(0, ge=0)
    final_status: str = Field(
        "in_progress", 
        description="completed, timeout, budget_exhausted, circuit_breaker"
    )
    entries: List[ExecutionTraceEntry] = Field(default_factory=list)
    total_tokens_used: int = Field(0, ge=0)
    total_sub_queries: int = Field(0, ge=0)
    total_entities_discovered: int = Field(0, ge=0)
    total_relationships_discovered: int = Field(0, ge=0)
    estimated_cost_usd: float = Field(0.0, ge=0.0)


class RLMConfig(BaseModel):
    """Configuration for RLM execution."""
    max_iterations: int = Field(10, ge=1, le=50)
    iteration_timeout_seconds: int = Field(30, ge=1, le=300)
    total_timeout_seconds: int = Field(120, ge=1, le=600)
    
    sub_query_budget: int = Field(5000, ge=0, description="Token budget for sub-queries")
    max_sub_queries: int = Field(20, ge=0)
    
    root_provider: str = Field("anthropic", description="anthropic or openai")
    root_model: str = Field("claude-sonnet-4-5-20250929")
    sub_provider: str = Field("anthropic")
    sub_model: str = Field("claude-haiku-4-5-20251001")
    
    temperature: float = Field(0.1, ge=0.0, le=2.0)
    max_output_length: int = Field(10000, ge=100)
    
    circuit_breaker_threshold: int = Field(3, ge=1, description="Iterations without progress")


class RLMResult(BaseModel):
    """Final result from RLM execution."""
    query_id: str
    status: str = Field(..., description="completed, timeout, budget_exhausted, circuit_breaker, fallback")
    answer: Optional[Any] = Field(None, description="Final answer from REPL")
    answer_text: Optional[str] = Field(None, description="Formatted answer text")
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    response_mode: str = Field("GROUNDED", description="GROUNDED, GAP, INFERRED")
    
    evidence_chain: List[str] = Field(default_factory=list, description="Evidence references")
    entities_found: List[EntitySummary] = Field(default_factory=list)
    relationships_found: List[Relationship] = Field(default_factory=list)
    
    execution_trace: Optional[ExecutionTrace] = Field(None, description="Full trace for debugging")
    
    latency_ms: int = Field(0, ge=0)
    tokens_used: int = Field(0, ge=0)
    estimated_cost_usd: float = Field(0.0, ge=0.0)


class RLMError(Exception):
    """Base error for RLM execution."""
    pass


class StaleEntityError(RLMError):
    """Entity ID no longer exists (Gardener archived/deleted it)."""
    def __init__(self, entity_id: str):
        self.entity_id = entity_id
        super().__init__(f"Entity {entity_id} no longer exists. It may have been archived by Gardener.")


class BudgetExhaustedError(RLMError):
    """Token or call budget exhausted."""
    def __init__(self, budget_type: str, limit: int):
        self.budget_type = budget_type
        self.limit = limit
        super().__init__(f"{budget_type} budget exhausted (limit: {limit})")


class REPLExecutionError(RLMError):
    """Code execution failed in sandbox."""
    def __init__(self, code: str, error: str, retry_hint: Optional[str] = None):
        self.code = code
        self.error = error
        self.retry_hint = retry_hint
        super().__init__(f"REPL execution failed: {error}")


class CircuitBreakerTripped(RLMError):
    """No progress detected, falling back to standard pipeline."""
    def __init__(self, iterations_without_progress: int):
        self.iterations = iterations_without_progress
        super().__init__(f"No progress after {iterations_without_progress} iterations")
