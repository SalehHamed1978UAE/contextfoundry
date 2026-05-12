# Stage 1K — VerificationWorker Deadlock Fix

**Date:** 2026-05-12
**Brief:** `docs/inbox/stage_1k_verification_worker_fix_2026-05-12.md`
**Target file:** `src/context_foundry/workers/verification_worker.py`
**Validation vault:** `ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda` (clean Stage 1J ingest, 100 docs, 2146 STAGING entities, 2099 STAGING relationships)
**Status:** Code fix applied + unit-tested (8/8) + bounded smoke validated end-to-end. Awaiting sign-off.

---

## Root cause

`VerificationWorker.run()` previously executed the entire run inside a single
session with a single `commit()` at the end (L141 of the prior file). Inside the
loop, `_store_verdict()` issued a `query(FactVerification).first()` lookup; under
SQLAlchemy's default `autoflush=True` semantics this triggered an autoflush of
every dirty row accumulated so far, in non-deterministic ORM order, against a
database where two other writers (`web_app.py` L2734 KG ingestion path and
`brain/app.py` `kg_ingestor` worker — both started by `Start All`) were
concurrently updating the same `entities` / `relationships` rows. The result was
a classic Postgres `40P01 deadlock detected`: writers A and B each held a row
lock the other needed, mid-autoflush, and one was killed.

The single end-of-run commit also meant a single deadlock cost the entire run
(thousands of LLM tokens and minutes of work) instead of a single batch.

## Fix (smallest viable)

`src/context_foundry/workers/verification_worker.py`:

1. Added `time` and `sqlalchemy.exc.OperationalError` imports.
2. `VerificationConfig`: added `deadlock_max_retries: int = 3` and
   `deadlock_initial_backoff_s: float = 0.5`.
3. `_iter_facts_in_batches()`: facts are now sorted by `(fact_type, fact_id)`
   before batching, so this worker takes row locks in a deterministic global
   order. Concurrent writers that follow the same convention will not deadlock
   with this worker; if they don't, this worker can still deadlock but will be
   the consistent victim and retry cleanly.
4. Replaced the single end-of-run `commit()` with a per-batch
   `_commit_batch_with_retry()` helper that:
   - Wraps the verdict-store + status-update phase in
     `with self.session.no_autoflush:` so a `SELECT` cannot trigger a partial
     flush of unrelated dirty rows.
   - Catches `OperationalError`, identifies deadlocks via
     `e.orig.pgcode == "40P01"` first and `"deadlock detected"` substring as a
     belt-and-braces fallback.
   - Retries up to `deadlock_max_retries` times with exponential backoff
     (`0.5s, 1.0s, 2.0s` by default), then surrenders cleanly and returns
     `False` so the caller can record an error and move on.
   - Critically: earlier batches that already committed are preserved when a
     later batch ultimately fails — partial progress is real progress now.

The change is local to the worker. No schema migration. No semantics change to
what the verifier verifies, what gets persisted, or what callers see in the
returned stats dict (other than a higher `errors` count for batches that
exhausted retries).

### Subtle correctness note (caught during testing)

The first iteration matched deadlocks via `"deadlock" in str(e).lower()`. This
was wrong: SQLAlchemy embeds the wrapped exception's qualified class name in
`str(OperationalError)`, e.g.
`(tests.test_verification_worker_deadlock_fix.FakeOrig) connection failure ...`
— and any module/class whose qualname contains the substring "deadlock" would
false-positive. Fixed to require the two-word phrase
`"deadlock detected"` (the literal Postgres message) as the string fallback,
with `pgcode == "40P01"` as the primary check. See test
`test_non_deadlock_operational_error_is_not_retried` which exercises exactly
this case.

## Tests

`tests/test_verification_worker_deadlock_fix.py` — 8 tests, all green:

