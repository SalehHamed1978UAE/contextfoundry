SEND TO REPLIT — START

# Stage 1G — Workflow-Backed Tenant-Scoped Promotion Run for S

## Alignment

- **Module touched:** one tenant-scoped Gardener promotion execution for S; read-only pre/post diagnostics
- **Product vs implementation:** implementation-level diagnostic before scheduler activation or Stage 2 default activation
- **Architecture-doc consistency:** follows Stage 1F findings: scoped extraction works mechanically, but promotion convergence remains unresolved; relationship promotion may be slow and/or blocked by relationship validation
- **Drift risk:** starting scheduler globally before proving tenant-scoped behavior; fixing performance before capturing the actual blocker; losing `result.block_reasons` / `result.errors` to shell timeout
- **Out of scope:** code edits, performance fixes, scheduler activation, VerificationWorker full run, Stage 2 implementation, Nexus 100 scoring, v2, workflow restarts unrelated to this one-shot run, `replit.md` edits

## Decision

Authorize **one workflow-backed tenant-scoped promotion run** on S.

Do not start the scheduler.

Do not edit Gardener code.

Do not fix the N+1 endpoint lookup yet.

Do not run VerificationWorker.

Do not run multiple cycles automatically.

Do not start Stage 2.

## Accepted Stage 1F findings

Accepted:

```text
promotion_pass runtime exceeds the shell timeout on S.
The relationship loop has an N+1 endpoint lookup pattern.
S has 1171 STAGING relationships.
The rel loop does roughly 2342 endpoint SQL roundtrips.
The pending-duplicates fetch is global and returns 1599 rows.
95 S STAGING relationships already have both endpoints TRUSTED.
26 of those 95 are blocked by invalid relationship types:
  FUNDED_BY, RELATED_TO, USES
69 endpoint-eligible relationships remain unexplained without a successful cycle.
````

Therefore, a successful full promotion run is needed to capture:

```text
result.block_reasons
result.errors
relationship promotion counts
whether the 69 unexplained relationships promote or hit a hidden gate
```

## Goal

Answer:

```text
Can a full tenant-scoped promotion cycle complete on S when run under a workflow-backed execution environment?
If it completes, do additional entities promote?
If it completes, do any relationships promote?
If relationships do not promote, what block reasons does the successful run report?
```

## Workflow authorization

Create a one-shot workflow only if needed for the long-running command.

Name:

```text
S1G-S-Manual-Promotion
```

Command:

```bash
bash -lc 'set -o pipefail; PYTHONPATH=. python -u scripts/run_promotion.py --tenant-id 5df41308-4033-441d-b712-77928b8ea93e 2>&1 | tee /tmp/s1b_beta/s1g_s_manual_promotion.log'
```

If the workflow system requires a simpler command, use the equivalent command that:

```text
sets PYTHONPATH=.
runs scripts/run_promotion.py --tenant-id 5df41308-4033-441d-b712-77928b8ea93e
captures stdout and stderr to /tmp/s1b_beta/s1g_s_manual_promotion.log
```

If a workflow slot issue appears, stop and report before removing or modifying any workflow.

Do not run this command against any tenant except:

```text
5df41308-4033-441d-b712-77928b8ea93e
```

## Pre-run snapshot

Before starting the workflow, capture:

```text
timestamp
S tenant/vault id
S entities by lifecycle_state
S relationships by lifecycle_state
S gardener_logs count and latest cycle id
S entities promoted_at >= previous manual attempt timestamp
S relationships promoted_at >= previous manual attempt timestamp
global ontology.types count
global ontology.relations count
```

Also capture eligibility counts:

```text
S STAGING entities total
S STAGING entities confidence >= default threshold
S STAGING entities past dwell
S STAGING entities validation_status valid
S STAGING relationships total
S STAGING relationships confidence >= default threshold
S STAGING relationships with trusted source endpoint
S STAGING relationships with trusted target endpoint
S STAGING relationships with both endpoints trusted
S endpoint-eligible relationships by relationship_type
S endpoint-eligible relationships that are valid in ontology.relations
S endpoint-eligible relationships that are NOT valid in ontology.relations
```

## Run

Run exactly one tenant-scoped promotion cycle through the one-shot workflow.

Do not start scheduler.

Do not run VerificationWorker.

Do not run a second cycle automatically.

## Monitoring

Poll the workflow until it exits.

At each poll, report:

```text
workflow status
runtime so far
latest log line from /tmp/s1b_beta/s1g_s_manual_promotion.log
global ontology.types count
global ontology.relations count
```

If runtime exceeds 10 minutes, stop and report. Do not kill unless the workflow system requires cleanup and the user explicitly authorizes it.

## Post-run snapshot

After the workflow exits, capture:

```text
exit status
runtime
whether COMMIT occurred
new gardener_logs cycle id, if any
S entities by lifecycle_state
S relationships by lifecycle_state
newly promoted entity count
newly promoted relationship count
newly archived entity count
newly archived relationship count
global ontology.types count
global ontology.relations count
relationship endpoint-trust counts after the cycle
```

Also capture from the workflow log:

```text
result.block_reasons
result.errors
any printed promotion_stats
any traceback or logger error
last 50 log lines
```

## Interpret outcome

Classify the result:

### Case 1 — Completes and promotes entities + relationships

Report:

```text
H1 cycle gap supported
endpoint-chained relationships unlocked
scheduler cadence likely needed before Stage 2
```

Do not run a second cycle automatically.

### Case 2 — Completes and promotes entities but no relationships

Report:

```text
relationship blocker remains
endpoint-trust counts after cycle
relationship block reasons
whether the 69 previously unexplained rels were blocked by validation, confidence, unresolved conflict, endpoint trust, or another gate
```

### Case 3 — Completes and promotes almost nothing

Report:

```text
hidden blocker identified by result.block_reasons
whether Stage 2 remains blocked
```

### Case 4 — Workflow times out or fails

Report:

```text
runtime
last log line
whether COMMIT occurred
state before/after
whether this is performance-only or a correctness blocker
recommended next task:
  performance fix
  relationship validation fix
  scheduler deferral
```

Do not retry automatically.

## Findings doc

Update:

```text
docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md
```

Add:

```text
Stage 1G workflow-backed promotion result
pre/post lifecycle counts
whether the full cycle completed
whether entity promotion changed
whether relationship promotion changed
result.block_reasons
result.errors
relationship endpoint-trust analysis after the run
whether scheduler activation is still recommended
whether Stage 2 remains blocked
N+1 endpoint lookup remains a performance ticket, not fixed here
```

## Stop triggers

Stop and report if:

```text
the command would run against more than the S tenant
a workflow slot must be freed
the workflow command differs from the approved command
the run requires code edit
the run requires scheduler activation
the run requires VerificationWorker
global ontology.types changes
global ontology.relations changes
another tenant/vault changes unexpectedly
runtime exceeds 10 minutes
the workflow fails
```

## Standing constraints

Do not start Stage 2.

Do not start scheduler.

Do not edit code.

Do not fix Gardener performance.

Do not run VerificationWorker.

Do not run Nexus 100 scoring.

Do not touch v2.

Do not restart unrelated workflows.

Do not edit `replit.md`.

## Final report

Report:

```text
pre-run snapshot
workflow name and command
runtime and exit status
post-run snapshot
gardener_logs delta
entity promotion delta
relationship promotion delta
relationship endpoint-trust analysis
result.block_reasons
result.errors
global ontology substrate check
updated hypothesis verdicts
recommendation for next action
whether scheduler activation is recommended
whether Stage 2 remains blocked
```

## Stop condition

Stop after the Stage 1G report.

Wait for sign-off.
