"""
Sync Worker for Bulk Ingestion.

Handles file discovery, junk filtering, deduplication, and queue submission.
Supports multiple source types: S3, Google Drive, direct uploads.
"""

import os
import re
import hashlib
import logging
import mimetypes
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class FileStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    QUEUED = "queued"
    SKIPPED = "skipped"
    FAILED = "failed"
    DUPLICATE = "duplicate"


@dataclass
class DiscoveredFile:
    """Represents a file discovered from a source."""
    name: str
    path: str
    size: int
    mime_type: Optional[str]
    external_id: str
    content_hash: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class JunkFilter:
    """Filters out junk files that shouldn't be processed."""
    
    JUNK_PATTERNS = [
        r'^\.DS_Store$',
        r'^Thumbs\.db$',
        r'^desktop\.ini$',
        r'^\.gitignore$',
        r'^\.git/',
        r'^__pycache__/',
        r'\.pyc$',
        r'^node_modules/',
        r'^\.npm/',
        r'^~\$',
        r'\.tmp$',
        r'\.temp$',
        r'\.swp$',
        r'\.swo$',
        r'^#.*#$',
        r'\.bak$',
        r'\.old$',
        r'^\.Spotlight-V100/',
        r'^\.Trashes/',
        r'^\.fseventsd/',
        r'^\.AppleDouble/',
        r'^\.LSOverride$',
        r'^Icon\r$',
        r'^\._',
        r'^~',
        r'^\.~lock\.',
        r'\.lnk$',
        r'^ehthumbs\.db$',
        r'^ehthumbs_vista\.db$',
    ]
    
    JUNK_REGEX = [re.compile(p, re.IGNORECASE) for p in JUNK_PATTERNS]
    
    ALLOWED_MIME_TYPES = [
        'text/plain',
        'text/markdown',
        'text/csv',
        'text/html',
        'text/xml',
        'application/json',
        'application/xml',
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'application/rtf',
        'text/rtf',
    ]
    
    MAX_FILE_SIZE = 50 * 1024 * 1024
    MIN_FILE_SIZE = 1
    
    @classmethod
    def is_junk(cls, file: DiscoveredFile) -> Tuple[bool, Optional[str]]:
        """
        Check if file should be filtered out.
        Returns (is_junk, reason) tuple.
        """
        for regex in cls.JUNK_REGEX:
            if regex.search(file.path) or regex.search(file.name):
                return True, f"Matches junk pattern"
        
        if file.size < cls.MIN_FILE_SIZE:
            return True, "File is empty"
        
        if file.size > cls.MAX_FILE_SIZE:
            return True, f"File exceeds {cls.MAX_FILE_SIZE // 1024 // 1024}MB limit"
        
        if file.mime_type:
            if not any(file.mime_type.startswith(allowed) for allowed in cls.ALLOWED_MIME_TYPES):
                ext = os.path.splitext(file.name)[1].lower()
                if ext in ['.txt', '.md', '.json', '.csv', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.rtf', '.html', '.xml']:
                    return False, None
                return True, f"Unsupported file type: {file.mime_type}"
        
        return False, None


class Deduplicator:
    """Handles content-based and external ID deduplication."""
    
    def __init__(self, db_session):
        self.session = db_session
    
    def compute_hash(self, content: bytes) -> str:
        """Compute SHA-256 hash of file content."""
        return hashlib.sha256(content).hexdigest()
    
    def check_duplicate(self, tenant_id: str, connector_id: str, 
                       external_id: str, content_hash: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Check if file is a duplicate.
        Returns (is_duplicate, existing_doc_id) tuple.
        """
        from sqlalchemy import text
        
        result = self.session.execute(
            text("""
                SELECT id FROM platform.documents 
                WHERE tenant_id = :tenant_id 
                AND source_connector_id = :connector_id 
                AND external_id = :external_id
            """),
            {"tenant_id": tenant_id, "connector_id": connector_id, "external_id": external_id}
        ).fetchone()
        
        if result:
            return True, str(result[0])
        
        if content_hash:
            result = self.session.execute(
                text("""
                    SELECT id FROM platform.documents 
                    WHERE tenant_id = :tenant_id 
                    AND content_hash = :content_hash
                    LIMIT 1
                """),
                {"tenant_id": tenant_id, "content_hash": content_hash}
            ).fetchone()
            
            if result:
                return True, str(result[0])
        
        return False, None


class SyncWorker:
    """
    Orchestrates sync jobs from source connectors.
    
    Flow:
    1. Create sync job record
    2. Discover files from source
    3. Filter junk files
    4. Check for duplicates
    5. Queue valid files for extraction
    6. Update job status
    """
    
    def __init__(self, db_session, encryption=None):
        self.session = db_session
        self.encryption = encryption
        self.junk_filter = JunkFilter()
        self.deduplicator = Deduplicator(db_session)
    
    def create_sync_job(self, connector_id: str, tenant_id: str) -> str:
        """Create a new sync job and return its ID."""
        from sqlalchemy import text
        
        result = self.session.execute(
            text("""
                INSERT INTO platform.sync_jobs (connector_id, tenant_id, status, started_at)
                VALUES (:connector_id, :tenant_id, 'running', NOW())
                RETURNING id
            """),
            {"connector_id": connector_id, "tenant_id": tenant_id}
        )
        self.session.commit()
        return str(result.fetchone()[0])
    
    def update_job_progress(self, job_id: str, files_total: int = None, 
                           files_processed: int = None, files_failed: int = None,
                           files_skipped: int = None, status: str = None,
                           error_message: str = None):
        """Update sync job progress."""
        from sqlalchemy import text
        
        updates = []
        params = {"job_id": job_id}
        
        if files_total is not None:
            updates.append("files_total = :files_total")
            params["files_total"] = files_total
        if files_processed is not None:
            updates.append("files_processed = :files_processed")
            params["files_processed"] = files_processed
        if files_failed is not None:
            updates.append("files_failed = :files_failed")
            params["files_failed"] = files_failed
        if files_skipped is not None:
            updates.append("files_skipped = :files_skipped")
            params["files_skipped"] = files_skipped
        if status is not None:
            updates.append("status = :status")
            params["status"] = status
            if status in ["completed", "failed"]:
                updates.append("completed_at = NOW()")
        if error_message is not None:
            updates.append("error_message = :error_message")
            params["error_message"] = error_message
        
        if updates:
            self.session.execute(
                text(f"UPDATE platform.sync_jobs SET {', '.join(updates)} WHERE id = :job_id"),
                params
            )
            self.session.commit()
    
    def process_file(self, file: DiscoveredFile, tenant_id: str, 
                    connector_id: str, job_id: str, 
                    content: bytes = None) -> Tuple[FileStatus, Optional[str]]:
        """
        Process a single discovered file.
        Returns (status, document_id or error message).
        """
        is_junk, reason = self.junk_filter.is_junk(file)
        if is_junk:
            logger.debug(f"Skipping junk file {file.name}: {reason}")
            return FileStatus.SKIPPED, reason
        
        content_hash = None
        if content:
            content_hash = self.deduplicator.compute_hash(content)
        
        is_dup, existing_id = self.deduplicator.check_duplicate(
            tenant_id, connector_id, file.external_id, content_hash
        )
        if is_dup:
            logger.debug(f"Skipping duplicate file {file.name}")
            return FileStatus.DUPLICATE, existing_id
        
        try:
            doc_id = self._create_document_record(
                file, tenant_id, connector_id, job_id, content_hash
            )
            return FileStatus.QUEUED, doc_id
        except Exception as e:
            logger.error(f"Failed to process file {file.name}: {e}")
            return FileStatus.FAILED, str(e)
    
    def _create_document_record(self, file: DiscoveredFile, tenant_id: str,
                                connector_id: str, job_id: str, 
                                content_hash: Optional[str]) -> str:
        """Create document record and queue for extraction."""
        from sqlalchemy import text
        
        result = self.session.execute(
            text("""
                INSERT INTO platform.documents 
                (tenant_id, name, mime_type, size, status, source_connector_id, 
                 external_id, content_hash, metadata)
                VALUES (:tenant_id, :name, :mime_type, :size, 'pending', 
                        :connector_id, :external_id, :content_hash, :metadata)
                RETURNING id
            """),
            {
                "tenant_id": tenant_id,
                "name": file.name,
                "mime_type": file.mime_type,
                "size": file.size,
                "connector_id": connector_id,
                "external_id": file.external_id,
                "content_hash": content_hash,
                "metadata": file.metadata
            }
        )
        self.session.commit()
        doc_id = str(result.fetchone()[0])
        
        self._queue_for_extraction(doc_id, tenant_id)
        
        return doc_id
    
    def _queue_for_extraction(self, document_id: str, tenant_id: str):
        """Queue document for extraction via message bus."""
        from sqlalchemy import text
        
        self.session.execute(
            text("""
                INSERT INTO platform.extraction_requests 
                (document_id, tenant_id, status)
                VALUES (:doc_id, :tenant_id, 'pending')
            """),
            {"doc_id": document_id, "tenant_id": tenant_id}
        )
        self.session.commit()
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current sync job status."""
        from sqlalchemy import text
        
        result = self.session.execute(
            text("""
                SELECT id, connector_id, tenant_id, status, files_total,
                       files_processed, files_failed, files_skipped,
                       started_at, completed_at, error_message
                FROM platform.sync_jobs WHERE id = :job_id
            """),
            {"job_id": job_id}
        ).fetchone()
        
        if not result:
            return None
        
        return {
            "id": str(result[0]),
            "connector_id": str(result[1]) if result[1] else None,
            "tenant_id": str(result[2]),
            "status": result[3],
            "files_total": result[4],
            "files_processed": result[5],
            "files_failed": result[6],
            "files_skipped": result[7],
            "started_at": result[8].isoformat() if result[8] else None,
            "completed_at": result[9].isoformat() if result[9] else None,
            "error_message": result[10]
        }
