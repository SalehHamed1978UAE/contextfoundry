"""
Backfill missing relationships deterministically (no LLM calls).

Three passes — each only fires when both ends share a source_document_id and
no edge of the target type already connects them:

    Pass 1  HOLDS_ROLE  PERSON  -> ROLE
    Pass 2  HAS_SPEC    PRODUCT|PROJECT|COMPONENT -> SPECIFICATION
    Pass 3  INVOLVES    INCIDENT|EVENT  -> ORGANIZATION

Provenance: the new edge inherits source_sentence + source_document_id from
the source-side entity (the one whose row is more specific, e.g. PERSON for
HOLDS_ROLE). Edge confidence is set to 0.6 to mark it as a deterministic
co-occurrence inference rather than LLM-extracted.

Usage:
    python -m scripts.backfill_missing_relationships --tenant-id <UUID> [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from typing import Iterable, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values


PASSES: list[Tuple[str, str, list[str], list[str]]] = [
    # (label, edge_type, source_entity_types, target_entity_types)
    ("HOLDS_ROLE", "HOLDS_ROLE", ["PERSON"], ["ROLE"]),
    ("HAS_SPEC", "HAS_SPEC", ["PRODUCT", "PROJECT", "COMPONENT"], ["SPECIFICATION"]),
    ("INVOLVES", "INVOLVES", ["INCIDENT", "EVENT"], ["ORGANIZATION"]),
]

INFERENCE_CONFIDENCE = 0.6


def fetch_candidate_pairs(
    cur,
    tenant_id: str,
    edge_type: str,
    source_types: list[str],
    target_types: list[str],
) -> list[dict]:
    """Return co-occurring (source_entity, target_entity) pairs that don't yet
    have an edge of `edge_type` between them, sharing source_document_id."""
    cur.execute(
        """
        SELECT
            s.id            AS source_id,
            s.name          AS source_name,
            s.entity_type   AS source_type,
            t.id            AS target_id,
            t.name          AS target_name,
            t.entity_type   AS target_type,
            s.source_document_id AS doc_id,
            COALESCE(s.source_sentence, t.source_sentence) AS source_sentence,
            s.source_section AS source_section
        FROM entities s
        JOIN entities t
          ON t.tenant_id = s.tenant_id
         AND t.source_document_id = s.source_document_id
         AND t.id <> s.id
        WHERE s.tenant_id = %(tenant)s
          AND s.entity_type = ANY(%(stypes)s)
          AND t.entity_type = ANY(%(ttypes)s)
          AND s.source_document_id IS NOT NULL
          AND NOT EXISTS (
                SELECT 1 FROM relationships r
                WHERE r.tenant_id = s.tenant_id
                  AND r.relationship_type = %(etype)s
                  AND ((r.source_id = s.id AND r.target_id = t.id)
                    OR (r.source_id = t.id AND r.target_id = s.id))
          )
        """,
        {
            "tenant": tenant_id,
            "stypes": source_types,
            "ttypes": target_types,
            "etype": edge_type,
        },
    )
    return cur.fetchall()


def insert_relationships(cur, tenant_id: str, edge_type: str, pairs: list[dict]) -> int:
    """Bulk-insert deterministic edges. De-duplicates on (source_id, target_id)
    so multiple co-occurring sentences in one doc only produce one edge."""
    seen: set[tuple[str, str]] = set()
    rows = []
    for p in pairs:
        key = (str(p["source_id"]), str(p["target_id"]))
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            (
                str(uuid.uuid4()),
                tenant_id,
                str(p["source_id"]),
                str(p["target_id"]),
                edge_type,
                "STAGING",
                INFERENCE_CONFIDENCE,
                p.get("doc_id"),
                p.get("source_section"),
                (p.get("source_sentence") or "")[:2000],
                f"Auto-derived {edge_type} from shared document co-occurrence "
                f"({p['source_type']} '{p['source_name']}' + "
                f"{p['target_type']} '{p['target_name']}')",
            )
        )
    if not rows:
        return 0

    execute_values(
        cur,
        """
        INSERT INTO relationships (
            id, tenant_id, source_id, target_id, relationship_type,
            lifecycle_state, confidence,
            source_document_id, source_section, source_sentence,
            description
        ) VALUES %s
        """,
        rows,
        template=(
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        ),
    )
    return len(rows)


def total_relationships(cur, tenant_id: str) -> int:
    cur.execute(
        "SELECT COUNT(*) AS c FROM relationships WHERE tenant_id = %s",
        (tenant_id,),
    )
    return cur.fetchone()["c"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tenant-id", required=True, help="Vault / tenant UUID")
    ap.add_argument("--dry-run", action="store_true", help="Compute counts only; do not write")
    ap.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL DSN (defaults to $DATABASE_URL)",
    )
    args = ap.parse_args()

    if not args.database_url:
        print("ERROR: DATABASE_URL not set and --database-url not given", file=sys.stderr)
        return 2

    conn = psycopg2.connect(args.database_url)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    before = total_relationships(cur, args.tenant_id)
    print(f"[BACKFILL] tenant={args.tenant_id}")
    print(f"[BACKFILL] relationships before: {before}")

    grand_total_created = 0
    per_pass_counts: list[tuple[str, int, int]] = []  # (label, candidates, created)

    for label, edge_type, src_types, tgt_types in PASSES:
        print(f"\n[PASS] {label}  ({'+'.join(src_types)} -> {'+'.join(tgt_types)})")
        pairs = fetch_candidate_pairs(cur, args.tenant_id, edge_type, src_types, tgt_types)
        print(f"  candidate (entity_a, entity_b) pairs: {len(pairs)}")

        if args.dry_run:
            unique_pairs = {(str(p["source_id"]), str(p["target_id"])) for p in pairs}
            print(f"  [DRY-RUN] would create up to {len(unique_pairs)} unique edges")
            per_pass_counts.append((label, len(pairs), len(unique_pairs)))
            continue

        created = insert_relationships(cur, args.tenant_id, edge_type, pairs)
        per_pass_counts.append((label, len(pairs), created))
        grand_total_created += created
        print(f"  created {created} new {edge_type} edges")

    if not args.dry_run:
        conn.commit()
    after = total_relationships(cur, args.tenant_id)

    print("\n[BACKFILL] === SUMMARY ===")
    print(f"  before:  {before}")
    print(f"  after:   {after}")
    print(f"  delta:   +{after - before}")
    for label, cand, created in per_pass_counts:
        print(f"  {label:<12} candidates={cand:<6} created={created}")

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
