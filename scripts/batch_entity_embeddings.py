#!/usr/bin/env python3
"""
Batch Entity Embedding Job

Computes OpenAI embeddings for all TRUSTED entities that don't have embeddings.
Runs in batches to handle large datasets and provides progress logging.
"""
import sys
import time
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context_foundry.agents.entity_resolver import compute_entity_embedding
from src.context_foundry.models.schema import Entity, LifecycleState, get_session

def main():
    session = get_session()
    
    total_trusted = session.query(Entity).filter(
        Entity.lifecycle_state == LifecycleState.TRUSTED
    ).count()
    
    missing = session.query(Entity).filter(
        Entity.lifecycle_state == LifecycleState.TRUSTED,
        Entity.name_embedding.is_(None)
    ).count()
    
    print(f"Total TRUSTED entities: {total_trusted}")
    print(f"Missing embeddings: {missing}")
    print(f"Already embedded: {total_trusted - missing}")
    print()
    
    if missing == 0:
        print("All entities already have embeddings!")
        return
    
    batch_size = 100
    processed = 0
    success = 0
    failed = 0
    start_time = time.time()
    
    print(f"Starting batch embedding job for {missing} entities (batch_size={batch_size})...")
    print("-" * 60)
    
    while processed < missing:
        entities = session.query(Entity).filter(
            Entity.lifecycle_state == LifecycleState.TRUSTED,
            Entity.name_embedding.is_(None)
        ).limit(batch_size).all()
        
        if not entities:
            break
        
        for entity in entities:
            try:
                embedding = compute_entity_embedding(entity)
                if embedding:
                    entity.name_embedding = embedding
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                print(f"  Error: {entity.name}: {e}")
            
            processed += 1
        
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Commit failed: {e}")
            break
        
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        eta = (missing - processed) / rate if rate > 0 else 0
        
        print(f"Progress: {processed}/{missing} ({100*processed/missing:.1f}%) | "
              f"Success: {success} | Failed: {failed} | "
              f"Rate: {rate:.1f}/s | ETA: {eta:.0f}s")
    
    elapsed = time.time() - start_time
    print("-" * 60)
    print(f"Complete! Processed: {processed} | Success: {success} | Failed: {failed}")
    print(f"Total time: {elapsed:.1f}s | Rate: {processed/elapsed:.1f}/s")
    
    with_embeddings = session.query(Entity).filter(
        Entity.lifecycle_state == LifecycleState.TRUSTED,
        Entity.name_embedding.isnot(None)
    ).count()
    print(f"Entities with embeddings: {with_embeddings}/{total_trusted}")


if __name__ == "__main__":
    main()
