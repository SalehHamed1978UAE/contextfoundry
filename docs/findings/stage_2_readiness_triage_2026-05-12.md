# Stage 2 Readiness Triage — Read-Only Audit

**Date:** 2026-05-12
**Brief:** `docs/inbox/stage_2_readiness_triage_2026-05-12.md`
**Mode:** Read-only. No code changes, no DB mutations, no schema changes.
**Refs:**
- Stage 1J validation: `docs/findings/stage_1j_fresh_ingestion_validation_2026-05-12.md`
- Stage 1K fix: `docs/findings/stage_1k_verification_worker_deadlock_fix_2026-05-12.md`
- Operating instructions: `docs/operating_instructions.md`

---

## TL;DR

**Verdict: B — Stage 2 design conversation can begin now; Stage 2 implementation needs one bounded fix first; Stage 2 default activation needs three fixes.**

The clean Stage 1J vault is structurally clean (2146 STAGING entities, 2099 STAGING relationships, 0 TRUSTED, 0 ARCHIVED, 0 cross-tenant contamination). The Stage 1K VerificationWorker fix is durable. But the path **STAGING → TRUSTED has never run end-to-end on this vault**: only ~2.5% of facts are verified, no Gardener pass has executed, and 6 facts are flagged NEEDS_REVIEW. Until at least one bounded promotion cycle has demonstrably moved facts to TRUSTED on this vault, Stage 2 implementation is premature. Three orphan-relation/schema items must be resolved before Stage 2 can be activated by default — though they are all small/medium scope and can be sequenced cheaply.

---

## 1. Current clean-vault state — `ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda`

### 1.1 Lifecycle counts

| Metric | Value | Note |
|---|---|---|
| Documents | 100 | full Stage 1J ingest |
| Entities, total | 2146 | |
| Entities, STAGING | 2146 | **100% — no promotion cycle has run** |
| Entities, TRUSTED | 0 | |
| Entities, ARCHIVED | 0 | |
| Relationships, total | 2099 | |
| Relationships, STAGING | 2099 | **100% — same** |
| Relationships, TRUSTED | 0 | |
| Relationships, ARCHIVED | 0 | |

### 1.2 Verification state (post Stage 1K validation)

| Metric | Value |
|---|---|
| `entities.verified=true` | 36 (1.7% of 2146) |
| `entities.verified=false` | 2110 |
| `relationships.verified=true` | 10 (0.5% of 2099) |
| `relationships.verified=false` | 2089 |
| `fact_verifications` rows total | 55 |
| `fact_verifications` VERIFIED | 49 |
| `fact_verifications` REJECTED | 0 |
| `fact_verifications` NEEDS_REVIEW | 6 |
| Entities `evidence_verification_status=VERIFIED` | 36 |
| Entities `evidence_verification_status=UNVERIFIED` | 2110 |
| Relationships `evidence_verification_status=VERIFIED` | 10 |
| Relationships `evidence_verification_status=NEEDS_REVIEW` | 4 |
| Relationships `evidence_verification_status=UNVERIFIED` | 2085 |

The 6 NEEDS_REVIEW (2 entities + 4 relationships) are real, signal-bearing — the verifier is not just rubber-stamping. Stage 2 must define what happens to NEEDS_REVIEW facts (queue, manual review, soft-trust, etc.).

### 1.3 Promotion state

- **No Gardener pass has run on this vault.** Zero TRUSTED facts.
- No `promotion error count` to report — none attempted.
- No `result.errors` from a promotion run — none attempted.
- `block_reasons` distribution **not measurable**: there is no `skip_reasons`/`block_reasons` column on `entities` or `relationships`. (The column-search hit 22 unrelated `*_reason` columns on other tables — none on the fact tables themselves.)

### 1.4 Cross-tenant invariants — still frozen ✅

