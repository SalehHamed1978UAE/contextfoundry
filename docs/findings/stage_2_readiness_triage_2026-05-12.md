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

---

## 8. Bounded Gardener Promotion Result — 2026-05-12 (added post-triage)

**Brief:** `docs/inbox/stage_2_readiness_promotion_validation_2026-05-12.md` — authorized one bounded tenant-scoped Gardener promotion cycle on `ecd2f1c2-...` to validate STAGING→TRUSTED end-to-end on the clean Stage 1J vault.

### 8.1 Run

- **Command:** `PYTHONPATH=. python -u scripts/run_promotion.py --tenant-id ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda`
- **Execution:** Foreground bash launch died at t=20s (sandbox killed detached child, same Stage 1K pattern). Authorized one-shot workflow `Stage2-Promo-ecd2f1c2` (autoStart, console outputType, 1 free slot in 9/10) per brief allowance — no slot removal needed.
- **Cycle ID:** `manual-ecd2f1c2`
- **Runtime:** 373.45s
- **Exit status:** 0 (workflow `finished` cleanly)
- **Commit:** confirmed via `ts._session.commit()` in script + post-snapshot deltas
- **Errors:** `[]` (none)

### 8.2 Outcome — **Case 1: Meaningful TRUSTED promotion**

| Metric | Pre | Post | Delta |
|---|---|---|---|
| Entities STAGING | 2146 | 73 | **−2073** |
| Entities TRUSTED | 0 | 2073 | **+2073 (96.6% conversion)** |
| Entities ARCHIVED | 0 | 0 | 0 |
| Relationships STAGING | 2099 | 484 | **−1615** |
| Relationships TRUSTED | 0 | 1615 | **+1615 (76.9% conversion)** |
| Relationships ARCHIVED | 0 | 0 | 0 |
| `gardener_logs` PROMOTE actions for cycle | 0 | 3688 | +3688 (= 2073 + 1615) ✓ |

### 8.3 Block reasons (entities: 73 blocked)

| Type | Blocked | Reason |
|---|---|---|
| FACILITY | 25 | confidence_too_low |
| PRODUCT | 18 | confidence_too_low |
| PROJECT | 12 | confidence_too_low |
| FINANCIAL_METRIC | 11 | confidence_too_low |
| LOCATION | 3 | confidence_too_low |
| ORGANIZATION | 2 | confidence_too_low |
| BUSINESS_UNIT | 1 | confidence_too_low |
| PERSON | 1 | confidence_too_low |

All entity blocks are confidence-threshold misses. **Zero entities blocked by `invalid_entity_type_*`** — the ontology validation passed for every type present, including `PROJECT`.

### 8.4 Block reasons (relationships: 484 blocked)

| Type | Blocked | Reason |
|---|---|---|
| FUNDED_BY | 188 | invalid_relationship_type (not in ontology.relations) |
| USES | 119 | invalid_relationship_type |
| RELATED_TO | 76 | invalid_relationship_type |
| OWNED_BY | 17 | invalid_relationship_type |
| FOCUSES_ON | 8 | invalid_relationship_type |
| WORKS_FOR | 1 | invalid_relationship_type |
| (mixed) | 75 | confidence_too_low |
| **Total** | **484** | |

The 6 governed-orphan relation types account for 409/484 (84.5%) of relationship blocks; threshold-confidence misses are the remaining 75.

### 8.5 Cross-tenant + ontology invariants — held

| Invariant | Pre | Post | Delta |
|---|---|---|---|
| Latest cross-tenant `relationships.updated_at` | `2026-05-11 05:59:56.823` | `2026-05-11 05:59:56.823` | **unchanged ✓** |
| Cross-tenant rels rooted at this vault | 0 | 0 | unchanged ✓ |
| `merge_audits` row count | 3901 | 3901 | unchanged ✓ |
| `ontology.types` count | 1037 | 1037 | unchanged ✓ |
| `ontology.relations` count | 254 | 254 | unchanged ✓ |

Promotion did **not** mutate ontology, did **not** create cross-tenant relations, did **not** trigger merge.

