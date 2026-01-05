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


class RuleType(str, Enum):
    INVARIANT = "INVARIANT"
    SAFETY_CHECK = "SAFETY_CHECK"
    ESCALATION_POLICY = "ESCALATION_POLICY"
    VALIDATION = "VALIDATION"


class ConflictType(str, Enum):
    """Types of conflicts that can occur between facts."""
    VALUE_MISMATCH = "VALUE_MISMATCH"
    RELATIONSHIP_CONFLICT = "RELATIONSHIP_CONFLICT"
    TEMPORAL_CONFLICT = "TEMPORAL_CONFLICT"
    DUPLICATE_ENTITY = "DUPLICATE_ENTITY"
    CONTRADICTORY_RULE = "CONTRADICTORY_RULE"


class ConflictStatus(str, Enum):
    """Status of a conflict record."""
    PENDING = "PENDING"
    AUTO_RESOLVED = "AUTO_RESOLVED"
    HUMAN_RESOLVED = "HUMAN_RESOLVED"
    DEFERRED = "DEFERRED"


class ReviewItemType(str, Enum):
    """Types of items that can be queued for human review."""
    CONFLICT = "CONFLICT"
    DUPLICATE = "DUPLICATE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    RULE_VIOLATION = "RULE_VIOLATION"
    MERGE_CANDIDATE = "MERGE_CANDIDATE"


