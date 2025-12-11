#!/usr/bin/env python3
"""Full re-extraction of all chunks with EntityMention creation."""

import sys
sys.path.insert(0, '/home/runner/workspace')

import logging
from uuid import UUID
from datetime import datetime
from src.context_foundry.models.schema import get_session, DocumentChunk
from src.context_foundry.extraction.entity_extractor import EntityExtractor
from src.context_foundry.extraction.staging_loader import StagingLoader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/reextraction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

TENANT_ID = "f3dd3201-7225-4a55-9264-445f99d0eba3"

def main():
    logger.info("Starting full re-extraction...")
    
    extractor = EntityExtractor(model="gpt-4o-mini", temperature=0.0)
    
    with get_session() as session:
        chunks = session.query(DocumentChunk).filter(
            DocumentChunk.tenant_id == UUID(TENANT_ID)
        ).order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).all()
        
        total_chunks = len(chunks)
        logger.info(f"Processing {total_chunks} chunks...")
        
        loader = StagingLoader(session, tenant_id=TENANT_ID)
        
        stats = {"entities": 0, "mentions": 0, "errors": 0}
        
        for i, chunk in enumerate(chunks):
            try:
                entities = extractor.extract_from_text(
                    text=chunk.text,
                    document_id=str(chunk.document_id),
                    chunk_id=str(chunk.id),
                    sentence_idx=chunk.chunk_index,
                )
                
                for entity in entities:
                    ent, action = loader.load_entity(entity)
                    if action == "created":
                        stats["entities"] += 1
                        stats["mentions"] += 1
                    elif action == "updated":
                        stats["mentions"] += 1
                
                if (i + 1) % 25 == 0:
                    session.commit()
                    logger.info(f"Progress: {i+1}/{total_chunks} chunks | Entities: {stats['entities']} | Mentions: {stats['mentions']}")
                    
            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Chunk {chunk.id}: {e}")
                if stats["errors"] > 50:
                    logger.error("Too many errors, stopping")
                    break
        
        session.commit()
        logger.info(f"Complete! Entities: {stats['entities']}, Mentions: {stats['mentions']}, Errors: {stats['errors']}")

if __name__ == "__main__":
    main()
