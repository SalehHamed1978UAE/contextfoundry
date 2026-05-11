# Stage 1H — Tenant Isolation Root-Cause Audit for Cross-Tenant Relationship Endpoints

## Alignment

- **Module touched:** read-only diagnosis of relationship endpoint tenant isolation; possible source-path audit in staging/canonicalization code
- **Product vs implementation:** implementation-level diagnosis before any repair, scheduler activation, or Stage 2 default activation
- **Architecture-doc consistency:** follows Stage 1G follow-up result: scoped extraction and promotion mechanics work, but S relationship rows are structurally entangled with other tenants and cannot promote under tenant-scoped RLS
- **Drift risk:** continuing promotion cycles when most S relationships can never become endpoint-eligible; fixing Gardener when Gardener is correctly fail-closing on invisible cross-tenant endpoints; applying data repair before knowing where the cross-tenant links were introduced
- **Out of scope:** DB mutations, data repair, schema constraints, code fixes, scheduler activation, Stage 2 implementation, Nexus 100 scoring, VerificationWorker full run, ontology backfill, v2 work, `replit.md` edits

## Accepted finding

Accept the Stage 1G follow-up result.

H11 is rejected:

```text
The batched endpoint lookup is not the root cause.
````

H12 is confirmed:

```text
S relationships contain cross-tenant endpoint references.
```

Key facts:

```text
S STAGING relationships: 1150
Both endpoints visible + TRUSTED under actual S tenant/RLS context: 24
Both endpoints TRUSTED under admin/global context: 179
Cross-tenant endpoint relationships: 665 / 1150 = 58%
Most cross-tenant endpoints point to:
  - L vault: f38e400f-...
  - original Nexus vault: 176a4fb2-...
```

Interpretation:

```text
Gardener is behaving correctly under tenant-scoped RLS.
Those relationships cannot promote because at least one endpoint is not visible inside S.
The problem is upstream relationship construction / canonicalization / entity resolution / data setup.
```

Do not run more promotion cycles.

Do not run Cycle 3.

Do not start scheduler.

Do not start Stage 2.

## Goal

Find where cross-tenant relationship endpoints are introduced.

Answer:

```text
Are S relationships created with cross-tenant endpoints during extraction/staging?
Are they created by canonicalization / identity-resolution after staging?
Are they copied or inherited from the old Nexus or L vault during corpus setup?
Are relationships being retargeted to canonical entities across tenants?
Is there any missing tenant filter in entity lookup / relationship creation code?
```

## Required read-only DB diagnostics

Run read-only queries only.

### 1. Full cross-tenant endpoint census

For S vault:

```text
relationships total by lifecycle_state
relationships by endpoint tenant classification:
  both endpoints in S
  source in S, target outside S
  source outside S, target in S
  both endpoints outside S
  missing source endpoint
  missing target endpoint
