"""
One-shot backfill: compute name_embedding for entities with NULL embeddings.

Uses OpenAI batch embeddings (100 names per API call) and a single bulk
UPDATE...FROM (VALUES ...) per batch. Suppresses noisy DEBUG/HTTP logs.
"""
import argparse
import logging
import os
import sys
import time
from typing import List

# Silence noisy DEBUG output from openai/httpx/httpcore/sqlalchemy BEFORE imports
for name in ("openai", "openai._base_client", "httpx", "httpcore",
             "sqlalchemy", "sqlalchemy.engine", "urllib3"):
    logging.getLogger(name).setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

from openai import OpenAI
from sqlalchemy import text

from src.context_foundry.models.schema import get_session

EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100


def _client() -> OpenAI:
    api_key = os.environ["OPENAI_API_KEY"]
    base_url = os.environ.get("OPENAI_BASE_URL")
    return OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)


def _embed_batch(client: OpenAI, texts: List[str]) -> List[List[float]]:
    cleaned = [(t or "").strip()[:8000] or " " for t in texts]
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=cleaned)
    return [d.embedding for d in resp.data]


def backfill(tenant_id: str, limit: int) -> dict:
    session = get_session(use_rls_role=False)
    client = _client()
    log = logging.getLogger("backfill")
    stats = {"checked": 0, "embedded": 0, "errors": 0}

    rows = session.execute(text("""
        SELECT id::text AS id, name FROM public.entities
        WHERE tenant_id = :t AND name_embedding IS NULL
        ORDER BY created_at
        LIMIT :lim
    """), {"t": tenant_id, "lim": limit}).fetchall()

    total = len(rows)
    log.info(f"[BACKFILL] {total} entities need embeddings")
    if total == 0:
        return stats

    t0 = time.time()
    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        names = [r.name or "" for r in batch]
        ids = [r.id for r in batch]
        try:
            vecs = _embed_batch(client, names)
        except Exception as e:
            log.error(f"[BACKFILL] embed failed at offset {i}: {e}")
            stats["errors"] += len(batch)
            stats["checked"] += len(batch)
            continue

        # Bulk UPDATE via UNNEST arrays — single round-trip per batch
        ids_arr = ids
        vec_literals = ['[' + ','.join(f'{float(x):.6f}' for x in v) + ']' for v in vecs]
        try:
            session.execute(text("""
                UPDATE public.entities AS e
                SET name_embedding = CAST(t.vec AS vector)
                FROM (SELECT UNNEST(CAST(:ids AS uuid[])) AS id,
                             UNNEST(CAST(:vecs AS text[])) AS vec) AS t
                WHERE e.id = t.id
            """), {"ids": ids_arr, "vecs": vec_literals})
            session.commit()
            stats["embedded"] += len(batch)
        except Exception as e:
            session.rollback()
            log.error(f"[BACKFILL] bulk update failed at offset {i}: {e}")
            stats["errors"] += len(batch)
        stats["checked"] += len(batch)

        elapsed = time.time() - t0
        rate = stats["embedded"] / max(elapsed, 0.001)
        eta = (total - stats["embedded"]) / max(rate, 0.001)
        log.info(f"[BACKFILL] {stats['embedded']}/{total} ({rate:.1f}/s, ETA {eta:.0f}s)")

    log.info(f"[BACKFILL] DONE in {time.time()-t0:.1f}s — {stats}")
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant-id", required=True)
    ap.add_argument("--limit", type=int, default=20000)
    args = ap.parse_args()
    stats = backfill(args.tenant_id, args.limit)
    print("\n=== Backfill Stats ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    sys.exit(0)


if __name__ == "__main__":
    main()
