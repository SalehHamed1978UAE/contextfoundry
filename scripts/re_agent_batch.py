#!/usr/bin/env python3
"""Relationship Inference Agent - Background batch processor with checkpointing."""

import sys
sys.path.insert(0, '/home/runner/workspace')

import logging
from uuid import UUID
from datetime import datetime
from sqlalchemy import text
from src.context_foundry.models.schema import get_session, Relationship, ProposedRelationship, Entity
from src.context_foundry.agents.relationship_inference import RelationshipInferenceAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/re_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

TENANT_ID = "f3dd3201-7225-4a55-9264-445f99d0eba3"
BATCH_SIZE = 10
AUTO_APPROVE_THRESHOLD = 0.85

def get_processed_entity_ids(session):
    """Get entity IDs that already have proposals (processed by RE Agent)."""
    result = session.execute(text("""
        SELECT DISTINCT source_entity_id 
        FROM proposed_relationships 
        WHERE tenant_id = :tid
        UNION
        SELECT DISTINCT target_entity_id 
        FROM proposed_relationships 
        WHERE tenant_id = :tid
    """), {"tid": TENANT_ID}).fetchall()
    return {row[0] for row in result}

def promote_auto_approved(session):
    """Promote AUTO_APPROVED proposals to relationships."""
    approved = session.query(ProposedRelationship).filter(
        ProposedRelationship.tenant_id == UUID(TENANT_ID),
        ProposedRelationship.status == 'AUTO_APPROVED'
    ).all()
    
    if not approved:
        return 0
    
    for pr in approved:
        rel = Relationship(
            tenant_id=UUID(TENANT_ID),
            source_id=pr.source_entity_id,
            target_id=pr.target_entity_id,
            relationship_type=pr.relationship_type,
            confidence=pr.confidence,
            lifecycle_state='TRUSTED',
            extracted_at=datetime.utcnow()
        )
        session.add(rel)
        pr.status = 'APPROVED'
    
    session.commit()
    return len(approved)

def approve_high_confidence_pending(session):
    """Auto-approve PENDING proposals with high confidence."""
    pending = session.query(ProposedRelationship).filter(
        ProposedRelationship.tenant_id == UUID(TENANT_ID),
        ProposedRelationship.status == 'PENDING',
        ProposedRelationship.confidence >= AUTO_APPROVE_THRESHOLD
    ).all()
    
    if not pending:
        return 0
    
    for pr in pending:
        rel = Relationship(
            tenant_id=UUID(TENANT_ID),
            source_id=pr.source_entity_id,
            target_id=pr.target_entity_id,
            relationship_type=pr.relationship_type,
            confidence=pr.confidence,
            lifecycle_state='TRUSTED',
            extracted_at=datetime.utcnow()
        )
        session.add(rel)
        pr.status = 'APPROVED'
    
    session.commit()
    return len(pending)

def get_density(session):
    """Calculate current relationship density."""
    result = session.execute(text("""
        SELECT 
            COUNT(DISTINCT e.id) as entities,
            COUNT(DISTINCT r.id) as relationships
        FROM entities e
        LEFT JOIN relationships r ON (e.id = r.source_id OR e.id = r.target_id) 
            AND r.lifecycle_state != 'ARCHIVED'
        WHERE e.tenant_id = :tid
          AND e.lifecycle_state = 'TRUSTED'
    """), {"tid": TENANT_ID}).fetchone()
    
    entities, relationships = result
    density = relationships / entities if entities > 0 else 0
    return entities, relationships, density

def main():
    logger.info("Starting RE Agent batch processor...")
    
    agent = RelationshipInferenceAgent(domain='GENERIC')
    
    with get_session() as session:
        processed_ids = get_processed_entity_ids(session)
        logger.info(f"Already processed: {len(processed_ids)} entities have proposals")
        
        all_entities = session.query(Entity).filter(
            Entity.tenant_id == UUID(TENANT_ID),
            Entity.lifecycle_state == 'TRUSTED'
        ).all()
        
        unprocessed = [e for e in all_entities if e.id not in processed_ids]
        
        total_all = len(all_entities)
        total_remaining = len(unprocessed)
        logger.info(f"Total TRUSTED: {total_all}, Unprocessed: {total_remaining}, Skipping: {total_all - total_remaining}")
        
        if total_remaining == 0:
            logger.info("All entities already processed!")
            entities, rels, density = get_density(session)
            logger.info(f"Final density: {density:.3f} ({rels} relationships / {entities} entities)")
            return
        
        stats = {"proposed": 0, "approved": 0, "batches": 0}
        
        for i in range(0, len(unprocessed), BATCH_SIZE):
            batch = unprocessed[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            
            try:
                logger.info(f"Processing batch {batch_num} ({len(batch)} entities)...")
                
                result = agent.run_inference(
                    tenant_id=UUID(TENANT_ID),
                    batch_size=len(batch)
                )
                
                stats["proposed"] += result.relationships_proposed
                stats["approved"] += result.relationships_approved
                stats["batches"] += 1
                
                promoted = promote_auto_approved(session)
                high_conf = approve_high_confidence_pending(session)
                
                entities, rels, density = get_density(session)
                
                processed_count = total_all - total_remaining + i + len(batch)
                logger.info(
                    f"Batch {batch_num}: +{result.relationships_proposed} proposed, "
                    f"+{promoted + high_conf} approved | "
                    f"Total: {rels} rels, density={density:.3f} | "
                    f"Progress: {processed_count}/{total_all} entities"
                )
                
                if density >= 1.0:
                    logger.info("TARGET DENSITY 1.0 REACHED!")
                    break
                    
            except Exception as e:
                logger.error(f"Batch {batch_num} error: {e}")
                continue
        
        final_entities, final_rels, final_density = get_density(session)
        logger.info(
            f"Complete! Batches: {stats['batches']}, "
            f"Proposed: {stats['proposed']}, Approved: {stats['approved']} | "
            f"Final: {final_rels} relationships, density={final_density:.3f}"
        )

if __name__ == "__main__":
    main()
