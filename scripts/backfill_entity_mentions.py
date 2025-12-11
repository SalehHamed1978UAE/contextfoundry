#!/usr/bin/env python3
"""
Backfill entity_mentions and document_chunks from existing extraction data.

This script creates the mention-level linkage between entities and document chunks
that the RelationshipInferenceAgent needs to find candidate entities in chunks.

Strategy:
1. For each document, create chunks based on content sections
2. For each entity with a source_document_id, search for mentions in those chunks
3. Create entity_mentions records linking entities to chunks

Usage:
    python scripts/backfill_entity_mentions.py [--tenant-id UUID] [--batch-size N]
"""

import argparse
import logging
import re
import sys
from datetime import datetime
from uuid import UUID

sys.path.insert(0, '.')

from sqlalchemy import text
from src.context_foundry.models.schema import (
    get_session, Entity, Document, DocumentChunk, EntityMention,
    LifecycleState
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """Split text into overlapping chunks."""
    if not text:
        return []
    
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        
        if end < text_len:
            break_point = text.rfind('.', start, end)
            if break_point > start + chunk_size // 2:
                end = break_point + 1
        
        chunks.append({
            'text': text[start:end],
            'char_start': start,
            'char_end': end
        })
        
        if end >= text_len:
            break
        start = end - overlap
    
    return chunks


def find_entity_mentions(entity_name: str, chunk_text: str) -> list:
    """Find all mentions of an entity name in chunk text."""
    mentions = []
    
    pattern = re.compile(re.escape(entity_name), re.IGNORECASE)
    
    for match in pattern.finditer(chunk_text):
        mentions.append({
            'mention_text': match.group(),
            'char_start': match.start(),
            'char_end': match.end()
        })
    
    return mentions


def backfill_chunks_for_document(session, document, tenant_id: UUID):
    """Create chunks for a single document."""
    existing = session.query(DocumentChunk).filter(
        DocumentChunk.document_id == document.id
    ).first()
    
    if existing:
        return session.query(DocumentChunk).filter(
            DocumentChunk.document_id == document.id
        ).order_by(DocumentChunk.chunk_index).all()
    
    if not document.content:
        return []
    
    text_chunks = chunk_text(document.content)
    chunk_objects = []
    
    for idx, chunk_data in enumerate(text_chunks):
        chunk = DocumentChunk(
            document_id=document.id,
            tenant_id=tenant_id,
            chunk_index=idx,
            text=chunk_data['text'],
            char_start=chunk_data['char_start'],
            char_end=chunk_data['char_end']
        )
        session.add(chunk)
        chunk_objects.append(chunk)
    
    return chunk_objects


def backfill_mentions_for_entity(session, entity, chunks: list, tenant_id: UUID) -> int:
    """Create mentions for an entity across chunks."""
    mentions_created = 0
    
    for chunk in chunks:
        mentions = find_entity_mentions(entity.name, chunk.text)
        
        for mention_data in mentions:
            existing = session.query(EntityMention).filter(
                EntityMention.entity_id == entity.id,
                EntityMention.chunk_id == chunk.id,
                EntityMention.char_start == mention_data['char_start']
            ).first()
            
            if existing:
                continue
            
            mention = EntityMention(
                entity_id=entity.id,
                document_id=chunk.document_id,
                chunk_id=chunk.id,
                tenant_id=tenant_id,
                mention_text=mention_data['mention_text'],
                char_start=mention_data['char_start'],
                char_end=mention_data['char_end'],
                confidence=1.0
            )
            session.add(mention)
            mentions_created += 1
    
    return mentions_created


def run_backfill(tenant_id: UUID = None, batch_size: int = 100, max_docs: int = None):
    """Run the backfill process using content-based entity matching."""
    session = get_session()
    
    try:
        result = session.execute(text(
            "SELECT DISTINCT tenant_id FROM entities WHERE tenant_id IS NOT NULL LIMIT 10"
        ))
        tenants = [UUID(str(row[0])) for row in result.fetchall()]
        
        if tenant_id:
            tenants = [t for t in tenants if t == tenant_id] or [tenant_id]
        
        total_chunks = 0
        total_mentions = 0
        
        for tid in tenants:
            logger.info(f"Processing tenant: {tid}")
            
            doc_query = session.query(Document)
            if max_docs:
                doc_query = doc_query.limit(max_docs)
            
            documents = doc_query.all()
            logger.info(f"Found {len(documents)} documents")
            
            entities = session.query(Entity).filter(
                Entity.tenant_id == tid,
                Entity.lifecycle_state == LifecycleState.TRUSTED
            ).all()
            
            logger.info(f"Found {len(entities)} TRUSTED entities for tenant")
            
            entity_names = {e.id: e.name for e in entities}
            
            for doc in documents:
                if not doc.content:
                    continue
                    
                chunks = backfill_chunks_for_document(session, doc, tid)
                if not chunks:
                    continue
                
                total_chunks += len(chunks)
                
                for entity in entities:
                    for chunk in chunks:
                        if entity.name.lower() in chunk.text.lower():
                            mentions = find_entity_mentions(entity.name, chunk.text)
                            for mention_data in mentions:
                                existing = session.query(EntityMention).filter(
                                    EntityMention.entity_id == entity.id,
                                    EntityMention.chunk_id == chunk.id,
                                    EntityMention.char_start == mention_data['char_start']
                                ).first()
                                
                                if existing:
                                    continue
                                
                                mention = EntityMention(
                                    entity_id=entity.id,
                                    document_id=doc.id,
                                    chunk_id=chunk.id,
                                    tenant_id=tid,
                                    mention_text=mention_data['mention_text'],
                                    char_start=mention_data['char_start'],
                                    char_end=mention_data['char_end'],
                                    confidence=1.0
                                )
                                session.add(mention)
                                total_mentions += 1
                
                if total_mentions > 0 and total_mentions % 100 == 0:
                    session.commit()
                    logger.info(f"Progress: {total_chunks} chunks, {total_mentions} mentions")
            
            session.commit()
        
        logger.info(f"Backfill complete: {total_chunks} chunks, {total_mentions} mentions")
        
        return {
            'chunks_created': total_chunks,
            'mentions_created': total_mentions,
            'tenants_processed': len(tenants)
        }
        
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description='Backfill entity mentions from extraction data')
    parser.add_argument('--tenant-id', type=str, help='Specific tenant ID to process')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for commits')
    parser.add_argument('--max-docs', type=int, help='Maximum documents to process (for testing)')
    
    args = parser.parse_args()
    
    tenant_id = UUID(args.tenant_id) if args.tenant_id else None
    
    result = run_backfill(
        tenant_id=tenant_id,
        batch_size=args.batch_size,
        max_docs=args.max_docs
    )
    
    print(f"\nBackfill Results:")
    print(f"  Chunks created: {result['chunks_created']}")
    print(f"  Mentions created: {result['mentions_created']}")
    print(f"  Tenants processed: {result['tenants_processed']}")


if __name__ == '__main__':
    main()
