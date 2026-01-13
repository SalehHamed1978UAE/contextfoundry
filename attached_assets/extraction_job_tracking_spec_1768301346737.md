# EXTRACTION JOB TRACKING — COMPLETE IMPLEMENTATION SPEC

## Overview

Build reliable extraction with job tracking, verification, and auto-recovery.

**Problem:** Currently there's no way to know if extraction completed, succeeded, or failed. Users are blind to pipeline status.

**Solution:** Track every extraction job with status, progress, retries, and independent verification.

---

## PHASE 1: DATABASE MIGRATION

Create file: `migrations/017_extraction_job_tracking.sql`

```sql
-- =============================================================================
-- Migration 017: Extraction Job Tracking
-- =============================================================================
-- Purpose: Track extraction jobs with status, progress, retries, and verification
-- Date: 2026-01-13
-- =============================================================================

CREATE TABLE extraction_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES vaults(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    
    -- Status tracking
    status VARCHAR(20) DEFAULT 'PENDING' 
        CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETE', 'PARTIAL', 'FAILED', 'TIMEOUT')),
    
    -- Progress tracking (for UI progress bar)
    chunks_total INTEGER DEFAULT 0,
    chunks_processed INTEGER DEFAULT 0,
    
    -- Results
    entities_extracted INTEGER DEFAULT 0,
    relationships_extracted INTEGER DEFAULT 0,
    
    -- Timing
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    timeout_at TIMESTAMP,
    
    -- Retry handling
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error_message TEXT,
    
    -- Cache optimization (skip re-extraction if unchanged)
    content_hash VARCHAR(64),
    
    -- Metadata
    extraction_config JSONB DEFAULT '{}'
);

-- Prevent duplicate active jobs for same document
CREATE UNIQUE INDEX idx_extraction_jobs_active_document 
ON extraction_jobs(document_id) 
WHERE status IN ('PENDING', 'RUNNING');

-- Query by tenant and status
CREATE INDEX idx_extraction_jobs_tenant_status 
ON extraction_jobs(tenant_id, status, created_at DESC);

-- Query job history for a document
CREATE INDEX idx_extraction_jobs_document_history 
ON extraction_jobs(document_id, created_at DESC);

-- Find timed-out jobs
CREATE INDEX idx_extraction_jobs_timeout 
ON extraction_jobs(timeout_at) 
WHERE status = 'RUNNING';

-- =============================================================================
-- Helper view for document status
-- =============================================================================
CREATE OR REPLACE VIEW document_extraction_status AS
SELECT 
    d.id as document_id,
    d.name as document_name,
    d.tenant_id,
    j.id as job_id,
    j.status,
    j.chunks_total,
    j.chunks_processed,
    CASE 
        WHEN j.chunks_total > 0 
        THEN (j.chunks_processed * 100 / j.chunks_total) 
        ELSE 0 
    END as progress_pct,
    j.entities_extracted,
    j.relationships_extracted,
    j.started_at,
    j.completed_at,
    j.error_message,
    j.retry_count
FROM documents d
LEFT JOIN LATERAL (
    SELECT * FROM extraction_jobs ej
    WHERE ej.document_id = d.id
    ORDER BY ej.created_at DESC
    LIMIT 1
) j ON true;

-- =============================================================================
-- End Migration 017
-- =============================================================================
```

**Verify after running:**
```sql
SELECT * FROM extraction_jobs LIMIT 1;
SELECT * FROM document_extraction_status LIMIT 5;
```

---

## PHASE 2: JOB TRACKER SERVICE

Create file: `src/context_foundry/extraction/job_tracker.py`

