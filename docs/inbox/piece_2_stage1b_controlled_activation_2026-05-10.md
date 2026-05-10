# Piece 2 Stage 1B — Controlled Scoped Ontology Activation

**Date:** 2026-05-10
**Builds on:** Stage 1 (`docs/inbox/piece_2_stage1_implementation_2026-05-10.md` + completion report)
**Status:** DRAFT — awaiting your sign-off on 5 design decisions before execution.

---

## Why Stage 1B exists (the gap left by Stage 1)

Stage 1 shipped scoped prompt construction + 3-branch decision logic + audit
recorder behind a constructor flag `enforce_scoped_prompts: bool = False`.
**Today nobody sets it to True in production.** Audit of 8 callers:

| File | Line | Sets `enforce_scoped_prompts`? | Passes `classification_metadata`? | Branch in production |
|---|---|---|---|---|
| `brain/app.py` (extraction worker) | 698 | no | no | legacy |
| `brain/app.py` (extraction request handler) | 1051 | no | no | legacy |
| `scripts/run_vault_extraction.py` | 708 | no | **YES** (line 781) | legacy (because flag is False) |
| `scripts/_batch_reextract_failed.py` | 91 | no | no | legacy |
| `scripts/_extract_one.py` | 35 | no | no | legacy |
| `scripts/reextract_5_docs.py` | 64 | no | no | legacy |
| `scripts/test_ontology_extraction.py` | 81 | no | no | legacy |
| `scripts/reextract_with_graph.py` | 87 | no | no | legacy |

The scoped path has **zero production traffic**. Stage 1 successfully shipped
the mechanism without changing behavior; Stage 1B activates it for one path,
in one observable way, with rollback safety. Stage 2 (later) flips the
default after Stage 1B yields enough evidence to justify the flip.

---

## Stage 1B scope (what this brief WILL do)

**ADD-only**, per Stage 1 discipline:

1. Add an env-var gate `CF_PIECE2_SCOPED_EXTRACTION` (default `false`,
   accepts `true`/`1`/`yes`) read in `scripts/run_vault_extraction.py` only.
   When set, that one caller passes `enforce_scoped_prompts=True` to the
   pipeline. **No other caller touched.** No constructor default flipped.
2. Reuse the `classification.to_dict()` already passed at line 781 — no
   new classification work.
3. Add structured per-document telemetry logging (NEW
   `extraction_events` rows under `platform.extraction_events` with
   event_type='scoped_extraction_decision') so we can see, after a Stage
   1B run: which docs took the scoped path, which fell to skip_failed,
   which would have taken legacy if the gate were off, and the audit
   row id for cross-reference.
4. Provide a one-document `dry_run_classify` helper script that prints
   the decision per doc without running extraction — for previewing
   what a full Stage 1B run would do.
5. Run a SINGLE controlled experiment: pick one corpus (decision #2
   below), run BOTH legacy and scoped against it, diff entity/relation
   counts + per-question accuracy if test set exists, write findings
   doc.

**NOT in Stage 1B:**

- No flip of `enforce_scoped_prompts` default.
- No changes to brain/app.py production extraction.
- No changes to MultiModelExtractor (SHA-locked since Stage 1).
- No changes to legacy SchemaPromptGenerator methods (signature lock
  preserved).
- No re-extraction of existing production vaults.
- No new audit signal types (continue using low_confidence + classification_failed
  + the new unknown_primary_domain reason code from the architect fix).

---

## Stage 1B steps (sequential, gated)

### Step A — env-var gate
- Add `CF_PIECE2_SCOPED_EXTRACTION` env-var read in
  `scripts/run_vault_extraction.py` near line 708 instantiation.
- Pass `enforce_scoped_prompts=<bool>` to the constructor.
- Log `[Piece2-Stage1B] CF_PIECE2_SCOPED_EXTRACTION=<value> → enforce_scoped_prompts=<bool>`
  at startup so it's unambiguous which path ran.
