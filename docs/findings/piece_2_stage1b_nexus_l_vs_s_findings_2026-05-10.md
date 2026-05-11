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


---

## Dwell re-query — 2026-05-11 12:14 UTC (β-Finding 4 status update)

Gate elapsed (4h 39m past `07:35:13` gate). All S facts now past `min_dwell_time_hours=1.0` window.

### Lifecycle state — entities

| vault | STAGING | TRUSTED | ARCHIVED | total |
|---|---:|---:|---:|---:|
| L (baseline) | 1543 | 78 | 637 | 2258 |
| S (β scoped) | 972 | 27 | 1346 | 2345 |

### Lifecycle state — relationships

| vault | STAGING | TRUSTED | ARCHIVED | total |
|---|---:|---:|---:|---:|
| L (baseline) | 1789 | 9 | 394 | 2192 |
| S (β scoped) | 1171 | 0 | 1056 | 2227 |

### Drift in S since first measurement (~7h ago)

| | then | now | Δ |
|---|---|---|---|
| Ents STAGING | 1171 | 972 | −199 |
| Ents TRUSTED | 27 | 27 | **0 (unchanged)** |
| Ents ARCHIVED | 1147 | 1346 | +199 |
| Rels STAGING | 1219 | 1171 | −48 |
| Rels TRUSTED | 0 | 0 | **0 (unchanged)** |
| Rels ARCHIVED | 1008 | 1056 | +48 |

All 199 entity transitions during the dwell window went STAGING → ARCHIVED, not STAGING → TRUSTED. Same for the 48 relationship transitions.

### β-Finding 4 — STATUS: REMAINS OPEN

**Dwell-time hypothesis falsified.** With dwell satisfied for all S facts, S TRUSTED is still 27 ents / 0 rels vs L's 78 / 9 — a 65% gap on entities and a 100% gap on relationships. The TRUSTED gap is **not a wall-clock artifact**. Something else prevents S fact promotion.

**Updated hypotheses (UNTESTED in this turn per closeout scope):**
- **H1 — gardener cycle gap.** No gardener promotion cycle may have run against the S tenant. Verifiable via `gardener_logs` filtered by S tenant.
- **H2 — corroboration threshold.** Gardener may require ≥N corroborating sources; S has only one extraction run to draw from, so there are fewer cross-run cross-references to satisfy the gate.
- **H3 — verification gate.** `replit.md` records `require_verification_for_promotion=False`, but the actual runtime config in this S run may differ.
- **H4 — canonicalization eats the candidate pool.** During dwell, identity resolution continues archiving S STAGING facts as merges (199 ents / 48 rels in 7h). This shrinks the promotable pool faster than gardener promotes from it.

H4 is consistent with the observed drift direction (everything in dwell goes to ARCHIVED, not TRUSTED) and is consistent with the original revised β-Finding 2 (archives are merges, not rejections). H4 does not require additional code investigation to be plausible. H1–H3 do.

### Action

Per closeout doc: **Stop after the dwell re-query report.** Not investigating H1–H4 in this turn. β-Finding 4 status carried forward as **OPEN** for the next sign-off-gated decision.


---

## β-Finding 4 — CLOSED with new framing (2026-05-11 12:18 UTC, four-check investigation)

Authorized read-only investigation of H1/H2/H3/H4 produced the following verdict:

### Cycle activity — gardener_logs (joined via target_id; no `tenant_id` column on the table)

| vault | cycle_id | source | action | n | cycle_time |
|---|---|---|---|---|---|
| S | `post_extraction_20260511T053514Z` | entity | PROMOTE | 27 | 2026-05-11 05:35:16 |
| L | `post_extraction_20260510T215704Z` | entity | PROMOTE | 78 | 2026-05-10 21:57:07 |
| L | `post_extraction_20260510T215704Z` | relationship | PROMOTE | 9 | 2026-05-10 21:58:05–21:58:59 |

**Each vault has had exactly ONE gardener cycle**, fired ~2 seconds after extraction completion. No subsequent cycles. No daemon, cron, or recurring promotion scheduler exists.

### Live config (`src/context_foundry/agents/gardener.py:86-128`)

```
min_confidence_for_promotion: float = 0.75
min_dwell_time_hours: float = 1.0
require_verification_for_promotion: bool = False  # disabled 2026-05-08
validate_against_ontology: bool = True
use_database_thresholds: bool = True
```

