"""
Learning Ticket Agent for Stage 3: Learning from Interaction

Creates and manages learning tickets from query gaps.
Tickets don't modify the World Model directly - they create async work for the Gardener.

Priority Formula (explicit):
    priority = base_severity * (1 + 0.2 * hit_count)
    
Where:
    - base_severity: 0.8 for missing_entity, 0.6 for sparse_relationships, 0.5 for stale_data
    - hit_count: number of queries that have hit this gap
    - Capped at 1.0
"""

import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from rich import print as rprint

from ..shared.tenant_context import ensure_tenant_context


BASE_SEVERITY = {
    'missing_entity': 0.8,
    'sparse_relationships': 0.6,
    'stale_data': 0.5,
    'low_confidence': 0.5,
    'source_conflict': 0.7
}


class LearningTicketAgent:
    """Creates and manages learning tickets from query gaps."""
    
    def __init__(self, session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    def create_tickets_from_gaps(
        self,
        gaps: List[Dict[str, Any]],
        query_id: str = None,
        source_chunk_ids: List[str] = None
    ) -> List[str]:
        """
        Create learning tickets for detected gaps.
        
        Uses proper transaction handling - all tickets are created atomically.
        If any ticket creation fails, all changes are rolled back.
        
        Args:
            gaps: List of gap dictionaries from SufficiencySignals.gaps_detected
            query_id: Optional ID of the query that detected these gaps
            source_chunk_ids: Optional list of document chunk IDs that might help
            
        Returns:
            List of ticket IDs (new or existing)
            
        Raises:
            Exception: If any ticket creation fails (all changes rolled back)
        """
        for gap in gaps:
            if not gap.get('type'):
                raise ValueError(f"Gap missing required 'type' field: {gap}")
        
        ensure_tenant_context(self.session, self.tenant_id)
        
        ticket_ids = []
        
        try:
            for gap in gaps:
                existing = self._find_similar_ticket(gap)
                
                if existing:
                    self._increment_ticket_priority(existing['id'], existing['hit_count'])
                    ticket_ids.append(existing['id'])
                else:
                    ticket_id = self._create_ticket(gap, query_id, source_chunk_ids)
                    ticket_ids.append(ticket_id)
            
            self.session.commit()
            return ticket_ids
        except Exception:
            self.session.rollback()
            raise
    
    def _find_similar_ticket(self, gap: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find an existing pending ticket for the same gap."""
        entity_id = gap.get('entity_id')
        entity_name = gap.get('entity_name')
        
        if entity_id:
            result = self.session.execute(
                text("""
                    SELECT id, hit_count, priority 
                    FROM learning_tickets
                    WHERE tenant_id = :tenant_id
                    AND gap_type = :gap_type
                    AND status = 'pending'
                    AND focal_entity_id = :entity_id
                    LIMIT 1
                """),
                {
                    'tenant_id': self.tenant_id,
                    'gap_type': gap['type'],
                    'entity_id': entity_id
                }
            ).fetchone()
        elif entity_name:
            result = self.session.execute(
                text("""
                    SELECT id, hit_count, priority 
                    FROM learning_tickets
                    WHERE tenant_id = :tenant_id
                    AND gap_type = :gap_type
                    AND status = 'pending'
                    AND LOWER(focal_entity_name) = LOWER(:entity_name)
                    AND focal_entity_id IS NULL
                    LIMIT 1
                """),
                {
                    'tenant_id': self.tenant_id,
                    'gap_type': gap['type'],
                    'entity_name': entity_name
                }
            ).fetchone()
        else:
            result = self.session.execute(
                text("""
                    SELECT id, hit_count, priority 
                    FROM learning_tickets
                    WHERE tenant_id = :tenant_id
                    AND gap_type = :gap_type
                    AND status = 'pending'
                    AND focal_entity_id IS NULL
                    AND focal_entity_name IS NULL
                    LIMIT 1
                """),
                {
                    'tenant_id': self.tenant_id,
                    'gap_type': gap['type']
                }
            ).fetchone()
        
        return dict(result._mapping) if result else None
    
    def _calculate_priority(self, base_severity: float, hit_count: int) -> float:
        """
        Calculate priority using explicit formula:
        priority = base_severity * (1 + 0.2 * hit_count), capped at 1.0
        """
        priority = base_severity * (1 + 0.2 * hit_count)
        return min(1.0, priority)
    
    def _increment_ticket_priority(self, ticket_id: str, current_hit_count: int, commit: bool = False):
        """Increment hit count and update priority using explicit formula."""
        new_hit_count = current_hit_count + 1
        
        result = self.session.execute(
            text("""
                SELECT context->>'severity' as severity
                FROM learning_tickets
                WHERE id = :ticket_id
            """),
            {'ticket_id': ticket_id}
        ).fetchone()
        
        base_severity = float(result.severity) if result and result.severity else 0.5
        new_priority = self._calculate_priority(base_severity, new_hit_count)
        
        self.session.execute(
            text("""
                UPDATE learning_tickets
                SET hit_count = :hit_count,
                    priority = :priority,
                    updated_at = NOW()
                WHERE id = :ticket_id
            """),
            {
                'ticket_id': ticket_id,
                'hit_count': new_hit_count,
                'priority': new_priority
            }
        )
        if commit:
            self.session.commit()
    
    def _create_ticket(
        self,
        gap: Dict[str, Any],
        query_id: str = None,
        source_chunk_ids: List[str] = None,
        commit: bool = False
    ) -> str:
        """Create a new learning ticket."""
        ensure_tenant_context(self.session, self.tenant_id)
        ticket_id = str(uuid.uuid4())
        
        gap_type = gap.get('type', 'unknown')
        base_severity = gap.get('severity', BASE_SEVERITY.get(gap_type, 0.5))
        priority = self._calculate_priority(base_severity, 1)
        
        context = {
            **gap,
            'severity': base_severity
        }
        
        entity_id = gap.get('entity_id')
        if entity_id and isinstance(entity_id, str):
            try:
                uuid.UUID(entity_id)
            except ValueError:
                entity_id = None
        
        self.session.execute(
            text("""
                INSERT INTO learning_tickets (
                    id, tenant_id, query_id, gap_type,
                    focal_entity_id, focal_entity_name, relationship_type,
                    context, source_chunk_ids, priority, hit_count, status
                ) VALUES (
                    :id, :tenant_id, :query_id, :gap_type,
                    :entity_id, :entity_name, :rel_type,
                    :context, :source_ids, :priority, 1, 'pending'
                )
            """),
            {
                'id': ticket_id,
                'tenant_id': self.tenant_id,
                'query_id': query_id,
                'gap_type': gap_type,
                'entity_id': entity_id,
                'entity_name': gap.get('entity_name'),
                'rel_type': gap.get('relationship_type'),
                'context': json.dumps(context),
                'source_ids': source_chunk_ids,
                'priority': priority
            }
        )
        if commit:
            self.session.commit()
        
        return ticket_id
    
    def get_pending_tickets(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending tickets ordered by priority."""
        ensure_tenant_context(self.session, self.tenant_id)
        
        result = self.session.execute(
            text("""
                SELECT id, gap_type, focal_entity_id, focal_entity_name,
                       relationship_type, context, source_chunk_ids,
                       priority, hit_count, status, created_at, updated_at
                FROM learning_tickets
                WHERE tenant_id = :tenant_id
                AND status = 'pending'
                ORDER BY (priority * hit_count) DESC
                LIMIT :limit
            """),
            {'tenant_id': self.tenant_id, 'limit': limit}
        ).fetchall()
        
        return [dict(row._mapping) for row in result]
    
    def get_ticket_stats(self) -> Dict[str, Any]:
        """Get statistics about learning tickets."""
        ensure_tenant_context(self.session, self.tenant_id)
        
        result = self.session.execute(
            text("""
                SELECT 
                    status,
                    COUNT(*) as count,
                    AVG(hit_count) as avg_hits,
                    AVG(priority) as avg_priority
                FROM learning_tickets
                WHERE tenant_id = :tenant_id
                GROUP BY status
            """),
            {'tenant_id': self.tenant_id}
        ).fetchall()
        
        stats = {
            'by_status': {row.status: {'count': row.count, 'avg_hits': float(row.avg_hits or 0), 'avg_priority': float(row.avg_priority or 0)} for row in result},
            'total': sum(row.count for row in result)
        }
        
        return stats