```

For each bucket, report:

```text
relationship count
relationship_type distribution
lifecycle_state distribution
created_at min/max
updated_at min/max
source_document_id coverage
evidence_records coverage
top endpoint tenant_ids
```

### 2. Creation-time analysis

For cross-tenant relationships, report:

```text
created_at distribution
created_at relative to S extraction start/end
created_at relative to L extraction start/end
created_at relative to original Nexus vault
updated_at distribution
whether source_id / target_id changed after creation if audit trail exists
```

Goal:

```text
Determine whether cross-tenant endpoints were inserted initially or introduced later by canonicalization/merge.
```

### 3. Source-document analysis

For cross-tenant relationships, join to documents/evidence if possible and report:

```text
relationship tenant_id
source_document_id tenant_id
source document filename
evidence span / evidence record tenant_id if present
source entity tenant_id
target entity tenant_id
relationship_type
raw_relationship_type
```

Goal:

```text
Determine whether the relationship itself belongs to S docs but points to non-S entities, or whether the relationship/source doc is also cross-tenant contaminated.
```

### 4. Entity-name equivalence check

For cross-tenant endpoints pointing into L or original Nexus, check whether S has an equivalent entity by name/type.

For a sample and aggregate:

```text
cross-tenant endpoint entity name
cross-tenant endpoint entity_type
cross-tenant endpoint tenant_id
matching S entity count by same normalized name/type
matching S entity lifecycle_state
matching S entity id if unique
```

Goal:

```text
Determine whether repair would be remap-to-S-equivalent vs re-extract vs archive.
```

### 5. Constraint check

Inspect schema constraints and indexes for:

```text
relationships.source_id FK
relationships.target_id FK
relationships.tenant_id
entities.tenant_id
any trigger enforcing source/target entity tenant == relationship tenant
any RLS policy relevant to relationship endpoint integrity
```

Answer:

```text
Does the database currently permit relationships whose tenant_id differs from endpoint entity tenant_id?
Is there any DB-level guard against this?
```

## Required code-path audit

Read code only. Do not edit.

Search and inspect:

```text
src/context_foundry/extraction/staging_loader.py
src/context_foundry/extraction/ontology_centric_pipeline.py
src/context_foundry/extraction/canonicalizer.py
src/context_foundry/extraction/*relationship*
src/context_foundry/agents/*relationship*
scripts/run_vault_extraction.py
src/corpus_maker/
```

Find all code paths that:

```text
insert relationships
update relationships.source_id
update relationships.target_id
canonicalize entities
merge entities
resolve entity mentions to canonical entities
look up entities by name/type before relationship insertion
copy documents/chunks/entities/relationships across tenants
```

For each path, report whether it filters by tenant_id.

Specific questions:

1. Does relationship staging resolve endpoints by name globally instead of tenant-scoped?
2. Does canonicalization merge entities across tenant boundaries?
3. Does identity resolution rewrite relationship endpoints to canonical entities from another tenant?
4. Does Corpus Maker or upload/copy logic copy relationships or entities from an existing vault?
5. Does any query use entity name/type lookup without `tenant_id = current_tenant`?
6. Does any update retarget relationship endpoints without tenant guard?
7. Does any `ON CONFLICT` or canonical lookup prefer an existing global entity over a tenant-local one?

## Required result classification

Classify root cause as one of:

```text
A. Extraction/staging endpoint resolution missing tenant filter
B. Canonicalization / identity-resolution cross-tenant merge
C. Corpus setup / clone contamination
D. Relationship endpoint retargeting bug
E. Database constraint gap only — code path unclear
F. Mixed cause
G. Inconclusive
```

## Repair plan only — do not execute

Prepare a repair plan, but do not run it.

The repair plan should include:

### Code fix options

Examples:

```text
tenant-scope endpoint lookup during relationship staging
tenant-scope canonical entity resolution
prevent cross-tenant relationship endpoint rewrites
fail-fast check before relationship insert/update if endpoint tenant differs
```

### Data repair options

Examples:

```text
remap cross-tenant endpoints to matching S entities by normalized name/type
archive cross-tenant relationships and re-run extraction after code fix
delete/re-stage only S relationship rows after code fix
rebuild S vault from raw docs after code fix
```

### Schema guard options

Examples:

```text
trigger enforcing relationship.tenant_id == source_entity.tenant_id and target_entity.tenant_id
application-level invariant test if DB trigger is too heavy
RLS policy review
```

Do not apply any repair.

Do not mutate data.

Do not create schema guards.

Do not change code.

## Required tests to propose

Propose tests that would catch this defect:

```text
relationship insertion cannot target entities from another tenant
canonicalization cannot rewrite relationship endpoints across tenants
identity-resolution merge remains tenant-scoped
tenant-scoped extraction of identical corpus into L and S produces relationships whose endpoints stay inside each respective tenant
Gardener endpoint visibility count matches DB tenant-scoped eligibility count
```

Do not write tests in this task unless you explicitly stop and ask first.

## Findings doc update

Update:

```text
docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md
```

Add:

```text
Stage 1H cross-tenant endpoint finding
H11 rejected
H12 confirmed and quantified
tenant endpoint classification table
root-cause classification
repair plan options
Stage 2 readiness impact
```

## Standing constraints

Do not start Stage 2.

Do not run more promotion cycles.

Do not start scheduler.

Do not run Nexus 100 scoring.

Do not run VerificationWorker.

Do not mutate DB.

Do not edit code.

Do not create schema constraints.

Do not backfill ontology.

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
cross-tenant endpoint census
creation-time analysis
source-document/evidence analysis
entity-name equivalence findings
schema/constraint findings
code-path audit findings with file:line references
root-cause classification
repair plan options
test plan
Stage 2 readiness verdict
recommended next action
```

## Stop condition

Stop after the Stage 1H report.

Wait for sign-off.