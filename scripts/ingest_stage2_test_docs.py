#!/usr/bin/env python3
"""
Stage 2 Test Document Ingestion Script

Ingests the 5 test documents for Stage 2: Context-Attached Knowledge testing.
Creates a test tenant and promotes all extracted entities/relationships to TRUSTED.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context_foundry.models.schema import get_session, Entity, Relationship, LifecycleState
from src.context_foundry.agents.graph_builder import GraphBuilderAgent


TEST_TENANT_ID = "11111111-1111-1111-1111-111111111111"

TEST_DOCUMENTS = [
    ("test_docs/career_history.md", "Career History", "PERSONNEL_RECORD"),
    ("test_docs/investment_portfolio.md", "Investment Portfolio", "FINANCIAL_RECORD"),
    ("test_docs/project_team.md", "Project Team Structure", "PROJECT_RECORD"),
    ("test_docs/board_positions.md", "Board Positions", "GOVERNANCE_RECORD"),
    ("test_docs/research_collaboration.md", "Research Collaboration", "RESEARCH_RECORD"),
]


def main():
    print("=" * 60)
    print("Stage 2: Context-Attached Knowledge - Test Document Ingestion")
    print("=" * 60)
    
    session = get_session()
    
    try:
        existing_count = session.query(Entity).filter(
            Entity.tenant_id == uuid.UUID(TEST_TENANT_ID)
        ).count()
        
        if existing_count > 0:
            print(f"\nFound {existing_count} existing entities for test tenant.")
            response = input("Clear existing data? (y/n): ").strip().lower()
            if response == 'y':
                session.query(Relationship).filter(
                    Relationship.tenant_id == uuid.UUID(TEST_TENANT_ID)
                ).delete()
                session.query(Entity).filter(
                    Entity.tenant_id == uuid.UUID(TEST_TENANT_ID)
                ).delete()
                session.commit()
                print("Cleared existing test data.")
        
        agent = GraphBuilderAgent(session=session)
        
        total_entities = 0
        total_relationships = 0
        
        for doc_path, title, doc_type in TEST_DOCUMENTS:
            print(f"\n--- Ingesting: {title} ---")
            
            if not os.path.exists(doc_path):
                print(f"  ERROR: File not found: {doc_path}")
                continue
            
            result = agent.ingest_document(
                doc_path=doc_path,
                doc_type=doc_type,
                title=title,
                tenant_id=TEST_TENANT_ID
            )
            
            print(f"  Entities extracted: {result.entities_extracted}")
            print(f"  Relationships extracted: {result.relationships_extracted}")
            print(f"  Entities staged: {result.entities_staged}")
            print(f"  Relationships staged: {result.relationships_staged}")
            
            if result.errors:
                print(f"  Errors: {result.errors}")
            
            total_entities += result.entities_staged
            total_relationships += result.relationships_staged
        
        print("\n" + "=" * 60)
        print("Promoting all STAGING items to TRUSTED...")
        print("=" * 60)
        
        entities_promoted = session.query(Entity).filter(
            Entity.tenant_id == uuid.UUID(TEST_TENANT_ID),
            Entity.lifecycle_state == LifecycleState.STAGING
        ).update({Entity.lifecycle_state: LifecycleState.TRUSTED})
        
        relationships_promoted = session.query(Relationship).filter(
            Relationship.tenant_id == uuid.UUID(TEST_TENANT_ID),
            Relationship.lifecycle_state == LifecycleState.STAGING
        ).update({Relationship.lifecycle_state: LifecycleState.TRUSTED})
        
        session.commit()
        
        print(f"\nPromoted {entities_promoted} entities to TRUSTED")
        print(f"Promoted {relationships_promoted} relationships to TRUSTED")
        
        print("\n" + "=" * 60)
        print("Verifying Context Fields...")
        print("=" * 60)
        
        relationships_with_context = session.query(Relationship).filter(
            Relationship.tenant_id == uuid.UUID(TEST_TENANT_ID),
            Relationship.lifecycle_state == LifecycleState.TRUSTED
        ).all()
        
        context_stats = {
            "total": len(relationships_with_context),
            "with_valid_from": 0,
            "with_valid_to": 0,
            "with_provenance": 0,
            "with_event_context": 0,
            "with_qualifiers": 0
        }
        
        print("\nSample relationships with context:")
        for i, rel in enumerate(relationships_with_context[:5]):
            if rel.valid_from:
                context_stats["with_valid_from"] += 1
            if rel.valid_to:
                context_stats["with_valid_to"] += 1
            if rel.provenance_text:
                context_stats["with_provenance"] += 1
            if rel.event_context:
                context_stats["with_event_context"] += 1
            if rel.qualifiers:
                context_stats["with_qualifiers"] += 1
            
            print(f"\n  [{i+1}] {rel.source_entity.name if rel.source_entity else '?'} "
                  f"--[{rel.relationship_type}]--> "
                  f"{rel.target_entity.name if rel.target_entity else '?'}")
            print(f"      valid_from: {rel.valid_from}")
            print(f"      valid_to: {rel.valid_to}")
            print(f"      event_context: {rel.event_context}")
            print(f"      provenance: {rel.provenance_text[:100] if rel.provenance_text else None}...")
            print(f"      qualifiers: {rel.qualifiers}")
        
        for rel in relationships_with_context[5:]:
            if rel.valid_from:
                context_stats["with_valid_from"] += 1
            if rel.valid_to:
                context_stats["with_valid_to"] += 1
            if rel.provenance_text:
                context_stats["with_provenance"] += 1
            if rel.event_context:
                context_stats["with_event_context"] += 1
            if rel.qualifiers:
                context_stats["with_qualifiers"] += 1
        
        print("\n" + "=" * 60)
        print("Context Field Statistics:")
        print("=" * 60)
        print(f"  Total relationships: {context_stats['total']}")
        print(f"  With valid_from: {context_stats['with_valid_from']} ({100*context_stats['with_valid_from']/max(1,context_stats['total']):.0f}%)")
        print(f"  With valid_to: {context_stats['with_valid_to']} ({100*context_stats['with_valid_to']/max(1,context_stats['total']):.0f}%)")
        print(f"  With provenance: {context_stats['with_provenance']} ({100*context_stats['with_provenance']/max(1,context_stats['total']):.0f}%)")
        print(f"  With event_context: {context_stats['with_event_context']} ({100*context_stats['with_event_context']/max(1,context_stats['total']):.0f}%)")
        print(f"  With qualifiers: {context_stats['with_qualifiers']} ({100*context_stats['with_qualifiers']/max(1,context_stats['total']):.0f}%)")
        
        print("\n" + "=" * 60)
        print("INGESTION COMPLETE")
        print("=" * 60)
        print(f"Test tenant ID: {TEST_TENANT_ID}")
        print(f"Total entities: {total_entities}")
        print(f"Total relationships: {total_relationships}")
        print("\nRun 'python scripts/stage2_test_runner.py' to test the 20 questions.")
        
    except Exception as e:
        print(f"\nError during ingestion: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        return 1
    finally:
        session.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
