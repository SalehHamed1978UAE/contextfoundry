"""
Document Entity Mentions Indexer

Populates the doc_entity_mentions table during document ingestion.
Required for EXACT counts on "How many documents mention X?" queries.

Integration points:
1. Call index_document() after document chunking/entity extraction
2. Call reindex_entity() when entity resolution changes
3. Call remove_document() when document is deleted
4. Run backfill_all() once to populate existing documents

Without this, doc mention counts return LOWER_BOUND or INSUFFICIENT.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class EntityMention:
    """A mention of an entity in a document."""
    entity_id: UUID
    mention_count: int = 1
    contexts: List[str] = None  # Optional: snippet contexts


class DocEntityMentionsIndexer:
    """
    Indexes entity mentions in documents for EXACT aggregation counts.
    
    The doc_entity_mentions table enables queries like:
    - "How many documents mention Project Phoenix?"
    - "Which entities appear in the most documents?"
    
    Without this index, such queries can only return LOWER_BOUND
    (from retrieval, which is incomplete by definition).
    """
    
    def __init__(self, session: Session, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
    
    # =========================================================================
    # Core indexing operations
    # =========================================================================
    
    def index_document(
        self,
        doc_id: UUID,
        entity_mentions: List[EntityMention],
    ) -> int:
        """
        Index entity mentions for a document.
        
        Call this after document processing extracts entities.
        
        Args:
            doc_id: Document UUID
            entity_mentions: List of EntityMention objects
            
        Returns:
            Number of mention rows written
        """
        if not entity_mentions:
            return 0
        
        # Aggregate mentions by entity (in case of duplicates in input)
        aggregated: Dict[UUID, int] = {}
        for mention in entity_mentions:
            entity_id = mention.entity_id
            aggregated[entity_id] = aggregated.get(entity_id, 0) + mention.mention_count
        
        # Upsert mentions
        now = datetime.utcnow()
        rows_written = 0
        
        for entity_id, count in aggregated.items():
            self.session.execute(
                text("""
                    INSERT INTO doc_entity_mentions 
                        (tenant_id, doc_id, entity_id, mention_count, first_seen_at)
                    VALUES 
                        (:tenant_id, :doc_id, :entity_id, :count, :now)
                    ON CONFLICT (tenant_id, doc_id, entity_id) 
                    DO UPDATE SET 
                        mention_count = doc_entity_mentions.mention_count + :count
                """),
                {
                    "tenant_id": str(self.tenant_id),
                    "doc_id": str(doc_id),
                    "entity_id": str(entity_id),
                    "count": count,
                    "now": now,
                }
            )
            rows_written += 1
        
        logger.info(f"Indexed {rows_written} entity mentions for doc {doc_id}")
        return rows_written
    
    def remove_document(self, doc_id: UUID) -> int:
        """
        Remove all mention records for a document.
        
        Call this when a document is deleted.
        
        Returns:
            Number of rows deleted
        """
        result = self.session.execute(
            text("""
                DELETE FROM doc_entity_mentions
                WHERE tenant_id = :tenant_id AND doc_id = :doc_id
            """),
            {"tenant_id": str(self.tenant_id), "doc_id": str(doc_id)}
        )
        
        deleted = result.rowcount
        logger.info(f"Removed {deleted} mention records for doc {doc_id}")
        return deleted
    
    def reindex_document(
        self,
        doc_id: UUID,
        entity_mentions: List[EntityMention],
    ) -> int:
        """
        Reindex a document (delete + insert).
        
        Call this when document content changes.
        """
        self.remove_document(doc_id)
        return self.index_document(doc_id, entity_mentions)
    
    # =========================================================================
    # Entity resolution updates
    # =========================================================================
    
    def merge_entities(
        self,
        source_entity_id: UUID,
        target_entity_id: UUID,
    ) -> int:
        """
        Merge mentions from source entity into target entity.
        
        Call this when entity resolution merges two entities.
        The source entity's mentions are transferred to target.
        
        Returns:
            Number of rows affected
        """
        # Update mentions to point to target entity
        # Handle conflicts by summing counts
        result = self.session.execute(
            text("""
                WITH source_mentions AS (
                    DELETE FROM doc_entity_mentions
                    WHERE tenant_id = :tenant_id AND entity_id = :source_id
                    RETURNING doc_id, mention_count, first_seen_at
                )
                INSERT INTO doc_entity_mentions 
                    (tenant_id, doc_id, entity_id, mention_count, first_seen_at)
                SELECT 
                    :tenant_id,
                    doc_id,
                    :target_id,
                    mention_count,
                    first_seen_at
                FROM source_mentions
                ON CONFLICT (tenant_id, doc_id, entity_id)
                DO UPDATE SET
                    mention_count = doc_entity_mentions.mention_count + EXCLUDED.mention_count,
                    first_seen_at = LEAST(doc_entity_mentions.first_seen_at, EXCLUDED.first_seen_at)
            """),
            {
                "tenant_id": str(self.tenant_id),
                "source_id": str(source_entity_id),
                "target_id": str(target_entity_id),
            }
        )
        
        affected = result.rowcount
        logger.info(f"Merged entity {source_entity_id} -> {target_entity_id}: {affected} mentions")
        return affected
    
    # =========================================================================
    # Backfill for existing documents
    # =========================================================================
    
    def backfill_from_chunks(
        self,
        entity_extractor: callable,
        batch_size: int = 100,
    ) -> Dict[str, int]:
        """
        Backfill mentions index from existing document chunks.
        
        Args:
            entity_extractor: Function(chunk_text, chunk_metadata) -> List[UUID]
                              Returns entity IDs mentioned in chunk
            batch_size: Number of documents to process per batch
            
        Returns:
            Stats dict: {docs_processed, mentions_indexed, errors}
        """
        stats = {"docs_processed": 0, "mentions_indexed": 0, "errors": 0}
        
        # Get all documents with chunks
        docs = self.session.execute(
            text("""
                SELECT DISTINCT d.id as doc_id
                FROM documents d
                JOIN chunks c ON c.document_id = d.id
                WHERE d.tenant_id = :tenant_id
                ORDER BY d.id
            """),
            {"tenant_id": str(self.tenant_id)}
        ).fetchall()
        
        logger.info(f"Backfilling mentions for {len(docs)} documents")
        
        for doc_row in docs:
            doc_id = doc_row.doc_id
            
            try:
                # Get chunks for document
                chunks = self.session.execute(
                    text("""
                        SELECT id, content, metadata
                        FROM chunks
                        WHERE document_id = :doc_id
                    """),
                    {"doc_id": str(doc_id)}
                ).fetchall()
                
                # Extract entity mentions from chunks
                doc_mentions: Dict[UUID, int] = {}
                for chunk in chunks:
                    entity_ids = entity_extractor(chunk.content, chunk.metadata)
                    for eid in entity_ids:
                        doc_mentions[eid] = doc_mentions.get(eid, 0) + 1
                
                # Index mentions
                mentions = [
                    EntityMention(entity_id=eid, mention_count=count)
                    for eid, count in doc_mentions.items()
                ]
                indexed = self.index_document(doc_id, mentions)
                
                stats["docs_processed"] += 1
                stats["mentions_indexed"] += indexed
                
            except Exception as e:
                logger.error(f"Error backfilling doc {doc_id}: {e}")
                stats["errors"] += 1
        
        logger.info(f"Backfill complete: {stats}")
        return stats
    
    def backfill_from_entity_links(self) -> Dict[str, int]:
        """
        Backfill from existing chunk-entity link table.
        
        Use this if you already have chunk_entity_links or similar.
        """
        result = self.session.execute(
            text("""
                INSERT INTO doc_entity_mentions (tenant_id, doc_id, entity_id, mention_count, first_seen_at)
                SELECT 
                    c.tenant_id,
                    c.document_id,
                    cel.entity_id,
                    COUNT(*) as mention_count,
                    MIN(c.created_at) as first_seen_at
                FROM chunk_entity_links cel
                JOIN chunks c ON c.id = cel.chunk_id
                WHERE c.tenant_id = :tenant_id
                GROUP BY c.tenant_id, c.document_id, cel.entity_id
                ON CONFLICT (tenant_id, doc_id, entity_id)
                DO UPDATE SET
                    mention_count = EXCLUDED.mention_count
            """),
            {"tenant_id": str(self.tenant_id)}
        )
        
        return {"rows_upserted": result.rowcount}
    
    # =========================================================================
    # Maintenance
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics for this tenant."""
        result = self.session.execute(
            text("""
                SELECT 
                    COUNT(DISTINCT doc_id) as doc_count,
                    COUNT(DISTINCT entity_id) as entity_count,
                    COUNT(*) as total_mention_rows,
                    SUM(mention_count) as total_mentions
                FROM doc_entity_mentions
                WHERE tenant_id = :tenant_id
            """),
            {"tenant_id": str(self.tenant_id)}
        ).fetchone()
        
        return {
            "doc_count": result.doc_count or 0,
            "entity_count": result.entity_count or 0,
            "total_mention_rows": result.total_mention_rows or 0,
            "total_mentions": result.total_mentions or 0,
        }
    
    def cleanup_orphaned_mentions(self) -> int:
        """
        Remove mentions for deleted documents or entities.
        
        Run periodically as maintenance.
        """
        result = self.session.execute(
            text("""
                DELETE FROM doc_entity_mentions dem
                WHERE dem.tenant_id = :tenant_id
                AND (
                    NOT EXISTS (SELECT 1 FROM documents d WHERE d.id = dem.doc_id)
                    OR NOT EXISTS (SELECT 1 FROM entities e WHERE e.id = dem.entity_id)
                )
            """),
            {"tenant_id": str(self.tenant_id)}
        )
        
        deleted = result.rowcount
        if deleted:
            logger.info(f"Cleaned up {deleted} orphaned mention rows")
        return deleted


# =============================================================================
# Integration hook for document processing pipeline
# =============================================================================

def index_document_mentions(
    session: Session,
    tenant_id: UUID,
    doc_id: UUID,
    extracted_entities: List[Dict[str, Any]],
) -> int:
    """
    Convenience function to call from document processing pipeline.
    
    Args:
        session: SQLAlchemy session
        tenant_id: Tenant UUID
        doc_id: Document UUID
        extracted_entities: List of dicts with 'entity_id' key
        
    Returns:
        Number of mention rows written
        
    Usage in your ingestion pipeline:
        # After entity extraction
        entities = extract_entities(document)
        
        # Index for aggregation
        index_document_mentions(session, tenant_id, doc_id, entities)
    """
    indexer = DocEntityMentionsIndexer(session, tenant_id)
    
    mentions = [
        EntityMention(
            entity_id=e["entity_id"],
            mention_count=e.get("mention_count", 1),
        )
        for e in extracted_entities
        if e.get("entity_id")
    ]
    
    return indexer.index_document(doc_id, mentions)
