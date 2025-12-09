"""
Progress tracking for long-running document ingestion.

Follows Anthropic's "long-running agent harness" pattern:
- Track each document through discrete steps
- Commit state after each step (clean checkpoint)
- Resume from last successful step on interruption
- Verify before marking complete

Reference: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
"""

import os
import uuid
import logging
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, String, Text, Integer, DateTime, 
    Enum as SQLEnum, JSON, Index, create_engine
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified

from src.context_foundry.models.schema import Base, get_engine, get_session

logger = logging.getLogger(__name__)


class IngestionStep(str, Enum):
    """Discrete steps in document ingestion pipeline."""
    QUEUED = "queued"
    READING = "reading"
    CLASSIFYING = "classifying"
    CHUNKING = "chunking"
    EXTRACTING = "extracting"
    RELATING = "relating"
    STAGING = "staging"
    VERIFYING = "verifying"
    PROMOTING = "promoting"
    COMPLETED = "completed"
    FAILED = "failed"


STEP_ORDER = [
    IngestionStep.QUEUED,
    IngestionStep.READING,
    IngestionStep.CLASSIFYING,
    IngestionStep.CHUNKING,
    IngestionStep.EXTRACTING,
    IngestionStep.RELATING,
    IngestionStep.STAGING,
    IngestionStep.VERIFYING,
    IngestionStep.PROMOTING,
    IngestionStep.COMPLETED,
]


class PipelineProgress(Base):
    """Database model for pipeline progress tracking."""
    __tablename__ = "pipeline_progress"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(String(36), unique=True, nullable=False, index=True)
    tenant_id = Column(String(36), nullable=False, index=True)
    current_step = Column(
        SQLEnum(
            IngestionStep, 
            name='ingestion_step', 
            create_type=False, 
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
            native_enum=True
        ),
        default=IngestionStep.QUEUED, 
        nullable=False, 
        index=True
    )
    steps_completed = Column(JSON, default=list)
    step_metadata = Column(JSON, default=dict)
    started_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    __table_args__ = (
        Index('idx_progress_tenant_step', 'tenant_id', 'current_step'),
        Index('idx_progress_updated', 'updated_at'),
    )


@dataclass
class DocumentProgress:
    """Progress state for a single document (read-only view)."""
    document_id: str
    tenant_id: str
    current_step: IngestionStep
    steps_completed: List[str]
    step_metadata: Dict[str, Any]
    started_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    error: Optional[str]
    retry_count: int
    
    @classmethod
    def from_db_model(cls, model: PipelineProgress) -> "DocumentProgress":
        """Create from database model."""
        return cls(
            document_id=model.document_id,
            tenant_id=model.tenant_id,
            current_step=model.current_step,
            steps_completed=model.steps_completed or [],
            step_metadata=model.step_metadata or {},
            started_at=model.started_at,
            updated_at=model.updated_at,
            completed_at=model.completed_at,
            error=model.error,
            retry_count=model.retry_count,
        )
    
    def get_next_step(self) -> Optional[IngestionStep]:
        """Get the next step after current, or None if at end."""
        if self.current_step in (IngestionStep.COMPLETED, IngestionStep.FAILED):
            return None
        try:
            idx = STEP_ORDER.index(self.current_step)
            if idx + 1 < len(STEP_ORDER):
                return STEP_ORDER[idx + 1]
        except ValueError:
            pass
        return None


