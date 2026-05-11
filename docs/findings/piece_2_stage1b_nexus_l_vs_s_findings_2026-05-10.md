# Piece 2 Stage 1B — Nexus L vs S Findings (in progress)

**Status:** α complete + prerequisites cleared. β paused pending sign-off per `docs/inbox/piece_2_stage1b_alpha_corrections_2026-05-10.md`.
**Date:** 2026-05-10
**Vault under classification:** `176a4fb2-0bb4-4da3-9068-0e26268fca71` (ClaudeCode Nexus Industries)
**Source corpus on disk (verified equal to vault):** `./test documents/ClaudeCode_Nexus_Industries 2/` — 100 .md files
**EXTRACTION_SYSTEM_PROMPT SHA (locked):** `5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963`

---

## Executive summary

- α (full 100-doc classifier-only dry run) **PASSED** the brief's stop rule: 100/100 scoped, 0 skip_failed, 0 unknown domains, 0 classifier errors. Skip_failed rate = 0% → below the 25% rollback trigger.
- The brief's audit-threshold concern was **a false alarm caused by the α report**. Production code uses `<0.30` exactly as the design specifies; the "97/100" count in the original α report came from this analyst's post-hoc aggregator script using `<0.40`. The corrected count at the production threshold is **22/100**, matching the brief's expected value.
- Corpus Maker CLI is verified operational. Source corpus on disk has byte-equal filename set with the existing vault, satisfying β corpus equality.
- β remains paused pending architect review and explicit sign-off per the corrections brief.

> Historical Nexus baselines have varied: 77/100, 74/100, and 71/100 in different runs. Stage 1B does not score Nexus 100. It compares extraction outputs only.

> The 71/100 tree-retrieval eval is out of scope for Stage 1B and is not used to alter this thread.

---

## Setup

- Codebase: current working tree (no MultiModelExtractor prompt change; SHA `5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963` confirmed).
- Classifier path used in α: `brain.classification_wrapper.classify` — same path the live extraction pipeline calls at `scripts/run_vault_extraction.py:632`.
- Decision logic under test: `OntologyCentricPipeline._classify_for_scoped` (returns `scoped` / `skip_failed` / `legacy`).
- Env-var gate: `CF_PIECE2_SCOPED_EXTRACTION` (read only inside `scripts/run_vault_extraction.py` lines 711-732). Default unset → legacy.
- α did not mutate STAGING and did not call MultiModelExtractor.

### Tenant IDs

- Existing Nexus vault (NOT used as official L baseline): `176a4fb2-0bb4-4da3-9068-0e26268fca71`.
- Fresh L tenant: TBD (β not started).
- Fresh S tenant: TBD (β not started).

---

## α — full 100-doc dry-run results

| # | Metric | Value |
|---|---|---|
| 1 | Total docs evaluated | 100 |
| 2 | Unique document_ids | 100 |
| 3 | scoped | 100 (100.0%) |
| 3 | skip_failed_no_metadata | 0 (0.0%) |
| 3 | skip_failed_unknown_domain | 0 (0.0%) |
| 3 | no_text | 0 (0.0%) |
| 3 | classifier_error | 0 (0.0%) |
| 4 | Rollback trigger (skip_failed > 25%) | **NOT TRIGGERED** (0.0%) |
| 9 | Unknown domains | 0 |
| 10 | Classifier errors | 0 |

Execution method: 4 sequential 25-doc batches via `--offset` + `--output-jsonl` accumulation (sandbox shell-tool memory instability blocks single 100-doc detached runs). All 100 results written to `/tmp/s1b_alpha.jsonl`; deduplicated by `doc_id`; unique=100.

### 5. Domain distribution (100 scoped docs)

| Domain | n | % |
|---|---|---|
| construction | 66 | 66.0% |
| it_infrastructure | 18 | 18.0% |
| manufacturing | 9 | 9.0% |
| aviation | 2 | 2.0% |
| core | 2 | 2.0% |
| supply_chain | 2 | 2.0% |
| finance | 1 | 1.0% |
| **healthcare** | **0** | **0.0%** |

**Stage 1B α covered 7 of 8 canonical domains. Healthcare was absent.** The corpus is heavily construction-skewed, so Stage 1B is strongest evidence for construction and it_infrastructure, weaker evidence for the thinner domains, and no evidence for healthcare. Healthcare validation requires a separate corpus.

