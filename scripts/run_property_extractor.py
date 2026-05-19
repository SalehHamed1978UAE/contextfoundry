#!/usr/bin/env python3
"""CLI runner for PropertyExtractor (Stage 3B).

Usage:
    python scripts/run_property_extractor.py \
        --tenant-id <uuid> \
        --batch-size 50 \
        --dry-run           # optional: log without writing
        --entities "Nexus Industries,Quantum Shield"  # optional: only these entities
        --log-file extraction.log  # optional: persist log to file

Connects to DB via DATABASE_URL, creates session, runs extraction, prints summary.
"""

import argparse
import json
import logging
import os
import sys

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logger = logging.getLogger("run_property_extractor")


def main():
    parser = argparse.ArgumentParser(description="Stage 3B: Extract property facts from document chunks")
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID")
    parser.add_argument("--batch-size", type=int, default=50, help="Log progress every N entities")
    parser.add_argument("--dry-run", action="store_true", help="Log extractions without writing to DB")
    parser.add_argument("--clean", action="store_true", help="Delete existing facts before extraction")
    parser.add_argument("--entities", type=str, default=None,
                        help="Comma-separated entity names to process (default: all)")
    parser.add_argument("--log-file", type=str, default="extraction.log",
                        help="Log file path (default: extraction.log)")
    args = parser.parse_args()

    # Set up logging: both console and file
    handlers = [logging.StreamHandler(sys.stdout)]
    if args.log_file:
        handlers.append(logging.FileHandler(args.log_file, mode="w"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    entity_filter = None
    if args.entities:
        entity_filter = set(n.strip() for n in args.entities.split(",") if n.strip())
        logger.info(f"Entity filter: {entity_filter}")

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
            if entity_filter:
                logger.info("--clean ignored when --entities is set (only full clean supported)")
            else:
                logger.info(f"Cleaning existing property_facts for tenant {args.tenant_id}...")
                store = PropertyStore(session, args.tenant_id)
                deleted = store.delete_tenant_facts()
                logger.info(f"Deleted {deleted} existing facts")

        # Run extraction
        logger.info(f"Starting property extraction for tenant {args.tenant_id} (dry_run={args.dry_run})")
        extractor = PropertyExtractor(session, args.tenant_id, dry_run=args.dry_run)
        report = extractor.extract_all(batch_size=args.batch_size, entity_filter=entity_filter)

        # Build summary
        lines = []
        lines.append("")
        lines.append("=" * 60)
        lines.append("Stage 3B Property Extraction Summary")
        lines.append("=" * 60)
        lines.append(f"Tenant:           {args.tenant_id}")
        lines.append(f"Dry run:          {args.dry_run}")
        lines.append(f"Entity filter:    {args.entities or 'ALL'}")
        lines.append(f"Entities scanned: {report.get('_total_entities', 0)}")
        lines.append(f"Facts extracted:  {report.get('_total_facts_extracted', 0)}")
        lines.append(f"Facts written:    {report.get('_total_facts_written', 0)}")
        lines.append(f"Entities failed:  {report.get('_total_entities_failed', 0)}")
        lines.append(f"Entities skipped: {report.get('_total_entities_skipped', 0)}")
        lines.append("")
        lines.append("By entity type:")
        for key, count in sorted(report.items()):
            if not key.startswith("_"):
                lines.append(f"  {key:30s} {count:5d} facts")
        lines.append("=" * 60)

        summary = "\n".join(lines)
        print(summary)
        logger.info(summary)

        # Save report JSON
        report_path = args.log_file.replace(".log", "_report.json") if args.log_file else "extraction_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report saved to {report_path}")

    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
