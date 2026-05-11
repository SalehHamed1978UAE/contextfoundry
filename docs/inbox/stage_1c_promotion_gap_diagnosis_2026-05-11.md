# Stage 1B β — Closeout Accepted, Promotion Gap Diagnosis Next

## Alignment

- **Module touched:** read-only diagnosis only — Gardener promotion behavior, lifecycle-state transitions, verification/corroboration inputs
- **Product vs implementation:** implementation-level diagnosis before Stage 2 default activation
- **Architecture-doc consistency:** matches Stage 1B β finding: scoped extraction mechanics validated, but TRUSTED promotion gap remains open
- **Drift risk:** starting Stage 2 while scoped extraction outputs are not promoting to TRUSTED; treating archive ratio as quality rejection without evidence; silently fixing Gardener before diagnosis
- **Out of scope:** code edits, DB mutations, Gardener fixes, VerificationWorker full run, Stage 2 implementation, Nexus 100 scoring, v2, workflow restarts, `replit.md` edits

## Decision

Stage 1B β extraction comparison is accepted.

β-Finding 4 remains open.

The dwell-time hypothesis is rejected:

```text
S entity TRUSTED count stayed 27 after dwell.
S relationship TRUSTED count stayed 0 after dwell.
All dwell windows elapsed.
STAGING rows moved to ARCHIVED, not TRUSTED.
````

Do **not** start Stage 2 implementation.

Run a read-only diagnostic task next:

```text
Stage 1C — Gardener Promotion Gap Diagnosis
```

## Goal

Determine why scoped S facts are not promoting to TRUSTED after dwell.

Do not fix anything in this task. Diagnose only.

## Required reads

Read:

```text
docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md
src/context_foundry/agents/gardener.py
src/context_foundry/workers/verification_worker.py
src/context_foundry/extraction/ontology_centric_pipeline.py
any scheduler / Start All code that invokes Gardener
```

## Required diagnostics

### 1. Gardener cycle coverage

For L and S tenants, report:

```text
whether Gardener cycles ran after extraction
cycle timestamps
tenant/vault IDs covered by each cycle
which passes ran
promotion_pass counts
demotion/archive counts
errors
```

If there is a `gardener_logs` table or equivalent, query it.

If no table exists, use logs or code path inspection.

### 2. Actual Gardener runtime config

Report actual values used by the running Gardener for:

```text
min_dwell_time_hours
require_verification_for_promotion
confidence thresholds
corroboration thresholds
type-specific thresholds
domain/ontology validation flags
tenant filters
batch limits
```

Do not rely on `replit.md` assertions. Inspect runtime config or code defaults.

### 3. Promotion eligibility comparison: L vs S

For L and S, compare STAGING rows against promotion criteria.

Report for entities and relationships:

```text
total STAGING
age >= dwell threshold
confidence distribution
verified / unverified counts
evidence_verification_status counts
corroboration counts if available
evidence_records counts if available
type/domain validation pass/fail if available
would-pass vs would-fail breakdown by criterion
```

### 4. Relationship-specific promotion blocker

S has:

```text
0 TRUSTED relationships
```

Investigate whether relationship promotion is blocked by:

```text
missing source_document_id
missing evidence_records
verification requirement
corroboration requirement
relationship type not domain-valid
scheduler not running relationship promotion
Gardener only promoting entities
```

Record findings. Do not fix.

### 5. Archive transition analysis

For the S rows that moved:

```text
199 entities STAGING → ARCHIVED
48 relationships STAGING → ARCHIVED
```

Sample archived rows and determine why they archived.

Check whether they have:

```text
duplicate_of / canonical_entity_id / merge target
conflict reason
demotion reason
low confidence
invalid type
missing evidence
identity-resolution merge marker
```

Classify archived rows into:

```text
identity-resolution merge
quality rejection
domain/ontology mismatch
verification failure
unknown
```

Do the same for a small L sample for comparison.

### 6. Scoped extraction effect on promotability

Compare L and S by type/relation distribution.

Answer:

```text
Did S create more duplicate/merge-prone mentions?
Did S create facts with lower confidence?
Did S create fewer corroborated facts?
Did S create facts with missing evidence links?
Did S create relationship rows that cannot be promoted because of schema gaps?
```

### 7. Hypothesis assessment

Evaluate the four recorded hypotheses:

```text
H1 gardener cycle gap
H2 corroboration threshold
H3 verification gate
H4 continued canonicalization archives candidates before promotion
```

For each, report:

```text
supported
rejected
inconclusive
evidence
```

Add any new hypothesis only if evidence supports it.

## Output

Produce a concise diagnostic report with:

```text
executive summary
root-cause candidate ranked list
evidence table
L vs S promotion eligibility table
archive reason sample table
relationship promotion blocker analysis
recommended next action
what remains unknown
```

## Stop conditions

Stop immediately and report if:

```text
diagnosis requires a DB mutation
diagnosis requires running VerificationWorker
diagnosis requires restarting workflows
diagnosis requires code changes
diagnosis finds an obvious one-line bug
```

Do not fix it in this task. Surface it for sign-off.

## Final report

Final report must include:

```text
whether Stage 2 remains blocked
whether a Gardener fix is needed before Stage 2
whether a VerificationWorker run is needed before Stage 2
whether relationship promotion is structurally blocked
whether S archive behavior is identity merge or quality rejection
```

## Standing constraints

Do not start Stage 2.

Do not run Nexus 100 scoring.

Do not run full S VerificationWorker.

Do not mutate DB.

Do not edit code.

Do not restart workflows.

Do not touch v2.

Do not edit `replit.md`.

## Stop condition

Stop after the Stage 1C diagnostic report.

Wait for sign-off.