```python
"""
Extraction Job Tracker

Tracks extraction jobs with status, progress, retries, and verification.
"""

import hashlib
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from sqlalchemy import text

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class ExtractionJobTracker:
    """Track and manage extraction jobs"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    # =========================================================================
    # Job Lifecycle
    # =========================================================================
    
    def create_job(
        self, 
        tenant_id: UUID, 
        document_id: UUID,
        content_hash: Optional[str] = None,
        chunks_total: int = 0
    ) -> UUID:
        """Create a new extraction job"""
        
        job_id = uuid4()
        
        self.db.execute(text("""
            INSERT INTO extraction_jobs 
            (id, tenant_id, document_id, status, chunks_total, content_hash)
            VALUES (:job_id, :tenant_id, :document_id, 'PENDING', :chunks_total, :content_hash)
        """), {
            "job_id": job_id,
            "tenant_id": tenant_id,
            "document_id": document_id,
            "chunks_total": chunks_total,
            "content_hash": content_hash
        })
        self.db.commit()
        
        logger.info(f"Created extraction job {job_id} for document {document_id}")
        return job_id
    
    def start_job(self, job_id: UUID, chunks_total: int = None) -> None:
        """Mark job as running with dynamic timeout"""
        
        started_at = datetime.utcnow()
        
        # Dynamic timeout: 30s per chunk + 60s buffer, min 2 min, max 30 min
        if chunks_total:
            timeout_seconds = max(120, min(1800, chunks_total * 30 + 60))
        else:
            timeout_seconds = 300  # Default 5 minutes
        
        timeout_at = started_at + timedelta(seconds=timeout_seconds)
        
        self.db.execute(text("""
            UPDATE extraction_jobs 
            SET status = 'RUNNING', 
                started_at = :started_at, 
                timeout_at = :timeout_at,
                chunks_total = COALESCE(:chunks_total, chunks_total)
            WHERE id = :job_id
        """), {
            "job_id": job_id,
            "started_at": started_at,
            "timeout_at": timeout_at,
            "chunks_total": chunks_total
        })
        self.db.commit()
        
        logger.info(f"Started job {job_id}, timeout at {timeout_at}")
    
    def update_progress(
        self, 
        job_id: UUID, 
        chunks_processed: int,
        entities_extracted: int = None,
        relationships_extracted: int = None
    ) -> None:
        """Update job progress (call after each chunk)"""
        
        self.db.execute(text("""
            UPDATE extraction_jobs 
            SET chunks_processed = :chunks_processed,
                entities_extracted = COALESCE(:entities, entities_extracted),
                relationships_extracted = COALESCE(:relationships, relationships_extracted)
            WHERE id = :job_id
        """), {
            "job_id": job_id,
            "chunks_processed": chunks_processed,
            "entities": entities_extracted,
            "relationships": relationships_extracted
        })
        self.db.commit()
    
    def complete_job(
        self, 
        job_id: UUID, 
        entities_extracted: int,
        relationships_extracted: int,
        partial: bool = False
    ) -> None:
        """Mark job as complete or partial"""
        
        status = JobStatus.PARTIAL if partial else JobStatus.COMPLETE
        
        self.db.execute(text("""
            UPDATE extraction_jobs 
            SET status = :status,
                completed_at = :completed_at,
                entities_extracted = :entities,
                relationships_extracted = :relationships
            WHERE id = :job_id
        """), {
            "job_id": job_id,
            "status": status.value,
            "completed_at": datetime.utcnow(),
            "entities": entities_extracted,
            "relationships": relationships_extracted
        })
        self.db.commit()
        
        logger.info(f"Completed job {job_id}: {status.value}, {entities_extracted} entities, {relationships_extracted} relationships")
    
    def fail_job(self, job_id: UUID, error_message: str) -> None:
        """Mark job as failed"""
        
        self.db.execute(text("""
            UPDATE extraction_jobs 
            SET status = 'FAILED',
                completed_at = :completed_at,
                error_message = :error_message
            WHERE id = :job_id
        """), {
            "job_id": job_id,
            "completed_at": datetime.utcnow(),
            "error_message": error_message[:1000]  # Truncate long errors
        })
        self.db.commit()
        
        logger.error(f"Failed job {job_id}: {error_message[:200]}")
    
    # =========================================================================
    # Cache Check
    # =========================================================================
    
    def should_skip_extraction(self, document_id: UUID, content_hash: str) -> bool:
        """Check if document unchanged since last successful extraction"""
        
        result = self.db.execute(text("""
            SELECT content_hash FROM extraction_jobs
            WHERE document_id = :document_id 
              AND status = 'COMPLETE'
            ORDER BY completed_at DESC 
            LIMIT 1
        """), {"document_id": document_id}).fetchone()
        
        if result and result.content_hash == content_hash:
            logger.info(f"Skipping extraction for {document_id}: content unchanged")
            return True
        
        return False
    
    @staticmethod
    def compute_content_hash(content: str) -> str:
        """SHA-256 hash of document content"""
        return hashlib.sha256(content.encode()).hexdigest()
    
    # =========================================================================
    # Queries
    # =========================================================================
    
    def get_job(self, job_id: UUID) -> Optional[Dict[str, Any]]:
        """Get job by ID"""
        result = self.db.execute(text("""
            SELECT * FROM extraction_jobs WHERE id = :job_id
        """), {"job_id": job_id}).fetchone()
        
        return dict(result._mapping) if result else None
    
    def get_document_status(self, document_id: UUID) -> Optional[Dict[str, Any]]:
        """Get latest extraction status for a document"""
        result = self.db.execute(text("""
            SELECT * FROM document_extraction_status 
            WHERE document_id = :document_id
        """), {"document_id": document_id}).fetchone()
        
        return dict(result._mapping) if result else None
    
    def get_vault_status(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get extraction status summary for a vault"""
        result = self.db.execute(text("""
            SELECT 
                COUNT(*) as total_documents,
                COUNT(*) FILTER (WHERE status = 'COMPLETE') as complete,
                COUNT(*) FILTER (WHERE status = 'PARTIAL') as partial,
                COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
                COUNT(*) FILTER (WHERE status = 'TIMEOUT') as timeout,
                COUNT(*) FILTER (WHERE status = 'RUNNING') as running,
                COUNT(*) FILTER (WHERE status = 'PENDING') as pending,
                COUNT(*) FILTER (WHERE status IS NULL) as not_started,
                COALESCE(SUM(entities_extracted), 0) as total_entities,
                COALESCE(SUM(relationships_extracted), 0) as total_relationships
            FROM document_extraction_status
            WHERE tenant_id = :tenant_id
        """), {"tenant_id": tenant_id}).fetchone()
        
        row = dict(result._mapping)
        
        # Determine health status
        if row['failed'] > 0 or row['timeout'] > 0:
            health = 'degraded'
        elif row['not_started'] > 0 or row['pending'] > 0:
            health = 'pending'
        elif row['complete'] == row['total_documents']:
            health = 'healthy'
        else:
            health = 'unknown'
        
        return {
            "status": health,
            "documents": {
                "total": row['total_documents'],
                "complete": row['complete'],
                "partial": row['partial'],
                "failed": row['failed'],
                "timeout": row['timeout'],
                "running": row['running'],
                "pending": row['pending'],
                "not_started": row['not_started']
            },
            "extraction": {
                "entities": row['total_entities'],
                "relationships": row['total_relationships']
            }
        }
    
    # =========================================================================
    # Verification
    # =========================================================================
    
    def verify_job(self, job_id: UUID) -> dict:
        """
        Independently verify extraction results match database state.
        
        Catches discrepancies between what the pipeline reported 
        and what actually landed in the database.
        """
        job = self.get_job(job_id)
        
        if not job:
            return {"error": "Job not found"}
        
        document_id = job['document_id']
        
        # Count actual chunks in database
        chunks_result = self.db.execute(text("""
            SELECT COUNT(*) as count FROM chunks 
            WHERE document_id = :doc_id
        """), {"doc_id": document_id}).fetchone()
        actual_chunks = chunks_result.count if chunks_result else 0
        
        # Count actual entities linked to this document
        entities_result = self.db.execute(text("""
            SELECT COUNT(DISTINCT e.id) as count 
            FROM entities e
            JOIN relationships r ON e.id = r.source_entity_id OR e.id = r.target_entity_id
            JOIN chunks c ON r.source_chunk_id = c.id
            WHERE c.document_id = :doc_id
        """), {"doc_id": document_id}).fetchone()
        actual_entities = entities_result.count if entities_result else 0
        
        # Count actual relationships linked to this document
        relationships_result = self.db.execute(text("""
            SELECT COUNT(*) as count FROM relationships r
            JOIN chunks c ON r.source_chunk_id = c.id
            WHERE c.document_id = :doc_id
        """), {"doc_id": document_id}).fetchone()
        actual_relationships = relationships_result.count if relationships_result else 0
        
        # Compare reported vs actual
        chunks_match = job['chunks_total'] == actual_chunks or job['chunks_processed'] == actual_chunks
        entities_match = job['entities_extracted'] == actual_entities
        relationships_match = job['relationships_extracted'] == actual_relationships
        
        return {
            "job_id": str(job_id),
            "document_id": str(document_id),
            "status": job['status'],
            "verification": {
                "chunks": {
                    "reported": job['chunks_total'],
                    "actual": actual_chunks,
                    "match": chunks_match
                },
                "entities": {
                    "reported": job['entities_extracted'],
                    "actual": actual_entities,
                    "match": entities_match
                },
                "relationships": {
                    "reported": job['relationships_extracted'],
                    "actual": actual_relationships,
                    "match": relationships_match
                }
            },
            "verified": chunks_match and entities_match and relationships_match,
            "discrepancies": [d for d in [
                f"chunks: {job['chunks_total']} reported vs {actual_chunks} actual" if not chunks_match else None,
                f"entities: {job['entities_extracted']} reported vs {actual_entities} actual" if not entities_match else None,
                f"relationships: {job['relationships_extracted']} reported vs {actual_relationships} actual" if not relationships_match else None
            ] if d]
        }
    
    def verify_document(self, document_id: UUID) -> dict:
        """Verify latest extraction for a document"""
        
        # Get latest job for this document
        result = self.db.execute(text("""
            SELECT id FROM extraction_jobs
            WHERE document_id = :doc_id
            ORDER BY created_at DESC
            LIMIT 1
        """), {"doc_id": document_id}).fetchone()
        
        if not result:
            return {
                "document_id": str(document_id),
                "verified": False,
                "error": "No extraction job found"
            }
        
        return self.verify_job(result.id)
    
    def verify_vault(self, tenant_id: UUID) -> dict:
        """Verify all extractions in a vault"""
        
        # Get all documents with their latest job
        results = self.db.execute(text("""
            SELECT DISTINCT document_id FROM extraction_jobs
            WHERE tenant_id = :tenant_id
        """), {"tenant_id": tenant_id}).fetchall()
        
        verifications = []
        all_verified = True
        discrepancy_count = 0
        
        for row in results:
            v = self.verify_document(row.document_id)
            verifications.append(v)
            
            if not v.get('verified', False):
                all_verified = False
                discrepancy_count += 1
        
        return {
            "tenant_id": str(tenant_id),
            "documents_checked": len(verifications),
            "all_verified": all_verified,
            "discrepancies": discrepancy_count,
            "details": verifications
        }


def get_job_tracker(db_session) -> ExtractionJobTracker:
    """
    Get tracker with provided session.
    In web contexts, pass the request-scoped session.
    """
    return ExtractionJobTracker(db_session)
```

