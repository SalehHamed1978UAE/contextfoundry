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
import logging
import os
import sys
from pathlib import Path

# Suppress DEBUG noise from httpcore/httpx/openai/litellm BEFORE any imports
# trigger their loggers. Without this the script bloats /tmp logs to 100s of
# MB during full-corpus runs and the sandbox kills the process.
logging.basicConfig(level=logging.WARNING)
for noisy in (
    "httpcore", "httpcore.http11", "httpcore.connection",
    "httpx", "openai", "openai._base_client", "litellm",
    "anthropic", "urllib3",
):
    logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger(noisy).propagate = False

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
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="OFFSET into ORDER BY created_at DESC (for batched runs)",
    )
    parser.add_argument(
        "--output-jsonl",
        type=str,
        default=None,
        help="Append per-doc results as JSON lines for downstream aggregation",
    )
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    sql = (
        "SELECT id, original_filename, name FROM platform.documents "
        "WHERE tenant_id = :tid ORDER BY created_at DESC "
        + (f"LIMIT {int(args.limit)}" if args.limit else "")
        + (f" OFFSET {int(args.offset)}" if args.offset else "")
    )
    rows = session.execute(sql_text(sql), {"tid": args.vault_id}).fetchall()

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

    import json as _json
    jsonl_fp = open(args.output_jsonl, "a") if args.output_jsonl else None

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
            if jsonl_fp:
                jsonl_fp.write(_json.dumps({
                    "doc_id": str(doc_id), "filename": display_name,
                    "decision": "no_text",
                }) + "\n")
                jsonl_fp.flush()
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
            if jsonl_fp:
                jsonl_fp.write(_json.dumps({
                    "doc_id": str(doc_id), "filename": display_name,
                    "decision": "classifier_error", "error": f"{type(e).__name__}: {e}",
                }) + "\n")
                jsonl_fp.flush()
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

        if jsonl_fp:
            jsonl_fp.write(_json.dumps({
                "doc_id": str(doc_id),
                "filename": display_name,
                "decision": decision,
                "primary_domain": primary_domain,
                "document_type": metadata.get("document_type"),
                "classification_status": cls_status,
                "classification_confidence": metadata.get("classification_confidence"),
                "classification_evidence": (metadata.get("classification_evidence") or "")[:200],
                "n_types": n_types if isinstance(n_types, int) else None,
            }) + "\n")
            jsonl_fp.flush()

        print(
            f"{str(doc_id)[:38]:<40} {display_name[:53]:<55} "
            f"{decision:<28} {(primary_domain or '-'):<18} "
            f"{str(n_types):<8} {cls_status or '-'}"
        )

    if jsonl_fp:
        jsonl_fp.close()
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
