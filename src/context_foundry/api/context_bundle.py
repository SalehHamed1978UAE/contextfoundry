"""
Context Bundle API Models - Pydantic schemas for the public Context Bundle API.
Pillar 4: "Deliver structured, trustworthy truth to AI."

The Context Bundle is the formal contract between Context Foundry and AI applications.
It provides structured, trustworthy context with explicit uncertainty boundaries.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class FrontierReason(str, Enum):
    """Reasons why graph traversal stopped at a node."""
    MAX_HOPS_REACHED = "max_hops_reached"
    NO_OUTGOING_RELATIONSHIPS = "no_outgoing_relationships"
    LOW_CONFIDENCE_PATH = "low_confidence_path"
    ENTITY_NOT_ACTIVE = "entity_not_active"
    CYCLE_DETECTED = "cycle_detected"


class FocalEntity(BaseModel):
    """An entity that is the primary subject of the query."""
    id: str = Field(..., description="Entity UUID")
    name: str = Field(..., description="Entity name")
    entity_type: str = Field(..., description="Entity type from ontology")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score 0-1")
    lifecycle_state: str = Field(..., description="Entity lifecycle state")
    description: Optional[str] = Field(None, description="Entity description")
    properties: Optional[Dict[str, Any]] = Field(None, description="Entity properties")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Payment Database",
                "entity_type": "DATABASE",
                "confidence": 0.95,
                "lifecycle_state": "TRUSTED",
                "description": "Primary payment processing database",
                "properties": {"tier": "critical", "region": "us-east-1"}
            }
        }


class RelatedEntity(BaseModel):
    """An entity within the N-hop neighborhood of focal entities."""
    id: str = Field(..., description="Entity UUID")
    name: str = Field(..., description="Entity name")
    entity_type: str = Field(..., description="Entity type from ontology")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score 0-1")
    lifecycle_state: str = Field(..., description="Entity lifecycle state")
    hop_distance: int = Field(..., ge=1, description="Number of hops from focal entity")
    path_confidence: float = Field(..., ge=0, le=1, description="Confidence along the path to this entity")
    description: Optional[str] = Field(None, description="Entity description")
    properties: Optional[Dict[str, Any]] = Field(None, description="Entity properties")


class Relationship(BaseModel):
    """A relationship between two entities."""
    id: str = Field(..., description="Relationship UUID")
    source_id: str = Field(..., description="Source entity UUID")
    source_name: str = Field(..., description="Source entity name")
    target_id: str = Field(..., description="Target entity UUID")
    target_name: str = Field(..., description="Target entity name")
    relationship_type: str = Field(..., description="Relationship type")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score 0-1")
    properties: Optional[Dict[str, Any]] = Field(None, description="Relationship properties")
    source_sentence: Optional[str] = Field(None, description="Source sentence from document")


class DocumentReference(BaseModel):
    """Reference to a source document."""
    id: str = Field(..., description="Document UUID")
    title: str = Field(..., description="Document title")
    doc_type: str = Field(..., description="Document type")
    content_preview: str = Field(..., description="Content preview (first 500 chars)")
    similarity: float = Field(..., ge=0, le=1, description="Semantic similarity score")
    chunk_index: Optional[int] = Field(None, description="Chunk index if chunked")


class ConfidenceSummary(BaseModel):
    """Summary of confidence across the bundle."""
    overall: float = Field(..., ge=0, le=1, description="Overall confidence 0-1")
    semantic_confidence: float = Field(..., ge=0, le=1, description="Semantic memory confidence")
    episodic_confidence: float = Field(..., ge=0, le=1, description="Episodic memory confidence")
    symbolic_confidence: float = Field(..., ge=0, le=1, description="Symbolic memory confidence")
    low_confidence_entities: List[str] = Field(default_factory=list, description="Entities below threshold")
    recommendation: str = Field(..., description="Action recommendation: proceed, caution, insufficient_context")


class IncidentPattern(BaseModel):
    """A historical incident pattern - 'This happened before'."""
    incident_id: str = Field(..., description="Incident identifier")
    title: str = Field(..., description="Incident title")
    occurred_at: datetime = Field(..., description="When incident occurred")
    severity: str = Field(..., description="Incident severity")
    similarity: float = Field(..., ge=0, le=1, description="Similarity to current query")
    affected_entities: List[str] = Field(default_factory=list, description="Entities affected")
    resolution_summary: Optional[str] = Field(None, description="How it was resolved")


class ChangeEvent(BaseModel):
    """A recent change event - 'This changed recently'."""
    entity_id: str = Field(..., description="Changed entity UUID")
    entity_name: str = Field(..., description="Changed entity name")
    change_type: str = Field(..., description="Type of change: created, updated, deprecated")
    changed_at: datetime = Field(..., description="When change occurred")
    changed_by: Optional[str] = Field(None, description="Who made the change")
    description: Optional[str] = Field(None, description="Change description")


class ApplicableRule(BaseModel):
    """A symbolic rule that applies to this context."""
    id: str = Field(..., description="Rule UUID")
    name: str = Field(..., description="Rule name")
    rule_type: str = Field(..., description="Rule type")
    priority: int = Field(..., description="Rule priority")
    condition: str = Field(..., description="Rule condition")
    action: str = Field(..., description="Rule action")
    match_score: Optional[float] = Field(None, description="Match relevance score")


class FrontierNode(BaseModel):
    """A node where graph traversal stopped - marks knowledge boundaries."""
    entity_id: str = Field(..., description="Entity UUID at frontier")
    entity_name: str = Field(..., description="Entity name at frontier")
    entity_type: str = Field(..., description="Entity type")
    reason: FrontierReason = Field(..., description="Why traversal stopped")
    reason_details: Optional[str] = Field(None, description="Additional context for the stop reason")
    potential_connections: int = Field(0, ge=0, description="Number of unexplored edges from this node")
    inferred_impact: Optional[str] = Field(None, description="Speculative inference about what lies beyond")

    class Config:
        json_schema_extra = {
            "example": {
                "entity_id": "550e8400-e29b-41d4-a716-446655440001",
                "entity_name": "External Payment Gateway",
                "entity_type": "SERVICE",
                "reason": "no_outgoing_relationships",
                "reason_details": "No documented downstream consumers",
                "potential_connections": 0,
                "inferred_impact": "May impact external merchant integrations"
            }
        }


class RetrievalMeta(BaseModel):
    """Metadata about the retrieval process for debugging."""
    semantic_query_time_ms: float = Field(..., description="Time spent querying semantic memory")
    episodic_query_time_ms: float = Field(..., description="Time spent querying episodic memory")
    symbolic_query_time_ms: float = Field(..., description="Time spent querying symbolic memory")
    graph_traversal_time_ms: float = Field(0, description="Time spent on graph traversal")
    total_time_ms: float = Field(..., description="Total retrieval time")
    entities_considered: int = Field(..., description="Total entities evaluated")
    entities_included: int = Field(..., description="Entities included in bundle")
    relationships_considered: int = Field(0, description="Relationships evaluated")
    relationships_included: int = Field(0, description="Relationships included")
    filter_reason_counts: Dict[str, int] = Field(default_factory=dict, description="Why entities were excluded")


class SpeculativeInference(BaseModel):
    """An AI-inferred relationship beyond confirmed knowledge."""
    source_entity_id: str = Field(..., description="Source entity UUID")
    source_entity_name: str = Field(..., description="Source entity name")
    target_entity_id: str = Field(..., description="Target entity UUID")
    target_entity_name: str = Field(..., description="Target entity name")
    relationship_type: str = Field(..., description="Inferred relationship type")
    confidence: float = Field(..., ge=0, le=1, description="Inference confidence")
    rule_name: str = Field(..., description="Rule that produced inference")
    explanation: str = Field(..., description="Why this was inferred")


class APIContextBundle(BaseModel):
    """
    The Context Bundle: A Contract for Trustworthy Reasoning.
    
    This is the formal delivery mechanism for structured, trustworthy context
    from Context Foundry to AI applications.
    """
    version: str = Field("1.0.0", description="API version for compatibility")
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique query identifier")
    query: str = Field(..., description="Original query text")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Bundle creation time")
    
    focal_entities: List[FocalEntity] = Field(default_factory=list, description="Primary entities the query is about")
    
    related_entities: List[RelatedEntity] = Field(default_factory=list, description="Entities within hop radius")
    relationships: List[Relationship] = Field(default_factory=list, description="Relationships connecting entities")
    graph_depth: int = Field(0, ge=0, description="Actual traversal depth achieved")
    
    source_documents: List[DocumentReference] = Field(default_factory=list, description="Source documents for provenance")
    confidence_summary: Optional[ConfidenceSummary] = Field(None, description="Confidence breakdown")
    
    similar_incidents: List[IncidentPattern] = Field(default_factory=list, description="Historical incident patterns")
    recent_changes: List[ChangeEvent] = Field(default_factory=list, description="Recent entity changes")
    
    applicable_rules: List[ApplicableRule] = Field(default_factory=list, description="Symbolic rules that apply")
    
    speculative_inferences: List[SpeculativeInference] = Field(default_factory=list, description="AI-inferred relationships")
    
    frontier_nodes: List[FrontierNode] = Field(default_factory=list, description="Where traversal stopped")
    knowledge_gaps: List[str] = Field(default_factory=list, description="What we don't know")
    
    retrieval_meta: Optional[RetrievalMeta] = Field(None, description="Retrieval timing and stats")
    
    overall_confidence: float = Field(0.0, ge=0, le=1, description="Overall bundle confidence")

    class Config:
        json_schema_extra = {
            "example": {
                "version": "1.0.0",
                "query_id": "abc123",
                "query": "What is affected if Payment Database goes down?",
                "focal_entities": [
                    {
                        "id": "uuid1",
                        "name": "Payment Database",
                        "entity_type": "DATABASE",
                        "confidence": 0.95,
                        "lifecycle_state": "TRUSTED"
                    }
                ],
                "knowledge_gaps": ["No visibility into downstream consumers of User Database"],
                "overall_confidence": 0.87
            }
        }


class ContextBundleRequest(BaseModel):
    """Request schema for the Context Bundle API."""
    query: str = Field(..., min_length=1, max_length=2000, description="Natural language query")
    focal_entity: Optional[str] = Field(None, description="Optional: specific entity to focus on")
    max_hops: int = Field(2, ge=1, le=5, description="Maximum graph traversal depth")
    include_episodic: bool = Field(True, description="Include similar incidents and documents")
    include_symbolic: bool = Field(True, description="Include applicable rules")
    include_speculative: bool = Field(True, description="Include AI-inferred relationships")
    min_confidence: float = Field(0.5, ge=0, le=1, description="Minimum confidence threshold")
    max_entities: int = Field(50, ge=1, le=200, description="Maximum entities to return")
    max_documents: int = Field(10, ge=1, le=50, description="Maximum documents to return")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What services are affected if Payment Database goes down?",
                "focal_entity": "Payment Database",
                "max_hops": 2,
                "include_episodic": True,
                "include_symbolic": True
            }
        }


class ContextBundleResponse(BaseModel):
    """Response schema for the Context Bundle API."""
    success: bool = Field(..., description="Whether the request succeeded")
    bundle: Optional[APIContextBundle] = Field(None, description="The context bundle")
    error: Optional[str] = Field(None, description="Error message if failed")
    meta: Optional[RetrievalMeta] = Field(None, description="Retrieval metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "bundle": {
                    "version": "1.0.0",
                    "query": "What is affected if Payment Database goes down?",
                    "overall_confidence": 0.87
                }
            }
        }
