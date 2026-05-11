# Stage 1H Follow-up — Identify Cross-Tenant Relationship Writer, Then Stop for Triage

## Alignment

- **Module touched:** read-only audit of unaudited relationship endpoint mutation paths
- **Product vs implementation:** implementation-level diagnosis before any repair, schema guard, scheduler activation, or Stage 2
- **Architecture-doc consistency:** follows Stage 1H finding: scoped extraction and promotion can work, but relationship endpoints are cross-tenant contaminated and cannot safely promote under tenant-scoped RLS
- **Drift risk:** letting Piece 2 keep expanding into repair work without triage; repairing symptoms before identifying the writer; adding constraints or backfills before root cause is known
- **Out of scope:** DB mutations, code edits, schema triggers, data repair, scheduler activation, Stage 2 implementation, Nexus 100 scoring, VerificationWorker full run, ontology backfill, v2 work, `replit.md` edits

## Decision

Stage 1H audit is accepted.

H12 is confirmed:

```text
S relationships contain cross-tenant endpoint references.
Gardener is correctly fail-closing under tenant-scoped RLS.
Promotion cannot converge until relationship endpoints are tenant-safe.
````

Do **not** repair yet.

Do **not** add constraint trigger yet.

Do **not** backfill yet.

Continue read-only audit only long enough to identify the writer.

After that, stop for scope triage.

## Priority order

Audit these paths in order:

```text
1. workers/verification_worker.py
2. agents/gardener.py
3. agents/relationship_inference.py
4. extraction/multi_extractor.py
5. extraction/relation_extractor.py
```

Reason:

```text
100% of cross-tenant relationships were modified after create with ~13-minute lag.
That points to a post-extraction pass more than initial staging.
```

## Required audit questions

For each suspect path, answer:

```text
Does it update relationships.source_id?
Does it update relationships.target_id?
Does it insert relationships?
Does it rewrite relationship endpoints after creation?
Does it resolve entity mentions to canonical entities?
Does it use canonical_entity_id / duplicate_of / merged_into / normalized name lookup?
Does every entity lookup filter by tenant_id?
Does every relationship update guard endpoint entity tenant == relationship tenant?
Does it run in the observed post-create lag window?
```

## Additional code-search targets

Search for:

```text
source_id =
target_id =
UPDATE relationships
INSERT INTO relationships
relationship.source_id
relationship.target_id
canonical_entity
duplicate_of
merged_into
entity_id replacement
resolve_entity
find_entity_by_name
normalized_name
relationship endpoint
```

For every relevant match, classify:

```text
tenant-scoped safe
tenant-scoped unsafe
not on this path
unclear
```

## Required DB diagnostics

Keep read-only.

### 1. L comparison

Quantify L vault cross-tenant percentage for comparison with S:

```text
L total relationships
L cross-tenant relationships
L cross-tenant percentage
L cross-tenant by lifecycle_state
L endpoint tenant distribution
```

Interpretation:

```text
If L has similar proportions, this is system-wide and longstanding.
If L is cleaner, the bug may be specific to sequential L→S extraction or second-vault dynamics.
```

### 2. Modified-after-create timing

For S cross-tenant relationships, report:

```text
created_at min/max
updated_at min/max
updated_at - created_at distribution
top update timestamps
which process logs/events align with those timestamps
```

### 3. Process correlation

Check logs/tables around the lag window:

```text
verification_worker logs
gardener_logs
relationship inference logs
extraction_events
audit_records
run manifests
```

Goal:

```text
Identify which process ran during the endpoint-retarget window.
```

### 4. Canonical entity / merge-target analysis

For cross-tenant endpoints, report whether endpoint entities are:

```text
canonical merge targets
duplicate targets
identity-resolution winners
entities with same normalized name/type as S entities
entities created before S extraction
entities updated during S extraction
```

## Root-cause classification

Classify final root cause as one of:

```text
A. VerificationWorker retargets relationship endpoints cross-tenant
B. Gardener / identity resolution retargets relationship endpoints cross-tenant
C. Relationship inference creates cross-tenant relationships
D. MultiModel / relation extractor creates cross-tenant relationships directly
E. Corpus setup contamination
F. DB constraint gap only, exact writer still unknown
G. Mixed cause
H. Inconclusive
```

## Repair plan only — do not execute

Prepare a repair plan, but do not run it.

Use this sequence unless evidence strongly argues otherwise:

```text
Phase 1: code fix to stop new poisoning
Phase 2: prevention check / invariant test
Phase 3: repair existing S data
Phase 4: DB trigger or constraint after data is clean
```

Do not recommend trigger-first unless you can prove it will not break extraction.

Do not recommend backfill-first unless you can prove the offending path cannot run again.

## Multi-candidate endpoint disposition

For now:

```text
746 unique S-equivalent endpoints = repairable candidates after code fix.
12 multi-candidate endpoints = quarantine for later review.
```

Do not use LLM disambiguation yet.

Do not manually resolve all 12 yet.

You may sample 2–3 of the 12 if useful to understand the failure mode, but do not mutate anything.

## Test plan to propose

Propose tests for the eventual fix:

```text
relationship insert cannot target entities from another tenant
relationship update cannot retarget endpoints across tenants
canonicalization cannot choose cross-tenant endpoint
verification_worker cannot rewrite endpoints across tenants
identity-resolution merge remains tenant-scoped
two fresh tenants with same corpus produce tenant-local endpoints
Gardener endpoint visibility count matches tenant-scoped DB eligibility
```

Do not write tests in this read-only task.

## Findings doc update

Update:

```text
docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md
```

Add:

```text
Stage 1H follow-up audit
L-vs-S cross-tenant comparison
unaudited path findings
modified-after-create timing
suspect process correlation
root-cause classification
repair sequencing recommendation
multi-candidate endpoint disposition
Stage 2 readiness verdict
```

## Final triage requirement

After this audit, stop and classify all discovered issues into:

```text
Must fix before Stage 2
Can defer with known limitation
Future architecture / Piece 3+
```

Do not begin any fix in the same turn.

## Standing constraints

Do not start Stage 2.

Do not run more promotion cycles.

Do not start scheduler.

Do not run Nexus 100 scoring.

Do not run VerificationWorker full pass.

Do not mutate DB.

Do not edit code.

Do not create schema constraints.

Do not backfill ontology.

Do not repair relationship endpoints.

Do not touch v2.

Do not edit `replit.md`.

## Stop triggers

Stop and report if:

```text
diagnosis requires data mutation
diagnosis requires schema mutation
diagnosis requires code edit
you find an obvious one-line code bug
you find data corruption outside S/L/original Nexus
root cause spans multiple subsystems and needs design decision
```

## Final report

Report:

```text
executive summary
L-vs-S cross-tenant comparison
suspect path audit table
DB timing/correlation analysis
code-path findings with file:line references
root-cause classification
repair sequencing recommendation
test plan
must-fix vs defer vs future triage
whether Stage 2 remains blocked
recommended next action
```

## Stop condition

Stop after the Stage 1H follow-up report.

Wait for sign-off.

SEND TO REPLIT — END

````

Bottom line:

```text
Keep going, but only through root-cause identification.
Then pause and triage.
No repair yet.
No trigger yet.
No backfill yet.
````
