#!/usr/bin/env python3
"""
Session 4: Threshold seeding script for Infrastructure domain types.

Categorizes 28 entity types by risk level and seeds promotion_thresholds table
with appropriate values:
- CRITICAL: Nuclear, permits, safety reports (strict: 0.90/3/6h)
- HIGH: Power plants, ports, airports (0.85/2/4h)  
- MEDIUM: Events, maintenance, inspections (0.80/2/2h)
- LOW: Equipment, wagons, vessels (0.75/1/1h)

Usage:
    python scripts/seed_infra_thresholds.py [--dry-run]
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.context_foundry.models.schema import get_session

RISK_CATEGORIES = {
    "CRITICAL": {
        "min_confidence": 0.90,
        "min_corroboration_count": 3,
        "min_staging_hours": 6,
        "types": [
            "NuclearReactor",
            "Permit",
            "SafetyReport",
            "EnvironmentalAssessment",
        ]
    },
    "HIGH": {
        "min_confidence": 0.85,
        "min_corroboration_count": 2,
        "min_staging_hours": 4,
        "types": [
            "PowerPlant",
            "DesalinationPlant",
            "Airport",
            "Port",
            "ControlCenter",
            "PurchaseAgreement",
        ]
    },
    "MEDIUM": {
        "min_confidence": 0.80,
        "min_corroboration_count": 2,
        "min_staging_hours": 2,
        "types": [
            "Outage",
            "MaintenanceEvent",
            "Inspection",
            "VesselCall",
            "Substation",
            "TransmissionLine",
            "Pipeline",
            "RailwayLine",
            "Station",
            "Terminal",
            "WasteProcessingFacility",
        ]
    },
    "LOW": {
        "min_confidence": 0.75,
        "min_corroboration_count": 1,
        "min_staging_hours": 1,
        "types": [
            "Berth",
            "Vessel",
            "Crane",
            "Runway",
            "Locomotive",
            "Wagon",
            "MaintenanceDepot",
        ]
    }
}


def get_type_id_map(session) -> dict:
    """Fetch type_name -> id mapping from ontology_types."""
    result = session.execute(text("""
        SELECT id, type_name 
        FROM ontology_types 
        WHERE id::text LIKE '20000000-0001%'
    """))
    return {row.type_name: str(row.id) for row in result}


def seed_thresholds(session, dry_run: bool = False) -> dict:
    """Seed promotion_thresholds for infrastructure types."""
    type_id_map = get_type_id_map(session)
    
    stats = {
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "errors": []
    }
    
    print(f"\n{'='*60}")
    print(f"Infrastructure Threshold Seeding")
    print(f"{'='*60}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Found {len(type_id_map)} infrastructure types in database")
    print()
    
    for category, config in RISK_CATEGORIES.items():
        print(f"\n{category} ({config['min_confidence']}/{config['min_corroboration_count']}/{config['min_staging_hours']}h):")
        
        for type_name in config["types"]:
            type_id = type_id_map.get(type_name)
            
            if not type_id:
                print(f"  WARNING: {type_name} not found in ontology_types")
                stats["errors"].append(f"{type_name} not found")
                continue
            
            existing = session.execute(text("""
                SELECT id FROM promotion_thresholds 
                WHERE entity_type_name = :type_name
            """), {"type_name": type_name}).fetchone()
            
            if existing:
                if not dry_run:
                    session.execute(text("""
                        UPDATE promotion_thresholds SET
                            min_confidence = :conf,
                            min_corroboration_count = :corrob,
                            min_staging_hours = :hours,
                            updated_at = NOW()
                        WHERE entity_type_name = :type_name
                    """), {
                        "type_name": type_name,
                        "conf": config["min_confidence"],
                        "corrob": config["min_corroboration_count"],
                        "hours": config["min_staging_hours"]
                    })
                print(f"  UPDATED: {type_name}")
                stats["updated"] += 1
            else:
                if not dry_run:
                    session.execute(text("""
                        INSERT INTO promotion_thresholds 
                        (entity_type_name, entity_type_id, min_confidence, min_corroboration_count, min_staging_hours, is_default)
                        VALUES (:type_name, :type_id, :conf, :corrob, :hours, false)
                    """), {
                        "type_name": type_name,
                        "type_id": type_id,
                        "conf": config["min_confidence"],
                        "corrob": config["min_corroboration_count"],
                        "hours": config["min_staging_hours"]
                    })
                print(f"  INSERTED: {type_name}")
                stats["inserted"] += 1
    
    if not dry_run:
        session.commit()
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Inserted: {stats['inserted']}")
    print(f"  Updated: {stats['updated']}")
    print(f"  Errors: {len(stats['errors'])}")
    if stats["errors"]:
        for err in stats["errors"]:
            print(f"    - {err}")
    print(f"{'='*60}\n")
    
    return stats


def verify_thresholds(session):
    """Verify thresholds were seeded correctly."""
    result = session.execute(text("""
        SELECT entity_type_name, min_confidence, min_corroboration_count, min_staging_hours
        FROM promotion_thresholds
        WHERE entity_type_name IN (
            SELECT type_name FROM ontology_types WHERE id::text LIKE '20000000-0001%'
        )
        ORDER BY min_confidence DESC, entity_type_name
    """))
    
    rows = list(result)
    print(f"\nVerification: {len(rows)} infrastructure thresholds configured")
    
    for row in rows:
        print(f"  {row.entity_type_name}: conf={row.min_confidence}, "
              f"corrob={row.min_corroboration_count}, hours={row.min_staging_hours}")
    
    return len(rows)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Seed promotion thresholds for infrastructure types")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()
    
    session = get_session()
    
    try:
        stats = seed_thresholds(session, dry_run=args.dry_run)
        
        if not args.dry_run:
            count = verify_thresholds(session)
            
            if count < 28:
                print(f"WARNING: Only {count}/28 infrastructure types have thresholds")
            else:
                print(f"SUCCESS: All 28 infrastructure types have thresholds")
    finally:
        session.close()


if __name__ == "__main__":
    main()
