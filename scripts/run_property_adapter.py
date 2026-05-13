#!/usr/bin/env python3
"""Run the Property Adapter to materialize entity.properties into property_facts (Stage 3A M2).

Usage:
    python scripts/run_property_adapter.py --tenant-id <uuid>
    python scripts/run_property_adapter.py --tenant-id <uuid> --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Run Property Adapter: entity.properties → property_facts"
    )
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse only, do not write to property_facts",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for entity fetching (default: 100)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    from src.context_foundry.models.schema import get_session, set_tenant_context
    from src.context_foundry.adapters.property_adapter import PropertyAdapter
    from src.context_foundry.memory.property_store import PropertyStore

    session = get_session()
    set_tenant_context(session, args.tenant_id)

    adapter = PropertyAdapter(session, args.tenant_id)

    if args.dry_run:
        print("=== DRY RUN: parsing only, no writes ===\n")
        report = adapter.adapt_all(batch_size=args.batch_size)
        print("\n=== Dry Run Results ===")
        for etype, count in sorted(report.items()):
            print(f"  {etype}: {count} facts")
        print(f"\n  Total: {sum(report.values())} facts")
    else:
        store = PropertyStore(session, args.tenant_id)
        report = adapter.adapt_and_store(store, batch_size=args.batch_size)
        print("\n=== Upsert Results ===")
        for etype, count in sorted(report.items()):
            print(f"  {etype}: {count} facts upserted")
        print(f"\n  Total: {sum(report.values())} facts upserted")

    session.close()


if __name__ == "__main__":
    main()