| Invariant | Value | Source-of-truth timestamp |
|---|---|---|
| Latest cross-tenant `relationships.updated_at` | `2026-05-11 05:59:56.823` | unchanged since Stage 1J baseline |
| `merge_audits` row count | 3901 | unchanged |
| Latest `merge_audits.merged_at` | `2026-05-11 05:59:59.118` | unchanged |
| `ontology.types` count | 1037 | unchanged |
| `ontology.relations` count | 254 | unchanged |

The Stage 1K fix has not introduced cross-tenant drift.

---

## 2. Extraction / ontology alignment

### 2.1 Distributions on clean vault

**Relationship types (17 distinct):** `PART_OF` 272, `HOLDS_POSITION` 272, `OWNS` 209, `PRODUCES` 192, `FUNDED_BY` 188, `CUSTOMER_OF` 187, `LOCATED_AT` 158, `LEADS` 125, `USES` 119, `PARTNER_OF` 109, `SUPPLIER_OF` 105, `RELATED_TO` 76, `REPORTS_TO` 52, `OWNED_BY` 17, `FOCUSES_ON` 8, `WORKS_FOR` 7, `MANAGES` 3.

**Entity types (14 distinct):** `FINANCIAL_METRIC` 384, `PERSON` 304, `PROJECT` 279, `ORGANIZATION` 200, `PRODUCT` 160, `BUSINESS_UNIT` 150, `LOCATION` 122, `TECHNOLOGY` 106, `CUSTOMER` 98, `FACILITY` 96, `POLICY` 96, `SUPPLIER` 65, `PARTNER` 50, `SERVICE` 36.

### 2.2 Ontology hygiene baseline

| Metric | Value |
|---|---|
| `ontology.types` total | 1037 |
| Layer 1 (governed) | 24 ACTIVE |
| Layer 2 (auto-proposed / ad-hoc) | 1006 ACTIVE + 2 PROPOSED = 1008 |
| Layer 3 (schemas) | 3 ACTIVE + 2 APPROVED = 5 |
| `ontology.relations` total | 254 |
| Status: ACTIVE | 253 |
| Status: DEPRECATED | 1 |
| Lower-cased `type_name` count | 0 |
| `invalid_*`/`unknown_*` named types | 0 |

The "803 ad-hoc types" cited in the brief is not literally that number anymore — it's now **1008 Layer-2 types**. Layer-2 = auto-proposed types. Type names are properly upper-snake-cased (no junk lower-case patterns survive). Stage 1K's earlier Gardener `validate_against_ontology` change should be keeping this from growing further; this remains worth governance review.

### 2.3 Orphan relation types (in vault, not in `ontology.relations`)

**6 orphan relation types covering 415 of 2099 relationships (19.8%):**

| relation | count in vault | in ontology? | recommended classification |
|---|---|---|---|
| `FUNDED_BY` | 188 | **no** | should be added through governance later — high-frequency, semantically meaningful |
| `USES` | 119 | **no** | should be mapped to existing governed relation (probably `USES_TECHNOLOGY` or split by target type) |
| `RELATED_TO` | 76 | **no** | should be blocked from extraction — semantically void, dilutes precision |
| `OWNED_BY` | 17 | **no** | should be mapped to existing governed relation — likely inverse of `OWNS` (already-governed) |
| `FOCUSES_ON` | 8 | **no** | should be added through governance later OR mapped to `RESPONSIBLE_FOR` if exists |
| `WORKS_FOR` | 7 | **no** | should be mapped to `HOLDS_POSITION`/`AFFILIATED_WITH` — a duplicate-by-synonym |

**2 brief-listed orphans not present in this vault:** `HAS_SPEC`, `USES_MATERIAL` — neither extracted on this corpus, governance can be deferred until a corpus actually generates them.

All 8 brief-listed candidates are also missing from `ontology.relations` table itself (verified by direct lookup of `relation_type` column) — so the orphan-ness is at the ontology layer, not just the vault layer.

