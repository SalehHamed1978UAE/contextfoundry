"""
Auto-Trigger Service for Multi-Model Extraction

Automatically detects unextracted documents in a vault and queues them
for extraction without hardcoded corpus names.

Key behaviors:
- Polls for documents with status='queued' that have no extraction_request
- Creates extraction requests for detected documents
- Works with any vault_id, no corpus-specific configuration needed
- Integrates with the multi-model extraction pipeline when enabled
"""

import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

MULTI_MODEL_EXTRACTION_ENABLED = os.environ.get(
    'MULTI_MODEL_EXTRACTION_ENABLED', 'false'
).lower() in ('true', '1', 'yes')


class ExtractionAutoTrigger:
    """
    Automatically triggers extraction for new documents.
    
    This service:
    1. Polls for documents that need extraction (status='queued', no request)
    2. Creates extraction_requests for them
    3. The ExtractionWorker picks them up and runs the pipeline
    """
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        poll_interval: float = 10.0,
        batch_size: int = 50,
    ):
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.running = False
        
    def _get_session(self):
        """Get database session."""
        engine = create_engine(self.database_url)
        Session = sessionmaker(bind=engine)
        return Session()
    
    def find_pending_documents(
        self,
        vault_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find documents that need extraction.
        
        A document needs extraction if:
        - status IN ('queued', 'uploaded') - documents awaiting extraction
        - No pending/processing extraction_request exists for it
        - No completed extraction_request exists (avoids re-extraction)
        
        Args:
            vault_id: Optional filter by vault (tenant_id)
            limit: Max documents to return
            
        Returns:
            List of documents needing extraction
        """
        session = self._get_session()
        try:
            query = """
                SELECT 
                    d.id as document_id,
                    d.tenant_id as vault_id,
                    d.name,
                    d.storage_path,
                    d.mime_type,
                    d.size_bytes,
                    d.created_at
                FROM platform.documents d
                WHERE d.status IN ('queued', 'uploaded')
                  AND NOT EXISTS (
                      SELECT 1 FROM platform.extraction_requests er
                      WHERE er.document_id = d.id
                        AND er.status IN ('pending', 'processing', 'completed')
                  )
            """
            
            params = {}
            
            if vault_id:
                query += " AND d.tenant_id = :vault_id"
                params['vault_id'] = vault_id
            
            query += " ORDER BY d.created_at ASC"
            
            if limit:
                query += f" LIMIT {limit}"
            elif self.batch_size:
                query += f" LIMIT {self.batch_size}"
            
            result = session.execute(text(query), params)
            
            documents = []
            for row in result.fetchall():
                documents.append({
                    'document_id': str(row.document_id),
                    'vault_id': str(row.vault_id),
                    'name': row.name,
                    'storage_path': row.storage_path,
                    'mime_type': row.mime_type or 'text/plain',
                    'size_bytes': row.size_bytes or 0,
                    'created_at': row.created_at.isoformat() if row.created_at else None,
                })
            
            return documents
            
        finally:
            session.close()
    
    def create_extraction_request(
        self,
        document_id: str,
        vault_id: str,
        file_path: str,
        file_name: str,
        mime_type: str = 'text/plain',
        file_size: int = 0,
        priority: str = 'normal',
    ) -> Optional[str]:
        """
        Create an extraction request for a document.
        
        Uses a CTE-based conditional insert to ensure idempotency:
        only creates a request if no pending/processing request exists.
        
        Args:
            document_id: Document UUID
            vault_id: Vault (tenant) UUID  
            file_path: Path to document file
            file_name: Original filename
            mime_type: MIME type
            file_size: File size in bytes
            priority: Request priority (normal, high, low)
            
        Returns:
            Request ID if created, None if skipped or failed
        """
        session = self._get_session()
        try:
            request_id = str(uuid4())
            new_id = str(uuid4())
            
            result = session.execute(text("""
                WITH existing AS (
                    SELECT 1 FROM platform.extraction_requests
                    WHERE document_id = :document_id
                      AND status IN ('pending', 'processing')
                    LIMIT 1
                )
                INSERT INTO platform.extraction_requests (
                    id, request_id, document_id, tenant_id,
                    file_path, file_name, mime_type, file_size_bytes,
                    extraction_mode, priority, status, 
                    retry_count, max_retries, submitted_at, created_at
                )
                SELECT 
                    :id, :request_id, :document_id, :tenant_id,
                    :file_path, :file_name, :mime_type, :file_size_bytes,
                    :extraction_mode, :priority, 'pending',
                    0, 3, NOW(), NOW()
                WHERE NOT EXISTS (SELECT 1 FROM existing)
                RETURNING request_id
            """), {
                'id': new_id,
                'request_id': request_id,
                'document_id': document_id,
                'tenant_id': vault_id,
                'file_path': file_path,
                'file_name': file_name,
                'mime_type': mime_type,
                'file_size_bytes': file_size,
                'extraction_mode': 'multi_model' if MULTI_MODEL_EXTRACTION_ENABLED else 'full',
                'priority': priority,
            })
            
            inserted = result.fetchone()
            session.commit()
            
            if inserted:
                logger.info(
                    f"[AutoTrigger] Created extraction request {request_id} "
                    f"for document {file_name} in vault {vault_id}"
                )
                return request_id
            else:
                logger.debug(
                    f"[AutoTrigger] Skipped {file_name} - request already exists"
                )
                return None
            
        except Exception as e:
            session.rollback()
            logger.error(f"[AutoTrigger] Failed to create extraction request: {e}")
            return None
        finally:
            session.close()
    
    def trigger_vault_extraction(
        self,
        vault_id: str,
        priority: str = 'normal',
    ) -> Dict[str, Any]:
        """
        Trigger extraction for all pending documents in a vault.
        
        Args:
            vault_id: Vault UUID
            priority: Request priority
            
        Returns:
            Summary of triggered extractions
        """
        pending = self.find_pending_documents(vault_id=vault_id)
        
        triggered = 0
        failed = 0
        
        for doc in pending:
            request_id = self.create_extraction_request(
                document_id=doc['document_id'],
                vault_id=doc['vault_id'],
                file_path=doc['storage_path'] or '',
                file_name=doc['name'],
                mime_type=doc['mime_type'],
                file_size=doc['size_bytes'],
                priority=priority,
            )
            
            if request_id:
                triggered += 1
            else:
                failed += 1
        
        logger.info(
            f"[AutoTrigger] Vault {vault_id}: "
            f"triggered={triggered}, failed={failed}, total_pending={len(pending)}"
        )
        
        return {
            'vault_id': vault_id,
            'documents_found': len(pending),
            'extractions_triggered': triggered,
            'failures': failed,
            'extraction_mode': 'multi_model' if MULTI_MODEL_EXTRACTION_ENABLED else 'legacy',
        }
    
    def trigger_all_pending(self, priority: str = 'normal') -> Dict[str, Any]:
        """
        Trigger extraction for all pending documents across all vaults.
        
        Returns:
            Summary by vault
        """
        pending = self.find_pending_documents()
        
        by_vault: Dict[str, int] = {}
        triggered = 0
        failed = 0
        
        for doc in pending:
            vault_id = doc['vault_id']
            by_vault[vault_id] = by_vault.get(vault_id, 0) + 1
            
            request_id = self.create_extraction_request(
                document_id=doc['document_id'],
                vault_id=vault_id,
                file_path=doc['storage_path'] or '',
                file_name=doc['name'],
                mime_type=doc['mime_type'],
                file_size=doc['size_bytes'],
                priority=priority,
            )
            
            if request_id:
                triggered += 1
            else:
                failed += 1
        
        logger.info(
            f"[AutoTrigger] All vaults: "
            f"triggered={triggered}, failed={failed}, vaults={len(by_vault)}"
        )
        
        return {
            'total_documents': len(pending),
            'extractions_triggered': triggered,
            'failures': failed,
            'vaults_affected': len(by_vault),
            'by_vault': by_vault,
            'extraction_mode': 'multi_model' if MULTI_MODEL_EXTRACTION_ENABLED else 'legacy',
        }
    
    def run_poll_cycle(self) -> Dict[str, Any]:
        """
        Run a single poll cycle.
        
        Finds pending documents and triggers extraction for them.
        """
        start = datetime.utcnow()
        
        result = self.trigger_all_pending()
        
        elapsed_ms = int((datetime.utcnow() - start).total_seconds() * 1000)
        result['cycle_duration_ms'] = elapsed_ms
        
        return result
    
    def run(self, max_cycles: Optional[int] = None):
        """
        Run the auto-trigger service in a polling loop.
        
        Args:
            max_cycles: Optional limit on cycles (for testing)
        """
        self.running = True
        cycles = 0
        
        logger.info(
            f"[AutoTrigger] Starting auto-trigger service "
            f"(poll_interval={self.poll_interval}s, batch_size={self.batch_size}, "
            f"multi_model={'enabled' if MULTI_MODEL_EXTRACTION_ENABLED else 'disabled'})"
        )
        
        while self.running:
            if max_cycles and cycles >= max_cycles:
                break
            
            try:
                result = self.run_poll_cycle()
                
                if result['extractions_triggered'] > 0:
                    logger.info(
                        f"[AutoTrigger] Cycle {cycles + 1}: "
                        f"triggered {result['extractions_triggered']} extractions"
                    )
                
            except Exception as e:
                logger.error(f"[AutoTrigger] Cycle error: {e}")
            
            cycles += 1
            time.sleep(self.poll_interval)
        
        logger.info(f"[AutoTrigger] Auto-trigger service stopped after {cycles} cycles")
    
    def stop(self):
        """Stop the auto-trigger service."""
        self.running = False


def get_auto_trigger(
    database_url: Optional[str] = None,
    poll_interval: float = 10.0,
) -> ExtractionAutoTrigger:
    """Get an auto-trigger instance."""
    return ExtractionAutoTrigger(
        database_url=database_url,
        poll_interval=poll_interval,
    )


def trigger_extraction_for_vault(vault_id: str) -> Dict[str, Any]:
    """
    Convenience function to trigger extraction for a vault.
    
    This is the main entry point for integrating with document upload flows.
    Call this after documents are uploaded to automatically queue extraction.
    
    Args:
        vault_id: The vault/tenant UUID
        
    Returns:
        Summary of triggered extractions
    """
    trigger = get_auto_trigger()
    return trigger.trigger_vault_extraction(vault_id)
