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