### 2.4 Orphan entity types

**Only 1 orphan entity type** in the clean vault: `PROJECT` (279 occurrences).

This is a **case-mismatch artifact**, not a true gap. `ontology.types` contains `Project` (Layer 2, ACTIVE), `ProjectManager`, `ProjectPhase`, `ProjectSponsor` — all PascalCase. The extractor emits `PROJECT` (UPPER_SNAKE) and the ontology has `Project` (PascalCase). All 13 other vault entity types are governed (cased to match).

This is a **trivially-fixable normalizer bug**: either case-fold both sides at validation time, or pick one canonical case and migrate. Cheap. **Stage 1L candidate.**

### 2.5 Ad-hoc ontology types created during fresh extraction

Cannot determine "during fresh extraction" precisely without timestamp comparison against a known baseline. What we can say:
- 1008 Layer-2 types currently exist; the Stage 1K Gardener `validate_against_ontology=True` flag should now block new ones from being added during promotion. New auto-creation during *extraction* (before Gardener) is a separate question requiring extractor-prompt audit.
- No `invalid_*`/`unknown_*` patterns remain → prior cleanup already ran.

---

## 3. Remaining v1 launch backlog — categorized

### 3.1 Must fix before Stage 2 design

*(None.)* Design conversations can proceed with current evidence. The Stage 1J/1K work has produced the clean baseline needed to reason about Stage 2 shape.

### 3.2 Must fix before Stage 2 implementation

