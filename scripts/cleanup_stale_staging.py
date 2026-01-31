#!/usr/bin/env python3
"""
Session 4: Stale staging cleanup script.

Handles STAGING entities that have exceeded configurable thresholds:
1. Entities in STAGING longer than max_staging_days (default: 30 days)
2. Entities with low confidence that haven't gained corroboration
3. Entities stuck due to unresolved conflicts

Actions:
- DEMOTE: Move to DEPRECATED state with reason
- NOTIFY: Generate report of stuck entities
- DELETE: Permanent removal (requires --force)

Usage:
    python scripts/cleanup_stale_staging.py [--max-days 30] [--dry-run] [--fix]
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.context_foundry.models.schema import get_session


def find_stale_staging(session, max_days: int = 30) -> list:
    """Find STAGING entities older than max_days."""
    cutoff = datetime.utcnow() - timedelta(days=max_days)
    
    result = session.execute(text("""
        SELECT e.id, e.name, e.entity_type, e.confidence, 
               e.created_at, e.validation_status,
               EXTRACT(DAY FROM (NOW() - e.created_at)) as age_days
        FROM entities e
        WHERE e.lifecycle_state = 'STAGING'
          AND e.created_at < :cutoff
        ORDER BY e.created_at ASC
    """), {"cutoff": cutoff})
    return list(result)


def find_low_confidence_stuck(session, min_confidence: float = 0.5, max_days: int = 7) -> list:
    """Find STAGING entities with low confidence stuck for too long."""
    cutoff = datetime.utcnow() - timedelta(days=max_days)
    
    result = session.execute(text("""
        SELECT e.id, e.name, e.entity_type, e.confidence, 
               e.created_at, e.validation_status,
               EXTRACT(DAY FROM (NOW() - e.created_at)) as age_days
        FROM entities e
        WHERE e.lifecycle_state = 'STAGING'
          AND e.confidence < :min_conf
          AND e.created_at < :cutoff
        ORDER BY e.confidence ASC
    """), {"min_conf": min_confidence, "cutoff": cutoff})
    return list(result)


def find_validation_failed(session) -> list:
    """Find STAGING entities that failed validation."""
    result = session.execute(text("""
        SELECT e.id, e.name, e.entity_type, e.confidence, 
               e.created_at, e.validation_status,
               EXTRACT(DAY FROM (NOW() - e.created_at)) as age_days
        FROM entities e
        WHERE e.lifecycle_state = 'STAGING'
          AND e.validation_status = 'INVALID'
        ORDER BY e.created_at ASC
    """))
    return list(result)


def demote_stale_entities(session, entities: list, reason: str, dry_run: bool = True) -> int:
    """Demote stale entities to ARCHIVED state."""
    if dry_run or not entities:
        return 0
    
    entity_ids = [str(e.id) for e in entities]
    
    session.execute(text("""
        UPDATE entities 
        SET lifecycle_state = 'ARCHIVED',
            properties = jsonb_set(
                COALESCE(properties, '{}'::jsonb),
                '{_demotion_reason}',
                :reason::jsonb
            ),
            updated_at = NOW()
        WHERE id = ANY(:ids::uuid[])
    """), {"ids": entity_ids, "reason": f'"{reason}"'})
    
    return len(entity_ids)


def generate_stuck_report(stale: list, low_conf: list, failed: list) -> str:
    """Generate a report of stuck entities."""
    report = []
    report.append("="*60)
    report.append("STALE STAGING REPORT")
    report.append(f"Generated: {datetime.utcnow().isoformat()}")
    report.append("="*60)
    
    if stale:
        report.append(f"\n## Stale Entities (>{len(stale)} items)")
        for e in stale[:20]:
            report.append(f"  - {e.name} ({e.entity_type}): "
                         f"age={int(e.age_days)}d, conf={e.confidence:.2f}")
    
    if low_conf:
        report.append(f"\n## Low Confidence Stuck ({len(low_conf)} items)")
        for e in low_conf[:20]:
            report.append(f"  - {e.name} ({e.entity_type}): "
                         f"conf={e.confidence:.2f}, age={int(e.age_days)}d")
    
    if failed:
        report.append(f"\n## Validation Failed ({len(failed)} items)")
        for e in failed[:20]:
            report.append(f"  - {e.name} ({e.entity_type}): "
                         f"status={e.validation_status}")
    
    report.append("")
    return "\n".join(report)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Cleanup stale STAGING entities")
    parser.add_argument("--max-days", type=int, default=30, help="Max days in STAGING (default: 30)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't fix")
    parser.add_argument("--fix", action="store_true", help="Apply fixes (demote stale)")
    parser.add_argument("--report", action="store_true", help="Generate detailed report")
    args = parser.parse_args()
    
    if args.fix and args.dry_run:
        print("ERROR: Cannot use both --dry-run and --fix")
        sys.exit(1)
    
    session = get_session()
    
    try:
        print(f"\n{'='*60}")
        print(f"Stale Staging Cleanup")
        print(f"{'='*60}")
        print(f"Mode: {'FIX' if args.fix else 'SCAN ONLY'}")
        print(f"Max staging age: {args.max_days} days")
        print()
        
        stale = find_stale_staging(session, max_days=args.max_days)
        print(f"\n1. Stale Entities (>{args.max_days} days): {len(stale)}")
        for e in stale[:5]:
            print(f"   - {e.name} ({e.entity_type}): age={int(e.age_days)}d")
        if len(stale) > 5:
            print(f"   ... and {len(stale) - 5} more")
        
        low_conf = find_low_confidence_stuck(session)
        print(f"\n2. Low Confidence Stuck (conf<0.5, >7d): {len(low_conf)}")
        for e in low_conf[:5]:
            print(f"   - {e.name} ({e.entity_type}): conf={e.confidence:.2f}")
        if len(low_conf) > 5:
            print(f"   ... and {len(low_conf) - 5} more")
        
        failed = find_validation_failed(session)
        print(f"\n3. Validation Failed: {len(failed)}")
        for e in failed[:5]:
            print(f"   - {e.name} ({e.entity_type}): status={e.validation_status}")
        if len(failed) > 5:
            print(f"   ... and {len(failed) - 5} more")
        
        if args.report:
            report = generate_stuck_report(stale, low_conf, failed)
            print(report)
        
        if args.fix:
            print(f"\n{'='*60}")
            print("Applying Fixes...")
            print(f"{'='*60}")
            
            demoted_stale = demote_stale_entities(session, stale, "stale_staging", dry_run=False)
            print(f"  Demoted stale entities: {demoted_stale}")
            
            demoted_failed = demote_stale_entities(session, failed, "validation_failed", dry_run=False)
            print(f"  Demoted failed validation: {demoted_failed}")
            
            session.commit()
            print("\nChanges committed.")
        else:
            total = len(stale) + len(low_conf) + len(failed)
            print(f"\n{'='*60}")
            print("Summary (no changes made)")
            print(f"{'='*60}")
            if total > 0:
                print(f"  Found {total} stale/stuck entities. Run with --fix to demote.")
            else:
                print("  No stale entities found. Staging is healthy.")
        
        print()
        
    finally:
        session.close()


if __name__ == "__main__":
    main()
