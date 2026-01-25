"""
Document Service - Document Management

Platform Foundation owns document lifecycle and storage.
Queues extraction requests to Brain.
"""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID, uuid4

import psycopg2
from psycopg2.extras import RealDictCursor

from packages.interface_types.src import ExtractionRequest, Priority, ExtractionMode

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    'text/plain': ['.txt'],
    'text/markdown': ['.md'],
    'text/csv': ['.csv'],
    'application/pdf': ['.pdf'],
    'application/json': ['.json'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    'application/vnd.ms-excel': ['.xls'],
}

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


class DocumentService:
    """Manages document upload, storage, and extraction queuing."""
    
    def __init__(self, database_url: Optional[str] = None, storage_root: str = "./storage"):
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        
    def _get_connection(self):
        return psycopg2.connect(self.database_url)
    
    def validate_file(self, filename: str, mime_type: str, size_bytes: int) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate file before upload.
        
        Returns:
            (is_valid, error_message, resolved_mime_type)
        """
        if size_bytes > MAX_FILE_SIZE_BYTES:
            return False, f"File too large. Maximum size is {MAX_FILE_SIZE_BYTES // (1024*1024)} MB", None
        
        ext = Path(filename).suffix.lower()
        
        ext_to_mime = {ext: mime for mime, exts in ALLOWED_MIME_TYPES.items() for ext in exts}
        
        if mime_type in ALLOWED_MIME_TYPES:
            if ext in ALLOWED_MIME_TYPES[mime_type]:
                return True, None, mime_type
        
        if ext in ext_to_mime:
            resolved_mime = ext_to_mime[ext]
            return True, None, resolved_mime
        
        allowed_exts = ", ".join(ext_to_mime.keys())
        return False, f"File extension '{ext}' not allowed. Supported: {allowed_exts}", None
    
    def check_quota(self, tenant_id: UUID) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if tenant has quota available for a new document.
        
        Returns:
            (has_quota, quota_info)
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        q.document_limit,
                        q.storage_gb_limit,
                        COUNT(d.id) as current_documents,
                        COALESCE(SUM(d.size_bytes), 0) as current_storage_bytes
                    FROM platform.tenant_quotas q
                    LEFT JOIN platform.documents d ON d.tenant_id = q.tenant_id
                    WHERE q.tenant_id = %s
                    GROUP BY q.tenant_id, q.document_limit, q.storage_gb_limit
                """, (str(tenant_id),))
                
                result = cur.fetchone()
                
                if not result:
                    cur.execute("""
                        INSERT INTO platform.tenant_quotas (tenant_id)
                        VALUES (%s)
                        ON CONFLICT (tenant_id) DO NOTHING
                    """, (str(tenant_id),))
                    conn.commit()
                    return True, {
                        "document_limit": 500,
                        "current_documents": 0,
                        "storage_gb_limit": 10,
                        "current_storage_gb": 0
                    }
                
                quota_info = {
                    "document_limit": result['document_limit'],
                    "current_documents": result['current_documents'],
                    "storage_gb_limit": result['storage_gb_limit'],
                    "current_storage_gb": result['current_storage_bytes'] / (1024**3)
                }
                
                if result['current_documents'] >= result['document_limit']:
                    return False, quota_info
                
                current_storage_gb = result['current_storage_bytes'] / (1024**3)
                if current_storage_gb >= result['storage_gb_limit']:
                    return False, quota_info
                
                return True, quota_info
    
    def store_file(self, tenant_id: UUID, document_id: UUID, file_content: bytes, version: int = 1) -> str:
        """
        Store file to disk with tenant-isolated path.
        
        Path format: /tenants/{tenant_id}/documents/{doc_id}/v{version}/
        
        Returns:
            The storage path
        """
        storage_dir = self.storage_root / "tenants" / str(tenant_id) / "documents" / str(document_id) / f"v{version}"
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = storage_dir / "content"
        file_path.write_bytes(file_content)
        
        logger.info(f"Stored file: {file_path}")
        return str(file_path)
    
    def get_file_content(self, storage_path: str) -> Optional[bytes]:
        """Read file content from storage path."""
        path = Path(storage_path)
        if path.exists():
            return path.read_bytes()
        return None
    
    def delete_file(self, storage_path: str) -> bool:
        """Delete a stored file."""
        path = Path(storage_path)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def create_document(
        self,
        tenant_id: UUID,
        name: str,
        original_filename: str,
        mime_type: str,
        size_bytes: int,
        storage_path: str,
        folder_id: Optional[UUID] = None,
        created_by: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Create a new document record with auto-generated ID.
        
        Args:
            tenant_id: Owner tenant
            name: Display name
            original_filename: Original uploaded filename
            mime_type: MIME type (application/pdf, etc.)
            size_bytes: File size in bytes
            storage_path: Path in object storage
            folder_id: Optional folder location
            created_by: Optional user who uploaded
            
        Returns:
            Created document record
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO platform.documents 
                    (tenant_id, name, original_filename, mime_type, size_bytes, storage_path, folder_id, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                """, (
                    str(tenant_id), name, original_filename, mime_type,
                    size_bytes, storage_path, 
                    str(folder_id) if folder_id else None,
                    str(created_by) if created_by else None
                ))
                
                document = dict(cur.fetchone())
                conn.commit()
                
                cur.execute("""
                    INSERT INTO platform.document_versions
                    (document_id, version_number, storage_path, size_bytes, created_by)
                    VALUES (%s, 1, %s, %s, %s)
                """, (
                    document['id'], storage_path, size_bytes,
                    str(created_by) if created_by else None
                ))
                conn.commit()
                
                logger.info(f"Created document: {name} for tenant {tenant_id}")
                return document
    
    def create_document_with_id(
        self,
        document_id: UUID,
        tenant_id: UUID,
        name: str,
        original_filename: str,
        mime_type: str,
        size_bytes: int,
        storage_path: str,
        folder_id: Optional[UUID] = None,
        created_by: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Create a new document record with a specified ID.
        Used when the document_id is pre-generated (e.g., for storage path matching).
        
        Returns:
            Created document record
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO platform.documents 
                    (id, tenant_id, name, original_filename, mime_type, size_bytes, storage_path, folder_id, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                """, (
                    str(document_id), str(tenant_id), name, original_filename, mime_type,
                    size_bytes, storage_path, 
                    str(folder_id) if folder_id else None,
                    str(created_by) if created_by else None
                ))
                
                document = dict(cur.fetchone())
                conn.commit()
                
                cur.execute("""
                    INSERT INTO platform.document_versions
                    (document_id, version_number, storage_path, size_bytes, created_by)
                    VALUES (%s, 1, %s, %s, %s)
                """, (
                    str(document_id), storage_path, size_bytes,
                    str(created_by) if created_by else None
                ))
                conn.commit()
                
                logger.info(f"Created document with ID {document_id}: {name} for tenant {tenant_id}")
                return document
    
    def get_document(self, document_id: UUID, tenant_id: UUID) -> Optional[Dict[str, Any]]:
        """Get document by ID with tenant isolation."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM platform.documents 
                    WHERE id = %s AND tenant_id = %s
                """, (str(document_id), str(tenant_id)))
                result = cur.fetchone()
                return dict(result) if result else None
    
    def list_documents(
        self,
        tenant_id: UUID,
        folder_id: Optional[UUID] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List documents with filters."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = "SELECT * FROM platform.documents WHERE tenant_id = %s"
                params = [str(tenant_id)]
                
                if folder_id:
                    query += " AND folder_id = %s"
                    params.append(str(folder_id))
                    
                if status:
                    query += " AND status = %s"
                    params.append(status)
                    
                query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]
    
    def update_document_status(
        self,
        document_id: UUID,
        tenant_id: UUID,
        status: str
    ) -> bool:
        """Update document extraction status."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE platform.documents 
                    SET status = %s, updated_at = NOW()
                    WHERE id = %s AND tenant_id = %s
                """, (status, str(document_id), str(tenant_id)))
                conn.commit()
                return cur.rowcount > 0
    
    def queue_for_extraction(
        self,
        document_id: UUID,
        tenant_id: UUID,
        priority: str = "normal",
        ontology_hints: Optional[List[str]] = None,
        extraction_mode: str = "full"
    ) -> Dict[str, Any]:
        """
        Queue a document for extraction by Brain.
        
        Creates an ExtractionRequest and writes to extraction_requests table.
        
        Returns:
            The extraction request record
        """
        document = self.get_document(document_id, tenant_id)
        if not document:
            raise ValueError(f"Document {document_id} not found for tenant {tenant_id}")
        
        request_id = str(uuid4())
        submitted_at = datetime.utcnow().isoformat() + "Z"
        
        request = ExtractionRequest(
            request_id=request_id,
            document_id=str(document_id),
            tenant_id=str(tenant_id),
            file_path=document['storage_path'],
            file_name=document['original_filename'],
            mime_type=document['mime_type'],
            file_size_bytes=document['size_bytes'],
            ontology_hints=ontology_hints,
            extraction_mode=ExtractionMode(extraction_mode),
            priority=Priority(priority),
            submitted_at=submitted_at
        )
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO platform.extraction_requests
                    (request_id, document_id, tenant_id, file_path, file_name, 
                     mime_type, file_size_bytes, ontology_hints, extraction_mode, priority)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                """, (
                    request.request_id,
                    str(document_id),
                    str(tenant_id),
                    request.file_path,
                    request.file_name,
                    request.mime_type,
                    request.file_size_bytes,
                    request.ontology_hints,
                    request.extraction_mode.value,
                    request.priority.value
                ))
                
                extraction_request = dict(cur.fetchone())
                
                cur.execute("""
                    UPDATE platform.documents SET status = 'queued', updated_at = NOW()
                    WHERE id = %s
                """, (str(document_id),))
                
                conn.commit()
                
                logger.info(f"Queued document {document_id} for extraction: {request_id}")
                return extraction_request
    
    def get_extraction_status(
        self,
        request_id: str,
        tenant_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get extraction request status."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT r.*, 
                           res.status as result_status,
                           res.entities_extracted,
                           res.relationships_extracted,
                           res.total_tokens,
                           res.error_message
                    FROM platform.extraction_requests r
                    LEFT JOIN platform.extraction_results res ON r.request_id = res.request_id
                    WHERE r.request_id = %s AND r.tenant_id = %s
                """, (request_id, str(tenant_id)))
                result = cur.fetchone()
                return dict(result) if result else None
    
    def upload_document(
        self,
        tenant_id: UUID,
        filename: str,
        mime_type: str,
        file_content: bytes,
        folder_id: Optional[UUID] = None,
        created_by: Optional[UUID] = None,
        auto_extract: bool = True,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        Complete upload flow: validate, check quota, store file, create record, queue for extraction.
        
        Args:
            tenant_id: Owner tenant
            filename: Original filename
            mime_type: MIME type
            file_content: Raw file bytes
            folder_id: Optional folder
            created_by: User who uploaded
            auto_extract: Whether to queue for extraction immediately
            priority: Extraction priority (low, normal, high)
            
        Returns:
            Document record with extraction_request_id if auto_extract=True
        """
        size_bytes = len(file_content)
        
        safe_filename = Path(filename).name
        if not safe_filename or safe_filename.startswith('.'):
            raise ValueError("Invalid filename")
        
        is_valid, error, resolved_mime = self.validate_file(safe_filename, mime_type, size_bytes)
        if not is_valid:
            raise ValueError(error)
        
        final_mime_type = resolved_mime or mime_type
        
        has_quota, quota_info = self.check_quota(tenant_id)
        if not has_quota:
            raise ValueError(
                f"Quota exceeded. Documents: {quota_info['current_documents']}/{quota_info['document_limit']}, "
                f"Storage: {quota_info['current_storage_gb']:.2f}/{quota_info['storage_gb_limit']} GB"
            )
        
        document_id = uuid4()
        storage_path = None
        
        try:
            storage_path = self.store_file(tenant_id, document_id, file_content, version=1)
            
            document = self.create_document_with_id(
                document_id=document_id,
                tenant_id=tenant_id,
                name=safe_filename,
                original_filename=safe_filename,
                mime_type=final_mime_type,
                size_bytes=size_bytes,
                storage_path=storage_path,
                folder_id=folder_id,
                created_by=created_by
            )
            
            self.log_usage(tenant_id, "upload", document_id=document['id'])
            
            if auto_extract:
                extraction_request = self.queue_for_extraction(
                    document_id=UUID(str(document['id'])),
                    tenant_id=tenant_id,
                    priority=priority
                )
                document['extraction_request_id'] = extraction_request['request_id']
            
            return document
            
        except Exception as e:
            if storage_path:
                try:
                    self.delete_file(storage_path)
                    storage_dir = Path(storage_path).parent
                    if storage_dir.exists() and not any(storage_dir.iterdir()):
                        shutil.rmtree(storage_dir.parent, ignore_errors=True)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup orphaned file: {cleanup_error}")
            raise e
    
    def log_usage(
        self,
        tenant_id: UUID,
        event_type: str,
        tokens_consumed: int = 0,
        user_id: Optional[UUID] = None,
        api_key_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a usage event for billing."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO platform.usage_events
                    (tenant_id, user_id, api_key_id, event_type, tokens_consumed, 
                     document_id, request_id, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    str(tenant_id),
                    str(user_id) if user_id else None,
                    str(api_key_id) if api_key_id else None,
                    event_type,
                    tokens_consumed,
                    str(document_id) if document_id else None,
                    request_id,
                    psycopg2.extras.Json(metadata) if metadata else None
                ))
                conn.commit()
                logger.debug(f"Logged usage: {event_type} for tenant {tenant_id}")
    
    def process_extraction_results(self) -> int:
        """
        Process completed extraction results.
        Updates document status and logs token usage.
        
        Returns:
            Number of results processed
        """
        processed = 0
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT r.*, req.document_id
                    FROM platform.extraction_results r
                    JOIN platform.extraction_requests req ON r.request_id = req.request_id
                    WHERE r.id NOT IN (
                        SELECT DISTINCT (metadata->>'extraction_result_id')::uuid
                        FROM platform.usage_events
                        WHERE event_type = 'extraction' 
                        AND metadata->>'extraction_result_id' IS NOT NULL
                    )
                """)
                
                results = cur.fetchall()
                
                for result in results:
                    new_status = 'extracted' if result['status'] == 'success' else 'failed'
                    if result['status'] == 'partial':
                        new_status = 'partial'
                    
                    cur.execute("""
                        UPDATE platform.documents
                        SET status = %s, extraction_level = 'single', single_extracted_at = NOW(), updated_at = NOW()
                        WHERE id = %s
                    """, (new_status, result['document_id']))
                    
                    cur.execute("""
                        INSERT INTO platform.usage_events
                        (tenant_id, event_type, tokens_consumed, document_id, request_id, metadata)
                        VALUES (%s, 'extraction', %s, %s, %s, %s)
                    """, (
                        result['tenant_id'],
                        result['total_tokens'],
                        result['document_id'],
                        result['request_id'],
                        psycopg2.extras.Json({
                            'extraction_result_id': str(result['id']),
                            'input_tokens': result['input_tokens'],
                            'output_tokens': result['output_tokens'],
                            'entities_extracted': result['entities_extracted'],
                            'relationships_extracted': result['relationships_extracted'],
                            'duration_ms': result['duration_ms']
                        })
                    ))
                    
                    processed += 1
                    logger.info(f"Processed extraction result for document {result['document_id']}: {new_status}")
                
                conn.commit()
        
        return processed
