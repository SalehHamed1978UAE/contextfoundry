#!/usr/bin/env python3
"""Re-extract documents with full entity + relationship extraction using OntologyCentricPipeline."""

import sys
sys.path.insert(0, '/home/runner/workspace')

import os
import logging
from uuid import UUID
from datetime import datetime
from sqlalchemy import text

from src.context_foundry.models.schema import get_session, set_tenant_context, DocumentChunk
from src.context_foundry.extraction.ontology_centric_pipeline import OntologyCentricPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/reextract_graph.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

TENANT_ID = "7627d577-e07c-484f-893a-ed2f464d28b9"

def get_documents_needing_extraction(session):
    """Get documents that have chunks but no entities with source_chunk_id."""
    result = session.execute(text("""
        SELECT DISTINCT d.id, d.name, dc.cnt as chunk_count
        FROM platform.documents d
        JOIN (SELECT document_id, COUNT(*) as cnt FROM document_chunks WHERE tenant_id = :tid GROUP BY document_id) dc
            ON dc.document_id = d.id
        LEFT JOIN entities e ON e.source_document_id = d.id::text AND e.source_chunk_id IS NOT NULL AND e.tenant_id = d.tenant_id
        WHERE d.tenant_id = :tid
        AND e.id IS NULL
        ORDER BY d.name
    """), {"tid": TENANT_ID}).fetchall()
    return result

def get_document_text(session, document_id: str):
    """Get full document text by concatenating chunks."""
    chunks = session.execute(text("""
        SELECT text FROM document_chunks 
        WHERE document_id = :doc_id 
        ORDER BY chunk_index
    """), {"doc_id": document_id}).fetchall()
    
    if not chunks:
        return None
    
    return "\n\n".join(row[0] for row in chunks if row[0])

def main():
    logger.info("=" * 60)
    logger.info("Starting graph extraction with chunk provenance...")
    logger.info("=" * 60)
    
    session = get_session()
    set_tenant_context(session, TENANT_ID)
    
    docs = get_documents_needing_extraction(session)
    logger.info(f"Found {len(docs)} documents needing extraction")
    
    if not docs:
        logger.info("All documents already have graph entities with chunk provenance!")
        session.close()
        return
    
    total_entities = 0
    total_relations = 0
    
    for i, (doc_id, doc_name, chunk_count) in enumerate(docs):
        logger.info(f"\n[{i+1}/{len(docs)}] Processing: {doc_name} ({chunk_count} chunks)")
        
        text_content = get_document_text(session, str(doc_id))
        if not text_content or len(text_content) < 100:
            logger.warning(f"  Skipping - insufficient text content")
            continue
        
        try:
            pipeline = OntologyCentricPipeline(
                session=session,
                tenant_id=TENANT_ID,
                model="gpt-4o-mini",
                enable_canonicalization=True,
                auto_stage=True,
            )
            
            result = pipeline.extract(
                text=text_content,
                document_id=str(doc_id),
                filename=doc_name,
            )
            
            if result.success:
                entities_count = len(result.entities)
                relations_count = len(result.relations)
                total_entities += entities_count
                total_relations += relations_count
                logger.info(f"  Extracted: {entities_count} entities, {relations_count} relationships")
                
                if result.staging_result:
                    logger.info(f"  Staged: {result.staging_result.entities_created} entities, {result.staging_result.relations_created} relations")
            else:
                logger.error(f"  Extraction failed: {result.error}")
            
            session.commit()
            
        except Exception as e:
            logger.error(f"  Error: {e}")
            session.rollback()
    
    logger.info("\n" + "=" * 60)
    logger.info(f"COMPLETE: {total_entities} entities, {total_relations} relationships from {len(docs)} documents")
    logger.info("=" * 60)
    
    session.close()

if __name__ == "__main__":
    main()