---

## PHASE 3: PIPELINE INTEGRATION

Update `src/context_foundry/extraction/ontology_centric_pipeline.py`:

Add import at top:
```python
from context_foundry.extraction.job_tracker import get_job_tracker, JobStatus
```

Update the extract method:
```python
def extract(
    self, 
    document_id: UUID, 
    tenant_id: UUID, 
    content: str,
    force: bool = False,  # Add this parameter
    db_session = None,
    ...
):
    tracker = get_job_tracker(db_session or self.db)
    
    # Compute content hash for cache check
    content_hash = tracker.compute_content_hash(content)
    
    # Check if we can skip (content unchanged)
    if not force and tracker.should_skip_extraction(document_id, content_hash):
        return {"skipped": True, "reason": "content_unchanged"}
    
    # Create job
    job_id = tracker.create_job(
        tenant_id=tenant_id,
        document_id=document_id,
        content_hash=content_hash
    )
    
    try:
        # Chunk the document
        chunks = self.chunker.chunk(content)
        
        # Start job with dynamic timeout
        tracker.start_job(job_id, chunks_total=len(chunks))
        
        all_entities = []
        all_relationships = []
        
        # Process each chunk
        for i, chunk in enumerate(chunks):
            entities, relationships = self._extract_chunk(chunk)
            all_entities.extend(entities)
            all_relationships.extend(relationships)
            
            # Update progress after each chunk
            tracker.update_progress(
                job_id=job_id,
                chunks_processed=i + 1,
                entities_extracted=len(all_entities),
                relationships_extracted=len(all_relationships)
            )
        
        # ... rest of extraction (post-processor, staging, etc.) ...
        
        # Complete job
        tracker.complete_job(
            job_id=job_id,
            entities_extracted=len(all_entities),
            relationships_extracted=len(all_relationships)
        )
        
        return {
            "job_id": str(job_id),
            "status": "complete",
            "entities": len(all_entities),
            "relationships": len(all_relationships)
        }
        
    except Exception as e:
        tracker.fail_job(job_id, str(e))
        raise
```

