# Stage 1B β — S Workflow Slot Resolution

## Alignment

- **Module touched:** workflow registry only, then Stage 1B S one-shot workflow
- **Product vs implementation:** infrastructure unblock for authorized S run
- **Architecture-doc consistency:** preserves v2 parked rule and workflow-restart rules; preserves signed-off β design
- **Drift risk:** interpreting `v2` workflow labels case-by-case; deleting logs/artifacts while freeing a workflow slot; running S outside workflow and reintroducing sandbox-reaping
- **Out of scope:** Stage 2, Nexus 100 scoring, prompt changes, MultiModelExtractor changes, `brain/app.py`, Gardener changes, Data Gates, v2 work, workflow restarts, `replit.md` edits

## Decision

Choose **Option B**.

Unregister:

```text
Run Canonical Bench
````

Do **not** unregister:

```text
Reextract Failed Docs v2
```

## Rationale

The v2-park rule is categorical. Workflow names containing `v2` are treated as v2-adjacent and are not touched unless explicitly unparked.

Even if `Reextract Failed Docs v2` is probably script-version naming and its command uses `--source v1`, interpreting that exception case-by-case creates the exact erosion the v2-park rule is meant to prevent.

`Run Canonical Bench` is the safer slot to free:

```text
- finished
- not v2-tagged
- not running
- results already captured in test_results/
- unregistering removes only the workflow shell
- it can be re-registered later if needed
```

## Why not Option C

Do not run S outside a workflow.

The sandbox already reaped detached/nohup/setsid processes. Workflows are the correct long-running execution primitive for the L/S extraction run.

## Guardrails before unregister

Before unregistering `Run Canonical Bench`, capture and paste:

```text
workflow name
workflow state
workflow command
whether any process for that command is currently running
known result artifact path(s), if visible
```

Expected:

```text
state = finished
no running process
results captured under test_results/
```

If any expected condition is false, stop and report.

## Removal scope

Remove only the workflow registration.

Do **not** delete:

```text
logs
artifacts
test_results
data
source code
finished-run records
```

Do not touch:

```text
Reextract Failed Docs v2
S1B-Beta-L-Extract
Start All
Test: ClaudeCode Medsync
Test: ClaudeCode Nexus
Test: Manus Orion
Test: Ontology Vault
v2 Oracle Run
v2 Parallel Run
```

## After slot is freed

Register:

```text
S1B-Beta-S-Extract
```

Command:

```bash
CF_PIECE2_SCOPED_EXTRACTION=true \
python -u scripts/run_vault_extraction.py --vault-id 5df41308-4033-441d-b712-77928b8ea93e
```

No other flags.

No `--use-ontology`.
No `--limit`.
No Nexus 100 scoring.

## Pre-start confirmations

Before starting S, re-confirm:

```text
S vault ID = 5df41308-4033-441d-b712-77928b8ea93e
S entities = 0
S relationships = 0
S documents = 100
S audit_records = 0
L remains stable at 2258 entities / 2192 relationships
ontology.types = 1037
ontology.relations = 254
EXTRACTION_SYSTEM_PROMPT SHA = 5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963
```

If any check fails, stop and report.

## Start S

Start `S1B-Beta-S-Extract`.

Capture:

```text
S workflow start time
S workflow command
S workflow name
S start epoch written to /tmp/s1b_beta/S_workflow_start_epoch.txt
```

## During S

Poll approximately every 10 minutes.

Report:

```text
workflow status
documents processed or phase marker
entities total
relationships total
audit_records count
low_confidence count
skip_failed count/rate
ontology.types count
ontology.relations count
ontology rows created/updated since S start
```

## Findings doc note

Add this operational note to:

```text
docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md
```

```text
The 10-workflow registry limit blocked registration of the S extraction workflow. The finished non-v2 workflow `Run Canonical Bench` was unregistered to free the slot. This removed only the workflow registration; result artifacts remained in `test_results/`. Future workflow lifecycle discipline should unregister finished benchmark workflows after results are captured.
```

## Stop triggers

Stop and report if:

```text
wrong workflow slot was removed
Run Canonical Bench is not actually finished
any result artifact would be deleted
S workflow command differs from approved command
S vault ID ambiguity reappears
S graph is not empty before start
skip_failed rate > 25%
scoped prompts include NULL-domain rows
scoped prompts fall back to full union
core is missing from scope
primary_domain is missing from scope
ontology.types changes
ontology.relations changes
MultiModelExtractor prompt SHA changes
brain/app.py changes
runtime or spend becomes concerning
```

## Continue constraints

Do not restart existing workflows.

Do not kill Start All.

Do not start Stage 2.

Do not run Nexus 100 scoring.

Do not touch prompts, MultiModelExtractor, `brain/app.py`, Gardener, Data Gates, v2, unrelated workflows, or `replit.md`.

## Final report

After S completes and stabilizes, produce the full β final report and architect review as previously authorized.

Do not begin Stage 2.

````

Compact version:

```text
Decision:
Option B.

Remove:
Run Canonical Bench workflow registration only.

Do not remove:
Reextract Failed Docs v2, logs, artifacts, test_results, data, code.

Then:
Register/start S1B-Beta-S-Extract with the approved scoped command.

Reason:
Avoid case-by-case interpretation of v2-labelled workflows.
````

This locks the rule going forward: **v2-labelled workflows are not touched unless explicitly unparked**, even if a specific case looks technically harmless.