- One unit test: env-var parsing (true/false/1/0/yes/no/missing).

### Step B — telemetry
- Add `_record_scope_decision_telemetry(document_id, scope_decision, primary_domain, audit_id)`
  helper on `OntologyCentricPipeline`.
- Inserts one row into `platform.extraction_events` with
  `event_type='scoped_extraction_decision'`, `document_id`, payload
  `{decision, primary_domain, classification_status, classification_confidence, audit_record_id}`.
- Wrap in SAVEPOINT (same pattern as `AuditRecorder.emit` post-architect fix).
- Wired only when `enforce_scoped_prompts=True` (no telemetry from legacy
  callers — they'd produce 100% noise).
- 2 unit tests: row is written + telemetry failure does not break pipeline.

### Step C — dry-run helper
- NEW `scripts/piece2_stage1b_dry_run_classify.py` that takes
  `--tenant-id` + `--corpus-folder` and walks the docs the way
  `run_vault_extraction.py` does, but instead of extracting:
  1. Loads document.
  2. Runs the same classifier (`classification.to_dict()`).
  3. Calls `pipe._classify_for_scoped(metadata)` with strict mode and
     prints `(doc_id, doc_name, primary_domain, confidence, decision,
     would_skip_count, expected_entity_types_count)`.
- No DB writes. Pure read-only audit.
- One smoke test: run against an existing tenant + assert script
  exits 0 with non-empty output.

### Step D — pilot run (the controlled experiment)
- Pick ONE corpus from decision #2 below.
- Two runs of `run_vault_extraction.py` against the SAME corpus into
  TWO DIFFERENT tenant_ids:
  - Run L: `CF_PIECE2_SCOPED_EXTRACTION=false` (legacy path, baseline).
  - Run S: `CF_PIECE2_SCOPED_EXTRACTION=true` (scoped path, pilot).
- After both finish, capture per-tenant counts:
  - entities by type
  - relations by type
  - skip_failed count + reasons (audit_records)
  - unknown_primary_domain count
  - low_confidence audit count
- If a test corpus exists for the chosen corpus (decision #3), run
  `python -m src.test_runner.runner --corpus <name>` against both
  tenant_ids and diff scores.

### Step E — findings doc
- Write `docs/inbox/piece_2_stage1b_findings_2026-05-10.md` with:
  - Counts table (legacy vs scoped per type).
  - Skip rate + reasons.
  - Question-set delta if applicable.
  - Recommendation: green-light Stage 2 default flip / iterate / rollback.
- Stop. Wait for sign-off on Stage 2 brief.

---

## 5 decisions I need from you before execution

### Decision 1 — gate scope
Stage 1B activates scoped mode behind `CF_PIECE2_SCOPED_EXTRACTION` env
var, applied ONLY to `scripts/run_vault_extraction.py`.

  - (a) **Env-var-only on `run_vault_extraction.py` (recommended).** brain/app.py
        production extraction stays legacy. Lowest blast radius. ← my recommendation
  - (b) Env-var on `run_vault_extraction.py` AND brain/app.py
        ExtractionWorker. Larger blast radius, but covers the live web ingestion
        path so the experiment also exercises real user uploads.
  - (c) Constructor-arg-only (`enforce_scoped_prompts=True`) in code, no
        env-var. Requires editing each caller individually and a code-flip
        to roll back. Slowest to revert.

### Decision 2 — pilot corpus
Which corpus do we run the controlled experiment against?

  - (a) **ClaudeCode Nexus Industries (recommended).** Has 100 questions, has a
        scored baseline (77/100, v1 ceiling per replit.md), classification almost
        certainly maps to manufacturing+supply_chain+finance+it_infrastructure
        domains — exercises 4 of 8 seeded domains. Question set will let us
        score scoped vs legacy directly.
  - (b) Manus Orion. Scored baseline exists but smaller. Currently failing
        workflow per logs.
  - (c) ClaudeCode Medsync. Healthcare-focused — single-domain test, will
        exercise the healthcare ontology cleanly.
  - (d) Synthetic 5-doc smoke corpus, no question set. Fastest iteration but
        no accuracy signal — only counts/decision-distribution signal.

### Decision 3 — accuracy scoring
Should Stage 1B include question-set accuracy scoring (vault → test runner)
or counts-only?

  - (a) **Counts + audit signals only (recommended for first pass).** Faster
        feedback (~30 min). Defer accuracy scoring to a Stage 1B-2 iteration if
        counts look healthy.
  - (b) Counts + full test-runner pass (~2-3 hrs based on Nexus baseline runs in
        replit.md). Single shot, complete picture, expensive if scoped is
        broken at the count level.
  - (c) Counts first; if signals are green, gate the test-runner pass on
        explicit second sign-off.

### Decision 4 — telemetry destination
The new scope-decision telemetry rows.

  - (a) **`platform.extraction_events` (recommended).** Existing table, already
        scoped to documents, query patterns established. Reuses infra.
  - (b) NEW dedicated table `platform.scope_decisions`. Cleaner schema but
        requires a migration + Step C-style sign-off cycle.
  - (c) Log lines only, no table writes. Cheapest, but loses queryability.

### Decision 5 — rollback definition
What constitutes "abort Stage 1B and roll back" mid-run?

  - (a) **`skip_failed` rate > 25% on the pilot corpus (recommended).** Indicates
        classification metadata quality is too low to support scoped mode safely.
  - (b) Any extraction job FAILED with new error type not seen in legacy run.
  - (c) Audit `unknown_primary_domain` rate > 5% (the architect-fix path —
        suggests classifier outputting domain names not in our 8-row seed).
  - (d) All of (a)+(b)+(c).
  - (e) Custom threshold — please specify.

---

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Classifier returns domain names not in our 8 seeded domains | Medium — seeded list is fixed, classifier may emit more granular labels | Architect-fix unknown_primary_domain handling already in place; Stage 1B audits the rate |
| Scoped extraction misses entities legacy would have caught (e.g. cross-domain doc) | Medium-high | Step D legacy-vs-scoped count diff catches this; rollback per Decision 5 |
| Telemetry table writes inflate tenant DB cost | Low | One row per extraction call, savepoint-isolated, scoped to runs with flag on |
| MultiModelExtractor SHA drifts | Locked by test, will fail loudly | SHA test in tests/extraction/test_multi_extractor_prompt_sha.py blocks |
| brain/app.py production extraction accidentally takes scoped path | Low IF Decision 1=(a) | Only changing run_vault_extraction.py; brain/app.py untouched |

---

## Acceptance criteria for Stage 1B close-out

- [ ] All Stage 1 tests still pass (87/87).
- [ ] New tests for env-var parsing + telemetry write + telemetry-failure isolation pass (target: +4 tests, total 91).
- [ ] Dry-run script runs cleanly against an existing tenant.
- [ ] Pilot run completes both legs (L and S) without unhandled exceptions.
- [ ] Findings doc written with concrete recommendation for Stage 2.
- [ ] No changes to brain/app.py extraction code (verified by git diff scope).
- [ ] `EXTRACTION_SYSTEM_PROMPT` SHA still 5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963.

---

## What happens after Stage 1B sign-off

Stage 2 brief (separate, after Stage 1B findings) will decide one of three paths
based on Stage 1B evidence:
- **Promote**: flip `enforce_scoped_prompts` default to True, migrate brain/app.py.
- **Iterate**: address specific failure modes (e.g. classifier coverage gap, missing
  domain seeds, prompt phrasing tweaks) in a Stage 1C, re-run pilot.
- **Rollback**: deprecate scoped path, document why scoped extraction underperformed
  legacy, recover Stage 1 + 1B effort as architectural learning.