---

## PHASE 4: CIRCUIT BREAKER

Create file: `src/context_foundry/extraction/circuit_breaker.py`

```python
"""
Circuit Breaker for Extraction Retries

Prevents runaway retries during systemic failures (e.g., LLM API down).
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"      # Normal operation, retries allowed
    OPEN = "OPEN"          # Too many failures, retries blocked
    HALF_OPEN = "HALF_OPEN"  # Testing if system recovered


class ExtractionCircuitBreaker:
    """
    Circuit breaker to prevent runaway retries.
    
    Opens after `failure_threshold` failures in `window_minutes`.
    Stays open for `cooldown_minutes` before allowing test retry.
    """
    
    def __init__(
        self, 
        db_session,
        failure_threshold: int = 10,
        window_minutes: int = 5,
        cooldown_minutes: int = 15
    ):
        self.db = db_session
        self.failure_threshold = failure_threshold
        self.window_minutes = window_minutes
        self.cooldown_minutes = cooldown_minutes
        self.state = CircuitState.CLOSED
        self.opened_at: Optional[datetime] = None
    
    def record_failure(self) -> None:
        """Record a failure and potentially open the circuit"""
        
        if self.state == CircuitState.OPEN:
            return  # Already open
        
        # Count recent failures (using parameterized query)
        result = self.db.execute(text("""
            SELECT COUNT(*) as count FROM extraction_jobs
            WHERE status IN ('FAILED', 'TIMEOUT')
              AND completed_at > NOW() - MAKE_INTERVAL(mins => :window)
        """), {"window": self.window_minutes}).fetchone()
        
        recent_failures = result.count if result else 0
        
        if recent_failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = datetime.utcnow()
            logger.error(
                f"Circuit breaker OPEN: {recent_failures} failures in {self.window_minutes} min. "
                f"Retries blocked for {self.cooldown_minutes} min."
            )
    
    def record_success(self) -> None:
        """Record a success, potentially closing the circuit"""
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.opened_at = None
            logger.info("Circuit breaker CLOSED: system recovered")
    
    def can_retry(self) -> bool:
        """Check if retries are allowed"""
        
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if cooldown has passed
            if self.opened_at and datetime.utcnow() > self.opened_at + timedelta(minutes=self.cooldown_minutes):
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker HALF_OPEN: allowing test retry")
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            return True  # Allow retry to test recovery
        
        return False
    
    def get_status(self) -> dict:
        """Get current circuit breaker status"""
        return {
            "state": self.state.value,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "cooldown_remaining": self._cooldown_remaining()
        }
    
    def _cooldown_remaining(self) -> Optional[int]:
        """Seconds remaining in cooldown, or None if not in cooldown"""
        if self.state != CircuitState.OPEN or not self.opened_at:
            return None
        
        cooldown_end = self.opened_at + timedelta(minutes=self.cooldown_minutes)
        remaining = (cooldown_end - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))


def get_circuit_breaker(db_session) -> ExtractionCircuitBreaker:
    """Get circuit breaker with provided session"""
    return ExtractionCircuitBreaker(db_session)
```

