from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum


# ============================================
# ENUMS
# ============================================

class LifecycleState(str, Enum):
    STAGING = "STAGING"
    TRUSTED = "TRUSTED"
    ARCHIVED = "ARCHIVED"


class Judgment(str, Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIAL = "partial"
    UNCERTAIN = "uncertain"


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class Recommendation(str, Enum):
    PROCEED = "proceed"
    CAUTION = "caution"
    INSUFFICIENT_CONTEXT = "insufficient_context"


# ============================================
# ENTITY & RELATIONSHIP MODELS
# ============================================

class EntityMetadata(BaseModel):
    entity_id: UUID = Field(default_factory=uuid4)
    entity_type: str
    lifecycle_state: LifecycleState = LifecycleState.STAGING
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # Provenance
    source_document_id: Optional[str] = None
    source_section: Optional[str] = None
    source_sentence: Optional[str] = None
    source_span_start: Optional[int] = None
    source_span_end: Optional[int] = None
    extracted_text: Optional[str] = None

    # Properties (entity-specific data)
    properties: Dict[str, Any] = Field(default_factory=dict)


class RelationshipMetadata(BaseModel):
    relationship_id: UUID = Field(default_factory=uuid4)
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: str
    lifecycle_state: LifecycleState = LifecycleState.STAGING
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # Provenance
    source_document_id: Optional[str] = None
    source_sentence: Optional[str] = None

    # Properties
    properties: Dict[str, Any] = Field(default_factory=dict)


# ============================================
# UNCERTAINTY MODELS
# ============================================

class UncertainItem(BaseModel):
    fact: str
    confidence: float
    reason: str
    impact: str


class UncertaintyReport(BaseModel):
    overall_confidence: float
    recommendation: Recommendation
    high_confidence_facts: int = 0
    medium_confidence_facts: int = 0
    low_confidence_facts: int = 0
    low_confidence_items: List[UncertainItem] = Field(default_factory=list)
    unresolved_entities: List[str] = Field(default_factory=list)
    missing_relationships: List[str] = Field(default_factory=list)
    stale_facts: List[str] = Field(default_factory=list)
    uncertainty_reasons: List[str] = Field(default_factory=list)


# ============================================
# CONTEXT BUNDLE
# ============================================

class EvidenceItem(BaseModel):
    fact: str
    source: Dict[str, Any]
    confidence: float


class ContextBundle(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    query_text: str
    session_id: Optional[UUID] = None

    # Retrieved context from three memory layers
    semantic_entities: List[Dict[str, Any]] = Field(default_factory=list)
    semantic_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    episodic_documents: List[Dict[str, Any]] = Field(default_factory=list)
    symbolic_rules_applied: List[Dict[str, Any]] = Field(default_factory=list)
    session_context: List[Dict[str, Any]] = Field(default_factory=list)

    # Uncertainty report
    uncertainty: UncertaintyReport

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    retrieval_latency_ms: Optional[int] = None


# ============================================
# REASONING RESPONSE
# ============================================

class AlternativeInterpretation(BaseModel):
    interpretation: str
    confidence: float
    reasoning: str


class ReasoningResponse(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    bundle_id: UUID

    # Core response
    answer: str
    confidence: float
    confidence_level: ConfidenceLevel

    # Uncertainty details
    uncertain_facts: List[str] = Field(default_factory=list)
    uncertainty_reasons: List[str] = Field(default_factory=list)
    would_help: List[str] = Field(default_factory=list)
    caveats: List[str] = Field(default_factory=list)

    # Evidence
    evidence_chain: List[EvidenceItem] = Field(default_factory=list)

    # Validation
    rules_checked: List[str] = Field(default_factory=list)
    rules_passed: bool = True
    validation_failures: List[Dict[str, Any]] = Field(default_factory=list)

    # Alternatives (if confidence < 0.7)
    alternatives: List[AlternativeInterpretation] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    total_latency_ms: Optional[int] = None


# ============================================
# FEEDBACK
# ============================================

class FeedbackRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)

    # What was evaluated
    bundle_id: Optional[UUID] = None
    query_text: str
    response_text: str

    # Human judgment
    judgment: Judgment
    error_type: Optional[str] = None
    human_correction: Optional[str] = None
    severity: Optional[Severity] = None

    # Context
    confidence_was: Optional[float] = None
    entities_involved: List[UUID] = Field(default_factory=list)
    rules_applied: List[UUID] = Field(default_factory=list)

    # Learning status
    processed: bool = False
    learning_action: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================
# QUERY REQUEST/RESPONSE
# ============================================

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[UUID] = None


class QueryResponse(BaseModel):
    success: bool
    response: Optional[ReasoningResponse] = None
    error: Optional[Dict[str, Any]] = None
