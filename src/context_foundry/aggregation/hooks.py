"""
Aggregation Framework Integration Hooks

Wire these into your existing pipelines:

1. Document ingestion → index_document_mentions()
2. Entity resolution merge → update_dedup_hints()
3. Startup → seed_definitions()
"""

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy.orm import Session


# =============================================================================
# Hook 1: Document Ingestion Pipeline
# =============================================================================

def on_document_processed(
    session: Session,
    tenant_id: UUID,
    doc_id: UUID,
    extracted_entities: List[Dict[str, Any]],
):
    """
    Call this after document processing extracts entities.
    
    Wire into your document ingestion pipeline, e.g.:
    
        # In your document processor
        def process_document(doc):
            chunks = chunk_document(doc)
            entities = extract_entities(chunks)
            
            # ... save chunks and entities ...
            
            # NEW: Index for aggregation
            on_document_processed(session, tenant_id, doc.id, entities)
    """
    from .mentions_indexer import index_document_mentions
    
    return index_document_mentions(session, tenant_id, doc_id, extracted_entities)


def on_document_deleted(
    session: Session,
    tenant_id: UUID,
    doc_id: UUID,
):
    """
    Call this when a document is deleted.
    
    Removes mention records to keep index accurate.
    """
    from .mentions_indexer import DocEntityMentionsIndexer
    
    indexer = DocEntityMentionsIndexer(session, tenant_id)
    return indexer.remove_document(doc_id)


# =============================================================================
# Hook 2: Entity Resolution Pipeline
# =============================================================================

def on_entities_merged(
    session: Session,
    tenant_id: UUID,
    source_entity_id: UUID,
    target_entity_id: UUID,
    similarity_score: float = 1.0,
):
    """
    Call this when entity resolution merges two entities.
    
    Updates:
    1. doc_entity_mentions (transfers mentions to target)
    2. entity_dedup_hints (records the merge decision)
    """
    from sqlalchemy import text
    from .mentions_indexer import DocEntityMentionsIndexer
    
    # Update mentions
    indexer = DocEntityMentionsIndexer(session, tenant_id)
    indexer.merge_entities(source_entity_id, target_entity_id)
    
    # Record dedup hint
    # Ensure canonical ordering (entity1_id < entity2_id)
    e1, e2 = sorted([source_entity_id, target_entity_id])
    
    session.execute(
        text("""
            INSERT INTO entity_dedup_hints 
                (tenant_id, entity1_id, entity2_id, similarity_score, decision, decided_by)
            VALUES 
                (:tenant_id, :e1, :e2, :score, 'merge', 'auto')
            ON CONFLICT (tenant_id, entity1_id, entity2_id)
            DO UPDATE SET
                decision = 'merge',
                similarity_score = :score,
                decided_at = now()
        """),
        {
            "tenant_id": str(tenant_id),
            "e1": str(e1),
            "e2": str(e2),
            "score": similarity_score,
        }
    )


def record_dedup_hint(
    session: Session,
    tenant_id: UUID,
    entity1_id: UUID,
    entity2_id: UUID,
    similarity_score: float,
    decision: str,  # 'merge', 'keep_separate', 'uncertain'
    decided_by: str = 'auto',
):
    """
    Record an entity deduplication hint.
    
    Call this when your entity resolution system makes a decision
    (or surfaces uncertainty for human review).
    """
    from sqlalchemy import text
    
    # Ensure canonical ordering
    e1, e2 = sorted([entity1_id, entity2_id])
    
    session.execute(
        text("""
            INSERT INTO entity_dedup_hints 
                (tenant_id, entity1_id, entity2_id, similarity_score, decision, decided_by)
            VALUES 
                (:tenant_id, :e1, :e2, :score, :decision, :decided_by)
            ON CONFLICT (tenant_id, entity1_id, entity2_id)
            DO UPDATE SET
                similarity_score = :score,
                decision = :decision,
                decided_by = :decided_by,
                decided_at = now()
        """),
        {
            "tenant_id": str(tenant_id),
            "e1": str(e1),
            "e2": str(e2),
            "score": similarity_score,
            "decision": decision,
            "decided_by": decided_by,
        }
    )


# =============================================================================
# Hook 3: Application Startup
# =============================================================================

def on_app_startup(
    session: Session,
    tenant_id: UUID,
    seed_definitions: bool = True,
):
    """
    Call this during application startup.
    
    Seeds aggregation definitions if not already present.
    """
    if seed_definitions:
        from .seed_definitions import seed_all_definitions
        seed_all_definitions(session, tenant_id)


# =============================================================================
# Hook 4: Sufficiency Gate Enhancement
# =============================================================================

def get_dedup_penalty(
    session: Session,
    tenant_id: UUID,
    entity_ids: List[UUID],
) -> float:
    """
    Get entity resolution penalty for sufficiency calculation.
    
    Returns a penalty value (0.0 to 1.0) based on uncertain dedup hints.
    Used by SufficiencyGate to penalize confidence.
    """
    from sqlalchemy import text
    
    if not entity_ids:
        return 0.0
    
    result = session.execute(
        text("""
            SELECT get_ambiguous_merge_rate(:tenant_id, :entity_ids) as rate
        """),
        {
            "tenant_id": str(tenant_id),
            "entity_ids": [str(e) for e in entity_ids],
        }
    ).fetchone()
    
    return float(result.rate) if result and result.rate else 0.0
