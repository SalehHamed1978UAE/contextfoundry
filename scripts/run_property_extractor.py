#!/usr/bin/env python3
"""CLI runner for PropertyExtractor (Stage 3B).

Usage:
    python scripts/run_property_extractor.py \
        --tenant-id <uuid> \
        --batch-size 50 \
        --dry-run           # optional: log without writing

Connects to DB via DATABASE_URL, creates session, runs extraction, prints summary.
"""

import argparse
import logging
import os
import sys

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_property_extractor")


def main():
    parser = argparse.ArgumentParser(description="Stage 3B: Extract property facts from document chunks")
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID")
    parser.add_argument("--batch-size", type=int, default=50, help="Log progress every N entities")
    parser.add_argument("--dry-run", action="store_true", help="Log extractions without writing to DB")
    parser.add_argument("--clean", action="store_true", help="Delete existing facts before extraction")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        from src.context_foundry.memory.property_store import PropertyStore
        from src.context_foundry.extraction.property_extractor import PropertyExtractor

        # Optionally clean existing facts
        if args.clean and not args.dry_run:
            logger.info(f"Cleaning existing property_facts for tenant {args.tenant_id}...")
            store = PropertyStore(session, args.tenant_id)
            deleted = store.delete_tenant_facts()
            logger.info(f"Deleted {deleted} existing facts")

        # Run extraction
        logger.info(f"Starting property extraction for tenant {args.tenant_id} (dry_run={args.dry_run})")
        extractor = PropertyExtractor(session, args.tenant_id, dry_run=args.dry_run)
        report = extractor.extract_all(batch_size=args.batch_size)

        # Print summary
        print("\n" + "=" * 60)
        print("Stage 3B Property Extraction Summary")
        print("=" * 60)
        print(f"Tenant:           {args.tenant_id}")
        print(f"Dry run:          {args.dry_run}")
        print(f"Entities scanned: {report.get('_total_entities', 0)}")
        print(f"Facts extracted:  {report.get('_total_facts_extracted', 0)}")
        print(f"Facts written:    {report.get('_total_facts_written', 0)}")
        print()
        print("By entity type:")
        for key, count in sorted(report.items()):
            if not key.startswith("_"):
                print(f"  {key:30s} {count:5d} facts")
        print("=" * 60)

    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
