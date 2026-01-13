#!/usr/bin/env python3
"""
Reset All Vaults - Complete cleanup script for Context Foundry

Deletes ALL vaults and associated data from both platform and public schemas.
Use this before running E2E tests to ensure a clean slate.

Usage:
    python scripts/reset_all_vaults.py
    python scripts/reset_all_vaults.py --demo-only  # Only delete demo vaults
"""

import os
import sys
import argparse
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def reset_all_vaults(demo_only: bool = False):
    """Delete all vaults and associated data."""
    from src.context_foundry.models.schema import get_session
    from sqlalchemy import text
    
    print("=" * 60)
    print("RESET ALL VAULTS")
    print("=" * 60)
    
    with get_session(use_rls_role=False) as session:
        if demo_only:
            vaults = session.execute(text("""
                SELECT id, name FROM platform.tenants WHERE type = 'demo'
            """)).fetchall()
            print(f"Found {len(vaults)} demo vaults to delete")
        else:
            vaults = session.execute(text("""
                SELECT id, name FROM platform.tenants
            """)).fetchall()
            print(f"Found {len(vaults)} total vaults to delete")
        
        if not vaults:
            print("No vaults to delete.")
            return
        
        deleted_count = 0
        for vault_id, vault_name in vaults:
            tid = str(vault_id)
            print(f"\nDeleting vault: {vault_name} ({tid})")
            
            try:
                try:
                    session.execute(text("UPDATE public.entities SET superseded_by = NULL WHERE tenant_id = :tid"), {"tid": tid})
                except:
                    session.rollback()
                
                public_tables = [
                    'entity_mentions',
                    'doc_entity_mentions', 
                    'merge_audits',
                    'relationships',
                    'entities',
                    'document_chunks',
                ]
                for table in public_tables:
                    try:
                        result = session.execute(text(f"DELETE FROM public.{table} WHERE tenant_id = :tid"), {"tid": tid})
                        if result.rowcount > 0:
                            print(f"  Deleted {result.rowcount} rows from public.{table}")
                    except Exception as e:
                        session.rollback()
                
                try:
                    result = session.execute(text("""
                        DELETE FROM platform.extraction_results 
                        WHERE request_id IN (
                            SELECT request_id FROM platform.extraction_requests WHERE tenant_id = :tid
                        )
                    """), {"tid": tid})
                    if result.rowcount > 0:
                        print(f"  Deleted {result.rowcount} rows from platform.extraction_results")
                except Exception as e:
                    session.rollback()
                
                try:
                    result = session.execute(text("""
                        DELETE FROM platform.document_versions 
                        WHERE document_id IN (
                            SELECT id FROM platform.documents WHERE tenant_id = :tid
                        )
                    """), {"tid": tid})
                    if result.rowcount > 0:
                        print(f"  Deleted {result.rowcount} rows from platform.document_versions")
                except Exception as e:
                    session.rollback()
                
                platform_tables = [
                    'extraction_requests',
                    'documents',
                    'user_tenants',
                    'usage_events',
                    'usage_snapshots',
                    'tenant_quotas',
                    'api_keys',
                    'folders',
                    'source_connectors',
                ]
                for table in platform_tables:
                    try:
                        result = session.execute(text(f"DELETE FROM platform.{table} WHERE tenant_id = :tid"), {"tid": tid})
                        if result.rowcount > 0:
                            print(f"  Deleted {result.rowcount} rows from platform.{table}")
                    except Exception as e:
                        session.rollback()
                
                session.execute(text("DELETE FROM platform.tenants WHERE id = :tid"), {"tid": tid})
                session.commit()
                print(f"  Deleted vault record")
                deleted_count += 1
                
                storage_path = f"storage/tenants/{tid}"
                if os.path.exists(storage_path):
                    shutil.rmtree(storage_path)
                    print(f"  Deleted storage: {storage_path}")
            except Exception as e:
                print(f"  ERROR: {e}")
                session.rollback()
    
    print("\n" + "=" * 60)
    print(f"COMPLETE: Deleted {len(vaults)} vaults")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Reset all vaults in Context Foundry")
    parser.add_argument("--demo-only", action="store_true", help="Only delete demo vaults")
    args = parser.parse_args()
    
    reset_all_vaults(demo_only=args.demo_only)


if __name__ == "__main__":
    main()
