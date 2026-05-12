# Stage 1J Pre-Step — Ontology Baseline Investigation (READ-ONLY)

> **Brief:** "Stage 1J Pre-Step — Ontology Baseline Investigation" (this thread, 2026-05-12)
> **Authority:** `docs/operating_instructions.md` + standing constraints
> **Predecessor:** Phase 3 repair plan signed-off scope (`docs/findings/stage_1i_phase_3_repair_plan_2026-05-11.md`)
> **Status:** PLAN/REPORT ONLY. **No DB mutation, no schema change, no ontology delete, no migration replay, no vault deletion.** Awaiting sign-off before any ontology mutation OR Stage 1J execution.

---

## 0. Executive summary

| | |
|---|---|
| **Two ontology systems exist in this DB** | `public.ontology_*` (41 types, 19 relations — LEGACY/dead) and `ontology.*` (1,037 types, 254 relations — LIVE, used by CF runtime) |
| User's "803 ad-hoc types" | **CONFIRMED** — `ontology.types` grew from ~233 baseline (Dec 2025) to 1,037 by Feb 2026. **Net adaptive growth ≈ 804** (784 in Jan + 20 in Feb). The "803" matches within 1. |
| User's "23 invalid relations" | **PARTIALLY CONFIRMED — actual count is 27** rel_types used in `relationships` table that are missing from `public.ontology_relations`. **Of those 27, 19 ARE in `ontology.relations`** (schema-qualified). **Only 8 are truly orphan** (missing from both): `FOCUSES_ON`, `FUNDED_BY`, `HAS_SPEC`, `OWNED_BY`, `RELATED_TO`, `USES`, `USES_MATERIAL`, `WORKS_FOR`. |
| Cleanest rollback path | **Option A2 — truncate `ontology.types` + `ontology.relations`, replay migrations 002+003+006+016+017** (with a DDL fix for migration 016/017 to target the correct schema). Requires migration audit + re-execution. |
| Lower-risk alternative | **Option D — no rollback, accept post-baseline state.** Runtime works today; a "clean ontology" is cosmetic if Stage 1J's goal is vault validation, not ontology validation. Defer ontology cleanup to a later phase. |
| Stage 1J prerequisite | Decision needed on Option A2 vs D **before** vault deletion. The two are independent operations — deleting vaults will not change the ontology state. |

---

## 1. Schema topology — TWO ontology systems coexist

This DB has **two separate ontology table families**, in two different PostgreSQL schemas:

| schema.table | row count | who reads it | who writes it | role |
|---|---:|---|---|---|
| `public.ontology_types` | **41** | (legacy code path / schema_loader fallback) | migrations 001/002/006 only — runtime does **not** write to it | **dead/legacy** — see §3 |
| `public.ontology_relations` | **19** | (legacy code path) | migrations 001/003/006 only | **dead/legacy** |
| `public.ontology_entity_types` | 0 | (unused) | (none) | empty stub |
| `public.ontology_relationship_types` | 0 | (unused) | (none) | empty stub |
| `public.ontology_proposals` | 0 | (unused) | (none) | empty stub |
| `public.ontology_candidates` | 645 (PENDING) | `OntologyCandidateStore`, governance UI | `CandidateStore.add_candidate()` | **live** — adaptive ontology proposals waiting for review |
| **`ontology.types`** | **1,037** | `staging_loader.py:213-237`, `entity_extractor.py:268`, `ontology_centric_pipeline.py:312-378`, `vault_operations.py:466` | `staging_loader._ensure_entity_type_exists()` (runtime extraction adds rows here on-the-fly) | **LIVE — primary entity-type registry** |
| **`ontology.relations`** | **254** | `discovery/type_discovery_agent.py:377` (`SELECT UPPER(relation_type) ... WHERE status='ACTIVE'`), validation triggers | migrations 016/017, runtime extraction code paths | **LIVE — primary relation-type registry** |
| `ontology.canonical_relations` | 4,639 | `canonicalizer.py:122` | `canonicalizer.py:400` | LIVE — canonicalization layer (separate from ontology proper) |
| `ontology.canonical_entity_types` | 0 | (declared but empty) | (none) | empty stub |
| `ontology.reference_ontologies` | 813 | `ontology_manager.py:269` | `ontology_manager.py:400` | reference-only document-type ontologies |
| `ontology.meta_ontology` | 5 | meta-config | (rare) | tiny config table |
| `ontology.domains` | **8** ✅ | (cross-cutting) | (rare) | the 8 canonical domains exist: `aviation`, `construction`, `core`, `finance`, `healthcare`, `it_infrastructure`, `manufacturing`, `supply_chain` (created 2026-05-09 — recent, see §4) |
| `ontology.relations_backup_pre_piece_0_6` | 254 | (manual rollback aid) | one-time backup | **NOT a clean baseline** — same row count and same date range as live `ontology.relations` (likely taken AFTER Piece 0.6, not before, despite the name) |
| `ontology.versions` (change-log) | 0 | (declared but unused) | (none) | empty audit table |
| `ontology.type_migrations` | 0 | (declared but unused) | (none) | empty migration log |
| `ontology.type_migration_map` | (not counted) | type-rename plumbing | (rare) | small |
| `ontology.rules` | (not counted) | validation engine | governance | live but small |
| `ontology.approval_requests` | (not counted) | approval workflow | governance | live but small |

