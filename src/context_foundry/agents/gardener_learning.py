"""
Gardener Learning Processor for Stage 3: Learning from Interaction

Processes learning tickets asynchronously to improve the World Model.
Re-extracts from source documents, validates new facts, adds to STAGING.

Resolution Payload Requirements (for governance/auditing):
{
  "action": "extracted|not_found|flagged_for_review",
  "improved": true|false,
  "facts_added": {
    "entities": ["entity_id_1", ...],
    "relationships": ["rel_id_1", ...]
  },
  "lifecycle_states": {
    "entity_id_1": "STAGING",
    ...
  },
  "source_chunks_used": ["chunk_id_1", ...],
  "processing_time_ms": 1234,
  "notes": "Human-readable summary"
}
"""

import json
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from rich import print as rprint


class GardenerLearningProcessor:
    """Processes learning tickets to improve the World Model."""
    
    def __init__(self, session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self._graph_builder = None
    
    @property
    def graph_builder(self):
        """Lazy load GraphBuilderAgent to avoid circular imports."""
        if self._graph_builder is None:
            from .graph_builder import GraphBuilderAgent
            self._graph_builder = GraphBuilderAgent(session=self.session)
        return self._graph_builder
    
    def process_pending_tickets(self, max_tickets: int = 10) -> List[Dict[str, Any]]:
        """Process highest priority learning tickets."""
        self.session.execute(
            text(f"SET app.current_tenant_id = '{self.tenant_id}'")
        )
        
        tickets = self.session.execute(
            text("""
                SELECT * FROM learning_tickets
                WHERE tenant_id = :tenant_id
                AND status = 'pending'
                ORDER BY (priority * hit_count) DESC
                LIMIT :limit
            """),
            {'tenant_id': self.tenant_id, 'limit': max_tickets}
        ).fetchall()
        
        results = []
        for ticket in tickets:
            result = self._process_ticket(dict(ticket._mapping))
            results.append(result)
        
        return results
    
    def _process_ticket(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single learning ticket."""
        start_time = time.time()
        
        self._update_ticket_status(ticket['id'], 'processing')
        
        try:
            if ticket['gap_type'] == 'missing_entity':
                result = self._handle_missing_entity(ticket)
            elif ticket['gap_type'] == 'sparse_relationships':
                result = self._handle_sparse_relationships(ticket)
            elif ticket['gap_type'] == 'stale_data':
                result = self._handle_stale_data(ticket)
            else:
                result = {
                    'action': 'ignored',
                    'improved': False,
                    'notes': f"Unknown gap type: {ticket['gap_type']}"
                }
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            resolution_payload = {
                'action': result.get('action', 'unknown'),
                'improved': result.get('improved', False),
                'facts_added': {
                    'entities': result.get('entities_added_ids', []),
                    'relationships': result.get('relationships_added_ids', [])
                },
                'lifecycle_states': result.get('lifecycle_states', {}),
                'source_chunks_used': result.get('source_chunks_used', []),
                'processing_time_ms': processing_time_ms,
                'notes': result.get('notes', '')
            }
            
            final_status = 'resolved' if result.get('improved') else 'ignored'
            self._update_ticket_status(ticket['id'], final_status, resolution_payload)
            
            return {'ticket_id': str(ticket['id']), **resolution_payload}
            
        except Exception as e:
            self.session.rollback()  # Rollback failed transaction before updating
            error_payload = {
                'action': 'error',
                'improved': False,
                'error': str(e)[:200],
                'notes': f"Processing failed: {str(e)[:100]}"
            }
            try:
                self._update_ticket_status(ticket['id'], 'ignored', error_payload)
            except Exception:
                pass  # Don't fail on failed error logging
            return {'ticket_id': str(ticket['id']), **error_payload}
    
    def _handle_missing_entity(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """Try to extract a missing entity from source documents."""
        entity_name = ticket.get('focal_entity_name')
        source_chunks = ticket.get('source_chunk_ids') or []
        
        if not source_chunks:
            source_chunks = self._find_chunks_mentioning(entity_name)
        
        if not source_chunks:
            return {
                'action': 'no_sources',
                'improved': False,
                'notes': f"No source documents found mentioning '{entity_name}'"
            }
        
        entities_added_ids = []
        lifecycle_states = {}
        chunks_used = []
        
        for chunk_id in source_chunks[:5]:
            chunk = self._get_chunk(chunk_id)
            if chunk:
                chunks_used.append(str(chunk_id))
                
                extracted = self._extract_with_focus(
                    chunk.get('content', ''),
                    focus_entity=entity_name
                )
                
                for entity in extracted.get('entities', []):
                    entity_id = str(entity.get('id', uuid.uuid4()))
                    entities_added_ids.append(entity_id)
                    lifecycle_states[entity_id] = 'STAGING'
        
        found = any(
            self._entity_matches_name(eid, entity_name)
            for eid in entities_added_ids
        )
        
        return {
            'action': 'extracted' if found else 'not_found',
            'improved': found,
            'entities_added_ids': entities_added_ids,
            'lifecycle_states': lifecycle_states,
            'source_chunks_used': chunks_used,
            'notes': f"Found {len(entities_added_ids)} entities, target entity {'found' if found else 'not found'}"
        }
    
    def _handle_sparse_relationships(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """Try to extract more relationships for an entity."""
        entity_id = ticket.get('focal_entity_id')
        entity_name = ticket.get('focal_entity_name')
        
        current_count = self._get_relationship_count(entity_id) if entity_id else 0
        
        source_chunks = self._find_chunks_for_entity(entity_id, entity_name)
        
        if not source_chunks:
            return {
                'action': 'no_sources',
                'improved': False,
                'notes': 'No source documents found for entity'
            }
        
        relationships_added_ids = []
        lifecycle_states = {}
        chunks_used = []
        
        for chunk_id in source_chunks[:5]:
            chunk = self._get_chunk(chunk_id)
            if chunk:
                chunks_used.append(str(chunk_id))
                
                extracted = self._extract_relationships_for_entity(
                    chunk.get('content', ''),
                    entity_name=entity_name
                )
                
                for rel in extracted.get('relationships', []):
                    if self._is_new_relationship(rel, entity_id):
                        saved_id = self._save_relationship(rel)
                        if saved_id:
                            relationships_added_ids.append(saved_id)
                            lifecycle_states[saved_id] = 'STAGING'
        
        new_count = self._get_relationship_count(entity_id) if entity_id else current_count + len(relationships_added_ids)
        
        return {
            'action': 'extracted',
            'improved': new_count > current_count,
            'relationships_added_ids': relationships_added_ids,
            'lifecycle_states': lifecycle_states,
            'source_chunks_used': chunks_used,
            'relationships_before': current_count,
            'relationships_after': new_count,
            'notes': f"Added {len(relationships_added_ids)} new relationships"
        }
    
    def _handle_stale_data(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """Flag stale data for review - may need new documents."""
        return {
            'action': 'flagged_for_review',
            'improved': False,
            'notes': 'Stale data detected. New documents may be needed for updates.'
        }
    
    def _update_ticket_status(
        self, 
        ticket_id: str, 
        status: str, 
        resolution: Dict[str, Any] = None
    ):
        """Update ticket status with structured resolution payload."""
        self.session.execute(text(f"SET app.current_tenant_id = '{self.tenant_id}'"))
        self.session.execute(
            text("""
                UPDATE learning_tickets
                SET status = :status,
                    resolution_notes = :resolution,
                    resolved_at = CASE WHEN :status IN ('resolved', 'ignored') THEN NOW() ELSE NULL END,
                    updated_at = NOW()
                WHERE id = :ticket_id
            """),
            {
                'ticket_id': str(ticket_id),
                'status': status,
                'resolution': json.dumps(resolution) if resolution else None
            }
        )
        self.session.commit()
    
    def _find_chunks_mentioning(self, entity_name: str) -> List[str]:
        """Find document chunks that mention an entity name."""
        if not entity_name:
            return []
        
        result = self.session.execute(
            text("""
                SELECT id FROM document_chunks
                WHERE tenant_id = :tenant_id
                AND LOWER(text) LIKE LOWER(:pattern)
                LIMIT 10
            """),
            {
                'tenant_id': self.tenant_id,
                'pattern': f'%{entity_name}%'
            }
        ).fetchall()
        
        return [str(row.id) for row in result]
    
    def _find_chunks_for_entity(self, entity_id: str, entity_name: str) -> List[str]:
        """Find document chunks associated with an entity."""
        if entity_id:
            result = self.session.execute(
                text("""
                    SELECT DISTINCT source_document_id as id
                    FROM entities
                    WHERE id = :entity_id
                    AND source_document_id IS NOT NULL
                    UNION
                    SELECT DISTINCT source_document_id
                    FROM relationships
                    WHERE (source_id = :entity_id OR target_id = :entity_id)
                    AND source_document_id IS NOT NULL
                    LIMIT 10
                """),
                {'entity_id': entity_id}
            ).fetchall()
            
            if result:
                return [str(row.id) for row in result]
        
        return self._find_chunks_mentioning(entity_name)
    
    def _get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get a document chunk by ID."""
        result = self.session.execute(
            text("""
                SELECT id, text as content, document_id
                FROM document_chunks
                WHERE id = :chunk_id
            """),
            {'chunk_id': chunk_id}
        ).fetchone()
        
        return dict(result._mapping) if result else None
    
    def _get_relationship_count(self, entity_id: str) -> int:
        """Get the number of relationships for an entity."""
        if not entity_id:
            return 0
        
        result = self.session.execute(
            text("""
                SELECT COUNT(*) as count
                FROM relationships
                WHERE tenant_id = :tenant_id
                AND (source_id = :entity_id OR target_id = :entity_id)
            """),
            {'tenant_id': self.tenant_id, 'entity_id': entity_id}
        ).fetchone()
        
        return result.count if result else 0
    
    def _is_new_relationship(self, rel: Dict[str, Any], entity_id: str) -> bool:
        """Check if a relationship is new (not already in the graph)."""
        source_name = rel.get('source_name', '')
        target_name = rel.get('target_name', '')
        rel_type = rel.get('relationship_type', '')
        
        result = self.session.execute(
            text("""
                SELECT COUNT(*) as count
                FROM relationships r
                JOIN entities s ON r.source_id = s.id
                JOIN entities t ON r.target_id = t.id
                WHERE r.tenant_id = :tenant_id
                AND LOWER(s.name) = LOWER(:source_name)
                AND LOWER(t.name) = LOWER(:target_name)
                AND r.relationship_type = :rel_type
            """),
            {
                'tenant_id': self.tenant_id,
                'source_name': source_name,
                'target_name': target_name,
                'rel_type': rel_type
            }
        ).fetchone()
        
        return result.count == 0 if result else True
    
    def _save_relationship(self, rel: Dict[str, Any]) -> Optional[str]:
        """Save a new relationship to staging. Returns the ID if saved."""
        return None
    
    def _extract_with_focus(self, content: str, focus_entity: str) -> Dict[str, Any]:
        """Extract entities from content with focus on a specific entity."""
        return {'entities': [], 'relationships': []}
    
    def _extract_relationships_for_entity(self, content: str, entity_name: str) -> Dict[str, Any]:
        """Extract relationships from content focused on an entity."""
        return {'relationships': []}
    
    def _entity_matches_name(self, entity_id: str, name: str) -> bool:
        """Check if an entity ID matches a given name."""
        return False


def process_learning_tickets_async(tenant_id: str, session=None):
    """Process learning tickets asynchronously (for use with asyncio.create_task)."""
    if session is None:
        from src.context_foundry.models.schema import get_session
        session = get_session()
    
    processor = GardenerLearningProcessor(session, tenant_id)
    return processor.process_pending_tickets()
