#!/usr/bin/env python3
"""
Diagnose why corpus maker vaults are empty (no documents).
Run this in Replit to investigate vault creation issues.
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path

def main():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    vault_name_filter = sys.argv[1] if len(sys.argv) > 1 else 'nexus test again'

    print(f"\n{'='*80}")
    print(f"CORPUS MAKER VAULT DIAGNOSTIC")
    print(f"Filter: {vault_name_filter}")
    print(f"{'='*80}\n")

    with psycopg2.connect(database_url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Find matching vaults
            cur.execute("""
                SELECT id, name, created_at, created_by
                FROM platform.tenants
                WHERE LOWER(name) LIKE %s
                ORDER BY created_at DESC
                LIMIT 5
            """, (f'%{vault_name_filter.lower()}%',))

            vaults = cur.fetchall()

            if not vaults:
                print(f"❌ No vaults found matching '{vault_name_filter}'")
                return

            print(f"Found {len(vaults)} vaults:\n")

            for vault in vaults:
                print(f"{'─'*80}")
                print(f"Vault: {vault['name']}")
                print(f"  ID: {vault['id']}")
                print(f"  Created: {vault['created_at']}")
                print(f"  Created By: {vault['created_by']}")

                # Check documents in platform.documents
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM platform.documents
                    WHERE tenant_id = %s
                """, (vault['id'],))
                doc_count = cur.fetchone()['count']

                print(f"\n  📄 Documents in platform.documents: {doc_count}")

                if doc_count == 0:
                    print("  ❌ EMPTY VAULT - No documents uploaded!")

                    # Check if there are any extraction requests
                    cur.execute("""
                        SELECT COUNT(*) as count
                        FROM platform.extraction_requests
                        WHERE vault_id = %s
                    """, (vault['id'],))
                    req_count = cur.fetchone()['count']
                    print(f"  📋 Extraction requests: {req_count}")

                    # Check corpus registry
                    print("\n  🔍 Checking corpus registry...")
                    try:
                        sys.path.insert(0, str(Path.cwd()))
                        from src.corpus_maker.registry import list_corpora

                        corpora = list_corpora()
                        matched_corpus = None

                        for corpus_name, config in corpora.items():
                            vault_ids = config.get('vault_ids', [])
                            if str(vault['id']) in vault_ids or config.get('vault_id') == str(vault['id']):
                                matched_corpus = (corpus_name, config)
                                break

                        if matched_corpus:
                            corpus_name, config = matched_corpus
                            print(f"  ✓ Found corpus: {corpus_name}")
                            print(f"    Root path: {config.get('root_path')}")

                            # Check if root path exists and has files
                            root_path = config.get('root_path')
                            if root_path:
                                root_dir = Path(root_path)
                                if root_dir.exists():
                                    files = list(root_dir.rglob('*'))
                                    doc_files = [f for f in files if f.is_file() and f.suffix.lower() in {'.pdf', '.docx', '.txt', '.md', '.csv', '.xlsx'}]
                                    print(f"    Files in root path: {len(doc_files)} documents")

                                    if doc_files:
                                        print(f"    ❌ ROOT CAUSE: Documents exist but weren't uploaded!")
                                        print(f"    Sample files:")
                                        for doc_file in doc_files[:5]:
                                            print(f"      - {doc_file.name}")
                                    else:
                                        print(f"    ⚠️  No valid documents found in root path")
                                else:
                                    print(f"    ❌ Root path does not exist: {root_path}")
                            else:
                                print(f"    ⚠️  No root_path configured")
                        else:
                            print(f"  ⚠️  Vault not found in corpus registry")

                    except Exception as e:
                        print(f"  ❌ Error checking corpus registry: {e}")
                else:
                    # Show documents
                    cur.execute("""
                        SELECT name, status, extraction_level, created_at
                        FROM platform.documents
                        WHERE tenant_id = %s
                        ORDER BY created_at
                        LIMIT 10
                    """, (vault['id'],))

                    docs = cur.fetchall()
                    print("\n  Documents:")
                    for doc in docs:
                        print(f"    - {doc['name']}")
                        print(f"      Status: {doc['status']}, Level: {doc['extraction_level']}")

                print()

    print(f"{'='*80}\n")

if __name__ == '__main__':
    main()
