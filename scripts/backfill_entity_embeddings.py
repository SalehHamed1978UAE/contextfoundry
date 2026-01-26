#!/usr/bin/env python3
"""
Batch script to compute and store embeddings for all entities.

This backfills the name_embedding column for entities that don't have embeddings,
enabling semantic search in the entity resolver.

Usage:
    python scripts/backfill_entity_embeddings.py [--batch-size 100] [--tenant-id <id>]
"""

import argparse
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.context_foundry.models.schema import get_session
from src.context_foundry.memory.episodic import openai_embedding, EMBEDDING_DIM


def backfill_embeddings(batch_size: int = 100, tenant_id: str = None, dry_run: bool = False):
    """
    Backfill embeddings for all entities without name_embedding.
    
    Args:
        batch_size: Number of entities to process per batch
        tenant_id: Optional tenant ID to filter entities
        dry_run: If True, don't actually update the database
    """
    session = get_session()
    
    tenant_filter = ""
    if tenant_id:
        tenant_filter = f"AND tenant_id = '{tenant_id}'"
    
    count_query = text(f"""
        SELECT COUNT(*) FROM entities 
        WHERE name_embedding IS NULL {tenant_filter}
    """)
    total_count = session.execute(count_query).scalar()
    
    print(f"=== Entity Embedding Backfill ===")
    print(f"Total entities without embeddings: {total_count}")
    print(f"Batch size: {batch_size}")
    print(f"Embedding dimension: {EMBEDDING_DIM}")
    if dry_run:
        print("DRY RUN - no changes will be made")
    print()
    
    if total_count == 0:
        print("All entities already have embeddings!")
        return
    
    processed = 0
    errors = 0
    start_time = time.time()
    
    while processed < total_count:
        fetch_query = text(f"""
            SELECT id, name FROM entities 
            WHERE name_embedding IS NULL {tenant_filter}
            ORDER BY created_at
            LIMIT :batch_size
        """)
        
        batch = session.execute(fetch_query, {"batch_size": batch_size}).fetchall()
        
        if not batch:
            break
        
        for entity_id, name in batch:
            try:
                embedding = openai_embedding(name)
                
                if not dry_run:
                    update_query = text("""
                        UPDATE entities 
                        SET name_embedding = :embedding
                        WHERE id = :entity_id
                    """)
                    session.execute(update_query, {
                        "embedding": embedding,
                        "entity_id": entity_id
                    })
                
                processed += 1
                
                if processed % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed if elapsed > 0 else 0
                    eta = (total_count - processed) / rate if rate > 0 else 0
                    print(f"  Processed {processed}/{total_count} ({100*processed/total_count:.1f}%) - {rate:.1f}/sec - ETA: {eta:.0f}s")
                
            except Exception as e:
                errors += 1
                print(f"  ERROR: Entity {entity_id} ({name[:50]}...): {e}")
                if errors > 10:
                    print("Too many errors, stopping.")
                    break
        
        if not dry_run:
            session.commit()
        
        time.sleep(0.1)
    
    elapsed = time.time() - start_time
    print()
    print(f"=== Complete ===")
    print(f"Processed: {processed}")
    print(f"Errors: {errors}")
    print(f"Time: {elapsed:.1f}s")
    print(f"Rate: {processed/elapsed:.1f} entities/sec")
    
    verify_query = text(f"""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE name_embedding IS NOT NULL) as with_embedding
        FROM entities {('WHERE tenant_id = ' + repr(tenant_id)) if tenant_id else ''}
    """)
    result = session.execute(verify_query).fetchone()
    print()
    print(f"=== Verification ===")
    print(f"Total entities: {result[0]}")
    print(f"With embeddings: {result[1]}")
    print(f"Coverage: {100*result[1]/result[0] if result[0] > 0 else 0:.1f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill entity embeddings")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")
    parser.add_argument("--tenant-id", type=str, help="Optional tenant ID to filter")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually update DB")
    
    args = parser.parse_args()
    
    backfill_embeddings(
        batch_size=args.batch_size,
        tenant_id=args.tenant_id,
        dry_run=args.dry_run
    )
