Here's the clean instruction set. Copy this whole thing into a new file at docs/inbox/piece_2_stage1b_beta_extraction_unblock_2026-05-10.md, then send Replit a one-line message pointing to it.

markdown# Piece 2 Stage 1B β — Extraction Execution Unblock

## Alignment

- **Module touched:** read-only queue-consumer investigation; one-shot workflow execution if needed; β extraction execution
- **Product vs implementation:** unblocking β extraction execution so the L-vs-S comparison can produce data
- **Architecture-doc consistency:** preserves signed-off β design — same corpus, fresh L/S vaults, same current codebase, only `CF_PIECE2_SCOPED_EXTRACTION` differs
- **Drift risk:** using a queue consumer that ignores the env var; creating workflows that affect anything outside the β extraction runs; silently downgrading to incremental polling or partial findings; L mutating global ontology before S runs
- **Out of scope:** Stage 2, Nexus 100 scoring, MultiModelExtractor prompt changes, `brain/app.py` edits, Gardener, Data Gates, v2, `replit.md` edits, restarting existing workflows, killing running workflows

## Decision

Run **D first as a bounded read-only investigation, max 10 minutes**, then proceed directly to **A** if D does not reveal a clean path.

Do not use B (incremental --limit polling) or C (stop and file partial findings).

Do not silently downgrade to δ or ε.

## Step D — Read-only investigation, max 10 minutes

Investigate whether an existing long-lived consumer can run the extraction safely.

Check:

1. Does `brain/app.py`, `web_app.py`, or another active service consume `extraction_requests`?
2. If yes, does it honor `CF_PIECE2_SCOPED_EXTRACTION`?
3. If yes, can it be targeted to one vault at a time?
4. If yes, can it guarantee:
   - L uses `CF_PIECE2_SCOPED_EXTRACTION=false`;
   - S uses `CF_PIECE2_SCOPED_EXTRACTION=true`;
   - no unrelated worker drains either queue;
   - L and S run sequentially, not concurrently?

Do not enable anything during D.

If an existing consumer exists but ignores the env var, it is unusable for β. Proceed to A.

If an existing consumer exists and does honor the env var, **stop and report before enabling it**.

If no clean consumer exists, **proceed directly to Step A** without pausing.

## Step A — One-shot workflows (pre-authorized fallback)

Create task-specific one-shot workflows for the extraction runs.

This is authorized as the fallback if D does not reveal a clean existing consumer.

This is **not** a restart of an existing workflow. It is a new task-specific workflow that runs once and exits. The standing "no workflow restarts" rule applies to Manus Orion, Ontology Vault, Start All, and Medsync; it does not apply to creating new task-specific workflows for authorized long-running commands.

### Workflow 1: `S1B-Beta-L-Extract`

Run:

```bash
CF_PIECE2_SCOPED_EXTRACTION=false \
python -u scripts/run_vault_extraction.py --vault-id f38e400f-0bba-47d8-b8cc-b41fbaff059f
```

If the runner uses a different supported vault/tenant flag, use the correct flag and report the exact command.

Wait for L to finish before starting S.

### Workflow 2: `S1B-Beta-S-Extract`

Run only after L completes and after the post-L global ontology substrate check passes:

```bash
CF_PIECE2_SCOPED_EXTRACTION=true \
python -u scripts/run_vault_extraction.py --vault-id 
```

Use the actual S vault ID from the upload report.

## Pre-run checks before L

Verify:

```text
L vault = 100 docs
S vault = 100 docs
L/S corpus equality still holds
L graph outputs empty
S graph outputs empty
EXTRACTION_SYSTEM_PROMPT SHA = 5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963
```

Capture global ontology substrate snapshot before L:

```text
ontology.types total count
ontology.types count by domain_id
ontology.relations total count
ontology.relations count by domain_id/status
```

## After L completes (before S)

Capture the same global ontology substrate snapshot.

