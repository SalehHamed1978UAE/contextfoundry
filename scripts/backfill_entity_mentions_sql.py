#!/usr/bin/env python3
"""
SQL-based entity_mentions backfill using PostgreSQL ILIKE for efficient matching.

Since source_document_id doesn't match existing documents, we use content-based
matching with SQL for efficiency.
"""

import argparse
import logging
import sys
from uuid import UUID

sys.path.insert(0, '.')

from sqlalchemy import text
from src.context_foundry.models.schema import get_session

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_sql_backfill(tenant_id: UUID, batch_size: int = 100):
    """Run backfill using SQL ILIKE matching - much faster than Python loops."""
    session = get_session()
    
    try:
        result = session.execute(text("""
            SELECT COUNT(*) FROM entities 
            WHERE tenant_id = :tid AND lifecycle_state = 'TRUSTED'
        """), {"tid": str(tenant_id)}).fetchone()
        total_entities = result[0]
        logger.info(f"Processing {total_entities} trusted entities")
        
        result = session.execute(text("""
            SELECT COUNT(*) FROM document_chunks
        """)).fetchone()
        total_chunks = result[0]
        logger.info(f"Matching against {total_chunks} chunks")
        
        offset = 0
        total_mentions = 0
        entities_covered = set()
        
        while True:
            entities = session.execute(text("""
                SELECT id, name FROM entities
                WHERE tenant_id = :tid AND lifecycle_state = 'TRUSTED'
                ORDER BY id
                LIMIT :limit OFFSET :offset
            """), {"tid": str(tenant_id), "limit": batch_size, "offset": offset}).fetchall()
            
            if not entities:
                break
            
            for entity_id, entity_name in entities:
                if len(entity_name) < 3:
                    continue
                
                safe_name = entity_name.replace('%', r'\%').replace('_', r'\_')
                
                matches = session.execute(text("""
                    SELECT dc.id as chunk_id, dc.document_id, dc.text
                    FROM document_chunks dc
                    WHERE dc.text ILIKE :pattern
                    LIMIT 50
                """), {"pattern": f"%{safe_name}%"}).fetchall()
                
                for chunk_id, document_id, chunk_text in matches:
                    import re
                    pattern = re.compile(re.escape(entity_name), re.IGNORECASE)
                    
                    for match in pattern.finditer(chunk_text or ''):
                        existing = session.execute(text("""
                            SELECT 1 FROM entity_mentions
                            WHERE entity_id = :eid AND chunk_id = :cid AND char_start = :cs
                            LIMIT 1
                        """), {"eid": str(entity_id), "cid": str(chunk_id), "cs": match.start()}).fetchone()
                        
                        if not existing:
                            session.execute(text("""
                                INSERT INTO entity_mentions 
                                (id, entity_id, document_id, chunk_id, tenant_id, mention_text, char_start, char_end, confidence, created_at)
                                VALUES (gen_random_uuid(), :eid, :did, :cid, :tid, :text, :cs, :ce, 1.0, NOW())
                            """), {
                                "eid": str(entity_id),
                                "did": str(document_id),
                                "cid": str(chunk_id),
                                "tid": str(tenant_id),
                                "text": match.group(),
                                "cs": match.start(),
                                "ce": match.end()
                            })
                            total_mentions += 1
                            entities_covered.add(entity_id)
                
                if total_mentions > 0 and total_mentions % 500 == 0:
                    session.commit()
                    logger.info(f"Progress: {offset + len(entities)}/{total_entities} entities, {total_mentions} mentions, {len(entities_covered)} entities covered")
            
            offset += batch_size
            session.commit()
            
            if offset % 500 == 0:
                logger.info(f"Progress: {offset}/{total_entities} entities checked, {total_mentions} mentions")
        
        session.commit()
        
        logger.info(f"Backfill complete: {total_mentions} mentions, {len(entities_covered)} entities covered")
        
        return {
            'mentions_created': total_mentions,
            'entities_covered': len(entities_covered),
            'entities_processed': total_entities
        }
        
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description='SQL-based entity mentions backfill')
    parser.add_argument('--tenant-id', type=str, required=True, help='Tenant ID')
    parser.add_argument('--batch-size', type=int, default=100, help='Entities per batch')
    
    args = parser.parse_args()
    tenant_id = UUID(args.tenant_id)
    
    result = run_sql_backfill(tenant_id, args.batch_size)
    
    print(f"\nBackfill Results:")
    print(f"  Mentions created: {result['mentions_created']}")
    print(f"  Entities covered: {result['entities_covered']}")
    print(f"  Entities processed: {result['entities_processed']}")


if __name__ == '__main__':
    main()
