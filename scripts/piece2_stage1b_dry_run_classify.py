#!/usr/bin/env python3
"""Piece 2 Stage 1B — dry-run classifier preview.

Walks documents in a vault/tenant, runs the SAME classifier that
scripts/run_vault_extraction.py uses at extraction time
(brain.classification_wrapper.classify), and prints the scope decision the
pipeline WOULD take with enforce_scoped_prompts=True. No DB writes, no
extraction. No telemetry rows.

Per signed-off Stage 1B brief Step C — purpose is to preview which docs in
a candidate pilot corpus would take scoped vs skip_failed before committing
to a full pilot run, and to surface the skip_failed rate against the
Decision 5a rollback trigger (>25% → halt).

Usage:
    python scripts/piece2_stage1b_dry_run_classify.py --vault-id <uuid>
    python scripts/piece2_stage1b_dry_run_classify.py --vault-id <uuid> --limit 20
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker

from brain.classification_wrapper import classify as classify_document
from src.context_foundry.extraction.ontology_centric_pipeline import (
    OntologyCentricPipeline,
)
from src.context_foundry.ontology.repository import OntologyRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-id", required=True, help="Tenant/vault UUID")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max docs to inspect (sample for cost control)",
    )
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    rows = session.execute(
        sql_text(
            "SELECT id, original_filename, name FROM platform.documents "
            "WHERE tenant_id = :tid ORDER BY created_at DESC "
            + (f"LIMIT {int(args.limit)}" if args.limit else "")
        ),
        {"tid": args.vault_id},
    ).fetchall()

    if not rows:
        print(f"No documents found for tenant {args.vault_id}")
        session.close()
        return

    pipe = OntologyCentricPipeline(
        session=session,
        tenant_id=args.vault_id,
        enforce_scoped_prompts=True,
        enable_canonicalization=False,
        auto_stage=False,
        enable_job_tracking=False,
    )

    repo = OntologyRepository()

    counts = {
        "scoped": 0,
        "skip_failed_no_metadata": 0,
        "skip_failed_unknown_domain": 0,
        "no_text": 0,
        "classifier_error": 0,
    }
    print(
        f"\n{'doc_id':<40} {'filename':<55} "
        f"{'decision':<28} {'primary_domain':<18} {'#types':<8} {'status'}"
    )
    print("-" * 165)

    for r in rows:
        doc_id, fname, dname = r
        display_name = fname or dname or str(doc_id)

        # Read the same content the pipeline would use — first ~3 chunks.
        chunk_rows = session.execute(
            sql_text(
                "SELECT text FROM document_chunks "
                "WHERE document_id = :doc_id "
                "ORDER BY chunk_index LIMIT 3"
            ),
            {"doc_id": doc_id},
        ).fetchall()
        text_sample = " ".join(c[0] for c in chunk_rows if c[0])[:8000]

        if len(text_sample.strip()) < 50:
            counts["no_text"] += 1
            print(
                f"{str(doc_id)[:38]:<40} {display_name[:53]:<55} "
                f"{'no_text':<28} {'-':<18} {'-':<8} -"
            )
            continue

        # Run the SAME classifier the pipeline will use at extraction time.
        try:
            classification = classify_document(text_sample, filename=display_name)
            metadata = classification.to_dict()
        except Exception as e:
            counts["classifier_error"] += 1
            print(
                f"{str(doc_id)[:38]:<40} {display_name[:53]:<55} "
                f"{'classifier_error':<28} {'-':<18} {'-':<8} {type(e).__name__}"
            )
            continue

        decision = pipe._classify_for_scoped(metadata)
        primary_domain = metadata.get("primary_domain")
        cls_status = metadata.get("classification_status")
        n_types = "-"

        if decision == "scoped":
            domain_types = repo.get_all_types(domain_id=primary_domain)
            if len(domain_types) == 0:
                decision = "skip_failed_unknown_domain"
                counts["skip_failed_unknown_domain"] += 1
                n_types = 0
            else:
                counts["scoped"] += 1
                lists = pipe._load_scoped_extraction_lists(primary_domain)
                n_types = len(lists[0])
        elif decision == "skip_failed":
            decision = "skip_failed_no_metadata"
            counts["skip_failed_no_metadata"] += 1

        print(
            f"{str(doc_id)[:38]:<40} {display_name[:53]:<55} "
            f"{decision:<28} {(primary_domain or '-'):<18} "
            f"{str(n_types):<8} {cls_status or '-'}"
        )

    print("-" * 165)
    print(f"\nSummary: {counts}")
    total = sum(counts.values())
    if total > 0:
        skip_failed_total = (
            counts["skip_failed_no_metadata"]
            + counts["skip_failed_unknown_domain"]
        )
        skip_failed_rate = 100 * skip_failed_total / total
        scoped_rate = 100 * counts["scoped"] / total
        for k, v in counts.items():
            print(f"  {k}: {v} ({100 * v / total:.1f}%)")
        print()
        print(f"  Total docs sampled:       {total}")
        print(f"  Scoped (would extract):   {counts['scoped']} ({scoped_rate:.1f}%)")
        print(f"  Skip-failed total:        {skip_failed_total} ({skip_failed_rate:.1f}%)")
        print(f"  Decision 5a rollback trigger: skip_failed > 25%")
        if skip_failed_rate > 25:
            print(f"  >>> ROLLBACK TRIGGER FIRED: {skip_failed_rate:.1f}% > 25%")
        else:
            print(f"  >>> Below rollback trigger.")

    session.close()


if __name__ == "__main__":
    main()