class ReviewStatus(str, Enum):
    """Status of a review queue item."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


class GardenerActionType(str, Enum):
    """Types of actions the Gardener agent can take."""
    PROMOTE = "PROMOTE"
    DEMOTE = "DEMOTE"
    ARCHIVE = "ARCHIVE"
    DECAY = "DECAY"
    MERGE = "MERGE"
    FLAG_CONFLICT = "FLAG_CONFLICT"
    RESOLVE_CONFLICT = "RESOLVE_CONFLICT"
    VALIDATE = "VALIDATE"


class ValidationStatus(str, Enum):
    """Validation status for facts (entities/relationships) in STAGING."""
    PENDING = "PENDING"      # Not yet validated
    VALID = "VALID"          # Passed all validation checks
    INVALID = "INVALID"      # Failed validation (has errors)
    CONFLICT = "CONFLICT"    # Conflicts with existing TRUSTED data


class Entity(Base):
    """Semantic Memory: Entities in the knowledge graph."""
    __tablename__ = "entities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), index=True)
    name = Column(String(255), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False, index=True)
    lifecycle_state = Column(SQLEnum(LifecycleState), default=LifecycleState.STAGING, index=True)
    validation_status = Column(SQLEnum(ValidationStatus), default=ValidationStatus.PENDING, index=True)
    
    properties = Column(JSON, default=dict)
    description = Column(Text)
    
    name_embedding = Column(Vector(1536))
    
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
    last_validated_at = Column(DateTime)
    
    valid_from = Column(DateTime, default=datetime.utcnow, index=True)
    valid_to = Column(DateTime, index=True)
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("entities.id"))
    change_reason = Column(Text)
    
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
            "entity_type": self.entity_type,
            "lifecycle_state": self.lifecycle_state.value if self.lifecycle_state else None,
            "properties": self.properties,
            "description": self.description,
            "confidence": self.confidence,
            "source_document_id": self.source_document_id,
            "source_sentence": self.source_sentence,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "superseded_by": str(self.superseded_by) if self.superseded_by else None,
            "change_reason": self.change_reason
        }


class Relationship(Base):
    """Semantic Memory: Relationships between entities."""
    __tablename__ = "relationships"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), index=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True)
    target_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True)
    relationship_type = Column(String(100), nullable=False, index=True)
    lifecycle_state = Column(SQLEnum(LifecycleState), default=LifecycleState.STAGING, index=True)
    validation_status = Column(SQLEnum(ValidationStatus), default=ValidationStatus.PENDING, index=True)
    
    properties = Column(JSON, default=dict)
    description = Column(Text)
    
    confidence = Column(Float, default=0.5)
    
    source_document_id = Column(String(255))
    source_section = Column(String(255))
    source_sentence = Column(Text)
    extracted_at = Column(DateTime, default=datetime.utcnow)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_validated_at = Column(DateTime)
    
    valid_from = Column(DateTime, default=datetime.utcnow, index=True)
    valid_to = Column(DateTime, index=True)
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("relationships.id"))
    change_reason = Column(Text)
    
    source_entity = relationship("Entity", foreign_keys=[source_id], back_populates="outgoing_relationships")
    target_entity = relationship("Entity", foreign_keys=[target_id], back_populates="incoming_relationships")
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "source_id": str(self.source_id),
            "target_id": str(self.target_id),
            "source_name": self.source_entity.name if self.source_entity else None,
            "target_name": self.target_entity.name if self.target_entity else None,
            "relationship_type": self.relationship_type,
            "lifecycle_state": self.lifecycle_state.value if self.lifecycle_state else None,
            "confidence": self.confidence,
            "source_document_id": self.source_document_id,
            "source_sentence": self.source_sentence,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "superseded_by": str(self.superseded_by) if self.superseded_by else None,
            "change_reason": self.change_reason
        }


class Document(Base):
    """Episodic Memory: Documents with vector embeddings."""
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), index=True)
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
    confidence = Column(Float)
    
    judgment = Column(String(20), index=True)
    error_type = Column(String(50), index=True)
    human_correction = Column(Text)
    severity = Column(String(20))
    
    confidence_was = Column(Float)
    
    processed = Column(Boolean, default=False, index=True)
    processed_at = Column(DateTime)
    learning_action = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "query_log_id": str(self.query_log_id) if self.query_log_id else None,
            "query_text": self.query_text,
            "response_text": self.response_text[:500] + "..." if self.response_text and len(self.response_text) > 500 else self.response_text,
            "confidence": self.confidence,
            "judgment": self.judgment,
            "error_type": self.error_type,
            "human_correction": self.human_correction,
            "processed": self.processed,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "learning_action": self.learning_action,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Conflict(Base):
    """Cognitive Loop: Tracks conflicts between two facts (entities or relationships)."""
    __tablename__ = "conflicts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    fact_a_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    fact_a_type = Column(String(20), nullable=False)
    fact_b_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    fact_b_type = Column(String(20), nullable=False)
    
    conflict_type = Column(SQLEnum(ConflictType), nullable=False, index=True)
    status = Column(SQLEnum(ConflictStatus), default=ConflictStatus.PENDING, index=True)
    
    description = Column(Text)
    fact_a_summary = Column(Text)
    fact_b_summary = Column(Text)
    
    confidence_a = Column(Float)
    confidence_b = Column(Float)
    
    resolution = Column(String(50))
    resolution_notes = Column(Text)
    winner_fact_id = Column(UUID(as_uuid=True))
    
    detected_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)
    resolved_by = Column(String(100))
    
    source_document_id = Column(String(255))
    cycle_id = Column(String(100))
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "fact_a_id": str(self.fact_a_id),
            "fact_a_type": self.fact_a_type,
            "fact_b_id": str(self.fact_b_id),
            "fact_b_type": self.fact_b_type,
            "conflict_type": self.conflict_type.value if self.conflict_type else None,
            "status": self.status.value if self.status else None,
            "description": self.description,
            "fact_a_summary": self.fact_a_summary,
            "fact_b_summary": self.fact_b_summary,
            "confidence_a": self.confidence_a,
            "confidence_b": self.confidence_b,
            "resolution": self.resolution,
            "resolution_notes": self.resolution_notes,
            "winner_fact_id": str(self.winner_fact_id) if self.winner_fact_id else None,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
        }


class ReviewQueue(Base):
    """Cognitive Loop: Items awaiting human review."""
    __tablename__ = "review_queue"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    item_type = Column(SQLEnum(ReviewItemType), nullable=False, index=True)
    item_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    priority = Column(Integer, default=50, index=True)
    status = Column(SQLEnum(ReviewStatus), default=ReviewStatus.PENDING, index=True)
    
    title = Column(String(255), nullable=False)
    description = Column(Text)
    context = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    
    assigned_to = Column(String(100))
    reviewed_at = Column(DateTime)
    reviewer_action = Column(String(50))
    reviewer_notes = Column(Text)
    
    source_cycle_id = Column(String(100))
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "item_type": self.item_type.value if self.item_type else None,
            "item_id": str(self.item_id),
            "priority": self.priority,
            "status": self.status.value if self.status else None,
            "title": self.title,
            "description": self.description,
            "context": self.context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "assigned_to": self.assigned_to,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewer_action": self.reviewer_action,
            "reviewer_notes": self.reviewer_notes,
        }


class GardenerLog(Base):
    """Cognitive Loop: Audit trail for all lifecycle changes by the Gardener agent."""
    __tablename__ = "gardener_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    action_type = Column(SQLEnum(GardenerActionType), nullable=False, index=True)
    
    target_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    target_type = Column(String(20), nullable=False)
    target_name = Column(String(255))
    
    old_state = Column(String(20))
    new_state = Column(String(20))
    
    old_confidence = Column(Float)
    new_confidence = Column(Float)
    
    reason = Column(Text, nullable=False)
    details = Column(JSON)
    
    cycle_id = Column(String(100), nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "action_type": self.action_type.value if self.action_type else None,
            "target_id": str(self.target_id),
            "target_type": self.target_type,
            "target_name": self.target_name,
            "old_state": self.old_state,
            "new_state": self.new_state,
            "old_confidence": self.old_confidence,
            "new_confidence": self.new_confidence,
            "reason": self.reason,
            "details": self.details,
            "cycle_id": self.cycle_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ConflictLog(Base):
    """Gardener: Persistent conflict records for review (legacy, use Conflict instead)."""
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


class InferenceRunStatus(str, Enum):
    """Status of an inference run."""
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class ProposedRelationshipStatus(str, Enum):
    """Status of a proposed relationship."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    AUTO_APPROVED = "AUTO_APPROVED"


