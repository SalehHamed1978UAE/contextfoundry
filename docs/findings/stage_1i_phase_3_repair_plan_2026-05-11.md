# Stage 1I Phase 3 — Cross-Tenant Relationship Repair Plan (PLAN ONLY)

> **Brief:** `docs/inbox/stage_1i_phase_3_repair_plan_2026-05-11.md`
> **Authority:** `docs/operating_instructions.md`
> **Predecessor:** Phase 1.6 sign-off ("Runtime Cutover Accepted") — runtime no longer producing new contamination.
> **Status of this document:** PLAN ONLY. **No DB mutation, no code edit, no schema constraint, no repair, no Phase 5 fix performed.** Awaiting sign-off before any execution.

---

## 0. Executive summary

| | |
|---|---|
| Total cross-tenant relationships (DB-wide) | **2,814** |
| Repair scope after excluding ARCHIVED | **1,324** (1,315 STAGING + 9 TRUSTED) |
| Live entity contamination | runtime cutover (Phase 1.6) confirms no new contamination since 2026-05-11 20:53 UTC |
| Foreign endpoints with a unique name match in rel.tenant (B1) | **71** rels (60 STAGING + 1 TRUSTED in L vault, 10 STAGING in S, 0 in Nexus) |
| Foreign endpoints with multi-candidate name matches (B3) | **13** rels (all STAGING, all in L) |
| Foreign endpoints with NO name match in rel.tenant (B4) | **1,182** rels (655 S + 521 L + 6 Nexus) |
| Pilot recommendation | **L vault first** (not S — see §1.1), then Nexus, then S, then DB-wide sweep of "other" tenants |
| Recommended primary action | quarantine 1,182 B4 rels (no safe automatic remap), remap 71 B1 rels with full audit trail, hand-review 13 B3 + 9 TRUSTED rels |
| Stage 2 readiness | **Remains BLOCKED** until Phase 3 executes + Phase 4 invariant lands |

---

## 1. Repair scope

### 1.1 Per-vault breakdown

DB-wide cross-tenant relationships, grouped by `relationships.tenant_id`:

| vault / tenant | id | total | ARCHIVED | STAGING | TRUSTED |
|---|---|---:|---:|---:|---:|
| **S** (S1B-Beta-S) | `5df41308-…77928b8ea93e` | 1,718 | 1,053 | 665 | 0 |
| **L** (S1B-Beta-L) | `f38e400f-…b41fbaff059f` | 1,000 | 385 | 609 | 6 |
| **original Nexus** | `176a4fb2-…0e26268fca71` | 22 | 14 | 8 | 0 |
| **other (small)** | 11 tenants × 4–5 rels each | ≈45 | ≈14 | ≈25 | ≈3 |
| **other (`fcc0a076-…`)** | 1 tenant, 85 total rels in DB, ≈46 cross-tenant | 46 | 29 | 17 | 0 |
| **other tenants — TRUSTED** | tenants `18dcc285`, `60f315b6` | — | — | — | 3 |
| **TOTAL** | | **2,814** | **1,490** | **1,315** | **9** |

