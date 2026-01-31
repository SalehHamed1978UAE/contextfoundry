#!/usr/bin/env python3
"""
Session 4: Orphan entity cleanup script.

Identifies and handles entities with invalid or missing type references:
1. Entities with entity_type not matching any ontology_types.type_name
2. Relationships with source/target entities that no longer exist
3. Relationships referencing invalid source_type_id/target_type_id

Usage:
    python scripts/cleanup_orphans.py [--dry-run] [--fix]
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.context_foundry.models.schema import get_session


def find_orphan_entities(session) -> list:
    """Find entities with entity_type not in ontology_types."""
    result = session.execute(text("""
        SELECT e.id, e.name, e.entity_type, e.lifecycle_state, e.created_at
        FROM entities e
        LEFT JOIN ontology_types ot ON LOWER(e.entity_type) = LOWER(ot.type_name)
        WHERE ot.id IS NULL
        ORDER BY e.created_at DESC
    """))
    return list(result)


def find_orphan_relationships(session) -> list:
    """Find relationships where source or target entity doesn't exist."""
    result = session.execute(text("""
        SELECT r.id, r.relationship_type, 
               r.source_id, r.target_id,
               se.name as source_name, te.name as target_name
        FROM relationships r
        LEFT JOIN entities se ON r.source_id = se.id
        LEFT JOIN entities te ON r.target_id = te.id
        WHERE se.id IS NULL OR te.id IS NULL
    """))
    return list(result)


def find_invalid_relationship_types(session) -> list:
    """Find relationships with types not in ontology_relations."""
    result = session.execute(text("""
        SELECT r.id, r.relationship_type, 
               se.name as source_name, te.name as target_name
        FROM relationships r
        JOIN entities se ON r.source_id = se.id
        JOIN entities te ON r.target_id = te.id
        LEFT JOIN ontology_relations orr ON LOWER(r.relationship_type) = LOWER(orr.relation_name)
        WHERE orr.id IS NULL
    """))
    return list(result)


def quarantine_orphan_entities(session, orphans: list, dry_run: bool = True) -> int:
    """Mark orphan entities as ARCHIVED (quarantine, not delete)."""
    if dry_run or not orphans:
        return 0
    
    entity_ids = [str(o.id) for o in orphans]
    
    session.execute(text("""
        UPDATE entities 
        SET lifecycle_state = 'ARCHIVED',
            properties = jsonb_set(
                COALESCE(properties, '{}'::jsonb),
                '{_quarantine_reason}',
                '"orphan_invalid_type"'
            ),
            updated_at = NOW()
        WHERE id = ANY(:ids::uuid[])
    """), {"ids": entity_ids})
    
    return len(entity_ids)


def delete_orphan_relationships(session, orphans: list, dry_run: bool = True) -> int:
    """Delete relationships with missing source/target entities."""
    if dry_run or not orphans:
        return 0
    
    rel_ids = [str(o.id) for o in orphans]
    
    session.execute(text("""
        DELETE FROM relationships WHERE id = ANY(:ids::uuid[])
    """), {"ids": rel_ids})
    
    return len(rel_ids)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Find and cleanup orphan entities/relationships")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't fix")
    parser.add_argument("--fix", action="store_true", help="Apply fixes (quarantine/delete)")
    args = parser.parse_args()
    
    if args.fix and args.dry_run:
        print("ERROR: Cannot use both --dry-run and --fix")
        sys.exit(1)
    
    session = get_session()
    
    try:
        print(f"\n{'='*60}")
        print(f"Orphan Detection & Cleanup")
        print(f"{'='*60}")
        print(f"Mode: {'FIX' if args.fix else 'SCAN ONLY'}")
        print()
        
        orphan_entities = find_orphan_entities(session)
        print(f"\n1. Orphan Entities (invalid entity_type): {len(orphan_entities)}")
        for o in orphan_entities[:10]:
            print(f"   - {o.name} (type={o.entity_type}, state={o.lifecycle_state})")
        if len(orphan_entities) > 10:
            print(f"   ... and {len(orphan_entities) - 10} more")
        
        orphan_rels = find_orphan_relationships(session)
        print(f"\n2. Orphan Relationships (missing entities): {len(orphan_rels)}")
        for o in orphan_rels[:10]:
            src = o.source_name or "MISSING"
            tgt = o.target_name or "MISSING"
            print(f"   - {src} --[{o.relationship_type}]--> {tgt}")
        if len(orphan_rels) > 10:
            print(f"   ... and {len(orphan_rels) - 10} more")
        
        invalid_rel_types = find_invalid_relationship_types(session)
        print(f"\n3. Invalid Relationship Types: {len(invalid_rel_types)}")
        for o in invalid_rel_types[:10]:
            print(f"   - {o.source_name} --[{o.relationship_type}]--> {o.target_name}")
        if len(invalid_rel_types) > 10:
            print(f"   ... and {len(invalid_rel_types) - 10} more")
        
        if args.fix:
            print(f"\n{'='*60}")
            print("Applying Fixes...")
            print(f"{'='*60}")
            
            fixed_entities = quarantine_orphan_entities(session, orphan_entities, dry_run=False)
            print(f"  Quarantined entities: {fixed_entities}")
            
            deleted_rels = delete_orphan_relationships(session, orphan_rels, dry_run=False)
            print(f"  Deleted orphan relationships: {deleted_rels}")
            
            session.commit()
            print("\nChanges committed.")
        else:
            print(f"\n{'='*60}")
            print("Summary (no changes made)")
            print(f"{'='*60}")
            total = len(orphan_entities) + len(orphan_rels) + len(invalid_rel_types)
            if total > 0:
                print(f"  Found {total} issues. Run with --fix to apply corrections.")
            else:
                print("  No orphans found. Database is clean.")
        
        print()
        
    finally:
        session.close()


if __name__ == "__main__":
    main()
