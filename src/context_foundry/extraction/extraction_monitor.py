"""
Extraction Monitor

Background process to detect stuck/failed extractions and trigger retries.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any
from uuid import UUID

from sqlalchemy import text
from .job_tracker import get_job_tracker, JobStatus
from .circuit_breaker import get_circuit_breaker

logger = logging.getLogger(__name__)


class ExtractionMonitor:
    """Monitor extraction jobs and handle failures"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.tracker = get_job_tracker(db_session)
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
            logger.warning(f"[ExtractionMonitor] Timeout: job={job.id}, document={job.document_id}")
            self.circuit_breaker.record_failure()
        
        if timed_out:
            logger.info(f"[ExtractionMonitor] Marked {len(timed_out)} jobs as TIMEOUT")
        
        return len(timed_out)
    
    def get_retriable_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get failed/timeout jobs that can be retried"""
        
        return self.tracker.get_retriable_jobs(limit)
    
    def queue_retry(self, job_id: UUID) -> bool:
        """Queue a job for retry"""
        
        if not self.circuit_breaker.can_retry():
            logger.warning(f"[ExtractionMonitor] Circuit breaker open, skipping retry for job {job_id}")
            return False
        
        job = self.tracker.get_job(job_id)
        if not job:
            logger.error(f"[ExtractionMonitor] Job {job_id} not found for retry")
            return False
        
        if job['retry_count'] >= job['max_retries']:
            logger.warning(f"[ExtractionMonitor] Job {job_id} has exceeded max retries")
            return False
        
        new_count = self.tracker.increment_retry(job_id)
        logger.info(f"[ExtractionMonitor] Queued retry #{new_count} for job {job_id}")
        
        return True
    
    def process_retries(self, limit: int = 5) -> Dict[str, Any]:
        """Process pending retries"""
        
        retriable = self.get_retriable_jobs(limit)
        
        queued = 0
        skipped = 0
        
        for job in retriable:
            if self.queue_retry(job['id']):
                queued += 1
            else:
                skipped += 1
        
        return {
            "checked": len(retriable),
            "queued": queued,
            "skipped": skipped,
            "circuit_breaker": self.circuit_breaker.get_status()
        }
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall extraction health summary"""
        
        result = self.db.execute(text("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'RUNNING') as running,
                COUNT(*) FILTER (WHERE status = 'PENDING') as pending,
                COUNT(*) FILTER (WHERE status = 'COMPLETE') as complete,
                COUNT(*) FILTER (WHERE status = 'PARTIAL') as partial,
                COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
                COUNT(*) FILTER (WHERE status = 'TIMEOUT') as timeout,
                COUNT(*) FILTER (WHERE status IN ('FAILED', 'TIMEOUT') 
                                 AND retry_count < max_retries
                                 AND created_at > NOW() - INTERVAL '24 hours') as retriable
            FROM extraction_jobs
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)).fetchone()
        
        row = dict(result._mapping)
        
        if row['failed'] > 5 or row['timeout'] > 5:
            health = 'critical'
        elif row['failed'] > 0 or row['timeout'] > 0:
            health = 'degraded'
        elif row['running'] > 0 or row['pending'] > 0:
            health = 'processing'
        else:
            health = 'healthy'
        
        return {
            "health": health,
            "last_24h": {
                "running": row['running'],
                "pending": row['pending'],
                "complete": row['complete'],
                "partial": row['partial'],
                "failed": row['failed'],
                "timeout": row['timeout'],
                "retriable": row['retriable']
            },
            "circuit_breaker": self.circuit_breaker.get_status()
        }
    
    def recover_stale_requests(self, stale_minutes: int = 10) -> int:
        """
        Recover extraction_requests stuck in 'processing' status.
        
        This fixes the gap where requests get stuck if the worker dies mid-processing.
        Requests in 'processing' for longer than stale_minutes are reset to 'pending'.
        """
        result = self.db.execute(text("""
            UPDATE platform.extraction_requests 
            SET status = 'pending',
                retry_count = LEAST(retry_count + 1, max_retries),
                submitted_at = NOW()
            WHERE status = 'processing'
              AND submitted_at < NOW() - MAKE_INTERVAL(mins => :stale_minutes)
              AND retry_count < max_retries
            RETURNING id, document_id, retry_count
        """), {"stale_minutes": stale_minutes})
        
        recovered = result.fetchall()
        self.db.commit()
        
        for req in recovered:
            logger.info(f"[ExtractionMonitor] Recovered stale request: id={req.id}, document={req.document_id}, retry={req.retry_count}")
        
        if recovered:
            logger.warning(f"[ExtractionMonitor] Recovered {len(recovered)} stale extraction requests (stuck > {stale_minutes} min)")
        
        return len(recovered)
    
    def check_orphaned_requests(self) -> Dict[str, int]:
        """
        Check for requests that have no corresponding active job.
        Returns count of orphaned requests by status.
        """
        result = self.db.execute(text("""
            SELECT er.status, COUNT(*) as count
            FROM platform.extraction_requests er
            LEFT JOIN extraction_jobs ej ON ej.document_id = er.document_id 
                AND ej.status = 'RUNNING'
            WHERE er.status = 'processing'
              AND ej.id IS NULL
            GROUP BY er.status
        """))
        
        orphans = {row.status: row.count for row in result.fetchall()}
        
        if orphans:
            total = sum(orphans.values())
            logger.warning(f"[ExtractionMonitor] Found {total} orphaned requests (processing but no running job)")
        
        return orphans
    
    def run_cycle(self) -> Dict[str, Any]:
        """Run a complete monitoring cycle"""
        
        stale_recovered = self.recover_stale_requests()
        timeouts = self.check_timeouts()
        retries = self.process_retries()
        health = self.get_health_summary()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "stale_requests_recovered": stale_recovered,
            "timeouts_detected": timeouts,
            "retries": retries,
            "health": health
        }


def get_extraction_monitor(db_session) -> ExtractionMonitor:
    """Get monitor with provided session"""
    return ExtractionMonitor(db_session)
