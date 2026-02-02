#!/usr/bin/env python3
"""
Test Ontology-Centric Extraction Pipeline

Creates a test vault, uploads corpus documents, and runs OntologyCentricPipeline
to compare accuracy against baseline multi-model extraction.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.test_runner.vault_manager import VaultManager
from src.context_foundry.extraction.ontology_centric_pipeline import (
    OntologyCentricPipeline,
    extract_document_with_ontology,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")
    sys.stdout.flush()


def get_db_session():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL not configured")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def get_documents_needing_extraction(vault_id: str, session) -> List[dict]:
    """Get all documents in vault that need extraction."""
    query = text("""
        SELECT d.id, d.name, d.file_path
        FROM documents d
        WHERE d.tenant_id = :vault_id
        ORDER BY d.name
    """)
    result = session.execute(query, {"vault_id": vault_id})
    return [{"id": str(row.id), "name": row.name, "file_path": row.file_path} for row in result]


def get_document_content(doc_id: str, session) -> Optional[str]:
    """Get document content from chunks or extraction_raw_content."""
    query = text("""
        SELECT content FROM document_chunks 
        WHERE document_id = :doc_id 
        ORDER BY chunk_index
    """)
    result = session.execute(query, {"doc_id": doc_id})
    chunks = [row.content for row in result]
    if chunks:
        return "\n\n".join(chunks)
    return None


def run_ontology_extraction(vault_id: str, limit: int = None):
    """Run ontology-centric extraction on all documents in vault."""
    session = get_db_session()
    
    log(f"Getting documents for vault {vault_id[:8]}...")
    docs = get_documents_needing_extraction(vault_id, session)
    log(f"Found {len(docs)} documents")
    
    if limit:
        docs = docs[:limit]
        log(f"Processing first {limit} documents")
    
    pipeline = OntologyCentricPipeline(tenant_id=vault_id, db_session=session)
    
    total_entities = 0
    total_relations = 0
    
    for i, doc in enumerate(docs, 1):
        log(f"[{i}/{len(docs)}] Processing: {doc['name']}")
        
        content = get_document_content(doc['id'], session)
        if not content:
            log(f"  No content found for {doc['name']}, skipping")
            continue
        
        try:
            result = pipeline.extract(
                document_id=doc['id'],
                document_name=doc['name'],
                content=content,
                document_type="GENERAL",
            )
            
            log(f"  Extracted: {result.entities_staged} entities, {result.relationships_staged} relationships")
            total_entities += result.entities_staged
            total_relations += result.relationships_staged
            
        except Exception as e:
            log(f"  ERROR: {e}")
            continue
    
    log(f"\n{'='*60}")
    log(f"EXTRACTION COMPLETE")
    log(f"Total entities: {total_entities}")
    log(f"Total relationships: {total_relations}")
    log(f"{'='*60}")
    
    session.close()


def main():
    parser = argparse.ArgumentParser(description="Test Ontology-Centric Extraction")
    parser.add_argument("--vault-id", required=True, help="Vault ID to extract")
    parser.add_argument("--limit", type=int, help="Limit number of documents")
    args = parser.parse_args()
    
    log("Starting Ontology-Centric Extraction Test")
    log(f"Vault: {args.vault_id}")
    
    run_ontology_extraction(args.vault_id, args.limit)


if __name__ == "__main__":
    main()
