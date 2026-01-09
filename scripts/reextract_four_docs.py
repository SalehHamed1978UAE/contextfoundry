"""
Re-extract entities and relationships from 4 test documents with open capture.
Persists relationships to the database.
"""
import sys
sys.path.insert(0, '/home/runner/workspace')

from uuid import uuid4, UUID
from sqlalchemy import text
from datetime import datetime
from src.context_foundry.models.schema import (
    get_session, set_tenant_context, Entity, Relationship, LifecycleState, ValidationStatus
)
from src.context_foundry.extraction.entity_extractor import EntityExtractor
from src.context_foundry.extraction.relation_extractor import RelationExtractor

TENANT_ID = "7627d577-e07c-484f-893a-ed2f464d28b9"

DOCUMENTS = [
    ("Horizon_Ventures_Portfolio.md", "a44f073e-12f6-493d-9a99-65fe34f81067"),
    ("Federated_Learning_Research_Paper.md", "34cc4a0c-65f6-4405-8e3b-3d77e3f0c757"),
    ("TechCorp_Global_Structure.md", "593b37a2-3c72-4f8f-9f7f-e98ecbeb69b8"),
    ("Global_AI_Summit_2024.md", "e36012a6-571d-4ac8-936b-ea4f01586423"),
]

def get_document_text(session, doc_id):
    """Get document text from chunks."""
    chunks = session.execute(text("""
        SELECT text FROM document_chunks 
        WHERE document_id = :doc_id 
        ORDER BY chunk_index
    """), {"doc_id": doc_id}).fetchall()
    return "\n\n".join(row[0] for row in chunks if row[0])

def find_entity_by_name(session, name, tenant_id):
    """Find entity by name (case-insensitive)."""
    result = session.execute(text("""
        SELECT id, name, entity_type FROM entities 
        WHERE tenant_id = :tenant_id 
        AND LOWER(name) = LOWER(:name)
        LIMIT 1
    """), {"tenant_id": tenant_id, "name": name}).fetchone()
    return result

def create_relationship(session, source_id, target_id, rel_type, doc_id, confidence, tenant_id, source_span=""):
    """Create a new relationship in the database."""
    rel = Relationship(
        id=uuid4(),
        tenant_id=UUID(tenant_id),
        source_id=source_id,
        target_id=target_id,
        relationship_type=rel_type,
        lifecycle_state=LifecycleState.STAGING,
        validation_status=ValidationStatus.PENDING,
        confidence=confidence,
        source_document_id=doc_id,
        source_sentence=source_span[:500] if source_span else None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(rel)
    return rel

def process_document(session, doc_name, doc_id, tenant_id):
    """Process a single document: extract entities and relationships."""
    print(f"\n{'='*60}")
    print(f"Processing: {doc_name}")
    print(f"Document ID: {doc_id}")
    print('='*60)
    
    doc_text = get_document_text(session, doc_id)
    if not doc_text:
        print(f"  WARNING: No text found for document {doc_id}")
        return {"entities": 0, "relationships": 0, "persisted": 0}
    
    print(f"  Document text length: {len(doc_text)} chars")
    
    entity_extractor = EntityExtractor()
    entities = entity_extractor.extract_from_text(doc_text, doc_id, 'chunk1')
    print(f"\n  Extracted {len(entities)} entities:")
    
    entity_types = {}
    for e in entities:
        entity_types[e.entity_type] = entity_types.get(e.entity_type, 0) + 1
    for etype, count in sorted(entity_types.items()):
        print(f"    - {etype}: {count}")
    
    entity_dicts = [{'entity_type': e.entity_type, 'canonical_name': e.canonical_name} for e in entities]
    relation_extractor = RelationExtractor()
    relations = relation_extractor.extract_from_text(doc_text, entity_dicts, doc_id, 'chunk1')
    
    print(f"\n  Extracted {len(relations)} relationships:")
    rel_types = {}
    for r in relations:
        rel_types[r.relation_type] = rel_types.get(r.relation_type, 0) + 1
    for rtype, count in sorted(rel_types.items()):
        print(f"    - {rtype}: {count}")
    
    persisted_count = 0
    skipped_count = 0
    
    for rel in relations:
        source_entity = find_entity_by_name(session, rel.source_name, tenant_id)
        target_entity = find_entity_by_name(session, rel.target_name, tenant_id)
        
        if source_entity and target_entity:
            create_relationship(
                session,
                source_id=source_entity[0],
                target_id=target_entity[0],
                rel_type=rel.relation_type,
                doc_id=doc_id,
                confidence=rel.confidence,
                tenant_id=tenant_id,
                source_span=rel.source_span
            )
            persisted_count += 1
        else:
            skipped_count += 1
    
    print(f"\n  Persisted {persisted_count} relationships to database")
    print(f"  Skipped {skipped_count} relationships (entities not found in DB)")
    
    return {
        "entities": len(entities),
        "relationships": len(relations),
        "persisted": persisted_count,
        "skipped": skipped_count
    }

def main():
    print("="*60)
    print("Re-extraction of 4 Test Documents")
    print("Open Capture Mode with Relationship Persistence")
    print("="*60)
    
    session = get_session()
    set_tenant_context(session, TENANT_ID)
    
    total_stats = {
        "entities": 0,
        "relationships": 0,
        "persisted": 0,
        "skipped": 0
    }
    
    for doc_name, doc_id in DOCUMENTS:
        try:
            stats = process_document(session, doc_name, doc_id, TENANT_ID)
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)
        except Exception as e:
            print(f"  ERROR processing {doc_name}: {e}")
            import traceback
            traceback.print_exc()
    
    session.commit()
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    print(f"Total entities extracted: {total_stats['entities']}")
    print(f"Total relationships extracted: {total_stats['relationships']}")
    print(f"Total relationships persisted: {total_stats['persisted']}")
    print(f"Total relationships skipped: {total_stats['skipped']}")
    print("\nAll relationships committed to database.")

if __name__ == "__main__":
    main()