class InferenceMethod(str, Enum):
    """Method used to infer a relationship."""
    LLM_EXTRACTION = "llm_extraction"
    HEURISTIC_NAME = "heuristic_name"
    HEURISTIC_TRANSITIVE = "heuristic_transitive"


class DocumentChunk(Base):
    """Document chunks for RE processing."""
    __tablename__ = "document_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    char_start = Column(Integer)
    char_end = Column(Integer)
    chunk_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_chunks_doc_index', 'document_id', 'chunk_index', unique=True),
    )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "chunk_index": self.chunk_index,
            "text": self.text[:200] + "..." if len(self.text) > 200 else self.text,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }


class EntityMention(Base):
    """Entity mentions linking entities to document chunks."""
    __tablename__ = "entity_mentions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunks.id"), index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    mention_text = Column(Text, nullable=False)
    char_start = Column(Integer)
    char_end = Column(Integer)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_mentions_entity_chunk', 'entity_id', 'chunk_id', 'char_start', unique=True),
    )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "entity_id": str(self.entity_id),
            "document_id": str(self.document_id),
            "chunk_id": str(self.chunk_id) if self.chunk_id else None,
            "mention_text": self.mention_text,
            "confidence": self.confidence,
        }


class InferenceRun(Base):
    """Track inference runs for idempotency and rollback."""
    __tablename__ = "inference_runs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(SQLEnum(InferenceRunStatus), default=InferenceRunStatus.RUNNING, index=True)
    
    batch_size = Column(Integer, nullable=False)
    entity_filter = Column(JSON)
    prompt_version = Column(String(50), nullable=False)
    ontology_version = Column(String(50))
    domain = Column(String(50), default='IT')
    
    entities_processed = Column(Integer, default=0)
    chunks_analyzed = Column(Integer, default=0)
    relationships_proposed = Column(Integer, default=0)
    relationships_approved = Column(Integer, default=0)
    relationships_rejected = Column(Integer, default=0)
    
    llm_tokens_used = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)
    
    rollback_executed = Column(Boolean, default=False)
    rollback_at = Column(DateTime)
    rollback_reason = Column(Text)
    error_message = Column(Text)
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "status": self.status.value if self.status else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "batch_size": self.batch_size,
            "entities_processed": self.entities_processed,
            "chunks_analyzed": self.chunks_analyzed,
            "relationships_proposed": self.relationships_proposed,
            "relationships_approved": self.relationships_approved,
            "relationships_rejected": self.relationships_rejected,
            "llm_tokens_used": self.llm_tokens_used,
            "estimated_cost_usd": self.estimated_cost_usd,
        }


