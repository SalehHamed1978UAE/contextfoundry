#!/usr/bin/env python3
"""
Re-extract SPECIFICATION entities from technical spec documents.

This script:
1. Finds chunks containing technical specifications
2. Runs the post_processor to extract SPECIFICATION entities
3. Stores the entities in the database
"""

import os
import sys
import uuid
import logging
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Target vault
VAULT_ID = '1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91'

# Queries to find spec-related chunks
SPEC_QUERIES = [
    # Battery specs
    "400 Wh/kg",
    "Energy Density",
    "Operating Temp",
    "-30 to 60",
    "LLZO",
    "Li7La3Zr2O12",
    "solid electrolyte",
    # Hydrogen specs  
    "425 kg/hr",
    "hydrogen production",
    "850 kg/hr",
    "Phase 1",
]


def get_db_session():
    """Create database session."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not set")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def find_spec_chunks(session):
    """Find chunks containing technical specifications."""
    chunks = []
    seen_ids = set()
    
    for query_term in SPEC_QUERIES:
        result = session.execute(
            text("""
                SELECT id, text, document_id 
                FROM document_chunks 
                WHERE tenant_id = :tenant_id 
                AND text ILIKE :pattern
                LIMIT 10
            """),
            {"tenant_id": VAULT_ID, "pattern": f"%{query_term}%"}
        )
        
        for row in result:
            if row.id not in seen_ids:
                seen_ids.add(row.id)
                chunks.append({
                    'id': row.id,
                    'text': row.text,
                    'document_id': row.document_id
                })
    
    return chunks


def extract_specs_from_text(text: str, chunk_id: str) -> list:
    """Extract SPECIFICATION entities from text using patterns."""
    from src.context_foundry.extraction.post_processor import get_post_processor
    
    post_processor = get_post_processor()
    
    # Use the spec extraction method with empty set for existing names
    specs = post_processor._extract_specification_entities(text, existing_entity_names=set())
    
    # Add chunk provenance
    for spec in specs:
        spec['source_chunk_id'] = chunk_id
        
    return specs


def store_specification_entity(session, spec: dict) -> str:
    """Store a SPECIFICATION entity in the database."""
    import json
    entity_id = str(uuid.uuid4())
    
    # Check for existing entity with same name
    existing = session.execute(
        text("""
            SELECT id FROM entities 
            WHERE tenant_id = :tenant_id 
            AND entity_type = 'SPECIFICATION'
            AND name = :name
            LIMIT 1
        """),
        {"tenant_id": VAULT_ID, "name": spec['name']}
    ).fetchone()
    
    if existing:
        logger.info(f"  SKIP (exists): {spec['name']}")
        return existing.id
    
    # Insert new entity
    properties = spec.get('properties', {})
    session.execute(
        text("""
            INSERT INTO entities (
                id, tenant_id, entity_type, name, 
                confidence, status, properties, created_at
            ) VALUES (
                :id, :tenant_id, 'SPECIFICATION', :name,
                :confidence, 'STAGING', CAST(:properties AS jsonb), :created_at
            )
        """),
        {
            "id": entity_id,
            "tenant_id": VAULT_ID,
            "name": spec['name'],
            "confidence": spec.get('confidence', 0.85),
            "properties": json.dumps(properties),
            "created_at": datetime.now(timezone.utc)
        }
    )
    
    logger.info(f"  CREATED: {spec['name']} ({properties})")
    return entity_id


def main():
    logger.info("=" * 60)
    logger.info("Re-extracting SPECIFICATION entities from tech spec chunks")
    logger.info("=" * 60)
    
    session = get_db_session()
    
    try:
        # Step 1: Find chunks with spec data
        logger.info("\n[1] Finding spec-related chunks...")
        chunks = find_spec_chunks(session)
        logger.info(f"    Found {len(chunks)} chunks with spec data")
        
        # Step 2: Extract specs from each chunk
        logger.info("\n[2] Extracting SPECIFICATION entities...")
        all_specs = []
        
        for chunk in chunks:
            specs = extract_specs_from_text(chunk['text'], chunk['id'])
            if specs:
                logger.info(f"    Chunk {str(chunk['id'])[:8]}: {len(specs)} specs found")
                all_specs.extend(specs)
        
        logger.info(f"\n    Total specs extracted: {len(all_specs)}")
        
        # Step 3: Deduplicate specs by name
        unique_specs = {}
        for spec in all_specs:
            key = spec['name']
            if key not in unique_specs or spec.get('confidence', 0) > unique_specs[key].get('confidence', 0):
                unique_specs[key] = spec
        
        logger.info(f"    Unique specs: {len(unique_specs)}")
        
        # Step 4: Store specs in database
        logger.info("\n[3] Storing SPECIFICATION entities...")
        created = 0
        for spec in unique_specs.values():
            entity_id = store_specification_entity(session, spec)
            if entity_id:
                created += 1
        
        session.commit()
        logger.info(f"\n    Committed {created} entities")
        
        # Step 5: Verify
        logger.info("\n[4] Verifying stored entities...")
        result = session.execute(
            text("""
                SELECT name, properties 
                FROM entities 
                WHERE tenant_id = :tenant_id 
                AND entity_type = 'SPECIFICATION'
                ORDER BY name
            """),
            {"tenant_id": VAULT_ID}
        )
        
        specs = list(result)
        logger.info(f"    Found {len(specs)} SPECIFICATION entities:")
        for row in specs[:20]:
            logger.info(f"      - {row.name}: {row.properties}")
        
        logger.info("\n" + "=" * 60)
        logger.info("Re-extraction complete!")
        logger.info("=" * 60)
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
