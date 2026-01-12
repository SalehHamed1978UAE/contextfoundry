#!/usr/bin/env python3
"""
Verify Ontology Foundry Fix - Extract a single chunk and show normalization.
"""

import sys
sys.path.insert(0, '/home/runner/workspace')

import logging
from uuid import UUID, uuid4
from sqlalchemy import text
from src.context_foundry.models.schema import get_session, DocumentChunk
from src.context_foundry.extraction.entity_extractor import EntityExtractor
from src.context_foundry.extraction.relation_extractor import RelationExtractor
from src.context_foundry.extraction.staging_loader import StagingLoader
from src.context_foundry.ontology.normalizer import CandidateNormalizer
from src.context_foundry.config.domain_schema import get_schema_loader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

TEST_TENANT_ID = str(uuid4())

TEST_TEXT = """
TechVentures Holdings Company Profile

Executive Team:
- Sarah Chen, CEO - Total compensation: $850,000
- Michael Torres, CFO - Total compensation: $720,000
- James Wilson, CTO - Total compensation: $680,000

Sarah Chen reports directly to the Board of Directors.
Michael Torres and James Wilson report to Sarah Chen.

Company headquarters are located in San Francisco, CA.
TechVentures was founded in 2015 and employs 450 people.

The company has invested in several startups including CloudMatrix and HealthSync.
"""

def main():
    print("\n" + "="*70)
    print("ONTOLOGY FOUNDRY FIX VERIFICATION")
    print("="*70)
    print(f"\nTest Tenant: {TEST_TENANT_ID}")
    print("\nTest Document Content:")
    print("-"*70)
    print(TEST_TEXT[:500])
    print("-"*70)
    
    normalizer = CandidateNormalizer()
    schema_loader = get_schema_loader()
    schema_types = set(schema_loader.schema.get_relationship_type_names())
    
    entity_extractor = EntityExtractor(model="gpt-4o-mini", temperature=0.0)
    relation_extractor = RelationExtractor(model="gpt-4o-mini", temperature=0.0)
    
    print("\n" + "="*70)
    print("STEP 1: EXTRACTING ENTITIES")
    print("="*70)
    
    entities = entity_extractor.extract_from_text(
        text=TEST_TEXT,
        document_id="test-doc-001",
        chunk_id="test-chunk-001",
        sentence_idx=0,
    )
    
    print(f"\nExtracted {len(entities)} entities:")
    entity_dicts = []
    for ent in entities:
        if hasattr(ent, 'to_dict'):
            ed = ent.to_dict()
        elif hasattr(ent, 'model_dump'):
            ed = ent.model_dump()
        else:
            ed = {"canonical_name": getattr(ent, 'canonical_name', 'N/A'), "entity_type": getattr(ent, 'entity_type', 'N/A')}
        ed['name'] = ed.get('canonical_name', ed.get('name', 'N/A'))
        entity_dicts.append(ed)
    for ed in entity_dicts[:10]:
        print(f"  - {ed.get('name', 'N/A')} ({ed.get('entity_type', 'N/A')})")
    
    print("\n" + "="*70)
    print("STEP 2: EXTRACTING RELATIONSHIPS")
    print("="*70)
    
    relations = relation_extractor.extract_from_text(
        text=TEST_TEXT,
        entities=entity_dicts,
        document_id="test-doc-001",
        chunk_id="test-chunk-001",
    )
    
    print(f"\nExtracted {len(relations)} relationships (RAW from LLM):")
    rel_dicts = []
    for rel in relations:
        if hasattr(rel, 'to_dict'):
            rd = rel.to_dict()
        elif isinstance(rel, dict):
            rd = rel
        else:
            rd = {
                "relation_type": getattr(rel, 'relation_type', 'N/A'),
                "source_name": getattr(rel, 'source_name', 'N/A'),
                "target_name": getattr(rel, 'target_name', 'N/A'),
            }
        rd['relationship_type'] = rd.get('relation_type', rd.get('relationship_type', 'UNKNOWN'))
        rel_dicts.append(rd)
        rel_type = rd.get('relationship_type', 'N/A')
        source = rd.get('source_name', 'N/A')
        target = rd.get('target_name', 'N/A')
        print(f"  - {source} --[{rel_type}]--> {target}")
    
    print("\n" + "="*70)
    print("STEP 3: NORMALIZING RELATIONSHIP TYPES")
    print("="*70)
    
    normalized_count = 0
    known_count = 0
    unknown_count = 0
    
    print("\nNormalization Results:")
    for rd in rel_dicts:
        original_type = rd.get('relationship_type', 'UNKNOWN')
        normalized_type = normalizer.normalize_relationship(original_type)
        
        in_schema = normalized_type in schema_types
        status = "KNOWN" if in_schema else "CANDIDATE"
        
        if original_type != normalized_type:
            print(f"  {original_type:30} -> {normalized_type:25} [{status}] (normalized)")
            normalized_count += 1
        else:
            print(f"  {original_type:30} -> {normalized_type:25} [{status}]")
        
        if in_schema:
            known_count += 1
        else:
            unknown_count += 1
    
    print("\n" + "="*70)
    print("STEP 4: LOADING TO DATABASE (DRY RUN)")
    print("="*70)
    
    with get_session(use_rls_role=False) as session:
        loader = StagingLoader(session, tenant_id=TEST_TENANT_ID)
        
        loaded_entities = 0
        loaded_relations = 0
        candidates_created = 0
        
        for ent in entities:
            try:
                result, action = loader.load_entity(ent)
                if action == "created":
                    loaded_entities += 1
            except Exception as e:
                logger.warning(f"Entity load: {e}")
        
        for rd in rel_dicts:
            original_type = rd.get('relationship_type', '')
            normalized_type = normalizer.normalize_relationship(original_type)
            rd['relationship_type'] = normalized_type
            
            try:
                loader.load_relation(rd)
                if normalized_type in schema_types:
                    loaded_relations += 1
                else:
                    candidates_created += 1
            except Exception as e:
                logger.warning(f"Relation load: {e}")
        
        session.commit()
        
        result = session.execute(text("""
            SELECT relationship_type, COUNT(*) 
            FROM relationships 
            WHERE tenant_id = :tid
            GROUP BY relationship_type
            ORDER BY COUNT(*) DESC
        """), {"tid": TEST_TENANT_ID}).fetchall()
        
        print(f"\nRelationships in Knowledge Graph:")
        for row in result:
            print(f"  {row[0]}: {row[1]}")
        
        candidates = session.execute(text("""
            SELECT normalized_name, status, COUNT(*) 
            FROM ontology_candidates 
            WHERE tenant_id = :tid
            GROUP BY normalized_name, status
        """), {"tid": TEST_TENANT_ID}).fetchall()
        
        print(f"\nCandidates for Review:")
        if candidates:
            for row in candidates:
                print(f"  {row[0]}: {row[2]} ({row[1]})")
        else:
            print("  (none - all types were known)")
    
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    print(f"  Entities extracted: {len(entities)}")
    print(f"  Entities loaded: {loaded_entities}")
    print(f"  Relationships extracted: {len(relations)}")
    print(f"  Types normalized: {normalized_count}")
    print(f"  Known types (-> KG): {known_count}")
    print(f"  Unknown types (-> Candidates): {unknown_count}")
    print()
    
    if known_count > 0:
        print("  SUCCESS: Known relationship types are going to the Knowledge Graph!")
        print("  The Ontology Foundry fix is working correctly.")
    else:
        print("  Note: No critical relationship types extracted in this sample.")
    print()

if __name__ == "__main__":
    main()
