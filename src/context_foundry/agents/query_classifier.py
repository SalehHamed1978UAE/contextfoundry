"""
Query Classifier and Data Sufficiency Checker

Implements the 4-LLM consensus Data Gates architecture to prevent hallucination:
- Classify queries by type (existence, relationship, impact, general)
- Check data sufficiency before routing to LLM
- Gate queries that lack sufficient data for safe answering
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def classify_query(query: str) -> str:
    """
    Classify query type for routing decisions.
    
    IMPORTANT: Check most specific patterns first (impact, relationship) 
    before generic patterns (existence) to avoid false positives.
    
    Returns one of: 'existence', 'relationship', 'impact', 'general'
    """
    query_lower = query.lower()
    
    impact_keywords = [
        'blast', 'radius', 'impact', 'affects', 'affected',
        'fail', 'fails', 'failure', 'outage',
        'cascade', 'cascading', 'downstream impact',
        'what happens if', 'what breaks',
        'go down', 'goes down', 'went down'
    ]
    if any(w in query_lower for w in impact_keywords):
        return 'impact'
    
    relationship_keywords = [
        'depend', 'depends on', 'dependency', 'dependencies',
        'owner', 'owns', 'owned by', 'who owns',
        'manages', 'managed by', 'manager',
        'connects', 'connected to', 'connection',
        'related', 'relationship', 'upstream', 'downstream',
        'talks to', 'calls', 'uses', 'used by',
        'reports to', 'escalate', 'escalation'
    ]
    if any(w in query_lower for w in relationship_keywords):
        return 'relationship'
    
    existence_keywords = ['exist', 'is there', 'do we have', 'do you know']
    if any(w in query_lower for w in existence_keywords):
        return 'existence'
    
    return 'general'


def get_data_sufficiency(session: Session, entity_id: str) -> dict:
    """
    Check if entity has enough data for different query types.
    
    Uses raw SQL for efficiency - this is called on every query.
    
    Returns:
        {
            'level': 'empty' | 'sparse' | 'adequate' | 'rich',
            'relationship_count': int,
            'outgoing_count': int,
            'incoming_count': int,
            'can_answer_relationship': bool,
            'can_answer_impact': bool
        }
    """
    result = session.execute(text("""
        SELECT 
            COUNT(*) FILTER (WHERE source_id = :entity_id) as outgoing,
            COUNT(*) FILTER (WHERE target_id = :entity_id) as incoming
        FROM relationships
        WHERE lifecycle_state = 'TRUSTED'
          AND (source_id = :entity_id OR target_id = :entity_id)
    """), {'entity_id': entity_id}).fetchone()
    
    outgoing = result[0] if result else 0
    incoming = result[1] if result else 0
    rel_count = outgoing + incoming
    
    if rel_count == 0:
        level = 'empty'
    elif rel_count < 3:
        level = 'sparse'
    elif rel_count < 6:
        level = 'adequate'
    else:
        level = 'rich'
    
    return {
        'level': level,
        'relationship_count': rel_count,
        'outgoing_count': outgoing,
        'incoming_count': incoming,
        'can_answer_relationship': rel_count > 0,
        'can_answer_impact': rel_count >= 2
    }


def format_no_relationships_response(entity_name: str, query_type: str, entity_type: Optional[str] = None) -> str:
    """
    Format response for entities with no documented relationships.
    This is a GROUNDED response - we are certain about the data gap.
    """
    type_info = f" (type: {entity_type})" if entity_type else ""
    base = f"Entity '{entity_name}'{type_info} exists in the knowledge graph."
    
    if query_type == 'impact':
        return (
            f"{base}\n\n"
            f"GROUNDED:\n"
            f"- Entity exists in the knowledge graph\n\n"
            f"GAPS:\n"
            f"- No dependency relationships documented for this entity\n"
            f"- Cannot assess blast radius or downstream impact without relationship data\n"
            f"- Impact of a failure would be limited to the entity itself based on current documentation"
        )
    elif query_type == 'relationship':
        return (
            f"{base}\n\n"
            f"GROUNDED:\n"
            f"- Entity exists in the knowledge graph\n\n"
            f"GAPS:\n"
            f"- No dependency relationships documented\n"
            f"- No ownership information documented\n"
            f"- No connection data available"
        )
    else:
        return (
            f"{base}\n\n"
            f"GROUNDED:\n"
            f"- Entity exists in the knowledge graph\n\n"
            f"GAPS:\n"
            f"- No relationship data available for this entity"
        )


def format_sparse_response(entity_name: str, entity_type: str, relationships: list, sufficiency: dict) -> str:
    """
    Format response for entities with sparse data (1-2 relationships).
    Uses simple formatting, not full LLM reasoning.
    """
    response = f"Entity '{entity_name}' (type: {entity_type}) has limited documentation.\n\n"
    response += "GROUNDED:\n"
    response += f"- Entity exists in the knowledge graph\n"
    
    if relationships:
        for rel in relationships:
            source_name = rel.get('source_name', 'Unknown')
            target_name = rel.get('target_name', 'Unknown')
            rel_type = rel.get('relationship_type', 'RELATED_TO')
            rel_id = rel.get('id', 'N/A')
            response += f"- {source_name} {rel_type} {target_name} [REL-{rel_id}]\n"
    
    response += f"\nGAPS:\n"
    response += f"- Only {sufficiency['relationship_count']} relationship(s) documented\n"
    response += f"- Additional relationships may exist but are not in the knowledge graph\n"
    
    if sufficiency['outgoing_count'] == 0:
        response += f"- No outgoing dependencies documented\n"
    if sufficiency['incoming_count'] == 0:
        response += f"- No incoming dependencies documented\n"
    
    return response


def should_gate_query(query_type: str, sufficiency: dict) -> tuple[bool, str]:
    """
    Determine if query should be gated (answered without LLM).
    
    Returns:
        (should_gate: bool, gate_reason: str)
    """
    if query_type in ['relationship', 'impact']:
        if sufficiency['relationship_count'] == 0:
            return True, 'no_relationships'
        if query_type == 'impact' and sufficiency['relationship_count'] < 2:
            return True, 'insufficient_for_impact'
    
    if sufficiency['level'] == 'sparse':
        return True, 'sparse_data'
    
    return False, ''
