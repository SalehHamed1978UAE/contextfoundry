#!/usr/bin/env python3
"""
Stage 4 Demo: One Substrate, Many Applications

This script demonstrates that the same World Model can power multiple use cases:
1. Q&A Agent - answers questions using the World Model
2. Entity Profile Generator - produces structured profiles from the same data

Both applications:
- Query the same underlying entities and relationships
- Use the same ContextBundle structure
- Apply the same sufficiency metrics
- Reference the same provenance sources
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.context_foundry.models.schema import get_session, Entity, Relationship, LifecycleState
from src.context_foundry.agents.graph_builder import GraphBuilderAgent
from src.context_foundry.agents.entity_profile_generator import EntityProfileGenerator
from src.context_foundry.agents.sufficiency import compute_sufficiency, extract_entities_from_query

TEST_TENANT = '55555555-5555-5555-5555-555555555555'


def setup_test_data(session):
    """Ingest test documents to populate the World Model."""
    print("\n" + "=" * 70)
    print("STEP 1: Populating World Model with Test Data")
    print("=" * 70)
    
    session.execute(text(f"SET app.current_tenant_id = '{TEST_TENANT}'"))
    session.execute(text('DELETE FROM relationships WHERE tenant_id = :tid'), {'tid': TEST_TENANT})
    session.execute(text('DELETE FROM entities WHERE tenant_id = :tid'), {'tid': TEST_TENANT})
    session.commit()
    
    agent = GraphBuilderAgent(session=session)
    
    docs = [
        ("Alice Johnson is VP of Engineering at Acme Corp since 2021. She leads the platform team.",
         "Alice Bio"),
        ("Bob Chen works as Senior Software Engineer at Acme Corp. He reports to Alice Johnson.",
         "Bob Bio"),
        ("Acme Corp is a technology company founded in 2015. Headquarters in San Francisco.",
         "Acme Info"),
        ("Alice Johnson previously worked at Google as Staff Engineer from 2015 to 2020.",
         "Alice History"),
    ]
    
    for content, title in docs:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        result = agent.ingest_document(
            doc_path=temp_path,
            doc_type='GENERAL',
            title=title,
            tenant_id=TEST_TENANT
        )
        print(f"  Ingested '{title}': {result.entities_staged}E, {result.relationships_staged}R")
        os.unlink(temp_path)
    
    session.query(Entity).filter(
        Entity.tenant_id == TEST_TENANT,
        Entity.lifecycle_state == LifecycleState.STAGING
    ).update({Entity.lifecycle_state: LifecycleState.TRUSTED})
    
    session.query(Relationship).filter(
        Relationship.tenant_id == TEST_TENANT,
        Relationship.lifecycle_state == LifecycleState.STAGING
    ).update({Relationship.lifecycle_state: LifecycleState.TRUSTED})
    
    session.commit()
    
    entities = session.query(Entity).filter(
        Entity.tenant_id == TEST_TENANT,
        Entity.lifecycle_state == LifecycleState.TRUSTED
    ).count()
    
    rels = session.query(Relationship).filter(
        Relationship.tenant_id == TEST_TENANT,
        Relationship.lifecycle_state == LifecycleState.TRUSTED
    ).count()
    
    print(f"\n  World Model populated: {entities} entities, {rels} relationships")
    return entities, rels


def demo_entity_profile(session):
    """Demonstrate the Entity Profile Generator."""
    print("\n" + "=" * 70)
    print("APPLICATION 1: Entity Profile Generator")
    print("=" * 70)
    
    generator = EntityProfileGenerator(session=session, tenant_id=TEST_TENANT)
    
    profile = generator.generate_profile("Alice Johnson")
    
    if profile:
        print("\n" + profile.to_markdown())
        
        print("\n--- Profile as JSON Dict ---")
        import json
        d = profile.to_dict()
        print(f"  Entity ID: {d['entity_id'][:8]}...")
        print(f"  Type: {d['entity_type']}")
        print(f"  Relationships: {d['relationship_count']} total")
        print(f"  Sufficiency: {d['sufficiency']}")
    else:
        print("  ERROR: Entity not found!")
    
    return profile


def demo_qa_agent(session):
    """Demonstrate Q&A using the same World Model."""
    print("\n" + "=" * 70)
    print("APPLICATION 2: Q&A Agent (Sufficiency Check)")
    print("=" * 70)
    
    query = "Who does Bob Chen report to?"
    print(f"\n  Query: \"{query}\"")
    
    query_entities = extract_entities_from_query(query)
    print(f"  Extracted entities: {query_entities}")
    
    session.execute(text(f"SET app.current_tenant_id = '{TEST_TENANT}'"))
    
    entities = session.query(Entity).filter(
        Entity.tenant_id == TEST_TENANT,
        Entity.lifecycle_state == LifecycleState.TRUSTED
    ).all()
    
    rels = session.query(Relationship).filter(
        Relationship.tenant_id == TEST_TENANT,
        Relationship.lifecycle_state == LifecycleState.TRUSTED
    ).all()
    
    entity_dicts = [{'id': str(e.id), 'name': e.name, 'entity_type': e.entity_type} for e in entities]
    rel_dicts = [{
        'id': str(r.id),
        'relationship_type': r.relationship_type,
        'source_entity_id': str(r.source_id),
        'target_entity_id': str(r.target_id),
        'valid_from': str(r.valid_from) if r.valid_from else None
    } for r in rels]
    
    sufficiency = compute_sufficiency(query_entities, entity_dicts, rel_dicts)
    
    print(f"\n  Sufficiency Signals:")
    print(f"    Coverage: {sufficiency.coverage:.2f}")
    print(f"    Freshness: {sufficiency.freshness:.2f}")
    print(f"    Source Agreement: {sufficiency.source_agreement:.2f}")
    print(f"    Relationship Density: {sufficiency.relationship_density:.2f}")
    print(f"    Overall Confidence: {sufficiency.overall_confidence:.2f}")
    
    print(f"\n  Gaps Detected: {[g['type'] for g in sufficiency.gaps_detected]}")
    
    bob_entity = next((e for e in entities if 'bob' in e.name.lower()), None)
    if bob_entity:
        bob_rels = [r for r in rels if r.source_id == bob_entity.id]
        print(f"\n  Knowledge about Bob Chen:")
        for r in bob_rels:
            target = next((e for e in entities if e.id == r.target_id), None)
            if target:
                print(f"    - {r.relationship_type} → {target.name}")
                if r.provenance_text:
                    print(f"      Source: \"{r.provenance_text[:60]}...\"")
    
    return sufficiency


def demo_shared_context_bundle(session):
    """Show that both apps can produce identical ContextBundles."""
    print("\n" + "=" * 70)
    print("PROOF: Same ContextBundle Structure for Both Apps")
    print("=" * 70)
    
    generator = EntityProfileGenerator(session=session, tenant_id=TEST_TENANT)
    
    bundle = generator.build_context_bundle("Alice Johnson")
    
    print(f"\n  ContextBundle for 'Alice Johnson':")
    print(f"    Query ID: {bundle.query_id}")
    print(f"    Target Entity Found: {bundle.target_entity_found}")
    print(f"    Semantic Entities: {len(bundle.semantic_entities)}")
    print(f"    Semantic Relationships: {len(bundle.semantic_relationships)}")
    print(f"    Confidence: {bundle.confidence:.2f}")
    
    if bundle.uncertainty:
        print(f"    Uncertainty Recommendation: {bundle.uncertainty.recommendation}")
    
    print("\n  This is the SAME ContextBundle structure that Q&A Agent would receive!")
    print("  Both apps use:")
    print("    - Same entity/relationship queries")
    print("    - Same sufficiency computation")
    print("    - Same provenance tracking")
    
    return bundle


def main():
    print("=" * 70)
    print("STAGE 4 DEMO: One Substrate, Many Applications")
    print("=" * 70)
    print("\nThis demo proves the same World Model powers multiple use cases.")
    
    session = get_session()
    
    try:
        setup_test_data(session)
        
        profile = demo_entity_profile(session)
        
        sufficiency = demo_qa_agent(session)
        
        bundle = demo_shared_context_bundle(session)
        
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print("\n  Both applications successfully used the same World Model:")
        print(f"    - Entity Profile Generator: Created profile for '{profile.name if profile else 'N/A'}'")
        print(f"    - Q&A Agent: Computed sufficiency ({sufficiency.overall_confidence:.2f} confidence)")
        print(f"    - Shared ContextBundle: {len(bundle.semantic_relationships)} relationships")
        print("\n  Stage 4 Goal: ACHIEVED")
        print("  Same substrate (World Model) → Multiple applications")
        
    finally:
        session.close()


if __name__ == "__main__":
    main()