### 1.1 Implication for Stage 1J

**Stage 1J vault deletion does not affect ontology tables.** Vaults live in `entities` / `relationships` / `documents` / `document_chunks` (tenant-scoped). Ontology tables are partly tenant-scoped and partly global, but Stage 1J vault-delete will only touch the listed tenants' rows in `entities`/`relationships`/etc., not the ontology registries.

The "ontology cleanup" question is therefore **independent** of Stage 1J vault cleanup, and the user can choose to do them together or separately.

---

## 2. Reconciliation of user's "803 ad-hoc types + 23 invalid relations"

### 2.1 The 803 number

Confirmed against `ontology.types`:

| month | rows created |
|---|---:|
| 2025-12 | 233 (baseline cluster — migrations 002/006 + early manual seeds) |
| 2026-01 | **784** (adaptive growth — runtime extraction added types on-the-fly) |
| 2026-02 | 20 (continued adaptive growth) |
| **TOTAL** | **1,037** |

**Net adaptive growth post-baseline ≈ 804 types** (784 + 20). User's "803" matches within 1. ✅

By layer × status:

| layer | status | n | earliest | latest |
|---|---|---:|---|---|
| 1 | ACTIVE | 24 | 2025-12-06 | 2026-01-24 |
| 2 | ACTIVE | **1,006** | 2025-12-06 | 2026-02-08 |
| 2 | PROPOSED | 2 | 2025-12-06 | 2025-12-06 |
| 3 | ACTIVE | 3 | 2025-12-06 | 2025-12-06 |
| 3 | APPROVED | 2 | 2025-12-06 | 2025-12-06 |

The ad-hoc growth is **entirely at Layer 2 (domain-specific)** — Layer 1 (universal) and Layer 3 (specialized refinements) are stable since December.

### 2.2 The 23 number

**The user's "23 invalid relations" is partly stale.** Live `relationships` table uses **28 distinct relationship_types**. Of those:

| validity | count | examples |
|---|---:|---|
| In `public.ontology_relations` (the legacy table) | 1 | (only `OWNS` overlaps) |
| In `ontology.relations` (the live table) | **20** | HOLDS_POSITION, PART_OF, PRODUCES, CUSTOMER_OF, OWNS, LEADS, MEMBER_OF, PARTNER_OF, SUPPLIER_OF, LOCATED_AT, LOCATED_IN, REPORTS_TO, INVESTED_IN, SUPPLIES, MEETS_SPEC, MANAGES, AFFILIATED_WITH, WORKS_AT, BOARD_MEMBER_OF, … |
| In **neither** (truly orphan) | **8** | `FOCUSES_ON` (8 rels), `FUNDED_BY` (334), `HAS_SPEC` (197), `OWNED_BY` (19), `RELATED_TO` (119), `USES` (284), `USES_MATERIAL` (47), `WORKS_FOR` (23) |

**Truly orphan rel-type total volume:** 1,031 relationships across 8 types (notably `USES` 284, `FUNDED_BY` 334, `HAS_SPEC` 197, `RELATED_TO` 119).

User's "23 invalid" likely came from earlier query against `public.ontology_relations` only, missing the schema-qualified `ontology.relations`. **Real number is 8 truly orphan types** (with 1,031 relationships referencing them).

### 2.3 The 645 PENDING candidates

