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


VALID_TRANSITIONS = {
    'PENDING': {'RUNNING', 'FAILED'},
    'RUNNING': {'COMPLETE', 'PARTIAL', 'FAILED', 'TIMEOUT'},
    'FAILED': {'PENDING'},
    'TIMEOUT': {'PENDING'},
}


class ExtractionJobTracker:
    """Track and manage extraction jobs"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def _guard_transition(self, job_id, current_status, new_status):
        if current_status not in VALID_TRANSITIONS or new_status not in VALID_TRANSITIONS[current_status]:
            msg = f"ILLEGAL TRANSITION: {current_status} → {new_status} for job {job_id}"
            logger.error(msg)
            raise ValueError(msg)
    
    def create_job(
        self, 
        tenant_id: UUID, 
        document_id: UUID,
        content_hash: Optional[str] = None,
        chunks_total: int = 0
    ) -> UUID:
        """Create a new extraction job.
        
        If an active job (PENDING/RUNNING) already exists for this document,
        it will be marked as FAILED first to allow creating a new job.
        """
        
        # Check for and clean up any existing active jobs for this document
        # This prevents UniqueViolation from idx_extraction_jobs_active_document
        existing = self.db.execute(text("""
            SELECT id, status FROM extraction_jobs 
            WHERE document_id = :doc_id AND status IN ('PENDING', 'RUNNING')
        """), {"doc_id": document_id}).fetchall()
        
        if existing:
            for row in existing:
                logger.info(f"[JobTracker] Cleaning up stale {row[1]} job {row[0]} for document {document_id}")
            
            self.db.execute(text("""
                UPDATE extraction_jobs 
                SET status = 'FAILED', error_message = 'Superseded by new extraction job'
                WHERE document_id = :doc_id AND status IN ('PENDING', 'RUNNING')
            """), {"doc_id": document_id})
            self.db.commit()
        
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
        
        logger.info(f"[JobTracker] Created extraction job {job_id} for document {document_id}")
        return job_id
    
    def _read_job_status(self, job_id: UUID) -> Optional[str]:
        row = self.db.execute(text("""
            SELECT status FROM extraction_jobs WHERE id = :job_id
        """), {"job_id": job_id}).fetchone()
        return row[0] if row else None

    def start_job(self, job_id: UUID, chunks_total: Optional[int] = None) -> None:
        """Mark job as running with dynamic timeout"""
        
        current = self._read_job_status(job_id)
        self._guard_transition(job_id, current, 'RUNNING')

        started_at = datetime.utcnow()
        
        if chunks_total:
            timeout_seconds = max(120, min(1800, chunks_total * 30 + 60))
        else:
            timeout_seconds = 300
        
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
        
        logger.info(f"[JobTracker] Started job {job_id}, timeout at {timeout_at}")
    
    def update_progress(
        self, 
        job_id: UUID, 
        chunks_processed: int,
        entities_extracted: Optional[int] = None,
        relationships_extracted: Optional[int] = None
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
        
        current = self._read_job_status(job_id)
        status = JobStatus.PARTIAL if partial else JobStatus.COMPLETE
        self._guard_transition(job_id, current, status.value)
        
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
        
        logger.info(f"[JobTracker] Completed job {job_id}: {status.value}, {entities_extracted} entities, {relationships_extracted} relationships")
    
    def fail_job(self, job_id: UUID, error_message: str) -> None:
        """Mark job as failed"""
        
        current = self._read_job_status(job_id)
        self._guard_transition(job_id, current, 'FAILED')

        self.db.execute(text("""
            UPDATE extraction_jobs 
            SET status = 'FAILED',
                completed_at = :completed_at,
                error_message = :error_message
            WHERE id = :job_id
        """), {
            "job_id": job_id,
            "completed_at": datetime.utcnow(),
            "error_message": error_message[:1000]
        })
        self.db.commit()
        
        logger.error(f"[JobTracker] Failed job {job_id}: {error_message[:200]}")
    
    def timeout_job(self, job_id: UUID) -> None:
        """Mark job as timed out"""
        
        current = self._read_job_status(job_id)
        self._guard_transition(job_id, current, 'TIMEOUT')

        self.db.execute(text("""
            UPDATE extraction_jobs 
            SET status = 'TIMEOUT',
                completed_at = :completed_at,
                error_message = 'Extraction timed out'
            WHERE id = :job_id
        """), {
            "job_id": job_id,
            "completed_at": datetime.utcnow()
        })
        self.db.commit()
        
        logger.warning(f"[JobTracker] Job {job_id} timed out")
    
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
            logger.info(f"[JobTracker] Skipping extraction for {document_id}: content unchanged")
            return True
        
        return False
    
    @staticmethod
    def compute_content_hash(content: str) -> str:
        """SHA-256 hash of document content"""
        return hashlib.sha256(content.encode()).hexdigest()
    
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
        
        chunks_result = self.db.execute(text("""
            SELECT COUNT(*) as count FROM document_chunks 
            WHERE document_id = :doc_id
        """), {"doc_id": document_id}).fetchone()
        actual_chunks = chunks_result.count if chunks_result else 0
        
        entities_result = self.db.execute(text("""
            SELECT COUNT(DISTINCT e.id) as count 
            FROM entities e
            JOIN relationships r ON e.id = r.source_id OR e.id = r.target_id
            JOIN document_chunks c ON r.source_chunk_id = c.id
            WHERE c.document_id = :doc_id
        """), {"doc_id": document_id}).fetchone()
        actual_entities = entities_result.count if entities_result else 0
        
        relationships_result = self.db.execute(text("""
            SELECT COUNT(*) as count FROM relationships r
            JOIN document_chunks c ON r.source_chunk_id = c.id
            WHERE c.document_id = :doc_id
        """), {"doc_id": document_id}).fetchone()
        actual_relationships = relationships_result.count if relationships_result else 0
        
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
    
    def get_timed_out_jobs(self) -> List[Dict[str, Any]]:
        """Get all jobs that have timed out"""
        
        result = self.db.execute(text("""
            SELECT id, document_id, tenant_id, started_at, timeout_at
            FROM extraction_jobs
            WHERE status = 'RUNNING' 
              AND timeout_at < NOW()
        """)).fetchall()
        
        return [dict(row._mapping) for row in result]
    
    def get_retriable_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get failed/timeout jobs that can be retried"""
        
        result = self.db.execute(text("""
            SELECT id, document_id, tenant_id, retry_count, content_hash
            FROM extraction_jobs
            WHERE status IN ('FAILED', 'TIMEOUT')
              AND retry_count < max_retries
              AND created_at > NOW() - INTERVAL '24 hours'
            ORDER BY created_at ASC
            LIMIT :limit
        """), {"limit": limit}).fetchall()
        
        return [dict(row._mapping) for row in result]
    
    def increment_retry(self, job_id: UUID) -> int:
        """Increment retry count and return new count"""
        
        result = self.db.execute(text("""
            UPDATE extraction_jobs 
            SET retry_count = retry_count + 1,
                status = 'PENDING'
            WHERE id = :job_id
            RETURNING retry_count
        """), {"job_id": job_id}).fetchone()
        
        self.db.commit()
        return result.retry_count if result else 0


def get_job_tracker(db_session) -> ExtractionJobTracker:
    """
    Get tracker with provided session.
    In web contexts, pass the request-scoped session.
    """
    return ExtractionJobTracker(db_session)
