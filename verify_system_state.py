#!/usr/bin/env python3
"""
Verify System State - Check for split-brain conditions
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import psycopg2
from psycopg2.extras import RealDictCursor

def verify_vault_state(vault_id: str):
    """Verify the actual state of a vault in the database."""
    database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"SYSTEM STATE VERIFICATION")
    print(f"Vault ID: {vault_id}")
    print(f"{'='*60}\n")

    with psycopg2.connect(database_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Check entities by stage
            cur.execute('''
                SELECT
                    stage,
                    COUNT(*) as count
                FROM entities
                WHERE tenant_id = %s
                GROUP BY stage
                ORDER BY stage
            ''', (vault_id,))

            print("1. ENTITIES BY STAGE:")
            entity_results = cur.fetchall()
            staging_entities = 0
            trusted_entities = 0
            for row in entity_results:
                print(f"   {row['stage']}: {row['count']}")
                if row['stage'] == 'staging':
                    staging_entities = row['count']
                elif row['stage'] == 'trusted':
                    trusted_entities = row['count']

            if not entity_results:
                print("   (none)")

            # 2. Check relationships by stage
            cur.execute('''
                SELECT
                    stage,
                    COUNT(*) as count
                FROM relationships
                WHERE tenant_id = %s
                GROUP BY stage
                ORDER BY stage
            ''', (vault_id,))

            print("\n2. RELATIONSHIPS BY STAGE:")
            rel_results = cur.fetchall()
            staging_rels = 0
            trusted_rels = 0
            for row in rel_results:
                print(f"   {row['stage']}: {row['count']}")
                if row['stage'] == 'staging':
                    staging_rels = row['count']
                elif row['stage'] == 'trusted':
                    trusted_rels = row['count']

            if not rel_results:
                print("   (none)")

            # 3. Check document status
            cur.execute('''
                SELECT
                    status,
                    COUNT(*) as count,
                    array_agg(name ORDER BY name) as doc_names
                FROM platform.documents
                WHERE tenant_id = %s
                GROUP BY status
                ORDER BY status
            ''', (vault_id,))

            print("\n3. DOCUMENTS BY STATUS:")
            doc_results = cur.fetchall()
            total_docs = 0
            for row in doc_results:
                total_docs += row['count']
                print(f"   {row['status']}: {row['count']}")
                for doc_name in row['doc_names']:
                    print(f"      - {doc_name}")

            if not doc_results:
                print("   (none)")

            # 4. Check chunks
            cur.execute('''
                SELECT COUNT(*) as count
                FROM chunks
                WHERE tenant_id = %s
            ''', (vault_id,))
            chunks_count = cur.fetchone()['count']
            print(f"\n4. CHUNKS: {chunks_count}")

            # 5. Check extraction requests
            cur.execute('''
                SELECT
                    status,
                    COUNT(*) as count
                FROM platform.extraction_requests
                WHERE vault_id = %s
                GROUP BY status
                ORDER BY status
            ''', (vault_id,))

            print("\n5. EXTRACTION REQUESTS BY STATUS:")
            req_results = cur.fetchall()
            for row in req_results:
                print(f"   {row['status']}: {row['count']}")

            if not req_results:
                print("   (none)")

            # 6. Database identity
            cur.execute('''
                SELECT
                    current_database() as db_name,
                    current_user as db_user,
                    inet_server_addr() as server_addr,
                    inet_server_port() as server_port
            ''')
            db_identity = cur.fetchone()

            print(f"\n6. DATABASE IDENTITY:")
            print(f"   Database: {db_identity['db_name']}")
            print(f"   User: {db_identity['db_user']}")
            print(f"   Server: {db_identity['server_addr']}:{db_identity['server_port']}")

            # 7. Validation check
            print(f"\n{'='*60}")
            print("VALIDATION RESULTS:")
            print(f"{'='*60}")

            is_valid = True
            issues = []

            if trusted_entities == 0 and staging_entities > 0:
                is_valid = False
                issues.append("❌ STAGING entities exist but NO TRUSTED entities")

            if trusted_rels == 0 and staging_rels > 0:
                is_valid = False
                issues.append("❌ STAGING relationships exist but NO TRUSTED relationships")

            if chunks_count > 0 and staging_entities == 0:
                is_valid = False
                issues.append(f"❌ {chunks_count} chunks exist but NO entities extracted")

            if is_valid:
                print("✅ System state appears valid")
                print(f"   - {trusted_entities} trusted entities")
                print(f"   - {trusted_rels} trusted relationships")
                print(f"   - {total_docs} documents processed")
            else:
                print("❌ INVALID SYSTEM STATE DETECTED:")
                for issue in issues:
                    print(f"   {issue}")

            print(f"\n{'='*60}\n")

if __name__ == '__main__':
    vault_id = sys.argv[1] if len(sys.argv) > 1 else 'b158cd16-810a-484d-99a8-8de786602c35'
    verify_vault_state(vault_id)