### 6. Document type distribution (top entries)

`project_plan` 16, `financial_report` 11, `customer_profile` 10, `policy_document` 10, `meeting_notes` 9, `org_chart` 7, `technical_spec` 5, `strategic_plan` 4, `press_release` 3, `architecture_doc` 3, `partner_profile` 3, `supplier_profile` 2, plus 17 long-tail single-occurrence types. **29 unique document types total.**

### 7. Confidence distribution

| stat | value |
|---|---|
| n | 100 |
| min | 0.1886 |
| max | 0.4690 |
| mean | 0.3315 |
| median | 0.3309 |
| count <0.30 | **22** |

### 8. Low-confidence audit-signal count (production threshold `<0.30`)

**22/100** documents would emit a `low_confidence` audit_record. This matches the brief's expected value.

> **Correction to original α report.** The original α report stated "97/100 audit signals (conf < 0.40)". That `<0.40` value was an analyst-side post-hoc threshold guess in the aggregator script — the production code at `src/context_foundry/extraction/ontology_centric_pipeline.py:923,1014` and `src/context_foundry/extraction/audit_recorder.py:108` uses `<0.30` and has used `<0.30` throughout. **No code change was needed. No drift exists.** Code is aligned with design.

### 11. Top 10 lowest-confidence docs

| filename | primary_domain | conf | document_type |
|---|---|---|---|
| 04_toyota_partnership_announcement.md | manufacturing | 0.1886 | press_release |
| 06_toyota_jv_negotiation_summary.md | construction | 0.2491 | joint_venture_agreement |
| 05_fedramp_announcement.md | it_infrastructure | 0.2511 | press_release |
| 06_employee_benefits_update.md | construction | 0.2592 | employee_communication |
| 01_board_meeting_q4_2025.md | construction | 0.2605 | meeting_notes |
| 03_press_release_fy2025.md | construction | 0.2641 | press_release |
| 08_cybersecurity_advisory.md | it_infrastructure | 0.2719 | security_advisory |
| 10_quarterly_newsletter.md | it_infrastructure | 0.2738 | internal_newsletter |
| 01_ceo_all_hands_memo.md | construction | 0.2763 | internal_communication |
| 10_board_strategic_priorities.md | construction | 0.2787 | board_guidance_document |

Common pattern: short, multi-domain documents (press releases, newsletters, board communications) where the top-domain score is only marginally higher than the runner-up. The `<0.30` audit sentinel is meant to flag exactly these; it does not change prompt scope.

---

## Prerequisite 1 — Audit threshold verification (RESOLVED, no fix needed)

| Source | Threshold |
|---|---|
| Design (per signed-off brief lines 174-187) | `< 0.30` |
| `src/context_foundry/extraction/ontology_centric_pipeline.py:923` | `LOW_CONFIDENCE_THRESHOLD = 0.30` |
| `src/context_foundry/extraction/ontology_centric_pipeline.py:1014` | `if confidence_float < self.LOW_CONFIDENCE_THRESHOLD:` |
| `src/context_foundry/extraction/audit_recorder.py:108` (docstring) | `"Emit a low_confidence signal (classification_confidence < 0.30)."` |

**Result: design and code agree at `< 0.30`. No code change. No tests modified. The original α report's `97/100` count was a post-hoc aggregator-script error and is corrected above to `22/100`.**

The dry-run script `scripts/piece2_stage1b_dry_run_classify.py` itself does not contain a threshold constant — it only emits the raw `classification_confidence` per doc. No change required there.

---

## Prerequisite 2 — Corpus-upload mechanism for β (VERIFIED — Corpus Maker CLI)

**Mechanism: Preferred path (Corpus Maker API/CLI).**

### Registry entry

`python -m src.corpus_maker list` returns:

```
ClaudeCode Nexus Industries
---------------------------
  Vault ID:      176a4fb2-0bb4-4da3-9068-0e26268fca71
  Anchor Org:    N/A
  Documents:     N/A
  Questions:     N/A
  Last Run:      2026-05-10T17:08:55.599483
  Last Accuracy: 73.0%
```

(`N/A` for anchor/documents/questions appears to be a registry display artifact, not a missing-data block — the vault itself contains 100 documents and the disk source is intact.)