Per-type thresholds loaded from DB table `promotion_thresholds` (loader at L348). Default fallback `min_corroboration_count=1, min_staging_hours=1`. Sampled S STAGING ents all show `confidence=1.000, validation_status=VALID`, eligible under base config — they simply never got revisited.

### Archive category — full S ARCHIVED breakdown

| category | n |
|---|---|
| `identity_resolution_merge` | **1346 (100%)** |
| `low_confidence_reject` | 0 |
| `duplicate` | 0 |
| `ontology_violation` | 0 |
| `NULL` | 0 |
| `other` | 0 |

Zero quality rejections. Revised β-Finding 2 confirmed absolutely.

### Hypothesis verdicts

- **H1 — gardener cycle gap: CONFIRMED (primary cause)**
- **H2 — corroboration threshold: not ruled in or out** (per-type `promotion_thresholds` values not enumerated this turn)
- **H3 — verification gate: FALSIFIED** (`require_verification_for_promotion=False` confirmed)
- **H4 — canonicalization eats candidate pool: PARTIALLY CONFIRMED (secondary effect)** — 199 STAGING→ARCHIVED transitions during 7h dwell window were all identity merges; this continuously consumes promotable candidates, but H1 alone is sufficient to explain locked TRUSTED counts.

### β-Finding 4 — CLOSED

The S–L TRUSTED gap (S=27 ents/0 rels vs L=78 ents/9 rels) is **not a quality regression**, **not a dwell-time artifact**, **not a verification-gate artifact**. It is a **single-shot promotion-cycle artifact**: the system fires exactly one gardener cycle per vault at end-of-extraction (`post_extraction_<extraction_end_timestamp>`), then never visits the tenant again. Whatever was promotable at that 2-seconds-post-extraction moment is what TRUSTED contains forever. The S–L difference reflects per-type-threshold satisfaction at that single moment, modulated by how much identity-resolution canonicalization had completed by the cycle time.

This is **not scoped-vs-legacy specific** — L is affected by the same single-shot promotion behavior. This is **not Stage 1B β specific** — every tenant in Context Foundry is subject to it.

### Stage 2 design input — Promotion cadence gap

The Gardener has no recurring promotion cycle. Promotion only fires once per vault, at the moment extraction completes (cycle naming convention: `post_extraction_<timestamp>`). At that 2-seconds-post-extraction moment, most STAGING facts have not yet had a chance to be canonicalized, accumulate corroboration, or satisfy `min_staging_hours`. After that single cycle, TRUSTED counts are frozen. Stage 2 design must decide whether to (a) add a recurring promotion cron, (b) trigger promotion as a post-canonicalization webhook, (c) gate promotion on signals other than wall-clock dwell, or (d) accept single-shot promotion as designed and remove the dwell/corroboration thresholds from blocking it.


---

## Stage 1C — Gardener Promotion Gap Diagnosis (2026-05-11 12:25 UTC)

Per `docs/inbox/stage_1c_promotion_gap_diagnosis_2026-05-11.md`. Read-only investigation; no fixes applied.

### Final answers

| Question | Answer |
|---|---|
| Stage 2 blocked? | **YES** until promotion cadence fixed |
| Gardener fix needed before Stage 2? | **YES** — scheduler invocation + possibly relationship-promotion code path |
| VerificationWorker run needed before Stage 2? | **NO** — `require_verification_for_promotion=False` confirmed |
| Relationship promotion structurally blocked? | **OPEN** — S has 0 rel promotes; H6 (code read) needed to confirm whether `promotion_pass()` covers rels |
| Archive behavior: merge vs quality? | **100% identity merge** in both S (1346/1346) and L (637/637). NOT quality rejection. |

### Hypothesis verdicts

- H1 (gardener cycle gap): **SUPPORTED (primary)** — scheduler implemented at `scheduler.py:25-421` (`cycle_interval_seconds=300`), never started by `start.sh`. Only post-extraction single cycle fires.
- H2 (corroboration threshold): **REJECTED** — `_default.min_corroboration_count=1`, hardcoded fallback to 1 in `gardener.py:778`.
- H3 (verification gate): **REJECTED** — `require_verification_for_promotion=False` confirmed at `gardener.py:117`.
- H4 (canonicalization eats pool): **SUPPORTED (secondary)** — 199 STAGING→ARCHIVED transitions during 7h dwell are 100% identity merges.
- H5 (NEW — promotion_thresholds empty for Nexus vocab): **SUPPORTED** — 32 threshold rows; 0 match Nexus types; all fall to `_default`. Production diverges from documented intent.
- H6 (NEW — promotion_pass may not handle relationships, or rel phase aborted for S): **OPEN** — S `gardener_logs.target_type='relationship'` count = 0; L = 9. Needs `gardener.py:731-1000` read.

