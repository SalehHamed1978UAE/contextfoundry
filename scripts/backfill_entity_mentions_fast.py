#!/usr/bin/env python3
"""
Fast entity_mentions backfill using document-scoped entity matching.

Optimization: Only match entities to their source document's chunks.
This reduces O(entities × all_chunks) to O(entities × source_doc_chunks).
"""

import argparse
import logging
import re
import sys
from datetime import datetime
from uuid import UUID
from collections import defaultdict

sys.path.insert(0, '.')

from sqlalchemy import text
from sqlalchemy.orm import joinedload
from src.context_foundry.models.schema import (
    get_session, Entity, Document, DocumentChunk, EntityMention,
    LifecycleState
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def chunk_text(text_content: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """Split text into overlapping chunks."""
    if not text_content:
        return []
    
    chunks = []
    start = 0
    text_len = len(text_content)
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            break_point = text_content.rfind('.', start, end)
            if break_point > start + chunk_size // 2:
                end = break_point + 1
        
        chunks.append({
            'text': text_content[start:end],
            'char_start': start,
            'char_end': end
        })
        
        if end >= text_len:
            break
        start = end - overlap
    
    return chunks


def run_fast_backfill(tenant_id: UUID, batch_size: int = 500):
    """Run optimized backfill using document-scoped entity matching."""
    session = get_session()
    
    try:
        entities = session.query(Entity).filter(
            Entity.tenant_id == tenant_id,
            Entity.lifecycle_state == LifecycleState.TRUSTED,
            Entity.source_document_id.isnot(None)
        ).all()
        
        logger.info(f"Found {len(entities)} TRUSTED entities with source_document_id")
        
        entities_by_doc = defaultdict(list)
        for e in entities:
            entities_by_doc[e.source_document_id].append(e)
        
        logger.info(f"Entities distributed across {len(entities_by_doc)} documents")
        
        existing_chunks = session.execute(text(
            "SELECT DISTINCT document_id FROM document_chunks"
        )).fetchall()
        docs_with_chunks = {row[0] for row in existing_chunks}
        logger.info(f"Found {len(docs_with_chunks)} documents with existing chunks")
        
        total_mentions = 0
        docs_processed = 0
        mentions_batch = []
        
        for doc_id, doc_entities in entities_by_doc.items():
            chunks = session.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc_id
            ).all()
            
            if not chunks:
                doc = session.query(Document).filter(Document.id == doc_id).first()
                if doc and doc.content:
                    text_chunks = chunk_text(doc.content)
                    for idx, chunk_data in enumerate(text_chunks):
                        chunk = DocumentChunk(
                            document_id=doc_id,
                            tenant_id=tenant_id,
                            chunk_index=idx,
                            text=chunk_data['text'],
                            char_start=chunk_data['char_start'],
                            char_end=chunk_data['char_end']
                        )
                        session.add(chunk)
                        chunks.append(chunk)
                    if chunks:
                        session.flush()
            
            if not chunks:
                continue
            
            chunk_texts_lower = {c.id: c.text.lower() if c.text else '' for c in chunks}
            
            for entity in doc_entities:
                entity_name_lower = entity.name.lower()
                pattern = re.compile(re.escape(entity.name), re.IGNORECASE)
                
                for chunk in chunks:
                    chunk_text_lower = chunk_texts_lower.get(chunk.id, '')
                    if entity_name_lower not in chunk_text_lower:
                        continue
                    
                    for match in pattern.finditer(chunk.text or ''):
                        mentions_batch.append({
                            'entity_id': entity.id,
                            'document_id': doc_id,
                            'chunk_id': chunk.id,
                            'tenant_id': tenant_id,
                            'mention_text': match.group(),
                            'char_start': match.start(),
                            'char_end': match.end(),
                            'confidence': 1.0
                        })
                        total_mentions += 1
            
            docs_processed += 1
            
            if len(mentions_batch) >= batch_size:
                insert_mentions_batch(session, mentions_batch)
                mentions_batch = []
                logger.info(f"Progress: {docs_processed}/{len(entities_by_doc)} docs, {total_mentions} mentions")
        
        if mentions_batch:
            insert_mentions_batch(session, mentions_batch)
        
        session.commit()
        
        result = session.execute(text("""
            SELECT COUNT(DISTINCT entity_id) FROM entity_mentions WHERE tenant_id = :tid
        """), {"tid": str(tenant_id)}).fetchone()
        
        logger.info(f"Backfill complete: {total_mentions} mentions, {result[0]} unique entities covered")
        
        return {
            'mentions_created': total_mentions,
            'entities_covered': result[0],
            'docs_processed': docs_processed
        }
        
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def insert_mentions_batch(session, mentions: list):
    """Bulk insert mentions, skipping duplicates."""
    if not mentions:
        return
    
    for m in mentions:
        existing = session.query(EntityMention).filter(
            EntityMention.entity_id == m['entity_id'],
            EntityMention.chunk_id == m['chunk_id'],
            EntityMention.char_start == m['char_start']
        ).first()
        
        if not existing:
            mention = EntityMention(
                entity_id=m['entity_id'],
                document_id=m['document_id'],
                chunk_id=m['chunk_id'],
                tenant_id=m['tenant_id'],
                mention_text=m['mention_text'],
                char_start=m['char_start'],
                char_end=m['char_end'],
                confidence=m['confidence']
            )
            session.add(mention)
    
    session.commit()


def main():
    parser = argparse.ArgumentParser(description='Fast entity mentions backfill')
    parser.add_argument('--tenant-id', type=str, required=True, help='Tenant ID')
    parser.add_argument('--batch-size', type=int, default=500, help='Batch size')
    
    args = parser.parse_args()
    tenant_id = UUID(args.tenant_id)
    
    result = run_fast_backfill(tenant_id, args.batch_size)
    
    print(f"\nBackfill Results:")
    print(f"  Mentions created: {result['mentions_created']}")
    print(f"  Entities covered: {result['entities_covered']}")
    print(f"  Documents processed: {result['docs_processed']}")


if __name__ == '__main__':
    main()
