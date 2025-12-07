"""
Query Interface Types
Platform Foundation → Brain (sync) → QueryResponse

RFC v2 Interface Contract - Query Flow
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class QueryType(str, Enum):
    """Supported query types."""
    SEMANTIC_SEARCH = "semantic_search"
    VERIFY_STATEMENT = "verify_statement"
    RETRIEVE_ENTITIES = "retrieve_entities"
    GET_SCHEMA = "get_schema"


class QueryErrorCode(str, Enum):
    """Error codes for query operations."""
    QUERY_SUCCESS = "QUERY_SUCCESS"
    NO_RESULTS = "NO_RESULTS"
    INVALID_QUERY = "INVALID_QUERY"
    TENANT_NOT_FOUND = "TENANT_NOT_FOUND"
    MODEL_ERROR = "MODEL_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class QueryError(BaseModel):
    """Error details for failed queries."""
    code: QueryErrorCode
    message: str = Field(description="Human-readable error message")


class QueryRequest(BaseModel):
    """
    Synchronous query request from Platform to Brain.
    
    Platform → Brain (HTTP) → QueryResponse
    Timeout: 30 seconds
    """
    tenant_id: str = Field(description="UUID, always required for tenant isolation")
    
    query_type: QueryType = Field(description="Type of query to execute")
    
    query_text: Optional[str] = Field(
        default=None,
        description="For semantic_search - the search query"
    )
    max_results: Optional[int] = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return"
    )
    similarity_threshold: Optional[float] = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for results"
    )
    
    statement: Optional[str] = Field(
        default=None,
        description="For verify_statement - the statement to verify"
    )
    
    entity_type: Optional[str] = Field(
        default=None,
        description="For retrieve_entities - filter by ontology type e.g., 'fibo:FinancialInstrument'"
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="For retrieve_entities - additional property filters"
    )
    
    ontology_domain: Optional[str] = Field(
        default=None,
        description="For get_schema - e.g., 'fibo', 'fhir', 'dcsa'"
    )
    
    include_provenance: Optional[bool] = Field(
        default=False,
        description="Include source document references in results"
    )
    include_confidence: Optional[bool] = Field(
        default=False,
        description="Include confidence scores in results"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174002",
                "query_type": "semantic_search",
                "query_text": "financial instruments",
                "max_results": 10,
                "include_provenance": True
            }
        }


class SemanticSearchResult(BaseModel):
    """Result item for semantic_search queries."""
    entity_id: str
    entity_type: str
    content: Dict[str, Any]
    similarity_score: float = Field(ge=0.0, le=1.0)
    source_document_id: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class VerifyStatementResult(BaseModel):
    """Result for verify_statement queries."""
    verified: bool
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_entities: List[str] = Field(default_factory=list)
    contradicting_entities: List[str] = Field(default_factory=list)
    explanation: str


class RetrieveEntitiesResult(BaseModel):
    """Result item for retrieve_entities queries."""
    entity_id: str
    entity_type: str
    content: Dict[str, Any]
    created_at: str
    source_document_id: str


class PropertyDefinition(BaseModel):
    """Property definition in schema."""
    name: str
    type: str
    required: bool = False
    description: Optional[str] = None


class RelationshipDefinition(BaseModel):
    """Relationship definition in schema."""
    name: str
    target_type: str
    cardinality: str = Field(description="'one' or 'many'")


class GetSchemaResult(BaseModel):
    """Result item for get_schema queries."""
    entity_type: str
    properties: List[PropertyDefinition] = Field(default_factory=list)
    relationships: List[RelationshipDefinition] = Field(default_factory=list)


class TokensConsumed(BaseModel):
    """Token consumption for metering."""
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class QueryResponse(BaseModel):
    """
    Response from Brain to Platform for query requests.
    
    Brain → Platform (HTTP response)
    """
    success: bool = Field(description="Whether the query succeeded")
    
    results: List[Any] = Field(
        default_factory=list,
        description="Query results - type depends on query_type"
    )
    total_count: int = Field(
        ge=0,
        default=0,
        description="Total matching results (may exceed returned count)"
    )
    
    tokens_consumed: TokensConsumed = Field(
        description="Token usage for metering - CRITICAL for billing"
    )
    
    duration_ms: int = Field(
        ge=0,
        default=0,
        description="Query processing duration in milliseconds"
    )
    
    error: Optional[QueryError] = Field(
        default=None,
        description="Error details if success is False"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "results": [
                    {
                        "entity_id": "ent-123",
                        "entity_type": "fibo:Contract",
                        "content": {"name": "Service Agreement"},
                        "similarity_score": 0.95
                    }
                ],
                "total_count": 1,
                "tokens_consumed": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "total_tokens": 150
                },
                "duration_ms": 250
            }
        }
