#!/usr/bin/env python3
"""
Run migration 025 to add tree_based_retrieval column to test_runs table.
Run this in Replit to fix the test runner.
"""
import os
import sys
import psycopg2
from pathlib import Path

def main():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    migration_file = Path(__file__).parent / 'src/context_foundry/migrations/025_add_tree_based_retrieval.sql'

    if not migration_file.exists():
        print(f"ERROR: Migration file not found: {migration_file}")
        sys.exit(1)

    print(f"\n{'='*80}")
    print(f"RUNNING MIGRATION 025: Add tree_based_retrieval column")
    print(f"{'='*80}\n")

    # Read migration SQL
    with open(migration_file) as f:
        migration_sql = f.read()

    print("Migration SQL:")
    print("-" * 80)
    print(migration_sql)
    print("-" * 80)
    print()

    # Connect and run migration
    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                # Execute migration
                print("Executing migration...")
                cur.execute(migration_sql)
                conn.commit()
                print("✅ Migration executed successfully!")

                # Verify column was added
                print("\nVerifying column was added...")
                cur.execute("""
                    SELECT column_name, data_type, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'test_runs' AND column_name = 'tree_based_retrieval'
                """)
                result = cur.fetchone()

                if result:
                    print(f"✅ Column exists: {result[0]} ({result[1]}, default: {result[2]})")
                else:
                    print("❌ Column was not created!")
                    sys.exit(1)

                # Show sample of existing test runs
                print("\nChecking existing test runs...")
                cur.execute("""
                    SELECT id, vault_name, tree_based_retrieval, started_at
                    FROM test_runs
                    ORDER BY started_at DESC
                    LIMIT 5
                """)
                rows = cur.fetchall()

                if rows:
                    print(f"\nRecent test runs ({len(rows)}):")
                    for row in rows:
                        print(f"  - {row[1]}: tree_based_retrieval={row[2]} ({row[3]})")
                else:
                    print("  No existing test runs found")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print(f"\n{'='*80}")
    print("✅ Migration 025 complete!")
    print("You can now run tests with tree-based retrieval enabled/disabled.")
    print(f"{'='*80}\n")

if __name__ == '__main__':
    main()
