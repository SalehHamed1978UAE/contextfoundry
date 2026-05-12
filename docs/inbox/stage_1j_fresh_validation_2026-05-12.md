# Stage 1J Decision — No Ontology Rollback, No Vault Deletion, Fresh Validation Next

## Alignment

- **Module touched:** decision only; next work is fresh validation vault
- **Product vs implementation:** implementation-level validation of the fixed ingestion path
- **Architecture-doc consistency:** follows Stage 1H / Stage 1I findings: IdentityResolver caused cross-tenant relationship contamination; fixes are loaded; next proof is fresh ingestion under current runtime
- **Drift risk:** turning Stage 1J into ontology rollback or vault cleanup instead of validating the fixed ingestion path
- **Out of scope:** ontology rollback, vault deletion, historical data repair, schema trigger, Stage 2, Nexus 100 scoring, VerificationWorker full run, ontology backfill, v2, `replit.md` edits

## Decision

Accept the Stage 1J ontology baseline investigation.

Choose **Option D**:

```text
No ontology rollback before Stage 1J fresh validation.

Do not delete existing vaults.

Do not decide or mutate the 8 orphan relation types now.

Proceed to fresh ingestion validation with legacy contaminated tenants preserved.

Accepted ontology investigation findings

Accepted:

Runtime uses ontology.types / ontology.relations, not public.ontology_*.
ontology.types has 1,037 rows.
The ~803 / ~804 ad-hoc-type concern is real in the live ontology schema.
ontology.relations has 254 rows.
public.ontology_* is legacy/dead relative to current runtime.
ontology.relations_backup_pre_piece_0_6 is not a clean baseline.
proposed_by / approved_by metadata is mostly absent.
ontology.versions and ontology.type_migrations are empty.
No clean rollback source exists today.

Why no ontology rollback now

Stage 1J’s purpose is not to clean the ontology.

Stage 1J’s purpose is:

Prove that the fixed ingestion / extraction / identity-resolution path no longer creates cross-tenant relationship endpoints.

Ontology rollback would be a separate governance project requiring:

missing baseline migration reconstruction
policy decisions for ad-hoc types
policy decisions for orphan relations
adaptive-growth policy
possibly disabling or routing adaptive ontology writes through governance

That is out of scope for Stage 1J.

Why no vault deletion now

Do not delete existing contaminated vaults before the fresh validation.

Reason:

The bug was cross-tenant merging into existing tenant entity spaces.
Leaving old tenants present makes the fresh validation stronger.

If the fresh tenant remains clean while old contaminated tenants still exist, the fix is stronger than it would be in an empty DB.

Existing vaults are not proof of correctness, but they are useful adversarial/forensic fixtures.

Orphan relation types

Defer decisions on:

FUNDED_BY
USES
HAS_SPEC
RELATED_TO
USES_MATERIAL
OWNED_BY
WORKS_FOR
FOCUSES_ON

Do not add them to ontology.relations.

Do not remap them.

Do not backfill them.

If fresh validation emits them, record them as ontology-validation gaps.

Next task: fresh ingestion validation

Create one fresh tenant/vault from the Nexus corpus using current fixed runtime.

Use Corpus Maker CLI with --no-extract, then run extraction explicitly.

Use the same raw Nexus source directory previously verified.

Do not use SQL clone.

Do not reuse old S/L/original Nexus vaults.

Do not delete old vaults.

Required pre-run checks

Before extraction, verify:

fresh tenant exists
fresh tenant_id recorded
documents = 100
entities = 0
relationships = 0
audit_records = 0
ontology.types = 1037
ontology.relations = 254
Start All is running fixed code
existing DB-wide cross-tenant relationship count recorded
existing contaminated tenant_ids recorded
latest cross-tenant relationship updated_at
latest identity_resolver merge_audit timestamp

The old contaminated tenants are intentionally preserved as adversarial fixtures.

Run extraction

Run extraction on the fresh tenant with:

CF_PIECE2_SCOPED_EXTRACTION=true

Use the current approved long-run mechanism if needed.

Do not run Nexus 100 scoring.

Post-extraction validation

After extraction completes and counts stabilize, report:

fresh tenant_id
documents processed
entities total
relationships total
relationships by lifecycle_state
entities by lifecycle_state
cross-tenant relationships total for fresh tenant
cross-tenant relationships by lifecycle_state for fresh tenant
endpoint tenant classification:
  both endpoints in fresh tenant
  source outside tenant
  target outside tenant
  both outside tenant
  missing source endpoint
  missing target endpoint
identity_resolver merges during run
cross-tenant identity_resolver merges during run
global ontology.types count
global ontology.relations count
ontology rows created/updated during run

Expected:

fresh tenant cross-tenant relationships = 0
fresh tenant cross-tenant identity_resolver merges = 0

If any fresh-tenant cross-tenant relationship appears, stop and report. The fix is incomplete.

Promotion validation

If fresh tenant cross-tenant relationships are zero, run one tenant-scoped promotion cycle on the fresh tenant.

Report:

entities by lifecycle_state before/after
relationships by lifecycle_state before/after
entity promotion delta
relationship promotion delta
block_reasons
errors
runtime
global ontology.types count
global ontology.relations count

Do not run multiple promotion cycles unless separately authorized.

Historical data status

Do not repair historical vaults in this task.

Do not delete historical vaults in this task.

Record:

Historical DB-wide cross-tenant relationships remain a separate hygiene task.
Old S/L/original Nexus vaults are contaminated diagnostic artifacts, not proof of clean ingestion.
They are intentionally preserved during this validation to prove the fixed pipeline does not merge across tenant boundaries even when old tenant data exists.

Findings doc update

Update:

docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md

Add:

Stage 1J ontology baseline investigation accepted
Option D selected
ontology rollback deferred
legacy vault deletion deferred
fresh tenant_id
legacy contaminated tenants preserved as adversarial fixtures
fresh-ingestion validation result
fresh tenant cross-tenant relationship count
identity_resolver merge result
promotion result
orphan relation types recorded as future ontology-governance work
whether Stage 2 remains blocked

Stop triggers

Stop and report if:

fresh ingestion creates any cross-tenant relationship
fresh identity resolver creates any cross-tenant merge
global ontology changes unexpectedly
extraction requires schema mutation
promotion fails with a new blocker
workflow creation requires deleting evidence

Standing constraints

Do not start Stage 2.

Do not run Nexus 100 scoring.

Do not repair historical data.

Do not delete existing vaults.

Do not mutate DB except normal fresh-ingestion/extraction/promotion outputs for the new tenant.

Do not add schema trigger.

Do not backfill relationships.

Do not roll back ontology.

Do not add or modify orphan relation types.

Do not touch v2.

Do not edit replit.md.

Final report

Report:

fresh tenant_id
pre-run checks
extraction metrics
fresh tenant cross-tenant endpoint validation
identity_resolver merge validation
promotion metrics
block_reasons/errors
global ontology substrate check
whether clean ingestion is validated
whether historical data repair/deletion is still needed
whether ontology rollback remains deferred
whether Stage 2 remains blocked

Stop condition

Stop after the fresh-ingestion validation and single promotion-cycle report.

Wait for sign-off.