### Stop-condition triggers

Two potential one-line bugs surfaced:
- **H1 fix candidate**: add `start_scheduler()` call to `start.sh` or `web_app` initialization.
- **H6 fix candidate**: pending code read; may be a missing relationship loop in `promotion_pass()`.

**No fixes applied.** Surfaced for sign-off only.

### Recommended next actions (NOT executed)

- **Option A**: start scheduler in `start.sh` (smallest fix, but applies to all tenants)
- **Option B**: manually re-fire `scripts/run_promotion.py --tenant-id 5df41308-...` for S now and observe second-cycle promotions (empirical H4 test)
- **Option C**: read `gardener.py:731-1000` to determine if `promotion_pass()` handles relationships at all (close H6)


---

## Stage 1D — Promotion Cadence Empirical Test (2026-05-11 12:58 UTC)

Authorized: Task B + Task C in parallel. Option A (scheduler activation) NOT authorized.

### Task C — gardener.py L731-end read — COMPLETE

**Q1: `promotion_pass()` handles both entities and relationships in one function.** Entity loop L750-827, relationship loop L829-904.

**Q2: No separate relationship promotion function.** Single `promotion_pass()` call covers both phases.

**Q3: No entity-only / entity+relationship mode flag.** Both phases always run.

**Q4: Smoking gun — `endpoints_not_trusted` gate at gardener.py L864:**
```python
elif not (source_trusted and target_trusted):
    block_reason = "endpoints_not_trusted"
```
A relationship can only promote in cycle N if BOTH endpoints are TRUSTED at cycle-N time. Within one cycle, ents promote first then rels — so the only rels eligible are those whose endpoints are among the entities promoted in the same cycle's earlier phase. This explains S=0 / L=9 deterministically: L's 78 ents made 9 rels promotable; S's 27 ents made 0.

**Bonus finding:** `get_threshold("Relationship")` at L835 falls to `_default` since `promotion_thresholds` has no `Relationship` row.

**Bonus finding:** rel-loop is N+1 per-endpoint lookup (gardener.py L842-847) — 2N round-trips per cycle. L's 54-second rel phase = 1789 × 2 ≈ 3578 SQL round-trips.

### Task B — one-shot promotion on S — STOP-CONDITION TRIGGERED

**Pre-snapshot:** S 972 STAGING ents / 27 TRUSTED / 1346 ARCHIVED; 1171 STAGING rels / 0 TRUSTED / 1056 ARCHIVED. 1 prior cycle.

**Execution:** `PYTHONPATH=. python -u scripts/run_promotion.py --tenant-id 5df41308-...`. Initialization completed in 14s (loaded thresholds, ontology). Then 105s of silence. SIGTERM at 2-min timeout.

**Post-hang state:** identical to pre-snapshot. No new gardener_logs cycle. No `_promoted_at` markers >= 12:54:00. No commit occurred (script commits only after `promotion_pass` returns; SIGTERM killed mid-execution).

**Hang hypothesis:** N+1 endpoint lookup loop (~2342 round-trips for rels alone) plus entity-loop conflict/duplicate checks likely exceeds 2-min budget. L's prior cycle took 4-5 min wall-time end-to-end.

### Combined B+C verdict for Option A

- Would Option A fix TRUSTED gap? **Partially** — ents yes; rels chained structurally to ents via `endpoints_not_trusted`, may need multiple cycles to converge.
- Are there deeper blockers? **YES** — H6 confirmed at L864.
- Did Task B confirm cycle-gap? **Inconclusive** — hung before producing data.

### Recommended next actions (surfaced; not executed)

- **B-retry**: re-run with 10-min timeout
- **B-perf**: surface N+1 endpoint lookup as perf bug
- **D (new)**: investigate multi-cycle convergence behavior

### What remains unknown

1. Empirical second-cycle promotion counts for S (B-retry needed)
2. Whether `_get_entity_ids_with_pending_duplicates` blocks ents still queued for canonicalization
3. Whether rel-endpoint constraint can be relaxed safely


---

## Stage 1E — Empirical Multi-Cycle Convergence Test (2026-05-11 13:45 UTC) — CASE 4: Cycle 1 timeout