Separate signal: `public.ontology_candidates` has **645 rows in PENDING status**, all `candidate_type='RELATIONSHIP'`, created 2026-01-13 → 2026-05-08. These are LLM-proposed new relationship types that the governance workflow has not approved/rejected. Top examples: `BELONGS_TO_SECTOR`, `CEO_OF`, `HAS_INVESTMENT`, `HAS_BOARD_SEAT`, `LEADS_BUSINESS_UNIT`, `HAS_EMISSION_SCOPE`, `INCLUDES`, `AUTHORED_BY`, `HAS_METRIC`, `PARTNERS_WITH`, `PRESENTS`, `HAS_USE_CASE`, …

These are **not "invalid"** — they are pending review. They are NOT being used by the extraction runtime (they live in a candidate table, not the live `ontology.relations`).

---

## 3. Migration history relevant to ontology

### 3.1 Migration files in chronological order

**`src/context_foundry/migrations/`** (CF-native migrations):

| file | date authored | targets | seeds | status |
|---|---|---|---|---|
| 001_ontology_tables.sql | early Dec 2025 | `public.ontology_types/relations` | (DDL only) | applied |
| 002_seed_ontology_types.sql | early Dec 2025 | `public.ontology_types` | Layer 0 (4 system) + Layer 1 (9 system) + Layer 2 IT-Ops (~14) | **applied to wrong table** — only 41 rows landed in `public.ontology_types`; CF runtime uses `ontology.types` (different schema) |
| 003_seed_ontology_relations.sql | early Dec 2025 | `public.ontology_relations` | Layer 2 IT-Ops relations (DEPENDS_ON, RUNS_ON, CONTAINS, OWNS) | **applied to wrong table** — 19 rows in `public.ontology_relations`; runtime ignores |
| 004_validation_triggers.sql | early Dec 2025 | trigger on `entities` | (validates entity_type against ontology) | applied |
| 005_promotion_thresholds.sql | mid Dec 2025 | (lifecycle) | n/a | applied |
| 006_infra_ontology.sql | 2025-12-06 | `public.ontology_types` | INFRA archetype (PowerPlant, DesalinationPlant, Substation, Port, Vessel, Pipeline, Locomotive, Airport, Terminal, …) | **applied to wrong table** |
| 007–015 | various | n/a (not ontology) | n/a | applied |
| 017_extraction_job_tracking.sql | (note: migration "017" name collision) | extraction tracking | n/a | applied |

**`migrations/`** (newer/separate migration set):

| file | date authored | targets | seeds | status |
|---|---|---|---|---|
| ontology_foundry_tables.sql | (early) | `public.ontology_candidates` etc | DDL only | applied |
| 016_seed_core_relations.sql | 2026-01-13 | **`ontology.types` + `ontology.relations`** (schema-qualified — the LIVE table) | PERSON, ORGANIZATION, LOCATION, JOB_TITLE, COMPENSATION, MONEY, PRODUCT, SERVICE, EVENT, DATE, DOCUMENT entity types + HOLDS_POSITION, HAS_COMPENSATION, BOARD_MEMBER_OF, LOCATED_IN, WORKS_AT, REPORTS_TO, MANAGES + others | **applied — landed in correct schema** |
| 017_add_supply_chain_relations.sql | 2026-02-09 | **`ontology.relations`** | CUSTOMER_OF, SUPPLIER_OF | **applied — landed in correct schema** |

**`platform_foundation/migrations/`** — non-ontology (auth, tenants, documents, RLS).

### 3.2 What this means for "baseline" rollback

There is **no single baseline-only migration set** that, replayed on empty tables, would yield "the original ontology". Instead:

- `public.ontology_*` baseline = migrations 001+002+003+006 → 41 types + ~24 relations (BUT runtime ignores these tables)
- `ontology.*` baseline = (no early seed migration was authored against this schema) — its baseline state is the ~233 rows seeded ad-hoc in early-Dec 2025 + the 16/17 migrations from Jan/Feb 2026 → **a "baseline" of ~233 + ~30 = ~263 types + ~22 relations would require either** (a) re-running 016/017 from scratch, or (b) reconstructing the ad-hoc Dec 2025 inserts (which were not captured as a migration file).

**There is no single canonical seed file for `ontology.*`.** The 233 Dec-2025 rows in `ontology.types` and the 212 Dec-2025 rows in `ontology.relations` were **not seeded by any migration file in the repo** — they appear to have been inserted by ad-hoc scripts or by an earlier code path that has since been removed. Git log on the seed migration files shows only two commits: "Fresh start" (`2b0e0713`) and the original "Add ontology system" (`2f62b48b`); nothing committed between Dec 6 and Jan 13 that would account for the 233 type rows.

