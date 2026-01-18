"""
Extraction Worker - Queue Consumer for ExtractionRequests

Brain side of the Platform ↔ Brain contract.
Consumes ExtractionRequests, runs extraction pipeline, writes ExtractionResults.
"""

import logging
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4

import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from packages.interface_types.src import (
        ExtractionRequest,
        ExtractionResult,
        ExtractionErrorCode,
        TokensConsumed,
    )
    from packages.interface_types.src.extraction import ExtractionError
except ImportError as e:
    raise ImportError(
        f"Missing dependency: packages.interface_types. "
        f"This module requires the interface_types package. "
        f"Either install it or use the extraction pipeline directly. Error: {e}"
    )

logger = logging.getLogger(__name__)


class ExtractionWorker:
    """
    Worker that consumes extraction requests from queue and processes them.
    
    Flow:
    1. Claim request from platform.extraction_requests queue
    2. Invoke extraction pipeline
    3. Write ExtractionResult to platform.extraction_results
    4. Update request status to completed/failed
    """
    
    def __init__(
        self,
        worker_id: Optional[str] = None,
        database_url: Optional[str] = None,
        poll_interval: float = 5.0,
        max_retries: int = 3
    ):
        self.worker_id = worker_id or f"worker-{uuid4().hex[:8]}"
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.running = False
        
    def _get_connection(self):
        return psycopg2.connect(self.database_url)
    
    def claim_request(self) -> Optional[Dict[str, Any]]:
        """
        Atomically claim the next extraction request.
        
        Returns:
            Request record if claimed, None if queue is empty
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM platform.claim_extraction_request(%s)",
                    (self.worker_id,)
                )
                result = cur.fetchone()
                conn.commit()
                
                if result and result.get('id'):
                    logger.info(f"[{self.worker_id}] Claimed request: {result['request_id']}")
                    return dict(result)
                return None
    
    def process_request(self, request: Dict[str, Any]) -> ExtractionResult:
        """
        Process an extraction request.
        
        This calls the Brain's extraction pipeline and wraps the result
        in the contract ExtractionResult format.
        """
        start_time = datetime.utcnow()
        started_at = start_time.isoformat() + "Z"
        
        try:
            self._update_request_status(request['request_id'], 'processing')
            
            extraction_result = self._run_extraction_pipeline(
                file_path=request['file_path'],
                file_name=request['file_name'],
                mime_type=request['mime_type'],
                tenant_id=request['tenant_id'],
                document_id=str(request['document_id']),
                ontology_hints=request.get('ontology_hints'),
                extraction_mode=request.get('extraction_mode', 'full')
            )
            
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            completed_at = end_time.isoformat() + "Z"
            
            result = ExtractionResult(
                request_id=str(request['request_id']),
                document_id=str(request['document_id']),
                tenant_id=str(request['tenant_id']),
                status="success" if extraction_result['success'] else "partial",
                entities_extracted=extraction_result.get('entities_count', 0),
                relationships_extracted=extraction_result.get('relationships_count', 0),
                tokens_consumed=TokensConsumed(
                    input_tokens=extraction_result.get('input_tokens', 0),
                    output_tokens=extraction_result.get('output_tokens', 0),
                    total_tokens=extraction_result.get('total_tokens', 0)
                ),
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                extraction_version="1.0.0",
                model_used=extraction_result.get('model_used', 'gpt-4o-mini')
            )
            
            logger.info(
                f"[{self.worker_id}] Extraction complete: "
                f"{result.entities_extracted} entities, "
                f"{result.relationships_extracted} relationships, "
                f"{result.tokens_consumed.total_tokens} tokens"
            )
            
            return result
            
        except Exception as e:
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            completed_at = end_time.isoformat() + "Z"
            
            logger.error(f"[{self.worker_id}] Extraction failed: {e}")
            
            return ExtractionResult(
                request_id=str(request['request_id']),
                document_id=str(request['document_id']),
                tenant_id=str(request['tenant_id']),
                status="failed",
                entities_extracted=0,
                relationships_extracted=0,
                tokens_consumed=TokensConsumed(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0
                ),
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                error=ExtractionError(
                    code=ExtractionErrorCode.INTERNAL_ERROR,
                    message=str(e),
                    recoverable=True
                ),
                extraction_version="1.0.0",
                model_used="gpt-4o-mini"
            )
    
    def _run_extraction_pipeline(
        self,
        file_path: str,
        file_name: str,
        mime_type: str,
        tenant_id: str,
        document_id: str,
        ontology_hints: Optional[list] = None,
        extraction_mode: str = "full"
    ) -> Dict[str, Any]:
        """
        Run the Brain's extraction pipeline.
        
        This is where we call the existing extraction logic.
        Returns structured result with token counts.
        """
        from ..extraction.ontology_centric_pipeline import run_ontology_centric_extraction
        from ..models.schema import get_session
        
        # Check if this is a spreadsheet file
        spreadsheet_extensions = ['.xlsx', '.xls', '.csv']
        file_ext = '.' + file_name.split('.')[-1].lower() if '.' in file_name else ''
        is_spreadsheet = file_ext in spreadsheet_extensions or mime_type in [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel',
            'text/csv'
        ]
        
        row_entities_count = 0
        row_relationships_count = 0
        
        # Handle spreadsheet files with row-level extraction
        if is_spreadsheet:
            try:
                from ..extraction.spreadsheet_loader import SpreadsheetLoader
                loader = SpreadsheetLoader()
                spreadsheet_doc = loader.load(file_path, original_filename=file_name)
                
                # Extract row-level entities
                row_entities, row_relationships = loader.extract_all_row_entities(
                    spreadsheet_doc.tables,
                    file_name
                )
                
                if row_entities:
                    logger.info(f"[ExtractionWorker] Extracted {len(row_entities)} row-level entities from spreadsheet")
                    
                    # Insert row-level entities into Knowledge Graph
                    session = get_session(use_rls_role=False)
                    try:
                        from sqlalchemy import text
                        session.execute(text(f"SET app.tenant_id = '{tenant_id}'"))
                        
                        row_entities_count, row_relationships_count = self._insert_row_entities(
                            session=session,
                            tenant_id=tenant_id,
                            document_id=document_id,
                            entities=row_entities,
                            relationships=row_relationships
                        )
                        
                        session.commit()
                        logger.info(f"[ExtractionWorker] Inserted {row_entities_count} row entities, {row_relationships_count} relationships")
                    except Exception as e:
                        session.rollback()
                        logger.error(f"Failed to insert row entities: {e}")
                    finally:
                        session.close()
                
                # Use the spreadsheet's raw_text (markdown tables) for LLM extraction
                text_content = spreadsheet_doc.raw_text
            except Exception as e:
                logger.error(f"Spreadsheet row extraction failed: {e}")
                # Fall back to reading as text
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text_content = f.read()
                except UnicodeDecodeError:
                    with open(file_path, 'rb') as f:
                        text_content = f.read().decode('utf-8', errors='replace')
        else:
            # Non-spreadsheet files: read as text
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text_content = f.read()
            except UnicodeDecodeError:
                with open(file_path, 'rb') as f:
                    text_content = f.read().decode('utf-8', errors='replace')
        
        session = get_session(use_rls_role=False)
        
        try:
            from sqlalchemy import text
            session.execute(text(f"SET app.tenant_id = '{tenant_id}'"))
            
            result = run_ontology_centric_extraction(
                session=session,
                tenant_id=tenant_id,
                text=text_content,
                document_id=document_id,
                filename=file_name
            )
            
            session.commit()
            
            entities_count = result.staging_result.entities_created if result.staging_result else 0
            relationships_count = result.staging_result.relations_created if result.staging_result else 0
            
            # Add row-level counts
            total_entities = entities_count + row_entities_count
            total_relationships = relationships_count + row_relationships_count
            
            input_tokens = 1500
            output_tokens = 500
            
            logger.info(f"[ExtractionWorker] Extracted: {total_entities} entities ({row_entities_count} from rows), {total_relationships} relationships")
            
            return {
                'success': True,
                'entities_count': total_entities,
                'relationships_count': total_relationships,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': input_tokens + output_tokens,
                'model_used': 'gpt-4o-mini'
            }
            
        except Exception as e:
            session.rollback()
            logger.error(f"Extraction pipeline failed: {e}")
            raise e
        finally:
            session.close()
    
    def _insert_row_entities(
        self,
        session,
        tenant_id: str,
        document_id: str,
        entities: list,
        relationships: list
    ) -> tuple[int, int]:
        """
        Insert row-level entities and relationships into the Knowledge Graph.
        
        Returns:
            Tuple of (entities_inserted, relationships_inserted)
        """
        from ..models.schema import Entity, Relationship, LifecycleState
        from ..memory.episodic import openai_embedding
        from uuid import UUID
        import json
        
        entities_inserted = 0
        relationships_inserted = 0
        
        # Track canonical names to UUIDs for relationship linking
        entity_name_to_id = {}
        
        for entity_data in entities:
            try:
                # Generate embedding for entity
                embed_text = f"{entity_data['display_name']} {entity_data['entity_type']}"
                for key, val in entity_data.get('attributes', {}).items():
                    if not key.startswith('_') and isinstance(val, str):
                        embed_text += f" {val}"
                
                embedding = openai_embedding(embed_text[:2000])
                
                # Create entity
                entity = Entity(
                    tenant_id=UUID(tenant_id),
                    canonical_name=entity_data['canonical_name'],
                    display_name=entity_data['display_name'],
                    entity_type=entity_data['entity_type'],
                    _confidence=entity_data.get('confidence', 0.95),
                    properties=json.dumps(entity_data.get('attributes', {})),
                    source_document_id=document_id,
                    lifecycle_state=LifecycleState.STAGING,
                    embedding=embedding
                )
                
                session.add(entity)
                session.flush()  # Get the entity ID
                
                entity_name_to_id[entity_data['canonical_name']] = entity.id
                entities_inserted += 1
                
            except Exception as e:
                logger.warning(f"Failed to insert entity {entity_data.get('canonical_name')}: {e}")
                continue
        
        # Insert relationships
        for rel_data in relationships:
            try:
                source_id = entity_name_to_id.get(rel_data['source_name'])
                target_id = entity_name_to_id.get(rel_data['target_name'])
                
                # If target doesn't exist, create an implicit entity
                if not target_id and rel_data.get('target_display_name'):
                    implicit_entity = Entity(
                        tenant_id=UUID(tenant_id),
                        canonical_name=rel_data['target_name'],
                        display_name=rel_data['target_display_name'],
                        entity_type=rel_data['target_type'],
                        _confidence=0.7,
                        properties=json.dumps({'_implicit': True}),
                        source_document_id=document_id,
                        lifecycle_state=LifecycleState.STAGING,
                        embedding=openai_embedding(rel_data['target_display_name'])
                    )
                    session.add(implicit_entity)
                    session.flush()
                    target_id = implicit_entity.id
                    entity_name_to_id[rel_data['target_name']] = target_id
                    entities_inserted += 1
                
                if source_id and target_id:
                    relationship = Relationship(
                        tenant_id=UUID(tenant_id),
                        source_entity_id=source_id,
                        target_entity_id=target_id,
                        relation_type=rel_data['relation_type'],
                        _confidence=rel_data.get('confidence', 0.8),
                        properties=json.dumps(rel_data.get('attributes', {})),
                        source_document_id=document_id,
                        lifecycle_state=LifecycleState.STAGING
                    )
                    session.add(relationship)
                    relationships_inserted += 1
                    
            except Exception as e:
                logger.warning(f"Failed to insert relationship {rel_data.get('relation_type')}: {e}")
                continue
        
        return entities_inserted, relationships_inserted
    
    def save_result(self, result: ExtractionResult):
        """Save extraction result to database."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO platform.extraction_results
                    (request_id, document_id, tenant_id, status,
                     entities_extracted, relationships_extracted,
                     input_tokens, output_tokens, total_tokens,
                     started_at, completed_at, duration_ms,
                     error_code, error_message, error_recoverable,
                     extraction_version, model_used)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    result.request_id,
                    result.document_id,
                    result.tenant_id,
                    result.status,
                    result.entities_extracted,
                    result.relationships_extracted,
                    result.tokens_consumed.input_tokens,
                    result.tokens_consumed.output_tokens,
                    result.tokens_consumed.total_tokens,
                    result.started_at,
                    result.completed_at,
                    result.duration_ms,
                    result.error.code.value if result.error else None,
                    result.error.message if result.error else None,
                    result.error.recoverable if result.error else None,
                    result.extraction_version,
                    result.model_used
                ))
                
                final_status = 'completed' if result.status in ('success', 'partial') else 'failed'
                cur.execute("""
                    UPDATE platform.extraction_requests
                    SET status = %s, completed_at = NOW()
                    WHERE request_id = %s
                """, (final_status, result.request_id))
                
                conn.commit()
                
        logger.info(f"[{self.worker_id}] Saved result for request: {result.request_id}")
    
    def _update_request_status(self, request_id: str, status: str):
        """Update extraction request status."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE platform.extraction_requests
                    SET status = %s
                    WHERE request_id = %s
                """, (status, str(request_id)))
                conn.commit()
    
    def process_one(self) -> bool:
        """
        Process a single request from the queue.
        
        Returns:
            True if a request was processed, False if queue was empty
        """
        request = self.claim_request()
        if not request:
            return False
            
        result = self.process_request(request)
        self.save_result(result)
        
        return True
    
    def run(self, max_iterations: Optional[int] = None):
        """
        Run the worker in a polling loop.
        
        Args:
            max_iterations: Optional limit on iterations (for testing)
        """
        self.running = True
        iterations = 0
        
        logger.info(f"[{self.worker_id}] Starting extraction worker")
        
        while self.running:
            if max_iterations and iterations >= max_iterations:
                break
                
            try:
                if not self.process_one():
                    time.sleep(self.poll_interval)
                    
            except Exception as e:
                logger.error(f"[{self.worker_id}] Worker error: {e}")
                time.sleep(self.poll_interval)
                
            iterations += 1
            
        logger.info(f"[{self.worker_id}] Extraction worker stopped")
    
    def stop(self):
        """Stop the worker gracefully."""
        self.running = False