class InferenceRunChunk(Base):
    """Track which chunks have been processed per run (idempotency)."""
    __tablename__ = "inference_run_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("inference_runs.id"), nullable=False, index=True)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunks.id"), nullable=False)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    status = Column(String(20), default='COMPLETED')
    relationships_found = Column(Integer, default=0)
    processed_at = Column(DateTime, default=datetime.utcnow)
    error_message = Column(Text)
    
    __table_args__ = (
        Index('idx_run_chunk_entity', 'run_id', 'chunk_id', 'entity_id', unique=True),
    )


class ProposedRelationship(Base):
    """Staging area for proposed relationships before approval."""
    __tablename__ = "proposed_relationships"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    source_entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True)
    target_entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True)
    relationship_type = Column(String(50), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    
    inference_run_id = Column(UUID(as_uuid=True), ForeignKey("inference_runs.id"), nullable=False, index=True)
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    source_chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunks.id"))
    evidence_span = Column(Text, nullable=False)
    evidence_char_start = Column(Integer)
    evidence_char_end = Column(Integer)
    
    inference_method = Column(SQLEnum(InferenceMethod), default=InferenceMethod.LLM_EXTRACTION)
    has_lexical_evidence = Column(Boolean, default=False)
    
    status = Column(SQLEnum(ProposedRelationshipStatus), default=ProposedRelationshipStatus.PENDING, index=True)
    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)
    rejection_reason = Column(Text)
    
    corroboration_count = Column(Integer, default=1)
    corroborating_chunks = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_proposed_unique', 'source_entity_id', 'target_entity_id', 'relationship_type', 'source_chunk_id', unique=True),
        Index('idx_proposed_confidence', 'confidence'),
    )
    
    source_entity = relationship("Entity", foreign_keys=[source_entity_id])
    target_entity = relationship("Entity", foreign_keys=[target_entity_id])
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "source_entity_id": str(self.source_entity_id),
            "target_entity_id": str(self.target_entity_id),
            "source_entity_name": self.source_entity.name if self.source_entity else None,
            "target_entity_name": self.target_entity.name if self.target_entity else None,
            "source_entity_type": self.source_entity.entity_type if self.source_entity else None,
            "target_entity_type": self.target_entity.entity_type if self.target_entity else None,
            "relationship_type": self.relationship_type,
            "confidence": self.confidence,
            "evidence_span": self.evidence_span,
            "has_lexical_evidence": self.has_lexical_evidence,
            "status": self.status.value if self.status else None,
            "inference_method": self.inference_method.value if self.inference_method else None,
            "corroboration_count": self.corroboration_count,
        }


