# Stage 1F — Read-Only Gardener Promotion Performance and Relationship Blocker Audit

## Alignment

- **Module touched:** read-only diagnosis only — Gardener promotion internals, relationship eligibility, ontology validation, pending-duplicates lookup
- **Product vs implementation:** implementation-level diagnosis before scheduler activation, promotion retry, or Stage 2 default activation
- **Architecture-doc consistency:** follows Stage 1D/1E findings: scoped extraction works mechanically, but promotion convergence remains blocked; relationship promotion is structurally chained and may also be blocked by validation or performance
- **Drift risk:** running longer workflows before knowing whether relationship promotion is logically blocked; fixing performance before locating the actual bottleneck; treating a timeout as convergence evidence
- **Out of scope:** code edits, DB mutations, workflow creation, scheduler activation, manual promotion run, VerificationWorker full run, Stage 2 implementation, Nexus 100 scoring, v2, workflow restarts, `replit.md` edits

## Decision

Do **Option 1** first.

Run a read-only audit of the Gardener promotion bottleneck and relationship blocker.

Do not run another promotion cycle yet.

Do not create a workflow.

Do not start scheduler.

Do not edit code.

## Accepted Stage 1E findings

Accepted:

```text
Cycle 1 timed out at 90s.
No COMMIT occurred.
S state was identical before and after.
Cycle 2 was correctly not run.
Global ontology remained unchanged.
95 S STAGING relationships already have both endpoints TRUSTED.
S still has 0 TRUSTED relationships.
promotion_pass runtime exceeds 90s on S.
````

This means Stage 1E is **inconclusive**, not failed.

## Goal

Answer two questions before any longer promotion run:

```text
1. Why does promotion_pass exceed 90 seconds on S?
2. Why did 95 endpoint-eligible relationships not promote?
```

## Required read-only code audit

Read and report on:

```text
src/context_foundry/agents/gardener.py
scripts/run_promotion.py
any ORM models/tables used by:
  duplicate/canonicalization checks
  relationship validation
  gardener_logs
  promotion thresholds
```

Focus on:

```text
_get_entity_ids_with_pending_duplicates
promotion_pass entity loop
promotion_pass relationship loop
is_valid_relationship_type / ontology relation validation
gardener.py exception handling around relationship promotion
where gardener_logs are written
where COMMIT happens
```

## Required DB diagnostics

Read-only queries only.

### 1. Pending duplicates / canonicalization bottleneck

Report:

```text
global pending duplicate count
S-specific pending duplicate count
whether _get_entity_ids_with_pending_duplicates is tenant-scoped
whether it fetches globally and filters in Python
whether it uses efficient joins/indexes
whether S pending duplicates include STAGING entities that are otherwise promotion-eligible
```

Also report whether pending duplicates are blocking promotion as intended or just slowing it down.

### 2. Entity promotion loop cost

Estimate the query pattern for S:

```text
number of S STAGING entities
per-entity queries executed
threshold lookup behavior
duplicate/conflict checks
ontology validation checks
expected total query count
```

Report whether the loop is likely to complete within:

```text
90 seconds
10 minutes
longer than 10 minutes
```

### 3. Relationship promotion loop cost

Estimate the query pattern for S:

```text
number of S STAGING relationships
source endpoint lookup count
target endpoint lookup count
ontology validation lookup count
threshold lookup count
expected total query count
```

Confirm whether the rel loop is an N+1 pattern.

### 4. Relationship validation for the 95 endpoint-eligible rels

For the 95 S STAGING relationships with both endpoints TRUSTED, report:

```text
relationship_type distribution
confidence distribution
validation_status distribution
source_document_id coverage
evidence_records coverage
whether relation_type exists in ontology.relations ACTIVE
whether relation_type is domain-valid under current validation logic
whether is_valid_relationship_type would pass or fail
```

This is critical. If all 95 fail ontology validation, a longer promotion run will not promote them.

### 5. Silent exception analysis

Inspect the relationship loop exception handling.

Report:

```text
where exceptions are caught
whether exceptions are logged
whether exceptions are swallowed and loop continues
whether an exception can abort all relationship promotion silently
whether gardener_logs would show the failure
```

### 6. Original post-extraction cycle analysis

Using gardener_logs and timestamps, report:

```text
did the original S post-extraction cycle reach the relationship loop?
were there any relationship BLOCK / SKIP / ERROR logs?
were the 95 endpoint-eligible relationships present at original cycle time or only later?
if they were present, why did they not promote?
if they were not present, when did they become endpoint-eligible?
```

## Required outputs

Produce:

```text
executive summary
runtime bottleneck ranked list
relationship blocker ranked list
evidence table
query-count estimate
95-relationship validation table
whether a 10-minute workflow-backed run is likely to complete
whether a longer run would be informative
recommended next action
```

## Hypothesis verdicts to update

Update these:

```text
H7 — silent rel-loop exception or ontology-validation block
H8 — promotion runtime exceeds 90s on S
H9 — global pending_duplicates fetch / N+1 query bottleneck
H10 — endpoint-eligible rels fail ontology validation
```

For each:

```text
supported
rejected
inconclusive
evidence
```

## Decision outputs

At the end, recommend one of:

```text
A. workflow-backed long-run is worth doing now
B. performance fix required before any long-run
C. relationship validation bug/fix required before any long-run
D. scheduler activation remains blocked
E. Stage 2 remains blocked
```

## Stop conditions

Stop and report immediately if diagnosis requires:

```text
DB mutation
code edit
workflow creation
scheduler activation
manual promotion run
VerificationWorker run
Nexus 100 scoring
v2 work
```

Do not fix anything in this task.

## Findings doc

Update:

```text
docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md
```

Add:

```text
Stage 1F read-only diagnosis
runtime bottleneck findings
relationship blocker findings
95 endpoint-eligible relationship analysis
recommendation for whether to run a workflow-backed promotion retry
whether Stage 2 remains blocked
```

## Standing constraints

Do not start Stage 2.

Do not mutate DB.

Do not edit code.

Do not create workflows.

Do not run promotion.

Do not start scheduler.

Do not run VerificationWorker.

Do not run Nexus 100 scoring.

Do not touch v2.

Do not restart workflows.

Do not edit `replit.md`.

## Stop condition

Stop after the Stage 1F read-only diagnostic report.

Wait for sign-off.