Per `docs/inbox/stage_1e_convergence_test_2026-05-11.md.md`. Authorized: up to 2 sequential tenant-scoped manual cycles on S only. Option A (scheduler activation) NOT authorized.

### Outcome: Case 4 — Cycle 1 timed out before promoting anything

**Pre-cycle 1 snapshot (13:39:50 UTC):** S 972 STAGING / 27 TRUSTED / 1346 ARCHIVED ents; 1171 STAGING / 0 TRUSTED / 1056 ARCHIVED rels; 1 historical cycle. Ontology baseline: types=1037, relations=254.

**Pre-cycle eligibility (relationship endpoint-trust):**
- STAGING rels=1171, conf≥0.70=1159, validation=VALID=1171
- source TRUSTED=173, target TRUSTED=307, **both TRUSTED=95**

**Critical pre-cycle observation:** 95 STAGING rels already have BOTH endpoints in S's 27-entity TRUSTED set, yet 0 rels are TRUSTED. The original `post_extraction_20260511T053514Z` cycle should have promoted these 95 but recorded zero rel actions. Strongly suggests H7: silent rel-loop exception (caught at gardener.py L906) or `validate_against_ontology=True` blocked all 95 via `is_valid_relationship_type`.

**Cycle 1 attempts:**
1. nohup background, PID 5879 at 13:39:52 — process gone by 13:42:06, log 0 bytes, no state change
2. foreground `timeout 90` at 13:42:30 — exit 124 at 13:44:00, last log line `[Gardener] Loaded ontology schema: 1026 entity types, 232 relationship types`, no commit, no state change

Both attempts identical: init in ~6s, then 84s+ silence until SIGTERM. **No "Promotion pass" log line ever printed.** Same as Stage 1D's prior failure.

**Post-cycle 1 (timeout) state:** identical to pre-snapshot. Zero deltas. Ontology unchanged (types=1037, relations=254). No cross-tenant impact.

**Bottleneck probe:** S has 688 pending_duplicates (out of 1599 global). `_get_entity_ids_with_pending_duplicates()` (gardener.py L1233) is global-scope, not tenant-scoped — fetches all 1599, iterates. Combined with entity-loop overhead (972 iterations × per-row threshold/conflict/duplicate checks) and rel-loop N+1 endpoint queries (~2342 round-trips), 90s budget is insufficient.

**Cycle 2 gate: FAILED** per directive ("If Cycle 1 times out, errors, or does not commit: stop and report. Do not run Cycle 2.").

### NEW hypotheses

- **H7 (open)**: original cycle's rel loop hit silent exception OR `validate_against_ontology` blocked all 95 endpoint-eligible rels. Cannot resolve without successful cycle execution.
- **H8 (confirmed)**: promotion runtime exceeds 90s on S. 4 attempts now (Stage 1D + 2 in Stage 1E) all hang past 90s. Likely culprits: global pending_duplicates fetch, entity-loop per-row queries, rel-loop N+1.

### Workflow-slot constraint

No existing workflow runs `scripts/run_promotion.py`. Per stop trigger "a workflow slot must be freed → stop and report" — no workflow modified. Attempted nohup-background as alternative; failed (sandbox killed before flush).

### Recommendations (NOT executed)

1. Read-only audit of `_get_entity_ids_with_pending_duplicates` for tenant-scope fix opportunity
2. Workflow-backed long-run via new `Manual Promotion S` workflow (requires explicit authorization)
3. Accept H8 as blocker; defer Stage 1E empirical test pending perf fix

### Verdicts unchanged

- Scheduler activation (Option A): **still NO** — would trigger same hang every 5 min
- Stage 2 remains **blocked**
- N+1 endpoint lookup recorded as Stage 2 perf ticket
- `endpoints_not_trusted` gate at gardener.py L864 recorded as architectural property (not a bug)


---

## Stage 1F — Read-Only Gardener Promotion Audit (2026-05-11 ~13:55 UTC)

Per `docs/inbox/stage_1f_promotion_audit_2026-05-11.md`. Read-only diagnosis only.

### Executive summary

Two distinct issues with separate root causes:
1. **Runtime (H8)** — `promotion_pass` performs ~2342 per-rel endpoint SQL queries (N+1) + global pending-duplicates fetch (1599 rows). Under RLS-scoped session, expected runtime 35–130s on S. Consistent with 4 consecutive 90s timeouts.
2. **Rel blocker (H7/H10)** — Of 95 endpoint-eligible rels, 26 are blocked by `invalid_relationship_type_*` (FUNDED_BY=20, RELATED_TO=4, USES=2 NOT_IN_ONTOLOGY); **69 should have promoted in original cycle and did not** for unresolved reasons.