class OntologyRelationshipType(Base):
    """Domain ontology configuration for relationship types."""
    __tablename__ = "ontology_relationship_types"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), index=True)
    domain = Column(String(50), nullable=False, index=True)
    relationship_type = Column(String(50), nullable=False)
    definition = Column(Text, nullable=False)
    
    valid_source_types = Column(ARRAY(Text), nullable=False)
    valid_target_types = Column(ARRAY(Text), nullable=False)
    lexical_patterns = Column(ARRAY(Text), nullable=False)
    
    min_confidence = Column(Float, default=0.70)
    auto_approve_confidence = Column(Float, default=0.90)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_ontology_unique', 'tenant_id', 'domain', 'relationship_type', unique=True),
    )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "domain": self.domain,
            "relationship_type": self.relationship_type,
            "definition": self.definition,
            "valid_source_types": self.valid_source_types,
            "valid_target_types": self.valid_target_types,
            "lexical_patterns": self.lexical_patterns,
            "min_confidence": self.min_confidence,
            "auto_approve_confidence": self.auto_approve_confidence,
            "is_active": self.is_active,
        }


class InteractionEvent(Base):
    """Append-only event log for app interactions (Phase 1 logging)."""
    __tablename__ = "cf_interaction_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(36), nullable=False, index=True)
    app_id = Column(String(50), nullable=False, index=True)
    user_id = Column(String(100))
    session_id = Column(String(100))
    trace_id = Column(String(100))
    
    event_type = Column(String(20), nullable=False)
    raw_text = Column(Text)
    analysis_type = Column(String(50))
    
    extracted_entities = Column(JSON)
    resolved_entities = Column(JSON)
    result_status = Column(String(30))
    confidence = Column(Float)
    
    helpfulness = Column(String(10))
    corrections = Column(JSON)
    
    elapsed_ms = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('idx_events_tenant_time', 'tenant_id', 'created_at'),
        Index('idx_events_tenant_app', 'tenant_id', 'app_id', 'created_at'),
    )


class EntityAlias(Base):
    """Alias dictionary with governance states."""
    __tablename__ = "cf_entity_aliases"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(36), nullable=False, index=True)
    alias_text = Column(String(255), nullable=False)
    entity_id = Column(String(36), nullable=False)
    
    status = Column(String(20), nullable=False, default='PROPOSED')
    confidence = Column(Float)
    source = Column(String(50))
    evidence = Column(JSON)
    
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen_at = Column(DateTime)
    
    __table_args__ = (
        Index('idx_aliases_lookup', 'tenant_id', 'alias_text'),
        Index('idx_aliases_unique', 'tenant_id', 'alias_text', 'entity_id', unique=True),
    )


class MemoryVersion(Base):
    """Memory versioning for incremental sync."""
    __tablename__ = "cf_memory_versions"
    
    tenant_id = Column(String(36), primary_key=True)
    current_version = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


_engine = None
_rls_engine = None
_session_factory = None
_rls_session_factory = None


def get_engine(use_rls: bool = False):
    """Create database engine from environment with connection pooling.
    
    SECURITY: For RLS enforcement, use use_rls=True or set DATABASE_URL_RLS.
    The RLS engine connects as app_user (NOBYPASSRLS) for tenant isolation.
    
    Args:
        use_rls: If True, returns the RLS-enforced engine (connects as app_user)
    """
    global _engine, _rls_engine
    
    if use_rls:
        if _rls_engine is None:
            rls_url = os.environ.get("DATABASE_URL_RLS")
            if not rls_url:
                rls_url = _construct_rls_url()
            if rls_url:
                _rls_engine = create_engine(
                    rls_url,
                    echo=False,
                    pool_pre_ping=True,
                    pool_recycle=300,
                    pool_size=5,
                    max_overflow=10,
                    pool_timeout=30,
                )
        if _rls_engine:
            return _rls_engine
    
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


def _construct_rls_url():
    """Construct an RLS-enforced DATABASE_URL using app_user credentials.
    
    Uses PGHOST, PGPORT, PGDATABASE from environment.
    Returns None if construction fails.
    """
    try:
        pghost = os.environ.get("PGHOST")
        pgport = os.environ.get("PGPORT", "5432")
        pgdatabase = os.environ.get("PGDATABASE")
        
        if not pghost or not pgdatabase:
            return None
        
        rls_password = os.environ.get("RLS_USER_PASSWORD", "RLS_Secure_Tenant_Isolation_2026!")
        return f"postgresql://app_user:{rls_password}@{pghost}:{pgport}/{pgdatabase}?sslmode=require"
    except Exception:
        return None


