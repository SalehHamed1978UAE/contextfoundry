"""
Database schema for Context Foundry tri-memory architecture.
- Semantic Memory: Knowledge graph with lifecycle states (STAGING/TRUSTED/ARCHIVED)
- Episodic Memory: Vector embeddings with pgvector
- Symbolic Memory: Rules with priority ordering
"""
import os
from datetime import datetime
from typing import Optional, List
from enum import Enum
from sqlalchemy import (
    create_engine, Column, String, Text, Float, Boolean, Integer,
    DateTime, ForeignKey, Enum as SQLEnum, JSON, Table, Index, text
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from pgvector.sqlalchemy import Vector
import uuid

Base = declarative_base()


class LifecycleState(str, Enum):
    STAGING = "STAGING"
    TRUSTED = "TRUSTED"
    ARCHIVED = "ARCHIVED"


class EntityType(str, Enum):
    SERVICE = "SERVICE"
    TEAM = "TEAM"
    PERSON = "PERSON"
    COMPONENT = "COMPONENT"
    DATABASE = "DATABASE"
    INCIDENT = "INCIDENT"
    RUNBOOK = "RUNBOOK"


class RelationshipType(str, Enum):
    DEPENDS_ON = "DEPENDS_ON"
    OWNS = "OWNS"
    SUPPORTS = "SUPPORTS"
    MEMBER_OF = "MEMBER_OF"
    MANAGES = "MANAGES"
    ESCALATES_TO = "ESCALATES_TO"
    CAUSED_BY = "CAUSED_BY"
    RESOLVED_BY = "RESOLVED_BY"
    DOCUMENTS = "DOCUMENTS"
    AFFECTS = "AFFECTS"
    USES = "USES"


class RuleType(str, Enum):
    INVARIANT = "INVARIANT"
    SAFETY_CHECK = "SAFETY_CHECK"
    ESCALATION_POLICY = "ESCALATION_POLICY"
    VALIDATION = "VALIDATION"


class Entity(Base):
    """Semantic Memory: Entities in the knowledge graph."""
    __tablename__ = "entities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    entity_type = Column(SQLEnum(EntityType), nullable=False, index=True)
    lifecycle_state = Column(SQLEnum(LifecycleState), default=LifecycleState.STAGING, index=True)
    
    properties = Column(JSON, default=dict)
    description = Column(Text)
    
    confidence = Column(Float, default=0.5)
    
    source_document_id = Column(String(255))
    source_section = Column(String(255))
    source_sentence = Column(Text)
    extracted_at = Column(DateTime, default=datetime.utcnow)
    extraction_method = Column(String(50), default="direct_ingest")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    promoted_at = Column(DateTime)
    archived_at = Column(DateTime)
    
    outgoing_relationships = relationship(
        "Relationship",
        foreign_keys="Relationship.source_id",
        back_populates="source_entity"
    )
    incoming_relationships = relationship(
        "Relationship",
        foreign_keys="Relationship.target_id",
        back_populates="target_entity"
    )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "entity_type": self.entity_type.value if self.entity_type else None,
            "lifecycle_state": self.lifecycle_state.value if self.lifecycle_state else None,
            "properties": self.properties,
            "description": self.description,
            "confidence": self.confidence,
            "source_document_id": self.source_document_id,
            "source_sentence": self.source_sentence
        }


class Relationship(Base):
    """Semantic Memory: Relationships between entities."""
    __tablename__ = "relationships"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True)
    target_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True)
    relationship_type = Column(SQLEnum(RelationshipType), nullable=False, index=True)
    lifecycle_state = Column(SQLEnum(LifecycleState), default=LifecycleState.STAGING, index=True)
    
    properties = Column(JSON, default=dict)
    description = Column(Text)
    
    confidence = Column(Float, default=0.5)
    
    source_document_id = Column(String(255))
    source_section = Column(String(255))
    source_sentence = Column(Text)
    extracted_at = Column(DateTime, default=datetime.utcnow)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    source_entity = relationship("Entity", foreign_keys=[source_id], back_populates="outgoing_relationships")
    target_entity = relationship("Entity", foreign_keys=[target_id], back_populates="incoming_relationships")
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "source_id": str(self.source_id),
            "target_id": str(self.target_id),
            "source_name": self.source_entity.name if self.source_entity else None,
            "target_name": self.target_entity.name if self.target_entity else None,
            "relationship_type": self.relationship_type.value if self.relationship_type else None,
            "lifecycle_state": self.lifecycle_state.value if self.lifecycle_state else None,
            "confidence": self.confidence,
            "source_document_id": self.source_document_id,
            "source_sentence": self.source_sentence
        }


