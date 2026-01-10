"""
DTL SQLAlchemy ORM Models

These models map to the DTL database schema.
Uses CF's existing Base and session patterns.
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Text, Float, Boolean, Integer,
    DateTime, ForeignKey, Enum as SQLEnum, JSON, Index, text, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, TSTZRANGE
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, Field

from src.context_foundry.models.schema import Base


class DecisionLifecycle(str, Enum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    APPROVED = "approved"
    ENACTED = "enacted"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    REVOKED = "revoked"


class CategoryLifecycle(str, Enum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    MERGED = "merged"


class SensitivityLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class EvidenceType(str, Enum):
    SLACK_MSG = "slack_msg"
    EMAIL = "email"
    MEETING_SEGMENT = "meeting_segment"
    JIRA = "jira"
    DOC = "doc"
    PR_COMMENT = "pr_comment"
    CODE_REVIEW = "code_review"
    MANUAL_NOTE = "manual_note"
    AGENT_LOG = "agent_log"


class DecisionEntityRole(str, Enum):
    SUBJECT = "subject"
    AFFECTED_PARTY = "affected_party"
    DECISION_MAKER = "decision_maker"
    APPROVER = "approver"
    ADVISOR = "advisor"
    IMPLEMENTER = "implementer"
    POLICY = "policy"
    SYSTEM_CONSULTED = "system_consulted"
    CONTEXT = "context"


class ResultStatus(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class DecisionTrace(Base):
    """Core decision event (Layer 1)"""
    __tablename__ = "decision_traces"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id = Column(String(50), nullable=False, unique=True)
    
    valid_from = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    valid_until = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime(9999, 12, 31))
    sys_period = Column(TSTZRANGE)
    
    decision_timestamp = Column(DateTime(timezone=True), nullable=False)
    decision_summary = Column(Text, nullable=False)
    decision_choice = Column(JSON, nullable=False, default=dict)
    
    decision_maker_id = Column(UUID(as_uuid=True), nullable=False)
    
    decision_type = Column(Text)
    decision_type_confidence = Column(Float)
    
    rationale_summary = Column(Text)
    rationale_structured = Column(JSON, nullable=False, default=dict)
    rationale_embedding = Column(Vector(1536))
    
    context_snapshot = Column(JSON, nullable=False, default=dict)
    
    lifecycle_state = Column(String(20), nullable=False, default="draft")
    
    source_system = Column(Text, nullable=False)
    source_reference = Column(Text)
    extraction_confidence = Column(Float)
    
    sensitivity = Column(String(20), nullable=False, default="internal")
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    created_by = Column(String(255), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    evidence = relationship("DecisionEvidence", back_populates="decision", cascade="all, delete-orphan")
    entity_links = relationship("DecisionEntityLink", back_populates="decision", cascade="all, delete-orphan")
    precedent_links = relationship("DecisionPrecedentLink", foreign_keys="DecisionPrecedentLink.decision_id", back_populates="decision", cascade="all, delete-orphan")
    exceptions = relationship("DecisionException", back_populates="decision", cascade="all, delete-orphan")
    confidence_scores = relationship("DecisionConfidenceScore", back_populates="decision", cascade="all, delete-orphan")
    executions = relationship("DecisionExecution", back_populates="decision", cascade="all, delete-orphan")
    results = relationship("DecisionResult", back_populates="decision", cascade="all, delete-orphan")
    assessments = relationship("DecisionAssessment", back_populates="decision", cascade="all, delete-orphan")


class DecisionEvidence(Base):
    """Evidence/receipts for decisions"""
    __tablename__ = "decision_evidence"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id = Column(UUID(as_uuid=True), ForeignKey("decision_traces.id", ondelete="CASCADE"), nullable=False)
    
    evidence_type = Column(String(50), nullable=False)
    source_uri = Column(Text)
    source_id = Column(Text)
    excerpt = Column(Text)
    excerpt_hash = Column(Text)
    event_timestamp = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    decision = relationship("DecisionTrace", back_populates="evidence")


class DecisionEntityLink(Base):
    """Links decisions to CF entities"""
    __tablename__ = "decision_entity_links"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id = Column(UUID(as_uuid=True), ForeignKey("decision_traces.id", ondelete="CASCADE"), nullable=False)
    
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    entity_role = Column(String(50), nullable=False)
    
    acted_at = Column(DateTime(timezone=True))
    resolution_method = Column(String(50))
    resolution_confidence = Column(Float)
    entity_state_at_decision = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    decision = relationship("DecisionTrace", back_populates="entity_links")


class DecisionPrecedentLink(Base):
    """Links decisions to precedent decisions"""
    __tablename__ = "decision_precedent_links"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id = Column(UUID(as_uuid=True), ForeignKey("decision_traces.id", ondelete="CASCADE"), nullable=False)
    precedent_decision_id = Column(UUID(as_uuid=True), ForeignKey("decision_traces.id", ondelete="CASCADE"), nullable=False)
    
    link_type = Column(String(50), nullable=False)
    similarity_score = Column(Float)
    match_reasoning = Column(Text)
    
    precedent_applied = Column(Boolean, nullable=False, default=True)
    deviation_reason = Column(Text)
    
    discovered_by = Column(String(50), nullable=False)
    discovered_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    decision = relationship("DecisionTrace", foreign_keys=[decision_id], back_populates="precedent_links")
    precedent = relationship("DecisionTrace", foreign_keys=[precedent_decision_id])


class DecisionException(Base):
    """Policy exceptions invoked in decisions"""
    __tablename__ = "decision_exceptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id = Column(UUID(as_uuid=True), ForeignKey("decision_traces.id", ondelete="CASCADE"), nullable=False)
    
    policy_id = Column(UUID(as_uuid=True))
    policy_name = Column(String(255), nullable=False)
    policy_version = Column(String(50))
    
    exception_type = Column(String(100), nullable=False)
    exception_aspect = Column(Text, nullable=False)
    
    policy_limit = Column(JSON)
    actual_value = Column(JSON)
    deviation_magnitude = Column(JSON)
    
    exception_justification = Column(Text, nullable=False)
    
    exception_requested_by = Column(UUID(as_uuid=True))
    exception_approved_by = Column(UUID(as_uuid=True))
    
    risk_acknowledged = Column(Boolean, nullable=False, default=False)
    risk_notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    decision = relationship("DecisionTrace", back_populates="exceptions")


class DecisionConfidenceScore(Base):
    """Multi-dimensional confidence scores"""
    __tablename__ = "decision_confidence_scores"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id = Column(UUID(as_uuid=True), ForeignKey("decision_traces.id", ondelete="CASCADE"), nullable=False)
    
    overall_confidence = Column(Float, nullable=False)
    
    extraction_accuracy = Column(Float)
    source_reliability = Column(Float)
    temporal_certainty = Column(Float)
    rationale_completeness = Column(Float)
    entity_resolution_confidence = Column(Float)
    
    scoring_model_version = Column(String(50), nullable=False)
    human_reviewed = Column(Boolean, nullable=False, default=False)
    reviewer_id = Column(UUID(as_uuid=True))
    reviewed_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    decision = relationship("DecisionTrace", back_populates="confidence_scores")


class DecisionExecution(Base):
    """Execution records for decisions"""
    __tablename__ = "decision_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id = Column(UUID(as_uuid=True), ForeignKey("decision_traces.id", ondelete="CASCADE"), nullable=False)
    
    expected_outcome = Column(JSON)
    execution_result = Column(JSON)
    executed_at = Column(DateTime(timezone=True))
    executed_by_entity_id = Column(UUID(as_uuid=True))
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    decision = relationship("DecisionTrace", back_populates="executions")


class DecisionResult(Base):
    """Outcome records for decisions"""
    __tablename__ = "decision_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id = Column(UUID(as_uuid=True), ForeignKey("decision_traces.id", ondelete="CASCADE"), nullable=False)
    
    outcome_status = Column(String(20), nullable=False, default="unknown")
    outcome_metrics = Column(JSON, nullable=False, default=dict)
    observed_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    result_notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    decision = relationship("DecisionTrace", back_populates="results")


class DecisionAssessment(Base):
    """Retrospective assessments of decision quality"""
    __tablename__ = "decision_assessments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id = Column(UUID(as_uuid=True), ForeignKey("decision_traces.id", ondelete="CASCADE"), nullable=False)
    
    decision_quality_score = Column(Float)
    assessment_notes = Column(Text)
    assessment_confidence = Column(Float)
    
    assessed_at = Column(DateTime(timezone=True))
    assessed_by_entity_id = Column(UUID(as_uuid=True))
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    decision = relationship("DecisionTrace", back_populates="assessments")


class DecisionCategory(Base):
    """Emergent decision categories"""
    __tablename__ = "decision_categories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    name = Column(Text, nullable=False)
    description = Column(Text)
    
    emerged_from_clustering = Column(Boolean, nullable=False, default=True)
    cluster_id = Column(String(100))
    
    human_validated = Column(Boolean, nullable=False, default=False)
    validated_by = Column(UUID(as_uuid=True))
    validated_at = Column(DateTime(timezone=True))
    
    prototype_embedding = Column(Vector(1536))
    typical_attributes = Column(JSON, nullable=False, default=dict)
    
    lifecycle = Column(String(20), nullable=False, default="proposed")
    merged_into_id = Column(UUID(as_uuid=True), ForeignKey("decision_categories.id"))
    
    usage_count = Column(Integer, nullable=False, default=0)
    last_used_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class SchemaEvolutionProposal(Base):
    """Schema evolution proposals from pattern detection"""
    __tablename__ = "schema_evolution_proposals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    proposal_type = Column(String(50), nullable=False)
    detection_method = Column(String(50))
    
    supporting_decision_count = Column(Integer, nullable=False)
    supporting_decision_ids = Column(ARRAY(UUID(as_uuid=True)))
    detection_confidence = Column(Float, nullable=False)
    
    proposal_summary = Column(Text, nullable=False)
    proposal_details = Column(JSON, nullable=False, default=dict)
    recommendation = Column(Text)
    
    status = Column(String(20), nullable=False, default="pending")
    reviewed_by = Column(UUID(as_uuid=True))
    reviewed_at = Column(DateTime(timezone=True))
    review_notes = Column(Text)
    
    implemented_at = Column(DateTime(timezone=True))
    implementation_notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class DecisionAccessGrant(Base):
    """Explicit access grants for restricted decisions"""
    __tablename__ = "decision_access_grants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    decision_id = Column(UUID(as_uuid=True), ForeignKey("decision_traces.id", ondelete="CASCADE"), nullable=False)
    grantee_id = Column(UUID(as_uuid=True), nullable=False)
    granted_by = Column(UUID(as_uuid=True))
    granted_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class DecisionAccessAudit(Base):
    """Access audit log for decisions"""
    __tablename__ = "decision_access_audit"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    accessor_id = Column(UUID(as_uuid=True), nullable=False)
    accessor_role = Column(String(100))
    
    decision_id = Column(UUID(as_uuid=True), ForeignKey("decision_traces.id"))
    access_type = Column(String(20), nullable=False)
    access_granted = Column(Boolean, nullable=False)
    denial_reason = Column(Text)
    
    access_reason = Column(Text)
    client_ip = Column(String(45))
    user_agent = Column(Text)
    
    accessed_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class DecisionCreate(BaseModel):
    """Pydantic model for creating decisions via API"""
    summary: str
    choice: Dict[str, Any]
    choice_type: str = "approval"
    rationale: str
    decision_type: Optional[str] = None
    decision_maker_id: str
    entity_ids: Optional[List[str]] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    evidence: List[Dict[str, Any]]
    sensitivity: str = "internal"
    tenant_id: str


class PrecedentSearchRequest(BaseModel):
    """Pydantic model for precedent search via API"""
    query: str
    tenant_id: str
    decision_type_hint: Optional[str] = None
    entity_ids: Optional[List[str]] = None
    min_confidence: float = 0.0
    limit: int = 10
    include_negative_outcomes: bool = True


class OutcomeCreate(BaseModel):
    """Pydantic model for recording decision outcomes"""
    outcome_status: str
    metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    notes: Optional[str] = None