If L changed global `ontology.types` or `ontology.relations` row counts, **stop before S and report**. Tenant-scoped extraction outputs may change (entities, relationships in the tenant's graph) — that is expected. Global ontology mutation is not.

If L did not change global ontology substrate, proceed to S.

Report L metrics:

```text
L workflow exit status
L runtime
L documents extracted/skipped/failed
L entities count
L relationships count
L audit_records count
L low_confidence count
L skip_failed count/rate
L extraction errors if any
```

## After S completes

Capture global ontology substrate snapshot for the third time.

Report S metrics:

```text
S workflow exit status
S runtime
S documents extracted/skipped/failed
S entities count
S relationships count
S audit_records count
S low_confidence count
S skip_failed count/rate
S extraction errors if any
number of docs using scoped prompts
domain distribution
documents with classification_status != ok
documents with unknown/unseeded primary_domain
```

## Prompt-scope evidence

For at least three scoped S documents, report:

```text
filename
primary_domain
scope domains = [core, primary_domain]
type count
relation count
example included core types
example included primary-domain types
example included core relations
example included primary-domain relations
confirmation NULL-domain rows excluded
confirmation other named domains excluded
```

## Comparison table

| Metric                  | Legacy L | Scoped S | Delta |
| ----------------------- | -------: | -------: | ----: |
| documents processed     |          |          |       |
| documents failed        |          |          |       |
| entities extracted      |          |          |       |
| relationships extracted |          |          |       |
| audit_records           |          |          |       |
| low_confidence signals  |          |          |       |
| runtime                 |          |          |       |

Also answer:

```text
Did scoped extraction reduce noisy entity types?
Did scoped extraction lose expected organizational relations?
Did scoped extraction skip any docs?
Did audit_records capture low-confidence cases?
Did scoped prompts include HOLDS_POSITION / WORKS_AT / REPORTS_TO after Piece 0.6?
Did HAS_COMPENSATION appear only in finance-scoped prompts?
```

## Findings document

Update:

```text
docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md
```

Include:

```text
executive summary
setup
tenant_ids
corpus equality verification
α full dry-run results
workflow execution method
global ontology substrate checks
legacy-vs-scoped counts
audit_records summary
prompt-scope evidence
rollback-trigger result
recommendation for Stage 2
known limitations
```

Include this limitation:

```text
Stage 1B β required one-shot Replit workflows because the bash tool reaps long-running child processes after the 120-second tool boundary. The extraction commands themselves were unchanged.
```

## Architect review

After β completes and before final report, run architect review focused on:

```text
workflow execution did not alter experiment design
env-var gate remained isolated to run_vault_extraction.py
default behavior remains legacy
brain/app.py untouched
MultiModelExtractor prompt unchanged
telemetry safe
global ontology substrate did not drift between L and S
findings doc distinguishes fresh L/S results from historical Nexus baselines
no Stage 2 behavior slipped in
```

If architect finds HIGH issues, stop and report.

## Execution rules

- Do not run L and S concurrently.
- Do not use a default queue worker unless D proves it honors the env var and is explicitly authorized.
- Do not restart existing workflows (Manus Orion, Ontology Vault).
- Do not kill Start All or Medsync.
- Do not run Nexus 100 scoring.
- Do not start Stage 2.
- Do not change MultiModelExtractor prompt.
- Do not touch `brain/app.py`.
- Do not touch Gardener, Data Gates, v2, or `replit.md`.

## Stop triggers

Stop and report if:

```text
D finds a potentially usable env-var-aware worker (requires authorization to enable)
workflow creation fails
L and S would run concurrently
an unrelated worker starts draining either queue
L changes global ontology.types or ontology.relations before S
skip_failed rate > 25% on either run
scoped prompts include NULL-domain rows
scoped prompts fall back to full union
core is missing from scope
primary_domain is missing from scope
MultiModelExtractor prompt SHA changes
brain/app.py changes
tests fail
runtime or spend becomes concerning
```

## Final report

Report:

```text
D investigation findings (or confirmation of "no clean consumer; proceeded to A")
workflow names and commands (if A used)
tenant_ids used
corpus equality verification
global ontology substrate checks (3 snapshots: pre-L, post-L/pre-S, post-S)
L run metrics
S run metrics
L-vs-S comparison
audit_records summary
prompt-scope evidence
findings doc path
architect review result
EXTRACTION_SYSTEM_PROMPT SHA
confirmation no Nexus 100 scoring
confirmation no Stage 2
confirmation no MultiModelExtractor prompt change
confirmation no brain/app.py, Gardener, DataGate, v2, workflow restart, or replit.md work
```

## Cleanup

If one-shot workflows are created, leave their logs available as evidence in the findings doc.

Do not delete the L/S vaults. They remain as inputs to Stage 2 design discussions.

## Stop condition

Stop after the Stage 1B β final report and architect review.

Do not begin Stage 2.
Do not run Nexus 100 scoring.