class ProgressTracker:
    """
    Tracks document ingestion progress with checkpoint/resume capability.
    
    Key Principle: After each update() call, the state is committed to the database.
    If the process is interrupted, resume() will return the last completed step.
    
    Usage:
        tracker = ProgressTracker()
        
        # Start new document
        progress = tracker.start(doc_id, tenant_id)
        
        # Update after each step completes
        progress = tracker.update(doc_id, IngestionStep.READING, {"size": 1024})
        progress = tracker.update(doc_id, IngestionStep.CHUNKING, {"chunks": 8})
        
        # If interrupted, resume from last checkpoint
        progress = tracker.resume(doc_id)
        # progress.current_step == IngestionStep.CHUNKING
        
        # Complete or fail
        tracker.complete(doc_id)
        # or
        tracker.fail(doc_id, "Extraction timeout")
    """
    
    def __init__(self, session=None):
        """
        Initialize tracker with database session.
        
        Args:
            session: SQLAlchemy session (optional, creates new if not provided)
        """
        self._session = session
        self._owns_session = session is None
    
    @property
    def session(self):
        """Lazy session creation."""
        if self._session is None:
            self._session = get_session()
        return self._session
    
    def _commit(self):
        """Commit current transaction - this is the CHECKPOINT."""
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            raise
    
    def start(self, document_id: str, tenant_id: str) -> DocumentProgress:
        """
        Register a new document for ingestion.
        
        Creates initial progress record with step=QUEUED.
        If document already exists, returns existing progress.
        
        Args:
            document_id: Unique document identifier
            tenant_id: Tenant identifier
            
        Returns:
            DocumentProgress with current state
        """
        existing = self.session.query(PipelineProgress).filter_by(
            document_id=document_id
        ).first()
        
        if existing:
            logger.info(f"Document {document_id} already has progress record, returning existing")
            return DocumentProgress.from_db_model(existing)
        
        model = PipelineProgress(
            document_id=document_id,
            tenant_id=tenant_id,
            current_step=IngestionStep.QUEUED,
            steps_completed=[],
            step_metadata={},
            started_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        try:
            self.session.add(model)
            self._commit()
            logger.info(f"Started progress tracking for document {document_id}")
            return DocumentProgress.from_db_model(model)
        except IntegrityError:
            self.session.rollback()
            existing = self.session.query(PipelineProgress).filter_by(
                document_id=document_id
            ).first()
            return DocumentProgress.from_db_model(existing)
    
    def update(self, document_id: str, step: IngestionStep, 
               metadata: Optional[Dict[str, Any]] = None) -> DocumentProgress:
        """
        Move document to next step and persist state.
        
        This is the CHECKPOINT - after this returns, we're in a clean state.
        If interrupted after update(), resume() will return this step.
        
        Args:
            document_id: Document identifier
            step: The step we just COMPLETED (not the one we're starting)
            metadata: Step-specific data (e.g., {"chunks": 8, "entities": 51})
            
        Returns:
            Updated DocumentProgress
            
        Raises:
            ValueError: If document not found
        """
        model = self.session.query(PipelineProgress).filter_by(
            document_id=document_id
        ).first()
        
        if not model:
            raise ValueError(f"No progress record for document {document_id}")
        
        steps_completed = model.steps_completed or []
        if step.value not in steps_completed:
            steps_completed.append(step.value)
        
        step_metadata = model.step_metadata or {}
        if metadata:
            step_metadata[step.value] = metadata
        
        model.current_step = step
        model.steps_completed = list(steps_completed)
        model.step_metadata = dict(step_metadata)
        model.updated_at = datetime.utcnow()
        
        flag_modified(model, 'steps_completed')
        flag_modified(model, 'step_metadata')
        
        self._commit()
        self.session.refresh(model)
        logger.info(f"Document {document_id} updated to step {step.value}")
        
        return DocumentProgress.from_db_model(model)
    
    def complete(self, document_id: str) -> DocumentProgress:
        """
        Mark document as COMPLETED.
        
        Only call after verification passes.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Final DocumentProgress
        """
        model = self.session.query(PipelineProgress).filter_by(
            document_id=document_id
        ).first()
        
        if not model:
            raise ValueError(f"No progress record for document {document_id}")
        
        steps_completed = list(model.steps_completed or [])
        if IngestionStep.COMPLETED.value not in steps_completed:
            steps_completed.append(IngestionStep.COMPLETED.value)
        
        model.current_step = IngestionStep.COMPLETED
        model.steps_completed = list(steps_completed)
        model.completed_at = datetime.utcnow()
        model.updated_at = datetime.utcnow()
        model.error = None
        
        flag_modified(model, 'steps_completed')
        
        self._commit()
        self.session.refresh(model)
        logger.info(f"Document {document_id} marked as COMPLETED")
        
        return DocumentProgress.from_db_model(model)
    
    def fail(self, document_id: str, error: str) -> DocumentProgress:
        """
        Mark document as FAILED with error message.
        
        Increments retry_count for potential retry logic.
        
        Args:
            document_id: Document identifier
            error: Error message describing the failure
            
        Returns:
            Updated DocumentProgress
        """
        model = self.session.query(PipelineProgress).filter_by(
            document_id=document_id
        ).first()
        
        if not model:
            raise ValueError(f"No progress record for document {document_id}")
        
        model.current_step = IngestionStep.FAILED
        model.error = error
        model.retry_count = (model.retry_count or 0) + 1
        model.updated_at = datetime.utcnow()
        
        self._commit()
        logger.warning(f"Document {document_id} marked as FAILED: {error}")
        
        return DocumentProgress.from_db_model(model)
    
    def resume(self, document_id: str) -> Optional[DocumentProgress]:
        """
        Load progress for interrupted document.
        
        Returns None if no progress record exists.
        
        Args:
            document_id: Document identifier
            
        Returns:
            DocumentProgress if exists, None otherwise
        """
        model = self.session.query(PipelineProgress).filter_by(
            document_id=document_id
        ).first()
        
        if not model:
            return None
        
        logger.info(f"Resumed document {document_id} at step {model.current_step.value}")
        return DocumentProgress.from_db_model(model)
    
    def reset_for_retry(self, document_id: str, from_step: IngestionStep = IngestionStep.QUEUED) -> DocumentProgress:
        """
        Reset a failed document to retry from a specific step.
        
        Clears stale steps_completed and step_metadata from the failed run,
        keeping only steps that precede from_step.
        
        Args:
            document_id: Document identifier
            from_step: Step to restart from (default: QUEUED)
            
        Returns:
            Reset DocumentProgress
        """
        model = self.session.query(PipelineProgress).filter_by(
            document_id=document_id
        ).first()
        
        if not model:
            raise ValueError(f"No progress record for document {document_id}")
        
        try:
            from_step_idx = STEP_ORDER.index(from_step)
        except ValueError:
            from_step_idx = 0
        
        steps_to_keep = [s.value for s in STEP_ORDER[:from_step_idx]]
        
        old_steps = model.steps_completed or []
        new_steps = [s for s in old_steps if s in steps_to_keep]
        
        old_metadata = model.step_metadata or {}
        new_metadata = {k: v for k, v in old_metadata.items() if k in steps_to_keep}
        
        model.current_step = from_step
        model.steps_completed = list(new_steps)
        model.step_metadata = dict(new_metadata)
        model.error = None
        model.updated_at = datetime.utcnow()
        
        flag_modified(model, 'steps_completed')
        flag_modified(model, 'step_metadata')
        
        self._commit()
        self.session.refresh(model)
        logger.info(f"Document {document_id} reset to step {from_step.value} for retry (cleared {len(old_steps) - len(new_steps)} stale steps)")
        
        return DocumentProgress.from_db_model(model)
    
    def get_pending(self, tenant_id: Optional[str] = None) -> List[DocumentProgress]:
        """
        Get all documents that aren't COMPLETED or FAILED.
        
        Args:
            tenant_id: Optional filter by tenant
            
        Returns:
            List of in-progress documents
        """
        query = self.session.query(PipelineProgress).filter(
            PipelineProgress.current_step.notin_([
                IngestionStep.COMPLETED,
                IngestionStep.FAILED
            ])
        )
        
        if tenant_id:
            query = query.filter_by(tenant_id=tenant_id)
        
        return [DocumentProgress.from_db_model(m) for m in query.all()]
    
    def get_stalled(self, threshold_mins: int = 30) -> List[DocumentProgress]:
        """
        Get documents stuck on same step for too long.
        
        Args:
            threshold_mins: Minutes before considering stalled
            
        Returns:
            List of stalled documents
        """
        threshold = datetime.utcnow() - timedelta(minutes=threshold_mins)
        
        query = self.session.query(PipelineProgress).filter(
            PipelineProgress.current_step.notin_([
                IngestionStep.COMPLETED,
                IngestionStep.FAILED
            ]),
            PipelineProgress.updated_at < threshold
        )
        
        return [DocumentProgress.from_db_model(m) for m in query.all()]
    
    def get_failed(self, tenant_id: Optional[str] = None, max_retries: int = 3) -> List[DocumentProgress]:
        """
        Get failed documents that haven't exceeded retry limit.
        
        Args:
            tenant_id: Optional filter by tenant
            max_retries: Maximum retries before excluding
            
        Returns:
            List of failed documents eligible for retry
        """
        query = self.session.query(PipelineProgress).filter(
            PipelineProgress.current_step == IngestionStep.FAILED,
            PipelineProgress.retry_count < max_retries
        )
        
        if tenant_id:
            query = query.filter_by(tenant_id=tenant_id)
        
        return [DocumentProgress.from_db_model(m) for m in query.all()]
    
    def get_summary(self, tenant_id: Optional[str] = None) -> Dict[str, int]:
        """
        Return counts by step for monitoring.
        
        Args:
            tenant_id: Optional filter by tenant
            
        Returns:
            Dict mapping step names to counts
            e.g., {"queued": 5, "extracting": 2, "completed": 100, "failed": 3}
        """
        from sqlalchemy import func
        
        query = self.session.query(
            PipelineProgress.current_step,
            func.count(PipelineProgress.id)
        ).group_by(PipelineProgress.current_step)
        
        if tenant_id:
            query = query.filter(PipelineProgress.tenant_id == tenant_id)
        
        result = {}
        for step, count in query.all():
            result[step.value] = count
        
        return result
    
    def delete_progress(self, document_id: str) -> bool:
        """
        Delete progress record for a document (for testing/cleanup).
        
        Args:
            document_id: Document identifier
            
        Returns:
            True if deleted, False if not found
        """
        model = self.session.query(PipelineProgress).filter_by(
            document_id=document_id
        ).first()
        
        if not model:
            return False
        
        self.session.delete(model)
        self._commit()
        return True
    
    def close(self):
        """Close session if we own it."""
        if self._owns_session and self._session is not None:
            self._session.close()
            self._session = None


def ensure_table_exists():
    """Create the pipeline_progress table if it doesn't exist."""
    engine = get_engine()
    PipelineProgress.__table__.create(engine, checkfirst=True)
    logger.info("Ensured pipeline_progress table exists")