def get_session(use_rls_role: bool = True):
    """Create a new database session with auto-reconnect.
    
    SECURITY: By default, uses RLS-enforced connection.
    Attempts to connect as app_user (NOBYPASSRLS) first.
    Falls back to SET ROLE if direct connection unavailable.
    
    Args:
        use_rls_role: If True (default), uses RLS-enforced connection.
                      Set to False only for admin/migration operations.
    """
    global _session_factory, _rls_session_factory
    
    if use_rls_role:
        rls_engine = get_engine(use_rls=True)
        if rls_engine is not None and rls_engine != get_engine(use_rls=False):
            if _rls_session_factory is None:
                _rls_session_factory = sessionmaker(bind=rls_engine)
            return _rls_session_factory()
        else:
            if _session_factory is None:
                _session_factory = sessionmaker(bind=get_engine())
            session = _session_factory()
            try:
                session.execute(text("SET ROLE app_user"))
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Could not SET ROLE app_user: {e}")
            return session
    else:
        if _session_factory is None:
            _session_factory = sessionmaker(bind=get_engine())
        return _session_factory()


from contextlib import contextmanager

@contextmanager
def tenant_session(tenant_id: str, role: str = 'user'):
    """Context manager for tenant-scoped database operations.
    
    Sets app.current_tenant_id for Row-Level Security policies.
    Automatically resets the setting when the context exits.
    
    SECURITY: RLS policies use fail-closed logic:
    - If tenant_id is not set, NO rows are returned (not all rows)
    - admin role bypasses RLS by using neondb_owner (which has BYPASSRLS)
    
    Usage:
        with tenant_session(tenant_id) as session:
            # All operations here use tenant context
            entities = session.query(Entity).all()
        # Setting is automatically reset when context exits
    
    Args:
        tenant_id: UUID string of the tenant
        role: 'user' (default) or 'admin' (bypasses RLS)
        
    Yields:
        SQLAlchemy session with tenant context set
    """
    if role == 'admin':
        session = get_session(use_rls_role=False)
    else:
        session = get_session(use_rls_role=True)
    try:
        if tenant_id:
            session.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'"))
        yield session
    finally:
        try:
            session.execute(text("RESET app.current_tenant_id"))
        except Exception:
            pass
        session.close()


def get_tenant_session(tenant_id: str, role: str = 'user'):
    """Create a database session with RLS tenant_id set.
    
    WARNING: This session must be closed and the connection reset manually.
    Prefer using tenant_session() context manager instead.
    
    Args:
        tenant_id: UUID string of the tenant
        role: 'user' (default) or 'admin' (bypasses RLS)
        
    Returns:
        SQLAlchemy session with tenant context set
    """
    if role == 'admin':
        session = get_session(use_rls_role=False)
    else:
        session = get_session(use_rls_role=True)
    if tenant_id:
        session.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'"))
    return session


def set_tenant_context(session, tenant_id: str, role: str = 'user'):
    """Set tenant context on an existing session for RLS.
    
    Use this when you already have a session (e.g., from Flask-SQLAlchemy)
    and need to set the tenant context for RLS policies.
    
    SECURITY: RLS policies use fail-closed logic:
    - If tenant_id is not set, NO rows are returned (not all rows)
    - admin role bypasses RLS for maintenance operations
    
    Args:
        session: SQLAlchemy session
        tenant_id: UUID string of the tenant
        role: 'user' (default) or 'admin' (bypasses RLS)
    """
    if tenant_id:
        session.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'"))
    if role == 'admin':
        session.execute(text("SET LOCAL app.role = 'admin'"))


def reset_tenant_context(session):
    """Reset tenant context on a session.
    
    Call this at the end of a request to clear RLS context.
    """
    try:
        session.execute(text("RESET app.current_tenant_id"))
        session.execute(text("RESET app.role"))
    except Exception:
        pass


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