class Document(Base):
    """Episodic Memory: Documents with vector embeddings."""
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False, index=True)
    doc_type = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    
    embedding = Column(Vector(1536))
    
    doc_metadata = Column(JSON, default=dict)
    
    source_document_id = Column(String(255))
    source_section = Column(String(255))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "title": self.title,
            "doc_type": self.doc_type,
            "content": self.content[:500] + "..." if len(self.content) > 500 else self.content,
            "metadata": self.doc_metadata,
            "source_document_id": self.source_document_id
        }


class Rule(Base):
    """Symbolic Memory: Business rules and invariants."""
    __tablename__ = "rules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    rule_type = Column(SQLEnum(RuleType), nullable=False, index=True)
    
    description = Column(Text, nullable=False)
    condition = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    
    priority = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    
    entity_types = Column(ARRAY(String))
    relationship_types = Column(ARRAY(String))
    
    rule_metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "rule_type": self.rule_type.value if self.rule_type else None,
            "description": self.description,
            "condition": self.condition,
            "action": self.action,
            "priority": self.priority,
            "is_active": self.is_active,
            "entity_types": self.entity_types,
            "relationship_types": self.relationship_types
        }


class QueryLog(Base):
    """Logging: Every query execution logged for analysis."""
    __tablename__ = "query_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_text = Column(Text, nullable=False)
    
    semantic_entities_count = Column(Integer, default=0)
    semantic_relationships_count = Column(Integer, default=0)
    episodic_documents_count = Column(Integer, default=0)
    rules_checked_count = Column(Integer, default=0)
    rules_passed_count = Column(Integer, default=0)
    
    response_text = Column(Text)
    confidence = Column(Float)
    success = Column(Boolean)
    
    context_bundle = Column(JSON)
    evidence_chain = Column(JSON)
    
    duration_seconds = Column(Float)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class FeedbackRecord(Base):
    """Feedback: Human judgments for learning loop."""
    __tablename__ = "feedback_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_log_id = Column(UUID(as_uuid=True), ForeignKey("query_logs.id"))
    
    query_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    
    judgment = Column(String(20))
    error_type = Column(String(50))
    human_correction = Column(Text)
    severity = Column(String(20))
    
    confidence_was = Column(Float)
    
    processed = Column(Boolean, default=False)
    learning_action = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class ConflictLog(Base):
    """Gardener: Persistent conflict records for review."""
    __tablename__ = "conflict_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conflict_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=True)
    relationship_id = Column(UUID(as_uuid=True), ForeignKey("relationships.id"), nullable=True)
    
    existing_value = Column(Text)
    new_value = Column(Text)
    existing_confidence = Column(Float)
    new_confidence = Column(Float)
    
    resolution = Column(String(50))
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime)
    resolved_by = Column(String(100))
    
    detected_at = Column(DateTime, default=datetime.utcnow)
    cycle_id = Column(String(100))
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "conflict_type": self.conflict_type,
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "relationship_id": str(self.relationship_id) if self.relationship_id else None,
            "existing_value": self.existing_value,
            "new_value": self.new_value,
            "existing_confidence": self.existing_confidence,
            "new_confidence": self.new_confidence,
            "resolution": self.resolution,
            "resolution_notes": self.resolution_notes,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "cycle_id": self.cycle_id,
        }


