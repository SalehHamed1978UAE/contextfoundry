"""
Temporal Query Functions for Stage 2: Context-Attached Knowledge

Provides ability to query relationships by time and get relationship timelines.
"""
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..utils.logger import logger


def get_relationships_at_time(
    session: Session,
    tenant_id: str,
    entity_id: str,
    at_time: datetime,
    relationship_type: str = None,
    direction: str = "both"
) -> List[Dict]:
    """
    Get relationships that were active at a specific time.
    
    Args:
        session: Database session
        tenant_id: Tenant ID for RLS
        entity_id: Entity to query relationships for
        at_time: Point in time to query
        relationship_type: Optional filter by relationship type
        direction: 'outgoing', 'incoming', or 'both'
    
    Returns:
        List of relationships that were active at the specified time
    """
    results = []
    
    base_query = """
        SELECT 
            r.id,
            r.relationship_type,
            r.valid_from,
            r.valid_to,
            r.provenance_text,
            r.event_context,
            r.qualifiers,
            r.confidence,
            r.source_sentence,
            :direction as direction,
            e.id as other_id,
            e.name as other_name,
            e.entity_type as other_type
        FROM relationships r
        JOIN entities e ON e.id = r.{other_col}
        WHERE r.tenant_id = :tenant_id
        AND r.{this_col} = :entity_id
        AND r.lifecycle_state = 'TRUSTED'
        AND (r.valid_from IS NULL OR r.valid_from <= :at_time)
        AND (r.valid_to IS NULL OR r.valid_to >= :at_time)
    """
    
    if direction in ["outgoing", "both"]:
        query = base_query.format(other_col="target_id", this_col="source_id")
        if relationship_type:
            query += " AND r.relationship_type = :rel_type"
        
        params = {
            "tenant_id": tenant_id,
            "entity_id": entity_id,
            "at_time": at_time,
            "direction": "outgoing"
        }
        if relationship_type:
            params["rel_type"] = relationship_type.upper()
        
        rows = session.execute(text(query), params).fetchall()
        results.extend([_row_to_dict(row) for row in rows])
    
    if direction in ["incoming", "both"]:
        query = base_query.format(other_col="source_id", this_col="target_id")
        if relationship_type:
            query += " AND r.relationship_type = :rel_type"
        
        params = {
            "tenant_id": tenant_id,
            "entity_id": entity_id,
            "at_time": at_time,
            "direction": "incoming"
        }
        if relationship_type:
            params["rel_type"] = relationship_type.upper()
        
        rows = session.execute(text(query), params).fetchall()
        results.extend([_row_to_dict(row) for row in rows])
    
    logger.debug(f"get_relationships_at_time: {len(results)} relationships at {at_time}")
    return results


def get_relationship_timeline(
    session: Session,
    tenant_id: str,
    entity_id: str,
    relationship_type: str = None,
    direction: str = "both"
) -> List[Dict]:
    """
    Get chronological timeline of relationships for an entity.
    
    Args:
        session: Database session
        tenant_id: Tenant ID for RLS
        entity_id: Entity to query timeline for
        relationship_type: Optional filter by relationship type
        direction: 'outgoing', 'incoming', or 'both'
    
    Returns:
        List of relationships ordered by valid_from date
    """
    results = []
    
    base_query = """
        SELECT 
            r.id,
            r.relationship_type,
            r.valid_from,
            r.valid_to,
            r.provenance_text,
            r.event_context,
            r.qualifiers,
            r.confidence,
            r.source_sentence,
            :direction as direction,
            e.id as other_id,
            e.name as other_name,
            e.entity_type as other_type
        FROM relationships r
        JOIN entities e ON e.id = r.{other_col}
        WHERE r.tenant_id = :tenant_id
        AND r.{this_col} = :entity_id
        AND r.lifecycle_state = 'TRUSTED'
    """
    
    if direction in ["outgoing", "both"]:
        query = base_query.format(other_col="target_id", this_col="source_id")
        if relationship_type:
            query += " AND r.relationship_type = :rel_type"
        query += " ORDER BY COALESCE(r.valid_from, '1900-01-01') ASC"
        
        params = {
            "tenant_id": tenant_id,
            "entity_id": entity_id,
            "direction": "outgoing"
        }
        if relationship_type:
            params["rel_type"] = relationship_type.upper()
        
        rows = session.execute(text(query), params).fetchall()
        results.extend([_row_to_dict(row) for row in rows])
    
    if direction in ["incoming", "both"]:
        query = base_query.format(other_col="source_id", this_col="target_id")
        if relationship_type:
            query += " AND r.relationship_type = :rel_type"
        query += " ORDER BY COALESCE(r.valid_from, '1900-01-01') ASC"
        
        params = {
            "tenant_id": tenant_id,
            "entity_id": entity_id,
            "direction": "incoming"
        }
        if relationship_type:
            params["rel_type"] = relationship_type.upper()
        
        rows = session.execute(text(query), params).fetchall()
        results.extend([_row_to_dict(row) for row in rows])
    
    results.sort(key=lambda x: x.get("valid_from") or "1900-01-01")
    
    logger.debug(f"get_relationship_timeline: {len(results)} relationships")
    return results


def get_entity_history(
    session: Session,
    tenant_id: str,
    entity_name: str,
    relationship_types: List[str] = None
) -> Dict:
    """
    Get complete history of an entity including all relationship changes over time.
    
    Args:
        session: Database session
        tenant_id: Tenant ID for RLS
        entity_name: Name of the entity to get history for
        relationship_types: Optional list of relationship types to include
    
    Returns:
        Dictionary with entity info and chronological relationship history
    """
    from sqlalchemy import func
    from ..models.schema import Entity
    
    entity = session.query(Entity).filter(
        func.lower(Entity.name) == func.lower(entity_name),
        Entity.tenant_id == tenant_id
    ).first()
    
    if not entity:
        return {"error": f"Entity '{entity_name}' not found"}
    
    timeline = get_relationship_timeline(
        session=session,
        tenant_id=tenant_id,
        entity_id=str(entity.id),
        direction="both"
    )
    
    if relationship_types:
        timeline = [
            r for r in timeline 
            if r.get("relationship_type") in [t.upper() for t in relationship_types]
        ]
    
    return {
        "entity": {
            "id": str(entity.id),
            "name": entity.name,
            "type": entity.entity_type
        },
        "relationship_count": len(timeline),
        "timeline": timeline
    }


def _row_to_dict(row) -> Dict:
    """Convert a database row to a dictionary."""
    return {
        "id": str(row.id) if row.id else None,
        "relationship_type": row.relationship_type,
        "valid_from": row.valid_from.isoformat() if row.valid_from else None,
        "valid_to": row.valid_to.isoformat() if row.valid_to else None,
        "provenance_text": row.provenance_text,
        "event_context": row.event_context,
        "qualifiers": row.qualifiers,
        "confidence": row.confidence,
        "source_sentence": row.source_sentence,
        "direction": row.direction,
        "other_entity": {
            "id": str(row.other_id) if row.other_id else None,
            "name": row.other_name,
            "type": row.other_type
        }
    }