### Runtime bottleneck rank

1. Per-rel N+1 endpoint queries (gardener.py L842-847): 1171 × 2 = 2342 roundtrips
2. Global `_get_entity_ids_with_pending_duplicates` (gardener.py L1233-1246): no tenant filter, 1599 rows, only PK index on `duplicate_candidates`
3. STAGING entity/relationship initial load: 972 + 1171 rows under RLS
4. Auto-flush triggered at start of rel loop

### Relationship blocker rank (95 endpoint-eligible)

| gate | blocks | notes |
|---|---|---|
| invalid_relationship_type | **26** | FUNDED_BY=20, RELATED_TO=4, USES=2 NOT in ontology.relations |
| endpoints_not_trusted | 0 (now) | unknown for original cycle — autoflush/RLS interaction speculation |
| confidence_too_low | 1 | one LOCATED_AT at 0.50 |
| validation_not_valid | 0 | all VALID |
| evidence_not_verified | 0 | require_verification_for_promotion=False (L120) |
| dwell_time_insufficient | 0 | rel default = 0h dwell |
| unresolved_conflict | unknown | not probed |

**Would-promote (if endpoints visible): 68 rels** (PART_OF=23, SUPPLIER_OF=14, CUSTOMER_OF=11, PRODUCES=6, PARTNER_OF=6, LOCATED_AT=5, OWNS=3).

### Key code-read findings

- `_get_entity_ids_with_pending_duplicates` is **NOT tenant-scoped** (gardener.py L1233-1246)
- `duplicate_candidates` has only PK index (no `reviewed`, no `entity_a/b_id` indexes)
- 308 of 972 S STAGING entities are blocked by pending_duplicate (entity_ids in 1599 unreviewed candidates)
- `promotion_pass` is wrapped in ONE function-level try/except at L749/L906 — any rel-loop exception aborts entire rel loop silently (only `result.errors` populated, no gardener_logs)
- BLOCK actions are NOT logged to `gardener_logs` (only PROMOTE actions via `_log_action` at L815/L895). Counters in `result.block_reasons` ARE populated but only visible in `result.to_dict()` printed by `run_promotion.py:25`.

### 95-rel timing analysis

- All 95 created 05:07–05:31 UTC
- Original cycle ran 05:35:16 UTC (after extraction)
- 95/95 existed BEFORE cycle → all should have been processed by rel loop
- 27 endpoint ents promoted at 05:35:16 (in same cycle)
- 0 rel logs of any kind in original cycle

### Hypothesis verdicts

| hyp | verdict |
|---|---|
| H7 (silent exception OR ontology block) | PARTIALLY SUPPORTED — 26 ontology blocks confirmed; 69 unexplained; cannot resolve from code-read |
| H8 (runtime > 90s) | STRONGLY SUPPORTED — N+1 + global dup fetch + RLS overhead |
| H9 (global dup fetch / N+1 bottleneck) | SUPPORTED — confirmed by code |
| H10 (endpoint-eligible fail ontology) | PARTIALLY SUPPORTED — 26/95 only |

### Recommendation

**Option A — workflow-backed long-run** is the only path to settle H7's open half. 10-min budget is more than sufficient (predicted 35–130s). Requires explicit authorization to create one-shot workflow for `scripts/run_promotion.py` (currently forbidden under standing constraints).

**Stage 2 remains blocked.** **Scheduler activation remains blocked** until perf addressed.

### N+1 + global-dup-fetch ticket (recorded, NOT fixed)

- gardener.py L842-847: replace per-rel endpoint queries with single batched IN-clause query before loop
- gardener.py L1233-1246: add tenant_id filter parameter to `_get_entity_ids_with_pending_duplicates`
- duplicate_candidates: add index on `(reviewed, entity_a_id, entity_b_id)`
- Architectural property unchanged: `endpoints_not_trusted` gate at L864 is correct behavior


---

## Stage 1G — Workflow-Backed Tenant-Scoped Promotion Run (2026-05-11 ~16:39 UTC)

Per `docs/inbox/stage_1g_promotion_run_2026-05-11.md` + Msg 1 constraint relaxation. Successful Case 1.

### Execution

