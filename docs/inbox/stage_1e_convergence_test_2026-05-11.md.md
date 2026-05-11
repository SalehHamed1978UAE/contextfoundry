# Stage 1E — Empirical Multi-Cycle Promotion Convergence Test

## Alignment

- **Module touched:** tenant-scoped Gardener promotion execution for S only
- **Product vs implementation:** implementation-level diagnostic before scheduler activation or Stage 2 default activation
- **Architecture-doc consistency:** follows Stage 1C/1D findings: scoped extraction mechanics validated, but TRUSTED promotion remains unresolved; relationship promotion is structurally chained behind trusted endpoints
- **Drift risk:** starting the global scheduler before proving tenant-scoped convergence; treating the 2-minute timeout as a correctness failure; fixing Gardener performance before measuring behavior
- **Out of scope:** code edits, scheduler activation, performance fixes, VerificationWorker full run, Stage 2 implementation, Nexus 100 scoring, v2, workflow restarts, `replit.md` edits

## Decision

Authorize **Stage 1E: Empirical Multi-Cycle Convergence Test**.

Run up to two sequential tenant-scoped manual promotion cycles on the S vault.

Do not start the scheduler.

Do not edit Gardener code.

Do not fix the N+1 endpoint lookup yet.

Do not run VerificationWorker.

Do not run a third cycle in this task.

## Accepted Stage 1D findings

Accepted:

```text
promotion_pass() handles both entities and relationships.
Entity loop runs first.
Relationship loop runs second.
Relationship promotion requires both endpoint entities to be TRUSTED.
S had only 27 trusted entities after its first cycle, so 0 trusted relationships is explainable.
L had 78 trusted entities after its first cycle, which allowed 9 relationships to promote.
The prior manual S promotion attempt was killed by the 2-minute timeout before promotion_pass() returned and before COMMIT.
No state changed during the failed attempt.
The N+1 endpoint lookup loop is a real performance concern but out of scope for this task.
````

## Goal

Empirically answer:

```text
If S gets additional promotion cycles after canonicalization has settled, do more entities promote, and do relationships begin promoting once endpoints are trusted?
```

## Execution rule

Run at most two tenant-scoped cycles:

```bash
PYTHONPATH=. python -u scripts/run_promotion.py --tenant-id 5df41308-4033-441d-b712-77928b8ea93e
```

Use a 10-minute timeout per cycle.

If a 10-minute foreground run is not possible in the shell tool, use the existing approved one-shot workflow pattern for this exact tenant-scoped command.

If a workflow slot issue appears, stop and report before freeing or modifying any workflow.

## Cycle 1 — B-retry

### Pre-cycle 1 snapshot

Before running, capture:

```text
timestamp
S tenant/vault id
S entities by lifecycle_state
S relationships by lifecycle_state
S gardener_logs count and latest cycle id
S entities promoted_at >= last run timestamp
S relationships promoted_at >= last run timestamp
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
```

### Run cycle 1

Run exactly one tenant-scoped promotion cycle.

Do not start scheduler.

Do not run VerificationWorker.

### Post-cycle 1 snapshot

After the command exits or times out, capture:

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
relationship endpoint-trust counts after cycle 1
```

## Gate before Cycle 2

Run Cycle 2 only if Cycle 1:

```text
completed successfully
committed
did not change global ontology.types
did not change global ontology.relations
did not trigger any stop condition
```

If Cycle 1 times out, errors, or does not commit:

```text
stop and report
do not run Cycle 2
```

## Cycle 2 — convergence check

If Cycle 1 passes the gate, run one more tenant-scoped promotion cycle with the same command and the same timeout.

### Pre-cycle 2 snapshot

Capture:

```text
S entities by lifecycle_state
S relationships by lifecycle_state
gardener_logs count and latest cycle id
relationship endpoint-trust counts after Cycle 1
```

### Run cycle 2

Run exactly one tenant-scoped promotion cycle.

Do not start scheduler.

Do not run VerificationWorker.

### Post-cycle 2 snapshot

Capture:

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
relationship endpoint-trust counts after cycle 2
```

## Comparative findings

After Cycle 1 and, if allowed, Cycle 2, report:

```text
total entities promoted in Cycle 1
total relationships promoted in Cycle 1
total entities promoted in Cycle 2
total relationships promoted in Cycle 2
whether Cycle 2 promoted meaningfully more relationships than Cycle 1
whether endpoint-chained relationships unlocked after Cycle 1 entity promotions
whether the system appears to be approaching steady-state
whether a Cycle 3 would likely add value
whether scheduler activation is still recommended
whether Stage 2 remains blocked
```

## Outcome classification

Classify the result:

### Case 1 — Cycle 1 completes and promotes many entities, Cycle 2 promotes relationships

Supports:

```text
H1 cycle gap + endpoint-chained relationship promotion
```

Recommendation likely:

```text
scheduler activation / recurring promotion cadence needed before Stage 2
```

### Case 2 — Cycle 1 promotes entities, Cycle 2 still promotes no relationships

Indicates:

```text
relationship endpoint gate or relationship eligibility remains blocked
```

Report exact endpoint-trust counts and failing criteria.

### Case 3 — Both cycles complete and promote almost nothing

Indicates:

```text
eligibility estimates missed a hidden blocker
```

Report the hidden criterion.

### Case 4 — Any cycle times out

Do not retry automatically.

Report:

```text
timeout duration
last log line
whether any commit occurred
state before/after
likely bottleneck
```

Then recommend either a performance-fix task or workflow-backed longer run.

## Findings doc

Update:

```text
docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md
```

Add:

```text
Stage 1E multi-cycle result
pre/post lifecycle counts per cycle
whether Cycle 1 promoted entities
whether Cycle 2 promoted relationships
relationship endpoint-trust counts per cycle
whether scheduler activation is still recommended
whether Stage 2 remains blocked
N+1 endpoint lookup recorded as a Stage 2 performance ticket, not fixed here
endpoints_not_trusted gate recorded as architectural property, not a bug
```

## Stop triggers

Stop and report immediately if:

```text
the command would run against more than the S tenant
the command requires code edit
the command requires scheduler activation
the command requires VerificationWorker
global ontology.types changes
global ontology.relations changes
a workflow slot must be freed
Cycle 1 times out
Cycle 1 errors
Cycle 1 does not commit
Cycle 2 times out
Cycle 2 errors
unexpected changes appear in another tenant/vault
```

## Standing constraints

Do not start Stage 2.

Do not start scheduler.

Do not edit code.

Do not fix Gardener performance.

Do not run VerificationWorker.

Do not run Nexus 100 scoring.

Do not touch v2.

Do not restart workflows.

Do not edit `replit.md`.

## Final report

Report:

```text
pre-cycle 1 snapshot
cycle 1 command, runtime, exit status
post-cycle 1 snapshot
whether Cycle 2 gate passed
pre-cycle 2 snapshot, if run
cycle 2 command, runtime, exit status, if run
post-cycle 2 snapshot, if run
gardener_logs delta
entity promotion delta per cycle
relationship promotion delta per cycle
relationship endpoint-trust analysis
global ontology substrate check
updated hypothesis verdicts
recommendation for next action
whether scheduler activation is recommended
whether Stage 2 remains blocked
```

## Stop condition

Stop after the Stage 1E report.

Wait for sign-off.