### 8.6 Orphan relation impact + recommended disposition

(Updated from §2.3 with measured promotion behavior. Existing governed alternatives confirmed by direct query of `ontology.relations.relation_type`.)

| relation | STAGING (pre) | promoted | blocked | recommended disposition | rationale |
|---|---|---|---|---|---|
| `FUNDED_BY` | 188 | 0 | 188 | **add through governance later** | high-frequency, semantically meaningful, no governed equivalent |
| `USES` | 119 | 0 | 119 | **map to existing governed relation** (split by target type → `DEVICE_USED_IN`, `FLIGHT_USES_RUNWAY`, etc., or add generic `USES` to governance) | overloaded; ontology has 3 type-specific `*USES*` variants |
| `RELATED_TO` | 76 | 0 | 76 | **block from extraction** | semantically void; dilutes precision |
| `OWNED_BY` | 17 | 0 | 17 | **map to existing governed relation `OWNS`** (inverse) | `OWNS` is governed (4 variants in ontology); `OWNED_BY` = inverse direction redundancy |
| `FOCUSES_ON` | 8 | 0 | 8 | **add through governance later** OR accept as known limitation | low-frequency; defer |
| `WORKS_FOR` | 7 | 0 (1 blocked invalid + 6 blocked confidence-or-missing) | 7 still STAGING | **map to existing governed `HOLDS_POSITION` / `AFFILIATED_WITH` / `WORKS_AT`** | duplicate-by-synonym; all three governed equivalents exist in ontology |

Ontology query confirmed: `HOLDS_POSITION`, `AFFILIATED_WITH`, `OWNS`, `PART_OF`, `WORKS_AT`, `MEMBER_OF` all governed and available as mapping targets.

### 8.7 PROJECT casing impact — **not a blocker after all**

- Pre: 279 PROJECT entities, all STAGING. Triage §2.4 hypothesized this was an `invalid_entity_type` blocker requiring Stage 1L fix.
- Post: **267 promoted, 12 blocked** — and the 12 are blocked **for `confidence_too_low_PROJECT`, NOT for `invalid_entity_type_PROJECT`**.
- Ontology contains `Project` (PascalCase, Layer-2 ACTIVE). The Gardener's `validate_against_ontology` check is evidently case-insensitive (or some normalization layer normalizes `PROJECT` → `Project` on validation). Either way, **promotion-path validation does not block on casing**.
- **Revised classification:** PROJECT casing fix is **NOT a Stage 2 implementation prerequisite**. It remains a **cosmetic Stage 1L candidate** for ontology hygiene (one canonical case across both layers) but does not gate Stage 2.

### 8.8 Updated Stage 2 readiness verdict

**Verdict upgrade: B → B+ (Stage 2 implementation cleared; default activation still gated).**

| Gate | Pre-promotion (§4) | Post-promotion |
|---|---|---|
| Stage 2 design conversation | READY | READY (unchanged) |
| Stage 2 implementation | NEEDS one bounded fix first | **READY** — STAGING→TRUSTED end-to-end demonstrated on clean vault, 96.6% / 76.9% promotion rate, zero errors, all invariants held |
| Stage 2 default activation | NEEDS items 3, 4, 5, 6 | NEEDS items 3, 4, **revised-5**, 6 (see 8.9) |

### 8.9 Revised "must-fix-before-default-activation" item 5

Item 5 (orphan relations) gets **specific, measurable mapping decisions** based on §8.6:
- `OWNED_BY` (17) → map to inverse of `OWNS` — small change in extraction or post-extraction normalization
- `WORKS_FOR` (7) → map to `HOLDS_POSITION`/`AFFILIATED_WITH`/`WORKS_AT` — small change
- `RELATED_TO` (76) → block in extraction prompt — small change
- `FUNDED_BY` (188), `USES` (119), `FOCUSES_ON` (8) → governance addition (3 new ontology rows) — single small migration

Worst-case impact if all 6 are addressed: **+409 promoted relationships → ~2024/2099 = 96.4% relationship promotion rate** (matching the entity rate).

### 8.10 Recommended next action