---

## PHASE 5: BACKGROUND MONITOR

Create file: `src/context_foundry/extraction/extraction_monitor.py`

```python
"""
Extraction Monitor

Background process to detect stuck/failed extractions and trigger retries.
"""

import logging
import time
from datetime import datetime

from sqlalchemy import text
from context_foundry.extraction.circuit_breaker import get_circuit_breaker

logger = logging.getLogger(__name__)


class ExtractionMonitor:
    """Monitor extraction jobs and handle failures"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.circuit_breaker = get_circuit_breaker(db_session)
    
    def check_timeouts(self) -> int:
        """Mark timed-out jobs as TIMEOUT"""
        
        result = self.db.execute(text("""
            UPDATE extraction_jobs 
            SET status = 'TIMEOUT', 
                completed_at = NOW(),
                error_message = 'Extraction timed out'
            WHERE status = 'RUNNING' 
              AND timeout_at < NOW()
            RETURNING id, document_id
        """))
        
        timed_out = result.fetchall()
        self.db.commit()
        
        for job in timed_out:
            logger.warning(f"Extraction timeout: job={job.id}, document={job.document_id}")
            self.circuit_breaker.record_failure()
        
        return len(timed_out)
    
    def get_retriable_jobs(self, limit: int = 10) -> list:
        """Get failed/timeout jobs that can be retried"""
        
        result = self.db.execute(text("""
            SELECT id, document_id, tenant_id, retry_count, content_hash
            FROM extraction_jobs
            WHERE status IN ('FAILED', 'TIMEOUT')
              AND retry_count < max_retries
              AND created_at > NOW() - INTERVAL '24 hours'
            ORDER BY created_at ASC
            LIMIT :limit
        """), {"limit": limit})
        
        return result.fetchall()
    
    def queue_retry(self, job) -> bool:
        """Queue a job for retry"""
        
        if not self.circuit_breaker.can_retry():
            logger.warning(f"Circuit breaker open, skipping retry for job {job.id}")
            return False
        
        # Create new job with incremented retry count
        self.db.execute(text("""
            INSERT INTO extraction_jobs 
            (tenant_id, document_id, status, retry_count, content_hash)
            VALUES (:tenant_id, :document_id, 'PENDING', :retry_count, :content_hash)
        """), {
            "tenant_id": job.tenant_id,
            "document_id": job.document_id,
            "retry_count": job.retry_count + 1,
            "content_hash": job.content_hash
        })
        self.db.commit()
        
        logger.info(f"Queued retry for document {job.document_id} (attempt {job.retry_count + 1})")
        return True
    
    def run_once(self) -> dict:
        """Run one monitoring cycle"""
        
        timeouts = self.check_timeouts()
        
        retriable = self.get_retriable_jobs()
        retried = 0
        
        for job in retriable:
            if self.queue_retry(job):
                retried += 1
        
        return {
            "timeouts_detected": timeouts,
            "retries_queued": retried,
            "circuit_breaker": self.circuit_breaker.get_status()
        }
    
    def run(self, interval_seconds: int = 60):
        """Run monitoring loop"""
        
        logger.info(f"Starting extraction monitor (interval={interval_seconds}s)")
        
        while True:
            try:
                result = self.run_once()
                
                if result['timeouts_detected'] > 0 or result['retries_queued'] > 0:
                    logger.info(f"Monitor cycle: {result}")
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            
            time.sleep(interval_seconds)


def start_monitor(db_session):
    """Start the extraction monitor"""
    monitor = ExtractionMonitor(db_session)
    monitor.run()
```