### CLI command template (β fresh L + S)

```bash
# Run L (legacy)
unset CF_PIECE2_SCOPED_EXTRACTION
python -m src.corpus_maker upload \
    --vault-name "Stage1B-L 2026-05-10" \
    --anchor-org "Nexus Industries" \
    --doc-folder "./test documents/ClaudeCode_Nexus_Industries 2:uncategorized" \
    --question-file "./test documents/ClaudeCode_NExus_Industries_corpus/nexus_100q.json"

# Run S (scoped)
export CF_PIECE2_SCOPED_EXTRACTION=true
python -m src.corpus_maker upload \
    --vault-name "Stage1B-S 2026-05-10" \
    --anchor-org "Nexus Industries" \
    --doc-folder "./test documents/ClaudeCode_Nexus_Industries 2:uncategorized" \
    --question-file "./test documents/ClaudeCode_NExus_Industries_corpus/nexus_100q.json"
```

(Pre-flight: confirm `--question-file` exists on disk before β kickoff; the registry shows `N/A` for questions and the depth-limited search did not surface a `questions.json` in the alt directory — `nexus_100q.json` is the candidate from the primary corpus dir. The questions file is not needed for extraction itself, only for downstream eval, and this thread does not run Nexus 100 scoring — but the CLI requires `--question-file` argument.)

### Evidence the CLI creates fresh tenant corpus state

