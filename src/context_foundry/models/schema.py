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
    
    embedding = Column(Vector(384))
    
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


def get_engine():
    """Create database engine from environment."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    return create_engine(database_url, echo=False)


def get_session():
    """Create a new database session."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


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