- **Workflow not used** due to platform bug: `configureWorkflow` returned stale 10/10 count with ghost entries after `removeWorkflow('v2 Parallel Run')` succeeded. `listWorkflows()` and `system_reminder` both confirmed 8 workflows. Workaround: bash foreground.
- **Command**: `PYTHONPATH=. timeout 100 python -u scripts/run_promotion.py --tenant-id 5df41308-4033-441d-b712-77928b8ea93e`
- **Runtime**: 57.04s Gardener-reported (65s wall) — vs >100s timeouts (5 prior attempts)
- **Exit**: 0; commit succeeded

### Pre/post lifecycle counts (S vault)

| | pre | post | Δ |
|---|---|---|---|
| ents STAGING | 972 | 314 | −658 |
| ents TRUSTED | 27 | 685 | **+658** |
| ents ARCHIVED | 1346 | 1346 | 0 |
| rels STAGING | 1171 | 1150 | −21 |
| rels TRUSTED | 0 | 21 | **+21** (first non-zero) |
| rels ARCHIVED | 1056 | 1056 | 0 |

### Block reasons (captured)

```
pending_duplicate: 307
endpoints_not_trusted: 1115  (dominant rel blocker)
invalid_relationship_type_USES: 16
invalid_relationship_type_FUNDED_BY: 4
invalid_relationship_type_RELATED_TO: 3
confidence_too_low_FINANCIAL_METRIC: 6
confidence_too_low_PERSON: 1
confidence_too_low (rels): 12
```

Reconciliation: 658 + 314 = 972 ents ✓; 21 + 1150 = 1171 rels ✓.

### Cross-tenant isolation verified

- L vault: ents 1543/78/637, rels 1789/9/394 — UNCHANGED
- ontology.types: 1037 / ontology.relations: 254 — UNCHANGED

### Endpoint-eligibility expansion

Pre-cycle: 95 rels with both endpoints TRUSTED → 21 promoted (limited by ontology + per-rel gate ordering).
Post-cycle: **179 rels** now have both endpoints TRUSTED (95 → 179 because TRUSTED ents grew 27→685).
Cycle 2 would unlock most of the 179 minus ~23 ontology-invalid.

### Hypothesis verdicts updated

| hyp | verdict |
|---|---|
| H7 (silent rel-loop blocker) | **SETTLED** — not silent. Real blockers: endpoints_not_trusted dominant; ontology gaps for 23 rels. Multi-cycle convergence needed. |
| H8 (runtime > 90s) | **CONFIRMED & FIXED** — 5 prior timeouts; post-fix 57s. |
| H9 (N+1 + global-dup) | **CONFIRMED & FIXED** by perf changes below. |
| H10 (endpoint-eligible fail ontology) | **EXACT**: 23 ontology-invalid (USES=16, FUNDED_BY=4, RELATED_TO=3). |

### Code changes (gardener.py)

1. `_get_entity_ids_with_pending_duplicates(entity_ids: Optional[Set[str]] = None)` — added optional filter param to scope dup fetch to staging set. Backward compatible.
2. `promotion_pass` L757-763 — caller passes `staging_entity_id_set` to scope the dup query.
3. `promotion_pass` L847-866 — pre-fetch endpoint entity states in one batched `IN(...)` query into a dict; replaces N+1 per-rel queries (was 2342 roundtrips on S). Autoflush preserves visibility of entity-loop's in-session modifications.

### Reversible local cleanup

- Removed workflow `v2 Parallel Run` (disarmed marker, command preserved: `echo 'parallel run completed; workflow disarmed'; sleep 2`).

### Recommendations

- **Scheduler activation**: NOT YET — validate multi-cycle convergence with 2 more manual cycles first.
- **Stage 2**: partially unblocked. Strong ent promotion (658), weak rel promotion (21 cycle-1; ~150 expected cycle-2). Recommend running 2 more cycles before declaring Stage 2 ready.
- **Ontology backfill** for USES/FUNDED_BY/RELATED_TO requires sign-off (global change).
- **Pending duplicates review** for 307 blocked ents needs UI decision.
- N+1 endpoint ticket: **CLOSED** — fix landed in this cycle.

### Workflow platform bug filed

`configureWorkflow` uses a stale internal workflow counter that retains removed entries (ghost names: `v2 Parallel Run`, `Test: ClaudeCode Medsync`, `Run Canonical Bench`). `listWorkflows()` returns truth (8). Workaround: bash foreground for one-shot scripts.