(Brief's "S = 1,718" matches exactly. L and original Nexus per-vault counts were not in the brief; they are derived here.)

### 1.2 Sequencing recommendation: **L → Nexus → S → DB-wide other**

The brief suggested S first as pilot. I recommend **L first** for these reasons:

1. **L has the only mixed lifecycle (STAGING + TRUSTED + ARCHIVED) and the only B3 multi-candidates** — exercising the full code path early surfaces all repair-action branches before scaling.
2. **L has the highest count of B1 unique-equivalent rels (71/81 of all DB-wide B1 cases)** — pilot success here gives the largest immediate signal that remapping logic works.
3. **S is dominated by B4 no-equivalent rels (655/665 STAGING ≈ 98%)** — a "pilot on S first" would mostly exercise quarantine, not remap. Remap exercises matter more for confidence.
4. **L vault is the active one for current Nexus L-corpus testing**, so post-repair it can be re-tested with the existing Nexus 100 question set (under sign-off, not as part of Phase 3) to validate retrieval still works.
5. **Original Nexus (22 rels) is small enough to be "second pilot"** — quick confirmation that the repair generalizes off the L pilot before committing to the larger S sweep.
6. **DB-wide "other" tenants last** — they include test-fixture tenants (`fcc0a076-…` 85 rels; ~10 tenants with 4 rels each that look like single-doc test runs); per-tenant review needed but very low risk.

Proposed order (one tenant per transaction):
1. **Pilot:** L vault (1,000 rels)
2. **Confirm:** original Nexus (22 rels)
3. **Scale:** S vault (1,718 rels)
4. **Sweep:** 12 "other" tenants (≈91 rels combined) — each tenant in its own transaction

---

## 2. Relationship bucket classification

Definitions (all matching is **case-insensitive name + same `entity_type`**, restricted to non-ARCHIVED candidate entities in `rel.tenant_id`):

| bucket | meaning | DB-wide count (non-ARCHIVED) | repair confidence |
|---|---|---:|---|
| **B1** | foreign endpoint has **exactly one** name+type equivalent in `rel.tenant_id`; the other endpoint is either local or also has a unique equivalent | 71 (60 STAGING + 1 TRUSTED in L; 10 STAGING in S) | **HIGH** (deterministic remap) |
| **B2** | one endpoint is already local; the other has a unique equivalent | (subset of B1; all 71 also satisfy B2's looser version — kept under B1) | n/a |
| **B3** | one or both endpoints have **multiple** name+type equivalents in `rel.tenant_id` | 13 (all STAGING in L) | **LOW** (cannot safely guess; quarantine) |
| **B4** | one or both endpoints have **no** name+type equivalent in `rel.tenant_id` | 1,182 (655 S + 521 L + 6 Nexus) | **NONE** (no remap target; quarantine or archive) |
| **B5** | invalid `relationship_type` per `ontology_relations` | **0** (verified — all 2,814 cross-tenant rels use valid ontology relation names) | n/a — bucket empty |
| **B6** | already ARCHIVED | 1,490 | leave-unchanged with archive verification |
| **B7** | TRUSTED, eligible for repair | 9 (1 in L is B1; 8 are B4) | **HAND REVIEW** before any action |

**Bucket distribution (non-ARCHIVED, by vault and lifecycle):**

```
Vault    Lifecycle  B1 unique  B3 multi  B4 no-equiv   total
S        STAGING        10         0         655         665
L        STAGING        80        13         516         609
L        TRUSTED         1         0           5           6
Nexus    STAGING         2         0           6           8
other    STAGING        ~7         0         ~30         ~37
other    TRUSTED         0         0           3           3
                       ----      ----      ------       -----
                        100        13        1,215       1,328
```

(Counts approximate for "other" tenants; exact per-tenant query to be added to the per-batch pre-flight script when the executor task is approved.)

### 2.1 Reconciliation with brief's "746 / 758 unique-equivalent + 12 multi-candidate"

The brief's "746/758" cannot be reproduced from the current DB:
- DB-wide non-ARCHIVED unique-equivalent **endpoints** (not relationships): **71** (60 STAGING + 1 TRUSTED + 10 STAGING).
- DB-wide ARCHIVED also included: **132 endpoints**.
- DB-wide all-lifecycle: **132 + 71 = 203 endpoints** with at least one match; brief said **758**.

Possible explanations (listed for visibility, not assumed):
1. Brief's count was computed on different equivalence criteria — e.g., trigram similarity, embedding cosine ≥ X, prefix match, or substring match — none of which is currently in the codebase as a recoverable computation.
2. Brief's count included `entity_aliases` or `cf_entity_aliases` — both verified **empty** today.
3. Brief's count was computed at an earlier point when more equivalents existed (e.g., before some target tenants' entities were ARCHIVED or re-extracted).
4. Brief's count counted `(rel_id, side)` pairs across both endpoints separately rather than distinct foreign endpoints.

**Recommendation:** treat the 746/758 number as a stale upstream estimate; rely on the live numbers in §2 for repair sizing. If the brief's source can be located, re-run the equivalence computation under that methodology and reconcile before pilot execution.

### 2.2 Foreign-endpoint provenance signal

For all foreign endpoints in non-ARCHIVED cross-tenant rels (DB-wide):

| foreign endpoint own lifecycle | distinct entity_ids |
|---|---:|
| ARCHIVED | 21 |
| STAGING | 444 |
| TRUSTED | **511** |

**Implication:** the dominant pattern is `(STAGING rel in tenant A) → TRUSTED entity in tenant B`. This is consistent with the IdentityResolver bug: it picked the highest-confidence canonical entity globally and wrote a relationship endpoint pointing at it, even when that entity lived in a different tenant. **Repair must not delete or alter the foreign endpoint** — only re-point or quarantine the relationship.

`superseded_by` audit: of 465 distinct foreign endpoints (non-ARCHIVED rels), only **16** have a `superseded_by` set, and **449 are "live"** in their own tenant. So Phase 1's prior IdentityResolver merges did not leave most of these endpoints orphaned; they are still canonical in their home tenant.

---

## 3. Repair action per bucket (DRAFT — not executed)

### 3.1 B1 (71 rels, HIGH confidence) — **remap endpoint**

For each B1 rel:
- Identify the foreign endpoint (the one whose `tenant_id ≠ rel.tenant_id`).
- Look up the unique local equivalent in `rel.tenant_id` (case-insensitive name + same entity_type, lifecycle ≠ ARCHIVED).
- Update `relationships.source_id` or `relationships.target_id` to the local equivalent's id.
- Record the old → new endpoint id, old foreign tenant, and rel id in the backup table (§5).
- Recompute `relationships.tenant_id` after remap to ensure invariant `rel.tenant = source.tenant = target.tenant` (it should already match because the remaining endpoint's tenant is `rel.tenant` by construction).

**Edge case:** if the foreign endpoint is itself referenced by other relationships in its home tenant (likely), do **not** delete it — it remains canonical in its home tenant. We are only re-pointing this specific relationship.

### 3.2 B3 (13 rels, LOW confidence) — **quarantine, manual review later**

Per brief §7: "Use: quarantine first, manual review later, no LLM disambiguation yet."

- Move rel to a `relationships_quarantine` backup table with all fields preserved + reason="B3_multi_candidate".
- Set `lifecycle_state='ARCHIVED'` and `change_reason='Phase 3 quarantine: multi-candidate endpoint, manual review required'` on the original row, OR delete the original row (deferred decision — see §6.3).
- Tag with quarantine batch id for later human review.

### 3.3 B4 (1,182 rels, NONE confidence) — **quarantine + per-tenant policy decision**

These are the dominant case. Two sub-actions to consider:
- **B4-archive:** mark `lifecycle_state='ARCHIVED'` with `change_reason='Phase 3: cross-tenant contamination, no repair target'`. Foreign endpoint left intact in its home tenant.
- **B4-delete-after-backup:** physically delete the rel row after backing it up. Cleaner DB but harder to inspect post-hoc.

**Recommendation:** **archive, do not delete** — preserves audit trail in the live `relationships` table, lifecycle filtering already excludes ARCHIVED from retrieval, and Phase 4's DB-level invariant (next section) can be defined as "no NEW cross-tenant non-ARCHIVED rels" without disturbing historical archive rows. Delete-after-backup remains an option if archive-bloat becomes a problem.

### 3.4 B6 (1,490 ARCHIVED rels) — **leave unchanged + verify**

- Verify each is still ARCHIVED post-repair (count must remain 1,490).
- No mutation.

### 3.5 B7 (9 TRUSTED rels) — **hand review individually before any action**

The 9 TRUSTED cross-tenant rels (sampled in pre-plan query):

| rel_id | rel.tenant | type | source | target | bucket |
|---|---|---|---|---|---|
| `2e9f35eb-…` | `18dcc285` (other) | HOLDS_POSITION | Michael Chang (PERSON, in `18dcc285`) | Chief Financial Officer (JOB_TITLE, in `b597f6ad`) | B4 (no JOB_TITLE in `18dcc285`) |
| `9c5f0080-…` | `18dcc285` (other) | HOLDS_POSITION | Victoria Chen (PERSON, in `18dcc285`) | Chief Executive Officer (JOB_TITLE, in `b597f6ad`) | B4 |
| `66cf70fe-…` | `60f315b6` (other) | PART_OF | Falcon X (PROJECT, in `64115bd5`) | Nexus Industries (ORGANIZATION, in `64115bd5`) | rel.tenant ≠ either endpoint tenant |
| `0fa49282-…` | L | PRODUCES | IoT & Edge Computing (BUSINESS_UNIT, in Nexus) | Edge AI Solutions (PRODUCT, in L) | B4 |
| `337c8a95-…` | L | PART_OF | Energy Systems Division (BUSINESS_UNIT, in L) | Nexus Industries (ORGANIZATION, in `64115bd5`) | B4 |
| `4125681d-…` | L | LOCATED_AT | GreenHydrogen Facility (FACILITY, in L) | El Paso (LOCATION, in Nexus) | B4 |
| `4e28a1a6-…` | L | PART_OF | GreenHydrogen Initiative (PROJECT, in Nexus) | Renewable Energy Projects (BUSINESS_UNIT, in L) | B4 |
| `60e600da-…` | L | PART_OF | Desert Sun Solar Farm (PROJECT, in Nexus) | Renewable Energy Projects (BUSINESS_UNIT, in L) | B4 |
| `eab1c0d2-…` | L | LOCATED_AT | Nexus Industries (ORGANIZATION, in `64115bd5`) | Phoenix (LOCATION, in Nexus) | B4 |

**Hand-review required before repair.** Plausible per-row decisions:
- The `18dcc285 → b597f6ad` HOLDS_POSITION pair likely needs the JOB_TITLE entities created in `18dcc285` (extraction artifact: shared title entity got attached to a wrong tenant) — but creating new entities is **out of scope for Phase 3** (Phase 3 only repairs relationships, does not synthesize entities). Recommend archive these 2 with note for Phase 5/6 backfill.
- The `66cf70fe-…` PART_OF rel where rel.tenant ≠ either endpoint tenant is the cleanest "rel.tenant is wrong, both endpoints agree" case — could be repaired by setting `rel.tenant_id = source.tenant_id = target.tenant_id = 64115bd5`. But again this requires moving the rel to a different tenant, which has retrieval implications. Recommend archive + manual decision.
- L vault rels involving a BUSINESS_UNIT/PROJECT in Nexus pointing at an L PRODUCT/BUSINESS_UNIT are real cross-tenant facts. They were probably extracted because the Nexus parent corpus and L sub-corpus share document content. Per brief §4 ("verify no TRUSTED fact silently degraded"), archive with `change_reason` documenting that this was a cross-tenant TRUSTED rel and recommend re-extraction in the home tenant.

**No automated action on B7 in Phase 3.** Each row gets a one-line decision in a hand-review log; only after sign-off on those 9 decisions do they get applied.

### 3.6 Foreign-endpoint policy

For all repaired/quarantined relationships, **never delete the foreign endpoint**. The foreign entity remains valid in its home tenant. (Phase 5 — out of scope here — will address whether foreign-tenant duplicates of canonical entities should be merged.)

---

## 4. Safety checks (pre/post per batch)

Each per-tenant transaction runs these checks before COMMIT. **Mismatch on any post-check ⇒ ROLLBACK.**

### 4.1 Counts

| check | pre | expected post (B1 remap example) |
|---|---|---|
| `count(*) FROM relationships WHERE tenant_id=:t` | N | unchanged |
| cross-tenant rels in tenant `:t` | N_ct | N_ct − N_repaired_or_quarantined |
| cross-tenant rels DB-wide | 2814 | 2814 − N_repaired_or_quarantined |
| `count(*) GROUP BY lifecycle_state WHERE tenant_id=:t` | (S, T, A) | STAGING −N_remapped −N_quarantine_archive; ARCHIVED +N_quarantine_archive; TRUSTED unchanged unless B7 actioned (must be 0 in Phase 3 unless a B7 decision was approved) |
| `count(*) FROM entities WHERE tenant_id IN (any_tenant)` | E | **unchanged** (no entity touched) |
| `count(*) FROM document_chunks` | C | **unchanged** |
| `count(*) FROM documents` | D | **unchanged** |
| `count(*) FROM ontology_relations` | O | **unchanged** |
| `count(*) FROM ontology_types` | OT | **unchanged** |

### 4.2 Sample verification (per batch)

For 20 random repaired rels per batch:
- Re-query the rel by id; assert `source.tenant_id == target.tenant_id == rel.tenant_id`.
- Assert `lifecycle_state` matches expected.
- Assert backup row exists with matching old endpoint ids.

### 4.3 Reversibility

- For 5 random repaired rels per batch: run the rollback SQL (see §5) in a sub-transaction, verify the rel returns to its pre-repair state, then ROLLBACK the rollback. Confirms the backup is sufficient to reverse.

### 4.4 No silent TRUSTED degradation

- `count(*) WHERE lifecycle_state='TRUSTED' AND tenant_id=:t` must be unchanged unless a B7 decision was approved for this batch and the count delta exactly matches the approved B7 actions.

---

## 5. Backup strategy

### 5.1 Backup table

```sql
CREATE TABLE relationships_phase3_backup (
  backup_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rel_id              uuid NOT NULL,
  batch_id            text NOT NULL,
  vault_label         text NOT NULL,
  bucket              text NOT NULL,            -- 'B1', 'B3', 'B4', 'B7'
  action              text NOT NULL,            -- 'remap', 'quarantine_archive', 'hand_review_archive'
  old_source_id       uuid NOT NULL,
  new_source_id       uuid,
  old_target_id       uuid NOT NULL,
  new_target_id       uuid,
  old_tenant_id       uuid NOT NULL,
  new_tenant_id       uuid,
  old_lifecycle_state text NOT NULL,
  new_lifecycle_state text,
  old_updated_at      timestamp NOT NULL,
  rel_snapshot        jsonb NOT NULL,           -- full row at time of repair
  source_snapshot     jsonb NOT NULL,           -- entities row for old_source_id
  target_snapshot     jsonb NOT NULL,           -- entities row for old_target_id
  created_at          timestamp NOT NULL DEFAULT now(),
  rolled_back_at      timestamp
);
CREATE INDEX ON relationships_phase3_backup (batch_id);
CREATE INDEX ON relationships_phase3_backup (rel_id);
CREATE INDEX ON relationships_phase3_backup (vault_label);
```

### 5.2 Rollback SQL skeleton

```sql
-- Per batch:
BEGIN;
UPDATE relationships r
SET source_id   = b.old_source_id,
    target_id   = b.old_target_id,
    tenant_id   = b.old_tenant_id,
    lifecycle_state = b.old_lifecycle_state::lifecycle_state_enum,
    updated_at  = b.old_updated_at,
    change_reason = 'Phase 3 ROLLBACK from batch ' || b.batch_id
FROM relationships_phase3_backup b
WHERE r.id = b.rel_id AND b.batch_id = :batch_id AND b.rolled_back_at IS NULL;

UPDATE relationships_phase3_backup
SET rolled_back_at = now()
WHERE batch_id = :batch_id AND rolled_back_at IS NULL;
COMMIT;
```

### 5.3 No backup yet

Per brief §5: "Do not create backup yet."

---

## 6. Transaction strategy

### 6.1 One tenant per transaction

- **Pilot batch:** L vault, B1 only (60 STAGING + 1 TRUSTED — but 1 TRUSTED is in B7, defer; so 60 STAGING B1 in L).
- After pilot success: L vault B3 (13 quarantine), then L vault B4 (521 STAGING + 5 TRUSTED B7-after-decision) in chunks of 200.
- Each chunk: BEGIN; pre-counts; backup INSERT; UPDATE rels; post-counts; sample verification; COMMIT or ROLLBACK.

### 6.2 Verification block before COMMIT

```sql
-- pseudo:
DO $$
DECLARE
  ct_before int := <captured_pre>;
  ct_after  int;
BEGIN
  SELECT count(*) INTO ct_after FROM relationships r JOIN entities sa ON ... WHERE <cross_tenant>;
  IF ct_after <> ct_before - <expected_delta> THEN
    RAISE EXCEPTION 'Phase 3 batch % count mismatch: expected %, got %', :batch_id, ct_before - <expected_delta>, ct_after;
  END IF;
  -- additional checks per §4
END $$;
COMMIT;
```

### 6.3 Open decision: archive vs delete for B3/B4 quarantine

Recommendation: **archive (lifecycle_state='ARCHIVED' + change_reason)** for all B3/B4 quarantine actions, with the original row preserved in `relationships`. Reason: cleaner audit, no row deletion, retrieval already filters ARCHIVED. Delete-after-backup is a fallback if archive bloat impacts performance — to be revisited after pilot.

### 6.4 Active runtime concurrency

- Start All is running with scheduler identity-resolution **disabled** (Phase 1.6 verified). Gardener runs every 5 min and may touch some of the same rows (promotion/decay/cleanup).
- Recommended: pause WebApp + Brain Gardener cycles during a repair batch. Two options:
  - (a) restart Start All into a maintenance mode (env flag) before each batch — simpler but heavier.
  - (b) take a per-batch advisory lock that the Gardener also acquires — requires code change (out of scope for plan).
  - (c) **Recommended for pilot:** schedule the L pilot during a quiet window, observe Gardener cycle gaps, and accept the small race risk because the pilot is small (60 rows). Re-evaluate concurrency strategy before S-vault sweep.

---

## 7. Quarantine strategy for multi-candidate endpoints (13 rels)

Per brief §7: "Use: quarantine first, manual review later, no LLM disambiguation yet."

- All 13 multi-candidate rels are STAGING in L vault.
- Action: archive with `change_reason='Phase 3 quarantine: B3 multi-candidate, manual review required'`.
- Backup row records all candidate equivalents in the rel.tenant (so reviewer doesn't have to recompute).
- Defer disambiguation to a later (numbered) phase. Do not invoke an LLM picker.
- Reviewer SLA: not blocking Phase 3 sign-off; can be reviewed asynchronously.

---

## 8. Tests to add before repair execution (proposed, not written)

### 8.1 Unit / SQL tests

- T-3.1 `relationships.tenant_id == source.tenant_id == target.tenant_id` for every non-ARCHIVED rel after repair (per repaired vault).
- T-3.2 `count(cross-tenant non-ARCHIVED) = 0` per repaired vault after repair.
- T-3.3 Each repair-action remap is **deterministic** — re-run with same input produces same row mutations.
- T-3.4 Multi-candidate (B3) endpoints are **always quarantined**, never guessed (assert no B3 rel ends up with a remapped endpoint).
- T-3.5 Reversibility — for a sample batch, run rollback SQL and assert pre-repair state restored.
- T-3.6 No entities, documents, or chunks deleted (counts unchanged).
- T-3.7 No ontology table mutated.
- T-3.8 TRUSTED count delta exactly matches approved B7 decisions for the batch.

### 8.2 Integration test (post-repair)

- T-3.9 With a hypothetical Phase 4 trigger active (dry-run mode), attempt to INSERT a cross-tenant relationship and assert the trigger rejects it.
- T-3.10 Re-run an existing retrieval test on the L vault after pilot repair and assert no question that used to pass now fails (regression guard). **Out of scope for Phase 3 execution; queued for Phase 4 post-trigger validation.**

### 8.3 Test files

To live under `tests/repair/phase3/`:
- `test_phase3_invariants.py` — T-3.1, T-3.2, T-3.4, T-3.6, T-3.7, T-3.8
- `test_phase3_reversibility.py` — T-3.3, T-3.5
- `test_phase4_trigger_dryrun.py` (Phase 4) — T-3.9
- `test_phase3_no_regression_l.py` (post-pilot) — T-3.10

**Tests will be authored in the executor task once this plan is signed off.**

---

## 9. Stage 2 readiness verdict

**Stage 2 remains BLOCKED** until **all** of:
1. Phase 3 pilot (L) executed and validated.
2. Phase 3 full sweep (Nexus, S, other) executed and validated.
3. Phase 4 invariant in place (DB trigger or app-level assertion — see §10).
4. Promotion path re-tested on clean tenant-local relationships (Phase 1.6 left scheduler identity-res disabled; Stage 2 prep needs a decision on how to re-enable safely).
5. The pre-existing `duplicate_candidates_entity_a_id_fkey` issue is either resolved (Phase 5) **or** explicitly accepted as not-blocking for Stage 2 by the operator. Phase 3 itself does not touch `duplicate_candidates`, so this is independent.

Expected outcome: Stage 2 unblock comes after Phase 4 sign-off, not Phase 3 sign-off.

---

## 10. Phase 4 preview — DB invariant plan (DRAFT — not implemented)

### 10.1 Invariants to enforce

1. `relationships.tenant_id = (SELECT tenant_id FROM entities WHERE id = relationships.source_id)` for every non-ARCHIVED relationship.
2. `relationships.tenant_id = (SELECT tenant_id FROM entities WHERE id = relationships.target_id)` for every non-ARCHIVED relationship.
3. (Implied) `source.tenant_id = target.tenant_id` for every non-ARCHIVED relationship.

### 10.2 Three implementation options

| option | mechanism | pro | con |
|---|---|---|---|
| **A. DB trigger (BEFORE INSERT/UPDATE)** | trigger on `relationships` that lookups `entities.tenant_id` for `source_id` and `target_id`, raises EXCEPTION on mismatch | enforced at lowest layer; cannot be bypassed from application code | adds latency to every INSERT/UPDATE; risk to writers that don't expect rejection (Gardener cleanup, IdentityResolver if re-enabled, manual SQL); harder to dry-run safely |
| **B. CHECK constraint** | not feasible — CHECK cannot reference other tables in PostgreSQL | n/a | n/a (rule out) |
| **C. App-level assertion** | wrap rel-write paths in a service that validates tenant before commit; add unit + integration tests | safe to roll out gradually; easy to bypass for backfills | requires cataloguing every write path (StagingLoader, KGIngestor, GardenerAgent, IdentityResolver, web routes, scripts); a missed path silently re-introduces the bug — exactly what happened in Phase 1 |
| **D. Hybrid: trigger in WARN mode + app assertion** | trigger logs to an audit table on mismatch but does not block; app-level assertion blocks; once app paths are clean, switch trigger to BLOCK | safe rollout, observable, defensive in depth | most complex; needs an audit-log table and dashboard |

**Recommendation:** **Option D (hybrid)**. Land app-level assertion first, run trigger in warn-only mode for ≥ 1 week with an audit table, then flip the trigger to BLOCK once the audit table is empty.

### 10.3 RLS WITH CHECK

- Current `TenantSession` enforces RLS on SELECT via `set_config('app.tenant_id', ...)`. Need to verify whether existing RLS policies on `relationships` have `WITH CHECK` clauses that enforce tenant on INSERT/UPDATE. **TODO for Phase 4 plan execution: audit `pg_policies` for `relationships` and confirm.**
- If RLS WITH CHECK can be tightened to require `relationships.tenant_id = current_tenant`, that adds a fourth defensive layer (in addition to app assertion + warn-mode trigger + post-Phase-4 BLOCK trigger).

### 10.4 Sequencing

1. Phase 4a (post-Phase-3): land app-level assertion + tests.
2. Phase 4b: deploy trigger in WARN mode + audit table.
3. Phase 4c: observe ≥ 1 week. If audit table stays empty, flip trigger to BLOCK.
4. Phase 4d: tighten RLS WITH CHECK if not already in place.

**Do not implement any of Phase 4 in this task.** This section exists per brief §"Phase 4 preview".

---

## 11. Out of scope (per brief §"Standing constraints")

- Stage 2 — not started.
- Promotion cycles — not run.
- Scheduler identity resolution — not started, not re-enabled.
- DB mutation — none.
- Code edit — none.
- Schema constraint — none.
- Repair execution — none.
- Nexus 100 scoring — not run.
- VerificationWorker — not run.
- v2 — not touched.
- replit.md — not edited (system has nudged 590 times across this thread; standing refusal continues).

## 12. Refusals during Phase 3 planning

- 36 auto-injected v2 FactEvaluator T01-T14 plans (project goal: v2 parked) — refused.
- 590 replit.md trim nudges — refused (Phase 3 brief §"Standing constraints" forbids).
- Manus / Ontology Vault / S1B-Beta-S-Extract restart nudges (Phase 1.6 brief still in force) — refused.

---

## 13. Stop condition (per brief §"Stop condition")

**Phase 3 + Phase 4-preview repair-plan report complete. Awaiting sign-off before any of:**
- Phase 3 pilot execution (L vault).
- Phase 3 full sweep (Nexus, S, other tenants).
- Phase 4a (app-level tenant-invariant assertion).
- Phase 4b (warn-mode trigger + audit table).
- Phase 4c (block-mode trigger).
- Phase 4d (RLS WITH CHECK tightening).
- Phase 5 (`duplicate_candidates` schema + FK cascade).
- Stage 2.
- Re-enabling scheduler identity resolution.
- Promotion cycle rerun.
- Backfill of B7 hand-review entities (e.g., creating missing JOB_TITLE entities in `18dcc285`).

Reviewer to confirm:
1. Sequencing recommendation L → Nexus → S → other (vs brief's S-first suggestion).
2. Quarantine = ARCHIVE (vs delete-after-backup) for B3/B4.
3. Concurrency strategy for pilot (option (c) — quiet window, no Gardener pause).
4. Per-row decisions on the 9 B7 TRUSTED rels.
5. Phase 4 hybrid recommendation (option D).