Per stop condition, **stop and await sign-off**. Recommended next-step ordering once authorized:

1. (small) Decide & implement the 6 orphan-relation mappings/blocks (item 5 / §8.9). Re-run promotion to confirm ~96% relationship promotion.
2. (small) Phase 4 trigger — DB-level relationship endpoint tenant-alignment guard (item 3).
3. (small) `relationships.source_document_id` varchar→uuid migration (item 6).
4. (medium) Phase 5 — `duplicate_candidates` / `merge_audits` `tenant_id` columns (item 4).
5. (design) NEEDS_REVIEW workflow design (item 2).

Stage 2 implementation work itself can begin in parallel with 1–4 above.

### 8.11 Stop

**Stopping here per brief stop condition.** No scheduler activation, no Stage 2 implementation, no ontology mutation, no orphan repair, no PROJECT normalizer fix, no schema/trigger work, no contaminated-vault repair, no Nexus 100, no v2, no replit.md edits, no further promotion cycles. Awaiting sign-off.

---

## 9. Hold-Position Decision — 2026-05-12 (post-promotion sign-off)

**Brief:** `docs/inbox/stage_2_hold_position_2026-05-12.md`

The Stage 2 Readiness Promotion Validation result (§8) is **accepted**. Engineering pauses here pending a human Stage 2 design conversation.

### 9.1 Accepted state

- Clean vault `ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda`: 96.6% entity / 76.9% relationship promotion
- Cross-tenant invariant held; ontology unchanged
- VerificationWorker fixed (Stage 1K); IdentityResolver tenant isolation fixed (Stage 1J)
- Gardener promotion works on clean tenant-local data

### 9.2 Updated readiness verdict (locked at this revision)

| Gate | Status |
|---|---|
| Stage 2 design conversation | **READY** |
| Stage 2 implementation | **READY to discuss, NOT YET AUTHORIZED** |
| Stage 2 default activation | **NOT READY** — gated by product/governance decisions, not just engineering |

### 9.3 Hold-position prohibitions

- Do **not** start Stage 2A orphan relation analysis
- Do **not** start any new engineering phase
- Do **not** mutate ontology
- Do **not** add schema constraints
- Do **not** run more promotion cycles
- Do **not** start Stage 2 implementation

### 9.4 Stage 2 design questions preserved for advisor conversation

(Engineering must not pre-decide these; they are product/governance scope.)

1. **Orphan relation policy** — for each of FUNDED_BY, USES, RELATED_TO, OWNED_BY, FOCUSES_ON, WORKS_FOR: govern / map to existing / block from extraction / STAGING-only / emit gap-audit signal?
2. **Generic relation policy** — are RELATED_TO / USES / FOCUSES_ON acceptable in a governed world model, or must extraction always prefer typed-specific relations?
3. **Ontology governance process** — for any addition (e.g., FUNDED_BY): who approves; what evidence required; source/target type signatures enumerated; Ontology Foundry lifecycle; UUID provenance (migration vs governance flow)?
4. **Canonicalization location** — for mappings (OWNED_BY → OWNS+invert; WORKS_FOR → WORKS_AT/HOLDS_POSITION/AFFILIATED_WITH; USES → domain variants): post-processor / canonicalizer / Gardener validation / ontology governance table / prompt instruction?
5. **Default-activation gate** — what must be true before scoped extraction becomes default: schema tenant guard, scheduler design, orphan relation policy, `source_document_id` migration, `duplicate_candidates`/`merge_audits` tenant columns, NEEDS_REVIEW workflow?

### 9.5 Recommended ordering from §8.10 — **suspended**

The 5-step "next action" sequence in §8.10 is suspended pending the design conversation. None of those steps may be started until a human design decision authorizes them.

### 9.6 Stop

**Stopping and waiting.** Next step is a human Stage 2 design conversation, not another engineering task. Standing constraints continue: continue refusing v2 injections, do not edit `replit.md`, do not restart unrelated workflows, do not start Stage 2 implementation.

---

**Findings doc path:** `docs/findings/stage_2_readiness_triage_2026-05-12.md`