---

## PHASE 6: API ENDPOINTS

Add to your API router:

```python
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from context_foundry.extraction.job_tracker import get_job_tracker
from context_foundry.extraction.circuit_breaker import get_circuit_breaker
from context_foundry.database import get_db

router = APIRouter(prefix="/api")


@router.get("/vault/{vault_id}/documents")
def get_vault_documents(vault_id: str, db: Session = Depends(get_db)):
    """Get all documents with extraction status"""
    tracker = get_job_tracker(db)
    
    from sqlalchemy import text
    results = db.execute(text("""
        SELECT * FROM document_extraction_status
        WHERE tenant_id = :vault_id
        ORDER BY document_name
    """), {"vault_id": vault_id}).fetchall()
    
    return [dict(r._mapping) for r in results]


@router.get("/vault/{vault_id}/health")
def get_vault_health(vault_id: str, db: Session = Depends(get_db)):
    """Get vault extraction health summary"""
    tracker = get_job_tracker(db)
    breaker = get_circuit_breaker(db)
    
    status = tracker.get_vault_status(vault_id)
    status["circuit_breaker"] = breaker.get_status()
    
    return status


@router.get("/vault/{vault_id}/verify")
def verify_vault_extractions(vault_id: str, db: Session = Depends(get_db)):
    """Verify all extractions in vault match database state"""
    tracker = get_job_tracker(db)
    return tracker.verify_vault(vault_id)


@router.get("/document/{document_id}/verify")
def verify_document_extraction(document_id: str, db: Session = Depends(get_db)):
    """Verify extraction for a specific document"""
    tracker = get_job_tracker(db)
    return tracker.verify_document(document_id)


@router.post("/document/{document_id}/refresh")
def refresh_document(document_id: str, force: bool = False, db: Session = Depends(get_db)):
    """Trigger re-extraction of a document"""
    # Implementation depends on your extraction queue
    # This should queue a new extraction job
    tracker = get_job_tracker(db)
    
    # Get document info
    doc = db.execute(text("""
        SELECT id, tenant_id FROM documents WHERE id = :doc_id
    """), {"doc_id": document_id}).fetchone()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Create new extraction job
    job_id = tracker.create_job(
        tenant_id=doc.tenant_id,
        document_id=doc.id
    )
    
    return {"job_id": str(job_id), "status": "queued"}


@router.post("/vault/{vault_id}/refresh-failed")
def refresh_failed_documents(vault_id: str, db: Session = Depends(get_db)):
    """Retry all failed extractions in a vault"""
    tracker = get_job_tracker(db)
    
    from sqlalchemy import text
    failed = db.execute(text("""
        SELECT document_id FROM document_extraction_status
        WHERE tenant_id = :vault_id
          AND status IN ('FAILED', 'TIMEOUT')
    """), {"vault_id": vault_id}).fetchall()
    
    queued = []
    for doc in failed:
        job_id = tracker.create_job(
            tenant_id=vault_id,
            document_id=doc.document_id
        )
        queued.append({"document_id": str(doc.document_id), "job_id": str(job_id)})
    
    return {"queued": len(queued), "jobs": queued}
```

