#!/usr/bin/env python3
"""
Check if platform.documents and public.documents are in sync
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_table_sync(vault_id: str):
    """Check if platform.documents and public.documents show the same data."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    print(f"\n{'='*80}")
    print(f"SPLIT-BRAIN VERIFICATION CHECK")
    print(f"Vault ID: {vault_id}")
    print(f"{'='*80}\n")

    with psycopg2.connect(database_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # Query platform.documents
            print("1. PLATFORM.DOCUMENTS")
            print("-" * 80)
            cur.execute("""
                SELECT id, name, status, extraction_level,
                       single_extracted_at, multi_extracted_at
                FROM platform.documents
                WHERE tenant_id = %s
                ORDER BY name
            """, (vault_id,))

            platform_docs = cur.fetchall()
            if platform_docs:
                for doc in platform_docs:
                    print(f"  ID: {doc['id']}")
                    print(f"  Name: {doc['name']}")
                    print(f"  Status: {doc['status']}")
                    print(f"  Extraction Level: {doc['extraction_level']}")
                    print(f"  Single Extracted: {doc['single_extracted_at']}")
                    print(f"  Multi Extracted: {doc['multi_extracted_at']}")
                    print()
            else:
                print("  (no documents found)")

            platform_count = len(platform_docs)
            print(f"  TOTAL: {platform_count} documents\n")

            # Query public.documents
            print("2. PUBLIC.DOCUMENTS")
            print("-" * 80)

            # First check if public.documents table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'documents'
                )
            """)
            public_table_exists = cur.fetchone()['exists']

            if not public_table_exists:
                print("  ❌ TABLE DOES NOT EXIST")
                print("  This explains the split-brain!")
                print("  All Brain queries to public.documents are failing.\n")
                public_docs = []
                public_count = 0
            else:
                cur.execute("""
                    SELECT id, name, status, extraction_level,
                           single_extracted_at, multi_extracted_at
                    FROM public.documents
                    WHERE tenant_id = %s
                    ORDER BY name
                """, (vault_id,))

                public_docs = cur.fetchall()
                if public_docs:
                    for doc in public_docs:
                        print(f"  ID: {doc['id']}")
                        print(f"  Name: {doc['name']}")
                        print(f"  Status: {doc['status']}")
                        print(f"  Extraction Level: {doc['extraction_level']}")
                        print(f"  Single Extracted: {doc['single_extracted_at']}")
                        print(f"  Multi Extracted: {doc['multi_extracted_at']}")
                        print()
                else:
                    print("  (no documents found)")

                public_count = len(public_docs)
                print(f"  TOTAL: {public_count} documents\n")

            # Compare
            print("3. SPLIT-BRAIN ANALYSIS")
            print("-" * 80)

            if not public_table_exists:
                print("❌ CRITICAL: public.documents table DOES NOT EXIST")
                print("   All Brain/extraction queries are failing or using wrong table")
                print("\n   IMPACT:")
                print("   - Extraction reads from platform.documents (fallback?)")
                print("   - Or extraction queries fail silently")
                print("   - Brain has no document records")
                print("   - This is architectural split-brain at schema level\n")
            elif platform_count != public_count:
                print(f"❌ SPLIT-BRAIN DETECTED: COUNT MISMATCH")
                print(f"   platform.documents: {platform_count} documents")
                print(f"   public.documents: {public_count} documents")
                print(f"   Difference: {abs(platform_count - public_count)} documents\n")
            else:
                print(f"✓ Document counts match: {platform_count} documents")

                # Check if content matches
                mismatches = []
                platform_ids = {doc['id']: doc for doc in platform_docs}
                public_ids = {doc['id']: doc for doc in public_docs}

                all_ids = set(platform_ids.keys()) | set(public_ids.keys())

                for doc_id in all_ids:
                    p_doc = platform_ids.get(doc_id)
                    pub_doc = public_ids.get(doc_id)

                    if not p_doc:
                        mismatches.append(f"  - {doc_id}: In public.documents but NOT in platform.documents")
                    elif not pub_doc:
                        mismatches.append(f"  - {doc_id}: In platform.documents but NOT in public.documents")
                    elif (p_doc['status'] != pub_doc['status'] or
                          p_doc['extraction_level'] != pub_doc['extraction_level']):
                        mismatches.append(f"  - {p_doc['name']}:")
                        mismatches.append(f"      platform: status={p_doc['status']}, level={p_doc['extraction_level']}")
                        mismatches.append(f"      public:   status={pub_doc['status']}, level={pub_doc['extraction_level']}")

                if mismatches:
                    print(f"\n❌ SPLIT-BRAIN DETECTED: DATA MISMATCH")
                    print("\n".join(mismatches))
                else:
                    print("✓ Document data matches (IDs, status, extraction_level)")
                    print("\n✅ NO SPLIT-BRAIN: Tables are in sync\n")

            # Check entities/relationships
            print("\n4. KNOWLEDGE GRAPH DATA")
            print("-" * 80)

            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE stage = 'staging') as staging_entities,
                    COUNT(*) FILTER (WHERE stage = 'trusted') as trusted_entities
                FROM entities
                WHERE tenant_id = %s
            """, (vault_id,))

            entities = cur.fetchone()
            print(f"  Entities (staging): {entities['staging_entities']}")
            print(f"  Entities (trusted): {entities['trusted_entities']}")

            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE stage = 'staging') as staging_rels,
                    COUNT(*) FILTER (WHERE stage = 'trusted') as trusted_rels
                FROM relationships
                WHERE tenant_id = %s
            """, (vault_id,))

            rels = cur.fetchone()
            print(f"  Relationships (staging): {rels['staging_rels']}")
            print(f"  Relationships (trusted): {rels['trusted_rels']}")

            if entities['trusted_entities'] == 0 and entities['staging_entities'] > 0:
                print("\n  ⚠️  WARNING: Entities in STAGING but NONE in TRUSTED")
                print("      Verification/promotion did not execute")

            if rels['trusted_rels'] == 0 and rels['staging_rels'] > 0:
                print("\n  ⚠️  WARNING: Relationships in STAGING but NONE in TRUSTED")
                print("      Verification/promotion did not execute")

            print(f"\n{'='*80}\n")

if __name__ == '__main__':
    vault_id = sys.argv[1] if len(sys.argv) > 1 else 'b158cd16-810a-484d-99a8-8de786602c35'
    check_table_sync(vault_id)