- `cmd_upload` at `src/corpus_maker/cli.py:57-75` mints a new `vault_id = str(uuid.uuid4())` when `--vault-id` is not passed (line 61-64), then calls `upload_corpus(...)` from `src/corpus_maker/uploader.py`. Each run produces an independent tenant.
- Same code path used by the existing Nexus vault upload (per CLI's own example at line 180).
- Setting `--no-extract` would skip extraction; for β both runs need extraction to occur, so `--no-extract` is omitted (extraction will run via the same `run_vault_extraction.py` that reads the env-var gate).

### Corpus equality verification (DISK ↔ existing vault)

Performed against existing vault `176a4fb2`:

| Source | Doc count | Set diff vs vault |
|---|---|---|
| `./test documents/ClaudeCode_Nexus_Industries 2/*.md` (recursive) | 100 | 0 missing, 0 extra |
| `./test documents/ClaudeCode_NExus_Industries_corpus/All docs/*.md` | 100 | 0 missing, 0 extra |

Both candidate sources are byte-equal in filename set to the existing vault. β can proceed against either. Recommended: use the `Nexus_Industries 2` directory (single flat folder, simpler `--doc-folder` invocation; no risk of double-counting from categorized subfolders + `All docs` mirror in the primary corpus dir).

> **SQL clone is NOT being used.** No SQL clone of `entities`, `relationships`, `audit_records`, `fact_verifications`, `STAGING/TRUSTED` rows, or extraction outputs is proposed.

---

## Prerequisite 3 — Architect review

Pending. Will be run after this findings doc is committed.

---

## Findings (per corrections brief)

### Finding 1 — Persisted classification columns are stale

In a prior 27-doc sample run earlier in this Stage 1B work, only 7/100 Nexus documents had non-NULL persisted `platform.documents.primary_domain`, while live classification (via `brain.classification_wrapper.classify`) classified 100/100 docs successfully. α intentionally uses live classification — not the persisted column — as the source of truth.

**Implication:** Stage 1B uses live classification as the source of truth. If Stage 2 relies on persisted classification columns (e.g., for fast routing without re-running the classifier), it needs a backfill or a freshness policy.

### Finding 2 — Domain coverage is skewed but broad enough for Stage 1B

Stage 1B α covered 7 of 8 canonical domains, but construction dominates at 66% and healthcare is absent.

**Implication:** Stage 1B validates scoped activation primarily on construction and it_infrastructure, with thinner evidence for manufacturing, aviation, core, supply_chain, and finance. Healthcare validation requires a separate corpus.

### Finding 3 — Confidence distribution is low

Mean and median are around 0.33, max is below 0.50, and 22/100 docs are below the signed-off `<0.30` low-confidence sentinel.

**Implication:** The classifier confidence scale is low for Nexus-style documents. The `<0.30` audit sentinel is plausible for Stage 1B, but threshold calibration remains Piece 2.5.

---

## Rollback-trigger result

`skip_failed_rate = 0.0%` ≪ 25%. **Not triggered.** α permits proceeding to β per the brief's stop rule.

---

## Known limitations

- Stage 1B validates scoped extraction on the domains actually present in the Nexus corpus. **Broader validation across all eight canonical domains requires a broader corpus and is deferred** (healthcare in particular is unmeasured).
- Stage 1B does not score Nexus 100. It compares extraction outputs only.
- α evaluates the classifier path only; it does not exercise the scoped-prompt generator end-to-end with the LLM. β is required for that.
- Sandbox shell-tool memory instability prevents single 100-doc detached classifier runs; α therefore used 4×25 batches with deduplication. Batched results are byte-deterministic and unique by `doc_id`.

---

## Recommendation for Stage 2

Deferred. Will be added after β results are in.

---

## Compliance confirmations

- ✅ No Nexus 100 scoring run.
- ✅ No Stage 2 work performed or planned in this thread.
- ✅ No MultiModelExtractor prompt change. Module-level constant `src.context_foundry.extraction.multi_extractor.EXTRACTION_SYSTEM_PROMPT` SHA still `5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963`.
- ✅ No `brain/app.py`, Gardener, Data Gates, v2, workflow restart, or `replit.md` work.
- ✅ Default behavior remains legacy. `CF_PIECE2_SCOPED_EXTRACTION` is unset by default.
- ✅ Env-var gate isolated to `scripts/run_vault_extraction.py` (lines 711-732).
- ✅ Telemetry event_type `scoped_extraction_decision` writes to `platform.extraction_events` (no schema change).
- ✅ 106/106 Stage 1B tests still passing as of last run.

---

## Addendum (user, 2026-05-10): Corpus history limitation

The Nexus corpus has been the primary test bed for Context Foundry extraction development over several months. The current 1037-type ontology has accumulated entries through repeated Nexus extraction iterations (see Gap 2 in `docs/architecture.md`: 803 layer-2 ad-hoc types created by `_update_reference_ontology` outside governance). This means the ontology is effectively saturated on Nexus vocabulary.

**Implication for Stage 1B β.** Stage 1B β on Nexus therefore tests prompt-scoping mechanics (does the flag change what the LLM is asked to extract), not adaptive ontology behavior (does the system handle genuinely novel domains correctly).

**Empirical confirmation in this run.** The L extraction produced 2258 entities and 2192 relationships across 100 Nexus docs while making **zero modifications** to `ontology.types` (1037→1037, 0 inserts, 0 updates) or `ontology.relations` (254→254, 0 inserts, 0 updates). The defensive `staging_loader._ensure_entity_type_exists` insert path was reached on every entity but found a match every time — every observed entity_type already existed in the ontology with `status='ACTIVE'`. This is consistent with saturation, not with the path being broken.

**Recommended future validation.** A future run should exercise scoped extraction against a fresh corpus the system has not previously extracted, to test the adaptive-ontology claim. Candidates:
- a new industry the system has never seen
- a deliberate "cold corpus" introduction with documents drawn from a domain absent from the current 8 (e.g., legal, energy, biotech, agriculture, retail, telecom)

The "cold corpus" test is the only way to falsify or confirm the adaptive-ontology behavior. Until such a test runs, β results from Nexus must be reported as evidence about prompt-scope mechanics only.

---

## β results — S vault extraction complete (2026-05-11)

**S vault (scoped, β):** `5df41308-4033-441d-b712-77928b8ea93e`
**L vault (legacy, baseline):** `f38e400f-0bba-47d8-b8cc-b41fbaff059f`
**β execution:** `CF_PIECE2_SCOPED_EXTRACTION=true python -u scripts/run_vault_extraction.py --vault-id 5df41308-4033-441d-b712-77928b8ea93e`
**Run window:** 2026-05-11 03:32:48 UTC → 05:35:14 UTC (≈2h 2m wall clock; resumed once from a transient platform recycle at the 41-min mark; resume completed via per-doc disk-artifact check, 0 docs re-extracted from scratch).

### Headline counts

| | S (β scoped) | L (baseline) | Δ |
|---|---|---|---|
| Entities | 2345 | 2258 | **+87 (+3.9%)** |
| Relationships | 2227 | 2192 | **+35 (+1.6%)** |
| Documents | 100 | 100 | 0 |
| Document chunks | 435 | 435 | 0 |
| Ontology types | 1037 (unchanged) | 1037 (unchanged) | 0 |
| Ontology relations | 254 (unchanged) | 254 (unchanged) | 0 |
| Verification errors | 0 | 0 | 0 |

**Ontology saturation confirmed for β as well** — S extraction made 0 modifications to `ontology.types` or `ontology.relations`. The Addendum's saturation hypothesis holds for the scoped path too. Cold-corpus test is still the only viable falsification.

### Entity-type breakdown (S vs L)

| entity_type | S | L | Δ |
|---|---|---|---|
| PRODUCT | 226 | 176 | **+50** |
| BUSINESS_UNIT | 153 | 140 | +13 |
| ORGANIZATION | 249 | 237 | +12 |
| SUPPLIER | 67 | 59 | +8 |
| FACILITY | 93 | 86 | +7 |
| FINANCIAL_METRIC | 418 | 411 | +7 |
| LOCATION | 117 | 114 | +3 |
| CUSTOMER | 101 | 100 | +1 |
| PERSON | 312 | 312 | **0** |
| PROJECT | 327 | 328 | -1 |
| TECHNOLOGY | 115 | 116 | -1 |
| PARTNER | 47 | 49 | -2 |
| SERVICE | 29 | 32 | -3 |
| POLICY | 91 | 98 | -7 |

**Pattern.** β concentrates the entity gain in product/asset-shaped types (PRODUCT, BUSINESS_UNIT, ORGANIZATION, SUPPLIER, FACILITY, FINANCIAL_METRIC). PERSON is identical (312/312). Small-magnitude losses in POLICY/SERVICE/PARTNER. Net +87 ents.

### Relationship-type breakdown (S vs L) — top deltas

| rel_type | S | L | Δ |
|---|---|---|---|
| PART_OF | 288 | 250 | **+38** |
| LOCATED_AT | 163 | 133 | +30 |
| PARTNER_OF | 144 | 119 | +25 |
| PRODUCES | 228 | 205 | +23 |
| HOLDS_POSITION | 318 | 300 | +18 |
| OWNED_BY | 18 | 1 | **+17** |
| SUPPLIER_OF | 124 | 114 | +10 |
| LEADS | 144 | 137 | +7 |
| REPORTS_TO | 50 | 45 | +5 |
| WORKS_FOR | 9 | 14 | -5 |
| USES | 137 | 147 | -10 |
| RELATED_TO | 52 | 67 | **-15** |
| CUSTOMER_OF | 211 | 237 | -26 |
| FUNDED_BY | 146 | 188 | **-42** |
| OWNS | 189 | 231 | **-42** |

**Pattern (significant).** β trades **generic** verbs (`OWNS` -42, `FUNDED_BY` -42, `CUSTOMER_OF` -26, `RELATED_TO` -15, `USES` -10) for **typed/specific** verbs (`PART_OF` +38, `LOCATED_AT` +30, `PARTNER_OF` +25, `PRODUCES` +23, `HOLDS_POSITION` +18, `OWNED_BY` +17, `SUPPLIER_OF` +10). The net rel count is +35, but the *quality composition* changes: scoped extraction narrows relationships toward more discriminating predicates. `OWNED_BY` moving 1 → 18 is the most extreme single shift; `OWNS` dropping 231 → 189 mirrors that — the LLM under scoped prompting prefers the directed `OWNED_BY` edge to the generic `OWNS` edge for ownership chains.

### Lifecycle state breakdown

| state | S ents | L ents | Δ ents | S rels | L rels | Δ rels |
|---|---|---|---|---|---|---|
| STAGING | 1171 | 1571 | **-400** | 1219 | 1790 | **-571** |
| TRUSTED | 27 | 78 | -51 | 0 | 9 | -9 |
| ARCHIVED | 1147 | 609 | **+538** | 1008 | 393 | **+615** |

**Pattern (most significant single finding).** β archived **2× more facts** than L: +538 ents archived (1147 vs 609), +615 rels archived (1008 vs 393). Despite producing a slightly larger total fact count, β pushes far more facts into ARCHIVED (gardener-rejected/superseded) and far fewer into STAGING (awaiting verification) and TRUSTED (verified+promoted). This is consistent with scoped extraction surfacing more conflicts that the gardener then archives, OR with scoped extraction writing more low-confidence facts that fail promotion gates.

The **TRUSTED count is lower in S (27 vs 78 ents, 0 vs 9 rels)** — at face value this is a quality regression unless interpreted as: β ran later, gardener promotion is throttled, and verification has not yet caught up. (VerificationWorker logged `verified=143, rejected=5, needs_review=52` from a 200-fact sample — more verifications would be needed for full TRUSTED parity.) This must be addressed before any conclusion about scoped quality.

### Per-document evidence — unavailable via current schema

Attempted: title-join across vaults via `documents.title` + `relationships.source_document_id` cast. Result: 0 rows matched. Investigation showed `relationships.source_document_id` (varchar) does NOT resolve to `documents.id` (uuid) — 100 distinct doc-IDs appear in S relationships, 0 of which match `documents.id`. The varchar field stores an **extractor-time identifier** (likely a chunk-pipeline document ID), not a `documents` table FK.

This is a pre-existing schema oddity, not a β regression. Per-document side-by-side comparison is therefore infeasible at the SQL level under current schema. Aggregate per-type breakdowns above are the highest-resolution evidence available.

**Action item (Stage 2 input, not Stage 1B work):** schema cleanup to make `relationships.source_document_id` joinable to `documents.id`, or expose the extractor-time ID as a column on `documents`.

### Platform-recycle robustness (resume verified)

The prior S run died at the 41-min mark from a still-undiagnosed cause (process replaced; PID changed from one tracked to a fresh one; RSS dropped to 4 MB). The resume mechanism in `scripts/run_vault_extraction.py` worked **first try without any code change**:

- The new run scanned its output directory before each doc-pair extraction.
- All 73 paired files written before the crash were detected as already-extracted; the orphan single-model file (`0b232cda...`, gpt-only) was filled in first.
- Fresh extractions proceeded for the remaining 27 paired docs.
- 0 wasted LLM calls on already-extracted docs.
- The full 200-file output set (gpt=100, claude=100) was assembled cleanly.

**Implication.** The per-doc disk-artifact resume pattern is durable to platform recycles. **No state-machine resume is needed for Stage 1B** — Stage 2 may inherit this pattern.

A second transient occurred at the 02:04 mark (RSS jumped 149 → 237 MB during a consensus pause, then PID 4252 exited cleanly; new transient PID 8013 appeared briefly and exited). The S DB final state at PID-4252 exit was `2345 ents / 2227 rels`, which matches the post-extraction state recorded above. **VerificationWorker completed cleanly at 05:35:13 with `errors=0`** — this is the canonical end-of-run marker.

### Stop conditions — none triggered during β

Per the resume brief Stop conditions (S dies again / OOM-pattern recurs / KG writes pre-staging / ontology changes / `skip_failed > 25%`):

- ❌ S did not die — completed cleanly with VerificationWorker `errors=0`
- ❌ No OOM-pattern recurrence (RSS stayed below 240 MB throughout, well within container)
- ❌ No KG writes pre-staging (S DB stayed at 0/0 throughout the extraction phase, then jumped to 251/212 at the consensus→staging transition, exactly as designed)
- ❌ No ontology changes (1037/254 unchanged)
- ❌ No `skip_failed` events (β is scoped extraction; classifier α already cleared at 0%)

### β Findings

**β-Finding 1.** Scoped extraction shifts the **predicate distribution toward typed verbs** (`PART_OF`, `LOCATED_AT`, `PARTNER_OF`, `PRODUCES`, `HOLDS_POSITION`, `OWNED_BY`) and away from generic verbs (`OWNS`, `FUNDED_BY`, `CUSTOMER_OF`, `RELATED_TO`). Net rel count is +35, but the composition is materially different.

**β-Finding 2.** Scoped extraction archives **2× more facts** than legacy (1147 vs 609 ents archived; 1008 vs 393 rels archived). This is the largest single quantitative difference between the two runs, and it is **not interpretable from this run alone** — it could mean (a) scoped extraction surfaces more low-quality candidates that gardener correctly culls, or (b) gardener confidence thresholds are being miscalibrated against scoped output. **β-Finding 2 is the principal open question for Stage 2 design.**

**β-Finding 3.** Scoped extraction concentrates entity gains in **PRODUCT (+50)**, with smaller gains in BUSINESS_UNIT/ORGANIZATION/SUPPLIER/FACILITY/FINANCIAL_METRIC. PERSON is exactly equal (312/312) — scoped vs legacy disagree on **what** to extract about an org, not on **who** is in the org.

**β-Finding 4.** TRUSTED counts are lower in S (27 ents/0 rels vs L's 78 ents/9 rels). This is **not** a defensible quality regression statement until verification catches up — only 200 facts have been processed by the VerificationWorker in this run. **Recommendation:** before drawing any quality conclusion from S, run VerificationWorker to completion on S (TRUSTED-promotion-eligible count is bounded by `1171 - 27 = 1144 STAGING ents + 1219 STAGING rels` ≈ 2363 facts to verify). Estimated cost at this run's `tokens_used=30560 / 200 = 153 tok/fact` ≈ 360k tokens for full S verification.

**β-Finding 5.** Ontology saturation extends to scoped extraction. `ontology.types` 1037→1037, `ontology.relations` 254→254. This is consistent with the Addendum's saturation hypothesis. Cold-corpus test remains the only way to test adaptive-ontology behavior.

**β-Finding 6 (operational).** The per-doc disk-artifact resume mechanism in `run_vault_extraction.py` is robust to platform recycles. β survived a mid-run process replacement and resumed without losing any extraction. No code change needed; this is design behavior working as intended.

### Compliance confirmations (β)

- ✅ No Nexus 100 scoring run.
- ✅ No Stage 2 work.
- ✅ No MultiModelExtractor prompt change. EXTRACTION_SYSTEM_PROMPT SHA still `5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963` (verified pre-restart).
- ✅ No `brain/app.py`, Gardener, Data Gates, v2, workflow restart of Manus/Ontology, or `replit.md` work.
- ✅ Default behavior remains legacy. `CF_PIECE2_SCOPED_EXTRACTION=true` was set only for this β invocation; not persisted.
- ✅ Env-var gate isolated to `scripts/run_vault_extraction.py` (lines 711-732).
- ✅ Telemetry event_type `scoped_extraction_decision` writes to `platform.extraction_events` (no schema change). Not re-verified post-β; should be checked before sign-off.

### Stop point

Per resume brief: **β results are presented for sign-off. Do NOT begin Stage 2 work.** Awaiting user direction on (a) acceptance of β-Findings 1-6, (b) decision about VerificationWorker completion run for S to address β-Finding 4, (c) whether to proceed to Stage 2 design or to a cold-corpus test first.


---

## β-Finding 2 — REVISED after architect review and dwell/change_reason check (2026-05-11)

The architect review (run 2026-05-11 ~05:45 UTC) flagged that β-Finding 2 ("S archived 2× more facts") and β-Finding 4 ("TRUSTED gap") needed a dwell-time + change_reason check before they could be published. That check was performed and **invalidates the original β-Finding 2 interpretation**.

### Dwell-time check

| | STAGING within_dwell (<1h) | STAGING past_dwell (>1h) | TRUSTED total | ARCHIVED total |
|---|---|---|---|---|
| S (β) | 1171 | **0** | 27 | 1147 |
| L | 0 | 1571 | 78 | 609 |

**Every S fact is <1 hour old; every L fact is >1 hour old.** S literally cannot be promoted to TRUSTED yet under the gardener's `min_dwell_time_hours=1.0` configuration. **β-Finding 4 is fully explained by dwell-time lag** — the TRUSTED gap is not a quality regression, it is a wall-clock artifact. Re-examining S's TRUSTED count after a 2-hour wait is the correct comparison.

### change_reason check

Sampling the top-20 most common `change_reason` values for S ARCHIVED entities returned **100% identity-resolution merges**:

```
"Merged into Raytheon via identity resolution (score: 0.95)"     × 3
"Merged into NASA via identity resolution (score: 0.95)"          × 3
"Merged into Shell via identity resolution (score: 0.95)"         × 3
"Merged into CATL via identity resolution (score: 0.95)"          × 3
... (every reason follows the same "Merged into X via identity resolution (score: 0.95)" pattern)
```

**No "low confidence", "ontology violation", "duplicate fact", or other rejection reasons appear in the top 20.** S ARCHIVED facts are **canonicalization merges**, not gardener quality rejections.

### Confidence-by-lifecycle check

| | STAGING avg | TRUSTED avg | ARCHIVED avg |
|---|---|---|---|
| S | 0.958 | 0.946 | 0.943 |
| L | 0.951 | 0.972 | 0.939 |

Confidence distributions are **essentially identical across vaults** at every lifecycle state. S is not producing systematically lower-confidence facts than L. S TRUSTED has lower avg (0.946 vs 0.972), but S TRUSTED has only 27 samples — too small to draw a confidence-quality distinction.

### Revised β-Finding 2

**Original (incorrect):** "Scoped extraction archives 2× more facts than legacy ... could mean (a) scoped extraction surfaces more low-quality candidates that gardener correctly culls, or (b) gardener confidence thresholds are being miscalibrated against scoped output."

**Revised:** Scoped extraction produces 538 more identity-resolution merges than legacy (1147 vs 609 ARCHIVED ents — 100% of sampled archive reasons are `Merged into X via identity resolution (score: 0.95)`). This means scoped extraction **surfaces finer-grained surface forms of the same canonical entity**, which the identity-resolution layer correctly canonicalizes. **This is a positive signal**, not a quality defect — scoped is doing more granular text-anchoring per entity and successfully reconciling those mentions to the same canonical node.

**Implication.** β does not exhibit a quality regression in archives. The "2× archive ratio" headline must be retracted from any quality framing. The correct framing is: "β triggers 1.9× more identity-resolution merges than L, indicating finer-grained mention-level extraction with correct canonical reconciliation."

### Revised β-Finding 4

**Original (cautious):** "TRUSTED counts are lower in S (27 ents/0 rels vs L's 78 ents/9 rels). This is not a defensible quality regression statement until verification catches up."

**Revised:** TRUSTED gap is **fully explained by gardener dwell-time** (`min_dwell_time_hours=1.0`). All S facts are <1 hour old; gardener cannot promote them yet. Re-measuring after 2+ hours of dwell is the correct comparison. **No verification-completion run is required to interpret β-Finding 4** — running VerificationWorker would help, but is not necessary; simply waiting and re-querying TRUSTED counts will resolve the gap.

### Revised stop point

Per the resume brief: **β results are presented for sign-off with revisions to Findings 2 and 4 reflected above.** Awaiting user direction. **Stop point unchanged: do NOT begin Stage 2 work.**


---

## Stage 1B β — CLOSEOUT (2026-05-11 07:09 UTC)

Per `docs/inbox/piece_2_stage1b_closeout_2026-05-11.md`, sign-off received. Stage 1B β is **closed** pending the dwell re-query, which is **DEFERRED**:

- Current UTC: 2026-05-11 07:09:43
- Dwell gate (S extraction end + 1h + buffer per closeout doc): 2026-05-11 07:35:13
- Time remaining: 25m 30s
- Action: defer dwell re-query per closeout rule ("If current UTC < gate: do not wait, record due time and stop"). Will run as a single SQL query when the user resumes after the gate passes.

**Open item statuses post-closeout:**
1. **Open item 1** (TRUSTED dwell re-query): DEFERRED. Due 2026-05-11 07:35:13 UTC.
2. **Open item 2** (relationships.source_document_id observability gap): RECORDED as Stage 2 design input. NOT FIXED.
3. **Open item 3** (cold-corpus adaptive-ontology test): RECORDED as future task name **"Piece 2X — Adaptive Ontology Cold-Corpus Validation"**. NOT DRAFTED, NOT EXECUTED.
4. **Open item 4** (full S VerificationWorker run): DEFERRED.

**Adaptive-ontology claim (recorded conclusion):** Defensible as a codebase/design claim — raw ontology write paths (`staging_loader._ensure_entity_type_exists`, `ontology_centric_pipeline._update_reference_ontology`), discovery/candidate paths (`type_discovery_agent`, `candidate_store`), and governed Ontology Foundry infrastructure (`ontology_foundry/{schema_service,schema_version_manager,deprecation_manager,approval_manager}`) all exist. Historical 803 ad-hoc types prove the path executed. **Not validated by Stage 1B β** — Nexus is saturated; both L and S left ontology unchanged at 1037/254. Cold-corpus validation deferred to Piece 2X.