---

## VERIFICATION CHECKLIST

### Phase 1: Migration
```bash
psql -f migrations/017_extraction_job_tracking.sql
```
```sql
SELECT * FROM extraction_jobs LIMIT 1;
SELECT * FROM document_extraction_status LIMIT 5;
```

### Phase 2: Job Tracker
```python
from context_foundry.extraction.job_tracker import get_job_tracker
tracker = get_job_tracker(db_session)
# Test create_job, start_job, complete_job
```

### Phase 3: Pipeline Integration
```bash
python scripts/e2e_lifecycle_test.py --vault TechVentures
```
```sql
SELECT document_name, status, progress_pct, entities_extracted 
FROM document_extraction_status 
WHERE tenant_id = (SELECT id FROM vaults WHERE name = 'TechVentures');
```

### Phase 4: Circuit Breaker
```python
from context_foundry.extraction.circuit_breaker import get_circuit_breaker
breaker = get_circuit_breaker(db_session)
breaker.record_failure()
print(breaker.get_status())
```

### Phase 5: Monitor
```python
from context_foundry.extraction.extraction_monitor import ExtractionMonitor
monitor = ExtractionMonitor(db_session)
print(monitor.run_once())
```

### Phase 6: API Endpoints
```bash
curl http://localhost:8000/api/vault/{vault_id}/health
curl http://localhost:8000/api/vault/{vault_id}/verify
```

---

## REPORT BACK AFTER EACH PHASE

1. Migration applied?
2. Job tracker working?
3. Pipeline creating jobs?
4. Circuit breaker tested?
5. Monitor detecting timeouts?
6. API endpoints responding?

Target: Full job tracking with verification and auto-recovery.
