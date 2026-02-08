#!/usr/bin/env python3
"""
Comprehensive Database Split-Brain Investigation

This script investigates the split-brain problem between platform.documents and public.documents.
It provides detailed analysis of table existence, schemas, data counts, and staging status.

Usage:
    python3 investigate_split_brain_comprehensive.py [vault_id]

Default vault_id: b158cd16-810a-484d-99a8-8de786602c35
"""

import os
import sys
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

TARGET_VAULT_ID = 'b158cd16-810a-484d-99a8-8de786602c35'


def main():
    vault_id = sys.argv[1] if len(sys.argv) > 1 else TARGET_VAULT_ID

    print("=" * 100)
    print("DATABASE SPLIT-BRAIN INVESTIGATION")
    print("=" * 100)
    print(f"\nTarget Vault ID: {vault_id}")
    print(f"Timestamp: {os.popen('date').read().strip()}\n")

    # Get database URL
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        print("\nThis script requires DATABASE_URL to be set in the environment.")
        print("In Replit, this should be automatically set if PostgreSQL is enabled.")
        sys.exit(1)

    # Mask password in output
    display_url = database_url
    if '@' in display_url and ':' in display_url.split('@')[0]:
        user_part, rest = display_url.split('@', 1)
        user, _ = user_part.rsplit(':', 1)
        display_url = f"{user}:***@{rest}"

    print(f"Database: {display_url}\n")

    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
    except Exception as e:
        print(f"❌ ERROR: Could not connect to database: {e}")
        sys.exit(1)

    # =========================================================================
    # TASK 1: Check if both tables exist
    # =========================================================================
    print("=" * 100)
    print("TASK 1: CHECKING TABLE EXISTENCE")
    print("=" * 100 + "\n")

    tables_to_check = [
        ('platform', 'documents'),
        ('public', 'documents'),
        ('platform', 'entities'),
        ('public', 'entities'),
        ('platform', 'relationships'),
        ('public', 'relationships')
    ]

    existing_tables = {}

    for schema, table in tables_to_check:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = %s
                AND table_name = %s
            );
        """, (schema, table))
        exists = cursor.fetchone()['exists']
        existing_tables[f"{schema}.{table}"] = exists

        symbol = "✓" if exists else "✗"
        status = "EXISTS" if exists else "MISSING"
        print(f"  {symbol} {schema:10}.{table:15} {status}")

    # =========================================================================
    # TASK 2: Get actual schema for each table that exists
    # =========================================================================
    print("\n" + "=" * 100)
    print("TASK 2: TABLE SCHEMAS (ACTUAL COLUMN NAMES)")
    print("=" * 100)

    schema_info = {}

    for schema, table in tables_to_check:
        table_name = f"{schema}.{table}"
        if existing_tables[table_name]:
            print(f"\n{'─' * 100}")
            print(f"Schema for {table_name}")
            print(f"{'─' * 100}")

            cursor.execute("""
                SELECT
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position;
            """, (schema, table))

            columns = cursor.fetchall()
            schema_info[table_name] = [col['column_name'] for col in columns]

            print(f"{'Column Name':<30} {'Data Type':<25} {'Nullable':<10}")
            print("─" * 65)
            for col in columns:
                print(f"{col['column_name']:<30} {col['data_type']:<25} {col['is_nullable']:<10}")

    # =========================================================================
    # TASK 3: Count documents for target vault
    # =========================================================================
    print("\n" + "=" * 100)
    print(f"TASK 3: DOCUMENT COUNTS FOR VAULT {vault_id}")
    print("=" * 100)

    document_data = {}

    for schema in ['platform', 'public']:
        table_name = f"{schema}.documents"
        if not existing_tables[table_name]:
            print(f"\n❌ {table_name} does not exist - SKIPPING")
            continue

        print(f"\n{'─' * 100}")
        print(f"Analyzing {table_name}")
        print(f"{'─' * 100}")

        # Determine which column to use for tenant filtering
        id_col = None
        if 'tenant_id' in schema_info[table_name]:
            id_col = 'tenant_id'
        elif 'vault_id' in schema_info[table_name]:
            id_col = 'vault_id'

        if not id_col:
            print(f"⚠️  WARNING: No tenant_id or vault_id column found in {table_name}")
            continue

        print(f"Using filter column: {id_col}")

        # Count documents for this vault
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM {schema}.documents
            WHERE {id_col} = %s;
        """, (vault_id,))
        count = cursor.fetchone()['count']
        document_data[schema] = {'count': count, 'id_col': id_col}

        print(f"\nDocuments WHERE {id_col} = {vault_id}: {count}")

        # Get sample documents
        if count > 0:
            cursor.execute(f"""
                SELECT id, status
                FROM {schema}.documents
                WHERE {id_col} = %s
                LIMIT 5;
            """, (vault_id,))

            samples = cursor.fetchall()
            print(f"\nSample documents (showing up to 5):")
            print(f"{'ID':<40} {'Status':<15}")
            print("─" * 60)
            for doc in samples:
                print(f"{doc['id']:<40} {doc['status']:<15}")

        # Get total count across all tenants
        cursor.execute(f"SELECT COUNT(*) as total FROM {schema}.documents;")
        total = cursor.fetchone()['total']
        print(f"\nTotal documents in {table_name} (all tenants): {total}")

    # =========================================================================
    # TASK 4: Check entities and relationships tables
    # =========================================================================
    print("\n" + "=" * 100)
    print(f"TASK 4: ENTITIES AND RELATIONSHIPS ANALYSIS FOR VAULT {vault_id}")
    print("=" * 100)

    entity_data = {}
    relationship_data = {}

    for schema in ['platform', 'public']:
        # ─────────────────────────────────────────────────────────────────────
        # Entities
        # ─────────────────────────────────────────────────────────────────────
        table_name = f"{schema}.entities"
        if not existing_tables[table_name]:
            continue

        print(f"\n{'─' * 100}")
        print(f"Analyzing {table_name}")
        print(f"{'─' * 100}")

        # Find tenant ID column
        id_col = None
        if 'tenant_id' in schema_info[table_name]:
            id_col = 'tenant_id'
        elif 'vault_id' in schema_info[table_name]:
            id_col = 'vault_id'

        if not id_col:
            print(f"⚠️  WARNING: No tenant_id or vault_id column found")
            continue

        # Find stage column
        stage_col = None
        for col_name in schema_info[table_name]:
            if 'stage' in col_name.lower() or col_name == 'status':
                stage_col = col_name
                break

        if not stage_col:
            print(f"⚠️  WARNING: No stage/status column found")
            continue

        print(f"Using columns: {id_col}, {stage_col}")

        # Count by stage
        cursor.execute(f"""
            SELECT {stage_col}, COUNT(*) as count
            FROM {schema}.entities
            WHERE {id_col} = %s
            GROUP BY {stage_col}
            ORDER BY count DESC;
        """, (vault_id,))

        results = cursor.fetchall()
        entity_data[schema] = results

        if results:
            print(f"\nEntities by {stage_col}:")
            for row in results:
                print(f"  {str(row[stage_col]):15} {row['count']:>6} entities")
        else:
            print(f"\n⚠️  No entities found for vault {vault_id}")

        # Total count
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM {schema}.entities
            WHERE {id_col} = %s;
        """, (vault_id,))
        total = cursor.fetchone()['count']
        print(f"\nTotal entities: {total}")

        # ─────────────────────────────────────────────────────────────────────
        # Relationships
        # ─────────────────────────────────────────────────────────────────────
        table_name = f"{schema}.relationships"
        if not existing_tables[table_name]:
            continue

        print(f"\n{'─' * 100}")
        print(f"Analyzing {table_name}")
        print(f"{'─' * 100}")

        # Find tenant ID column
        id_col = None
        if 'tenant_id' in schema_info[table_name]:
            id_col = 'tenant_id'
        elif 'vault_id' in schema_info[table_name]:
            id_col = 'vault_id'

        if not id_col:
            print(f"⚠️  WARNING: No tenant_id or vault_id column found")
            continue

        # Find stage column
        stage_col = None
        for col_name in schema_info[table_name]:
            if 'stage' in col_name.lower() or col_name == 'status':
                stage_col = col_name
                break

        if not stage_col:
            print(f"⚠️  WARNING: No stage/status column found")
            continue

        print(f"Using columns: {id_col}, {stage_col}")

        # Count by stage
        cursor.execute(f"""
            SELECT {stage_col}, COUNT(*) as count
            FROM {schema}.relationships
            WHERE {id_col} = %s
            GROUP BY {stage_col}
            ORDER BY count DESC;
        """, (vault_id,))

        results = cursor.fetchall()
        relationship_data[schema] = results

        if results:
            print(f"\nRelationships by {stage_col}:")
            for row in results:
                print(f"  {str(row[stage_col]):15} {row['count']:>6} relationships")
        else:
            print(f"\n⚠️  No relationships found for vault {vault_id}")

        # Total count
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM {schema}.relationships
            WHERE {id_col} = %s;
        """, (vault_id,))
        total = cursor.fetchone()['count']
        print(f"\nTotal relationships: {total}")

    # =========================================================================
    # TASK 5: Report findings
    # =========================================================================
    print("\n" + "=" * 100)
    print("TASK 5: FINDINGS SUMMARY")
    print("=" * 100 + "\n")

    # ─────────────────────────────────────────────────────────────────────────
    # Table Existence Summary
    # ─────────────────────────────────────────────────────────────────────────
    print("TABLE EXISTENCE:")
    print("─" * 50)
    for table, exists in existing_tables.items():
        status = "✓ EXISTS" if exists else "✗ MISSING"
        print(f"  {status:12} {table}")

    # ─────────────────────────────────────────────────────────────────────────
    # Split-Brain Analysis
    # ─────────────────────────────────────────────────────────────────────────
    print("\n\nSPLIT-BRAIN ANALYSIS:")
    print("─" * 50)

    has_split_brain = False
    split_brain_issues = []

    # Check documents split-brain
    if existing_tables['platform.documents'] and existing_tables['public.documents']:
        print("\n⚠️  WARNING: Both platform.documents AND public.documents exist!")

        if 'platform' in document_data and 'public' in document_data:
            plat_count = document_data['platform']['count']
            pub_count = document_data['public']['count']

            if plat_count != pub_count:
                has_split_brain = True
                split_brain_issues.append(
                    f"❌ SPLIT-BRAIN CONFIRMED: Document count mismatch!\n"
                    f"   platform.documents: {plat_count} documents\n"
                    f"   public.documents: {pub_count} documents\n"
                    f"   Difference: {abs(plat_count - pub_count)} documents"
                )
            else:
                print(f"   Document counts match: {plat_count} documents")
                print("   (However, using two separate tables is still risky)")

    elif existing_tables['platform.documents']:
        print("\n✓  Only platform.documents exists")
        print("   This is expected for newer schema architecture")

    elif existing_tables['public.documents']:
        print("\n⚠️  Only public.documents exists")
        print("   This may indicate older schema or incomplete migration")

    else:
        has_split_brain = True
        split_brain_issues.append("❌ CRITICAL: No documents table found in either schema!")

    # Check entities split-brain
    if existing_tables['platform.entities'] and existing_tables['public.entities']:
        print("\n⚠️  WARNING: Both platform.entities AND public.entities exist!")
        has_split_brain = True

    # Check relationships split-brain
    if existing_tables['platform.relationships'] and existing_tables['public.relationships']:
        print("\n⚠️  WARNING: Both platform.relationships AND public.relationships exist!")
        has_split_brain = True

    # ─────────────────────────────────────────────────────────────────────────
    # Staging vs Trusted Analysis
    # ─────────────────────────────────────────────────────────────────────────
    print("\n\nSTAGING VS TRUSTED STATUS:")
    print("─" * 50)

    staging_issues = []

    for schema in ['platform', 'public']:
        if schema in entity_data and entity_data[schema]:
            staging_count = 0
            trusted_count = 0

            for row in entity_data[schema]:
                stage_value = str(row[0]).lower()
                if 'staging' in stage_value:
                    staging_count = row['count']
                elif 'trusted' in stage_value:
                    trusted_count = row['count']

            if staging_count > 0 and trusted_count == 0:
                staging_issues.append(
                    f"⚠️  {schema}.entities: {staging_count} entities in STAGING, NONE in TRUSTED\n"
                    f"   → Promotion/verification pipeline did not execute"
                )

        if schema in relationship_data and relationship_data[schema]:
            staging_count = 0
            trusted_count = 0

            for row in relationship_data[schema]:
                stage_value = str(row[0]).lower()
                if 'staging' in stage_value:
                    staging_count = row['count']
                elif 'trusted' in stage_value:
                    trusted_count = row['count']

            if staging_count > 0 and trusted_count == 0:
                staging_issues.append(
                    f"⚠️  {schema}.relationships: {staging_count} relationships in STAGING, NONE in TRUSTED\n"
                    f"   → Promotion/verification pipeline did not execute"
                )

    if staging_issues:
        for issue in staging_issues:
            print(f"\n{issue}")
    else:
        print("\n✓  No staging promotion issues detected")

    # ─────────────────────────────────────────────────────────────────────────
    # Column Name Reference
    # ─────────────────────────────────────────────────────────────────────────
    print("\n\nACTUAL COLUMN NAMES TO USE IN CODE:")
    print("─" * 50)

    for table, exists in existing_tables.items():
        if exists and table in schema_info:
            print(f"\n{table}:")

            # Highlight key columns
            key_columns = []
            for col in schema_info[table]:
                if col in ['id', 'tenant_id', 'vault_id', 'stage', 'status', 'name']:
                    key_columns.append(col)

            if key_columns:
                print(f"  Key columns: {', '.join(key_columns)}")

    # ─────────────────────────────────────────────────────────────────────────
    # Final Verdict
    # ─────────────────────────────────────────────────────────────────────────
    print("\n\n" + "=" * 100)
    print("FINAL VERDICT")
    print("=" * 100 + "\n")

    if has_split_brain:
        print("❌ SPLIT-BRAIN DETECTED\n")
        for issue in split_brain_issues:
            print(issue)
            print()
    else:
        print("✓  No split-brain detected at table count level")
        print("   (Still verify data consistency if both schemas exist)\n")

    if staging_issues:
        print("⚠️  STAGING PROMOTION ISSUES DETECTED\n")
    else:
        print("✓  No staging promotion issues\n")

    # ─────────────────────────────────────────────────────────────────────────
    # Recommendations
    # ─────────────────────────────────────────────────────────────────────────
    print("\nRECOMMENDATIONS:")
    print("─" * 50)

    if has_split_brain or (existing_tables['platform.documents'] and existing_tables['public.documents']):
        print("\n1. ❌ Choose ONE authoritative schema:")
        print("   - Option A: Consolidate on platform.documents (recommended for newer deployments)")
        print("   - Option B: Consolidate on public.documents (if using older schema)")
        print("   - Update all code to use consistent schema")
        print("\n2. 🔍 Analyze codebase usage:")
        print(f"   - Files using platform.documents: ~57 SELECT statements, ~15 UPDATE statements")
        print(f"   - Files using public.documents: ~8 SELECT statements, ~0 UPDATE statements")
        print(f"   - Recommendation: Migrate to platform.documents (more actively maintained)")
        print("\n3. 🔧 Implementation steps:")
        print("   a. Audit all SQL queries in codebase")
        print("   b. Update queries to use chosen schema")
        print("   c. Test extraction pipeline end-to-end")
        print("   d. Consider dropping deprecated table after verification")

    if staging_issues:
        print("\n4. 🔄 Fix staging promotion pipeline:")
        print("   - Verify that verification/promotion workflows are enabled")
        print("   - Check for errors in promotion logic")
        print("   - Ensure entities/relationships progress from staging → trusted")

    print("\n5. 📊 Monitor and validate:")
    print("   - Run this script regularly to detect split-brain")
    print("   - Add automated consistency checks before extraction runs")
    print("   - Implement cross-table validation in CI/CD")

    cursor.close()
    conn.close()

    print("\n" + "=" * 100)
    print("INVESTIGATION COMPLETE")
    print("=" * 100 + "\n")

    # Exit with appropriate code
    if has_split_brain:
        sys.exit(1)
    elif staging_issues:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