class MergeAudit(Base):
    """Identity Resolution: Persistent merge audit trail."""
    __tablename__ = "merge_audits"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merged_entity_id = Column(UUID(as_uuid=True), nullable=False)
    merged_entity_name = Column(String(255), nullable=False)
    surviving_entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    surviving_entity_name = Column(String(255), nullable=False)
    entity_type = Column(String(50), nullable=False)
    
    merge_confidence = Column(Float, nullable=False)
    merge_signals = Column(JSON)
    auto_merged = Column(Boolean, default=False)
    relationships_transferred = Column(Integer, default=0)
    properties_merged = Column(JSON)
    
    merged_at = Column(DateTime, default=datetime.utcnow)
    merged_by = Column(String(100), default="identity_resolver")
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "merged_entity_id": str(self.merged_entity_id),
            "merged_entity_name": self.merged_entity_name,
            "surviving_entity_id": str(self.surviving_entity_id),
            "surviving_entity_name": self.surviving_entity_name,
            "entity_type": self.entity_type,
            "merge_confidence": self.merge_confidence,
            "merge_signals": self.merge_signals,
            "auto_merged": self.auto_merged,
            "relationships_transferred": self.relationships_transferred,
            "properties_merged": self.properties_merged,
            "merged_at": self.merged_at.isoformat() if self.merged_at else None,
            "merged_by": self.merged_by,
        }


class DuplicateCandidate(Base):
    """Identity Resolution: Flagged duplicate candidates for review."""
    __tablename__ = "duplicate_candidates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_a_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    entity_b_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    entity_a_name = Column(String(255), nullable=False)
    entity_b_name = Column(String(255), nullable=False)
    entity_type = Column(String(50), nullable=False)
    
    similarity_score = Column(Float, nullable=False)
    signals = Column(JSON)
    merge_decision = Column(String(50), nullable=False)
    reason = Column(Text)
    
    flagged_at = Column(DateTime, default=datetime.utcnow)
    reviewed = Column(Boolean, default=False)
    reviewed_at = Column(DateTime)
    reviewed_by = Column(String(100))
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "entity_a_id": str(self.entity_a_id),
            "entity_b_id": str(self.entity_b_id),
            "entity_a_name": self.entity_a_name,
            "entity_b_name": self.entity_b_name,
            "entity_type": self.entity_type,
            "similarity_score": self.similarity_score,
            "signals": self.signals,
            "merge_decision": self.merge_decision,
            "reason": self.reason,
            "flagged_at": self.flagged_at.isoformat() if self.flagged_at else None,
            "reviewed": self.reviewed,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": self.reviewed_by,
        }


class EvaluationVote(Base):
    """Stores A/B evaluation votes for blind comparison."""
    __tablename__ = "evaluation_votes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pair_id = Column(String(255), nullable=False, unique=True, index=True)
    query_id = Column(String(50), nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    
    a_is_context_foundry = Column(Boolean, nullable=False)
    response_a = Column(Text)
    response_b = Column(Text)
    latency_a_ms = Column(Float)
    latency_b_ms = Column(Float)
    
    human_preference = Column(String(10))
    reviewed_by = Column(String(255), default='anonymous')
    notes = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    voted_at = Column(DateTime)
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "pair_id": self.pair_id,
            "query_id": self.query_id,
            "query_text": self.query_text,
            "a_is_context_foundry": self.a_is_context_foundry,
            "human_preference": self.human_preference,
            "reviewed_by": self.reviewed_by,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "voted_at": self.voted_at.isoformat() if self.voted_at else None,
        }


_engine = None
_session_factory = None


def get_engine():
    """Create database engine from environment with connection pooling."""
    global _engine
    if _engine is None:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        _engine = create_engine(
            database_url, 
            echo=False,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
        )
    return _engine


def get_session():
    """Create a new database session with auto-reconnect."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(bind=engine)
    return _session_factory()


def init_database():
    """Initialize database with all tables and extensions."""
    engine = get_engine()
    
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
        conn.commit()
    
    Base.metadata.create_all(engine)
    print("Database initialized successfully.")
    return engine
