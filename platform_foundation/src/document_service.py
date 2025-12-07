"""
Document Service - Document Management

Platform Foundation owns document lifecycle and storage.
Queues extraction requests to Brain.
"""

import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

import psycopg2
from psycopg2.extras import RealDictCursor

from packages.interface_types.src import ExtractionRequest, Priority, ExtractionMode

logger = logging.getLogger(__name__)


class DocumentService:
    """Manages document upload, storage, and extraction queuing."""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        
    def _get_connection(self):
        return psycopg2.connect(self.database_url)
    
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
        Create a new document record.
        
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
