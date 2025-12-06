#!/usr/bin/env python3
"""
Session 4: FK-safe Sequential Cleanup Runner.

Orchestrates data cleanup scripts in the correct order to avoid FK violations:
1. Orphan relationships (delete references to missing entities)
2. Orphan entities (quarantine entities with invalid types)
3. Stale staging (demote stuck entities)
4. Verification pass (confirm graph health)

Usage:
    python scripts/cleanup_runner.py [--dry-run] [--fix] [--verbose]
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.context_foundry.models.schema import get_session


class CleanupRunner:
    """Orchestrates cleanup in FK-safe order."""
    
    def __init__(self, session, dry_run: bool = True, verbose: bool = False):
        self.session = session
        self.dry_run = dry_run
        self.verbose = verbose
        self.stats = {
            "orphan_rels_deleted": 0,
            "orphan_entities_quarantined": 0,
            "stale_entities_demoted": 0,
            "errors": []
        }
    
    def log(self, msg: str, level: str = "INFO"):
        """Log with optional verbosity filtering."""
        if level == "DEBUG" and not self.verbose:
            return
        prefix = {"INFO": "  ", "DEBUG": "    ", "WARN": "  ⚠️", "ERROR": "  ❌"}
        print(f"{prefix.get(level, '  ')}{msg}")
    
    def phase_1_orphan_relationships(self):
        """Phase 1: Delete relationships with missing entities."""
        self.log("Phase 1: Orphan Relationships", "INFO")
        
        result = self.session.execute(text("""
            SELECT COUNT(*) as cnt FROM relationships r
            LEFT JOIN entities se ON r.source_id = se.id
            LEFT JOIN entities te ON r.target_id = te.id
            WHERE se.id IS NULL OR te.id IS NULL
        """)).scalar()
        
        self.log(f"Found {result} orphan relationships", "DEBUG")
        
        if result > 0 and not self.dry_run:
            deleted = self.session.execute(text("""
                DELETE FROM relationships r
                USING (
                    SELECT r2.id FROM relationships r2
                    LEFT JOIN entities se ON r2.source_id = se.id
                    LEFT JOIN entities te ON r2.target_id = te.id
                    WHERE se.id IS NULL OR te.id IS NULL
                ) orphans
                WHERE r.id = orphans.id
            """)).rowcount
            self.stats["orphan_rels_deleted"] = deleted
            self.log(f"Deleted {deleted} orphan relationships", "INFO")
        else:
            self.log(f"Would delete {result} orphan relationships", "INFO")
    
    def phase_2_orphan_entities(self):
        """Phase 2: Quarantine entities with invalid types."""
        self.log("Phase 2: Orphan Entities (invalid types)", "INFO")
        
        result = self.session.execute(text("""
            SELECT COUNT(*) as cnt FROM entities e
            LEFT JOIN ontology_types ot ON LOWER(e.entity_type) = LOWER(ot.type_name)
            WHERE ot.id IS NULL
        """)).scalar()
        
        self.log(f"Found {result} entities with invalid types", "DEBUG")
        
        if result > 0 and not self.dry_run:
            updated = self.session.execute(text("""
                UPDATE entities e
                SET lifecycle_state = 'ARCHIVED',
                    properties = jsonb_set(
                        COALESCE(properties, '{}'::jsonb),
                        '{_quarantine_reason}',
                        '"orphan_invalid_type"'
                    ),
                    updated_at = NOW()
                FROM (
                    SELECT e2.id FROM entities e2
                    LEFT JOIN ontology_types ot ON LOWER(e2.entity_type) = LOWER(ot.type_name)
                    WHERE ot.id IS NULL
                ) orphans
                WHERE e.id = orphans.id
            """)).rowcount
            self.stats["orphan_entities_quarantined"] = updated
            self.log(f"Quarantined {updated} orphan entities", "INFO")
        else:
            self.log(f"Would quarantine {result} orphan entities", "INFO")
    
    def phase_3_stale_staging(self, max_days: int = 30):
        """Phase 3: Demote stale STAGING entities."""
        self.log("Phase 3: Stale Staging", "INFO")
        
        result = self.session.execute(text("""
            SELECT COUNT(*) as cnt FROM entities
            WHERE lifecycle_state = 'STAGING'
              AND created_at < NOW() - INTERVAL '1 day' * :days
        """), {"days": max_days}).scalar()
        
        self.log(f"Found {result} stale staging entities (>{max_days} days)", "DEBUG")
        
        if result > 0 and not self.dry_run:
            updated = self.session.execute(text("""
                UPDATE entities
                SET lifecycle_state = 'ARCHIVED',
                    properties = jsonb_set(
                        COALESCE(properties, '{}'::jsonb),
                        '{_demotion_reason}',
                        '"stale_staging"'
                    ),
                    updated_at = NOW()
                WHERE lifecycle_state = 'STAGING'
                  AND created_at < NOW() - INTERVAL '1 day' * :days
            """), {"days": max_days}).rowcount
            self.stats["stale_entities_demoted"] = updated
            self.log(f"Demoted {updated} stale entities", "INFO")
        else:
            self.log(f"Would demote {result} stale entities", "INFO")
    
    def phase_4_verify(self):
        """Phase 4: Verify graph health after cleanup."""
        self.log("Phase 4: Verification", "INFO")
        
        counts = {}
        
        result = self.session.execute(text("""
            SELECT lifecycle_state, COUNT(*) as cnt 
            FROM entities 
            GROUP BY lifecycle_state 
            ORDER BY cnt DESC
        """))
        counts["entities_by_state"] = {row.lifecycle_state: row.cnt for row in result}
        
        result = self.session.execute(text("""
            SELECT lifecycle_state, COUNT(*) as cnt 
            FROM relationships 
            GROUP BY lifecycle_state 
            ORDER BY cnt DESC
        """))
        counts["relationships_by_state"] = {row.lifecycle_state: row.cnt for row in result}
        
        result = self.session.execute(text("""
            SELECT COUNT(*) FROM entities e
            LEFT JOIN ontology_types ot ON LOWER(e.entity_type) = LOWER(ot.type_name)
            WHERE ot.id IS NULL AND e.lifecycle_state NOT IN ('ARCHIVED')
        """)).scalar()
        counts["remaining_orphans"] = result
        
        self.log(f"Entity states: {counts['entities_by_state']}", "DEBUG")
        self.log(f"Relationship states: {counts['relationships_by_state']}", "DEBUG")
        
        if counts["remaining_orphans"] > 0:
            self.log(f"WARNING: {counts['remaining_orphans']} orphan entities remain active", "WARN")
        else:
            self.log("Graph health: OK (no active orphans)", "INFO")
        
        return counts
    
    def run(self, max_staging_days: int = 30):
        """Execute all cleanup phases in order."""
        print(f"\n{'='*60}")
        print(f"FK-Safe Sequential Cleanup")
        print(f"{'='*60}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"Time: {datetime.utcnow().isoformat()}")
        print()
        
        try:
            self.phase_1_orphan_relationships()
            self.phase_2_orphan_entities()
            self.phase_3_stale_staging(max_days=max_staging_days)
            
            if not self.dry_run:
                self.session.commit()
                print("\n✓ All changes committed")
            
            self.phase_4_verify()
            
        except Exception as e:
            self.stats["errors"].append(str(e))
            self.session.rollback()
            print(f"\n❌ Error: {e}")
            raise
        
        print(f"\n{'='*60}")
        print("Summary")
        print(f"{'='*60}")
        print(f"  Orphan relationships deleted: {self.stats['orphan_rels_deleted']}")
        print(f"  Orphan entities quarantined: {self.stats['orphan_entities_quarantined']}")
        print(f"  Stale entities demoted: {self.stats['stale_entities_demoted']}")
        print(f"  Errors: {len(self.stats['errors'])}")
        print()
        
        return self.stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="FK-safe sequential cleanup runner")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't apply changes")
    parser.add_argument("--fix", action="store_true", help="Apply all cleanup phases")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("--max-staging-days", type=int, default=30, help="Max days in STAGING")
    args = parser.parse_args()
    
    if args.fix and args.dry_run:
        print("ERROR: Cannot use both --dry-run and --fix")
        sys.exit(1)
    
    session = get_session()
    
    try:
        runner = CleanupRunner(
            session=session,
            dry_run=not args.fix,
            verbose=args.verbose
        )
        runner.run(max_staging_days=args.max_staging_days)
    finally:
        session.close()


if __name__ == "__main__":
    main()
