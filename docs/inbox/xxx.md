
# Stage_1J—Fresh_Ingestion_Validation_After_IdentityResolver_Fix

## Alignment

- **Module touched:** fresh validation vault only; no historical-vault repair or deletion
- **Product vs implementation:** implementation-level validation of the fixed ingestion/extraction/promotion path
- **Architecture-doc consistency:** follows Stage 1H / Stage 1I findings: IdentityResolver caused historical cross-tenant relationship contamination; fixes are now loaded in runtime; next proof is fresh ingestion, not historical repair
- **Drift risk:** deleting forensic evidence before validating the fixed pipeline; repairing old polluted data and mistaking that for clean ingestion; over-cleaning the environment and making the validation less realistic
- **Out of scope:** deleting existing vaults, historical backfill, DB-wide repair, schema trigger, Stage 2, Nexus 100 scoring, VerificationWorker full run, ontology backfill, v2 work, `replit.md` edits

## Decision

Pause Phase 3 historical backfill.

Do **not** delete existing vaults.

The next proof is a fresh ingestion validation.

Existing vaults are contaminated historical artifacts. They should not be used as proof that the pipeline now works. But they remain useful forensic evidence and should not be deleted yet.

## Rationale

Repairing old contaminated vaults answers:

```text
Can we salvage old polluted diagnostic data?

Fresh validation answers the product question:

Does the fixed ingestion pipeline now produce tenant-local relationships?

The second question matters more right now.

Keeping old contaminated vaults in place makes the fresh validation stronger: the new tenant must remain clean even while legacy contaminated tenants still exist in the database.

Task

Create one fresh tenant/vault from the Nexus corpus using the current fixed runtime.

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
latest cross-tenant relationship updated_at remains from before Phase 1.6 unless this fresh run creates new rows
latest identity_resolver merge_audit remains from before Phase 1.6 unless this fresh run creates new rows

Run extraction

Run extraction on the fresh tenant.

Use the current intended scoped path:

CF_PIECE2_SCOPED_EXTRACTION=true

If the workflow system is needed for the long-running extraction, use the current approved one-shot workflow pattern.

Do not run Nexus 100 scoring.

Post-extraction validation

After extraction completes and counts stabilize, report:

fresh tenant_id
documents processed
entities total
relationships total
relationships by lifecycle_state
entities by lifecycle_state
cross-tenant relationships total
cross-tenant relationships by lifecycle_state
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

Expected result:

cross-tenant relationships = 0
cross-tenant identity_resolver merges = 0
ontology unchanged unless explicitly expected and reported

If any cross-tenant relationship appears, stop and report. The fix is incomplete.

Promotion validation

If cross-tenant relationships are zero, run one tenant-scoped promotion cycle on the fresh tenant.

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
They remain preserved for forensic comparison until a separate deletion/archive policy is approved.

Findings doc update

Update:

docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md

Add:

Stage 1J pivot rationale
fresh tenant_id
fresh-ingestion validation result
cross-tenant relationship count on fresh tenant
identity_resolver merge result
promotion result
whether historical repair is still needed
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

Do not touch v2.

Do not edit replit.md.

Final report

Report:

fresh tenant_id
pre-run checks
extraction metrics
cross-tenant endpoint validation
identity_resolver merge validation
promotion metrics
block_reasons/errors
global ontology substrate check
whether clean ingestion is validated
whether historical data repair/deletion is still needed
whether Stage 2 remains blocked

Stop condition

Stop after the fresh-ingestion validation and single promotion-cycle report.

Wait for sign-off.

SEND TO REPLIT — END

## Bottom line

Claude is right about the core insight:

```text
Do not polish contaminated diagnostic vaults.
Validate the fixed pipeline on a fresh vault.

But I would not delete all existing vaults yet.

The clean move is:

fresh validation first
then decide whether old vaults should be archived, repaired, or deleted

If the fresh vault comes out clean, then you have your proof that ingestion is fixed. Historical cleanup becomes optional hygiene, not the proof of correctness.