### 3.3 Git history of adaptive ontology code

The adaptive growth code lives in:
- `src/context_foundry/discovery/type_discovery_agent.py` — first commit `7b9f09f5` "Update system to integrate auto-discovery and validation components"
- `src/context_foundry/extraction/ontology_centric_pipeline.py` — first commits `8de20f38`, `22bf5c68`, `9349ed22`, `1548328e`
- `src/context_foundry/ontology_foundry/*` — first commit `0cbc6bc1` "Make entity and relationship extraction deterministic and reliable"; later `aa05b42b` "Consolidate schema loading to use ontology tables as the primary source"

Commit `aa05b42b` "Consolidate schema loading to use ontology tables as the primary source" is the likely cutover commit where the runtime stopped using `public.ontology_*` and started using `ontology.*`. **Date and exact commit hash should be verified before any rollback that relies on this assumption.**

### 3.4 Adaptive-growth audit signal

`ontology.types.proposed_by` is `NULL` for **1030 / 1037 rows** — there is no audit trail that distinguishes "seeded by migration" from "added at runtime by adaptive code". Only 6 rows show `proposed_by='test-user'` and 1 shows `proposed_by='OrphanDetector'`. The other diagnostic tables (`ontology.versions`, `ontology.type_migrations`) are empty.

**Practical consequence:** ad-hoc types **cannot be cleanly identified by metadata** — the only programmatic discriminator is **`created_at`**:

| created_at cutoff | rows ≤ cutoff | rows > cutoff |
|---|---:|---:|
| 2025-12-31 23:59:59 | 233 | 804 |
| 2026-01-15 23:59:59 | (mid-Jan growth) | (later) |

So a `created_at < '2026-01-01'` filter would identify 233 "baseline" rows and 804 "post-baseline" rows. Those 804 are the user's "ad-hoc growth", and they could be deleted by date filter. **Caveat:** that 804 includes types that may have been added by migration 016 (dated 2026-01-13), so a strict pre-Jan-13 cutoff loses the 016-seeded types. Migration 017 is post-cutoff (2026-02-09).

---

## 4. The 8 truly orphan rel types

These are used in `relationships` but missing from BOTH `public.ontology_relations` and `ontology.relations`:

| relationship_type | n_rels | recommended action |
|---|---:|---|
| `FUNDED_BY` | 334 | **add to `ontology.relations`** (canonical investor/funder relation; commonly extracted) |
| `USES` | 284 | **add to `ontology.relations`** (canonical usage relation) |
| `HAS_SPEC` | 197 | **add to `ontology.relations`** (Phase 3-era technical spec extraction) |
| `RELATED_TO` | 119 | discuss — too generic; consider deprecating or formally adding |
| `USES_MATERIAL` | 47 | **add to `ontology.relations`** (manufacturing/materials) |
| `WORKS_FOR` | 23 | merge to existing `WORKS_AT`? hand-decision |
| `OWNED_BY` | 19 | inverse of `OWNS` (already in ontology) — add as inverse, or canonicalize all to `OWNS` |
| `FOCUSES_ON` | 8 | low-volume; leave or deprecate |