| Test | Asserts |
|---|---|
| `test_facts_are_processed_in_deterministic_pk_order` | `(fact_type, fact_id)` sort applied before batching |
| `test_commits_per_batch_not_once_at_end` | 3 batches → 3 commits (was 1 commit before fix) |
| `test_store_verdict_runs_inside_no_autoflush_block` | `_store_verdict` reads occur with autoflush disabled |
| `test_batch_retries_on_deadlock_and_succeeds` | pgcode=40P01 → retry → success, 2 commits, 1 rollback |
| `test_batch_deadlock_retry_is_bounded` | persistent deadlock → exactly `max_retries+1` attempts then surrender, no infinite loop |
| `test_non_deadlock_operational_error_is_not_retried` | pgcode=08006 → no retry, batch error counted |
| `test_tenant_scoping_is_preserved` | `_get_unverified_facts` still filters by tenant_id |
| `test_empty_input_no_commits` | zero facts → zero commits |

```
$ python -m pytest tests/test_verification_worker_deadlock_fix.py -v
======================== 8 passed, 9 warnings in 0.28s =========================
```

## Live validation (clean Stage 1J vault `ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda`)

Bounded end-to-end run against real Stage 1J facts with the real Anthropic
verifier:

```
$ python -m src.context_foundry.workers.verification_worker \
    --tenant-id ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda \
    --limit 5 --batch-size 5

[VerificationWorker] Found 5 unverified facts to process
... (5 LLM calls, 770 tokens) ...
[VerificationWorker] Completed: {
  'facts_processed': 5, 'verified': 5, 'rejected': 0,
  'needs_review': 0, 'errors': 0, 'tokens_used': 770
}
```

Persisted (target tenant, post-run):
- `entities.verified=true`: 0 → 4
- `relationships.verified=true`: 0 → 1
- `fact_verifications` rows: 0 → 5 (all `VERIFIED`)

A larger 50-fact stress run was attempted in a detached subprocess to exercise
multi-batch commits + the new no-autoflush wrap under real concurrency with
`Start All`. The Replit sandbox killed the detached child before completion
regardless of `setsid`/`disown`/`nohup`. The 5-fact run is sufficient for the
Stage 1K brief's "bounded verify" gate: it proves the patched code path loads,
commits cleanly per batch, and persists across the new `no_autoflush` block.
Multi-batch behavior is covered by unit tests (`test_commits_per_batch_not_once_at_end`).

## Cross-tenant invariants — frozen ✅

Confirmed before and after the bounded validation run. Pre-state was already
recorded in `stage_1j_fresh_ingestion_validation_2026-05-12.md`; this fix makes
no schema changes and does not touch other tenants.

| Invariant | Pre-Stage-1K | Post-bounded-verify | Status |
|---|---|---|---|
| Latest cross-tenant `relationships.updated_at` | `2026-05-11 05:59:56.823` | `2026-05-11 05:59:56.823` | 🔒 frozen |
| `merge_audits` row count | 3901 | 3901 | 🔒 frozen |
| Latest `merge_audits.merged_at` | `2026-05-11 05:59:59.118` | `2026-05-11 05:59:59.118` | 🔒 frozen |
| `ontology.types` count | 1037 | 1037 | 🔒 frozen |
| `ontology.relations` count | 254 | 254 | 🔒 frozen |

## Out of scope (deliberately not done)

Per the Stage 1K brief's "smallest targeted fix" directive:

1. **`scripts/run_vault_extraction.py` L1273-1278 `extraction_level` UUID/text
   bulk-update bug.** Brief lists this as "optional secondary fix." Not
   touched in this stage; recommend filing as Stage 1L follow-up — it is an
   independent bug in a different file with no shared root cause.
2. **Concurrent-writer cooperation.** This fix makes *this* worker a clean
   retry victim. The other writers (`web_app.py` L2734, `brain/app.py`
   kg_ingestor) still need their own deterministic-ordering pass before
   deadlocks can be eliminated rather than merely recovered from. Recommend
   Stage 1L item.
3. **Phase 3 historical contamination repair, Stage 2, scheduler, Nexus 100
   re-scoring, v2/FactEvaluator, replit.md edits** — all explicitly forbidden
   by Stage 1K standing constraints.

## Files changed

- `src/context_foundry/workers/verification_worker.py` — fix
- `tests/test_verification_worker_deadlock_fix.py` — new, 8 tests

## STOP — awaiting sign-off

Per Stage 1K brief: stop here for review before any further extraction,
promotion, or scheduling work.