| # | Item | Scope | Why it matters | Order |
|---|---|---|---|---|
| 1 | **Run at least one bounded Gardener promotion cycle on `ecd2f1c2-...`** to demonstrate STAGING→TRUSTED end-to-end on a clean vault | small (one auth'd command + observation) | Stage 2 will be built on top of TRUSTED facts — we have never observed a successful promotion on this vault. Could surface `verified=true` requirement gating + ontology-validation gating + cross-tenant invariant interactions only when run. | **first** |
| 2 | **NEEDS_REVIEW handling design** — what queue, who reviews, what unblocks promotion | small (design) → medium (impl) | 6/55 (≈11%) of verifications already flagged NEEDS_REVIEW. Stage 2 must have a defined story for these or they'll silently rot in STAGING forever. | second |

### 3.3 Must fix before Stage 2 default activation

| # | Item | Scope | Why it matters | Order |
|---|---|---|---|---|
| 3 | **Phase 4: relationship endpoint tenant-alignment DB guard** (trigger or check constraint) | small | Today nothing at the DB level prevents a relationship from pointing at an entity in a different tenant. Stage 1J showed this can happen if app-layer code regresses. Trigger is a permanent guard. | third |
| 4 | **Phase 5: `duplicate_candidates` and `merge_audits` `tenant_id` columns + FK cascade policy** | medium (schema migration) | Confirmed: neither table has `tenant_id`. Cross-tenant merge audits would be unattributable; tenant deletion would orphan rows. Blocks any Stage 2 multi-tenant operational story. | fourth |
| 5 | **6 orphan relation types resolution** (mapping decisions for FUNDED_BY, USES, RELATED_TO, OWNED_BY, FOCUSES_ON, WORKS_FOR) | medium | 415/2099 (19.8%) of vault relationships are governance-orphan. Stage 2 retrieval/reasoning over these is meaningless — they will either be silently dropped at promotion (validate_against_ontology=True will reject them) or will leak ungoverned semantics into TRUSTED. | fifth |
| 6 | **`relationships.source_document_id` varchar→uuid schema migration** | small (data is already UUID-shaped strings) | Confirmed varchar today. Type-mismatch causes silent join misses and wins from this fix are immediate. | sixth |

### 3.4 Can defer with known limitation

| # | Item | Scope | Why deferable |
|---|---|---|---|
| 7 | Scheduler per-tenant iteration design (`scheduler.py:225 NotImplementedError`) | medium | Manual per-tenant invocation works for Stage 2 launch on a small fleet. Needed only when tenant count grows. |
| 8 | Single-shot Gardener / scheduler activation | small | Acceptable to run gardener manually for early Stage 2 customers. |
| 9 | 803 → 1008 ad-hoc Layer-2 ontology types governance hygiene | medium | Already non-growing if Stage 1K validate_against_ontology=True is in effect. Audit & retire dormant types after a quarter of measurement. |
| 10 | Stage 1L: `lock_timeout` hardening on VerificationWorker | small | Stage 1K's deadlock-retry already handles the failure mode. `lock_timeout` is depth-in-defense, not on the critical path. |
| 11 | Stage 1L: deterministic ordering for other verification writers (`web_app.py` L2734, `brain/app.py` kg_ingestor) | small per writer | Stage 1K's worker is now a clean retry victim — those writers can deadlock with each other but the symptom is bounded retry, not corruption. |
| 12 | Stage 1L: `extraction_level` UUID/text bulk-update bug (`scripts/run_vault_extraction.py` L1273-1278) | small | Affects re-extraction script only, not extraction or query. |
| 13 | Cold-corpus adaptive ontology validation | medium | Only matters when Stage 2 onboards a domain we haven't seen. Manageable per-domain. |
| 14 | MultiModelExtractor staged activation | medium | Single-model is sufficient for Stage 2 v1 launch correctness; multi-model is a quality lever for later. |
| 15 | `audit_records` consumer / review queue | medium | Becomes urgent once Stage 2 has paying customers. Pre-launch we can read the table directly. |

### 3.5 Future architecture / Piece 3+

| # | Item | Why future |
|---|---|---|
| 16 | v2 / FactEvaluator | deprioritized per operating instructions, do not re-open here |
| 17 | RLM integration (per `docs/RLM_*` specs) | downstream of Stage 2 stability |
| 18 | Tree-based retrieval (parked at v1 ceiling 77/100) | quality lever, not Stage 2 prerequisite |

### 3.6 No longer needed

| # | Item | Status |
|---|---|---|
| 19 | Phase 3 historical contamination repair | **NOT REQUIRED** — historical contaminated vaults are forensic/adversarial fixtures per operating_instructions.md |
| 20 | Re-running the contaminated S1B vaults | NOT REQUIRED |
| 21 | Nexus 100 scoring before Stage 2 design | NOT REQUIRED — Nexus is a v1 ceiling artifact, doesn't gate Stage 2 |
| 22 | Full VerificationWorker run on contaminated vault | NOT REQUIRED — Stage 1K validation on the *clean* vault is the production-relevant signal |

### 3.7 Newly discovered backlog items (from this audit)

| # | Item | Category |
|---|---|---|
| 23 | `PROJECT` (UPPER) ↔ `Project` (Pascal) entity-type case-mismatch | Stage 1L (small) — would otherwise be classified as ontology orphan even though semantically present |
| 24 | NEEDS_REVIEW resolution workflow (already listed as item 2 above) | Must-fix-before-Stage-2-impl |

---

## 4. Stage 2 readiness verdict

**B. Stage 2 needs one more bounded fix first.** Specifically:

- **Stage 2 design conversation:** READY NOW. The clean-vault evidence is sufficient to reason about Stage 2 shape, scope, and customer-facing surface. No further measurement gates this conversation.
- **Stage 2 implementation:** NEEDS one bounded fix first — execute a single authorized bounded Gardener promotion cycle on `ecd2f1c2-...` to demonstrate STAGING→TRUSTED end-to-end. Without this, we are building on an unproven promotion path. (~30 min wall-clock.)
- **Stage 2 default activation (turning it on for real customers):** NEEDS the three Phase-4/Phase-5/orphan-relations items (3, 4, 5 above) plus the small `source_document_id` migration (6). All are small/medium scope. Estimated 1–2 weeks if sequenced.

---

## 5. Recommended sequence

Optimized for: minimum work that unblocks Stage 2 design → maximum confidence before Stage 2 ship.

```
1. (auth required, small)   Authorize one bounded Gardener promotion cycle on
                            `ecd2f1c2-...`. Observe: how many of the 36/10
                            verified facts actually promote. Capture verified-
                            but-unpromotable count (likely ontology-orphan
                            blocks). This is the single highest-information
                            cheap action.

2. (design, no code)        Stage 2 design conversation. Inputs are now:
                            clean-vault state + STAGING→TRUSTED conversion
                            rate from step 1 + NEEDS_REVIEW rate (~11%) +
                            orphan-relation impact (19.8%).

3. (small)                  Decide & implement the 6 orphan-relation
                            mappings/blocks (item 5). Mechanical: 
                            RELATED_TO→block, OWNED_BY→inverse-of OWNS,
                            WORKS_FOR→HOLDS_POSITION/AFFILIATED_WITH,
                            FUNDED_BY→govern-as-new, USES→split-by-target,
                            FOCUSES_ON→govern-or-map. Re-run promotion to
                            measure delta.

4. (small)                  Phase 4 trigger — DB-level relationship endpoint
                            tenant-alignment guard (item 3). Defense in
                            depth, prevents future Stage 1J-style
                            regressions.

5. (small)                  Schema: relationships.source_document_id 
                            varchar→uuid (item 6). Mechanical migration.

6. (medium)                 Phase 5 — duplicate_candidates / merge_audits
                            tenant_id columns + FK cascade (item 4).

7. (small)                  Stage 1L cleanup batch: PROJECT case-mismatch
                            (item 23), extraction_level UUID bug (item 12),
                            other-writer deterministic ordering (item 11),
                            lock_timeout hardening (item 10).

8. (design)                 NEEDS_REVIEW workflow design + impl (item 2).

9. (defer)                  Items 7-9 (scheduler activation), 13-15 
                            (multi-model, cold-corpus, audit consumer)
                            picked up as Stage 2 maturity / customer
                            demand drives.
```

Step 1 is the **single most valuable next action** — it converts ~300 lines of "should work" into observed behavior at minimal cost.

---

## 6. What is no longer required

Per operating_instructions.md "Historical contaminated vaults are forensic/adversarial fixtures unless a specific use case requires repair":

| Question | Answer |
|---|---|
| Phase 3 historical contamination repair? | **NO** — fixtures preserved, not repaired |
| Re-run contaminated S1B vaults? | **NO** — keep as adversarial fixtures |
| Nexus 100 scoring before Stage 2 design? | **NO** — v1 ceiling artifact, orthogonal to Stage 2 |
| Full VerificationWorker run on contaminated vault? | **NO** — clean-vault path is the production-relevant signal |

---

## 7. What remains blocked / what is safe to defer

**Blocked (needs explicit user authorization per operating_instructions.md):**
- Step 1 above — bounded Gardener promotion cycle (counts as "production data mutation outside the active diagnostic target" since it would write TRUSTED rows)
- Items 3, 4, 6 (schema changes)
- Item 5 (ontology change — `global ontology change`)
- Stage 2 default activation
- Scheduler activation (items 7, 8)

**Safe to defer indefinitely:**
- v2 / FactEvaluator (item 16) — operating instructions: deprioritized
- Tree-based retrieval (item 18) — v1 ceiling reached, not on Stage 2 critical path
- Items 9, 10, 11, 12, 13, 14, 15 — labeled `Can defer` above

---

## Stop condition

**Stop here.** This is a read-only triage. Awaiting sign-off before any new Phase, fix, schema work, scheduler activation, ontology mutation, promotion cycle, or Stage 2 implementation per the brief's stop condition.

---

**Findings doc path:** `docs/findings/stage_2_readiness_triage_2026-05-12.md`