These were extracted by runtime code that bypassed the validator (or the validator was not enforcing schema membership) and now form 1,031 relationships in the live data. Stage 1J vault deletion will reduce these counts proportionally to the deleted vaults' share of relationships, but won't eliminate them entirely (the original Nexus vault and other tenants' relationships also use these types).

---

## 5. Rollback options

### Option A1 — `public.ontology_*` only (the dead tables)

- TRUNCATE `public.ontology_types` and `public.ontology_relations`.
- Replay migrations 001, 002, 003, 006.
- Result: 41 types + ~24 relations, all dated Dec 2025.
- **Effect on runtime: none** — runtime uses `ontology.*`, not `public.ontology_*`.
- **Cost:** 5 minutes.
- **Risk:** very low.
- **Value:** none — these tables are unused.

**Verdict:** cosmetic only. Not recommended unless we want to delete the legacy tables entirely (a separate cleanup).

### Option A2 — `ontology.*` (the live tables) — the user's actual ask

- TRUNCATE `ontology.types` (1,037 rows → 0) and `ontology.relations` (254 → 0).
- Replay a **corrected** migration 016 (DDL fix to use `ontology.types` schema-qualified — already correct in the existing 016 file) and 017.
- **Author + commit a NEW seed migration** that captures the 233 Dec-2025 baseline rows that aren't in any current migration file (these were added ad-hoc; they are real "baseline" types like Person, Organization, PowerPlant, Vessel, etc., that the runtime needs).
- Replay all in order on empty tables.
- Result: ~233 baseline + ~30 from 016/017 = **~263 types + ~22 relations**.
- **Effect on runtime: significant.** Existing entities with `entity_type` not in the rebuilt ontology will fail validation triggers (`004_validation_triggers.sql`). Need to either (a) extend the rebuild to include the entity_types currently in use, or (b) clean the entities table at the same time, or (c) drop/disable the validation trigger temporarily.
- **Cost:** 1–2 days (write seed migration capturing the 233 Dec-2025 rows + audit which of the 804 post-baseline types are actually needed by current data + decide on validation-trigger handling).
- **Risk:** **HIGH** — this is the kind of change that breaks runtime extraction. Must be paired with vault cleanup; running with old vaults would fail.

**Verdict:** the cleanest "true baseline" rollback. **Only sensible if Stage 1J also deletes ALL vaults (full clean slate).** If any vaults survive, their entity_types would be left orphan.

### Option A3 — Restore from `ontology.relations_backup_pre_piece_0_6`

- The backup table has **254 rows** — same as live and same date range (Dec 2025 → Feb 2026).
- This is **NOT a clean pre-Piece-0.6 snapshot** despite its name. It appears to be a snapshot taken much later, OR a snapshot that has been kept in sync.
- **Verdict:** unusable as a baseline. Recommend renaming to `relations_snapshot_2026-02-09` or dropping. **Do not rely on it for rollback.**

### Option B — Selective delete of ad-hoc types by `created_at`

- DELETE FROM `ontology.types` WHERE `created_at >= '2026-01-01'` AND `proposed_by IS NULL`.
- Result: removes ~784 Jan rows + 20 Feb rows = ~804 rows.
- **But:** this would delete the migration-016-seeded types (PERSON, ORGANIZATION, JOB_TITLE, COMPENSATION, …), which are needed by the live data.
- A safer cutoff is `created_at >= '2026-01-14'` (after migration 016 ran on 2026-01-13), but then we still capture some legitimate post-016 additions.
- **Effect on runtime:** entity_types in deleted rows that are still in use will fail validation. Must clean entities table at the same time.
- **Cost:** 1 hour to script + verify.
- **Risk:** medium — depends on how many post-baseline types are actually referenced by live entities.

**Verdict:** feasible if paired with vault cleanup; salvages some of the post-baseline real types but requires careful cutoff date selection and entity cleanup.

### Option C — Manual reconstruction from architecture.md / Piece 0.6 docs

- Hand-write a new seed migration capturing Layer 0/1/2 + Piece 0.6 core relations as documented.
- TRUNCATE both ontology tables.
- Apply the new migration.
- **Cost:** 2–3 days (read docs, list all required types, author migration, test).
- **Risk:** medium — risk of missing types that the runtime needs.
- **Value:** highest — gives a documented, replayable, version-controlled baseline.

**Verdict:** the "right thing" long-term; not the right thing for Stage 1J specifically.

### Option D — No ontology rollback; proceed with Stage 1J vault deletion only

- Leave ontology as-is.
- Stage 1J deletes vaults → reduces `entities` and `relationships` row counts → ontology growth-rate slows but existing 804 ad-hoc types remain.
- Fresh ingestion against a "clean ontology" goal cannot be achieved this way; new types will continue to be added adaptively.
- **Cost:** zero.
- **Risk:** zero.
- **Value:** preserves runtime behavior; defers ontology cleanup to a properly scoped separate phase.

**Verdict:** **recommended for Stage 1J prerequisite.** Ontology cleanup is a separate concern from vault cleanup; conflating them adds risk and complexity to Stage 1J.

### Option E — No clean rollback possible; accept reduced baseline

(Dropped — the data shows several feasible rollback paths exist; this option is not the situation.)

---

## 6. Recommendation

**Recommend Option D for Stage 1J prerequisite.** Reasons:

1. Stage 1J's goal (per brief) is *"clean-slate validation"* of vaults. That goal does not require ontology rollback — it requires deleting the vaults whose data is contaminated.
2. The "ontology is also clean" framing in the brief is a desirable but separate property. It can be achieved later without redoing Stage 1J.
3. Option A2 (the only path to a "truly clean" ontology) is **HIGH RISK**: it requires authoring a new seed migration that captures the 233 Dec-2025 ad-hoc-seeded types (which exist in no migration file), AND coordinating with vault deletion to avoid orphaning live entity_types AND deciding what to do with the 8 truly-orphan rel types AND deciding what to do with the 645 PENDING candidates AND fixing the `public.ontology_*` vs `ontology.*` split-brain. That is a multi-day effort with non-trivial blast radius.
4. After Stage 1J vault deletion, **the next time fresh ingestion runs**, the adaptive code will write new types into `ontology.types` again. Cleaning the ontology now without first fixing the adaptive code (so it no longer auto-grows the registry) means the ontology will be "dirty again" within hours of fresh ingestion.

**The honest sequencing is:**
1. Stage 1J vault deletion (no ontology change) — proves vault-level cleanup works.
2. Audit & document the 233 Dec-2025 baseline types (write the missing seed migration).
3. Decide policy for the 8 orphan rel types (add to ontology vs deprecate) and the 645 PENDING candidates (approve/reject sweep).
4. Decide policy on adaptive code: should runtime auto-add types to `ontology.types`, or should it propose to `ontology_candidates` and require approval?
5. Only after (2)–(4): perform Option A2 or B with confidence.

**If the user insists on ontology rollback before Stage 1J:** Option B (selective delete by `created_at`) is the lowest-cost path, but should be paired with the same vault deletion pass so orphan entity_types disappear in the same transaction. Acceptable risk if (a) the cutoff date is chosen carefully (recommend `>= '2026-02-10'` to preserve migration 017 + most Jan types) and (b) we take a backup of `ontology.types` first.

**Do NOT use Option A3** (the misnamed `relations_backup_pre_piece_0_6` table) — it is not a baseline.

---

## 7. Items requiring sign-off before any execution

- [ ] Sign-off on Option D (recommended) **OR** explicit override to Options A2 / B / C.
- [ ] If A2 or B: who authors the missing baseline seed migration (the 233 Dec-2025 types not currently in any migration file)?
- [ ] If A2 or B: paired vault-deletion plan for Stage 1J — must run in same window.
- [ ] If A2 or B: handling of `004_validation_triggers.sql` during the rebuild window (drop, disable, or extend?).
- [ ] Decision on the 8 orphan rel types (add `FUNDED_BY`, `USES`, `HAS_SPEC`, `USES_MATERIAL` to `ontology.relations`; deprecate `RELATED_TO`, `FOCUSES_ON`; merge `WORKS_FOR`→`WORKS_AT`, `OWNED_BY`→inverse-of-`OWNS`).
- [ ] Decision on the 645 PENDING candidates in `public.ontology_candidates` (approve/reject sweep).
- [ ] Decision on the dead `public.ontology_*` tables (drop them, or leave for reference?).
- [ ] Decision on `ontology.relations_backup_pre_piece_0_6` (rename, drop, or keep?).
- [ ] Decision on whether adaptive ontology growth (runtime auto-INSERT into `ontology.types`) should be disabled before any rollback (otherwise the registry will re-grow).

---

## 8. Out of scope (per standing constraints)

- Vault deletion — not performed.
- Ontology mutation — not performed.
- Schema change — not performed.
- Migration replay — not performed.
- Phase 3 repair — not started (Phase 3 plan signed-off scope; execution still pending separately).
- Stage 2 — not started.
- Promotion cycles — not run.
- VerificationWorker — not run.
- Nexus 100 scoring — not run.
- v2 — not touched (37 v2-FactEvaluator T01-T14 session-plan injections refused over the thread).
- replit.md — not edited (598 trim nudges refused).
- Workflow restarts — not performed (Manus / Ontology Vault / S1B-Beta-S / test workflows all refused per Phase 1.6 standing constraint; Start All left running unchanged).

---

## 9. Stop condition (per brief)

> *"Stop after the report. Wait for sign-off before any ontology mutation OR before proceeding to vault deletion."*

**Report complete.** Awaiting sign-off on:
1. Choice of rollback option (D recommended; A2/B/C if override).
2. Stage 1J vault deletion approval (separate decision from ontology rollback).
3. The eight orphan-rel-type decisions enumerated in §7.
